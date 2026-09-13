# -*- coding: utf-8 -*-
"""Un fallo al dibujar dice en qué paso y por qué. Nunca sólo que ocurrió.

**El caso, en AutoCAD, 2026-09-13, `.lsp` 3.4.0 sobre `v1plantas.dxf`.** El
servidor resolvió 30 casillas y 4 notas; el comando dijo «No he podido dibujar
la tabla. No se ha quedado nada a medias.» y nada más. AutoCAD no mostró ningún
error: `am:dibujar-cuadro` lo capturaba con `vl-catch-all-apply` y lo tiraba,
devolviendo `nil` a secas. Y la segunda frase no se comprobaba: si la tabla
llegaba a crearse, se quedaba en el dibujo.

**Método firmado por Pablo** («ha costado horas cuatro veces»): el mensaje dice
la causa. Estos tests lo guardan en el fuente, porque el `.lsp` no se ejecuta en
CI: que el handler conserve el mensaje de AutoCAD y el paso, que nada se trague
en silencio dentro del dibujo, y que el comando lo enseñe y no prometa lo que no
ha comprobado.
"""
from __future__ import annotations

import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LSP = open(os.path.join(RAIZ, "autocad", "archmuse.lsp"), encoding="utf-8").read()


def _sin_comentarios(texto):
    return "\n".join(linea.split(";;")[0] for linea in texto.splitlines())


def _funcion(nombre):
    ini = LSP.index("(defun %s " % nombre)
    fin = LSP.find("\n(defun ", ini + 1)
    return LSP[ini:fin if fin > 0 else len(LSP)]


# --- 1. El handler conserva la causa -----------------------------------------

def test_dibujar_cuadro_guarda_el_paso_y_el_mensaje_de_autocad():
    cuerpo = _sin_comentarios(_funcion("am:dibujar-cuadro"))
    assert "(vl-catch-all-error-message r)" in cuerpo
    assert re.search(r'\(setq \*am:fallo-del-dibujo\*\s+\(strcat "al " paso ": "', cuerpo)
    # Se vacía al empezar: un fallo de antes no puede enseñarse como de ahora.
    assert re.search(r"\(setq \*am:fallo-del-dibujo\* nil", cuerpo)


def test_todo_paso_que_puede_tumbar_la_tabla_esta_nombrado_antes_de_darlo():
    """Cada llamada que escribe en el dibujo y NO va por `am:intentar` tiene que
    tener un `(setq paso …)` antes dentro del bloque protegido. Si no, un fallo en
    ella se contaría con el nombre del paso anterior: una causa falsa."""
    cuerpo = _sin_comentarios(_funcion("am:dibujar-cuadro"))
    bloque = cuerpo[cuerpo.index("'(lambda"):]
    llamadas = [m.start() for m in re.finditer(
        r"\((vla-(?:Add|AddTable|AddMText|put-[A-Za-z]+|Set[A-Za-z]+))\s", bloque)]
    pasos = [m.start() for m in re.finditer(r"\(setq paso ", bloque)]
    assert len(pasos) >= 8, "se nombran muy pocos pasos: %d" % len(pasos)
    for inicio in llamadas:
        assert any(p < inicio for p in pasos), bloque[inicio:inicio + 60]


def test_dentro_del_dibujo_nada_se_traga_en_silencio():
    """Dentro de `am:dibujar-cuadro` y `am:estilo-de-tabla`, un `vl-catch-all-apply`
    sólo puede ser el handler que guarda la causa o una consulta de existencia
    (`vla-Item`: «¿ya existe esta capa?»). Todo lo demás va por `am:intentar`,
    que apunta el motivo."""
    for nombre in ("am:dibujar-cuadro", "am:estilo-de-tabla"):
        cuerpo = _sin_comentarios(_funcion(nombre))
        # `'\(lambda` primero: con `'?[^\s()]+` delante, el apóstrofo suelto de
        # `'(lambda` se capturaba como si fuera el nombre de una función.
        capturas = re.findall(r"\(vl-catch-all-apply\s+('\(lambda|\(lambda|'?[^\s()]+)", cuerpo)
        silenciosas = [c for c in capturas if c not in ("'vla-Item", "'(lambda")]
        assert not silenciosas, "%s traga fallos sin decirlos: %s" % (nombre, silenciosas)
        assert cuerpo.count("'(lambda") == 1, nombre


def test_intentar_y_el_estilo_de_tabla_apuntan_el_motivo():
    intentar = _sin_comentarios(_funcion("am:intentar"))
    assert "(vl-catch-all-error-message r)" in intentar and "am:avisar-del-dibujo" in intentar
    estilo = _sin_comentarios(_funcion("am:estilo-de-tabla"))
    assert "(vl-catch-all-error-message r)" in estilo and "am:avisar-del-dibujo" in estilo
    # El paso y el mensaje, en ese orden: «…«ARCHMUSE», al crearlo: <mensaje>».
    assert 'al " paso ": "' in estilo


# --- 2. El comando lo enseña y no promete lo que no ha comprobado -------------

def test_el_comando_ensena_la_causa_y_la_registra():
    comando = _funcion("c:ARCHMUSE")
    rama = comando[comando.index("(setq tabla (am:dibujar-cuadro m celdas))"):]
    rama = rama[:rama.index("(exit)")]
    assert "*am:fallo-del-dibujo*" in rama
    assert re.search(r"\(am:log \(strcat \"fallo al dibujar el cuadro \"", rama)


def test_no_se_dice_que_no_ha_quedado_nada_a_medias_sin_comprobarlo():
    # Sin comentarios: el que explica el cambio cita la frase vieja a propósito.
    comando = _sin_comentarios(_funcion("c:ARCHMUSE"))
    assert "No se ha quedado nada a medias" not in comando
    rama = comando[comando.index("(setq tabla (am:dibujar-cuadro m celdas))"):]
    rama = rama[:rama.index("(exit)")]
    # Deshace sólo si llegó a dibujar algo: con el grupo vacío, el UNDO desharía
    # lo último que hizo el arquitecto.
    assert re.search(r"\(if \*am:dibujo-empezado\*\s+\(if \(vl-catch-all-error-p "
                     r"\(vl-catch-all-apply 'command \(list \"_\.U\"\)\)\)", rama)


def test_los_avisos_se_ensenan_aunque_la_tabla_salga():
    comando = _funcion("c:ARCHMUSE")
    assert re.search(r"\(if \*am:avisos-del-dibujo\*", comando)
    assert "La tabla está dibujada, pero esto no se ha podido hacer" in comando
