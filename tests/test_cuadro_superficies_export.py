# -*- coding: utf-8 -*-
"""Fase 3 — exportación de la copia DXF con el cuadro de superficies relleno
(`analyzer/cuadro_superficies_export.py`).

Ejecutar:  python tests/test_cuadro_superficies_export.py

Usa el `v2s.dxf` real que apunte `ARCHMUSE_DXF_V2S` (mismo criterio que
`tests/test_cuadro_superficies.py`: si no está disponible, se salta con
aviso). Genera de verdad `v2s_ArchMuse_relleno.dxf` en la misma carpeta que el
original -- es el propio entregable de la Fase 3, así que este test NO lo borra
al terminar.

Que protege:

1. El DXF original queda BYTE A BYTE idéntico (hash SHA-256 antes/después).
2. Se crea únicamente el archivo de salida esperado, nada más en el directorio.
3. La copia se reabre con `ezdxf.readfile` sin excepción, y `audit()` no
   encuentra errores.
4. Cada celda escrita tiene la capa/altura/estilo/alineación/coordenada
   exactas que pide el encargo.
5. Ninguna celda BLOQUEADA lleva un número -- siempre literalmente "N/D".
6. "VIVIENDA TIPO" no se duplica: sigue habiendo exactamente un MTEXT con
   ese contenido en toda la tabla.
"""
import hashlib
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

fallos = []
comprobaciones = 0


def check(ok, etiqueta, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s%s" % ("OK  " if ok else "FALLO", etiqueta, ("  -> " + detalle) if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


#: `v2s.dxf` es un plano real de un cliente: no está en el repositorio ni puede
#: estarlo. Se localiza con la variable de entorno `ARCHMUSE_DXF_V2S`. Sin ella
#: esta parte se salta, igual que antes — lo que ya no hay es la ruta personal
#: de nadie escrita en un repositorio público.
ORIGEN = os.environ.get("ARCHMUSE_DXF_V2S", "")
#: El entregable se genera JUNTO al origen, sea cual sea su carpeta.
DESTINO = os.path.join(os.path.dirname(ORIGEN), "v2s_ArchMuse_relleno.dxf") if ORIGEN else ""

if not os.path.exists(ORIGEN):
    print("(v2s.dxf no disponible (define ARCHMUSE_DXF_V2S con su ruta) -- test omitido, mismo criterio que")
    print(" tests/test_cuadro_superficies.py / tests/test_analizar_planta.py)")
    print("Todas las comprobaciones OK (0)")
    sys.exit(0)

directorio = os.path.dirname(ORIGEN)

if os.path.exists(DESTINO):
    os.remove(DESTINO)  # limpio ANTES de tomar la foto "antes", para que el test 2 sea concluyente
                         # aunque el test ya se haya ejecutado antes en este mismo directorio

otros_relleno_antes = set(
    f for f in os.listdir(directorio) if f.startswith("v2s") and "relleno" in f.lower()
)

with open(ORIGEN, "rb") as f:
    hash_origen_antes = hashlib.sha256(f.read()).hexdigest()
tam_origen_antes = os.path.getsize(ORIGEN)

from analyzer.cuadro_superficies_export import (  # noqa: E402
    ALTURA_TEXTO,
    CAPA_CUADRO,
    ESTILO_TEXTO,
    PUNTO_INSERCION,
    exportar_cuadro_relleno,
)
from analyzer.cuadro_superficies import BLOQUEADO, NO_DISPONIBLE  # noqa: E402

resultado = exportar_cuadro_relleno(ORIGEN, DESTINO)


print()
print("1. El original permanece idéntico")
print("-" * 68)

with open(ORIGEN, "rb") as f:
    hash_origen_despues = hashlib.sha256(f.read()).hexdigest()
check(hash_origen_despues == hash_origen_antes, "sha256 de v2s.dxf sin cambios")
check(os.path.getsize(ORIGEN) == tam_origen_antes, "tamaño de v2s.dxf sin cambios")


print()
print("2. Se crea únicamente la copia de salida")
print("-" * 68)

check(os.path.exists(DESTINO), "el archivo de salida existe", DESTINO)
otros_relleno_despues = set(
    f for f in os.listdir(directorio) if f.startswith("v2s") and "relleno" in f.lower()
)
nuevos = otros_relleno_despues - otros_relleno_antes
check(nuevos == {os.path.basename(DESTINO)},
      "no aparece ningún otro archivo *relleno* además del esperado", str(nuevos))


print()
print("3. La copia se abre con ezdxf sin corromperse")
print("-" * 68)

import ezdxf  # noqa: E402

try:
    doc_copia = ezdxf.readfile(DESTINO)
    check(True, "ezdxf.readfile(destino) no lanza excepción")
except Exception as exc:  # noqa: BLE001
    check(False, "ezdxf.readfile(destino) no lanza excepción", str(exc))
    print("\nNo se puede continuar sin poder abrir la copia.")
    sys.exit(1)

auditor = doc_copia.audit()
check(not auditor.has_errors, "doc.audit() no encuentra errores en la copia",
      "; ".join(e.message for e in auditor.errors[:3]) if auditor.has_errors else "")
check(resultado.reabierta_sin_errores is True, "exportar_cuadro_relleno() también confirma la reapertura")


print()
print("4. Cada celda escrita tiene capa/altura/estilo/alineación/coordenada correctos")
print("-" * 68)

msp_copia = doc_copia.modelspace()
mtexts_nuevos = {}
for m in msp_copia.query("MTEXT[layer=='%s']" % CAPA_CUADRO):
    mtexts_nuevos.setdefault(m.text, []).append(m)

esperado = {c.campo: c for c in resultado.celdas_escritas}
check(len(resultado.celdas_escritas) == 17, "se escribieron 17 celdas (18 menos VIVIENDA TIPO)",
      "%d" % len(resultado.celdas_escritas))

for celda in resultado.celdas_escritas:
    coincidencias = [
        m for lista in mtexts_nuevos.values() for m in lista
        if abs(m.dxf.insert.x - celda.x) < 1e-3 and abs(m.dxf.insert.y - celda.y) < 1e-3
    ]
    ok_una = len(coincidencias) == 1
    check(ok_una, "%s: exactamente un MTEXT en su coordenada destino" % celda.campo,
          "%d encontrados" % len(coincidencias))
    if not ok_una:
        continue
    m = coincidencias[0]
    check(m.text == celda.texto, "%s: texto correcto" % celda.campo, m.text)
    check(m.dxf.layer == CAPA_CUADRO, "%s: capa %s" % (celda.campo, CAPA_CUADRO), m.dxf.layer)
    check(abs(m.dxf.char_height - ALTURA_TEXTO) < 1e-6,
          "%s: char_height %.2f" % (celda.campo, ALTURA_TEXTO), str(m.dxf.char_height))
    check(m.dxf.style == ESTILO_TEXTO, "%s: estilo %s" % (celda.campo, ESTILO_TEXTO), m.dxf.style)
    check(m.dxf.attachment_point == PUNTO_INSERCION,
          "%s: attachment_point %d (centrado)" % (celda.campo, PUNTO_INSERCION), str(m.dxf.attachment_point))


print()
print("5. Ninguna celda BLOQUEADA lleva una cifra")
print("-" * 68)

campos_bloqueados_o_nd = {"tendedero", "terraza_1", "terraza_2", "total_util_exterior", "total_util",
                           "superficie_construida_cerrada", "superficie_construida_exterior",
                           "numero_unidades"}
for campo, celda in esperado.items():
    if campo in campos_bloqueados_o_nd:
        check(celda.texto == "N/D", "%s escrito como N/D, nunca un número" % campo, celda.texto)
        check("m²" not in celda.texto, "%s no contiene 'm²'" % campo, celda.texto)
    else:
        check("N/D" not in celda.texto, "%s SÍ lleva un valor numérico (no N/D)" % campo, celda.texto)


print()
print("6. VIVIENDA TIPO no se duplica")
print("-" * 68)

check("vivienda_tipo" in resultado.celdas_omitidas, "vivienda_tipo está en las celdas omitidas (no escritas)")

# El "VT1 /3" original vive DENTRO del ACAD_TABLE (bloque anónimo *T424,
# ver informe de Fase 1) -- no es una entidad de modelspace consultable por
# `msp.query()`. Se comprueba en los dos sitios: (a) sigue existiendo,
# intacto, dentro de la tabla; (b) NO se ha añadido un MTEXT nuevo y real en
# modelspace que lo duplique.
tabla_copia = doc_copia.modelspace().query("ACAD_TABLE")[0]
vt_en_tabla = [m for m in tabla_copia.virtual_entities() if m.dxftype() == "MTEXT" and "VT1" in m.text]
check(len(vt_en_tabla) == 1, "sigue habiendo exactamente UN MTEXT con 'VT1' DENTRO del ACAD_TABLE (el original)",
      "%d encontrados: %r" % (len(vt_en_tabla), [m.text for m in vt_en_tabla]))
if vt_en_tabla:
    check(vt_en_tabla[0].text == "VT1 /3", "y es el texto original, sin tocar", vt_en_tabla[0].text)

vt_en_modelspace_real = [m for m in msp_copia.query("MTEXT[layer=='%s']" % CAPA_CUADRO) if "VT1" in m.text]
check(len(vt_en_modelspace_real) == 0,
      "y NO se ha creado ningún MTEXT nuevo (entidad real de modelspace) que lo duplique",
      "%d encontrados" % len(vt_en_modelspace_real))


print()
print("=" * 68)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
print()
print("Entregable de Fase 3 generado en: %s" % DESTINO)
