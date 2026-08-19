# -*- coding: utf-8 -*-
"""Lo que ve el planificador, y sólo eso (tarea `ME-5`).

**El planificador nunca ve el grafo completo.** Ve tres cosas: qué sabe hacer
ArchMuse, qué rutas del proyecto están resueltas y cuáles no, y qué está en
conflicto. Ni un valor de más.

Tres motivos, y ninguno es estético:

1. **Coste.** Un proyecto grande tiene miles de atributos. Volcarlos en cada
   llamada multiplica la factura sin cambiar ni una decisión del planificador,
   que lo único que necesita saber es si un requisito está cubierto.
2. **Privacidad.** Lo que viaja al modelo son datos del proyecto de un cliente.
   Enviar lo que no hace falta para decidir es exponerlo sin motivo — el mismo
   criterio que hace que `ia/uso.py` registre métricas y jamás prompts.
3. **Caché.** Los manifiestos van en el **prefijo** del mensaje y el estado del
   proyecto detrás. Si el prefijo cambia de orden entre procesos, la caché de
   prompt no acierta nunca y el planificador se encarece **en silencio**, que
   es la peor forma de encarecerse. Por eso `prefijo_cacheable` ordena, y por
   eso hay un test que lo comprueba entre invocaciones.

**Cómo se acota el tamaño.** No se trunca por longitud —truncar deja fuera
justo lo que decide, sin decirlo—: se acota por **estructura**.

- Las claves que alguna Skill declara como requisito van **enteras**, con su
  estado. Son las que deciden si un plan es ejecutable, y su número lo fija el
  catálogo de Skills (`C4`: entre 8 y 12), no el tamaño del proyecto.
- Todo lo demás se agrega por espacio de nombres: `programa: 12 conocidas, 3
  sin resolver`. El planificador no necesita los nombres de las 12; necesita
  saber que están.
- Los conflictos se listan acotados y **se dice cuántos quedan fuera**. Un
  conflicto oculto es peor que un conflicto resumido.

De ahí sale la propiedad que pide `ME-5`: el resumen de un proyecto de 10.000
atributos ocupa aproximadamente lo mismo que el de uno de 20.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

from analyzer.hechos import KNOWN, UNKNOWN
from .memoria import MemoriaDeProyecto

#: Cuántos conflictos se nombran antes de pasar a contarlos. Cinco caben en una
#: decisión; cincuenta son un volcado.
MAX_CONFLICTOS = 5

#: Cuántos espacios de nombres se detallan. Un proyecto con más de veinte
#: familias de atributos tiene un problema de modelado, no de resumen.
MAX_ESPACIOS = 20


def _espacio_de(clave: str) -> str:
    """`programa.dormitorios` -> `programa`. Una clave sin punto es su propio
    espacio: no se inventa una jerarquía que nadie declaró."""
    return clave.split(".", 1)[0] if "." in clave else clave


def claves_que_deciden(skills: Iterable[Any]) -> Tuple[str, ...]:
    """Las claves que alguna Skill exige, en orden estable.

    Son las únicas que el planificador necesita ver una por una: de ellas
    depende que un plan sea ejecutable o que la respuesta correcta sea una
    pregunta.
    """
    claves = set()
    for skill in skills or ():
        for requisito in getattr(skill, "requiere", ()) or ():
            claves.add(requisito.clave)
    return tuple(sorted(claves))


def resumen_del_proyecto(memoria: Optional[MemoriaDeProyecto],
                         skills: Iterable[Any] = (),
                         *, max_conflictos: int = MAX_CONFLICTOS,
                         max_espacios: int = MAX_ESPACIOS) -> Dict[str, Any]:
    """El estado del proyecto en tamaño acotado, con la forma que decide.

    Sin memoria devuelve un resumen vacío explícito y no `None`: quien lo lee
    tiene que poder distinguir "proyecto sin datos" de "no me han pasado el
    proyecto", y las dos cosas llevan a planes distintos.
    """
    if memoria is None:
        return {"proyecto_id": None, "sin_memoria": True,
                "requisitos": {}, "espacios": {}, "conflictos": [], "conflictos_omitidos": 0}

    vigentes = {e.clave: e for e in memoria.todo()}
    decisivas = claves_que_deciden(skills)

    requisitos: Dict[str, str] = {}
    for clave in decisivas:
        entrada = vigentes.get(clave)
        requisitos[clave] = entrada.afirmacion.estado if entrada else UNKNOWN

    espacios: Dict[str, Dict[str, int]] = {}
    for clave, entrada in vigentes.items():
        if clave in requisitos:
            continue                      # ya va detallada; no se cuenta dos veces
        fila = espacios.setdefault(_espacio_de(clave), {})
        estado = entrada.afirmacion.estado
        fila[estado] = fila.get(estado, 0) + 1

    ordenados = sorted(espacios.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))
    detallados = dict(ordenados[:max_espacios])
    omitidos = ordenados[max_espacios:]
    if omitidos:
        detallados["(otros %d espacios)" % len(omitidos)] = {
            "total": sum(sum(f.values()) for _, f in omitidos)
        }

    conflictos = [c.clave for c in memoria.conflictos()]
    return {
        "proyecto_id": memoria.proyecto_id,
        "requisitos": requisitos,
        "espacios": detallados,
        "conflictos": conflictos[:max_conflictos],
        "conflictos_omitidos": max(0, len(conflictos) - max_conflictos),
    }


def prefijo_cacheable(capacidades: Iterable[Any], skills: Iterable[Any] = ()) -> str:
    """Los manifiestos, en orden determinista, listos para el prefijo del prompt.

    Que esto sea **texto** y no una estructura es deliberado: lo que la caché de
    prompt compara son tokens, y un `dict` serializado con orden de inserción
    variable produce dos prefijos distintos para el mismo catálogo.
    """
    bloques: List[str] = []
    for cap in sorted(capacidades or (), key=lambda c: c.id):
        bloques.append(json.dumps(cap.esquema(), ensure_ascii=False, sort_keys=True))
    for skill in sorted(skills or (), key=lambda s: (s.id, s.version)):
        bloques.append(json.dumps(skill.manifiesto(), ensure_ascii=False, sort_keys=True,
                                  default=str))
    return "\n".join(bloques)


def a_texto(resumen: Dict[str, Any]) -> str:
    """El resumen en la forma en que va al modelo: corta, tabular y sin valores.

    Se dice **explícitamente** lo que no se envía. Un modelo que no sabe que
    hay más datos de los que ve se comporta como si no existieran, y eso
    produce planes que dan por resuelto lo que nadie ha resuelto.
    """
    if resumen.get("sin_memoria"):
        return ("ESTADO DEL PROYECTO: no hay memoria de proyecto en esta ejecución. "
                "No se puede dar por sabido ningún dato.")
    lineas = ["ESTADO DEL PROYECTO «%s»" % resumen["proyecto_id"], ""]
    lineas.append("Datos que las Skills exigen (KNOWN = se puede usar):")
    if resumen["requisitos"]:
        for clave, estado in sorted(resumen["requisitos"].items()):
            lineas.append("  %-40s %s" % (clave, estado))
    else:
        lineas.append("  (ninguna Skill declara requisitos)")
    if resumen["espacios"]:
        lineas.append("")
        lineas.append("Otros datos del proyecto, contados por familia (no se envían "
                      "sus valores; pídelos con una capacidad si hacen falta):")
        for espacio, cuenta in resumen["espacios"].items():
            detalle = ", ".join("%s: %d" % (k, v) for k, v in sorted(cuenta.items()))
            lineas.append("  %-40s %s" % (espacio, detalle))
    if resumen["conflictos"]:
        lineas.append("")
        lineas.append("SIN RESOLVER: el cliente ha dicho dos cosas distintas sobre:")
        for clave in resumen["conflictos"]:
            lineas.append("  · %s" % clave)
        if resumen["conflictos_omitidos"]:
            lineas.append("  · … y %d más" % resumen["conflictos_omitidos"])
        lineas.append("No elijas tú: manda el más reciente para poder seguir, pero el "
                      "conflicto tiene que aparecer en la respuesta.")
    return "\n".join(lineas)


def contexto_del_planificador(memoria: Optional[MemoriaDeProyecto],
                              capacidades: Iterable[Any],
                              skills: Iterable[Any] = ()) -> Dict[str, Any]:
    """Las dos mitades separadas: el prefijo estable y el estado variable.

    Separarlas **es** la optimización: el prefijo se cachea entre ejecuciones
    del mismo despliegue; el estado cambia y va detrás.
    """
    resumen = resumen_del_proyecto(memoria, skills)
    return {
        "prefijo": prefijo_cacheable(capacidades, skills),
        "estado": resumen,
        "estado_texto": a_texto(resumen),
    }


__all__ = [
    "KNOWN", "UNKNOWN", "MAX_CONFLICTOS", "MAX_ESPACIOS",
    "a_texto", "claves_que_deciden", "contexto_del_planificador",
    "prefijo_cacheable", "resumen_del_proyecto",
]
