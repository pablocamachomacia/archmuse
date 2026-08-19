# -*- coding: utf-8 -*-
"""La vía del plan enchufada a la fachada: proponer, enseñar, ejecutar.

Ejecutar:  pytest tests/test_agente_copiloto_plan.py

El planificador (`AG-1`) y su validador (`AG-2`) estaban construidos, probados
y **no los alcanzaba nadie**: `planificar()` sólo lo llamaban los tests y la
demostración. Este fichero fija el contrato de la vía por la que sí se alcanzan,
y lo que fija no es «que funcione» sino las cuatro cosas que un arquitecto
necesita que sean ciertas:

1. **Proponer no ejecuta.** Ni un fichero, ni un paso, ni una autorización.
2. **El plan se enseña antes**, con los efectos que habrá que autorizar y las
   preguntas que le faltan — no después de haberlos ejecutado.
3. **Decir que no para todo.** Si el arquitecto no confirma, no se ejecuta el
   primer paso, ni el que no tenía efectos.
4. **El texto de la vía del plan no lo escribe un modelo.** Se deriva de lo que
   pasó, así que no puede contener una cifra que ninguna herramienta produjo.

Y una garantía vieja que no se puede perder al añadir la vía nueva: la vía del
bucle sigue haciendo exactamente lo que hacía.

Todo con cliente guionizado: la suite no gasta un céntimo ni necesita clave.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente import copiloto  # noqa: E402
from agente import efectos as _efectos  # noqa: E402
from agente import planificador as plani  # noqa: E402
from agente.carencias import CarenciasEnMemoria, RegistroDeCarencias  # noqa: E402
from agente.ejecucion import BitacoraEnMemoria  # noqa: E402
from agente.memoria import MemoriaDeProyecto, SustratoEnMemoria  # noqa: E402
from agente.registro import registro, registro_de_skills  # noqa: E402


# --- Dobles ----------------------------------------------------------------

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
    input_tokens = 1200
    output_tokens = 90
    cache_creation_input_tokens = 1200
    cache_read_input_tokens = 0


class RespuestaFalsa:
    def __init__(self, *bloques):
        self.content = list(bloques)
        self.usage = UsoFalso()


class ClienteGuionizado:
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


def cliente_con_plan(*pasos, motivo=""):
    entrada = {"pasos": list(pasos), "motivo": motivo} if motivo else {"pasos": list(pasos)}
    return ClienteGuionizado(RespuestaFalsa(BloqueHerramienta(entrada)))


PASO_FICHA = {"id": "ficha", "skill": "territorial.ficha_normativa_de_parcela"}


@pytest.fixture
def skills():
    return registro_de_skills()


@pytest.fixture
def capacidades():
    return registro()


@pytest.fixture
def memoria_completa():
    """Una memoria con todo lo que la Skill territorial pide."""
    return memoria_con(territorial__municipio="Madrid",
                       proyecto__uso="residencial.vivienda_libre",
                       proyecto__tipologia="plurifamiliar")


# --- 1. Proponer no ejecuta -------------------------------------------------

def test_proponer_no_ejecuta_nada(tmp_path, monkeypatch, capacidades, skills,
                                  memoria_completa):
    """La mitad de la garantía: entre ver el plan y aceptarlo no pasa nada.

    Se vigila sobre el disco entero del proceso, no sobre una bandera: una
    Skill que escribiera un fichero por su cuenta se colaría por debajo de
    cualquier comprobación que se limitara a mirar los estados de los pasos.
    """
    monkeypatch.chdir(tmp_path)
    antes = set(tmp_path.rglob("*"))

    cliente = cliente_con_plan(PASO_FICHA)
    propuesta = copiloto.proponer("Comprueba esta parcela", cliente,
                                  memoria_completa, capacidades=capacidades,
                                  skills=skills)

    assert propuesta.plan is not None
    assert [p.id for p in propuesta.plan.pasos] == ["ficha"]
    assert set(tmp_path.rglob("*")) == antes
    # Y una sola llamada al modelo: planificar es una, revisar es cero.
    assert len(cliente.llamadas) == 1


def test_revisar_no_cuesta_una_segunda_llamada(capacidades, skills,
                                               memoria_completa):
    cliente = cliente_con_plan(PASO_FICHA)
    copiloto.proponer("Comprueba esta parcela", cliente, memoria_completa,
                      capacidades=capacidades, skills=skills)
    assert len(cliente.llamadas) == 1


# --- 2. El plan se enseña ANTES, con los efectos ----------------------------

def test_la_propuesta_ensena_los_efectos_antes_de_ejecutarlos(capacidades, skills):
    """Enterarse de que algo escribe un fichero después no sirve de nada."""
    con_efectos = [
        (sid, s) for sid, s in _todas(skills) if s.efectos
    ]
    if not con_efectos:
        pytest.skip("ninguna Skill del registro declara efectos todavía")
    sid, skill = con_efectos[0]

    cliente = cliente_con_plan({"id": "p1", "skill": sid})
    propuesta = copiloto.proponer("haz eso", cliente, memoria_con(),
                                  capacidades=capacidades, skills=skills)

    assert set(skill.efectos) <= set(propuesta.efectos_a_autorizar)
    # Sin autorizar nada, todos están pendientes; y el texto los nombra.
    assert set(propuesta.falta_autorizar()) == set(propuesta.efectos_a_autorizar)
    texto = propuesta.texto()
    for efecto in skill.efectos:
        assert efecto in texto
    assert "HAY QUE AUTORIZAR ANTES DE SEGUIR" in texto


def test_un_efecto_ya_autorizado_no_se_vuelve_a_pedir(capacidades, skills):
    con_efectos = [(sid, s) for sid, s in _todas(skills) if s.efectos]
    if not con_efectos:
        pytest.skip("ninguna Skill del registro declara efectos todavía")
    sid, skill = con_efectos[0]

    cliente = cliente_con_plan({"id": "p1", "skill": sid})
    propuesta = copiloto.proponer("haz eso", cliente, memoria_con(),
                                  capacidades=capacidades, skills=skills)
    concedidas = _efectos.Autorizaciones.de(skill.efectos, por="usuario:pablo")
    assert propuesta.falta_autorizar(concedidas) == ()


def test_un_efecto_ya_autorizado_sigue_diciendose(capacidades, skills):
    """Que desaparezca de la pantalla en cuanto se autoriza es cómo el
    arquitecto acaba sin saber qué va a tocar su ordenador."""
    con_efectos = [(sid, s) for sid, s in _todas(skills) if s.efectos]
    if not con_efectos:
        pytest.skip("ninguna Skill del registro declara efectos todavía")
    sid, skill = con_efectos[0]

    cliente = cliente_con_plan({"id": "p1", "skill": sid})
    propuesta = copiloto.proponer("haz eso", cliente, memoria_con(),
                                  capacidades=capacidades, skills=skills)
    concedidas = _efectos.Autorizaciones.de(skill.efectos, por="usuario:pablo")
    texto = propuesta.texto(concedidas)
    assert "HAY QUE AUTORIZAR ANTES DE SEGUIR" not in texto
    for efecto in skill.efectos:
        assert efecto in texto


def test_la_lista_de_efectos_no_sale_dos_veces(capacidades, skills):
    """Imprimirla dos veces con dos criterios distintos es cómo se consigue que
    el arquitecto deje de leerla."""
    con_efectos = [(sid, s) for sid, s in _todas(skills) if s.efectos]
    if not con_efectos:
        pytest.skip("ninguna Skill del registro declara efectos todavía")
    sid, _skill = con_efectos[0]

    cliente = cliente_con_plan({"id": "p1", "skill": sid})
    propuesta = copiloto.proponer("haz eso", cliente, memoria_con(),
                                  capacidades=capacidades, skills=skills)
    assert propuesta.texto().count("Habrá que autorizar") == 0


def test_un_requisito_que_falta_sale_como_pregunta_en_la_propuesta(
        capacidades, skills):
    """El peor momento del producto convertido en el mejor: una pregunta
    concreta que el arquitecto sabe contestar, y sin haber ejecutado nada."""
    cliente = cliente_con_plan(PASO_FICHA)
    propuesta = copiloto.proponer("Comprueba esta parcela", cliente,
                                  memoria_con(), capacidades=capacidades,
                                  skills=skills)
    assert propuesta.preguntas, "una memoria vacía tiene que producir preguntas"
    assert "PARA PODER TERMINARLO HAY QUE CONTESTAR" in propuesta.texto()
    # Y aun así el plan es ejecutable: los pasos con sus datos se hacen igual.
    assert propuesta.ejecutable


# --- 3. Decir que no para todo ----------------------------------------------

def test_no_confirmar_no_ejecuta_ni_el_primer_paso(capacidades, skills,
                                                   memoria_completa):
    cliente = cliente_con_plan(PASO_FICHA)
    bitacora = BitacoraEnMemoria()
    propuesta = copiloto.proponer("Comprueba esta parcela", cliente,
                                  memoria_completa, capacidades=capacidades,
                                  skills=skills)
    entrega = copiloto.ejecutar_propuesta(
        propuesta, memoria_completa, bitacora=bitacora,
        confirmar=lambda _p: False,
    )

    assert entrega.respuesta.parada == "no_confirmado"
    assert entrega.respuesta.pasos_de_skill == ()
    assert bitacora.leer(propuesta.ejecucion_id) == []
    assert entrega.acta.completa is False


def test_confirmar_que_si_ejecuta(capacidades, skills, memoria_completa):
    cliente = cliente_con_plan(PASO_FICHA)
    propuesta = copiloto.proponer("Comprueba esta parcela", cliente,
                                  memoria_completa, capacidades=capacidades,
                                  skills=skills)
    vistos = []
    entrega = copiloto.ejecutar_propuesta(
        propuesta, memoria_completa, confirmar=lambda p: vistos.append(p) or True,
    )
    assert len(vistos) == 1 and vistos[0] is propuesta
    assert entrega.respuesta.parada == "fin"
    assert len(entrega.respuesta.pasos_de_skill) == 1


# --- 4. El texto de la vía del plan no lo escribe un modelo -----------------

def test_el_texto_no_trae_cifras_que_nadie_produjo(capacidades, skills,
                                                   memoria_completa):
    cliente = cliente_con_plan(PASO_FICHA)
    entrega = copiloto.atender("Comprueba esta parcela", cliente,
                               memoria_completa, via=copiloto.VIA_PLAN,
                               capacidades=capacidades, skills=skills)
    assert entrega.fundamentada, entrega.respuesta.cifras_sin_respaldo


def test_la_via_del_plan_no_llama_al_modelo_para_redactar(capacidades, skills,
                                                          memoria_completa):
    """Una sola llamada en toda la vía: la de planificar.

    Si algún día se añade una llamada de redacción al final, este test cae — y
    tiene que caer, porque esa llamada es justo por donde entraría una cifra
    que ninguna herramienta produjo.
    """
    cliente = cliente_con_plan(PASO_FICHA)
    copiloto.atender("Comprueba esta parcela", cliente, memoria_completa,
                     via=copiloto.VIA_PLAN, capacidades=capacidades, skills=skills)
    assert len(cliente.llamadas) == 1


# --- 5. Plan vacío, plan inválido: resultados, no fallos --------------------

def test_lo_que_archmuse_no_sabe_hacer_entrega_acta_y_motivo(capacidades, skills,
                                                             memoria_completa):
    carencias = RegistroDeCarencias(CarenciasEnMemoria())
    cliente = cliente_con_plan(motivo="ArchMuse no calcula estructuras")
    entrega = copiloto.atender("Calcula el forjado", cliente, memoria_completa,
                               via=copiloto.VIA_PLAN, capacidades=capacidades,
                               skills=skills, carencias=carencias)

    assert entrega.respuesta.parada == "plan_vacio"
    assert "ArchMuse no calcula estructuras" in entrega.texto
    assert entrega.acta.completa is False
    assert carencias.de("Calcula el forjado").veces == 1


def test_un_plan_que_nombra_una_skill_inexistente_no_ejecuta_nada(
        capacidades, skills, memoria_completa):
    bitacora = BitacoraEnMemoria()
    cliente = cliente_con_plan({"id": "p1", "skill": "inventada.que_no_existe"})
    propuesta = copiloto.proponer("haz algo", cliente, memoria_completa,
                                  capacidades=capacidades, skills=skills)
    entrega = copiloto.ejecutar_propuesta(propuesta, memoria_completa,
                                          bitacora=bitacora)

    assert entrega.respuesta.parada == "plan_invalido"
    assert propuesta.motivos
    assert bitacora.leer(propuesta.ejecucion_id) == []
    assert entrega.acta.completa is False


def test_un_acta_de_un_trabajo_que_nadie_hizo_no_dice_completa(
        capacidades, skills, memoria_completa):
    """`all()` de nada es cierto. El acta no puede heredar esa verdad vacía."""
    cliente = cliente_con_plan(motivo="no sé hacer eso")
    entrega = copiloto.atender("haz lo imposible", cliente, memoria_completa,
                               via=copiloto.VIA_PLAN, capacidades=capacidades,
                               skills=skills)
    assert entrega.acta.a_dict()["completa"] is False


# --- 6. La vía del bucle sigue siendo la de siempre -------------------------

def test_el_defecto_sigue_siendo_el_bucle(capacidades, skills, memoria_completa):
    """Cambiar el defecto cambia el comportamiento de todo llamador existente.

    Se decide con datos de uso (`AG-3`), no de golpe — y hasta entonces esto lo
    fija.
    """
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueTexto("hecho")))
    entrega = copiloto.atender("hola", cliente, memoria_completa,
                               capacidades=capacidades, skills=skills)
    assert entrega.propuesta is None
    assert entrega.respuesta.parada == "fin"


def test_una_via_que_no_existe_se_rechaza_sin_gastar(capacidades, skills,
                                                     memoria_completa):
    cliente = ClienteGuionizado()
    with pytest.raises(copiloto.ViaDesconocida):
        copiloto.atender("hola", cliente, memoria_completa, via="langgraph",
                         capacidades=capacidades, skills=skills)
    assert cliente.llamadas == []


# --- 7. El plan viaja con la entrega ----------------------------------------

def test_la_entrega_lleva_el_plan_que_se_enseno(capacidades, skills,
                                               memoria_completa):
    """Lo que se enseñó y lo que se hizo van en el mismo documento: es lo que
    permite comprobar después que fueron lo mismo."""
    cliente = cliente_con_plan(PASO_FICHA)
    entrega = copiloto.atender("Comprueba esta parcela", cliente,
                               memoria_completa, via=copiloto.VIA_PLAN,
                               capacidades=capacidades, skills=skills)
    cuerpo = entrega.a_dict()
    assert cuerpo["plan"] is not None
    assert cuerpo["plan"]["planificacion"]["plan"]["pasos"][0]["id"] == "ficha"
    assert cuerpo["acta"]["sello"]


def test_ejecutar_propuesta_usa_el_catalogo_que_se_enseno(capacidades, skills,
                                                         memoria_completa):
    """Ejecutar contra un catálogo distinto del que se enseñó sería enseñar una
    cosa y hacer otra. Los registros viajan dentro de la propuesta."""
    cliente = cliente_con_plan(PASO_FICHA)
    propuesta = copiloto.proponer("Comprueba esta parcela", cliente,
                                  memoria_completa, capacidades=capacidades,
                                  skills=skills)
    assert propuesta.capacidades is capacidades
    assert propuesta.skills is skills


# --- Auxiliar ---------------------------------------------------------------

def _todas(skills):
    """(id, skill) de todo el registro, sin depender de su API interna."""
    fuera = []
    for skill in skills:
        fuera.append((skill.id, skill))
    return fuera
