"""scripts/curar_corpus.py — docs/prd/2026-08-21-curacion-y-firma-del-corpus-db-sua.md.

Los dos actos se prueban por separado a propósito (§2 del PRD, "nunca
fusionados en una tecla"): `resolver` nunca escribe en `normativa/es/`, y
`firmar` es la única acción que sí lo hace, siempre a partir de
resoluciones ya aprobadas.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extraccion import almacen  # noqa: E402
from normativa import loader  # noqa: E402
from normativa.validacion import validar_fichero, validar_firma_de_regla_firmada  # noqa: E402
from scripts.curar_corpus import (  # noqa: E402
    _clave,
    _claves_registradas,
    _generar_regla_firmada,
    procesar_firmar,
    procesar_resolver,
    resolver_uno,
)

CANDIDATAS = RAIZ / "extraccion" / "estado" / "candidatas" / "codigotecnico__DB-SUA__3cfb5bbb135e.jsonl"
FIXTURE_CORPUS = RAIZ / "tests" / "fixtures" / "corpus_ficticio"

PENDIENTE_DISCREPANCIA = {
    "candidata_padre": "DB-SUA 2.2 Atrapamiento",
    "parametro_nombre": "distancia_objeto_fijo_proximo_puerta_corredera_manual",
    "motivo": "la ruta B no produjo el mismo valor/unidad para este artículo",
    "lectura_a": {"valor": 20.0, "unidad": "cm", "contexto_citado": "la distancia será 20 cm, como mínimo."},
    "lectura_b": {"valor": 25.0, "unidad": "cm", "contexto_citado": "la distancia será 25 cm, como mínimo."},
}

PENDIENTE_SOLO_B = {
    "candidata_padre": "DB-SUA 2.2 Atrapamiento",
    "parametro_nombre": "otro_parametro",
    "motivo": "solo la ruta B ancló este valor: hallazgo nuevo, no confirmado por la ruta A",
    "lectura_a": None,
    "lectura_b": {"valor": 4.0, "unidad": "mm", "contexto_citado": "No tendrá juntas... 4 mm."},
}


def _entrada(respuestas):
    it = iter(respuestas)
    return lambda _prompt: next(it)


def _sin_salida(*_a, **_k):
    pass


# --- resolver_uno: las cuatro opciones a/r/e/s ------------------------------

def test_resolver_uno_aprueba_unica_lectura_b():
    resolucion = resolver_uno(PENDIENTE_SOLO_B, entrada=_entrada(["a"]), salida=_sin_salida)
    assert resolucion["decision"] == "aprobada"
    assert resolucion["fuente"] == "B"
    assert resolucion["valor_final"] == 4.0
    assert resolucion["timestamp"]


def test_resolver_uno_aprueba_elige_entre_dos_lecturas():
    resolucion = resolver_uno(PENDIENTE_DISCREPANCIA, entrada=_entrada(["a", "b"]), salida=_sin_salida)
    assert resolucion["decision"] == "aprobada"
    assert resolucion["fuente"] == "B"
    assert resolucion["valor_final"] == 25.0


def test_resolver_uno_aprobar_sin_elegir_lectura_valida_no_registra_nada():
    resolucion = resolver_uno(PENDIENTE_DISCREPANCIA, entrada=_entrada(["a", "x"]), salida=_sin_salida)
    assert resolucion is None


def test_resolver_uno_rechaza_con_motivo():
    resolucion = resolver_uno(
        PENDIENTE_DISCREPANCIA, entrada=_entrada(["r", "las dos rutas citan cifras distintas, no me fío de ninguna"]),
        salida=_sin_salida,
    )
    assert resolucion["decision"] == "rechazada"
    assert "no me fío" in resolucion["motivo"]


def test_resolver_uno_rechazar_sin_motivo_no_registra_nada():
    resolucion = resolver_uno(PENDIENTE_DISCREPANCIA, entrada=_entrada(["r", "   "]), salida=_sin_salida)
    assert resolucion is None


def test_resolver_uno_edita_y_aprueba():
    resolucion = resolver_uno(PENDIENTE_DISCREPANCIA, entrada=_entrada(["e", "22,5", "cm"]), salida=_sin_salida)
    assert resolucion["decision"] == "aprobada"
    assert resolucion["fuente"] == "editado"
    assert resolucion["valor_final"] == 22.5
    assert resolucion["unidad_final"] == "cm"


def test_resolver_uno_edita_con_valor_invalido_no_registra_nada():
    resolucion = resolver_uno(PENDIENTE_DISCREPANCIA, entrada=_entrada(["e", "no-es-numero", "cm"]), salida=_sin_salida)
    assert resolucion is None


def test_resolver_uno_salta_no_devuelve_nada():
    assert resolver_uno(PENDIENTE_DISCREPANCIA, entrada=_entrada(["s"]), salida=_sin_salida) is None


# --- procesar_resolver: ledger, reanudable, NUNCA toca normativa/es/ --------

def test_procesar_resolver_registra_en_ledger_append_only(tmp_path):
    ruta_resoluciones = tmp_path / "resoluciones.jsonl"
    pendientes_ruta = tmp_path / "pendientes.jsonl"
    pendientes_ruta.write_text(json.dumps(PENDIENTE_DISCREPANCIA, ensure_ascii=False) + "\n", encoding="utf-8")

    resultado = procesar_resolver(
        pendientes_ruta, entrada=_entrada(["a", "a"]), salida=_sin_salida, resoluciones_ruta=ruta_resoluciones,
    )
    assert resultado == {"total_pendientes": 1, "resueltas_ahora": 1, "aprobadas": 1, "rechazadas": 0}
    registradas = [json.loads(l) for l in ruta_resoluciones.read_text(encoding="utf-8").splitlines()]
    assert len(registradas) == 1
    assert registradas[0]["decision"] == "aprobada"


def test_procesar_resolver_es_reanudable(tmp_path):
    ruta_resoluciones = tmp_path / "resoluciones.jsonl"
    pendientes_ruta = tmp_path / "pendientes.jsonl"
    pendientes_ruta.write_text(json.dumps(PENDIENTE_DISCREPANCIA, ensure_ascii=False) + "\n", encoding="utf-8")

    procesar_resolver(pendientes_ruta, entrada=_entrada(["r", "motivo"]), salida=_sin_salida,
                       resoluciones_ruta=ruta_resoluciones)
    assert _clave(PENDIENTE_DISCREPANCIA) in _claves_registradas(ruta_resoluciones)

    # Segunda pasada sobre el MISMO fichero: no debe consumir ninguna
    # respuesta (si lo hiciera, next() fallaría — el iterador está vacío).
    resultado = procesar_resolver(pendientes_ruta, entrada=_entrada([]), salida=_sin_salida,
                                   resoluciones_ruta=ruta_resoluciones)
    assert resultado["resueltas_ahora"] == 0


def test_procesar_resolver_nunca_escribe_reglas():
    """`resolver` no recibe siquiera un directorio de salida — no hay forma
    de que escriba en normativa/es/, ni por accidente."""
    import inspect
    from scripts.curar_corpus import procesar_resolver as f
    parametros = list(inspect.signature(f).parameters)
    assert "salida_dir" not in parametros
    assert not any("normativa" in p for p in parametros)


# --- procesar_firmar: única acción que escribe reglas, inmutable -----------

def _por_padre():
    candidatas = almacen.leer(CANDIDATAS)
    return {c["articulo"]: c for c in candidatas}


def test_procesar_firmar_exige_curador(tmp_path):
    ruta_resoluciones = tmp_path / "resoluciones.jsonl"
    ruta_resoluciones.write_text("", encoding="utf-8")
    with pytest.raises(SystemExit):
        procesar_firmar(ruta_resoluciones, {}, tmp_path, "0" * 64, curador="", salida=_sin_salida,
                        firmas_ruta=tmp_path / "firmas.jsonl")


def test_procesar_firmar_genera_regla_firmada_valida(tmp_path):
    ruta_resoluciones = tmp_path / "resoluciones.jsonl"
    resolucion = {
        "candidata_padre": PENDIENTE_DISCREPANCIA["candidata_padre"],
        "parametro_nombre": PENDIENTE_DISCREPANCIA["parametro_nombre"],
        "decision": "aprobada", "fuente": "A",
        "valor_final": 20.0, "unidad_final": "cm",
        "contexto_citado": PENDIENTE_DISCREPANCIA["lectura_a"]["contexto_citado"],
        "timestamp": "2026-08-21T10:00:00+00:00",
    }
    ruta_resoluciones.write_text(json.dumps(resolucion, ensure_ascii=False) + "\n", encoding="utf-8")

    salida_dir = tmp_path / "corpus"
    salida_dir.mkdir()
    firmas_ruta = tmp_path / "firmas.jsonl"

    resultado = procesar_firmar(
        ruta_resoluciones, _por_padre(), salida_dir, "0" * 64, curador="Pablo",
        salida=_sin_salida, firmas_ruta=firmas_ruta,
    )
    assert len(resultado["firmadas_ahora"]) == 1
    destino = resultado["firmadas_ahora"][0]
    assert not destino.name.startswith("_"), "una regla FIRMADA debe ser descubrible por el loader"

    doc = yaml.safe_load(destino.read_text(encoding="utf-8"))
    regla = doc["reglas"][0]
    assert regla["estado"] == "FIRMADA"
    assert regla["firma"] == {"curador": "Pablo", "fecha": date.today().isoformat()}
    assert doc["norma"]["fuente"]["documento_sha256"] == "0" * 64
    assert not validar_fichero(doc)

    firmas = [json.loads(l) for l in firmas_ruta.read_text(encoding="utf-8").splitlines()]
    assert len(firmas) == 1
    assert firmas[0]["curador"] == "Pablo"
    assert firmas[0]["concept_id"] == regla["concept_id"]


def test_procesar_firmar_ignora_rechazadas(tmp_path):
    ruta_resoluciones = tmp_path / "resoluciones.jsonl"
    resolucion = {
        "candidata_padre": PENDIENTE_DISCREPANCIA["candidata_padre"],
        "parametro_nombre": PENDIENTE_DISCREPANCIA["parametro_nombre"],
        "decision": "rechazada", "motivo": "no me fío", "timestamp": "2026-08-21T10:00:00+00:00",
    }
    ruta_resoluciones.write_text(json.dumps(resolucion, ensure_ascii=False) + "\n", encoding="utf-8")
    salida_dir = tmp_path / "corpus"
    salida_dir.mkdir()

    resultado = procesar_firmar(ruta_resoluciones, _por_padre(), salida_dir, "0" * 64, curador="Pablo",
                                 salida=_sin_salida, firmas_ruta=tmp_path / "firmas.jsonl")
    assert resultado["firmadas_ahora"] == []


def test_procesar_firmar_es_reanudable_no_duplica(tmp_path):
    ruta_resoluciones = tmp_path / "resoluciones.jsonl"
    resolucion = {
        "candidata_padre": PENDIENTE_DISCREPANCIA["candidata_padre"],
        "parametro_nombre": PENDIENTE_DISCREPANCIA["parametro_nombre"],
        "decision": "aprobada", "fuente": "A", "valor_final": 20.0, "unidad_final": "cm",
        "contexto_citado": "", "timestamp": "2026-08-21T10:00:00+00:00",
    }
    ruta_resoluciones.write_text(json.dumps(resolucion, ensure_ascii=False) + "\n", encoding="utf-8")
    salida_dir = tmp_path / "corpus"
    salida_dir.mkdir()
    firmas_ruta = tmp_path / "firmas.jsonl"

    procesar_firmar(ruta_resoluciones, _por_padre(), salida_dir, "0" * 64, curador="Pablo",
                     salida=_sin_salida, firmas_ruta=firmas_ruta)
    resultado_2 = procesar_firmar(ruta_resoluciones, _por_padre(), salida_dir, "0" * 64, curador="Pablo",
                                   salida=_sin_salida, firmas_ruta=firmas_ruta)
    assert resultado_2["firmadas_ahora"] == []
    assert len(list(salida_dir.glob("*.yaml"))) == 1


def test_procesar_firmar_regla_firmada_es_inmutable_no_se_sobreescribe(tmp_path):
    """Si el fichero de destino ya existe (p. ej. escrito a mano, o el
    ledger de firmas se perdió) `firmar` nunca lo pisa — lo reporta como
    conflicto y sigue con las demás."""
    ruta_resoluciones = tmp_path / "resoluciones.jsonl"
    resolucion = {
        "candidata_padre": PENDIENTE_DISCREPANCIA["candidata_padre"],
        "parametro_nombre": PENDIENTE_DISCREPANCIA["parametro_nombre"],
        "decision": "aprobada", "fuente": "A", "valor_final": 20.0, "unidad_final": "cm",
        "contexto_citado": "", "timestamp": "2026-08-21T10:00:00+00:00",
    }
    ruta_resoluciones.write_text(json.dumps(resolucion, ensure_ascii=False) + "\n", encoding="utf-8")
    salida_dir = tmp_path / "corpus"
    salida_dir.mkdir()

    # Pre-existe un fichero con el nombre que le tocaría (simula el ledger
    # de firmas perdido/desincronizado, el peor caso). El slug incluye
    # SIEMPRE el parametro_nombre (sufijo_desambiguador incondicional, ver
    # docstring de _generar_regla_firmada) — no solo el artículo.
    concept_slug = "2_2_atrapamiento_" + PENDIENTE_DISCREPANCIA["parametro_nombre"]
    (salida_dir / f"firmada_db_sua_{concept_slug}.yaml").write_text("version: 1\n", encoding="utf-8")

    resultado = procesar_firmar(ruta_resoluciones, _por_padre(), salida_dir, "0" * 64, curador="Pablo",
                                 salida=_sin_salida, firmas_ruta=tmp_path / "firmas.jsonl")
    assert resultado["firmadas_ahora"] == []
    assert len(resultado["conflictos"]) == 1
    # El fichero preexistente sigue intacto, no se ha tocado.
    assert (salida_dir / f"firmada_db_sua_{concept_slug}.yaml").read_text(encoding="utf-8") == "version: 1\n"


# --- Los dos actos están separados, verificado por test --------------------

def test_resolver_y_firmar_son_pasos_separados(tmp_path):
    """resolver() no deja ninguna regla en disco; solo firmar(), a partir
    de lo que resolver() aprobó, escribe algo en normativa/es/."""
    ruta_resoluciones = tmp_path / "resoluciones.jsonl"
    pendientes_ruta = tmp_path / "pendientes.jsonl"
    pendientes_ruta.write_text(json.dumps(PENDIENTE_DISCREPANCIA, ensure_ascii=False) + "\n", encoding="utf-8")
    salida_dir = tmp_path / "corpus"
    salida_dir.mkdir()

    procesar_resolver(pendientes_ruta, entrada=_entrada(["a", "a"]), salida=_sin_salida,
                       resoluciones_ruta=ruta_resoluciones)
    assert list(salida_dir.glob("*.yaml")) == [], "resolver() no debe escribir ninguna regla"

    procesar_firmar(ruta_resoluciones, _por_padre(), salida_dir, "0" * 64, curador="Pablo",
                     salida=_sin_salida, firmas_ruta=tmp_path / "firmas.jsonl")
    assert len(list(salida_dir.glob("*.yaml"))) == 1, "firmar() es quien escribe la regla, y solo tras aprobar"


# --- Las 101 entradas reales, de principio a fin, sin excepción ------------

PENDIENTES_REALES = RAIZ / "extraccion" / "estado" / "pendientes" / "codigotecnico__DB-SUA__3cfb5bbb135e.verificacion_doble.jsonl"


def test_procesar_resolver_recorre_las_101_entradas_reales_sin_excepcion(tmp_path):
    """Contra el fichero real del Prompt 2 (no un fixture sintético):
    saltar las 101 no debe lanzar ninguna excepción, sea cual sea la forma
    exacta de cada entrada (con o sin lectura_a/b, con o sin
    `no_reconocidas_b_del_articulo`)."""
    ruta_resoluciones = tmp_path / "resoluciones.jsonl"
    resultado = procesar_resolver(
        PENDIENTES_REALES, entrada=_entrada(["s"] * 101), salida=_sin_salida,
        resoluciones_ruta=ruta_resoluciones,
    )
    assert resultado["total_pendientes"] == 101
    assert resultado["resueltas_ahora"] == 0  # todo saltado, nada registrado


def test_procesar_resolver_aprueba_las_101_entradas_reales_sin_excepcion(tmp_path):
    """Igual que el anterior pero aprobando todo lo aprobable (eligiendo
    siempre "a" cuando hace falta elegir entre A/B) — recorre de verdad la
    rama de generar una resolución para cada una de las 101, no solo la de
    saltar."""
    ruta_resoluciones = tmp_path / "resoluciones.jsonl"
    # Suficientes "a" para cubrir tanto la pregunta principal como la
    # sub-pregunta ocasional "¿cuál apruebas? [a/b]" sin agotar el iterador.
    respuestas = _entrada(["a"] * 300)
    resultado = procesar_resolver(
        PENDIENTES_REALES, entrada=respuestas, salida=_sin_salida, resoluciones_ruta=ruta_resoluciones,
    )
    assert resultado["total_pendientes"] == 101
    assert resultado["resueltas_ahora"] == 101
    assert resultado["aprobadas"] == 101


# --- Validación 19: firma obligatoria para estado FIRMADA -------------------

def _doc_firmado(firma=None, estado="FIRMADA"):
    regla = dict(_REGLA_BASE)
    regla["estado"] = estado
    if firma is not None:
        regla["firma"] = firma
    doc = dict(_DOC_BASE)
    doc["reglas"] = [regla]
    return doc


_REGLA_BASE = {
    "concept_id": "es.ficticio.materia.regla_firma_test",
    "instance_id": "es.ficticio.materia.regla_firma_test@1",
    "nombre": "Regla de prueba de firma",
    "materia": "seguridad_utilizacion",
    "tipo": "exigencia_cuantitativa",
    "patron": "UMBRAL_SIMPLE",
    "prioridad": "bloqueante",
    "nivel_de_conocimiento": 2,
    "aplicabilidad": {"ambito": "es"},
    "parametro": {"ejes": [], "unidad": "cm", "repliegue": ["todos"], "valores": [{"valor": 20}]},
    "mensaje": "mensaje de prueba",
    "vigencia": {"vigencia_desde": "2010-04-11"},
}
_DOC_BASE = {
    "version": 1,
    "norma": {
        "concept_id": "es.ficticio.norma",
        "instance_id": "es.ficticio.norma@1",
        "ambito": "es",
        "fuente": {
            "rango": "Real Decreto", "organismo": "Ministerio ficticio",
            "identificador_oficial": "FICTICIO-000/2010", "titulo": "Documento ficticio",
            "boletin": "FICTICIO-A-2010-0001",
        },
        "articulo": {"documento_basico": "DB-SUA"},
        "vigencia": {"vigencia_desde": "2010-04-11"},
    },
}


def test_validacion_19_rechaza_firmada_sin_bloque_firma():
    fallos = validar_firma_de_regla_firmada(_doc_firmado(firma=None))
    assert fallos and "[19]" in fallos[0]


def test_validacion_19_rechaza_firma_sin_curador():
    fallos = validar_firma_de_regla_firmada(_doc_firmado(firma={"curador": "", "fecha": "2026-08-21"}))
    assert any("curador" in f for f in fallos)


def test_validacion_19_rechaza_fecha_no_iso():
    fallos = validar_firma_de_regla_firmada(_doc_firmado(firma={"curador": "Pablo", "fecha": "21/08/2026"}))
    assert any("fecha" in f for f in fallos)


def test_validacion_19_acepta_firma_completa():
    assert validar_firma_de_regla_firmada(_doc_firmado(firma={"curador": "Pablo", "fecha": "2026-08-21"})) == []


def test_validacion_19_no_exige_nada_si_no_esta_firmada():
    assert validar_firma_de_regla_firmada(_doc_firmado(firma=None, estado="BORRADOR")) == []


def test_validar_fichero_completo_rechaza_firmada_sin_firma():
    fallos = validar_fichero(_doc_firmado(firma=None))
    assert any("[19]" in f for f in fallos)


# --- Integración: el loader carga normativa/es/ sin errores tras firmar ----

def test_loader_carga_sin_errores_tras_firmar_una_regla_de_prueba(tmp_path):
    """Reproduce el patrón ya usado por
    tests/test_normativa_borrador_no_afirma.py: corpus ficticio copiado a
    un directorio temporal, una regla nueva colocada en `es/estatal/`, y el
    loader real cargando ese árbol — nunca el corpus de producción."""
    corpus_tmp = tmp_path / "corpus_ficticio"
    shutil.copytree(FIXTURE_CORPUS, corpus_tmp)

    ruta_resoluciones = tmp_path / "resoluciones.jsonl"
    resolucion = {
        "candidata_padre": PENDIENTE_DISCREPANCIA["candidata_padre"],
        "parametro_nombre": PENDIENTE_DISCREPANCIA["parametro_nombre"],
        "decision": "aprobada", "fuente": "A", "valor_final": 20.0, "unidad_final": "cm",
        "contexto_citado": PENDIENTE_DISCREPANCIA["lectura_a"]["contexto_citado"],
        "timestamp": "2026-08-21T10:00:00+00:00",
    }
    ruta_resoluciones.write_text(json.dumps(resolucion, ensure_ascii=False) + "\n", encoding="utf-8")

    salida_dir = corpus_tmp / "es" / "estatal"
    resultado = procesar_firmar(
        ruta_resoluciones, _por_padre(), salida_dir, "0" * 64, curador="Pablo",
        salida=_sin_salida, firmas_ruta=tmp_path / "firmas.jsonl",
    )
    assert len(resultado["firmadas_ahora"]) == 1
    destino = resultado["firmadas_ahora"][0]

    # Es descubrible (sin «_») y la carga completa no rechaza nada.
    descubiertos = loader.descubrir(["es"], raiz=corpus_tmp)
    assert destino in descubiertos

    carga = loader.cargar(["es"], raiz=corpus_tmp)
    assert not carga.hay_rechazos, carga.rechazados

    reglas_firmadas = [r for r in carga.reglas if r.get("estado") == "FIRMADA"]
    assert len(reglas_firmadas) == 1
    assert reglas_firmadas[0]["firma"]["curador"] == "Pablo"


def test_loader_carga_sin_colision_al_firmar_todo_el_corpus_real_de_db_sua(tmp_path):
    """El escenario real que Pablo va a ejecutar esta semana: firmar TODAS
    las sub-candidatas de las 20 candidatas reales de DB-SUA (incluida
    DB-SUA 1.4, que por sí sola aporta ~15 exigencias dimensionales bajo el
    mismo artículo) — no una regla de prueba aislada.

    Antes de la corrección de la validación 14 (docs/design/2026-08-21-
    limite-aplicabilidad-generica-verificada-automatica.md), esto rompía la
    carga del corpus COMPLETO al firmar la segunda regla de la misma
    materia+patrón con `aplicabilidad` genérica — determinista, no un
    problema de volumen. Este test fija ese comportamiento para que una
    regresión futura de la validación 14 no la reintroduzca en silencio."""
    corpus_tmp = tmp_path / "corpus_ficticio"
    shutil.copytree(FIXTURE_CORPUS, corpus_tmp)
    salida_dir = corpus_tmp / "es" / "estatal"

    candidatas = almacen.leer(CANDIDATAS)
    n_firmadas = 0
    for cand in candidatas:
        for p in (cand.get("parametros") or []):
            resolucion = {
                "parametro_nombre": p["nombre"], "valor_final": 20.0,
                "unidad_final": p.get("unidad") or "cm", "contexto_citado": p.get("contexto_citado", ""),
            }
            if _generar_regla_firmada(resolucion, cand, salida_dir, "0" * 64, "Pablo", salida=_sin_salida):
                n_firmadas += 1

    assert n_firmadas >= 30, "el fixture de candidatas debería producir al menos 30 reglas firmables"

    carga = loader.cargar(["es"], raiz=corpus_tmp)
    assert not carga.hay_rechazos, carga.rechazados
    assert sum(1 for r in carga.reglas if r.get("estado") == "FIRMADA") == n_firmadas
