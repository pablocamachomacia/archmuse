# -*- coding: utf-8 -*-
"""Lectura compartida de un paquete de borradores de curación.

Un «paquete» son los ficheros `normativa/es/estatal/<prefijo>*.yaml` (con su
`_` delante: invisibles al loader de producción). Este módulo los enumera y
aplana en filas estables — la misma numeración R-01, R-02… en la hoja
impresa, en el ledger y en el volcado, porque las tres cosas tienen que
hablar de la misma fila.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, cast

import yaml

from normativa import loader
from normativa.firma import hash_de_contenido_firmado

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_CORPUS = RAIZ / "normativa" / "es" / "estatal"
PREFIJO_POR_DEFECTO = "_paquete_dbsi3_"

_CID = "es.rd_314_2006.seguridad_incendio."

#: La selección de la sesión p1 (lunes 25), decidida por Pablo el 22-08: solo
#: lo evaluable que la skill de recorridos consume o va a consumir de
#: inmediato. Fuera las definiciones (no evaluables) y el resto de reglas
#: transcritas, que quedan en borrador. El ORDEN de esta tupla es el orden de
#: la hoja: la regla que la skill usa hoy va primera. La numeración R-01… se
#: deriva de aquí, así que hoja y volcado hablan de la misma fila.
SELECCION_P1 = (
    _CID + "longitud_recorrido_evacuacion",
    _CID + "incremento_recorridos_extincion_automatica",
    _CID + "ocupacion_maxima_salida_unica",
    _CID + "altura_evacuacion_maxima_salida_unica",
    _CID + "anchura_minima_elementos_evacuacion",
    _CID + "anchura_hoja_puerta_evacuacion",
)


@dataclass(frozen=True)
class Fila:
    """Una regla del paquete, con todo lo que la hoja y el volcado necesitan."""
    numero: str            # "R-01"
    fichero: Path
    norma: Dict[str, Any]
    regla: Dict[str, Any]
    huella: str            # hash_de_contenido_firmado, 64 hex

    @property
    def concept_id(self) -> str:
        return self.regla.get("concept_id", "")

    @property
    def huella_corta(self) -> str:
        return self.huella[:10]


def cargar_paquete(prefijo: str = PREFIJO_POR_DEFECTO,
                   carpeta: Path = CARPETA_CORPUS) -> List[Fila]:
    """Las filas del paquete, en orden estable (ficheros y reglas por orden)."""
    filas: List[Fila] = []
    for ruta in sorted(carpeta.glob(prefijo + "*.yaml")):
        doc = cast(Dict[str, Any], loader.normalizar_fechas(
            yaml.safe_load(ruta.read_text(encoding="utf-8"))))
        norma = doc.get("norma") or {}
        for regla in doc.get("reglas") or []:
            filas.append(Fila(
                numero="R-%02d" % (len(filas) + 1),
                fichero=ruta,
                norma=norma,
                regla=regla,
                huella=hash_de_contenido_firmado(norma, regla),
            ))
    return filas


def seleccionar(filas: List[Fila], seleccion) -> List[Fila]:
    """Las filas de una selección, renumeradas R-01… en el orden de la
    selección. Un concept_id de la selección que no esté en el paquete falla
    con KeyError, a propósito: una hoja con una fila de menos en silencio es
    peor que un error."""
    if not seleccion:
        return list(filas)
    por_cid = {f.concept_id: f for f in filas}
    resultado: List[Fila] = []
    for cid in seleccion:
        f = por_cid[cid]
        resultado.append(Fila(numero="R-%02d" % (len(resultado) + 1),
                              fichero=f.fichero, norma=f.norma,
                              regla=f.regla, huella=f.huella))
    return resultado


def huella_del_paquete(filas: List[Fila]) -> str:
    """SHA-256 de la concatenación ordenada de huellas de fila: identifica el
    paquete entero. Va en la cabecera de la hoja y al pie del anexo, para atar
    las dos partes del documento impreso."""
    return hashlib.sha256(
        "".join(f.huella for f in filas).encode("ascii")).hexdigest()


def localizacion(fila: Fila) -> str:
    """Dónde comprobarlo en un minuto: «DB-SI, SI 3 §3, tabla 3.1»."""
    articulo = fila.norma.get("articulo") or {}
    partes = [articulo.get("documento_basico") or "",
              articulo.get("seccion") or ""]
    if articulo.get("apartado"):
        partes.append("§" + str(articulo["apartado"]))
    if articulo.get("punto"):
        partes.append("punto " + str(articulo["punto"]))
    if articulo.get("tabla"):
        partes.append("tabla " + str(articulo["tabla"]))
    return ", ".join(p for p in partes if p)


def exigencia_resumida(fila: Fila) -> str:
    """La exigencia en lenguaje de arquitecto, valores incluidos, para la fila
    de la hoja. No sustituye al literal (que va en el anexo): es lo que se
    coteja CONTRA el literal."""
    regla = fila.regla
    if regla.get("tipo") == "definicion":
        return "Definición (no evaluable). %s" % (regla.get("explicacion_tecnica") or "")
    parametro = regla.get("parametro") or {}
    unidad = parametro.get("unidad") or ""
    trozos = []
    for valor in parametro.get("valores") or []:
        ejes = "; ".join("%s: %s" % (k.replace("_", " "), str(v).replace("_", " "))
                         for k, v in valor.items() if k != "valor")
        cifra = str(valor.get("valor")).replace(".", ",")
        trozos.append("%s %s (%s)" % (cifra, unidad, ejes) if ejes
                      else "%s %s" % (cifra, unidad))
    usos = ", ".join((regla.get("aplicabilidad") or {}).get("usos") or []) or "todos los usos"
    return "%s — %s. Aplica a: %s." % (regla.get("nombre", ""), " · ".join(trozos), usos)
