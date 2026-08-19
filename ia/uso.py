# -*- coding: utf-8 -*-
"""Cuánto cuesta cada llamada a un modelo, medido y con un techo.

**Qué problema resuelve** (tarea V0-3 del plan de migración v2). Hasta hoy
`response.usage` no se leía en **ningún** punto del repositorio: ni
`input_tokens`, ni `output_tokens`, ni coste. La consecuencia práctica es que
la pregunta "cuánto cuesta un usuario" no tenía respuesta con datos — las
cifras de la auditoría (~$0,90-1,20 por proyecto completo) son estimaciones
desde los techos de `max_tokens`, y así lo dicen. Este módulo las sustituye por
medidas.

**Tres decisiones que conviene no deshacer:**

1. **Sólo métricas, nunca texto.** No se registra ni un carácter del prompt ni
   de la respuesta. Lo que viaja en esos prompts son datos del proyecto de un
   cliente, y un fichero de registro no es sitio para ellos. Quien necesite
   depurar un prompt lo hace en su sesión, no en el histórico.

2. **El techo de gasto corta, no avisa.** `ARCHMUSE_TOPE_GASTO_USD` acota lo
   que un proceso puede gastar. Se comprueba **antes** de cada llamada: pasarse
   por una llamada que ya se ha pagado no sirve de nada. Es la defensa contra
   el modo de fallo clásico de un orquestador —replanificar en bucle— antes de
   que exista el orquestador que podría sufrirlo.

3. **JSONL, no una tabla.** Es deliberadamente provisional: en V1-1 esto pasa a
   la tabla `run_steps`, donde el registro de ejecución *es* el acta de
   procedencia. Montar ahora una tabla sería construir dos veces.

**De dónde salen los precios.** De la tarifa pública de la API de Anthropic,
consultada el 2026-08-18. Están aquí como dato editable y con fecha, no
escondidos en una fórmula: cuando cambien, se cambian aquí y se anota. Un
modelo que no esté en la tabla se registra igual, con `coste_usd: null` — nunca
se inventa una cifra, que es la misma regla que gobierna el resto del producto.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, Optional

#: $ por millón de tokens, (entrada, salida). Tarifa pública, 2026-08-18.
#: `claude-sonnet-5` tiene precio promocional hasta el 2026-08-31 ($2/$10);
#: aquí va el de tarifa, para no subestimar el coste al planificar.
PRECIOS_USD_POR_MTOK: Dict[str, tuple] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

#: Multiplicadores de caché sobre el precio de entrada.
FACTOR_ESCRITURA_CACHE = 1.25
FACTOR_LECTURA_CACHE = 0.10

#: Techo por proceso, en dólares. Generoso a propósito: es una red contra un
#: bucle, no un presupuesto de producto. El presupuesto por ejecución llega con
#: el validador de planes (V1-11).
TOPE_POR_DEFECTO_USD = 5.00

_VAR_TOPE = "ARCHMUSE_TOPE_GASTO_USD"
_VAR_FICHERO = "ARCHMUSE_REGISTRO_USO"

_candado = threading.Lock()
_gastado_usd = 0.0
_llamadas = 0
#: Gasto acumulado por punto de llamada y por modelo. Es lo que convierte
#: "este análisis ha costado 0,42 USD" en "0,31 de ellos los gastó
#: `analyzer/ai_generator.py`", que es la única forma de saber qué recortar.
_por_llamante: Dict[str, Dict[str, float]] = {}
_por_modelo: Dict[str, Dict[str, float]] = {}

_VAR_CAMBIO = "ARCHMUSE_EUR_POR_USD"


class TopeDeGastoSuperado(RuntimeError):
    """El proceso ha alcanzado `ARCHMUSE_TOPE_GASTO_USD`."""


def tope_usd() -> float:
    """Techo vigente. Un valor no numérico o <= 0 se ignora y vale el de aquí:
    una variable mal escrita no puede dejar el proceso sin límite — mismo
    criterio que los timeouts de `ia/cliente.py`."""
    bruto = os.environ.get(_VAR_TOPE)
    if not bruto:
        return TOPE_POR_DEFECTO_USD
    try:
        valor = float(bruto)
    except ValueError:
        return TOPE_POR_DEFECTO_USD
    return valor if valor > 0 else TOPE_POR_DEFECTO_USD


def ruta_registro() -> str:
    """Fichero JSONL. Junto a la base de datos por defecto, o donde diga
    `ARCHMUSE_REGISTRO_USO`.

    Se resuelve `ARCHMUSE_DATA_DIR` aquí en vez de importar
    `analyzer.storage.data_dir()` a propósito: `extraccion/interprete.py` tiene
    **prohibido** importar `analyzer/` (frontera vigilada por
    `tests/test_extraccion_fronteras.py`), y este módulo lo usan los seis
    llamantes. Una fachada que solo la mitad del repositorio puede importar no
    es una fachada — el mismo motivo por el que `ia/` es un paquete de primer
    nivel."""
    override = os.environ.get(_VAR_FICHERO)
    if override:
        return os.path.abspath(override)
    base = os.environ.get("ARCHMUSE_DATA_DIR")
    base = os.path.abspath(base) if base else os.path.join(os.path.expanduser("~"), ".archmuse")
    return os.path.join(base, "uso_ia.jsonl")


def coste_usd(modelo: str, uso: Any) -> Optional[float]:
    """Coste de una llamada, o `None` si el modelo no está tarifado.

    `None` es una respuesta legítima y se propaga tal cual hasta el registro:
    es preferible a una cifra plausible inventada con el precio de otro modelo.
    """
    precios = PRECIOS_USD_POR_MTOK.get(modelo)
    if precios is None:
        return None
    entrada, salida = precios
    n = lambda campo: float(getattr(uso, campo, 0) or 0)  # noqa: E731
    total = (
        n("input_tokens") * entrada
        + n("cache_creation_input_tokens") * entrada * FACTOR_ESCRITURA_CACHE
        + n("cache_read_input_tokens") * entrada * FACTOR_LECTURA_CACHE
        + n("output_tokens") * salida
    )
    return total / 1_000_000


def comprobar_tope() -> None:
    """Se llama **antes** de gastar. Pasarse por una llamada ya pagada no
    sirve de nada."""
    techo = tope_usd()
    with _candado:
        gastado = _gastado_usd
    if gastado >= techo:
        raise TopeDeGastoSuperado(
            "Este proceso lleva gastados %.4f USD y el techo es %.2f USD "
            "(%s). Se corta antes de hacer la llamada."
            % (gastado, techo, _VAR_TOPE)
        )


def registrar(*, modelo: str, llamante: str, uso: Any, duracion_s: float) -> Optional[float]:
    """Anota una llamada ya hecha y devuelve su coste. Nunca lanza.

    Que no lance es deliberado: un fallo escribiendo el registro no puede
    tumbar un análisis que el arquitecto ya ha pagado. El techo sí corta, pero
    eso ocurre en `comprobar_tope()`, antes de gastar.
    """
    global _gastado_usd, _llamadas
    coste = coste_usd(modelo, uso)
    with _candado:
        _gastado_usd += coste or 0.0
        _llamadas += 1
        acumulado = _gastado_usd
        for tabla, clave in ((_por_llamante, llamante), (_por_modelo, modelo)):
            fila_acum = tabla.setdefault(
                clave, {"llamadas": 0, "usd": 0.0, "sin_tarifar": 0,
                        "input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}
            )
            fila_acum["llamadas"] += 1
            fila_acum["usd"] += coste or 0.0
            if coste is None:
                fila_acum["sin_tarifar"] += 1
            for campo in ("input_tokens", "output_tokens", "cache_read_input_tokens"):
                fila_acum[campo] += int(getattr(uso, campo, 0) or 0)
    fila = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "llamante": llamante,
        "modelo": modelo,
        "input_tokens": getattr(uso, "input_tokens", None),
        "output_tokens": getattr(uso, "output_tokens", None),
        "cache_creation_input_tokens": getattr(uso, "cache_creation_input_tokens", None),
        "cache_read_input_tokens": getattr(uso, "cache_read_input_tokens", None),
        "duracion_s": round(duracion_s, 3),
        "coste_usd": round(coste, 6) if coste is not None else None,
        "acumulado_usd": round(acumulado, 6),
    }
    try:
        ruta = ruta_registro()
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return coste


def resumen() -> Dict[str, float]:
    """Lo gastado por este proceso. Para un test, o para imprimirlo al final
    de un análisis."""
    with _candado:
        return {"llamadas": _llamadas, "gastado_usd": round(_gastado_usd, 6),
                "tope_usd": tope_usd()}


def eur_por_usd() -> Optional[float]:
    """Tipo de cambio **declarado**, o `None` si nadie lo ha declarado.

    No hay valor por defecto, y es a propósito. La tarifa de Anthropic está en
    dólares; convertir a euros con un cambio inventado o caducado produce una
    cifra que parece contable y no lo es, y este producto tiene una sola regla
    transversal: nunca una cifra plausible sin respaldo. Quien quiera euros
    declara su cambio en `ARCHMUSE_EUR_POR_USD` — el de su banco, el del día en
    que factura — y entonces, y sólo entonces, el desglose los da.
    """
    bruto = os.environ.get(_VAR_CAMBIO)
    if not bruto:
        return None
    try:
        valor = float(bruto)
    except ValueError:
        return None
    return valor if valor > 0 else None


def en_euros(usd: Optional[float]) -> Optional[float]:
    """Convierte, o devuelve `None` si no hay cambio declarado (ver arriba)."""
    cambio = eur_por_usd()
    if usd is None or cambio is None:
        return None
    return round(usd * cambio, 6)


def desglose() -> Dict[str, Any]:
    """Lo gastado por este proceso, **por punto de llamada y por modelo**.

    Es la respuesta a la pregunta que hasta hoy no tenía datos: cuánto cuesta
    un análisis y en qué se va. El total suelto no sirve para decidir nada; el
    desglose sí, porque señala el módulo concreto que hay que abaratar (o el
    modelo que hay que bajar de perfil, que es la tarea `AG-3`).

    `sin_tarifar` cuenta las llamadas cuyo modelo no está en
    `PRECIOS_USD_POR_MTOK`: su coste no se estima, se declara desconocido, y
    ese contador es lo que impide leer el total como si fuera completo.
    """
    with _candado:
        total = _gastado_usd
        filas_llamante = {k: dict(v) for k, v in _por_llamante.items()}
        filas_modelo = {k: dict(v) for k, v in _por_modelo.items()}
        llamadas = _llamadas
    for tabla in (filas_llamante, filas_modelo):
        for fila in tabla.values():
            fila["usd"] = round(fila["usd"], 6)
            fila["eur"] = en_euros(fila["usd"])
    return {
        "llamadas": llamadas,
        "total_usd": round(total, 6),
        "total_eur": en_euros(total),
        "tope_usd": tope_usd(),
        "sin_tarifar": sum(f["sin_tarifar"] for f in filas_llamante.values()),
        "por_llamante": filas_llamante,
        "por_modelo": filas_modelo,
    }


def a_texto(desg: Optional[Dict[str, Any]] = None) -> str:
    """El desglose en una tabla legible, para imprimirlo al terminar un
    análisis o pegarlo en una incidencia."""
    d = desglose() if desg is None else desg
    moneda = "EUR" if d.get("total_eur") is not None else "USD"
    total = d["total_eur"] if moneda == "EUR" else d["total_usd"]
    lineas = ["Coste medido: %.4f %s en %d llamada(s)" % (total or 0.0, moneda, d["llamadas"])]
    if d["sin_tarifar"]:
        lineas.append("  AVISO: %d llamada(s) con modelo sin tarifa: el total es incompleto"
                      % d["sin_tarifar"])
    for titulo, clave in (("Por punto de llamada", "por_llamante"), ("Por modelo", "por_modelo")):
        if not d[clave]:
            continue
        lineas.append("  %s:" % titulo)
        for nombre, fila in sorted(d[clave].items(), key=lambda kv: -kv[1]["usd"]):
            importe = fila["eur"] if moneda == "EUR" else fila["usd"]
            lineas.append("    %-44s %8.4f %s  (%d llamadas, %d tok entrada, %d salida)"
                          % (nombre, importe or 0.0, moneda, fila["llamadas"],
                             fila["input_tokens"], fila["output_tokens"]))
    return "\n".join(lineas)


def desglose_de_registro(ruta: Optional[str] = None) -> Dict[str, Any]:
    """El mismo desglose, pero leído del JSONL en vez de los contadores vivos.

    Es lo que responde «cuánto ha costado un análisis completo» cuando el
    análisis lo hizo otro proceso —el servidor, un worker, la suite— y ya ha
    terminado. Las filas ilegibles se saltan: un registro corrupto a la mitad
    tiene que dar la cuenta de lo que sí se puede leer, no un error.
    """
    ruta = ruta or ruta_registro()
    filas_llamante: Dict[str, Dict[str, Any]] = {}
    filas_modelo: Dict[str, Dict[str, Any]] = {}
    total, llamadas, sin_tarifar = 0.0, 0, 0
    try:
        with open(ruta, encoding="utf-8") as fh:
            crudas = fh.readlines()
    except OSError:
        crudas = []
    for linea in crudas:
        try:
            fila = json.loads(linea)
        except ValueError:
            continue
        coste = fila.get("coste_usd")
        llamadas += 1
        total += coste or 0.0
        if coste is None:
            sin_tarifar += 1
        for tabla, clave in ((filas_llamante, fila.get("llamante") or "?"),
                             (filas_modelo, fila.get("modelo") or "?")):
            acum = tabla.setdefault(
                clave, {"llamadas": 0, "usd": 0.0, "sin_tarifar": 0,
                        "input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}
            )
            acum["llamadas"] += 1
            acum["usd"] += coste or 0.0
            if coste is None:
                acum["sin_tarifar"] += 1
            for campo in ("input_tokens", "output_tokens", "cache_read_input_tokens"):
                acum[campo] += int(fila.get(campo) or 0)
    for tabla in (filas_llamante, filas_modelo):
        for acum in tabla.values():
            acum["usd"] = round(acum["usd"], 6)
            acum["eur"] = en_euros(acum["usd"])
    return {
        "llamadas": llamadas,
        "total_usd": round(total, 6),
        "total_eur": en_euros(total),
        "tope_usd": tope_usd(),
        "sin_tarifar": sin_tarifar,
        "por_llamante": filas_llamante,
        "por_modelo": filas_modelo,
    }


def reiniciar() -> None:
    """Pone el contador a cero. Sólo para los tests."""
    global _gastado_usd, _llamadas
    with _candado:
        _gastado_usd = 0.0
        _llamadas = 0
        _por_llamante.clear()
        _por_modelo.clear()
