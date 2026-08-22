# -*- coding: utf-8 -*-
"""El sistema de Skills: memoria, efectos, verificación, ejecución y acta.

**El criterio que gobierna este fichero.** Cada garantía que el sistema promete
tiene aquí un test que la hace **fallar a propósito**. Una guarda que nunca se
ha visto morder no es una guarda, es un comentario largo: comprobar que algo
funciona cuando todo va bien es la parte fácil y la que menos dice.

Ninguno de estos tests toca la red ni gasta un token. Las Skills se ejecutan de
verdad —contra el corpus normativo real— y donde hace falta un modelo se usa el
cliente guionizado de `tests/test_agente_nucleo.py`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
if str(RAIZ / "tests") not in sys.path:
    sys.path.insert(0, str(RAIZ / "tests"))

from agente import acta as _acta  # noqa: E402
from agente import efectos  # noqa: E402
from agente import verificacion as verif  # noqa: E402
from agente.afirmacion import (  # noqa: E402
    Afirmacion,
    AfirmacionInvalida,
    CALCULO,
    INFERENCIA,
    PROPUESTA,
    calculo,
    de_capacidad,
    desconocido,
    hecho,
    propuesta,
)
from agente.carencias import (  # noqa: E402
    CarenciasEnMemoria,
    RegistroDeCarencias,
    normalizar,
    proponer,
)
from agente.copiloto import atender  # noqa: E402
from agente.ejecucion import (  # noqa: E402
    BitacoraEnFicheros,
    BitacoraEnMemoria,
    Ejecutor,
    FALLIDO,
    HECHO,
    NO_EJECUTADO,
    PENDIENTE_DE_AUTORIZACION,
    PENDIENTE_DE_DATOS,
    Paso,
    Plan,
    PlanInvalido,
)
from agente.memoria import (  # noqa: E402
    DATO,
    MemoriaDeProyecto,
    MemoriaInvalida,
    REQUISITO,
    SustratoEnFicheros,
    SustratoEnMemoria,
)
from agente.registro import (  # noqa: E402
    RegistroDeSkills,
    registro,
    registro_de_skills,
)
from agente.skill import (  # noqa: E402
    CapacidadNoDeclarada,
    Contexto,
    Entregable,
    RequisitosInsatisfechos,
    Requisito,
    ResultadoDeSkill,
    Skill,
    SkillInvalida,
)
from test_agente_nucleo import (  # noqa: E402
    BloqueHerramienta,
    BloqueTexto,
    ClienteGuionizado,
    RespuestaFalsa,
)

DATOS_DEL_PROYECTO = {
    "territorial.municipio": "Madrid",
    "proyecto.uso": "residencial.vivienda_libre",
    "proyecto.tipologia": "plurifamiliar",
    "proyecto.fecha_devengo": "2026-01-01",
    "evacuacion.numero_salidas": "una",
    "evacuacion.condicion": "general",
    "evacuacion.longitud_recorrido_m": 21.4,
}


@pytest.fixture
def memoria() -> MemoriaDeProyecto:
    m = MemoriaDeProyecto("proyecto-de-prueba", SustratoEnMemoria())
    for clave, valor in DATOS_DEL_PROYECTO.items():
        m.declarar(clave, valor, registrado_por="usuario:pablo")
    return m


@pytest.fixture
def skills() -> RegistroDeSkills:
    return registro_de_skills(recargar=True)


def _skill_de_prueba(**cambios) -> Skill:
    base = dict(
        id="prueba.demo", version="1.0.0", dominio="prueba",
        objetivo="Demostrar el sistema.", cuando_usarla="Solo en tests.",
        procedimiento=("Uno",), requiere=(), capacidades=(), produce=("prueba.valor",),
        funcion=lambda ctx: ResultadoDeSkill(
            afirmaciones=(calculo("prueba.valor", 1, fuente=ctx.firma),)
        ),
    )
    base.update(cambios)
    return Skill(**base)


# =========================================================================
# Afirmación: hecho, cálculo, inferencia, propuesta
# =========================================================================

def test_las_cuatro_naturalezas_se_distinguen():
    assert hecho("area", 412.0).naturaleza == "hecho"
    assert calculo("ocupacion", 38.0, fuente="c@1.0.0").naturaleza == CALCULO
    assert propuesta("mejora", "mover el núcleo", fuente="s@1.0.0").naturaleza == PROPUESTA
    # Solo el cálculo determinista es reproducible por un tercero.
    assert calculo("x", 1, fuente="c@1.0.0").verificable
    assert not hecho("x", 1).verificable
    assert not propuesta("x", "y", fuente="s@1.0.0").verificable


def test_una_capacidad_llm_no_puede_emitir_un_hecho_ni_un_calculo():
    """La regla del ADR, hecha cumplir por construcción y no por revisión."""
    salida = de_capacidad("resumen", "algo", capacidad_id="redaccion.resumir",
                          version="1.0.0", naturaleza_capacidad="llm")
    assert salida.naturaleza == INFERENCIA
    assert salida.hipotesis, "una inferencia de un LLM viaja con su hipótesis"

    determinista = de_capacidad("area", 412.0, capacidad_id="geo.area", version="1.0.0",
                                naturaleza_capacidad="determinista")
    assert determinista.naturaleza == CALCULO


def test_una_inferencia_sin_hipotesis_se_rechaza():
    with pytest.raises(AfirmacionInvalida, match="hipótesis"):
        Afirmacion(nombre="x", naturaleza=INFERENCIA, valor=1, origen="supuesto")


def test_un_desconocido_sin_motivo_se_rechaza():
    with pytest.raises(AfirmacionInvalida, match="motivo"):
        Afirmacion(nombre="x", naturaleza="hecho", valor=None, estado="UNKNOWN",
                   origen="observado")
    # Con motivo, sí: es un hueco declarado, no un hueco mudo.
    assert desconocido("x", "sin_dato", "no venía en el DXF").motivo is not None


def test_una_propuesta_no_tiene_origen_epistemico():
    """No es un dato del proyecto: es algo que ArchMuse sugiere."""
    with pytest.raises(AfirmacionInvalida, match="propuesta"):
        Afirmacion(nombre="x", naturaleza=PROPUESTA, valor="y", origen="observado")


# =========================================================================
# Memoria de proyecto
# =========================================================================

def test_la_memoria_es_append_only_y_conserva_la_historia():
    m = MemoriaDeProyecto("p", SustratoEnMemoria())
    m.declarar("programa.dormitorios", 3, registrado_por="cliente")
    m.declarar("programa.dormitorios", 4, registrado_por="cliente")

    assert m.valor("programa.dormitorios") == 4      # manda el último
    assert len(m.historial("programa.dormitorios")) == 2
    assert m.historial("programa.dormitorios")[0].afirmacion.valor == 3


def test_un_cambio_de_requisito_se_declara_como_conflicto():
    """No se resuelve: se declara. Elegir en silencio pierde clientes."""
    m = MemoriaDeProyecto("p", SustratoEnMemoria())
    m.declarar("programa.dormitorios", 3, registrado_por="cliente")
    m.declarar("programa.dormitorios", 4, registrado_por="cliente")

    conflictos = m.conflictos()
    assert len(conflictos) == 1
    assert (conflictos[0].anterior.afirmacion.valor, conflictos[0].vigente.afirmacion.valor) == (3, 4)


def test_un_valor_estimado_no_satisface_un_requisito_por_defecto():
    """Una tipología estimada por el sistema no es una declarada por el arquitecto."""
    from agente.afirmacion import inferencia

    m = MemoriaDeProyecto("p", SustratoEnMemoria())
    m.recordar(DATO, "proyecto.tipologia",
               inferencia("proyecto.tipologia", "plurifamiliar",
                          hipotesis=("deducida del número de portales",), fuente="x@1.0.0"),
               registrado_por="x@1.0.0")

    assert m.satisface("proyecto.tipologia") is False
    assert m.satisface("proyecto.tipologia", admite_estimado=True) is True


def test_una_propuesta_no_se_guarda_como_requisito_del_cliente():
    m = MemoriaDeProyecto("p", SustratoEnMemoria())
    with pytest.raises(MemoriaInvalida, match="cliente no la ha pedido"):
        m.recordar(REQUISITO, "x", propuesta("x", "yo haría esto", fuente="s@1.0.0"),
                   registrado_por="s@1.0.0")


def test_la_memoria_en_ficheros_sobrevive_al_proceso(tmp_path):
    sustrato = SustratoEnFicheros(tmp_path / "memoria")
    MemoriaDeProyecto("p", sustrato).declarar(
        "territorial.municipio", "Madrid", registrado_por="usuario:pablo"
    )
    # Otro objeto, otro sustrato, mismo disco: es lo que pasa al reiniciar.
    releida = MemoriaDeProyecto("p", SustratoEnFicheros(tmp_path / "memoria"))
    entrada = releida.vigente("territorial.municipio")
    assert entrada is not None
    assert entrada.afirmacion.valor == "Madrid"
    assert entrada.afirmacion.origen == "declarado"
    assert entrada.registrado_por == "usuario:pablo"


def test_el_resumen_para_el_planificador_no_lleva_los_valores():
    """Al planificador se le dice qué sabe, no cuánto ocupa."""
    m = MemoriaDeProyecto("p", SustratoEnMemoria())
    m.declarar("programa.memoria_larga", "x" * 5000, registrado_por="cliente")
    resumen = json.dumps(m.resumen(), ensure_ascii=False)
    assert "xxxx" not in resumen
    assert "programa.memoria_larga" in resumen


# =========================================================================
# Efectos y autorización
# =========================================================================

def test_el_catalogo_de_efectos_es_cerrado():
    with pytest.raises(efectos.EfectoDesconocido):
        efectos.validar(("hacer_lo_que_sea",))


def test_un_efecto_irreversible_no_se_autoriza_en_bloque():
    """«Modifica el fichero del cliente» no admite un permiso permanente."""
    with pytest.raises(ValueError, match="ejecucion"):
        efectos.Autorizacion(efecto=efectos.MODIFICA_FICHERO_DEL_CLIENTE,
                             alcance="siempre", autorizada_por="pablo")
    # Puntual sí.
    assert efectos.Autorizacion(efecto=efectos.MODIFICA_FICHERO_DEL_CLIENTE,
                                alcance="ejecucion", autorizada_por="pablo")


def test_una_autorizacion_sin_firma_no_es_una_autorizacion():
    with pytest.raises(ValueError, match="firma"):
        efectos.Autorizacion(efecto=efectos.GASTA_TOKENS, alcance="proyecto",
                             autorizada_por="")


def test_el_portero_dice_exactamente_que_falta():
    autorizadas = efectos.Autorizaciones.de([efectos.GASTA_TOKENS], por="pablo")
    with pytest.raises(efectos.EfectoNoAutorizado) as exc:
        autorizadas.exigir("skill.x", (efectos.GASTA_TOKENS, efectos.ESCRIBE_FICHERO))
    assert exc.value.efectos == (efectos.ESCRIBE_FICHERO,)


def test_la_solicitud_de_permiso_se_lee_en_castellano():
    """Lo que ve quien autoriza, no lo que ve el programador."""
    peticion = efectos.solicitud("skill.x", (efectos.MODIFICA_FICHERO_DEL_CLIENTE,))
    uno = peticion["efectos"][0]
    assert uno["descripcion"] == "Modificar un fichero aportado por el cliente"
    assert uno["reversible"] is False
    assert uno["alcance_maximo"] == "ejecucion"


# =========================================================================
# Verificación
# =========================================================================

def test_sin_comprobaciones_no_hay_verificado():
    """«No había nada que comprobar» no puede leerse como «lo he comprobado»."""
    assert verif.dictaminar([], ResultadoDeSkill()).verificado is False


def test_una_verificacion_que_falla_impide_dar_el_resultado_por_bueno():
    resultado = ResultadoDeSkill(afirmaciones=(calculo("area", 4_000_000.0, fuente="c@1.0.0"),))
    dictamen = verif.dictaminar([verif.valor_dentro_de("area", maximo=1000)], resultado)
    assert dictamen.verificado is False
    assert "por encima" in dictamen.avisos[0]


def test_una_verificacion_que_revienta_cuenta_como_fallo_y_no_como_caida():
    def _explota(_resultado):
        raise RuntimeError("me he roto")

    rota = verif.Verificacion(nombre="rota", descripcion="x", funcion=_explota)
    dictamen = verif.dictaminar([rota], ResultadoDeSkill())
    assert dictamen.verificado is False
    assert "RuntimeError" in dictamen.avisos[0]


def test_una_cifra_sin_fuente_no_pasa_la_generica():
    huerfana = Afirmacion(nombre="area", naturaleza="calculo", valor=1.0,
                          origen="derivado", fuente="")
    dictamen = verif.dictaminar([verif.toda_cifra_tiene_fuente()],
                                ResultadoDeSkill(afirmaciones=(huerfana,)))
    assert dictamen.verificado is False


# =========================================================================
# Skill: las cinco garantías
# =========================================================================

def test_un_requisito_insatisfecho_produce_la_pregunta_y_no_ejecuta_nada():
    ejecutada = []

    skill = _skill_de_prueba(
        requiere=(Requisito(clave="proyecto.altura", pregunta="¿Qué altura tiene?"),),
        funcion=lambda ctx: ejecutada.append(1) or ResultadoDeSkill(),
    )
    vacia = MemoriaDeProyecto("p", SustratoEnMemoria())
    with pytest.raises(RequisitosInsatisfechos) as exc:
        skill.ejecutar(Contexto(skill, memoria=vacia, registro=registro()))

    assert exc.value.preguntas == ("¿Qué altura tiene?",)
    assert ejecutada == [], "no se ejecuta nada: el chequeo es previo y gratis"


def test_una_skill_no_puede_usar_una_capacidad_que_no_declara(memoria):
    skill = _skill_de_prueba(
        capacidades=(),
        funcion=lambda ctx: ctx.invocar("territorial.resolver_ambito", municipio="Madrid"),
    )
    with pytest.raises(CapacidadNoDeclarada, match="no declara la capacidad"):
        skill.ejecutar(Contexto(skill, memoria=memoria, registro=registro()))


def test_una_skill_que_no_declara_el_efecto_no_puede_escribir_en_la_memoria(memoria):
    skill = _skill_de_prueba(
        efectos=(),
        funcion=lambda ctx: ctx.memoria.declarar("x", 1, registrado_por="y"),
    )
    with pytest.raises(AttributeError, match="no declara el efecto"):
        skill.ejecutar(Contexto(skill, memoria=memoria, registro=registro()))


def test_lo_que_el_manifiesto_promete_se_comprueba(memoria):
    """`produce` es una promesa, no documentación."""
    incumplidora = _skill_de_prueba(
        produce=("prueba.valor", "prueba.olvidado"),
    )
    salida = incumplidora.ejecutar(Contexto(incumplidora, memoria=memoria, registro=registro()))
    assert salida.verificado is False
    assert any("prueba.olvidado" in a for a in salida.dictamen.avisos)


def test_no_existe_entregable_que_no_sea_borrador():
    with pytest.raises(SkillInvalida, match="borrador"):
        Entregable(nombre="memoria.pdf", tipo="pdf", borrador=False)


def test_una_skill_mal_declarada_no_se_construye():
    with pytest.raises(SkillInvalida, match="semver"):
        _skill_de_prueba(version="1.0")
    with pytest.raises(SkillInvalida, match="dominio"):
        _skill_de_prueba(id="sindominio")
    with pytest.raises(SkillInvalida, match="no declara qué produce"):
        _skill_de_prueba(produce=())


# =========================================================================
# Registro de Skills
# =========================================================================

def test_las_skills_se_descubren_y_estan_validadas(skills):
    assert set(skills.ids()) == {
        "territorial.ficha_normativa_de_parcela",
        "revision.recorridos_de_evacuacion",
        "programa.registrar_requisitos_del_cliente",
        # El procedimiento del primer vertical (tarea SK-1, 2026-08-19). Es la
        # primera Skill con efectos: la que entrega un fichero.
        "superficies.cuadro_de_vivienda",
        # El segundo entregable profesional (tarea CO-5, 2026-08-19), y el
        # primero que NO depende del corpus normativo: repasa el plano contra
        # sí mismo antes de entregarlo.
        "revision.coherencia_del_plano",
        # El tercero (tarea SK-10, 2026-08-19): mide una planta ENTERA, con
        # todas sus viviendas, sin necesitar que el plano traiga dibujado
        # ningún cuadro de superficies. Es el caso normal de un edificio
        # residencial, y era el que el producto no sabía hacer.
        "superficies.medicion_de_planta",
    }
    for skill in skills:
        # Sus capacidades existen, Y declara los efectos de esas capacidades
        # (invariante añadido con TL-2: el manifiesto no puede mentir por
        # omisión sobre lo que le va a pasar al ordenador del arquitecto).
        skill.comprobar_registro(registro())


def test_una_skill_se_puede_pedir_por_version_exacta():
    """Es lo que permite reproducir un informe de hace seis meses."""
    reg = RegistroDeSkills((_skill_de_prueba(version="1.0.0"),
                            _skill_de_prueba(version="2.0.0")))
    assert reg.buscar("prueba.demo").version == "2.0.0"        # la última
    assert reg.buscar("prueba.demo@1.0.0").version == "1.0.0"  # la de entonces


def test_una_skill_que_declara_una_capacidad_inexistente_falla_al_cargarse():
    """Al arrancar, no delante de un cliente."""
    mentirosa = _skill_de_prueba(capacidades=("geometria.que_no_existe",))
    with pytest.raises(SkillInvalida, match="que no existe"):
        mentirosa.comprobar_registro(registro())


def test_una_skill_nueva_aparece_sin_tocar_ningun_init():
    destino = RAIZ / "agente" / "skills" / "zzz_prueba_descubrimiento.py"
    destino.write_text(
        "# -*- coding: utf-8 -*-\n"
        "from agente.skill import ResultadoDeSkill, Skill\n"
        "from agente.afirmacion import calculo\n"
        "SKILLS = (Skill(id='prueba.descubierta', version='0.1.0', dominio='prueba',\n"
        "    objetivo='x', cuando_usarla='y', procedimiento=('z',), requiere=(),\n"
        "    capacidades=(), produce=('prueba.k',),\n"
        "    funcion=lambda ctx: ResultadoDeSkill(\n"
        "        afirmaciones=(calculo('prueba.k', 1, fuente=ctx.firma),))),)\n",
        encoding="utf-8",
    )
    try:
        assert "prueba.descubierta" in registro_de_skills(recargar=True).ids()
    finally:
        destino.unlink()
        registro_de_skills(recargar=True)
    assert "prueba.descubierta" not in registro_de_skills(recargar=True).ids()


# =========================================================================
# Ejecución: fallo aislado, reanudación, autorización
# =========================================================================

def _plan(*pasos, objetivo="prueba") -> Plan:
    return Plan(objetivo=objetivo, proyecto_id="proyecto-de-prueba", pasos=tuple(pasos))


def test_un_plan_con_ciclo_se_rechaza_antes_de_ejecutar_nada():
    plan = _plan(Paso(id="a", skill="prueba.demo", depende_de=("b",)),
                 Paso(id="b", skill="prueba.demo", depende_de=("a",)))
    reg = RegistroDeSkills((_skill_de_prueba(),))
    assert any("ciclo" in m for m in plan.validar(reg))
    with pytest.raises(PlanInvalido):
        plan.orden()


def test_un_paso_que_falla_no_aborta_las_ramas_independientes(memoria):
    def _explota(_ctx):
        raise RuntimeError("el corpus no está")

    reg = RegistroDeSkills((
        _skill_de_prueba(id="prueba.buena"),
        _skill_de_prueba(id="prueba.mala", funcion=_explota),
        _skill_de_prueba(id="prueba.dependiente"),
    ))
    plan = _plan(
        Paso(id="mala", skill="prueba.mala"),
        Paso(id="independiente", skill="prueba.buena"),
        Paso(id="dependiente", skill="prueba.dependiente", depende_de=("mala",)),
    )
    resultado = Ejecutor(capacidades=registro(), skills=reg).ejecutar(
        plan, memoria, ejecucion_id="e-fallo"
    )
    por_id = {p.paso_id: p for p in resultado.pasos}
    assert por_id["mala"].estado == FALLIDO
    assert "RuntimeError" in por_id["mala"].motivo
    assert por_id["independiente"].estado == HECHO, "una rama sana sigue adelante"
    assert por_id["dependiente"].estado == NO_EJECUTADO
    assert resultado.completa is False
    assert len(resultado.no_hecho) == 2, "el informe dice qué faltó y por qué"


def test_una_ejecucion_interrumpida_se_reanuda_sin_repetir_lo_hecho(memoria):
    """El comportamiento que sustituye a un sistema de ejecución durable."""
    veces = {"a": 0, "b": 0}

    def _contar(clave):
        def _fn(ctx):
            veces[clave] += 1
            return ResultadoDeSkill(
                afirmaciones=(calculo("prueba.valor", veces[clave], fuente=ctx.firma),)
            )
        return _fn

    def _explota(_ctx):
        raise RuntimeError("corte de luz")

    bitacora = BitacoraEnMemoria()
    reg_rota = RegistroDeSkills((
        _skill_de_prueba(id="prueba.a", funcion=_contar("a")),
        _skill_de_prueba(id="prueba.b", funcion=_explota),
    ))
    plan = _plan(Paso(id="p1", skill="prueba.a"), Paso(id="p2", skill="prueba.b"))

    primera = Ejecutor(capacidades=registro(), skills=reg_rota, bitacora=bitacora).ejecutar(
        plan, memoria, ejecucion_id="e-reanuda"
    )
    assert primera.completa is False
    assert veces["a"] == 1

    # Se arregla lo que fallaba y se relanza la MISMA ejecución.
    reg_sana = RegistroDeSkills((
        _skill_de_prueba(id="prueba.a", funcion=_contar("a")),
        _skill_de_prueba(id="prueba.b", funcion=_contar("b")),
    ))
    segunda = Ejecutor(capacidades=registro(), skills=reg_sana, bitacora=bitacora).ejecutar(
        plan, memoria, ejecucion_id="e-reanuda"
    )
    assert segunda.completa is True
    assert veces["a"] == 1, "el paso ya hecho NO se repite"
    assert veces["b"] == 1
    assert segunda.reanudados == ("p1",)


def test_la_bitacora_en_ficheros_sirve_para_reanudar_tras_reiniciar(tmp_path, memoria):
    veces = {"n": 0}

    def _fn(ctx):
        veces["n"] += 1
        return ResultadoDeSkill(afirmaciones=(calculo("prueba.valor", 1, fuente=ctx.firma),))

    reg = RegistroDeSkills((_skill_de_prueba(funcion=_fn),))
    plan = _plan(Paso(id="p1", skill="prueba.demo"))

    Ejecutor(capacidades=registro(), skills=reg,
             bitacora=BitacoraEnFicheros(tmp_path)).ejecutar(
        plan, memoria, ejecucion_id="e-disco")
    # Otro ejecutor, otra bitácora, mismo disco: es lo que ocurre al reiniciar.
    segunda = Ejecutor(capacidades=registro(), skills=reg,
                       bitacora=BitacoraEnFicheros(tmp_path)).ejecutar(
        plan, memoria, ejecucion_id="e-disco")

    assert veces["n"] == 1
    assert segunda.reanudados == ("p1",)


def test_sin_autorizacion_el_efecto_no_se_aplica(memoria, skills):
    """La prueba de que el portero no es decorativo: la memoria queda intacta."""
    plan = _plan(Paso(id="req", skill="programa.registrar_requisitos_del_cliente",
                      argumentos={"requisitos": {"programa.dormitorios": 4},
                                  "origen": "correo"}))
    resultado = Ejecutor(capacidades=registro(), skills=skills).ejecutar(
        plan, memoria, ejecucion_id="e-sin-permiso"
    )
    assert resultado.pasos[0].estado == PENDIENTE_DE_AUTORIZACION
    assert resultado.efectos_pendientes == (efectos.ESCRIBE_MEMORIA,)
    assert memoria.vigente("programa.dormitorios") is None, "no se ha escrito nada"


def test_con_autorizacion_el_efecto_se_aplica(memoria, skills):
    plan = _plan(Paso(id="req", skill="programa.registrar_requisitos_del_cliente",
                      argumentos={"requisitos": {"programa.dormitorios": 4},
                                  "origen": "correo del 12/08"}))
    resultado = Ejecutor(capacidades=registro(), skills=skills).ejecutar(
        plan, memoria, ejecucion_id="e-con-permiso",
        autorizaciones=efectos.Autorizaciones.de([efectos.ESCRIBE_MEMORIA], por="pablo"),
    )
    assert resultado.pasos[0].estado == HECHO
    assert memoria.valor("programa.dormitorios") == 4
    assert "correo del 12/08" in memoria.vigente("programa.dormitorios").registrado_por


def test_un_paso_con_requisitos_sin_cumplir_devuelve_la_pregunta(skills):
    vacia = MemoriaDeProyecto("proyecto-de-prueba", SustratoEnMemoria())
    plan = _plan(Paso(id="ficha", skill="territorial.ficha_normativa_de_parcela"))
    resultado = Ejecutor(capacidades=registro(), skills=skills).ejecutar(
        plan, vacia, ejecucion_id="e-sin-datos"
    )
    assert resultado.pasos[0].estado == PENDIENTE_DE_DATOS
    assert any("municipio" in q for q in resultado.preguntas)


# =========================================================================
# Las Skills reales, contra el corpus real
# =========================================================================

def test_la_cadena_completa_produce_el_umbral_del_boe(memoria, skills):
    """Dos Skills encadenadas, y el 25 sale del PDF oficial vía el corpus."""
    plan = _plan(
        Paso(id="ficha", skill="territorial.ficha_normativa_de_parcela"),
        Paso(id="evac", skill="revision.recorridos_de_evacuacion", depende_de=("ficha",)),
        objetivo="Comprueba la parcela y los recorridos de evacuación",
    )
    resultado = Ejecutor(capacidades=registro(), skills=skills).ejecutar(
        plan, memoria, ejecucion_id="e-cadena"
    )
    assert resultado.completa

    datos = {}
    for paso in resultado.pasos:
        for a in paso.salida["resultado"]["afirmaciones"]:
            datos[a["nombre"]] = a

    assert datos["territorial.codigo_ine"]["valor"] == "28079"
    assert datos["evacuacion.umbral_m"]["valor"] == 25
    assert datos["evacuacion.holgura_m"]["valor"] == pytest.approx(3.6)
    assert datos["evacuacion.cumple"]["valor"] is True
    assert "BOE-A-2006-5515" in datos["evacuacion.umbral_m"]["cita"]
    # Y las doce materias que NO se han comprobado están dichas por su nombre.
    assert len(datos["normativa.materias_sin_cobertura"]["valor"]) >= 10


def test_sin_umbral_aplicable_no_se_da_un_veredicto(skills):
    """La propiedad que sostiene todo: cuando no se sabe, no se contesta."""
    m = MemoriaDeProyecto("proyecto-de-prueba", SustratoEnMemoria())
    datos = dict(DATOS_DEL_PROYECTO)
    datos["evacuacion.condicion"] = "una_condicion_que_no_esta_en_la_tabla"
    for clave, valor in datos.items():
        m.declarar(clave, valor, registrado_por="usuario:pablo")

    plan = _plan(Paso(id="evac", skill="revision.recorridos_de_evacuacion"))
    resultado = Ejecutor(capacidades=registro(), skills=skills).ejecutar(
        plan, m, ejecucion_id="e-sin-umbral"
    )
    afirmaciones = {
        a["nombre"]: a for a in resultado.pasos[0].salida["resultado"]["afirmaciones"]
    }
    assert afirmaciones["evacuacion.cumple"]["valor"] is None
    assert afirmaciones["evacuacion.cumple"]["estado"] == "UNKNOWN"
    assert afirmaciones["evacuacion.cumple"]["motivo"]["codigo"] == "umbral_sin_valor"


def test_la_verificacion_de_coherencia_del_veredicto_puede_fallar(memoria, skills):
    """Se fuerza la contradicción a mano: una verificación que no puede fallar
    no vale nada, y esta tiene que poder."""
    from agente.skills import evacuacion

    resultado = ResultadoDeSkill(afirmaciones=(
        calculo("evacuacion.cumple", True, fuente="s@1.0.0"),
        calculo("evacuacion.holgura_m", -4.0, fuente="s@1.0.0", unidad="m"),
    ))
    veredicto = evacuacion._coherencia_del_veredicto(resultado)
    assert veredicto is not True
    assert "contradice" in veredicto


# =========================================================================
# Acta de procedencia
# =========================================================================

def test_el_acta_dice_de_donde_sale_cada_numero_y_que_no_se_comprobo(memoria, skills):
    plan = _plan(
        Paso(id="ficha", skill="territorial.ficha_normativa_de_parcela"),
        Paso(id="evac", skill="revision.recorridos_de_evacuacion", depende_de=("ficha",)),
        objetivo="Revisión de evacuación",
    )
    resultado = Ejecutor(capacidades=registro(), skills=skills).ejecutar(
        plan, memoria, ejecucion_id="e-acta"
    )
    documento = _acta.levantar(resultado, capacidades=registro(), skills=skills)

    texto = documento.a_texto()
    assert "BORRADOR PARA REVISIÓN DE UN COLEGIADO" in texto
    assert "revision.recorridos_de_evacuacion@1.0.0" in texto
    assert "normativa.umbral_de_regla@1.1.0" in texto      # la capacidad concreta
    assert "QUÉ NO SE HA COMPROBADO" in texto

    # La lista de «no comprobado» se DERIVA de los manifiestos: si mañana se
    # añade una limitación a una Skill, aparece aquí sin tocar el acta.
    assert any("no comprueba" in n for n in documento.no_comprobado)
    assert any("firma colegiada" in n for n in documento.no_comprobado)


def test_el_sello_del_acta_cambia_si_cambia_su_contenido():
    base = _acta.Acta(objetivo="x", proyecto_id="p", ejecucion_id="e", emitida_en="2026-01-01")
    igual = _acta.Acta(objetivo="x", proyecto_id="p", ejecucion_id="e", emitida_en="2026-01-01")
    distinta = _acta.Acta(objetivo="y", proyecto_id="p", ejecucion_id="e",
                          emitida_en="2026-01-01")
    assert base.sello == igual.sello
    assert base.sello != distinta.sello


def test_un_paso_no_verificado_se_declara_en_el_acta(memoria):
    incumplidora = _skill_de_prueba(produce=("prueba.valor", "prueba.olvidado"))
    reg = RegistroDeSkills((incumplidora,))
    resultado = Ejecutor(capacidades=registro(), skills=reg).ejecutar(
        _plan(Paso(id="p1", skill="prueba.demo")), memoria, ejecucion_id="e-noverif"
    )
    documento = _acta.levantar(resultado, capacidades=registro(), skills=reg)
    assert any("no ha superado sus propias comprobaciones" in n
               for n in documento.no_comprobado)


# =========================================================================
# Carencias: proponer sin instalar
# =========================================================================

def test_una_carencia_madura_a_la_segunda_peticion_distinta():
    registro_de_carencias = RegistroDeCarencias(CarenciasEnMemoria())
    registro_de_carencias.anotar("Hazme los planos de carpintería")
    assert registro_de_carencias.maduras() == ()

    registro_de_carencias.anotar("Prepárame los planos de carpinterías")
    maduras = registro_de_carencias.maduras()
    assert len(maduras) == 1
    assert maduras[0].veces == 2


def test_repetir_la_misma_frase_no_madura_una_carencia():
    """Insistir no es señal: son peticiones distintas lo que cuenta."""
    r = RegistroDeCarencias(CarenciasEnMemoria())
    for _ in range(5):
        r.anotar("hazme los planos")
    assert r.maduras() == ()


def test_la_normalizacion_agrupa_lo_que_es_la_misma_peticion():
    """Sin esto, dos formas de pedir lo mismo nunca llegarian al umbral."""
    assert (normalizar("Hazme los planos de carpinteria")
            == normalizar("Preparame planos de carpinterias"))
    assert normalizar("revisa el modelo BIM") != normalizar("revisa la memoria")


def test_la_propuesta_es_un_borrador_y_deja_lo_profesional_a_un_humano():
    borrador = proponer("hazme los detalles constructivos",
                        capacidades_disponibles=("territorial.resolver_ambito",))
    assert borrador["estado"].startswith("PROPUESTA")
    assert any("procedimiento" in p for p in borrador["por_rellenar_por_un_humano"])
    assert "no instala Skills por su cuenta" in borrador["aviso"]


def test_el_agente_no_tiene_ninguna_via_para_escribir_una_skill():
    """No es una promesa del docstring: se comprueba sobre el código.

    Si algún día alguien añade una escritura a `agente/skills/`, este test se
    pone rojo antes de que llegue a producción — que es donde tiene que
    detectarse un sistema que se amplía a sí mismo.
    """
    sospechosas = []
    for fichero in sorted((RAIZ / "agente").rglob("*.py")):
        codigo = fichero.read_text(encoding="utf-8")
        for linea_n, linea in enumerate(codigo.splitlines(), 1):
            escribe = ("write_text(" in linea or "open(" in linea and '"w"' in linea
                       or "'w'" in linea)
            if escribe and "skills" in linea:
                sospechosas.append("%s:%d" % (fichero.name, linea_n))
    assert sospechosas == [], (
        "ArchMuse no puede instalar Skills por su cuenta: %s" % sospechosas
    )


# =========================================================================
# La fachada
# =========================================================================

def test_la_entrega_trae_siempre_su_acta(memoria):
    cliente = ClienteGuionizado(
        RespuestaFalsa(
            BloqueHerramienta("skill__territorial__ficha_normativa_de_parcela", {}, "k1")
        ),
        RespuestaFalsa(BloqueTexto("Rige el DB-SI; hay materias sin comprobar.")),
    )
    entrega = atender("Comprueba esta parcela y su normativa", cliente, memoria)

    assert entrega.texto
    assert entrega.acta.sello
    assert entrega.acta.leyenda.startswith("BORRADOR")
    assert entrega.fundamentada, entrega.respuesta.cifras_sin_respaldo
    assert entrega.respuesta.pasos_de_skill[0].estado == HECHO


def test_una_skill_con_efecto_pide_permiso_desde_la_conversacion(memoria):
    cliente = ClienteGuionizado(
        RespuestaFalsa(BloqueHerramienta(
            "skill__programa__registrar_requisitos_del_cliente",
            {"requisitos": {"programa.dormitorios": 4}, "origen": "correo"}, "k1")),
        RespuestaFalsa(BloqueTexto("Necesito que autorices escribir en la memoria.")),
    )
    entrega = atender("Apunta que quieren 4 dormitorios", cliente, memoria)

    assert entrega.efectos_pendientes == (efectos.ESCRIBE_MEMORIA,)
    assert memoria.vigente("programa.dormitorios") is None


def test_sin_memoria_de_proyecto_no_se_ofrecen_skills():
    """Una Skill comprueba sus requisitos contra la memoria: sin memoria, todas
    dirían que les falta todo. Ofrecerlas rotas es peor que no ofrecerlas."""
    from agente.nucleo import ejecutar as bucle

    cliente = ClienteGuionizado(RespuestaFalsa(BloqueTexto("Hola.")))
    bucle("Hola", cliente)
    nombres = [h["name"] for h in cliente.llamadas[0]["tools"]]
    assert not any(n.startswith("skill__") for n in nombres)


def test_con_memoria_las_skills_se_ofrecen_junto_a_las_capacidades(memoria):
    from agente.nucleo import ejecutar as bucle

    cliente = ClienteGuionizado(RespuestaFalsa(BloqueTexto("Hola.")))
    bucle("Hola", cliente, memoria=memoria)
    nombres = [h["name"] for h in cliente.llamadas[0]["tools"]]
    assert sum(1 for n in nombres if n.startswith("skill__")) == len(registro_de_skills())
    assert "territorial__resolver_ambito" in nombres


def test_ninguna_skill_sabe_de_transporte():
    """La prueba del plugin: una Skill se invoca igual desde la web, desde Revit
    o desde un `python -c`. Si importa Flask, no."""
    import re

    prohibido = re.compile(r"^\s*(from|import)\s+(flask|fastapi|django|werkzeug)\b", re.M)
    culpables = [
        f.name for f in sorted((RAIZ / "agente" / "skills").rglob("*.py"))
        if prohibido.search(f.read_text(encoding="utf-8"))
    ]
    assert culpables == []


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
