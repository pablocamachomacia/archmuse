"""Exportación a DXF de los contornos de una planta ya analizada o generada.

`docs/prd/2026-08-17-viabilidad-economica-y-exportacion-dxf.md`, tarea 1 del
plan de implementación. Punto de partida honesto (§0/§9 del PRD): un
proyecto de ArchMuse -- analizado desde un DXF real o generado con IA -- solo
tiene, en su modelo de datos común, POLÍGONOS DE HABITACIÓN (el mismo dato
que ya dibuja `analyzer/plan_svg.py`). No hay muros con espesor, ni puertas
con simbología de apertura, ni huecos de ventana posicionados en ningún punto
del pipeline. Este módulo exporta exactamente eso, con la misma fidelidad que
el dato soporta -- nunca más: una polilínea cerrada por estancia, en una capa
con su nombre, con una etiqueta de texto en el centroide. Ningún texto de
interfaz que use este módulo debe describir el resultado como "muros,
puertas y huecos" (criterio de aceptación §8.4 del PRD).

Función pura, sin I/O: no sube nada, no guarda nada en disco. Quien llame
decide cómo servir el `ezdxf.Document` devuelto (típicamente volcándolo a
`io.StringIO`/`io.BytesIO` para una descarga HTTP, ver `app.py`).
"""
from __future__ import annotations

import re
from typing import Any, Iterable

import ezdxf
from ezdxf.document import Drawing

_CAPA_INVALIDA = re.compile(r"[^A-Za-z0-9_\-]")
_NOMBRE_CAPA_DEFECTO = "ESTANCIA"


def _nombre_capa(nombre: str) -> str:
    """Normaliza un nombre de estancia a un nombre de capa DXF seguro:
    algunos lectores CAD antiguos no aceptan espacios/acentos en nombres de
    capa -- se sustituyen por `_` y se pasa a mayúsculas, mismo criterio
    simple que el resto del proyecto usa para claves derivadas de texto
    libre. Nunca lanza: una entrada vacía o solo de caracteres inválidos
    devuelve `_NOMBRE_CAPA_DEFECTO`, no una capa sin nombre."""
    limpio = _CAPA_INVALIDA.sub("_", nombre.strip().upper())
    limpio = limpio.strip("_")
    return limpio[:255] if limpio else _NOMBRE_CAPA_DEFECTO


def _puntos_validos(poligono: Any) -> list[tuple[float, float]]:
    """`poligono` -> lista de `(x, y)` float, o `[]` si no hay al menos 3
    puntos numéricos utilizables. Tolerante con datos de entrada (mismo
    criterio que el resto del pipeline): nunca lanza por un punto mal
    formado, simplemente lo descarta."""
    if not isinstance(poligono, list):
        return []
    puntos = []
    for p in poligono:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            continue
        try:
            puntos.append((float(p[0]), float(p[1])))
        except (TypeError, ValueError):
            continue
    return puntos if len(puntos) >= 3 else []


def exportar_planta_dxf(habitaciones: Iterable[dict]) -> Drawing:
    """Construye un `ezdxf.Document` con una polilínea cerrada por estancia
    de `habitaciones` -- el mismo dato (`poligono`, `nombre`) que ya recibe
    `analyzer/plan_svg.py` para dibujar el SVG del plano, servido aquí en
    formato DXF en vez de SVG. Cada estancia va en su propia capa (nombre
    normalizado, ver `_nombre_capa`) con una etiqueta de texto en su
    centroide aproximado -- para que el archivo sea legible en un CAD
    externo sin tener que adivinar qué contorno es cada cosa.

    Cualquier entrada sin `poligono` válido (menos de 3 puntos utilizables)
    se omite en silencio -- mismo criterio tolerante que el resto del
    pipeline con datos de entrada incompletos, nunca un error 5xx por una
    habitación mal formada."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    capas_creadas: set[str] = set()

    for h in habitaciones:
        if not isinstance(h, dict):
            continue
        puntos = _puntos_validos(h.get("poligono"))
        if not puntos:
            continue
        nombre = str(h.get("nombre") or "").strip() or "Estancia"
        capa = _nombre_capa(nombre)
        if capa not in capas_creadas:
            doc.layers.add(name=capa)
            capas_creadas.add(capa)

        msp.add_lwpolyline(puntos, close=True, dxfattribs={"layer": capa})

        cx = sum(p[0] for p in puntos) / len(puntos)
        cy = sum(p[1] for p in puntos) / len(puntos)
        texto = msp.add_text(nombre, dxfattribs={"layer": capa, "height": 0.25})
        texto.set_placement((cx, cy))

    return doc
