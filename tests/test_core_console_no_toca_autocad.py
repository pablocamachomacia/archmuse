# -*- coding: utf-8 -*-
"""Core Console no puede dejar cambiado el AutoCAD del arquitecto (`C-16`, 2026-09-16).

**Medido el 2026-09-16 en el ordenador de Pablo, con su AutoCAD abierto:** AutoCAD
Core Console escribe `FileDialog = 0` en
`HKCU\\...\\FixedProfile\\General Configuration` **al arrancar** y lo devuelve **sólo
si sale limpio**. Matado a mitad, el 0 se queda; y un AutoCAD que se abra mientras
corre lo lee. Así quedó FILEDIA a 0 dos veces: el 14-sep, al matar unos Core
Console colgados, y el 15-sep, con una sonda que no salió limpia. Cada reinicio de
AutoCAD después de instalar lo volvía a leer. Con `/isolate` no toca el registro,
ni matado (medido el mismo día).

Por eso Core Console se lanza desde un solo sitio, `herramientas/core_console.py`:
siempre con `/isolate`, y devolviendo después lo que haya cambiado en
`FixedProfile\\General Configuration` aunque haya que matarlo.

Los tests de comportamiento usan una consola falsa sobre un árbol del registro de
prueba (`ARCHMUSE_RAIZ_AUTOCAD`); nunca tocan el AutoCAD de nadie. El de Core
Console de verdad sólo corre con `ARCHMUSE_PROBAR_CORE_CONSOLE=1`.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import textwrap
import uuid
import winreg
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

GENERAL = r"FixedProfile\General Configuration"
PRODUCTO = r"R26.0\ACAD-PRUEBA:000"


@pytest.fixture
def perfil_de_prueba(monkeypatch):
    """Un árbol `R26.0\\<producto>\\FixedProfile\\General Configuration` con
    FileDialog = 1 bajo `HKCU\\Software\\ArchMuse-tests\\<uuid>`, borrado al final."""
    raiz = r"Software\ArchMuse-tests\%s" % uuid.uuid4().hex
    clave = "%s\\%s\\%s" % (raiz, PRODUCTO, GENERAL)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, clave) as k:
        winreg.SetValueEx(k, "FileDialog", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "OtroAjuste", 0, winreg.REG_SZ, "igual")
    monkeypatch.setenv("ARCHMUSE_RAIZ_AUTOCAD", raiz)
    yield raiz, clave
    _borrar_arbol(raiz)


def _borrar_arbol(ruta):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ruta) as k:
            hijas = []
            while True:
                try:
                    hijas.append(winreg.EnumKey(k, len(hijas)))
                except OSError:
                    break
    except OSError:
        return
    for h in hijas:
        _borrar_arbol(ruta + "\\" + h)
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, ruta)


def _file_dialog(clave):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave) as k:
        return winreg.QueryValueEx(k, "FileDialog")[0]


def _consola_falsa(tmp_path, sale_sola: bool) -> list:
    """Hace lo que se midió en Core Console: pone FileDialog a 0 al arrancar y,
    si `sale_sola`, termina sin devolverlo (como una sonda con un error);
    si no, se queda colgada hasta que la maten. Apunta sus argumentos."""
    script = tmp_path / "consola_falsa.py"
    script.write_text(textwrap.dedent('''
        import os, sys, time, winreg
        open(sys.argv[1], "w", encoding="utf-8").write("\\n".join(sys.argv[2:]))
        raiz = os.environ["ARCHMUSE_RAIZ_AUTOCAD"]
        clave = raiz + r"\\%s\\%s"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "FileDialog", 0, winreg.REG_DWORD, 0)
        if %s:
            sys.exit(0)
        time.sleep(120)
    ''' % (PRODUCTO, GENERAL, "True" if sale_sola else "False")), encoding="utf-8")
    return [sys.executable, str(script), str(tmp_path / "argumentos.txt")]


# -- La puerta única ----------------------------------------------------------

def test_core_console_se_lanza_siempre_aislado():
    from herramientas import core_console as cc

    args = cc.argumentos("s.scr", dibujo="p.dwg", carpeta_aislada=r"C:\tmp\aislada",
                         solo_lectura=True)
    i = args.index("/isolate")
    assert args[i + 1] and args[i + 2] == r"C:\tmp\aislada"
    assert args[args.index("/s") + 1] == "s.scr" and args[args.index("/i") + 1] == "p.dwg"
    assert "/readonly" in args


def test_matada_por_tiempo_devuelve_filedia(perfil_de_prueba, tmp_path):
    from herramientas import core_console as cc

    _raiz, clave = perfil_de_prueba
    r = cc.ejecutar("s.scr", orden=_consola_falsa(tmp_path, sale_sola=False), plazo_s=5,
                    cwd=str(tmp_path))
    assert r.agotado, "la consola falsa no se ha colgado: el test no prueba nada"
    assert _file_dialog(clave) == 1, "Core Console matado ha dejado FILEDIA a 0 en el perfil"
    assert any("FileDialog" in c for c in r.restaurado)
    assert "/isolate" in (tmp_path / "argumentos.txt").read_text(encoding="utf-8").split("\n")


def test_una_salida_sin_devolverlo_tambien_se_corrige(perfil_de_prueba, tmp_path):
    from herramientas import core_console as cc

    _raiz, clave = perfil_de_prueba
    r = cc.ejecutar("s.scr", orden=_consola_falsa(tmp_path, sale_sola=True), plazo_s=30,
                    cwd=str(tmp_path))
    assert not r.agotado
    assert _file_dialog(clave) == 1


def test_una_carpeta_aislada_pedida_se_usa_y_no_se_borra(perfil_de_prueba, tmp_path):
    """La prueba del guardián compara dos sesiones: con la carpeta aislada nueva
    cada vez, todas las rutas de AutoCAD cambiarían (medido el 2026-09-16)."""
    from herramientas import core_console as cc

    aislada = tmp_path / "aislada"
    cc.ejecutar("s.scr", orden=_consola_falsa(tmp_path, sale_sola=True), plazo_s=30,
                cwd=str(tmp_path), carpeta_aislada=str(aislada))
    argumentos = (tmp_path / "argumentos.txt").read_text(encoding="utf-8").split("\n")
    assert argumentos[argumentos.index("/isolate") + 2] == str(aislada)
    assert aislada.is_dir()


def test_lo_que_no_ha_cambiado_no_se_escribe(perfil_de_prueba, tmp_path):
    """Devolver es sólo lo que cambió: escribir el resto pisaría un ajuste que
    el arquitecto hubiera cambiado mientras tanto en otra clave."""
    from herramientas import core_console as cc

    _raiz, _clave = perfil_de_prueba
    r = cc.ejecutar("s.scr", orden=_consola_falsa(tmp_path, sale_sola=True), plazo_s=30,
                    cwd=str(tmp_path))
    assert [c for c in r.restaurado if "OtroAjuste" in c] == []


# -- Nadie más lanza Core Console ---------------------------------------------

_EXTENSIONES = {".py", ".pyw", ".ps1", ".psm1", ".bat", ".cmd", ".iss", ".lsp", ".scr"}
_FUERA = {"venv", ".venv", "tests", "docs", "node_modules", ".git", "__pycache__"}


def _codigo_del_repositorio():
    for ruta in RAIZ.rglob("*"):
        if ruta.suffix.lower() not in _EXTENSIONES or not ruta.is_file():
            continue
        partes = set(ruta.relative_to(RAIZ).parts)
        if partes & _FUERA:
            continue
        yield ruta


def test_solo_la_puerta_unica_nombra_core_console():
    """El 14 y el 15-sep Core Console se lanzó a mano, sin `/isolate`, y dejó
    FILEDIA a 0. Cualquier otro sitio que lo lance tiene que pasar por
    `herramientas/core_console.py`."""
    propia = RAIZ / "herramientas" / "core_console.py"
    fuera = [str(r.relative_to(RAIZ)) for r in _codigo_del_repositorio()
             if r != propia and re.search(r"(?i)accoreconsole", r.read_text(encoding="utf-8",
                                                                            errors="replace"))]
    assert fuera == [], "lanzan Core Console sin la puerta única: %s" % fuera


def test_el_benchmark_convierte_los_dwg_por_la_puerta_unica():
    texto = (RAIZ / "benchmark" / "ejecutar.py").read_text(encoding="utf-8")
    assert "core_console" in texto and "subprocess.run([programa, \"/i\"" not in texto


def test_el_comando_de_autocad_nunca_lanza_core_console():
    lsp = (RAIZ / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")
    assert not re.search(r"(?i)accoreconsole|acad\.exe", lsp)


# -- Core Console de verdad, sólo si se pide -----------------------------------

CONSOLA_REAL = Path(r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe")


@pytest.mark.skipif(os.environ.get("ARCHMUSE_PROBAR_CORE_CONSOLE") != "1" or not CONSOLA_REAL.exists(),
                    reason="Core Console de verdad: ARCHMUSE_PROBAR_CORE_CONSOLE=1 (lee el perfil real)")
def test_core_console_de_verdad_matado_no_deja_filedia_cambiado(tmp_path):
    """Lee el perfil de AutoCAD de esta máquina antes y después de matar Core
    Console a mitad. No escribe en él salvo para devolver lo que cambie."""
    from herramientas import core_console as cc

    antes = cc.foto_de_dialogos()
    scr = tmp_path / "esperar.scr"
    scr.write_bytes(b'(command "_.DELAY" 20000)\r\n_.QUIT\r\n_Y\r\n')
    r = cc.ejecutar(str(scr), plazo_s=6, cwd=str(tmp_path))
    assert r.agotado
    assert cc.foto_de_dialogos() == antes
    assert r.restaurado == [], "con /isolate no debería haber nada que devolver: %s" % r.restaurado


def test_la_herramienta_de_barrido_y_la_prueba_del_guardian_usan_la_puerta():
    for ps1 in ("herramientas/barrido_dwg/barrer.ps1",
                "herramientas/guardian_autocad/probar_en_core_console.ps1"):
        texto = (RAIZ / ps1).read_text(encoding="utf-8")
        assert "herramientas.core_console" in texto, ps1
        assert "Start-Process -FilePath $Consola" not in texto, ps1
