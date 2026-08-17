"""Ingesta Fase 1: conector BOE, detección de cambios, almacén versionado.

Deterministas contra fixtures REALES grabados el 2026-08-06
(`tests/fixtures/boe/`) — nada inventado: `BOE-A-2006-5515` es el Código
Técnico de la Edificación de verdad, y `sumario-20260805.json` es un recorte
de una respuesta real del servicio (recortado en tamaño, no en forma: se
conservan a propósito las dos variantes estructurales que el BOE usa según
la sección — ver `ingesta/fuentes/boe.py`).

Un test aparte, no deterministic, comprueba contra el servicio EN VIVO —
saltado por defecto, solo corre si `ARCHMUSE_TEST_RED=1` está en el entorno.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ingesta import almacen, pipeline  # noqa: E402
from ingesta.errores import DocumentoIlegible, ErrorDeRed, ErrorIngesta  # noqa: E402
from ingesta.fuentes.base import FuenteOficial  # noqa: E402
from ingesta.fuentes.boe import FuenteBOE  # noqa: E402
from ingesta.modelo import DocumentoOficial, ItemSumario, como_lista  # noqa: E402

FIXTURES = RAIZ / "tests" / "fixtures" / "boe"
SUMARIO_REAL = (FIXTURES / "sumario-20260805.json").read_bytes()
CTE_REAL = (FIXTURES / "BOE-A-2006-5515.xml").read_bytes()


# --- como_lista: la trampa central del formato ------------------------------

def test_como_lista_normaliza_los_tres_casos():
    assert como_lista(None) == []
    assert como_lista({"a": 1}) == [{"a": 1}]
    assert como_lista([{"a": 1}, {"a": 2}]) == [{"a": 1}, {"a": 2}]


# --- Parseo del sumario, contra una respuesta real --------------------------

def test_parseo_de_sumario_real_recupera_los_tres_items():
    """El fixture conserva a propósito las dos formas de anidar `epigrafe`
    que el BOE usa de verdad (`departamento.texto.epigrafe` en la sección 1,
    `departamento.epigrafe` directo en la 2A) y un `departamento` en forma de
    lista (2 elementos) junto a uno en forma de objeto (1 elemento, sección 1).
    Si el parser asumiera una sola forma, perdería items en silencio — este
    test falla exactamente así si alguien simplifica `_items_de_departamento`."""
    boe = FuenteBOE()
    items = boe._items_desde_json(SUMARIO_REAL, date(2026, 8, 5))
    ids = {i.identificador for i in items}
    assert ids == {"BOE-A-2026-17003", "BOE-A-2026-17004", "BOE-A-2026-17005"}

    disposicion = next(i for i in items if i.identificador == "BOE-A-2026-17003")
    assert disposicion.seccion_codigo == "1"
    assert disposicion.seccion_nombre == "I. Disposiciones generales"
    assert disposicion.epigrafe == "Contaminación atmosférica. Subvenciones"
    assert disposicion.url_xml == "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2026-17003"

    nombramiento = next(i for i in items if i.identificador == "BOE-A-2026-17004")
    assert nombramiento.seccion_codigo == "2A"
    assert nombramiento.departamento_nombre.startswith("MINISTERIO DE LA PRESIDENCIA")


def test_dia_sin_boletin_es_lista_vacia_no_error():
    """`status.code` distinto de "200" (festivo, sin publicación) no es un
    fallo de red: es un hecho del calendario. `ErrorDeRed` debe reservarse
    para cuando la fuente de verdad no responde, no para cuando responde que
    no hay nada."""
    sin_boletin = b'{"status": {"code": "404", "text": "No hay sumario para esa fecha"}, "data": {}}'
    boe = FuenteBOE()
    assert boe._items_desde_json(sin_boletin, date(2026, 1, 1)) == []


def test_sumario_json_roto_es_documentoilegible():
    boe = FuenteBOE()
    try:
        boe._items_desde_json(b"esto no es json", date(2026, 1, 1))
    except DocumentoIlegible:
        pass
    else:
        raise AssertionError("un sumario ilegible debe fallar explícito, no devolver lista vacía")


# --- Parseo del documento individual, contra el CTE real --------------------

def test_parseo_del_cte_real():
    """`BOE-A-2006-5515` es el Real Decreto 314/2006 que aprueba el CTE — el
    documento que ya está citado por nombre en `normativa/esquema/materias.yaml`.
    Verifica que los metadatos que la Fase 5 (promoción) necesitará mapear a
    `normativa.modelo.Fuente` salen completos y correctos."""
    boe = FuenteBOE()
    doc = boe._documento_desde_xml(
        "BOE-A-2006-5515", "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2006-5515", CTE_REAL
    )
    assert doc.identificador == "BOE-A-2006-5515"
    assert doc.rango_codigo == "1340"
    assert doc.rango_nombre == "Real Decreto"
    assert doc.numero_oficial == "314/2006"
    assert doc.organismo == "Ministerio de Vivienda"
    assert doc.fecha_publicacion == "20060328"
    assert doc.titulo.startswith("Real Decreto 314/2006")
    assert doc.url_oficial == "https://www.boe.es/eli/es/rd/2006/03/17/314"
    assert doc.fecha_actualizacion  # el BOE declara cuándo se actualizó la consolidación
    assert len(doc.hash_texto) == 64  # sha256 hex


def test_documento_xml_roto_es_documentoilegible():
    boe = FuenteBOE()
    try:
        boe._documento_desde_xml("X", "https://ejemplo.invalid", b"<no cierra")
    except DocumentoIlegible:
        pass
    else:
        raise AssertionError("un XML roto debe fallar explícito")


def test_hash_es_determinista_y_sensible_al_contenido():
    boe = FuenteBOE()
    a = boe._documento_desde_xml("X", "u", CTE_REAL)
    b = boe._documento_desde_xml("X", "u", CTE_REAL)
    assert a.hash_texto == b.hash_texto
    otro = boe._documento_desde_xml("X", "u", CTE_REAL.replace(b"314/2006", b"999/9999"))
    assert otro.hash_texto != a.hash_texto


# --- Almacén: versionado y detección de cambios -----------------------------

def _doc(identificador="BOE-A-2006-5515", hash_texto="a" * 64, texto="contenido"):
    return DocumentoOficial(
        identificador=identificador, fuente="boe", titulo="t", organismo="o",
        rango_codigo="1340", rango_nombre="Real Decreto", numero_oficial="314/2006",
        fecha_publicacion="20060328", fecha_disposicion="20060317",
        fecha_actualizacion="20260101000000",
        url_oficial="https://ejemplo.invalid", url_xml="https://ejemplo.invalid/xml",
        texto_crudo=texto, hash_texto=hash_texto,
    )


def _tmp_raiz():
    return Path(tempfile.mkdtemp(prefix="archmuse_ingesta_"))


def test_primera_descarga_es_nueva():
    raiz = _tmp_raiz()
    try:
        r = almacen.registrar(_doc(), raiz)
        assert r.estado == "nuevo"
        assert r.hash_anterior is None
        assert r.ruta_cache == "cache/boe__BOE-A-2006-5515__" + "a" * 12 + ".xml"
        assert (raiz / r.ruta_cache).exists()
    finally:
        shutil.rmtree(raiz, ignore_errors=True)


def test_misma_descarga_dos_veces_es_sin_cambios_y_no_duplica_cache():
    raiz = _tmp_raiz()
    try:
        r1 = almacen.registrar(_doc(hash_texto="h1"), raiz)
        r2 = almacen.registrar(_doc(hash_texto="h1"), raiz)
        assert r1.estado == "nuevo"
        assert r2.estado == "sin_cambios"
        assert r2.ruta_cache is None  # no se vuelve a guardar el crudo
        cache = raiz / "cache"
        assert len(list(cache.glob("*.xml"))) == 1
    finally:
        shutil.rmtree(raiz, ignore_errors=True)


def test_hash_distinto_es_modificado_y_conserva_ambas_versiones():
    """Versionar de verdad: la versión anterior no se pisa."""
    raiz = _tmp_raiz()
    try:
        almacen.registrar(_doc(hash_texto="h1", texto="version 1"), raiz)
        r2 = almacen.registrar(_doc(hash_texto="h2", texto="version 2"), raiz)
        assert r2.estado == "modificado"
        assert r2.hash_anterior == "h1"
        cache = raiz / "cache"
        assert len(list(cache.glob("*.xml"))) == 2
        historial = almacen.historial("BOE-A-2006-5515", "boe", raiz)
        assert [h["estado"] for h in historial] == ["nuevo", "modificado"]
        assert [h["hash_nuevo"] for h in historial] == ["h1", "h2"]
    finally:
        shutil.rmtree(raiz, ignore_errors=True)


def test_documentos_distintos_no_interfieren():
    raiz = _tmp_raiz()
    try:
        almacen.registrar(_doc(identificador="A", hash_texto="h1"), raiz)
        r = almacen.registrar(_doc(identificador="B", hash_texto="h1"), raiz)
        assert r.estado == "nuevo"  # "B" nunca se ha visto, aunque "A" tenga el mismo hash
    finally:
        shutil.rmtree(raiz, ignore_errors=True)


def test_ledger_es_legible_linea_a_linea():
    """Es el requisito de diseño: un PR con el ledger debe poder revisarse
    como texto, no como un blob opaco."""
    raiz = _tmp_raiz()
    try:
        almacen.registrar(_doc(hash_texto="h1"), raiz)
        contenido = (raiz / "ledger.jsonl").read_text(encoding="utf-8")
        assert contenido.count("\n") == 1
        assert '"identificador": "BOE-A-2006-5515"' in contenido
    finally:
        shutil.rmtree(raiz, ignore_errors=True)


# --- Pipeline: orquestación con una fuente falsa (sin red) ------------------

class _FuenteFalsa(FuenteOficial):
    """Doble de prueba: no toca la red, sirve items y documentos fijados a
    mano. Prueba `pipeline.py` de forma aislada de si el conector real de
    BOE funciona o no — ambas cosas se prueban por separado."""

    id = "falsa"

    def __init__(self, items, documentos):
        self._items = items
        self._documentos = documentos

    def listar_sumario(self, fecha):
        return self._items

    def descargar_documento(self, item):
        if item.identificador not in self._documentos:
            raise ErrorDeRed(item.url_xml or "?", RuntimeError("404 simulado"))
        return self._documentos[item.identificador]


def _item(identificador, seccion_codigo="1"):
    return ItemSumario(
        identificador=identificador, titulo=f"Título de {identificador}", fuente="falsa",
        fecha_publicacion="20260805", seccion_codigo=seccion_codigo,
        seccion_nombre="I. Disposiciones generales", departamento_codigo="1",
        departamento_nombre="Ministerio de prueba", epigrafe=None,
        url_html=None, url_pdf=None, url_xml=f"https://ejemplo.invalid/{identificador}",
    )


def test_pipeline_filtra_por_seccion_por_defecto():
    """El filtro por defecto (solo sección "1") es lo que evita el barrido
    masivo: un item de sección "2A" (nombramientos) se lista pero no se
    descarga."""
    disposicion = _item("A", seccion_codigo="1")
    nombramiento = _item("B", seccion_codigo="2A")
    fuente = _FuenteFalsa(
        [disposicion, nombramiento],
        {"A": _doc(identificador="A", hash_texto="ha"), "B": _doc(identificador="B", hash_texto="hb")},
    )
    raiz = _tmp_raiz()
    try:
        r = pipeline.ingerir_fecha(fuente, date(2026, 8, 5), raiz_almacen=raiz)
        assert r.items_filtrados == 1
        assert len(r.descargas) == 1
        assert r.descargas[0].identificador == "A"
    finally:
        shutil.rmtree(raiz, ignore_errors=True)


def test_pipeline_sin_filtro_descarga_todo():
    disposicion = _item("A", seccion_codigo="1")
    nombramiento = _item("B", seccion_codigo="2A")
    fuente = _FuenteFalsa(
        [disposicion, nombramiento],
        {"A": _doc(identificador="A", hash_texto="ha"), "B": _doc(identificador="B", hash_texto="hb")},
    )
    raiz = _tmp_raiz()
    try:
        r = pipeline.ingerir_fecha(fuente, date(2026, 8, 5), solo_secciones=None, raiz_almacen=raiz)
        assert r.items_filtrados == 0
        assert len(r.descargas) == 2
    finally:
        shutil.rmtree(raiz, ignore_errors=True)


def test_pipeline_registra_aviso_si_un_documento_falla_y_sigue_con_los_demas():
    """Un documento que no se puede traer no aborta la ingesta del día
    entero: se avisa y se sigue — el mismo principio fail-closed-por-unidad
    que ya usa `normativa/loader.py` con ficheros de corpus inválidos."""
    ok = _item("A")
    roto = _item("C")  # no está en el diccionario de documentos de la fuente falsa
    fuente = _FuenteFalsa([ok, roto], {"A": _doc(identificador="A", hash_texto="ha")})
    raiz = _tmp_raiz()
    try:
        r = pipeline.ingerir_fecha(fuente, date(2026, 8, 5), raiz_almacen=raiz)
        assert len(r.descargas) == 1
        assert len(r.avisos) == 1
        assert "C" in r.avisos[0]
    finally:
        shutil.rmtree(raiz, ignore_errors=True)


def test_ingerir_documento_directo_por_id():
    """El camino usado para traer el CTE sin escanear ningún sumario."""
    boe_falso = _FuenteFalsa([], {})
    boe_falso.descargar_por_id = lambda identificador: _doc(identificador=identificador, hash_texto="hcte")
    raiz = _tmp_raiz()
    try:
        r = pipeline.ingerir_documento(boe_falso, "BOE-A-2006-5515", raiz_almacen=raiz)
        assert r.estado == "nuevo"
        assert r.identificador == "BOE-A-2006-5515"
    finally:
        shutil.rmtree(raiz, ignore_errors=True)


def test_ingerir_documento_sin_soporte_de_id_directo_falla_explicito():
    class _SinIdDirecto(FuenteOficial):
        id = "sin_id"
        def listar_sumario(self, fecha):
            return []
        def descargar_documento(self, item):
            raise NotImplementedError

    try:
        pipeline.ingerir_documento(_SinIdDirecto(), "X")
    except ErrorIngesta:
        pass
    else:
        raise AssertionError("una fuente sin descarga directa por id debe fallar explícito")


# --- Rango de fechas ---------------------------------------------------------

def test_ingerir_rango_recorre_cada_dia():
    llamadas = []

    class _Contador(_FuenteFalsa):
        def listar_sumario(self, fecha):
            llamadas.append(fecha)
            return []

    raiz = _tmp_raiz()
    try:
        pipeline.ingerir_rango(_Contador([], {}), date(2026, 8, 1), date(2026, 8, 3), raiz_almacen=raiz)
        assert llamadas == [date(2026, 8, 1), date(2026, 8, 2), date(2026, 8, 3)]
    finally:
        shutil.rmtree(raiz, ignore_errors=True)


def test_ingerir_rango_invertido_falla_explicito():
    try:
        pipeline.ingerir_rango(_FuenteFalsa([], {}), date(2026, 8, 5), date(2026, 8, 1))
    except ValueError:
        pass
    else:
        raise AssertionError("un rango con hasta < desde debe rechazarse, no recorrer al revés en silencio")


# --- Prueba opcional contra el servicio EN VIVO ------------------------------

def test_conector_real_contra_boe_en_vivo():
    """Saltada por defecto — determinismo y velocidad de la suite no deben
    depender de que boe.es esté arriba. Se activa a mano con
    ARCHMUSE_TEST_RED=1 para confirmar que el conector sigue funcionando
    contra el servicio real, no solo contra los fixtures grabados."""
    if os.environ.get("ARCHMUSE_TEST_RED") != "1":
        print("  [SALTADO] define ARCHMUSE_TEST_RED=1 para probar contra boe.es en vivo")
        return
    boe = FuenteBOE()
    doc = boe.descargar_por_id("BOE-A-2006-5515")
    assert doc.identificador == "BOE-A-2006-5515"
    assert doc.rango_nombre == "Real Decreto"
    assert doc.numero_oficial == "314/2006"


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
