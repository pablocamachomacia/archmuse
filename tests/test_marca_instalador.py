# -*- coding: utf-8 -*-
"""El símbolo de ArchMuse en el instalador: icono, imágenes del asistente y dónde se usan.

**Por qué existe.** Hasta el 2026-09-15 el instalador llevaba el icono genérico de
Inno Setup (la caja con el CD), los accesos directos del menú Inicio salían con
el icono de Python —apuntan a `pythonw.exe`— y los ficheros `.archmuse` como una
hoja en blanco. El símbolo es la dirección «B1 · Paredes desplazadas», elegida por
Pablo, y lo genera `empaquetado/marca/generar_marca.py`.

Estos tests guardan tres cosas: que los ficheros versionados son los que dibuja
el script (cada tamaño del icono es su propio dibujo, no una reducción), que
tienen las medidas que pide Inno Setup, y que el `.iss` los usa en todos los
sitios donde antes salía otra cosa.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
MARCA = RAIZ / "empaquetado" / "marca"
ISS = RAIZ / "empaquetado" / "ArchMuse-Beta.iss"

sys.path.insert(0, str(MARCA))
import generar_marca as g  # noqa: E402


def _secciones() -> dict:
    iss = ISS.read_text(encoding="utf-8-sig")
    return dict(re.findall(r"^\[(\w+)\][ \t]*$(.*?)(?=^\[\w+\][ \t]*$|\Z)", iss, re.M | re.S))


def _directiva(nombre: str) -> str:
    m = re.search(r"^%s=(.*)$" % re.escape(nombre), _secciones()["Setup"], re.M)
    assert m, "falta %s en [Setup]" % nombre
    return m.group(1).strip()


# --- 1. Los ficheros ---------------------------------------------------------

def test_el_ico_lleva_los_cinco_tamanos_y_cada_uno_es_su_propio_dibujo():
    """Reducir el de 256 a 24 px pondría las paredes en 1,5 px: borrosas."""
    ico = Image.open(MARCA / "archmuse.ico")
    assert sorted(ico.ico.sizes()) == [(l, l) for l in g.TAMANOS_ICO]
    for lado in g.TAMANOS_ICO:
        guardado = ico.ico.getimage((lado, lado)).convert("RGBA").tobytes()
        assert guardado == g.icono(lado).tobytes(), "%d px no es el dibujo de ese tamaño" % lado


@pytest.mark.parametrize("lado", g.CABECERA)
def test_la_imagen_de_cabecera_es_cuadrada_y_es_la_que_dibuja_el_script(lado):
    imagen = Image.open(MARCA / ("cabecera-%d.png" % lado)).convert("RGBA")
    assert imagen.size == (lado, lado)
    assert imagen.tobytes() == g.icono(lado).tobytes()


@pytest.mark.parametrize("ancho,alto", g.LATERAL)
def test_la_imagen_lateral_tiene_la_medida_de_inno_y_fondo_negro(ancho, alto):
    imagen = Image.open(MARCA / ("lateral-%d.png" % ancho)).convert("RGB")
    assert imagen.size == (ancho, alto)
    for esquina in ((0, 0), (ancho - 1, 0), (0, alto - 1), (ancho - 1, alto - 1)):
        assert imagen.getpixel(esquina) == g.NEGRO[:3]


def test_las_medidas_son_las_de_la_documentacion_de_inno_setup():
    """Tablas de `topic_setup_wizardsmallimagefile` y `topic_setup_wizardimagefile`
    (Inno Setup 6.7), consultadas el 2026-09-14."""
    assert g.CABECERA == (58, 77, 97, 116, 124, 143, 159)
    assert g.LATERAL == ((202, 386), (269, 515), (336, 643), (403, 772),
                         (430, 824), (498, 953), (534, 1022))


# --- 2. Dónde se usan --------------------------------------------------------

def test_el_instalador_y_el_desinstalador_llevan_el_simbolo():
    assert _directiva("SetupIconFile") == r"marca\archmuse.ico"
    assert _directiva("UninstallDisplayIcon") == r"{app}\archmuse.ico"


def test_las_imagenes_del_asistente_van_en_todas_las_escalas():
    pequenas = _directiva("WizardSmallImageFile").split(",")
    assert pequenas == [r"marca\cabecera-%d.png" % l for l in g.CABECERA]
    laterales = _directiva("WizardImageFile").split(",")
    assert laterales == [r"marca\lateral-%d.png" % a for a, _ in g.LATERAL]
    for ruta in pequenas + laterales:
        assert (RAIZ / "empaquetado" / ruta).is_file(), ruta


def test_el_icono_se_instala_junto_a_la_aplicacion():
    assert re.search(r'^Source: "marca\\archmuse\.ico"; DestDir: "\{app\}"', _secciones()["Files"], re.M)


def test_ningun_acceso_directo_sale_con_el_icono_de_python():
    """Los que apuntan a `pythonw.exe` tomaban su icono."""
    lineas = [l for l in _secciones()["Icons"].splitlines() if l.startswith("Name:")]
    con_python = [l for l in lineas if "pythonw.exe" in l]
    assert con_python, "ya no hay accesos directos a pythonw.exe: revisa este test"
    for linea in con_python:
        assert 'IconFilename: "{app}\\archmuse.ico"' in linea, linea


def test_los_ficheros_archmuse_tienen_icono():
    """Sin `DefaultIcon`, Windows los enseña como una hoja en blanco."""
    registro = _secciones()["Registry"]
    assert re.search(r'Subkey: "Software\\Classes\\ArchMuse\.Actualizacion\\DefaultIcon"; '
                     r'ValueType: string; ValueName: ""; ValueData: "\{app\}\\archmuse\.ico,0"',
                     registro)


def test_los_datos_del_editor_estan_y_no_llevan_datos_personales():
    assert _directiva("AppPublisherURL") == "https://github.com/pablocamachomacia/archmuse"
    assert _directiva("AppSupportURL") == "https://github.com/pablocamachomacia/archmuse/issues"
    assert _directiva("AppCopyright") == "© 2026 ArchMuse"
    for nombre in ("VersionInfoVersion", "VersionInfoProductVersion"):
        assert _directiva(nombre) == "{#Version}"
    assert "@" not in _secciones()["Setup"]
