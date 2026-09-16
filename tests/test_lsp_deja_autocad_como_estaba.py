# -*- coding: utf-8 -*-
"""`C-16` (propuesto, pendiente de firma): el comando deja AutoCAD exactamente como
lo encontró, pase lo que pase.

**Por qué existe.** Pablo pidió el 2026-09-15 una auditoría acotada del comando.
Encontró un hueco de verdad: un Esc o un error sin capturar mientras dibujaba
dejaba **el grupo de deshacer abierto** y la tabla a medias sin marca de borrador.
(FILEDIA apareció a 0 ese día en su AutoCAD. El comando no lo toca; la causa,
reproducida el 2026-09-16, fueron Core Console matados de las herramientas de
desarrollo: ver `docs/audits/2026-09-16-incidente-filedia-a-cero.md` y
`tests/test_core_console_no_toca_autocad.py`.)

Es `C-7` otra vez: el servidor no ve el estado de AutoCAD, así que ningún test
del servidor podía verlo. **Estos tests tampoco lo ven**: leen el código. Cazan
en la suite lo que se puede cazar leyendo —una variable nueva sin devolver, una
orden nueva, el grupo sin cerrar—. Lo que pasa de verdad dentro de AutoCAD lo
comprueba el guardián, `herramientas/guardian_autocad/guardian.lsp`, que se
ejecuta en un AutoCAD real.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LSP = (RAIZ / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")
GUARDIAN = RAIZ / "herramientas" / "guardian_autocad" / "guardian.lsp"

#: Lo que ARCHMUSE cambia de AutoCAD a propósito, medido en la auditoría del
#: 2026-09-15. Añadir una aquí exige que *error* la devuelva y que el guardián
#: lo haya comprobado en AutoCAD.
#: ORTHOMODE, SNAPMODE, OSMODE y AUTOSNAP (3.9.7, 2026-09-17): sólo durante el
#: arrastre del segundo clic, para que la tabla vaya pegada al cursor aunque haya
#: Orto; se devuelven al terminar y en *error*.
VARIABLES_QUE_CAMBIA = {"CMDECHO", "ORTHOMODE", "SNAPMODE", "OSMODE", "AUTOSNAP"}
#: Las órdenes de AutoCAD que lanza. `_.DELAY` espera al servidor; `_.U` retira
#: lo dibujado cuando no se puede terminar; `_.MOVE` (3.9.6, 2026-09-16) arrastra lo
#: que acaba de dibujar en el segundo clic: sólo mueve esas entidades y cambia
#: LASTPOINT, que el guardián ya cuenta entre los cambios de haber dibujado.
ORDENES_QUE_LANZA = {"_.DELAY", "_.U", "_.MOVE"}


def _sin_comentarios(texto: str) -> str:
    """Quita los comentarios `;` y deja las cadenas intactas (un `;` dentro de
    una cadena no abre un comentario)."""
    salida, i, en_cadena = [], 0, False
    while i < len(texto):
        c = texto[i]
        if en_cadena:
            salida.append(c)
            if c == "\\" and i + 1 < len(texto):
                salida.append(texto[i + 1])
                i += 2
                continue
            if c == '"':
                en_cadena = False
        elif c == '"':
            en_cadena = True
            salida.append(c)
        elif c == ";":
            fin = texto.find("\n", i)
            i = len(texto) if fin == -1 else fin
            continue
        else:
            salida.append(c)
        i += 1
    return "".join(salida)


def _forma(texto: str, ini: int) -> str:
    """La expresión que empieza en `ini`, contando paréntesis fuera de cadenas."""
    profundidad, i, en_cadena = 0, ini, False
    while i < len(texto):
        c = texto[i]
        if en_cadena:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                en_cadena = False
        elif c == '"':
            en_cadena = True
        elif c == "(":
            profundidad += 1
        elif c == ")":
            profundidad -= 1
            if profundidad == 0:
                return texto[ini:i + 1]
        i += 1
    raise AssertionError("paréntesis sin cerrar desde %d" % ini)


def _defun(texto: str, nombre: str) -> str:
    marca = "(defun %s " % nombre
    assert marca in texto, "no encuentro %s" % marca
    return _forma(texto, texto.index(marca))


CODIGO = _sin_comentarios(LSP)
COMANDO = _defun(CODIGO, "c:ARCHMUSE")
ERROR = _defun(COMANDO, "*error*")
FLUJO = COMANDO.replace(ERROR, "")


def test_toda_variable_que_cambia_el_comando_la_devuelve_su_error():
    """Un Esc en cualquier pregunta acaba en *error*: si una variable no se
    devuelve ahí, se queda cambiada en el AutoCAD del arquitecto."""
    cambiadas = set(re.findall(r'\(setvar\s+"([A-Za-z_]+)"', CODIGO))
    assert cambiadas <= VARIABLES_QUE_CAMBIA, (
        "el .lsp cambia variables nuevas: %s. Sólo si *error* las devuelve y el "
        "guardián lo ha comprobado en AutoCAD" % sorted(cambiadas - VARIABLES_QUE_CAMBIA))
    for variable in cambiadas:
        assert '(setvar "%s"' % variable in ERROR, (
            "*error* no devuelve %s: un Esc la deja cambiada" % variable)


def test_no_cambia_ajustes_de_autocad_por_otras_vias():
    """`setvar` no es la única puerta. Capa, estilo o color activos, variables
    por ActiveX o de entorno: ninguna se toca."""
    for via in ("vla-SetVariable", "vla-put-ActiveLayer", "vla-put-ActiveTextStyle",
                "vla-put-ActiveDimStyle", "vla-put-ActiveLinetype", "vla-put-ActiveUCS",
                "vla-put-ActiveSpace", "(setenv", "vl-registry-write", "vl-registry-delete"):
        assert via not in CODIGO, "el .lsp usa %s: eso cambia AutoCAD más allá del dibujo" % via


def test_solo_lanza_las_ordenes_de_autocad_que_se_conocen():
    """Una orden de AutoCAD puede cambiar variables por su cuenta. Las que hay
    están auditadas; una nueva tiene que pasar por la misma auditoría."""
    directas = set(re.findall(r'\(command(?:-s)?\s+"([^"]+)"', CODIGO))
    por_apply = set(re.findall(r"'command(?:-s)?\s+\(list\s+\"([^\"]+)\"", CODIGO))
    assert (directas | por_apply) <= ORDENES_QUE_LANZA, (
        "órdenes nuevas: %s" % sorted((directas | por_apply) - ORDENES_QUE_LANZA))


def test_un_esc_o_un_fallo_mientras_dibuja_cierra_el_deshacer_y_retira_lo_dibujado():
    """El hueco de la auditoría. *error* tiene que cerrar el grupo si está
    abierto y, si llegó a dibujarse algo, deshacerlo: sin marca de borrador
    (`C-3`) no puede quedar nada."""
    locales = COMANDO[:COMANDO.index(")")]
    assert "grupo-abierto" in locales.split(), "`grupo-abierto` no es local del comando"
    assert "(if grupo-abierto" in ERROR, "*error* no mira si hay un grupo abierto"
    assert "vla-EndUndoMark" in ERROR, "*error* no cierra el grupo de deshacer"
    assert "'command-s (list \"_.U\")" in ERROR, (
        "*error* no retira lo dibujado, o usa `command`, que AutoCAD no admite ahí")
    assert "(if *am:dibujo-empezado*" in ERROR, (
        "*error* deshace sin mirar si ha dibujado: se llevaría algo del arquitecto")


def test_la_bandera_del_grupo_va_pegada_a_abrirlo_y_a_cerrarlo():
    """Si la bandera y el grupo se separan, *error* cierra un grupo que no existe
    o deja abierto uno que sí."""
    aperturas = len(re.findall(r"vla-StartUndoMark", FLUJO))
    assert aperturas == len(re.findall(
        r"\(setq \*am:dibujo-empezado\* nil grupo-abierto T\)\s*"
        r"\(vl-catch-all-apply 'vla-StartUndoMark", FLUJO)), (
        "hay un StartUndoMark sin poner antes `grupo-abierto` a T (y el dibujo a nil)")
    cierres = len(re.findall(r"vla-EndUndoMark", FLUJO))
    assert cierres >= 2
    assert cierres == len(re.findall(
        r"\(setq grupo-abierto nil\)\s*\(vl-catch-all-apply 'vla-EndUndoMark", FLUJO)), (
        "hay un EndUndoMark sin poner antes `grupo-abierto` a nil: *error* lo cerraría dos veces")


def test_el_guardian_existe_y_no_toca_nada_de_autocad():
    """El que vigila no puede cambiar lo que vigila."""
    texto = GUARDIAN.read_text(encoding="utf-8")
    codigo = _sin_comentarios(texto)
    assert "(defun c:ARCHMUSE-GUARDIAN " in codigo
    for prohibido in ("(setvar", "(command", "command-s", "vla-put-", "vla-SetVariable",
                      "vl-registry-write", "vl-registry-delete", "(setenv"):
        assert prohibido not in codigo, "el guardián usa %s" % prohibido
    for variable in ("FILEDIA", "CMDECHO", "UNDOCTL", "CLAYER", "OSMODE"):
        assert '"%s"' % variable in codigo, "el guardián no vigila %s" % variable
