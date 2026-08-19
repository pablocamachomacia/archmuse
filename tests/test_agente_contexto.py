# -*- coding: utf-8 -*-
"""ME-5 — el planificador ve lo que decide, y nada más.

Ejecutar:  pytest tests/test_agente_contexto.py

La propiedad que se compra aquí tiene dos caras, y las dos son de dinero:

1. **Tamaño acotado.** El resumen de un proyecto de 10.000 atributos ocupa
   aproximadamente lo mismo que el de uno de 20. Sin esto, cada llamada del
   planificador crece con el proyecto sin mejorar ni una decisión.
2. **Orden estable.** Los manifiestos van en el prefijo del prompt. Un orden
   que cambie entre procesos hace que la caché no acierte nunca y encarece el
   planificador **en silencio**, que es lo que lo hace peligroso.

Y una tercera que no es de dinero: lo que se omite se **dice**. Un modelo que
no sabe que hay más datos de los que ve da por resuelto lo que nadie resolvió.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente import contexto  # noqa: E402
from agente.memoria import MemoriaDeProyecto, SustratoEnMemoria  # noqa: E402
from agente.registro import registro, registro_de_skills  # noqa: E402


def memoria_con(claves: dict, proyecto_id: str = "p") -> MemoriaDeProyecto:
    m = MemoriaDeProyecto(proyecto_id, SustratoEnMemoria())
    for clave, valor in claves.items():
        m.declarar(clave, valor, registrado_por="usuario:pablo")
    return m


# --- 1. Tamaño acotado ------------------------------------------------------

def test_el_resumen_no_crece_con_el_proyecto():
    """LA PROPIEDAD CENTRAL DE ME-5.

    Diez mil atributos y veinte producen resúmenes del mismo orden de tamaño,
    porque lo que crece se agrega por familia en vez de listarse.
    """
    skills = registro_de_skills(recargar=True)
    pequeno = memoria_con({"programa.dato_%d" % i: i for i in range(20)})
    grande = memoria_con({"programa.dato_%d" % i: i for i in range(10_000)})

    texto_pequeno = contexto.a_texto(contexto.resumen_del_proyecto(pequeno, skills))
    texto_grande = contexto.a_texto(contexto.resumen_del_proyecto(grande, skills))

    assert len(texto_grande) < 2 * len(texto_pequeno)
    assert len(texto_grande) < 4000, "el resumen tiene que caber en una decisión"


def test_lo_que_no_se_envia_se_dice_y_se_cuenta():
    """Callar los datos omitidos haría que el modelo los diera por inexistentes."""
    skills = registro_de_skills(recargar=True)
    resumen = contexto.resumen_del_proyecto(
        memoria_con({"programa.dato_%d" % i: i for i in range(500)}), skills)
    assert resumen["espacios"]["programa"]["KNOWN"] == 500
    assert "por familia" in contexto.a_texto(resumen)


def test_los_espacios_de_nombres_tambien_estan_acotados():
    muchos = memoria_con({"espacio_%03d.dato" % i: i for i in range(60)})
    resumen = contexto.resumen_del_proyecto(muchos, (), max_espacios=10)
    assert len(resumen["espacios"]) == 11        # 10 detallados + la línea de resto
    resto = [k for k in resumen["espacios"] if k.startswith("(otros")]
    assert resto and resumen["espacios"][resto[0]]["total"] == 50


def test_los_conflictos_se_acotan_pero_se_dice_cuantos_faltan():
    """Un conflicto oculto es peor que un conflicto resumido."""
    m = MemoriaDeProyecto("p", SustratoEnMemoria())
    for i in range(9):
        m.declarar("programa.c%d" % i, 1, registrado_por="cliente (marzo)")
        m.declarar("programa.c%d" % i, 2, registrado_por="cliente (agosto)")
    resumen = contexto.resumen_del_proyecto(m, (), max_conflictos=3)
    assert len(resumen["conflictos"]) == 3
    assert resumen["conflictos_omitidos"] == 6
    assert "y 6 más" in contexto.a_texto(resumen)


# --- 2. Lo que decide va entero --------------------------------------------

def test_las_claves_que_alguna_skill_exige_van_una_por_una():
    """Son las que deciden si un plan es ejecutable o la respuesta es una
    pregunta. Agregarlas por familia perdería justo la información útil."""
    skills = registro_de_skills(recargar=True)
    decisivas = contexto.claves_que_deciden(skills)
    assert "territorial.municipio" in decisivas

    resumen = contexto.resumen_del_proyecto(memoria_con({"territorial.municipio": "Madrid"}),
                                            skills)
    assert resumen["requisitos"]["territorial.municipio"] == contexto.KNOWN
    for clave in decisivas:
        assert clave in resumen["requisitos"]


def test_un_requisito_ausente_se_declara_UNKNOWN_y_no_se_omite():
    """Omitirlo se leería como «no hace falta», que es la lectura contraria."""
    skills = registro_de_skills(recargar=True)
    resumen = contexto.resumen_del_proyecto(memoria_con({}), skills)
    assert set(resumen["requisitos"].values()) == {contexto.UNKNOWN}
    assert "territorial.municipio" in contexto.a_texto(resumen)


def test_un_requisito_no_se_cuenta_dos_veces():
    skills = registro_de_skills(recargar=True)
    resumen = contexto.resumen_del_proyecto(memoria_con({"territorial.municipio": "Madrid"}),
                                            skills)
    assert "territorial" not in resumen["espacios"]


def test_los_valores_del_proyecto_no_viajan_al_modelo():
    """Lo que hay en esos atributos son datos del proyecto de un cliente.

    El planificador decide con estados, no con valores: enviarlos sería
    exponerlos sin que cambie ninguna decisión.
    """
    m = memoria_con({"programa.presupuesto_del_cliente": "1.250.000 EUR",
                     "programa.nombre_del_cliente": "Fulano de Tal"})
    texto = contexto.a_texto(contexto.resumen_del_proyecto(m, ()))
    assert "1.250.000" not in texto
    assert "Fulano" not in texto


def test_sin_memoria_se_dice_que_no_hay_memoria():
    """«Proyecto sin datos» y «no me han pasado el proyecto» llevan a planes
    distintos, así que no pueden representarse igual."""
    resumen = contexto.resumen_del_proyecto(None, ())
    assert resumen["sin_memoria"] is True
    assert "no hay memoria de proyecto" in contexto.a_texto(resumen)


# --- 3. Orden estable, que es lo que hace que la caché acierte ------------

def test_el_prefijo_de_manifiestos_es_identico_entre_llamadas():
    caps, skills = registro(recargar=True), registro_de_skills(recargar=True)
    primero = contexto.prefijo_cacheable(caps, skills)
    segundo = contexto.prefijo_cacheable(registro(recargar=True),
                                         registro_de_skills(recargar=True))
    assert primero == segundo


def test_el_prefijo_no_depende_del_orden_en_que_lleguen_las_capacidades():
    caps = list(registro(recargar=True))
    assert contexto.prefijo_cacheable(caps) == contexto.prefijo_cacheable(list(reversed(caps)))


def test_el_prefijo_lleva_las_limitaciones_de_cada_capacidad():
    """Si el prefijo perdiera el «NO comprueba», el planificador elegiría
    herramientas creyendo que hacen más de lo que hacen."""
    assert "NO comprueba" in contexto.prefijo_cacheable(registro(recargar=True))


def test_el_contexto_separa_lo_estable_de_lo_variable():
    caps, skills = registro(recargar=True), registro_de_skills(recargar=True)
    ctx = contexto.contexto_del_planificador(memoria_con({"territorial.municipio": "Madrid"}),
                                             caps, skills)
    assert ctx["prefijo"] == contexto.prefijo_cacheable(caps, skills)
    assert "Madrid" not in ctx["estado_texto"]      # el valor no, el estado sí
    assert "territorial.municipio" in ctx["estado_texto"]
