"""Las 17 validaciones de carga, probadas contra los defectos REALES del motor.

Cada fixture de este fichero reproduce un defecto que
`docs/audits/NORMATIVE_AUDIT.md` encontró en el código de producción. La
pregunta que responde cada test no es "¿el validador funciona?" sino "¿este
validador habría impedido el defecto que ya cometimos?".

Los dos centrales:

- `test_11_*` reproduce el hallazgo M1: la superficie mínima de vivienda es
  competencia autonómica, y el motor la resuelve por tipología emitiendo un
  código estatal. Con este validador, esa regla no entra al corpus.
- `test_12_*` reproduce M1-M5: cinco citas de Documento Básico que no
  corresponden a la materia que regula ese DB.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from normativa import validacion  # noqa: E402
from normativa.loader import cargar  # noqa: E402


def regla_valida() -> dict:
    """Una regla bien formada. Cada test la rompe de UNA manera.

    Los datos son ficticios y están marcados como tales: transcribir normativa
    real contra boletín es la Fase 1 y exige validador colegiado (tarea 18 del
    PRD). Aquí solo se ejercita la maquinaria.
    """
    return {
        "version": 1,
        "norma": {
            "concept_id": "es.ficticia.norma_de_prueba",
            "instance_id": "es.ficticia.norma_de_prueba@1",
            "ambito": "es.13",
            "literal": "TEXTO FICTICIO DE PRUEBA — no es normativa real.",
            "fuente": {
                "rango": "Decreto",
                "organismo": "Organismo de prueba",
                "identificador_oficial": "000/2000",
                "titulo": "Norma ficticia para pruebas del cargador",
                "boletin": "PRUEBA-0000-0",
            },
            "articulo": {"documento_basico": None, "seccion": "1", "apartado": "1"},
            "vigencia": {"vigencia_desde": "2000-01-01"},
        },
        "reglas": [
            {
                "concept_id": "cam.ficticia.habitabilidad.superficie_minima",
                "instance_id": "cam.ficticia.habitabilidad.superficie_minima@1",
                "nombre": "Superficie útil mínima de vivienda (FICTICIA)",
                "materia": "habitabilidad_superficies",
                "tipo": "exigencia_cuantitativa",
                "patron": "UMBRAL_SIMPLE",
                "prioridad": "bloqueante",
                "nivel_de_conocimiento": 2,
                "aplicabilidad": {
                    "ambito": "es.13",
                    "usos": ["residencial"],
                    "tipologias": ["plurifamiliar"],
                },
                "parametro": {
                    "ejes": ["tipologia"],
                    "valores": [{"tipologia": "plurifamiliar", "valor": 30.0}],
                    "repliegue": ["tipologia", "ninguno"],
                    "unidad": "m2",
                },
                "vigencia": {"vigencia_desde": "2000-01-01"},
            }
        ],
    }


def test_00_la_fixture_es_valida():
    """Si la fixture base no valida, los demás tests no prueban nada."""
    assert validacion.validar_fichero(regla_valida()) == []


# --- 1-8 --------------------------------------------------------------------

def test_01_esquema_rechaza_prioridad_numerica():
    """La prioridad NUNCA es un número (`REASONING_ENGINE_SPEC.md` entidad 20)."""
    doc = regla_valida()
    doc["reglas"][0]["prioridad"] = 3
    assert any("[1]" in f for f in validacion.validar_fichero(doc))


def test_01b_sin_boletin_no_hay_norma_citable():
    """Sin boletín no hay NormaFuente, y sin NormaFuente no hay regla activable.

    Es lo que hace imposible que una etiqueta de agrupación (`HABITABILIDAD`,
    `EFICIENCIA`) se presente como código normativo, que es lo que hace hoy
    `evaluator.py`.
    """
    doc = regla_valida()
    doc["norma"]["fuente"]["boletin"] = ""
    fallos = validacion.validar_fichero(doc)
    assert any("boletín" in f for f in fallos)


def test_03_tipo_no_evaluable_no_puede_tener_patron():
    """Una `definicion` con patrón de umbral significa que alguien intentó
    evaluar algo que solo se referencia."""
    doc = regla_valida()
    doc["reglas"][0]["tipo"] = "definicion"
    assert any("[3]" in f and "no es evaluable" in f for f in validacion.validar_fichero(doc))


def test_03_tipo_evaluable_exige_patron():
    doc = regla_valida()
    doc["reglas"][0]["patron"] = None
    assert any("[3]" in f and "no declara patrón" in f for f in validacion.validar_fichero(doc))


def test_04_no_se_puede_derogar_antes_de_entrar_en_vigor():
    doc = regla_valida()
    doc["reglas"][0]["vigencia"] = {"vigencia_desde": "2020-01-01", "vigencia_hasta": "2019-01-01"}
    assert any("[4]" in f for f in validacion.validar_fichero(doc))


def test_07_ningun_umbral_es_un_escalar_desnudo():
    """LOS 41 UMBRALES DE `NORMATIVE_AUDIT.md` §5.2.

    Un parámetro sin cadena de repliegue declarada es el Bug #1 esperando a
    repetirse: cuando no haya valor para el contexto, algo se elegirá en
    silencio.
    """
    doc = regla_valida()
    doc["reglas"][0]["parametro"]["repliegue"] = []
    assert any("[7]" in f for f in validacion.validar_fichero(doc))


def test_07_un_nivel_de_repliegue_inexistente_se_rechaza_con_su_nombre():
    """EL DEFECTO REAL DEL 2026-08-18, reproducido.

    La primera transcripción de `es/estatal/seguridad_incendio.yaml` declaró
    `repliegue: [numero_salidas_y_condicion, numero_salidas, ninguno]`. Ninguno
    de esos dos primeros niveles existe para `Parametro.resolver`, que compara
    cada nivel contra un eje suelto o contra `todos`. La regla se cargó sin
    protestar y luego no resolvía nunca — que desde fuera se lee como «esta
    norma no aplica», la peor respuesta posible.

    El validador tiene que nombrar el nivel culpable: un fallo que no dice cuál
    de los tres niveles sobra obliga a depurar a ojo un YAML de 200 líneas.
    """
    doc = regla_valida()
    doc["reglas"][0]["parametro"]["repliegue"] = ["tipologia_y_uso", "tipologia", "ninguno"]
    fallos = validacion.validar_fichero(doc)
    assert any("[7]" in f and "tipologia_y_uso" in f for f in fallos), fallos


def test_07_un_nivel_valido_pero_sin_fila_propia_tambien_se_rechaza():
    """Que el nombre exista no basta: tiene que haber a dónde replegarse.

    Replegarse a un eje solo recoge las filas indexadas **exactamente** por ese
    eje. Una tabla cuyas filas cruzan siempre dos ejes no admite un repliegue a
    uno solo de ellos: ese nivel es cadena muerta, y la regla vuelve a quedar
    muda sin que nada falle.
    """
    doc = regla_valida()
    doc["reglas"][0]["parametro"].update(
        ejes=["tipologia", "uso"],
        valores=[{"tipologia": "plurifamiliar", "uso": "residencial", "valor": 30.0}],
        repliegue=["tipologia", "ninguno"],
    )
    fallos = validacion.validar_fichero(doc)
    assert any("[7]" in f and "inalcanzable" in f and "tipologia" in f for f in fallos), fallos


def test_07_una_fila_indexada_por_algo_que_no_es_eje_no_la_busca_nadie():
    doc = regla_valida()
    doc["reglas"][0]["parametro"]["valores"] = [
        {"tipologia": "plurifamiliar", "valor": 30.0},
        {"tipologa": "unifamiliar", "valor": 25.0},   # errata de transcripción
    ]
    fallos = validacion.validar_fichero(doc)
    assert any("[7]" in f and "tipologa" in f for f in fallos), fallos


def test_07_detras_de_ninguno_no_hay_nada_que_ejecutar():
    doc = regla_valida()
    doc["reglas"][0]["parametro"]["repliegue"] = ["ninguno", "tipologia"]
    fallos = validacion.validar_fichero(doc)
    assert any("[7]" in f and "cierra la cadena" in f for f in fallos), fallos


def test_07_todos_y_ninguno_siguen_siendo_niveles_validos():
    """La regla real del corpus usa `[todos, ninguno]`: no puede romperse."""
    doc = regla_valida()
    doc["reglas"][0]["parametro"]["repliegue"] = ["todos", "ninguno"]
    assert [f for f in validacion.validar_fichero(doc) if "[7]" in f] == []


def test_08_hash_detecta_deriva_del_literal():
    import hashlib

    doc = regla_valida()
    doc["norma"]["fuente"]["hash_texto"] = hashlib.sha256(b"otro texto").hexdigest()
    assert any("[8]" in f for f in validacion.validar_fichero(doc))


# --- 9-17 -------------------------------------------------------------------

def test_09_ambito_inexistente():
    """Un código INE mal escrito produce una regla que no aplicará nunca a
    nadie y que no da ningún error visible: se queda muda para siempre."""
    doc = regla_valida()
    doc["reglas"][0]["aplicabilidad"]["ambito"] = "es.99"
    assert any("[9]" in f for f in validacion.validar_fichero(doc))


def test_09_municipio_fuera_del_registro():
    doc = regla_valida()
    doc["reglas"][0]["aplicabilidad"]["ambito"] = "es.13.28.28999"
    assert any("[9]" in f and "28999" in f for f in validacion.validar_fichero(doc))


def test_10_materia_fuera_del_catalogo():
    """Si la materia fuera texto libre, la competencia dejaría de ser
    computable y toda la jerarquía territorial se vendría abajo."""
    doc = regla_valida()
    doc["reglas"][0]["materia"] = "habitabilidad"  # etiqueta suelta, no materia
    assert any("[10]" in f for f in validacion.validar_fichero(doc))


def test_11_M1_superficie_minima_no_puede_ser_estatal():
    """EL HALLAZGO M1, impedido por construcción.

    La superficie mínima de vivienda es competencia autonómica exclusiva. Una
    regla estatal que la fije no entra al corpus — y nótese que un modelo de
    "gana la más restrictiva" nunca lo habría detectado, porque presupone que
    ambas capas regulan lo mismo. Aquí no hay dos normas que comparar: hay una
    sola capa competente.
    """
    doc = regla_valida()
    doc["reglas"][0]["aplicabilidad"]["ambito"] = "es"
    fallos = validacion.validar_fichero(doc)
    assert any("[11]" in f for f in fallos), fallos
    assert any("competencia autonomico" in f or "competencia autonómica" in f.lower() for f in fallos)


def test_11_superficie_minima_tampoco_puede_ser_municipal():
    doc = regla_valida()
    doc["reglas"][0]["aplicabilidad"]["ambito"] = "es.13.28.28115"
    assert any("[11]" in f for f in validacion.validar_fichero(doc))


def test_11_urbanismo_si_es_municipal():
    """La contraparte: los parámetros urbanísticos SÍ son municipales, y una
    regla municipal de urbanismo debe pasar."""
    doc = regla_valida()
    doc["reglas"][0]["materia"] = "urbanismo_parametros"
    doc["reglas"][0]["aplicabilidad"]["ambito"] = "es.13.28.28115"
    assert not [f for f in validacion.validar_fichero(doc) if "[11]" in f]


def test_11_incendio_estatal_con_endurecimiento_municipal():
    """Materia con modo `suelo`: el municipio SÍ puede endurecer el DB-SI."""
    doc = regla_valida()
    doc["reglas"][0]["materia"] = "seguridad_incendio"
    doc["norma"]["articulo"]["documento_basico"] = "DB-SI"
    doc["reglas"][0]["aplicabilidad"]["ambito"] = "es.13.28.28115"
    assert not [f for f in validacion.validar_fichero(doc) if "[11]" in f]


def test_11_estructural_no_admite_endurecimiento():
    """`seguridad_estructural` declara `permite_endurecer: []`: ninguna capa
    inferior puede tocarla."""
    doc = regla_valida()
    doc["reglas"][0]["materia"] = "seguridad_estructural"
    doc["norma"]["articulo"]["documento_basico"] = "DB-SE"
    doc["reglas"][0]["aplicabilidad"]["ambito"] = "es.13"
    assert any("[11]" in f for f in validacion.validar_fichero(doc))


def test_12_M1_M5_citar_un_DB_que_no_regula_la_materia():
    """LAS 5 DISCREPANCIAS M1-M5, impedidas por construcción.

    Hoy nada impide emitir `CTE-DB-HE` (ahorro de energía) para una regla de
    superficie mínima de vivienda. El CTE no regula esa materia en absoluto:
    `materias.yaml` la declara con `documentos_basicos: []` y esta validación
    lo convierte en un error de carga.
    """
    doc = regla_valida()
    doc["norma"]["articulo"]["documento_basico"] = "DB-HE"
    fallos = validacion.validar_fichero(doc)
    assert any("[12]" in f and "ningún Documento Básico" in f for f in fallos), fallos


def test_12_DB_equivocado_para_la_materia():
    """Accesibilidad se regula en DB-SUA, no en DB-HR."""
    doc = regla_valida()
    doc["reglas"][0]["materia"] = "accesibilidad"
    doc["reglas"][0]["aplicabilidad"]["ambito"] = "es"
    doc["norma"]["articulo"]["documento_basico"] = "DB-HR"
    assert any("[12]" in f for f in validacion.validar_fichero(doc))


def test_13_uso_inventado_no_filtra_nada():
    """Un uso escrito a mano que no está en el árbol haría que la regla
    aplicara a todo o a nada sin que nadie se entere."""
    doc = regla_valida()
    doc["reglas"][0]["aplicabilidad"]["usos"] = ["vivienda"]  # el nodo es "residencial"
    assert any("[13]" in f for f in validacion.validar_fichero(doc))


def test_13_tipologia_inventada():
    doc = regla_valida()
    doc["reglas"][0]["aplicabilidad"]["tipologias"] = ["rehabilitacion"]  # es intervención
    assert any("[13]" in f for f in validacion.validar_fichero(doc))


def test_14_dos_reglas_compitiendo_fallan_en_carga():
    """Si dos reglas del mismo nivel, materia y perfil se solapan, el resolver
    tendría que desempatar — y cualquier desempate no declarado (orden de
    carga, alfabético) es un criterio oculto disfrazado de determinismo
    (`CONFLICT_ENGINE.md` §2). Se prohíbe en carga, no en ejecución.
    """
    a = regla_valida()
    b = copy.deepcopy(regla_valida())
    b["reglas"][0]["concept_id"] = "cam.ficticia.habitabilidad.superficie_minima_bis"
    b["reglas"][0]["instance_id"] = "cam.ficticia.habitabilidad.superficie_minima_bis@1"
    assert any("[14]" in f for f in validacion.validar_corpus([a, b]))


def test_14_no_compiten_si_cambia_el_perfil():
    a = regla_valida()
    b = copy.deepcopy(regla_valida())
    b["reglas"][0]["concept_id"] = "cam.ficticia.habitabilidad.superficie_minima_uni"
    b["reglas"][0]["instance_id"] = "cam.ficticia.habitabilidad.superficie_minima_uni@1"
    b["reglas"][0]["aplicabilidad"]["tipologias"] = ["unifamiliar_aislada"]
    assert not [f for f in validacion.validar_corpus([a, b]) if "[14]" in f]


def test_15_arista_rota():
    doc = regla_valida()
    doc["reglas"][0]["aristas"] = [{"tipo": "remite_a", "destino": "es.no.existe"}]
    assert any("[15]" in f for f in validacion.validar_corpus([doc]))


def test_15_ciclo_de_derogaciones():
    """Un ciclo de derogaciones no es una situación legal: es un error de
    transcripción, y debe fallar la carga."""
    a = regla_valida()
    a["reglas"][0]["aristas"] = [{"tipo": "deroga", "destino": "cam.ficticia.b"}]
    b = copy.deepcopy(regla_valida())
    b["reglas"][0]["concept_id"] = "cam.ficticia.b"
    b["reglas"][0]["instance_id"] = "cam.ficticia.b@1"
    b["reglas"][0]["aplicabilidad"]["tipologias"] = ["unifamiliar_aislada"]
    b["reglas"][0]["aristas"] = [
        {"tipo": "deroga", "destino": "cam.ficticia.habitabilidad.superficie_minima"}
    ]
    assert any("ciclo" in f for f in validacion.validar_corpus([a, b]))


def test_16_regla_sin_nivel_de_conocimiento():
    """Sin nivel de conocimiento, `EVIDENCE_MODEL.md` §3 no puede calcular la
    fuerza del tramo y la cadena de confianza se queda sin primer eslabón."""
    doc = regla_valida()
    doc["reglas"][0]["nivel_de_conocimiento"] = 7
    assert any("[16]" in f for f in validacion.validar_fichero(doc))


def test_17_cobertura_declarada_sin_respaldo_en_disco():
    """Declarar cobertura que no existe es el error peligroso: el informe
    afirmaría más de lo que sabe."""
    manifiesto = {
        "cobertura": [{"ambito": "es.13", "materias": {"habitabilidad_superficies": {"estado": "completo"}}}]
    }
    fallos = validacion.validar_cobertura(manifiesto, ambitos_en_disco={})
    assert any("[17]" in f and "no hay ninguna regla" in f for f in fallos)


def test_17_cobertura_en_disco_sin_declarar():
    """El error opuesto: hay trabajo hecho y el usuario cree que no lo hay."""
    manifiesto = {"cobertura": [{"ambito": "es.13", "materias": {}}]}
    fallos = validacion.validar_cobertura(
        manifiesto, ambitos_en_disco={"es.13": {"habitabilidad_superficies"}}
    )
    assert any("[17]" in f and "no declara su cobertura" in f for f in fallos)


# --- Loader -----------------------------------------------------------------

def test_loader_es_fail_closed(tmp_path=None):
    """Lo que este test protege es el *fail-closed*: un fichero inválido no
    entra a medias, y lo que entra ha pasado las validaciones enteras.

    Se escribió cuando el corpus estaba vacío, y por eso comprobaba
    `reglas == []`. Desde la tarea V0-5 hay una regla real transcrita, así que
    el corpus vacío ya no es la condición — pero el invariante sí: cero
    rechazos, y todo lo cargado con su `concept_id` y su vigencia.
    """
    resultado = cargar(["es"])
    assert not resultado.hay_rechazos, resultado.rechazados
    for regla in resultado.reglas:
        assert regla.get("concept_id"), regla
        assert (regla.get("vigencia") or {}).get("vigencia_desde"), regla


def test_lo_declarado_y_lo_que_hay_en_disco_coinciden():
    """El invariante que sustituye a «el corpus está vacío».

    Se escribió cuando lo estaba, y comprobaba `cobertura == []`. Desde el
    2026-08-19 el manifiesto declara la única materia transcrita, así que lo
    que hay que sostener ya no es la lista vacía sino la correspondencia: ni
    declarar cobertura que no existe —el informe afirmaría más de lo que sabe—
    ni tener reglas sin declararlas. Este test corre sobre el corpus **de
    producción**, no sobre el fixture: la versión que solo miraba el fixture es
    la razón de que el desajuste real pasara desapercibido.
    """
    from normativa.manifiesto import _manifiesto

    resultado = cargar(["es"])
    fallos = validacion.validar_cobertura(_manifiesto(), resultado.materias_por_ambito)
    assert not fallos, fallos


def test_ninguna_materia_del_corpus_se_declara_completa_todavia():
    """`completo` es una frase de venta —«este Documento Básico lo cubrimos»—
    y hoy ninguna materia se la ha ganado. La cierra `NOR-2`, con la entrega
    del curador que la justifique; hasta entonces esto tiene que fallar si
    alguien la escribe."""
    from normativa.manifiesto import _manifiesto

    for entrada in _manifiesto().get("cobertura") or []:
        for materia, estado in (entrada.get("materias") or {}).items():
            e = estado.get("estado") if isinstance(estado, dict) else estado
            assert e != "completo", (entrada["ambito"], materia)


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


# --- 17 · El recorrido va sobre la unión, no sobre lo declarado ------------
#
# Encontrado el 2026-08-19 sobre el corpus de producción: tenía una regla de
# `seguridad_incendio` en disco y `cobertura: []` en el manifiesto, y la
# validación respondía que todo cuadraba. El segundo recorrido —«hay reglas sin
# declarar»— vivía dentro del bucle sobre lo declarado, así que un ámbito sin
# entrada en el manifiesto no se miraba nunca. Es justo el error que comete
# quien EMPIEZA a transcribir, que es todo el trabajo que queda por delante.

def test_un_ambito_con_reglas_y_sin_entrada_en_el_manifiesto_se_detecta():
    fallos = validacion.validar_cobertura(
        {"cobertura": []}, ambitos_en_disco={"es": {"seguridad_incendio"}})
    assert len(fallos) == 1
    assert "seguridad_incendio" in fallos[0]
    assert "no declara su cobertura" in fallos[0]


def test_el_manifiesto_vacio_con_el_disco_vacio_sigue_estando_bien():
    """El estado inicial legítimo: nada transcrito, nada declarado."""
    assert validacion.validar_cobertura({"cobertura": []}, ambitos_en_disco={}) == []


def test_se_detectan_varios_ambitos_sin_declarar_a_la_vez():
    fallos = validacion.validar_cobertura({"cobertura": []}, ambitos_en_disco={
        "es": {"seguridad_incendio"},
        "es.13": {"habitabilidad", "accesibilidad"},
    })
    assert len(fallos) == 3


def test_declarar_de_mas_sigue_detectandose_donde_ya_lo_hacia():
    """El otro sentido no se ha perdido al cambiar el recorrido: es el
    peligroso, porque hace que el informe afirme más de lo que sabe."""
    fallos = validacion.validar_cobertura(
        {"cobertura": [{"ambito": "es", "materias": {"accesibilidad": "completo"}}]},
        ambitos_en_disco={})
    assert len(fallos) == 1 and "no hay ninguna regla" in fallos[0]

