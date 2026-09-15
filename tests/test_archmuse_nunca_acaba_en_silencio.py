# -*- coding: utf-8 -*-
"""ArchMuse nunca acaba en silencio.

**El caso (Pablo, 2026-09-15, AutoCAD).** Sobre un plano grande, ARCHMUSE tardó
más de cinco minutos. Al final dijo «Servidor ArchMuse 0.3.9 · comando 3.8.0»,
**no dibujó nada y no dijo por qué**.

**Por qué acababa callado — leído en el código, sin ejecutar en AutoCAD.** Todas
las ramas que siguen a esa línea imprimen algo antes de salir. La única salida
muda era el `*error*` del comando, que se callaba ante un Esc (`*CANCEL*`).
Mientras AutoCAD espera al servidor la interfaz está bloqueada, y el Esc de quien
cree que se ha colgado se procesa cuando llega la respuesta: justo después de
imprimir la versión. El comando se cancelaba sin decir nada.

Dos invariantes, leyendo el `.lsp`:

1. Un Esc dice que se ha cancelado. La única salida callada es la de `(exit)`,
   que el propio comando usa **después** de haber dicho el motivo.
2. Ningún `(exit)` del comando llega sin mensaje delante: o hay un `princ` con
   texto en su rama, o la condición es una función de una lista cerrada que ya
   ha dicho el motivo antes de devolver nil.
"""
from __future__ import annotations

import re
from pathlib import Path

LSP = (Path(__file__).resolve().parent.parent / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")

#: Funciones que, cuando devuelven nil, ya han dicho por qué. Añadir una aquí
#: exige comprobar que TODAS sus ramas que devuelven nil imprimen el motivo.
DICEN_EL_MOTIVO = {
    "am:post",               # «no se ha podido crear el objeto HTTP», «no responde», «error N»
    "am:elegir-capa",        # «no hay ni una polilínea», «… no es ninguna de las de arriba»
    "am:recolectar",         # «no hay ninguna polilínea en la capa …»
    "am:recintos-en-xref-p", # «NO MIDO ESTE DIBUJO…»
    "am:elegir-por-clic",    # la duda, la distancia o C-13 que redacta el servidor (3.9.0)
}


def _sin_comentarios(texto: str) -> str:
    salida, i, cadena = [], 0, False
    while i < len(texto):
        c = texto[i]
        if cadena:
            salida.append(c)
            if c == "\\" and i + 1 < len(texto):
                salida.append(texto[i + 1])
                i += 2
                continue
            if c == '"':
                cadena = False
        elif c == '"':
            cadena = True
            salida.append(c)
        elif c == ";":
            fin = texto.find("\n", i)
            i = len(texto) if fin < 0 else fin
            continue
        else:
            salida.append(c)
        i += 1
    return "".join(salida)


def _forma(texto: str, ini: int) -> str:
    prof, i, cadena = 0, ini, False
    while i < len(texto):
        c = texto[i]
        if cadena:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                cadena = False
        elif c == '"':
            cadena = True
        elif c == "(":
            prof += 1
        elif c == ")":
            prof -= 1
            if prof == 0:
                return texto[ini:i + 1]
        i += 1
    raise AssertionError("paréntesis sin cerrar")


CODIGO = _sin_comentarios(LSP)
COMANDO = _forma(CODIGO, CODIGO.index("(defun c:ARCHMUSE ("))
ERROR = _forma(COMANDO, COMANDO.index("(defun *error*"))
FLUJO = COMANDO.replace(ERROR, "")
CON_TEXTO = re.compile(r'\(princ\s+(?:"|\(strcat|\(if)')


def test_un_esc_dice_que_se_ha_cancelado():
    """Callarse sólo ante `(exit)`, que es la salida ordenada del propio comando."""
    assert "*CANCEL*" in ERROR, "*error* no distingue el Esc"
    silenciosos = re.search(r'\(wcmatch \(strcase msg\)\s*"([^"]*)"', ERROR)
    assert silenciosos, "*error* ya no filtra mensajes: revisa este test"
    callados = silenciosos.group(1).split(",")
    assert "*CANCEL*" not in callados and "*BREAK*" not in callados, (
        "un Esc sigue acabando en silencio: *error* calla %s" % callados)
    rama = ERROR[ERROR.index("*CANCEL*"):]
    assert re.search(r'\(princ\s+"\\nCancelado', rama), "el Esc no dice «Cancelado…»"


def test_ningun_exit_del_comando_llega_sin_decir_por_que():
    mudos = []
    for m in re.finditer(r"\(exit\)", FLUJO):
        # La rama: el `(if …)` más cercano que contiene este `(exit)`.
        ini = FLUJO.rfind("(if ", 0, m.start())
        while ini >= 0 and m.start() > ini + len(_forma(FLUJO, ini)):
            ini = FLUJO.rfind("(if ", 0, ini)
        rama = _forma(FLUJO, ini) if ini >= 0 else FLUJO[max(0, m.start() - 400):m.start()]
        antes = rama[:rama.index("(exit)")] if "(exit)" in rama else rama
        if CON_TEXTO.search(antes):
            continue
        # La función que ya dijo el motivo puede estar en la condición o en el
        # `setq` inmediatamente anterior: `(setq capa (am:elegir-capa))` y luego
        # `(if (null capa) … (exit))`.
        previo = FLUJO[max(0, ini - 200):ini] if ini >= 0 else ""
        if any("(%s" % f in antes or "(%s" % f in previo for f in DICEN_EL_MOTIVO):
            continue
        linea = FLUJO.count("\n", 0, m.start()) + 1
        mudos.append((linea, " ".join(antes.split())[:160]))
    assert mudos == [], "salidas sin motivo: %s" % mudos
