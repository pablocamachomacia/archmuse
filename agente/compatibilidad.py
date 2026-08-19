# -*- coding: utf-8 -*-
"""Qué cambio de una capacidad rompe a quien la invoca (tarea `CAD-2`).

**El problema, dicho en una frase:** el día que ArchMuse viva dentro de Revit,
un complemento instalado en el ordenador de un estudio invocará capacidades de
un servidor que se actualiza sin preguntarle. Si alguien renombra un parámetro
un martes, ese complemento deja de funcionar el martes — y el arquitecto no
sabrá por qué, ni tendrá nada que tocar.

`CAD-1` demostró que se puede invocar el motor desde fuera. `CAD-2` es lo que
hace que esa invocación siga valiendo mañana.

## La política, escrita

Cada capacidad declara `version` en semver. Lo que decide el tramo **no es el
tamaño del cambio, sino a quién rompe**:

| Tramo | Cuándo | Por qué |
|---|---|---|
| **MAYOR** | quitar un parámetro; añadir uno obligatorio; renombrar; estrechar un tipo; cambiar la `naturaleza`; **añadir un efecto** | Un invocador que hoy funciona deja de funcionar, o hace algo que nadie autorizó |
| **MENOR** | añadir un parámetro opcional; añadir una limitación declarada; ensanchar un tipo | Lo que ya se invocaba sigue invocándose igual |
| **PARCHE** | descripción, prosa, corrección interna sin cambio de contrato | Nadie de fuera lo nota |

**Añadir un efecto es MAYOR, y conviene entender por qué.** Los efectos son lo
que el portero de `agente/efectos.py` exige autorizar. Una capacidad que ayer
era pura y hoy escribe un fichero, con la misma versión, se ejecutaría bajo una
autorización concedida para otra cosa. No es un cambio de contrato: es un
cambio de lo que le pasa al ordenador del arquitecto.

**Añadir una limitación es MENOR y no MAYOR**, aunque suene a lo contrario:
declarar que algo *no* se comprueba no cambia lo que la capacidad hace, sólo lo
que dice de sí misma — y hacerlo más honesto nunca puede ser caro.

## Cómo se vigila

`huella()` reduce una capacidad a **su contrato** —lo que un invocador de fuera
puede notar— y deja fuera la prosa. `tests/test_agente_compatibilidad.py`
compara la huella de hoy con la congelada en
`tests/fixtures/contratos_de_capacidad.json`: si el contrato cambió y la
versión mayor no subió, la suite se pone roja **diciendo qué cambió y qué
tramo tocaba subir**. No hay forma de que ese cambio pase inadvertido, que es
justo lo que hoy no está garantizado en ningún sitio.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .capacidad import Capacidad

MAYOR, MENOR, PARCHE = "mayor", "menor", "parche"


class VersionInvalida(ValueError):
    """Una versión que no es semver, o una comparación imposible."""


def partes(version: str) -> Tuple[int, int, int]:
    trozos = version.split(".")
    if len(trozos) != 3:
        raise VersionInvalida("«%s» no es semver (mayor.menor.parche)" % version)
    try:
        return tuple(int(t) for t in trozos)      # type: ignore[return-value]
    except ValueError as exc:
        raise VersionInvalida("«%s» no es semver: %s" % (version, exc)) from exc


def huella(cap: Capacidad) -> Dict[str, Any]:
    """El **contrato** de una capacidad: lo que un invocador de fuera nota.

    Deja fuera la descripción a propósito. La prosa que lee el modelo se
    reescribe a menudo —y debe poder reescribirse— sin que eso obligue a nadie
    a subir una versión ni a actualizar un complemento instalado.
    """
    propiedades = cap.parametros.get("properties") or {}
    return {
        "id": cap.id,
        "version": cap.version,
        "naturaleza": cap.naturaleza,
        "efectos": sorted(cap.efectos),
        "obligatorios": sorted(cap.parametros.get("required") or []),
        "parametros": {
            nombre: {"type": (esquema or {}).get("type")}
            for nombre, esquema in sorted(propiedades.items())
        },
        # El número de limitaciones, no su texto: añadir una es un cambio
        # menor y redactarla mejor no es ningún cambio.
        "limitaciones": len(cap.limitaciones),
    }


def _tipos(valor: Any) -> set:
    if valor is None:
        return set()
    return set(valor) if isinstance(valor, list) else {valor}


def comparar(antes: Dict[str, Any], ahora: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
    """Devuelve `(tramo_exigido, motivos)`.

    `tramo_exigido` es `None` si el contrato no ha cambiado. Los motivos se
    devuelven **todos**, no el primero: quien está subiendo una versión quiere
    la lista completa para decidir de una vez.
    """
    mayores: List[str] = []
    menores: List[str] = []

    if antes.get("naturaleza") != ahora.get("naturaleza"):
        mayores.append(
            "cambia la naturaleza (%s -> %s): lo que era reproducible puede dejar de serlo"
            % (antes.get("naturaleza"), ahora.get("naturaleza")))

    efectos_antes, efectos_ahora = set(antes.get("efectos") or ()), set(ahora.get("efectos") or ())
    nuevos_efectos = sorted(efectos_ahora - efectos_antes)
    if nuevos_efectos:
        mayores.append(
            "efecto(s) nuevo(s) %s: se ejecutarían bajo una autorización concedida para otra cosa"
            % nuevos_efectos)
    if efectos_antes - efectos_ahora:
        menores.append("deja de tener efecto(s) %s" % sorted(efectos_antes - efectos_ahora))

    p_antes = antes.get("parametros") or {}
    p_ahora = ahora.get("parametros") or {}
    obl_antes = set(antes.get("obligatorios") or ())
    obl_ahora = set(ahora.get("obligatorios") or ())

    quitados = sorted(set(p_antes) - set(p_ahora))
    if quitados:
        mayores.append("desaparece(n) el/los parámetro(s) %s: quien los pasaba deja de poder" % quitados)

    anadidos = sorted(set(p_ahora) - set(p_antes))
    obligatorios_nuevos = sorted(n for n in anadidos if n in obl_ahora)
    if obligatorios_nuevos:
        mayores.append(
            "parámetro(s) obligatorio(s) nuevo(s) %s: toda invocación anterior queda inválida"
            % obligatorios_nuevos)
    opcionales_nuevos = sorted(n for n in anadidos if n not in obl_ahora)
    if opcionales_nuevos:
        menores.append("parámetro(s) opcional(es) nuevo(s) %s" % opcionales_nuevos)

    ascendidos = sorted((obl_ahora - obl_antes) & set(p_antes))
    if ascendidos:
        mayores.append("%s pasa(n) a ser obligatorio(s): una invocación que no los daba se rompe"
                       % ascendidos)
    degradados = sorted((obl_antes - obl_ahora) & set(p_ahora))
    if degradados:
        menores.append("%s deja(n) de ser obligatorio(s)" % degradados)

    for nombre in sorted(set(p_antes) & set(p_ahora)):
        t_antes = _tipos((p_antes[nombre] or {}).get("type"))
        t_ahora = _tipos((p_ahora[nombre] or {}).get("type"))
        if t_antes == t_ahora:
            continue
        if t_antes - t_ahora:
            mayores.append(
                "«%s» estrecha su tipo (%s -> %s): un valor que se aceptaba deja de aceptarse"
                % (nombre, sorted(t_antes), sorted(t_ahora)))
        else:
            menores.append("«%s» ensancha su tipo (%s -> %s)" % (nombre, sorted(t_antes), sorted(t_ahora)))

    if (ahora.get("limitaciones") or 0) != (antes.get("limitaciones") or 0):
        menores.append("cambia el número de limitaciones declaradas (%s -> %s)"
                       % (antes.get("limitaciones"), ahora.get("limitaciones")))

    if mayores:
        return MAYOR, mayores + menores
    if menores:
        return MENOR, menores
    return None, []


def tramo_subido(antes: str, ahora: str) -> Optional[str]:
    """Qué tramo de la versión se ha subido, o `None` si no se subió ninguno.

    Bajar una versión devuelve `None` a propósito: no es «no subir», es un
    error distinto, y lo denuncia quien compara.
    """
    (ma, mi, pa), (Ma, Mi, Pa) = partes(antes), partes(ahora)
    if Ma > ma:
        return MAYOR
    if Ma == ma and Mi > mi:
        return MENOR
    if Ma == ma and Mi == mi and Pa > pa:
        return PARCHE
    return None


#: Orden de suficiencia: subir la mayor cubre cualquier exigencia menor.
_RANGO = {PARCHE: 1, MENOR: 2, MAYOR: 3}


def basta(subido: Optional[str], exigido: Optional[str]) -> bool:
    """Si el tramo que se subió cubre el que exige el cambio de contrato."""
    if exigido is None:
        return True
    if subido is None:
        return False
    return _RANGO[subido] >= _RANGO[exigido]


def revisar(anteriores: Dict[str, Dict[str, Any]], capacidades) -> List[str]:
    """Compara el contrato congelado con el de hoy. Lista vacía = todo en orden.

    Una capacidad **nueva** no produce ningún fallo: no puede romper a nadie.
    Una capacidad que **desaparece** sí, y con motivo: alguien tiene un plan
    guardado que la nombra.
    """
    fallos: List[str] = []
    de_hoy = {c.id: huella(c) for c in capacidades}

    for identificador in sorted(set(anteriores) - set(de_hoy)):
        fallos.append(
            "%s ha desaparecido del registro. Un plan guardado que la nombre deja de "
            "poder reproducirse: retirar una capacidad es un cambio mayor del producto, "
            "no una limpieza." % identificador)

    for identificador in sorted(set(anteriores) & set(de_hoy)):
        antes, ahora = anteriores[identificador], de_hoy[identificador]
        exigido, motivos = comparar(antes, ahora)
        subido = tramo_subido(antes["version"], ahora["version"])
        if partes(ahora["version"]) < partes(antes["version"]):
            fallos.append("%s: la versión ha BAJADO (%s -> %s)"
                          % (identificador, antes["version"], ahora["version"]))
            continue
        if not basta(subido, exigido):
            fallos.append(
                "%s: el contrato cambia y exige subir la versión **%s**, pero la versión "
                "sigue en %s (subido: %s). Motivos:\n    - %s"
                % (identificador, exigido, ahora["version"], subido or "nada",
                   "\n    - ".join(motivos)))
    return fallos
