# -*- coding: utf-8 -*-
"""Comprueba el corpus normativo. Para el colegiado que transcribe, no para el programador.

    python scripts/validar_corpus.py
    python scripts/validar_corpus.py --ambitos es,es.13

**Por qué existe.** La tarea `NOR-1` se da por terminada cuando un colegiado que
no ha hablado con Pablo transcribe una segunda regla siguiendo la ficha **sin
ayuda**. Sin este guion no puede: las validaciones existen —diecisiete por
fichero y dos sobre el manifiesto— pero sólo se invocaban desde los tests, así
que la única forma de saber si un YAML recién escrito está bien era preguntarle
a un programador. Eso convierte a Pablo en el cuello de botella de lo único que
no puede tenerlo, porque es el trabajo que hay que repetir cientos de veces.

**Lo que este guion NO hace, y hay que decirlo aquí porque es la mitad del
asunto.** Comprueba la *forma*: que el YAML case con el esquema, que los
catálogos existan, que el documento básico citado corresponda a la materia, que
las remisiones apunten a algo, que el manifiesto de cobertura y el disco digan
lo mismo. **No comprueba que la regla sea fiel a la norma.** Los tres criterios
humanos de la ficha §4 —que cada número esté en el literal citado, que la
localización permita ir a comprobarlo, y que el mensaje le sirva a un
arquitecto— no los puede ver una máquina, y este guion los enumera al final en
vez de callárselos. Un corpus que pasa esta comprobación entera puede seguir
siendo normativa mal transcrita.

No escribe nada. No toca el corpus, no toca el manifiesto, no descarga nada.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from normativa import validacion  # noqa: E402
from normativa.loader import cargar, descubrir  # noqa: E402
from normativa.manifiesto import ESTADOS, MANIFIESTO, _manifiesto  # noqa: E402

#: Los ámbitos que se recorren si no se indica otra cosa. `es` es el estatal, y
#: es el único con contenido hoy; los otros se añaden a mano cuando el curador
#: empiece con autonómico o municipal.
AMBITOS_POR_DEFECTO = ("es",)

TAG_SIN_FIRMAR = validacion.TAG_SIN_FIRMAR


def _salida_en_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):     # pragma: no cover
            pass


def _titulo(texto: str) -> None:
    print()
    print("=" * 78)
    print(texto)
    print("=" * 78)


def _reglas_por_ambito_y_materia(carga) -> Dict[Tuple[str, str], List[dict]]:
    fuera: Dict[Tuple[str, str], List[dict]] = {}
    for fichero in carga.ficheros:
        for regla in (fichero.doc.get("reglas") or []):
            fuera.setdefault((fichero.ambito, regla.get("materia")), []).append(regla)
    return fuera


def _revisar_ficheros(carga, ambitos: Sequence[str]) -> int:
    """Los rechazos de carga, con el fichero y el motivo tal cual los da el validador.

    Los mensajes no se reescriben: vienen numerados por validación (`[3]`,
    `[17]`...) y ese número es lo que permite ir a la ficha y leer qué exige esa
    comprobación concreta.
    """
    _titulo("1. CADA FICHERO, CONTRA LAS VALIDACIONES DE CARGA")
    rutas = descubrir(ambitos)
    if not rutas:
        print("  No hay ningún fichero de corpus. No es un error: es un corpus vacío.")
        return 0

    for ruta in rutas:
        rechazo = carga.rechazados.get(str(ruta))
        relativa = _relativa(ruta)
        if rechazo:
            print("  [RECHAZADO] %s" % relativa)
            for fallo in rechazo:
                print("      %s" % fallo)
        else:
            n = sum(len(f.doc.get("reglas") or []) for f in carga.ficheros
                    if f.ruta == ruta)
            print("  [OK]        %s — %d regla(s)" % (relativa, n))
    return sum(len(v) for v in carga.rechazados.values())


def _relativa(ruta: Path) -> str:
    try:
        return ruta.relative_to(RAIZ).as_posix()
    except ValueError:
        return str(ruta)


def _revisar_manifiesto(carga) -> int:
    """Las dos validaciones que miran el corpus entero, no fichero a fichero."""
    _titulo("2. EL MANIFIESTO DE COBERTURA, CONTRA LO QUE HAY EN DISCO")
    try:
        manifiesto = _manifiesto()
    except Exception as exc:                      # noqa: BLE001
        print("  No se puede leer %s: %s" % (_relativa(MANIFIESTO), exc))
        return 1

    fallos = validacion.validar_cobertura(manifiesto, carga.materias_por_ambito)
    fallos += validacion.validar_firma_de_lo_declarado(
        manifiesto, _reglas_por_ambito_y_materia(carga))

    estados_malos = []
    for entrada in manifiesto.get("cobertura") or []:
        for materia, estado in (entrada.get("materias") or {}).items():
            e = estado.get("estado") if isinstance(estado, dict) else estado
            if e not in ESTADOS:
                estados_malos.append(
                    "«%s» no es un estado de cobertura válido (%s: %s). Los válidos "
                    "son: %s" % (e, entrada["ambito"], materia, ", ".join(ESTADOS)))
    fallos += estados_malos

    if fallos:
        for fallo in fallos:
            print("  [FALLA] %s" % fallo)
    else:
        print("  [OK] Lo declarado y lo que hay en disco coinciden, y nada se")
        print("       declara afirmable con reglas sin firmar.")
    return len(fallos)


def _revisar_firmas(carga) -> None:
    """Qué hay transcrito y qué de ello puede usarse.

    No es un fallo tener reglas sin firmar: es el estado normal entre que se
    transcriben y que un colegiado las revisa. Lo que sí sería un fallo es que
    ArchMuse afirmara sobre ellas, y de eso se ocupa la validación 18.
    """
    _titulo("3. QUÉ ESTÁ FIRMADO Y QUÉ NO")
    reglas = carga.reglas
    if not reglas:
        print("  No hay ninguna regla transcrita.")
        return

    sin_firmar = [r for r in reglas if TAG_SIN_FIRMAR in (r.get("tags") or [])]
    firmadas = [r for r in reglas if r not in sin_firmar]

    print("  Transcritas: %d · firmadas por un colegiado: %d · pendientes: %d"
          % (len(reglas), len(firmadas), len(sin_firmar)))
    for regla in sin_firmar:
        print("      pendiente de firma: %s" % regla.get("concept_id", "?"))
    if sin_firmar and not firmadas:
        print()
        print("  Ninguna regla del corpus está firmada todavía, así que ArchMuse no")
        print("  afirma nada sobre normativa: sigue bloqueando por falta de cobertura.")
        print("  Eso es correcto y es lo que tiene que pasar hasta la primera firma.")


def _lo_que_no_comprueba_una_maquina() -> None:
    """Los tres criterios humanos de la ficha §4, dichos y no escondidos."""
    _titulo("4. LO QUE ESTA COMPROBACIÓN NO PUEDE VER")
    print("  Todo lo anterior es forma. Que una regla sea FIEL A LA NORMA lo decide")
    print("  una persona leyendo el boletín, y son los tres criterios humanos de la")
    print("  ficha (§4, criterios 5 a 7):")
    print()
    print("    5. Fidelidad al literal — cada número de la regla aparece en el texto")
    print("       citado en `literal`. Un número que no esté ahí se rechaza sin")
    print("       discusión.")
    print("    6. Localización exacta — `articulo` lleva a un tercero al sitio donde")
    print("       comprobarlo en un minuto.")
    print("    7. El mensaje sirve — `mensaje` le dice a un arquitecto qué hacer, no")
    print("       le repite el artículo.")
    print()
    print("  Un corpus que pasa esta comprobación entera puede seguir siendo")
    print("  normativa mal transcrita. Por eso la firma no la da este guion.")


def _ambitos_pedidos(argv: Sequence[str]) -> Tuple[str, ...]:
    for i, arg in enumerate(argv):
        if arg == "--ambitos" and i + 1 < len(argv):
            crudo = argv[i + 1]
        elif arg.startswith("--ambitos="):
            crudo = arg.split("=", 1)[1]
        else:
            continue
        pedidos = tuple(a.strip() for a in crudo.split(",") if a.strip())
        if pedidos:
            return pedidos
    return AMBITOS_POR_DEFECTO


def main(argv: List[str]) -> int:
    _salida_en_utf8()
    ambitos = _ambitos_pedidos(list(argv))

    print("Comprobación del corpus normativo de ArchMuse")
    print("Ámbitos: %s" % ", ".join(ambitos))

    carga = cargar(ambitos)
    fallos = _revisar_ficheros(carga, ambitos)
    fallos += _revisar_manifiesto(carga)
    _revisar_firmas(carga)
    _lo_que_no_comprueba_una_maquina()

    _titulo("RESULTADO")
    if fallos:
        print("  %d problema(s) de forma. El corpus NO se carga entero." % fallos)
        print("  Arréglalos y vuelve a ejecutar esto; ninguno necesita a un programador.")
        return 1
    print("  Sin problemas de forma.")
    print("  Eso NO quiere decir que la normativa esté bien transcrita: ver el punto 4.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
