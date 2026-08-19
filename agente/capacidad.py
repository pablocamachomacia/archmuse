# -*- coding: utf-8 -*-
"""`Capacidad`: la declaración ejecutable de una herramienta del agente.

**Qué problema cierra.** El riesgo a diez años no es tener cientos de
herramientas, es que nadie sepa cuál es segura de llamar, cuál cuesta dinero,
cuál escribe en disco y qué NO comprueba. La respuesta del ADR
(`docs/design/2026-08-18-cerebro-arquitecto-adr.md` §B.3) es que cada capacidad
se declare y que la declaración sea ejecutable. Esto es esa declaración,
reducida al subconjunto que el núcleo mínimo necesita hoy.

**Qué falta del ADR, a propósito.** El manifiesto completo lleva además
`requiere`, `produce` y `origen_emitido`: las rutas del grafo que la capacidad
exige como `KNOWN` antes de ejecutarse y las que escribe. Aquí no están, y no
es un olvido: sin grafo portante (tarea V1-7 del plan de migración) esos tres
campos no se podrían comprobar contra nada y serían decoración — tres cadenas
que el validador leería sin poder validar, que es exactamente el tipo de
contrato que se incumple el primer martes con prisa. Entran cuando entre el
grafo, no antes.

**Lo que sí se sostiene desde el primer día:**

- `version` en semver, para que un plan guardado se pueda reproducir.
- `naturaleza`, que particiona las pruebas: `determinista` es golden-testeable,
  `llm` se prueba por contrato y **nunca** puede emitir un valor observado.
- `limitaciones`, que es la materia prima del acta de procedencia: la lista de
  "esto no lo hemos comprobado" se **deriva** de las capacidades ejecutadas, no
  se redacta a mano.
- `efectos`, para que "esto gasta dinero" o "esto escribe un fichero" sea un
  dato del registro y no algo que se descubre leyendo el código.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from . import efectos as _efectos

#: `determinista` — misma entrada, misma salida, siempre.
#: `llm` — no reproducible; nunca puede emitir un valor como observado.
#: `io` — toca disco, red o dinero; exige confirmación explícita.
NATURALEZAS = ("determinista", "llm", "io")


class ErrorDeCapacidad(Exception):
    """Raíz de los errores de esta capa."""


class ArgumentosInvalidos(ErrorDeCapacidad):
    """El modelo pidió la capacidad con argumentos que su esquema no admite.

    Es un rechazo tipado y **barato**: ocurre antes de ejecutar nada, sin tocar
    disco ni gastar un token más. Que el modelo se equivoque al rellenar un
    esquema es normal; lo que no puede pasar es que ese error se convierta en
    una llamada con un argumento inventado.
    """


class ResultadoInvalido(ErrorDeCapacidad):
    """La capacidad devolvió algo que no es un resultado estructurado.

    El contrato es que **toda** capacidad devuelve un `dict` con la clave `ok`.
    Un texto libre volvería al modelo como prosa y ahí ya no se distingue un
    dato medido de una frase plausible — que es justo lo que este núcleo
    existe para impedir.
    """


@dataclass(frozen=True)
class Capacidad:
    """Una herramienta declarada. Inmutable: el registro no se edita en caliente."""

    id: str                                   # "territorial.resolver_ambito"
    version: str                              # semver
    dominio: str
    naturaleza: str
    descripcion: str                          # lo que lee el modelo para decidir
    parametros: Dict[str, Any]                # JSON Schema del objeto de argumentos
    funcion: Callable[..., Dict[str, Any]]
    efectos: Tuple[str, ...] = ()             # () = pura
    limitaciones: Tuple[str, ...] = ()        # lo que esta capacidad NO comprueba
    referencia_normativa: Optional[str] = None

    def __post_init__(self) -> None:
        if self.naturaleza not in NATURALEZAS:
            raise ValueError(
                f"{self.id}: naturaleza «{self.naturaleza}» desconocida; "
                f"admitidas {list(NATURALEZAS)}"
            )
        if len(self.version.split(".")) != 3:
            raise ValueError(f"{self.id}: la versión «{self.version}» no es semver")
        if self.parametros.get("type") != "object":
            raise ValueError(f"{self.id}: `parametros` tiene que ser un esquema de objeto")

    # --- Nombre para la API ------------------------------------------------

    @property
    def nombre_de_herramienta(self) -> str:
        """El `id` traducido a lo que la API de Anthropic admite como nombre.

        Los identificadores del registro llevan punto porque el espacio de
        nombres por dominio es lo que evita el `if/elif` de 382 líneas. La API
        no admite el punto, así que se traduce aquí, en un solo sitio, y el
        registro sabe deshacer la traducción.
        """
        return self.id.replace(".", "__")

    # --- Manifiesto -> esquema de herramienta ------------------------------

    def esquema(self) -> Dict[str, Any]:
        """El manifiesto convertido en herramienta para la API de Anthropic.

        Una sola declaración, un consumidor generado. El plan de migración
        (V1-5) pide tres: éste, la operación OpenAPI y la firma programática.
        Aquí está el primero; los otros dos se generan del mismo `dataclass`
        cuando haga falta, que es la propiedad que se está comprando.
        """
        limites = ""
        if self.limitaciones:
            limites = "\n\nNO comprueba: " + "; ".join(self.limitaciones) + "."
        return {
            "name": self.nombre_de_herramienta,
            "description": self.descripcion.strip() + limites,
            "input_schema": self.parametros,
        }

    # --- Invocación --------------------------------------------------------

    def invocar(self, argumentos: Mapping[str, Any],
                autorizaciones: Optional["_efectos.Autorizaciones"] = None) -> Dict[str, Any]:
        """Valida los argumentos contra el esquema declarado y ejecuta.

        La validación es deliberadamente pequeña —claves admitidas y
        obligatorias presentes— y no pretende ser un validador de JSON Schema:
        lo que tiene que impedir es que un argumento que el manifiesto no
        declara llegue a la función como si lo hubiera declarado.

        **El portero de efectos vive aquí, y no sólo en el ejecutor de Skills**
        (tarea `TL-2`). Hasta ahora la autorización se exigía al ejecutar una
        Skill; una capacidad con efectos invocada por otra puerta —el CLI de
        `CAD-1`, un servidor MCP, un plugin de Revit— escribía sin que nadie lo
        hubiera permitido. Poner el portero en la capacidad cierra **todas** las
        puertas a la vez, que es la única forma de que la garantía siga siendo
        cierta cuando aparezca la cuarta.

        `autorizaciones=None` significa **nada autorizado**, no «no compruebes».
        Es fail-closed a propósito: el descuido de no pasarlas tiene que
        producir un rechazo ruidoso, nunca una escritura silenciosa.
        """
        if self.efectos:
            permitidas = autorizaciones if autorizaciones is not None else _efectos.NINGUNA
            permitidas.exigir(self.id, self.efectos)

        propiedades = self.parametros.get("properties") or {}
        obligatorios = self.parametros.get("required") or []

        sobran = sorted(set(argumentos) - set(propiedades))
        if sobran:
            raise ArgumentosInvalidos(
                f"{self.id}: argumento(s) no declarado(s) {sobran}; "
                f"admitidos {sorted(propiedades)}"
            )
        faltan = sorted(k for k in obligatorios if k not in argumentos)
        if faltan:
            raise ArgumentosInvalidos(
                f"{self.id}: falta(n) el/los argumento(s) obligatorio(s) {faltan}"
            )

        resultado = self.funcion(**dict(argumentos))

        if not isinstance(resultado, dict) or "ok" not in resultado:
            raise ResultadoInvalido(
                f"{self.id}: una capacidad devuelve un dict con la clave «ok», "
                f"no {type(resultado).__name__}"
            )
        return resultado
