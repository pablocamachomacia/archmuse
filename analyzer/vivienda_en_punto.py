# -*- coding: utf-8 -*-
"""Un clic, una tabla: qué vivienda está al lado del punto, y qué hace falta para medirla.

PRD `docs/prd/2026-09-15-un-clic-una-tabla.md`. Criterio `C-17`, **PROPUESTO,
PENDIENTE DE FIRMA** (`docs/design/2026-09-08-criterios-firmados-de-medicion.md`).

**Aquí no se mide nada.** Se decide de qué vivienda es la tabla, con el mismo
agrupador que la medición (`evaluator.agrupar_por_rotulo`, o por proximidad si el
plano no tiene rótulos `VT`), y qué polilíneas de las demás capas tiene que mandar
el comando para que la medición de esa vivienda salga **idéntica** a la de la
planta entera. La medición la hace después la ruta de siempre.

**Por qué las zonas son los cuadrados de los rótulos de construida.** De las
polilíneas de otras capas, la medición sólo mira las que están al alcance de un
rótulo «Superficie construida cerrada» (`C-12`, `plantilla_cuadro.medir_construida`):
las que están a su alcance cuentan —también para decir que un rótulo tiene dos y
es dudoso— y las demás no aparecen en ningún cálculo. Una polilínea a menos del
alcance del punto del rótulo corta el cuadrado de ese alcance, así que mandar las
que cortan esos cuadrados es mandar todas las que pueden cambiar una cifra. La
caja de la vivienda no bastaría: el segundo candidato de un rótulo dudoso puede
estar lejos de ella.

Las capas de clasificación `AM_*` cambian de dónde salen los recintos: ésas viajan
enteras, también antes de elegir.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from shapely.geometry import Point

#: `C-17`, propuesto. Hay duda si la segunda vivienda más cercana está a menos del
#: doble de distancia que la primera…
FACTOR_DE_DUDA = 2.0
#: …o a menos de un metro más lejos.
MARGEN_DE_DUDA_M = 1.0
#: Más lejos que esto, un clic no dice de qué vivienda es la tabla.
DISTANCIA_MAXIMA_M = 30.0
#: Holgura de las zonas sobre el alcance del rótulo: sólo puede mandar de más.
HOLGURA_DE_ZONA = 0.01
#: Dos rótulos a menos de esto son el mismo (en metros).
TOLERANCIA_DE_ROTULO_M = 0.01


def _metros(valor: float) -> str:
    return ("%.2f" % valor).replace(".", ",")


@dataclass(frozen=True)
class ViviendaDelPlano:
    nombre: str
    #: Dónde está su rótulo `VT`, en metros; `None` si se agrupó por proximidad.
    rotulo: Optional[Tuple[float, float]]
    rooms: tuple
    viviendas_con_el_mismo_rotulo: int
    #: Su sitio en el orden del agrupador, el mismo que el de
    #: `medicion.medir_planta(plano).viviendas`. Con él se distinguen dos
    #: viviendas con el mismo rótulo (enmienda de `C-13`, Pablo, 2026-09-15).
    posicion: int = 0

    def distancia_a(self, punto: Point) -> float:
        return min(r.polygon.distance(punto) for r in self.rooms)

    def a_json(self) -> str:
        """Lo que el comando devuelve tal cual en la segunda petición."""
        rotulo = None if self.rotulo is None else [round(self.rotulo[0], 6), round(self.rotulo[1], 6)]
        return json.dumps({"nombre": self.nombre, "rotulo": rotulo}, ensure_ascii=False)


def viviendas_del_plano(plano) -> List[ViviendaDelPlano]:
    """Las viviendas del plano, con el agrupador de `medicion.medir_planta`."""
    from . import evaluator

    rooms = list(plano.rooms)
    etiquetas = list(getattr(plano, "unit_labels", None) or [])
    if etiquetas:
        grupos = [(etiquetas[i][0], (float(etiquetas[i][1]), float(etiquetas[i][2])), piezas)
                  for i, piezas in evaluator.agrupar_por_rotulo(rooms, etiquetas)]
    else:
        grupos = [(u.name, None, u.rooms) for u in evaluator.group_rooms_by_proximity(rooms)]
    cuenta = Counter(nombre for nombre, _r, _p in grupos)
    return [ViviendaDelPlano(nombre, rotulo, tuple(piezas), cuenta[nombre], posicion)
            for posicion, (nombre, rotulo, piezas) in enumerate(grupos)]


def factor_a_metros(plano) -> float:
    from . import plantilla_cuadro

    return plantilla_cuadro._factor_a_metros(plano)


def punto_en_metros(punto: Sequence[float], plano) -> Tuple[float, float]:
    factor = factor_a_metros(plano)
    return (float(punto[0]) * factor, float(punto[1]) * factor)


@dataclass(frozen=True)
class Eleccion:
    vivienda: Optional[ViviendaDelPlano]
    motivo: Optional[str]
    aviso: Optional[str]
    distancia_m: Optional[float] = None


def elegir(viviendas: Sequence[ViviendaDelPlano], punto_m: Tuple[float, float]) -> Eleccion:
    """`C-17`, propuesto: la vivienda más cercana al punto, o por qué no se mide."""
    if not viviendas:
        return Eleccion(None, "no hay ninguna vivienda en la capa de recintos: no hay nada que "
                              "medir.", None)
    punto = Point(punto_m)
    orden = sorted((v.distancia_a(punto), n, v) for n, v in enumerate(viviendas))
    d1, _n, primera = orden[0]
    if d1 > DISTANCIA_MAXIMA_M:
        return Eleccion(None, "No mido: la vivienda más cercana al punto, %s, está a %s m, y un "
                              "clic tan lejos no dice de qué vivienda quieres la tabla. Haz clic "
                              "junto a su dibujo (C-17, propuesto)." % (primera.nombre, _metros(d1)),
                        None, d1)
    siguiente = None
    if len(orden) > 1:
        d2, _n2, siguiente = orden[1]
        # **Dentro de una pieza no hay duda** (medido el 2026-09-15 en el maestro:
        # 7 de 52 clics dentro de la pieza mayor de una vivienda decían «No mido»
        # porque el tabique de la de al lado quedaba a menos de 1 m). Un punto que
        # cae dentro de una sola vivienda no está «a distancia parecida» de dos.
        dentro_de_una = d1 == 0 and d2 > 0
        if not dentro_de_una and (d2 < FACTOR_DE_DUDA * d1 or d2 - d1 < MARGEN_DE_DUDA_M):
            return Eleccion(None, "No mido: el punto está a %s m de %s y a %s m de %s, y no sé de "
                                  "cuál de las dos quieres la tabla. Haz clic más cerca de una "
                                  "(C-17, propuesto)."
                            % (_metros(d1), primera.nombre, _metros(d2), siguiente.nombre), None, d1)
    donde = ("el punto cae dentro de su dibujo" if d1 == 0 else "a %s m del punto" % _metros(d1))
    if siguiente is not None:
        aviso = ("Mido %s: es la vivienda más cercana (%s; la siguiente, %s, está a %s m)."
                 % (primera.nombre, donde, siguiente.nombre, _metros(orden[1][0])))
    else:
        aviso = "Mido %s: es la única vivienda del plano (%s)." % (primera.nombre, donde)
    if primera.viviendas_con_el_mismo_rotulo > 1:
        # Enmienda de `C-13` firmada por Pablo el 2026-09-15: el clic la distingue.
        aviso += (" Hay %d viviendas rotuladas «%s»: mido la de este clic, por su posición, "
                  "y sus cifras no se suman con las de las otras (C-13)."
                  % (primera.viviendas_con_el_mismo_rotulo, primera.nombre))
    return Eleccion(primera, None, aviso, d1)


def es_la_pedida(vivienda: ViviendaDelPlano, pedida: dict) -> bool:
    """¿Es ésta la vivienda que eligió la primera petición?"""
    if not isinstance(pedida, dict) or pedida.get("nombre") != vivienda.nombre:
        return False
    rotulo = pedida.get("rotulo")
    if vivienda.rotulo is None or rotulo is None:
        return vivienda.rotulo is None and rotulo is None
    try:
        x, y = float(rotulo[0]), float(rotulo[1])
    except (TypeError, ValueError, IndexError):
        return False
    return (abs(x - vivienda.rotulo[0]) <= TOLERANCIA_DE_ROTULO_M
            and abs(y - vivienda.rotulo[1]) <= TOLERANCIA_DE_ROTULO_M)


def zonas_de_otras_capas(doc, plano) -> List[Tuple[float, float, float, float]]:
    """Rectángulos, **en unidades de dibujo**, de los que el comando tiene que
    mandar las polilíneas de otras capas: el cuadrado del alcance de cada rótulo
    de construida, con una holgura que sólo puede añadir polilíneas."""
    from . import plantilla_cuadro

    factor = factor_a_metros(plano)
    zonas = []
    for rotulo in plantilla_cuadro.rotulos_de_construida(doc, factor):
        if rotulo.alcance_m is None:
            continue
        a = rotulo.alcance_m * (1 + HOLGURA_DE_ZONA) / factor + 1e-6
        x, y = rotulo.punto[0] / factor, rotulo.punto[1] / factor
        zonas.append((x - a, y - a, x + a, y + a))
    return zonas


def corta_alguna_zona(vertices: Iterable[Sequence[float]], zonas) -> bool:
    """La misma prueba que hace el comando: la caja de la polilínea corta la zona."""
    puntos = [(float(v[0]), float(v[1])) for v in vertices]
    xs = [p[0] for p in puntos]
    ys = [p[1] for p in puntos]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    return any(x0 <= z[2] and x1 >= z[0] and y0 <= z[3] and y1 >= z[1] for z in zonas)


def capas_enteras(capas_del_dibujo: Iterable[str]) -> List[str]:
    """Las capas de clasificación `AM_*` que tiene el dibujo, con su nombre allí."""
    from .parser import CAPAS_AM_OPERATIVAS

    operativas = {c.lower() for c in CAPAS_AM_OPERATIVAS}
    return sorted({str(c) for c in capas_del_dibujo if str(c).strip().lower() in operativas})


def a_dict(eleccion: Eleccion) -> dict:
    v = eleccion.vivienda
    return {
        "ok": v is not None,
        "motivo": eleccion.motivo,
        "aviso": eleccion.aviso,
        "vivienda": None if v is None else v.nombre,
        "vivienda_json": None if v is None else v.a_json(),
    }
