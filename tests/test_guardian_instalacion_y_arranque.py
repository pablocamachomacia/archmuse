# -*- coding: utf-8 -*-
"""`C-16` también fuera del comando: instalar, actualizar, ARCHMUSE-ACTUALIZAR y el
arranque de AutoCAD no cambian ningún ajuste suyo (2026-09-16).

**Por qué.** FILEDIA apareció a 0 dos veces, las dos justo después de instalar una
versión. El guardián sólo vigilaba el comando ARCHMUSE, así que nada vigilaba lo
que pasa alrededor de una instalación. La causa resultó estar fuera de ArchMuse
—Core Console, ver `tests/test_core_console_no_toca_autocad.py`—, pero sólo se
supo midiendo, y lo que se midió a mano tiene que quedar vigilado:

- **La instalación y la actualización** corren fuera de AutoCAD. Las vigila
  `herramientas/guardian_autocad/guardian_registro.py`: foto del registro de
  AutoCAD antes y después. Aquí, sobre un árbol del registro de prueba, con el
  actualizador de verdad.
- **ARCHMUSE-ACTUALIZAR y el arranque** corren dentro de AutoCAD. Se leen del
  `.lsp`, y el guardián de AutoCAD guarda su foto en un fichero para poder
  comparar después de instalar y de cerrar y abrir AutoCAD.
"""
from __future__ import annotations

import re
import uuid
import winreg
from pathlib import Path

import pytest

from test_actualizaciones import _instalada, _paquete, mundo  # noqa: F401 - el fixture
from test_lsp_deja_autocad_como_estaba import _defun, _forma, _sin_comentarios

RAIZ = Path(__file__).resolve().parent.parent
LSP = (RAIZ / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")
CODIGO = _sin_comentarios(LSP)
GUARDIAN = RAIZ / "herramientas" / "guardian_autocad" / "guardian.lsp"
PRODUCTO = r"R26.0\ACAD-PRUEBA:000"

#: Lo que un trozo de código que corre en AutoCAD no puede usar si no es el comando.
_CAMBIAN_AUTOCAD = ("(setvar", "(command", "command-s", "vl-cmdf", "vla-SetVariable",
                    "vl-registry-write", "vl-registry-delete", "(setenv", "vla-put-")


# -- El registro alrededor de instalar y actualizar ---------------------------

def _crear(ruta, valores):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ruta) as k:
        for nombre, (tipo, valor) in valores.items():
            winreg.SetValueEx(k, nombre, 0, tipo, valor)


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


@pytest.fixture
def autocad_de_prueba(mundo, monkeypatch):  # noqa: F811
    """Un perfil de AutoCAD de mentira en el registro: FILEDIA a 1, CMDECHO y una
    ruta de confianza de otro programa. Borrado al final."""
    local = mundo[0]
    raiz = r"Software\ArchMuse-tests\%s" % uuid.uuid4().hex
    _crear(r"%s\%s\FixedProfile\General Configuration" % (raiz, PRODUCTO),
           {"FileDialog": (winreg.REG_DWORD, 1), "CmdDia": (winreg.REG_DWORD, 1)})
    _crear(r"%s\%s\Profiles\<<Perfil sin nombre>>\Variables" % (raiz, PRODUCTO),
           {"TRUSTEDPATHS": (winreg.REG_SZ, r"C:\OtroPrograma"),
            "CMDECHO": (winreg.REG_SZ, "1")})
    monkeypatch.setenv("ARCHMUSE_RAIZ_AUTOCAD", raiz)
    monkeypatch.setattr(local, "autocad_abierto", lambda: False)
    yield mundo, raiz
    _borrar_arbol(raiz)


def _guardian_registro():
    from herramientas.guardian_autocad import guardian_registro
    return guardian_registro


def test_instalar_una_version_solo_anade_nuestra_ruta_de_confianza(autocad_de_prueba, tmp_path):
    (local, firma, _act, actualizador, _), raiz = autocad_de_prueba
    gr = _guardian_registro()
    _instalada(local, "0.3.8")
    antes = gr.foto(raiz)
    actualizador.instalar(str(_paquete(firma, tmp_path / "p.archmuse", "0.3.9")), arrancar=False)
    cambios = gr.diferencias(antes, gr.foto(raiz))
    assert [c for c in cambios if c[0].endswith("TRUSTEDPATHS")], "no ha añadido la ruta: el test no prueba nada"
    assert gr.inesperadas(cambios, local.ruta_de_confianza()) == []


def test_activar_y_volver_atras_no_tocan_nada_mas(autocad_de_prueba, tmp_path):
    (local, firma, _act, actualizador, _), raiz = autocad_de_prueba
    gr = _guardian_registro()
    _instalada(local, "0.3.8")
    actualizador.instalar(str(_paquete(firma, tmp_path / "p.archmuse", "0.3.9")), arrancar=False)
    antes = gr.foto(raiz)
    actualizador.volver(arrancar=False)
    actualizador.activar("0.3.9", arrancar=False)
    assert gr.diferencias(antes, gr.foto(raiz)) == []


def test_el_guardian_del_registro_caza_un_ajuste_cambiado_al_instalar(autocad_de_prueba, tmp_path,
                                                                      monkeypatch):
    """Roto a propósito: una instalación que además pone FILEDIA a 0."""
    (local, firma, _act, actualizador, _), raiz = autocad_de_prueba
    gr = _guardian_registro()
    _instalada(local, "0.3.8")
    original = local.anadir_confianza

    def y_ademas_filedia(escribir=True):
        hechos = original(escribir)
        if escribir:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"%s\%s\FixedProfile\General Configuration" % (raiz, PRODUCTO),
                                0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, "FileDialog", 0, winreg.REG_DWORD, 0)
        return hechos
    monkeypatch.setattr(local, "anadir_confianza", y_ademas_filedia)
    antes = gr.foto(raiz)
    actualizador.instalar(str(_paquete(firma, tmp_path / "p.archmuse", "0.3.9")), arrancar=False)
    inesperadas = gr.inesperadas(gr.diferencias(antes, gr.foto(raiz)), local.ruta_de_confianza())
    assert [c[0] for c in inesperadas] == [
        r"%s\FixedProfile\General Configuration : FileDialog" % PRODUCTO]


def test_el_guardian_del_registro_no_perdona_otra_ruta_de_confianza():
    gr = _guardian_registro()
    nuestra = r"C:\ArchMuse\Contents"
    buena = [(r"X\Variables : TRUSTEDPATHS", r"C:\Otro", r"C:\Otro;" + nuestra)]
    mala = [(r"X\Variables : TRUSTEDPATHS", r"C:\Otro", r"C:\Otro;C:\Intruso")]
    borra_otra = [(r"X\Variables : TRUSTEDPATHS", r"C:\Otro;" + nuestra, nuestra)]
    assert gr.inesperadas(buena, nuestra) == []
    assert gr.inesperadas(mala, nuestra) == mala
    assert gr.inesperadas(borra_otra, nuestra) == borra_otra


def test_ni_el_instalador_ni_el_actualizador_escriben_otro_valor_del_perfil():
    """Leyendo el código: `TRUSTEDPATHS` es lo único del perfil de AutoCAD que
    escriben, y el instalador sólo registra la extensión `.archmuse`."""
    capa_b = RAIZ / "empaquetado" / "capa_b"
    escrituras = []
    for f in list(capa_b.glob("*.py")) + list(capa_b.glob("*.pyw")):
        for m in re.finditer(r"SetValueEx\([^,]+,\s*([^,]+),", f.read_text(encoding="utf-8")):
            escrituras.append((f.name, m.group(1).strip()))
    assert escrituras == [("archmuse_local.py", '"TRUSTEDPATHS"')], escrituras
    iss = (RAIZ / "empaquetado" / "ArchMuse-Beta.iss").read_text(encoding="utf-8")
    subclaves = re.findall(r'Root:\s*HK\w+;\s*Subkey:\s*"([^"]+)"', iss)
    assert subclaves and all(s.startswith("Software\\Classes\\") for s in subclaves), subclaves


# -- Dentro de AutoCAD: el arranque y ARCHMUSE-ACTUALIZAR ----------------------

def _formas_de_primer_nivel(codigo):
    i, formas = 0, []
    while True:
        j = codigo.find("(", i)
        if j < 0:
            return formas
        forma = _forma(codigo, j)
        formas.append(forma)
        i = j + len(forma)


def test_lo_que_se_ejecuta_al_cargar_no_cambia_autocad():
    """Al abrir AutoCAD el paquete carga el `.lsp`: todo lo que no es un `defun`
    se ejecuta en ese momento, en cada dibujo."""
    al_cargar = [f for f in _formas_de_primer_nivel(CODIGO) if not f.startswith("(defun ")]
    assert al_cargar, "no encuentro nada que se ejecute al cargar"
    for forma in al_cargar:
        for via in _CAMBIAN_AUTOCAD:
            assert via not in forma, "al cargar se ejecuta %s: %s" % (via, forma[:120])


def test_archmuse_actualizar_y_el_aviso_no_cambian_autocad():
    for nombre in ("c:ARCHMUSE-ACTUALIZAR", "am:ofrecer-actualizacion", "am:actualizaciones-al-cargar",
                   "am:actualizacion-pendiente-en", "am:lanzar-sin-ventana", "am:escribe-fichero"):
        cuerpo = _defun(CODIGO, nombre)
        for via in _CAMBIAN_AUTOCAD:
            assert via not in cuerpo, "%s usa %s" % (nombre, via)
    ofrecer = _defun(CODIGO, "am:ofrecer-actualizacion")
    assert re.findall(r'"\\" (\w[^"]*)"', ofrecer) == ["actualizador --instalar-pendiente"], (
        "ARCHMUSE-ACTUALIZAR lanza algo más que el actualizador")


def test_solo_el_comando_cambia_variables():
    """CMDECHO se devuelve en el *error* del comando (`C-16`). Fuera de él no hay
    *error* que la devuelva, así que fuera de él no se toca ninguna."""
    comando = _defun(CODIGO, "c:ARCHMUSE")
    assert CODIGO.count("(setvar") == comando.count("(setvar")


# -- El guardián de AutoCAD compara también después de cerrar y abrir ----------

def test_el_guardian_guarda_la_foto_en_un_fichero_para_despues_de_reiniciar():
    codigo = _sin_comentarios(GUARDIAN.read_text(encoding="utf-8"))
    assert "archmuse-guardian-foto" in codigo, "la foto de antes sólo vive en memoria"
    guardar = _defun(codigo, "amg:guardar-foto")
    leer = _defun(codigo, "amg:leer-foto")
    assert "amg:a-texto" in guardar and "(read" in leer
    # `prin1` escribe los reales con 6 cifras: leídos otra vez, no serían iguales y
    # el guardián avisaría de cambios que no hay.
    assert "(rtos v 2 16)" in _defun(codigo, "amg:a-texto")
    comando = _defun(codigo, "c:ARCHMUSE-GUARDIAN")
    assert "(amg:leer-foto)" in comando, "sin foto en memoria no mira la guardada"
    assert "vl-file-delete" in comando, "la foto guardada no se retira tras comparar"
    assert "amg:guardar-foto" in comando


def test_lo_que_se_ignora_entre_sesiones_lleva_motivo_y_no_es_un_ajuste():
    """Entre dos sesiones cambian solas unas pocas variables del dibujo y del
    registro de sesión. Ignorar un ajuste de verdad ahí escondería justo el fallo
    que se busca: FILEDIA apareció a 0 de una sesión a la siguiente."""
    codigo = _sin_comentarios(GUARDIAN.read_text(encoding="utf-8"))
    ini = codigo.index("(setq *amg:por-otra-sesion*")
    lista = _forma(codigo, ini)
    pares = re.findall(r'\("(\w+)" \. "([^"]+)"\)', lista)
    assert pares, "no encuentro la lista"
    nombres = {n for n, _motivo in pares}
    assert nombres <= {"LOGFILENAME", "TDCREATE", "TDUCREATE", "TDUUPDATE"}, nombres
    assert all(len(motivo) > 20 for _n, motivo in pares)
    comparar = _defun(codigo, "amg:comparar")
    assert "(and otra-sesion (assoc (car d) *amg:por-otra-sesion*))" in comparar, (
        "la lista de otra sesión se aplica también dentro de una misma sesión")


def test_ninguna_forma_del_guardian_se_corta_en_un_scr():
    """`probar_en_core_console.ps1` incrusta cada forma en UNA línea del `.scr`, y
    Core Console corta las líneas de unos 2048 caracteres (medido el 2026-09-16:
    una forma de 2235 se cortó y la prueba se quedó colgada 300 s; 1805 pasaba)."""
    formas, actual, prof = [], [], 0
    for linea in GUARDIAN.read_text(encoding="utf-8").splitlines():
        s = linea.strip()
        if not s or s.startswith(";"):
            continue
        actual.append(s)
        prof += linea.count("(") - linea.count(")")
        if prof == 0:
            formas.append(" ".join(actual))
            actual = []
    largas = [(len(f), f[:60]) for f in formas if len(f.encode("cp1252", "replace")) > 1800]
    assert largas == [], largas


def test_el_leeme_explica_las_tres_pasadas():
    leeme = (RAIZ / "herramientas" / "guardian_autocad" / "LEEME.md").read_text(encoding="utf-8")
    for texto in ("ARCHMUSE-ACTUALIZAR", "cerrar y abrir AutoCAD", "guardian_registro.py"):
        assert texto in leeme, texto
