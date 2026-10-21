import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
DATOS = Path(__file__).parent / "datos"

# Credenciales falsas: los clientes de boto3 se crean al importar, pero las pruebas no llaman a AWS.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "prueba")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "prueba")
os.environ.setdefault("POWERTOOLS_TRACE_DISABLED", "true")
os.environ.setdefault("POWERTOOLS_DEV", "false")
sys.path.insert(0, str(BACKEND))


def cargar_funcion(nombre: str):
    """Cada Lambda se llama app.py: se importa con un nombre único para que no choquen."""
    ruta = BACKEND / "funciones" / nombre / "app.py"
    spec = importlib.util.spec_from_file_location(f"funcion_{nombre}", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def leer_dato(nombre: str):
    return json.loads((DATOS / nombre).read_text(encoding="utf-8"))


class ContextoLambda:
    function_name = "prueba"
    memory_limit_in_mb = 512
    invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:prueba"
    aws_request_id = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def contexto():
    return ContextoLambda()


class TablaFalsa:
    """Doble mínimo de una tabla de DynamoDB que guarda las llamadas."""

    def __init__(self, items=None):
        self.items = dict(items or {})
        self.puestos = []
        self.actualizaciones = []

    def put_item(self, Item):
        self.puestos.append(Item)
        self.items[Item["documentoId"]] = Item

    def get_item(self, Key):
        item = self.items.get(Key["documentoId"])
        return {"Item": item} if item else {}

    def update_item(self, **kwargs):
        self.actualizaciones.append(kwargs)
