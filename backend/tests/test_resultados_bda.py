import pytest
from comun.resultados_bda import (
    armar_resultado,
    confianza_por_campo,
    costo_estimado,
    rutas_salida,
    separar_uri,
)
from conftest import leer_dato


def test_rutas_salen_de_job_metadata():
    rutas = rutas_salida(leer_dato("job_metadata.json"))
    assert rutas["standard"].endswith("standard_output/0/result.json")
    assert rutas["custom"].endswith("custom_output/0/result.json")
    assert rutas["estadoCustom"] == "MATCH"


def test_rutas_vacias_si_no_hay_segmentos():
    assert rutas_salida({"output_metadata": []})["standard"] is None


def test_separar_uri():
    assert separar_uri("s3://b/bda/x/result.json") == ("b", "bda/x/result.json")
    with pytest.raises(ValueError):
        separar_uri("https://b/x")


def test_listas_y_tablas_promedian_sus_celdas():
    # custom_result.json es una salida real de BDA (cv-02-data-science en la consola).
    confianza = confianza_por_campo(leer_dato("custom_result.json"))
    assert confianza["experiencia"] == 0.352
    assert confianza["habilidades_tecnicas"] == 0.332
    assert confianza["nombre_completo"] == 0.562


def test_campos_vacios_no_cuentan():
    # linkedin, titulo_profesional, certificaciones e idiomas vienen vacíos en el CV.
    confianza = confianza_por_campo(leer_dato("custom_result.json"))
    for campo in ("linkedin", "titulo_profesional", "certificaciones", "idiomas"):
        assert campo not in confianza


def test_resultado_completo_marca_campos_bajo_umbral():
    r = armar_resultado(
        documento_id="doc-1",
        standard=leer_dato("standard_result.json"),
        custom=leer_dato("custom_result.json"),
        rutas=rutas_salida(leer_dato("job_metadata.json")),
        es_imagen=False,
        umbral=0.35,
        precio_pagina=0.04,
        precio_imagen=0.005,
    )
    # resumen_perfil (0.289) es texto generado: se muestra, pero no va a revisión.
    assert r["confianza"]["resumen_perfil"] == 0.289
    assert r["camposARevisar"] == ["habilidades_tecnicas"]
    assert r["confianzaMin"] == 0.332
    assert r["salidaEstandar"]["paginas"] == 2
    assert r["salidaEstandar"]["tablasDetectadas"] == 1
    assert r["costoEstimadoUsd"] == 0.08
    assert r["blueprintCoincidente"] == {"nombre": "hojadevidatest", "confianza": 1, "estado": "MATCH"}
    assert r["camposPersonalizados"]["nivel_seniority"] == "Senior"


def test_sin_salida_personalizada_no_falla():
    r = armar_resultado(
        documento_id="doc-2",
        standard={"metadata": {}, "pages": [{}]},
        custom=None,
        rutas={"standard": "s3://b/s.json", "custom": None, "estadoCustom": "NO_MATCH"},
        es_imagen=False,
        umbral=0.8,
        precio_pagina=0.04,
        precio_imagen=0.005,
    )
    assert r["confianzaMin"] is None
    assert r["camposARevisar"] == []
    assert r["salidaEstandar"]["paginas"] == 1


def test_costo_imagen_es_por_imagen():
    assert costo_estimado(3, True, 0.04, 0.005) == 0.005
    assert costo_estimado(3, False, 0.04, 0.005) == 0.12
