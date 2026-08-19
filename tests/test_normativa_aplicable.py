"""FASE 1 — `normativa_aplicable()`: el resolver de extremo a extremo.

Dos tests mandan sobre los demás, y no son los que comprueban que Pozuelo
resuelve bien:

- `test_corpus_real_vacio_bloquea` — con el corpus de producción vacío, el
  motor NO devuelve una lista corta: levanta `CoberturaInsuficiente` diciendo
  qué falta. Una lista de normativa se lee siempre como completa.
- `test_ninguna_regla_sale_sin_estado_ni_motivo` — el invariante estructural
  del subsistema. Una regla que desaparece del resultado sin decir por qué es
  indistinguible de una que no existe.

Todo lo demás se prueba contra `tests/fixtures/corpus_ficticio/`, que es
inventado a propósito (ver su LEEME.md): el algoritmo se puede verificar sin
esperar a que un arquitecto colegiado valide cifras contra boletín, que es la
dependencia externa que bloquea la tarea 18 del PRD.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from normativa import validacion  # noqa: E402
from normativa.api import (  # noqa: E402
    CoberturaInsuficiente,
    contexto_territorial,
    normativa_aplicable,
    perfil_proyecto,
    resolver_ambito,
)
from normativa.condiciones import Ternario, evaluar  # noqa: E402
from normativa.loader import cargar  # noqa: E402
from normativa.resolucion import ESTADOS  # noqa: E402

CORPUS = RAIZ / "tests" / "fixtures" / "corpus_ficticio"
MANIFIESTO = CORPUS / "manifiesto.yaml"
DEVENGO = date(2026, 3, 1)


def _resolver(
    municipio="Pozuelo de Alarcón",
    tipologia="plurifamiliar",
    uso="residencial.vivienda_libre",
    sectoriales=None,
    hechos=None,
    fecha_devengo=DEVENGO,
    estricto=False,
    ruta_manifiesto=MANIFIESTO,
    **kw,
):
    ctx = contexto_territorial(
        municipio=municipio,
        tipologia=tipologia,
        uso=uso,
        sectoriales=sectoriales,
        fecha_devengo=fecha_devengo,
    )
    return normativa_aplicable(
        ctx,
        hechos=hechos,
        estricto=estricto,
        raiz_corpus=CORPUS,
        ruta_manifiesto=ruta_manifiesto,
        **kw,
    )


# --- Fail-closed ------------------------------------------------------------

def test_corpus_real_vacio_bloquea():
    """EL TEST QUE MÁS IMPORTA.

    Contra el corpus de PRODUCCIÓN (vacío), cualquier proyecto debe bloquear.
    Devolver un conjunto vacío se leería como "no hay nada que incumplir".
    """
    ctx = contexto_territorial(
        municipio="Pozuelo de Alarcón", tipologia="plurifamiliar", fecha_devengo=DEVENGO
    )
    try:
        normativa_aplicable(ctx)
    except CoberturaInsuficiente as exc:
        # Nombra cada materia que falta, no un "faltan datos" genérico.
        assert len(exc.faltantes) >= 12, exc.faltantes
        assert any("seguridad_incendio" in f for f in exc.faltantes)
        assert any("habitabilidad_superficies" in f for f in exc.faltantes)
        assert any("urbanismo_parametros" in f for f in exc.faltantes)
        # Y dice explícitamente que ausencia no es inexistencia.
        assert "no la hemos transcrito" in str(exc)
    else:
        raise AssertionError("con el corpus vacío el motor no puede devolver un resultado")


def test_falta_una_sola_materia_y_tambien_bloquea():
    """El fail-closed no es "si falta casi todo": es si falta UNA.

    Se resuelve contra el fixture pero SIN su manifiesto, así que la cobertura
    declarada desaparece entera. Lo que se comprueba es que basta con que una
    materia exigible no sea afirmable para que no se emita resultado.
    """
    ctx = contexto_territorial(
        municipio="Pozuelo de Alarcón", tipologia="plurifamiliar", fecha_devengo=DEVENGO
    )
    try:
        normativa_aplicable(ctx, estricto=True, raiz_corpus=CORPUS)
    except CoberturaInsuficiente as exc:
        assert exc.faltantes
    else:
        raise AssertionError("sin manifiesto no hay cobertura declarada: debe bloquear")


def test_estricto_false_devuelve_el_hueco_en_vez_de_levantarlo():
    """Para una interfaz que quiera PINTAR el hueco. Nunca para seguir
    calculando como si no existiera: `completo` es False y se ve."""
    c = _resolver(estricto=False, ruta_manifiesto=None)
    assert not c.completo
    assert c.faltantes
    assert all(f.justificacion for f in c.faltantes), "un hueco sin justificar no es accionable"


def test_cobertura_declarada_completa_no_bloquea():
    """Con el manifiesto del fixture, las 12 materias exigibles están
    declaradas y el motor sí resuelve."""
    c = _resolver(estricto=True)
    assert c.completo and not c.faltantes
    assert c.aplicables(), "debería haber reglas aplicables"


def test_patrimonio_no_exigible_hasta_que_se_declara():
    """Un sectorial sin declarar no hace la materia «no exigible»: la deja en
    PREGUNTA. Es la asimetría que evita que cada proyecto sin declarar
    patrimonio quede bloqueado — y que, por reacción, se acabara relajando el
    bloqueo que sí importa."""
    c = _resolver(sectoriales=None)
    assert any("patrimonio" in p for p in c.preguntas_pendientes)
    assert not any(f.materia == "patrimonio" for f in c.faltantes)

    # Declarado presente y con cobertura declarada -> exigible y cubierto.
    c2 = _resolver(sectoriales={"patrimonio": True})
    assert not any(f.materia == "patrimonio" for f in c2.faltantes)

    # Declarado ausente -> ni se exige ni se pregunta.
    c3 = _resolver(sectoriales={"patrimonio": False})
    assert not any("¿El proyecto está afectado por patrimonio?" == p for p in c3.preguntas_pendientes)


# --- Nunca silencio ---------------------------------------------------------

def test_ninguna_regla_sale_sin_estado_ni_motivo():
    """INVARIANTE ESTRUCTURAL. Toda candidata sale con estado válido y motivo
    escrito, en los cuatro estados — no solo en `no_aplica`."""
    c = _resolver(sectoriales={"patrimonio": True})
    assert c.normas
    for n in c.normas:
        assert n.estado in ESTADOS, n
        assert n.motivo.strip(), f"{n.id} sale sin motivo"
        assert n.traza, f"{n.id} sale sin traza"


def test_cada_norma_trae_los_campos_que_el_arquitecto_necesita():
    """id, nombre, ámbito, organismo, versión, fecha, prioridad, motivo,
    cobertura y fuente oficial. Sin boletín no hay cita verificable, y sin cita
    verificable esto es una opinión, no normativa."""
    c = _resolver()
    for n in c.aplicables():
        assert n.id and n.nombre and n.ambito and n.organismo
        assert n.version and n.fecha and n.prioridad and n.motivo and n.cobertura
        assert n.fuente.boletin and n.fuente.identificador_oficial and n.fuente.rango
        date.fromisoformat(n.fecha)


# --- Herencia territorial y orden ------------------------------------------

def test_las_tres_capas_estan_y_en_orden():
    """El ejemplo de Pablo: CTE -> autonómica -> PGOU/ordenanzas -> sectorial.
    Es el orden en que un arquitecto lee la normativa de un proyecto.

    La regla sectorial del fixture es `exigencia_cualitativa` (rige, no se
    puntúa), así que se busca entre TODAS las que rigen — `aplica` +
    `aplica_no_evaluable` — no solo entre las evaluables."""
    c = _resolver(sectoriales={"patrimonio": True})
    vigentes = [n for n in c.normas if n.estado in ("aplica", "aplica_no_evaluable")]
    niveles = [n.nivel for n in vigentes]
    assert niveles == sorted(niveles, key=lambda x: ["estatal", "autonomico", "municipal", "sectorial"].index(x))
    assert set(niveles) == {"estatal", "autonomico", "municipal", "sectorial"}


def test_dentro_de_un_nivel_manda_la_prioridad():
    c = _resolver()
    estatales = [n for n in c.aplicables() if n.nivel == "estatal"]
    orden = ["bloqueante", "riesgo_variable", "recomendable", "preferencial"]
    idx = [orden.index(n.prioridad) for n in estatales]
    assert idx == sorted(idx)


def test_sin_municipio_no_hay_capa_municipal_pero_se_dice():
    """Analizar contra CTE + autonómica sin fijar municipio es legítimo. Lo que
    NO puede pasar es que el urbanismo municipal desaparezca en silencio."""
    ctx = contexto_territorial(
        comunidad="Comunidad de Madrid", tipologia="plurifamiliar", fecha_devengo=DEVENGO
    )
    c = normativa_aplicable(ctx, estricto=False, raiz_corpus=CORPUS, ruta_manifiesto=MANIFIESTO)
    assert not any(n.nivel == "municipal" for n in c.aplicables())
    faltan = {f.materia for f in c.faltantes}
    assert "urbanismo_parametros" in faltan and "urbanismo_estetica" in faltan


# --- Composición por competencia -------------------------------------------

def test_suelo_estatal_y_endurecimiento_autonomico_conviven():
    """Endurecer NO borra el suelo: ambas se citan. Deducir cuál gana comparando
    magnitudes sería el «gana la más restrictiva» que §7.1 declara incorrecto."""
    c = _resolver()
    accesibilidad = [n for n in c.aplicables() if n.materia == "accesibilidad"]
    assert len(accesibilidad) == 2
    autonomica = next(n for n in accesibilidad if n.nivel == "autonomico")
    assert any(r.tipo == "endurece" for r in autonomica.relaciones)


def test_exclusivo_autonomico_no_admite_capa_estatal():
    """Habitabilidad es competencia autonómica exclusiva: el CTE no la regula,
    así que no hay nada que comparar (hallazgo M1 de NORMATIVE_AUDIT.md)."""
    c = _resolver()
    superficies = [n for n in c.aplicables() if n.materia == "habitabilidad_superficies"]
    assert superficies and all(n.nivel == "autonomico" for n in superficies)


def test_urbanismo_solo_municipal():
    c = _resolver()
    urb = [n for n in c.aplicables() if n.materia.startswith("urbanismo")]
    assert urb and all(n.nivel == "municipal" for n in urb)


# --- Exclusiones, excepciones y estados ------------------------------------

def test_regla_de_otro_uso_sale_no_aplica_con_motivo():
    """La regla de vivienda protegida no desaparece en un proyecto de vivienda
    libre: sale `no_aplica` diciendo exactamente por qué."""
    c = _resolver(uso="residencial.vivienda_libre")
    vpo = next(n for n in c.normas if n.id.endswith("superficie_vpo"))
    assert vpo.estado == "no_aplica"
    assert "residencial.vivienda_protegida" in vpo.motivo

    c2 = _resolver(uso="residencial.vivienda_protegida")
    vpo2 = next(n for n in c2.normas if n.id.endswith("superficie_vpo"))
    assert vpo2.estado == "aplica"


def test_regla_derogada_no_desaparece_sale_con_la_fecha():
    c = _resolver()
    derogada = next(n for n in c.normas if n.id.endswith("regla_derogada"))
    assert derogada.estado == "no_aplica"
    assert "2019-12-01" in derogada.motivo


def test_fecha_de_devengo_cambia_el_conjunto():
    """La normativa aplicable a un proyecto no es la vigente hoy: es la vigente
    en su fecha de devengo. Es todo el sentido del versionado."""
    antigua = _resolver(fecha_devengo=date(2015, 6, 1))
    ids = {n.id for n in antigua.aplicables()}
    assert "es.ficticio_dbsi.seguridad_incendio.regla_derogada" in ids

    moderna = _resolver(fecha_devengo=DEVENGO)
    assert "es.ficticio_dbsi.seguridad_incendio.regla_derogada" not in {
        n.id for n in moderna.aplicables()
    }


def test_eje_de_registro_reconstruye_un_informe_pasado():
    """Segundo eje bitemporal: no qué estaba en vigor, sino qué SABÍAMOS.

    La regla autonómica de accesibilidad está en vigor desde 1993 pero declara
    `registro_desde: 2024`. Un informe reconstruido a 2020 no puede incluirla:
    no la teníamos. Es lo que hace un informe defendible tres años después.

    OJO — LÍMITE REAL: solo filtra las reglas que declaran `registro_desde`.
    `Vigencia.conocida_en` (Fase 0) trata la ausencia de ese campo como
    "conocida siempre", así que un corpus que no lo declare hace este eje
    inoperante sin decirlo. Hoy no muerde porque el corpus está vacío; cuando
    se transcriba de verdad, `registro_desde` debe ser obligatorio.
    """
    hoy = _resolver()
    assert any(n.id.endswith("anchura_reforzada") for n in hoy.aplicables())

    pasado = _resolver(fecha_de_registro=date(2020, 1, 1))
    reforzada = next(n for n in pasado.normas if n.id.endswith("anchura_reforzada"))
    assert reforzada.estado == "no_aplica"
    assert "no tenía esta regla en su corpus" in reforzada.motivo
    # La estatal, que no declara el eje de registro, sigue aplicando.
    assert any(n.id.endswith("anchura_itinerario") for n in pasado.aplicables())


def test_sectorial_sin_declarar_no_es_no_aplica():
    """La ausencia de evidencia no es evidencia de ausencia
    (INFERENCE_ENGINE.md §2.2). Es la variante más peligrosa del Bug #1 porque
    falla como un tranquilizador «aquí no hay problema de patrimonio»."""
    c = _resolver(sectoriales=None)
    pat = next(n for n in c.normas if n.materia == "patrimonio")
    assert pat.estado == "aplica_no_evaluable"
    assert pat.preguntas_pendientes

    c_no = _resolver(sectoriales={"patrimonio": False})
    pat_no = next(n for n in c_no.normas if n.materia == "patrimonio")
    assert pat_no.estado == "no_aplica" and "no le afecta" in pat_no.motivo


def test_exencion_solo_cuando_la_eximente_aplica_de_verdad():
    """Tres escenarios, tres resultados distintos, ninguno silencioso.

    (La regla eximida, `composicion_fachada`, es `exigencia_cualitativa` en el
    fixture: cuando NO está eximida rige pero no se puntúa, así que su estado
    "vivo" es `aplica_no_evaluable`, no `aplica` — el mismo cierre de tipo que
    prueba `test_regla_cualitativa_rige_pero_no_se_puntua`.)
    """
    # Sectorial declarado: la exención se aplica y se cita. Esto SÍ debe ganar
    # a "es cualitativa": una regla eximida no rige en absoluto, así que no
    # hay nada que marcar como no evaluable.
    c = _resolver(sectoriales={"patrimonio": True})
    estetica = next(n for n in c.normas if n.materia == "urbanismo_estetica")
    assert estetica.estado == "no_aplica" and "eximida por" in estetica.motivo

    # Sectorial sin declarar: la eximente no se sabe, así que la eximida
    # tampoco se descarta. Eximir con una condición sin comprobar es la forma
    # más silenciosa de perder una exigencia.
    c2 = _resolver(sectoriales=None)
    est2 = next(n for n in c2.normas if n.materia == "urbanismo_estetica")
    assert est2.estado == "aplica_no_evaluable"
    assert any("eximida" in p or "patrimonio" in p for p in est2.preguntas_pendientes) or est2.preguntas_pendientes

    # Sectorial descartado: la eximente no aplica y la exigencia sigue viva,
    # rigiendo — pero como cualitativa que es, sin puntuarse.
    c3 = _resolver(sectoriales={"patrimonio": False})
    est3 = next(n for n in c3.normas if n.materia == "urbanismo_estetica")
    assert est3.estado == "aplica_no_evaluable"
    assert "eximida" not in est3.motivo


def test_condicion_sin_dato_deja_la_regla_no_evaluable_con_pregunta():
    c = _resolver(hechos=None)
    sector = next(n for n in c.normas if n.id.endswith("sector_por_altura"))
    assert sector.estado == "aplica_no_evaluable"
    assert any("plantas_sobre_rasante" in p for p in sector.preguntas_pendientes)

    c_si = _resolver(hechos={"plantas_sobre_rasante": 6})
    assert next(n for n in c_si.normas if n.id.endswith("sector_por_altura")).estado == "aplica"

    c_no = _resolver(hechos={"plantas_sobre_rasante": 2})
    negada = next(n for n in c_no.normas if n.id.endswith("sector_por_altura"))
    assert negada.estado == "no_aplica" and "condiciones" in negada.motivo


# --- Parámetros -------------------------------------------------------------

def test_el_umbral_sale_del_contexto_y_deja_traza_del_repliegue():
    """Un repliegue silencioso en materia autonómica es el Bug #1 reencarnado
    en la capa normativa (CONSTRAINT_MODEL.md §9)."""
    plurifamiliar = _resolver(tipologia="plurifamiliar")
    sup = next(n for n in plurifamiliar.aplicables() if n.id.endswith("superficie_minima"))
    assert sup.valor_parametro == 38 and sup.unidad == "m2"

    unifamiliar = _resolver(tipologia="unifamiliar_aislada")
    sup2 = next(n for n in unifamiliar.aplicables() if n.id.endswith("superficie_minima"))
    assert sup2.valor_parametro == 60
    assert any("parámetro" in t for t in sup2.traza)


def test_parametro_sin_valor_no_coge_uno_por_defecto():
    """Pozuelo no está en la tabla de zonas climáticas, así que la regla
    indexada por `zona_cte` se queda sin valor. Debe quedar NO EVALUABLE, jamás
    coger la primera fila de la tabla."""
    c = _resolver(municipio="Pozuelo de Alarcón")
    demanda = next(n for n in c.normas if n.id.endswith("ahorro_energia.demanda"))
    assert demanda.estado == "aplica_no_evaluable"
    assert demanda.valor_parametro is None

    # En Madrid capital sí hay zona climática (D) y el umbral se resuelve.
    c2 = _resolver(municipio="Madrid")
    demanda2 = next(n for n in c2.normas if n.id.endswith("ahorro_energia.demanda"))
    assert demanda2.valor_parametro == 40


# --- Conflictos -------------------------------------------------------------

def test_el_conflicto_se_expone_no_se_resuelve():
    """Dos reglas de la misma materia y ámbito que se solapan sin ser
    idénticas: la validación 14 no puede rechazarlas en carga (su clave incluye
    la lista de usos, y aquí difieren). El motor NO desempata."""
    c = _resolver()
    conf = [k for k in c.conflictos if k.materia == "habitabilidad_dimensional"]
    assert len(conf) == 1
    assert len(conf[0].reglas) == 2
    assert all(conf[0].citas), "un conflicto sin ambas citas no sirve para nada"
    # Y ambas siguen aplicando: ninguna se descarta por el camino.
    dimensionales = [n for n in c.aplicables() if n.materia == "habitabilidad_dimensional"]
    assert len(dimensionales) == 2


def test_endurecimiento_declarado_no_se_reporta_como_conflicto():
    """Si el corpus declara la relación, hay jerarquía escrita, no
    contradicción. Es justo lo que se le pide al Curador."""
    c = _resolver()
    assert not [k for k in c.conflictos if k.materia == "accesibilidad"]


# --- Determinismo y frontera ------------------------------------------------

def test_determinismo():
    """Mismas entradas -> mismo resultado (TRACEABILITY.md §10)."""
    a = _resolver(sectoriales={"patrimonio": True})
    b = _resolver(sectoriales={"patrimonio": True})
    assert a.a_dict() == b.a_dict()


def test_municipio_desconocido_no_repliega():
    """Un municipio ausente del registro no produce el conjunto de Madrid."""
    from normativa.errores import AmbitoDesconocido

    try:
        _resolver(municipio="Villarriba del Alcor")
    except AmbitoDesconocido:
        pass
    else:
        raise AssertionError("un municipio desconocido no puede resolver normativa")


def test_no_se_puede_pasar_dos_fechas_de_devengo_distintas():
    """Ante dos valores contradictorios no se elige uno en silencio."""
    ctx = contexto_territorial(municipio="Madrid", tipologia="plurifamiliar", fecha_devengo=DEVENGO)
    try:
        normativa_aplicable(ctx, fecha_devengo=date(2020, 1, 1), raiz_corpus=CORPUS)
    except ValueError as exc:
        assert "contradice" in str(exc)
    else:
        raise AssertionError("dos fechas de devengo distintas deben ser un error explícito")


def test_cadena_y_perfil_sueltos_dan_el_mismo_resultado_que_el_contexto():
    """Las dos formas de llamar derivan los ejes por el mismo camino."""
    cadena = resolver_ambito(municipio="Madrid")
    perfil = perfil_proyecto(tipologia="plurifamiliar", uso="residencial.vivienda_libre")
    a = normativa_aplicable(
        cadena, perfil, fecha_devengo=DEVENGO, estricto=False,
        raiz_corpus=CORPUS, ruta_manifiesto=MANIFIESTO,
    )
    ctx = contexto_territorial(municipio="Madrid", tipologia="plurifamiliar", fecha_devengo=DEVENGO)
    b = normativa_aplicable(
        ctx, estricto=False, raiz_corpus=CORPUS, ruta_manifiesto=MANIFIESTO
    )
    assert a.a_dict() == b.a_dict()


def test_regla_cualitativa_rige_pero_no_se_puntua():
    """Cuatro de los 7 tipos de regla no son evaluables por un motor
    geométrico, y eso es correcto (NORMATIVE_ENGINE.md §6): una regla
    `exigencia_cualitativa` no desaparece —rige, se cita— pero sale
    `aplica_no_evaluable`, nunca `aplica`: prometer una comprobación que nunca
    se hace sería peor que decir que no se comprueba."""
    c = _resolver()
    resbal = next(n for n in c.normas if n.id.endswith("resbaladicidad"))
    assert resbal.estado == "aplica_no_evaluable"
    assert not resbal.evaluable
    assert "no se puntúa" in resbal.motivo


# --- Lógica ternaria (unidad) ----------------------------------------------

def test_logica_ternaria_de_kleene():
    """`NO ∧ DESCONOCIDO` es NO: una condición ya falsa lo es sin el dato que
    falta. Preguntar por un hecho que no puede cambiar el resultado es ruido, y
    el ruido en la lista de preguntas es lo que hace que se dejen de leer."""
    falsa = {"hecho": "a", "comparador": ">=", "valor": 10}
    cierta = {"hecho": "a", "comparador": "<=", "valor": 10}
    ausente = {"hecho": "z", "comparador": ">=", "valor": 1}
    h = {"a": 5}

    assert evaluar({"todas": [falsa, ausente]}, h).valor is Ternario.NO
    assert evaluar({"todas": [cierta, ausente]}, h).valor is Ternario.DESCONOCIDO
    assert evaluar({"alguna": [cierta, ausente]}, h).valor is Ternario.SI
    assert evaluar({"alguna": [falsa, ausente]}, h).valor is Ternario.DESCONOCIDO
    assert evaluar({"no": ausente}, h).valor is Ternario.DESCONOCIDO
    assert evaluar({"no": cierta}, h).valor is Ternario.NO
    assert evaluar(None, h).valor is Ternario.SI


def test_nodo_o_comparador_no_reconocido_es_indecidible_no_cierto():
    """Ignorar un nodo que no se entiende dejaría la regla aplicando
    incondicionalmente: afirmar más de lo que el corpus dice."""
    assert evaluar({"quizas": []}, {}).valor is Ternario.DESCONOCIDO
    assert evaluar({"hecho": "a", "comparador": "aproximadamente", "valor": 1}, {"a": 1}).valor is Ternario.DESCONOCIDO
    # Comparar texto con número es un error de corpus: indecidible, no excepción.
    assert evaluar({"hecho": "a", "comparador": ">=", "valor": 1}, {"a": "hola"}).valor is Ternario.DESCONOCIDO


# --- El corpus de prueba es corpus válido ----------------------------------

def test_el_fixture_pasa_las_17_validaciones():
    """Si el fixture no pasara la validación real, estaría probando el motor
    contra reglas que el corpus de producción nunca aceptaría."""
    carga = cargar(["es", "es.13", "es.13.28.28115"], raiz=CORPUS)
    assert not carga.rechazados, carga.rechazados
    assert carga.reglas


def test_manifiesto_del_fixture_cuadra_con_el_disco():
    """Validación 17 en los dos sentidos: ni declarar cobertura inexistente, ni
    tener cobertura sin declararla."""
    import yaml

    carga = cargar(["es", "es.13", "es.13.28.28115"], raiz=CORPUS)
    with MANIFIESTO.open(encoding="utf-8") as f:
        manifiesto = yaml.safe_load(f)
    fallos = validacion.validar_cobertura(manifiesto, carga.materias_por_ambito)
    # El fixture declara de más las materias estatales sin regla propia sería
    # un fallo; declararlas todas con regla es lo que se comprueba aquí.
    assert not fallos, fallos


#: Lo único que hay hoy en el corpus de producción: la regla piloto de la
#: tarea V0-5, transcrita del PDF oficial de DB-SI. Ampliar esta lista es un
#: acto consciente y va acompañado de la entrega del curador que la justifica.
CORPUS_PRODUCCION_ESPERADO = {"estatal/seguridad_incendio.yaml"}

#: Etiqueta que toda regla del corpus de producción lleva mientras no la haya
#: firmado un colegiado. Ver `docs/design/2026-08-18-ficha-de-transcripcion-
#: normativa.md` §4, criterios humanos 5-7.
TAG_SIN_FIRMAR = "pendiente_firma_colegiado"


def test_en_el_corpus_de_produccion_solo_esta_lo_que_se_espera():
    """Antes este test exigía que `normativa/es/` estuviera **vacío**, y era lo
    correcto mientras no hubiera nada transcrito: protegía contra que alguien
    copiara el fixture ficticio al corpus real.

    Desde la tarea V0-5 hay una regla real, así que el test cambia de forma
    pero no de propósito: sigue siendo la guardia contra el corpus que crece
    sin que nadie lo mire. Lo que se comprueba ahora es que el contenido es
    exactamente el declarado, y en particular **que no se ha colado nada
    ficticio** — que era el riesgo original.
    """
    from normativa.loader import RAIZ as RAIZ_CORPUS

    raiz_es = RAIZ_CORPUS / "es"
    reales = sorted(p.relative_to(raiz_es).as_posix()
                    for p in raiz_es.rglob("*.yaml")) if raiz_es.exists() else []
    assert set(reales) == CORPUS_PRODUCCION_ESPERADO, (
        f"el corpus de produccion no es el declarado: {reales}")

    texto = "\n".join((raiz_es / r).read_text(encoding="utf-8") for r in reales)
    assert "ficticio" not in texto.lower(), (
        "hay contenido del fixture ficticio en el corpus real")


def test_ninguna_regla_de_produccion_se_da_por_validada_sin_firma_humana():
    """**Este es el test que importa.** El corpus tiene contenido, pero ese
    contenido todavía no es normativa productiva: pasa las cuatro validaciones
    automáticas de la ficha y ninguna de las tres humanas.

    Mientras eso sea así, cada regla lo declara en sus `tags`. El día que un
    colegiado firme, se retira la etiqueta de esa regla y este test deja de
    exigírsela — retirarla sin firma es falsificar el estado del corpus, que es
    exactamente lo que el producto entero existe para no hacer.
    """
    from normativa.loader import cargar as cargar_produccion

    resultado = cargar_produccion(["es"])
    assert resultado.reglas, "el corpus de produccion esta vacio; revisa V0-5"
    sin_marca = [r["concept_id"] for r in resultado.reglas
                 if TAG_SIN_FIRMAR not in (r.get("tags") or [])]
    assert not sin_marca, (
        f"estas reglas se presentan como validadas sin firma de colegiado: {sin_marca}")


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
            except Exception as exc:  # noqa: BLE001
                fallos += 1
                print(f"ERROR {nombre}: {type(exc).__name__}: {exc}")
    print(f"\n{'TODO OK' if not fallos else str(fallos) + ' FALLOS'}")
    sys.exit(1 if fallos else 0)
