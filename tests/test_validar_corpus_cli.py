# -*- coding: utf-8 -*-
"""El guion que el curador ejecuta solo (`scripts/validar_corpus.py`, `NOR-1`).

Ejecutar:  pytest tests/test_validar_corpus_cli.py

`NOR-1` se cierra cuando un colegiado transcribe una regla **sin ayuda**. Eso
exige que pueda comprobar su trabajo él mismo: hasta ahora las validaciones
existían pero sólo se invocaban desde los tests, así que la única forma de saber
si un YAML recién escrito estaba bien era preguntarle a un programador.

Lo que se fija aquí es lo que hace útil a un guion así, que no es que funcione
cuando todo va bien:

1. **Sale con código 1 cuando algo está mal**, para que se pueda encadenar.
2. **Dice qué fichero y qué regla**, no «el corpus es inválido».
3. **Declara lo que NO puede comprobar.** Un guion que sólo enseña lo que
   verifica enseña a confiar en él de más, y los tres criterios que deciden si
   una regla es fiel a la norma no los ve una máquina.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

GUION = RAIZ / "scripts" / "validar_corpus.py"


def _ejecutar():
    proceso = subprocess.run(
        [sys.executable, str(GUION)], capture_output=True, cwd=str(RAIZ))
    return proceso.returncode, proceso.stdout.decode("utf-8", errors="replace")


def test_sobre_el_corpus_actual_pasa():
    codigo, salida = _ejecutar()
    assert codigo == 0, salida
    assert "Sin problemas de forma" in salida


def test_dice_que_regla_falta_por_firmar_y_no_solo_cuantas():
    """«1 pendiente» obliga a buscarla; el `concept_id` lleva directo a ella."""
    _, salida = _ejecutar()
    assert "es.rd_314_2006.seguridad_incendio.longitud_recorrido_evacuacion" in salida
    assert "pendiente de firma" in salida


def test_declara_los_tres_criterios_que_no_puede_comprobar():
    """Lo que más importa de este guion: que no invite a confiar de más."""
    _, salida = _ejecutar()
    assert "LO QUE ESTA COMPROBACIÓN NO PUEDE VER" in salida
    assert "Fidelidad al literal" in salida
    assert "Localización exacta" in salida
    assert "El mensaje sirve" in salida
    assert "puede seguir siendo" in salida and "mal transcrita" in salida


def test_dice_que_hoy_archmuse_no_afirma_nada_sobre_normativa():
    """El estado real del producto, dicho donde se ve, no enterrado en un YAML."""
    _, salida = _ejecutar()
    assert "no" in salida and "afirma nada sobre normativa" in salida


def test_una_regla_rota_hace_fallar_el_guion_y_se_dice_donde(tmp_path, monkeypatch):
    """La prueba que vale: el caso en el que el guion tiene que ser incómodo.

    Se toca una copia del corpus, nunca el corpus real: este test no puede
    dejar el repositorio en otro estado del que lo encontró.
    """
    import shutil

    origen = RAIZ / "normativa" / "es" / "estatal" / "seguridad_incendio.yaml"
    respaldo = tmp_path / "respaldo.yaml"
    shutil.copy2(origen, respaldo)
    try:
        texto = origen.read_text(encoding="utf-8")
        # El error típico de quien empieza: una materia que no está en el catálogo.
        origen.write_text(
            texto.replace("    materia: seguridad_incendio",
                          "    materia: seguridad_contra_el_fuego", 1),
            encoding="utf-8", newline="\n")
        codigo, salida = _ejecutar()
        assert codigo == 1, salida
        assert "seguridad_incendio.yaml" in salida
        assert "seguridad_contra_el_fuego" in salida
        assert "catálogo" in salida
    finally:
        shutil.copy2(respaldo, origen)

    # Y el corpus queda como estaba: si esto fallara, el test habría roto el
    # repositorio para todos los siguientes.
    codigo, _ = _ejecutar()
    assert codigo == 0
