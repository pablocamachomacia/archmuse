# -*- coding: utf-8 -*-
"""C4 — Geometría por referencia.

**La regla, y es estructural:** un nodo no contiene geometría; la referencia
por `geom_id`. `Espacio.geometrias` es un mapa `representacion -> geom_id`, no
un polígono.

    Espacio(id="es-0001")
       └─ geometrias: {"huella_2d": "g-0001"}
                                      │
    AlmacenGeometria ─────────────────┘   único sitio del modelo donde vive
                                          shapely (frontera comprobada por
                                          tests/test_modelo_fronteras.py)

Cuatro cosas que esto hace posibles y que un polígono embebido impide:

1. **El editor** mueve geometría sin tocar identidad ni semántica.
2. **El 3D** obtiene otra representación (`solido`, `malla`) del mismo
   elemento, en vez de una conversión improvisada — hoy el visor reconstruye
   el edificio en JavaScript con sus propias constantes.
3. **El importador** puede aportar dos geometrías del mismo elemento (huella
   2D del DXF, sólido del IFC) sin que una destruya la otra.
4. **La presentación** genera una representación más, marcada como vista, en
   vez de contaminar el dato. Hoy `api_serializer` publica en `poligono` la
   geometría ya recolocada por el layout del SVG.

**La unidad de medida está en el tipo, no en el comentario** (principio P4).
`Room.area_m2` devuelve `polygon.area` y sólo es verdad si la `Room` vino de
`leer_plano`; su propio docstring lo admite. Aquí el almacén se niega a
guardar geometría cuya unidad no sea el metro. La escala se resuelve en la
frontera de entrada (`analyzer/escala.py`, que ya prefiere no responder a
responder mal) y nunca después.

**Derivados admitidos** (`KNOWLEDGE_GRAPH.md` §0.2): función pura de la
geometría del propio nodo, sin umbrales, estables entre ejecuciones. Área,
perímetro, centroide, envolvente, alargamiento, lado mayor y lado menor.

**Un derivado de esa lista que aquí NO se implementa, y por qué.**
`KNOWLEDGE_GRAPH.md` §0.2 incluye «profundidad máxima desde el borde». Medida
así, sin decir *qué* borde, no es función pura de la geometría del nodo: la
profundidad que le importa a la iluminación natural es la distancia **desde la
fachada**, y saber qué lado del polígono es fachada exige mirar los demás
nodos. Es decir, no pasa el propio filtro de §0.2. Se publican en su lugar
`lado_mayor_m` y `lado_menor_m` del rectángulo envolvente mínimo, que son
puros y sostienen los mismos usos sin fingir una semántica que no está.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity

_log = logging.getLogger(__name__)

# --- Vocabulario de representaciones ---------------------------------------
# Cerrado. E1 sólo produce la primera; las otras tres están declaradas para
# que el día que existan no haya que inventar el nombre ni migrar el mapa.

HUELLA_2D = "huella_2d"
EJE = "eje"
SOLIDO = "solido"
MALLA = "malla"

REPRESENTACIONES = (HUELLA_2D, EJE, SOLIDO, MALLA)

# Unidad única del modelo. No hay parámetro para cambiarla: es el contrato.
METRO = "m"

DECIMALES = 3  # milímetro; mismo redondeo que `api_serializer._polygon_points`


class UnidadNoAdmitida(ValueError):
    """Se ha intentado guardar geometría que no está en metros."""


class AlmacenGeometria:
    """`geom_id -> geometría`. El único sitio del modelo que toca shapely.

    Inmutable de hecho: se inserta durante la construcción y, una vez sellada
    la versión, nadie más escribe (invariante I8).
    """

    def __init__(self) -> None:
        self._geometrias: Dict[str, BaseGeometry] = {}
        self._representaciones: Dict[str, str] = {}
        self._contador = 0

    # --- Escritura --------------------------------------------------------

    def insertar(self, geometria: BaseGeometry, representacion: str = HUELLA_2D,
                 unidad: str = METRO) -> str:
        """Guarda una geometría y devuelve su `geom_id`.

        `unidad` es obligatoria en la firma y sólo admite el metro. No es
        decorativo: es la corrección estructural del defecto que ya costó una
        vez —un DXF en milímetros pasaba todas las superficies mínimas con
        nota alta— trasladada del comentario al tipo.
        """
        if unidad != METRO:
            raise UnidadNoAdmitida(
                "el modelo solo admite geometria en metros (recibido %r). "
                "La escala se resuelve en la frontera de entrada, no aqui."
                % (unidad,)
            )
        if representacion not in REPRESENTACIONES:
            raise ValueError(
                "representacion desconocida: %r (admitidas: %r)"
                % (representacion, REPRESENTACIONES)
            )
        if geometria is None or geometria.is_empty:
            raise ValueError("no se guarda una geometria vacia")
        self._contador += 1
        geom_id = "g-%04d" % self._contador
        self._geometrias[geom_id] = _canonica(geometria)
        self._representaciones[geom_id] = representacion
        return geom_id

    # --- Lectura ----------------------------------------------------------

    def __contains__(self, geom_id: str) -> bool:
        return geom_id in self._geometrias

    def __len__(self) -> int:
        return len(self._geometrias)

    def ids(self) -> List[str]:
        return sorted(self._geometrias)

    def representacion(self, geom_id: str) -> str:
        return self._representaciones[geom_id]

    def bruta(self, geom_id: str) -> BaseGeometry:
        """La geometría shapely.

        **Sólo para el constructor, el serializador y la capa de
        compatibilidad.** Una regla que llame aquí se ha saltado la frontera:
        lo que se le ofrece son los derivados de abajo.
        """
        return self._geometrias[geom_id]

    # --- Derivados admitidos (§0.2) ---------------------------------------

    def area_m2(self, geom_id: str) -> float:
        return float(self._geometrias[geom_id].area)

    def perimetro_m(self, geom_id: str) -> float:
        return float(self._geometrias[geom_id].length)

    def centroide(self, geom_id: str) -> Tuple[float, float]:
        c = self._geometrias[geom_id].centroid
        return float(c.x), float(c.y)

    def envolvente(self, geom_id: str) -> Tuple[float, float, float, float]:
        return tuple(float(v) for v in self._geometrias[geom_id].bounds)

    def _lados_del_rectangulo(self, geom_id: str) -> Tuple[float, float]:
        """Lados del rectángulo envolvente mínimo, mayor primero.

        Se toman dos lados **consecutivos**, no los dos mayores: en un
        rectángulo los dos largos son iguales y el alargamiento saldría
        siempre 1,0. Es el mismo cuidado que ya tuvo el experimento.
        """
        rect = self._geometrias[geom_id].minimum_rotated_rectangle
        xs, ys = rect.exterior.coords.xy
        lados = []
        for i in range(len(xs) - 1):
            dx, dy = xs[i + 1] - xs[i], ys[i + 1] - ys[i]
            lados.append((dx * dx + dy * dy) ** 0.5)
        if len(lados) < 2:
            return 0.0, 0.0
        largo, ancho = lados[0], lados[1]
        return float(max(largo, ancho)), float(min(largo, ancho))

    def lado_mayor_m(self, geom_id: str) -> float:
        return self._lados_del_rectangulo(geom_id)[0]

    def lado_menor_m(self, geom_id: str) -> float:
        return self._lados_del_rectangulo(geom_id)[1]

    def alargamiento(self, geom_id: str) -> float:
        mayor, menor = self._lados_del_rectangulo(geom_id)
        return mayor / (menor or 1e-9)

    def derivados(self, geom_id: str) -> dict:
        """Todos los derivados admitidos de una geometría, ya redondeados.

        Es lo que el serializador publica y lo que una regla debería leer. No
        incluye ni una conclusión: área y perímetro son aritmética, y ahí
        acaba lo que el modelo se permite calcular.
        """
        cx, cy = self.centroide(geom_id)
        mayor, menor = self._lados_del_rectangulo(geom_id)
        return {
            "area_m2": round(self.area_m2(geom_id), DECIMALES),
            "perimetro_m": round(self.perimetro_m(geom_id), DECIMALES),
            "centroide": [round(cx, DECIMALES), round(cy, DECIMALES)],
            "envolvente": [round(v, DECIMALES) for v in self.envolvente(geom_id)],
            "lado_mayor_m": round(mayor, DECIMALES),
            "lado_menor_m": round(menor, DECIMALES),
            "alargamiento": round(self.alargamiento(geom_id), DECIMALES),
        }

    # --- Serialización ----------------------------------------------------

    def a_dict(self) -> dict:
        """Contorno exterior de cada geometría, en metros y a 3 decimales.

        Sin el punto de cierre duplicado, misma convención que
        `api_serializer._polygon_points`. Un `MultiPolygon` guarda su
        sub-polígono de mayor área: el modelo representa un recinto como un
        volumen, no como varios.
        """
        salida = {}
        for geom_id, geom in self._geometrias.items():
            salida[geom_id] = {
                "representacion": self._representaciones[geom_id],
                "unidad": METRO,
                "tipo": "poligono",
                "puntos": _puntos_de(geom),
            }
        return salida

    @classmethod
    def desde_dict(cls, datos: dict) -> "AlmacenGeometria":
        almacen = cls()
        for geom_id in sorted(datos):
            entrada = datos[geom_id]
            almacen._geometrias[geom_id] = Polygon(
                [(p[0], p[1]) for p in entrada["puntos"]])
            almacen._representaciones[geom_id] = entrada["representacion"]
            almacen._contador = max(almacen._contador, int(geom_id.split("-")[1]))
        return almacen


def _canonica(geom: BaseGeometry) -> BaseGeometry:
    """La misma geometría, sin los vértices que se repiten al milímetro.

    **Por qué existe** (defecto H1 de
    `docs/audits/2026-08-13-hallazgos-cierre-geometrico.md` §2). Este módulo
    declaraba el milímetro como su precisión (`DECIMALES`) y `a_dict()` la
    aplicaba al salir, pero `insertar()` guardaba el polígono tal cual llegaba
    del DXF. Resultado: un grafo recién construido y el mismo grafo recargado
    desde JSON tenían el **mismo sellado** —porque el sellado se calcula sobre
    la forma ya normalizada— y sin embargo **polígonos distintos en memoria**,
    con distinto número de vértices en `exterior.coords`. El round-trip de C7.4
    era exacto en el JSON y no lo era en el modelo.

    Medido sobre `ejemplo.dxf`: 9 de 40 geometrías traen un vértice de más
    (`g-0029` y `g-0034`, dos). Son los recintos que `_esta_cerrada()` recupera
    por coincidencia geométrica pese al flag `closed=False`: su vértice de
    cierre está repetido a menos de un milímetro del primero, no exactamente
    encima. Por eso **no vale deduplicar a precisión completa** — 8 de las 9 no
    tienen ni un par de vértices exactamente iguales; los duplicados sólo
    aparecen al redondear.

    La corrección es imponer al entrar la precisión que el módulo ya prometía,
    con la misma función que usa la serialización (`_puntos_de`), de forma que
    construir y recargar produzcan el mismo objeto por construcción. **No se
    toca `verificar_sellado()`:** el sello sigue siendo tan estricto como era;
    lo que cambia es que la geometría guardada ya es canónica.

    **Lo que esta función NO hace, y por qué.** No redondea las coordenadas que
    sobreviven. El primer intento sí lo hacía —guardar directamente
    `_puntos_de(geom)`, la forma ya redondeada— y G9 lo rechazó: mover cada
    vértice hasta medio milímetro basta para que `tramo_enfrentado_m` deje de
    ver 21 de las adyacencias que el analizador sí encuentra
    (`equivalencia_G3.coinciden` pasaba a `False`). La topología se mide sobre
    la geometría de origen; lo único que sobra es el vértice redundante.

    Así que se decide **qué** vértice sobra mirando la coordenada redondeada, y
    se conserva la coordenada **sin redondear** del superviviente. El recuento
    de vértices pasa a coincidir con el del grafo recargado —que es lo que
    rompía el round-trip— sin desplazar ni un contorno.

    Sólo se canoniza un `Polygon`. Cualquier otra geometría se guarda tal cual:
    hoy no se inserta ninguna (las 40 de `ejemplo.dxf` son polígonos) y reducir
    aquí un `MultiPolygon` a su mayor parte, como hace `a_dict()`, sería un
    cambio de semántica que este defecto no pide.
    """
    if geom.geom_type != "Polygon":
        return geom
    crudos = list(geom.exterior.coords)
    conservados: List[Tuple[float, float]] = []
    vistos: List[Tuple[float, float]] = []
    for x, y in crudos:
        clave = (round(x, DECIMALES), round(y, DECIMALES))
        if vistos and vistos[-1] == clave:
            continue  # redundante por debajo del milímetro: sobra
        conservados.append((x, y))
        vistos.append(clave)
    # El vértice de cierre explícito: shapely lo repone solo al construir.
    if len(vistos) > 1 and vistos[0] == vistos[-1]:
        conservados = conservados[:-1]
        vistos = vistos[:-1]
    if len(conservados) < 3:
        raise ValueError(
            "geometria degenerada al milimetro: quedan %d vertices distintos "
            "tras redondear a %d decimales. Una huella asi no describe un "
            "recinto; revisa la escala de entrada." % (len(conservados), DECIMALES)
        )
    limpia = Polygon(conservados)
    # `crudos` trae el vértice de cierre que shapely repone, así que los
    # vértices reales del contorno de origen son uno menos.
    originales = len(crudos) - 1
    descartados = originales - len(conservados)
    if descartados > 0:
        # Nunca en silencio, por el mismo motivo que
        # `parser._recuperar_cierre_por_geometria`: descartar un vertice es una
        # correccion de datos, no un hecho neutro, y tiene que quedar visible
        # para quien audite despues por que una superficie salio como salio.
        # El caso de `reparado` es el que mas importa: un contorno que pasa de
        # invalido a valido deja de emitir `GEOMETRY_INVALID` aguas abajo
        # (`analyzer/superficie_util.py::_revisar`), asi que este aviso es el
        # unico rastro de que el defecto existia en el dibujo de origen.
        if not geom.is_valid and limpia.is_valid:
            nota = ("El contorno de origen era INVALIDO (%s) y al descartarlos "
                    "pasa a ser valido: es un defecto del dibujo, no del "
                    "modelo." % explain_validity(geom))
        else:
            nota = "La validez del contorno no cambia."
        _log.warning(
            "Contorno canonizado: %d vertice(s) descartado(s) por repetirse al "
            "redondear a %d decimales (de %d a %d). %s",
            descartados, DECIMALES, originales, len(conservados), nota,
        )
    return limpia


def _puntos_de(geom: BaseGeometry) -> List[List[float]]:
    objetivo = geom
    if objetivo.geom_type == "MultiPolygon":
        objetivo = max(objetivo.geoms, key=lambda g: g.area, default=None)
        if objetivo is None:
            return []
    if objetivo.geom_type != "Polygon":
        return []
    redondeados = [(round(x, DECIMALES), round(y, DECIMALES))
                   for x, y in objetivo.exterior.coords]
    coords: List[Tuple[float, float]] = []
    for punto in redondeados:
        if not coords or coords[-1] != punto:
            coords.append(punto)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return [[x, y] for x, y in coords]


def distancia_m(almacen: AlmacenGeometria, a: str, b: str) -> float:
    """Separación entre dos geometrías. Vive aquí, con shapely, y no en
    `aristas.py`: la topología decide *qué* significa cerca, no *cuánto*."""
    return float(almacen.bruta(a).distance(almacen.bruta(b)))


def distancia_centroides_m(almacen: AlmacenGeometria, a: str, b: str) -> float:
    return float(almacen.bruta(a).centroid.distance(almacen.bruta(b).centroid))


def tramo_enfrentado_m(almacen: AlmacenGeometria, a: str, b: str,
                       tolerancia: float) -> float:
    """Longitud del tramo en que dos contornos se miran de frente.

    No se puede medir como borde compartido: en los planos reales los
    polígonos casi nunca se tocan —cada recinto se dibuja en la cara interior
    de su propio muro— y por eso el criterio antiguo de borde compartido
    (`evaluator._is_adjacent`, ya eliminado) no disparaba nunca. Se
    mide cuánto del contorno de cada uno cae dentro del espesor de muro
    plausible del otro, y se toma el menor de los dos.

    **Se mide y se guarda; no filtra.** Decisión cerrada de E0: el umbral de
    contigüidad sigue abierto hasta tener proyectos reales, porque el
    experimento demostró que el 0,60 m propuesto no está justificado (en VT3/3
    hay un tramo de 0,570 m del que depende un hallazgo).
    """
    ga, gb = almacen.bruta(a), almacen.bruta(b)
    ab = gb.boundary.intersection(ga.buffer(tolerancia)).length
    ba = ga.boundary.intersection(gb.buffer(tolerancia)).length
    return float(min(ab, ba))
