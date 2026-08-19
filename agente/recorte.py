# -*- coding: utf-8 -*-
"""Qué se le manda al modelo cuando un resultado no cabe.

**El problema, medido.** El bucle de `nucleo.py` añade cada resultado de
herramienta al historial **entero y literal**, y no quita nada nunca. Con las
capacidades de hoy eso no molesta; con un DXF de cuarenta recintos leído de
punta a punta, un solo resultado se come el contexto de toda la conversación y
las herramientas siguientes empiezan a fallar por una razón que no tiene nada
que ver con lo que se pidió. Es el fallo más caro de un agente: no se ve venir,
no da un error legible y aparece justo cuando el plano es grande — o sea, con
el cliente de verdad.

**La regla que gobierna este módulo.** Recortar lo que ve el modelo **no puede
crear un hueco que el modelo rellene**. Por eso:

1. **Se recorta con la estructura, no con la cadena.** Cortar el JSON por el
   carácter 20.000 produce un JSON roto, y un modelo que recibe un JSON roto
   improvisa. Aquí las claves se conservan todas, las listas se acortan y las
   cadenas largas se cortan; lo que sale sigue siendo JSON válido y sigue
   diciendo de qué habla.
2. **El recorte se declara donde se hizo.** Cada corte deja una marca legible
   —`«… (recortado: 812 elementos más)»`— y la lista de cortes viaja hasta la
   `Respuesta`. Un recorte silencioso es indistinguible de un dato que no
   existía.
3. **`ok` no se toca, y ninguna clave desaparece.** El modelo tiene que poder
   seguir distinguiendo un resultado bueno de uno fallido, y un dato ausente de
   uno recortado.

**Lo que este módulo NO hace, a propósito.** No resume: resumir es inventar en
pequeño, y un resumen de un resultado de herramienta es exactamente por dónde
entra una cifra que nadie midió. No decide qué es importante. No llama a un
modelo. Corta por tamaño, dice dónde cortó, y se acabó.

**El resultado completo no se pierde nunca.** Lo recortado es la copia que
viaja al modelo; `PasoEjecutado.resultado` guarda el original íntegro, y es
contra el original —no contra el recorte— contra lo que `respaldo.py` comprueba
las cifras del texto final. Un modelo que ve menos puede citar menos, nunca más.
"""
from __future__ import annotations

import json
from typing import Any, List, Tuple

#: Tope por resultado de herramienta, en caracteres del JSON que se manda.
#: Veinte mil son del orden de cinco mil tokens: de sobra para cualquier
#: resultado que hoy produce el registro, y aun así un techo. Que no salte
#: nunca en uso normal es el diseño, no una casualidad.
MAX_CARACTERES = 20_000

#: Tope del historial entero antes de la siguiente llamada. Superarlo no se
#: arregla recortando más: significa que la conversación ya no cabe, y seguir
#: sólo gasta dinero para recibir un error del proveedor.
MAX_CONTEXTO = 300_000

#: Cuántos elementos de una lista se conservan, y cuántos caracteres de una
#: cadena, en la primera pasada. Si con eso no cabe, se aprietan por mitades.
MAX_ELEMENTOS = 40
MAX_TEXTO = 2_000

#: Suelo: por debajo de esto no se sigue apretando. Un resultado reducido a
#: tres elementos ya no informa de nada, y es mejor decirlo que fingirlo.
MIN_ELEMENTOS = 3
MIN_TEXTO = 200

MARCA_LISTA = "… (recortado: %d elemento(s) más, omitidos por tamaño)"
MARCA_TEXTO = "… (recortado: %d carácter(es) más)"

#: La clave que se añade al resultado recortado. Empieza y acaba por guiones
#: bajos dobles para que no colisione con ninguna clave de una capacidad: las
#: claves de un manifiesto son identificadores en castellano.
CLAVE_RECORTE = "__recorte__"

AVISO = (
    "Este resultado NO viene entero: se ha recortado por tamaño. Lo omitido "
    "existe pero no lo estás viendo. No supongas su contenido, no cuentes lo "
    "que no ves y no escribas ninguna cifra que no aparezca aquí."
)


def tamano(valor: Any) -> int:
    """Los caracteres que ocupa el valor tal como viajará al modelo."""
    return len(_serializar(valor))


def _serializar(valor: Any) -> str:
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, default=str)


def recortar(valor: Any, *, limite: int = MAX_CARACTERES) -> Tuple[Any, Tuple[str, ...]]:
    """El valor tal como se le manda al modelo, y la lista de lo que se cortó.

    Si cabe, vuelve **idéntico** y sin ninguna nota: el camino normal no toca
    nada. Si no cabe, se poda por estructura y se aprieta por mitades hasta que
    quepa o hasta llegar al suelo. Que el resultado siga sin caber en el suelo
    es posible, y entonces se devuelve igualmente lo podado con su nota: mandar
    un resultado enorme y que el proveedor lo rechace es peor que mandarlo
    recortado y decirlo.
    """
    if tamano(valor) <= limite:
        return valor, ()

    max_elementos, max_texto = MAX_ELEMENTOS, MAX_TEXTO
    while True:
        notas: List[str] = []
        podado = _podar(valor, notas, max_elementos, max_texto)
        marcado = _marcar(podado, notas)
        if tamano(marcado) <= limite:
            return marcado, tuple(notas)
        if max_elementos <= MIN_ELEMENTOS and max_texto <= MIN_TEXTO:
            notas.append(
                "el resultado no cabe en %d caracteres ni recortado al mínimo; "
                "va incompleto" % limite
            )
            return _marcar(podado, notas), tuple(notas)
        max_elementos = max(MIN_ELEMENTOS, max_elementos // 2)
        max_texto = max(MIN_TEXTO, max_texto // 2)


def _podar(valor: Any, notas: List[str], max_elementos: int, max_texto: int,
           camino: str = "") -> Any:
    """Poda por estructura. **Nunca quita una clave**, sólo acorta su valor."""
    if isinstance(valor, str):
        if len(valor) <= max_texto:
            return valor
        notas.append("%s: texto de %d caracteres recortado a %d"
                     % (camino or "(raíz)", len(valor), max_texto))
        return valor[:max_texto] + (MARCA_TEXTO % (len(valor) - max_texto))

    if isinstance(valor, list):
        conservados = valor[:max_elementos]
        podada: List[Any] = [
            _podar(v, notas, max_elementos, max_texto, "%s[%d]" % (camino, i))
            for i, v in enumerate(conservados)
        ]
        if len(valor) > max_elementos:
            notas.append("%s: lista de %d elementos recortada a %d"
                         % (camino or "(raíz)", len(valor), max_elementos))
            podada.append(MARCA_LISTA % (len(valor) - max_elementos))
        return podada

    if isinstance(valor, dict):
        return {
            clave: _podar(v, notas, max_elementos, max_texto,
                          "%s.%s" % (camino, clave) if camino else str(clave))
            for clave, v in valor.items()
        }

    return valor


def _marcar(podado: Any, notas: List[str]) -> Any:
    """Añade el aviso al propio resultado, que es donde el modelo lo lee.

    Ponerlo sólo en la traza no serviría: quien tiene que no rellenar el hueco
    es el modelo, y el modelo lee el resultado.
    """
    if not notas:
        return podado
    if isinstance(podado, dict):
        marcado = dict(podado)
        marcado[CLAVE_RECORTE] = {"aviso": AVISO, "cortes": list(notas)}
        return marcado
    return {CLAVE_RECORTE: {"aviso": AVISO, "cortes": list(notas)},
            "valor": podado}


def cabe_el_historial(mensajes: Any, *, limite: int = MAX_CONTEXTO) -> bool:
    """Si la conversación entera todavía cabe antes de la siguiente llamada.

    Se comprueba **antes** de llamar y no después de que el proveedor conteste
    con un error: pagar una llamada para enterarse de que no cabía es la peor
    forma de enterarse.
    """
    return tamano(mensajes) <= limite
