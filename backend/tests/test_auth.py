import time

import jwt
import pytest
from conftest import cargar_funcion
from cryptography.hazmat.primitives.asymmetric import rsa

pre_signup = cargar_funcion("pre_signup")
autorizador = cargar_funcion("autorizador")

EMISOR = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_prueba"
CLIENTE = "cliente-web"
LLAVE = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _token(**cambios):
    reclamos = {
        "sub": "sub-1",
        "email": "persona@ejemplo.com",
        "iss": EMISOR,
        "aud": CLIENTE,
        "token_use": "id",
        "exp": int(time.time()) + 600,
    }
    reclamos.update(cambios)
    return jwt.encode(reclamos, LLAVE, algorithm="RS256")


@pytest.mark.parametrize(
    ("correo", "permitido"),
    [
        ("Persona@Ejemplo.com", True),
        ("otra@ejemplo.com", True),
        ("alguien@lista.co", True),
        ("intrusa@otro.com", False),
        ("sin-arroba", False),
        ("", False),
    ],
)
def test_correo_permitido(correo, permitido):
    assert pre_signup.correo_permitido(correo, {"alguien@lista.co"}, {"ejemplo.com"}) is permitido


def test_pre_signup_rechaza_fuera_de_lista(monkeypatch, contexto):
    monkeypatch.setenv("CORREOS_PERMITIDOS", "")
    monkeypatch.setenv("DOMINIOS_PERMITIDOS", "ejemplo.com")
    evento = {"request": {"userAttributes": {"email": "x@otro.com"}}}
    with pytest.raises(Exception, match="no está habilitado"):
        pre_signup.handler(evento, contexto)
    evento_ok = {"request": {"userAttributes": {"email": "x@ejemplo.com"}}}
    assert pre_signup.handler(evento_ok, contexto) is evento_ok


def test_token_valido():
    reclamos = autorizador.validar_token(
        _token(), LLAVE.public_key(), emisor=EMISOR, cliente=CLIENTE
    )
    assert reclamos["sub"] == "sub-1"


@pytest.mark.parametrize(
    "cambios",
    [
        {"aud": "otro-cliente"},
        {"iss": "https://emisor-falso"},
        {"exp": int(time.time()) - 10},
        {"token_use": "access"},
    ],
)
def test_token_invalido(cambios):
    with pytest.raises(jwt.InvalidTokenError):
        autorizador.validar_token(
            _token(**cambios), LLAVE.public_key(), emisor=EMISOR, cliente=CLIENTE
        )


def test_handler_sin_token_no_autoriza(contexto):
    assert autorizador.handler({"headers": {}}, contexto) == {"isAuthorized": False}


def test_handler_pasa_sub_y_email(monkeypatch, contexto):
    class Llave:
        key = LLAVE.public_key()

    monkeypatch.setattr(autorizador._jwks, "get_signing_key_from_jwt", lambda _t: Llave())
    monkeypatch.setattr(autorizador, "EMISOR", EMISOR)
    monkeypatch.setattr(autorizador, "CLIENT_ID", CLIENTE)
    token = _token(**{"cognito:groups": ["reclutamiento"]})
    r = autorizador.handler({"headers": {"authorization": f"Bearer {token}"}}, contexto)
    assert r == {
        "isAuthorized": True,
        "context": {"sub": "sub-1", "email": "persona@ejemplo.com", "grupos": "reclutamiento"},
    }
