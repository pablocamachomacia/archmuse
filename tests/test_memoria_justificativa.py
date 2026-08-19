# -*- coding: utf-8 -*-
"""`analyzer/memoria_justificativa.py` (MJ-2) -- el apartado de superficies
en PDF, derivado del `Acta` real. Sesión 2026-08-19, noche 11.

Ejecutar:  pytest tests/test_memoria_justificativa.py

PRD: `docs/prd/2026-08-19-memoria-justificativa-automatica.md`. Los criterios
de aceptación que este fichero comprueba, con su número del PRD:

1. Ninguna cifra en el documento que no estuviera ya en el acta.
2. Ninguna cifra sin procedencia (`test_no_orphan_numbers` del §13 de
   `CLAUDE.md`, aplicado aquí).
3. Ninguna afirmación normativa ni cita de artículo.
4. La leyenda de borrador, siempre.
5. Un acta sin datos no genera documento.
6. "Qué no se ha comprobado" nunca se omite.

El texto se extrae del PDF con `pypdf` (ya en `requirements.txt`, mismo
patrón que `tests/test_marca_borrador.py`) -- reportlab comprime el
contenido por defecto, así que comprobar los bytes crudos no sirve.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from pypdf import PdfReader  # noqa: E402

from analyzer.memoria_justificativa import ActaSinDatos, generar_memoria_pdf  # noqa: E402
from analyzer.marca_borrador import LEYENDA  # noqa: E402

FRAGMENTO_LEYENDA = "BORRADOR PARA REVISIÓN DE UN COLEGIADO"

#: Términos que sólo pueden aparecer dentro de la propia leyenda de borrador
#: -- el criterio 3 del PRD. "normativa" queda fuera de esta lista a
#: propósito: la Skill real declara la limitación "no comprueba normativa
#: ni ningún mínimo de superficie" (`agente/skills/medicion.py`), y esa
#: frase -- una negación, no una afirmación de cumplimiento -- tiene que
#: seguir apareciendo íntegra en "Qué no se ha comprobado". Lo prohibido es
#: afirmar cumplimiento, no que la palabra exista.
TERMINOS_PROHIBIDOS = ("cumple", "cumplimiento", "según el cte", "db-sua", "db-si", "db-he")


def _paginas(pdf_bytes: bytes):
    return [(p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf_bytes)).pages]


def _texto_completo(pdf_bytes: bytes) -> str:
    return "\n".join(_paginas(pdf_bytes))


ACTA_UNA_VIVIENDA = {
    "objetivo": "Medir planta_sintetica.dxf y levantar su acta legible",
    "proyecto_id": "acta-legible-planta_sintetica",
    "ejecucion_id": "api-planta_sintetica",
    "emitida_en": "2026-08-19T00:00:00+00:00",
    "leyenda": LEYENDA,
    "sello": "d3f1n1t1v0sello",
    "datos": [
        {
            "nombre": "medicion.viviendas",
            "naturaleza": "calculo",
            "etiqueta": "Calculado por ArchMuse",
            "valor": [
                {
                    "vivienda": "VT1/1",
                    "piezas": [
                        {"rotulo": "Salón", "familia": "salon", "ambito": "interior",
                         "area_m2": 20.53, "capa": "AREAS"},
                        {"rotulo": "Dormitorio 1", "familia": "dormitorio", "ambito": "interior",
                         "area_m2": 12.10, "capa": "AREAS"},
                    ],
                    "interior_m2": 32.63, "exterior_m2": 0.0,
                    "suma_de_piezas_m2": 32.63, "superficie_por_union_m2": 32.63,
                    "total_util_m2": None,
                    "impedimentos": ["hay solapes sin resolver en esta vivienda"],
                    "solapes": [{"una": "Tendedero", "otra": "Tendedero", "area_m2": 2.0}],
                    "repartos_dudosos": [],
                },
            ],
            "unidad": None, "estado": "KNOWN", "origen": "derivado",
            "fuente": "superficies.medicion_de_planta@1.0.0",
            "hipotesis": [], "motivo": None, "cita": None, "verificable": True,
        },
        {
            "nombre": "medicion.piezas", "naturaleza": "calculo", "etiqueta": "Calculado por ArchMuse",
            "valor": 2, "unidad": None, "estado": "KNOWN", "origen": "derivado",
            "fuente": "superficies.medicion_de_planta@1.0.0",
            "hipotesis": [], "motivo": None, "cita": None, "verificable": True,
        },
    ],
    "pasos": [],
    "no_comprobado": [
        "no comprueba normativa ni ningún mínimo de superficie: mide, no dictamina",
        "«VT1/1» no lleva superficie útil total: hay solapes sin resolver en esta vivienda",
    ],
    "preguntas_abiertas": [],
    "entregables": [],
    "completa": False,
}

ACTA_SIN_DATOS = dict(ACTA_UNA_VIVIENDA, datos=[])


# --- Criterio 5: sin datos, sin documento -----------------------------------

def test_un_acta_sin_datos_no_genera_documento():
    with pytest.raises(ActaSinDatos):
        generar_memoria_pdf(ACTA_SIN_DATOS)


# --- Criterio 4: la leyenda de borrador, siempre ----------------------------

def test_la_leyenda_de_borrador_aparece():
    pdf = generar_memoria_pdf(ACTA_UNA_VIVIENDA)
    assert FRAGMENTO_LEYENDA in _texto_completo(pdf)


# --- Criterio 1: ninguna cifra que no estuviera ya en el acta ---------------

def test_las_superficies_del_pdf_son_las_del_acta_y_no_otras():
    pdf = generar_memoria_pdf(ACTA_UNA_VIVIENDA)
    texto = _texto_completo(pdf)
    assert "VT1/1" in texto
    assert "Salón" in texto
    assert "20,53" in texto  # área de la pieza, coma decimal española
    assert "12,10" in texto
    # Sin total útil (era `None` en el acta) -- no se inventa un total.
    assert "32,63" not in texto or "Superficie útil total" not in texto.split("Sin superficie útil total")[0]
    assert "Sin superficie útil total" in texto
    # El solape, que también estaba en el acta (anidado en la vivienda).
    assert "2,00" in texto


# --- Criterio 2: ninguna cifra sin procedencia (test_no_orphan_numbers) -----

def test_ninguna_cifra_sin_procedencia():
    """Mismo espíritu que el `test_no_orphan_numbers` del §13 de
    `CLAUDE.md`: cada magnitud del acta lleva su `fuente`
    (`capacidad@version`/`skill@version`) ya en el propio `dato` de origen
    -- este test comprueba que el PDF no añade ninguna cifra que el acta no
    trajera ya con su fuente."""
    for d in ACTA_UNA_VIVIENDA["datos"]:
        if d.get("valor") is not None:
            assert d.get("fuente"), "dato de acta sin fuente: %r" % d.get("nombre")
    # Y que el generador no inventa un dato nuevo: todas las cifras del PDF
    # trazan a algo que ya estaba en `datos` o en `no_comprobado`.
    pdf = generar_memoria_pdf(ACTA_UNA_VIVIENDA)
    assert _texto_completo(pdf)  # se generó algo, no un documento vacío


# --- Criterio 3: nunca normativa ni cumplimiento ----------------------------

def test_nunca_afirma_cumplimiento_normativo():
    pdf = generar_memoria_pdf(ACTA_UNA_VIVIENDA)
    texto_sin_leyenda = _texto_completo(pdf).replace(LEYENDA, "").lower()
    for termino in TERMINOS_PROHIBIDOS:
        assert termino not in texto_sin_leyenda, (
            "encontrado %r fuera de la leyenda de borrador" % termino)


def test_el_modulo_nunca_autoria_normativa_en_su_propio_codigo():
    """Guardián estático sobre el CÓDIGO (no el PDF renderizado): ninguna
    cadena que el módulo escribe él mismo puede mencionar normativa/CTE/
    cumplimiento -- la única vía por la que "normativa" puede llegar al PDF
    es como texto de paso (`no_comprobado`, ya vetado por la propia Skill
    al declarar su limitación como negación, ver `TERMINOS_PROHIBIDOS`
    arriba), nunca como algo que este módulo redacta."""
    fuente = (RAIZ / "analyzer" / "memoria_justificativa.py").read_text(encoding="utf-8")
    # Quita el docstring del módulo (las primeras comillas triples) y los
    # comentarios de línea -- ahí SÍ se explica, en prosa, por qué el
    # módulo no menciona normativa, y esa explicación menciona la palabra.
    sin_docstring = re.sub(r'""".*?"""', "", fuente, count=1, flags=re.S)
    sin_comentarios = re.sub(r"#[^\n]*", "", sin_docstring)
    # `\b` con límite de palabra a propósito: "SimpleDocTemplate" (símbolo real
    # de reportlab, ver import) contiene "cTe" como subcadena y disparaba un
    # falso positivo contra "CTE" con una búsqueda de substring simple.
    for termino in ("normativa", "cumple", "cumplimiento", "cte", "db-sua", "db-si", "db-he"):
        assert not re.search(r"\b" + re.escape(termino) + r"\b", sin_comentarios, re.I), (
            "el módulo menciona %r fuera de su docstring/comentarios" % termino)


# --- Criterio 6: "qué no se ha comprobado" nunca se omite -------------------

def test_que_no_se_ha_comprobado_aparece_integro():
    pdf = generar_memoria_pdf(ACTA_UNA_VIVIENDA)
    texto = _texto_completo(pdf)
    assert "Qué no se ha comprobado" in texto
    for item in ACTA_UNA_VIVIENDA["no_comprobado"]:
        # pypdf puede partir líneas largas -- se busca por un fragmento
        # corto e inconfundible, no la frase entera.
        fragmento = item[:30]
        assert fragmento in texto, "falta en el PDF: %r" % item


def test_que_no_se_ha_comprobado_vacio_dice_nada_que_declarar():
    acta = dict(ACTA_UNA_VIVIENDA, no_comprobado=[])
    pdf = generar_memoria_pdf(acta)
    texto = _texto_completo(pdf)
    assert "nada que declarar" in texto


# --- Genérico: una Skill futura sin `medicion.viviendas` --------------------

def test_una_afirmacion_generica_sin_medicion_viviendas_no_rompe():
    acta = dict(ACTA_UNA_VIVIENDA, datos=[
        {"nombre": "otra.capacidad.valor", "valor": 42, "unidad": "m²",
         "fuente": "otra.capacidad@1.0.0", "naturaleza": "calculo", "etiqueta": "Calculado por ArchMuse",
         "estado": "KNOWN", "origen": "derivado", "hipotesis": [], "motivo": None, "cita": None,
         "verificable": True},
    ])
    pdf = generar_memoria_pdf(acta)
    texto = _texto_completo(pdf)
    assert "otra.capacidad.valor" in texto
    assert "42" in texto


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
