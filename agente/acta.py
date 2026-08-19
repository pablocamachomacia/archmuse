# -*- coding: utf-8 -*-
"""El acta de procedencia: de dónde salió cada número y qué NO se comprobó.

**Esto es producto, no telemetría.** Es la distinción del §3 de la revisión de
stack y conviene no perderla: la traza operativa —latencia, tokens, errores—
vive en observabilidad y le importa al que opera el sistema. El acta le importa
al arquitecto que va a firmar, viaja con el entregable y es la mitad del
argumento de venta. Enseñarle a un arquitecto un volcado de trazas y llamarlo
transparencia es el fallo que este módulo existe para evitar.

**Lo que la hace defendible y no un adorno:**

1. **La lista de «no comprobado» se DERIVA.** Sale de las `limitaciones` de las
   Skills y capacidades que se ejecutaron, y de las ramas que quedaron sin
   hacer. Nadie la redacta, así que nadie puede olvidarse de actualizarla al
   añadir una comprobación nueva.
2. **Cada afirmación dice quién la produjo y de qué clase es.** Un hecho, un
   cálculo, una inferencia y una propuesta se leen distinto, y el acta los
   presenta distinto.
3. **Va sellada.** Un sha256 del contenido: dos actas que dicen lo mismo tienen
   el mismo sello, y una que se editó después ya no cuadra.
4. **Fija las versiones.** `skill@version` y `capacidad@version` en cada paso,
   que es lo que permite reproducir dentro de dos años lo que se emitió hoy —
   requisito de defender una firma ante un litigio.

**Lo que el acta NO hace:** no juzga. No dice si el proyecto está bien. Dice qué
se miró, con qué, qué salió y qué se quedó fuera.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from .ejecucion import HECHO, ResultadoDeEjecucion
from .registro import CapacidadDesconocida, Registro, RegistroDeSkills, SkillDesconocida
from analyzer.marca_borrador import LEYENDA as _LEYENDA

#: Se estampa en toda acta, sin excepción y sin opción de quitarlo.
#: La misma leyenda que estampan los PDF (`analyzer/marca_borrador.py`), leída
#: de allí y no copiada: dos textos que dicen lo mismo hoy dicen cosas
#: distintas dentro de un año, y este en concreto delimita qué es ArchMuse
#: —asesor, no firmante—, así que no puede haber dos versiones. La dirección
#: de la dependencia es la correcta: el agente puede leer del dominio.
LEYENDA_BORRADOR = _LEYENDA


def _sello(datos) -> str:
    crudo = json.dumps(datos, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Acta:
    """El documento. Inmutable, sellado y serializable."""

    objetivo: str
    proyecto_id: str
    ejecucion_id: str
    emitida_en: str
    datos: Tuple[dict, ...] = field(default_factory=tuple)
    pasos: Tuple[dict, ...] = field(default_factory=tuple)
    no_comprobado: Tuple[str, ...] = field(default_factory=tuple)
    preguntas_abiertas: Tuple[str, ...] = field(default_factory=tuple)
    entregables: Tuple[dict, ...] = field(default_factory=tuple)
    completa: bool = False
    leyenda: str = LEYENDA_BORRADOR

    @property
    def sello(self) -> str:
        return _sello(self._cuerpo())

    def _cuerpo(self) -> dict:
        return {
            "objetivo": self.objetivo,
            "proyecto_id": self.proyecto_id,
            "ejecucion_id": self.ejecucion_id,
            "emitida_en": self.emitida_en,
            "datos": [dict(d) for d in self.datos],
            "pasos": [dict(p) for p in self.pasos],
            "no_comprobado": list(self.no_comprobado),
            "preguntas_abiertas": list(self.preguntas_abiertas),
            "entregables": [dict(e) for e in self.entregables],
            "completa": self.completa,
            "leyenda": self.leyenda,
        }

    def a_dict(self) -> dict:
        cuerpo = self._cuerpo()
        cuerpo["sello"] = _sello(cuerpo)
        return cuerpo

    # -- Lectura humana ------------------------------------------------------

    def a_texto(self) -> str:
        """El acta en castellano, para leerla sin abrir un JSON.

        Deliberadamente corta y por secciones: C2 del documento de alineación
        pide una página con el porqué a un clic, no un volcado exhaustivo. Lo
        exhaustivo está en `a_dict()`.
        """
        lineas: List[str] = [
            "ACTA DE PROCEDENCIA — %s" % self.objetivo,
            "Proyecto %s · ejecución %s · %s" % (self.proyecto_id, self.ejecucion_id,
                                                 self.emitida_en),
            self.leyenda,
            "",
            "QUÉ SE HA ESTABLECIDO",
        ]
        if not self.datos:
            lineas.append("  (nada)")
        for d in self.datos:
            valor = d.get("valor")
            unidad = (" %s" % d["unidad"]) if d.get("unidad") else ""
            if valor is None:
                motivo = (d.get("motivo") or {}).get("detalle", "sin motivo")
                lineas.append("  - %s: NO DETERMINADO — %s" % (d["nombre"], motivo))
            else:
                lineas.append(
                    "  - %s: %s%s  [%s · %s]"
                    % (d["nombre"], valor, unidad, d["etiqueta"], d.get("fuente", "?"))
                )
            if d.get("cita"):
                lineas.append("      fuente oficial: %s" % d["cita"])
            for h in d.get("hipotesis") or ():
                lineas.append("      hipótesis: %s" % h)

        lineas += ["", "CÓMO SE HA HECHO"]
        for p in self.pasos:
            lineas.append("  - %s (%s) — %s" % (p["paso_id"], p["skill"], p["estado"]))
            for inv in p.get("invocaciones") or ():
                lineas.append("      usó %s@%s" % (inv["capacidad"], inv["version"]))
            for c in p.get("comprobaciones") or ():
                # Tres estados, no dos. «No se ha podido comprobar» no es
                # «falla»: lo primero dice que falta un dato de entrada, lo
                # segundo acusa al plano del arquitecto de un defecto. Ver
                # `NoSeHaPodidoComprobar` en `agente/verificacion.py`.
                if c["ok"]:
                    marca = "[OK]"
                elif c.get("no_procede"):
                    marca = "[NO SE HA PODIDO COMPROBAR]"
                else:
                    marca = "[FALLA]"
                lineas.append(
                    "      %s %s%s"
                    % (marca, c["nombre"],
                       ("" if c["ok"] else " — %s" % c["detalle"]))
                )

        lineas += ["", "QUÉ NO SE HA COMPROBADO"]
        if not self.no_comprobado:
            lineas.append("  (nada que declarar)")
        for n in self.no_comprobado:
            lineas.append("  - %s" % n)

        if self.preguntas_abiertas:
            lineas += ["", "QUÉ HACE FALTA PARA TERMINAR"]
            for q in self.preguntas_abiertas:
                lineas.append("  - %s" % q)

        lineas += ["", "Sello: %s" % self.sello]
        return "\n".join(lineas)


def levantar(resultado: ResultadoDeEjecucion, *, capacidades: Registro,
             skills: RegistroDeSkills, emitida_en: Optional[str] = None) -> Acta:
    """Construye el acta a partir de lo que realmente ocurrió.

    No recibe nada que no venga de la ejecución: si un dato no está en el
    resultado de un paso, no puede aparecer en el acta. Es lo que impide que el
    acta se convierta en un texto paralelo a lo que pasó.
    """
    datos: List[dict] = []
    pasos: List[dict] = []
    no_comprobado: List[str] = []
    entregables: List[dict] = []

    for paso in resultado.pasos:
        salida = paso.salida or {}
        cuerpo = salida.get("resultado") or {}
        dictamen = salida.get("dictamen") or {}

        pasos.append({
            "paso_id": paso.paso_id,
            "skill": paso.skill,
            "estado": paso.estado,
            "momento": paso.momento,
            "motivo": paso.motivo,
            "invocaciones": salida.get("invocaciones") or [],
            "comprobaciones": dictamen.get("comprobaciones") or [],
            "verificado": bool(dictamen.get("verificado")),
            "sello_del_paso": paso.sello,
        })

        datos.extend(cuerpo.get("afirmaciones") or [])
        entregables.extend(cuerpo.get("entregables") or [])
        no_comprobado.extend(cuerpo.get("no_hecho") or [])

        if paso.estado != HECHO:
            no_comprobado.append(
                "paso «%s» (%s): %s" % (paso.paso_id, paso.skill, paso.motivo or paso.estado)
            )
        elif not dictamen.get("verificado"):
            no_comprobado.append(
                "el resultado de «%s» no ha superado sus propias comprobaciones: %s"
                % (paso.paso_id, dictamen.get("avisos") or [])
            )

        # Una comprobación que no llegó a ejecutarse pertenece a esta sección
        # aunque el paso saliera verificado: es exactamente «lo que no se ha
        # comprobado», y callarla dejaría al arquitecto creyendo que se miró.
        for pendiente in dictamen.get("no_comprobadas") or ():
            no_comprobado.append(
                "no se ha podido comprobar en «%s» — %s" % (paso.paso_id, pendiente)
            )

        # Las limitaciones declaradas de la Skill y de cada capacidad que usó.
        # Derivadas, no redactadas: añadir una limitación al manifiesto la mete
        # en todas las actas futuras sin tocar este fichero.
        no_comprobado.extend(_limitaciones_de(paso.skill, skills))
        for inv in salida.get("invocaciones") or []:
            no_comprobado.extend(_limitaciones_de_capacidad(inv["capacidad"], capacidades))

    return Acta(
        objetivo=resultado.plan.objetivo,
        proyecto_id=resultado.plan.proyecto_id,
        ejecucion_id=resultado.ejecucion_id,
        emitida_en=emitida_en or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        datos=tuple(datos),
        pasos=tuple(pasos),
        no_comprobado=tuple(dict.fromkeys(no_comprobado)),
        preguntas_abiertas=tuple(resultado.preguntas),
        entregables=tuple(entregables),
        completa=resultado.completa,
    )


def _limitaciones_de(firma: str, skills: RegistroDeSkills) -> List[str]:
    try:
        skill = skills.buscar(firma)
    except SkillDesconocida:
        return []
    return ["%s no comprueba: %s" % (skill.id, l) for l in skill.limitaciones]


def _limitaciones_de_capacidad(capacidad_id: str, capacidades: Registro) -> List[str]:
    try:
        capacidad = capacidades.buscar(capacidad_id)
    except CapacidadDesconocida:
        return []
    return ["%s no comprueba: %s" % (capacidad.id, l) for l in capacidad.limitaciones]
