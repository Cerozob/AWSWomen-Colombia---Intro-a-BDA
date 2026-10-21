"""HTTP API con Lambda autorizadora (valida el JWT de Cognito) y una Lambda por ruta."""

from aws_cdk import Duration, Stack
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_authorizers as autorizadores
from aws_cdk import aws_apigatewayv2_integrations as integraciones
from constructs import Construct

from bda_ats.config import Config
from bda_ats.constructos.almacenamiento import PREFIJO_BDA, PREFIJO_ENTRADA, Almacenamiento
from bda_ats.constructos.auth import GRUPO_RECLUTAMIENTO, Auth
from bda_ats.constructos.funcion_python import FuncionPython


class Api(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        config: Config,
        almacenamiento: Almacenamiento,
        auth: Auth,
        origenes: list[str],
    ) -> None:
        super().__init__(scope, id)
        a = almacenamiento
        region = Stack.of(self).region

        autorizador = FuncionPython(
            self,
            "Autorizador",
            nombre="autorizador",
            descripcion="Valida el ID token de Cognito (firma, emisor, audiencia, expiración)",
            timeout_s=10,
            entorno={
                "USER_POOL_ID": auth.user_pool.user_pool_id,
                "CLIENT_ID": auth.cliente.user_pool_client_id,
                "REGION_COGNITO": region,
                "GRUPO_RECLUTAMIENTO": GRUPO_RECLUTAMIENTO,
            },
        ).funcion

        self.http_api = apigw.HttpApi(
            self,
            "HttpApi",
            api_name=f"{config.prefijo}-api",
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins=origenes,
                allow_methods=[apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.POST],
                allow_headers=["authorization", "content-type"],
                max_age=Duration.hours(1),
            ),
            default_authorizer=autorizadores.HttpLambdaAuthorizer(
                "AutorizadorCognito",
                autorizador,
                response_types=[autorizadores.HttpLambdaResponseType.SIMPLE],
                identity_source=["$request.header.Authorization"],
                results_cache_ttl=Duration.minutes(5),
            ),
        )

        tablas = {
            "TABLA_SEGUIMIENTO": a.seguimiento.table_name,
            "TABLA_RESULTADOS": a.resultados.table_name,
            "INDICE_POR_USUARIO": a.INDICE_POR_USUARIO,
        }

        subir = self._ruta(
            "SubirCv", "subir_cv", "POST", "/cvs",
            "Crea el documento y devuelve una URL prefirmada para subir la hoja de vida",
            {**tablas, "BUCKET_CVS": a.cvs.bucket_name},
        )
        a.cvs.grant_put(subir, f"{PREFIJO_ENTRADA}*")
        a.seguimiento.grant(subir, "dynamodb:PutItem")

        listar = self._ruta(
            "ListarCvs", "listar_cvs", "GET", "/cvs",
            "Lista las hojas de vida propias, o todas (?vista=todas) para el grupo de reclutamiento",
            tablas,
        )
        a.seguimiento.grant(listar, "dynamodb:Query", "dynamodb:Scan")
        a.resultados.grant(listar, "dynamodb:BatchGetItem")

        obtener = self._ruta(
            "ObtenerCv", "obtener_cv", "GET", "/cvs/{id}",
            "Seguimiento, resultados y URL prefirmada del archivo original",
            {**tablas, "BUCKET_CVS": a.cvs.bucket_name},
        )
        a.cvs.grant_read(obtener, f"{PREFIJO_ENTRADA}*")
        a.seguimiento.grant(obtener, "dynamodb:GetItem")
        a.resultados.grant(obtener, "dynamodb:GetItem")

        crudo = self._ruta(
            "ObtenerCrudo", "obtener_crudo", "GET", "/cvs/{id}/crudo",
            "URLs prefirmadas del JSON crudo de la salida estándar y personalizada de BDA",
            {**tablas, "BUCKET_RESULTADOS_BDA": a.resultados_bda.bucket_name},
        )
        a.seguimiento.grant(crudo, "dynamodb:GetItem")
        a.resultados.grant(crudo, "dynamodb:GetItem")
        a.resultados_bda.grant_read(crudo, f"{PREFIJO_BDA}*")

        self.url = self.http_api.api_endpoint

    def _ruta(self, id, nombre, metodo, ruta, descripcion, entorno):
        funcion = FuncionPython(
            self, id, nombre=nombre, descripcion=descripcion, entorno=entorno
        ).funcion
        self.http_api.add_routes(
            path=ruta,
            methods=[apigw.HttpMethod(metodo)],
            integration=integraciones.HttpLambdaIntegration(f"{id}Integracion", funcion),
        )
        return funcion
