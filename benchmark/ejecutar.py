# -*- coding: utf-8 -*-
"""Banco de compatibilidad externo: ArchMuse contra planos que no son del estudio.

    venv\\Scripts\\python.exe benchmark\\ejecutar.py C:\\ArchMuse-Benchmark\\planos

Lee cada DXF o DWG de la carpeta **tal cual**, con el motor de siempre y sin
ajustes por plano, y anota qué sale. Si el plano ya trae su cuadro de superficies
relleno, cada cifra de ArchMuse se compara con la de ese cuadro. Ver
`benchmark/README.md`.

**Qué no hace, y no puede hacer.** Mide el motor —lector, medición y reparto—
sobre el fichero entero. No mide la integración con AutoCAD: el comando lee el
dibujo con `ssget` y manda la geometría, y lo que se pierda en ese camino no sale
aquí (`C-7`).

**Privacidad.** Los planos no entran al repositorio: la carpeta tiene que estar
fuera de él, y la salida va a `benchmark/resultados/`, que git ignora. Cada plano
se nombra `plano-01`, `plano-02`…; la correspondencia con su fichero sólo existe
en `resultados/correspondencia.json`.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from analyzer import cuadro_superficies as cs  # noqa: E402
from analyzer import evaluator, medicion, parser  # noqa: E402
from analyzer import plantilla_cuadro as pc  # noqa: E402
from analyzer import reparto_cuadro as rc  # noqa: E402
from analyzer.texto_dxf import decodificar_escapes  # noqa: E402

SALIDA_POR_DEFECTO = os.path.join(RAIZ, "benchmark", "resultados")

#: Dos cifras coinciden si no se separan más de un céntimo de metro cuadrado.
TOLERANCIA_M2 = 0.01

COINCIDENCIA = "coincidencia"
MISMATCH = "MISMATCH"
VACIO_CON_MOTIVO = "ArchMuse vacío con motivo"
REFERENCIA_INEXISTENTE = "referencia inexistente"

#: Las únicas clases que admite un MISMATCH. Las pone una persona en
#: `clasificacion.csv`; el banco no adivina ninguna.
REDONDEO = "redondeo"
CUADRO_DESACTUALIZADO = "cuadro desactualizado"
ERROR_DE_ARCHMUSE = "error de ArchMuse"
PENDIENTE_DE_DETERMINAR = "pendiente de determinar"
CLASES_DE_MISMATCH = (REDONDEO, CUADRO_DESACTUALIZADO, ERROR_DE_ARCHMUSE, PENDIENTE_DE_DETERMINAR)

PASS = "PASS"
PARTIAL = "PARTIAL"
FAIL = "FAIL"
PENDIENTE = "PENDIENTE DE REVISIÓN"
SIN_REFERENCIA = "SIN REFERENCIA"
RESULTADOS = (PASS, PARTIAL, FAIL, PENDIENTE, SIN_REFERENCIA)

#: Los campos del cuadro que son una superficie. `numero_unidades` y
#: `vivienda_tipo` no se comparan.
CAMPOS_COMPARABLES = cs.CAMPOS_SUMANDOS_UTIL + cs.CAMPOS_TOTAL_UTIL + cs.CAMPOS_CONSTRUIDA

COLUMNAS = ("plano", "formato", "viviendas_detectadas", "viviendas_con_cuadro",
            "viviendas_emparejadas", "viviendas_correctas", "estancias", "superficies",
            "campos_vacios", "preguntas", "cifras_comparadas", "coincidencias", "mismatches",
            "vacios_con_motivo", "referencias_inexistentes", "errores", "tiempo_s",
            "tiempo_conversion_s", "resultado", "motivo")


class CarpetaNoPermitida(ValueError):
    """Una carpeta de planos o de resultados que podría acabar en git."""


# ---------------------------------------------------------------------------
# Cifras
# ---------------------------------------------------------------------------

_CIFRA = re.compile(r"^\s*(\d+)(?:[.,](\d+))?\s*(?:m\s*(?:2|\u00b2|\^2))?\s*$", re.IGNORECASE)


def cifra_de_referencia(texto: Optional[str]) -> Optional[float]:
    """La superficie escrita a mano en su cuadro: «23.24m²», «8,53 m2», «3.16».
    `None` si el texto no es sólo una cifra (celda vacía, «-», «N/D»…)."""
    m = _CIFRA.match(decodificar_escapes(texto or ""))
    if not m:
        return None
    return float("%s.%s" % (m.group(1), m.group(2) or "0"))


def coinciden(una: float, otra: float) -> bool:
    return round(abs(una - otra), 6) <= TOLERANCIA_M2


# ---------------------------------------------------------------------------
# Carpetas, identificadores y clasificación
# ---------------------------------------------------------------------------

def _dentro_de(ruta: str, carpeta: str) -> bool:
    ruta, carpeta = os.path.normcase(os.path.abspath(ruta)), os.path.normcase(os.path.abspath(carpeta))
    return ruta == carpeta or ruta.startswith(carpeta.rstrip("\\/") + os.sep)


def comprobar_carpetas(planos: str, salida: str) -> None:
    if not os.path.isdir(planos):
        raise CarpetaNoPermitida("no existe la carpeta de planos: %s" % planos)
    if _dentro_de(planos, RAIZ):
        raise CarpetaNoPermitida("la carpeta de planos está dentro del repositorio: los planos de "
                                 "terceros no pueden entrar en git. Ponlos fuera.")
    if _dentro_de(salida, RAIZ) and not _dentro_de(salida, SALIDA_POR_DEFECTO):
        raise CarpetaNoPermitida("dentro del repositorio, los resultados sólo pueden ir a "
                                 "benchmark/resultados/, que git ignora.")


def planos_de(carpeta: str) -> List[str]:
    return sorted(os.path.join(carpeta, n) for n in os.listdir(carpeta)
                  if n.lower().endswith((".dxf", ".dwg"))
                  and os.path.isfile(os.path.join(carpeta, n)))


def _huella(ruta: str) -> str:
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def asignar_ids(rutas: List[str], salida: str) -> Dict[str, str]:
    """`plano-NN` por contenido, estable entre ejecuciones: añadir un plano no
    cambia el id de los demás, y la clasificación de un MISMATCH sigue en su sitio."""
    fichero = os.path.join(salida, "correspondencia.json")
    try:
        with open(fichero, encoding="utf-8") as f:
            guardada = json.load(f)
    except (OSError, ValueError):
        guardada = {}
    usados = {v["id"] for v in guardada.values()}
    ids = {}
    for ruta in rutas:
        huella = _huella(ruta)
        if huella not in guardada:
            n = 1
            while "plano-%02d" % n in usados:
                n += 1
            guardada[huella] = {"id": "plano-%02d" % n, "fichero": os.path.basename(ruta)}
            usados.add("plano-%02d" % n)
        ids[ruta] = guardada[huella]["id"]
    os.makedirs(salida, exist_ok=True)
    with open(fichero, "w", encoding="utf-8") as f:
        json.dump(guardada, f, ensure_ascii=False, indent=1)
    return ids


def leer_clasificacion(ruta: Optional[str]) -> Dict[Tuple[str, str, str], Tuple[str, str]]:
    """`(plano, vivienda, campo) -> (clase, nota)`. Una clase que no sea una de las
    cuatro cuenta como sin clasificar: nunca asciende a explicada."""
    if not ruta or not os.path.isfile(ruta):
        return {}
    clasificacion = {}
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            clase = (fila.get("clase") or "").strip()
            if clase in CLASES_DE_MISMATCH:
                clave = tuple((fila.get(k) or "").strip() for k in ("plano", "vivienda", "campo"))
                clasificacion[clave] = (clase, (fila.get("nota") or "").strip())
    return clasificacion


# ---------------------------------------------------------------------------
# DWG -> DXF, fuera del repositorio
# ---------------------------------------------------------------------------

def buscar_conversor() -> Optional[Tuple[str, str]]:
    """`("oda" | "accoreconsole", ruta)`, o `None`."""
    for tipo, variable, patron in (
            ("oda", "ARCHMUSE_ODA", r"C:\Program Files\ODA\ODAFileConverter*\ODAFileConverter.exe"),
            ("accoreconsole", "ARCHMUSE_ACCORECONSOLE",
             r"C:\Program Files\Autodesk\AutoCAD *\accoreconsole.exe")):
        ruta = os.environ.get(variable)
        if ruta and os.path.isfile(ruta):
            return tipo, ruta
        encontrados = sorted(glob.glob(patron))
        if encontrados:
            return tipo, encontrados[-1]
    return None


def convertir_dwg(ruta: str, temporal: str, conversor: Optional[Tuple[str, str]],
                  limite_s: int = 600) -> Tuple[Optional[str], Optional[str]]:
    """`(dxf, None)` o `(None, motivo)`. Trabaja sobre una copia en `temporal`."""
    if conversor is None:
        return None, ("no se ha podido convertir el DWG: no hay ODA File Converter ni AutoCAD "
                      "Core Console en este ordenador.")
    tipo, programa = conversor
    entrada = os.path.join(temporal, "entrada")
    os.makedirs(entrada, exist_ok=True)
    copia = os.path.join(entrada, "plano.dwg")
    shutil.copy2(ruta, copia)
    try:
        if tipo == "oda":
            destino = os.path.join(temporal, "salida")
            os.makedirs(destino, exist_ok=True)
            subprocess.run([programa, entrada, destino, "ACAD2018", "DXF", "0", "0", "*.DWG"],
                           cwd=temporal, capture_output=True, timeout=limite_s)
            dxf = os.path.join(destino, "plano.dxf")
        else:
            dxf = os.path.join(temporal, "plano.dxf")
            guion = os.path.join(temporal, "convertir.scr")
            with open(guion, "w", encoding="cp1252", newline="\r\n") as f:
                f.write('_.DXFOUT\n"%s"\n16\n_.QUIT\n_Y\n' % dxf.replace("\\", "/"))
            subprocess.run([programa, "/i", copia, "/s", guion],
                           cwd=temporal, capture_output=True, timeout=limite_s)
    except subprocess.TimeoutExpired:
        return None, "no se ha podido convertir el DWG: el conversor no ha terminado en %d s." % limite_s
    except OSError as exc:
        return None, "no se ha podido convertir el DWG: %s" % exc.__class__.__name__
    if not os.path.isfile(dxf) or os.path.getsize(dxf) == 0:
        return None, "no se ha podido convertir el DWG: el conversor no ha dejado ningún DXF."
    return dxf, None


# ---------------------------------------------------------------------------
# Un plano
# ---------------------------------------------------------------------------

def _unidades(plano):
    rooms = list(plano.rooms)
    if plano.unit_labels:
        return evaluator.group_rooms_by_unit_label(rooms, list(plano.unit_labels))
    return evaluator.group_rooms_by_proximity(rooms)


def _motivo_de(plantilla, etiqueta: str) -> Optional[str]:
    for etiquetas, motivo in plantilla.notas_por_motivo:
        if etiqueta in etiquetas:
            return motivo
    return None


def _cobertura(plantilla) -> dict:
    piezas = list(plantilla.interiores) + list(plantilla.exteriores)
    totales = (plantilla.cierre[0][1], plantilla.cierre[0][3], plantilla.cierre[1][1],
               plantilla.cierre[2][1])
    valores = [f.valor for f in piezas] + list(totales)
    return {
        "superficies": sum(1 for v in valores if v),
        "campos_vacios": sum(1 for v in valores if not v) + len(plantilla.sin_fila),
        "preguntas": len(plantilla.preguntas),
        "causas": [motivo for etiquetas, motivo in plantilla.notas_por_motivo
                   if tuple(etiquetas) != (pc.NUMERO_UDS.rstrip(":"),)],
    }


def analizar_dxf(ruta: str, plano_id: str, clasificacion) -> dict:
    """Todo lo que el banco anota de un DXF. Nunca lanza: un fallo es un resultado."""
    r = {"plano": plano_id, "viviendas_detectadas": 0, "viviendas_con_cuadro": 0,
         "viviendas_emparejadas": 0, "viviendas_correctas": 0, "estancias": 0, "superficies": 0,
         "campos_vacios": 0, "preguntas": 0, "errores": [], "causas": [], "comparaciones": [],
         "discrepancias_internas": [], "lectura": None}
    try:
        doc = parser.load_document(ruta)
    except Exception as exc:  # noqa: BLE001 - un plano ajeno puede fallar de cualquier forma
        r["errores"].append("no se ha podido abrir el DXF: %s" % exc.__class__.__name__)
        return r
    try:
        cuadros = cs.detectar_cuadros_superficies(doc)
    except Exception as exc:  # noqa: BLE001
        r["errores"].append("fallo al buscar su cuadro de superficies: %s" % exc.__class__.__name__)
        cuadros = []
    r["viviendas_con_cuadro"] = len(cuadros)

    try:
        plano = parser.leer_plano(doc)
    except ValueError as exc:
        # `CapaIndeterminada` y `EscalaIndeterminada`: ArchMuse pregunta en vez de suponer.
        r["lectura"] = str(exc)
        r["causas"].append(str(exc))
        plano = None
    except Exception as exc:  # noqa: BLE001
        r["errores"].append("fallo al leer el plano: %s" % exc.__class__.__name__)
        plano = None

    plantillas: Dict[str, object] = {}
    unidades, medida = [], None
    if plano is not None:
        try:
            medida = medicion.medir_planta(plano)
            unidades = _unidades(plano)
        except Exception as exc:  # noqa: BLE001
            r["errores"].append("fallo al medir: %s" % exc.__class__.__name__)
            medida, unidades = None, []
    if medida is not None:
        r["viviendas_detectadas"] = len(medida.viviendas)
        for vivienda in medida.viviendas:
            r["estancias"] += len(vivienda.piezas)
            try:
                plantilla = pc.construir(doc, plano, vivienda.nombre, medida=medida)
            except ValueError as exc:
                # `C-13`: varias viviendas con el mismo rótulo. Sin tabla y con motivo.
                plantillas.setdefault(vivienda.nombre, str(exc))
                r["causas"].append(str(exc))
                r["campos_vacios"] += 1
                continue
            except Exception as exc:  # noqa: BLE001
                r["errores"].append("fallo al preparar la tabla: %s" % exc.__class__.__name__)
                continue
            plantillas[vivienda.nombre] = plantilla
            cobertura = _cobertura(plantilla)
            for clave in ("superficies", "campos_vacios", "preguntas"):
                r[clave] += cobertura[clave]
            r["causas"].extend(cobertura["causas"])

    for cuadro in cuadros:
        _comparar_cuadro(r, cuadro, unidades, medida, plantillas, clasificacion)
    return r


def _comparar_cuadro(r, cuadro, unidades, medida, plantillas, clasificacion) -> None:
    celdas = [c for c in cuadro.celdas if c.campo in CAMPOS_COMPARABLES]
    if medida is None:
        unidad, motivo = None, r["lectura"] or "el plano no se ha podido medir."
    else:
        unidad, motivo = rc.elegir_vivienda(unidades, cuadro)
    tipo = cuadro.celda("vivienda_tipo")
    nombre = unidad.name if unidad is not None else ((tipo.texto_actual or "").strip()
                                                     if tipo is not None else "") or "?"
    if unidad is None:
        r["causas"].append(motivo)
        for celda in celdas:
            _anotar(r, nombre, celda, None, motivo, clasificacion)
        return
    r["viviendas_emparejadas"] += 1
    posicion = next(i for i, u in enumerate(unidades) if u is unidad)
    impedimentos = tuple(medida.viviendas[posicion].impedimentos)
    reparto = rc.calcular_reparto(unidad, cuadro.como_plantilla(), unidad.rooms,
                                  medicion_limpia=not impedimentos, impedimentos=impedimentos)
    escritas = {c.campo: c.texto for c in reparto.celdas}
    motivos = {n.campo: n.motivo for n in reparto.no_escritas}
    plantilla = plantillas.get(unidad.name)

    for celda in celdas:
        if celda.campo == "superficie_construida_cerrada":
            # La construida sale de `C-12` (la tabla de ArchMuse), no del reparto.
            if isinstance(plantilla, pc.Plantilla):
                texto = plantilla.cierre[2][1]
                motivo_celda = _motivo_de(plantilla, pc.CONSTRUIDA)
            else:
                texto, motivo_celda = "", plantilla or "no hay tabla de ArchMuse para esta vivienda."
        else:
            texto, motivo_celda = escritas.get(celda.campo, ""), motivos.get(celda.campo)
        _anotar(r, unidad.name, celda, texto, motivo_celda, clasificacion)

    if isinstance(plantilla, pc.Plantilla):
        _contrastar_con_la_tabla(r, unidad.name, escritas, plantilla)

    propias = [c for c in r["comparaciones"] if c["vivienda"] == unidad.name]
    if propias and all(c["estado"] in (COINCIDENCIA, REFERENCIA_INEXISTENTE) for c in propias) \
            and any(c["estado"] == COINCIDENCIA for c in propias):
        r["viviendas_correctas"] += 1


def _anotar(r, vivienda, celda, texto, motivo, clasificacion) -> None:
    referencia = cifra_de_referencia(celda.texto_actual)
    archmuse = cs.superficie_en_m2(texto) if texto else None
    fila = {"vivienda": vivienda, "campo": celda.campo, "referencia": referencia,
            "archmuse": archmuse, "motivo": None, "clase": None, "nota": None}
    if referencia is None:
        fila["estado"] = REFERENCIA_INEXISTENTE
    elif archmuse is None:
        fila["estado"] = VACIO_CON_MOTIVO
        fila["motivo"] = motivo
        if motivo:
            r["causas"].append(motivo)
    elif coinciden(archmuse, referencia):
        fila["estado"] = COINCIDENCIA
    else:
        fila["estado"] = MISMATCH
        clase, nota = clasificacion.get((r["plano"], vivienda, celda.campo), (None, None))
        fila["clase"], fila["nota"] = clase, nota
    r["comparaciones"].append(fila)


def _contrastar_con_la_tabla(r, vivienda, escritas, plantilla) -> None:
    """Las cifras se comparan por campo con el reparto; lo que se dibuja es la
    tabla de ArchMuse. Si las dos no dicen lo mismo, la comparación no vale y se
    anota para revisarla."""
    de_la_tabla = {f.valor for f in list(plantilla.interiores) + list(plantilla.exteriores) if f.valor}
    for campo, texto in escritas.items():
        if campo in cs.CAMPOS_SUMANDOS_UTIL and texto not in de_la_tabla:
            r["discrepancias_internas"].append(
                "%s · %s: el reparto da %s y la tabla de ArchMuse no lleva esa cifra"
                % (vivienda, campo, texto))
    for campo, indice in (("total_util_interior", 1), ("total_util_exterior", 3)):
        if campo in escritas and escritas[campo] != plantilla.cierre[0][indice]:
            r["discrepancias_internas"].append(
                "%s · %s: el reparto da %s y la tabla de ArchMuse %s"
                % (vivienda, campo, escritas[campo], plantilla.cierre[0][indice] or "lo deja vacío"))


# ---------------------------------------------------------------------------
# Resultado de un plano (criterios del banco, no de arquitectura)
# ---------------------------------------------------------------------------

def resultado_del_plano(r) -> Tuple[str, str]:
    comparaciones = r["comparaciones"]
    con_referencia = [c for c in comparaciones if c["estado"] != REFERENCIA_INEXISTENTE]
    mismatches = [c for c in comparaciones if c["estado"] == MISMATCH]
    sin_explicar = [c for c in mismatches if c["clase"] in (None, PENDIENTE_DE_DETERMINAR)]
    de_archmuse = [c for c in mismatches if c["clase"] == ERROR_DE_ARCHMUSE]
    vacios = [c for c in comparaciones if c["estado"] == VACIO_CON_MOTIVO]
    sin_motivo = [c for c in vacios if not c["motivo"]]
    coincidencias = [c for c in comparaciones if c["estado"] == COINCIDENCIA]

    if r["errores"]:
        return FAIL, r["errores"][0]
    if de_archmuse:
        return FAIL, "%d cifra(s) distinta(s) del cuadro por error de ArchMuse" % len(de_archmuse)
    if sin_explicar or sin_motivo or r["discrepancias_internas"]:
        partes = []
        if sin_explicar:
            partes.append("%d MISMATCH sin explicar" % len(sin_explicar))
        if sin_motivo:
            partes.append("%d campo(s) vacío(s) sin motivo" % len(sin_motivo))
        if r["discrepancias_internas"]:
            partes.append("%d diferencia(s) entre el reparto y la tabla de ArchMuse"
                          % len(r["discrepancias_internas"]))
        return PENDIENTE, "; ".join(partes)
    if not r["viviendas_con_cuadro"]:
        if r["lectura"]:
            return FAIL, "sin cuadro de referencia y sin leer: %s" % r["lectura"]
        return SIN_REFERENCIA, "el plano no trae un cuadro de superficies relleno"
    if not con_referencia:
        return SIN_REFERENCIA, "su cuadro no tiene ninguna superficie escrita"
    if not coincidencias:
        return FAIL, "ninguna cifra de su cuadro sale en ArchMuse"
    if mismatches or vacios or r["viviendas_emparejadas"] < r["viviendas_con_cuadro"]:
        partes = []
        if mismatches:
            partes.append("%d MISMATCH explicado(s) (%s)"
                          % (len(mismatches), ", ".join(sorted({c["clase"] for c in mismatches}))))
        if vacios:
            partes.append("%d campo(s) vacío(s) con motivo" % len(vacios))
        if r["viviendas_emparejadas"] < r["viviendas_con_cuadro"]:
            partes.append("%d cuadro(s) sin vivienda emparejada"
                          % (r["viviendas_con_cuadro"] - r["viviendas_emparejadas"]))
        return PARTIAL, "; ".join(partes)
    return PASS, "las %d cifras de su cuadro coinciden" % len(coincidencias)


# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------

def causa(motivo: str) -> str:
    """El motivo sin lo que es propio de un plano —nombres, cifras, identificadores—,
    para agrupar lo que se repite."""
    texto = re.sub(r"«[^»]*»", "«…»", motivo or "")
    texto = re.sub(r"\([^)]*\)", "(…)", texto)
    texto = re.sub(r"\d+([.,]\d+)?", "N", texto)
    return re.sub(r"\s+", " ", texto).strip()[:200]


def escribir_resumen(filas: List[dict], detalles: List[dict], carpeta: str) -> str:
    cuenta = {k: sum(1 for f in filas if f["resultado"] == k) for k in RESULTADOS}
    veces: Dict[str, int] = {}
    en_planos: Dict[str, set] = {}
    for d in detalles:
        for motivo in d["causas"] + d["errores"]:
            clave = causa(motivo)
            veces[clave] = veces.get(clave, 0) + 1
            en_planos.setdefault(clave, set()).add(d["plano"])
    clases: Dict[str, int] = {}
    for d in detalles:
        for c in d["comparaciones"]:
            if c["estado"] == MISMATCH:
                clave = c["clase"] or "sin clasificar"
                clases[clave] = clases.get(clave, 0) + 1

    lineas = ["# Banco de compatibilidad · %s" % datetime.now().strftime("%Y-%m-%d %H:%M"), "",
              "%d planos." % len(filas), "", "| Resultado | Planos |", "|---|---|"]
    lineas += ["| %s | %d |" % (k, cuenta[k]) for k in RESULTADOS if cuenta[k]]
    total = lambda k: sum(int(f[k]) for f in filas)  # noqa: E731
    lineas += ["", "| Cifras comparadas | Coincidencias | MISMATCH | Vacío con motivo | Sin referencia |",
               "|---|---|---|---|---|",
               "| %d | %d | %d | %d | %d |" % (total("cifras_comparadas"), total("coincidencias"),
                                              total("mismatches"), total("vacios_con_motivo"),
                                              total("referencias_inexistentes")),
               "", "## Por plano", "",
               "| Plano | Formato | Viviendas | Con cuadro | Correctas | Estancias | Resultado | Motivo |",
               "|---|---|---|---|---|---|---|---|"]
    lineas += ["| %s | %s | %s | %s | %s | %s | %s | %s |"
               % (f["plano"], f["formato"], f["viviendas_detectadas"], f["viviendas_con_cuadro"],
                  f["viviendas_correctas"], f["estancias"], f["resultado"], causa(f["motivo"]))
               for f in filas]
    lineas += ["", "## MISMATCH por clase", ""]
    lineas += (["- %s: %d" % (k, v) for k, v in sorted(clases.items())] or ["Ninguno."])
    repetidas = sorted((k for k in veces if len(en_planos[k]) >= 2),
                       key=lambda k: (-len(en_planos[k]), -veces[k], k))
    lineas += ["", "## Patrones repetidos (en dos planos o más)", ""]
    lineas += (["- **%d planos**, %d veces: %s" % (len(en_planos[k]), veces[k], k)
                for k in repetidas] or ["Ninguno."])
    unicas = sorted(k for k in veces if len(en_planos[k]) < 2)
    lineas += ["", "## Causas en un solo plano", ""]
    lineas += (["- %s (%s, %d veces)" % (k, next(iter(en_planos[k])), veces[k]) for k in unicas]
               or ["Ninguna."])
    lineas += ["", "## Lo que este banco no mide", "",
               "Mide el motor de ArchMuse (lector, medición y reparto) sobre el fichero entero. "
               "No mide la integración con AutoCAD: el comando lee el dibujo con `ssget` y manda "
               "la geometría, y lo que se pierda en ese camino no aparece aquí (C-7).", ""]
    ruta = os.path.join(carpeta, "resumen.md")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    return ruta


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------

def ejecutar(planos: str, salida: str = SALIDA_POR_DEFECTO, clasificacion: Optional[str] = None,
             buscar=buscar_conversor) -> dict:
    """`buscar` devuelve el conversor de DWG; los tests lo sustituyen."""
    planos, salida = os.path.abspath(planos), os.path.abspath(salida)
    comprobar_carpetas(planos, salida)
    rutas = planos_de(planos)
    ids = asignar_ids(rutas, salida)
    tabla = leer_clasificacion(clasificacion or os.path.join(salida, "clasificacion.csv"))
    conversor = buscar() if any(p.lower().endswith(".dwg") for p in rutas) else None
    carpeta = os.path.join(salida, datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    os.makedirs(carpeta, exist_ok=True)

    nivel = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    filas, detalles = [], []
    try:
        for ruta in sorted(rutas, key=lambda p: ids[p]):
            plano_id = ids[ruta]
            formato = os.path.splitext(ruta)[1][1:].upper()
            temporal = tempfile.mkdtemp(prefix="archmuse_banco_")
            try:
                inicio = time.perf_counter()
                dxf, motivo = ruta, None
                if formato == "DWG":
                    dxf, motivo = convertir_dwg(ruta, temporal, conversor)
                conversion = time.perf_counter() - inicio
                inicio = time.perf_counter()
                if dxf is None:
                    d = {"plano": plano_id, "errores": [motivo], "causas": [], "comparaciones": [],
                         "discrepancias_internas": [], "lectura": None, "viviendas_detectadas": 0,
                         "viviendas_con_cuadro": 0, "viviendas_emparejadas": 0,
                         "viviendas_correctas": 0, "estancias": 0, "superficies": 0,
                         "campos_vacios": 0, "preguntas": 0}
                else:
                    d = analizar_dxf(dxf, plano_id, tabla)
                tiempo = time.perf_counter() - inicio
            finally:
                shutil.rmtree(temporal, ignore_errors=True)
            resultado, motivo = resultado_del_plano(d)
            estados = [c["estado"] for c in d["comparaciones"]]
            fila = {"plano": plano_id, "formato": formato,
                    "viviendas_detectadas": d["viviendas_detectadas"],
                    "viviendas_con_cuadro": d["viviendas_con_cuadro"],
                    "viviendas_emparejadas": d["viviendas_emparejadas"],
                    "viviendas_correctas": d["viviendas_correctas"], "estancias": d["estancias"],
                    "superficies": d["superficies"], "campos_vacios": d["campos_vacios"],
                    "preguntas": d["preguntas"],
                    "cifras_comparadas": sum(1 for e in estados if e != REFERENCIA_INEXISTENTE),
                    "coincidencias": estados.count(COINCIDENCIA), "mismatches": estados.count(MISMATCH),
                    "vacios_con_motivo": estados.count(VACIO_CON_MOTIVO),
                    "referencias_inexistentes": estados.count(REFERENCIA_INEXISTENTE),
                    "errores": len(d["errores"]), "tiempo_s": "%.2f" % tiempo,
                    "tiempo_conversion_s": "%.2f" % conversion if formato == "DWG" else "",
                    "resultado": resultado, "motivo": motivo}
            d.update(resultado=resultado, motivo=motivo, formato=formato, tiempo_s=fila["tiempo_s"])
            filas.append(fila)
            detalles.append(d)
    finally:
        logging.disable(nivel)

    with open(os.path.join(carpeta, "resultados.csv"), "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)
    with open(os.path.join(carpeta, "detalle.json"), "w", encoding="utf-8") as f:
        json.dump(detalles, f, ensure_ascii=False, indent=1)
    with open(os.path.join(carpeta, "mismatches.csv"), "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(["plano", "vivienda", "campo", "referencia", "archmuse", "clase", "nota"])
        for d in detalles:
            for c in d["comparaciones"]:
                if c["estado"] == MISMATCH:
                    escritor.writerow([d["plano"], c["vivienda"], c["campo"], c["referencia"],
                                       c["archmuse"], c["clase"] or "", c["nota"] or ""])
    resumen = escribir_resumen(filas, detalles, carpeta)
    return {"carpeta": carpeta, "resumen": resumen, "filas": filas, "detalles": detalles}


def main(argv=None) -> int:
    argumentos = argparse.ArgumentParser(description="Banco de compatibilidad externo de ArchMuse.")
    argumentos.add_argument("planos", help="carpeta con los DXF/DWG, fuera del repositorio")
    argumentos.add_argument("--salida", default=SALIDA_POR_DEFECTO)
    argumentos.add_argument("--clasificacion", default=None,
                            help="CSV con la clase de cada MISMATCH (por defecto, "
                                 "<salida>/clasificacion.csv)")
    opciones = argumentos.parse_args(argv)
    try:
        hecho = ejecutar(opciones.planos, opciones.salida, opciones.clasificacion)
    except CarpetaNoPermitida as exc:
        print("No ejecuto el banco: %s" % exc)
        return 2
    cuenta = {}
    for fila in hecho["filas"]:
        cuenta[fila["resultado"]] = cuenta.get(fila["resultado"], 0) + 1
    print("%d planos: %s" % (len(hecho["filas"]),
                             ", ".join("%s %d" % (k, cuenta[k]) for k in RESULTADOS if k in cuenta)
                             or "ninguno"))
    print("Resumen: %s" % hecho["resumen"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
