# -*- coding: utf-8 -*-
"""Diagnostico de ingesta: que hay dentro de un DXF y por que ArchMuse lo
entiende o no.

Tarea 1 del PRD `docs/prd/2026-08-02-ingesta-de-dxf-ajenos.md`. Existe para
convertir seis fallos SUPUESTOS en fallos MEDIDOS, antes de escribir una sola
linea de solucion.

    python herramientas/diagnostico_dxf.py ruta/al/plano.dxf
    python herramientas/diagnostico_dxf.py carpeta/con/dxf --csv salida.csv

Deliberadamente NO importa nada de `analyzer/`. Si usara `parser.py` para
mirar el archivo, heredaria las mismas suposiciones que estamos intentando
medir: preguntaria "cuantas habitaciones hay en la capa 00 areas" en vez de
"que capas hay y cual parece contener habitaciones". Solo depende de ezdxf.

Tampoco llama a la IA ni escribe en `~/.archmuse/archmuse.db`: se puede
ejecutar sin ANTHROPIC_API_KEY configurada.

La salida es ASCII a proposito, como el resto de scripts del proyecto: la
consola de Windows no acepta acentos de forma fiable.
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import sys
import traceback

try:
    import ezdxf
except ImportError:  # pragma: no cover - entorno sin dependencias
    print("Falta ezdxf. Activa el venv del proyecto:  venv\\Scripts\\activate")
    sys.exit(2)


# Codigos de $INSUNITS segun la especificacion DXF. Solo se nombran los que
# pueden aparecer de verdad en un plano de arquitectura; el resto se muestran
# por su numero.
UNIDADES = {
    0: "sin especificar",
    1: "pulgadas",
    2: "pies",
    3: "millas",
    4: "milimetros",
    5: "centimetros",
    6: "metros",
    7: "kilometros",
    10: "yardas",
    14: "decimetros",
}

# Factor de conversion a metros de las unidades que un plano de arquitectura
# puede usar de forma razonable. El diagnostico prueba las cuatro contra el
# tamano real de los poligonos (ver `hipotesis_de_escala`).
FACTORES_A_METRO = [("metros", 1.0), ("decimetros", 0.1), ("centimetros", 0.01), ("milimetros", 0.001)]

# Rango en m2 dentro del cual una habitacion de vivienda es plausible. Un aseo
# baja de 3 m2 y un salon-cocina-comedor grande pasa de 60, asi que el rango es
# deliberadamente ancho: sirve para descartar ordenes de magnitud absurdos
# (0,00002 m2 o 24.000.000 m2), no para validar una habitacion concreta.
#
# DEBEN COINCIDIR con `analyzer/escala.py`, que es quien decide de verdad. Se
# duplican en vez de importarse por la razon del docstring del modulo -- si el
# diagnostico importara de analyzer/ heredaria las suposiciones que mide -- y
# `tests/test_escala.py` comprueba que los dos juegos de numeros son iguales,
# porque medir con una regla y publicar con otra seria una trampa.
AREA_PLAUSIBLE_MIN = 2.0
AREA_PLAUSIBLE_MAX = 150.0

# Por debajo de esta cantidad de poligonos en una capa, la mediana no es fiable
# y no se propone ninguna escala.
MINIMO_POLIGONOS = 3

# Igual que `parser.UNIT_LABEL_PATTERN`. Se repite aqui a proposito, para no
# importar de `analyzer/` (ver docstring del modulo).
PATRON_VIVIENDA = re.compile(r"^VT\s*\d+", re.IGNORECASE)

# Tope de anidamiento al descender por referencias de bloque. Tres niveles
# cubren el montaje habitual (planta -> vivienda -> mobiliario) sin riesgo de
# quedarse dando vueltas en un DXF con bloques que se referencian entre si.
PROFUNDIDAD_MAX_BLOQUES = 3

LAYER_ARCHMUSE = "00 areas"


# ---------------------------------------------------------------------------
# Geometria (shoelace, sin shapely: solo hace falta el area)
# ---------------------------------------------------------------------------

def area_poligono(puntos):
    """Area absoluta del poligono por la formula del cordon de zapato, en
    unidades del dibujo al cuadrado."""
    if len(puntos) < 3:
        return 0.0
    total = 0.0
    for i in range(len(puntos)):
        x1, y1 = puntos[i]
        x2, y2 = puntos[(i + 1) % len(puntos)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def puntos_de(entidad):
    """Vertices (x, y) de una LWPOLYLINE o POLYLINE clasica. Lista vacia para
    cualquier otro tipo."""
    tipo = entidad.dxftype()
    try:
        if tipo == "LWPOLYLINE":
            return [(p[0], p[1]) for p in entidad.get_points()]
        if tipo == "POLYLINE":
            return [(v.dxf.location.x, v.dxf.location.y) for v in entidad.vertices]
    except Exception:  # noqa: BLE001 - DXF ajeno: cualquier entidad puede venir mal formada
        return []
    return []


def esta_cerrada(entidad):
    tipo = entidad.dxftype()
    try:
        if tipo == "LWPOLYLINE":
            return bool(entidad.closed)
        if tipo == "POLYLINE":
            return bool(entidad.is_closed)
    except Exception:  # noqa: BLE001
        return False
    return False


def mediana(valores):
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    n = len(ordenados)
    if n % 2:
        return ordenados[n // 2]
    return (ordenados[n // 2 - 1] + ordenados[n // 2]) / 2.0


# ---------------------------------------------------------------------------
# Recorrido del documento
# ---------------------------------------------------------------------------

def recoger_poligonos(entidades, destino, capa_insert=None):
    """Acumula en `destino` (dict capa -> lista de areas) el area de cada
    polilinea CERRADA de `entidades`.

    `capa_insert`, cuando viene, es la capa de la referencia de bloque que
    contiene estas entidades: las que esten en la capa "0" la heredan.
    """
    for entidad in entidades:
        if entidad.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
            continue
        if not esta_cerrada(entidad):
            continue
        puntos = puntos_de(entidad)
        if len(puntos) < 3:
            continue
        try:
            capa = entidad.dxf.layer
        except Exception:  # noqa: BLE001
            capa = "(sin capa)"
        if capa_insert is not None and capa == "0":
            capa = capa_insert
        destino.setdefault(capa, []).append(area_poligono(puntos))


def recoger_textos(entidades, destino):
    """Acumula en `destino` (dict tipo -> lista de textos) el contenido de
    cada MTEXT y TEXT."""
    for entidad in entidades:
        tipo = entidad.dxftype()
        try:
            if tipo == "MTEXT":
                texto = entidad.plain_text().strip()
            elif tipo == "TEXT":
                texto = str(entidad.dxf.text).strip()
            else:
                continue
        except Exception:  # noqa: BLE001
            continue
        if texto:
            destino.setdefault(tipo, []).append(texto)


def descender_bloques(entidades, poligonos, textos, hatches, profundidad=0, capa_insert=None):
    """Repite la recogida dentro de cada referencia de bloque (INSERT).

    Desde la tarea 8 del PRD, `analyzer/parser.py` tambien entra en los
    bloques, asi que esto ya no mide algo que se pierde: mide cuanto entra por
    esta via. Se sigue contando aparte porque saber que proporcion de un plano
    vive dentro de bloques es informacion util del archivo.

    Se resuelve la herencia de la capa "0" igual que `parser._capa_efectiva`:
    una entidad en capa 0 dentro de un bloque toma la capa del INSERT. Sin eso
    el diagnostico atribuiria a la capa "0" habitaciones que ArchMuse si
    atribuye bien, y la medicion no coincidiria con la realidad.
    """
    if profundidad >= PROFUNDIDAD_MAX_BLOQUES:
        return
    for insert in entidades:
        if insert.dxftype() != "INSERT":
            continue
        try:
            propia = insert.dxf.layer
        except AttributeError:
            propia = "0"
        capa = capa_insert if (capa_insert is not None and propia == "0") else propia
        try:
            hijos = list(insert.virtual_entities())
        except Exception:  # noqa: BLE001 - bloque roto o referencia circular
            continue
        recoger_poligonos(hijos, poligonos, capa)
        recoger_textos(hijos, textos)
        for hijo in hijos:
            if hijo.dxftype() == "HATCH":
                try:
                    hatches[hijo.dxf.layer] = hatches.get(hijo.dxf.layer, 0) + 1
                except Exception:  # noqa: BLE001
                    pass
        descender_bloques(hijos, poligonos, textos, hatches, profundidad + 1, capa)


def hipotesis_de_escala(area_mediana, n_poligonos=None):
    """Que unidades de dibujo harian que `area_mediana` fuese una habitacion
    plausible. Devuelve la lista de nombres compatibles.

    Es el prototipo de la comprobacion de plausibilidad de la tarea 3 del PRD:
    `$INSUNITS` esta a 0 con mucha frecuencia, y a veces esta directamente mal,
    asi que la unica forma de no equivocarse en silencio es contrastarlo con el
    tamano real de lo dibujado.
    """
    if area_mediana <= 0:
        return []
    if n_poligonos is not None and n_poligonos < MINIMO_POLIGONOS:
        return []
    compatibles = []
    for nombre, factor in FACTORES_A_METRO:
        en_m2 = area_mediana * factor * factor
        if AREA_PLAUSIBLE_MIN <= en_m2 <= AREA_PLAUSIBLE_MAX:
            compatibles.append(nombre)
    return compatibles


def analizar_dxf(ruta):
    """Todo lo que se puede saber de un DXF sin suponer nada sobre como se
    dibujo. Nunca lanza: un archivo ilegible devuelve un informe con `error`
    relleno, para que un lote de 10 archivos no se detenga por culpa de uno."""
    informe = {
        "archivo": os.path.basename(ruta),
        "ruta": ruta,
        "mb": round(os.path.getsize(ruta) / (1024.0 * 1024.0), 1),
        "error": "",
        "unidades_codigo": None,
        "unidades": "",
        "capas_totales": 0,
        "capas_candidatas": [],
        "poligonos_modelspace": 0,
        "poligonos_en_bloques": 0,
        "inserts": 0,
        "mtext": 0,
        "text": 0,
        "etiquetas_vt": 0,
        "hatches": 0,
        "tiene_capa_archmuse": False,
        "area_mediana": 0.0,
        "escalas_compatibles": [],
    }

    try:
        doc = ezdxf.readfile(ruta)
    except Exception as exc:  # noqa: BLE001 - DXF arbitrario: danado, version rara, no-DXF
        informe["error"] = "%s: %s" % (type(exc).__name__, exc)
        return informe

    try:
        codigo = int(doc.header.get("$INSUNITS", 0) or 0)
    except Exception:  # noqa: BLE001
        codigo = 0
    informe["unidades_codigo"] = codigo
    informe["unidades"] = UNIDADES.get(codigo, "codigo %d" % codigo)

    try:
        informe["capas_totales"] = len(doc.layers)
        informe["tiene_capa_archmuse"] = any(
            capa.dxf.name.strip().lower() == LAYER_ARCHMUSE for capa in doc.layers
        )
    except Exception:  # noqa: BLE001
        pass

    msp = doc.modelspace()
    entidades = list(msp)

    poligonos_msp = {}
    textos_msp = {}
    hatches = {}
    recoger_poligonos(entidades, poligonos_msp)
    recoger_textos(entidades, textos_msp)
    for entidad in entidades:
        if entidad.dxftype() == "HATCH":
            try:
                hatches[entidad.dxf.layer] = hatches.get(entidad.dxf.layer, 0) + 1
            except Exception:  # noqa: BLE001
                pass

    # Los poligonos de dentro de bloques se cuentan por separado: son los que
    # ArchMuse no ve hoy, y el objetivo es medir exactamente cuantos son.
    poligonos_blq = {}
    textos_blq = {}
    informe["inserts"] = sum(1 for e in entidades if e.dxftype() == "INSERT")
    descender_bloques(entidades, poligonos_blq, textos_blq, hatches)

    informe["poligonos_modelspace"] = sum(len(v) for v in poligonos_msp.values())
    informe["poligonos_en_bloques"] = sum(len(v) for v in poligonos_blq.values())
    informe["hatches"] = sum(hatches.values())

    todos_textos = []
    for origen in (textos_msp, textos_blq):
        for tipo, lista in origen.items():
            if tipo == "MTEXT":
                informe["mtext"] += len(lista)
            elif tipo == "TEXT":
                informe["text"] += len(lista)
            todos_textos.extend(lista)
    informe["etiquetas_vt"] = sum(1 for t in todos_textos if PATRON_VIVIENDA.match(t))

    # Capas candidatas: las que contienen polilineas cerradas, de mas a menos.
    # No se filtra por nombre a proposito -- el nombre es justo lo que no se
    # puede dar por supuesto.
    combinado = {}
    for capa, areas in poligonos_msp.items():
        combinado.setdefault(capa, {"msp": [], "blq": []})["msp"] = areas
    for capa, areas in poligonos_blq.items():
        combinado.setdefault(capa, {"msp": [], "blq": []})["blq"] = areas

    candidatas = []
    for capa, datos in combinado.items():
        areas = list(datos["msp"]) + list(datos["blq"])
        med = mediana(areas)
        candidatas.append({
            "capa": capa,
            "total": len(areas),
            "en_modelspace": len(datos["msp"]),
            "en_bloques": len(datos["blq"]),
            "area_mediana": med,
            "escalas": hipotesis_de_escala(med, len(areas)),
        })
    candidatas.sort(key=lambda c: -c["total"])
    informe["capas_candidatas"] = candidatas

    if candidatas:
        informe["area_mediana"] = candidatas[0]["area_mediana"]
        informe["escalas_compatibles"] = candidatas[0]["escalas"]

    return informe


# ---------------------------------------------------------------------------
# Salida
# ---------------------------------------------------------------------------

def veredicto(informe):
    """Una linea: por que ArchMuse entenderia o no este archivo HOY, con el
    codigo tal cual esta. Es la conclusion que se lee primero."""
    if informe["error"]:
        return "NO ABRE", "el archivo no se puede leer"

    candidatas = informe["capas_candidatas"]
    if not candidatas:
        return "NO", "no hay ninguna polilinea cerrada en todo el archivo"

    archmuse = [c for c in candidatas if c["capa"].strip().lower() == LAYER_ARCHMUSE]
    if not archmuse:
        return "NO", "no existe la capa '%s' (la mejor candidata es '%s', con %d)" % (
            LAYER_ARCHMUSE, candidatas[0]["capa"], candidatas[0]["total"])

    # Aqui habia un "NO" cuando todas las polilineas estaban dentro de bloques,
    # y un aviso cuando solo algunas. Los dos se retiran con la tarea 8: desde
    # que `parser._recorrer_plano` atraviesa los INSERT, estar dentro de un
    # bloque dejo de ser un problema. El recuento se sigue mostrando en la
    # ficha porque saber que parte del plano vive en bloques es informacion
    # util, pero ya no penaliza.
    capa = archmuse[0]

    avisos = []
    if capa["escalas"] and "metros" not in capa["escalas"]:
        avisos.append("la escala NO parece estar en metros, sino en %s" % " o ".join(capa["escalas"]))
    elif not capa["escalas"]:
        avisos.append("el tamano de los poligonos no encaja con ninguna escala razonable")
    # Aqui habia un aviso por rotular con TEXT en vez de MTEXT. Se retira con
    # la tarea 7 del PRD: `parser.extract_labels` lee los dos, asi que ya no es
    # un problema. Los recuentos se siguen mostrando porque son informacion
    # util del archivo, no un defecto.
    if informe["mtext"] == 0 and informe["text"] == 0:
        avisos.append("no hay ningun rotulo: las estancias saldran sin nombre")
    if informe["etiquetas_vt"] == 0:
        avisos.append("sin etiquetas VT: agrupacion por proximidad, mas fragil")

    if avisos:
        return "PARCIAL", "; ".join(avisos)
    return "SI", "%d habitaciones en '%s'%s" % (
        capa["total"], LAYER_ARCHMUSE,
        " (%d dentro de bloques)" % capa["en_bloques"] if capa["en_bloques"] else "")


def imprimir(informe):
    print("=" * 72)
    print("%s   (%s MB)" % (informe["archivo"], informe["mb"]))
    print("=" * 72)

    if informe["error"]:
        print("  ERROR: %s" % informe["error"])
        print()
        return

    print("  $INSUNITS ........ %s (codigo %s)" % (informe["unidades"], informe["unidades_codigo"]))
    print("  capas ............ %d en total" % informe["capas_totales"])
    print("  polilineas ....... %d en modelspace, %d dentro de bloques (%d INSERT)" % (
        informe["poligonos_modelspace"], informe["poligonos_en_bloques"], informe["inserts"]))
    print("  rotulos .......... %d MTEXT, %d TEXT" % (informe["mtext"], informe["text"]))
    print("  etiquetas VT ..... %d" % informe["etiquetas_vt"])
    print("  HATCH ............ %d" % informe["hatches"])

    if informe["capas_candidatas"]:
        print()
        print("  capas con polilineas cerradas (de mas a menos):")
        print("    %-30s %6s %6s %6s   %-12s %s" % (
            "capa", "total", "msp", "bloq", "area med.", "escala compatible"))
        for c in informe["capas_candidatas"][:8]:
            marca = " *" if c["capa"].strip().lower() == LAYER_ARCHMUSE else "  "
            escalas = ", ".join(c["escalas"]) if c["escalas"] else "ninguna"
            print("  %s%-30s %6d %6d %6d   %-12s %s" % (
                marca, c["capa"][:30], c["total"], c["en_modelspace"], c["en_bloques"],
                "%.2f" % c["area_mediana"], escalas))
        if len(informe["capas_candidatas"]) > 8:
            print("    ... y %d capas mas" % (len(informe["capas_candidatas"]) - 8))
        print("    (* = la capa que ArchMuse busca hoy; 'area med.' en unidades de dibujo al cuadrado)")

    estado, motivo = veredicto(informe)
    print()
    print("  ARCHMUSE HOY: %s -- %s" % (estado, motivo))
    print()


CAMPOS_CSV = [
    "archivo", "mb", "error", "unidades", "capas_totales", "poligonos_modelspace",
    "poligonos_en_bloques", "inserts", "mtext", "text", "etiquetas_vt", "hatches",
    "tiene_capa_archmuse", "mejor_capa", "mejor_capa_total", "area_mediana",
    "escalas_compatibles", "veredicto", "motivo",
]


def fila_csv(informe):
    estado, motivo = veredicto(informe)
    mejor = informe["capas_candidatas"][0] if informe["capas_candidatas"] else None
    return {
        "archivo": informe["archivo"],
        "mb": informe["mb"],
        "error": informe["error"],
        "unidades": informe["unidades"],
        "capas_totales": informe["capas_totales"],
        "poligonos_modelspace": informe["poligonos_modelspace"],
        "poligonos_en_bloques": informe["poligonos_en_bloques"],
        "inserts": informe["inserts"],
        "mtext": informe["mtext"],
        "text": informe["text"],
        "etiquetas_vt": informe["etiquetas_vt"],
        "hatches": informe["hatches"],
        "tiene_capa_archmuse": "si" if informe["tiene_capa_archmuse"] else "no",
        "mejor_capa": mejor["capa"] if mejor else "",
        "mejor_capa_total": mejor["total"] if mejor else 0,
        "area_mediana": round(informe["area_mediana"], 3),
        "escalas_compatibles": " ".join(informe["escalas_compatibles"]),
        "veredicto": estado,
        "motivo": motivo,
    }


def resumen(informes):
    print("=" * 72)
    print("RESUMEN DE %d ARCHIVO(S)" % len(informes))
    print("=" * 72)
    print("  %-34s %-9s %s" % ("archivo", "archmuse", "motivo"))
    conteo = {}
    for inf in informes:
        estado, motivo = veredicto(inf)
        conteo[estado] = conteo.get(estado, 0) + 1
        print("  %-34s %-9s %s" % (inf["archivo"][:34], estado, motivo[:60]))
    print()
    partes = ["%s: %d" % (k, v) for k, v in sorted(conteo.items())]
    print("  " + "   ".join(partes))
    total = len(informes)
    ok = conteo.get("SI", 0)
    print()
    print("  LA CIFRA QUE IMPORTA: %d de %d se analizarian correctamente sin tocar nada." % (ok, total))
    print()


def rutas_dxf(objetivo):
    if os.path.isdir(objetivo):
        encontrados = []
        for patron in ("*.dxf", "*.DXF"):
            encontrados.extend(glob.glob(os.path.join(objetivo, "**", patron), recursive=True))
        return sorted(set(encontrados))
    return [objetivo] if os.path.exists(objetivo) else []


def main():
    parser = argparse.ArgumentParser(
        description="Diagnostico de ingesta DXF (tarea 1 del PRD de ingesta de DXF ajenos).")
    parser.add_argument("objetivo", help="archivo .dxf o carpeta que los contenga (busca en subcarpetas)")
    parser.add_argument("--csv", help="ademas, vuelca una fila por archivo a este CSV")
    args = parser.parse_args()

    rutas = rutas_dxf(args.objetivo)
    if not rutas:
        print("No se ha encontrado ningun .dxf en: %s" % args.objetivo)
        return 1

    informes = []
    for i, ruta in enumerate(rutas, 1):
        print("[%d/%d] leyendo %s ..." % (i, len(rutas), os.path.basename(ruta)))
        try:
            informes.append(analizar_dxf(ruta))
        except Exception:  # noqa: BLE001 - un archivo raro no puede tumbar el lote
            traceback.print_exc()
            informes.append({
                "archivo": os.path.basename(ruta), "ruta": ruta, "mb": 0, "capas_candidatas": [],
                "error": "fallo inesperado del diagnostico (traza arriba)",
                "unidades_codigo": None, "unidades": "", "capas_totales": 0,
                "poligonos_modelspace": 0, "poligonos_en_bloques": 0, "inserts": 0,
                "mtext": 0, "text": 0, "etiquetas_vt": 0, "hatches": 0,
                "tiene_capa_archmuse": False, "area_mediana": 0.0, "escalas_compatibles": [],
            })
    print()

    for informe in informes:
        imprimir(informe)

    if len(informes) > 1:
        resumen(informes)

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            escritor = csv.DictWriter(fh, fieldnames=CAMPOS_CSV)
            escritor.writeheader()
            for informe in informes:
                escritor.writerow(fila_csv(informe))
        print("CSV escrito en: %s" % args.csv)

    return 0


if __name__ == "__main__":
    sys.exit(main())
