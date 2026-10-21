"""Último paso del flujo: lee la salida de BDA, guarda el perfil y marca el documento PROCESADO."""

import json
import os

import boto3
from aws_lambda_powertools import Logger, Tracer
from comun.datos import IMAGENES, PROCESADO, a_dynamo, ahora_iso, evento, segundos_entre
from comun.resultados_bda import armar_resultado, rutas_salida, separar_uri

logger = Logger()
tracer = Tracer()

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
TABLA_SEGUIMIENTO = os.environ.get("TABLA_SEGUIMIENTO", "")
TABLA_RESULTADOS = os.environ.get("TABLA_RESULTADOS", "")
UMBRAL = float(os.environ.get("UMBRAL_CONFIANZA", "0.35"))
PRECIO_PAGINA = float(os.environ.get("PRECIO_DOC_CUSTOM", "0.04"))
PRECIO_IMAGEN = float(os.environ.get("PRECIO_IMG_CUSTOM", "0.005"))


def leer_json(uri: str | None):
    if not uri:
        return None
    bucket, llave = separar_uri(uri)
    return json.loads(s3.get_object(Bucket=bucket, Key=llave)["Body"].read())


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event, context):
    documento_id = event["documentoId"]
    job_metadata = leer_json(event["rutaMetadatos"])
    rutas = rutas_salida(job_metadata)
    if not rutas["standard"]:
        raise ValueError("job_metadata.json no trae standard_output_path")

    tabla_seguimiento = dynamodb.Table(TABLA_SEGUIMIENTO)
    seguimiento = tabla_seguimiento.get_item(Key={"documentoId": documento_id}).get("Item", {})
    extension = seguimiento.get("s3Key", "").rsplit(".", 1)[-1].lower()

    resultado = armar_resultado(
        documento_id=documento_id,
        standard=leer_json(rutas["standard"]),
        custom=leer_json(rutas["custom"]),
        rutas=rutas,
        es_imagen=extension in IMAGENES,
        umbral=UMBRAL,
        precio_pagina=PRECIO_PAGINA,
        precio_imagen=PRECIO_IMAGEN,
    )
    dynamodb.Table(TABLA_RESULTADOS).put_item(Item=a_dynamo(resultado))

    ahora = ahora_iso()
    tabla_seguimiento.update_item(
        Key={"documentoId": documento_id},
        UpdateExpression=(
            "SET estado = :estado, etapa = :estado, paginas = :paginas, costoEstimadoUsd = :costo, "
            "segundosTotales = :segundos, vueltasSondeo = :vueltas, actualizadoEn = :ahora, "
            "historial = list_append(if_not_exists(historial, :vacio), :evento)"
        ),
        ExpressionAttributeValues=a_dynamo(
            {
                ":estado": PROCESADO,
                ":paginas": resultado["salidaEstandar"]["paginas"],
                ":costo": resultado["costoEstimadoUsd"],
                ":segundos": segundos_entre(seguimiento.get("creadoEn", ahora), ahora),
                ":vueltas": int(event.get("vueltasSondeo", 0)),
                ":ahora": ahora,
                ":vacio": [],
                ":evento": [evento(PROCESADO, ahora)],
            }
        ),
    )
    logger.info(
        "Documento procesado",
        extra={"documentoId": documento_id, "camposARevisar": resultado["camposARevisar"]},
    )
    return {"documentoId": documento_id, "estado": PROCESADO}
