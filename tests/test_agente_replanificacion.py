# -*- coding: utf-8 -*-
"""AG-4 — se replanifica UNA vez, y el segundo fallo es una pregunta.

Ejecutar:  pytest tests/test_agente_replanificacion.py

Un plan puede no salir por una razón que otro plan sí sabría rodear: la Skill
elegida no era la buena, o el dato que falta lo sabe conseguir otra. Lo que no
puede pasar es que el agente dé vueltas: se come el presupuesto del arquitecto
y le entrega media respuesta como si fuera entera.

Lo que se fija, y las cinco son de no gastar y de no engañar:

1. **Se replanifica cuando hay algo que otro plan podría arreglar**, con lo
   observado a la vista y derivado de los pasos, nunca redactado por un modelo.
2. **Una vez. Nunca dos.** El techo es duro: pedir cinco da uno.
3. **Nunca para esquivar una autorización.** Si falta un permiso, se para y se
   pide. Buscar otra ruta que no necesite el permiso que acaban de no darte es
   la única cosa que este sistema no puede hacer nunca.
4. **Lo que ya salió bien no se repite** — ni se recalcula, ni se vuelve a
   cobrar, ni se vuelve a escribir un fichero.
5. **Un plan idéntico al que acaba de fallar no se ejecuta**: no hay nada nuevo
   que pueda salir de él, y sí una factura.
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
from agente.ejecucion import BitacoraEnMemoria, HECHO  # noqa: E402
from agente.memoria import MemoriaDeProyecto, SustratoEnMemoria  # noqa: E402
from agente.registro import Registro, RegistroDeSkills  # noqa: E402
from agente.skill import Requisito, ResultadoDeSkill, Skill  # noqa: E402


# --- Dobles ----------------------------------------------------------------

class BloqueHerramienta:
    type = "tool_use"

    def __init__(self, entrada):
        self.name = plani.NOMBRE_HERRAMIENTA
        self.input = entrada
        self.id = "tu_1"


class RespuestaFalsa:
    def __init__(self, entrada):
        self.content = [BloqueHerramienta(entrada)]
        self.usage = None


class ClienteDeGuion:
    """Devuelve un plan por llamada, en orden. Apunta lo que le pidieron."""

    def __init__(self, *planes):
        self._planes = list(planes)
        self.llamadas = []
        self.messages = self

    def create(self, **kwargs):
        self.llamadas.append(kwargs)
        return RespuestaFalsa(self._planes.pop(0) if self._planes else {"pasos": []})

    @property
    def observaciones(self):
        """El texto que se le mandó en cada llamada, detrás de la intención."""
        return [ll["messages"][0]["content"][1]["text"] for ll in self.llamadas]


def _skill(nombre, *, ejecutadas, requiere=(), efectos=(), revienta=False):
    def _funcion(_contexto):
        ejecutadas.append(nombre)
        if revienta:
            raise RuntimeError("esta rama no se puede comprobar")
        return ResultadoDeSkill(notas=("hecho: %s" % nombre,))

    return Skill(
        id="prueba.%s" % nombre, version="1.0.0", dominio="prueba",
        objetivo="Skill de prueba «%s»." % nombre,
        cuando_usarla="Nunca en producción.",
        procedimiento=("hacer",), requiere=tuple(requiere), capacidades=(),
        produce=("prueba.%s" % nombre,), funcion=_funcion, efectos=tuple(efectos),
    )


def _memoria():
    return MemoriaDeProyecto("p", SustratoEnMemoria())


def _atender(cliente, skills, memoria, **extra):
    return copiloto.atender(
        "haz el trabajo", cliente, memoria, via=copiloto.VIA_PLAN,
        capacidades=Registro(()), skills=RegistroDeSkills(skills),
        bitacora=extra.pop("bitacora", BitacoraEnMemoria()), **extra,
    )


def _paso(pid, nombre, **extra):
    return dict(id=pid, skill="prueba.%s" % nombre, **extra)


# --- 1. Se replanifica cuando otro plan podría arreglarlo ------------------

def test_un_paso_fallido_dispara_una_replanificacion_que_lo_rodea():
    ejecutadas = []
    skills = [_skill("rota", ejecutadas=ejecutadas, revienta=True),
              _skill("otra", ejecutadas=ejecutadas)]
    cliente = ClienteDeGuion(
        {"pasos": [_paso("p1", "rota")]},
        {"pasos": [_paso("p2", "otra")]},
    )
    entrega = _atender(cliente, skills, _memoria())

    assert len(cliente.llamadas) == 2, "tenía que haber replanificado"
    assert entrega.replanificado is True
    assert len(entrega.intentos) == 2
    assert ejecutadas == ["rota", "otra"]
    assert [p.estado for p in entrega.respuesta.pasos_de_skill] == [HECHO]


def test_la_observacion_dice_lo_que_paso_y_sale_de_los_pasos():
    """No la redacta un modelo: si lo hiciera, el segundo plan se construiría
    sobre un resumen y no sobre lo que pasó."""
    ejecutadas = []
    skills = [_skill("rota", ejecutadas=ejecutadas, revienta=True),
              _skill("otra", ejecutadas=ejecutadas)]
    cliente = ClienteDeGuion(
        {"pasos": [_paso("p1", "rota")]},
        {"pasos": [_paso("p2", "otra")]},
    )
    _atender(cliente, skills, _memoria())

    primera, segunda = cliente.observaciones
    assert "ESTO YA SE HA INTENTADO" not in primera
    assert "ESTO YA SE HA INTENTADO" in segunda
    assert "NO HA SALIDO, Y POR QUÉ" in segunda
    assert "esta rama no se puede comprobar" in segunda
    assert "plan VACÍO" in segunda


def test_un_dato_que_falta_tambien_replanifica_por_si_otra_skill_lo_consigue():
    ejecutadas = []
    pide_municipio = _skill(
        "ficha", ejecutadas=ejecutadas,
        requiere=(Requisito(clave="territorial.municipio",
                            pregunta="¿En qué municipio está la parcela?"),))
    skills = [pide_municipio, _skill("catastro", ejecutadas=ejecutadas)]
    cliente = ClienteDeGuion(
        {"pasos": [_paso("p1", "ficha")]},
        {"pasos": [_paso("p2", "catastro")]},
    )
    entrega = _atender(cliente, skills, _memoria())

    assert len(cliente.llamadas) == 2
    assert "¿En qué municipio está la parcela?" in cliente.observaciones[1]
    assert entrega.replanificado is True


def test_si_sale_todo_a_la_primera_no_se_replanifica():
    ejecutadas = []
    skills = [_skill("buena", ejecutadas=ejecutadas)]
    cliente = ClienteDeGuion({"pasos": [_paso("p1", "buena")]})
    entrega = _atender(cliente, skills, _memoria())

    assert len(cliente.llamadas) == 1
    assert entrega.replanificado is False
    assert entrega.acta.completa is True


def test_un_plan_vacio_no_se_replanifica():
    """ArchMuse no sabe hacer eso. Volver a preguntárselo al mismo catálogo
    tampoco lo va a saber."""
    cliente = ClienteDeGuion({"pasos": [], "motivo": "no sé calcular estructuras"})
    entrega = _atender(cliente, [_skill("x", ejecutadas=[])], _memoria())

    assert len(cliente.llamadas) == 1
    assert entrega.respuesta.parada == "plan_vacio"
    assert entrega.replanificado is False


def test_un_plan_no_confirmado_no_se_replanifica():
    """El arquitecto ha dicho que no. Proponerle otro sin que lo pida es
    exactamente lo contrario de lo que significó su «no»."""
    ejecutadas = []
    cliente = ClienteDeGuion({"pasos": [_paso("p1", "x")]})
    entrega = _atender(cliente, [_skill("x", ejecutadas=ejecutadas)], _memoria(),
                       confirmar=lambda _p: False)

    assert len(cliente.llamadas) == 1
    assert entrega.respuesta.parada == "no_confirmado"
    assert ejecutadas == []


# --- 2. Una vez. Nunca dos. ------------------------------------------------

def test_nunca_hay_un_tercer_intento():
    ejecutadas = []
    skills = [_skill(n, ejecutadas=ejecutadas, revienta=True)
              for n in ("a", "b", "c", "d")]
    cliente = ClienteDeGuion(
        {"pasos": [_paso("p1", "a")]},
        {"pasos": [_paso("p2", "b")]},
        {"pasos": [_paso("p3", "c")]},
        {"pasos": [_paso("p4", "d")]},
    )
    entrega = _atender(cliente, skills, _memoria())

    assert len(cliente.llamadas) == 2, "una planificación y UNA replanificación"
    assert ejecutadas == ["a", "b"]
    assert len(entrega.intentos) == 2


def test_el_techo_es_duro_aunque_pidan_mas():
    """Un parámetro que admitiera cinco es cómo se consigue un agente que se
    come el presupuesto dando vueltas."""
    ejecutadas = []
    skills = [_skill(n, ejecutadas=ejecutadas, revienta=True) for n in "abcde"]
    cliente = ClienteDeGuion(*[{"pasos": [_paso("p%d" % i, n)]}
                               for i, n in enumerate("abcde")])
    _atender(cliente, skills, _memoria(), max_replanificaciones=5)

    assert len(cliente.llamadas) == 2


def test_cero_replanificaciones_lo_desactiva():
    ejecutadas = []
    skills = [_skill("a", ejecutadas=ejecutadas, revienta=True),
              _skill("b", ejecutadas=ejecutadas)]
    cliente = ClienteDeGuion({"pasos": [_paso("p1", "a")]},
                             {"pasos": [_paso("p2", "b")]})
    entrega = _atender(cliente, skills, _memoria(), max_replanificaciones=0)

    assert len(cliente.llamadas) == 1
    assert entrega.replanificado is False
    assert ejecutadas == ["a"]


# --- 3. Nunca para esquivar una autorización -------------------------------

def test_un_permiso_que_falta_no_se_rodea_replanificando():
    """La única cosa que este sistema no puede hacer nunca. Es una regla, no
    una heurística: si falta un permiso, se para y se pide."""
    ejecutadas = []
    skills = [_skill("escribe", ejecutadas=ejecutadas,
                     efectos=(_efectos.ESCRIBE_FICHERO,)),
              _skill("sinefectos", ejecutadas=ejecutadas)]
    cliente = ClienteDeGuion(
        {"pasos": [_paso("p1", "escribe")]},
        {"pasos": [_paso("p2", "sinefectos")]},   # la ruta que NO debe tomarse
    )
    entrega = _atender(cliente, skills, _memoria())   # sin autorizaciones

    assert len(cliente.llamadas) == 1, "no puede haber buscado otra ruta"
    assert entrega.replanificado is False
    assert ejecutadas == []
    assert _efectos.ESCRIBE_FICHERO in entrega.efectos_pendientes


def test_con_el_permiso_dado_ya_no_hay_nada_que_rodear():
    ejecutadas = []
    skills = [_skill("escribe", ejecutadas=ejecutadas,
                     efectos=(_efectos.ESCRIBE_FICHERO,))]
    cliente = ClienteDeGuion({"pasos": [_paso("p1", "escribe")]})
    permiso = _efectos.Autorizaciones.de([_efectos.ESCRIBE_FICHERO],
                                         por="usuario:pablo")
    entrega = _atender(cliente, skills, _memoria(), autorizaciones=permiso)

    assert len(cliente.llamadas) == 1
    assert ejecutadas == ["escribe"]
    assert entrega.acta.completa is True


# --- 4. Lo que ya salió bien no se repite ----------------------------------

def test_el_paso_que_ya_salio_no_se_vuelve_a_ejecutar():
    """Ni se recalcula, ni se vuelve a cobrar, ni se vuelve a escribir un
    fichero. La reanudación de `Ejecutor` es quien lo garantiza, y lo que la
    hace segura aquí es que un paso se reconozca por su Skill y sus argumentos."""
    ejecutadas = []
    skills = [_skill("buena", ejecutadas=ejecutadas),
              _skill("rota", ejecutadas=ejecutadas, revienta=True),
              _skill("otra", ejecutadas=ejecutadas)]
    cliente = ClienteDeGuion(
        {"pasos": [_paso("ok", "buena"), _paso("mal", "rota")]},
        # El segundo plan conserva el paso que salió y cambia el que no.
        {"pasos": [_paso("ok", "buena"), _paso("otro", "otra")]},
    )
    entrega = _atender(cliente, skills, _memoria())

    # `ok` y `mal` son independientes, así que van a la vez (`AG-8`) y su orden
    # entre sí no está fijado. Lo que sí lo está: `buena` **una sola vez**.
    assert sorted(ejecutadas) == ["buena", "otra", "rota"], ejecutadas
    assert ejecutadas.count("buena") == 1
    assert ejecutadas[-1] == "otra", "lo replanificado va después"
    assert entrega.acta.completa is True


def test_un_id_reutilizado_para_otra_skill_no_se_da_por_hecho():
    """El defecto que la replanificación destapa: la reanudación buscaba por
    `paso_id` a secas, así que el segundo plan podía llevarse el resultado del
    primero por coincidir el nombre — con su sello y su acta, y sin que nada
    fallara."""
    ejecutadas = []
    skills = [_skill("buena", ejecutadas=ejecutadas),
              _skill("rota", ejecutadas=ejecutadas, revienta=True),
              _skill("distinta", ejecutadas=ejecutadas)]
    cliente = ClienteDeGuion(
        {"pasos": [_paso("p1", "buena"), _paso("p2", "rota")]},
        # `p1` ahora es OTRA Skill. No puede reutilizarse el resultado viejo.
        {"pasos": [_paso("p1", "distinta")]},
    )
    entrega = _atender(cliente, skills, _memoria())

    assert "distinta" in ejecutadas, "el paso p1 nuevo tenía que ejecutarse"
    firmas = {p.paso_id: p.skill for p in entrega.respuesta.pasos_de_skill}
    assert firmas["p1"].startswith("prueba.distinta")


def test_los_mismos_argumentos_cambiados_tampoco_se_dan_por_hechos():
    ejecutadas = []
    con_argumentos = Skill(
        id="prueba.conargs", version="1.0.0", dominio="prueba",
        objetivo="Recibe argumentos.", cuando_usarla="Nunca en producción.",
        procedimiento=("hacer",), requiere=(), capacidades=(),
        produce=("prueba.conargs",),
        parametros={"type": "object",
                    "properties": {"ruta": {"type": "string"}},
                    "additionalProperties": False},
        funcion=lambda ctx: ejecutadas.append(ctx.argumentos.get("ruta")) or
        ResultadoDeSkill(notas=("hecho",)),
    )
    rota = _skill("rota", ejecutadas=ejecutadas, revienta=True)
    cliente = ClienteDeGuion(
        {"pasos": [_paso("p1", "conargs", argumentos={"ruta": "a.dxf"}),
                   _paso("p2", "rota")]},
        {"pasos": [_paso("p1", "conargs", argumentos={"ruta": "b.dxf"})]},
    )
    _atender(cliente, [con_argumentos, rota], _memoria())

    assert "a.dxf" in ejecutadas and "b.dxf" in ejecutadas, ejecutadas


# --- 5. Un plan idéntico no se vuelve a ejecutar ---------------------------

def test_el_mismo_plan_otra_vez_no_se_ejecuta():
    """No hay nada nuevo que pueda salir de él, y sí una factura."""
    ejecutadas = []
    skills = [_skill("rota", ejecutadas=ejecutadas, revienta=True)]
    mismo = {"pasos": [_paso("p1", "rota")]}
    cliente = ClienteDeGuion(mismo, dict(mismo))
    entrega = _atender(cliente, skills, _memoria())

    assert len(cliente.llamadas) == 2, "sí se pide otro plan"
    assert ejecutadas == ["rota"], "pero no se ejecuta dos veces el mismo"
    assert entrega.replanificado is False
    assert len(entrega.intentos) == 1


def test_la_entrega_lleva_los_dos_planes_para_poder_contarlo():
    """«Lo intentó de otra forma» es información del arquitecto, no traza
    interna: explica por qué tardó el doble y por qué el plan que ve no es el
    que se le enseñó primero."""
    ejecutadas = []
    skills = [_skill("rota", ejecutadas=ejecutadas, revienta=True),
              _skill("otra", ejecutadas=ejecutadas)]
    cliente = ClienteDeGuion({"pasos": [_paso("p1", "rota")]},
                             {"pasos": [_paso("p2", "otra")]})
    cuerpo = _atender(cliente, skills, _memoria()).a_dict()

    assert cuerpo["replanificado"] is True
    assert len(cuerpo["planes_propuestos"]) == 2
    assert cuerpo["planes_propuestos"][0]["planificacion"]["plan"]["pasos"][0]["id"] == "p1"
    assert cuerpo["planes_propuestos"][1]["planificacion"]["plan"]["pasos"][0]["id"] == "p2"


def test_la_via_del_bucle_no_replanifica_nunca():
    """`AG-4` es de la vía del plan. El bucle tiene su propio freno."""
    class ClienteQueHabla:
        def __init__(self):
            self.llamadas = []
            self.messages = self

        def create(self, **kwargs):
            self.llamadas.append(kwargs)

            class R:
                content = [type("B", (), {"type": "text", "text": "listo"})()]
            return R()

    cliente = ClienteQueHabla()
    entrega = copiloto.atender("hola", cliente, _memoria(),
                               capacidades=Registro(()),
                               skills=RegistroDeSkills([]))
    assert entrega.replanificado is False
    assert entrega.intentos == ()
