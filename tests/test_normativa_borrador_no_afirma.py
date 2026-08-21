"""Test de política del Prompt 1
(docs/prd/2026-08-21-pipeline-borradores-corpus-db-sua.md): ninguna regla en
`estado: BORRADOR` puede llegar a una afirmación de cumplimiento.

Dos guardarraíles independientes, cada uno probado por separado:

1. `normativa/loader.py::descubrir()` ignora los ficheros `_borrador_*.yaml`
   por su nombre — nunca entran en la carga.
2. `normativa/resolucion.py::_paso1_candidatas` descarta explícitamente toda
   regla con `estado: BORRADOR`, incluso si (por error) viviera en un
   fichero SIN el prefijo `_` — no depende de la convención de nombre para
   ser cierto. Este test coloca una deliberadamente en un fichero
   descubrible para demostrar que el descarte no depende del guardarraíl 1.
"""
from __future__ import annotations

import shutil
import sys
from datetime import date
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from normativa import loader  # noqa: E402
from normativa.api import contexto_territorial, normativa_aplicable  # noqa: E402
from normativa.resolucion import _paso1_candidatas  # noqa: E402

FIXTURE = RAIZ / "tests" / "fixtures" / "corpus_ficticio"

REGLA_BORRADOR = {
    "concept_id": "es.ficticio_dbsi.seguridad_incendio.regla_borrador_de_prueba",
    "instance_id": "es.ficticio_dbsi.seguridad_incendio.regla_borrador_de_prueba@1",
    "nombre": "Regla BORRADOR de prueba — nunca debe afirmarse",
    "materia": "seguridad_incendio",
    "tipo": "exigencia_cuantitativa",
    "patron": "UMBRAL_SIMPLE",
    "prioridad": "bloqueante",
    "nivel_de_conocimiento": 2,
    "estado": "BORRADOR",
    # `usos` deliberadamente distinto de cualquier regla real del fixture:
    # sin esto, validar_sin_contradiccion (14) rechaza el corpus ENTERO por
    # competir con es.ficticio_dbsi.seguridad_incendio.recorrido_evacuacion
    # en la misma materia/ámbito/perfil — un rechazo real y correcto, pero
    # que taparía el guardarraíl que este test quiere aislar.
    "aplicabilidad": {"ambito": "es", "usos": ["docente"]},
    "parametro": {"ejes": [], "unidad": "m", "repliegue": ["todos"], "valores": [{"valor": 999}]},
    "mensaje": "Si esto aparece como aplicable en un informe, el guardarraíl BORRADOR ha fallado.",
    "vigencia": {"vigencia_desde": "2006-03-28"},
}

DOC_CON_BORRADOR = {
    "version": 1,
    "norma": {
        "concept_id": "es.ficticio_dbsi.norma",
        "instance_id": "es.ficticio_dbsi.norma@1",
        "ambito": "es",
        "literal": "Texto ficticio de prueba.",
        "fuente": {
            "rango": "Real Decreto",
            "organismo": "Ministerio ficticio de pruebas",
            "identificador_oficial": "FICTICIO-000/2006",
            "titulo": "Documento Básico ficticio de seguridad en caso de incendio",
            "boletin": "FICTICIO-A-2006-0001",
        },
        "articulo": {"documento_basico": "DB-SI", "seccion": "SI-3", "apartado": "9"},
        "vigencia": {"vigencia_desde": "2006-03-28"},
    },
    "reglas": [REGLA_BORRADOR],
}


def test_paso1_candidatas_descarta_toda_regla_borrador():
    """Unidad: el guardarraíl del motor, sin pasar por territorio ni fechas."""
    fichero = loader.FicheroCorpus(
        ruta=Path("ficticio.yaml"), ambito="es", doc=DOC_CON_BORRADOR, materias={"seguridad_incendio"},
    )
    carga = loader.ResultadoCarga(raiz=RAIZ)
    carga.ficheros.append(fichero)

    avisos: list = []
    candidatas = _paso1_candidatas(carga, ids_en_cadena={"es"}, avisos=avisos)

    assert len(candidatas) == 1
    c = candidatas[0]
    assert c.id == REGLA_BORRADOR["concept_id"]
    assert c.estado == "no_aplica"
    assert "BORRADOR" in c.motivo


def test_paso1_candidatas_deja_pasar_verificada_automatica():
    """El reverso del test anterior: una regla VERIFICADA_AUTOMATICA sí
    llega a ser candidata evaluable — si el guardarraíl del Prompt 2 se
    escribiera al revés (bloqueando todo lo que no sea `None`), este test
    lo detectaría."""
    regla_verificada = dict(REGLA_BORRADOR)
    regla_verificada["estado"] = "VERIFICADA_AUTOMATICA"
    regla_verificada["concept_id"] += "_verificada"

    doc = dict(DOC_CON_BORRADOR)
    doc["reglas"] = [regla_verificada]
    fichero = loader.FicheroCorpus(
        ruta=Path("ficticio.yaml"), ambito="es", doc=doc, materias={"seguridad_incendio"},
    )
    carga = loader.ResultadoCarga(raiz=RAIZ)
    carga.ficheros.append(fichero)

    candidatas = _paso1_candidatas(carga, ids_en_cadena={"es"}, avisos=[])
    assert len(candidatas) == 1
    assert candidatas[0].estado != "no_aplica"


def test_grep_del_motor_el_guardarrail_esta_en_el_codigo():
    """Prompt 1 pide explícitamente «grep del motor + test». La cadena tiene
    que estar en el código, no solo probada por comportamiento — así una
    refactorización que la borre por accidente rompe este test aunque el
    comportamiento coincidiera por casualidad.

    El Prompt 2 (verificación doble) amplió el guardarraíl de "descarta
    BORRADOR" a "descarta lo que no sea VERIFICADA_AUTOMATICA/FIRMADA" —
    la cadena exacta cambió, pero el contrato (greppable, en el código, no
    solo en el comportamiento) sigue siendo el mismo."""
    texto = (RAIZ / "normativa" / "resolucion.py").read_text(encoding="utf-8")
    assert 'estado_regla not in ("VERIFICADA_AUTOMATICA", "FIRMADA")' in texto


def test_ficheros_de_borrador_reales_son_invisibles_al_loader():
    """Guardarraíl 1, contra el corpus de producción real: si el Prompt 1 ya
    generó ficheros `_borrador_*.yaml` en normativa/es/estatal/, el
    descubridor de producción no debe verlos."""
    encontrados = loader.descubrir(["es"])
    for ruta in encontrados:
        assert not ruta.name.startswith("_borrador_"), (
            f"{ruta} es un borrador y no debería ser descubrible por el corpus real"
        )


def test_end_to_end_regla_borrador_en_fichero_descubrible_nunca_se_afirma(tmp_path):
    """Integración completa contra `normativa.api`, con la regla BORRADOR
    colocada a propósito en un fichero SIN el prefijo `_` — para demostrar
    que el descarte de `_paso1_candidatas` no depende de esa convención de
    nombre. Reutiliza el corpus ficticio de pruebas (nunca el real)."""
    corpus_tmp = tmp_path / "corpus_ficticio"
    shutil.copytree(FIXTURE, corpus_tmp)

    destino = corpus_tmp / "es" / "estatal" / "con_borrador_descubrible.yaml"
    destino.write_text(yaml.safe_dump(DOC_CON_BORRADOR, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # Confirma la premisa del test: SÍ es descubrible (a propósito, sin «_»).
    descubiertos = loader.descubrir(["es"], raiz=corpus_tmp)
    assert destino in descubiertos

    ctx = contexto_territorial(
        municipio="Pozuelo de Alarcón",
        tipologia="plurifamiliar",
        uso="residencial.vivienda_libre",
        fecha_devengo=date(2026, 3, 1),
    )
    conjunto = normativa_aplicable(
        ctx,
        estricto=False,
        raiz_corpus=corpus_tmp,
        ruta_manifiesto=corpus_tmp / "manifiesto.yaml",
    )

    encontrada = [n for n in conjunto.normas if n.id == REGLA_BORRADOR["concept_id"]]
    assert encontrada, "la regla BORRADOR debería aparecer en el informe con su estado, no desaparecer en silencio"
    norma = encontrada[0]
    assert norma.estado == "no_aplica"
    assert "BORRADOR" in norma.motivo
    assert norma.valor_parametro is None
    # La afirmación de cumplimiento que un informe pudiera enseñar al
    # arquitecto nunca sale de una regla en este estado.
    assert norma.estado != "aplica"
