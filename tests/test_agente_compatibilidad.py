# -*- coding: utf-8 -*-
"""CAD-2 — un cambio incompatible sin subir la mayor no pasa de aquí.

Ejecutar:  pytest tests/test_agente_compatibilidad.py
Recongelar: python tests/test_agente_compatibilidad.py --congelar  (y explicar por qué)

**Qué se está protegiendo.** `CAD-1` demostró que el motor se puede invocar
desde fuera: un CLI hoy, un complemento de Revit o un servidor MCP mañana. Ese
invocador vivirá en el ordenador de un estudio y hablará con un servidor que se
actualiza sin preguntarle. Si alguien renombra un parámetro un martes, el
complemento deja de funcionar el martes, y el arquitecto no sabrá por qué.

Lo que se fija:

1. **El contrato de cada capacidad está congelado** en
   `tests/fixtures/contratos_de_capacidad.json`. Cambiarlo sin subir el tramo
   de versión que corresponde pone la suite en rojo, **diciendo qué cambió y
   qué tramo tocaba**.
2. **La política es explícita** y se prueba con casos: quitar un parámetro es
   mayor, añadir uno opcional es menor, añadir un efecto es mayor.
3. **Un plan guardado con una versión antigua se ejecuta o falla claro.** Nunca
   «lo más parecido»: eso reescribiría en silencio lo que se hizo aquel día.

La prosa (descripciones) queda **fuera** del contrato a propósito: reescribir
lo que lee el modelo tiene que poder hacerse sin obligar a nadie a actualizar
un complemento instalado.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente import compatibilidad as comp  # noqa: E402
from agente.capacidad import Capacidad  # noqa: E402
from agente.registro import CapacidadDesconocida, registro  # noqa: E402

CONGELADO = RAIZ / "tests" / "fixtures" / "contratos_de_capacidad.json"


def capacidad(**cambios) -> Capacidad:
    base = dict(
        id="prueba.medir", version="1.0.0", dominio="prueba",
        naturaleza="determinista", descripcion="Mide algo.",
        parametros={
            "type": "object",
            "properties": {"largo": {"type": "number"}, "unidad": {"type": "string"}},
            "required": ["largo"],
        },
        funcion=lambda largo, unidad="m": {"ok": True},
    )
    base.update(cambios)
    return Capacidad(**base)


def _congelado() -> dict:
    if not CONGELADO.exists():
        return {}
    return {k: v for k, v in json.loads(CONGELADO.read_text(encoding="utf-8")).items()
            if not k.startswith("_")}


# --- 1. El contrato del registro real --------------------------------------

def test_ninguna_capacidad_ha_cambiado_de_contrato_sin_subir_version():
    """LA TAREA `CAD-2` EN UNA LÍNEA.

    Recorre el registro contra el contrato congelado. No hay lista escrita a
    mano: una capacidad nueva no rompe nada (no puede romper a nadie), pero una
    que cambia calladamente sí.
    """
    fallos = comp.revisar(_congelado(), registro(recargar=True))
    assert fallos == [], "\n".join(fallos)


def test_toda_capacidad_del_registro_tiene_su_contrato_congelado():
    """Una capacidad sin contrato congelado es una que puede cambiar sin que
    nadie se entere: el hueco exacto que esta tarea cierra."""
    faltan = sorted(set(registro(recargar=True).ids()) - set(_congelado()))
    assert faltan == [], (
        "sin contrato congelado: %s. Ejecuta "
        "`python tests/test_agente_compatibilidad.py --congelar`." % faltan)


def test_la_prosa_no_forma_parte_del_contrato():
    """Reescribir la descripción que lee el modelo no puede obligar a nadie a
    actualizar un complemento instalado."""
    original = capacidad()
    reescrita = capacidad(descripcion="Mide algo, explicado mucho mejor y más largo.")
    assert comp.huella(original) == comp.huella(reescrita)
    assert comp.comparar(comp.huella(original), comp.huella(reescrita)) == (None, [])


# --- 2. La política, caso a caso ------------------------------------------

def _tramo(antes: Capacidad, ahora: Capacidad):
    return comp.comparar(comp.huella(antes), comp.huella(ahora))


def test_quitar_un_parametro_es_mayor():
    ahora = capacidad(parametros={"type": "object",
                                  "properties": {"largo": {"type": "number"}},
                                  "required": ["largo"]},
                      funcion=lambda largo: {"ok": True})
    tramo, motivos = _tramo(capacidad(), ahora)
    assert tramo == comp.MAYOR
    assert any("unidad" in m for m in motivos)


def test_anadir_un_parametro_obligatorio_es_mayor():
    ahora = capacidad(parametros={
        "type": "object",
        "properties": {"largo": {"type": "number"}, "unidad": {"type": "string"},
                       "alto": {"type": "number"}},
        "required": ["largo", "alto"]},
        funcion=lambda largo, alto, unidad="m": {"ok": True})
    tramo, motivos = _tramo(capacidad(), ahora)
    assert tramo == comp.MAYOR
    assert any("alto" in m for m in motivos)


def test_anadir_un_parametro_opcional_es_menor():
    ahora = capacidad(parametros={
        "type": "object",
        "properties": {"largo": {"type": "number"}, "unidad": {"type": "string"},
                       "nota": {"type": "string"}},
        "required": ["largo"]},
        funcion=lambda largo, unidad="m", nota=None: {"ok": True})
    assert _tramo(capacidad(), ahora)[0] == comp.MENOR


def test_ascender_un_opcional_a_obligatorio_es_mayor():
    ahora = capacidad(parametros={
        "type": "object",
        "properties": {"largo": {"type": "number"}, "unidad": {"type": "string"}},
        "required": ["largo", "unidad"]},
        funcion=lambda largo, unidad: {"ok": True})
    assert _tramo(capacidad(), ahora)[0] == comp.MAYOR


def test_estrechar_un_tipo_es_mayor_y_ensancharlo_es_menor():
    ancho = capacidad(parametros={
        "type": "object",
        "properties": {"largo": {"type": ["number", "string"]}, "unidad": {"type": "string"}},
        "required": ["largo"]})
    assert _tramo(ancho, capacidad())[0] == comp.MAYOR       # de dos tipos a uno
    assert _tramo(capacidad(), ancho)[0] == comp.MENOR       # de uno a dos


def test_anadir_un_efecto_es_mayor():
    """El caso que más importa de todos.

    Una capacidad que ayer era pura y hoy escribe un fichero, con la misma
    versión, se ejecutaría bajo una autorización concedida para otra cosa. No
    es un cambio de contrato: es un cambio de lo que le pasa al ordenador del
    arquitecto.
    """
    ahora = capacidad(naturaleza="io", efectos=("escribe_fichero",))
    tramo, motivos = _tramo(capacidad(), ahora)
    assert tramo == comp.MAYOR
    assert any("autorización" in m for m in motivos)


def test_cambiar_la_naturaleza_es_mayor():
    assert _tramo(capacidad(), capacidad(naturaleza="llm"))[0] == comp.MAYOR


def test_anadir_una_limitacion_declarada_es_solo_menor():
    """Declarar que algo NO se comprueba no cambia lo que la capacidad hace,
    sólo lo que dice de sí misma. Hacerse más honesto no puede salir caro."""
    ahora = capacidad(limitaciones=("no comprueba si el rectángulo existe",))
    assert _tramo(capacidad(), ahora)[0] == comp.MENOR


# --- Suficiencia del tramo subido -----------------------------------------

@pytest.mark.parametrize("antes,ahora,esperado", [
    ("1.0.0", "1.0.1", comp.PARCHE),
    ("1.0.0", "1.1.0", comp.MENOR),
    ("1.0.0", "2.0.0", comp.MAYOR),
    ("1.0.0", "1.0.0", None),
])
def test_se_detecta_que_tramo_se_ha_subido(antes, ahora, esperado):
    assert comp.tramo_subido(antes, ahora) == esperado


def test_subir_la_mayor_cubre_cualquier_exigencia_menor():
    assert comp.basta(comp.MAYOR, comp.MENOR)
    assert comp.basta(comp.MENOR, comp.MENOR)
    assert not comp.basta(comp.MENOR, comp.MAYOR)
    assert not comp.basta(None, comp.PARCHE)
    assert comp.basta(None, None)


def test_un_cambio_incompatible_sin_subir_la_mayor_se_denuncia():
    """El criterio de terminado de `CAD-2`, literal."""
    antes = {capacidad().id: comp.huella(capacidad())}
    rota = capacidad(version="1.0.1", naturaleza="io", efectos=("escribe_fichero",))
    fallos = comp.revisar(antes, [rota])
    assert len(fallos) == 1
    assert "mayor" in fallos[0] and "escribe_fichero" in fallos[0]


def test_el_mismo_cambio_con_la_mayor_subida_pasa():
    antes = {capacidad().id: comp.huella(capacidad())}
    correcta = capacidad(version="2.0.0", naturaleza="io", efectos=("escribe_fichero",))
    assert comp.revisar(antes, [correcta]) == []


def test_bajar_una_version_se_denuncia_aparte():
    antes = {capacidad(version="2.0.0").id: comp.huella(capacidad(version="2.0.0"))}
    fallos = comp.revisar(antes, [capacidad(version="1.9.9")])
    assert len(fallos) == 1 and "BAJADO" in fallos[0]


def test_una_capacidad_nueva_no_rompe_a_nadie():
    assert comp.revisar({}, [capacidad()]) == []


def test_una_capacidad_que_desaparece_si_rompe():
    """Alguien tiene un plan guardado que la nombra. Retirarla es un cambio
    mayor del producto, no una limpieza."""
    fallos = comp.revisar({capacidad().id: comp.huella(capacidad())}, [])
    assert len(fallos) == 1 and "desaparecido" in fallos[0]


# --- 3. Los planes guardados ----------------------------------------------

def test_un_plan_que_pide_la_version_exacta_se_ejecuta():
    reg = registro(recargar=True)
    assert reg.buscar("territorial.resolver_ambito@1.0.0").id == "territorial.resolver_ambito"


def test_un_plan_que_pide_una_version_compatible_se_ejecuta():
    """Es exactamente lo que promete el semver del manifiesto: dentro de la
    misma mayor, lo que se invocaba se sigue invocando igual."""
    reg = registro(recargar=True)
    assert reg.buscar("territorial.resolver_ambito@1.0.5").version == "1.0.0"


def test_un_plan_que_pide_otra_mayor_falla_con_un_mensaje_claro():
    """Y no se ejecuta «lo más parecido»: eso reescribiría en silencio lo que
    se hizo aquel día, que es lo contrario de un registro defendible."""
    reg = registro(recargar=True)
    with pytest.raises(CapacidadDesconocida) as excinfo:
        reg.buscar("territorial.resolver_ambito@2.0.0")
    mensaje = str(excinfo.value)
    assert "2.0.0" in mensaje and "1.0.0" in mensaje
    assert "incompatible" in mensaje


def test_un_plan_que_nombra_una_capacidad_inexistente_sigue_fallando_igual():
    reg = registro(recargar=True)
    with pytest.raises(CapacidadDesconocida):
        reg.buscar("no.existe@1.0.0")


def _congelar() -> None:
    contratos = {
        "_nota": ("Contrato de cada capacidad (tarea CAD-2): lo que un invocador de fuera "
                  "nota. La descripción NO está aquí a propósito. Generado por "
                  "`python tests/test_agente_compatibilidad.py --congelar`. Si esto cambia, "
                  "alguien ha cambiado un contrato: la versión tiene que reflejarlo."),
    }
    for cap in sorted(registro(recargar=True), key=lambda c: c.id):
        contratos[cap.id] = comp.huella(cap)
    CONGELADO.write_text(json.dumps(contratos, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    print("Congelados %d contratos en %s." % (len(contratos) - 1, CONGELADO.name))


if __name__ == "__main__":
    if "--congelar" in sys.argv:
        _congelar()
    else:
        print(__doc__)
