# -*- coding: utf-8 -*-
"""Fase 5 — "Datos necesarios para completar el cuadro" (`detectar_solicitudes`,
`aplicar_respuestas`, `celdas_sin_resolver`, en `analyzer/cuadro_superficies.py`).

Ejecutar:  python tests/test_solicitudes_cuadro_superficies.py

Que protege (mismo orden que pidió Pablo al encargar la Fase 5):

A. Caso completamente automático: ningún campo queda BLOQUEADO/NO_DISPONIBLE
   -> `detectar_solicitudes` devuelve lista vacía, no se pregunta nada.
B. `v2s.dxf` real: aparecen EXACTAMENTE las cuatro solicitudes que pidió
   Pablo (asignación tendedero/terraza 1/terraza 2 con sus candidatos reales;
   superficie construida cerrada; superficie construida exterior; número de
   unidades) -- ninguna otra (no se pregunta por salón, dormitorios, baño,
   aseo, pasillo, vestíbulo ni total útil interior, que ya se calculan solos).
C. Tras responder esas cuatro: las 18 celdas tienen un valor real, cero
   apariciones de `N/D` -- ni en el resultado en memoria ni en el DXF
   exportado de verdad.
D. Los totales (útil exterior, útil) se recalculan con la MISMA función de
   siempre (`_celda_total`), a partir de las respuestas.
E. El DXF original en disco conserva el mismo sha256 antes y después de todo
   el flujo (`exportar_cuadro_relleno` con `respuestas`).
F. Una respuesta que contradice una celda YA preexistente en el DXF real
   (aquí, "VIVIENDA TIPO") bloquea esa celda con un motivo de conflicto
   explícito -- nunca la sobrescribe -- y ESO bloquea también la descarga
   completa a nivel de `exportar_cuadro_relleno` (`campos_sin_resolver` no
   queda vacío).
"""
import hashlib
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer.cuadro_superficies import (  # noqa: E402
    BLOQUEADO,
    CERO_REAL,
    CeldaCuadro,
    CuadroSuperficies,
    aplicar_respuestas,
    calcular_relleno_cuadro,
    celdas_sin_resolver,
    detectar_cuadro_superficies,
    detectar_solicitudes,
)
from analyzer.cuadro_superficies_export import exportar_cuadro_relleno  # noqa: E402

fallos = []
comprobaciones = 0


def check(ok, etiqueta, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s%s" % ("OK  " if ok else "FALLO", etiqueta, ("  -> " + detalle) if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


class RoomFalso:
    """Mismo doble mínimo que `tests/test_cuadro_superficies.py`."""
    def __init__(self, label, area_m2):
        self.label = label
        self.area_m2 = area_m2


class UnitFalso:
    def __init__(self, name, rooms):
        self.name = name
        self.rooms = rooms


def cuadro_completo(existentes=None):
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
print("A. Caso completamente automático -- ninguna solicitud")
print("-" * 68)

rooms_auto = [
    RoomFalso("Salón/cocina", 20.0),
    RoomFalso("Dormitorio 1", 10.0),
    RoomFalso("Tendedero", 4.0),
    RoomFalso("Terraza 1", 5.0),
    RoomFalso("Terraza 2", 6.0),
    # Sin dormitorio 2/3, sin baño, sin aseo, sin pasillo, sin vestíbulo:
    # CERO_REAL en todos -- un hecho negativo, no una ambigüedad, así que
    # tampoco genera pregunta.
]
unit_auto = UnitFalso("VT-AUTO/1", rooms_auto)
# Las tres celdas que SIEMPRE serían NO_DISPONIBLE si estuvieran vacías ya
# vienen declaradas en el DXF (simulando un cuadro que un arquitecto ya
# rellenó a mano para esos tres campos) -- así el caso queda sin ninguna
# pregunta pendiente, que es justo lo que prueba esta sección.
cuadro_auto = cuadro_completo(existentes={
    "superficie_construida_cerrada": "45,00 m²",
    "superficie_construida_exterior": "10,00 m²",
    "numero_unidades": "4",
})
resultado_auto = calcular_relleno_cuadro(unit_auto, cuadro_auto, rooms_auto)

check(len(celdas_sin_resolver(resultado_auto)) == 0,
      "sin ningún campo BLOQUEADO/NO_DISPONIBLE",
      str([r.campo for r in celdas_sin_resolver(resultado_auto)]))

solicitudes_auto = detectar_solicitudes(resultado_auto, rooms_auto)
check(solicitudes_auto == [], "detectar_solicitudes() = [] -- nada que preguntar",
      str([s.id for s in solicitudes_auto]))

# Redundancia deliberada: ninguna celda queda con "N/D" como resultado final.
check(all(r.texto != "N/D" for r in resultado_auto),
      "ninguna celda quedó con N/D en el caso automático")


print()
print("B, C, D, E, F. `v2s.dxf` real")
print("-" * 68)

#: `v2s.dxf` es un plano real de un cliente: no está en el repositorio ni puede
#: estarlo. Se localiza con la variable de entorno `ARCHMUSE_DXF_V2S`. Sin ella
#: esta parte se salta, igual que antes — lo que ya no hay es la ruta personal
#: de nadie escrita en un repositorio público.
DXF_PATH = os.environ.get("ARCHMUSE_DXF_V2S", "")

if not os.path.exists(DXF_PATH):
    print("  (v2s.dxf no disponible (define ARCHMUSE_DXF_V2S con su ruta) -- secciones omitidas, mismo criterio que")
    print("   tests/test_cuadro_superficies.py)")
else:
    import ezdxf
    from analyzer import evaluator, parser

    doc = ezdxf.readfile(DXF_PATH)
    plano = parser.leer_plano(doc)
    advanced = evaluator.evaluate_advanced(plano.rooms, plano.unit_labels)
    unit_real = advanced.units[0]
    cuadro_real = detectar_cuadro_superficies(doc)
    resultado_real = calcular_relleno_cuadro(unit_real, cuadro_real, unit_real.rooms)
    por_campo_real = {r.campo: r for r in resultado_real}

    print()
    print("B. Exactamente las cuatro solicitudes indicadas por Pablo")
    print("-" * 68)

    solicitudes = detectar_solicitudes(resultado_real, unit_real.rooms)
    check(len(solicitudes) == 4, "detectar_solicitudes() devuelve exactamente 4", str(len(solicitudes)))

    ids = {s.id for s in solicitudes}
    check(ids == {
        "asignacion_exterior", "superficie_construida_cerrada",
        "superficie_construida_exterior", "numero_unidades",
    }, "y son exactamente esas cuatro -- ninguna otra (no salón, dormitorios, baño, "
       "aseo, pasillo, vestíbulo ni total útil interior)", str(ids))

    asignacion_sol = next(s for s in solicitudes if s.id == "asignacion_exterior")
    check(asignacion_sol.tipo == "asignacion", "la de espacios exteriores es tipo asignacion")
    check(set(asignacion_sol.campos) == {"tendedero", "terraza_1", "terraza_2"},
          "cubre los tres huecos (tendedero, terraza 1, terraza 2)", str(asignacion_sol.campos))
    candidatos = list(asignacion_sol.candidatos)
    check(len(candidatos) >= 2, "trae al menos dos geometrías candidatas reales", str(len(candidatos)))
    check(all(c.room_label and c.area_m2 > 0 for c in candidatos),
          "cada candidato trae nombre y superficie real (no vacíos)")
    check(all(isinstance(c.x, float) and isinstance(c.y, float) for c in candidatos),
          "cada candidato trae una posición (centroide) real")

    numericas = {s.id: s for s in solicitudes if s.tipo == "numerico"}
    check(set(numericas) == {"superficie_construida_cerrada", "superficie_construida_exterior", "numero_unidades"},
          "las tres solicitudes numéricas son exactamente esas")
    for campo_num, unidad_esperada in (
        ("superficie_construida_cerrada", "m²"), ("superficie_construida_exterior", "m²"),
        ("numero_unidades", "uds"),
    ):
        check(numericas[campo_num].unidad == unidad_esperada,
              "%s pide la unidad correcta (%s)" % (campo_num, unidad_esperada))

    # No debe preguntar por lo que ya se calcula solo.
    campos_solicitados = set()
    for s in solicitudes:
        campos_solicitados.update(s.campos)
    for campo_no_pedido in ("salon_cocina", "dormitorio_1", "dormitorio_2", "dormitorio_3",
                             "bano", "aseo", "pasillo", "vestibulo", "total_util_interior"):
        check(campo_no_pedido not in campos_solicitados,
              "no se pregunta por %s (ya se calcula solo)" % campo_no_pedido)

    print()
    print("C y D. Tras responder: 18 celdas con valor, cero N/D, totales correctos")
    print("-" * 68)

    respuestas = [
        {
            "tipo": "asignacion", "solicitud_id": "asignacion_exterior",
            "asignaciones": {
                "tendedero": candidatos[0].id,
                "terraza_1": candidatos[1].id,
                "terraza_2": None,  # el arquitecto confirma que no hay una segunda terraza real
            },
        },
        {"tipo": "numerico", "campo": "superficie_construida_cerrada", "valor": 70.5},
        {"tipo": "numerico", "campo": "superficie_construida_exterior", "valor": 12.0},
        {"tipo": "numerico", "campo": "numero_unidades", "valor": 3},
    ]
    resultado_final = aplicar_respuestas(resultado_real, unit_real.rooms, respuestas)
    por_campo_final = {r.campo: r for r in resultado_final}

    check(len(resultado_final) == 18, "las 18 celdas siguen presentes", str(len(resultado_final)))
    check(len(celdas_sin_resolver(resultado_final)) == 0,
          "ninguna celda queda BLOQUEADO/NO_DISPONIBLE tras responder",
          str([r.campo for r in celdas_sin_resolver(resultado_final)]))
    check(all(r.texto != "N/D" for r in resultado_final),
          "ninguna celda contiene N/D", str([r.campo for r in resultado_final if r.texto == "N/D"]))

    check(por_campo_final["tendedero"].declarado_por_usuario is True,
          "tendedero queda marcado declarado_por_usuario=True")
    check(por_campo_final["terraza_1"].declarado_por_usuario is True,
          "terraza_1 queda marcado declarado_por_usuario=True")
    check(por_campo_final["terraza_2"].estado == CERO_REAL and por_campo_final["terraza_2"].declarado_por_usuario is True,
          "terraza_2 (sin asignar) -> CERO_REAL declarado, no un CERO_REAL automático",
          por_campo_final["terraza_2"].texto)
    check(por_campo_final["superficie_construida_cerrada"].texto == "70,50 m²",
          "superficie_construida_cerrada = 70,50 m² (declarada)", por_campo_final["superficie_construida_cerrada"].texto)
    check(por_campo_final["numero_unidades"].texto == "3",
          "numero_unidades = 3, sin decimales ni unidad", por_campo_final["numero_unidades"].texto)

    esperado_exterior = candidatos[0].area_m2 + candidatos[1].area_m2 + 0.0
    texto_exterior_esperado = ("%.2f m²" % esperado_exterior).replace(".", ",")
    check(por_campo_final["total_util_exterior"].texto == texto_exterior_esperado,
          "total_util_exterior se recalcula = %s" % texto_exterior_esperado,
          por_campo_final["total_util_exterior"].texto)

    interior_val = float(por_campo_final["total_util_interior"].texto.replace(" m²", "").replace(",", "."))
    exterior_val = float(por_campo_final["total_util_exterior"].texto.replace(" m²", "").replace(",", "."))
    texto_total_esperado = ("%.2f m²" % (interior_val + exterior_val)).replace(".", ",")
    check(por_campo_final["total_util"].texto == texto_total_esperado,
          "total_util = total_util_interior + total_util_exterior recalculado",
          por_campo_final["total_util"].texto)

    print()
    print("E. El DXF original conserva el mismo hash tras exportar la versión completa")
    print("-" * 68)

    with open(DXF_PATH, "rb") as f:
        hash_antes = hashlib.sha256(f.read()).hexdigest()

    tmp_dir = tempfile.mkdtemp(prefix="archmuse_test_fase5_")
    try:
        destino = os.path.join(tmp_dir, "v2s_completo.dxf")
        resultado_export = exportar_cuadro_relleno(DXF_PATH, destino, respuestas=respuestas)

        check(resultado_export.campos_sin_resolver == [],
              "exportar_cuadro_relleno: campos_sin_resolver vacío -- cuadro completo de verdad",
              str(resultado_export.campos_sin_resolver))
        check(resultado_export.reabierta_sin_errores is True, "la copia se reabre sin errores de audit")

        with open(DXF_PATH, "rb") as f:
            hash_despues = hashlib.sha256(f.read()).hexdigest()
        check(hash_despues == hash_antes, "v2s.dxf en disco NO ha cambiado (mismo sha256)")

        doc_final = ezdxf.readfile(destino)
        mtexts_cuadro = doc_final.modelspace().query("MTEXT[layer=='00 CUADROS']")
        n_nd = sum(1 for m in mtexts_cuadro if m.text == "N/D")
        check(n_nd == 0, "el DXF exportado no tiene ningún MTEXT con N/D en el cuadro", "%d" % n_nd)
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print()
    print("F. Respuesta contradictoria con una celda preexistente -> bloquea, explica, no sobrescribe")
    print("-" * 68)

    vt_real = por_campo_real["vivienda_tipo"]
    check(vt_real.preexistente is True and vt_real.texto == "VT1 /3",
          "vivienda_tipo es preexistente en v2s.dxf (precondición del caso F)", vt_real.texto)

    # Respuesta numérica para un campo que en el DXF real YA tiene texto
    # (nunca se pregunta esto en el flujo normal -- se ejerce aquí la red de
    # seguridad de `_con_conflicto_o` con un conflicto real, no fabricado).
    respuesta_conflicto = {"tipo": "numerico", "campo": "vivienda_tipo", "valor": 12.34}
    resultado_conflicto = aplicar_respuestas(resultado_real, unit_real.rooms, [respuesta_conflicto])
    vt_conflicto = [r for r in resultado_conflicto if r.campo == "vivienda_tipo"][0]

    check(vt_conflicto.estado == BLOQUEADO, "vivienda_tipo queda BLOQUEADO ante la contradicción")
    check("Conflicto" in (vt_conflicto.motivo or ""), "el motivo explica que es un conflicto",
          vt_conflicto.motivo)
    check(vt_conflicto.texto == "VT1 /3", "el texto que queda es el ORIGINAL del DXF, no el declarado",
          vt_conflicto.texto)
    check(vt_conflicto.escribir is False, "escribir=False -- tampoco aquí se toca la celda")

    # Y ese conflicto bloquea también la descarga completa (no solo la
    # celda en memoria): `exportar_cuadro_relleno` lo refleja en
    # `campos_sin_resolver`/`detalles_sin_resolver`.
    tmp_dir2 = tempfile.mkdtemp(prefix="archmuse_test_fase5_conflicto_")
    try:
        destino2 = os.path.join(tmp_dir2, "v2s_conflicto.dxf")
        resultado_export_conflicto = exportar_cuadro_relleno(
            DXF_PATH, destino2, respuestas=[respuesta_conflicto],
        )
        check("vivienda_tipo" in resultado_export_conflicto.campos_sin_resolver,
              "exportar_cuadro_relleno: vivienda_tipo queda en campos_sin_resolver -- descarga bloqueada",
              str(resultado_export_conflicto.campos_sin_resolver))
        detalle_vt = next(
            (d for d in resultado_export_conflicto.detalles_sin_resolver if d["campo"] == "vivienda_tipo"), None,
        )
        check(detalle_vt is not None and "Conflicto" in (detalle_vt.get("motivo") or ""),
              "y el detalle trae el motivo del conflicto, explicado",
              detalle_vt.get("motivo") if detalle_vt else None)
    finally:
        import shutil
        shutil.rmtree(tmp_dir2, ignore_errors=True)


print()
print("=" * 68)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
