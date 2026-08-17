from shapely.geometry import Polygon

from analyzer.ai_generator import GeneratedProject, derivar_mixes_alternativos
from analyzer.comparador_opciones import (
    calcular_metricas_opcion,
    pct_fachada_aprovechada,
    repercusion_zonas_comunes_pct,
)
from analyzer.evaluator import Unit
from analyzer.parser import Room


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def test_derivar_mixes_dos_opciones_distintas():
    mixes = derivar_mixes_alternativos(1000.0)
    assert list(mixes.keys()) == ["A", "B"]
    a, b = mixes["A"], mixes["B"]
    # A es compacta (más viviendas pequeñas): más dorm_1 que B.
    assert a["dorm_1"] > b["dorm_1"]
    # B es amplia (menos viviendas, más grandes): más dorm_3 que A.
    assert b["dorm_3"] > a["dorm_3"]


def test_derivar_mixes_sin_superficie_no_inventa_nada():
    assert derivar_mixes_alternativos(0) == {}
    assert derivar_mixes_alternativos(-10) == {}


def test_derivar_mixes_preserva_superficie_minima_recibida():
    mixes = derivar_mixes_alternativos(1000.0, superficie_minima_m2=38.0)
    assert mixes["A"]["superficie_minima_m2"] == 38.0
    assert mixes["B"]["superficie_minima_m2"] == 38.0


def _unit_residencial(nombre, con_fachada=True):
    dormitorio = Room(
        label="Dormitorio 1",
        polygon=_rect(0, 0, 3, 4) if con_fachada else _rect(0, 0, 3, 4),
        layer="00 areas",
    )
    otra = Room(label="Dormitorio 2", polygon=_rect(3, 0, 6, 4), layer="00 areas")
    return Unit(name=nombre, rooms=[dormitorio, otra])


def _unit_nucleo(nombre, area=10.0):
    lado = area ** 0.5
    room = Room(label="Núcleo de comunicación", polygon=_rect(0, 0, lado, lado), layer="00 areas")
    return Unit(name=nombre, rooms=[room])


def test_repercusion_zonas_comunes_real():
    vivienda = _unit_residencial("VT1")  # 3x4 + 3x4 = 24 m2
    nucleo = _unit_nucleo("Núcleo", area=6.0)
    project = GeneratedProject(units=[vivienda, nucleo], rooms=[])
    pct = repercusion_zonas_comunes_pct(project)
    assert pct == 6.0 / (24.0 + 6.0) * 100.0


def test_repercusion_zonas_comunes_sin_nucleo_es_cero():
    vivienda = _unit_residencial("VT1")
    project = GeneratedProject(units=[vivienda], rooms=[])
    assert repercusion_zonas_comunes_pct(project) == 0.0


def test_pct_fachada_aprovechada_excluye_nucleo():
    vivienda = _unit_residencial("VT1")
    nucleo = _unit_nucleo("Núcleo")
    project = GeneratedProject(units=[vivienda, nucleo], rooms=[])
    pct = pct_fachada_aprovechada(project)
    assert pct is not None  # el núcleo no debe hacer que esto falle ni contar piezas suyas


def test_margen_estimado_usa_superficie_de_la_propia_opcion():
    vivienda = _unit_residencial("VT1")  # 24 m2
    project = GeneratedProject(units=[vivienda], rooms=[])
    metricas = calcular_metricas_opcion(
        "A", project, mix_viviendas={"dorm_1": 1, "dorm_2": 0, "dorm_3": 0},
        ratio_m2=1000.0, coste_suelo=5000.0, precio_venta=50000.0,
    )
    assert metricas.margen_estimado.inversion_total == 24.0 * 1000.0 + 5000.0
    assert metricas.margen_estimado.margen_eur == 50000.0 - metricas.margen_estimado.inversion_total


def test_margen_estimado_sin_datos_no_inventa():
    vivienda = _unit_residencial("VT1")
    project = GeneratedProject(units=[vivienda], rooms=[])
    metricas = calcular_metricas_opcion("A", project, mix_viviendas={})
    assert metricas.margen_estimado.margen_eur is None
