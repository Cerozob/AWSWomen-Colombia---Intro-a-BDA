"""GET /cvs: hojas de vida propias; con ?vista=todas, todas las corridas (solo reclutamiento)."""

import os

import boto3
from aws_lambda_powertools import Logger, Tracer
from boto3.dynamodb.conditions import Key
from comun.http import error, identidad, respuesta

logger = Logger()
tracer = Tracer()

TABLA_SEGUIMIENTO = os.environ.get("TABLA_SEGUIMIENTO", "")
TABLA_RESULTADOS = os.environ.get("TABLA_RESULTADOS", "")
INDICE_POR_USUARIO = os.environ.get("INDICE_POR_USUARIO", "porUsuario")

dynamodb = boto3.resource("dynamodb")

CAMPOS_RESUMEN = (
    "nombre_completo",
    "titulo_profesional",
    "area_profesional",
    "nivel_seniority",
    "anios_experiencia",
)


def resumir(seguimiento: dict, resultado: dict | None) -> dict:
    fila = {
        "documentoId": seguimiento["documentoId"],
        "nombreOriginal": seguimiento.get("nombreOriginal", ""),
        "email": seguimiento.get("email", ""),
        "estado": seguimiento.get("estado", ""),
        "etapa": seguimiento.get("etapa", ""),
        "creadoEn": seguimiento.get("creadoEn", ""),
        "paginas": seguimiento.get("paginas"),
        "segundosTotales": seguimiento.get("segundosTotales"),
        "costoEstimadoUsd": seguimiento.get("costoEstimadoUsd"),
        "motivo": seguimiento.get("motivo"),
    }
    if resultado:
        campos = resultado.get("camposPersonalizados", {})
        fila.update({c: campos.get(c) for c in CAMPOS_RESUMEN})
        fila["habilidadesTop"] = list(campos.get("habilidades_tecnicas") or [])[:3]
        fila["idiomasEstimados"] = [i for i in campos.get("idiomas_estimados") or [] if i]
        fila["confianzaMin"] = resultado.get("confianzaMin")
    return fila


def _escanear() -> list[dict]:
    tabla = dynamodb.Table(TABLA_SEGUIMIENTO)
    items, args = [], {}
    while True:
        pagina = tabla.scan(**args)
        items.extend(pagina.get("Items", []))
        if "LastEvaluatedKey" not in pagina:
            return items
        args["ExclusiveStartKey"] = pagina["LastEvaluatedKey"]


def _propios(usuario_id: str) -> list[dict]:
    tabla = dynamodb.Table(TABLA_SEGUIMIENTO)
    items, args = [], {
        "IndexName": INDICE_POR_USUARIO,
        "KeyConditionExpression": Key("usuarioId").eq(usuario_id),
    }
    while True:
        pagina = tabla.query(**args)
        items.extend(pagina.get("Items", []))
        if "LastEvaluatedKey" not in pagina:
            return items
        args["ExclusiveStartKey"] = pagina["LastEvaluatedKey"]


def _resultados(ids: list[str]) -> dict[str, dict]:
    encontrados: dict[str, dict] = {}
    for i in range(0, len(ids), 100):
        pedido = {TABLA_RESULTADOS: {"Keys": [{"documentoId": d} for d in ids[i : i + 100]]}}
        while pedido:
            r = dynamodb.batch_get_item(RequestItems=pedido)
            for item in r.get("Responses", {}).get(TABLA_RESULTADOS, []):
                encontrados[item["documentoId"]] = item
            pedido = r.get("UnprocessedKeys") or None
    return encontrados


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event, context):
    usuario = identidad(event)
    vista = (event.get("queryStringParameters") or {}).get("vista", "mias")
    if vista == "todas":
        if not usuario["reclutamiento"]:
            return error(403, "Solo el equipo de reclutamiento ve todas las candidaturas.")
        seguimiento = _escanear()
    else:
        seguimiento = _propios(usuario["sub"])
    resultados = _resultados([s["documentoId"] for s in seguimiento])
    filas = [resumir(s, resultados.get(s["documentoId"])) for s in seguimiento]
    filas.sort(key=lambda f: f["creadoEn"], reverse=True)
    return respuesta(200, {"documentos": filas})
