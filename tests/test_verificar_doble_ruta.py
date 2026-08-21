"""Verificación doble del corpus (Prompt 2,
docs/prd/2026-08-21-verificacion-doble-del-corpus.md), ruta B determinista
(decisión de Pablo, 2026-08-21, sin API). Golden tests contra las 20
candidatas reales de DB-SUA y el PDF real — mismo principio que el resto
de esta fase: el resultado (qué se promueve, qué queda pendiente, y por
qué) es tan parte del contrato como el código que lo produce.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from normativa.validacion import validar_fichero  # noqa: E402
from scripts.verificar_doble_ruta import (  # noqa: E402
    _normalizar_unidad,
    _valores_convertibles_a,
    comparar_padre,
    procesar,
)

CANDIDATAS = RAIZ / "extraccion" / "estado" / "candidatas" / "codigotecnico__DB-SUA__3cfb5bbb135e.jsonl"
PDF = RAIZ / "tests" / "fixtures" / "codigotecnico" / "DB-SUA.pdf"

CONCEPT_IDS_VERIFICADOS = {
    "es.rd_173_2010.seguridad_utilizacion.1_2_discontinuidades_en_el_pavimento",
    "es.rd_173_2010.seguridad_utilizacion.4_1_alumbrado_normal_en_zonas_de_circulacion",
    "es.rd_173_2010.seguridad_utilizacion.5_1_ambito_de_aplicacion",
}


def test_normalizar_unidad_equivalencias():
    assert _normalizar_unidad("m2") == "m²"
    assert _normalizar_unidad("M2") == "m²"
    assert _normalizar_unidad("cm") == "cm"
    assert _normalizar_unidad(None) == ""


# --- comparar_padre, con lecturas fabricadas — sin tocar el PDF ------------

def _cand(articulo: str, texto_original: str, nombre: str, valor_citado: str, unidad: str) -> dict:
    return {
        "articulo": articulo,
        "texto_original": texto_original,
        "parametros": [{"nombre": nombre, "valor_citado": valor_citado, "unidad": unidad,
                        "comparador": ">=", "contexto_citado": texto_original}],
    }


def test_comparar_padre_promueve_cuando_coinciden_valor_y_unidad():
    cand_a = _cand("X 1.1 Prueba", "La altura será 80 cm, como mínimo.", "altura", "80 cm", "cm")
    registro_b = {
        "valores": [{"nombre": "altura_0", "valor_citado": "80 cm", "unidad": "cm",
                    "comparador": ">=", "contexto_citado": "La altura será 80 cm, como mínimo."}],
        "no_reconocidas": [],
    }
    resultado = comparar_padre(cand_a, registro_b)
    assert len(resultado["promovidas"]) == 1
    assert not resultado["pendientes"]
    assert resultado["promovidas"][0]["valor"] == 80.0
    assert resultado["promovidas"][0]["unidad"] == "cm"


def test_comparar_padre_no_promueve_si_las_unidades_no_coinciden_tras_normalizar():
    """m2 vs m² SÍ coinciden (equivalentes); cm vs mm NO."""
    cand_a = _cand("X 1.1 Prueba", "La superficie será 5000 m2, como mínimo.", "superficie", "5000 m2", "m2")
    registro_b_coincide = {
        "valores": [{"nombre": "s_0", "valor_citado": "5000 m²", "unidad": "m²",
                    "comparador": ">=", "contexto_citado": "..."}],
        "no_reconocidas": [],
    }
    assert len(comparar_padre(cand_a, registro_b_coincide)["promovidas"]) == 1

    registro_b_no_coincide = {
        "valores": [{"nombre": "s_0", "valor_citado": "5000 mm", "unidad": "mm",
                    "comparador": ">=", "contexto_citado": "..."}],
        "no_reconocidas": [],
    }
    resultado = comparar_padre(cand_a, registro_b_no_coincide)
    assert not resultado["promovidas"]
    assert len(resultado["pendientes"]) == 2  # la de A sin confirmar + la de B como hallazgo nuevo


def test_comparar_padre_discrepancia_de_valor_va_a_pendientes_con_las_dos_lecturas():
    cand_a = _cand("X 1.1 Prueba", "La altura será 80 cm, como mínimo.", "altura", "80 cm", "cm")
    registro_b = {
        "valores": [{"nombre": "altura_0", "valor_citado": "90 cm", "unidad": "cm",
                    "comparador": ">=", "contexto_citado": "..."}],
        "no_reconocidas": [],
    }
    resultado = comparar_padre(cand_a, registro_b)
    assert not resultado["promovidas"]
    pendientes = resultado["pendientes"]
    assert len(pendientes) == 2  # A (80cm, sin confirmar) y B (90cm, hallazgo nuevo)
    valores_a = [p["lectura_a"]["valor"] for p in pendientes if p["lectura_a"]]
    valores_b = [p["lectura_b"]["valor"] for p in pendientes if p["lectura_b"]]
    assert valores_a == [80.0]
    assert valores_b == [90.0]


def test_comparar_padre_sin_lectura_b_deja_pendiente_solo_con_lectura_a():
    cand_a = _cand("X 1.1 Prueba", "La altura será 80 cm, como mínimo.", "altura", "80 cm", "cm")
    resultado = comparar_padre(cand_a, None)
    assert not resultado["promovidas"]
    assert len(resultado["pendientes"]) == 1
    assert resultado["pendientes"][0]["lectura_a"]["valor"] == 80.0
    assert resultado["pendientes"][0]["lectura_b"] is None
    assert "no segmentó" in resultado["pendientes"][0]["motivo"]


def test_valores_convertibles_a_no_incluye_grupos_no_atomicos():
    """Reutiliza el guardián del Prompt 1.5 (`_descomponer`): un artículo
    con dos cifras en la misma cláusula no aporta ningún convertible."""
    cand = {
        "articulo": "X 1.1 Prueba",
        "texto_original": "capacidad mayor que 200 vehículos o con superficie mayor que 5000 m2, se aplicará.",
        "materia_sugerida": "seguridad_utilizacion",
        "documento_identificador": "DB-SUA",
        "parametros": [
            {"nombre": "capacidad", "valor_citado": "200 vehículos", "unidad": "vehículos",
             "comparador": ">", "contexto_citado": "capacidad mayor que 200 vehículos"},
            {"nombre": "superficie", "valor_citado": "5000 m2", "unidad": "m2",
             "comparador": ">", "contexto_citado": "con superficie mayor que 5000 m2"},
        ],
    }
    assert _valores_convertibles_a(cand) == []


# --- Integración real, contra el PDF y las candidatas reales de DB-SUA -----

def _ejecutar(tmp_path):
    salida = tmp_path / "corpus"
    pendientes = tmp_path / "pendientes.jsonl"
    resultado = procesar(CANDIDATAS, PDF, salida, pendientes)
    return resultado, salida, pendientes


def test_produce_al_menos_tres_verificada_automatica_reales(tmp_path):
    resultado, _, _ = _ejecutar(tmp_path)
    assert len(resultado["verificadas"]) >= 3


def test_concept_ids_verificados_incluyen_los_tres_esperados(tmp_path):
    resultado, _, _ = _ejecutar(tmp_path)
    vistos = set()
    for ruta in resultado["verificadas"]:
        doc = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        for regla in doc["reglas"]:
            vistos.add(regla["concept_id"])
    assert vistos >= CONCEPT_IDS_VERIFICADOS


def test_cada_fichero_verificado_es_valido_y_lleva_hash_del_pdf(tmp_path):
    resultado, _, _ = _ejecutar(tmp_path)
    assert resultado["verificadas"]
    for ruta in resultado["verificadas"]:
        assert ruta.name.startswith("_"), f"{ruta.name} no empieza por «_»: el loader lo vería"
        doc = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        for regla in doc["reglas"]:
            assert regla["estado"] == "VERIFICADA_AUTOMATICA"
        assert doc["norma"]["fuente"]["documento_sha256"] == resultado["sha256_pdf"]
        assert len(resultado["sha256_pdf"]) == 64
        fallos = validar_fichero(doc)
        assert not fallos, f"{ruta.name} no pasa validar_fichero: {fallos}"


def test_golden_resalto_maximo_junta_1_2_valor_confirmado_por_las_dos_rutas(tmp_path):
    """El caso adversarial del Prompt 1.5 (DB-SUA 1.2): el resalto máximo de
    junta (4 mm) sale confirmado por las dos rutas — la ruta A vía IA, la
    ruta B vía el patrón «más de» añadido tras encontrar este hueco real."""
    resultado, _, _ = _ejecutar(tmp_path)
    encontrado = None
    for ruta in resultado["verificadas"]:
        doc = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        for regla in doc["reglas"]:
            if regla["concept_id"] == "es.rd_173_2010.seguridad_utilizacion.1_2_discontinuidades_en_el_pavimento":
                encontrado = regla
    assert encontrado is not None
    assert encontrado["parametro"]["valores"][0]["valor"] == 4.0
    assert encontrado["parametro"]["unidad"] == "mm"


def test_pendientes_dobles_no_pierden_ninguna_cifra_en_silencio(tmp_path):
    _, _, pendientes_ruta = _ejecutar(tmp_path)
    pendientes = [json.loads(linea) for linea in pendientes_ruta.read_text(encoding="utf-8").splitlines()]
    assert pendientes
    for p in pendientes:
        assert p.get("motivo")
        assert p.get("lectura_a") or p.get("lectura_b"), f"pendiente sin ninguna lectura: {p}"


def test_los_5_articulos_sin_segmentar_por_la_ruta_b_estan_declarados(tmp_path):
    resultado, _, _ = _ejecutar(tmp_path)
    assert len(resultado["articulos_sin_ruta_b"]) == 5
    numeros = {a.split()[1] for a in resultado["articulos_sin_ruta_b"]}
    assert numeros == {"1.5", "2.1", "2.2", "8.1", "8.2"}


def test_idempotente_no_repite_la_extraccion_de_la_ruta_b(tmp_path):
    """La segunda corrida lee el `.jsonl` ya escrito por
    `extraccion/estado/ruta_b/` en vez de re-segmentar y re-extraer —
    determinista, así que el resultado tiene que ser idéntico de todas
    formas, pero esto prueba que el camino de caché funciona sin excepción."""
    r1, _, _ = _ejecutar(tmp_path)
    r2, _, _ = _ejecutar(tmp_path)
    assert r1["segmentadas_b"] == r2["segmentadas_b"]
    assert len(r1["verificadas"]) == len(r2["verificadas"])
