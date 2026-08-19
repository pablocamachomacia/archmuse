# -*- coding: utf-8 -*-
"""La caja de herramientas comun a toda Skill (`agente/skills/_comun.py`).

Ejecutar:  pytest tests/test_agente_skills_comun.py

**Que se fija aqui y por que importa.** Antes de este modulo, el invariante mas
caro del producto —*todo lo que una Skill prometio y no produjo sale `UNKNOWN`
con motivo, nunca ausente*— estaba escrito en cuatro sitios y de tres formas
distintas: `_sin_hacer` en `superficies`, `_desconocidas` en `evacuacion`, y dos
bucles a pelo dentro de `territorial._ejecutar`. Cuatro copias del mismo
invariante no son redundancia defensiva: son cuatro sitios donde arreglar el bug
de uno deja los otros tres rotos.

El invariante no es cosmetico. Un hueco mudo se lee como «no aplica», que es la
lectura contraria a la verdadera, y en un documento que un arquitecto firma esa
diferencia es responsabilidad civil.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente.afirmacion import calculo  # noqa: E402
from agente.skill import ResultadoDeSkill  # noqa: E402
from agente.skills import _comun  # noqa: E402

PRODUCE = ("a.uno", "a.dos", "a.tres")


# --- 1. Lo prometido y no producido sale UNKNOWN con motivo ---------------

def test_lo_que_no_se_produjo_sale_unknown_con_motivo_y_no_ausente():
    afirmaciones = _comun.sin_producir(
        PRODUCE, codigo="plano_ilegible", detalle="el DXF no se abre", fuente="s@1.0.0")
    assert [a.nombre for a in afirmaciones] == list(PRODUCE)
    for a in afirmaciones:
        assert a.estado == "UNKNOWN"
        assert a.valor is None
        # El motivo es lo que separa «no lo se» de «no aplica».
        assert a.motivo is not None and a.motivo.codigo == "plano_ilegible"
        assert a.motivo.detalle == "el DXF no se abre"


def test_lo_ya_calculado_se_conserva_tal_cual():
    hecha = calculo("a.dos", 42.0, fuente="s@1.0.0", unidad="m2")
    afirmaciones = _comun.sin_producir(
        PRODUCE, codigo="x", detalle="d", fuente="s@1.0.0", ya_hecho={"a.dos": hecha})
    por_nombre = {a.nombre: a for a in afirmaciones}
    assert por_nombre["a.dos"] is hecha
    assert por_nombre["a.uno"].estado == "UNKNOWN"
    assert por_nombre["a.tres"].estado == "UNKNOWN"


def test_el_orden_es_el_de_produce_para_que_dos_actas_se_puedan_comparar():
    """Dos ejecuciones de la misma Skill tienen que producir actas comparables
    linea a linea. Con el orden dependiendo de que paso llego a completarse,
    comparar dos actas del mismo plano obliga a leerlas enteras."""
    hecha = calculo("a.tres", 1, fuente="s@1.0.0")
    afirmaciones = _comun.sin_producir(
        PRODUCE, codigo="x", detalle="d", fuente="s@1.0.0", ya_hecho={"a.tres": hecha})
    assert [a.nombre for a in afirmaciones] == list(PRODUCE)


def test_una_afirmacion_ya_hecha_fuera_de_produce_no_se_pierde_en_silencio():
    """Perder una afirmacion ya calculada es el mismo hueco mudo por la otra
    puerta, y ademas uno que nadie ve."""
    extra = calculo("a.extra", 7, fuente="s@1.0.0")
    afirmaciones = _comun.sin_producir(
        PRODUCE, codigo="x", detalle="d", fuente="s@1.0.0", ya_hecho={"a.extra": extra})
    assert extra in afirmaciones
    assert len(afirmaciones) == len(PRODUCE) + 1


def test_sin_claves_no_inventa_afirmaciones():
    assert _comun.sin_producir((), codigo="x", detalle="d", fuente="s") == ()


# --- 2. Buscar un valor del resultado -------------------------------------

def test_valor_encuentra_lo_que_hay_y_devuelve_el_defecto_si_no():
    resultado = ResultadoDeSkill(afirmaciones=(calculo("a.uno", 3.5, fuente="s"),))
    assert _comun.valor(resultado, "a.uno") == 3.5
    assert _comun.valor(resultado, "a.nada") is None
    assert _comun.valor(resultado, "a.nada", "por_defecto") == "por_defecto"


def test_valor_distingue_un_none_declarado_de_un_nombre_que_no_existe():
    """Los dos devuelven `None` con el defecto de fabrica, y son cosas
    distintas: uno es «se midio y no habia», el otro es «nadie lo midio». Quien
    necesite separarlos pasa un centinela."""
    resultado = ResultadoDeSkill(
        afirmaciones=(_comun.sin_producir(("a.uno",), codigo="c", detalle="d",
                                          fuente="s")[0],))
    centinela = object()
    assert _comun.valor(resultado, "a.uno", centinela) is None
    assert _comun.valor(resultado, "a.dos", centinela) is centinela


# --- 3. Una pregunta que no se puede contestar no es preguntar ------------
#
# Encontrado sobre el plano real `v2s.dxf`: la capacidad devuelve preguntas
# completas —que hueco resuelven, que opciones hay, con que superficie cada una,
# y con que forma se contesta— y la Skill se quedaba con el `titulo`. Para
# contestar habia que saltarse la Skill e ir a la capacidad, es decir, leer el
# codigo.

def test_una_pregunta_de_asignacion_llega_con_sus_opciones_y_su_forma():
    texto = _comun.pregunta_legible({
        "id": "grupo_exterior",
        "tipo": "asignacion",
        "campos": ["terraza_1", "tendedero_1"],
        "titulo": "Que recinto es cada pieza exterior?",
        "ayuda": "El plano tiene dos piezas rotuladas igual.",
        "unidad": None,
        "candidatos": [
            {"id": "cand_0", "etiqueta": "Tendedero", "area_m2": 4.0},
            {"id": "cand_1", "etiqueta": "Terraza", "area_m2": 3.08},
        ],
    })
    # Los ids son lo que hay que devolver en `respuestas`: sin ellos la
    # respuesta se escribe de memoria, que es como se cambia una asignacion sin
    # querer.
    assert "cand_0" in texto and "cand_1" in texto
    # Y la superficie de cada opcion, que es con lo que se decide.
    assert "4.0" in texto and "3.08" in texto
    # Los huecos del cuadro que la respuesta desbloquea.
    assert "terraza_1" in texto and "tendedero_1" in texto
    # La forma exacta de la respuesta, no una descripcion de la forma.
    assert '"tipo": "asignacion"' in texto
    assert '"solicitud_id": "grupo_exterior"' in texto
    assert "El plano tiene dos piezas rotuladas igual." in texto


def test_una_pregunta_numerica_dice_que_campo_y_en_que_unidad():
    texto = _comun.pregunta_legible({
        "id": "num_construida",
        "tipo": "numerico",
        "campos": ["superficie_construida_cerrada"],
        "titulo": "Cual es la superficie construida cerrada?",
        "ayuda": "No se deduce de la geometria del plano.",
        "unidad": "m2",
        "candidatos": [],
    })
    assert '"tipo": "numerico"' in texto
    assert '"campo": "superficie_construida_cerrada"' in texto
    assert "m2" in texto


def test_una_asignacion_sin_candidatos_lo_dice_en_vez_de_ofrecer_una_lista_vacia():
    """El caso que produce «Opciones: .» y deja al arquitecto adivinando si el
    fallo es suyo o del plano."""
    texto = _comun.pregunta_legible({
        "id": "x", "tipo": "asignacion", "campos": ["terraza_1"],
        "titulo": "Cual es la terraza?", "ayuda": "", "candidatos": [],
    })
    assert "ninguna" in texto and "candidatas" in texto


def test_una_pregunta_sin_titulo_lo_dice_en_vez_de_salir_vacia():
    texto = _comun.pregunta_legible({"id": "x", "tipo": "numerico", "campos": []})
    assert texto.strip()
    assert "sin título" in texto


# --- 4. La guardia que impide que la duplicacion vuelva -------------------

def test_ninguna_skill_vuelve_a_escribir_el_bucle_de_UNKNOWN_por_su_cuenta():
    """El test que evita que esto se deshaga solo.

    La duplicacion no volvera porque alguien decida duplicar: volvera porque
    quien escriba la Skill numero cinco no sepa que existe esta pieza y escriba
    tres lineas que funcionan. Entonces habra dos implementaciones otra vez y
    nadie se enterara hasta que una de las dos tenga un fallo.

    Se mira el fuente y no el comportamiento a proposito: el comportamiento de
    la copia seria correcto — ese es justo el problema.
    """
    import re
    from pathlib import Path

    skills = Path(__file__).resolve().parent.parent / "agente" / "skills"
    culpables = []
    for fichero in sorted(skills.glob("*.py")):
        if fichero.name in ("_comun.py", "__init__.py"):
            continue
        fuente = fichero.read_text(encoding="utf-8")
        # Construir una `Afirmacion` UNKNOWN a mano dentro de una Skill es la
        # senal: para eso esta `sin_producir`, y una excepcion legitima usa
        # `desconocido()`, que es el constructor con nombre.
        if re.search(r'estado\s*=\s*"UNKNOWN"', fuente):
            culpables.append(fichero.name)
    assert not culpables, (
        "estas Skills construyen una afirmacion UNKNOWN a mano en vez de usar "
        "`_comun.sin_producir` o `afirmacion.desconocido`: %s" % culpables)
