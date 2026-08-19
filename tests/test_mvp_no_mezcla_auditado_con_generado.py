# -*- coding: utf-8 -*-
"""Lo auditado y lo generado por el modelo no comparten sitio en la pantalla.

Ejecutar:  pytest tests/test_mvp_no_mezcla_auditado_con_generado.py

**Por que existe este test.** En la vista `/mvp` conviven dos cosas que se
parecen mucho en pantalla y no se parecen en nada por dentro:

- `analyzer/alternativas.py` — aritmetica sobre los parametros que introdujo el
  arquitecto. Cada cifra vuelve con su procedencia.
- `analyzer/ai_generator.py` — un modelo de lenguaje colocando estancias segun
  criterio propio. No se deriva de ningun parametro comprobable, no lleva
  procedencia, y con el §8 corregido el 2026-08-19 esta **fuera de alcance**.

Hasta el 2026-08-19 las dos escribian en `#p-alternativas`, y la segunda borraba
a la primera: cuatro tarjetas con el mismo aspecto y respaldo distinto, sin que
nada en pantalla lo dijera. Pablo lo pidio separado explicitamente.

Esto lee el fuente en vez de renderizar la pagina. Es menos elegante que un test
de navegador y es lo que hay sin infraestructura de front; a cambio falla en
milisegundos el dia que alguien vuelva a cablear el generador al panel auditado.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
JS = (RAIZ / "static" / "mvp.js").read_text(encoding="utf-8")
HTML = (RAIZ / "static" / "mvp.html").read_text(encoding="utf-8")

#: Las pestanas cuyo contenido sale, entera o parcialmente, del generador.
PANELES_DEL_MODELO = ("pintarDistribucion", "pintarAnalisis", "pintarNormativa",
                      "pintarCostes", "pintarExportar")

#: Donde acaba el cuerpo de una funcion: la siguiente declaracion de primer
#: nivel del fichero (otra funcion, o un `$("...").addEventListener`).
SIGUIENTE_BLOQUE = re.compile(r"\n(?:async )?function |\n\$\(")


def _cuerpo(nombre: str) -> str:
    """El codigo de una funcion de `mvp.js`, sin sus comentarios.

    Los comentarios se quitan porque justamente explican la separacion y
    nombran los dos paneles: dejarlos dentro haria que el aviso de no mezclar
    contara como una mezcla.
    """
    inicio = JS.index("function %s(" % nombre)
    resto = JS[inicio + 1:]
    siguiente = SIGUIENTE_BLOQUE.search(resto)
    cuerpo = resto[: siguiente.start()] if siguiente else resto
    return "\n".join(l for l in cuerpo.splitlines() if not l.lstrip().startswith("//"))


def test_los_dos_paneles_existen_y_son_distintos():
    assert 'id="p-alternativas"' in HTML
    assert 'id="p-distribucion"' in HTML
    assert 'data-p="alternativas"' in HTML
    assert 'data-p="distribucion"' in HTML


def test_la_pestana_del_generador_va_marcada_en_la_propia_navegacion():
    """No basta con avisar dentro del panel: quien no lo abre no lee el aviso."""
    pestana = HTML[HTML.index('data-p="distribucion"'):]
    pestana = pestana[: pestana.index("</button>")]
    assert "sin auditar" in pestana.lower()


def test_lo_que_pinta_el_generador_no_escribe_en_el_panel_auditado():
    for nombre in PANELES_DEL_MODELO:
        assert "p-alternativas" not in _cuerpo(nombre), (
            "%s escribe en el panel de las alternativas derivadas. Ese panel es "
            "solo de `analyzer/alternativas.py`, que lleva procedencia." % nombre)


def test_la_llamada_al_generador_tampoco_escribe_en_el_panel_auditado():
    """`generar()` es quien llama a `/api/generar-opciones`: ni su mensaje de
    espera ni su error pueden aterrizar en el panel auditado."""
    cuerpo = _cuerpo("generar")
    assert "generar-opciones" in cuerpo, "este test vigila la funcion equivocada"
    assert "p-alternativas" not in cuerpo


def test_solo_lo_derivado_de_parametros_escribe_en_el_panel_auditado():
    cuerpo = _cuerpo("pintarParametricas")
    assert "p-alternativas" in cuerpo
    assert "p-distribucion" not in cuerpo


def test_todo_panel_del_generador_lleva_la_franja():
    for nombre in PANELES_DEL_MODELO:
        assert "FRANJA_SIN_AUDITAR" in _cuerpo(nombre), (
            "%s pinta salida del generador sin la franja que lo dice" % nombre)


def test_la_franja_dice_las_tres_cosas_que_tiene_que_decir():
    franja = JS[JS.index("const FRANJA_SIN_AUDITAR"):]
    franja = franja[: franja.index(";\n")].lower()
    assert "sin auditar" in franja
    assert "modelo de lenguaje" in franja
    assert "procedencia" in franja


def test_el_panel_auditado_no_se_queda_con_el_encargo_anterior():
    """Un cambio del copiloto invalida las alternativas derivadas tanto como las
    del generador. Si solo se regenerase lo del modelo, la pestana auditada
    seguiria enseñando el reparto viejo -- y esa si lleva procedencia, asi que
    seria una cifra con respaldo y equivocada, que es lo peor de los dos mundos.
    """
    manejador = JS[JS.index('$("entrada").addEventListener'):]
    cambio = manejador[manejador.index("hubo_cambio"):]
    assert "derivarAlternativas()" in cambio
