# -*- coding: utf-8 -*-
"""Invocar una capacidad sin web, sin Flask y sin FastAPI (tarea `CAD-1`).

    python -m agente.invocar                                   # qué sabe hacer
    python -m agente.invocar territorial.resolver_ambito --municipio Madrid
    python -m agente.invocar --openapi                         # el contrato HTTP
    python -m agente.invocar --comprobar                       # los tres consumidores casan

Una capacidad con efectos declarados **no se ejecuta sin `--autorizar`**: se
enseña qué iba a pasar y se sale con código 3 sin tocar nada. En una pantalla
eso será un diálogo; en una línea de órdenes, la casilla que se marca es un
argumento.

**Esto no es un plugin de Revit. Es la prueba de que el plugin será posible.**

`CAD-3` —el complemento real— está aplazado con motivo: construir el envoltorio
antes de tener capacidades que merezcan invocarse es hacer el lazo de un regalo
vacío. Pero el aplazamiento sólo es reversible si la arquitectura no se cierra
mientras tanto, y eso es lo que aquí se comprueba en media jornada en vez de
descubrirlo dentro de un año: el motor responde por una tercera puerta —ni la
API de herramientas, ni HTTP— usando **el mismo manifiesto** y **el mismo
portero de argumentos**.

Los argumentos de la línea de órdenes no se declaran a mano: se derivan del
esquema de la capacidad con `manifiesto.firma`. Añadir una capacidad no obliga
a tocar este fichero, que es justo la propiedad que `TL-3` compra. Si algún día
hace falta escribirlos aquí, la propiedad se ha perdido.

Sale con código 0 si la capacidad devolvió `ok: true`, y con 1 si devolvió
`ok: false`. Que `ok: false` no sea un error de ejecución es deliberado: es una
respuesta legítima —"falta este dato", "hay dos municipios con ese nombre"— y
un guion que la trate como una excepción perdería la pregunta que la acompaña.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

from .capacidad import Capacidad, ErrorDeCapacidad
from .efectos import (DESCRIPCIONES, EfectoNoAutorizado, Autorizacion,
                      Autorizaciones)
from .manifiesto import (comprobar_registro, documento_openapi, firma,
                         invocar as invocar_capacidad)
from .registro import CapacidadDesconocida, registro


def _convertir(bruto: str, anotacion: Any) -> Any:
    """El texto de la consola al tipo que declara el manifiesto.

    Un valor que no encaja se deja **tal cual, como texto**, y la capacidad
    decide: forzarlo aquí a un número inventado sería el repliegue silencioso
    que este producto persigue en todas partes.
    """
    base = anotacion
    if getattr(anotacion, "__origin__", None) is not None:  # Optional[X]
        candidatos = [a for a in getattr(anotacion, "__args__", ()) if a is not type(None)]
        base = candidatos[0] if len(candidatos) == 1 else str
    try:
        if base is bool:
            return bruto.strip().lower() in ("1", "true", "si", "sí", "yes")
        if base in (int, float):
            return base(bruto)
        if base in (dict, list):
            return json.loads(bruto)
    except (TypeError, ValueError):
        return bruto
    return bruto


def _parser_de(cap: Capacidad) -> argparse.ArgumentParser:
    """El parser de una capacidad, generado de su firma. Nunca escrito a mano."""
    propiedades = cap.parametros.get("properties") or {}
    parser = argparse.ArgumentParser(
        prog="python -m agente.invocar " + cap.id,
        description=cap.descripcion.strip(),
        epilog=("NO comprueba: " + "; ".join(cap.limitaciones) if cap.limitaciones else None),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    for nombre, p in firma(cap).parameters.items():
        obligatorio = p.default is inspect.Parameter.empty
        parser.add_argument(
            "--" + nombre.replace("_", "-"),
            dest=nombre,
            required=obligatorio,
            default=None,
            help=(propiedades.get(nombre) or {}).get("description") or (
                "obligatorio" if obligatorio else "opcional"),
        )
    return parser


def listar(capacidades) -> str:
    """Qué sabe hacer ArchMuse, leído del registro y no de una lista escrita."""
    lineas = ["Capacidades disponibles (%d):" % len(capacidades), ""]
    for cap in capacidades:
        lineas.append("  %s@%s  [%s]" % (cap.id, cap.version, cap.naturaleza))
        lineas.append("      %s" % cap.descripcion.strip().split("\n")[0])
        lineas.append("      %s" % str(firma(cap)))
        if cap.efectos:
            lineas.append("      efectos (exigen --autorizar): %s"
                          % "; ".join(DESCRIPCIONES.get(e, e) for e in cap.efectos))
        if cap.limitaciones:
            lineas.append("      NO comprueba: %s" % "; ".join(cap.limitaciones))
        lineas.append("")
    lineas.append("Uso:  python -m agente.invocar <id> --parametro valor")
    return "\n".join(lineas)


def _salida_en_utf8() -> None:
    """La consola de Windows habla cp1252 y los municipios espanoles no caben.

    Un CLI que imprime «Espa?a» no vale como prueba de que el motor se puede
    invocar desde fuera: lo que salga de aqui lo va a leer un plugin.
    """
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):     # pragma: no cover - flujo capturado
            pass


def ejecutar(argv: Optional[Sequence[str]] = None) -> int:
    _salida_en_utf8()
    argv = list(sys.argv[1:] if argv is None else argv)
    reg = registro()

    if "--openapi" in argv:
        print(json.dumps(documento_openapi(reg), ensure_ascii=False, indent=2))
        return 0

    if "--comprobar" in argv:
        fallos: List[str] = comprobar_registro(reg)
        if fallos:
            print("MANIFIESTOS INCOHERENTES:", file=sys.stderr)
            for f in fallos:
                print("  · " + f, file=sys.stderr)
            return 2
        print("Los tres consumidores coinciden en las %d capacidades del registro." % len(reg))
        return 0

    if not argv or argv[0] in ("-h", "--help", "--listar"):
        print(listar(reg))
        return 0

    try:
        cap = reg.buscar(argv[0])
    except CapacidadDesconocida as exc:
        print(str(exc), file=sys.stderr)
        return 2

    autorizado = "--autorizar" in argv
    argv = [a for a in argv if a != "--autorizar"]
    if cap.efectos and not autorizado:
        # Se enseña lo que iba a pasar ANTES de que pase, y no se ejecuta. Es
        # la aprobación explícita del PRD de `TL-2` traducida a una superficie
        # sin diálogos: en un CLI, la casilla que se marca es un argumento.
        print("«%s» tiene efectos y nadie los ha autorizado:" % cap.id, file=sys.stderr)
        for efecto in cap.efectos:
            print("  · %s" % DESCRIPCIONES.get(efecto, efecto), file=sys.stderr)
        print("No se ha ejecutado nada y no se ha creado ningún fichero.", file=sys.stderr)
        print("Si es lo que quieres, repite el comando con --autorizar.", file=sys.stderr)
        return 3

    args = _parser_de(cap).parse_args(argv[1:])
    firma_cap = firma(cap)
    argumentos: Dict[str, Any] = {}
    for nombre, valor in vars(args).items():
        if valor is None:
            continue        # no pasado: que mande el defecto de la función
        argumentos[nombre] = _convertir(valor, firma_cap.parameters[nombre].annotation)

    permisos = None
    if cap.efectos:
        quien = "cli:%s" % (os.environ.get("USERNAME") or os.environ.get("USER") or "?")
        permisos = Autorizaciones(tuple(
            Autorizacion(efecto=e, alcance="ejecucion", autorizada_por=quien)
            for e in cap.efectos
        ))

    try:
        resultado = invocar_capacidad(cap, autorizaciones=permisos, **argumentos)
    except EfectoNoAutorizado as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except ErrorDeCapacidad as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
    return 0 if resultado.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(ejecutar())
