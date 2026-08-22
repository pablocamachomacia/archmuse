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
