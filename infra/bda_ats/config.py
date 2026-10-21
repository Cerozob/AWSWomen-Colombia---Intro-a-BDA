"""Lee y valida config.json (raíz del repo). Falla en synth si falta algo crítico."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
NAG_FLAGS = (
    "aws_solutions",
    "hipaa_security",
    "nist_800_53_r4",
    "nist_800_53_r5",
    "pci_dss_321",
    "serverless",
)


class ErrorConfig(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    cuenta: str
    region: str
    prefijo: str
    tags: dict[str, str]
    nag: dict[str, bool]
    correos_permitidos: list[str]
    dominios_permitidos: list[str]
    correos_reclutamiento: list[str]
    perfil_bda: str
    segundos_espera: int
    max_vueltas: int
    confianza_alta: float
    confianza_media: float
    precio_documento_pagina: float
    precio_imagen: float


def _requerido(datos: dict[str, Any], llave: str) -> Any:
    if llave not in datos:
        raise ErrorConfig(f"config.json: falta la llave '{llave}'")
    return datos[llave]


def cargar(ruta: Path | None = None) -> Config:
    ruta = ruta or Path(os.environ.get("BDA_ATS_CONFIG", RAIZ / "config.json"))
    if not ruta.exists():
        raise ErrorConfig(f"No existe {ruta}. Copia config.json.example a config.json y ajústalo.")
    datos = json.loads(ruta.read_text(encoding="utf-8"))

    tags = datos.get("tags")
    if not isinstance(tags, dict) or not tags:
        raise ErrorConfig("config.json: 'tags' es obligatorio y no puede estar vacío")
    for llave, valor in tags.items():
        if llave.lower().startswith("aws:"):
            raise ErrorConfig(f"config.json: el prefijo 'aws:' está reservado (tag '{llave}')")
        if len(llave) > 128 or len(str(valor)) > 256:
            raise ErrorConfig(f"config.json: el tag '{llave}' excede los límites de AWS")

    nag = datos.get("nag", {})
    faltan = [f for f in NAG_FLAGS if f not in nag]
    if faltan:
        raise ErrorConfig(f"config.json: faltan flags en 'nag': {', '.join(faltan)}")

    registro = _requerido(datos, "registro")
    bda = _requerido(datos, "bda")
    confianza = _requerido(datos, "confianza")
    precios = _requerido(datos, "precios_usd")

    # El perfil de BDA es por geografía y debe coincidir con la región del stack
    # (us.* en us-east-1; global.* solo existe en ap-southeast-1). Si no, InvokeDataAutomationAsync
    # responde "The provided DataAutomationProfile ARN is invalid".
    perfil = bda.get("perfil", "us.data-automation-v1")
    region = _requerido(datos, "region")
    geografia = {"us": "us.", "eu": "eu.", "ap": "apac."}.get(region.split("-")[0])
    if geografia and region != "ap-southeast-1" and not perfil.startswith(geografia):
        raise ErrorConfig(
            f"config.json: el perfil de BDA '{perfil}' no sirve en {region}; "
            f"usa '{geografia}data-automation-v1'"
        )

    return Config(
        cuenta=str(_requerido(datos, "cuenta")),
        region=_requerido(datos, "region"),
        prefijo=datos.get("prefijo", "bda-ats"),
        tags={k: str(v) for k, v in tags.items()},
        nag={f: bool(nag[f]) for f in NAG_FLAGS},
        correos_permitidos=list(registro.get("correos_permitidos", [])),
        dominios_permitidos=list(registro.get("dominios_permitidos", [])),
        correos_reclutamiento=list(registro.get("correos_reclutamiento", [])),
        perfil_bda=perfil,
        segundos_espera=int(bda.get("segundos_espera", 5)),
        max_vueltas=int(bda.get("max_vueltas", 60)),
        confianza_alta=float(confianza["alta"]),
        confianza_media=float(confianza["media"]),
        precio_documento_pagina=float(precios["documento_pagina_custom"]),
        precio_imagen=float(precios["imagen_custom"]),
    )
