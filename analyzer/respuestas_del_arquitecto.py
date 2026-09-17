# -*- coding: utf-8 -*-
"""Modo preguntar: lo que contesta el arquitecto, cómo se lee y dónde se guarda.

PRD `docs/prd/2026-09-17-modo-preguntar.md`. Las decisiones D-1 a D-8 son
**propuestas, pendientes de firma**.

**Una respuesta nunca es una cifra.** Dice a qué vivienda pertenece una pieza, qué
polilínea es la superficie construida, cuál de sus nombres tiene una pieza o si una
familia es interior o exterior. Las superficies se miden cada vez (`C-11`). El almacén
lo vigila: un registro con un número que no sea una coordenada de rótulo no se guarda.

**Identidades (D-1):** una pieza, por el handle de su polilínea; una vivienda, por su
rótulo y la posición del rótulo, con la tolerancia de 1 cm del clic (`C-17`). Si la
pieza se redibuja o el rótulo se mueve, la respuesta deja de aplicarse y se vuelve a
preguntar.

**Dónde (D-2):** `respuestas-del-arquitecto/` en la carpeta de datos de ArchMuse
(`storage.data_dir()`), un JSON por plano, nombrado por la huella de su ruta. Nunca
dentro de su dibujo (`C-16`).

**Esc o Enter sin contestar (D-3)** no se guarda: llega en `sin_respuesta` para que la
tabla lo diga, y la siguiente vez se pregunta otra vez.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple

PERTENENCIA = "pertenencia"
CONSTRUIDA = "construida"
NOMBRE = "nombre"
AMBITO = "ambito"
TIPOS = (PERTENENCIA, CONSTRUIDA, NOMBRE, AMBITO)

#: `C-17`: dos rótulos a menos de esto son el mismo (en metros).
TOLERANCIA_DE_ROTULO_M = 0.01
#: Pablo: «Como máximo 3 preguntas por vivienda».
MAXIMO_DE_PREGUNTAS = 3
CARPETA = "respuestas-del-arquitecto"
VERSION_DEL_FICHERO = 1

CONFIRMADO = "Confirmado por el arquitecto."
SIN_RESPUESTA = "El arquitecto no ha respondido."


@dataclass(frozen=True)
class Vivienda:
    """Una vivienda como la identifica una respuesta: su rótulo y dónde está (metros)."""

    nombre: str
    rotulo: Optional[Tuple[float, float]]

    def es(self, otra: "Vivienda") -> bool:
        if self.nombre != otra.nombre:
            return False
        if self.rotulo is None or otra.rotulo is None:
            return self.rotulo is None and otra.rotulo is None
        return (abs(self.rotulo[0] - otra.rotulo[0]) <= TOLERANCIA_DE_ROTULO_M
                and abs(self.rotulo[1] - otra.rotulo[1]) <= TOLERANCIA_DE_ROTULO_M)

    def a_dict(self) -> dict:
        return {"nombre": self.nombre,
                "rotulo": None if self.rotulo is None else [round(self.rotulo[0], 4),
                                                            round(self.rotulo[1], 4)]}

    @classmethod
    def desde(cls, bruto) -> Optional["Vivienda"]:
        if not isinstance(bruto, dict) or not isinstance(bruto.get("nombre"), str):
            return None
        rotulo = bruto.get("rotulo")
        if rotulo is None:
            return cls(bruto["nombre"], None)
        try:
            return cls(bruto["nombre"], (float(rotulo[0]), float(rotulo[1])))
        except (TypeError, ValueError, IndexError):
            return None

    def clave(self) -> str:
        """Para los ids de las preguntas: `x|y|nombre` (el nombre, al final)."""
        if self.rotulo is None:
            return "-|-|%s" % self.nombre
        return "%.4f|%.4f|%s" % (self.rotulo[0], self.rotulo[1], self.nombre)

    @classmethod
    def desde_clave(cls, partes: Sequence[str]) -> Optional["Vivienda"]:
        if len(partes) < 3:
            return None
        nombre = "|".join(partes[2:])
        if partes[0] == "-" and partes[1] == "-":
            return cls(nombre, None)
        try:
            return cls(nombre, (float(partes[0]), float(partes[1])))
        except ValueError:
            return None


# ---------------------------------------------------------------------------
# Ids de las preguntas: el comando los devuelve tal cual con la respuesta
# ---------------------------------------------------------------------------

def id_pertenencia(handle: str, vivienda: Vivienda) -> str:
    return "%s|%s|%s" % (PERTENENCIA, handle, vivienda.clave())


def id_construida(vivienda: Vivienda) -> str:
    return "%s|%s" % (CONSTRUIDA, vivienda.clave())


def id_nombre(handle: str) -> str:
    return "%s|%s" % (NOMBRE, handle)


def id_ambito(familia: str) -> str:
    return "%s|%s" % (AMBITO, familia)


def _registro_desde_respuesta(bruto) -> Optional[dict]:
    """Una respuesta del comando, `{"id", "valor"}`, como registro guardable, o `None`
    si no se entiende (se ignora: nunca se adivina qué quería decir)."""
    if not isinstance(bruto, dict) or not isinstance(bruto.get("id"), str):
        return None
    partes = bruto["id"].split("|")
    valor = bruto.get("valor")
    valor_texto = str(valor).strip().lower() if valor is not None else ""
    tipo = partes[0]
    if tipo == PERTENENCIA and len(partes) >= 5 and valor_texto in ("si", "sí", "no"):
        vivienda = Vivienda.desde_clave(partes[2:])
        if vivienda is None or not partes[1]:
            return None
        return {"tipo": PERTENENCIA, "pieza": partes[1], "vivienda": vivienda.a_dict(),
                "es_suya": valor_texto != "no"}
    if tipo == CONSTRUIDA and len(partes) >= 4:
        vivienda = Vivienda.desde_clave(partes[1:])
        handle = str(valor or "").strip()
        if vivienda is None or not handle:
            return None
        return {"tipo": CONSTRUIDA, "vivienda": vivienda.a_dict(), "polilinea": handle}
    if tipo == NOMBRE and len(partes) == 2 and partes[1]:
        try:
            opcion = int(str(valor).strip())
        except (TypeError, ValueError):
            return None
        return {"tipo": NOMBRE, "pieza": partes[1], "opcion": opcion} if opcion >= 1 else None
    if tipo == AMBITO and len(partes) >= 2 and valor_texto in ("interior", "exterior"):
        return {"tipo": AMBITO, "familia": "|".join(partes[1:]), "ambito": valor_texto}
    return None


def _clave_de_registro(registro: dict) -> Tuple:
    tipo = registro.get("tipo")
    if tipo == PERTENENCIA:
        v = registro["vivienda"]
        return (tipo, registro["pieza"], v["nombre"], tuple(v["rotulo"] or ()))
    if tipo == CONSTRUIDA:
        v = registro["vivienda"]
        return (tipo, v["nombre"], tuple(v["rotulo"] or ()))
    if tipo == NOMBRE:
        return (tipo, registro["pieza"])
    return (tipo, registro.get("familia"))


def es_registro_valido(registro) -> bool:
    """Un registro guardable: de un tipo conocido y **sin ninguna cifra de superficie**."""
    if not isinstance(registro, dict) or registro.get("tipo") not in TIPOS:
        return False
    tipo = registro["tipo"]
    permitidas = {
        PERTENENCIA: {"tipo", "pieza", "vivienda", "es_suya", "fecha"},
        CONSTRUIDA: {"tipo", "vivienda", "polilinea", "fecha"},
        NOMBRE: {"tipo", "pieza", "nombre", "fecha"},
        AMBITO: {"tipo", "familia", "ambito", "fecha"},
    }[tipo]
    if set(registro) - permitidas:
        return False
    if tipo in (PERTENENCIA, CONSTRUIDA) and Vivienda.desde(registro.get("vivienda")) is None:
        return False
    if tipo == PERTENENCIA:
        return isinstance(registro.get("pieza"), str) and isinstance(registro.get("es_suya"), bool)
    if tipo == CONSTRUIDA:
        return isinstance(registro.get("polilinea"), str) and bool(registro["polilinea"])
    if tipo == NOMBRE:
        return isinstance(registro.get("pieza"), str) and isinstance(registro.get("nombre"), str)
    return registro.get("ambito") in ("interior", "exterior") and isinstance(
        registro.get("familia"), str)


def fusionar(anteriores: Iterable[dict], nuevos: Iterable[dict]) -> List[dict]:
    """Los registros de siempre con los nuevos encima: el mismo hecho, la última respuesta."""
    por_clave: Dict[Tuple, dict] = {}
    for registro in list(anteriores) + list(nuevos):
        clave = _clave_de_registro(registro)
        por_clave.pop(clave, None)
        por_clave[clave] = registro
    return list(por_clave.values())


# ---------------------------------------------------------------------------
# Las respuestas que aplica la tabla
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Respuestas:
    registros: Tuple[dict, ...] = ()
    #: Ids de las preguntas que el arquitecto dejó sin contestar en esta pasada.
    sin_respuesta: FrozenSet[str] = frozenset()
    #: Preguntas ya hechas en esta pasada del comando (D-8).
    preguntas_hechas: int = 0
    #: Las respuestas de interior/exterior por el camino anterior (`ambitos`).
    ambitos_sueltos: Mapping[str, str] = field(default_factory=dict)
    #: Ids de las preguntas contestadas en esta pasada: no se vuelven a hacer en ella.
    respondidas: FrozenSet[str] = frozenset()

    @property
    def vacias(self) -> bool:
        return not self.registros and not self.sin_respuesta and not self.ambitos_sueltos

    def pertenencia(self, handle: Optional[str], vivienda: Vivienda) -> Optional[bool]:
        """¿Es esta pieza de esta vivienda, según él? `None` si no lo ha dicho.

        La última respuesta sobre la pieza que dice algo de esta vivienda manda. Un «Sí»
        a otra vivienda es «No» para ésta (D-4); un «No» a otra no dice nada de ésta."""
        if not handle:
            return None
        for registro in reversed(self.registros):
            if registro.get("tipo") != PERTENENCIA or registro.get("pieza") != handle:
                continue
            suya = Vivienda.desde(registro.get("vivienda"))
            if suya is None:
                continue
            if suya.es(vivienda):
                return bool(registro.get("es_suya"))
            if registro.get("es_suya"):
                return False
        return None

    def de_otra(self, handle: Optional[str], vivienda: Vivienda) -> Optional[str]:
        """El nombre de la vivienda a la que él dio esta pieza, si no es ésta."""
        if not handle:
            return None
        for registro in reversed(self.registros):
            if (registro.get("tipo") == PERTENENCIA and registro.get("pieza") == handle
                    and registro.get("es_suya")):
                suya = Vivienda.desde(registro.get("vivienda"))
                return None if suya is None or suya.es(vivienda) else suya.nombre
        return None

    def construida(self, vivienda: Vivienda) -> Optional[str]:
        for registro in reversed(self.registros):
            if registro.get("tipo") == CONSTRUIDA:
                suya = Vivienda.desde(registro.get("vivienda"))
                if suya is not None and suya.es(vivienda):
                    return registro.get("polilinea")
        return None

    def nombre(self, handle: Optional[str], opciones: Sequence[str]) -> Optional[str]:
        """El nombre que eligió, si es uno de los que tiene la pieza."""
        if not handle:
            return None
        for registro in reversed(self.registros):
            if registro.get("tipo") != NOMBRE or registro.get("pieza") != handle:
                continue
            if "nombre" in registro:
                return registro["nombre"] if registro["nombre"] in opciones else None
            opcion = registro.get("opcion")
            if isinstance(opcion, int) and 1 <= opcion <= len(opciones):
                return opciones[opcion - 1]
            return None
        return None

    def ambito(self, familia: str) -> Optional[str]:
        for registro in reversed(self.registros):
            if registro.get("tipo") == AMBITO and registro.get("familia") == familia:
                return registro.get("ambito")
        valor = self.ambitos_sueltos.get(familia)
        return valor if valor in ("interior", "exterior") else None


def desde_peticion(cuerpo: Mapping, guardadas: Sequence[dict] = ()) -> Tuple[Respuestas, List[dict]]:
    """Las respuestas guardadas más las que trae la petición, y las nuevas por separado
    (para guardarlas si la tabla las acepta)."""
    nuevas = [r for r in (_registro_desde_respuesta(b)
                          for b in (cuerpo.get("respuestas_del_arquitecto") or []))
              if r is not None]
    sin = frozenset(str(i) for i in (cuerpo.get("sin_respuesta") or []) if isinstance(i, str))
    try:
        hechas = max(0, int(cuerpo.get("preguntas_hechas") or 0))
    except (TypeError, ValueError):
        hechas = 0
    ambitos = cuerpo.get("ambitos") if isinstance(cuerpo.get("ambitos"), dict) else {}
    from .plantilla_cuadro import clave_de_familia

    sueltos = {clave_de_familia(k): str(v).strip().lower() for k, v in ambitos.items()}
    respondidas = frozenset(b["id"] for b in (cuerpo.get("respuestas_del_arquitecto") or [])
                            if isinstance(b, dict) and isinstance(b.get("id"), str))
    respuestas = Respuestas(tuple(fusionar([r for r in guardadas if es_registro_valido(r)], nuevas)),
                            sin, hechas, sueltos, respondidas)
    return respuestas, nuevas


def polilineas_de_la_peticion(cuerpo: Mapping) -> List[dict]:
    """Las polilíneas que él ha marcado como construida y que el comando manda con la
    respuesta: se añaden a `otras_polilineas` para medirlas con el lector de siempre."""
    salida = []
    for bruto in cuerpo.get("respuestas_del_arquitecto") or []:
        if isinstance(bruto, dict) and isinstance(bruto.get("polilinea"), dict):
            salida.append(bruto["polilinea"])
    return salida


# ---------------------------------------------------------------------------
# El almacén
# ---------------------------------------------------------------------------

def huella_del_plano(ruta: str) -> str:
    normal = os.path.normcase(os.path.normpath(str(ruta).strip()))
    return hashlib.sha256(normal.encode("utf-8")).hexdigest()[:24]


class Almacen:
    """Un JSON por plano en `carpeta`. Nunca lanza hacia fuera por un fichero roto: una
    respuesta perdida sólo hace que se vuelva a preguntar."""

    def __init__(self, carpeta: Optional[str] = None):
        if carpeta is None:
            from .storage import data_dir

            carpeta = os.path.join(data_dir(), CARPETA)
        self.carpeta = carpeta

    def _ruta(self, plano: str) -> str:
        return os.path.join(self.carpeta, huella_del_plano(plano) + ".json")

    def cargar(self, plano: Optional[str]) -> List[dict]:
        if not plano:
            return []
        try:
            with open(self._ruta(plano), encoding="utf-8") as f:
                datos = json.load(f)
        except (OSError, ValueError):
            return []
        return [r for r in (datos.get("respuestas") or []) if es_registro_valido(r)]

    def guardar(self, plano: Optional[str], nuevos: Iterable[dict]) -> int:
        """Añade `nuevos` a lo guardado del plano. Devuelve cuántos ha guardado."""
        if not plano:
            return 0
        anteriores = self.cargar(plano)
        sin_fecha = lambda r: {k: v for k, v in r.items() if k != "fecha"}  # noqa: E731
        ya = [sin_fecha(r) for r in anteriores]
        nuevos = [dict(r, fecha=r.get("fecha") or datetime.now().isoformat(timespec="seconds"))
                  for r in nuevos]
        # Una respuesta que ya estaba guardada igual no se reescribe: conserva su fecha.
        nuevos = [r for r in nuevos if es_registro_valido(r) and sin_fecha(r) not in ya]
        if not nuevos:
            return 0
        registros = fusionar(anteriores, nuevos)
        os.makedirs(self.carpeta, exist_ok=True)
        ruta = self._ruta(plano)
        temporal = ruta + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            # Sin la ruta: la carpeta de un proyecto lleva el nombre del cliente, y el
            # fichero ya se llama por su huella.
            json.dump({"version": VERSION_DEL_FICHERO, "respuestas": registros},
                      f, ensure_ascii=False, indent=1)
        os.replace(temporal, ruta)
        return len(nuevos)
