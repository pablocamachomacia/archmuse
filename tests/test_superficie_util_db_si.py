# -*- coding: utf-8 -*-
"""CAP-1: superficie_util_db_si mide lo que el DB-SI define, o dice que no puede.

Ejecutar:  python tests/test_superficie_util_db_si.py

Rapido (<3 s): geometria sintetica + ejemplo.dxf si esta disponible.

Que protege:

1. Que la magnitud sea UNION geometrica, no suma. El doble conteo medido en
   VT5/1 (12,43 m2) y VT6/2 (27,32 m2) no puede repetirse aqui.
2. Que un problema geometrico NO se tape con una cifra. Un area plausible
   calculada sobre poligonos solapados es indistinguible de una correcta.
3. Que terraza y tendedero COMPUTEN. El DB-SI no excluye ningun recinto de la
   superficie util, asi que excluirlos por el rotulo -como hace el criterio
   antiguo- no tiene respaldo (docs/design/DB-SI_DECISIONS.md D6).
4. Que todo UNKNOWN lleve motivo estructurado, no un None.
5. Que las reglas antiguas (R03/R07/R14) sigan intactas: CAP-1 anade, no toca.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from shapely.geometry import Polygon  # noqa: E402

from analyzer.evaluator import Unit, group_rooms_by_unit_label  # noqa: E402
from analyzer.hechos import KNOWN, MEDIA, UNKNOWN  # noqa: E402
from analyzer.parser import Room  # noqa: E402
from analyzer.superficie_util import (  # noqa: E402
    AMBIGUO,
    GEOMETRIA_AUSENTE,
    GEOMETRIA_INVALIDA,
    OCUPABLE,
    OCUPACION_NULA,
    RECINTO_AMBIGUO,
    SIN_RECINTOS,
    SOLAPE_NO_RESUELTO,
    clasificar_recinto,
    superficie_util_db_si,
)

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


def rect(x0, y0, ancho, alto, etiqueta):
    return Room(label=etiqueta, layer="00 areas",
                polygon=Polygon([(x0, y0), (x0 + ancho, y0),
                                 (x0 + ancho, y0 + alto), (x0, y0 + alto)]))


def codigos(hecho):
    return [m.codigo for m in hecho.motivos]


print("A. Caso 1 - geometrias sin solape: KNOWN")

limpia = Unit(name="limpia", rooms=[
    rect(0, 0, 4, 5, "Salon"), rect(5, 0, 3, 4, "Dormitorio 1"),
    rect(9, 0, 2, 2, "Bano")])
h = superficie_util_db_si(limpia)
check(h.estado == KNOWN, "estado KNOWN", h.estado)
check(abs(h.valor - 36.0) < 1e-9, "area = union de 20+12+4", repr(h.valor))
check(h.confianza == MEDIA, "confianza Media (se clasifica por rotulo)", str(h.confianza))
check(h.referencia_normativa == "es.cte.db_si.anejo_a.superficie_util",
      "cita la definicion por concept_id", h.referencia_normativa)
check(len(h.procedencia) == 3, "la procedencia lista los 3 recintos",
      " | ".join(h.procedencia))

print("\nB. Caso 2 - geometrias solapadas: UNKNOWN, no la union")

solapada = Unit(name="solapada", rooms=[
    rect(0, 0, 4, 5, "Salon"), rect(3, 0, 4, 5, "Dormitorio 1")])
h = superficie_util_db_si(solapada)
check(h.estado == UNKNOWN, "estado UNKNOWN", h.estado)
check(SOLAPE_NO_RESUELTO in codigos(h), "motivo GEOMETRY_OVERLAP_UNRESOLVED",
      str(codigos(h)))
check(h.valor is None, "NO publica valor pese a poder calcular la union",
      "la union serian 35.0 m2, y se guarda solo como diagnostico")
check(abs(h.diagnostico["area_union_m2"] - 35.0) < 1e-9,
      "pero conserva la union en diagnostico para el humano",
      repr(h.diagnostico["area_union_m2"]))
check(abs(h.diagnostico["area_suma_m2"] - 40.0) < 1e-9,
      "y la suma, que es lo que el metodo antiguo habria dado",
      "suma 40.0 vs union 35.0: 5 m2 de doble conteo")

print("\nC. Caso 3 - un recinto contenido dentro de otro")

contenida = Unit(name="contenida", rooms=[
    rect(0, 0, 10, 10, "Salon"), rect(2, 2, 3, 3, "Dormitorio 1")])
h = superficie_util_db_si(contenida)
check(h.estado == UNKNOWN, "estado UNKNOWN", h.estado)
check(SOLAPE_NO_RESUELTO in codigos(h),
      "se detecta como solape (es la firma del contorno agrupador)")
check("comparten 9.00 m2" in h.motivos[0].detalle,
      "y el motivo dice cuantos m2 comparten", h.motivos[0].detalle[:90])

print("\nD. Casos 4 y 5 - terraza y tendedero COMPUTAN (DB-SI_DECISIONS.md D6)")

check(clasificar_recinto("Terraza") == OCUPABLE,
      "«Terraza» COMPUTA como superficie util",
      "DB-SI no excluye ningun recinto de la superficie util (D6)")
check(clasificar_recinto("Tendedero") == OCUPABLE, "«Tendedero» tambien computa")
check(clasificar_recinto("Trastero") == OCUPACION_NULA,
      "«Trastero» se aparta: Anejo SI A, zona de ocupacion nula",
      "sigue siendo superficie util; se marca para que CAP-3 lo descuente")
check(clasificar_recinto("Salon") == OCUPABLE and clasificar_recinto("Bano") == OCUPABLE,
      "salon y bano computan")
check(clasificar_recinto("Vestidor") == OCUPABLE,
      "un rotulo no previsto tambien computa: la definicion es inclusiva")
check(clasificar_recinto(None) == AMBIGUO,
      "pero un recinto SIN ROTULO es AMBIGUO",
      "ahi la duda no es si es ocupable, sino si es un recinto")

con_terraza = Unit(name="con_terraza", rooms=[
    rect(0, 0, 4, 5, "Salon"), rect(5, 0, 3, 3, "Terraza")])
h = superficie_util_db_si(con_terraza)
check(h.estado == KNOWN, "una vivienda con terraza es KNOWN", h.estado)
check(abs(h.valor - 29.0) < 1e-9, "y la terraza SUMA (20 + 9)", repr(h.valor))

con_tendedero = Unit(name="con_tendedero", rooms=[
    rect(0, 0, 4, 5, "Salon"), rect(5, 0, 2, 2, "Tendedero")])
h2 = superficie_util_db_si(con_tendedero)
check(h2.estado == KNOWN and abs(h2.valor - 24.0) < 1e-9,
      "lo mismo con tendedero (20 + 4)", repr(h2.valor))

sin_rotulo = Unit(name="sin_rotulo", rooms=[
    rect(0, 0, 4, 5, "Salon"), rect(9, 0, 3, 3, None)])
h3 = superficie_util_db_si(sin_rotulo)
check(h3.estado == UNKNOWN and RECINTO_AMBIGUO in codigos(h3),
      "pero un poligono SIN ROTULO sigue siendo AMBIGUO -> UNKNOWN",
      "podria ser el contorno agrupador de la vivienda")

print("\nE. Caso 6 - geometria invalida")

lazo = Polygon([(0, 0), (4, 4), (4, 0), (0, 4)])  # se cruza a si mismo
invalida = Unit(name="invalida", rooms=[
    Room(label="Salon", layer="00 areas", polygon=lazo),
    rect(6, 0, 3, 3, "Dormitorio 1")])
h = superficie_util_db_si(invalida)
check(h.estado == UNKNOWN, "estado UNKNOWN", h.estado)
check(GEOMETRIA_INVALIDA in codigos(h), "motivo GEOMETRY_INVALID", str(codigos(h)))

print("\nF. Caso 7 - geometria ausente o degenerada")

vacio = Unit(name="vacio", rooms=[
    Room(label="Salon", layer="00 areas", polygon=Polygon()),
    rect(6, 0, 3, 3, "Dormitorio 1")])
h = superficie_util_db_si(vacio)
check(h.estado == UNKNOWN and GEOMETRIA_AUSENTE in codigos(h),
      "poligono vacio -> GEOMETRY_MISSING", str(codigos(h)))

minusculo = Unit(name="minusculo", rooms=[
    rect(0, 0, 0.05, 0.05, "Salon"), rect(6, 0, 3, 3, "Dormitorio 1")])
check(GEOMETRIA_AUSENTE in codigos(superficie_util_db_si(minusculo)),
      "area por debajo del minimo -> GEOMETRY_MISSING",
      "0.0025 m2 no es un recinto")

print("\nG. Caso 8 - vivienda sin recintos validos")

h = superficie_util_db_si(Unit(name="sin_nada", rooms=[]))
check(h.estado == UNKNOWN and SIN_RECINTOS in codigos(h),
      "vivienda sin recintos -> NO_ROOMS", str(codigos(h)))
check(h.valor is None, "sin valor")

solo_anonimos = Unit(name="solo_anonimos", rooms=[
    rect(0, 0, 3, 3, None), rect(4, 0, 2, 2, "")])
h = superficie_util_db_si(solo_anonimos)
check(h.estado == UNKNOWN, "vivienda solo con poligonos anonimos -> UNKNOWN")

print("\nH. Casos 9 y 10 - el contrato del hecho se cumple siempre")

for nombre, u in [("limpia", limpia), ("solapada", solapada),
                  ("sin_rotulo", sin_rotulo), ("sin_nada", Unit("sin_nada", []))]:
    h = superficie_util_db_si(u)
    if h.estado == UNKNOWN:
        check(bool(h.motivos) and all(m.codigo and m.detalle for m in h.motivos),
              "«%s»: UNKNOWN con motivo estructurado (codigo + detalle)" % nombre,
              h.motivo_principal.codigo)
        check(h.valor is None, "«%s»: UNKNOWN no publica valor" % nombre)
    else:
        check(h.valor is not None and h.confianza is not None,
              "«%s»: KNOWN con valor y confianza" % nombre)
    check(h.explicacion != "", "«%s»: siempre hay explicacion legible" % nombre)

print("\nI. ejemplo.dxf - VT5/1 y VT6/2, donde ya medimos solapes")

DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")
if not os.path.exists(DXF):
    print("  [SALTA] no se encuentra %s" % DXF)
else:
    from analyzer import parser  # noqa: E402
    from analyzer.evaluator import (  # noqa: E402
        evaluate_circulation_efficiency, evaluate_unit_efficiency,
        evaluate_unit_minimum_area,
    )

    plano = parser.leer_plano(parser.load_document(DXF))
    unidades = group_rooms_by_unit_label(plano.rooms, plano.unit_labels)
    hechos = {u.name: superficie_util_db_si(u) for u in unidades}

    check(len(hechos) == 6, "6 viviendas", str(len(hechos)))

    # Desde la correccion de cierre geometrico de 2026-08-13
    # (analyzer/parser.py::_esta_cerrada, ver tests/test_cierre_recuperado.py):
    # el "Salon/cocina" real de VT5/1 -antes invisible por closed=False mal
    # puesto- aparece, y con el aparece tambien el "Baño" de esa vivienda;
    # `_discard_container_candidates` descarta solo el contorno duplicado
    # (52.13 m2) que antes se conservaba por no tener con que compararlo.
    # VT5/1 pasa a KNOWN, sin solape.
    #
    # VT6/2 sigue UNKNOWN, pero YA NO por el contorno duplicado de
    # "Salon/cocina" (58.58 m2, tambien descartado ahora): el "Dormitorio 2"
    # recuperado en esa vivienda es el geometricamente invalido en el DXF de
    # origen (autointerseccion), y ademas dos "Terraza" de esa misma vivienda
    # ya se solapaban entre si antes de esta correccion -- las dos causas
    # son independientes del cierre recuperado. Detalle completo en
    # docs/audits/2026-08-13-hallazgos-cierre-geometrico.md.
    h6 = hechos["VT6/2"]
    check(SOLAPE_NO_RESUELTO in codigos(h6),
          "VT6/2: se detecta el solape (Terraza/Terraza, no relacionado con "
          "el cierre recuperado)", str(codigos(h6)))
    check(h6.estado == UNKNOWN and h6.valor is None, "VT6/2: UNKNOWN, sin cifra")
    union = h6.diagnostico.get("area_union_m2")
    suma = h6.diagnostico.get("area_suma_m2")
    check(union is not None and suma is not None and suma - union > 1.0,
          "VT6/2: el doble conteo queda medido y visible",
          "suma %.2f - union %.2f = %.2f m2 contados dos veces"
          % (suma, union, suma - union))

    h5 = hechos["VT5/1"]
    check(h5.estado == KNOWN and h5.valor is not None,
          "VT5/1: ya no hay solape, KNOWN con cifra", "%r" % h5.valor)

    limpias = {n: h for n, h in hechos.items() if h.estado == KNOWN}
    check(len(limpias) == 5,
          "las 5 viviendas sin solape ahora SI son KNOWN",
          "; ".join("%s=%.2f m2" % (n, h.valor) for n, h in sorted(limpias.items())))
    check(hechos["VT6/2"].estado == UNKNOWN,
          "y solo VT6/2 queda UNKNOWN, por solape",
          "ya no por terraza excluida: la terraza computa")

    print("\nJ. Las reglas antiguas NO han cambiado")

    # Recalculados el 2026-08-13 tras la correccion de cierre geometrico
    # (ver bloque I arriba y tests/test_cierre_recuperado.py).
    R03 = {"VT1/3": "0.8862489408444045", "VT2/2": "0.8722520478815108",
           "VT3/3": "0.8880697613574597", "VT4/2": "0.8707562503816217",
           "VT5/1": "0.9058127313769088", "VT6/2": "0.6215614081192977"}
    for r in evaluate_unit_efficiency(unidades):
        check(repr(r.ratio) == R03[r.unit_name],
              "R03 %s intacta" % r.unit_name, repr(r.ratio))
    R07 = {"VT1/3": "58.7837267762472", "VT2/2": "50.976887332164566",
           "VT3/3": "59.099203268743615", "VT4/2": "50.91271677234972",
           "VT5/1": "41.04679458653981", "VT6/2": "46.22524551476647"}
    for u in unidades:
        check(repr(evaluate_unit_minimum_area(u, "plurifamiliar").useful_area_m2)
              == R07[u.name], "R07 %s intacta" % u.name)
    check(all(evaluate_circulation_efficiency(u) is None for u in unidades),
          "R14 sigue sin evaluarse en las 6 (no hay Pasillo)")

print("\n" + "=" * 60)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
