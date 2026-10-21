import json
from pathlib import Path

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template
from bda_ats import config as modulo_config
from bda_ats.config import RAIZ, ErrorConfig

EJEMPLO = RAIZ / "config.json.example"


@pytest.fixture(scope="module")
def plantilla():
    import os

    os.environ["BDA_ATS_CONFIG"] = str(EJEMPLO)
    import app as entrada

    app = cdk.App(context={"omitirFrontend": "true"})
    entrada.construir_app(app)
    return Template.from_stack(app.node.find_child("BdaAtsStack"))


def _definicion(plantilla) -> dict:
    """ASL que CDK genera a partir de los constructs (los tokens de CloudFormation se vuelven texto)."""
    maquina = next(iter(plantilla.find_resources("AWS::StepFunctions::StateMachine").values()))
    definicion = maquina["Properties"]["DefinitionString"]
    if isinstance(definicion, dict):
        partes = definicion["Fn::Join"][1]
        definicion = "".join(p if isinstance(p, str) else json.dumps(p).replace('"', "'") for p in partes)
    return json.loads(definicion)


def test_maquina_jsonata_con_pasos_nativos_de_bda(plantilla):
    asl = _definicion(plantilla)
    assert asl["QueryLanguage"] == "JSONata"
    estados = asl["States"]
    assert set(estados) == {
        "Inicio", "Preprocesar", "EsValido", "InvocarBDA", "RegistrarEnBda", "EsperarBda",
        "ConsultarEstadoBda", "EstadoBda", "MarcarFallidoBda", "Postprocesar", "MarcarFallido",
        "Fin", "Fallo",
    }
    assert estados["InvocarBDA"]["Resource"].endswith(
        "aws-sdk:bedrockdataautomationruntime:invokeDataAutomationAsync"
    )
    assert estados["ConsultarEstadoBda"]["Resource"].endswith(
        "aws-sdk:bedrockdataautomationruntime:getDataAutomationStatus"
    )
    assert estados["EsperarBda"]["Next"] == "ConsultarEstadoBda"
    assert estados["ConsultarEstadoBda"]["Next"] == "EstadoBda"
    # Todos los Task terminan en MarcarFallido si algo falla, no se quedan colgados.
    for nombre, estado in estados.items():
        if estado["Type"] == "Task" and nombre != "MarcarFallido":
            assert estado["Catch"][0]["Next"] == "MarcarFallido", nombre


def test_dos_buckets_y_solo_el_de_cvs_con_eventbridge(plantilla):
    buckets = plantilla.find_resources("AWS::S3::Bucket")
    # CDK activa EventBridge con un recurso personalizado, no en las propiedades del bucket.
    notificaciones = plantilla.find_resources("Custom::S3BucketNotifications")
    con_eventos = [
        n for n in notificaciones.values()
        if "EventBridgeConfiguration" in n["Properties"]["NotificationConfiguration"]
    ]
    assert len(buckets) == 3  # cvs, resultados de BDA y sitio
    assert len(con_eventos) == 1


def test_lambdas_python_313_arm(plantilla):
    funciones = plantilla.find_resources(
        "AWS::Lambda::Function", {"Properties": {"Runtime": "python3.13", "Handler": "app.handler"}}
    )
    assert len(funciones) == 9
    for f in funciones.values():
        assert f["Properties"]["Architectures"] == ["arm64"]


def test_regla_eventbridge_filtra_prefijo_entrada(plantilla):
    plantilla.has_resource_properties(
        "AWS::Events::Rule",
        {
            "EventPattern": {
                "source": ["aws.s3"],
                "detail-type": ["Object Created"],
                "detail": {"object": {"key": [{"prefix": "entrada/"}]}},
            }
        },
    )


def test_rol_de_la_maquina_puede_llamar_bda(plantilla):
    politicas = json.dumps(plantilla.find_resources("AWS::IAM::Policy"))
    assert "bedrock:InvokeDataAutomationAsync" in politicas
    assert "bedrock:GetDataAutomationStatus" in politicas
    assert "data-automation-profile/us.data-automation-v1" in politicas


def test_proyecto_bda_usa_el_blueprint(plantilla):
    plantilla.has_resource_properties(
        "AWS::Bedrock::DataAutomationProject",
        {
            "CustomOutputConfiguration": {
                "Blueprints": [Match.object_like({"BlueprintStage": "LIVE"})]
            },
            "OverrideConfiguration": {"ModalityRouting": {"jpeg": "DOCUMENT", "png": "DOCUMENT"}},
        },
    )
    plantilla.resource_count_is("AWS::Bedrock::Blueprint", 1)


def test_api_con_autorizador_lambda_y_4_rutas(plantilla):
    plantilla.has_resource_properties(
        "AWS::ApiGatewayV2::Authorizer",
        {"AuthorizerType": "REQUEST", "EnableSimpleResponses": True},
    )
    rutas = plantilla.find_resources("AWS::ApiGatewayV2::Route")
    llaves = sorted(r["Properties"]["RouteKey"] for r in rutas.values())
    assert llaves == ["GET /cvs", "GET /cvs/{id}", "GET /cvs/{id}/crudo", "POST /cvs"]
    for r in rutas.values():
        assert r["Properties"]["AuthorizationType"] == "CUSTOM"


def test_todo_se_destruye(plantilla):
    for tipo in ("AWS::S3::Bucket", "AWS::DynamoDB::GlobalTable", "AWS::Cognito::UserPool"):
        for recurso in plantilla.find_resources(tipo).values():
            assert recurso["DeletionPolicy"] == "Delete", tipo


def test_tags_de_config_en_recursos(plantilla):
    plantilla.has_resource_properties(
        "AWS::S3::Bucket",
        {"Tags": Match.array_with([{"Key": "awswomen:proyecto", "Value": "bda-ats-demo"}])},
    )


def test_config_sin_tags_falla(tmp_path: Path):
    datos = json.loads(EJEMPLO.read_text(encoding="utf-8"))
    datos["tags"] = {}
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(ErrorConfig, match="tags"):
        modulo_config.cargar(ruta)


def test_config_rechaza_prefijo_aws(tmp_path: Path):
    datos = json.loads(EJEMPLO.read_text(encoding="utf-8"))
    datos["tags"] = {"aws:reservado": "x"}
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(ErrorConfig, match="reservado"):
        modulo_config.cargar(ruta)


def test_login_administrado_de_cognito(plantilla):
    plantilla.has_resource_properties(
        "AWS::Cognito::UserPoolDomain", {"Domain": "bda-ats-123456789012", "ManagedLoginVersion": 2}
    )
    plantilla.resource_count_is("AWS::Cognito::ManagedLoginBranding", 1)
    plantilla.has_resource_properties(
        "AWS::Cognito::UserPoolClient",
        {"AllowedOAuthFlows": ["code"], "AllowedOAuthFlowsUserPoolClient": True},
    )
    plantilla.has_resource_properties("AWS::Cognito::UserPoolGroup", {"GroupName": "reclutamiento"})


def test_sin_localhost_en_cors_ni_en_el_login(plantilla):
    texto = json.dumps(plantilla.to_json())
    assert "localhost" not in texto
    cliente = next(iter(plantilla.find_resources("AWS::Cognito::UserPoolClient").values()))
    # La URL de retorno sale de la distribución de CloudFront que crea el mismo stack.
    assert "DomainName" in json.dumps(cliente["Properties"]["CallbackURLs"])


def test_indice_por_usuario_para_mis_hojas_de_vida(plantilla):
    plantilla.has_resource_properties(
        "AWS::DynamoDB::GlobalTable",
        {"GlobalSecondaryIndexes": [Match.object_like({"IndexName": "porUsuario"})]},
    )


def test_espera_bda_configurable(plantilla):
    estados = _definicion(plantilla)["States"]
    assert estados["EsperarBda"]["Seconds"] == 5
    condiciones = json.dumps(estados["EstadoBda"]["Choices"])
    assert "$vueltas < 60" in condiciones


def test_config_rechaza_perfil_bda_de_otra_geografia(tmp_path: Path):
    datos = json.loads(EJEMPLO.read_text(encoding="utf-8"))
    datos["bda"]["perfil"] = "global.data-automation-v1"
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(ErrorConfig, match="us.data-automation-v1"):
        modulo_config.cargar(ruta)


def test_arn_del_perfil_us_en_la_maquina(plantilla):
    argumentos = _definicion(plantilla)["States"]["InvocarBDA"]["Arguments"]
    assert "data-automation-profile/us.data-automation-v1" in argumentos["DataAutomationProfileArn"]
