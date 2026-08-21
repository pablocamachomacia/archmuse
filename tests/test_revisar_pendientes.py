"""scripts/revisar_pendientes.py (Prompt 2 §5.5) — resolución simulada, sin
terminal interactivo real: `entrada`/`salida` son inyectables precisamente
para esto.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extraccion import almacen  # noqa: E402
from normativa.validacion import validar_fichero  # noqa: E402
from scripts.revisar_pendientes import (  # noqa: E402
    _clave,
    _ya_resueltas,
    procesar,
    resolver_uno,
)

CANDIDATAS = RAIZ / "extraccion" / "estado" / "candidatas" / "codigotecnico__DB-SUA__3cfb5bbb135e.jsonl"

PENDIENTE_DISCREPANCIA = {
    "candidata_padre": "DB-SUA 1.1 Prueba",
    "parametro_nombre": "altura",
    "motivo": "la ruta B no produjo el mismo valor/unidad para este artículo",
    "lectura_a": {"valor": 80.0, "unidad": "cm", "contexto_citado": "La altura será 80 cm, como mínimo."},
    "lectura_b": {"valor": 90.0, "unidad": "cm", "contexto_citado": "La altura será 90 cm, como mínimo."},
}

PENDIENTE_SOLO_A = {
    "candidata_padre": "DB-SUA 1.2 Prueba",
    "parametro_nombre": "resalto",
    "motivo": "la ruta B no segmentó este artículo",
    "lectura_a": {"valor": 4.0, "unidad": "mm", "contexto_citado": "No tendrá juntas... 4 mm."},
    "lectura_b": None,
}


def _entrada(respuestas):
    it = iter(respuestas)
    return lambda _prompt: next(it)


def test_resolver_uno_elige_a():
    resolucion = resolver_uno(PENDIENTE_DISCREPANCIA, entrada=_entrada(["a"]), salida=lambda *_: None)
    assert resolucion["resolucion"] == "A"
    assert resolucion["valor_final"] == 80.0
    assert resolucion["unidad_final"] == "cm"
    assert resolucion["resuelto_por"] == "Pablo"
    assert resolucion["fecha"]


def test_resolver_uno_elige_b():
    resolucion = resolver_uno(PENDIENTE_DISCREPANCIA, entrada=_entrada(["b"]), salida=lambda *_: None)
    assert resolucion["resolucion"] == "B"
    assert resolucion["valor_final"] == 90.0


def test_resolver_uno_corrige_a_mano():
    resolucion = resolver_uno(PENDIENTE_DISCREPANCIA, entrada=_entrada(["m", "85", "cm"]), salida=lambda *_: None)
    assert resolucion["resolucion"] == "manual"
    assert resolucion["valor_final"] == 85.0
    assert resolucion["unidad_final"] == "cm"


def test_resolver_uno_a_mano_con_coma_decimal():
    resolucion = resolver_uno(PENDIENTE_DISCREPANCIA, entrada=_entrada(["m", "85,5", "cm"]), salida=lambda *_: None)
    assert resolucion["valor_final"] == 85.5


def test_resolver_uno_descarta():
    resolucion = resolver_uno(PENDIENTE_DISCREPANCIA, entrada=_entrada(["d"]), salida=lambda *_: None)
    assert resolucion["resolucion"] == "descartada"
    assert resolucion["valor_final"] is None


def test_resolver_uno_salta_no_devuelve_nada():
    assert resolver_uno(PENDIENTE_DISCREPANCIA, entrada=_entrada(["s"]), salida=lambda *_: None) is None


def test_resolver_uno_no_ofrece_b_si_no_hay_lectura_b():
    """PENDIENTE_SOLO_A no tiene lectura_b — elegir "b" no es una opción
    válida y se trata como "saltar", no como un error que rompa el flujo."""
    resultado = resolver_uno(PENDIENTE_SOLO_A, entrada=_entrada(["b"]), salida=lambda *_: None)
    assert resultado is None


def test_resolver_uno_a_mano_con_valor_invalido_no_registra_nada():
    resolucion = resolver_uno(PENDIENTE_DISCREPANCIA, entrada=_entrada(["m", "no-es-un-numero", "cm"]),
                              salida=lambda *_: None)
    assert resolucion is None


# --- procesar(): registro en resoluciones.jsonl + generación de regla ------

def test_procesar_registra_resolucion_y_genera_regla_verificada(tmp_path):
    ruta_resoluciones = tmp_path / "resoluciones.jsonl"

    pendientes_ruta = tmp_path / "pendientes.jsonl"
    pendientes_ruta.write_text(json.dumps(PENDIENTE_DISCREPANCIA, ensure_ascii=False) + "\n", encoding="utf-8")

    candidatas = almacen.leer(CANDIDATAS)
    cand_padre = next(c for c in candidatas if "2.2 Atrapamiento" in c["articulo"])
    por_padre = {PENDIENTE_DISCREPANCIA["candidata_padre"]: cand_padre}

    salida_dir = tmp_path / "corpus"
    salida_dir.mkdir()
    resultado = procesar(
        pendientes_ruta, por_padre, salida_dir, "0" * 64,
        entrada=_entrada(["a"]), salida=lambda *_: None,
        resoluciones_ruta=ruta_resoluciones,
    )

    assert resultado["resueltos_ahora"] == 1
    assert len(resultado["generadas"]) == 1
    assert ruta_resoluciones.exists()
    registradas = [json.loads(linea) for linea in ruta_resoluciones.read_text(encoding="utf-8").splitlines()]
    assert len(registradas) == 1
    assert registradas[0]["resolucion"] == "A"
    assert registradas[0]["candidata_padre"] == PENDIENTE_DISCREPANCIA["candidata_padre"]

    doc = yaml.safe_load(resultado["generadas"][0].read_text(encoding="utf-8"))
    regla = doc["reglas"][0]
    assert regla["estado"] == "VERIFICADA_AUTOMATICA"
    assert any(t.startswith("resuelto_manualmente:") for t in regla["tags"])
    fallos = validar_fichero(doc)
    assert not fallos, fallos


def test_procesar_descartar_no_genera_regla_pero_registra(tmp_path):
    ruta_resoluciones = tmp_path / "resoluciones.jsonl"

    pendientes_ruta = tmp_path / "pendientes.jsonl"
    pendientes_ruta.write_text(json.dumps(PENDIENTE_DISCREPANCIA, ensure_ascii=False) + "\n", encoding="utf-8")

    salida_dir = tmp_path / "corpus"
    salida_dir.mkdir()
    resultado = procesar(
        pendientes_ruta, {}, salida_dir, "0" * 64,
        entrada=_entrada(["d"]), salida=lambda *_: None,
        resoluciones_ruta=ruta_resoluciones,
    )
    assert resultado["resueltos_ahora"] == 1
    assert not resultado["generadas"]
    registradas = [json.loads(linea) for linea in ruta_resoluciones.read_text(encoding="utf-8").splitlines()]
    assert registradas[0]["resolucion"] == "descartada"


def test_procesar_es_reanudable_no_vuelve_a_preguntar_lo_ya_resuelto(tmp_path):
    ruta_resoluciones = tmp_path / "resoluciones.jsonl"

    pendientes_ruta = tmp_path / "pendientes.jsonl"
    pendientes_ruta.write_text(json.dumps(PENDIENTE_DISCREPANCIA, ensure_ascii=False) + "\n", encoding="utf-8")
    salida_dir = tmp_path / "corpus"
    salida_dir.mkdir()

    # Primera pasada: se descarta y queda registrado.
    procesar(pendientes_ruta, {}, salida_dir, "0" * 64, entrada=_entrada(["d"]), salida=lambda *_: None,
             resoluciones_ruta=ruta_resoluciones)
    assert _clave(PENDIENTE_DISCREPANCIA) in _ya_resueltas(ruta_resoluciones)

    # Segunda pasada sobre el MISMO fichero de pendientes: no debería
    # consumir ninguna entrada de `entrada` (si lo hiciera, `next()` fallaría
    # porque el iterador está vacío).
    resultado = procesar(pendientes_ruta, {}, salida_dir, "0" * 64, entrada=_entrada([]), salida=lambda *_: None,
                         resoluciones_ruta=ruta_resoluciones)
    assert resultado["resueltos_ahora"] == 0
