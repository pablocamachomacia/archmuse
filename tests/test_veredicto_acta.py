"""El acta abre con un veredicto, y el motivo no se repite seis veces.

Defecto que estos tests congelan (2026-08-23, hallazgo de Pablo sobre
`cs_01.dxf`): cuando una Skill se cortaba, **el párrafo entero del parser
—con sus capas candidatas— se copiaba en cada afirmación no producida**: 6 en
`revision`, 5 en `medicion`, más `no_hecho` y `preguntas`. En pantalla eran
7 y 6 repeticiones del mismo texto de 326 caracteres, medidas.

Los tres tests de repetición fallarían con el código anterior. No son
decorativos: son la razón de este fichero.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer.acta_legible import (  # noqa: E402
    _partir_explicacion, _veredicto, render,
)

#: El texto real que `parser._mensaje_de_capa` produce ante `cs_01.dxf`.
MENSAJE_LARGO = (
    "He encontrado varias capas que podrían contener las estancias y ninguna "
    "destaca lo suficiente: «Area Verde» (1110 polilíneas cerradas); "
    "«A-HATCH MUROS» (486 polilíneas cerradas); «A-MOBILIARIO» (312 polilíneas "
    "cerradas, 4% con rótulo dentro); «A-PUERTASVENTANAS» (30 polilíneas "
    "cerradas). Indica cuál es la buena."
)

PRODUCE_REVISION = (
    "revision.recintos", "revision.hallazgos", "revision.recuento_por_tipo",
    "revision.comprobado", "revision.informe", "revision.recintos_geometria",
)


def _acta_cortada(codigo="capa_indeterminada", motivo="no se sabe qué capa del "
                  "DXF contiene las estancias", nombres=PRODUCE_REVISION):
    """Un acta como la que levanta una Skill que no ha podido producir nada."""
    return {
        "objetivo": "Revisa la coherencia de cs_01.dxf",
        "proyecto_id": "p", "ejecucion_id": "e", "emitida_en": "2026-08-23T00:00:00+00:00",
        "datos": [
            {"nombre": n, "valor": None, "unidad": "", "etiqueta": "UNKNOWN",
             "fuente": "skill@1", "motivo": {"codigo": codigo, "detalle": motivo}}
            for n in nombres
        ],
        "pasos": [], "no_comprobado": (motivo,), "preguntas_abiertas": (MENSAJE_LARGO,),
        "entregables": (), "completa": False, "leyenda": "Borrador",
        "sello": "0" * 64,
    }


def _acta_medida():
    """Un acta con resultado, como la de `V5.dxf`."""
    return {
        "objetivo": "Revisa la coherencia de V5.dxf",
        "proyecto_id": "p", "ejecucion_id": "e", "emitida_en": "2026-08-23T00:00:00+00:00",
        "datos": [
            {"nombre": "revision.recintos", "valor": 22, "unidad": "",
             "etiqueta": "CALCULO", "fuente": "skill@1"},
            {"nombre": "revision.hallazgos", "valor": [{"d": 1}, {"d": 2}, {"d": 3}],
             "unidad": "", "etiqueta": "CALCULO", "fuente": "skill@1"},
        ],
        "pasos": [], "no_comprobado": ("no gradúa la gravedad de nada",),
        "preguntas_abiertas": (), "entregables": (), "completa": True,
        "leyenda": "Borrador", "sello": "0" * 64,
    }


# --- El bug: el texto largo aparece UNA vez ---------------------------------

def test_el_mensaje_largo_no_se_repite_en_coherencia():
    """Con el código anterior esto daba 7. La cifra está medida, no supuesta."""
    html = render(_acta_cortada())
    fragmento = "He encontrado varias capas que podrían contener las estancias"
    assert html.count(fragmento) == 1, (
        "el mensaje del parser aparece %d veces; debe aparecer 1"
        % html.count(fragmento))


def test_el_mensaje_largo_no_se_repite_en_medicion():
    """Mismo defecto, misma Skill hermana: `PRODUCE` de 5 entradas -> 6 copias."""
    html = render(_acta_cortada(nombres=(
        "medicion.viviendas", "medicion.piezas", "medicion.viviendas_con_total",
        "medicion.sin_total", "medicion.informe")))
    fragmento = "He encontrado varias capas que podrían contener las estancias"
    assert html.count(fragmento) == 1


def test_los_campos_sin_determinar_se_agrupan_en_una_linea():
    """Seis campos con el mismo motivo son una frase, no seis."""
    html = render(_acta_cortada())
    assert html.count("No determinado") == 1
    # ...y la frase nombra cuántos campos son, para no esconder información.
    assert "6 campos" in html


# --- El veredicto ------------------------------------------------------------

def test_titular_nombra_el_hecho_sin_calificar_el_plano():
    titular, _visible, _plegado = _veredicto(_acta_cortada())
    assert titular == "Este plano no trae las estancias como polilíneas cerradas"
    # D-7: el titular no puede calificar el trabajo de otro arquitecto.
    for palabra in ("incompleto", "mal", "error del plano", "defectuoso"):
        assert palabra not in titular.lower()


def test_titular_de_escala_indeterminada():
    titular, _v, _p = _veredicto(_acta_cortada(codigo="escala_indeterminada"))
    assert titular == "No se puede saber en qué unidad está dibujado este plano"


def test_titular_de_exito_cuenta_lo_que_hay():
    titular, _v, _p = _veredicto(_acta_medida())
    assert titular == "Plano revisado · 22 recintos, 3 hallazgos"


def test_codigo_desconocido_no_inventa_titular():
    """El fallback dice qué código ha llegado en vez de improvisar una frase."""
    titular, visible, _p = _veredicto(_acta_cortada(codigo="codigo_que_no_existe"))
    assert titular == "No se ha podido completar la revisión"
    assert "codigo_que_no_existe" in visible


def test_la_explicacion_visible_es_corta():
    """Como mucho tres frases fuera de los desplegables."""
    _t, visible, _p = _veredicto(_acta_cortada())
    assert visible.count(".") <= 3, visible
    assert len(visible) < 200, visible


# --- El plegado --------------------------------------------------------------

def test_la_lista_de_capas_queda_plegada_y_no_se_pierde():
    _t, visible, plegado = _veredicto(_acta_cortada())
    assert "Area Verde" not in visible, "la enumeración no debe estar a la vista"
    assert "Area Verde" in plegado, "...pero tiene que seguir estando"
    # Nada se pierde por el camino.
    assert "1110 polilíneas cerradas" in plegado


def test_partir_explicacion_no_pierde_texto():
    visible, plegado = _partir_explicacion(MENSAJE_LARGO)
    for trozo in ("He encontrado varias capas", "Area Verde",
                  "A-PUERTASVENTANAS", "Indica cuál es la buena"):
        assert trozo in visible or trozo in plegado, trozo


def test_un_texto_sin_lista_se_deja_entero():
    """Si el mensaje no tiene la forma esperada, no se parte a la fuerza."""
    corto = "No encuentro ese fichero."
    visible, plegado = _partir_explicacion(corto)
    assert visible == corto
    assert plegado == ""


def test_las_secciones_largas_van_plegadas():
    html = render(_acta_medida())
    for seccion in ("Qué se ha establecido", "Qué no se ha comprobado"):
        assert "<summary>%s</summary>" % seccion in html, seccion


if __name__ == "__main__":
    fallos = 0
    for nombre, funcion in sorted(globals().items()):
        if not nombre.startswith("test_") or not callable(funcion):
            continue
        try:
            funcion()
            print("[OK]    %s" % nombre)
        except AssertionError as exc:
            fallos += 1
            print("[FALLA] %s: %s" % (nombre, exc))
    sys.exit(1 if fallos else 0)
