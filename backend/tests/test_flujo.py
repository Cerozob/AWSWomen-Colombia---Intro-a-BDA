import io
import json
from decimal import Decimal

import pytest
from conftest import DATOS, TablaFalsa, cargar_funcion

preprocesar = cargar_funcion("preprocesar")
postprocesar = cargar_funcion("postprocesar")


@pytest.mark.parametrize(
    ("llave", "tamano", "valido"),
    [
        ("entrada/u/d.pdf", 1000, True),
        ("entrada/u/d.DOCX", 1000, True),
        ("entrada/u/d.jpg", 1000, True),
        ("entrada/u/d.exe", 1000, False),
        ("entrada/u/d.pdf", 0, False),
    ],
)
def test_validar(llave, tamano, valido):
    assert (preprocesar.validar(llave, tamano) is None) is valido


class S3Falso:
    def __init__(self, objetos=None, cabecera=None):
        self.objetos = objetos or {}
        self.cabecera = cabecera or {}

    def head_object(self, Bucket, Key):
        return self.cabecera

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objetos[f"s3://{Bucket}/{Key}"])}


def test_preprocesar_registra_y_valida(monkeypatch, contexto):
    tabla = TablaFalsa()
    monkeypatch.setattr(preprocesar, "tabla", tabla)
    monkeypatch.setattr(
        preprocesar,
        "s3",
        S3Falso(cabecera={
            "ContentLength": 2048,
            "ContentType": "application/pdf",
            "Metadata": {"email": "p@ejemplo.com", "nombre-original": "CV%20Ana.pdf"},
        }),
    )
    r = preprocesar.handler(
        {"bucket": "b", "llave": "entrada/sub-1/doc-1.pdf", "documentoId": "doc-1"}, contexto
    )
    assert r == {"documentoId": "doc-1", "valido": True, "motivo": ""}
    valores = tabla.actualizaciones[0]["ExpressionAttributeValues"]
    assert valores[":nombre"] == "CV Ana.pdf"
    assert valores[":usuario"] == "sub-1"


def test_postprocesar_guarda_resultado_y_marca_procesado(monkeypatch, contexto):
    meta = json.loads((DATOS / "job_metadata.json").read_text(encoding="utf-8"))
    segmento = meta["output_metadata"][0]["segment_metadata"][0]
    objetos = {
        "s3://resultados-bda/bda/doc-1/job_metadata.json": json.dumps(meta).encode(),
        segmento["standard_output_path"]: (DATOS / "standard_result.json").read_bytes(),
        segmento["custom_output_path"]: (DATOS / "custom_result.json").read_bytes(),
    }
    seguimiento = TablaFalsa({
        "doc-1": {"documentoId": "doc-1", "s3Key": "entrada/u/doc-1.pdf",
                  "creadoEn": "2026-10-22T23:00:00Z"}
    })
    resultados = TablaFalsa()

    class DynamoFalso:
        def Table(self, nombre):
            return resultados if nombre == "resultados" else seguimiento

    monkeypatch.setattr(postprocesar, "s3", S3Falso(objetos))
    monkeypatch.setattr(postprocesar, "dynamodb", DynamoFalso())
    monkeypatch.setattr(postprocesar, "TABLA_RESULTADOS", "resultados")

    r = postprocesar.handler(
        {"documentoId": "doc-1", "rutaMetadatos": "s3://resultados-bda/bda/doc-1/job_metadata.json",
         "vueltasSondeo": 4},
        contexto,
    )
    assert r["estado"] == "PROCESADO"
    guardado = resultados.puestos[0]
    assert guardado["costoEstimadoUsd"] == Decimal("0.08")
    valores = seguimiento.actualizaciones[0]["ExpressionAttributeValues"]
    assert valores[":estado"] == "PROCESADO"
    assert valores[":vueltas"] == 4
    assert valores[":paginas"] == 2
