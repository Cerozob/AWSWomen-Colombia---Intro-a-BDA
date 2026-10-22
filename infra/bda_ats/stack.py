"""Stack único del demo: un `cdk destroy` limpia todo después del evento."""

from pathlib import Path

from aws_cdk import CfnOutput, Stack
from constructs import Construct

from bda_ats.config import Config
from bda_ats.constructos.almacenamiento import Almacenamiento
from bda_ats.constructos.api import Api
from bda_ats.constructos.auth import Auth
from bda_ats.constructos.bda import Bda
from bda_ats.constructos.flujo import Flujo
from bda_ats.constructos.sitio import Sitio


class BdaAtsStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        config: Config,
        dist_frontend: Path | None,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        almacenamiento = Almacenamiento(self, "Almacenamiento")
        bda = Bda(self, "Bda", prefijo=config.prefijo, perfil=config.perfil_bda)
        flujo = Flujo(self, "Flujo", config=config, almacenamiento=almacenamiento, bda=bda)
        sitio = Sitio(self, "Sitio")
        # Solo el sitio desplegado: sin localhost en CORS ni en las URLs de retorno del login.
        auth = Auth(self, "Auth", config=config, url_sitio=sitio.url)
        almacenamiento.permitir_navegador_desde(sitio.url)
        api = Api(
            self, "Api", config=config, almacenamiento=almacenamiento, auth=auth, origenes=[sitio.url]
        )

        sitio.desplegar(
            dist_frontend,
            {
                "region": self.region,
                "apiUrl": api.url,
                "userPoolId": auth.user_pool.user_pool_id,
                "userPoolClientId": auth.cliente.user_pool_client_id,
                "dominioLogin": auth.dominio_login,
                "urlSitio": sitio.url,
                "confianza": {"alta": config.confianza_alta, "media": config.confianza_media},
                "bucketCvs": almacenamiento.cvs.bucket_name,
                "bucketResultadosBda": almacenamiento.resultados_bda.bucket_name,
                "consolaStepFunctions": (
                    f"https://{self.region}.console.aws.amazon.com/states/home"
                    f"?region={self.region}#/v2/executions/details/"
                ),
            },
        )

        CfnOutput(self, "SitioUrl", value=sitio.url)
        CfnOutput(self, "ApiUrl", value=api.url)
        CfnOutput(self, "UserPoolId", value=auth.user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=auth.cliente.user_pool_client_id)
        CfnOutput(self, "DominioLogin", value=f"https://{auth.dominio_login}")
        CfnOutput(self, "CvsBucketName", value=almacenamiento.cvs.bucket_name)
        CfnOutput(self, "MaquinaEstadosArn", value=flujo.maquina.state_machine_arn)
        CfnOutput(self, "ProyectoBdaArn", value=bda.proyecto_arn)
