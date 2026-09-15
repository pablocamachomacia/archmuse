# -*- coding: utf-8 -*-
"""Lo que dibuja ArchMuse no es un dato del plano.

**Por qué existe (2026-09-15).** En una segunda ejecución sobre el plano de
referencia del estudio el comando dijo «He encontrado 2 cuadro(s)»: la tabla que
él mismo había dibujado lleva el mismo título que el cuadro del arquitecto. Y
medido ese día: releída por la vía web, la casilla «VT1/3» del cuadro exportado
era una segunda vivienda con el mismo nombre, y la segunda pasada dejaba de
escribir cifras (`C-13`). Ver `tests/test_archmuse_no_se_lee_a_si_mismo.py`.

**Cómo se reconoce: por la capa.** Todo lo que dibuja ArchMuse va en una de
estas capas desde la 3.3.0: el cuadro del comando (un `ACAD_TABLE`), el de la
web (`LINE` y `MTEXT`), sus notas al pie y la marca de borrador.
`00 ARCHMUSE BORRADOR` es la capa de la marca web hasta el 2026-09-11
(`tests/test_marca_borrador.py`): un plano marcado entonces todavía la lleva.

**Constantes escritas aquí y no importadas:** `marca_borrador` carga reportlab y
`parser` no debe arrastrarlo. Un test las compara con las de
`maquetacion_cuadro` y `marca_borrador`.
"""
from __future__ import annotations

CAPAS_DE_ARCHMUSE = ("ARCHMUSE - CUADRO", "ARCHMUSE - BORRADOR", "00 ARCHMUSE BORRADOR")
_EN_MAYUSCULAS = frozenset(c.upper() for c in CAPAS_DE_ARCHMUSE)


def es_capa_de_archmuse(capa) -> bool:
    """AutoCAD no distingue mayúsculas en los nombres de capa; aquí tampoco."""
    return isinstance(capa, str) and capa.strip().upper() in _EN_MAYUSCULAS


def capa_de(entidad):
    """La capa de una entidad, **también la de un `ACAD_TABLE`**.

    ezdxf guarda los `ACAD_TABLE` como `DXFTagStorage` y **no carga su capa**:
    `dxf.layer` da «0» aunque el fichero diga otra cosa. Medido el 2026-09-15 en
    el fixture sintético y en un plano real guardado por AutoCAD. Las etiquetas
    crudas sí están (`xtags`), y la capa es su grupo 8. Para el resto de
    entidades, `dxf.layer`. `None` si no hay forma de saberla.
    """
    xtags = getattr(entidad, "xtags", None)
    if xtags is not None:
        try:
            for subclase in xtags.subclasses:
                for etiqueta in subclase:
                    if etiqueta.code == 8:
                        return str(etiqueta.value)
        except Exception:  # noqa: BLE001 - etiquetas de un DXF ajeno
            pass
    try:
        return entidad.dxf.layer
    except Exception:  # noqa: BLE001
        return None


def es_de_archmuse(entidad) -> bool:
    """Si la entidad está en una capa de ArchMuse. Una entidad sin capa legible no
    es de ArchMuse: ante la duda se lee, como hasta ahora."""
    return es_capa_de_archmuse(capa_de(entidad))
