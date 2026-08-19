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

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

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


#: Cómo se dice cada incumplimiento del esquema en el idioma del proyecto.
#: `jsonschema` los explica en inglés y con el vocabulario de JSON Schema; esto
#: viaja hasta un modelo que tiene que corregir la llamada y, en el CLI de
#: `CAD-1`, hasta una persona. Se traducen los que un modelo comete de verdad;
#: para el resto se deja el mensaje original, que es peor pero nunca falso.
_QUE_FALLA = {
    "type": "«%(ruta)s» tiene que ser de tipo %(espera)s y ha llegado %(tipo)s (%(valor)s)",
    "enum": "«%(ruta)s» sólo admite %(espera)s, y ha llegado %(valor)s",
    "const": "«%(ruta)s» sólo admite %(espera)s, y ha llegado %(valor)s",
    "minimum": "«%(ruta)s» no puede ser menor que %(espera)s, y ha llegado %(valor)s",
    "maximum": "«%(ruta)s» no puede ser mayor que %(espera)s, y ha llegado %(valor)s",
    "exclusiveMinimum": "«%(ruta)s» tiene que ser mayor que %(espera)s, y ha llegado %(valor)s",
    "exclusiveMaximum": "«%(ruta)s» tiene que ser menor que %(espera)s, y ha llegado %(valor)s",
    "minLength": "«%(ruta)s» necesita al menos %(espera)s carácter(es), y ha llegado %(valor)s",
    "maxLength": "«%(ruta)s» admite como mucho %(espera)s carácter(es), y ha llegado %(valor)s",
    "minItems": "«%(ruta)s» necesita al menos %(espera)s elemento(s), y ha llegado %(valor)s",
    "maxItems": "«%(ruta)s» admite como mucho %(espera)s elemento(s), y ha llegado %(valor)s",
    "pattern": "«%(ruta)s» tiene que seguir el patrón %(espera)s, y ha llegado %(valor)s",
}

#: Cómo se llama en castellano cada tipo de JSON Schema.
_TIPOS = {
    "string": "texto", "number": "número", "integer": "número entero",
    "boolean": "sí/no", "array": "lista", "object": "objeto", "null": "nulo",
}

#: Longitud a la que se corta un valor al citarlo en un mensaje de error. Un
#: argumento de treinta mil caracteres no se explica mejor por enseñarlo entero.
_MAX_VALOR_EN_MENSAJE = 120


def _tipo_de(valor: Any) -> str:
    if isinstance(valor, bool):
        return _TIPOS["boolean"]
    if isinstance(valor, int):
        return _TIPOS["integer"]
    if isinstance(valor, float):
        return _TIPOS["number"]
    if isinstance(valor, str):
        return _TIPOS["string"]
    if isinstance(valor, list):
        return _TIPOS["array"]
    if isinstance(valor, dict):
        return _TIPOS["object"]
    if valor is None:
        return _TIPOS["null"]
    return type(valor).__name__


def _citar(valor: Any) -> str:
    texto = repr(valor)
    if len(texto) > _MAX_VALOR_EN_MENSAJE:
        return texto[:_MAX_VALOR_EN_MENSAJE] + "…"
    return texto


def _ruta_de(error: "ValidationError") -> str:
    """El argumento que falla, nombrado como lo escribiría quien llama.

    `plantas[0].uso` y no `deque(['plantas', 0, 'uso'])`: el mensaje lo lee un
    modelo que tiene que corregir la llamada siguiente.
    """
    partes: List[str] = []
    for tramo in error.absolute_path:
        if isinstance(tramo, int):
            partes.append("[%d]" % tramo)
        elif partes:
            partes.append(".%s" % tramo)
        else:
            partes.append(str(tramo))
    return "".join(partes) or "(los argumentos)"


def _esperado_de(error: "ValidationError") -> str:
    validador = error.validator
    valor = error.validator_value
    if validador == "type":
        tipos = valor if isinstance(valor, list) else [valor]
        return " o ".join(_TIPOS.get(t, str(t)) for t in tipos)
    if validador in ("enum", "const"):
        opciones = valor if isinstance(valor, list) else [valor]
        return ", ".join(_citar(o) for o in opciones)
    return _citar(valor)


def _en_castellano(error: "ValidationError") -> str:
    """Un incumplimiento del esquema, dicho para que se pueda corregir."""
    plantilla = _QUE_FALLA.get(str(error.validator))
    if plantilla is None:
        return "«%s»: %s" % (_ruta_de(error), error.message)

    if str(error.validator) in ("minLength", "maxLength"):
        visto: Any = len(error.instance) if isinstance(error.instance, str) else error.instance
    elif str(error.validator) in ("minItems", "maxItems"):
        visto = len(error.instance) if isinstance(error.instance, list) else error.instance
    else:
        visto = _citar(error.instance)

    return plantilla % {
        "ruta": _ruta_de(error),
        "espera": _esperado_de(error),
        "tipo": _tipo_de(error.instance),
        "valor": visto,
    }


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

    #: El validador compilado del esquema. No es un campo del dataclass a
    #: propósito: no forma parte del contrato, no viaja al manifiesto y no
    #: entra en la huella de compatibilidad. Lo pone `__post_init__`.
    _validador: "Draft202012Validator" = field(init=False, repr=False,
                                               compare=False, default=None)  # type: ignore[assignment]

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
        # El esquema se compila **al declarar la capacidad**, no en la primera
        # llamada. Un manifiesto con un esquema mal escrito tiene que reventar
        # cuando se escribe, no seis meses después cuando el modelo por fin usa
        # esa herramienta con el argumento raro.
        Draft202012Validator.check_schema(self.parametros)
        object.__setattr__(self, "_validador", Draft202012Validator(self.parametros))

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
        """Valida los argumentos contra el esquema declarado **entero** y ejecuta.

        La validación es estructural y completa: tipos, `enum`, rangos,
        longitudes, patrones y objetos anidados, contra el mismo JSON Schema
        que se le enseñó al modelo. No es una comprobación de estilo, es la
        frontera del sistema: los argumentos los rellena un modelo de lenguaje,
        y un `"25 m"` donde el manifiesto dice `number`, o un `"nave"` donde
        dice `enum: [vivienda, local]`, entra en la función y sale por el otro
        lado convertido en un resultado con pinta de bueno. Rechazarlo aquí
        cuesta cero tokens y produce un mensaje que el modelo sabe corregir en
        la iteración siguiente; dejarlo pasar produce un número que nadie midió.

        **Se devuelven todos los problemas, no el primero.** Quien corrige una
        llamada —modelo o persona— prefiere ver los tres a la vez, y el modelo
        además reintenta una sola vez.

        `jsonschema` ya era dependencia directa de `normativa/validacion.py`, así
        que esto no añade ninguna: la validación somera anterior era una
        omisión, no una decisión de no depender de nada.

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

        # Las dos comprobaciones de arriba las hace también el esquema, y se
        # quedan: su mensaje dice qué se admite y qué falta, que es lo que se
        # puede corregir. Lo que sigue es todo lo demás — tipos, enums, rangos,
        # longitudes, patrones y lo anidado.
        problemas = self._problemas_de_esquema(argumentos)
        if problemas:
            raise ArgumentosInvalidos(
                "%s: %d problema(s) con los argumentos: %s"
                % (self.id, len(problemas), "; ".join(problemas))
            )

        resultado = self.funcion(**dict(argumentos))

        if not isinstance(resultado, dict) or "ok" not in resultado:
            raise ResultadoInvalido(
                f"{self.id}: una capacidad devuelve un dict con la clave «ok», "
                f"no {type(resultado).__name__}"
            )
        return resultado

    # --- Validación estructural --------------------------------------------

    def _problemas_de_esquema(self, argumentos: Mapping[str, Any]) -> List[str]:
        """Todos los incumplimientos del esquema, en castellano y ordenados.

        Ordenados por la ruta del argumento y no por el orden en que
        `jsonschema` los encuentre: dos llamadas con los mismos argumentos malos
        tienen que producir el mismo mensaje, o un test de esto no se puede
        escribir.
        """
        errores = sorted(
            self._validador.iter_errors(dict(argumentos)),
            key=lambda e: (list(e.absolute_path), e.validator or ""),
        )
        problemas: List[str] = []
        for error in errores:
            # `required` y `additionalProperties` **de la raíz** ya los ha dicho
            # `invocar` con un mensaje mejor: repetirlos aquí sería decir dos
            # veces lo mismo con dos redacciones distintas. Los de dentro de un
            # objeto anidado no los dice nadie más —las dos comprobaciones a
            # mano sólo miran el primer nivel— así que ésos sí van, y son justo
            # donde un modelo se equivoca de verdad.
            de_la_raiz = not list(error.absolute_path)
            if de_la_raiz and error.validator in ("required", "additionalProperties"):
                continue
            texto = _en_castellano(error)
            if texto not in problemas:
                problemas.append(texto)
        return problemas
