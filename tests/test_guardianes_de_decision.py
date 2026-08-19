# -*- coding: utf-8 -*-
"""Hay asserts que NO se arreglan cambiando el assert.

Ejecutar:  pytest tests/test_guardianes_de_decision.py
Congelar:  python tests/test_guardianes_de_decision.py --congelar   (y decir por qué)

**El fallo real que esto cierra, contado tal cual pasó.** El 2026-08-19 la suite
estaba roja por cinco sitios. Cuatro eran inventarios que iban por detrás del
registro —el conjunto de ids esperados, los casos de invocación, el golden y los
contratos congelados— y la forma correcta de arreglarlos es exactamente esa:
actualizarlos para que describan lo que hay. El quinto era
`assert len(reg) <= 12`, y **se arregló igual que los otros cuatro: subiendo el
número a 14**. Hubo que revertirlo el mismo día.

El error no fue de descuido, fue de categoría. Los cinco fallos se parecían en
pantalla y son dos cosas distintas:

- **Un test descriptivo** dice *lo que el código es*. Si el código cambia a
  propósito, el test se actualiza. Los cuatro inventarios son de estos.
- **Un test prescriptivo** dice *lo que alguien decidió que el código no haga*.
  El número que lleva dentro no es una descripción desactualizada: es la
  decisión. Actualizarlo para que pase **es derogar la decisión**, y quien no la
  tomó no puede derogarla.

Cuatro aciertos seguidos de «actualiza el inventario» hicieron que el quinto
pareciera el mismo movimiento. Nada en el código decía que no lo era.

**Lo que hace este test.** Los asserts prescriptivos se marcan con un comentario
`# GUARDIAN DE DECISION: <nombre>` en la línea de encima, y su texto exacto vive
congelado aquí al lado con el nombre de quién decide y dónde está escrita la
decisión. Cambiar uno deja de ser una edición de un carácter en un fichero y pasa
a ser un cambio en dos ficheros que nombra a un responsable.

**Lo que NO hace, dicho por delante:** no impide nada. `--congelar` existe y
cualquiera puede ejecutarlo. Lo que consigue es que el atajo deje de ser
invisible: aparece en el diff, con el nombre de quien decide al lado. Un guardián
que se puede saltar y se nota es mejor que uno que se salta sin que nadie lo vea,
y es todo lo que un test puede hacer aquí.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

RAIZ = Path(__file__).resolve().parent.parent
CONGELADO = RAIZ / "tests" / "fixtures" / "guardianes_de_decision.json"
MARCA = "# GUARDIAN DE DECISION:"


def _guardianes_del_fuente() -> Dict[str, List[str]]:
    """Nombre del guardián -> las líneas que protege, tal cual están hoy."""
    encontrados: Dict[str, List[str]] = {}
    for fichero in sorted((RAIZ / "tests").glob("test_*.py")):
        if fichero.name == Path(__file__).name:
            continue
        lineas = fichero.read_text(encoding="utf-8").splitlines()
        for i, linea in enumerate(lineas):
            if MARCA not in linea:
                continue
            nombre = linea.split(MARCA, 1)[1].strip()
            # La línea protegida es la siguiente que no es comentario ni blanco.
            for siguiente in lineas[i + 1:]:
                limpia = siguiente.strip()
                if limpia and not limpia.startswith("#"):
                    encontrados.setdefault(nombre, []).append(
                        "%s :: %s" % (fichero.name, " ".join(limpia.split())))
                    break
            else:  # pragma: no cover - una marca al final del fichero
                raise AssertionError(
                    "la marca de %s en %s no protege ninguna línea" % (nombre, fichero.name))
    return {k: sorted(v) for k, v in encontrados.items()}


def _congelado() -> dict:
    if not CONGELADO.exists():
        return {}
    datos = json.loads(CONGELADO.read_text(encoding="utf-8"))
    return {k: v for k, v in datos.items() if not k.startswith("_")}


def test_ninguna_decision_cambia_sin_nombrar_a_quien_la_toma():
    esperado = _congelado()
    actual = _guardianes_del_fuente()

    for nombre in sorted(set(esperado) | set(actual)):
        ficha = esperado.get(nombre, {})
        lineas_esperadas = ficha.get("lineas", [])
        lineas_actuales = actual.get(nombre, [])
        assert lineas_actuales == lineas_esperadas, (
            "el guardián «%s» ha cambiado.\n\n"
            "  esperado: %s\n"
            "  ahora:    %s\n\n"
            "Esa línea no es un inventario desactualizado: es una decisión de %s, "
            "escrita en %s. Si el test está en rojo, la respuesta no es cambiar el "
            "número — es o cambiar el código para que quepa, o pedirle la decisión "
            "a %s. Si de verdad la ha tomado, congela con "
            "`python tests/test_guardianes_de_decision.py --congelar` y di en el "
            "mismo cambio quién y cuándo."
            % (nombre, lineas_esperadas or "(ninguna)", lineas_actuales or "(ninguna)",
               ficha.get("decide", "?"), ficha.get("documento", "?"),
               ficha.get("decide", "quien decida")))


def test_todo_guardian_congelado_sigue_existiendo_en_el_fuente():
    """El reverso: borrar la marca sería la forma silenciosa de desactivarlo."""
    actual = _guardianes_del_fuente()
    huerfanos = sorted(set(_congelado()) - set(actual))
    assert not huerfanos, (
        "estos guardianes están congelados y ya no aparecen en ningún test: %s. "
        "Quitar la marca desactiva la protección sin tocar el assert." % huerfanos)


def test_cada_guardian_dice_quien_decide_y_donde_esta_escrito():
    for nombre, ficha in sorted(_congelado().items()):
        assert ficha.get("decide"), "%s no dice quién decide" % nombre
        documento = ficha.get("documento", "")
        assert documento, "%s no dice dónde está escrita la decisión" % nombre
        assert (RAIZ / documento).exists(), (
            "%s apunta a %s, que no existe" % (nombre, documento))


def _congelar() -> None:  # pragma: no cover - herramienta de línea de órdenes
    datos = json.loads(CONGELADO.read_text(encoding="utf-8")) if CONGELADO.exists() else {}
    nota = datos.get("_nota", "")
    nuevo = {"_nota": nota}
    for nombre, lineas in _guardianes_del_fuente().items():
        ficha = dict(datos.get(nombre, {}))
        ficha["lineas"] = lineas
        ficha.setdefault("decide", "?")
        ficha.setdefault("documento", "?")
        nuevo[nombre] = ficha
    CONGELADO.write_text(json.dumps(nuevo, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                         encoding="utf-8")
    print("Congelados %d guardianes en %s." % (len(nuevo) - 1, CONGELADO.name))


if __name__ == "__main__":  # pragma: no cover
    if "--congelar" in sys.argv:
        _congelar()
    else:
        import pytest
        sys.exit(pytest.main([__file__, "-q"]))
