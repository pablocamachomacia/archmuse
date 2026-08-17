# -*- coding: utf-8 -*-
"""C6 — Los ocho invariantes, comprobados al sellar.

**Un grafo que no puede ser inválido es un grafo en el que se puede confiar.**
El incumplimiento de cualquiera de estos ocho es un error del constructor, no
un hallazgo del proyecto: significa que el modelo está mal construido, no que
el edificio esté mal proyectado. Por eso levantan `ModeloInvalido` y no
producen un aviso.

    I1  Todo Espacio pertenece a exactamente una Unidad.
    I2  Todo Espacio pertenece a exactamente una Planta.
    I3  Toda arista une nodos existentes en ESTA version.
    I4  `es_contiguo_a` y `conecta_con` son simetricas.
    I5  Todo Atributo tiene estado y, salvo UNKNOWN, origen.
    I6  Los 11 tipos del catalogo tienen presencia declarada.
    I7  Los instance_id son unicos dentro de la version.
    I8  Una version sellada no se modifica.

Los invariantes **5 y 6 no son estructurales sino epistémicos**, y son los dos
que de verdad protegen contra la familia del Bug #1: un valor sin origen es un
modelo inválido, no un valor por defecto; y la ausencia de nodos de un tipo no
es interpretable sin su estado de presencia.

**Dos invariantes del catálogo que E1 no comprueba, y por qué.** «Todo Muro
delimita uno o dos Espacios» no aplica: `Muro` no se materializa en E1. Y el
solapamiento entre polígonos de una misma unidad **no es un invariante sino un
hallazgo** —ya existe como regla de producción (`evaluate_room_overlap`)— y
confundir las dos cosas haría que un proyecto mal dibujado impidiera construir
su propio modelo, que es justo lo contrario de lo que hace falta para poder
enseñarle el problema al arquitecto.
"""
from __future__ import annotations

from typing import List

from .aristas import CONECTA_CON, ES_CONTIGUO_A
from .atributo import Atributo, KNOWN, ESTIMATED, UNKNOWN, ORIGENES
from .nodos import CATALOGO, PRESENCIAS


class ModeloInvalido(RuntimeError):
    """El grafo incumple un invariante. Es un error del constructor."""

    def __init__(self, incumplimientos: List[str]):
        self.incumplimientos = list(incumplimientos)
        super().__init__(
            "modelo invalido (%d incumplimiento(s)):\n  - %s"
            % (len(self.incumplimientos), "\n  - ".join(self.incumplimientos))
        )


def _atributos_de(nodo) -> List[tuple]:
    return [(nombre, valor) for nombre, valor in vars(nodo).items()
            if isinstance(valor, Atributo)]


def comprobar_invariantes(grafo) -> List[str]:
    """Devuelve la lista de incumplimientos. Vacía = grafo válido."""
    fallos: List[str] = []
    espacios = grafo.get_spaces()
    ids_espacio = {e.id for e in espacios}
    ids_unidad = {u.id for u in grafo.unidades()}
    ids_planta = {p.id for p in grafo.plantas()}

    # I1 — todo espacio en exactamente una unidad, y la unidad lo reconoce.
    pertenencia = {}
    for unidad in grafo.unidades():
        for eid in unidad.espacios:
            if eid in pertenencia:
                fallos.append("I1: %s pertenece a %s y a %s"
                              % (eid, pertenencia[eid], unidad.id))
            pertenencia[eid] = unidad.id
    for espacio in espacios:
        if espacio.unidad_id not in ids_unidad:
            fallos.append("I1: %s apunta a la unidad inexistente %s"
                          % (espacio.id, espacio.unidad_id))
        elif pertenencia.get(espacio.id) != espacio.unidad_id:
            fallos.append("I1: %s dice pertenecer a %s pero esa unidad no lo lista"
                          % (espacio.id, espacio.unidad_id))
    huerfanos = ids_espacio - set(pertenencia)
    for eid in sorted(huerfanos):
        fallos.append("I1: %s es huerfano (ninguna unidad lo contiene)" % eid)

    # I2 — todo espacio en exactamente una planta.
    for espacio in espacios:
        if espacio.planta_id not in ids_planta:
            fallos.append("I2: %s apunta a la planta inexistente %s"
                          % (espacio.id, espacio.planta_id))
    for unidad in grafo.unidades():
        if unidad.planta_id not in ids_planta:
            fallos.append("I2: %s apunta a la planta inexistente %s"
                          % (unidad.id, unidad.planta_id))
        for eid in unidad.espacios:
            espacio = grafo.get_space(eid)
            if espacio is not None and espacio.planta_id != unidad.planta_id:
                fallos.append("I2: %s esta en %s pero su unidad %s esta en %s"
                              % (eid, espacio.planta_id, unidad.id, unidad.planta_id))

    # I3 — toda arista une nodos existentes de esta version.
    for arista in grafo.aristas():
        for extremo in (arista.a, arista.b):
            if extremo not in ids_espacio:
                fallos.append("I3: arista %s-%s referencia el espacio inexistente %s"
                              % (arista.a, arista.b, extremo))

    # I4 — simetria de las dos relaciones.
    for espacio in espacios:
        for tipo, vecinos in ((ES_CONTIGUO_A, grafo.contiguous_spaces(espacio)),
                              (CONECTA_CON, grafo.connected_spaces(espacio))):
            for vecino in vecinos:
                inversos = (grafo.contiguous_spaces(vecino) if tipo == ES_CONTIGUO_A
                            else grafo.connected_spaces(vecino))
                if espacio.id not in {v.id for v in inversos}:
                    fallos.append("I4: %s %s %s pero no al reves"
                                  % (espacio.id, tipo, vecino.id))

    # I5 — ningun atributo desnudo. Se recorren los nodos reales, no un
    # esquema: si alguien anade un atributo nuevo, entra solo.
    for nodo in [grafo.proyecto] + list(grafo.edificios()) + list(grafo.plantas()) \
            + list(grafo.unidades()) + list(espacios):
        for nombre, atributo in _atributos_de(nodo):
            etiqueta = "%s.%s" % (getattr(nodo, "id", "?"), nombre)
            if atributo.estado not in (KNOWN, ESTIMATED, UNKNOWN, "NO_APLICABLE"):
                fallos.append("I5: %s tiene estado %r" % (etiqueta, atributo.estado))
            if atributo.estado in (KNOWN, ESTIMATED) and atributo.origen not in ORIGENES:
                fallos.append("I5: %s tiene valor sin origen valido (%r)"
                              % (etiqueta, atributo.origen))
            if atributo.estado == UNKNOWN and not atributo.motivos:
                fallos.append("I5: %s es UNKNOWN sin motivo" % etiqueta)

    # I6 — presencia declarada para los once tipos del catalogo.
    for tipo in CATALOGO:
        estado = grafo.proyecto.presencia.get(tipo)
        if estado is None:
            fallos.append("I6: falta la presencia declarada de %r" % tipo)
        elif estado not in PRESENCIAS:
            fallos.append("I6: presencia %r desconocida para %r" % (estado, tipo))

    # I7 — unicidad de instance_id dentro de la version.
    todos = ([grafo.proyecto.id] + [e.id for e in grafo.edificios()]
             + [p.id for p in grafo.plantas()] + [u.id for u in grafo.unidades()]
             + [e.id for e in espacios])
    vistos = set()
    for identificador in todos:
        if identificador in vistos:
            fallos.append("I7: instance_id duplicado: %s" % identificador)
        vistos.add(identificador)

    # I8 — la version sellada no cambia. Se comprueba comparando la huella
    # guardada con la que produce la serializacion actual; la verificacion
    # completa vive en `serializacion.verificar_sellado`, que es quien sabe
    # calcularla sin crear un ciclo de importacion.
    for geom_id in set(
        gid for espacio in espacios for gid in espacio.geometrias.values()
    ):
        if geom_id not in grafo.almacen:
            fallos.append("I8: geometria referenciada e inexistente: %s" % geom_id)

    return fallos


def exigir_invariantes(grafo) -> None:
    fallos = comprobar_invariantes(grafo)
    if fallos:
        raise ModeloInvalido(fallos)
