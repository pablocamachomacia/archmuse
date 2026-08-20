# -*- coding: utf-8 -*-
"""E1.10 — El Constructor del Grafo: único punto de contacto con el sustrato actual.

Fases de `KNOWLEDGE_GRAPH.md` §5, con las que E1 no hace marcadas como tales:

    Fase 0  Admision        escala y capa resueltas -> las trae `leer_plano`
    Fase 1  Espacios        poligonos cerrados -> nodos Espacio
    Fase 2  Clasificacion   rotulo -> tipo, SIEMPRE como (valor, origen)
    Fase 3  Agrupacion      espacios -> Unidades
    Fase 4  Muros inferidos NO en E1 (decision 2, cerrada por Pablo)
    Fase 5  Topologia       aristas, una sola vez, con un solo criterio
    Fase 6  Sellado         invariantes + huella; la version queda inmutable

**Regla dura del paquete:** éste es el ÚNICO módulo de `modelo/` autorizado a
importar `analyzer.parser`, `analyzer.evaluator` y `analyzer.adyacencia`
(junto con `compat.py`, que es la salida simétrica). Lo comprueba
`tests/test_modelo_fronteras.py`. Todo lo demás de `modelo/` no sabe que
existe un DXF.

**Por qué el constructor importa la agrupación en vez de reimplementarla.**
`group_rooms_by_unit_label` es hoy la única definición de «qué habitaciones
forman una vivienda». Copiarla aquí crearía una segunda —el problema que el
modelo existe para eliminar (principio P5)— y haría que las dos pudieran
divergir en silencio. Se importa, se declara la dependencia y se documenta que
en E2 esa función se muda a este módulo, cuando ya no queden consumidores del
`Unit` original. Lo mismo con `WALL_GAP_TOLERANCE_M`: el número vive en
`adyacencia.py` y el modelo lo lee, en vez de tener su propia copia.
"""
from __future__ import annotations

import unicodedata
from typing import List, Optional, Sequence, Tuple

from analyzer import adyacencia, evaluator, parser  # frontera declarada

from .aristas import CONECTA_CON, CRITERIO_ACTUAL, ES_CONTIGUO_A, Arista, Criterio
from .atributo import (
    ALTA, BAJA, MEDIA, OBSERVADO, SUPUESTO, Atributo, declarado,
    derivado, desconocido, observado,
)
from .geometria import (
    AlmacenGeometria, HUELLA_2D, distancia_centroides_m, distancia_m,
    tramo_enfrentado_m,
)
from .grafo import Grafo
from .identidad import Identidades
from .invariantes import exigir_invariantes
from .nodos import (
    Edificio, Espacio, Planta, PRESENCIA_INFERIDO,
    PRESENCIA_NO_OBSERVABLE, PRESENCIA_OBSERVADO, Procedencia, Proyecto, Unidad,
)
from .serializacion import sellado_de

# --- Fase 2: clasificación (vocabulario de `SPACE_TAXONOMY.md`) -------------
#
# Copiada de `experimentos/grafo/constructor.py`, que la validó contra
# `ejemplo.dxf`. Se copia y no se importa: `experimentos/` es código
# desechable y producción no puede depender de él (regla 13 de E1). El
# experimento se conserva intacto como evidencia, vigilado por G7.
#
# Primer patrón que casa, gana. El orden no es arbitrario: "TENDEDERO" antes
# que "TERRAZA", y los dormitorios antes que nada, porque un rótulo como
# "DORMITORIO 1 (con baño)" es un dormitorio y no un baño.

CLASIFICACION: Tuple[Tuple[str, str], ...] = (
    ("TENDEDERO", "tendedero"),
    ("TERRAZA", "terraza"),
    ("DORMITORIO", "dormitorio"),
    ("ASEO", "aseo"),
    ("BANO", "bano"),
    ("COCINA", "cocina"),
    ("SALON", "salon"),
    ("PASILLO", "circulacion"),
    ("VESTIBULO", "circulacion"),
    ("DISTRIBUIDOR", "circulacion"),
    ("RECIBIDOR", "circulacion"),
    ("TRASTERO", "trastero"),
    ("GARAJE", "garaje"),
    ("PORTAL", "zona_comun"),
)

TIPO_NO_ROTULADO = "SPACE_TYPE_UNLABELLED"
TIPO_NO_RECONOCIDO = "SPACE_TYPE_UNRECOGNISED"
PLANTA_NO_OBSERVABLE = "FLOOR_NOT_OBSERVABLE"
COTA_NO_OBSERVABLE = "LEVEL_NOT_OBSERVABLE"
ALTURA_NO_OBSERVABLE = "CLEAR_HEIGHT_NOT_OBSERVABLE"
USO_NO_DECLARADO = "USE_NOT_DECLARED"
NORTE_NO_DECLARADO = "NORTH_NOT_DECLARED"
TIPOLOGIA_NO_DECLARADA = "TYPOLOGY_NOT_DECLARED"
CIUDAD_NO_DECLARADA = "CITY_NOT_DECLARED"


def _normalizar(texto: str) -> str:
    """Mayúsculas y sin acentos. Misma convención que `evaluator._normalize` y
    `superficie_util._normalizar`, reimplementada aquí para que `modelo/` no
    herede el ciclo de vida del evaluador — igual que ya decidió CAP-1."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return sin_tildes.upper().strip()


def clasificar(rotulo: Optional[str]) -> Tuple[Atributo, Tuple[str, ...]]:
    """(tipo con origen, tipos que también casaban).

    Un espacio sin rótulo no se cae del análisis en silencio: sale
    `UNKNOWN` con motivo, que es lo que el `UNCERTAINTY_MODEL` puede convertir
    en un desconocido visible. Hoy `evaluator.py` clasifica por expresión
    regular y un polígono sin rótulo entra en el motor sin tipo, y las reglas
    sencillamente no le aplican, sin que nadie se entere.

    La segunda mitad del resultado es lo que no existe en ninguna parte hoy:
    si un rótulo casa con dos tipos ("SALÓN-COCINA"), eso es una ambigüedad
    real del plano y el modelo la registra en vez de quedarse con el primero
    y callarse.
    """
    if not rotulo or not rotulo.strip():
        return desconocido(
            TIPO_NO_ROTULADO,
            "El recinto no tiene rotulo dentro: no se puede decir que es.",
        ), ()
    texto = _normalizar(rotulo)
    casan = [tipo for patron, tipo in CLASIFICACION if patron in texto]
    if not casan:
        return desconocido(
            TIPO_NO_RECONOCIDO,
            "El rotulo %r no casa con ningun tipo del catalogo." % rotulo,
        ), ()
    confianza = MEDIA if len(casan) == 1 else BAJA
    return Atributo(valor=casan[0], estado="KNOWN", origen=OBSERVADO,
                    confianza=confianza,
                    fuente="rotulo del plano"), tuple(casan[1:])


# --- Presencia (§0.4) -------------------------------------------------------


def _presencia(etiquetas_observadas: bool) -> dict:
    """El mapa completo de los once tipos. Ninguno puede faltar (I6).

    Es la parte del modelo que dice lo que NO se sabe, y por eso se escribe
    entera aunque nueve de las once entradas digan lo mismo desde hace meses.
    """
    return {
        "proyecto": PRESENCIA_OBSERVADO,
        "espacio": PRESENCIA_OBSERVADO,
        "unidad": PRESENCIA_OBSERVADO if etiquetas_observadas else PRESENCIA_INFERIDO,
        # Un edificio por fichero: es una suposición que hasta ahora no estaba
        # escrita en ninguna parte. Escribirla como estado ya es una mejora.
        "edificio": PRESENCIA_INFERIDO,
        # Un DXF de distribución no dice qué planta es. CAP-4 lo resolvió
        # preguntando; aquí se declara que no se observa.
        "planta": PRESENCIA_NO_OBSERVABLE,
        "parcela": PRESENCIA_NO_OBSERVABLE,
        # Inferible del hueco entre polígonos (0,03–0,38 m medidos), y
        # deliberadamente NO materializado en E1 (decisión 2).
        "muro": PRESENCIA_NO_OBSERVABLE,
        "hueco": PRESENCIA_NO_OBSERVABLE,
        "pilar": PRESENCIA_NO_OBSERVABLE,
        "instalacion": PRESENCIA_NO_OBSERVABLE,
        "zona_comun": PRESENCIA_NO_OBSERVABLE,
    }


# --- Construcción -----------------------------------------------------------


def _atributo_declarado(valor, motivo_codigo: str, motivo_texto: str) -> Atributo:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return desconocido(motivo_codigo, motivo_texto)
    return declarado(valor)


def _escala_de(plano) -> Atributo:
    deteccion = getattr(plano, "escala", None)
    factor = getattr(deteccion, "factor", None)
    if factor is None:
        return desconocido("SCALE_UNKNOWN", "La escala del plano no se ha determinado.")
    origen = getattr(deteccion, "origen", "")
    # `declarada`/`confirmada` = lo dijo el arquitecto; el resto lo dedujo
    # `escala.py` cruzando $INSUNITS con el tamaño de las estancias.
    if origen == "confirmada":
        return declarado(float(factor), fuente="escala confirmada por el arquitecto")
    return derivado(float(factor), confianza=ALTA,
                    fuente="deteccion de escala (%s)" % (origen or "?"))


def ensamblar(
    unidades_entrada: Sequence[Tuple[str, Sequence, bool]],
    *,
    semilla: Optional[str] = None,
    criterio: Criterio = CRITERIO_ACTUAL,
    escala: Optional[Atributo] = None,
    procedencia: Optional[Procedencia] = None,
    etiquetas_observadas: bool = True,
    tipologia: Optional[str] = None,
    ciudad: Optional[str] = None,
    norte_grados: Optional[float] = None,
) -> Grafo:
    """Fases 1, 2, 3, 5 y 6 sobre una lista de `(nombre, rooms, observada)`.

    Recibe la agrupación ya hecha para que el mismo código sirva al plano
    completo y a una sola vivienda (que es lo que necesita `compat.py` para
    alimentar `circulation.py` sin cambiar la forma de sus datos).
    """
    if criterio.tolerancia_muro_m is None:
        # El número vive en un solo sitio del repositorio. Aquí se lee, no se
        # copia: si mañana cambia allí, el modelo cambia con él — y por eso la
        # mutación K1 del canario sigue siendo detectable a través del modelo.
        criterio = criterio.con_tolerancia(adyacencia.WALL_GAP_TOLERANCE_M)

    identidades = Identidades(semilla=semilla)
    almacen = AlmacenGeometria()
    proc = procedencia or Procedencia()

    proyecto_id = identidades.instancia("pr", ancho=2)
    edificio_id = identidades.instancia("ed", ancho=2)
    planta_id = identidades.instancia("pl", ancho=2)

    espacios: List[Espacio] = []
    unidades: List[Unidad] = []
    aristas: List[Arista] = []
    geometria_de: dict = {}   # espacio_id -> geom_id, para la fase 5

    for nombre, rooms, observada in unidades_entrada:
        unidad_id = identidades.instancia("un")
        ids_unidad: List[str] = []

        # Fases 1 y 2 — espacios y clasificación.
        for room in rooms:
            espacio_id = identidades.instancia("es")
            tipo, ambiguos = clasificar(getattr(room, "label", None))
            geom_id = almacen.insertar(room.polygon, HUELLA_2D, unidad="m")
            espacios.append(Espacio(
                id=espacio_id,
                concepto=identidades.concepto(espacio_id),
                unidad_id=unidad_id,
                planta_id=planta_id,
                rotulo=getattr(room, "label", None),
                tipo=tipo,
                geometrias={HUELLA_2D: geom_id},
                procedencia=Procedencia(
                    formato=proc.formato, fichero=proc.fichero,
                    capa=getattr(room, "layer", None), id_nativo=None),
                tipos_ambiguos=ambiguos,
            ))
            geometria_de[espacio_id] = geom_id
            ids_unidad.append(espacio_id)

        unidades.append(Unidad(
            id=unidad_id,
            concepto=identidades.concepto(unidad_id),
            planta_id=planta_id,
            etiqueta=(observado(nombre, confianza=ALTA, fuente="rotulo VT del plano")
                      if observada else
                      derivado(nombre, confianza=BAJA,
                               fuente="agrupacion por proximidad")),
            # El uso de la unidad no se infiere del rótulo VT: ese número es el
            # tipo de vivienda de la convención de rotulado de un despacho, sin
            # relación semántica garantizada. Es la misma prohibición que CAP-4
            # impuso para la planta.
            uso=desconocido(USO_NO_DECLARADO,
                            "El uso de la unidad no consta ni declarado ni observado."),
            espacios=tuple(ids_unidad),
        ))

        # Fase 5 — topología. Mismo doble bucle `i<j` que `adyacencia.py`, a
        # propósito: los recorridos con empate dependen del orden de la lista
        # de vecinos, y sin esto la migración mediría el desempate en vez de
        # la arquitectura.
        for i in range(len(ids_unidad)):
            for j in range(i + 1, len(ids_unidad)):
                a_id, b_id = ids_unidad[i], ids_unidad[j]
                ga, gb = geometria_de[a_id], geometria_de[b_id]
                separacion = distancia_m(almacen, ga, gb)
                if separacion > criterio.tolerancia_muro_m:
                    continue
                tramo = tramo_enfrentado_m(almacen, ga, gb, criterio.tolerancia_muro_m)
                distancia = distancia_centroides_m(almacen, ga, gb)
                if tramo >= criterio.tramo_minimo_contiguidad_m:
                    aristas.append(Arista(
                        tipo=ES_CONTIGUO_A, a=a_id, b=b_id, origen=OBSERVADO,
                        separacion_m=separacion, tramo_m=tramo, distancia_m=distancia))
                if tramo >= criterio.tramo_minimo_conexion_m:
                    # SUPUESTO, no observado: sin datos de puertas, tratar la
                    # contiguidad como paso es una hipotesis, y aqui queda
                    # escrita en la arista en vez de en un comentario.
                    aristas.append(Arista(
                        tipo=CONECTA_CON, a=a_id, b=b_id, origen=SUPUESTO,
                        separacion_m=separacion, tramo_m=tramo, distancia_m=distancia))

    planta = Planta(
        id=planta_id,
        concepto=identidades.concepto(planta_id),
        edificio_id=edificio_id,
        numero=desconocido(PLANTA_NO_OBSERVABLE,
                           "Un DXF de distribucion no dice que planta es. "
                           "CAP-4 la resuelve preguntando, no adivinando."),
        cota_base_m=desconocido(COTA_NO_OBSERVABLE,
                                "La cota de la planta no es observable en este origen."),
        altura_libre_m=desconocido(ALTURA_NO_OBSERVABLE,
                                   "La altura libre no es observable en este origen."),
        unidades=tuple(u.id for u in unidades),
    )
    edificio = Edificio(id=edificio_id,
                        concepto=identidades.concepto(edificio_id),
                        plantas=(planta_id,))
    proyecto = Proyecto(
        id=proyecto_id,
        concepto=identidades.concepto(proyecto_id),
        escala=escala or desconocido("SCALE_UNKNOWN", "Escala no determinada."),
        norte_grados=_atributo_declarado(
            norte_grados, NORTE_NO_DECLARADO, "El norte no se ha declarado."),
        tipologia=_atributo_declarado(
            tipologia, TIPOLOGIA_NO_DECLARADA, "La tipologia no se ha declarado."),
        ciudad=_atributo_declarado(
            ciudad, CIUDAD_NO_DECLARADA, "La ciudad no se ha declarado."),
        procedencia=proc,
        presencia=_presencia(etiquetas_observadas),
        edificios=(edificio_id,),
    )

    grafo = Grafo(proyecto=proyecto, edificios=[edificio], plantas=[planta],
                  unidades=unidades, espacios=espacios, aristas=aristas,
                  almacen=almacen, criterio=criterio)

    # Fase 6 — sellado y validación.
    exigir_invariantes(grafo)
    return grafo.sellar(sellado_de(grafo))


def construir(
    plano,
    *,
    semilla: Optional[str] = None,
    criterio: Criterio = CRITERIO_ACTUAL,
    fichero: str = "",
    tipologia: Optional[str] = None,
    ciudad: Optional[str] = None,
    norte_grados: Optional[float] = None,
) -> Grafo:
    """`PlanoLeido` -> versión sellada del modelo.

    Fase 0 (admisión) ya la ha hecho `leer_plano`: si la escala no era
    determinable o la capa no era identificable, allí se lanzó
    `EscalaIndeterminada` o `CapaIndeterminada` en vez de suponer. Ese es el
    precedente de todo este modelo — la única parte del sistema que ya
    prefería no responder a responder mal.
    """
    if not isinstance(plano, parser.PlanoLeido):
        raise TypeError("construir() espera un PlanoLeido, no %r" % type(plano).__name__)

    unidades_parser = evaluator.group_rooms_by_unit_label(plano.rooms, plano.unit_labels)
    observadas = bool(plano.unit_labels)
    return ensamblar(
        [(u.name, u.rooms, observadas) for u in unidades_parser],
        semilla=semilla,
        criterio=criterio,
        escala=_escala_de(plano),
        procedencia=Procedencia(formato="dxf", fichero=fichero, capa=plano.layer),
        etiquetas_observadas=observadas,
        tipologia=tipologia,
        ciudad=ciudad,
        norte_grados=norte_grados,
    )


def construir_de_unidad(unidad, *, semilla: Optional[str] = None,
                        criterio: Criterio = CRITERIO_ACTUAL) -> Grafo:
    """Modelo de una sola vivienda, a partir de un `evaluator.Unit`.

    Es lo que necesita `compat.py` para alimentar a `circulation.py` sin
    cambiar la forma de sus datos ni el ámbito en el que razona. No es un
    atajo: `circulation` ya razona por vivienda, y construir el plano entero
    para responderle sería trabajo tirado.
    """
    return ensamblar([(unidad.name, unidad.rooms, True)],
                     semilla=semilla, criterio=criterio,
                     procedencia=Procedencia(formato="dxf"),
                     escala=derivado(1.0, confianza=ALTA,
                                     fuente="geometria ya en metros (leer_plano)"))
