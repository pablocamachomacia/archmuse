# -*- coding: utf-8 -*-
"""Si una fase tarda, ArchMuse dice en qué está.

**El caso (Pablo, 2026-09-15).** Sobre un plano de 677 recintos el comando pasó
más de cinco minutos con la línea de comandos parada en «Midiendo…». Desde
fuera no se distingue un servidor que trabaja de un AutoCAD colgado, y quien
cree que se ha colgado pulsa Esc (`test_archmuse_nunca_acaba_en_silencio.py`).

Medido ese día en una copia del plano con AutoCAD Core Console: leer el dibujo
tarda 6-8 s (9.220 polilíneas y 6.280 textos) y el servidor tardaba 413 s, que
ahora son unos 12. Las dos fases pueden seguir tardando en un plano mayor.

Lo que se comprueba leyendo el `.lsp` —**sin ejecutar en AutoCAD**: la espera
asíncrona de WinHttp no se ha probado en la interfaz—:

1. Antes de leer el dibujo se dice que se está leyendo.
2. La petición larga no bloquea AutoCAD en una sola llamada: se envía asíncrona
   y se espera a trozos, y cada pocos segundos se dice que sigue midiendo.
"""
from __future__ import annotations

import re
from pathlib import Path

LSP = (Path(__file__).resolve().parent.parent / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    """Quita los `;` de comentario sin tocar los que van dentro de una cadena."""
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


def _funcion(nombre: str) -> str:
    ini = LSP.index("(defun %s " % nombre)
    fin = LSP.find("\n(defun ", ini + 1)
    return LSP[ini:fin if fin > 0 else len(LSP)]


def test_antes_de_leer_el_dibujo_dice_que_lo_esta_leyendo():
    comando = LSP[LSP.index("(defun c:ARCHMUSE ("):]
    llamada = comando.index("(am:recolectar capa")
    antes = _sin_comentarios(comando[max(0, llamada - 600):llamada])
    assert re.search(r'\(princ\s+"\\nLeyendo', antes), (
        "el comando lee el dibujo —segundos en un plano grande— sin decirlo")


def test_la_peticion_larga_se_espera_a_trozos_y_avisa_de_que_sigue():
    peticion = _sin_comentarios(_funcion("am:peticion"))
    assert re.search(r"'Open\s+metodo\s+url\s+:vlax-true", peticion), (
        "la petición sigue siendo síncrona: AutoCAD se queda bloqueado en `Send` "
        "hasta que el servidor contesta, y no puede decir nada mientras")
    espera = re.search(r"\(while\b(.*)", peticion, re.S)
    assert espera and "'WaitForResponse" in espera.group(1), (
        "no hay un bucle que espere la respuesta a trozos")
    assert re.search(r'\(princ\s+\(strcat\s+"\\n\s*Sigo midiendo', peticion), (
        "mientras espera no dice que sigue midiendo")
