# -*- coding: utf-8 -*-
"""Repasa un plano antes de que salga del estudio.

    python scripts/revisar_plano.py mi_plano.dxf
    python scripts/revisar_plano.py mi_plano.dxf informe.pdf

Ejecuta la Skill `revision.coherencia_del_plano` (tarea `CO-5`) sobre un DXF y
entrega dos cosas:

1. **El informe en PDF**: qué no cuadra, dónde exactamente y cuánto mide, más
   qué se ha comprobado y qué no se ha podido comprobar y por qué.
2. **El acta de procedencia**: qué capacidades se han ejecutado y qué NO
   comprueban, derivado de sus manifiestos y no redactado a mano.

**Qué contesta y qué no.** Contesta si el plano es coherente **consigo mismo**:
si el dibujo y el cuadro de superficies hablan del mismo piso y si la geometría
está bien construida. **No comprueba normativa.** Un informe limpio significa
que el plano no se contradice, no que el proyecto esté bien.

**No gradúa la gravedad de nada.** Dice qué es y cuánto mide; el criterio lo
pone el arquitecto. Es una frontera de producto —el criterio profesional de
ArchMuse está sin firmar (`D-7`)— y está comprobada por una verificación
bloqueante de la Skill, no por buena voluntad.

**No usa la API de Anthropic.** No hace falta clave ni red: todo el
procedimiento es determinista.

**El plano original no se toca.** Se abre sólo para leer y su sha256 se verifica
antes y después. Lo único que se escribe es el informe.

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

SKILL = "revision.coherencia_del_plano"

#: Cómo se titula cada tipo de hallazgo en pantalla. Mismo criterio que el PDF:
#: el identificador interno sirve para programar, no para leer.
TITULOS = {
    "solape_entre_recintos": "Recintos que se solapan",
    "polilinea_mal_cerrada": "Contornos cerrados por suposición",
    "geometria_descartada": "Geometría que no ha entrado en el análisis",
    "etiqueta_duplicada": "Rótulos repetidos",
    "recinto_sin_etiqueta": "Piezas sin rotular",
    "el_cuadro_pide_una_pieza_que_no_esta_dibujada":
        "El cuadro pide piezas que no están dibujadas",
    "pieza_dibujada_que_el_cuadro_no_contempla":
        "Piezas dibujadas que el cuadro no contempla",
    "el_cuadro_y_el_plano_no_cuentan_lo_mismo": "El cuadro y el plano no cuentan lo mismo",
    "no_se_ha_leido_ningun_recinto": "No se ha leído ningún recinto",
}


def _salida_en_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):     # pragma: no cover
            pass


def _destino_por_defecto(origen: str) -> str:
    """`plano.dxf` -> `plano_ArchMuse_revision.pdf`, junto al original.

    Con un nombre que dice de dónde salió: dentro de un mes, en una carpeta con
    veinte ficheros, eso importa más que ser corto.
    """
    ruta = Path(origen)
    return str(ruta.with_name(ruta.stem + "_ArchMuse_revision.pdf"))


def _titulo(texto: str) -> None:
    print("\n" + "=" * 78)
    print(texto)
    print("=" * 78)


def _valor(salida: dict, nombre: str):
    """El valor de una afirmación de la salida del paso, que llega ya en `dict`.

    El ejecutor serializa cada `SalidaDeSkill` antes de guardarla en el
    resultado: lo que se recorre aquí son diccionarios, no objetos. Es la misma
    forma que queda en la bitácora, así que leer de aquí es leer exactamente lo
    que se ha registrado.
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
    print("  Plano:   %s" % origen)
    print("  Informe: %s" % destino)
    print("  Skill:   %s@%s" % (skill.id, skill.version))
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
    memoria = MemoriaDeProyecto("revision-%s" % Path(origen).stem, SustratoEnMemoria())
    plan = Plan(
        objetivo="Revisa la coherencia de %s" % Path(origen).name,
        proyecto_id=memoria.proyecto_id,
        pasos=(Paso(id="revisar", skill=SKILL, argumentos={
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

    # **Que el fichero exista NO significa que se haya entregado**, y confundir
    # las dos cosas era un defecto real de este guion: pidiendo el informe
    # encima del propio plano, la capacidad se negaba —bien, y el DXF no se
    # tocó— pero el destino existía (era el plano del arquitecto), así que esto
    # anunciaba «LO QUE TE LLEVAS: PDF tu_plano.dxf». La protección aguantó; lo
    # que falló fue lo que se le contaba al arquitecto, y en un entregable eso
    # es igual de grave. Lo que decide si hay entregable es que **la Skill lo
    # declare**, no que haya un fichero en esa ruta.
    salida = resultado.pasos[0].salida if resultado.pasos else None
    entregado = any(
        e.get("ruta") == os.path.abspath(destino)
        for e in (documento.a_dict().get("entregables") or ())
    )
    if salida is None or not entregado or not os.path.isfile(destino):
        _titulo("NO SE HA PODIDO REVISAR")
        for paso in resultado.pasos:
            if paso.motivo:
                print("  · %s" % paso.motivo)
        for pregunta in ((salida or {}).get("resultado") or {}).get("preguntas") or ():
            print("  Pregunta: %s" % pregunta)
        print("\nNo se ha escrito ningún informe. Nada de tu plano ha cambiado.")
        return 1

    hallazgos = _valor(salida, "revision.hallazgos") or []
    _titulo("LO QUE CONVIENE MIRAR (%d)" % len(hallazgos))
    if not hallazgos:
        print("  Nada. Ninguna de las comprobaciones del informe ha dado resultado.")
        print("  Eso quiere decir que el plano no se contradice a sí mismo en lo que")
        print("  ArchMuse sabe mirar; NO quiere decir que el proyecto esté correcto.")
    else:
        # Agrupados por tipo y en el orden en que se encontraron. Ordenar por
        # importancia exigiría decidir cuál importa más, que es justo lo que
        # esta herramienta no hace.
        por_tipo: dict = {}
        for h in hallazgos:
            por_tipo.setdefault(h.get("tipo", ""), []).append(h)
        for tipo, grupo in por_tipo.items():
            print("\n  %s (%d)" % (TITULOS.get(tipo, tipo), len(grupo)))
            for h in grupo:
                print("    · %s" % h.get("descripcion", ""))
                magnitud = h.get("magnitud")
                sufijo = ("  [%g %s]" % (magnitud, h.get("unidad") or "")).rstrip()
                print("      dónde: %s%s" % (h.get("entidad", ""),
                                             "" if magnitud is None else sufijo))

    _titulo("LO QUE TE LLEVAS")
    print("  PDF  %s" % destino)
    print("  El original conserva su sha256: no se ha tocado.")
    print("  El informe sale marcado como BORRADOR para revisión de un colegiado.")
    print("  No comprueba normativa: dice si el plano es coherente consigo mismo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
