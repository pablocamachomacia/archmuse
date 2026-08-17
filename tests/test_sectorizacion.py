# -*- coding: utf-8 -*-
"""CAP-4, tarea 9: `C01`, limite de 2.500 m2 de superficie por planta.

Ejecutar:  python tests/test_sectorizacion.py

Rapido (<1 s): funciones puras sobre Hecho sinteticos, sin DXF ni Flask.

Que protege (PRD Sec4ter):

1. Suma de superficie_util_db_si de la planta >= 2.500 m2 -> FAIL (Hecho
   KNOWN, valor = suma).
2. Suma < 2.500 m2, con o sin unidades sin superficie -> UNKNOWN, NUNCA PASS.
3. planta UNKNOWN -> C01 UNKNOWN para esa unidad, sin agregarla con nadie.
4. Ausencia total de dato (todas las superficies de la planta UNKNOWN) ->
   UNKNOWN.
5. Monotonia: una unidad sin superficie medida no puede convertir un FAIL ya
   demostrado en UNKNOWN.
6. Trazabilidad: valor, unidad, planta_numero, limite_m2 y motivo viajan
   siempre en el Hecho devuelto.
7. Nunca existe ningun camino de codigo que produzca un veredicto "PASS".
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer.hechos import ALTA, ESTIMATED, KNOWN, MEDIA, UNKNOWN, Hecho, Motivo  # noqa: E402
from analyzer.planta import (  # noqa: E402
    ORIGEN_CONVENCION_NOMBRE,
    ORIGEN_DECLARADO,
    planta as hecho_planta,
)
from analyzer.sectorizacion import (  # noqa: E402
    CODIGO_C01,
    LIMITE_M2,
    PLANTA_NO_DISPONIBLE,
    SUPERFICIE_INSUFICIENTE,
    limite_superficie_sector,
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


def sup_known(ambito, valor, confianza=MEDIA):
    return Hecho(nombre="superficie_util_db_si", ambito=ambito, tipo="derivado",
                 unidad="m2", estado=KNOWN, valor=valor, confianza=confianza)


def sup_unknown(ambito, detalle="Recintos que comparten superficie: solape de prueba."):
    return Hecho(nombre="superficie_util_db_si", ambito=ambito, tipo="derivado",
                 unidad="m2", estado=UNKNOWN,
                 motivos=(Motivo("GEOMETRY_OVERLAP_UNRESOLVED", detalle),))


TODOS_LOS_HECHOS = []  # se acumulan aqui para el barrido final "nunca PASS"


def registrar(hechos):
    TODOS_LOS_HECHOS.extend(hechos)
    return hechos


print("A. Suma >= 2.500 m2 -> FAIL")

p1_v1 = hecho_planta("vivienda V1", numero=1, sobre_rasante=True, origen=ORIGEN_DECLARADO)
s_v1 = sup_known("vivienda V1", 3000.0)
res = registrar(limite_superficie_sector([s_v1], [p1_v1]))
h = res[0]
check(h.estado == KNOWN, "suma 3000 >= 2500 -> KNOWN (evidencia de FAIL)", h.estado)
check(h.valor == 3000.0, "valor = suma acumulada, sin recortar", h.valor)
check(h.ambito == "planta 1", "ambito = 'planta 1' (magnitud de planta, no de vivienda)", h.ambito)
check(h.unidad == "m2", "unidad = m2")
check(h.diagnostico.get("veredicto") == "FAIL", "diagnostico['veredicto'] == 'FAIL'",
      h.diagnostico.get("veredicto"))
check(h.diagnostico.get("limite_m2") == LIMITE_M2, "diagnostico trae el limite (2500)")
check(h.diagnostico.get("planta_numero") == 1, "diagnostico trae la planta afectada")
check(h.diagnostico.get("codigo_regla") == CODIGO_C01,
      "diagnostico trae el codigo propio de C01", h.diagnostico.get("codigo_regla"))
check(CODIGO_C01 != "CTE-DB-SI-3", "el codigo de C01 es distinto de CTE-DB-SI-3", CODIGO_C01)

print("\nA2. Suma exacta de varias unidades en la misma planta")

p_a = hecho_planta("vivienda A", numero=2, origen=ORIGEN_DECLARADO)
p_b = hecho_planta("vivienda B", numero=2, origen=ORIGEN_DECLARADO)
s_a = sup_known("vivienda A", 1400.0)
s_b = sup_known("vivienda B", 1200.0)  # 1400+1200 = 2600 >= 2500
res2 = registrar(limite_superficie_sector([s_a, s_b], [p_a, p_b]))
check(res2[0].estado == KNOWN and res2[1].estado == KNOWN,
      "dos unidades de la misma planta comparten el mismo veredicto (FAIL)")
check(res2[0].valor == 2600.0 and res2[1].valor == 2600.0,
      "ambas llevan la SUMA de la planta, no su superficie individual",
      repr((res2[0].valor, res2[1].valor)))
check(res2[0].ambito == res2[1].ambito == "planta 2",
      "mismo ambito para las dos: la planta, no la vivienda")

print("\nB. Suma < 2.500 m2, todas las unidades medidas -> UNKNOWN, nunca PASS")

p2_v1 = hecho_planta("vivienda V2", numero=1, origen=ORIGEN_DECLARADO)
s_v2 = sup_known("vivienda V2", 1800.0)
res_b = registrar(limite_superficie_sector([s_v2], [p2_v1]))
hb = res_b[0]
check(hb.estado == UNKNOWN, "1800 < 2500, todo medido -> UNKNOWN (nunca PASS)", hb.estado)
check(hb.valor is None, "UNKNOWN no publica valor (P6 del contrato de Hecho)")
check(hb.diagnostico.get("veredicto") is None,
      "diagnostico['veredicto'] no es 'FAIL' (y desde luego no 'PASS')")
check(hb.diagnostico.get("suma_parcial_m2") == 1800.0,
      "el acumulado SI se conserva en diagnostico aunque el hecho sea UNKNOWN",
      hb.diagnostico.get("suma_parcial_m2"))
check(len(hb.motivos) == 1 and hb.motivos[0].codigo == SUPERFICIE_INSUFICIENTE,
      "motivo estructurado con el codigo esperado")
check("no es posible descartar" in hb.motivos[0].detalle.lower()
      or "subestima" in hb.motivos[0].detalle.lower(),
      "el motivo explica la razon real: el proxy subestima, no que falten datos",
      hb.motivos[0].detalle)

print("\nC. planta UNKNOWN -> C01 UNKNOWN, sin agregar con nadie")

p_desconocida = hecho_planta("vivienda V3", numero=None)
s_v3 = sup_known("vivienda V3", 4000.0)  # superficie grande, pero SIN planta
res_c = registrar(limite_superficie_sector([s_v3], [p_desconocida]))
hc = res_c[0]
check(hc.estado == UNKNOWN, "planta UNKNOWN -> C01 UNKNOWN aunque la superficie sea grande",
      hc.estado)
check(hc.ambito == "vivienda V3",
      "sin planta resuelta, el ambito es el de la propia unidad (no hay planta a la que agregar)")
check(len(hc.motivos) == 1 and hc.motivos[0].codigo == PLANTA_NO_DISPONIBLE,
      "motivo especifico: PLANTA_NO_DISPONIBLE")
check(hc.diagnostico.get("planta_numero") is None,
      "diagnostico no inventa un numero de planta")

print("\nD. Ausencia total de dato: todas las superficies de la planta son UNKNOWN")

p_d1 = hecho_planta("vivienda D1", numero=5, origen=ORIGEN_DECLARADO)
p_d2 = hecho_planta("vivienda D2", numero=5, origen=ORIGEN_DECLARADO)
s_d1 = sup_unknown("vivienda D1")
s_d2 = sup_unknown("vivienda D2")
res_d = registrar(limite_superficie_sector([s_d1, s_d2], [p_d1, p_d2]))
check(all(h.estado == UNKNOWN for h in res_d),
      "ninguna superficie medida en toda la planta -> UNKNOWN, nunca inventar un 0")
check(res_d[0].diagnostico.get("suma_parcial_m2") == 0,
      "suma parcial es 0 (no None): no hay ninguna unidad KNOWN que sumar")
check(res_d[0].diagnostico.get("unidades_sin_superficie") == ["vivienda D1", "vivienda D2"],
      "diagnostico lista explicitamente que unidades faltan",
      res_d[0].diagnostico.get("unidades_sin_superficie"))
check("no tienen superficie util determinada" in res_d[0].motivos[0].detalle,
      "el motivo distingue este caso (falta dato) del caso B (dato insuficiente)")

print("\nE. Monotonia: FAIL ya demostrado no se convierte en UNKNOWN por una unidad sin medir")

p_e1 = hecho_planta("vivienda E1", numero=7, origen=ORIGEN_DECLARADO)
p_e2 = hecho_planta("vivienda E2", numero=7, origen=ORIGEN_DECLARADO)
s_e1 = sup_known("vivienda E1", 2600.0)  # ya solo, >= 2500
s_e2 = sup_unknown("vivienda E2")        # esta unidad no aporta superficie
res_e = registrar(limite_superficie_sector([s_e1, s_e2], [p_e1, p_e2]))
check(all(h.estado == KNOWN for h in res_e),
      "FAIL se mantiene aunque una unidad de la planta no tenga superficie medida")
check(all(h.valor == 2600.0 for h in res_e),
      "el valor es la suma de lo medido (2600), no se espera a la unidad sin medir")
check(res_e[0].diagnostico.get("unidades_sin_superficie") == ["vivienda E2"],
      "se deja constancia de que E2 no aporto dato, aunque no cambie el veredicto")

# Version "inversa" para blindar la monotonia: si se AÑADE una unidad sin
# medir a un grupo que YA fallaba, el resultado no puede mejorar a UNKNOWN.
res_e_solo = registrar(limite_superficie_sector([s_e1], [p_e1]))
check(res_e_solo[0].estado == KNOWN and res_e_solo[0].valor == 2600.0,
      "el mismo FAIL se sostiene solo con E1, antes de añadir E2")
check(res_e[0].estado == res_e_solo[0].estado == KNOWN,
      "anadir una unidad UNKNOWN al grupo NUNCA degrada un FAIL a UNKNOWN "
      "(monotonia estricta)")

print("\nF. Trazabilidad completa (ambos veredictos)")

for hecho_a_revisar, contexto in ((h, "FAIL"), (hb, "UNKNOWN")):
    check(hecho_a_revisar.unidad == "m2", "%s: unidad = m2" % contexto)
    check(hecho_a_revisar.diagnostico.get("limite_m2") == LIMITE_M2,
          "%s: limite_m2 presente" % contexto)
    check(hecho_a_revisar.diagnostico.get("planta_numero") is not None,
          "%s: planta_numero presente" % contexto)
    check(bool(hecho_a_revisar.explicacion), "%s: explicacion no vacia" % contexto)
    check(bool(hecho_a_revisar.procedencia), "%s: procedencia no vacia" % contexto)
check(h.motivos == (), "FAIL (KNOWN) no lleva motivos de ausencia")
check(len(hb.motivos) == 1, "UNKNOWN si lleva motivo")

print("\nG. planta ESTIMATED (convencion de nombre) tambien agrupa, y baja la confianza")

p_est = hecho_planta("vivienda G1", numero=9, sobre_rasante=True,
                      origen=ORIGEN_CONVENCION_NOMBRE)
s_g1 = sup_known("vivienda G1", 2800.0, confianza=MEDIA)
res_g = registrar(limite_superficie_sector([s_g1], [p_est]))
check(res_g[0].estado == KNOWN, "planta ESTIMATED tambien agrupa (no solo KNOWN)")
check(res_g[0].confianza == MEDIA,
      "confianza refleja el eslabon mas debil (superficie Media, planta Media)",
      res_g[0].confianza)

print("\nH. Contrato de longitudes, igual que ocupacion_por_zona")

try:
    limite_superficie_sector([s_v1], [p1_v1, p2_v1])
    check(False, "listas de distinta longitud deben fallar")
except ValueError:
    check(True, "listas de distinta longitud -> ValueError, no un emparejado silencioso")

print("\nI. Barrido final: en NINGUN hecho generado en este test existe un veredicto PASS")

check(len(TODOS_LOS_HECHOS) >= 10, "hay una muestra amplia de hechos que barrer",
      len(TODOS_LOS_HECHOS))
for hecho_generado in TODOS_LOS_HECHOS:
    check(hecho_generado.estado in (KNOWN, UNKNOWN),
          "estado solo KNOWN/UNKNOWN, nunca un tercer estado inventado",
          hecho_generado.estado)
    check(hecho_generado.diagnostico.get("veredicto") != "PASS",
          "diagnostico['veredicto'] nunca es 'PASS'",
          hecho_generado.diagnostico.get("veredicto"))
    if hecho_generado.estado == KNOWN:
        check(hecho_generado.diagnostico.get("veredicto") == "FAIL",
              "todo hecho KNOWN de C01 es, exactamente, un FAIL — no hay otra "
              "razon para que sea KNOWN")

print("\nJ. Test negativo dedicado — limite_superficie_sector() jamas produce PASS")
print("   (unico proposito de este bloque: uno por camino, reutilizando A-D, sin fixtures nuevas)")

# Los cuatro caminos relevantes de C01, cada uno con su hecho ya calculado
# en las secciones A-D. No se reconstruye nada: se re-verifica, de forma
# aislada y explicita, que NINGUNO de los cuatro es ni puede leerse como
# "PASS".
CAMINOS_C01 = (
    ("superficie >= 2.500 -> FAIL",        h,          KNOWN,   "FAIL"),
    ("superficie < 2.500 -> UNKNOWN",      hb,         UNKNOWN, None),
    ("planta UNKNOWN -> UNKNOWN",          hc,          UNKNOWN, None),
    ("sin superficie (todas UNKNOWN) -> UNKNOWN", res_d[0], UNKNOWN, None),
)

for descripcion, hecho_camino, estado_esperado, veredicto_esperado in CAMINOS_C01:
    check(hecho_camino.estado == estado_esperado,
          "%s: estado == %s" % (descripcion, estado_esperado), hecho_camino.estado)
    check(hecho_camino.diagnostico.get("veredicto") == veredicto_esperado,
          "%s: diagnostico['veredicto'] == %r, nunca 'PASS'"
          % (descripcion, veredicto_esperado),
          hecho_camino.diagnostico.get("veredicto"))
    check(hecho_camino.diagnostico.get("veredicto") != "PASS",
          "%s: veredicto NO es 'PASS' (afirmacion directa, no por descarte)" % descripcion)

check(all(c[3] != "PASS" for c in CAMINOS_C01),
      "ninguno de los cuatro caminos de C01 tiene 'PASS' como resultado esperado")

print("\nK. Regresion sobre ejemplo.dxf (datos reales) — tarea 11")

DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")
if not os.path.exists(DXF):
    print("  [SALTA] no se encuentra %s" % DXF)
else:
    from analyzer import parser  # noqa: E402
    from analyzer.evaluator import evaluate_advanced  # noqa: E402
    from analyzer.superficie_util import (  # noqa: E402
        superficie_util_db_si,
        superficie_util_ocupable_db_si,
    )
    from analyzer.uso_previsto import ZonaDeUso, usos_por_zona  # noqa: E402
    from analyzer.ocupacion import ocupacion as calcular_ocupacion  # noqa: E402
    from analyzer.planta import normalizar_declaracion_planta  # noqa: E402

    plano = parser.leer_plano(parser.load_document(DXF))
    advanced = evaluate_advanced(
        plano.rooms, unit_labels=plano.unit_labels, norte_grados=0,
        tipologia="plurifamiliar", zona_cte="C", densidad_urbana="media",
    )
    usos_dxf = usos_por_zona(
        [ZonaDeUso(nombre="vivienda %s" % us.unit.name) for us in advanced.unit_scores],
        tipologia="plurifamiliar", uso_principal=None,
    )

    # K.1 — Baseline de ocupacion, recalculada el 2026-08-13 tras la
    # correccion de cierre geometrico (analyzer/parser.py::_esta_cerrada,
    # ver tests/test_cierre_recuperado.py). Valores obtenidos ejecutando
    # directamente el codigo actual (no de memoria).
    #
    # Frente a la baseline anterior (CAP-3, bd1a62f: 4 ESTIMATED + 2 UNKNOWN):
    # VT1/3, VT3/3 y VT4/2 cambian de valor porque ganan un recinto que antes
    # no se leia (closed=False mal puesto). VT5/1 pasa de UNKNOWN a ESTIMATED:
    # su solape (contorno duplicado de "Salon/cocina") se resuelve solo, al
    # aparecer el recinto real mas pequeno que antes era invisible. VT6/2
    # sigue UNKNOWN, pero ya NO por ese solape -- ahora por una causa propia
    # y genuina del DXF: el "Dormitorio 2" recuperado es geometricamente
    # invalido, y ademas dos "Terraza" de esa misma vivienda ya se solapaban
    # entre si antes de esta correccion. Detalle completo en
    # docs/audits/2026-08-13-hallazgos-cierre-geometrico.md (fuera de
    # alcance de esta tarea: no se toca esa geometria).
    OCUPACION_BASELINE_BD1A62F = {
        "VT1/3": 3.316434247032157,
        "VT2/2": 2.9221420262626543,
        "VT3/3": 3.3273964411538737,
        "VT4/2": 2.923476963273963,
        "VT5/1": 2.265743964767715,
        "VT6/2": None,  # UNKNOWN (geometria invalida + solape Terraza/Terraza)
    }

    print("K.1 Sin planta declarada — identico a la linea base recalculada")

    check(normalizar_declaracion_planta(None) is None,
          "sin declaracion, el normalizador no produce ninguna planta")

    plantas_hechos_sin = [
        hecho_planta("vivienda %s" % us.unit.name, numero=None)
        for us in advanced.unit_scores
    ]
    ocup_sin = [
        calcular_ocupacion(superficie_util_ocupable_db_si(us.unit), uso_h, planta=p)
        for us, uso_h, p in zip(advanced.unit_scores, usos_dxf, plantas_hechos_sin)
    ]

    n_estimated = sum(1 for h in ocup_sin if h.estado == ESTIMATED)
    n_unknown = sum(1 for h in ocup_sin if h.estado == UNKNOWN)
    check(n_estimated == 5 and n_unknown == 1,
          "5 ESTIMATED + 1 UNKNOWN",
          "%d ESTIMATED, %d UNKNOWN" % (n_estimated, n_unknown))
    check(all(p.estado == UNKNOWN for p in plantas_hechos_sin),
          "planta = UNKNOWN para las 6 unidades, sin declarar")

    for us, h in zip(advanced.unit_scores, ocup_sin):
        esperado = OCUPACION_BASELINE_BD1A62F[us.unit.name]
        if esperado is None:
            check(h.estado == UNKNOWN, "%s: UNKNOWN" % us.unit.name)
        else:
            check(h.estado == ESTIMATED and abs(h.valor - esperado) < 1e-9,
                  "%s: ocupacion == linea base EXACTO (sin redondear)" % us.unit.name,
                  "obtenido=%r esperado=%r" % (h.valor, esperado))
        check(h.diagnostico.get("agregado_no_normativo") is True,
              "%s: agregado_no_normativo=True (sin planta)" % us.unit.name)

    # Cadena causal del unico UNKNOWN que queda (VT6/2), intacta. VT5/1 ya no
    # esta aqui: su solape se resolvio con la correccion de cierre geometrico.
    causales = {h_.ambito: h_ for h_ in ocup_sin if h_.estado == UNKNOWN}
    for ambito_vivienda in ("vivienda VT6/2",):
        hc = causales.get(ambito_vivienda)
        check(hc is not None, "%s presente entre los UNKNOWN" % ambito_vivienda)
        if hc is None:
            continue
        check(len(hc.motivos) == 1 and hc.motivos[0].codigo == "AREA_NOT_AVAILABLE",
              "%s: motivo AREA_NOT_AVAILABLE intacto" % ambito_vivienda)
        check(hc.procedencia == ("superficie_util_ocupable_db_si -> UNKNOWN",),
              "%s: procedencia (cadena causal) intacta" % ambito_vivienda,
              hc.procedencia)
        check(hc.diagnostico.get("cadena_causal") == ["superficie_util_ocupable_db_si -> UNKNOWN"],
              "%s: diagnostico.cadena_causal intacto" % ambito_vivienda)

    print("\nK.2 C01 sin planta declarada — UNKNOWN para las 6 unidades")

    sup_db_si_sin = [superficie_util_db_si(us.unit) for us in advanced.unit_scores]
    c01_sin = registrar(limite_superficie_sector(sup_db_si_sin, plantas_hechos_sin))
    check(len(c01_sin) == 6, "un hecho C01 por cada una de las 6 unidades")
    check(all(h.estado == UNKNOWN for h in c01_sin),
          "C01 = UNKNOWN para las 6 unidades, sin planta declarada")
    check(all(h.motivos and h.motivos[0].codigo == PLANTA_NO_DISPONIBLE for h in c01_sin),
          "todas por el mismo motivo: PLANTA_NO_DISPONIBLE")
    check(all(h.diagnostico.get("veredicto") != "PASS" for h in c01_sin),
          "ningun PASS, sin planta declarada")

    print("\nK.3 Con planta declarada valida (\"Planta 1\") — ocupacion identica, solo cambia el ambito")

    numero, sobre_rasante = normalizar_declaracion_planta("Planta 1")
    plantas_hechos_con = [
        hecho_planta("vivienda %s" % us.unit.name, numero=numero,
                         sobre_rasante=sobre_rasante, origen=ORIGEN_DECLARADO)
        for us in advanced.unit_scores
    ]
    check(all(p.estado == KNOWN and p.valor == 1 for p in plantas_hechos_con),
          "planta pasa a KNOWN, numero=1, para las 6 unidades")

    ocup_con = [
        calcular_ocupacion(superficie_util_ocupable_db_si(us.unit), uso_h, planta=p)
        for us, uso_h, p in zip(advanced.unit_scores, usos_dxf, plantas_hechos_con)
    ]
    for us, h_sin, h_con in zip(advanced.unit_scores, ocup_sin, ocup_con):
        check(h_sin.estado == h_con.estado,
              "%s: mismo estado con y sin planta" % us.unit.name)
        if h_sin.estado != UNKNOWN:
            check(h_sin.valor == h_con.valor,
                  "%s: MISMO valor de ocupacion exacto, con y sin planta "
                  "(planta nunca toca el calculo)" % us.unit.name,
                  "sin=%r con=%r" % (h_sin.valor, h_con.valor))
        check(h_con.diagnostico.get("agregado_no_normativo") is False,
              "%s: CON planta, agregado_no_normativo pasa a False" % us.unit.name)
        check(h_con.diagnostico.get("ambito_emitido") == "planta 1",
              "%s: CON planta, ambito_emitido cambia a 'planta 1'" % us.unit.name)
        check(h_con.ambito == "planta 1, %s" % h_sin.ambito,
              "%s: el ambito antepone la planta sin perder la vivienda" % us.unit.name)

    print("\nK.4 C01 con planta declarada — semantica del PRD, nunca PASS")

    sup_db_si_con = [superficie_util_db_si(us.unit) for us in advanced.unit_scores]
    c01_con = registrar(limite_superficie_sector(sup_db_si_con, plantas_hechos_con))
    suma_real = sum(
        s.valor for s in sup_db_si_con if s.estado == KNOWN
    )
    check(abs(suma_real - 295.10387284980726) < 1e-6,
          "suma real de superficie_util_db_si de las 5 unidades medibles "
          "(295.10 m2, muy por debajo de 2500)", suma_real)
    check(all(h.ambito == "planta 1" for h in c01_con),
          "las 6 unidades comparten el mismo ambito de C01: 'planta 1'")
    check(all(h.estado == UNKNOWN for h in c01_con),
          "C01 = UNKNOWN para las 6 (suma 295 m2 << 2500, y ademas VT6/2 sin "
          "superficie: geometria invalida + solape Terraza/Terraza)")
    check(all(h.diagnostico.get("veredicto") != "PASS" for h in c01_con),
          "NINGUN PASS de C01, con planta declarada, sobre datos reales")
    check(c01_con[0].diagnostico.get("suma_parcial_m2") is not None
          and abs(c01_con[0].diagnostico["suma_parcial_m2"] - suma_real) < 1e-6,
          "trazabilidad: suma_parcial_m2 coincide con el calculo directo")
    check(c01_con[0].diagnostico.get("unidades_sin_superficie") ==
          ["vivienda VT6/2"],
          "trazabilidad: se lista la unidad sin superficie",
          c01_con[0].diagnostico.get("unidades_sin_superficie"))

print("\nL. Fixture multiplanta sintetica — tarea 12")
print("   Dos plantas independientes: planta 1 se queda corta, planta 2 supera el limite.")

# Planta 1 (numero=1): 2 unidades medidas (2100 m2, por debajo de 2500) + 1
# sin superficie (solape). Debe salir UNKNOWN.
p1_a = hecho_planta("vivienda P1-A", numero=1, origen=ORIGEN_DECLARADO)
p1_b = hecho_planta("vivienda P1-B", numero=1, origen=ORIGEN_DECLARADO)
p1_c = hecho_planta("vivienda P1-C", numero=1, origen=ORIGEN_DECLARADO)
s1_a = sup_known("vivienda P1-A", 1200.0)
s1_b = sup_known("vivienda P1-B", 900.0)   # 1200+900 = 2100 < 2500
s1_c = sup_unknown("vivienda P1-C")

# Planta 2 (numero=2): 2 unidades medidas (2700 m2, supera 2500) + 1 sin
# superficie (solape). Debe salir FAIL pese al UNKNOWN (monotonia).
p2_a = hecho_planta("vivienda P2-A", numero=2, origen=ORIGEN_DECLARADO)
p2_b = hecho_planta("vivienda P2-B", numero=2, origen=ORIGEN_DECLARADO)
p2_c = hecho_planta("vivienda P2-C", numero=2, origen=ORIGEN_DECLARADO)
s2_a = sup_known("vivienda P2-A", 1800.0)
s2_b = sup_known("vivienda P2-B", 900.0)   # 1800+900 = 2700 >= 2500
s2_c = sup_unknown("vivienda P2-C")

# Entrada DELIBERADAMENTE entrelazada (P1/P2 alternados, no agrupados) para
# que ningun acierto dependa del orden de llegada — la agregacion tiene que
# venir del numero de planta, nunca de la posicion en la lista.
superficies_multiplanta = [s1_a, s2_a, s1_b, s2_b, s1_c, s2_c]
plantas_multiplanta =    [p1_a, p2_a, p1_b, p2_b, p1_c, p2_c]

res_multi = registrar(limite_superficie_sector(superficies_multiplanta, plantas_multiplanta))
por_ambito_multi = {}
for s, h in zip(superficies_multiplanta, res_multi):
    por_ambito_multi.setdefault(s.ambito, h)

h_p1 = por_ambito_multi["vivienda P1-A"]
h_p2 = por_ambito_multi["vivienda P2-A"]

print("\nL.1 Agregacion independiente por planta (1)")

check(h_p1.diagnostico.get("suma_parcial_m2") == 2100.0,
      "planta 1: suma_parcial_m2 == 2100 (SOLO P1-A + P1-B, no mezclada con planta 2)",
      h_p1.diagnostico.get("suma_parcial_m2"))
check(h_p2.diagnostico.get("suma_parcial_m2") == 2700.0,
      "planta 2: suma_parcial_m2 == 2700 (SOLO P2-A + P2-B, no mezclada con planta 1)",
      h_p2.diagnostico.get("suma_parcial_m2"))

print("\nL.2 Planta 2 (>= 2.500 m2) -> FAIL")

check(h_p2.estado == KNOWN, "planta 2: FAIL (KNOWN, evidencia suficiente)", h_p2.estado)
check(h_p2.valor == 2700.0, "planta 2: valor == 2700", h_p2.valor)
check(h_p2.diagnostico.get("veredicto") == "FAIL", "planta 2: veredicto == 'FAIL'")

print("\nL.3 Planta 1 (< 2.500 m2) -> UNKNOWN, nunca PASS")

check(h_p1.estado == UNKNOWN, "planta 1: UNKNOWN (no llega a 2500)", h_p1.estado)
check(h_p1.valor is None, "planta 1: sin valor publicado (P6)")
check(h_p1.diagnostico.get("veredicto") != "PASS",
      "planta 1: veredicto NUNCA es 'PASS' aunque este por debajo del limite")

print("\nL.4 Un UNKNOWN de una planta no contamina la otra")

check(h_p1.diagnostico.get("unidades_sin_superficie") == ["vivienda P1-C"],
      "planta 1: solo lista SU propia unidad sin superficie (P1-C), no P2-C",
      h_p1.diagnostico.get("unidades_sin_superficie"))
check(h_p2.diagnostico.get("unidades_sin_superficie") == ["vivienda P2-C"],
      "planta 2: solo lista SU propia unidad sin superficie (P2-C), no P1-C",
      h_p2.diagnostico.get("unidades_sin_superficie"))
check(h_p1.diagnostico.get("unidades_computadas") == ["vivienda P1-A", "vivienda P1-B"],
      "planta 1: solo las unidades de la planta 1 entran en el computo",
      h_p1.diagnostico.get("unidades_computadas"))
check(h_p2.diagnostico.get("unidades_computadas") == ["vivienda P2-A", "vivienda P2-B"],
      "planta 2: solo las unidades de la planta 2 entran en el computo",
      h_p2.diagnostico.get("unidades_computadas"))

print("\nL.5 No existe suma global entre plantas que produzca un falso FAIL")

suma_global_erronea = (
    h_p1.diagnostico["suma_parcial_m2"] + h_p2.diagnostico["suma_parcial_m2"]
)
check(suma_global_erronea >= LIMITE_M2,
      "control: la suma GLOBAL (2100+2700=4800) SI superaria el limite si se "
      "sumara todo el proyecto junto — precisamente el error que hay que evitar",
      suma_global_erronea)
check(h_p1.estado == UNKNOWN,
      "y aun asi planta 1 SIGUE siendo UNKNOWN: su veredicto no se contagia "
      "del total del proyecto, solo de sus propias unidades")
check(h_p1.valor != suma_global_erronea and h_p1.diagnostico["suma_parcial_m2"] != suma_global_erronea,
      "planta 1 nunca lleva el acumulado global (4800) en ningun campo")

print("\nL.6 Trazabilidad: la planta responsable es la correcta, no al reves")

check(h_p1.ambito == "planta 1" and h_p1.diagnostico.get("planta_numero") == 1,
      "planta 1: ambito y planta_numero == 1, no 2")
check(h_p2.ambito == "planta 2" and h_p2.diagnostico.get("planta_numero") == 2,
      "planta 2: ambito y planta_numero == 2, no 1")
check(h_p1.ambito != h_p2.ambito, "las dos plantas nunca comparten ambito")
# Todas las unidades de una misma planta deben devolver EL MISMO objeto de
# veredicto (mismo ambito/valor/diagnostico), verificado sobre las 3 de cada.
for nombre_vivienda in ("vivienda P1-A", "vivienda P1-B", "vivienda P1-C"):
    check(por_ambito_multi[nombre_vivienda].ambito == "planta 1",
          "%s resuelve al veredicto de planta 1, no de planta 2" % nombre_vivienda)
for nombre_vivienda in ("vivienda P2-A", "vivienda P2-B", "vivienda P2-C"):
    check(por_ambito_multi[nombre_vivienda].ambito == "planta 2",
          "%s resuelve al veredicto de planta 2, no de planta 1" % nombre_vivienda)

print("\nL.7 Monotonia dentro de la fixture multiplanta")

# Planta 2 ya es FAIL con P2-A+P2-B; anadir P2-C (UNKNOWN) no lo degrada.
res_p2_sin_c = limite_superficie_sector([s2_a, s2_b], [p2_a, p2_b])
check(res_p2_sin_c[0].estado == KNOWN and res_p2_sin_c[0].valor == 2700.0,
      "planta 2 sola (sin P2-C) ya es FAIL con 2700")
check(h_p2.estado == KNOWN and h_p2.valor == 2700.0,
      "planta 2 CON P2-C (UNKNOWN anadida) sigue siendo el mismo FAIL — "
      "monotonia: anadir una unidad sin medir no degrada un FAIL ya probado")

print("\n" + "=" * 60)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
