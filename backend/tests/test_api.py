import json
from urllib.parse import parse_qs, urlparse

import pytest
from conftest import TablaFalsa, cargar_funcion

subir_cv = cargar_funcion("subir_cv")
listar_cvs = cargar_funcion("listar_cvs")

USUARIO = {"sub": "sub-1", "email": "persona@ejemplo.com"}


def test_preparar_arma_llave_y_metadatos():
    datos = subir_cv.preparar({"nombreArchivo": "CV Ñandú.PDF"}, USUARIO, "doc-1")
    assert datos["llave"] == "entrada/sub-1/doc-1.pdf"
    assert datos["tipo"] == "application/pdf"
    assert datos["metadatos"]["nombre-original"].isascii()
    assert datos["item"]["estado"] == "PENDIENTE"
    assert datos["item"]["historial"][0]["etapa"] == "SUBIDO"


@pytest.mark.parametrize("nombre", ["virus.exe", "sin-extension", ""])
def test_preparar_rechaza_formatos(nombre):
    with pytest.raises(ValueError, match="Formato no soportado"):
        subir_cv.preparar({"nombreArchivo": nombre}, USUARIO, "doc-1")


def test_subir_devuelve_url_firmada_con_metadatos(monkeypatch, contexto):
    tabla = TablaFalsa()
    monkeypatch.setattr(subir_cv, "tabla", tabla)
    monkeypatch.setattr(subir_cv, "BUCKET", "cvs-bucket")
    evento = {
        "body": json.dumps({"nombreArchivo": "cv.docx"}),
        "requestContext": {"authorizer": {"lambda": USUARIO}},
    }
    r = subir_cv.handler(evento, contexto)
    cuerpo = json.loads(r["body"])
    assert r["statusCode"] == 201
    url = urlparse(cuerpo["url"])
    assert url.netloc.startswith("cvs-bucket.")
    assert url.path == f"/entrada/sub-1/{cuerpo['documentoId']}.docx"
    assert "x-amz-meta-email" in parse_qs(url.query)["X-Amz-SignedHeaders"][0]
    assert cuerpo["encabezados"]["x-amz-meta-email"] == "persona@ejemplo.com"
    assert tabla.puestos[0]["documentoId"] == cuerpo["documentoId"]


def test_subir_formato_invalido_es_400(contexto):
    evento = {"body": json.dumps({"nombreArchivo": "x.exe"}), "requestContext": {}}
    assert subir_cv.handler(evento, contexto)["statusCode"] == 400


def test_resumir_combina_seguimiento_y_resultado():
    fila = listar_cvs.resumir(
        {"documentoId": "d", "estado": "PROCESADO", "creadoEn": "2026-10-22T00:00:00Z"},
        {
            "camposPersonalizados": {
                "nombre_completo": "Ana",
                "nivel_seniority": "Semi-senior",
                "area_profesional": "Tecnología",
                "habilidades_tecnicas": ["AWS", "Python", "SQL", "Go"],
                "idiomas_estimados": ["inglés", "", "español"],
            },
            "confianzaMin": 0.7,
        },
    )
    assert fila["habilidadesTop"] == ["AWS", "Python", "SQL"]
    assert fila["idiomasEstimados"] == ["inglés", "español"]
    assert fila["nivel_seniority"] == "Semi-senior"
    assert fila["area_profesional"] == "Tecnología"
    assert fila["confianzaMin"] == 0.7


def test_resumir_sin_resultado_aun():
    fila = listar_cvs.resumir({"documentoId": "d", "estado": "PENDIENTE"}, None)
    assert fila["estado"] == "PENDIENTE"
    assert "habilidadesTop" not in fila


obtener_cv = cargar_funcion("obtener_cv")
obtener_crudo = cargar_funcion("obtener_crudo")
post_confirmacion = cargar_funcion("post_confirmacion")


def _evento(sub="sub-1", grupos="", **extra):
    return {
        "requestContext": {
            "authorizer": {"lambda": {"sub": sub, "email": "p@ejemplo.com", "grupos": grupos}}
        },
        **extra,
    }


class TablaConsulta(TablaFalsa):
    def __init__(self, items=None):
        super().__init__(items)
        self.consultas = []
        self.escaneos = 0

    def query(self, **kwargs):
        self.consultas.append(kwargs)
        return {"Items": [i for i in self.items.values() if i.get("usuarioId") == "sub-1"]}

    def scan(self, **kwargs):
        self.escaneos += 1
        return {"Items": list(self.items.values())}


class DynamoFalso:
    def __init__(self, seguimiento, resultados=None):
        self.seguimiento = seguimiento
        self.resultados = resultados or TablaFalsa()

    def Table(self, nombre):
        return self.resultados if nombre == "resultados" else self.seguimiento

    def batch_get_item(self, RequestItems):
        return {"Responses": {}}


DOCS = {
    "a": {
        "documentoId": "a",
        "usuarioId": "sub-1",
        "creadoEn": "2026-10-20T01:00:00Z",
        "estado": "PROCESADO",
    },
    "b": {
        "documentoId": "b",
        "usuarioId": "sub-2",
        "creadoEn": "2026-10-20T02:00:00Z",
        "estado": "PENDIENTE",
    },
}


def test_listar_por_defecto_solo_propias(monkeypatch, contexto):
    tabla = TablaConsulta(DOCS)
    monkeypatch.setattr(listar_cvs, "dynamodb", DynamoFalso(tabla))
    r = listar_cvs.handler(_evento(), contexto)
    ids = [d["documentoId"] for d in json.loads(r["body"])["documentos"]]
    assert ids == ["a"]
    assert tabla.consultas[0]["IndexName"] == "porUsuario"
    assert tabla.escaneos == 0


def test_vista_todas_exige_reclutamiento(monkeypatch, contexto):
    tabla = TablaConsulta(DOCS)
    monkeypatch.setattr(listar_cvs, "dynamodb", DynamoFalso(tabla))
    evento = _evento(queryStringParameters={"vista": "todas"})
    assert listar_cvs.handler(evento, contexto)["statusCode"] == 403

    evento = _evento(grupos="reclutamiento", queryStringParameters={"vista": "todas"})
    r = listar_cvs.handler(evento, contexto)
    ids = [d["documentoId"] for d in json.loads(r["body"])["documentos"]]
    assert ids == ["b", "a"]  # más reciente primero


def test_obtener_documento_ajeno_es_404(monkeypatch, contexto):
    monkeypatch.setattr(obtener_cv, "dynamodb", DynamoFalso(TablaFalsa(DOCS)))
    evento = _evento(pathParameters={"id": "b"})
    assert obtener_cv.handler(evento, contexto)["statusCode"] == 404
    evento = _evento(grupos="reclutamiento", pathParameters={"id": "b"})
    assert obtener_cv.handler(evento, contexto)["statusCode"] == 200


def test_crudo_devuelve_urls_prefirmadas(monkeypatch, contexto):
    resultados = TablaFalsa(
        {
            "a": {
                "documentoId": "a",
                "rutasCrudas": {
                    "standard": "s3://resultados/bda/a/x/standard_output/0/result.json",
                    "custom": "s3://resultados/bda/a/x/custom_output/0/result.json",
                },
            }
        }
    )
    monkeypatch.setattr(obtener_crudo, "dynamodb", DynamoFalso(TablaFalsa(DOCS), resultados))
    monkeypatch.setattr(obtener_crudo, "BUCKET", "resultados")
    monkeypatch.setattr(obtener_crudo, "TABLA_RESULTADOS", "resultados")
    r = obtener_crudo.handler(_evento(pathParameters={"id": "a"}), contexto)
    cuerpo = json.loads(r["body"])
    assert r["statusCode"] == 200
    url = urlparse(cuerpo["custom"])
    assert url.netloc.startswith("resultados.")
    assert url.path.endswith("/custom_output/0/result.json")
    assert "X-Amz-Signature" in parse_qs(url.query)


def test_crudo_rechaza_rutas_de_otro_bucket(monkeypatch):
    monkeypatch.setattr(obtener_crudo, "BUCKET", "resultados")
    with pytest.raises(ValueError):
        obtener_crudo.url_firmada("s3://otro-bucket/secreto.json")


def test_post_confirmacion_solo_agrega_correos_configurados(monkeypatch, contexto):
    llamadas = []

    class CognitoFalso:
        def admin_add_user_to_group(self, **kwargs):
            llamadas.append(kwargs)

    monkeypatch.setattr(post_confirmacion, "cognito", CognitoFalso())
    monkeypatch.setenv("CORREOS_RECLUTAMIENTO", "Admin@Ejemplo.com")
    base = {"triggerSource": "PostConfirmation_ConfirmSignUp", "userPoolId": "pool", "userName": "u1"}
    post_confirmacion.handler(
        {**base, "request": {"userAttributes": {"email": "otra@ejemplo.com"}}}, contexto
    )
    assert llamadas == []
    post_confirmacion.handler(
        {**base, "request": {"userAttributes": {"email": "admin@ejemplo.com"}}}, contexto
    )
    assert llamadas == [{"UserPoolId": "pool", "Username": "u1", "GroupName": "reclutamiento"}]
    recuperacion = {
        **base,
        "triggerSource": "PostConfirmation_ConfirmForgotPassword",
        "request": {"userAttributes": {"email": "admin@ejemplo.com"}},
    }
    post_confirmacion.handler(recuperacion, contexto)
    assert len(llamadas) == 1


def test_obtener_incluye_url_del_archivo_original(monkeypatch, contexto):
    docs = {"a": {**DOCS["a"], "s3Key": "entrada/sub-1/a.pdf", "tipo": "application/pdf"}}
    monkeypatch.setattr(obtener_cv, "dynamodb", DynamoFalso(TablaFalsa(docs)))
    monkeypatch.setattr(obtener_cv, "BUCKET_CVS", "cvs")
    r = obtener_cv.handler(_evento(pathParameters={"id": "a"}), contexto)
    url = urlparse(json.loads(r["body"])["urlArchivo"])
    consulta = parse_qs(url.query)
    assert url.netloc.startswith("cvs.")
    assert url.path == "/entrada/sub-1/a.pdf"
    assert consulta["response-content-disposition"] == ["inline"]
    assert consulta["response-content-type"] == ["application/pdf"]


def test_url_de_descarga_usa_el_nombre_original(monkeypatch):
    monkeypatch.setattr(obtener_cv, "BUCKET_CVS", "cvs")
    seguimiento = {"s3Key": "entrada/u/a.pdf", "tipo": "application/pdf", "nombreOriginal": "CV Ñandú.pdf"}
    consulta = parse_qs(urlparse(obtener_cv.url_archivo(seguimiento, descarga=True)).query)
    assert consulta["response-content-disposition"] == [
        "attachment; filename*=UTF-8''CV%20%C3%91and%C3%BA.pdf"
    ]
