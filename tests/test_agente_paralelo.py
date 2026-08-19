# -*- coding: utf-8 -*-
"""AG-8 — ejecutar a la vez lo independiente, sin que el resultado dependa de ello.

Ejecutar:  pytest tests/test_agente_paralelo.py

El planificador le dice al modelo, textualmente, que «los pasos independientes
se declaran independientes: es lo que permite ejecutarlos a la vez». Hasta
`AG-8` eso era mentira: `Plan.orden()` calculaba los niveles topológicos y los
aplanaba, y el ejecutor recorría la lista. Este fichero fija las cuatro cosas
que hacen que dejar de ser mentira sea seguro:

1. **Se respetan las dependencias.** Un paso nunca empieza antes de que termine
   aquel del que depende, ejecute lo que ejecute a la vez.
2. **Sólo se solapa lo que es seguro.** Lista blanca cerrada de efectos: en
   cuanto un paso del nivel escribe un fichero o toca la memoria del proyecto,
   el nivel entero va en serie.
3. **El resultado no depende de ejecutar a la vez.** Mismos estados, mismos
   sellos y **la misma bitácora, línea a línea**, que ejecutando en serie. Es
   el criterio literal de `AG-8`, y de él depende la reanudación.
4. **Y se gana tiempo de verdad.** Cuatro ramas independientes tardan menos que
   en serie, que es la otra mitad del criterio.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente import efectos as _efectos  # noqa: E402
from agente.ejecucion import (  # noqa: E402
    HECHO,
    BitacoraEnMemoria,
    Ejecutor,
    Paso,
    Plan,
)
from agente.memoria import MemoriaDeProyecto, SustratoEnMemoria  # noqa: E402
from agente.registro import Registro, RegistroDeSkills  # noqa: E402
from agente.skill import ResultadoDeSkill, Skill  # noqa: E402

ESPERA = 0.20  # lo que "tarda" cada paso de mentira


# --- Un taller de Skills de mentira ----------------------------------------

class Vigilante:
    """Apunta quién entra y quién sale, y cuántos coincidieron dentro."""

    def __init__(self) -> None:
        self._cerrojo = threading.Lock()
        self.dentro = 0
        self.maximo_a_la_vez = 0
        self.entradas: list = []
        self.salidas: list = []

    def entra(self, quien: str) -> None:
        with self._cerrojo:
            self.dentro += 1
            self.maximo_a_la_vez = max(self.maximo_a_la_vez, self.dentro)
            self.entradas.append(quien)

    def sale(self, quien: str) -> None:
        with self._cerrojo:
            self.dentro -= 1
            self.salidas.append(quien)


def _skill(nombre: str, vigilante: Vigilante, *, efectos=(), espera=ESPERA):
    """Una Skill que sólo espera y apunta. Sin corpus, sin disco, sin red."""

    def _funcion(_contexto):
        vigilante.entra(nombre)
        try:
            time.sleep(espera)
        finally:
            vigilante.sale(nombre)
        return ResultadoDeSkill(notas=("estuvo dentro: %s" % nombre,))

    return Skill(
        id="prueba.%s" % nombre,
        version="1.0.0",
        dominio="prueba",
        objetivo="Espera un poco y apunta que estuvo dentro.",
        cuando_usarla="Nunca en producción: es un doble de test.",
        procedimiento=("esperar", "apuntar"),
        requiere=(),
        capacidades=(),
        produce=("prueba.marca",),
        funcion=_funcion,
        efectos=tuple(efectos),
    )


@pytest.fixture
def vigilante():
    return Vigilante()


@pytest.fixture
def memoria():
    return MemoriaDeProyecto("p", SustratoEnMemoria())


def _plan(*pasos, objetivo="probar el paralelismo"):
    return Plan(objetivo=objetivo, proyecto_id="p", pasos=tuple(pasos))


def _ejecutor(skills, *, bitacora=None, max_paralelo=4):
    return Ejecutor(capacidades=Registro(()), skills=RegistroDeSkills(skills),
                    bitacora=bitacora if bitacora is not None else BitacoraEnMemoria(),
                    max_paralelo=max_paralelo)


# --- 1. Los niveles son lo que dicen ser -----------------------------------

def test_los_pasos_independientes_van_en_el_mismo_nivel():
    plan = _plan(
        Paso(id="a", skill="prueba.a"),
        Paso(id="b", skill="prueba.b"),
        Paso(id="c", skill="prueba.c", depende_de=("a", "b")),
    )
    assert [[p.id for p in nivel] for nivel in plan.niveles()] == [["a", "b"], ["c"]]


def test_orden_sigue_siendo_el_aplanado_de_los_niveles():
    """`orden()` es el orden de referencia de la bitácora y no puede moverse."""
    plan = _plan(
        Paso(id="c", skill="prueba.c", depende_de=("a",)),
        Paso(id="a", skill="prueba.a"),
        Paso(id="b", skill="prueba.b"),
    )
    aplanado = [p.id for n in plan.niveles() for p in n]
    assert [p.id for p in plan.orden()] == aplanado == ["a", "b", "c"]


def test_una_cadena_no_tiene_ningun_nivel_con_dos_pasos():
    plan = _plan(
        Paso(id="a", skill="prueba.a"),
        Paso(id="b", skill="prueba.b", depende_de=("a",)),
        Paso(id="c", skill="prueba.c", depende_de=("b",)),
    )
    assert [len(n) for n in plan.niveles()] == [1, 1, 1]


# --- 2. Se respetan las dependencias ---------------------------------------

def test_un_paso_dependiente_no_empieza_antes_de_que_acabe_el_suyo(vigilante, memoria):
    """La garantía que ninguna optimización puede romper."""
    skills = [_skill(n, vigilante) for n in ("a", "b", "c")]
    plan = _plan(
        Paso(id="a", skill="prueba.a"),
        Paso(id="b", skill="prueba.b"),
        Paso(id="c", skill="prueba.c", depende_de=("a", "b")),
    )
    _ejecutor(skills).ejecutar(plan, memoria, ejecucion_id="e1")

    # `c` entró después de que salieran los dos de los que depende.
    assert vigilante.entradas.index("c") == 2
    assert set(vigilante.salidas[:2]) == {"a", "b"}
    assert vigilante.salidas[2] == "c"


def test_una_cadena_nunca_solapa(vigilante, memoria):
    skills = [_skill(n, vigilante) for n in ("a", "b", "c")]
    plan = _plan(
        Paso(id="a", skill="prueba.a"),
        Paso(id="b", skill="prueba.b", depende_de=("a",)),
        Paso(id="c", skill="prueba.c", depende_de=("b",)),
    )
    _ejecutor(skills).ejecutar(plan, memoria, ejecucion_id="e2")
    assert vigilante.maximo_a_la_vez == 1


# --- 3. Sólo se solapa lo que es seguro ------------------------------------

def test_pasos_sin_efectos_se_solapan(vigilante, memoria):
    skills = [_skill(n, vigilante) for n in ("a", "b", "c", "d")]
    plan = _plan(*[Paso(id=n, skill="prueba.%s" % n) for n in ("a", "b", "c", "d")])
    _ejecutor(skills).ejecutar(plan, memoria, ejecucion_id="e3")
    assert vigilante.maximo_a_la_vez == 4


def test_una_consulta_externa_tambien_se_solapa(vigilante, memoria):
    """`llama_api_externa` está en la lista blanca, y es la razón de ser de
    todo esto: lo que se solapa son esperas de red."""
    skills = [_skill(n, vigilante, efectos=(_efectos.LLAMA_API_EXTERNA,))
              for n in ("a", "b")]
    plan = _plan(Paso(id="a", skill="prueba.a"), Paso(id="b", skill="prueba.b"))
    permiso = _efectos.Autorizaciones.de([_efectos.LLAMA_API_EXTERNA],
                                         por="usuario:pablo", alcance="proyecto")
    _ejecutor(skills).ejecutar(plan, memoria, ejecucion_id="e4",
                               autorizaciones=permiso)
    assert vigilante.maximo_a_la_vez == 2


@pytest.mark.parametrize("efecto", [
    _efectos.ESCRIBE_FICHERO,
    _efectos.ESCRIBE_MEMORIA,
    _efectos.MODIFICA_FICHERO_DEL_CLIENTE,
    _efectos.ENVIA_AL_EXTERIOR,
])
def test_un_solo_paso_con_efecto_serio_pone_el_nivel_entero_en_serie(
        efecto, vigilante, memoria):
    """Todo o nada: no hay que razonar sobre interleavings para saber si un
    plan es seguro."""
    skills = [
        _skill("a", vigilante),
        _skill("b", vigilante),
        _skill("z", vigilante, efectos=(efecto,)),
    ]
    plan = _plan(Paso(id="a", skill="prueba.a"), Paso(id="b", skill="prueba.b"),
                 Paso(id="z", skill="prueba.z"))
    autorizaciones = _efectos.Autorizaciones.de([efecto], por="usuario:pablo")
    _ejecutor(skills).ejecutar(plan, memoria, ejecucion_id="e5",
                               autorizaciones=autorizaciones)
    assert vigilante.maximo_a_la_vez == 1


def test_la_lista_blanca_es_cerrada():
    """Un efecto nuevo del catálogo nace secuencial. Si algún día se añade uno
    y aparece aquí sin que nadie lo haya pensado, este test lo dice."""
    assert _efectos.SEGUROS_EN_PARALELO == frozenset(
        {_efectos.LLAMA_API_EXTERNA, _efectos.GASTA_TOKENS})
    assert not (_efectos.SEGUROS_EN_PARALELO & _efectos.EXIGEN_AUTORIZACION_PUNTUAL)


def test_max_paralelo_uno_lo_desactiva(vigilante, memoria):
    skills = [_skill(n, vigilante) for n in ("a", "b")]
    plan = _plan(Paso(id="a", skill="prueba.a"), Paso(id="b", skill="prueba.b"))
    _ejecutor(skills, max_paralelo=1).ejecutar(plan, memoria, ejecucion_id="e6")
    assert vigilante.maximo_a_la_vez == 1


def test_no_se_lanzan_mas_hilos_que_el_techo(vigilante, memoria):
    """Veinte peticiones simultáneas a Catastro no son veinte veces más rápidas:
    son una forma de que Catastro deje de contestar."""
    nombres = [chr(ord("a") + i) for i in range(8)]
    skills = [_skill(n, vigilante) for n in nombres]
    plan = _plan(*[Paso(id=n, skill="prueba.%s" % n) for n in nombres])
    _ejecutor(skills, max_paralelo=3).ejecutar(plan, memoria, ejecucion_id="e7")
    assert vigilante.maximo_a_la_vez == 3


# --- 4. El resultado no depende de ejecutar a la vez -----------------------

def test_mismos_sellos_y_misma_bitacora_que_en_serie(memoria):
    """El criterio literal de `AG-8`: **el mismo sello** que en serie. Y la
    bitácora línea a línea, que es de lo que depende la reanudación."""
    nombres = ("a", "b", "c", "d")
    plan = _plan(
        *[Paso(id=n, skill="prueba.%s" % n) for n in nombres],
        Paso(id="fin", skill="prueba.fin", depende_de=nombres),
    )

    def _corre(max_paralelo):
        vig = Vigilante()
        skills = [_skill(n, vig, espera=0.01) for n in nombres + ("fin",)]
        bitacora = BitacoraEnMemoria()
        resultado = _ejecutor(skills, bitacora=bitacora,
                              max_paralelo=max_paralelo).ejecutar(
            plan, MemoriaDeProyecto("p", SustratoEnMemoria()), ejecucion_id="e8")
        apuntes = [(r.paso_id, r.estado, r.sello) for r in bitacora.leer("e8")]
        return resultado, apuntes, vig

    en_serie, apuntes_serie, vig_serie = _corre(1)
    a_la_vez, apuntes_paralelo, vig_paralelo = _corre(4)

    assert vig_serie.maximo_a_la_vez == 1
    # Que se solaparan de verdad es lo que hace que la comparación signifique
    # algo. Cuántos exactamente coincidieron depende del arranque del pozo de
    # hilos, y afirmar un número exacto aquí sería un test que falla los martes.
    assert vig_paralelo.maximo_a_la_vez > 1
    assert apuntes_serie == apuntes_paralelo          # y da exactamente lo mismo
    assert [(p.paso_id, p.estado, p.sello) for p in en_serie.pasos] == \
           [(p.paso_id, p.estado, p.sello) for p in a_la_vez.pasos]
    assert en_serie.completa and a_la_vez.completa


def test_un_fallo_en_una_rama_no_arrastra_a_las_hermanas(vigilante, memoria):
    """La garantía nº1 del ejecutor sigue en pie con hilos por medio."""
    def _revienta(_contexto):
        raise RuntimeError("esta rama no se puede comprobar")

    rota = _skill("rota", vigilante)
    object.__setattr__(rota, "funcion", _revienta)
    skills = [rota, _skill("sana", vigilante),
              _skill("despues", vigilante)]
    plan = _plan(
        Paso(id="rota", skill="prueba.rota"),
        Paso(id="sana", skill="prueba.sana"),
        Paso(id="despues", skill="prueba.despues", depende_de=("rota",)),
    )
    resultado = _ejecutor(skills).ejecutar(plan, memoria, ejecucion_id="e9")
    por_id = {p.paso_id: p for p in resultado.pasos}

    assert por_id["rota"].estado == "fallido"
    assert por_id["sana"].estado == HECHO            # la hermana se hizo igual
    assert por_id["despues"].estado == "no_ejecutado"
    assert "esta rama no se puede comprobar" in por_id["rota"].motivo


def test_reanudar_tras_una_tanda_en_paralelo_no_repite_nada(memoria):
    vig1 = Vigilante()
    skills1 = [_skill(n, vig1, espera=0.01) for n in ("a", "b")]
    bitacora = BitacoraEnMemoria()
    plan = _plan(Paso(id="a", skill="prueba.a"), Paso(id="b", skill="prueba.b"))
    _ejecutor(skills1, bitacora=bitacora).ejecutar(plan, memoria, ejecucion_id="e10")

    vig2 = Vigilante()
    skills2 = [_skill(n, vig2, espera=0.01) for n in ("a", "b")]
    otra = _ejecutor(skills2, bitacora=bitacora).ejecutar(
        plan, memoria, ejecucion_id="e10")

    assert vig2.entradas == []                       # no se volvió a entrar
    assert sorted(otra.reanudados) == ["a", "b"]


# --- 5. Y se gana tiempo de verdad -----------------------------------------

def test_cuatro_ramas_independientes_tardan_menos_que_en_serie(memoria):
    """La otra mitad del criterio de `AG-8`. Con margen generoso: lo que se
    mide es que se solapan, no cuánto exactamente."""
    nombres = ("a", "b", "c", "d")
    plan = _plan(*[Paso(id=n, skill="prueba.%s" % n) for n in nombres])

    def _cronometrar(max_paralelo):
        vig = Vigilante()
        skills = [_skill(n, vig, espera=ESPERA) for n in nombres]
        comienzo = time.monotonic()
        _ejecutor(skills, max_paralelo=max_paralelo).ejecutar(
            plan, MemoriaDeProyecto("p", SustratoEnMemoria()),
            ejecucion_id="e11-%d" % max_paralelo)
        return time.monotonic() - comienzo

    en_serie = _cronometrar(1)
    a_la_vez = _cronometrar(4)
    assert a_la_vez < en_serie / 2, (a_la_vez, en_serie)
