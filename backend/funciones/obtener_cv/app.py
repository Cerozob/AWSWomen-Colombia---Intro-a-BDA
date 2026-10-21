"""GET /cvs/{id}: seguimiento + resultados de un documento, y un enlace firmado al archivo original."""

import os
from urllib.parse import quote

import boto3
from aws_lambda_powertools import Logger, Tracer
from botocore.config import Config
from comun.http import error, identidad, puede_ver, respuesta

logger = Logger()
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3", config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))
TABLA_SEGUIMIENTO = os.environ.get("TABLA_SEGUIMIENTO", "")
TABLA_RESULTADOS = os.environ.get("TABLA_RESULTADOS", "")
BUCKET_CVS = os.environ.get("BUCKET_CVS", "")
# Suficiente para revisar el documento en el visor durante la demo.
VIGENCIA_ARCHIVO_S = 900


def url_archivo(seguimiento: dict, descarga: bool = False) -> str | None:
    """URL prefirmada de la hoja de vida: para verla en el navegador o para descargarla con su nombre."""
    llave = seguimiento.get("s3Key")
    if not llave:
        return None
    disposicion = "inline"
    if descarga:
        # filename* (RFC 6266) conserva tildes y eñes del nombre original.
        nombre = quote(seguimiento.get("nombreOriginal") or "hoja-de-vida")
        disposicion = f"attachment; filename*=UTF-8''{nombre}"
    params = {"Bucket": BUCKET_CVS, "Key": llave, "ResponseContentDisposition": disposicion}
    if seguimiento.get("tipo"):
        params["ResponseContentType"] = seguimiento["tipo"]
    return s3.generate_presigned_url("get_object", Params=params, ExpiresIn=VIGENCIA_ARCHIVO_S)


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event, context):
    documento_id = (event.get("pathParameters") or {}).get("id", "")
    seguimiento = dynamodb.Table(TABLA_SEGUIMIENTO).get_item(
        Key={"documentoId": documento_id}
    ).get("Item")
    # 404 también para documentos ajenos: no se revela que existen.
    if not seguimiento or not puede_ver(identidad(event), seguimiento):
        return error(404, "No encontramos ese documento.")
    resultado = dynamodb.Table(TABLA_RESULTADOS).get_item(
        Key={"documentoId": documento_id}
    ).get("Item")
    return respuesta(
        200,
        {
            "seguimiento": seguimiento,
            "resultado": resultado,
            "urlArchivo": url_archivo(seguimiento),
            "urlDescarga": url_archivo(seguimiento, descarga=True),
        },
    )
