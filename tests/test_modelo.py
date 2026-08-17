# -*- coding: utf-8 -*-
"""Contrato del modelo común (C1–C7), sobre geometría sintética.

Ejecutar:  python tests/test_modelo.py

Rápido y sin DXF a propósito: lo que se comprueba aquí son las reglas que el
modelo hace cumplir **por construcción**, y ésas se prueban mejor con casos
fabricados a medida que con un plano real. La equivalencia con producción va
en `tests/test_modelo_compat.py` y en los goldens.

Un bloque por paso de E1:

    B. E1.2  identidad          F. E1.7  API del grafo
    C. E1.3  atributo           G. E1.8  invariantes
    D. E1.4  geometria          H. E1.9  serializacion
    E. E1.6  aristas            I. E1.10 constructor
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from shapely.geometry import Polygon  # noqa: E402

from analyzer import hechos  # noqa: E402
from modelo import aristas as mod_aristas  # noqa: E402
from modelo import atributo as mod_atributo  # noqa: E402
from modelo import constructor, invariantes, serializacion  # noqa: E402
from modelo.geometria import (  # noqa: E402
    AlmacenGeometria, HUELLA_2D, UnidadNoAdmitida,
)
from modelo.identidad import Identidades, emparejar  # noqa: E402

fallos = []
comprobaciones = 0


def check(condicion, titulo, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s" % ("OK  " if condicion else "FALLO", titulo))
    if detalle:
        print("         %s" % detalle)
    if not condicion:
        fallos.append(titulo)


def rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


class RoomFalsa:
    """Lo mínimo que el constructor mira de un recinto: rótulo, polígono, capa."""

    def __init__(self, label, polygon, layer="00 areas"):
        self.label, self.polygon, self.layer = label, polygon, layer


class UnidadFalsa:
    def __init__(self, name, rooms):
        self.name, self.rooms = name, rooms


# ---------------------------------------------------------------------------
print("B. E1.2 — identidad en dos niveles")
# ---------------------------------------------------------------------------

ids_a = Identidades(semilla="s")
ids_b = Identidades(semilla="s")
check([ids_a.instancia("es") for _ in range(3)] == ["es-0001", "es-0002", "es-0003"],
      "instance_id determinista y con formato estable")
check(ids_a.concepto("es-0001") == ids_b.concepto("es-0001"),
      "con la misma semilla, dos construcciones dan el mismo concept_id")
check(Identidades(semilla="otra").concepto("es-0001") != ids_a.concepto("es-0001"),
      "semillas distintas dan concept_id distintos")
check(ids_a.concepto("es-0002") == ids_a.concepto("es-0002"),
      "concepto() es idempotente dentro de una version")
concepto = ids_a.concepto("es-0001")
check(len(concepto) == 12 and all(c in "0123456789abcdef" for c in concepto),
      "concept_id opaco: 12 hex, sin rastro del valor del nodo", concepto)
check(Identidades().concepto("es-0001") != Identidades().concepto("es-0001"),
      "sin semilla, uuid4: cada proyecto nace una vez")
try:
    emparejar(None, None)
    check(False, "emparejar() debe negarse mientras no este decidido")
except NotImplementedError as exc:
    check("E2" in str(exc), "emparejar() lanza NotImplementedError citando E2")

# ---------------------------------------------------------------------------
print("\nC. E1.3 — Atributo: un solo vocabulario de incertidumbre")
# ---------------------------------------------------------------------------

check(mod_atributo.KNOWN is hechos.KNOWN and mod_atributo.ESTADOS is hechos.ESTADOS,
      "los estados son LOS de hechos.py, no una copia")
check(mod_atributo.Motivo is hechos.Motivo, "el Motivo es el de hechos.py")

for titulo, kwargs in (
    ("valor sin origen", dict(valor=3.0, estado=hechos.KNOWN)),
    ("KNOWN sin valor", dict(valor=None, estado=hechos.KNOWN, origen="observado")),
    ("UNKNOWN con valor", dict(valor=1, estado=hechos.UNKNOWN)),
    ("UNKNOWN sin motivo", dict(valor=None, estado=hechos.UNKNOWN)),
    ("estado inventado", dict(valor=1, estado="MAS_O_MENOS", origen="observado")),
    ("origen inventado", dict(valor=1, estado=hechos.KNOWN, origen="intuicion")),
):
    try:
        mod_atributo.Atributo(**kwargs)
        check(False, "Atributo rechaza: %s" % titulo)
    except ValueError:
        check(True, "Atributo rechaza: %s" % titulo)

a = mod_atributo.observado(12.5, confianza=hechos.ALTA, fuente="rotulo")
check(a.conocido and a.resuelto, "observado() produce KNOWN resuelto")
check(mod_atributo.supuesto(2.5).estado == hechos.ESTIMATED,
      "supuesto() es ESTIMATED, nunca KNOWN")
d = mod_atributo.desconocido("X", "no consta")
check(d.estado == hechos.UNKNOWN and d.valor is None and d.motivos,
      "desconocido() lleva motivo obligatorio y no publica valor")

h = a.a_hecho("superficie", "vivienda VT1/3", unidad="m2")
check(isinstance(h, hechos.Hecho) and h.estado == hechos.KNOWN and h.valor == 12.5,
      "a_hecho() es el unico puente y produce un Hecho valido")
h2 = mod_atributo.supuesto(2.5).a_hecho("altura", "planta", unidad="m")
check(h2.tipo == "derivado" and h2.estado == hechos.ESTIMATED,
      "un supuesto se publica como derivado+ESTIMATED (hechos.py no tiene 'supuesto')")
h3 = d.a_hecho("planta", "edificio")
check(h3.estado == hechos.UNKNOWN and h3.motivos, "un UNKNOWN cruza el puente con su motivo")

# ---------------------------------------------------------------------------
print("\nD. E1.4 — geometria por referencia y en metros")
# ---------------------------------------------------------------------------

almacen = AlmacenGeometria()
gid = almacen.insertar(rect(0, 0, 4, 2), HUELLA_2D, unidad="m")
check(gid == "g-0001" and gid in almacen, "insertar() devuelve un geom_id referenciable")
try:
    almacen.insertar(rect(0, 0, 1, 1), HUELLA_2D, unidad="mm")
    check(False, "el almacen rechaza geometria que no este en metros")
except UnidadNoAdmitida:
    check(True, "el almacen rechaza geometria que no este en metros")
try:
    almacen.insertar(rect(0, 0, 1, 1), "sombreado")
    check(False, "el almacen rechaza representaciones fuera del vocabulario")
except ValueError:
    check(True, "el almacen rechaza representaciones fuera del vocabulario")

check(abs(almacen.area_m2(gid) - 8.0) < 1e-9, "area derivada correcta")
check(abs(almacen.perimetro_m(gid) - 12.0) < 1e-9, "perimetro derivado correcto")
check(abs(almacen.alargamiento(gid) - 2.0) < 1e-9, "alargamiento = lado mayor / lado menor")
check(abs(almacen.lado_mayor_m(gid) - 4.0) < 1e-9 and abs(almacen.lado_menor_m(gid) - 2.0) < 1e-9,
      "lados del rectangulo envolvente minimo")
derivados = almacen.derivados(gid)
check(all(isinstance(v, (int, float)) or isinstance(v, list) for v in derivados.values()),
      "derivados() devuelve solo numeros: ni una conclusion")
check(all(round(v, 3) == v for v in derivados.values() if isinstance(v, float)),
      "derivados ya redondeados a 3 decimales")

# ---------------------------------------------------------------------------
print("\nE. E1.6 — aristas: dos tipos, y el criterio en un solo sitio")
# ---------------------------------------------------------------------------

check(mod_aristas.TIPOS == ("es_contiguo_a", "conecta_con"), "solo dos tipos de arista")
for titulo, kwargs in (
    ("tipo inventado", dict(tipo="toca_con", a="es-1", b="es-2", origen="observado")),
    ("origen no admitido", dict(tipo="conecta_con", a="es-1", b="es-2", origen="declarado")),
    ("bucle sobre si mismo", dict(tipo="conecta_con", a="es-1", b="es-1", origen="observado")),
):
    try:
        mod_aristas.Arista(**kwargs)
        check(False, "Arista rechaza: %s" % titulo)
    except ValueError:
        check(True, "Arista rechaza: %s" % titulo)

check(mod_aristas.CRITERIO_ACTUAL.tolerancia_muro_m is None,
      "el criterio NO trae una copia del umbral: lo rellena el constructor")
check(mod_aristas.CRITERIO_ACTUAL.tramo_minimo_contiguidad_m == 0.0
      and mod_aristas.CRITERIO_ACTUAL.tramo_minimo_conexion_m == 0.0,
      "tramo_m se mide y NO filtra (decision 3, umbral abierto)")

# ---------------------------------------------------------------------------
print("\nF/I. E1.7 y E1.10 — constructor y API del grafo, sobre un caso a medida")
# ---------------------------------------------------------------------------

# Tres piezas en fila: A|B|C, con 0,10 m de separacion (un tabique plausible).
piezas = [
    RoomFalsa("Salón/cocina", rect(0.0, 0.0, 4.0, 3.0)),
    RoomFalsa("Pasillo", rect(4.1, 0.0, 5.1, 3.0)),
    RoomFalsa("Dormitorio 1", rect(5.2, 0.0, 9.2, 3.0)),
    RoomFalsa(None, rect(20.0, 20.0, 22.0, 22.0)),   # lejos y sin rotulo
]
modelo = constructor.ensamblar([("VTX", piezas, True)], semilla="t")

espacios = modelo.get_spaces()
check(len(espacios) == 4 and [e.id for e in espacios] ==
      ["es-0001", "es-0002", "es-0003", "es-0004"],
      "un espacio por recinto, en orden de lectura")
check(espacios[1].tipo.valor == "circulacion",
      "clasificacion por rotulo, con el vocabulario de SPACE_TAXONOMY")
# "Salón/cocina" casa con DOS tipos. El modelo se queda con el primero del
# catalogo y **registra el otro**: es la ambiguedad real de un plano que hoy
# nadie recoge — `evaluator.py` reconoce `SALON|COCINA` como un solo patron
# con un solo umbral, asi que dos tipos distintos se evaluan como uno.
check(espacios[0].tipo.valor == "cocina" and espacios[0].tipos_ambiguos == ("salon",),
      "un rotulo ambiguo se resuelve por orden y la alternativa queda registrada",
      "%r -> %s + %s" % (espacios[0].rotulo, espacios[0].tipo.valor,
                         espacios[0].tipos_ambiguos))
check(espacios[0].tipo.confianza == hechos.BAJA,
      "un tipo ambiguo baja la confianza; uno inequivoco no")
check(espacios[1].tipo.confianza == hechos.MEDIA,
      "un tipo inequivoco se queda en confianza Media (viene de un rotulo)")
check(espacios[3].tipo.estado == hechos.UNKNOWN,
      "un recinto sin rotulo sale UNKNOWN, no se cae del analisis en silencio")
check(espacios[0].tipo.origen == "observado", "el tipo lleva su origen pegado")

salon, pasillo, dormitorio, suelto = espacios
check([e.id for e in modelo.connected_spaces(pasillo)] == ["es-0001", "es-0003"],
      "el pasillo conecta con los dos vecinos")
check(modelo.connected_spaces(suelto) == [], "el recinto lejano no conecta con nadie")
camino = modelo.camino(salon, dormitorio)
check(camino is not None and [e.id for e in camino] == ["es-0001", "es-0002", "es-0003"],
      "camino() cruza el pasillo")
check(modelo.camino(salon, suelto) is None, "camino() devuelve None si no hay ruta")
_c, distancia = modelo.camino_mas_corto(salon, dormitorio)
# Centroides en x = 2,0 / 4,6 / 7,2: dos tramos de 2,6 m. Es distancia entre
# centroides, no recorrido andado — el mismo peso que usa `adyacencia.py`.
check(abs(distancia - 5.2) < 0.01, "camino_mas_corto() suma distancias reales",
      "%.3f m" % distancia)
check(len(modelo.aristas("conecta_con")) == 2 and len(modelo.aristas("es_contiguo_a")) == 2,
      "en E1 las dos relaciones coinciden: el umbral de contiguidad sigue abierto")
check(modelo.aristas("conecta_con")[0].origen == "supuesto",
      "conecta_con es SUPUESTO: sin puertas, el paso es una hipotesis")
check(modelo.aristas("es_contiguo_a")[0].origen == "observado",
      "es_contiguo_a es observado: la separacion fisica si se mide")

vista = modelo.unidad("un-0001")
check(len(vista.get_spaces()) == 4 and vista.nombre == "VTX", "VistaUnidad acota a la vivienda")
check(modelo.presencia("muro") == "no_observable",
      "muro declarado no observable: no se materializa en E1")
check(modelo.presencia("planta") == "no_observable", "planta declarada no observable")
check(any("tipo desconocido" in d for d in modelo.desconocidos()),
      "desconocidos() enumera lo que no se sabe")
check(modelo.criterio.tolerancia_muro_m == 0.5,
      "el constructor toma el umbral de adyacencia.py, sin copiarlo")

# ---------------------------------------------------------------------------
print("\nG. E1.8 — invariantes")
# ---------------------------------------------------------------------------

check(invariantes.comprobar_invariantes(modelo) == [],
      "un modelo bien construido no incumple ninguno")

import dataclasses  # noqa: E402

roto = dataclasses.replace(modelo.get_space("es-0001"), unidad_id="un-9999")
modelo._espacios["es-0001"] = roto
fallos_i1 = invariantes.comprobar_invariantes(modelo)
check(any(f.startswith("I1") for f in fallos_i1), "I1 detecta un espacio sin unidad valida",
      fallos_i1[0] if fallos_i1 else "")
modelo._espacios["es-0001"] = salon  # se deshace

sin_presencia = dataclasses.replace(
    modelo.proyecto, presencia={k: v for k, v in modelo.proyecto.presencia.items()
                                if k != "hueco"})
copia = modelo
copia.proyecto = sin_presencia
fallos_i6 = invariantes.comprobar_invariantes(copia)
check(any(f.startswith("I6") for f in fallos_i6),
      "I6 detecta que falta la presencia declarada de un tipo del catalogo")
copia.proyecto = dataclasses.replace(sin_presencia,
                                     presencia=dict(sin_presencia.presencia, hueco="no_observable"))
check(invariantes.comprobar_invariantes(copia) == [], "restaurado, vuelve a ser valido")

try:
    invariantes.exigir_invariantes(
        dataclasses.replace(modelo, ) if False else copia)
    check(True, "exigir_invariantes() no levanta sobre un modelo valido")
except invariantes.ModeloInvalido:
    check(False, "exigir_invariantes() no levanta sobre un modelo valido")

# ---------------------------------------------------------------------------
print("\nH. E1.9 — serializacion determinista")
# ---------------------------------------------------------------------------

texto = serializacion.volcar(modelo)
check(texto.endswith("\n") and "\r" not in texto, "JSON con salto final y sin CRLF")
recargado = serializacion.cargar(texto)
check(serializacion.volcar(recargado) == texto, "round-trip byte a byte")
check(recargado.sellado == modelo.sellado, "el sellado sobrevive al round-trip")
check(serializacion.verificar_sellado(recargado), "el sellado describe el contenido (I8)")

otro = constructor.ensamblar([("VTX", piezas, True)], semilla="t")
check(serializacion.volcar(otro) == texto, "mismo input + misma semilla -> mismo JSON")
distinto = constructor.ensamblar([("VTX", piezas, True)], semilla="u")
check(serializacion.volcar(distinto) != texto, "otra semilla -> otros concept_id")

try:
    serializacion.canonico({"x": {1, 2}})
    check(False, "la serializacion rechaza conjuntos (orden no estable)")
except TypeError:
    check(True, "la serializacion rechaza conjuntos (orden no estable)")

try:
    modelo.sellar("otra-cosa")
    check(False, "una version sellada no se vuelve a sellar (I8)")
except Exception:
    check(True, "una version sellada no se vuelve a sellar (I8)")

print()
print("=" * 64)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
