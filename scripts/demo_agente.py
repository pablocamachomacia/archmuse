# -*- coding: utf-8 -*-
"""Demostración del núcleo agéntico, sin red y sin gastar un céntimo.

    python scripts/demo_agente.py

**Qué demuestra, y por qué así.** Ejecuta un plan de dos Skills reales contra el
corpus normativo real y enseña el acta que sale. No usa la API de Anthropic a
propósito: lo que hay que ver aquí no es que un modelo sepa elegir herramientas
—eso ya se prueba con cliente guionizado en `tests/test_agente_nucleo.py`— sino
que **el trabajo que se entrega es rastreable hasta el BOE**. Esa parte no
necesita modelo, y mezclarla con una llamada de pago haría que la demostración
dependiera de tener clave.

Enseña cuatro cosas, y las cuatro son el producto:

1. Un objetivo compuesto se resuelve encadenando procedimientos, no funciones.
2. Cada número lleva de dónde salió y de qué clase es (hecho, cálculo,
   inferencia o propuesta).
3. Lo que **no** se ha comprobado se dice por su nombre, derivado de los
   manifiestos y no redactado a mano.
4. Cuando falta un dato, la respuesta es la pregunta concreta.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from agente import acta as _acta  # noqa: E402
from agente import planificador as _plani  # noqa: E402
from agente.ejecucion import BitacoraEnMemoria, Ejecutor, Paso, Plan  # noqa: E402
from agente.memoria import MemoriaDeProyecto, SustratoEnMemoria  # noqa: E402
from agente.registro import registro, registro_de_skills  # noqa: E402

PROYECTO = "demo-madrid"

# Lo que sabría ArchMuse de un proyecto real: lo que el arquitecto ha declarado.
# En producción esto vive en la memoria del proyecto y se rellena preguntando.
DATOS = {
    "territorial.municipio": "Madrid",
    "proyecto.uso": "residencial.vivienda_libre",
    "proyecto.tipologia": "plurifamiliar",
    "proyecto.fecha_devengo": "2026-01-01",
    "evacuacion.numero_salidas": "una",
    "evacuacion.condicion": "general",
    "evacuacion.longitud_recorrido_m": 21.4,
}


class _BloqueDeGuion:
    """Un `tool_use` de mentira, para que la demostración no cueste nada."""

    type = "tool_use"

    def __init__(self, entrada: dict) -> None:
        self.name = _plani.NOMBRE_HERRAMIENTA
        self.input = entrada
        self.id = "guion"


class _RespuestaDeGuion:
    def __init__(self, entrada: dict) -> None:
        self.content = [_BloqueDeGuion(entrada)]
        self.usage = None


class _ClienteDeGuion:
    """El cliente de Anthropic sustituido por un doble que ya sabe qué decir.

    Lo que esta demostración enseña no es que un modelo acierte —eso se prueba
    en la suite, y con clave costaría dinero cada vez—, sino que **su respuesta
    se valida antes de ejecutar nada**: si el plan nombrara una Skill que no
    existe, o tuviera un ciclo, se rechazaría aquí mismo con el motivo.
    """

    def __init__(self, entrada: dict) -> None:
        self._entrada = entrada
        self.messages = self

    def create(self, **_kwargs):
        return _RespuestaDeGuion(self._entrada)


def _titulo(texto: str) -> None:
    print("\n" + "=" * 78)
    print(texto)
    print("=" * 78)


def main() -> int:
    capacidades = registro(recargar=True)
    skills = registro_de_skills(recargar=True)

    _titulo("LO QUE ARCHMUSE SABE HACER HOY")
    print("Capacidades (funciones sueltas, con manifiesto):")
    for c in capacidades:
        print("  · %s@%s — %s" % (c.id, c.version, c.descripcion.split(".")[0]))
    print("\nSkills (procedimientos profesionales):")
    for s in skills:
        print("  · %s@%s" % (s.id, s.version))
        print("      %s" % s.objetivo)
        print("      necesita: %s" % ([r.clave for r in s.requiere] or "nada"))

    # --- 1. Sin datos, la respuesta es la pregunta -------------------------
    _titulo("1. SIN DATOS DEL PROYECTO, LA SALIDA ES UNA PREGUNTA")
    vacia = MemoriaDeProyecto(PROYECTO, SustratoEnMemoria())
    plan_ficha = Plan(
        objetivo="Comprueba esta parcela y su normativa",
        proyecto_id=PROYECTO,
        pasos=(Paso(id="ficha", skill="territorial.ficha_normativa_de_parcela"),),
    )
    ejecutor = Ejecutor(capacidades=capacidades, skills=skills, bitacora=BitacoraEnMemoria())
    sin_datos = ejecutor.ejecutar(plan_ficha, vacia, ejecucion_id="demo-sin-datos")
    print("Estado del paso: %s" % sin_datos.pasos[0].estado)
    print("No se ha gastado un token ni se ha tocado un fichero. Preguntas:")
    for q in sin_datos.preguntas:
        print("  · %s" % q)

    # --- 2. Con datos, trabajo de verdad -----------------------------------
    _titulo("2. CON LOS DATOS DECLARADOS, EL TRABAJO COMPLETO")
    memoria = MemoriaDeProyecto(PROYECTO, SustratoEnMemoria())
    for clave, valor in DATOS.items():
        memoria.declarar(clave, valor, registrado_por="usuario:pablo")

    plan = Plan(
        objetivo="Comprueba la parcela y si el recorrido de evacuación cabe en norma",
        proyecto_id=PROYECTO,
        pasos=(
            Paso(id="ficha", skill="territorial.ficha_normativa_de_parcela"),
            Paso(id="evacuacion", skill="revision.recorridos_de_evacuacion",
                 depende_de=("ficha",)),
        ),
    )
    resultado = ejecutor.ejecutar(plan, memoria, ejecucion_id="demo-completa")
    print("Plan de %d pasos · completa: %s" % (len(plan.pasos), resultado.completa))

    documento = _acta.levantar(resultado, capacidades=capacidades, skills=skills)
    print(documento.a_texto())

    # --- 3. Un requisito que cambia ----------------------------------------
    _titulo("3. UN REQUISITO QUE CAMBIA NO BORRA EL ANTERIOR")
    memoria.declarar("programa.dormitorios", 3, registrado_por="cliente (reunión 01/08)")
    memoria.declarar("programa.dormitorios", 4, registrado_por="cliente (correo 12/08)")
    for conflicto in memoria.conflictos():
        print("  · «%s»: antes %s (%s), ahora %s (%s)" % (
            conflicto.clave,
            conflicto.anterior.afirmacion.valor, conflicto.anterior.registrado_por,
            conflicto.vigente.afirmacion.valor, conflicto.vigente.registrado_por,
        ))
    print("  Manda el más reciente para poder seguir trabajando, y el conflicto")
    print("  queda declarado. ArchMuse no elige en silencio entre dos cosas que")
    print("  ha dicho el cliente.")

    # --- 3b. El plan se puede VER antes de ejecutarse ----------------------
    _titulo("4. LO QUE ARCHMUSE VA A HACER, ANTES DE HACERLO")
    print("Una frase del arquitecto se traduce en un plan que se puede leer,")
    print("corregir o cancelar — con los efectos que habrá que autorizar. El")
    print("modelo va guionizado aquí para que esta demostración no cueste nada:")
    print("lo que se enseña no es que acierte, sino que su respuesta es un plan")
    print("tipado que el ejecutor acepta o rechaza con motivo, nunca prosa.")
    print()
    planificacion = _plani.planificar(
        "Rellena el cuadro de superficies de este plano",
        _ClienteDeGuion({"pasos": [{
            "id": "cuadro",
            "skill": "superficies.cuadro_de_vivienda",
            "argumentos": {"ruta_dxf": "plano.dxf", "ruta_destino": "plano_relleno.dxf"},
        }]}),
        memoria=memoria, capacidades=capacidades, skills=skills,
    )
    print(_plani.a_texto(planificacion, skills))

    _titulo("5. LO QUE ARCHMUSE NO SABE HACER, DICHO")
    vacio = _plani.planificar(
        "Calcula el forjado de la planta primera",
        _ClienteDeGuion({"pasos": [], "motivo": (
            "ArchMuse no calcula estructuras: ninguna Skill del catálogo lo cubre.")}),
        memoria=memoria, capacidades=capacidades, skills=skills,
    )
    print(_plani.a_texto(vacio, skills))
    print()
    print("Un plan aproximado con las Skills que sí hay sería peor que ninguno:")
    print("produce trabajo que nadie pidió y respuestas que parecen ciertas.")

    # --- 4. Reanudación ----------------------------------------------------
    _titulo("6. LA MISMA EJECUCIÓN, RELANZADA, NO REPITE LO HECHO")
    otra_vez = ejecutor.ejecutar(plan, memoria, ejecucion_id="demo-completa")
    print("Pasos reanudados sin volver a ejecutarse: %s" % list(otra_vez.reanudados))
    print("Es lo que permite matar el proceso a mitad de un trabajo de diez")
    print("minutos y no perder nada.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
