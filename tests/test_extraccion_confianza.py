"""Cálculo determinista de confianza y comprobaciones mecánicas.

Ni un solo test de este fichero llama a un modelo — es exactamente lo que
`docs/design/2026-08-06-extraccion-cte.md` §3 punto 7 pide: que "si la
confianza no es alta, no promover" sea comprobable con datos inventados, no
solo una promesa del prompt.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extraccion.confianza import calcular_confianza  # noqa: E402
from extraccion.modelo import Parametro, Segmento, Señales  # noqa: E402
from extraccion.verificacion import (  # noqa: E402
    cifras_verificadas_en_texto,
    comparador_valido,
    construir_señales,
    materia_valida,
    patron_valido,
    segmento_correcto,
    severidad_valida,
    tipo_coherente_con_patron,
    tipo_valido,
)


def _señales_limpias(**overrides) -> Señales:
    base = dict(
        patron_en_catalogo_cerrado=True, materia_en_catalogo_cerrado=True,
        tipo_en_catalogo_cerrado=True, severidad_en_catalogo_cerrado=True,
        tipo_coherente_con_patron=True, cifras_verificadas_en_texto=True,
        segmento_correcto=True, pide_revision_la_propia_ia=False,
    )
    base.update(overrides)
    return Señales(**base)


# --- calcular_confianza: la tabla, sin excepción ----------------------------

def test_todo_limpio_es_confianza_alta():
    nivel, revisar, motivos = calcular_confianza(_señales_limpias())
    assert nivel == "Alta"
    assert revisar is False
    assert motivos == ()


def test_un_solo_fallo_grave_hunde_a_baja_aunque_todo_lo_demas_este_bien():
    """La regla de la tabla: ningún fallo grave se diluye entre señales
    buenas. Es la misma disciplina de "mínimo, nunca media" de
    EVIDENCE_MODEL.md §9."""
    señales = _señales_limpias(cifras_verificadas_en_texto=False)
    nivel, revisar, motivos = calcular_confianza(señales)
    assert nivel == "Baja"
    assert revisar is True
    assert "cifra" in motivos[0]


def test_ia_pide_revision_hunde_a_baja_aunque_todo_lo_tecnico_este_bien():
    """El mecanismo 4 del diseño: necesita_revision_humana=true NUNCA
    convive con Alta, sea cual sea el resto."""
    señales = _señales_limpias(pide_revision_la_propia_ia=True)
    nivel, revisar, motivos = calcular_confianza(señales)
    assert nivel == "Baja"
    assert revisar is True


def test_segmento_incorrecto_es_fallo_grave():
    señales = _señales_limpias(segmento_correcto=False)
    nivel, revisar, _ = calcular_confianza(señales)
    assert nivel == "Baja" and revisar is True


def test_tipo_incoherente_con_patron_es_fallo_grave():
    señales = _señales_limpias(tipo_coherente_con_patron=False)
    nivel, revisar, _ = calcular_confianza(señales)
    assert nivel == "Baja" and revisar is True


def test_solo_fallos_menores_es_confianza_media_no_baja():
    """Un patrón o materia fuera de catálogo es grave para la corrección del
    dato, pero no es del mismo orden que una cifra inventada o una
    contradicción tipo/patrón — se distingue en Media, no se colapsa a Baja."""
    señales = _señales_limpias(patron_en_catalogo_cerrado=False, materia_en_catalogo_cerrado=False)
    nivel, revisar, motivos = calcular_confianza(señales)
    assert nivel == "Media"
    assert revisar is True  # revisar_manualmente es "!= Alta", Media también revisa
    assert len(motivos) == 2


def test_revisar_manualmente_es_mecanico_ninguna_confianza_no_alta_se_libra():
    for nivel_objetivo, señales in [
        ("Media", _señales_limpias(severidad_en_catalogo_cerrado=False)),
        ("Baja", _señales_limpias(cifras_verificadas_en_texto=False)),
    ]:
        nivel, revisar, _ = calcular_confianza(señales)
        assert nivel == nivel_objetivo
        assert revisar is True, f"confianza {nivel} debe revisarse siempre"


# --- Verificaciones mecánicas individuales ----------------------------------

def test_patron_valido():
    assert patron_valido(None) is True  # ausente es legítimo (tipo no evaluable)
    assert patron_valido("UMBRAL_SIMPLE") is True
    assert patron_valido("UMBRAL_INVENTADO") is False


def test_materia_valida():
    assert materia_valida(None) is True
    assert materia_valida("seguridad_incendio") is True
    assert materia_valida("materia_que_no_existe") is False


def test_tipo_valido_no_admite_ausente():
    """A diferencia de patrón/materia, el tipo SIEMPRE debe declararse —
    no hay «tipo ausente legítimo» en el catálogo de 7."""
    assert tipo_valido(None) is False
    assert tipo_valido("exigencia_cuantitativa") is True
    assert tipo_valido("tipo_inventado") is False


def test_severidad_valida():
    assert severidad_valida(None) is True
    assert severidad_valida("bloqueante") is True
    assert severidad_valida("urgente") is False  # no es de la escala de 4


def test_comparador_valido_incluye_los_de_presencia():
    assert comparador_valido(">=") is True
    assert comparador_valido("existe") is True
    assert comparador_valido("no_existe") is True
    assert comparador_valido("aproximadamente") is False


def test_tipo_coherente_con_patron_evaluable_exige_patron():
    assert tipo_coherente_con_patron("exigencia_cuantitativa", "UMBRAL_SIMPLE") is True
    assert tipo_coherente_con_patron("exigencia_cuantitativa", None) is False  # falta patrón


def test_tipo_coherente_con_patron_no_evaluable_prohibe_patron():
    assert tipo_coherente_con_patron("definicion", None) is True
    assert tipo_coherente_con_patron("definicion", "UMBRAL_SIMPLE") is False  # patrón de más


def test_tipo_coherente_con_patron_tipo_desconocido_nunca_es_coherente():
    assert tipo_coherente_con_patron(None, None) is False
    assert tipo_coherente_con_patron("tipo_inventado", None) is False


def test_cifras_verificadas_detecta_valor_no_presente():
    texto = "La anchura mínima del itinerario accesible será de 1,20 m."
    presente = (Parametro("anchura", "1,20 m", "m", ">=", None),)
    ausente = (Parametro("anchura", "2,50 m", "m", ">=", None),)
    assert cifras_verificadas_en_texto(presente, texto) is True
    assert cifras_verificadas_en_texto(ausente, texto) is False


def test_cifras_verificadas_sin_parametros_es_vacuamente_cierto():
    assert cifras_verificadas_en_texto((), "cualquier texto") is True


def test_segmento_correcto_detecta_salto_de_articulo():
    seg = Segmento(
        id="articulo_11", tipo_segmento="articulo", titulo="Artículo 11", capitulo=None,
        texto="texto", documento_identificador="X", orden=11,
    )
    assert segmento_correcto("articulo_11", seg) is True
    assert segmento_correcto("articulo_12", seg) is False
    assert segmento_correcto(None, seg) is False


# --- construir_señales: el punto de entrada único ---------------------------

def test_construir_señales_integra_todas_las_comprobaciones():
    seg = Segmento(
        id="articulo_11", tipo_segmento="articulo", titulo="Artículo 11", capitulo=None,
        texto="El recorrido no superará los 25 m.", documento_identificador="X", orden=11,
    )
    señales = construir_señales(
        tipo="exigencia_cuantitativa", patron="UMBRAL_SIMPLE", materia="seguridad_incendio",
        severidad="bloqueante", parametros=(Parametro("recorrido", "25 m", "m", "<=", None),),
        texto_original=seg.texto, segmento_id_declarado="articulo_11", segmento=seg,
        necesita_revision_humana=False,
    )
    nivel, revisar, _ = calcular_confianza(señales)
    assert nivel == "Alta" and revisar is False


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_"):
            try:
                fn()
                print(f"OK    {nombre}")
            except AssertionError as exc:
                fallos += 1
                print(f"FALLO {nombre}: {exc}")
    print(f"\n{'TODO OK' if not fallos else str(fallos) + ' FALLOS'}")
    sys.exit(1 if fallos else 0)
