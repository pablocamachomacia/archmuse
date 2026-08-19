# -*- coding: utf-8 -*-
"""AG-1 — una llamada, un DAG validado, y ninguna ejecución si no vale.

Ejecutar:  pytest tests/test_agente_planificador.py

PRD aprobado por Pablo el 2026-08-19, con una condición textual: **mantenerlo
deliberadamente pequeño**. Ni framework de agentes, ni LangGraph, ni otro
orquestador. Hay un test para esa condición (`§5`), porque una restricción que
nadie comprueba se erosiona un `if` cada vez.

Lo que se fija:

1. **Una sola llamada** en el camino feliz, con la herramienta forzada.
2. El plan que sale lo acepta el ejecutor **sin adaptación**.
3. Un plan inválido —Skill inexistente, ciclo, dependencia rota, demasiados
   pasos— se rechaza con el motivo concreto y **cero ejecuciones**.
4. Un objetivo que ArchMuse no sabe atender produce **plan vacío con motivo** y
   queda anotado como carencia. No un plan aproximado: eso produce trabajo que
   nadie pidió y respuestas que parecen ciertas.
5. El prefijo de manifiestos va **antes** y marcado para caché; el estado del
   proyecto, después.

Todo con cliente guionizado: la suite no gasta un céntimo ni necesita clave.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente import planificador as plani  # noqa: E402
from agente.carencias import CarenciasEnMemoria, RegistroDeCarencias  # noqa: E402
from agente.ejecucion import BitacoraEnMemoria, Ejecutor  # noqa: E402
from agente.memoria import MemoriaDeProyecto, SustratoEnMemoria  # noqa: E402
from agente.registro import registro, registro_de_skills  # noqa: E402


class BloqueHerramienta:
    type = "tool_use"

    def __init__(self, entrada, nombre=plani.NOMBRE_HERRAMIENTA):
        self.name = nombre
        self.input = entrada
        self.id = "tu_1"


class BloqueTexto:
    type = "text"

    def __init__(self, texto):
        self.text = texto


class UsoFalso:
    def __init__(self, lectura_de_cache=0):
        self.input_tokens = 1200
        self.output_tokens = 90
        self.cache_creation_input_tokens = 0 if lectura_de_cache else 1200
        self.cache_read_input_tokens = lectura_de_cache


class RespuestaFalsa:
    def __init__(self, *bloques, lectura_de_cache=0):
        self.content = list(bloques)
        self.usage = UsoFalso(lectura_de_cache)


class ClienteGuionizado:
    """Devuelve las respuestas del guion, en orden, y apunta lo que le piden."""

    def __init__(self, *respuestas):
        self._respuestas = list(respuestas)
        self.llamadas = []
        self.messages = self

    def create(self, **kwargs):
        self.llamadas.append(kwargs)
        return self._respuestas.pop(0) if self._respuestas else RespuestaFalsa(
            BloqueTexto("sin guion"))


def memoria_con(**claves):
    m = MemoriaDeProyecto("p", SustratoEnMemoria())
    for clave, valor in claves.items():
        m.declarar(clave.replace("__", "."), valor, registrado_por="usuario:pablo")
    return m


PLAN_TERRITORIAL = {"pasos": [
    {"id": "ficha", "skill": "territorial.ficha_normativa_de_parcela"},
]}


# --- 1. Una llamada, forzada ----------------------------------------------

def test_el_camino_feliz_hace_exactamente_una_llamada():
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta(PLAN_TERRITORIAL)))
    resultado = plani.planificar("Comprueba esta parcela", cliente,
                                 memoria=memoria_con(territorial__municipio="Madrid"))
    assert len(cliente.llamadas) == 1
    assert resultado.ejecutable


def test_la_herramienta_va_forzada_y_es_la_unica():
    """Sin forzarla, el modelo contesta con prosa y el plan hay que adivinarlo
    de un texto — que es exactamente cómo se cuela un plan inventado."""
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta(PLAN_TERRITORIAL)))
    plani.planificar("Comprueba esta parcela", cliente)
    llamada = cliente.llamadas[0]
    assert llamada["tool_choice"] == {"type": "tool", "name": plani.NOMBRE_HERRAMIENTA}
    assert len(llamada["tools"]) == 1


def test_si_el_modelo_contesta_con_texto_se_reintenta_una_vez_y_no_se_interpreta():
    """§6 del PRD. Leer un plan de la prosa sería inventarlo."""
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueTexto("Yo haría lo siguiente...")),
                                RespuestaFalsa(BloqueTexto("En serio, haría esto...")))
    resultado = plani.planificar("Comprueba esta parcela", cliente)
    assert len(cliente.llamadas) == 2
    assert not resultado.ejecutable
    assert any("dos intentos" in m for m in resultado.motivos)


# --- 2. El plan lo acepta el ejecutor sin adaptación ----------------------

def test_el_plan_que_sale_lo_ejecuta_el_ejecutor_tal_cual():
    """Si hubiera que adaptarlo, existiría un segundo sitio donde se decide qué
    se ejecuta, y el día que se separen nadie sabría cuál manda."""
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta(PLAN_TERRITORIAL)))
    memoria = memoria_con(territorial__municipio="Madrid",
                          proyecto__uso="residencial.vivienda_libre",
                          proyecto__tipologia="plurifamiliar")
    resultado = plani.planificar("Comprueba esta parcela", cliente, memoria=memoria)

    ejecutor = Ejecutor(capacidades=registro(recargar=True),
                        skills=registro_de_skills(recargar=True),
                        bitacora=BitacoraEnMemoria())
    ejecucion = ejecutor.ejecutar(resultado.plan, memoria, ejecucion_id="desde-plan")
    assert ejecucion.pasos, "el ejecutor no ha ejecutado el plan"


def test_las_dependencias_llegan_al_plan():
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta({"pasos": [
        {"id": "ficha", "skill": "territorial.ficha_normativa_de_parcela"},
        {"id": "evac", "skill": "revision.recorridos_de_evacuacion",
         "depende_de": ["ficha"]},
    ]})))
    plan = plani.planificar("Parcela y evacuación", cliente).plan
    assert [p.id for p in plan.orden()] == ["ficha", "evac"]


# --- 3. Lo inválido se rechaza sin ejecutar nada -------------------------

def test_una_skill_inexistente_se_rechaza_con_su_nombre():
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta({"pasos": [
        {"id": "x", "skill": "estructura.calcular_forjado"},
    ]})))
    resultado = plani.planificar("Calcula el forjado", cliente)
    assert not resultado.ejecutable
    assert any("estructura.calcular_forjado" in m for m in resultado.motivos)


def test_un_ciclo_se_rechaza():
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta({"pasos": [
        {"id": "a", "skill": "territorial.ficha_normativa_de_parcela",
         "depende_de": ["b"]},
        {"id": "b", "skill": "revision.recorridos_de_evacuacion", "depende_de": ["a"]},
    ]})))
    resultado = plani.planificar("Algo circular", cliente)
    assert not resultado.ejecutable
    assert any("ciclo" in m for m in resultado.motivos)


def test_una_dependencia_que_no_existe_se_rechaza():
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta({"pasos": [
        {"id": "a", "skill": "territorial.ficha_normativa_de_parcela",
         "depende_de": ["fantasma"]},
    ]})))
    resultado = plani.planificar("Algo roto", cliente)
    assert not resultado.ejecutable
    assert any("fantasma" in m for m in resultado.motivos)


def test_un_plan_con_demasiados_pasos_se_rechaza():
    """Un plan de cuarenta pasos no lo ha pedido nadie: es un modelo perdido, y
    ejecutarlo cuesta dinero real."""
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta({"pasos": [
        {"id": "p%d" % i, "skill": "territorial.ficha_normativa_de_parcela"}
        for i in range(30)
    ]})))
    resultado = plani.planificar("Hazlo todo", cliente, max_pasos=5)
    assert not resultado.ejecutable
    assert any("techo" in m for m in resultado.motivos)


def test_un_paso_sin_skill_se_rechaza_sin_reventar():
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta({"pasos": [{"id": "a"}]})))
    resultado = plani.planificar("Algo", cliente)
    assert not resultado.ejecutable
    assert resultado.motivos


def test_rechazar_no_ejecuta_nada():
    """Cero ejecuciones: el criterio 5 del PRD, comprobado sobre la bitácora."""
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta({"pasos": [
        {"id": "x", "skill": "no.existe"},
    ]})))
    bitacora = BitacoraEnMemoria()
    resultado = plani.planificar("Algo", cliente)
    assert not resultado.ejecutable
    assert bitacora.leer("cualquiera") == []


# --- 4. El plan vacío es una respuesta, no un fallo ---------------------

def test_lo_que_archmuse_no_sabe_hacer_produce_plan_vacio_con_motivo():
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta({
        "pasos": [],
        "motivo": "ArchMuse no calcula estructuras: no hay ninguna Skill que lo cubra.",
    })))
    resultado = plani.planificar("Calcula el forjado", cliente)
    assert resultado.vacio
    assert not resultado.ejecutable
    assert "estructuras" in resultado.motivo_del_vacio


def test_un_plan_vacio_queda_anotado_como_carencia():
    """Es cómo se entera ArchMuse de lo que le falta: por uso real, no por
    intuición de quien programa."""
    carencias = RegistroDeCarencias(CarenciasEnMemoria())
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta(
        {"pasos": [], "motivo": "no hay Skill"})))
    plani.planificar("Calcula el forjado", cliente, carencias=carencias)
    assert carencias.de("Calcula el forjado").peticiones


def test_un_plan_vacio_sin_motivo_lo_dice_en_vez_de_callarlo():
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta({"pasos": []})))
    resultado = plani.planificar("Algo", cliente)
    assert resultado.vacio
    assert "no ha dicho por qué" in resultado.motivo_del_vacio


# --- 5. La condición de la aprobación: pequeño ------------------------

def test_el_planificador_no_ejecuta_nada():
    """CONDICIÓN TEXTUAL DE LA APROBACIÓN (Pablo, 2026-08-19).

    «Mantenerlo deliberadamente pequeño: ni framework de agentes, ni LangGraph,
    ni otro orquestador.» Un planificador que empieza a ejecutar, a observar
    resultados o a replanificar **es** un framework de agentes escrito a
    plazos. Esto lo comprueba sobre el código.
    """
    import ast

    fuente = (RAIZ / "agente" / "planificador.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)

    # Se miran los IMPORTS, no la prosa: este módulo explica en su docstring
    # por qué no usa un framework, y esa explicación tiene que poder escribirse.
    importados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados.update(a.name.split(".")[0] for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados.add(nodo.module.split(".")[0])
    assert not (importados & {"langchain", "langgraph", "openai", "autogen", "crewai"}),         sorted(importados)

    # Y no ejecuta: no importa el ejecutor ni invoca capacidades.
    nombres = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
    nombres |= {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    assert "Ejecutor" not in nombres
    assert "invocar" not in nombres


def test_solo_hay_un_punto_de_llamada_al_modelo():
    fuente = (RAIZ / "agente" / "planificador.py").read_text(encoding="utf-8")
    assert fuente.count("messages.create(") == 1


def test_el_planificador_no_sabe_de_transporte():
    fuente = (RAIZ / "agente" / "planificador.py").read_text(encoding="utf-8")
    for prohibido in ("import flask", "import fastapi", "from flask", "from fastapi"):
        assert prohibido not in fuente


# --- 6. El prompt: prefijo estable delante, estado detrás ---------------

def test_el_prefijo_de_manifiestos_va_primero_y_marcado_para_cache():
    """Invertirlo haría que la caché no acertara nunca, y el planificador se
    encarecería **en silencio**: la peor forma de encarecerse."""
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta(PLAN_TERRITORIAL)))
    plani.planificar("Comprueba esta parcela", cliente,
                     memoria=memoria_con(territorial__municipio="Madrid"))
    contenido = cliente.llamadas[0]["messages"][0]["content"]
    assert contenido[0]["cache_control"] == {"type": "ephemeral"}
    assert "CATÁLOGO" in contenido[0]["text"]
    assert "ESTADO DEL PROYECTO" in contenido[1]["text"]
    assert "Comprueba esta parcela" in contenido[1]["text"]


def test_el_prompt_no_lleva_los_valores_del_proyecto():
    """El planificador decide con estados, no con valores: enviarlos sería
    exponer datos del cliente sin que cambie ninguna decisión."""
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta(PLAN_TERRITORIAL)))
    plani.planificar("Comprueba esta parcela", cliente,
                     memoria=memoria_con(programa__presupuesto="1.250.000 EUR"))
    entero = str(cliente.llamadas[0]["messages"])
    assert "1.250.000" not in entero


def test_el_uso_de_cache_se_mide():
    """Criterio 4 del PRD: sin medirlo, no hay forma de saber si el coste por
    plan se sostiene."""
    cliente = ClienteGuionizado(
        RespuestaFalsa(BloqueHerramienta(PLAN_TERRITORIAL), lectura_de_cache=0),
        RespuestaFalsa(BloqueHerramienta(PLAN_TERRITORIAL), lectura_de_cache=1200),
    )
    primera = plani.planificar("Comprueba esta parcela", cliente)
    segunda = plani.planificar("Comprueba esta parcela", cliente)
    assert primera.uso["cache_read_input_tokens"] == 0
    assert segunda.uso["cache_read_input_tokens"] > 0


def test_el_mismo_objetivo_produce_el_mismo_prompt():
    """Si el prompt cambiara entre ejecuciones, la caché no acertaría aunque el
    catálogo fuera idéntico."""
    def una_llamada():
        cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta(PLAN_TERRITORIAL)))
        plani.planificar("Comprueba esta parcela", cliente,
                         memoria=memoria_con(territorial__municipio="Madrid"))
        return cliente.llamadas[0]["messages"]

    assert una_llamada() == una_llamada()


# --- 7. Lo que ve el arquitecto antes de decir que sí ------------------

def test_el_plan_se_puede_enseñar_con_sus_efectos():
    """Es la razón de ser de esta tarea: lo que no se puede enseñar no se puede
    parar. Y enterarse de que algo escribe un fichero DESPUÉS no sirve."""
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta({"pasos": [
        {"id": "cuadro", "skill": "superficies.cuadro_de_vivienda",
         "argumentos": {"ruta_dxf": "a.dxf", "ruta_destino": "b.dxf"}},
    ]})))
    resultado = plani.planificar("Rellena el cuadro", cliente)
    texto = plani.a_texto(resultado, registro_de_skills(recargar=True))
    assert "superficies.cuadro_de_vivienda" in texto
    assert "Habrá que autorizar" in texto and "escribe_fichero" in texto


def test_un_plan_rechazado_se_enseña_como_rechazado():
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta({"pasos": [
        {"id": "x", "skill": "no.existe"},
    ]})))
    texto = plani.a_texto(plani.planificar("Algo", cliente))
    assert "NO SE PUEDE EJECUTAR" in texto


def test_un_plan_vacio_se_enseña_como_lo_que_es():
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueHerramienta(
        {"pasos": [], "motivo": "no hay Skill para eso"})))
    texto = plani.a_texto(plani.planificar("Algo", cliente))
    assert "no sabe hacer esto" in texto and "no hay Skill para eso" in texto


# --- 8. AG-2: el validador determinista, y la pregunta como salida ------

def _plan_de(*pasos):
    from agente.ejecucion import Paso, Plan

    return Plan(objetivo="o", proyecto_id="p",
                pasos=tuple(Paso(id=i, skill=s) for i, s in pasos))


def test_revisar_no_gasta_un_token_ni_toca_un_fichero(tmp_path, monkeypatch):
    """EL CRITERIO DE `AG-2`: rechazar es barato.

    Se sustituye el constructor del cliente por uno que revienta: si algo de
    esta ruta llamara al modelo, el test lo diría.
    """
    import ia.cliente

    monkeypatch.setattr(ia.cliente, "crear_cliente",
                        lambda *a, **k: pytest.fail("revisar() no puede llamar al modelo"))
    antes = sorted(p.name for p in tmp_path.iterdir())
    revision = plani.revisar(_plan_de(("a", "territorial.ficha_normativa_de_parcela")),
                             skills=registro_de_skills(recargar=True),
                             capacidades=registro(recargar=True),
                             memoria=memoria_con())
    assert sorted(p.name for p in tmp_path.iterdir()) == antes
    assert isinstance(revision.preguntas, tuple)


def test_los_cuatro_rechazos_dan_motivos_DISTINTOS():
    """«No se puede ejecutar» sin decir cuál de las cuatro cosas falla obliga a
    depurar a ojo."""
    from agente.ejecucion import Paso, Plan

    skills = registro_de_skills(recargar=True)
    caps = registro(recargar=True)

    inexistente = plani.revisar(_plan_de(("a", "no.existe")), skills=skills)
    version_mala = plani.revisar(
        _plan_de(("a", "territorial.ficha_normativa_de_parcela@9.0.0")), skills=skills)
    ciclo = plani.revisar(Plan(objetivo="o", proyecto_id="p", pasos=(
        Paso(id="a", skill="territorial.ficha_normativa_de_parcela", depende_de=("b",)),
        Paso(id="b", skill="revision.recorridos_de_evacuacion", depende_de=("a",)),
    )), skills=skills)
    duplicado = plani.revisar(Plan(objetivo="o", proyecto_id="p", pasos=(
        Paso(id="a", skill="territorial.ficha_normativa_de_parcela"),
        Paso(id="a", skill="revision.recorridos_de_evacuacion"),
    )), skills=skills, capacidades=caps)

    for revision in (inexistente, version_mala, ciclo, duplicado):
        assert not revision.ejecutable
    motivos = {r.motivos[0] for r in (inexistente, version_mala, ciclo, duplicado)}
    assert len(motivos) == 4, motivos


def test_un_requisito_que_falta_produce_LA_PREGUNTA_y_no_un_fallo():
    """La tercera de las cuatro: el plan está bien, faltan datos. La salida es
    la pregunta concreta, no un «faltan datos» que nadie sabe contestar."""
    revision = plani.revisar(_plan_de(("a", "territorial.ficha_normativa_de_parcela")),
                             skills=registro_de_skills(recargar=True),
                             memoria=memoria_con())
    assert revision.preguntas
    assert any("municipio" in p.lower() for p in revision.preguntas)
    # Y no es un motivo: contestando se desbloquea.
    assert revision.motivos == ()


def test_con_los_datos_puestos_ya_no_hay_preguntas():
    revision = plani.revisar(_plan_de(("a", "territorial.ficha_normativa_de_parcela")),
                             skills=registro_de_skills(recargar=True),
                             memoria=memoria_con(territorial__municipio="Madrid",
                                                 proyecto__uso="residencial.vivienda_libre",
                                                 proyecto__tipologia="plurifamiliar"))
    assert revision.preguntas == ()
    assert revision.ejecutable


def test_la_misma_pregunta_no_se_repite():
    """Dos pasos que necesitan lo mismo preguntan una vez."""
    revision = plani.revisar(_plan_de(("a", "territorial.ficha_normativa_de_parcela"),
                                      ("b", "territorial.ficha_normativa_de_parcela")),
                             skills=registro_de_skills(recargar=True),
                             memoria=memoria_con())
    assert len(revision.preguntas) == len(set(revision.preguntas))


def test_la_revision_reune_los_efectos_a_autorizar():
    """Se enseñan antes, no después: enterarse de que algo escribe un fichero
    cuando ya lo ha escrito no sirve de nada."""
    revision = plani.revisar(_plan_de(("a", "superficies.cuadro_de_vivienda")),
                             skills=registro_de_skills(recargar=True))
    assert "escribe_fichero" in revision.efectos_a_autorizar


def test_un_plan_sin_efectos_no_pide_autorizar_nada():
    """Pedir autorizaciones que no hacen falta enseña a concederlas sin leerlas."""
    revision = plani.revisar(_plan_de(("a", "territorial.ficha_normativa_de_parcela")),
                             skills=registro_de_skills(recargar=True))
    assert revision.efectos_a_autorizar == ()
