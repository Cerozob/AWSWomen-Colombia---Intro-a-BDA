"""Paso 1 del flujo: lee metadatos del archivo, valida formato y tamaño y registra el documento."""

import os
from urllib.parse import unquote

import boto3
from aws_lambda_powertools import Logger, Tracer
from comun.datos import EXTENSIONES, PENDIENTE, TAMANO_MAXIMO_BYTES, ahora_iso, evento

logger = Logger()
tracer = Tracer()

s3 = boto3.client("s3")
TABLA = os.environ.get("TABLA_SEGUIMIENTO", "")
tabla = boto3.resource("dynamodb").Table(TABLA) if TABLA else None


def validar(llave: str, tamano: int) -> str | None:
    """Devuelve el motivo si el archivo no se puede procesar, o None si está bien."""
    extension = llave.rsplit(".", 1)[-1].lower() if "." in llave else ""
    if extension not in EXTENSIONES:
        return f"Formato .{extension} no soportado por el demo"
    if tamano <= 0:
        return "El archivo está vacío"
    if tamano > TAMANO_MAXIMO_BYTES:
        return "El archivo supera el tamaño máximo de BDA"
    return None


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event, context):
    bucket, llave, documento_id = event["bucket"], event["llave"], event["documentoId"]
    cabecera = s3.head_object(Bucket=bucket, Key=llave)
    metadatos = cabecera.get("Metadata", {})
    tamano = int(cabecera.get("ContentLength", 0))
    motivo = validar(llave, tamano)
    ahora = ahora_iso()
    partes = llave.split("/")

    # if_not_exists: el ítem normalmente lo creó SubirCv, pero un archivo subido por script
    # (plan B) también queda registrado.
    tabla.update_item(
        Key={"documentoId": documento_id},
        UpdateExpression=(
            "SET usuarioId = if_not_exists(usuarioId, :usuario), "
            "email = if_not_exists(email, :email), "
            "nombreOriginal = if_not_exists(nombreOriginal, :nombre), "
            "s3Key = :llave, tipo = if_not_exists(tipo, :tipo), "
            "estado = if_not_exists(estado, :pendiente), creadoEn = if_not_exists(creadoEn, :ahora), "
            "tamanoBytes = :tamano, ejecucionArn = :ejecucion, etapa = :etapa, actualizadoEn = :ahora, "
            "historial = list_append(if_not_exists(historial, :vacio), :evento)"
        ),
        ExpressionAttributeValues={
            ":usuario": partes[1] if len(partes) > 2 else "desconocido",
            ":email": metadatos.get("email", ""),
            ":nombre": unquote(metadatos.get("nombre-original", partes[-1])),
            ":llave": llave,
            ":tipo": cabecera.get("ContentType", ""),
            ":pendiente": PENDIENTE,
            ":ahora": ahora,
            ":tamano": tamano,
            ":ejecucion": event.get("ejecucionArn", ""),
            ":etapa": "VALIDADO",
            ":vacio": [],
            ":evento": [evento("VALIDADO", ahora)],
        },
    )
    logger.info("Documento validado", extra={"documentoId": documento_id, "motivo": motivo})
    return {"documentoId": documento_id, "valido": motivo is None, "motivo": motivo or ""}
