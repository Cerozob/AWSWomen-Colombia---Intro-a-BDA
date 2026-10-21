"""POST /cvs: crea el documento en PENDIENTE y devuelve una URL prefirmada para el PUT."""

import json
import os
import uuid
from urllib.parse import quote

import boto3
from aws_lambda_powertools import Logger, Tracer
from botocore.config import Config
from comun.datos import EXTENSIONES, PENDIENTE, ahora_iso, evento
from comun.http import error, identidad, respuesta

logger = Logger()
tracer = Tracer()

BUCKET = os.environ.get("BUCKET_CVS", "")
TABLA = os.environ.get("TABLA_SEGUIMIENTO", "")
VIGENCIA_S = 300

s3 = boto3.client("s3", config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))
tabla = boto3.resource("dynamodb").Table(TABLA) if TABLA else None


def preparar(cuerpo: dict, usuario: dict, documento_id: str) -> dict:
    """Valida el archivo pedido y arma la llave, metadatos e ítem inicial."""
    nombre = str(cuerpo.get("nombreArchivo", "")).strip()
    extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if extension not in EXTENSIONES:
        raise ValueError(
            "Formato no soportado. Usa PDF, DOCX, JPG, PNG o TIFF."
        )
    tipo = EXTENSIONES[extension]
    llave = f"entrada/{usuario['sub']}/{documento_id}.{extension}"
    ahora = ahora_iso()
    # Los metadatos de S3 solo admiten ASCII: el nombre original va codificado.
    metadatos = {"email": usuario["email"], "nombre-original": quote(nombre)}
    item = {
        "documentoId": documento_id,
        "usuarioId": usuario["sub"],
        "email": usuario["email"],
        "nombreOriginal": nombre,
        "s3Key": llave,
        "tipo": tipo,
        "estado": PENDIENTE,
        "etapa": "SUBIDO",
        "historial": [evento("SUBIDO", ahora)],
        "creadoEn": ahora,
        "actualizadoEn": ahora,
    }
    return {"llave": llave, "tipo": tipo, "metadatos": metadatos, "item": item}


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event, context):
    usuario = identidad(event)
    try:
        cuerpo = json.loads(event.get("body") or "{}")
        datos = preparar(cuerpo, usuario, str(uuid.uuid4()))
    except (ValueError, json.JSONDecodeError) as exc:
        return error(400, str(exc))

    tabla.put_item(Item=datos["item"])
    url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": BUCKET,
            "Key": datos["llave"],
            "ContentType": datos["tipo"],
            "Metadata": datos["metadatos"],
        },
        ExpiresIn=VIGENCIA_S,
    )
    encabezados = {"content-type": datos["tipo"]}
    encabezados.update({f"x-amz-meta-{k}": v for k, v in datos["metadatos"].items()})
    logger.info("URL de subida creada", extra={"documentoId": datos["item"]["documentoId"]})
    return respuesta(
        201,
        {"documentoId": datos["item"]["documentoId"], "url": url, "encabezados": encabezados},
    )
