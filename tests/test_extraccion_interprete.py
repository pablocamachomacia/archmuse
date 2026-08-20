"""Interpretación por IA — el único módulo de `extraccion/` que llama a un
modelo real. Saltado por defecto (cuesta tokens de verdad, no solo tiempo):
se activa a mano con `ARCHMUSE_TEST_IA=1` en el entorno.

Dos fuentes de material:

1. **Segmentos reales**, sacados con `extraccion.segmentador.segmentar()`
   del CTE real (`BOE-A-2006-5515.xml`) — Artículo 2 (Ámbito de aplicación,
   `exigencia_cualitativa`/`definicion` esperado) y Artículo 11 (Exigencias
   básicas de seguridad en caso de incendio, marco general sin umbral
   propio). Prueban el extractor contra prosa legal real y desordenada, no
   contra un caso de laboratorio.

2. **Un segmento FICTICIO**, con el estilo real de un artículo de Documento
   Básico (numeración, unidad, excepción) pero **inventado para este test**
   — ver `docs/design/2026-08-06-extraccion-cte.md` §0: el documento real ya
   ingerido (Parte I del CTE) no contiene ningún Documento Básico, así que no
   hay ningún artículo real con un umbral numérico que probar todavía. Nunca
   se cita como normativa real; solo aparece en este test, con el aviso
   delante.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extraccion.interprete import interpretar  # noqa: E402
from extraccion.modelo import Segmento  # noqa: E402
from extraccion.pipeline import _candidata_desde_bruto  # noqa: E402
from extraccion.segmentador import segmentar  # noqa: E402
from ingesta.fuentes.boe import FuenteBOE  # noqa: E402

ACTIVO = os.environ.get("ARCHMUSE_TEST_IA") == "1"

FIXTURE_CTE = (RAIZ / "tests" / "fixtures" / "boe" / "BOE-A-2006-5515.xml").read_bytes()

# --- El segmento ficticio, con el aviso por delante -------------------------
# NO ES NORMATIVA REAL. Estilo realista de un artículo de Documento Básico
# (DB-SUA, accesibilidad), inventado únicamente para ejercitar la rama de
# extracción con umbral numérico, que el CTE realmente ingerido no contiene.
SEGMENTO_FICTICIO = Segmento(
    id="segmento_ficticio_dbsua_9_1",
    tipo_segmento="articulo",
    titulo="[FICTICIO — no es normativa real] SUA 9.1 Condiciones de accesibilidad",
    capitulo="[FICTICIO] Sección SUA 9",
    texto=(
        "[FICTICIO — NO CITAR COMO NORMATIVA REAL] 1 Con el fin de facilitar el acceso y la "
        "utilización no discriminatoria, independiente y segura de los edificios a las personas "
        "con discapacidad se cumplirán las condiciones funcionales y de dotación de elementos "
        "accesibles que se establecen a continuación. 2 La anchura libre mínima de los itinerarios "
        "accesibles será de 1,20 m, salvo en los puntos fijos de atención, en los que podrá "
        "reducirse a 0,80 m. 3 Se exceptúa de lo anterior a las obras de rehabilitación en "
        "edificios catalogados en las que se justifique la imposibilidad técnica o económica de "
        "cumplir la anchura mínima, siempre que se adopte una solución alternativa razonable."
    ),
    documento_identificador="FICTICIO-NO-USAR",
    orden=1,
)


def _documento_cte():
    return FuenteBOE()._documento_desde_xml(
        "BOE-A-2006-5515", "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2006-5515", FIXTURE_CTE
    )


def _saltar(nombre: str) -> bool:
    if not ACTIVO:
        print(f"  [SALTADO] {nombre}: define ARCHMUSE_TEST_IA=1 para probar contra la API real")
        return True
    return False


def test_articulo_2_real_produce_tipo_no_evaluable():
    """El Ámbito de aplicación es una definición de qué obras cubre el CTE,
    no un umbral — el tipo correcto es "definicion" o "exigencia_cualitativa",
    nunca "exigencia_cuantitativa" con un patrón inventado."""
    if _saltar("test_articulo_2_real_produce_tipo_no_evaluable"):
        return
    segmentos = segmentar(_documento_cte())
    articulo_2 = next(s for s in segmentos if s.id == "articulo_2")
    bruto = interpretar(articulo_2)

    assert bruto["segmento_id"] == "articulo_2"
    assert bruto["tipo"] in ("definicion", "exigencia_cualitativa", "procedimental")
    assert not bruto.get("patron"), f"un tipo no evaluable no debería traer patrón: {bruto.get('patron')}"

    candidata = _candidata_desde_bruto(bruto, articulo_2, _documento_cte())
    assert candidata.texto_original == articulo_2.texto  # trazabilidad literal
    assert candidata.documento_identificador == "BOE-A-2006-5515"
    assert candidata.url_oficial
    print(f"  articulo_2 -> tipo={candidata.tipo} confianza={candidata.nivel_confianza}")


def test_articulo_11_real_no_inventa_umbral_del_db_si():
    """Artículo 11 (Exigencias básicas SI) es el marco general — remite a un
    Documento Básico que NO está en el texto ingerido. El extractor no debe
    inventar un umbral de distancia de evacuación "porque lo sabe" del CTE
    real: si lo hace, `cifras_verificadas_en_texto` debe pillarlo y la
    confianza debe caer a Baja."""
    if _saltar("test_articulo_11_real_no_inventa_umbral_del_db_si"):
        return
    segmentos = segmentar(_documento_cte())
    articulo_11 = next(s for s in segmentos if s.id == "articulo_11")
    bruto = interpretar(articulo_11)
    candidata = _candidata_desde_bruto(bruto, articulo_11, _documento_cte())

    for p in candidata.parametros:
        assert p.valor_citado in articulo_11.texto, (
            f"cifra «{p.valor_citado}» no está en el texto real del artículo 11 — "
            f"posible alucinación no detectada"
        )
    print(f"  articulo_11 -> tipo={candidata.tipo} confianza={candidata.nivel_confianza} "
          f"parametros={len(candidata.parametros)}")


def test_segmento_ficticio_con_umbral_extrae_el_valor_citado():
    """La rama que el CTE real ingerido no puede ejercitar: un artículo con
    umbral numérico explícito, condición de aplicación y excepción. El valor
    "1,20 m" debe aparecer tal cual — no "1.20", no "120 cm", no redondeado."""
    if _saltar("test_segmento_ficticio_con_umbral_extrae_el_valor_citado"):
        return
    bruto = interpretar(SEGMENTO_FICTICIO)
    candidata = _candidata_desde_bruto(bruto, SEGMENTO_FICTICIO, _documento_cte())

    # El tipo puede variar entre "exigencia_cuantitativa" y "exigencia_compuesta"
    # de una llamada a otra (temperature=0 no garantiza bit-a-bit — limitación
    # honesta ya documentada en §3 punto 6 del diseño): el artículo ficticio
    # combina un umbral principal con una excepción cuantitativa parcial Y una
    # cualitativa, así que ambas lecturas son razonables. Lo que NO puede
    # variar, y es lo que de verdad importa aquí, es que las cifras extraídas
    # sean las reales del texto — eso es lo que prueba este test.
    assert candidata.tipo in ("exigencia_cuantitativa", "exigencia_compuesta"), bruto
    assert candidata.patron in ("UMBRAL_SIMPLE", "UMBRAL_CON_EXCEPCION"), bruto
    valores = [p.valor_citado for p in candidata.parametros]
    assert any("1,20" in v for v in valores), f"no se extrajo el umbral real: {valores}"
    assert candidata.excepciones, "el artículo ficticio declara una excepción explícita"
    assert candidata.señales.cifras_verificadas_en_texto is True
    print(f"  ficticio -> tipo={candidata.tipo} patron={candidata.patron} "
          f"parametros={valores} confianza={candidata.nivel_confianza}")


def test_segmento_ficticio_simple_sin_excepciones_llega_a_confianza_alta():
    """Contrapunto necesario a los tests anteriores. Verificado en vivo: los
    tres segmentos previos (dos reales, uno ficticio con excepción) salen
    todos con `necesita_revision_humana=true` — el modelo, siguiendo la
    regla 4 del prompt, señala con razón que un artículo-paraguas (11), una
    excepción con cuatro condiciones cualitativas acumuladas (2) o una
    excepción real (el ficticio con umbral) merecen revisión. Es el
    comportamiento correcto, no que el mecanismo esté "atascado" en Baja: un
    artículo genuinamente simple y sin matices sí debe llegar a Alta, y este
    test lo prueba con uno construido para no tener ninguna ambigüedad."""
    if _saltar("test_segmento_ficticio_simple_sin_excepciones_llega_a_confianza_alta"):
        return
    simple = Segmento(
        id="segmento_ficticio_simple", tipo_segmento="articulo",
        titulo="[FICTICIO] Artículo Y. Anchura de puerta",
        capitulo=None,
        texto=(
            "[FICTICIO] La anchura libre de paso en puertas de acceso a vivienda será, "
            "en todo caso, igual o superior a 0,80 m."
        ),
        documento_identificador="FICTICIO-NO-USAR", orden=1,
    )
    bruto = interpretar(simple)
    candidata = _candidata_desde_bruto(bruto, simple, _documento_cte())

    assert candidata.tipo == "exigencia_cuantitativa", bruto
    assert candidata.patron == "UMBRAL_SIMPLE", bruto
    assert candidata.nivel_confianza == "Alta", (candidata.nivel_confianza, candidata.motivos_revision)
    assert candidata.revisar_manualmente is False
    assert candidata.lista_para_promocion is True


def test_pide_revision_humana_ante_ambiguedad_deliberada():
    """Un segmento deliberadamente ambiguo (una remisión sin contenido
    propio) debería hacer que el modelo pida revisión — no que rellene un
    tipo cualquiera con confianza alta para "no dejar el campo vacío"."""
    if _saltar("test_pide_revision_humana_ante_ambiguedad_deliberada"):
        return
    ambiguo = Segmento(
        id="segmento_ficticio_remision", tipo_segmento="articulo",
        titulo="[FICTICIO] Artículo X. Remisión",
        capitulo=None,
        texto="[FICTICIO] Se estará a lo dispuesto en la normativa sectorial que resulte de aplicación.",
        documento_identificador="FICTICIO-NO-USAR", orden=1,
    )
    bruto = interpretar(ambiguo)
    assert bruto.get("necesita_revision_humana") is True or bruto.get("tipo") == "remision", bruto


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
            except Exception as exc:  # noqa: BLE001
                fallos += 1
                print(f"ERROR {nombre}: {type(exc).__name__}: {exc}")
    print(f"\n{'TODO OK' if not fallos else str(fallos) + ' FALLOS'}")
    sys.exit(1 if fallos else 0)
