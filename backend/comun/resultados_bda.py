"""Convierte la salida de BDA (job_metadata.json + result.json) en el ítem de ResultadosCvTable.

No se adivinan rutas: job_metadata.json dice dónde quedó la salida estándar y la personalizada.
"""

from typing import Any
from urllib.parse import urlparse


def separar_uri(uri: str) -> tuple[str, str]:
    partes = urlparse(uri)
    if partes.scheme != "s3":
        raise ValueError(f"URI de S3 inválida: {uri}")
    return partes.netloc, partes.path.lstrip("/")


def rutas_salida(job_metadata: dict[str, Any]) -> dict[str, str | None]:
    """Primer segmento del primer asset: un documento = un asset."""
    for asset in job_metadata.get("output_metadata", []):
        for segmento in asset.get("segment_metadata", []):
            return {
                "standard": segmento.get("standard_output_path"),
                "custom": segmento.get("custom_output_path"),
                "estadoCustom": segmento.get("custom_output_status"),
            }
    return {"standard": None, "custom": None, "estadoCustom": None}


def _confianzas(nodo: Any, ruta: str, salida: dict[str, float]) -> None:
    """Recorre explainability_info: hojas con 'confidence', listas (tablas) y grupos anidados.

    Las hojas sin valor (campo que no está en el documento) se omiten: su confianza baja
    no significa que haya algo que revisar.
    """
    if isinstance(nodo, dict):
        if isinstance(nodo.get("confidence"), int | float):
            if nodo.get("value") not in (None, "", []):
                salida[ruta] = float(nodo["confidence"])
            return
        for llave, hijo in nodo.items():
            _confianzas(hijo, f"{ruta}.{llave}" if ruta else llave, salida)
    elif isinstance(nodo, list):
        for i, hijo in enumerate(nodo):
            _confianzas(hijo, f"{ruta}[{i}]", salida)


def confianza_por_campo(custom: dict[str, Any]) -> dict[str, float]:
    """Confianza promedio por campo de primer nivel.

    Se promedia (no se toma el mínimo) porque en listas y tablas largas BDA reporta celdas
    individuales muy bajas y el mínimo dejaría casi todo como "Baja".
    """
    detalle: dict[str, float] = {}
    for bloque in custom.get("explainability_info", []) or []:
        _confianzas(bloque, "", detalle)
    por_campo: dict[str, list[float]] = {}
    for ruta, valor in detalle.items():
        campo = ruta.split(".")[0].split("[")[0]
        por_campo.setdefault(campo, []).append(valor)
    return {campo: round(sum(v) / len(v), 3) for campo, v in por_campo.items()}


def paginas(standard: dict[str, Any]) -> int:
    metadatos = standard.get("metadata", {}) or {}
    numero = metadatos.get("number_of_pages")
    if isinstance(numero, int) and numero > 0:
        return numero
    return max(1, len(standard.get("pages", []) or []))


def resumen_estandar(standard: dict[str, Any]) -> dict[str, Any]:
    documento = standard.get("document", {}) or {}
    tablas = sum(
        1
        for elemento in standard.get("elements", []) or []
        if str(elemento.get("type", "")).upper() == "TABLE"
    )
    return {
        "resumenDocumento": documento.get("summary", ""),
        "paginas": paginas(standard),
        "tablasDetectadas": tablas,
        "modalidad": standard.get("metadata", {}).get("semantic_modality", ""),
    }


def costo_estimado(
    num_paginas: int, es_imagen: bool, precio_pagina: float, precio_imagen: float
) -> float:
    return round(precio_imagen if es_imagen else num_paginas * precio_pagina, 4)


# Texto que BDA redacta (no extrae): su confianza es baja por naturaleza (0.07 en una prueba real)
# y no indica un error de lectura, así que se muestra pero no manda el campo a revisión.
CAMPOS_GENERADOS = frozenset({"resumen_perfil", "logros_cuantificables"})


def armar_resultado(
    *,
    documento_id: str,
    standard: dict[str, Any],
    custom: dict[str, Any] | None,
    rutas: dict[str, str | None],
    es_imagen: bool,
    umbral: float,
    precio_pagina: float,
    precio_imagen: float,
) -> dict[str, Any]:
    custom = custom or {}
    confianza = confianza_por_campo(custom)
    evaluables = {c: v for c, v in confianza.items() if c not in CAMPOS_GENERADOS}
    a_revisar = sorted(campo for campo, valor in evaluables.items() if valor < umbral)
    blueprint = custom.get("matched_blueprint", {}) or {}
    estandar = resumen_estandar(standard)
    return {
        "documentoId": documento_id,
        "camposPersonalizados": custom.get("inference_result", {}) or {},
        "confianza": confianza,
        "camposARevisar": a_revisar,
        "confianzaMin": min(evaluables.values()) if evaluables else None,
        "blueprintCoincidente": {
            "nombre": blueprint.get("name", ""),
            "confianza": blueprint.get("confidence"),
            "estado": rutas.get("estadoCustom"),
        },
        "salidaEstandar": estandar,
        "rutasCrudas": {"standard": rutas.get("standard"), "custom": rutas.get("custom")},
        "costoEstimadoUsd": costo_estimado(
            estandar["paginas"], es_imagen, precio_pagina, precio_imagen
        ),
    }
