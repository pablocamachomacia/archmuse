# -*- coding: utf-8 -*-
"""Fase 2 — borrador de relleno del cuadro de superficies (`analyzer/cuadro_superficies.py`).

Ejecutar:  python tests/test_cuadro_superficies.py

Rapido salvo la seccion C (parsea `v2s.dxf`, ~unos segundos). No escribe
ningun DXF, no toca `evaluator.py` ni `parser.py`.

Que protege:

A. Caso sintetico sin ambiguedad -- cada familia con exactamente 0 o 1
   coincidencia hace lo que debe (CALCULADO / CERO_REAL), y los totales en
   cascada suman bien cuando no hay nada bloqueado.
B. Conservacion de una celda ya rellenada -- "VIVIENDA TIPO" no se
   sobrescribe si ya coincide, y se bloquea (no se pisa) si no coincide.
C. `v2s.dxf` real -- confirma exactamente el resultado que se pidio: 8
   campos CALCULADO, 2 CERO_REAL, 5 BLOQUEADO (tendedero + terraza 1/2 +
   los dos totales que dependen de ellos), 3 NO_DISPONIBLE, y que ningun
   campo bloqueado lleva un numero inventado.
D. `ejemplo.dxf` real -- bug encontrado en la Fase 4 y corregido aqui: su
   cuadro llega con 9 de las 18 celdas YA rellenadas (salon+cocina,
   tendedero, terraza 1, los tres dormitorios, bano, aseo y numero de
   unidades), en formatos que este modulo no genera ("21.90m2", "8.48"...).
   Antes de la correccion, `calcular_relleno_cuadro` las recalculaba y las
   habria sobrescrito -- solo "VIVIENDA TIPO" se protegia. Ahora la regla es
   general: cualquier celda con texto ya escrito se conserva tal cual, y los
   totales que dependen de una celda preexistente no sumable se bloquean en
   vez de fallar o inventar una conversion.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer.cuadro_superficies import (  # noqa: E402
    BLOQUEADO,
    CALCULADO,
    CERO_REAL,
    NO_DISPONIBLE,
    CeldaCuadro,
    CuadroSuperficies,
    calcular_relleno_cuadro,
    detectar_cuadro_superficies,
)

fallos = []
comprobaciones = 0


def check(ok, etiqueta, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s%s" % ("OK  " if ok else "FALLO", etiqueta, ("  -> " + detalle) if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


class RoomFalso:
    """Doble minimo de `parser.Room`: solo lo que este modulo lee (label, area_m2)."""
    def __init__(self, label, area_m2):
        self.label = label
        self.area_m2 = area_m2


class UnitFalso:
    def __init__(self, name, rooms):
        self.name = name
        self.rooms = rooms


def cuadro_completo(existentes=None):
    """Un `CuadroSuperficies` con las 18 celdas, ninguna con texto previo
    salvo las que se pasen en `existentes` ({campo: texto})."""
    existentes = existentes or {}
    campos_col = {
        "salon_cocina": "B", "pasillo": "B", "dormitorio_1": "B", "dormitorio_2": "B",
        "dormitorio_3": "B", "bano": "B", "aseo": "B", "vestibulo": "B",
        "total_util_interior": "B", "total_util": "B", "superficie_construida_cerrada": "B",
        "vivienda_tipo": "B",
        "tendedero": "D", "terraza_1": "D", "terraza_2": "D", "total_util_exterior": "D",
        "superficie_construida_exterior": "D", "numero_unidades": "D",
    }
    return CuadroSuperficies(celdas=[
        CeldaCuadro(campo=c, etiqueta=c, columna=col, x=0.0, y=float(i),
                    texto_actual=existentes.get(c))
        for i, (c, col) in enumerate(campos_col.items())
    ])


print()
print("A. Caso sintetico sin ambiguedad")
print("-" * 68)

rooms = [
    RoomFalso("Salón/cocina", 20.0),
    RoomFalso("Dormitorio 1", 10.0),
    RoomFalso("Dormitorio 2", 8.0),
    # Sin Dormitorio 3, sin baño, sin aseo, sin vestibulo, sin pasillo:
    # deben salir CERO_REAL, no un fallo.
    RoomFalso("Aseo", 3.0),
    RoomFalso("Tendedero", 4.0),
    RoomFalso("Terraza 1", 5.0),
    RoomFalso("Terraza 2", 6.0),
]
unit = UnitFalso("VT-TEST/1", rooms)
resultado = calcular_relleno_cuadro(unit, cuadro_completo(), rooms)
por_campo = {r.campo: r for r in resultado}

check(por_campo["salon_cocina"].estado == CALCULADO and por_campo["salon_cocina"].texto == "20,00 m²",
      "salon_cocina calculado", por_campo["salon_cocina"].texto)
check(por_campo["dormitorio_1"].texto == "10,00 m²", "dormitorio_1 calculado")
check(por_campo["dormitorio_2"].texto == "8,00 m²", "dormitorio_2 calculado")
check(por_campo["dormitorio_3"].estado == CERO_REAL and por_campo["dormitorio_3"].texto == "0,00 m²",
      "dormitorio_3 (no existe) -> CERO_REAL, no un fallo")
check(por_campo["bano"].estado == CERO_REAL, "bano (no existe) -> CERO_REAL")
check(por_campo["pasillo"].estado == CERO_REAL, "pasillo (no existe) -> CERO_REAL")
check(por_campo["vestibulo"].estado == CERO_REAL, "vestibulo (no existe) -> CERO_REAL")
check(por_campo["aseo"].texto == "3,00 m²", "aseo calculado")

# Terraza 1/2: dos piezas reales, dos huecos, cada una numerada en su propia
# etiqueta -> SI se puede asignar sin inventar nada.
check(por_campo["terraza_1"].estado == CALCULADO and por_campo["terraza_1"].texto == "5,00 m²",
      "terraza_1 asignada por coincidencia exacta de numero", por_campo["terraza_1"].texto)
check(por_campo["terraza_2"].texto == "6,00 m²", "terraza_2 asignada por coincidencia exacta de numero")
check(por_campo["tendedero"].estado == CALCULADO and por_campo["tendedero"].texto == "4,00 m²",
      "tendedero (una sola pieza, un solo hueco) -> calculado")

# Totales: nada bloqueado, deben sumar bien.
esperado_interior = 20.0 + 10.0 + 8.0 + 0.0 + 3.0 + 0.0 + 0.0  # salon+dorm1+dorm2+dorm3(0)+aseo+bano(0)+pasillo(0)+vestibulo(0)
# (orden real de suma en el modulo: salon_cocina,pasillo,d1,d2,d3,bano,aseo,vestibulo)
check(por_campo["total_util_interior"].estado == CALCULADO,
      "total_util_interior calculado (nada bloqueado)", por_campo["total_util_interior"].texto)
check(por_campo["total_util_interior"].texto == "41,00 m²",
      "total_util_interior = 20+10+8+3 = 41,00 m²", por_campo["total_util_interior"].texto)
check(por_campo["total_util_exterior"].texto == "15,00 m²",
      "total_util_exterior = 4+5+6 = 15,00 m²", por_campo["total_util_exterior"].texto)
check(por_campo["total_util"].texto == "56,00 m²",
      "total_util = 41+15 = 56,00 m²", por_campo["total_util"].texto)

check(por_campo["superficie_construida_cerrada"].estado == NO_DISPONIBLE, "construida cerrada -> N/D siempre")
check(por_campo["superficie_construida_exterior"].estado == NO_DISPONIBLE, "construida exterior -> N/D siempre")
check(por_campo["numero_unidades"].estado == NO_DISPONIBLE, "numero_unidades -> N/D siempre")

check(por_campo["vivienda_tipo"].estado == CALCULADO and por_campo["vivienda_tipo"].texto == "VT-TEST/1",
      "vivienda_tipo calculado cuando la celda esta vacia", por_campo["vivienda_tipo"].texto)
check(por_campo["vivienda_tipo"].escribir is True, "y SI se marca para escribir (celda vacia)")


print()
print("B. Conservacion de una celda ya rellenada")
print("-" * 68)

# B1: coincide -> se conserva, no se reescribe.
cuadro_ok = cuadro_completo(existentes={"vivienda_tipo": "VT-TEST /1"})
res_ok = calcular_relleno_cuadro(unit, cuadro_ok, rooms)
vt_ok = [r for r in res_ok if r.campo == "vivienda_tipo"][0]
check(vt_ok.estado == CALCULADO, "vivienda_tipo ya escrita y coincide -> CALCULADO (no BLOQUEADO)")
check(vt_ok.texto == "VT-TEST /1", "se conserva el texto EXACTO que ya habia en el DXF (no se reformatea)",
      vt_ok.texto)
check(vt_ok.preexistente is True, "preexistente=True")
check(vt_ok.escribir is False, "escribir=False -- la Fase 3 debe saltarsela")

# B2: NO coincide -> nunca se pisa, se bloquea para revision humana.
cuadro_mal = cuadro_completo(existentes={"vivienda_tipo": "VT-OTRA/9"})
res_mal = calcular_relleno_cuadro(unit, cuadro_mal, rooms)
vt_mal = [r for r in res_mal if r.campo == "vivienda_tipo"][0]
check(vt_mal.estado == BLOQUEADO, "vivienda_tipo ya escrita y NO coincide -> BLOQUEADO, nunca sobrescrita")
check(vt_mal.texto == "VT-OTRA/9", "el texto devuelto sigue siendo el que YA HABIA (no el calculado)",
      vt_mal.texto)
check(vt_mal.escribir is False, "escribir=False -- tampoco en este caso se toca la celda")


print()
print("C. `v2s.dxf` real")
print("-" * 68)

#: `v2s.dxf` es un plano real de un cliente: no está en el repositorio ni puede
#: estarlo. Se localiza con la variable de entorno `ARCHMUSE_DXF_V2S`. Sin ella
#: esta parte se salta, igual que antes — lo que ya no hay es la ruta personal
#: de nadie escrita en un repositorio público.
DXF_PATH = os.environ.get("ARCHMUSE_DXF_V2S", "")

if not os.path.exists(DXF_PATH):
    print("  (v2s.dxf no disponible (define ARCHMUSE_DXF_V2S con su ruta) -- seccion omitida, mismo criterio que")
    print("   tests/test_analizar_planta.py con ejemplo.dxf)")
else:
    import ezdxf
    from analyzer import evaluator, parser

    doc = ezdxf.readfile(DXF_PATH)
    plano = parser.leer_plano(doc)
    advanced = evaluator.evaluate_advanced(plano.rooms, plano.unit_labels)
    check(len(advanced.units) == 1, "v2s.dxf sigue produciendo una sola vivienda (VT1/3)",
          "%d unidades" % len(advanced.units))
    unit_real = advanced.units[0]

    cuadro_real = detectar_cuadro_superficies(doc)
    check(cuadro_real is not None, "detectar_cuadro_superficies encuentra el ACAD_TABLE por su titulo")
    check(len(cuadro_real.celdas) == 18, "las 18 celdas de valor detectadas", "%d" % len(cuadro_real.celdas))

    resultado_real = calcular_relleno_cuadro(unit_real, cuadro_real, unit_real.rooms)
    por_campo_real = {r.campo: r for r in resultado_real}

    esperado_calculado = {
        "salon_cocina", "dormitorio_1", "dormitorio_2", "dormitorio_3",
        "bano", "aseo", "total_util_interior", "vivienda_tipo",
    }
    esperado_cero = {"pasillo", "vestibulo"}
    esperado_bloqueado = {"tendedero", "terraza_1", "terraza_2", "total_util_exterior", "total_util"}
    esperado_nd = {"superficie_construida_cerrada", "superficie_construida_exterior", "numero_unidades"}

    for campo in esperado_calculado:
        check(por_campo_real[campo].estado == CALCULADO, "%s -> CALCULADO" % campo,
              por_campo_real[campo].estado)
    for campo in esperado_cero:
        check(por_campo_real[campo].estado == CERO_REAL and por_campo_real[campo].texto == "0,00 m²",
              "%s -> CERO_REAL (0,00 m²)" % campo, por_campo_real[campo].texto)
    for campo in esperado_bloqueado:
        check(por_campo_real[campo].estado == BLOQUEADO, "%s -> BLOQUEADO" % campo,
              por_campo_real[campo].estado)
        check(por_campo_real[campo].escribir is False, "%s -> escribir=False" % campo)
        check(por_campo_real[campo].motivo is not None and len(por_campo_real[campo].motivo) > 0,
              "%s -> tiene motivo explicado" % campo)
    for campo in esperado_nd:
        check(por_campo_real[campo].estado == NO_DISPONIBLE, "%s -> NO_DISPONIBLE" % campo,
              por_campo_real[campo].estado)

    # El criterio mas importante de todos: ningun campo bloqueado lleva un
    # numero. "BLOQUEADO" es texto, nunca "m²".
    for campo in esperado_bloqueado:
        check("m²" not in por_campo_real[campo].texto,
              "%s bloqueado NO lleva ninguna cifra inventada" % campo, por_campo_real[campo].texto)

    check(por_campo_real["vivienda_tipo"].texto == "VT1 /3", "vivienda_tipo conserva el texto EXACTO del DXF",
          por_campo_real["vivienda_tipo"].texto)
    check(por_campo_real["vivienda_tipo"].preexistente is True, "vivienda_tipo marcada preexistente")
    check(por_campo_real["vivienda_tipo"].escribir is False, "vivienda_tipo NO se reescribe")

    check(por_campo_real["total_util_interior"].texto == "58,78 m²",
          "total_util_interior real = 58,78 m²", por_campo_real["total_util_interior"].texto)


print()
print("D. `ejemplo.dxf` real -- celdas preexistentes fuera de VIVIENDA TIPO")
print("-" * 68)

EJEMPLO_DXF_PATH = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")

if not os.path.exists(EJEMPLO_DXF_PATH):
    print("  (ejemplo.dxf no disponible en este entorno -- seccion omitida)")
else:
    import ezdxf as _ezdxf  # noqa: E402
    from analyzer import evaluator as _evaluator, parser as _parser  # noqa: E402

    doc_ej = _ezdxf.readfile(EJEMPLO_DXF_PATH)
    plano_ej = _parser.leer_plano(doc_ej)
    advanced_ej = _evaluator.evaluate_advanced(plano_ej.rooms, plano_ej.unit_labels)
    unit_ej = advanced_ej.units[0]  # VT1/3, la primera del edificio

    cuadro_ej = detectar_cuadro_superficies(doc_ej)
    check(cuadro_ej is not None, "ejemplo.dxf tambien tiene un cuadro reconocible")

    resultado_ej = calcular_relleno_cuadro(unit_ej, cuadro_ej, unit_ej.rooms)
    por_campo_ej = {r.campo: r for r in resultado_ej}

    preexistentes_esperados = {
        "salon_cocina": "21.90m2", "dormitorio_1": "12.72m2", "dormitorio_2": "8.48",
        "dormitorio_3": "8.53m2", "bano": "4.01m2", "aseo": "3.14m2",
        "tendedero": "4.22m2", "terraza_1": "3.32m2", "numero_unidades": "8",
    }
    for campo, texto_original in preexistentes_esperados.items():
        r = por_campo_ej[campo]
        check(r.estado == CALCULADO and r.texto == texto_original and r.preexistente is True,
              "%s: se conserva EXACTO (%r), no se recalcula ni se pierde" % (campo, texto_original),
              "%s / preexistente=%s" % (r.texto, r.preexistente))
        check(r.escribir is False, "%s: escribir=False (nunca se reescribe)" % campo)

    # terraza_2 esta vacia, pero terraza_1 (misma familia) ya esta declarada:
    # no se completa por su cuenta -- no hay forma fiable de saber si la
    # unica Terraza real de mas ya la cuenta terraza_1 o no.
    check(por_campo_ej["terraza_2"].estado == BLOQUEADO,
          "terraza_2 (vacia, con terraza_1 ya declarada) -> BLOQUEADO, no se inventa")

    # Los totales dependen de celdas preexistentes en formatos ajenos
    # ("21.90m2", "8.48"...) que este modulo no puede sumar con garantias:
    # se bloquean en vez de fallar o de inventar una conversion.
    for campo in ("total_util_interior", "total_util_exterior", "total_util"):
        check(por_campo_ej[campo].estado == BLOQUEADO,
              "%s se bloquea (no se suman formatos preexistentes ajenos)" % campo,
              por_campo_ej[campo].estado)

    # pasillo/vestibulo SI estan vacios de verdad (sin texto previo) y sin
    # ninguna estancia real que los rellene -> siguen siendo CERO_REAL, el
    # camino normal, no BLOQUEADO ni preexistente.
    for campo in ("pasillo", "vestibulo"):
        check(por_campo_ej[campo].estado == CERO_REAL and por_campo_ej[campo].preexistente is False,
              "%s sigue siendo CERO_REAL normal (no preexistente)" % campo)


print()
print("=" * 68)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
