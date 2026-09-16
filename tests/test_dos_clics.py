# -*- coding: utf-8 -*-
"""Dos clics: uno elige la vivienda y otro coloca el cuadro (Pablo, 2026-09-16).

**La decisión de producto:**

1. «Haz clic dentro de la vivienda que quieres medir.»
2. «Vivienda VTx seleccionada. Mueve el cursor para colocar el cuadro de superficies
   y haz clic.» Durante el paso 2 el contorno de la tabla sigue al cursor, como al
   insertar un bloque. Se coloca **exactamente** donde se hace clic. Si tapa el
   dibujo, se coloca igualmente y **sólo se avisa**.

Y se quita la colocación automática en el hueco libre (2026-09-15). Condiciones:
se mide antes de enseñar la vista previa; Esc en el paso 2 no deja nada dibujado,
dice «Cancelado con Esc» y deja AutoCAD como estaba (`C-16`); ningún mensaje dice
algo que el programa no haga; un solo U deshace la tabla entera.

El servidor se prueba de verdad; el `.lsp`, leyendo el código: el clic y la vista
previa **no se han probado en la interfaz de AutoCAD** (`C-7`).
"""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from analyzer import maquetacion_cuadro as mq  # noqa: E402
from analyzer import plantilla_cuadro as pc  # noqa: E402

CELDAS = [(0, 0, pc.TITULO)] + [(1, c, t) for c, t in enumerate(pc.ENCABEZADOS)] + [
    (2, 0, "Salón/cocina"), (2, 1, "23,24 m²"), (2, 2, "Terraza"), (2, 3, "3,32 m²"),
    (3, 0, "Dormitorio 1"), (3, 1, "12,47 m²"),
]
NOTAS = ("Nº de unidades: a mano",)
LSP = (RAIZ / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")


def _huella(m):
    x, y = m.esquina
    return (x, y - m.alto_total), (x + m.ancho_total, y)


# -- El servidor: donde se hace clic, siempre ---------------------------------

def test_si_no_tapa_nada_va_en_el_punto_y_no_avisa():
    m = mq.maquetar_en_punto(CELDAS, NOTAS, (20.0, 9.0), 0.125, obstaculos=[(0.0, 0.0, 12.0, 9.0)])
    assert isinstance(m, mq.Maquetacion)
    assert m.esquina == (20.0, 9.0)
    assert m.tapa is None


def test_si_tapa_el_dibujo_va_igualmente_en_el_punto_y_solo_avisa():
    # Dos dentro de la huella (esquina en (6, 6), hacia la derecha y abajo) y uno lejos.
    obstaculos = [(0.0, 0.0, 12.0, 9.0), (7.0, 5.0, 7.5, 5.5), (500.0, 500.0, 501.0, 501.0)]
    m = mq.maquetar_en_punto(CELDAS, NOTAS, (6.0, 6.0), 0.125, obstaculos=obstaculos)
    assert isinstance(m, mq.Maquetacion)
    assert m.esquina == (6.0, 6.0), "la tabla se ha movido del punto"
    assert m.tapa and "2 elementos" in m.tapa, m.tapa
    assert "donde has hecho clic" in m.tapa and "Ctrl+Z" in m.tapa


def test_si_tapa_su_cuadro_tambien_se_coloca_y_se_dice_que_es_su_cuadro():
    (x0, y0), (x1, y1) = _huella(mq.maquetar_en_punto(CELDAS, NOTAS, (100.0, 50.0), 0.125))
    m = mq.maquetar_en_punto(CELDAS, NOTAS, (100.0, 50.0), 0.125,
                             cajas_prohibidas=[((x0 + 0.1, y0 + 0.1), (x0 + 0.2, y0 + 0.2))])
    assert isinstance(m, mq.Maquetacion), "con dos clics ya no se niega a dibujar sobre su cuadro"
    assert m.esquina == (100.0, 50.0)
    assert m.tapa and "tu cuadro de superficies" in m.tapa


def test_la_huella_que_se_mira_incluye_las_notas_y_la_marca():
    m = mq.maquetar_en_punto(CELDAS, NOTAS, (0.0, 0.0), 0.125)
    debajo_de_la_tabla = (1.0, -m.alto_total + 0.01, 1.2, -m.alto_tabla - 0.01)
    con = mq.maquetar_en_punto(CELDAS, NOTAS, (0.0, 0.0), 0.125, obstaculos=[debajo_de_la_tabla])
    assert con.tapa, "lo que tapan las notas o la marca no se ha contado"


def test_ya_no_hay_colocacion_automatica():
    assert not hasattr(mq, "_hueco_mas_cercano")
    assert "zona" not in inspect.signature(mq.maquetar_en_punto).parameters
    assert not hasattr(mq.Maquetacion, "colocacion")
    from analyzer import vivienda_en_punto as vp
    assert not hasattr(vp, "zona_de_colocacion")


def test_la_respuesta_trae_el_tamano_para_la_vista_previa_antes_de_las_notas():
    m = mq.maquetar_en_punto(CELDAS, NOTAS, (6.0, 6.0), 0.125, obstaculos=[(0.0, 0.0, 12.0, 9.0)])
    d = mq.a_dict(m)
    claves = list(d)
    for clave in ("ancho_total", "alto_tabla", "alto_total", "tapa"):
        assert clave in d and claves.index(clave) < claves.index("notas"), clave
    assert "colocacion" not in d
    assert (d["ancho_total"], d["alto_total"]) == (m.ancho_total, m.alto_total)


def test_el_endpoint_coloca_en_el_punto_y_avisa(tmp_path):
    import app as srv
    from analyzer.geometria_recibida import payload_desde_dxf

    fixture = RAIZ / "tests" / "fixtures" / "cuadro_sintetico" / "cuadro_sintetico.dxf"
    cliente = srv.app.test_client()
    cuadro = cliente.post("/api/medicion-geometria", json=dict(
        payload_desde_dxf(str(fixture)), punto=[40.0, 10.0],
        ambitos={"TRASTERO": "interior"})).get_json()["repartos"][0]["cuadro_a_dibujar"]
    textos = cuadro["textos_a_medir"]
    cuerpo = {"estilo_texto": cuadro["estilo_texto"], "punto": [40.0, 10.0],
              "altura_minima": cuadro["altura_minima"],
              "celdas": [[c["fila"], c["columna"], c["texto"]] for c in cuadro["celdas"]],
              "notas": cuadro["notas_del_dibujo"], "textos_medidos": textos,
              "anchos_medidos": [0.6 * len(t) for t in textos],
              "obstaculos": [[40.1, 9.0, 40.3, 9.9]],
              "zona_de_colocacion": [0, 0, 1, 1]}
    d = cliente.post("/api/maquetar-cuadro", json=cuerpo).get_json()
    assert d["cabe"] is True and (d["x"], d["y"]) == (40.0, 10.0)
    assert d["tapa"] and "1 elemento" in d["tapa"]
    vivienda = cliente.post("/api/vivienda-en-punto", json=dict(
        payload_desde_dxf(str(fixture)), punto=[2.0, 2.0])).get_json()
    assert "zona_de_colocacion" not in vivienda


# -- El comando (leyendo el `.lsp`) --------------------------------------------

def _sin_comentarios(texto):
    return "\n".join(l.split(";")[0] if not l.lstrip().startswith(";") else "" for l in texto.splitlines())


def _defun(nombre):
    ini = LSP.index("(defun %s " % nombre)
    fin = LSP.find("\n(defun ", ini + 1)
    return _sin_comentarios(LSP[ini:fin if fin > 0 else len(LSP)])


def test_primer_clic_dentro_de_la_vivienda():
    assert '"\\nHaz clic dentro de la vivienda que quieres medir: "' in _defun("am:pedir-punto")


def test_segundo_clic_con_la_vista_previa_siguiendo_al_cursor():
    colocar = _defun("am:colocar-cuadro")
    assert '"\\nVivienda " nombre " seleccionada. Mueve el cursor y haz clic donde quieres el cuadro de superficies."' \
        in " ".join(colocar.split())
    assert re.search(r"\(grread T \d+ 0\)", colocar), "el cursor no se sigue con grread"
    assert "grvecs" in colocar and "(redraw)" in colocar
    # Se coloca donde se hace clic: el punto del clic (código 3), sin forzarlo a nada.
    assert "(= (car r) 3)" in colocar


def test_la_vista_previa_no_dibuja_nada_en_el_plano():
    colocar = _defun("am:colocar-cuadro") + _defun("am:contorno-del-cuadro")
    for via in ("entmake", "vla-Add", "(command", "command-s", "vl-cmdf", "(setvar",
                "vla-StartUndoMark"):
        assert via not in colocar, via


def test_se_mide_antes_de_la_vista_previa_y_se_dibuja_despues_del_clic():
    comando = _defun("c:ARCHMUSE")
    orden = [comando.index(t) for t in (
        "(am:pedir-punto)",
        "(am:post cuerpo)",
        "(am:medir-textos textos estilo-texto)",
        "(am:maquetar bloque textos medidos punto nil estilo-texto nil)",
        "(am:colocar-cuadro m (nth elegida nombres))",
        "(am:obstaculos (am:huella-del-cuadro m colocado))",
        "(am:maquetar bloque textos medidos colocado cuadros estilo-texto obstaculos)",
        "vla-StartUndoMark",
        "(am:dibujar-cuadro m celdas)")]
    assert orden == sorted(orden), orden


def test_esc_en_el_segundo_clic_limpia_la_vista_previa_y_lo_dice():
    comando = _defun("c:ARCHMUSE")
    error = comando[comando.index("(defun *error*"):comando.index('(setq eco (getvar "CMDECHO"))')]
    assert "(redraw)" in error, "un Esc dejaría el contorno pintado en pantalla"
    assert '"\\nCancelado con Esc."' in error and '" No se ha dibujado nada."' in error
    colocar = _defun("am:colocar-cuadro")
    # Si AutoCAD devuelve el Esc como tecla, se dice lo mismo y no se dibuja.
    assert "27" in colocar and "Cancelado con Esc. No se ha dibujado nada." in colocar


def test_si_tapa_lo_dice_y_si_no_dice_solo_lo_que_hace():
    comando = _defun("c:ARCHMUSE")
    assert '(am:valor-tras m "tapa" 0)' in comando
    assert '"\\n  El cuadro va donde has hecho clic."' in comando


#: Órdenes de AutoCAD en inglés que un mensaje no puede nombrar tal cual. En AutoCAD
#: en español «U» abre UNIR y «UNDO» no deshace (Pablo, 2026-09-16): lo que se le
#: dice al arquitecto es Ctrl+Z. En el código, `_.U` con guion bajo sí vale.
_ORDENES_EN_INGLES = re.compile(r"(?<![_.\w])(UNDO|U|REGEN|ZOOM|APPLOAD|NETLOAD|LAYER|INSERT|"
                                r"EXPLODE|PURGE|ERASE|MOVE|OPEN|SAVE)(?![\w])")


def _mensajes_del_lsp():
    """Los textos con espacios del `.lsp`: son los que lee el arquitecto."""
    codigo = _sin_comentarios(LSP)
    return [t for t in re.findall(r'"((?:[^"\\]|\\.)*)"', codigo) if " " in t]


def test_ningun_mensaje_nombra_una_orden_en_ingles():
    malos = [t for t in _mensajes_del_lsp() if _ORDENES_EN_INGLES.search(t)]
    assert malos == [], malos
    servidor = [(f.name, t) for f in (RAIZ / "analyzer").glob("*.py")
                for t in re.findall(r'"((?:[^"\\\n]|\\.)*)"', f.read_text(encoding="utf-8"))
                if " " in t and re.search(r"(?<![_.\w])(UNDO|U)(?![\w])", t)]
    assert servidor == [], servidor


def test_el_mensaje_final_dice_ctrl_z():
    assert '"\\nCtrl+Z deshace todo lo que acabo de escribir."' in _defun("c:ARCHMUSE")


def test_esc_en_cualquier_paso_llega_al_mismo_aviso():
    """Todas las preguntas del comando (capa, primer clic, alinear rótulos, interior o
    exterior, segundo clic) cancelan con Esc a través de *error*: nada se dibuja antes
    del segundo clic, y *error* dice «Cancelado con Esc» y devuelve CMDECHO."""
    comando = _defun("c:ARCHMUSE")
    error = comando[comando.index("(defun *error*"):comando.index('(setq eco (getvar "CMDECHO"))')]
    assert '"*BREAK*,*CANCEL*"' in error and '(setvar "CMDECHO"' in error
    cuerpo = comando[comando.index('(setq eco (getvar "CMDECHO"))'):]
    primer_dibujo = cuerpo.index("vla-StartUndoMark")
    for pregunta in ("(am:elegir-capa)", "(am:pedir-punto)", "getkword", "(am:preguntar-ambitos",
                     "(am:colocar-cuadro"):
        assert cuerpo.index(pregunta) < primer_dibujo, pregunta


# -- Sin códigos internos en lo que ve el arquitecto (Pablo, 2026-09-16) --------

_CODIGO = re.compile(r"\b[CD]-\d+\b|propuest[oa]\b|pendiente de firma", re.I)


def test_ningun_texto_del_comando_que_se_ve_lleva_codigos():
    """Los códigos pueden ir al registro (`am:log`); a la pantalla, no."""
    codigo = _sin_comentarios(LSP)
    malos = []
    for linea in codigo.splitlines():
        if "(am:log" in linea or "(am:contexto" in linea:
            continue
        malos += [t for t in re.findall(r'"((?:[^"\\]|\\.)*)"', linea)
                  if " " in t and _CODIGO.search(t) and "(propuesta)" not in t]
    assert malos == [], malos


@pytest.mark.parametrize("texto, esperado", [
    ("Está medida y no tiene fila (C-18).", "Está medida y no tiene fila."),
    ("Haz clic junto a su dibujo (C-17, propuesto).", "Haz clic junto a su dibujo."),
    ("no se escribe (`C-12`).", "no se escribe."),
    ("el plano lo declara, pero leer lo que el plano declara (C-8) no está implementado todavía",
     "el plano lo declara, pero leer lo que el plano declara no está implementado todavía"),
    ("C-15: los recintos están en una referencia externa", "los recintos están en una referencia externa"),
    ("no se escribe: sus cifras suman cero (D-13); el total tampoco (C-2, C-14).",
     "no se escribe: sus cifras suman cero; el total tampoco."),
    ("Dormitorio (4,00 m²)", "Dormitorio (4,00 m²)"),
])
def test_los_codigos_se_quitan_sin_estropear_la_frase(texto, esperado):
    from analyzer.texto_para_el_arquitecto import sin_codigos
    assert sin_codigos(texto) == esperado


def test_la_respuesta_para_el_comando_no_lleva_codigos_y_la_de_la_web_sigue_igual():
    import app as srv
    from analyzer.geometria_recibida import payload_desde_dxf

    cliente = srv.app.test_client()
    for fixture in (RAIZ / "tests" / "fixtures" / "reales" / "vivienda_con_solapes.dxf",
                    RAIZ / "tests" / "fixtures" / "cuadro_sintetico" / "cuadro_sintetico.dxf"):
        base = payload_desde_dxf(str(fixture))
        v = base["recintos"][0]["vertices"]
        punto = [sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)]
        cuerpo = dict(base, punto=punto)
        lisp = cliente.post("/api/medicion-geometria?formato=lisp", json=cuerpo).get_data(as_text=True)
        assert not _CODIGO.search(lisp), _CODIGO.search(lisp)
        lejos = dict(base, punto=[punto[0] + 5000.0, punto[1] + 5000.0])
        lejos.pop("otras_polilineas", None)
        texto = cliente.post("/api/vivienda-en-punto?formato=lisp", json=lejos).get_data(as_text=True)
        assert "No mido" in texto and not _CODIGO.search(texto), texto[:300]
    # La web y el agente siguen recibiendo los códigos: allí se citan los criterios.
    web = cliente.post("/api/vivienda-en-punto", json=lejos).get_json()
    assert _CODIGO.search(web["motivo"])


def test_ningun_mensaje_habla_de_la_colocacion_automatica():
    codigo = _sin_comentarios(LSP)
    for texto in ("hueco libre", "He movido", "no pisa nada", "para no poner la tabla encima",
                  "zona_de_colocacion", "ahí irá la esquina", "Haz clic al lado de la vivienda",
                  "desde el punto que has marcado", "pisaría tu cuadro"):
        assert texto not in codigo, texto
    servidor = inspect.getsource(mq)
    for texto in ("hueco libre", "He movido", "Marca otro punto"):
        assert texto not in servidor, texto
