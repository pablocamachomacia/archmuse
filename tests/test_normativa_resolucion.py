"""Resolución territorial: cadena de ámbitos, alias, ambigüedad y perfil.

El test que más importa aquí no es el que comprueba que Pozuelo resuelve bien:
es `test_municipio_desconocido_no_repliega`. Un repliegue silencioso a otro
municipio es el Bug #1 (`TECH_REVIEW.md`) reencarnado en la capa territorial,
y falla del peor modo posible: dando una respuesta tranquilizadora y falsa.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from normativa.api import contexto_territorial, perfil_proyecto, resolver_ambito  # noqa: E402
from normativa.errores import AmbitoAmbiguo, AmbitoDesconocido  # noqa: E402
from normativa.registro import registro  # noqa: E402


def test_cadena_de_pozuelo():
    """El ejemplo trabajado de NORMATIVE_RESOLUTION.md §13."""
    c = resolver_ambito(municipio="Pozuelo de Alarcón")
    assert [a.id for a in c.ambitos] == ["es", "es.13", "es.13.28", "es.13.28.28115"]
    assert c.por_nivel("autonomico").nombre == "Comunidad de Madrid"
    assert c.mas_especifico.codigo == "28115"


def test_la_provincia_no_aporta_corpus():
    """Ninguna provincia española regula edificación: está en la cadena para
    desambiguar homónimos, pero el loader no le pide ficheros."""
    c = resolver_ambito(municipio="Pozuelo de Alarcón")
    assert c.ids_con_corpus == ["es", "es.13", "es.13.28.28115"]
    assert "es.13.28" not in c.ids_con_corpus


def test_alias_y_normalizacion():
    """Tildes, mayúsculas, cooficiales y formas castellanas."""
    esperado = {
        "Pozuelo de Alarcón": "28115", "POZUELO DE ALARCON": "28115", "pozuelo": "28115",
        "Donostia": "20069", "San Sebastián": "20069",
        "elche": "03065", "Elx": "03065",
        "La Coruña": "15030", "A Coruña": "15030",
        "valencia": "46250", "València": "46250",
        "Palma de Mallorca": "07040",
    }
    for texto, codigo in esperado.items():
        assert resolver_ambito(municipio=texto).mas_especifico.codigo == codigo, texto


def test_municipio_desconocido_no_repliega():
    """EL TEST QUE MÁS IMPORTA.

    El registro tiene 31 de 8.131 municipios. Un municipio ausente debe
    levantar AmbitoDesconocido — nunca devolver Madrid, ni el primero de la
    lista, ni un ámbito solo estatal fingiendo que da igual.
    """
    for texto in ("Villarriba del Alcor", "Leganés", "Alcobendas", "Getafe"):
        try:
            resolver_ambito(municipio=texto)
        except AmbitoDesconocido as exc:
            assert texto in str(exc)
        else:
            raise AssertionError(f"«{texto}» no está en el registro y aun así resolvió")


def test_nombre_ambiguo_pregunta_no_elige(tmp_path=None):
    """Un nombre que corresponde a varios municipios devuelve los candidatos.

    Hoy la semilla no tiene homónimos, así que se construye el caso: lo que se
    verifica es que el mecanismo pregunta en vez de elegir (p. ej. el más
    poblado), que sería un repliegue silencioso disfrazado de conveniencia.
    """
    reg = registro()
    original = dict(reg._indice_municipios)
    try:
        reg._indice_municipios["villanueva"] = ["28115", "08019"]
        try:
            resolver_ambito(municipio="Villanueva")
        except AmbitoAmbiguo as exc:
            assert len(exc.candidatos) == 2
            assert {c["codigo"] for c in exc.candidatos} == {"28115", "08019"}
        else:
            raise AssertionError("un nombre ambiguo debe preguntar, no elegir")
    finally:
        reg._indice_municipios.clear()
        reg._indice_municipios.update(original)


def test_provincia_desambigua():
    reg = registro()
    original = dict(reg._indice_municipios)
    try:
        reg._indice_municipios["villanueva"] = ["28115", "08019"]
        c = resolver_ambito(municipio="Villanueva", provincia="Madrid")
        assert c.mas_especifico.codigo == "28115"
    finally:
        reg._indice_municipios.clear()
        reg._indice_municipios.update(original)


def test_cadena_sin_municipio_es_legitima():
    """Analizar contra CTE + normativa autonómica sin fijar municipio es un
    caso real: produce ausencia de capa municipal, no un municipio inventado."""
    c = resolver_ambito(comunidad="Cataluña")
    assert [a.id for a in c.ambitos] == ["es", "es.09"]
    assert c.por_nivel("municipal") is None


def test_sectoriales_sin_declarar_son_desconocidos():
    """Un sectorial sin declarar NO es 'no aplica'.

    `INFERENCE_ENGINE.md` §2.2: la ausencia de evidencia no es evidencia de
    ausencia. Es la variante más peligrosa del Bug #1 porque falla como un
    tranquilizador 'aquí no hay problema de patrimonio'.
    """
    c = resolver_ambito(municipio="Madrid")
    assert len(c.sectoriales_sin_declarar) == 4
    assert all(s.declarado is None for s in c.sectoriales_sin_declarar)

    c2 = resolver_ambito(municipio="Madrid", sectoriales={"patrimonio": False})
    patrimonio = next(s for s in c2.sectoriales if s.id == "patrimonio")
    assert patrimonio.declarado is False and not patrimonio.desconocido


def test_procedencia_viaja_con_la_cadena():
    """El registro es una semilla manual sin verificar, y eso no se puede
    perder por el camino."""
    c = resolver_ambito(municipio="Madrid")
    assert c.procedencia is not None
    assert c.procedencia.verificado is False
    assert c.procedencia.origen == "semilla_manual"


def test_perfil_traduce_los_valores_heredados_con_asuncion():
    """`rehabilitacion` es un tipo de intervención, no una tipología. Se
    traduce, y la traducción se declara."""
    p = perfil_proyecto(tipologia="rehabilitacion")
    assert p.tipo_de_intervencion == "rehabilitacion"
    assert p.tipologia == "plurifamiliar"
    assert p.asunciones and "tipo de intervención" in p.asunciones[0]

    p2 = perfil_proyecto(tipologia="unifamiliar")
    assert p2.tipologia == "unifamiliar_aislada"
    assert p2.asunciones


def test_perfil_sin_asunciones_cuando_todo_se_declara():
    p = perfil_proyecto(
        tipo_de_intervencion="obra_nueva",
        uso="residencial.vivienda_libre",
        tipologia="unifamiliar_aislada",
    )
    assert p.asunciones == ()


def test_uso_es_un_arbol():
    """Una regla que declara `residencial` cubre `residencial.vivienda_libre`,
    pero no al revés."""
    p = perfil_proyecto(tipologia="plurifamiliar", uso="residencial.vivienda_protegida")
    assert p.cubre_uso("residencial")
    assert p.cubre_uso("residencial.vivienda_protegida")
    assert not p.cubre_uso("residencial.vivienda_libre")
    assert not p.cubre_uso("industrial")


def test_uso_mixto():
    """Un edificio residencial con local comercial tiene dos usos: las reglas
    de comercial aplican al local aunque el edificio sea residencial."""
    p = perfil_proyecto(
        tipologia="plurifamiliar",
        uso="residencial.vivienda_libre",
        usos_presentes=["residencial.vivienda_libre", "comercial"],
    )
    assert p.cubre_uso("residencial") and p.cubre_uso("comercial")


def test_fecha_de_devengo_omitida_es_asuncion_declarada():
    """`fecha_devengo=None` usa hoy, pero NUNCA en silencio."""
    ctx = contexto_territorial(municipio="Madrid", tipologia="plurifamiliar")
    assert ctx.fecha_devengo == date.today()
    assert any("fecha de devengo" in a for a in ctx.asunciones)

    ctx2 = contexto_territorial(
        municipio="Madrid", tipologia="plurifamiliar", fecha_devengo=date(2025, 3, 15)
    )
    assert ctx2.fecha_devengo == date(2025, 3, 15)
    assert not any("fecha de devengo" in a for a in ctx2.asunciones)


def test_zona_desconocida_se_declara_no_se_repliega():
    """Pozuelo no está en la tabla de zonas climáticas. El contexto lo dice
    en vez de coger la 'C' por defecto — que es lo que hace la fachada
    heredada de `cte_zonas.py`, deliberadamente, para no regresionar."""
    ctx = contexto_territorial(municipio="Pozuelo de Alarcón", tipologia="unifamiliar_aislada")
    assert ctx.zona_climatica is None
    assert any("zona climática" in a for a in ctx.asunciones)

    ctx_madrid = contexto_territorial(municipio="Madrid", tipologia="plurifamiliar")
    assert ctx_madrid.zona_climatica == "D"


def test_ejes_de_contexto_no_inventan_valores():
    ctx = contexto_territorial(municipio="Pozuelo de Alarcón", tipologia="unifamiliar_aislada")
    ejes = ctx.ejes_de_contexto()
    assert ejes["comunidad"] == "13" and ejes["municipio"] == "28115"
    assert ejes["zona_cte"] is None  # desconocido, no "C"


def test_determinismo():
    """Mismas entradas -> mismo resultado. Requisito de TRACEABILITY.md §10."""
    a = contexto_territorial(municipio="Madrid", tipologia="plurifamiliar", fecha_devengo=date(2026, 1, 1))
    b = contexto_territorial(municipio="Madrid", tipologia="plurifamiliar", fecha_devengo=date(2026, 1, 1))
    assert a == b


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_"):
            try:
                fn()
                print(f"OK   {nombre}")
            except AssertionError as exc:
                fallos += 1
                print(f"FALLO {nombre}: {exc}")
    print(f"\n{'TODO OK' if not fallos else str(fallos) + ' FALLOS'}")
    sys.exit(1 if fallos else 0)
