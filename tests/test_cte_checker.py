from shapely.geometry import Polygon

from analyzer.cte_checker import (
    ESTADO_CUMPLE,
    ESTADO_NO_CUMPLE,
    ESTADO_NO_EVALUABLE,
    generar_checklist_cte,
)
from analyzer.evaluator import Unit, score_unit
from analyzer.parser import Room


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _unit_con_pasillo(ancho_pasillo=1.3, dormitorio_1_area_ok=True):
    """Vivienda sintética: Salón/Cocina + Pasillo + Dormitorio 1, todos
    contiguos, para que el grafo de evacuación/circulación tenga algo que
    recorrer y `evaluate_corridor_width` tenga un Pasillo que medir."""
    salon = Room(label="Salón", polygon=_rect(0, 0, 5, 4.5), layer="00 areas")
    pasillo = Room(
        label="Pasillo", polygon=_rect(0, 4.5, 5, 4.5 + ancho_pasillo), layer="00 areas",
    )
    dorm_area = 12.0 if dormitorio_1_area_ok else 4.0
    dorm_ancho = dorm_area / 3.0
    dormitorio = Room(
        label="Dormitorio 1",
        polygon=_rect(0, 4.5 + ancho_pasillo, dorm_ancho, 4.5 + ancho_pasillo + 3.0),
        layer="00 areas",
    )
    return Unit(name="VT1", rooms=[salon, pasillo, dormitorio])


def _score(unit, tipologia="plurifamiliar"):
    return score_unit(unit, hierarchy=[], efficiency=[], orientation=[], tipologia=tipologia)


def test_evacuacion_siempre_no_evaluable_nunca_veredicto():
    """El hallazgo central del PRD: aunque el usuario confirme 'dos
    salidas', la evacuación no puede dar verde/rojo -- ver docstring de
    `docs/audits/DB-SI_REVIEW.md` ficha C09."""
    us = _score(_unit_con_pasillo())
    for dos_salidas in (False, True):
        items = generar_checklist_cte(us, "plurifamiliar", dos_salidas_confirmado=dos_salidas)
        evacuacion = next(i for i in items if i.titulo == "Distancia de evacuación")
        assert evacuacion.estado == ESTADO_NO_EVALUABLE
        assert evacuacion.datos["distancia_m"] > 0


def test_evacuacion_umbral_datos_refleja_checkbox():
    us = _score(_unit_con_pasillo())
    items = generar_checklist_cte(us, "plurifamiliar", dos_salidas_confirmado=True)
    evacuacion = next(i for i in items if i.titulo == "Distancia de evacuación")
    assert evacuacion.datos["umbral_1_salida_m"] == 25.0
    assert evacuacion.datos["umbral_2_salidas_m"] == 50.0


def test_itinerario_accesible_no_aplica_fuera_de_plurifamiliar():
    us = _score(_unit_con_pasillo(), tipologia="unifamiliar")
    items = generar_checklist_cte(us, "unifamiliar")
    itin = next(i for i in items if "Itinerario accesible" in i.titulo)
    assert itin.estado == ESTADO_NO_EVALUABLE
    assert "no aplica" in itin.detalle.lower()


def test_itinerario_accesible_cumple_con_pasillo_ancho():
    us = _score(_unit_con_pasillo(ancho_pasillo=1.3))
    items = generar_checklist_cte(us, "plurifamiliar")
    itin = next(i for i in items if "Itinerario accesible" in i.titulo)
    assert itin.estado == ESTADO_CUMPLE


def test_itinerario_accesible_no_cumple_con_pasillo_estrecho():
    us = _score(_unit_con_pasillo(ancho_pasillo=1.0))
    items = generar_checklist_cte(us, "plurifamiliar")
    itin = next(i for i in items if "Itinerario accesible" in i.titulo)
    assert itin.estado == ESTADO_NO_CUMPLE


def test_superficie_minima_dormitorio_no_cumple():
    us = _score(_unit_con_pasillo(dormitorio_1_area_ok=False))
    items = generar_checklist_cte(us, "plurifamiliar")
    dorm = next(i for i in items if "Dormitorio 1" in i.titulo)
    assert dorm.estado == ESTADO_NO_CUMPLE
    assert dorm.codigo == "HABITABILIDAD-SUP"


def test_superficie_minima_salon_cumple():
    us = _score(_unit_con_pasillo())
    items = generar_checklist_cte(us, "plurifamiliar")
    salon = next(i for i in items if "Salón/Cocina" in i.titulo)
    assert salon.estado == ESTADO_CUMPLE


def test_hueco_paso_siempre_no_evaluable():
    us = _score(_unit_con_pasillo())
    items = generar_checklist_cte(us, "plurifamiliar")
    hueco = next(i for i in items if "hueco de paso" in i.titulo.lower())
    assert hueco.estado == ESTADO_NO_EVALUABLE


def test_ancho_pasillo_estrecho_no_cumple():
    us = _score(_unit_con_pasillo(ancho_pasillo=0.5))
    items = generar_checklist_cte(us, "plurifamiliar")
    pasillos = [i for i in items if i.titulo.startswith("Ancho de paso")]
    assert pasillos and all(i.estado == ESTADO_NO_CUMPLE for i in pasillos)
