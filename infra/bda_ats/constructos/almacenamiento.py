"""Buckets (hojas de vida y resultados de BDA) y tablas de DynamoDB."""

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_s3 as s3
from constructs import Construct

PREFIJO_ENTRADA = "entrada/"
PREFIJO_BDA = "bda/"


def _bucket(scope: Construct, id: str, *, event_bridge: bool) -> s3.Bucket:
    return s3.Bucket(
        scope,
        id,
        block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        encryption=s3.BucketEncryption.S3_MANAGED,
        enforce_ssl=True,
        event_bridge_enabled=event_bridge,
        removal_policy=RemovalPolicy.DESTROY,
        auto_delete_objects=True,
        lifecycle_rules=[s3.LifecycleRule(expiration=Duration.days(7))],
    )


class Almacenamiento(Construct):
    INDICE_POR_USUARIO = "porUsuario"

    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)

        # Lo que sube la persona usuaria; EventBridge dispara el flujo con prefijo entrada/.
        self.cvs = _bucket(self, "CvsBucket", event_bridge=True)
        # Lo que escribe BDA. Bucket aparte para que su salida no dispare la regla.
        self.resultados_bda = _bucket(self, "ResultadosBdaBucket", event_bridge=False)

        self.seguimiento = dynamodb.TableV2(
            self,
            "SeguimientoTable",
            partition_key=dynamodb.Attribute(name="documentoId", type=dynamodb.AttributeType.STRING),
            # "Mis hojas de vida": los documentos de una persona, del más reciente al más antiguo.
            global_secondary_indexes=[
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name=self.INDICE_POR_USUARIO,
                    partition_key=dynamodb.Attribute(name="usuarioId", type=dynamodb.AttributeType.STRING),
                    sort_key=dynamodb.Attribute(name="creadoEn", type=dynamodb.AttributeType.STRING),
                )
            ],
            billing=dynamodb.Billing.on_demand(),
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.resultados = dynamodb.TableV2(
            self,
            "ResultadosCvTable",
            partition_key=dynamodb.Attribute(name="documentoId", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
            removal_policy=RemovalPolicy.DESTROY,
        )

    def permitir_navegador_desde(self, origen: str) -> None:
        """CORS solo para el sitio desplegado, siempre con URLs prefirmadas: PUT de la hoja de vida,
        GET de la hoja de vida (PDF.js la descarga para dibujar las cajas) y GET del JSON crudo."""
        self.cvs.add_cors_rule(
            allowed_methods=[s3.HttpMethods.PUT, s3.HttpMethods.GET],
            allowed_origins=[origen],
            allowed_headers=["*"],
            max_age=3000,
        )
        self.resultados_bda.add_cors_rule(
            allowed_methods=[s3.HttpMethods.GET],
            allowed_origins=[origen],
            allowed_headers=["*"],
            max_age=3000,
        )
