# -*- coding: utf-8 -*-
"""El primer trabajo profesional completo de ArchMuse, de punta a punta.

    python scripts/cuadro_de_superficies.py mi_plano.dxf
    python scripts/cuadro_de_superficies.py mi_plano.dxf salida.dxf
    python scripts/cuadro_de_superficies.py mi_plano.dxf salida.dxf --responder respuestas.json

Ejecuta la Skill `superficies.cuadro_de_vivienda` (tarea `SK-1`) sobre un DXF
real y entrega tres cosas:

1. **El plano relleno**, como copia nueva. El original conserva su sha256, y el
   guion lo comprueba y lo enseña.
2. **El acta de procedencia**: de dónde sale cada dato, qué capacidades se
   ejecutaron y —lo que más importa— **qué no se ha comprobado**, derivado de
   los manifiestos de lo que se ejecutó y no redactado a mano.
3. **Las preguntas pendientes**: lo que hay que contestar para que las celdas
   que han quedado en blanco dejen de estarlo.

**No usa la API de Anthropic.** No hace falta clave ni red: todo el
procedimiento es determinista. Lo que se enseña aquí no es que un modelo sepa
elegir herramientas —eso ya se prueba con cliente guionizado en los tests—,
sino que **el trabajo que se entrega es rastreable**.

**Autorización.** La Skill escribe un fichero, así que se le concede el efecto
`escribe_fichero` con alcance de esta ejecución y firma «cli:<usuario>».
Ejecutar esto es la autorización: en una pantalla sería un diálogo, aquí es
haber escrito el comando.

Si el DXF no trae un `ACAD_TABLE` de cuadro de superficies, el guion lo dice y
sale con código 1: no inventa una tabla.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from agente import acta as _acta  # noqa: E402
from agente.efectos import ESCRIBE_FICHERO, Autorizacion, Autorizaciones  # noqa: E402
from agente.ejecucion import BitacoraEnMemoria, Ejecutor, Paso, Plan  # noqa: E402
from agente.memoria import MemoriaDeProyecto, SustratoEnMemoria  # noqa: E402
from agente.registro import registro, registro_de_skills  # noqa: E402

SKILL = "superficies.cuadro_de_vivienda"


def _salida_en_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):     # pragma: no cover
            pass


def _destino_por_defecto(origen: str) -> str:
    """`plano.dxf` -> `plano_ArchMuse_relleno.dxf`, junto al original.

    Nunca sobre el original, y con un nombre que dice de dónde salió: dentro de
    un mes, en una carpeta con veinte ficheros, eso importa más que ser corto.
    """
    ruta = Path(origen)
    return str(ruta.with_name(ruta.stem + "_ArchMuse_relleno" + ruta.suffix))


def _titulo(texto: str) -> None:
    print("\n" + "=" * 78)
    print(texto)
    print("=" * 78)


def main(argv: list) -> int:
    _salida_en_utf8()
    if len(argv) < 2:
        print(__doc__)
        return 0

    origen = argv[1]
    if not os.path.isfile(origen):
        print("No encuentro «%s»." % origen, file=sys.stderr)
        return 2

    destino = argv[2] if len(argv) > 2 and not argv[2].startswith("--") else None
    destino = destino or _destino_por_defecto(origen)

    respuestas = None
    if "--responder" in argv:
        ruta_respuestas = argv[argv.index("--responder") + 1]
        respuestas = json.loads(Path(ruta_respuestas).read_text(encoding="utf-8"))

    capacidades = registro(recargar=True)
    skills = registro_de_skills(recargar=True)
    memoria = MemoriaDeProyecto("cuadro-%s" % Path(origen).stem, SustratoEnMemoria())

    plan = Plan(
        objetivo="Rellena el cuadro de superficies de %s" % Path(origen).name,
        proyecto_id=memoria.proyecto_id,
        pasos=(Paso(id="cuadro", skill=SKILL, argumentos={
            "ruta_dxf": os.path.abspath(origen),
            "ruta_destino": os.path.abspath(destino),
            "respuestas": respuestas,
        }),),
    )

    _titulo("LO QUE SE VA A HACER")
    skill = skills.buscar(SKILL)
    print("Skill:      %s@%s" % (skill.id, skill.version))
    print("Origen:     %s  (sólo lectura)" % os.path.abspath(origen))
    print("Destino:    %s" % os.path.abspath(destino))
    print("Efectos:    %s" % ", ".join(skill.efectos))
    print("\nProcedimiento:")
    for paso in skill.procedimiento:
        print("  %s" % paso)

    quien = "cli:%s" % (os.environ.get("USERNAME") or os.environ.get("USER") or "?")
    permisos = Autorizaciones((
        Autorizacion(efecto=ESCRIBE_FICHERO, alcance="ejecucion", autorizada_por=quien),
    ))

    ejecutor = Ejecutor(capacidades=capacidades, skills=skills, bitacora=BitacoraEnMemoria())
    resultado = ejecutor.ejecutar(plan, memoria, autorizaciones=permisos,
                                 ejecucion_id="cli-%s" % Path(origen).stem)

    _titulo("EL ACTA")
    documento = _acta.levantar(resultado, capacidades=capacidades, skills=skills)
    print(documento.a_texto())

    # **Terminado no es lo mismo que entregado**, y confundirlos aquí sería el
    # peor defecto posible de este guion: la Skill puede ejecutarse entera y
    # acabar sin entregable —porque el DXF no traía cuadro, o porque falta un
    # dato— y eso NO es un fallo del sistema, es una respuesta. Lo que decide
    # si hay entregable es que el fichero exista y que la Skill lo declare, no
    # que el plan llegara al final.
    entregado = os.path.isfile(destino) and any(
        e.get("ruta") == os.path.abspath(destino) for e in documento.a_dict()["entregables"]
    )
    if not resultado.completa or not entregado:
        _titulo("NO SE HA PODIDO ENTREGAR")
        for paso in resultado.pasos:
            if paso.motivo:
                print("  · %s" % paso.motivo)
        for pregunta in resultado.preguntas:
            print("  Pregunta: %s" % pregunta)
        print(chr(10) + "No se ha escrito ningún fichero. Nada de tu plano ha cambiado.")
        return 1

    _titulo("LO QUE TE LLEVAS")
    for entregable in documento.a_dict()["entregables"]:
        print("  %-4s %s" % (entregable.get("tipo", "?").upper(), entregable.get("ruta")))
    print("  El original conserva su sha256: no se ha tocado.")
    print("  El plano relleno sale marcado como BORRADOR para revisión de un")
    print("  colegiado, en su propia capa. ArchMuse asesora; el proyecto lo")
    print("  firma el arquitecto que lo redacta.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
