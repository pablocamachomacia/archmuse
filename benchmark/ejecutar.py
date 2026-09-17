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

from herramientas import core_console  # noqa: E402
from analyzer import cuadro_superficies as cs  # noqa: E402
from analyzer import medicion, parser  # noqa: E402
from analyzer import plantilla_cuadro as pc  # noqa: E402
from analyzer import respuestas_del_arquitecto as rda  # noqa: E402
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
            "vacios_con_motivo", "referencias_inexistentes", "automatico", "un_clic", "vacio",
            "cifras_distintas", "filas_sin_celda", "cifras_incorrectas",
            "intervenciones_por_vivienda", "viviendas_sin_intervencion_pct",
            "viviendas_completas_con_un_clic_pct", "errores", "tiempo_s",
            "tiempo_conversion_s", "resultado", "motivo")

# ---------------------------------------------------------------------------
# Cuánta intervención haría falta (Pablo, 2026-09-17). **Sólo se mide**: el
# «modo preguntar» no existe todavía.
# ---------------------------------------------------------------------------

AUTOMATICO = "AUTOMÁTICO"
UN_CLIC = "UN CLIC"
VACIO = "VACÍO"
#: Una celda con cifra distinta de la del arquitecto que nadie ha explicado como
#: redondeo o cuadro desactualizado. No es ninguna de las tres: es un error por mirar.
CIFRA_DISTINTA = "CIFRA DISTINTA"
#: Un motivo que sólo repite que otra cifra está bloqueada («ver sus notas»): toma la
#: categoría de lo que la bloquea (`resolver_derivadas`).
DERIVADO = "derivado"

#: `(fragmento, categoría)`. Cada fragmento es texto literal de un motivo de
#: `analyzer/` (lo vigila un test: si cambia la redacción, se pone rojo). Si un motivo
#: trae varias causas, gana la peor: VACÍO sobre UN CLIC sobre derivado. **Un motivo
#: que no casa con ninguno es VACÍO**: no se cuenta como resoluble lo que no se sabe.
PATRONES_DE_MOTIVO = (
    # UN CLIC: una pregunta con respuesta cerrada.
    ("no se sabe si es de esta vivienda o de", UN_CLIC),          # reparto dudoso (tabla)
    ("entre viviendas no es firme", UN_CLIC),                     # reparto dudoso (medición)
    ("hay una pieza que duda si es de esta vivienda", UN_CLIC),   # fila que falta por eso
    ("polilíneas a menos de", UN_CLIC),                           # C-12: dos al alcance
    ("polilíneas rotuladas como construida cerrada que", UN_CLIC),  # C-12: dos rotuladas
    ("no se sabe cuál de los dos es la construida", UN_CLIC),     # C-20: duda
    ("tiene dos nombres dentro", UN_CLIC),                        # C-18
    ("no sabe si es un espacio interior o exterior", UN_CLIC),    # ámbito (tabla)
    ("no se sabe si son superficie interior o exterior", UN_CLIC),  # ámbito (medición)
    ("ArchMuse no las distingue", UN_CLIC),                       # C-13: lo resuelve el clic
    ("dentro de la superficie construida que el plano rotula para", UN_CLIC),  # de otra vivienda
    # Modo preguntar (2026-09-17): una pregunta de pertenencia o un clic en la construida.
    ("linda con la superficie construida que el plano rotula para", UN_CLIC),  # C-21, de otra
    ("puede ser de esta vivienda", UN_CLIC),                      # pieza de la vecina en duda
    ("que has marcado", UN_CLIC),                                 # construida marcada que no vale
    # VACÍO: no hay pregunta que lo arregle.
    ("dibujados dos veces", VACIO),
    ("se solapa con otra pieza dibujada", VACIO),
    ("es superficie construida, no útil", VACIO),
    ("redondea a cero", VACIO),
    ("no tiene rótulo", VACIO),
    ("no es un nombre de estancia", VACIO),
    ("no rotula ninguna polilínea", VACIO),
    ("de una sola polilínea que contenga", VACIO),
    ("no trae altura de texto", VACIO),
    ("no hay ningún espacio de este lado", VACIO),
    ("no tiene ningún espacio interior", VACIO),
    ("no tiene fila para", VACIO),
    # Derivados: repiten que otra cifra está bloqueada.
    ("no se calcula sobre una cifra bloqueada", DERIVADO),
    ("alguna fila de este lado no lleva cifra", DERIVADO),
    ("no contiene todas las piezas interiores", DERIVADO),
    ("con un contorno rotulado como superficie", DERIVADO),
)
_GRAVEDAD = {DERIVADO: 0, UN_CLIC: 1, VACIO: 2}


def categoria_de_motivo(motivo: Optional[str]) -> str:
    encontradas = {categoria for fragmento, categoria in PATRONES_DE_MOTIVO
                   if fragmento in (motivo or "")}
    if not encontradas:
        return VACIO
    return max(encontradas, key=_GRAVEDAD.get)


TOTALES_DE_LADO = ("total_util_interior", "total_util_exterior")


def resolver_derivadas(categorias: List[str], campos: Optional[List[str]] = None) -> List[str]:
    """Las derivadas toman la peor categoría de lo que las bloquea; si no hay nada,
    VACÍO.

    Con `campos`, lo que bloquea depende de la celda: el útil total, de los dos
    totales de lado (`C-14`); un total de lado o la construida, de las piezas. Sin
    `campos`, de todas las demás."""
    def peor(indices):
        propias = [categorias[i] for i in indices if categorias[i] in (UN_CLIC, VACIO)]
        return max(propias, key=_GRAVEDAD.get) if propias else None

    todas = range(len(categorias))
    if campos is None:
        comun = peor(todas) or VACIO
        return [comun if c == DERIVADO else c for c in categorias]
    piezas = [i for i in todas if campos[i] not in TOTALES_DE_LADO + ("total_util",
                                                                      "superficie_construida_cerrada")]
    salida = list(categorias)
    for i in todas:
        if salida[i] == DERIVADO and campos[i] != "total_util":
            salida[i] = peor(piezas) or peor(todas) or VACIO
    for i in todas:
        if salida[i] == DERIVADO:
            lados = [j for j in todas if campos[j] in TOTALES_DE_LADO]
            categorias_lados = [salida[j] for j in lados if salida[j] in (UN_CLIC, VACIO)]
            salida[i] = (max(categorias_lados, key=_GRAVEDAD.get) if categorias_lados
                         else peor(piezas) or VACIO)
    return salida


def motivo_de_fila_que_falta(campo: str, vecina: Optional[str]) -> str:
    """La tabla no tiene fila para una celda de su cuadro. Si en otra vivienda hay una
    pieza de esa familia que duda si es de ésta, una respuesta la traería."""
    if vecina:
        return ("la tabla de ArchMuse no lleva «%s»: en %s hay una pieza que duda si es de "
                "esta vivienda" % (campo, vecina))
    return "la tabla de ArchMuse no tiene fila para «%s»" % campo


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
    """`("oda" | "core_console", ruta)`, o `None`.

    Core Console se busca y se lanza **sólo** por `herramientas/core_console.py`
    (2026-09-16): lanzado a mano y matado por un plazo deja FILEDIA a 0 en el
    AutoCAD del usuario."""
    ruta = os.environ.get("ARCHMUSE_ODA")
    if ruta and os.path.isfile(ruta):
        return "oda", ruta
    encontrados = sorted(glob.glob(r"C:\Program Files\ODA\ODAFileConverter*\ODAFileConverter.exe"))
    if encontrados:
        return "oda", encontrados[-1]
    consola = core_console.buscar_consola()
    return ("core_console", consola) if consola else None


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
            r = core_console.ejecutar(guion, dibujo=copia, consola=programa, cwd=temporal,
                                      plazo_s=limite_s)
            if r.agotado:
                raise subprocess.TimeoutExpired(programa, limite_s)
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
         "intervenciones": [], "lectura": None}
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
    medida = None
    if plano is not None:
        try:
            medida = medicion.medir_planta(plano)
        except Exception as exc:  # noqa: BLE001
            r["errores"].append("fallo al medir: %s" % exc.__class__.__name__)
            medida = None
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

    viviendas = []
    for cuadro in cuadros:
        viviendas.append(_comparar_cuadro(r, doc, plano, cuadro, medida, plantillas, clasificacion))
    r["intervenciones"] = [v for v in viviendas if v is not None]
    return r


def _clave_de_vivienda(texto: Optional[str]) -> str:
    """«VT1 /3» y «VT13/3FN» del cuadro son la «VT1/3» y la «VT13/3» del dibujo: sin
    espacios, y sin las letras que el estudio añade tras la tipología (decisión del
    banco, 2026-09-17: medido en el plano maestro, «FN» y «PMR» en 3 de 25 cuadros)."""
    limpio = "".join((texto or "").split()).upper()
    return re.sub(r"^(VT\d+/\d+)[A-Z]+$", r"\1", limpio)


CAMPOS_DE_CIERRE = ("total_util_interior", "total_util_exterior", "total_util",
                    "superficie_construida_cerrada")


def _lecturas_de_la_tabla(plantilla) -> Dict[str, List[dict]]:
    """Lo que dibuja ArchMuse, por campo del cuadro: `{campo: [{texto, motivo}]}`. Una
    fila cuyo rótulo no es ningún campo del cuadro va con su rótulo: también es una
    cifra que se dibuja."""
    lecturas: Dict[str, List[dict]] = {}
    for fila in list(plantilla.interiores) + list(plantilla.exteriores):
        campo = cs.campo_de_la_pieza(fila.rotulo) or "«%s»" % fila.rotulo
        lecturas.setdefault(campo, []).append(
            {"campo": campo, "texto": fila.valor,
             "motivo": None if fila.valor else _motivo_de(plantilla, fila.rotulo)})
    for campo, texto, etiqueta in (
            ("total_util_interior", plantilla.cierre[0][1], pc.TOTAL_INTERIOR),
            ("total_util_exterior", plantilla.cierre[0][3], pc.TOTAL_EXTERIOR),
            ("total_util", plantilla.cierre[1][1], pc.TOTAL_UTIL),
            ("superficie_construida_cerrada", plantilla.cierre[2][1], pc.CONSTRUIDA)):
        lecturas[campo] = [{"campo": campo, "texto": texto,
                            "motivo": None if texto else _motivo_de(plantilla, etiqueta)}]
    return lecturas


def _familia(campo: str) -> str:
    return re.sub(r"_\d+$", "", campo)


def _emparejar(celdas, lecturas) -> Dict[int, Optional[dict]]:
    """Qué fila de la tabla va con cada celda del cuadro.

    Por su campo si sólo hay una fila con ese campo. Si hay varias con el mismo
    campo —dos «Terraza» sin número dan las dos `terraza_1`— o la del número no
    existe, entre las de su familia **por la cifra**: nunca por el orden, que sería
    inventar cuál es cuál. Sin ninguna que coincida, la más cercana (y sale como
    cifra distinta), y si no, una sin cifra."""
    usadas = set()
    elegidas: Dict[int, Optional[dict]] = {}
    todas = [f for filas in lecturas.values() for f in filas]
    for pasada in (1, 2):
        for i, celda in enumerate(celdas):
            if i in elegidas:
                continue
            referencia = cifra_de_referencia(celda.texto_actual)
            exactas = [f for f in lecturas.get(celda.campo, []) if id(f) not in usadas]
            if len(lecturas.get(celda.campo, [])) == 1:
                candidatas = exactas
            else:
                candidatas = [f for f in todas if id(f) not in usadas
                              and _familia(f["campo"]) == _familia(celda.campo)
                              and (f["campo"] == celda.campo or len(lecturas[f["campo"]]) > 1)]
            valor = lambda f: cs.superficie_en_m2(f["texto"]) if f["texto"] else None  # noqa: E731
            iguales = [f for f in candidatas if referencia is not None and valor(f) is not None
                       and coinciden(valor(f), referencia)]
            if pasada == 1:
                elegida = iguales[0] if iguales else None
            elif not candidatas:
                elegida = None
                elegidas[i] = None
                continue
            else:
                con_cifra = [f for f in candidatas if valor(f) is not None]
                if con_cifra and referencia is not None:
                    elegida = min(con_cifra, key=lambda f: abs(valor(f) - referencia))
                else:
                    elegida = (con_cifra or candidatas)[0]
            if elegida is not None:
                usadas.add(id(elegida))
                elegidas[i] = elegida
    return elegidas


def filas_sin_celda(lecturas, elegidas, celdas) -> List[str]:
    """Las filas de piezas **con cifra** que su cuadro no respalda: no han ido con
    ninguna celda, o han ido con una celda que su cuadro deja sin cifra. Cuentan como
    cifras incorrectas (Pablo, 2026-09-17). **Límite:** una estancia bien medida que su
    cuadro no recoge también sale aquí; se cuenta y se revisa, no se da por buena.

    Medido en el plano maestro: la fila «aseo» del cuadro estaba vacía y la tabla
    escribía ahí el aseo de la vecina; contar sólo las filas sin celda no lo veía."""
    respaldadas = {id(f) for i, f in elegidas.items()
                   if f is not None and cifra_de_referencia(celdas[i].texto_actual) is not None}
    return [f["campo"] for campo, filas in lecturas.items() if campo not in CAMPOS_DE_CIERRE
            for f in filas if f["texto"] and id(f) not in respaldadas]


def _comparar_con_plantilla(r, nombre, celdas, plantilla, medida, clasificacion):
    lecturas = _lecturas_de_la_tabla(plantilla)
    elegidas = _emparejar(celdas, lecturas)
    filas = []
    for i, celda in enumerate(celdas):
        lectura = elegidas.get(i)
        if lectura is None:
            vecinas = [v.nombre for v in (medida.viviendas if medida else ())
                       for d in v.repartos_dudosos
                       if d.siguiente == nombre and cs.campo_de_la_pieza(d.pieza)
                       and _familia(cs.campo_de_la_pieza(d.pieza) or "") == _familia(celda.campo)]
            motivo = motivo_de_fila_que_falta(celda.campo, vecinas[0] if vecinas else None)
            filas.append(_anotar(r, nombre, celda, "", motivo, clasificacion))
        else:
            filas.append(_anotar(r, nombre, celda, lectura["texto"], lectura["motivo"], clasificacion))
    return filas, filas_sin_celda(lecturas, elegidas, celdas)


def _comparar_cuadro(r, doc, plano, cuadro, medida, plantillas, clasificacion) -> Optional[dict]:
    """Compara su cuadro con **la tabla que dibuja ArchMuse** para su vivienda.

    Hasta el 2026-09-17 se comparaba con `reparto_cuadro.calcular_reparto` sobre su
    cuadro vaciado, un camino que el producto dejó de usar con la plantilla fija
    (2026-09-13): medido en el plano maestro, sin `C-14` en el útil, bloqueando las
    terrazas sin número y sin emparejar los cuadros «…FN». Ahora se mide lo que el
    arquitecto recibe.

    Con varias viviendas del mismo rótulo, el comando las distingue por el clic
    (enmienda de `C-13`); aquí se mide cada una como distinguida y se toma la que
    mejor coincide, que es la que él marcaría con el clic."""
    celdas = [c for c in cuadro.celdas if c.campo in CAMPOS_COMPARABLES]
    tipo = cuadro.celda("vivienda_tipo")
    declarado = (tipo.texto_actual or "").strip() if tipo is not None else ""
    if medida is None:
        candidatas, motivo = [], r["lectura"] or "el plano no se ha podido medir."
    else:
        clave = _clave_de_vivienda(declarado)
        if clave:
            candidatas = [i for i, v in enumerate(medida.viviendas) if _clave_de_vivienda(v.nombre) == clave]
        else:
            candidatas = [0] if len(medida.viviendas) == 1 else []
        motivo = ("el cuadro dice ser de la vivienda «%s» y el plano no tiene ninguna con ese "
                  "rótulo" % declarado if declarado else
                  "el cuadro no dice de qué vivienda es y el plano tiene %d" % len(medida.viviendas))
    if not candidatas:
        r["causas"].append(motivo)
        filas = [_anotar(r, declarado or "?", celda, None, motivo, clasificacion) for celda in celdas]
        r["comparaciones"].extend(filas)
        return _intervenciones(declarado or "?", filas, [])

    mejor = None
    for posicion in candidatas:
        vivienda = medida.viviendas[posicion]
        sobrantes: List[str] = []
        plantilla, medida_usada, distinguida_en = None, medida, None
        try:
            if vivienda.viviendas_con_el_mismo_rotulo > 1:
                distinguida = medicion.medir_planta(plano, distinguida=posicion)
                plantilla = pc.construir(doc, plano, vivienda.nombre, medida=distinguida,
                                         posicion=posicion)
                medida_usada, distinguida_en = distinguida, posicion
            else:
                plantilla = plantillas.get(vivienda.nombre)
                if not isinstance(plantilla, pc.Plantilla):
                    raise ValueError(plantilla or "no hay tabla de ArchMuse para esta vivienda.")
            filas, sobrantes = _comparar_con_plantilla(r, vivienda.nombre, celdas, plantilla, medida,
                                                       clasificacion)
        except ValueError as exc:
            filas = [_anotar(r, vivienda.nombre, celda, None, str(exc), clasificacion) for celda in celdas]
        except Exception as exc:  # noqa: BLE001
            r["errores"].append("fallo al preparar la tabla: %s" % exc.__class__.__name__)
            continue
        puntos = (sum(1 for f in filas if f["estado"] == COINCIDENCIA),
                  -sum(1 for f in filas if f["estado"] == MISMATCH) - len(sobrantes))
        if mejor is None or puntos > mejor[0]:
            mejor = (puntos, vivienda.nombre, filas, sobrantes,
                     (plantilla if isinstance(plantilla, pc.Plantilla) else None,
                      medida_usada, distinguida_en))
    if mejor is None:
        return None
    _puntos, nombre, filas, sobrantes, (plantilla, medida_usada, distinguida_en) = mejor
    r["viviendas_emparejadas"] += 1
    for f in filas:
        if f["estado"] == VACIO_CON_MOTIVO and f["motivo"]:
            r["causas"].append(f["motivo"])
    r["comparaciones"].extend(filas)
    con_referencia = [f for f in filas if f["estado"] != REFERENCIA_INEXISTENTE]
    if con_referencia and all(f["estado"] == COINCIDENCIA for f in con_referencia) and not sobrantes:
        r["viviendas_correctas"] += 1
    resumen = _intervenciones(nombre, filas, sobrantes)

    # Número de unidades (`C-8`): lo que dice su cuadro y lo que escribe ArchMuse.
    unidades = cuadro.celda("numero_unidades")
    resumen["unidades"] = {"referencia": (unidades.texto_actual or "").strip() if unidades else "",
                           "archmuse": plantilla.cierre[3][3] if plantilla is not None else ""}

    # Modo preguntar, con el arquitecto simulado.
    if plantilla is not None:
        try:
            despues, hechas = preguntar_y_responder(doc, plano, nombre, medida_usada,
                                                    distinguida_en, celdas)
            filas_despues, sobrantes_despues = _comparar_con_plantilla(
                r, nombre, celdas, despues, medida_usada, clasificacion)
        except Exception as exc:  # noqa: BLE001
            r["errores"].append("fallo al preguntar: %s" % exc.__class__.__name__)
        else:
            vacias = lambda fs: [f for f in fs if f["estado"] == VACIO_CON_MOTIVO]  # noqa: E731
            resumen["preguntar"] = {
                "preguntas": [list(h) for h in hechas],
                "sin_respuesta": sum(1 for _t, v in hechas if v is None),
                "celdas_vacias_antes": len(vacias(filas)),
                "celdas_vacias_despues": len(vacias(filas_despues)),
                "completa_antes": _completa(filas, sobrantes),
                "completa_despues": _completa(filas_despues, sobrantes_despues),
                "cifras_distintas_despues": sum(1 for f in filas_despues if f["estado"] == MISMATCH
                                                and f["clase"] not in (REDONDEO, CUADRO_DESACTUALIZADO)),
                "filas_sin_celda_despues": list(sobrantes_despues),
                "vacias_despues": [{"campo": f["campo"], "motivo": f["motivo"]}
                                   for f in vacias(filas_despues)],
                "nota_de_preguntas": [m for etiquetas, m in despues.notas_por_motivo
                                      if "Preguntas" in etiquetas],
                "confirmadas": pc.a_dict(despues)["confirmadas_por_el_arquitecto"],
            }
    return resumen


def _intervenciones(nombre, filas, sobrantes) -> dict:
    """Pone la categoría a cada celda comparada y resume la vivienda."""
    comparadas = [f for f in filas if f["estado"] != REFERENCIA_INEXISTENTE]
    categorias = []
    for f in comparadas:
        if f["estado"] == COINCIDENCIA or f["clase"] in (REDONDEO, CUADRO_DESACTUALIZADO):
            categorias.append(AUTOMATICO)
        elif f["estado"] == MISMATCH:
            categorias.append(CIFRA_DISTINTA)
        else:
            categorias.append(categoria_de_motivo(f["motivo"]))
    categorias = resolver_derivadas(categorias, [f["campo"] for f in comparadas])
    for f, categoria in zip(comparadas, categorias, strict=True):
        f["categoria"] = categoria
    return {"vivienda": nombre, "celdas": len(comparadas), "filas_sin_celda": list(sobrantes),
            "cifras_incorrectas": categorias.count(CIFRA_DISTINTA) + len(sobrantes),
            **{clave: categorias.count(valor) for clave, valor in (
                ("automatico", AUTOMATICO), ("un_clic", UN_CLIC), ("vacio", VACIO),
                ("cifras_distintas", CIFRA_DISTINTA))}}


def _anotar(r, vivienda, celda, texto, motivo, clasificacion) -> dict:
    referencia = cifra_de_referencia(celda.texto_actual)
    archmuse = cs.superficie_en_m2(texto) if texto else None
    fila = {"vivienda": vivienda, "campo": celda.campo, "referencia": referencia,
            "archmuse": archmuse, "motivo": None, "clase": None, "nota": None, "categoria": None}
    if referencia is None:
        fila["estado"] = REFERENCIA_INEXISTENTE
    elif archmuse is None:
        fila["estado"] = VACIO_CON_MOTIVO
        fila["motivo"] = motivo
    elif coinciden(archmuse, referencia):
        fila["estado"] = COINCIDENCIA
    else:
        fila["estado"] = MISMATCH
        clase, nota = clasificacion.get((r["plano"], vivienda, celda.campo), (None, None))
        fila["clase"], fila["nota"] = clase, nota
    return fila


def resumen_de_intervenciones(viviendas: List[dict]) -> dict:
    """Recuentos y porcentajes de un conjunto de viviendas (un plano o todos)."""
    n = len(viviendas)
    suma = lambda k: sum(v[k] for v in viviendas)  # noqa: E731
    # Una vivienda con una cifra que su cuadro no respalda no está resuelta.
    sin_intervencion = sum(1 for v in viviendas if v["celdas"] and v["automatico"] == v["celdas"]
                           and not v["filas_sin_celda"])
    con_un_clic = sum(1 for v in viviendas
                      if v["celdas"] and v["automatico"] + v["un_clic"] == v["celdas"]
                      and not v["filas_sin_celda"])
    return {"viviendas": n, "automatico": suma("automatico"), "un_clic": suma("un_clic"),
            "vacio": suma("vacio"), "cifras_distintas": suma("cifras_distintas"),
            "filas_sin_celda": sum(len(v["filas_sin_celda"]) for v in viviendas),
            "cifras_incorrectas": suma("cifras_incorrectas"),
            "intervenciones_por_vivienda": suma("un_clic") / n if n else 0.0,
            "sin_intervencion_pct": 100.0 * sin_intervencion / n if n else 0.0,
            "completas_con_un_clic_pct": 100.0 * con_un_clic / n if n else 0.0}


# ---------------------------------------------------------------------------
# Modo preguntar: un arquitecto simulado que contesta con su cuadro (2026-09-17)
# ---------------------------------------------------------------------------
#
# PRD `docs/prd/2026-09-17-modo-preguntar.md`, §12. **Lo que mide y lo que no.** Mide
# cuántas preguntas haría ArchMuse y si, contestadas, la tabla sale completa y sin cifras
# incorrectas. No mide si el arquitecto contestaría así: contesta **con su propio
# cuadro**, que es lo que él sabe, y cuando su cuadro no basta para contestar, no
# contesta (como un Esc). Las cifras siguen saliendo de la medición: una respuesta sólo
# dice pertenencia, nombre o qué polilínea es la construida.
#
# - **¿Esta pieza es de VTx?** «Sí» si su cuadro tiene, en esa familia, una cifra libre
#   (que no lleve ya otra pieza de la tabla) igual a la de la pieza; «No» si su cuadro
#   no tiene ninguna cifra libre de esa familia; si tiene otra cifra, no contesta.
# - **La construida:** la polilínea del plano, de cualquier capa, cuya superficie es la
#   de su cuadro. Si no hay exactamente una, no contesta. La comprobación de `C-12` la
#   hace ArchMuse con la respuesta (D-6), no el arquitecto simulado.
# - **Nombre:** el que, en su cuadro, tiene una cifra libre igual a la de la pieza.
# - **Interior o exterior:** su cuadro no dice de qué familia es un nombre que ArchMuse no
#   reconoce, así que no contesta.

def _referencias_por_familia(celdas) -> Dict[str, List[float]]:
    salida: Dict[str, List[float]] = {}
    for celda in celdas:
        if celda.campo in CAMPOS_DE_CIERRE:
            continue
        valor = cifra_de_referencia(celda.texto_actual)
        if valor is not None:
            salida.setdefault(_familia(celda.campo), []).append(valor)
    return salida


class ArquitectoSimulado:
    def __init__(self, doc, plano, celdas, vecinas=()):
        self.doc, self.plano = doc, plano
        #: Las piezas de otras viviendas por las que ArchMuse puede preguntar (sus `Room`).
        self.vecinas = list(vecinas)
        self.referencias = _referencias_por_familia(celdas)
        construida = next((c for c in celdas if c.campo == "superficie_construida_cerrada"), None)
        self.construida = cifra_de_referencia(construida.texto_actual) if construida else None
        self.recintos = {r.handle: r for r in plano.rooms if getattr(r, "handle", None)}
        self._polilineas = None

    def _libres(self, plantilla) -> Dict[str, List[float]]:
        libres = {f: list(v) for f, v in self.referencias.items()}
        for fila in list(plantilla.interiores) + list(plantilla.exteriores):
            if not fila.valor:
                continue
            valor = cs.superficie_en_m2(fila.valor)
            lista = libres.get(_familia(cs.campo_de_la_pieza(fila.rotulo) or ""), [])
            igual = next((x for x in lista if valor is not None and coinciden(x, valor)), None)
            if igual is not None:
                lista.remove(igual)
        return libres

    def contestar(self, pregunta, plantilla) -> Optional[dict]:
        """`{"id", "valor"}` como la manda el comando, o `None` (no contesta)."""
        if pregunta.tipo == rda.PERTENENCIA:
            recinto = self.recintos.get(pregunta.resaltar[0]) if pregunta.resaltar else None
            familia = _familia(cs.campo_de_la_pieza(recinto.label or "") or "") if recinto else ""
            if not familia:
                return None
            libres = self._libres(plantilla).get(familia, [])
            area = round(recinto.polygon.area + 1e-9, 2)
            iguales = [x for x in libres if coinciden(x, area)]
            if iguales:
                # **Sin adivinar cuál** (medido en el banco, 2026-09-17): en plantas simétricas
                # su baño y el de la vecina miden lo mismo, y su cuadro no dice cuál de los dos
                # es el suyo. Si hay más piezas posibles con esa cifra que cifras libres, no
                # contesta.
                posibles = [f for f in list(plantilla.interiores) + list(plantilla.exteriores)
                            if not f.valor and _familia(cs.campo_de_la_pieza(f.rotulo) or "") == familia
                            and coinciden(round(f.area_m2 + 1e-9, 2), area)]
                posibles += [r for r in self.vecinas
                             if _familia(cs.campo_de_la_pieza(r.label or "") or "") == familia
                             and coinciden(round(r.polygon.area + 1e-9, 2), area)]
                return {"id": pregunta.id, "valor": "Si"} if len(posibles) <= len(iguales) else None
            return None if libres else {"id": pregunta.id, "valor": "No"}
        if pregunta.tipo == rda.CONSTRUIDA:
            if self.construida is None:
                return None
            if self._polilineas is None:
                self._polilineas = pc.polilineas_del_plano(self.doc, pc._factor_a_metros(self.plano))
            iguales = [h for h, poligono in self._polilineas
                       if coinciden(round(poligono.area + 1e-9, 2), self.construida)]
            return {"id": pregunta.id, "valor": iguales[0]} if len(iguales) == 1 else None
        if pregunta.tipo == rda.NOMBRE:
            recinto = self.recintos.get(pregunta.resaltar[0]) if pregunta.resaltar else None
            if recinto is None:
                return None
            area = round(recinto.polygon.area + 1e-9, 2)
            libres = self._libres(plantilla)
            buenas = [i for i, opcion in enumerate(pregunta.opciones, start=1)
                      if any(coinciden(x, area) for x in
                             libres.get(_familia(cs.campo_de_la_pieza(opcion) or ""), []))]
            return {"id": pregunta.id, "valor": str(buenas[0])} if len(buenas) == 1 else None
        return None


def preguntar_y_responder(doc, plano, nombre, medida, posicion, celdas):
    """El turno del comando con el arquitecto simulado: `(plantilla, preguntas)`, con
    `preguntas` = `[(tipo, contestación o None)]` en el orden en que se hicieron."""
    plantilla = pc.construir(doc, plano, nombre, medida=medida, posicion=posicion, preguntar=True)
    lugar = posicion if posicion is not None else next(
        i for i, v in enumerate(medida.viviendas) if v.nombre == nombre)
    yo = rda.Vivienda(plantilla.vivienda, plantilla.rotulo_de_la_vivienda)
    vecinas = [r for r, *_ in pc._piezas_vecinas_en_duda(plano, medida, lugar, yo, rda.Respuestas())]
    arquitecto = ArquitectoSimulado(doc, plano, celdas, vecinas)
    registros: List[dict] = []
    sin, respondidas, hechas = set(), set(), []
    while plantilla.preguntas_al_arquitecto and len(hechas) < rda.MAXIMO_DE_PREGUNTAS:
        for pregunta in plantilla.preguntas_al_arquitecto:
            contestacion = arquitecto.contestar(pregunta, plantilla)
            hechas.append((pregunta.tipo, contestacion["valor"] if contestacion else None))
            if contestacion is None:
                sin.add(pregunta.id)
                continue
            respondidas.add(pregunta.id)
            registros = rda.fusionar(registros, rda.desde_peticion(
                {"respuestas_del_arquitecto": [contestacion]})[1])
        plantilla = pc.construir(doc, plano, nombre, medida=medida, posicion=posicion,
                                 preguntar=True, respuestas=rda.Respuestas(
                                     tuple(registros), frozenset(sin), len(hechas), {},
                                     frozenset(respondidas)))
    return plantilla, hechas


def _completa(filas, sobrantes) -> bool:
    con_referencia = [f for f in filas if f["estado"] != REFERENCIA_INEXISTENTE]
    return bool(con_referencia) and not sobrantes and all(
        f["estado"] == COINCIDENCIA for f in con_referencia)


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
    if sin_explicar or sin_motivo:
        partes = []
        if sin_explicar:
            partes.append("%d MISMATCH sin explicar" % len(sin_explicar))
        if sin_motivo:
            partes.append("%d campo(s) vacío(s) sin motivo" % len(sin_motivo))
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

    def coma(valor, decimales):
        return ("%.*f" % (decimales, valor)).replace(".", ",")

    def fila_de_intervenciones(etiqueta, i):
        return "| %s | %d | %d | %d | %d | %d | %d | %s | %s %% | %s %% |" % (
            etiqueta, i["viviendas"], i["automatico"], i["un_clic"], i["vacio"],
            i["cifras_incorrectas"], i["filas_sin_celda"], coma(i["intervenciones_por_vivienda"], 2),
            coma(i["sin_intervencion_pct"], 1), coma(i["completas_con_un_clic_pct"], 1))

    lineas += ["", "## Intervenciones", "",
               "Cada celda de su cuadro con cifra: **AUTOMÁTICO** (ArchMuse lo resuelve solo), "
               "**UN CLIC** (lo resolvería una pregunta simple al arquitecto) o **VACÍO** (queda "
               "vacío con motivo). **Cifras incorrectas (objetivo: 0)**: las distintas de su cuadro "
               "sin explicar, más las filas con cifra que su cuadro no tiene.", "",
               "| Plano | Viviendas | AUTOMÁTICO | UN CLIC | VACÍO | Cifras incorrectas | "
               "De ellas, filas que su cuadro no tiene | Intervenciones por vivienda | "
               "Sin ninguna intervención | Completas con los UN CLIC |",
               "|---|---|---|---|---|---|---|---|---|---|"]
    lineas += [fila_de_intervenciones(d["plano"], resumen_de_intervenciones(d.get("intervenciones", [])))
               for d in detalles]
    lineas += [fila_de_intervenciones(
        "Total", resumen_de_intervenciones([v for d in detalles for v in d.get("intervenciones", [])])),
        "",
        "*Intervenciones por vivienda* = celdas UN CLIC / viviendas con cuadro. Una pregunta puede "
        "resolver varias celdas, así que cuenta de más. *Completas con los UN CLIC* supone que la "
        "respuesta basta para que la celda salga bien: no se ha medido, porque ArchMuse todavía "
        "no pregunta. Una vivienda con una fila que su cuadro no tiene no cuenta como resuelta. "
        "**Límite de las filas que su cuadro no tiene:** una estancia bien medida que el "
        "arquitecto no puso en su cuadro también sale ahí; hay que revisarlas una a una."]
    viviendas = [v for d in detalles for v in d.get("intervenciones", [])]
    con_preguntas = [v for v in viviendas if "preguntar" in v]
    lineas += ["", "## Modo preguntar (arquitecto simulado con su cuadro)", "",
               "Contesta con su propio cuadro; si su cuadro no basta, no contesta (como un Esc). "
               "Las cifras siguen saliendo de la medición. Ver `benchmark/ejecutar.py`.", "",
               "| Viviendas | Completas antes | Preguntas hechas | Sin respuesta | Completas después "
               "| Celdas vacías antes | Celdas vacías después | Cifras incorrectas después |",
               "|---|---|---|---|---|---|---|---|"]
    if con_preguntas:
        pr = [v["preguntar"] for v in con_preguntas]
        lineas.append("| %d | %d | %d | %d | %d | %d | %d | %d |" % (
            len(pr), sum(x["completa_antes"] for x in pr), sum(len(x["preguntas"]) for x in pr),
            sum(x["sin_respuesta"] for x in pr), sum(x["completa_despues"] for x in pr),
            sum(x["celdas_vacias_antes"] for x in pr), sum(x["celdas_vacias_despues"] for x in pr),
            sum(x["cifras_distintas_despues"] + len(x["filas_sin_celda_despues"]) for x in pr)))
        lineas += ["", "| Vivienda | Preguntas | Sin respuesta | Completa antes | Completa después "
                       "| Vacías antes → después |", "|---|---|---|---|---|---|"]
        for v in con_preguntas:
            x = v["preguntar"]
            lineas.append("| %s | %s | %d | %s | %s | %d → %d |" % (
                v["vivienda"], ", ".join("%s: %s" % (t, c or "sin respuesta") for t, c in x["preguntas"])
                or "ninguna", x["sin_respuesta"], "sí" if x["completa_antes"] else "no",
                "sí" if x["completa_despues"] else "no", x["celdas_vacias_antes"],
                x["celdas_vacias_despues"]))
    unidades = [v["unidades"] for v in viviendas if "unidades" in v]
    lineas += ["", "## Número de unidades (C-8)", "",
               "| Cuadros | Coinciden | Vacías en ArchMuse | Distintas |", "|---|---|---|---|",
               "| %d | %d | %d | %d |" % (
                   len(unidades), sum(1 for u in unidades if u["archmuse"] and u["archmuse"] == u["referencia"]),
                   sum(1 for u in unidades if not u["archmuse"]),
                   sum(1 for u in unidades if u["archmuse"] and u["archmuse"] != u["referencia"]))]
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
                         "intervenciones": [], "lectura": None, "viviendas_detectadas": 0,
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
            intervenciones = resumen_de_intervenciones(d["intervenciones"])
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
                    "automatico": intervenciones["automatico"], "un_clic": intervenciones["un_clic"],
                    "vacio": intervenciones["vacio"],
                    "cifras_distintas": intervenciones["cifras_distintas"],
                    "filas_sin_celda": intervenciones["filas_sin_celda"],
                    "cifras_incorrectas": intervenciones["cifras_incorrectas"],
                    "intervenciones_por_vivienda": "%.2f" % intervenciones["intervenciones_por_vivienda"],
                    "viviendas_sin_intervencion_pct": "%.1f" % intervenciones["sin_intervencion_pct"],
                    "viviendas_completas_con_un_clic_pct":
                        "%.1f" % intervenciones["completas_con_un_clic_pct"],
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
