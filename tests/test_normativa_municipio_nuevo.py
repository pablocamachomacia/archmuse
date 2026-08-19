"""Criterio de aceptación 5: añadir un municipio NO toca código.

Es la promesa central del encargo y la más fácil de perder sin darse cuenta:
basta con que alguien añada un `if` en el cargador "solo para este caso" y a
partir de ahí cada municipio nuevo cuesta una release.

El test crea un municipio con corpus **en el árbol real**, comprueba que el
cargador lo descubre, lo valida y lo indexa sin que exista ninguna línea de
código que lo mencione, y lo borra. Si el cargador tuviera algo hardcodeado,
este test fallaría.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from normativa import indice  # noqa: E402
from normativa.loader import cargar, descubrir  # noqa: E402
from normativa.registro import registro  # noqa: E402

# Madrid capital: está en el registro geográfico pero no tiene corpus. Es el
# caso exacto que interesa — el registro conoce 8.131 municipios y el corpus
# cubre unos pocos, y esa asimetría tiene que funcionar.
DIR_MUNICIPIO = RAIZ / "normativa" / "es" / "13-madrid" / "municipios" / "28079-madrid"

ORDENANZA = """\
# FICHERO DE PRUEBA generado por tests/test_normativa_municipio_nuevo.py.
# Contenido FICTICIO: no es normativa real. Transcribir normativa de verdad
# exige boletín y validador colegiado (Fase 1, tarea 18 del PRD).
version: 1
norma:
  concept_id: mad.ficticia.ordenanza_de_prueba
  instance_id: mad.ficticia.ordenanza_de_prueba@1
  ambito: es.13.28.28079
  literal: TEXTO FICTICIO DE PRUEBA.
  fuente:
    rango: Ordenanza
    organismo: Organismo de prueba
    identificador_oficial: 000/2000
    titulo: Ordenanza ficticia para pruebas
    boletin: PRUEBA-0000-0
  articulo:
    documento_basico: null
    seccion: "1"
  vigencia:
    vigencia_desde: 2000-01-01
reglas:
  - concept_id: mad.ficticia.urbanismo.ocupacion_maxima
    instance_id: mad.ficticia.urbanismo.ocupacion_maxima@1
    nombre: Ocupación máxima de parcela (FICTICIA)
    materia: urbanismo_parametros
    tipo: exigencia_cuantitativa
    patron: UMBRAL_SIMPLE
    prioridad: bloqueante
    nivel_de_conocimiento: 2
    aplicabilidad:
      ambito: es.13.28.28079
      usos: [residencial]
    parametro:
      ejes: [tipologia]
      valores:
        - {tipologia: plurifamiliar, valor: 60.0}
      repliegue: [tipologia, ninguno]
      unidad: pct
    vigencia:
      vigencia_desde: 2000-01-01
"""


def _crear_municipio() -> None:
    (DIR_MUNICIPIO / "ordenanzas").mkdir(parents=True, exist_ok=True)
    (DIR_MUNICIPIO / "_ambito.yaml").write_text(
        "ambito: es.13.28.28079\nnombre: Madrid\nverificado: false\n", encoding="utf-8"
    )
    (DIR_MUNICIPIO / "ordenanzas" / "urbanismo_parametros.yaml").write_text(
        ORDENANZA, encoding="utf-8"
    )


def _borrar_municipio() -> None:
    if DIR_MUNICIPIO.exists():
        shutil.rmtree(DIR_MUNICIPIO)
    padre = DIR_MUNICIPIO.parent
    for d in (padre, padre.parent):
        if d.exists() and not any(d.iterdir()):
            d.rmdir()


def test_municipio_nuevo_se_descubre_valida_e_indexa():
    """El ciclo completo, sin tocar una línea de Python."""
    _borrar_municipio()
    try:
        # Antes: el municipio existe en el registro, pero no tiene corpus.
        assert "28079" in registro().municipios
        assert cargar(["es.13.28.28079"]).reglas == []

        _crear_municipio()

        # Descubrimiento: el cargador encuentra el fichero por la estructura
        # del árbol, no por una lista de municipios activos.
        rutas = descubrir(["es.13.28.28079"])
        assert len(rutas) == 1, rutas

        # Validación: las 17 pasan sobre un fichero que nadie había visto.
        resultado = cargar(["es.13.28.28079"])
        assert not resultado.hay_rechazos, resultado.rechazados
        assert len(resultado.reglas) == 1
        assert resultado.reglas[0]["concept_id"] == "mad.ficticia.urbanismo.ocupacion_maxima"

        # El ámbito se deduce de la ubicación en el árbol, no de un registro
        # central: el directorio lleva código y slug, y manda el código.
        assert resultado.ficheros[0].ambito == "es.13.28.28079"

        # Indexado. `reconstruir()` sin ámbitos recorre el corpus ENTERO, así
        # que cuenta también la regla piloto de `es/estatal/` que la tarea V0-5
        # incorporó (antes de ella el corpus estaba vacío y este número era 1).
        # Se comprueba el incremento y no el total, para que la cifra no vuelva
        # a caducar con cada entrega del curador.
        n_con_municipio = indice.reconstruir()
        _borrar_municipio()
        n_sin_municipio = indice.reconstruir()
        assert n_con_municipio - n_sin_municipio == 1, (
            f"el municipio nuevo debe aportar exactamente 1 regla al indice "
            f"(con={n_con_municipio}, sin={n_sin_municipio})")
    finally:
        _borrar_municipio()
        indice.reconstruir()


def test_el_slug_del_directorio_puede_cambiar_sin_romper_nada():
    """La identidad es el código INE; el slug es para el humano que navega el
    repositorio. Renombrar el directorio no puede afectar a la resolución."""
    _borrar_municipio()
    try:
        _crear_municipio()
        antes = cargar(["es.13.28.28079"])
        assert len(antes.reglas) == 1

        renombrado = DIR_MUNICIPIO.parent / "28079-madrid-capital-nombre-nuevo"
        DIR_MUNICIPIO.rename(renombrado)
        try:
            despues = cargar(["es.13.28.28079"])
            assert len(despues.reglas) == 1
            assert despues.ficheros[0].ambito == "es.13.28.28079"
        finally:
            renombrado.rename(DIR_MUNICIPIO)
    finally:
        _borrar_municipio()
        indice.reconstruir()


def test_un_fichero_invalido_no_entra_a_medias():
    """Fail-closed: si el corpus del municipio está roto, esa materia queda
    sin cobertura. Nunca se carga «lo que sí funciona»: un informe que afirma
    cumplimiento sobre un corpus mutilado sin que nadie lo sepa es el peor
    resultado posible."""
    _borrar_municipio()
    try:
        _crear_municipio()
        roto = ORDENANZA.replace("materia: urbanismo_parametros", "materia: inventada")
        (DIR_MUNICIPIO / "ordenanzas" / "urbanismo_parametros.yaml").write_text(roto, encoding="utf-8")

        resultado = cargar(["es.13.28.28079"])
        assert resultado.hay_rechazos
        assert resultado.reglas == []
        fallos = next(iter(resultado.rechazados.values()))
        assert any("[10]" in f for f in fallos)

        # Y la materia rota se puede nombrar, que es lo que alimenta el
        # estado `sin_cobertura` del informe.
        assert ("es.13.28.28079", "urbanismo_parametros") in resultado.materias_sin_cobertura_por_fallo()
    finally:
        _borrar_municipio()
        indice.reconstruir()


def test_carga_perezosa_no_abre_el_corpus_entero():
    """El coste de carga depende de la cadena del proyecto, no del tamaño del
    corpus. Es la propiedad sin la cual 8.131 municipios sí serían un
    problema."""
    _borrar_municipio()
    try:
        _crear_municipio()
        # Pedir solo el estatal no abre el fichero del municipio.
        assert descubrir(["es"]) == [] or all(
            "28079" not in str(r) for r in descubrir(["es"])
        )
        assert len(descubrir(["es.13.28.28079"])) == 1
    finally:
        _borrar_municipio()
        indice.reconstruir()


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_"):
            try:
                fn()
                print(f"OK   {nombre}")
            except AssertionError as exc:
                fallos += 1
                print(f"FALLO {nombre}: {str(exc)[:200]}")
    print(f"\n{'TODO OK' if not fallos else str(fallos) + ' FALLOS'}")
    sys.exit(1 if fallos else 0)
