"""Cognito Pre SignUp: solo deja registrarse a correos o dominios de la lista permitida."""

import os

from aws_lambda_powertools import Logger

logger = Logger()


def _lista(variable: str) -> set[str]:
    return {v.strip().lower() for v in os.environ.get(variable, "").split(",") if v.strip()}


def correo_permitido(correo: str, correos: set[str], dominios: set[str]) -> bool:
    correo = correo.strip().lower()
    if not correo or "@" not in correo:
        return False
    return correo in correos or correo.rsplit("@", 1)[1] in dominios


@logger.inject_lambda_context
def handler(event, context):
    correo = event.get("request", {}).get("userAttributes", {}).get("email", "")
    if not correo_permitido(correo, _lista("CORREOS_PERMITIDOS"), _lista("DOMINIOS_PERMITIDOS")):
        logger.info("Registro rechazado", extra={"dominio": correo.rsplit("@", 1)[-1]})
        # Cognito muestra este mensaje en la pantalla de registro.
        raise Exception("Este correo no está habilitado para registrarse en el demo.")
    return event
