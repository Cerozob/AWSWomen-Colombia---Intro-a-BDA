"""Cognito Post Confirmation: agrega al grupo de reclutamiento los correos configurados."""

import os

import boto3
from aws_lambda_powertools import Logger

logger = Logger()
cognito = boto3.client("cognito-idp")


def es_reclutamiento(correo: str, lista: str) -> bool:
    permitidos = {c.strip().lower() for c in lista.split(",") if c.strip()}
    return correo.strip().lower() in permitidos


@logger.inject_lambda_context
def handler(event, context):
    # También llega en "olvidé mi contraseña"; solo interesa el registro.
    if event.get("triggerSource") != "PostConfirmation_ConfirmSignUp":
        return event
    correo = event.get("request", {}).get("userAttributes", {}).get("email", "")
    if es_reclutamiento(correo, os.environ.get("CORREOS_RECLUTAMIENTO", "")):
        cognito.admin_add_user_to_group(
            UserPoolId=event["userPoolId"],
            Username=event["userName"],
            GroupName=os.environ.get("GRUPO", "reclutamiento"),
        )
        logger.info("Persona agregada al grupo de reclutamiento")
    return event
