# -*- coding: utf-8 -*-
"""Qué modelo se usa para qué, en un solo sitio.

**El problema, medido.** `claude-sonnet-5` estaba escrito literalmente en seis
módulos: `analyzer/ai_analyst.py`, `analyzer/ai_generator.py`,
`analyzer/estilos.py`, `analyzer/interview/claude_interprete.py`,
`analyzer/pliego_extractor.py` y `extraccion/interprete.py`. Eso no es una
decisión de proveedor repetida seis veces: es una constante duplicada seis
veces, con dos consecuencias concretas.

1. Cambiar de modelo es un `grep`, y un `grep` se olvida uno.
2. **Usar un modelo distinto según la tarea es imposible sin tocar código.** Y
   esa es justo la palanca de coste que un agente 24/7 necesita: planificar
   ejige más capacidad que clasificar, y pagarlas igual es tirar dinero en una
   dirección o calidad en la otra.

**Lo que este módulo NO hace, y es deliberado:** no cambia ningún modelo. Los
seis perfiles apuntan hoy al mismo `claude-sonnet-5` que ya se usaba, así que
introducirlo no altera el comportamiento de nada. Lo único que cambia es que a
partir de ahora la decisión se toma en una línea y no en seis ficheros. Qué
modelo merece cada perfil es una decisión de coste que necesita datos reales de
`ia/uso.py`, y está anotada como D-5 en `docs/design/decisiones-pendientes.md`.

**Anulable por entorno** (`ARCHMUSE_MODELO_<PERFIL>`) para poder probar un
modelo nuevo en un perfil sin desplegar código, que es como se consiguen los
datos que faltan para decidir.
"""
from __future__ import annotations

import os
from typing import Dict

#: El modelo con el que la suite pasa hoy en verde. Cualquier cambio de este
#: valor se prueba antes con la suite entera, igual que una dependencia.
POR_DEFECTO = "claude-sonnet-5"

#: Perfil -> modelo. Un perfil es **una clase de tarea**, no un módulo: si
#: mañana hay tres sitios que interpretan documentos, comparten perfil y
#: comparten decisión.
PERFILES: Dict[str, str] = {
    # Elegir qué capacidades usar y en qué orden. Es donde un modelo mejor se
    # nota más, porque un plan malo cuesta varias ejecuciones.
    "planificacion": POR_DEFECTO,
    # Leer un documento del cliente y sacar datos estructurados de él.
    "interpretacion": POR_DEFECTO,
    # Redactar texto para un humano.
    "redaccion": POR_DEFECTO,
    # Etiquetar, clasificar, elegir entre pocas opciones. La tarea más barata.
    "clasificacion": POR_DEFECTO,
    # Generar geometría o propuestas de proyecto. La de salida más larga.
    "generacion": POR_DEFECTO,
}


def para(perfil: str) -> str:
    """El modelo de un perfil, con el entorno por encima de la tabla.

    Un perfil desconocido devuelve el modelo por defecto **y no levanta**: que
    alguien invente un perfil nuevo no puede dejar sin modelo a una llamada en
    producción. Lo que sí hace es quedar registrado en el nombre de la variable
    de entorno que nadie habrá definido.
    """
    del_entorno = os.environ.get("ARCHMUSE_MODELO_%s" % perfil.upper())
    if del_entorno:
        return del_entorno
    return PERFILES.get(perfil, POR_DEFECTO)


def perfiles() -> Dict[str, str]:
    """La tabla resuelta, con los valores del entorno ya aplicados."""
    return {p: para(p) for p in PERFILES}
