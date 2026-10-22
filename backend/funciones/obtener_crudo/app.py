"""GET /cvs/{id}/crudo: URLs prefirmadas del JSON que escribió BDA (salida estándar y personalizada).

El navegador descarga los archivos directo de S3, así su tamaño no pasa por la API.
"""

import json
import os

import boto3
from aws_lambda_powertools import Logger, Tracer
from botocore.config import Config
from comun.http import error, identidad, puede_ver, respuesta
from comun.resultados_bda import separar_uri

logger = Logger()
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3", config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))
TABLA_SEGUIMIENTO = os.environ.get("TABLA_SEGUIMIENTO", "")
TABLA_RESULTADOS = os.environ.get("TABLA_RESULTADOS", "")
BUCKET = os.environ.get("BUCKET_RESULTADOS_BDA", "")
VIGENCIA_S = 300


def url_firmada(uri: str | None) -> str | None:
    if not uri:
        return None
    bucket, llave = separar_uri(uri)
    if bucket != BUCKET:
        raise ValueError("Ruta fuera del bucket de resultados")
    return s3.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": llave}, ExpiresIn=VIGENCIA_S
    )


def imagenes_extraidas(standard: dict | None) -> list[dict]:
    """Figuras que BDA recortó del documento (elementos con crop_images en la salida estándar)."""
    imagenes = []
    for elemento in (standard or {}).get("elements", []) or []:
        for uri in elemento.get("crop_images", []) or []:
            imagenes.append(
                {
                    "tipo": elemento.get("sub_type") or elemento.get("type") or "",
                    "descripcion": elemento.get("summary") or elemento.get("title") or "",
                    "pagina": (elemento.get("page_indices") or [None])[0],
                    "uri": uri,
                }
            )
    return imagenes


def leer_json(uri: str | None) -> dict | None:
    if not uri:
        return None
    bucket, llave = separar_uri(uri)
    if bucket != BUCKET:
        raise ValueError("Ruta fuera del bucket de resultados")
    return json.loads(s3.get_object(Bucket=bucket, Key=llave)["Body"].read())


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event, context):
    documento_id = (event.get("pathParameters") or {}).get("id", "")
    seguimiento = dynamodb.Table(TABLA_SEGUIMIENTO).get_item(
        Key={"documentoId": documento_id}
    ).get("Item")
    if not seguimiento or not puede_ver(identidad(event), seguimiento):
        return error(404, "No encontramos ese documento.")
    resultado = dynamodb.Table(TABLA_RESULTADOS).get_item(
        Key={"documentoId": documento_id}
    ).get("Item")
    if not resultado:
        return error(404, "Este documento todavía no tiene resultados de BDA.")
    rutas = resultado.get("rutasCrudas", {})
    imagenes = []
    for imagen in imagenes_extraidas(leer_json(rutas.get("standard"))):
        try:
            imagenes.append({**imagen, "url": url_firmada(imagen.pop("uri"))})
        except ValueError:
            logger.warning("Imagen fuera del bucket de resultados")
    return respuesta(
        200,
        {
            "standard": url_firmada(rutas.get("standard")),
            "custom": url_firmada(rutas.get("custom")),
            "imagenes": imagenes,
            "vigenciaSegundos": VIGENCIA_S,
        },
    )
