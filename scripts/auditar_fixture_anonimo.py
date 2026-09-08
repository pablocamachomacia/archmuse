#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audita un DXF antes de dejarlo entrar al repositorio público.

**No comprueba que la anonimización se hizo: comprueba que no queda nada.** Es
la diferencia que pidió Pablo el 2026-09-08 — «no me fío de que baste con
borrar capas». Este script no confía en `derivar_fixture_anonimo.py`: abre el
fichero de salida como si viniera de un desconocido y **enseña todo lo que
contiene texto**, para que la revisión sea de lo que hay y no de lo que se
pretendía dejar.

Recorre, y en este orden:

1. **Todas las variables de cabecera** que pueden llevar rastro (`$LASTSAVEDBY`,
   `$PROJECTNAME`, `$HYPERLINKBASE`, `$FINGERPRINTGUID`…).
2. **Todas las capas**, incluidas las apagadas y las congeladas.
3. **Todas las definiciones de bloque**, estén insertadas o no. Aquí es donde
   viven los nombres de vivienda del export de Revit de los planos reales.
4. **Todos los estilos de texto, tipos de línea y estilos de cota.**
5. **Todo el texto de todas las entidades** de todos los layouts, entrando en
   los bloques: `TEXT`, `MTEXT`, `ATTRIB`, `ATTDEF`, `DIMENSION`, `MLEADER`.
6. **Todo el `XDATA` y todos los diccionarios/`XRECORD`** del documento.
7. **Las propiedades personalizadas** del documento.

Al final compara el texto encontrado contra la lista de lo que se espera —
rótulos de estancia y códigos `VT<n>/<m>`— y **señala en rojo cualquier cosa que
no encaje**. Un texto inesperado no es necesariamente una fuga; es algo que hay
que mirar con los ojos antes de commitear.

Uso:

    python scripts/auditar_fixture_anonimo.py <fichero.dxf>
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ezdxf  # noqa: E402

#: Cabeceras que han llevado alguna vez el nombre de una persona, de una ruta o
#: de un proyecto. No es una lista exhaustiva del formato: se imprimen TODAS las
#: cabeceras con valor de texto, y éstas además se señalan.
CABECERAS_SENSIBLES = (
    "$LASTSAVEDBY", "$PROJECTNAME", "$HYPERLINKBASE", "$FINGERPRINTGUID",
    "$VERSIONGUID", "$TITLE", "$SUBJECT", "$AUTHOR", "$KEYWORDS", "$COMMENTS",
)

#: Lo que sí se espera encontrar: códigos de tipología y rótulos de estancia.
PATRON_VIVIENDA = re.compile(r"^VT\d+/\d+$")
ROTULOS_ESPERADOS = re.compile(
    r"^(sal[oó]n|cocina|sal[oó]n\s*[/y+]\s*cocina|dormitorio|ba[ñn]o|aseo|"
    r"pasillo|distribuidor|vest[ií]bulo|terraza|tendedero|lavadero|trastero|"
    r"despensa|armario|estar|comedor|hall|recibidor|porche|balc[oó]n)"
    r"[\s\d/y+.\-]*$", re.IGNORECASE)


def _texto_de(entidad) -> str:
    for via in ("plain_text", ):
        try:
            return str(getattr(entidad, via)()).strip()
        except Exception:  # noqa: BLE001
            pass
    for atributo in ("text", "tag", "insert_text", "default"):
        try:
            valor = getattr(entidad.dxf, atributo, None)
            if valor:
                return str(valor).strip()
        except Exception:  # noqa: BLE001
            pass
    return ""


def auditar(ruta: str) -> int:
    doc = ezdxf.readfile(ruta)
    problemas = 0

    print("=" * 72)
    print("AUDITORÍA DE %s  (%d bytes)" % (ruta, os.path.getsize(ruta)))
    print("=" * 72)

    # -- 1. Cabecera --------------------------------------------------------
    print("\n[1] CABECERA — todas las variables con valor de texto")
    encontradas = 0
    for clave, valor in sorted(doc.header.hdrvars.items()):
        bruto = getattr(valor, "value", valor)
        if isinstance(bruto, str) and bruto.strip():
            marca = "  <-- SENSIBLE" if clave in CABECERAS_SENSIBLES else ""
            print("    %-20s %r%s" % (clave, bruto, marca))
            encontradas += 1
            if clave in CABECERAS_SENSIBLES and bruto.strip():
                problemas += 1
    if not encontradas:
        print("    (ninguna)")

    # -- 2. Capas -----------------------------------------------------------
    capas = sorted(c.dxf.name for c in doc.layers)
    print("\n[2] CAPAS (%d), incluidas apagadas y congeladas" % len(capas))
    for nombre in capas:
        print("    %s" % nombre)

    # -- 3. Definiciones de bloque -----------------------------------------
    bloques = sorted(b.name for b in doc.blocks if not b.name.startswith("*"))
    print("\n[3] DEFINICIONES DE BLOQUE (%d), insertadas o no" % len(bloques))
    for nombre in bloques:
        print("    %s" % nombre)
    if bloques:
        problemas += len(bloques)
        print("    ^^ un fixture derivado no debería tener NINGUNO")

    # -- 4. Estilos ---------------------------------------------------------
    estilos = sorted(e.dxf.name for e in doc.styles)
    tipos = sorted(t.dxf.name for t in doc.linetypes)
    cotas = sorted(d.dxf.name for d in doc.dimstyles)
    print("\n[4] ESTILOS  texto=%s  linea=%s  cota=%s" % (estilos, tipos, cotas))

    # -- 5. Todo el texto de todas las entidades ---------------------------
    print("\n[5] TEXTO DE TODAS LAS ENTIDADES (modelspace, layouts y bloques)")
    textos = []
    espacios = [("modelspace", doc.modelspace())]
    for layout in doc.layouts:
        if layout.name.lower() != "model":
            espacios.append(("layout:%s" % layout.name, layout))
    for bloque in doc.blocks:
        # Los `*Model_Space` / `*Paper_Space` son los propios layouts vistos como
        # bloque: ya se han recorrido arriba y duplicarlos aquí sólo llena la
        # auditoría de ruido, que es lo que hace que no se lea.
        if not bloque.name.startswith("*"):
            espacios.append(("bloque:%s" % bloque.name, bloque))

    for donde, espacio in espacios:
        for entidad in espacio:
            tipo = entidad.dxftype()
            if tipo in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF", "DIMENSION",
                        "MULTILEADER", "MLEADER"):
                texto = _texto_de(entidad)
                if texto:
                    textos.append((donde, tipo, texto))
            for attrib in getattr(entidad, "attribs", ()) or ():
                texto = _texto_de(attrib)
                if texto:
                    textos.append((donde, "ATTRIB", texto))

    for donde, tipo, texto in textos:
        print("    [%-14s] %-8s %r" % (donde[:14], tipo, texto))
    if not textos:
        print("    (ninguno)")

    # -- 6. XDATA y diccionarios -------------------------------------------
    print("\n[6] XDATA Y DICCIONARIOS")
    con_xdata = 0
    for espacio_nombre, espacio in espacios:
        for entidad in espacio:
            if getattr(entidad, "xdata", None):
                print("    XDATA en %s / %s" % (espacio_nombre, entidad.dxftype()))
                con_xdata += 1
                problemas += 1
    if not con_xdata:
        print("    Ninguna entidad con XDATA")
    claves = sorted(doc.rootdict.keys())
    print("    Diccionario raíz: %s" % ", ".join(claves))

    # -- 7. Propiedades del documento --------------------------------------
    print("\n[7] PROPIEDADES DEL DOCUMENTO")
    try:
        meta = doc.ezdxf_metadata()
        for clave in list(meta):
            print("    %s = %r" % (clave, meta.get(clave)))
    except Exception:  # noqa: BLE001
        print("    (sin metadatos de ezdxf)")

    # -- Veredicto ----------------------------------------------------------
    print("\n" + "=" * 72)
    inesperados = [
        (d, t, x) for d, t, x in textos
        if not PATRON_VIVIENDA.match(x) and not ROTULOS_ESPERADOS.match(x)
    ]
    if inesperados:
        problemas += len(inesperados)
        print("TEXTO INESPERADO — MIRAR UNO A UNO ANTES DE COMMITEAR:")
        for donde, tipo, texto in inesperados:
            print("    [%s] %s %r" % (donde, tipo, texto))
    else:
        print("Todo el texto encaja con lo esperado: rótulos de estancia y "
              "códigos VT<n>/<m>.")

    print("\nRESULTADO: %s" % ("%d cosa(s) que revisar" % problemas if problemas
                               else "limpio"))
    print("=" * 72)
    return 1 if problemas else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fichero")
    args = ap.parse_args()
    return auditar(args.fichero)


if __name__ == "__main__":
    raise SystemExit(main())
