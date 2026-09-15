# -*- coding: utf-8 -*-
"""El banco de compatibilidad externo (`benchmark/ejecutar.py`), con planos sintéticos.

Ningún plano real: cada caso se dibuja aquí con el generador del fixture sintético
(`tests/fixtures/cuadro_sintetico/generar.py`) y un cuadro relleno a mano. Lo que
se prueba es el banco —cómo compara, cómo clasifica, qué escribe y qué no—, no
la medición, que tiene sus propios tests.
"""
from __future__ import annotations

import csv
import importlib.util
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)


def _cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


banco = _cargar("benchmark_ejecutar", os.path.join(RAIZ, "benchmark", "ejecutar.py"))
GENERADOR = os.path.join(RAIZ, "tests", "fixtures", "cuadro_sintetico", "generar.py")

#: Tres piezas interiores, sin la dudosa del fixture ni exteriores: 20,00 · 12,00 ·
#: 9,00. La envolvente rotulada del generador da la construida: 49,30 (`C-12`).
#:
#: **Sin terraza a propósito.** Con una fila «terraza» sin número el detector no
#: la reconoce, la terraza medida queda sin fila y `C-6` retira los dos totales
#: (medido el 2026-09-15). Es lo que hace ArchMuse, no un fallo del banco, y un
#: caso «todo coincide» no puede apoyarse en él.
RECINTOS = (
    ("Salón/cocina", 0.0, 0.0, 5.0, 4.0),
    ("Dormitorio 1", 5.1, 0.0, 8.1, 4.0),
    ("Dormitorio 2", 8.2, 0.0, 11.2, 3.0),
)
CABECERA = (
    (0, 0, "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA"),
    (1, 0, "ESPACIOS INTERIORES"), (1, 1, "SUPERFICIES UTILES"),
    (1, 2, "ESPACIOS EXTERIORES"), (1, 3, "SUPERFICIES UTILES"),
    (2, 0, "salón + cocina"),
    (3, 0, "dormitorio 1"),
    (4, 0, "dormitorio 2"),
    (5, 0, "TOTAL SUP. INTERIOR (m2)"), (5, 2, "TOTAL SUP. EXTERIOR (m2)"),
    (6, 0, "TOTAL S. UTIL(m2)"),
    (7, 0, "S. CONSTRUIDA C."),
    (8, 0, "VIVIENDA TIPO"), (8, 1, "VT1 /3"), (8, 2, "NUMERO UDS:"),
)
#: Las cifras del cuadro «bien rellenado», escritas como las escribe una persona.
CIFRAS_BUENAS = {(2, 1): "20,00 m²", (3, 1): "12.00m²", (4, 1): "9,00 m2", (5, 1): "41,00",
                 (7, 1): "49.30"}


def _dibujar(destino, cifras=None, con_cuadro=True, recintos=RECINTOS):
    generador = _cargar("generar_cuadro_sintetico_banco", GENERADOR)
    generador.RECINTOS = recintos
    cuadro = list(CABECERA) + [(f, c, t) for (f, c), t in (cifras or {}).items()]
    generador.CUADRO = tuple(cuadro)
    if con_cuadro:
        return generador.guardar(str(destino))
    doc, _bloque, _handle = generador.construir()
    doc.saveas(str(destino))
    return str(destino)


@pytest.fixture
def carpetas(tmp_path):
    planos, salida = tmp_path / "planos", tmp_path / "resultados"
    planos.mkdir()
    return planos, salida


def _uno(hecho):
    assert len(hecho["filas"]) == 1
    return hecho["filas"][0], hecho["detalles"][0]


def _escribir_clasificacion(ruta, filas):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(["plano", "vivienda", "campo", "clase", "nota"])
        escritor.writerows(filas)


# -- Cifras ---------------------------------------------------------------

@pytest.mark.parametrize("texto, valor", [
    ("23.24m²", 23.24), ("8,53 m2", 8.53), ("3.16", 3.16), (" 12 ", 12.0), ("7,5 m^2", 7.5)])
def test_lee_la_cifra_que_escribe_una_persona(texto, valor):
    assert banco.cifra_de_referencia(texto) == pytest.approx(valor)


@pytest.mark.parametrize("texto", [None, "", "-", "N/D", "VT1/3", "12 uds"])
def test_lo_que_no_es_una_cifra_no_es_referencia(texto):
    assert banco.cifra_de_referencia(texto) is None


def test_la_tolerancia_es_un_centimo_de_metro():
    assert banco.coinciden(58.96, 58.97)
    assert not banco.coinciden(58.96, 58.98)


# -- Resultados -----------------------------------------------------------

def test_cuadro_que_coincide_entero_es_PASS(carpetas):
    planos, salida = carpetas
    _dibujar(planos / "a.dxf", CIFRAS_BUENAS)
    fila, detalle = _uno(banco.ejecutar(str(planos), str(salida)))
    assert fila["resultado"] == banco.PASS, (fila, detalle["comparaciones"])
    assert fila["coincidencias"] == 5 and fila["mismatches"] == 0
    assert fila["viviendas_detectadas"] == 1 and fila["viviendas_correctas"] == 1
    assert fila["estancias"] == 3
    campos = {c["campo"] for c in detalle["comparaciones"] if c["estado"] == banco.COINCIDENCIA}
    assert "superficie_construida_cerrada" in campos, "la construida sale de C-12 y también se compara"


def test_un_mismatch_sin_explicar_nunca_es_PASS(carpetas):
    planos, salida = carpetas
    _dibujar(planos / "a.dxf", {**CIFRAS_BUENAS, (4, 1): "9,40"})
    fila, detalle = _uno(banco.ejecutar(str(planos), str(salida)))
    assert fila["resultado"] == banco.PENDIENTE
    [m] = [c for c in detalle["comparaciones"] if c["estado"] == banco.MISMATCH]
    assert (m["campo"], m["referencia"], m["archmuse"]) == ("dormitorio_2", 9.4, 9.0)


@pytest.mark.parametrize("clase, esperado", [
    ("redondeo", "PARTIAL"), ("cuadro desactualizado", "PARTIAL"),
    ("error de ArchMuse", "FAIL"), ("pendiente de determinar", "PENDIENTE DE REVISIÓN"),
    ("me lo invento", "PENDIENTE DE REVISIÓN")])
def test_la_clase_la_pone_una_persona_y_decide_el_resultado(carpetas, clase, esperado):
    planos, salida = carpetas
    _dibujar(planos / "a.dxf", {**CIFRAS_BUENAS, (4, 1): "9,40"})
    salida.mkdir()
    clasificacion = salida / "clasificacion.csv"
    _escribir_clasificacion(clasificacion, [["plano-01", "VT1/3", "dormitorio_2", clase, ""]])
    fila, _d = _uno(banco.ejecutar(str(planos), str(salida)))
    assert fila["resultado"] == esperado


def test_un_campo_que_archmuse_deja_vacio_lleva_su_motivo(carpetas):
    """`C-1`: el útil total no se rellena nunca. Si su cuadro lo trae, ArchMuse
    queda vacío con motivo: PARTIAL, no PASS y no MISMATCH."""
    planos, salida = carpetas
    _dibujar(planos / "a.dxf", {**CIFRAS_BUENAS, (6, 1): "45,50"})
    fila, detalle = _uno(banco.ejecutar(str(planos), str(salida)))
    [vacio] = [c for c in detalle["comparaciones"] if c["estado"] == banco.VACIO_CON_MOTIVO]
    assert vacio["campo"] == "total_util" and vacio["motivo"]
    assert fila["resultado"] == banco.PARTIAL and fila["mismatches"] == 0


def test_plano_sin_cuadro_es_SIN_REFERENCIA_con_su_cobertura(carpetas):
    planos, salida = carpetas
    _dibujar(planos / "a.dxf", con_cuadro=False)
    fila, _d = _uno(banco.ejecutar(str(planos), str(salida)))
    assert fila["resultado"] == banco.SIN_REFERENCIA
    assert fila["viviendas_detectadas"] == 1 and fila["estancias"] == 3
    assert fila["superficies"] >= 3 and fila["cifras_comparadas"] == 0


def test_un_fichero_ilegible_es_FAIL_y_no_para_el_banco(carpetas):
    planos, salida = carpetas
    (planos / "a.dxf").write_text("esto no es un DXF", encoding="utf-8")
    _dibujar(planos / "b.dxf", CIFRAS_BUENAS)
    hecho = banco.ejecutar(str(planos), str(salida))
    resultados = sorted(f["resultado"] for f in hecho["filas"])
    assert resultados == [banco.FAIL, banco.PASS]


def test_un_DWG_sin_conversor_es_FAIL_con_motivo(carpetas):
    planos, salida = carpetas
    (planos / "a.dwg").write_bytes(b"AC1032 no importa")
    fila, _d = _uno(banco.ejecutar(str(planos), str(salida), buscar=lambda: None))
    assert fila["resultado"] == banco.FAIL and fila["formato"] == "DWG"
    assert "no hay ODA File Converter ni AutoCAD Core Console" in fila["motivo"]


# -- Privacidad ------------------------------------------------------------

def test_ningun_nombre_de_fichero_sale_en_lo_que_se_comparte(carpetas):
    planos, salida = carpetas
    _dibujar(planos / "Estudio Fulano - Calle Real 12.dxf", CIFRAS_BUENAS)
    hecho = banco.ejecutar(str(planos), str(salida))
    for nombre in ("resultados.csv", "resumen.md", "detalle.json", "mismatches.csv"):
        with open(os.path.join(hecho["carpeta"], nombre), encoding="utf-8-sig") as f:
            texto = f.read()
        assert "Fulano" not in texto and "Calle Real" not in texto, nombre
    assert hecho["filas"][0]["plano"] == "plano-01"


def test_los_ids_no_cambian_al_anadir_planos(carpetas):
    planos, salida = carpetas
    _dibujar(planos / "m.dxf", CIFRAS_BUENAS)
    primero = banco.ejecutar(str(planos), str(salida))["filas"][0]["plano"]
    _dibujar(planos / "a.dxf", con_cuadro=False)
    segunda = banco.ejecutar(str(planos), str(salida))["filas"]
    assert {f["plano"]: f["resultado"] for f in segunda}[primero] == banco.PASS
    assert sorted(f["plano"] for f in segunda) == ["plano-01", "plano-02"]


def test_se_niega_a_leer_planos_dentro_del_repositorio(tmp_path):
    with pytest.raises(banco.CarpetaNoPermitida):
        banco.ejecutar(os.path.join(RAIZ, "tests"), str(tmp_path))


def test_se_niega_a_escribir_resultados_en_otra_carpeta_del_repositorio(carpetas):
    planos, _salida = carpetas
    with pytest.raises(banco.CarpetaNoPermitida):
        banco.ejecutar(str(planos), os.path.join(RAIZ, "docs"))


def test_git_ignora_los_resultados():
    with open(os.path.join(RAIZ, ".gitignore"), encoding="utf-8") as f:
        assert "benchmark/resultados/" in f.read().splitlines()


# -- Resumen ---------------------------------------------------------------

def test_el_resumen_solo_lista_causas_que_aparecen(carpetas):
    planos, salida = carpetas
    _dibujar(planos / "a.dxf", CIFRAS_BUENAS)
    hecho = banco.ejecutar(str(planos), str(salida))
    with open(hecho["resumen"], encoding="utf-8") as f:
        resumen = f.read()
    assert "| PASS | 1 |" in resumen
    assert "FAIL" not in resumen.split("## Por plano")[0]
    assert "C-7" in resumen


def test_un_patron_repetido_es_el_que_sale_en_dos_planos(carpetas):
    planos, salida = carpetas
    for nombre in ("a.dxf", "b.dxf"):
        _dibujar(planos / nombre, {**CIFRAS_BUENAS, (6, 1): "45,50"})
    hecho = banco.ejecutar(str(planos), str(salida))
    with open(hecho["resumen"], encoding="utf-8") as f:
        repetidos = f.read().split("## Patrones repetidos")[1].split("##")[0]
    assert "**2 planos**" in repetidos


def test_la_causa_agrupa_sin_nombres_ni_cifras():
    assert (banco.causa("hay 2 viviendas en el plano rotuladas «VT1/3»: no se sabe")
            == banco.causa("hay 3 viviendas en el plano rotuladas «VT2/2»: no se sabe"))
