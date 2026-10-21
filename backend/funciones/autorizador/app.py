"""Lambda autorizadora del HTTP API: valida el ID token de Cognito y pasa sub y email al contexto."""

import os

import jwt
from aws_lambda_powertools import Logger

logger = Logger()

REGION = os.environ.get("REGION_COGNITO", "us-east-1")
USER_POOL_ID = os.environ.get("USER_POOL_ID", "")
CLIENT_ID = os.environ.get("CLIENT_ID", "")
EMISOR = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"

# Se reutiliza entre invocaciones: las llaves JWKS públicas quedan en caché.
_jwks = jwt.PyJWKClient(f"{EMISOR}/.well-known/jwks.json", cache_keys=True)


def validar_token(token: str, clave, *, emisor: str, cliente: str) -> dict:
    """Firma, emisor, audiencia (client_id), expiración y que sea un ID token."""
    reclamos = jwt.decode(
        token,
        clave,
        algorithms=["RS256"],
        audience=cliente,
        issuer=emisor,
        options={"require": ["exp", "iss", "aud", "sub", "token_use"]},
    )
    if reclamos.get("token_use") != "id":
        raise jwt.InvalidTokenError("Se esperaba un ID token")
    return reclamos


def _extraer_token(event) -> str:
    encabezado = (event.get("headers") or {}).get("authorization", "")
    return encabezado[7:].strip() if encabezado.lower().startswith("bearer ") else encabezado.strip()


@logger.inject_lambda_context
def handler(event, context):
    token = _extraer_token(event)
    if not token:
        return {"isAuthorized": False}
    try:
        clave = _jwks.get_signing_key_from_jwt(token).key
        reclamos = validar_token(token, clave, emisor=EMISOR, cliente=CLIENT_ID)
    except Exception as exc:  # noqa: BLE001 - cualquier falla de validación es un "no"
        logger.info("Token rechazado", extra={"motivo": type(exc).__name__})
        return {"isAuthorized": False}
    return {
        "isAuthorized": True,
        "context": {
            "sub": reclamos["sub"],
            "email": reclamos.get("email", ""),
            # El contexto de la respuesta simple solo admite valores escalares.
            "grupos": ",".join(reclamos.get("cognito:groups", [])),
        },
    }
