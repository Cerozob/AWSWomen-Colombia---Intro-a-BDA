"""Regla de EventBridge + máquina de estados `flujo-procesar-cv` (JSONata, pasos nativos de BDA).

La máquina se arma con constructs de CDK en JSONata; BDA se invoca y se consulta con
integraciones aws-sdk (`CallAwsService`), sin Lambda de por medio.
"""

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_logs as logs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

from bda_ats.config import Config
from bda_ats.constructos.almacenamiento import PREFIJO_BDA, PREFIJO_ENTRADA, Almacenamiento
from bda_ats.constructos.bda import Bda
from bda_ats.constructos.funcion_python import FuncionPython

ERRORES_BDA_REINTENTABLES = [
    "BedrockDataAutomationRuntime.ThrottlingException",
    "BedrockDataAutomationRuntime.InternalServerException",
]
EN_CURSO = "$bda.Status in ['Created', 'InProgress']"


def _motivo(paso: str) -> dict[str, str]:
    """Assign para un Catch: guarda qué paso falló y por qué."""
    return {"motivo": f"{{% '{paso}: ' & $states.errorOutput.Error & ' ' & $states.errorOutput.Cause %}}"}


def _evento(etapa: str | tasks.DynamoAttributeValue) -> tasks.DynamoAttributeValue:
    """Elemento para `historial` (lista de {etapa, en})."""
    valor = (
        etapa
        if isinstance(etapa, tasks.DynamoAttributeValue)
        else tasks.DynamoAttributeValue.from_string(etapa)
    )
    return tasks.DynamoAttributeValue.from_list(
        [
            tasks.DynamoAttributeValue.from_map(
                {"etapa": valor, "en": tasks.DynamoAttributeValue.from_string("{% $now() %}")}
            )
        ]
    )


class Flujo(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        config: Config,
        almacenamiento: Almacenamiento,
        bda: Bda,
    ) -> None:
        super().__init__(scope, id)
        stack = Stack.of(self)
        a = almacenamiento

        self.preprocesar = FuncionPython(
            self,
            "Preprocesar",
            nombre="preprocesar",
            descripcion="Valida la hoja de vida y registra el documento antes de enviarlo a BDA",
            entorno={"TABLA_SEGUIMIENTO": a.seguimiento.table_name},
        ).funcion
        a.cvs.grant_read(self.preprocesar, f"{PREFIJO_ENTRADA}*")
        a.seguimiento.grant(self.preprocesar, "dynamodb:UpdateItem")

        self.postprocesar = FuncionPython(
            self,
            "Postprocesar",
            nombre="postprocesar",
            descripcion="Lee la salida de BDA y guarda el perfil estructurado",
            timeout_s=60,
            entorno={
                "TABLA_SEGUIMIENTO": a.seguimiento.table_name,
                "TABLA_RESULTADOS": a.resultados.table_name,
                "UMBRAL_CONFIANZA": str(config.confianza_media),
                "PRECIO_DOC_CUSTOM": str(config.precio_documento_pagina),
                "PRECIO_IMG_CUSTOM": str(config.precio_imagen),
            },
        ).funcion
        a.resultados_bda.grant_read(self.postprocesar, f"{PREFIJO_BDA}*")
        a.resultados.grant(self.postprocesar, "dynamodb:PutItem")
        a.seguimiento.grant(self.postprocesar, "dynamodb:UpdateItem", "dynamodb:GetItem")

        definicion = self._definicion(config, a, bda, stack)

        logs_maquina = logs.LogGroup(
            self,
            "LogsMaquina",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.maquina = sfn.StateMachine(
            self,
            "Maquina",
            state_machine_name=f"{config.prefijo}-flujo-procesar-cv",
            state_machine_type=sfn.StateMachineType.STANDARD,
            query_language=sfn.QueryLanguage.JSONATA,
            comment="Procesa una hoja de vida con Bedrock Data Automation (pasos nativos, sin Lambda).",
            definition_body=sfn.DefinitionBody.from_chainable(definicion),
            tracing_enabled=True,
            logs=sfn.LogOptions(
                destination=logs_maquina,
                level=sfn.LogLevel.ERROR,
                include_execution_data=True,
            ),
        )

        # BDA lee la entrada y escribe la salida con la identidad de quien lo invoca (este rol).
        a.cvs.grant_read(self.maquina, f"{PREFIJO_ENTRADA}*")
        a.resultados_bda.grant_put(self.maquina, f"{PREFIJO_BDA}*")

        events.Rule(
            self,
            "NuevaHojaDeVida",
            description="Inicia flujo-procesar-cv cuando llega un archivo a entrada/",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [a.cvs.bucket_name]},
                    "object": {"key": [{"prefix": PREFIJO_ENTRADA}]},
                },
            ),
            targets=[targets.SfnStateMachine(self.maquina)],
        )

    def _definicion(self, config: Config, a: Almacenamiento, bda: Bda, stack: Stack) -> sfn.IChainable:
        texto = tasks.DynamoAttributeValue.from_string
        llave = {"documentoId": texto("{% $documentoId %}")}

        # --- Fin con error: guarda el motivo en Seguimiento y termina en Fail ---
        fallo = sfn.Fail.jsonata(
            self, "Fallo", error="ProcesamientoFallido", cause="{% $substring($motivo, 0, 1000) %}"
        )
        marcar_fallido = tasks.DynamoUpdateItem.jsonata(
            self,
            "MarcarFallido",
            table=a.seguimiento,
            key=llave,
            update_expression=(
                "SET estado = :estado, etapa = :estado, motivo = :motivo, actualizadoEn = :ahora, "
                "historial = list_append(if_not_exists(historial, :vacio), :evento)"
            ),
            expression_attribute_values={
                ":estado": texto("FALLIDO"),
                ":motivo": texto("{% $substring($motivo, 0, 1000) %}"),
                ":ahora": texto("{% $now() %}"),
                ":vacio": tasks.DynamoAttributeValue.from_list([]),
                ":evento": _evento("FALLIDO"),
            },
        ).next(fallo)

        def con_catch(tarea: sfn.TaskStateBase, nombre: str) -> sfn.TaskStateBase:
            return tarea.add_catch(marcar_fallido, errors=["States.ALL"], assign=_motivo(nombre))

        # --- Inicio: el documentoId va en el nombre del archivo entrada/{usuarioId}/{documentoId}.{ext} ---
        inicio = sfn.Pass.jsonata(
            self,
            "Inicio",
            assign={
                "bucket": "{% $states.input.detail.bucket.name %}",
                "llave": "{% $states.input.detail.object.key %}",
                "documentoId": (
                    "{% $substringBefore($split($states.input.detail.object.key, '/')[-1], '.') %}"
                ),
                "vueltas": 0,
                "motivo": "",
            },
        )

        preprocesar = con_catch(
            tasks.LambdaInvoke.jsonata(
                self,
                "PasoPreprocesar",
                # Mismo nombre de estado que la Lambda; el id del construct no puede repetirse.
                state_name="Preprocesar",
                lambda_function=self.preprocesar,
                payload=sfn.TaskInput.from_object(
                    {
                        "bucket": "{% $bucket %}",
                        "llave": "{% $llave %}",
                        "documentoId": "{% $documentoId %}",
                        "ejecucionArn": "{% $states.context.Execution.Id %}",
                    }
                ),
                outputs="{% $states.result.Payload %}",
                assign={
                    "motivo": "{% $states.result.Payload.motivo ? $states.result.Payload.motivo : '' %}"
                },
            ).add_retry(
                errors=["Lambda.TooManyRequestsException"],
                interval=Duration.seconds(2),
                max_attempts=3,
                backoff_rate=2,
            ),
            "Preprocesar",
        )

        # --- BDA: paso nativo; ClientToken = documentoId evita jobs duplicados si se reintenta ---
        invocar_bda = con_catch(
            tasks.CallAwsService.jsonata(
                self,
                "InvocarBDA",
                service="bedrockdataautomationruntime",
                action="invokeDataAutomationAsync",
                parameters={
                    "InputConfiguration": {"S3Uri": "{% 's3://' & $bucket & '/' & $llave %}"},
                    "OutputConfiguration": {
                        "S3Uri": f"{{% 's3://{a.resultados_bda.bucket_name}/{PREFIJO_BDA}' & $documentoId %}}"
                    },
                    "DataAutomationConfiguration": {
                        "DataAutomationProjectArn": bda.proyecto_arn,
                        "Stage": "LIVE",
                    },
                    "DataAutomationProfileArn": bda.perfil_arn,
                    "ClientToken": "{% $documentoId %}",
                },
                iam_action="bedrock:InvokeDataAutomationAsync",
                # El perfil es cross-Region: BDA puede atender el job desde otra región de la geografía.
                iam_resources=[bda.proyecto_arn, bda.perfil_arn_iam, bda.blueprint.attr_blueprint_arn],
                assign={"invocationArn": "{% $states.result.InvocationArn %}"},
            ).add_retry(
                errors=ERRORES_BDA_REINTENTABLES,
                interval=Duration.seconds(2),
                max_attempts=3,
                backoff_rate=2,
            ),
            "InvocarBDA",
        )

        registrar_en_bda = con_catch(
            tasks.DynamoUpdateItem.jsonata(
                self,
                "RegistrarEnBda",
                table=a.seguimiento,
                key=llave,
                update_expression=(
                    "SET invocationArn = :arn, etapa = :etapa, actualizadoEn = :ahora, "
                    "historial = list_append(if_not_exists(historial, :vacio), :evento)"
                ),
                expression_attribute_values={
                    ":arn": texto("{% $invocationArn %}"),
                    ":etapa": texto("EN_BDA"),
                    ":ahora": texto("{% $now() %}"),
                    ":vacio": tasks.DynamoAttributeValue.from_list([]),
                    ":evento": _evento("EN_BDA"),
                },
            ),
            "RegistrarEnBda",
        )

        esperar_bda = sfn.Wait.jsonata(
            self, "EsperarBda", time=sfn.WaitTime.duration(Duration.seconds(config.segundos_espera))
        )

        consultar_estado = con_catch(
            tasks.CallAwsService.jsonata(
                self,
                "ConsultarEstadoBda",
                service="bedrockdataautomationruntime",
                action="getDataAutomationStatus",
                parameters={"InvocationArn": "{% $invocationArn %}"},
                iam_action="bedrock:GetDataAutomationStatus",
                iam_resources=[
                    stack.format_arn(
                        service="bedrock", resource="data-automation-invocation", resource_name="*"
                    )
                ],
                assign={"vueltas": "{% $vueltas + 1 %}", "bda": "{% $states.result %}"},
            ).add_retry(
                errors=ERRORES_BDA_REINTENTABLES,
                interval=Duration.seconds(2),
                max_attempts=3,
                backoff_rate=2,
            ),
            "ConsultarEstadoBda",
        )

        postprocesar = con_catch(
            tasks.LambdaInvoke.jsonata(
                self,
                "PasoPostprocesar",
                # Mismo nombre de estado que la Lambda; el id del construct no puede repetirse.
                state_name="Postprocesar",
                lambda_function=self.postprocesar,
                payload=sfn.TaskInput.from_object(
                    {
                        "documentoId": "{% $documentoId %}",
                        "rutaMetadatos": "{% $bda.OutputConfiguration.S3Uri %}",
                        "vueltasSondeo": "{% $vueltas %}",
                    }
                ),
                outputs="{% $states.result.Payload %}",
            ).add_retry(
                errors=["Lambda.TooManyRequestsException"],
                interval=Duration.seconds(2),
                max_attempts=3,
                backoff_rate=2,
            ),
            "Postprocesar",
        ).next(sfn.Succeed.jsonata(self, "Fin"))

        # ClientError / ServiceError: se guarda el mensaje que devolvió BDA.
        marcar_fallido_bda = sfn.Pass.jsonata(
            self,
            "MarcarFallidoBda",
            assign={"motivo": "{% 'BDA ' & $bda.Status & ': ' & $bda.ErrorType & ' ' & $bda.ErrorMessage %}"},
        ).next(marcar_fallido)

        estado_bda = (
            sfn.Choice.jsonata(self, "EstadoBda")
            .when(sfn.Condition.jsonata("{% $bda.Status = 'Success' %}"), postprocesar)
            .when(
                sfn.Condition.jsonata(f"{{% {EN_CURSO} and $vueltas < {config.max_vueltas} %}}"),
                esperar_bda,
            )
            .when(
                sfn.Condition.jsonata(f"{{% {EN_CURSO} %}}"),
                marcar_fallido,
                assign={"motivo": "{% 'BDA no terminó después de ' & $string($vueltas) & ' consultas' %}"},
            )
            .otherwise(marcar_fallido_bda)
        )

        es_valido = (
            sfn.Choice.jsonata(self, "EsValido")
            .when(sfn.Condition.jsonata("{% $states.input.valido = true %}"), invocar_bda)
            .otherwise(marcar_fallido)
        )

        invocar_bda.next(registrar_en_bda).next(esperar_bda).next(consultar_estado).next(estado_bda)
        return inicio.next(preprocesar).next(es_valido)
