# -*- coding: utf-8 -*-
"""T4 y T5 del PRD de la beta: el comando busca su servidor, lo levanta si no
está, y **no escribe contra un servidor que no es el suyo**.

`docs/prd/2026-09-11-beta-instalable-en-el-ordenador-del-arquitecto.md`, D-1
(rama C) y D-2 (el cotejo). El cotejo es condición de la aprobación del PRD.

Como el resto de tests del `.lsp`, éstos leen el fichero: no hay AutoCAD aquí.
Prueban las promesas —de dónde sale el puerto, qué se lanza, en qué orden se
coteja y se escribe— y que las dos mitades (Python y LISP, `.iss` y LISP)
dicen lo mismo. **Que `_.DELAY` y `WScript.Shell` se comporten dentro de
AutoCAD como está escrito no lo prueba ninguno**: está anotado en el propio
`.lsp` y va al checklist del trial.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from analyzer import version as version_mod

RAIZ = Path(__file__).resolve().parent.parent
LSP = (RAIZ / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")
ISS = (RAIZ / "empaquetado" / "ArchMuse-Beta.iss").read_text(encoding="utf-8-sig")
VERSION_CORTA = re.search(r'\(setq \*am:version-corta\* "([^"]+)"\)', LSP).group(1)

CUERPO = {
    "capa": "00 areas",
    "recintos": [{"handle": "1", "capa": "00 areas", "color": 256, "cerrada": True,
                  "vertices": [[0, 0], [5, 0], [5, 4], [0, 4]]}],
    "textos": [{"texto": "Salón", "x": 2.5, "y": 2.0}],
}


def _defun(nombre: str) -> str:
    inicio = LSP.index("(defun %s " % nombre)
    fin = LSP.find("\n(defun ", inicio + 1)
    return LSP[inicio: fin if fin != -1 else len(LSP)]


@pytest.fixture(scope="module")
def cliente():
    import app as srv

    return srv.app.test_client()


# ── el servidor dice con qué .lsp va ────────────────────────────────────────

def test_salud_y_medicion_declaran_el_lsp_con_el_que_va_el_servidor(cliente):
    assert cliente.get("/api/salud").get_json()["lsp"] == VERSION_CORTA
    respuesta = cliente.post("/api/medicion-geometria?formato=lisp",
                             data=json.dumps(CUERPO), content_type="application/json")
    assert respuesta.status_code == 200
    # Exactamente lo que busca `am:valor-tras respuesta "lsp"`.
    assert '("lsp" . "%s")' % VERSION_CORTA in respuesta.get_data(as_text=True)


def test_el_version_json_del_paquete_manda_sobre_el_lsp_del_repositorio(tmp_path, monkeypatch):
    fichero = tmp_path / "version.json"
    fichero.write_text(json.dumps({"version": "0.3.2", "lsp": "9.9.9"}), encoding="utf-8")
    monkeypatch.setattr(version_mod, "_FICHERO", str(fichero))
    assert version_mod.lsp() == "9.9.9"


def test_sin_version_json_se_lee_del_propio_lsp(tmp_path, monkeypatch):
    """En el repositorio: editar el `.lsp` sin volver a cargarlo en AutoCAD
    también lo caza el cotejo, porque el servidor lee la versión del fichero."""
    monkeypatch.setattr(version_mod, "_FICHERO", str(tmp_path / "no-existe.json"))
    assert version_mod.lsp() == VERSION_CORTA


# ── T4: el puerto ───────────────────────────────────────────────────────────

def test_el_puerto_sale_de_servidor_json_y_ya_no_esta_escrito_a_mano():
    assert "localhost:5000" not in LSP
    assert "*am:url*" not in LSP
    cuerpo = _defun("am:puerto")
    assert "\\\\ArchMuse\\\\servidor.json" in cuerpo
    # La clave que busca el LISP es la que escribe `json.dump` en el lanzador.
    assert '"\\"puerto\\":"' in cuerpo
    assert '"puerto":' in json.dumps({"puerto": 5001, "version": "0.3.1"})


def test_todas_las_peticiones_usan_el_puerto_que_se_acaba_de_leer():
    assert "(am:url)" in _defun("am:post")
    assert "(am:url-base)" in _defun("am:salud-responde")


# ── T5: la rama C ───────────────────────────────────────────────────────────

def test_la_rama_c_lanza_lo_que_deja_el_instalador():
    cuerpo = _defun("am:servidor-instalado")
    assert "\\\\ArchMuse\\\\runtime\\\\pythonw.exe" in cuerpo
    assert "\\\\ArchMuse\\\\app\\\\actual\\\\lanzador.pyw" in cuerpo
    assert r"DefaultDirName={localappdata}\ArchMuse" in ISS
    assert r"{app}\runtime\pythonw.exe" in ISS
    assert r"{app}\app\actual\lanzador.pyw" in ISS


def test_la_rama_c_espera_como_mucho_veinte_segundos_preguntando_a_salud():
    cuerpo = _defun("am:levantar-servidor")
    assert "(< i 20)" in cuerpo
    assert "(am:salud-responde)" in cuerpo
    salud = _defun("am:salud-responde")
    assert '"GET"' in salud and "/api/salud" in salud


def test_la_rama_c_se_intenta_una_sola_vez_y_solo_si_no_contesta_nadie():
    cuerpo = _defun("am:post")
    assert cuerpo.count("(am:levantar-servidor)") == 1
    assert "(= (type r) 'STR)" in cuerpo.split("(am:levantar-servidor)")[0]


def test_la_rama_c_no_escribe_rutas_en_el_registro():
    """`%LOCALAPPDATA%` lleva el nombre de usuario de Windows dentro."""
    for llamada in re.findall(r"\(am:log [^\n]*", _defun("am:levantar-servidor")):
        assert "instalado" not in llamada and "base" not in llamada


# ── D-2: el cotejo va antes de escribir ─────────────────────────────────────

def test_el_cotejo_va_despues_de_medir_y_antes_de_dibujar_y_sale_sin_escribir():
    comando = _defun("c:ARCHMUSE")
    cotejo = comando.index('(am:valor-tras respuesta "lsp" 0)')
    assert comando.index("(am:post cuerpo)") < cotejo < comando.index("(am:dibujar-cuadro")
    bloque = comando[cotejo: comando.index(";; 2a.", cotejo)]
    assert "(/= r *am:version-corta*)" in bloque
    assert "NO ESCRIBO NADA" in bloque
    assert "(exit)" in bloque
