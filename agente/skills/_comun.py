# -*- coding: utf-8 -*-
"""Lo que toda Skill necesita y ninguna debería volver a escribir.

**Por qué existe, con el hallazgo delante.** Al ir a escribir la segunda Skill
de verdad se contó lo que ya había: el mismo invariante —*todo lo que la Skill
prometió producir y no ha producido sale `UNKNOWN` con motivo, nunca ausente*—
estaba escrito **en cuatro sitios y de tres formas distintas**:

- `superficies.py::_sin_hacer`, que además construye el `ResultadoDeSkill`;
- `evacuacion.py::_desconocidas`, que devuelve una lista y arma el resultado
  aparte;
- `territorial.py`, con **dos** bucles a pelo dentro de `_ejecutar`.

Cuatro copias del mismo invariante no son redundancia defensiva: son cuatro
sitios donde arreglar el bug de uno deja los otros tres rotos. Y el
invariante no es cosmético — es lo único que impide que un hueco mudo se lea
como «no aplica», que es la lectura contraria a la verdadera y el modo de fallo
más caro del producto.

**Qué NO va aquí, y es la mitad del criterio.** Aquí va lo que es cierto para
toda Skill. El procedimiento profesional —qué se mira, en qué orden, con qué
comprobaciones— es de cada Skill y no se comparte: el día que dos Skills
compartan procedimiento es que son la misma Skill. Este módulo tiene que poder
crecer sin que nadie tenga la tentación de meter aquí criterio de arquitecto.

**Y por qué está en `agente/skills/` y no en `agente/skill.py`.** Esto no es el
contrato de una Skill: es la caja de herramientas de quien escribe una. El
contrato lo hace cumplir `skill.py` con sus cinco garantías, y una Skill que
prefiera no usar nada de aquí sigue siendo válida.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from ..afirmacion import Afirmacion, desconocido


def valor(resultado, nombre: str, por_defecto: Any = None) -> Any:
    """El valor de una afirmación del resultado, por nombre.

    Lo usan las verificaciones, que reciben el `ResultadoDeSkill` entero y
    necesitan una cifra concreta. Recorrer la tupla a mano en cada verificación
    es lo que hace que una verificación nueva se escriba mal la primera vez.
    """
    for afirmacion in resultado.afirmaciones:
        if afirmacion.nombre == nombre:
            return afirmacion.valor
    return por_defecto


def sin_producir(claves: Iterable[str], *, codigo: str, detalle: str, fuente: str,
                 ya_hecho: Optional[Mapping[str, Afirmacion]] = None
                 ) -> Tuple[Afirmacion, ...]:
    """Las afirmaciones de una Skill que se cortó a mitad: lo hecho, y el resto
    `UNKNOWN` **con motivo**.

    El orden de la salida es el de `claves`, con lo ya hecho en su sitio, para
    que dos ejecuciones de la misma Skill produzcan actas comparables línea a
    línea. Una clave de `ya_hecho` que no esté en `claves` se conserva al final:
    perder silenciosamente una afirmación ya calculada sería el mismo hueco mudo
    por la otra puerta.
    """
    hechas: Dict[str, Afirmacion] = dict(ya_hecho or {})
    salida = []
    for clave in claves:
        salida.append(
            hechas.pop(clave, None)
            or desconocido(clave, codigo, detalle, fuente=fuente)
        )
    salida.extend(hechas.values())
    return tuple(salida)


def pregunta_legible(pregunta: Mapping[str, Any]) -> str:
    """Una pregunta pendiente convertida en algo que se puede contestar.

    **El defecto que esto corrige, encontrado sobre el plano real `v2s.dxf`.**
    La capacidad devuelve preguntas completas —qué hueco resuelven, qué opciones
    hay, con qué superficie cada una, y con qué forma se contesta— y la Skill se
    quedaba con el `titulo`. El arquitecto leía «¿A qué recinto corresponde cada
    terraza?» y no tenía ni las opciones ni la forma de la respuesta: para
    contestar había que saltarse la Skill e ir a la capacidad, es decir, leer el
    código. Una pregunta que no se puede contestar no es preguntar; es el mismo
    hueco mudo que el producto entero existe para evitar, sólo que con signos de
    interrogación.

    El plano real lo enseñó bien: sus dos «Tendedero» y su «Terraza» solapada
    producen justo este tipo de solicitud, y el reparto NO se hace por orden de
    aparición — se pregunta. Por eso la respuesta se rinde con sus `id`s: son lo
    que hay que devolver en `respuestas`, y escribirlos de memoria es
    exactamente el error que produce una asignación cambiada sin querer.
    """
    partes = [(pregunta.get("titulo") or "pregunta sin título").strip()]
    ayuda = (pregunta.get("ayuda") or "").strip()
    if ayuda:
        partes.append(ayuda)

    campos = [c for c in (pregunta.get("campos") or ()) if c]
    if campos:
        partes.append("Resuelve: %s." % ", ".join(campos))

    tipo = pregunta.get("tipo")
    identificador = pregunta.get("id") or ""
    if tipo == "asignacion":
        opciones = []
        for candidato in pregunta.get("candidatos") or ():
            etiqueta = (candidato.get("etiqueta") or "sin rótulo").strip()
            opciones.append("%s = «%s» (%s m²)"
                            % (candidato.get("id"), etiqueta, candidato.get("area_m2")))
        partes.append("Opciones: %s."
                      % ("; ".join(opciones) if opciones
                         else "ninguna; el plano no ofrece piezas candidatas"))
        partes.append(
            'Para contestar: {"tipo": "asignacion", "solicitud_id": "%s", '
            '"asignaciones": {"<campo>": "<id de la opción>"}}.' % identificador)
    elif tipo == "numerico":
        unidad = pregunta.get("unidad") or "m2"
        partes.append(
            'Para contestar: {"tipo": "numerico", "campo": "%s", "valor": <%s>}.'
            % (campos[0] if campos else "<campo>", unidad))
    return " ".join(partes)
