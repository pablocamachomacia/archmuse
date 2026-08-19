# -*- coding: utf-8 -*-
"""Mide las superficies útiles de una planta, vivienda por vivienda.

    python scripts/medir_planta.py mi_planta.dxf
    python scripts/medir_planta.py mi_planta.dxf medicion.pdf

Ejecuta la Skill `superficies.medicion_de_planta` sobre un DXF y entrega dos
cosas:

1. **La medición en PDF**: una tabla por vivienda con cada pieza, su superficie
   y **de dónde sale** —qué recinto, con qué rótulo y en qué capa del DXF—, más
   los subtotales interior y exterior y el total de cada vivienda cuando se
   puede afirmar.
2. **El acta de procedencia**: qué capacidades se han ejecutado y qué **no**
   comprueban, derivado de sus manifiestos y no redactado a mano.

**Para qué sirve y cuándo usar la otra.** Ésta mide **lo que hay dibujado**: no
necesita que el plano traiga ningún cuadro de superficies y no se rinde ante una
planta con varias viviendas, que es el caso normal de un edificio residencial.
Si el plano SÍ trae su `ACAD_TABLE` de cuadro y lo que quieres es rellenarlo
dentro del propio DXF, la buena es `scripts/cuadro_de_superficies.py`.

**Una vivienda que no cuadra no lleva total.** Si hay piezas solapadas, si el
reparto de una pieza entre dos viviendas no es firme, o si hay una pieza cuyo
rótulo no dice si es superficie interior o exterior, esa vivienda sale **sin
total y con el motivo escrito**, con su magnitud. Las piezas se miden igual. Un
total que puede estar mal se copia a la memoria del proyecto; la ausencia de
total se pregunta.

**No emite criterio.** Dice qué piezas hay y cuánto miden. No dice si una
vivienda es pequeña ni si un solape es un error del plano o una convención de su
autor: eso es criterio de un colegiado.

**No usa la API de Anthropic.** No hace falta clave ni red: todo el
procedimiento es determinista.

**El plano original no se toca.** Se abre sólo para leer y su sha256 se verifica
antes y después. Lo único que se escribe es el PDF.

**Autorización.** La Skill escribe un fichero, así que se le concede el efecto
`escribe_fichero` con alcance de esta ejecución. Ejecutar esto es la
autorización: en una pantalla sería un diálogo, aquí es haber escrito el
comando.
"""
from __future__ import annotations

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

SKILL = "superficies.medicion_de_planta"


def _salida_en_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):     # pragma: no cover
            pass


def _destino_por_defecto(origen: str) -> str:
    """`planta.dxf` -> `planta_ArchMuse_medicion.pdf`, junto al original.

    Con un nombre que dice de dónde salió: dentro de un mes, en una carpeta con
    veinte ficheros, eso importa más que ser corto.
    """
    ruta = Path(origen)
    return str(ruta.with_name(ruta.stem + "_ArchMuse_medicion.pdf"))


def _titulo(texto: str) -> None:
    print("\n" + "=" * 78)
    print(texto)
    print("=" * 78)


def _m2(valor) -> str:
    if valor is None:
        return "—"
    return ("%.2f m²" % float(valor)).replace(".", ",")


def _valor(salida: dict, nombre: str):
    """El valor de una afirmación de la salida del paso, ya serializada.

    El ejecutor convierte cada `SalidaDeSkill` a `dict` antes de guardarla, así
    que lo que se recorre aquí son diccionarios. Es la misma forma que queda en
    la bitácora: leer de aquí es leer exactamente lo que se ha registrado.
    """
    for a in ((salida or {}).get("resultado") or {}).get("afirmaciones") or ():
        if a.get("nombre") == nombre:
            return a.get("valor")
    return None


def main(argv: list) -> int:
    _salida_en_utf8()
    if len(argv) < 2:
        print(__doc__)
        return 0

    origen = argv[1]
    destino = argv[2] if len(argv) > 2 else _destino_por_defecto(origen)

    skill = registro_de_skills(recargar=True).buscar(SKILL)

    _titulo("QUÉ VOY A HACER")
    print("  Plano:    %s" % origen)
    print("  Medición: %s" % destino)
    print("  Skill:    %s@%s" % (skill.id, skill.version))
    print()
    for paso in skill.procedimiento:
        print("  %s" % paso)
    print("\n  El plano original NO se modifica: se abre sólo para leer y su sha256")
    print("  se comprueba antes y después.")

    quien = "cli:%s" % (os.environ.get("USERNAME") or os.environ.get("USER") or "?")
    permisos = Autorizaciones((
        Autorizacion(efecto=ESCRIBE_FICHERO, alcance="ejecucion", autorizada_por=quien),
    ))

    capacidades = registro(recargar=True)
    skills = registro_de_skills(recargar=True)
    memoria = MemoriaDeProyecto("medicion-%s" % Path(origen).stem, SustratoEnMemoria())
    plan = Plan(
        objetivo="Mide las superficies útiles de %s" % Path(origen).name,
        proyecto_id=memoria.proyecto_id,
        pasos=(Paso(id="medir", skill=SKILL, argumentos={
            "ruta_dxf": os.path.abspath(origen),
            "ruta_informe": os.path.abspath(destino),
        }),),
    )
    ejecutor = Ejecutor(capacidades=capacidades, skills=skills, bitacora=BitacoraEnMemoria())
    resultado = ejecutor.ejecutar(plan, memoria, autorizaciones=permisos,
                                 ejecucion_id="cli-%s" % Path(origen).stem)

    _titulo("EL ACTA")
    documento = _acta.levantar(resultado, capacidades=capacidades, skills=skills)
    print(documento.a_texto())

    # Que el fichero exista NO significa que se haya entregado: lo que decide si
    # hay entregable es que **la Skill lo declare**. Es el mismo criterio que
    # `scripts/revisar_plano.py`, y por el mismo motivo — pidiendo la medición
    # encima del propio plano, la capacidad se niega (bien, y el DXF no se toca)
    # pero el destino existe, porque es el plano del arquitecto.
    salida = resultado.pasos[0].salida if resultado.pasos else None
    entregado = any(
        e.get("ruta") == os.path.abspath(destino)
        for e in (documento.a_dict().get("entregables") or ())
    )
    if salida is None or not entregado or not os.path.isfile(destino):
        _titulo("NO SE HA PODIDO MEDIR")
        for paso in resultado.pasos:
            if paso.motivo:
                print("  · %s" % paso.motivo)
        for pregunta in ((salida or {}).get("resultado") or {}).get("preguntas") or ():
            print("  Pregunta: %s" % pregunta)
        print("\nNo se ha escrito ninguna medición. Nada de tu plano ha cambiado.")
        return 1

    viviendas = _valor(salida, "medicion.viviendas") or []
    _titulo("LO QUE MIDE ESTA PLANTA (%d vivienda(s))" % len(viviendas))
    for vivienda in viviendas:
        print("\n  %s" % vivienda.get("vivienda"))
        for pieza in vivienda.get("piezas") or ():
            print("    %-24s %10s   %s"
                  % (pieza.get("rotulo"), _m2(pieza.get("area_m2")),
                     pieza.get("ambito")))
        print("    %-24s %10s" % ("útil interior", _m2(vivienda.get("interior_m2"))))
        print("    %-24s %10s" % ("útil exterior", _m2(vivienda.get("exterior_m2"))))
        total = vivienda.get("total_util_m2")
        if total is None:
            print("    %-24s %10s" % ("TOTAL S. ÚTIL", "sin total"))
            for motivo in vivienda.get("impedimentos") or ():
                print("      · %s" % motivo)
        else:
            print("    %-24s %10s" % ("TOTAL S. ÚTIL", _m2(total)))

    _titulo("LO QUE TE LLEVAS")
    print("  PDF  %s" % destino)
    print("  El original conserva su sha256: no se ha tocado.")
    print("  La medición sale marcada como BORRADOR para revisión de un")
    print("  colegiado. ArchMuse mide; el proyecto lo firma el arquitecto que")
    print("  lo redacta.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
