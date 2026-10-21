"""Utilidades compartidas: estados, historial, tiempos y conversión para DynamoDB."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

# Estados visibles en la app. La etapa (SUBIDO, EN_BDA, ...) solo alimenta la línea de tiempo.
PENDIENTE = "PENDIENTE"
PROCESADO = "PROCESADO"
FALLIDO = "FALLIDO"

EXTENSIONES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "tif": "image/tiff",
    "tiff": "image/tiff",
}
IMAGENES = {"jpg", "jpeg", "png"}
TAMANO_MAXIMO_BYTES = 500 * 1024 * 1024


def ahora_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def evento(etapa: str, en: str | None = None) -> dict[str, str]:
    return {"etapa": etapa, "en": en or ahora_iso()}


def a_dynamo(valor: Any) -> Any:
    """DynamoDB no acepta float: se pasa por JSON a Decimal."""
    return json.loads(json.dumps(valor), parse_float=Decimal)


def _normalizar(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    if isinstance(valor, set):
        return sorted(valor)
    raise TypeError(f"No serializable: {type(valor)}")


def a_json(valor: Any) -> str:
    return json.dumps(valor, default=_normalizar, ensure_ascii=False)


def segundos_entre(inicio_iso: str, fin_iso: str) -> int:
    formato = "%Y-%m-%dT%H:%M:%SZ"
    inicio = datetime.strptime(inicio_iso, formato)
    fin = datetime.strptime(fin_iso, formato)
    return max(0, int((fin - inicio).total_seconds()))
