"""Respuestas de API Gateway HTTP API y datos de la persona autenticada."""

import os
from typing import Any

from comun.datos import a_json

GRUPO_RECLUTAMIENTO = os.environ.get("GRUPO_RECLUTAMIENTO", "reclutamiento")


def respuesta(codigo: int, cuerpo: Any) -> dict[str, Any]:
    return {
        "statusCode": codigo,
        "headers": {"content-type": "application/json; charset=utf-8"},
        "body": a_json(cuerpo),
    }


def error(codigo: int, mensaje: str) -> dict[str, Any]:
    return respuesta(codigo, {"mensaje": mensaje})


def identidad(evento: dict[str, Any]) -> dict[str, Any]:
    """Contexto que deja la Lambda autorizadora (respuesta simple)."""
    contexto = evento.get("requestContext", {}).get("authorizer", {}).get("lambda", {}) or {}
    grupos = [g for g in str(contexto.get("grupos", "")).split(",") if g]
    return {
        "sub": contexto.get("sub", ""),
        "email": contexto.get("email", ""),
        "grupos": grupos,
        "reclutamiento": GRUPO_RECLUTAMIENTO in grupos,
    }


def puede_ver(usuario: dict[str, Any], seguimiento: dict[str, Any]) -> bool:
    """Quien subió el documento o el equipo de reclutamiento."""
    return usuario["reclutamiento"] or seguimiento.get("usuarioId") == usuario["sub"]
