"""Prompt 1 (docs/prd/2026-08-21-pipeline-borradores-corpus-db-sua.md) y su
paso de descomposición (docs/prd/2026-08-21-descomposicion-de-candidatas-
compuestas.md).

Golden tests contra las candidatas REALES de DB-SUA
(`extraccion/estado/candidatas/codigotecnico__DB-SUA__3cfb5bbb135e.jsonl`),
no contra fixtures inventadas: el criterio de terminado de ambos prompts es
«corre offline sobre las candidatas reales», y el resultado (qué se
convierte y qué se descarta, y por qué) es tan parte del contrato como el
código que lo produce.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extraccion import almacen  # noqa: E402
from normativa.validacion import validar_fichero  # noqa: E402
from scripts.generar_borrador_corpus import _decidir, _descomponer, _numero, procesar  # noqa: E402

CANDIDATAS = RAIZ / "extraccion" / "estado" / "candidatas" / "codigotecnico__DB-SUA__3cfb5bbb135e.jsonl"

# Las 7 sub-candidatas que la descomposición consigue convertir de las 20
# candidatas reales de DB-SUA. Es el resultado esperado, no un mínimo — si
# cambia, algo en la clasificación o en la descomposición cambió y este test
# debe fallar para que se note. Dos de ellas (resalto/diámetro) vienen del
# MISMO artículo compuesto (DB-SUA 1.2) partido en dos cláusulas
# independientes — la prueba de que la descomposición funciona.
#
# DB-SUA 7.2 y 7.3 tuvieron una sub-candidata que localizó un solo
# `parametro` en su cláusula pero la cláusula citaba una segunda cifra sin
# anclar (la pendiente 5% junto a la profundidad 4,5m en 7.2; la capacidad
# >200 veh. junto a la superficie >5000 m² en 7.3, una disyunción real —
# ver `test_no_convierte_capacidad_aparcamiento_sola_por_ser_mitad_de_una_disyuncion`).
# `_contar_cifras_de_umbral` las corta antes de convertir: quedan en
# pendientes con motivo `posible_cifra_adicional_no_extraida`, no en esta lista.
CONCEPT_IDS_ESPERADOS = {
    "es.rd_173_2010.seguridad_utilizacion.1_2_discontinuidades_en_el_pavimento_resalto_maximo_junta",
    "es.rd_173_2010.seguridad_utilizacion.1_2_discontinuidades_en_el_pavimento_diametro_maximo_perforacion",
    "es.rd_173_2010.seguridad_utilizacion.1_5_limpieza_de_los_acristalamientos_exteriores",
    "es.rd_173_2010.seguridad_utilizacion.2_2_atrapamiento",
    "es.rd_173_2010.seguridad_utilizacion.4_1_alumbrado_normal_en_zonas_de_circulacion",
    "es.rd_173_2010.seguridad_utilizacion.5_1_ambito_de_aplicacion",
    "es.rd_173_2010.seguridad_utilizacion.7_1_ambito_de_aplicacion",
}

# Ningún motivo de descarte restante puede ser el genérico "artículo
# compuesto" — es el criterio de terminado literal del encargo de la
# descomposición. Lo que queda son motivos que sí exigen juicio humano.
CATEGORIAS_PROHIBIDAS = {"multiples_exigencias_agrupadas"}


def _ejecutar(tmp_path):
    salida = tmp_path / "corpus"
    pendientes = tmp_path / "pendientes.jsonl"
    resultado = procesar(CANDIDATAS, salida, pendientes)
    return resultado, salida, pendientes


def _candidata_por_articulo(fragmento: str) -> dict:
    for c in almacen.leer(CANDIDATAS):
        if fragmento in (c.get("articulo") or ""):
            return c
    raise AssertionError(f"no hay candidata con «{fragmento}» en su artículo")


def _regla_generada(resultado, concept_id: str) -> tuple[dict, dict]:
    for ruta in resultado["convertidas"]:
        doc = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        for regla in doc["reglas"]:
            if regla["concept_id"] == concept_id:
                return regla, doc
    raise AssertionError(f"no se generó ninguna regla con concept_id {concept_id}")


# --- Resultado global sobre las 20 candidatas reales ------------------------

def test_convierte_las_siete_sub_candidatas_estructuralmente_limpias(tmp_path):
    resultado, _, _ = _ejecutar(tmp_path)
    generados = {p.stem for p in resultado["convertidas"]}
    assert len(resultado["convertidas"]) == 7, (
        f"se esperaban 7 reglas BORRADOR, salieron {len(resultado['convertidas'])}: {generados}"
    )


def test_tasa_de_conversion_sube_de_forma_medible_respecto_al_prompt_1(tmp_path):
    """El Prompt 1 (sin descomposición) convertía 3/20. El criterio de
    terminado de la descomposición es que la tasa suba de forma medible."""
    resultado, _, _ = _ejecutar(tmp_path)
    tasa_antes = 3 / 20
    tasa_ahora = len(resultado["convertidas"]) / resultado["leidas"]
    assert tasa_ahora > tasa_antes
    assert tasa_ahora == 7 / 20


def test_ningun_motivo_de_descarte_es_ya_articulo_compuesto(tmp_path):
    """Criterio de terminado literal del encargo: lo que quede en pendientes
    tiene un motivo que de verdad exige juicio humano, nunca el genérico
    "el artículo agrupa N exigencias... no se auto-divide" del Prompt 1."""
    resultado, _, _ = _ejecutar(tmp_path)
    categorias_presentes = set(resultado["motivos"])
    interseccion = categorias_presentes & CATEGORIAS_PROHIBIDAS
    assert not interseccion, f"sigue apareciendo un motivo genérico: {interseccion}"


def test_ninguna_sub_candidata_desaparece_sin_convertirse_ni_pendiente(tmp_path):
    resultado, _, _ = _ejecutar(tmp_path)
    total = len(resultado["convertidas"]) + resultado["descartadas"]
    assert total == resultado["unidades"]
    assert resultado["leidas"] == 20


def test_cada_fichero_generado_es_borrador_invisible_al_loader_y_valido(tmp_path):
    resultado, _, _ = _ejecutar(tmp_path)
    assert resultado["convertidas"], "no se generó ningún fichero para comprobar"
    for ruta in resultado["convertidas"]:
        # Defensa 1: nombre invisible para normativa/loader.py::descubrir().
        assert ruta.name.startswith("_"), f"{ruta.name} no empieza por «_»: el loader lo vería"

        doc = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        assert doc["reglas"], f"{ruta.name}: sin reglas"
        for regla in doc["reglas"]:
            # Defensa 2: el campo estado, que resolucion.py filtra explícitamente.
            assert regla["estado"] == "BORRADOR"
            assert regla["concept_id"] in CONCEPT_IDS_ESPERADOS

        # El propio validador de carga (12 comprobaciones por fichero) no
        # protesta: BORRADOR es aditivo al esquema, no rompe nada existente.
        fallos = validar_fichero(doc)
        assert not fallos, f"{ruta.name} no pasa validar_fichero: {fallos}"


def test_concept_ids_generados_son_exactamente_los_esperados(tmp_path):
    resultado, _, _ = _ejecutar(tmp_path)
    vistos = set()
    for ruta in resultado["convertidas"]:
        doc = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        for regla in doc["reglas"]:
            vistos.add(regla["concept_id"])
    assert vistos == CONCEPT_IDS_ESPERADOS


def test_no_regresion_las_tres_conversiones_del_prompt_1_siguen_igual(tmp_path):
    """Las candidatas ya atómicas del Prompt 1 (0 o 1 parámetro de origen) no
    pasan por descomposición (`_descomponer` las deja intactas) — sus
    `concept_id` no deben cambiar por este paso nuevo."""
    resultado, _, _ = _ejecutar(tmp_path)
    _regla_generada(resultado, "es.rd_173_2010.seguridad_utilizacion.2_2_atrapamiento")
    _regla_generada(resultado, "es.rd_173_2010.seguridad_utilizacion.5_1_ambito_de_aplicacion")
    _regla_generada(resultado, "es.rd_173_2010.seguridad_utilizacion.7_1_ambito_de_aplicacion")


# --- Golden: cada regla convertida contra su candidata origen --------------

def test_golden_atrapamiento_cita_literal_y_parametro_fieles_a_la_candidata(tmp_path):
    resultado, _, _ = _ejecutar(tmp_path)
    cand = _candidata_por_articulo("2.2 Atrapamiento")
    regla, doc = _regla_generada(resultado, "es.rd_173_2010.seguridad_utilizacion.2_2_atrapamiento")

    assert doc["norma"]["literal"] == cand["texto_original"]
    assert regla["patron"] == cand["patron"] == "UMBRAL_SIMPLE"
    assert regla["materia"] == cand["materia_sugerida"] == "seguridad_utilizacion"
    assert regla["parametro"]["valores"][0]["valor"] == _numero(cand["parametros"][0]["valor_citado"]) == 20.0
    assert regla["parametro"]["unidad"] == cand["parametros"][0]["unidad"] == "cm"
    assert f"confianza_{cand['nivel_confianza'].lower()}" in regla["tags"]


def test_golden_ambito_graderios_umbral_de_aforo_fiel_a_la_candidata(tmp_path):
    resultado, _, _ = _ejecutar(tmp_path)
    cand = _candidata_por_articulo("5.1 Ámbito de aplicación")
    regla, doc = _regla_generada(resultado, "es.rd_173_2010.seguridad_utilizacion.5_1_ambito_de_aplicacion")

    assert doc["norma"]["literal"] == cand["texto_original"]
    assert regla["parametro"]["valores"][0]["valor"] == 3000.0
    assert regla["parametro"]["unidad"] == "espectadores de pie"


def test_golden_ambito_aparcamiento_presencia_obligatoria_sin_parametro(tmp_path):
    resultado, _, _ = _ejecutar(tmp_path)
    cand = _candidata_por_articulo("7.1 Ámbito de aplicación")
    regla, doc = _regla_generada(resultado, "es.rd_173_2010.seguridad_utilizacion.7_1_ambito_de_aplicacion")

    assert doc["norma"]["literal"] == cand["texto_original"]
    assert regla["patron"] == "PRESENCIA_OBLIGATORIA"
    assert regla["parametro"] is None
    assert cand["parametros"] == () or cand["parametros"] == []


# --- Golden: descomposición — una enumeración (DB-SUA 1.2) -----------------

def test_golden_descomposicion_enumeracion_convierte_las_clausulas_limpias(tmp_path):
    """DB-SUA 1.2 (a/b/c) es el caso de diseño del PRD: item «c)»
    (diámetro de perforación) y el párrafo «2» (resalto de junta, en
    realidad el primer punto del artículo) están cada uno solos en su
    cláusula y sin remisión — se convierten. El resto no."""
    resultado, _, _ = _ejecutar(tmp_path)
    cand = _candidata_por_articulo("1.2 Discontinuidades")

    resalto, doc_resalto = _regla_generada(
        resultado, "es.rd_173_2010.seguridad_utilizacion.1_2_discontinuidades_en_el_pavimento_resalto_maximo_junta"
    )
    diametro, doc_diametro = _regla_generada(
        resultado, "es.rd_173_2010.seguridad_utilizacion.1_2_discontinuidades_en_el_pavimento_diametro_maximo_perforacion"
    )

    # La cita literal de CADA sub-candidata es el texto_original COMPLETO
    # del padre, nunca un recorte — la atomización es de la exigencia, no
    # del texto fuente (restricción explícita del encargo).
    assert doc_resalto["norma"]["literal"] == cand["texto_original"]
    assert doc_diametro["norma"]["literal"] == cand["texto_original"]
    assert doc_resalto["norma"]["literal"] == doc_diametro["norma"]["literal"]

    assert resalto["parametro"]["valores"][0]["valor"] == 4.0
    assert resalto["parametro"]["unidad"] == "mm"
    assert diametro["parametro"]["valores"][0]["valor"] == 1.5
    assert diametro["parametro"]["unidad"] == "cm"

    # Cada una lleva su propia trazabilidad al padre.
    assert resalto["concept_id"] != diametro["concept_id"]


def test_golden_descomposicion_no_parte_la_condicion_entrelazada_desnivel_pendiente(tmp_path):
    """El caso adversarial del PRD §5: DB-SUA 1.2-b) («Los desniveles que no
    excedan de 5 cm se resolverán con una pendiente que no exceda del
    25 %») es UNA exigencia condicional con dos cifras, no dos exigencias
    independientes. Partir por letra las trataría como atómicas — este test
    falla si eso llega a pasar. (En esta corrida caen a
    `contexto_no_localizable` por un artefacto de guionizado del PDF sobre
    "resolverán"; el punto del test es que NUNCA se conviertan por separado,
    sea cual sea el motivo de pendiente.)"""
    resultado, _, _ = _ejecutar(tmp_path)
    convertidos = set()
    for ruta in resultado["convertidas"]:
        doc = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        for regla in doc["reglas"]:
            convertidos.add(regla["concept_id"])

    desnivel_solo = "es.rd_173_2010.seguridad_utilizacion.1_2_discontinuidades_en_el_pavimento_desnivel_maximo_con_pendiente"
    pendiente_sola = "es.rd_173_2010.seguridad_utilizacion.1_2_discontinuidades_en_el_pavimento_pendiente_maxima_desnivel"
    assert desnivel_solo not in convertidos
    assert pendiente_sola not in convertidos


def test_no_convierte_capacidad_aparcamiento_sola_por_ser_mitad_de_una_disyuncion(tmp_path):
    """El hallazgo más importante de la descomposición sobre datos reales:
    DB-SUA 7.3 dice «capacidad mayor que 200 vehículos O superficie mayor
    que 5000 m2» — sus propias `excepciones` lo confirman («Si la capacidad
    es ≤200 vehículos Y la superficie es ≤5000 m², el apartado no es de
    aplicación»). Solo `capacidad_aparcamiento` se ancla en el texto
    (`superficie_aparcamiento` cae a «superficie m ayor», guionizado del
    PDF) — convertirla sola presentaría un umbral disyuntivo como si fuera
    incondicional. `_contar_cifras_de_umbral` lo corta: la cláusula sigue
    citando «5000» aunque ese `parametro` no se pudiera anclar."""
    resultado, _, pendientes_ruta = _ejecutar(tmp_path)
    cand = _candidata_por_articulo("7.3 Protección de recorridos peatonales")
    assert any(
        "≤ 200 vehículos" in e or "200 vehículos" in e for e in cand.get("excepciones") or []
    ), "la propia candidata debería documentar la disyunción capacidad/superficie"

    convertidos = {
        regla["concept_id"]
        for ruta in resultado["convertidas"]
        for regla in yaml.safe_load(ruta.read_text(encoding="utf-8"))["reglas"]
    }
    assert not any("capacidad_aparcamiento" in c for c in convertidos)

    pendientes = [json.loads(linea) for linea in pendientes_ruta.read_text(encoding="utf-8").splitlines()]
    entrada = next(
        d for d in pendientes
        if any(p["nombre"] == "capacidad_aparcamiento" for p in (d.get("parametros") or []))
    )
    assert entrada["categoria_descarte"] == "posible_cifra_adicional_no_extraida"
    assert entrada["categoria_descarte"] not in CATEGORIAS_PROHIBIDAS


def test_no_convierte_pendiente_sola_por_venir_con_profundidad_en_la_misma_frase(tmp_path):
    """DB-SUA 7.2: «con una profundidad... de 4,5 m como mínimo y una
    pendiente del 5% como máximo» — una sola frase con dos cifras. Solo
    `pendiente_espacio_acceso_espera` se ancla (`profundidad...` cae a «tip
    o de vehículo», guionizado del PDF). No se convierte sola: aunque aquí
    las dos cifras son independientes y no una disyunción, el pipeline no
    puede distinguir ese caso del de DB-SUA 7.3 sin arriesgarse — la
    cláusula tiene más de una cifra y con eso basta para no decidir sola."""
    resultado, _, pendientes_ruta = _ejecutar(tmp_path)
    convertidos = {
        regla["concept_id"]
        for ruta in resultado["convertidas"]
        for regla in yaml.safe_load(ruta.read_text(encoding="utf-8"))["reglas"]
    }
    assert not any("caracteristicas_constructivas" in c for c in convertidos)

    pendientes = [json.loads(linea) for linea in pendientes_ruta.read_text(encoding="utf-8").splitlines()]
    entrada = next(
        d for d in pendientes
        if any(p["nombre"] == "pendiente_espacio_acceso_espera" for p in (d.get("parametros") or []))
    )
    assert entrada["categoria_descarte"] == "posible_cifra_adicional_no_extraida"


def test_descomponer_agrupa_saliente_y_umbral_de_1_2_como_no_atomico():
    """Item «a)» de DB-SUA 1.2 también une el saliente puntual (12 mm) con
    el umbral de saliente en cara enfrentada (6 mm) en la misma frase — se
    agrupan, no se convierten por separado, y el motivo es específico."""
    cand = _candidata_por_articulo("1.2 Discontinuidades")
    grupos = _descomponer(cand)
    nombres_por_grupo = [{p["nombre"] for p in g.parametros} for g in grupos]

    grupo_saliente = next(
        (g for g in nombres_por_grupo
         if {"saliente_maximo_elemento_puntual", "umbral_saliente_cara_enfrentada_circulacion"} <= g),
        None,
    )
    assert grupo_saliente is not None, f"no se agruparon juntos: {nombres_por_grupo}"


# --- Golden: descomposición — una tabla (DB-SUA 8.2) ------------------------

def test_golden_descomposicion_tabla_no_mezcla_filas_ni_inventa_valores(tmp_path):
    """DB-SUA 8.2 (Tabla 2.1, niveles de protección contra el rayo) tiene 4
    filas, cada una su propio `parametro`. Sus `contexto_citado` son un
    resumen de la IA sobre la tabla («Tabla 2.1 — Eficiencia requerida
    E > 0,98 → Nivel de protección 1»), no una cita literal de la tabla tal
    como quedó en el texto extraído del PDF — así que ninguna se ancla, y
    el resultado correcto es pendientes, no una conversión con una cita que
    en realidad no está en `texto_original`."""
    resultado, _, pendientes_ruta = _ejecutar(tmp_path)
    cand = _candidata_por_articulo("8.2 Tipo de instalación")
    assert len(cand["parametros"]) == 4

    convertidos = {
        regla["concept_id"]
        for ruta in resultado["convertidas"]
        for regla in yaml.safe_load(ruta.read_text(encoding="utf-8"))["reglas"]
    }
    assert not any("nivel_proteccion" in c for c in convertidos), (
        "ninguna fila de la tabla 2.1 debería convertirse: su contexto_citado no es literal"
    )

    pendientes = [json.loads(linea) for linea in pendientes_ruta.read_text(encoding="utf-8").splitlines()]
    fila_1_2_o_3_o_4 = [
        d for d in pendientes
        if d.get("candidata_padre") and "8.2" in d["candidata_padre"]
    ]
    assert fila_1_2_o_3_o_4, "las 4 filas de la tabla deberían aparecer en pendientes"
    # Ninguna cifra de la tabla se pierde: las 4 siguen presentes, agrupadas
    # o no, con su propio nombre — no desaparecen del todo.
    nombres_pendientes = {p["nombre"] for d in fila_1_2_o_3_o_4 for p in (d.get("parametros") or [])}
    nombres_originales = {p["nombre"] for p in cand["parametros"]}
    assert nombres_pendientes == nombres_originales
    for d in fila_1_2_o_3_o_4:
        assert d["categoria_descarte"] not in CATEGORIAS_PROHIBIDAS
        assert d.get("candidata_padre") == cand["articulo"]


# --- Trazabilidad bidireccional ---------------------------------------------

def test_toda_sub_candidata_pendiente_lleva_padre_y_criterio(tmp_path):
    _, _, pendientes_ruta = _ejecutar(tmp_path)
    pendientes = [json.loads(linea) for linea in pendientes_ruta.read_text(encoding="utf-8").splitlines()]
    assert pendientes
    for d in pendientes:
        assert d.get("candidata_padre"), f"sin candidata_padre: {d.get('articulo')}"
        assert d.get("criterio_particion"), f"sin criterio_particion: {d.get('articulo')}"
        # No se recorta la cita: cada pendiente conserva el texto_original
        # íntegro del padre, aunque sea una sub-candidata de una sola cifra.
        assert d.get("texto_original")


def test_toda_sub_candidata_convertida_lleva_criterio_en_su_cabecera(tmp_path):
    """Las sub-candidatas producidas por descomposición real (no las tres
    ya-atómicas del Prompt 1) declaran en la cabecera del YAML de qué
    artículo padre y con qué criterio salieron."""
    resultado, _, _ = _ejecutar(tmp_path)
    encontrada = False
    for ruta in resultado["convertidas"]:
        texto = ruta.read_text(encoding="utf-8")
        if "discontinuidades_en_el_pavimento" in ruta.stem:
            assert "Sub-candidata por descomposición del artículo padre" in texto
            assert "DB-SUA 1.2 Discontinuidades en el pavimento" in texto
            encontrada = True
    assert encontrada


# --- Motivos de descarte, por categoría (no se inventa, se rechaza con motivo) --

def test_articulo_con_tabla_cruzada_se_descarta_por_falta_de_parametros(tmp_path):
    """Resbaladicidad de los suelos (Tabla 1.1 x Tabla 1.2, dos ejes
    cruzados) es exactamente el caso que Prompt 1 anticipa como «tabla no
    parseable». La propia extracción ya lo dejó sin `parametros`, así que
    la descomposición no tiene nada que agrupar (§6 del PRD)."""
    cand = _candidata_por_articulo("1.1 Resbaladicidad")
    motivo = _decidir(cand)
    assert motivo is not None
    categoria, _ = motivo
    assert categoria == "sin_parametros_extraidos"


def test_decidir_en_aislado_conserva_el_fallback_generico_como_defensa(tmp_path):
    """`_decidir()` en sí mismo (sin pasar por `_descomponer`/`_unidades`)
    conserva su rama genérica de "múltiples exigencias" — es la defensa por
    si algún día una candidata multi-parámetro llegara a `_decidir` sin
    pasar por descomposición. El pipeline real (`procesar`) ya no la
    alcanza: ver `test_ningun_motivo_de_descarte_es_ya_articulo_compuesto`."""
    cand = _candidata_por_articulo("1.2 Discontinuidades")
    assert len(cand["parametros"]) > 1
    motivo = _decidir(cand)
    assert motivo is not None
    categoria, texto = motivo
    assert categoria == "multiples_exigencias_agrupadas"
    assert str(len(cand["parametros"])) in texto


def test_materia_incoherente_con_documento_se_descarta():
    """DB-SUA 4.2 sugiere materia seguridad_incendio, que el catálogo regula
    en DB-SI, no en DB-SUA — la validación 12 (db_coherente) la habría
    rechazado igualmente; el script la corta antes."""
    cand = _candidata_por_articulo("4.2 Alumbrado de emergencia")
    assert cand["materia_sugerida"] == "seguridad_incendio"
    motivo = _decidir(cand)
    assert motivo is not None
    assert motivo[0] == "materia_incoherente_con_documento"


def test_idempotente_no_duplica_ficheros_al_correr_dos_veces(tmp_path):
    r1, salida, _ = _ejecutar(tmp_path)
    r2, _, _ = _ejecutar(tmp_path)
    assert sorted(p.name for p in r1["convertidas"]) == sorted(p.name for p in r2["convertidas"])
    assert sorted(salida.glob("_borrador_*.yaml")) == sorted(r2["convertidas"])
