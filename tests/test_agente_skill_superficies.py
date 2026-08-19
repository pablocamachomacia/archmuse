# -*- coding: utf-8 -*-
"""SK-1 — el procedimiento del cuadro de superficies, no la suma de sus piezas.

Ejecutar:  pytest tests/test_agente_skill_superficies.py

PRD aprobado por Pablo el 2026-08-19, con una condición textual: **la
verificación de la suma es informativa, no bloqueante**, hasta tener al menos
diez proyectos reales. Ese punto tiene su test propio (`§3`), porque una
condición de aprobación que nadie comprueba se pierde en el primer refactor.

Lo que se fija aquí:

1. La Skill existe, está versionada y el registro la valida **al cargarse** —
   incluido el invariante nuevo de `TL-2`: una Skill no puede declarar una
   capacidad cuyo efecto no declara.
2. **El orden del procedimiento importa.** Si el plano no está en la unidad que
   dice, se para y se pregunta **antes** de calcular nada: un plano en
   milímetros leído como metros cumple todos los mínimos y sale impecable.
3. La suma se cruza contra la superficie medida por otro camino, y el aviso no
   impide entregar.
4. Sin autorización del efecto no se ejecuta.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente.efectos import ESCRIBE_FICHERO, Autorizaciones, EfectoNoAutorizado  # noqa: E402
from agente.memoria import MemoriaDeProyecto, SustratoEnMemoria  # noqa: E402
from agente.registro import registro, registro_de_skills  # noqa: E402
from agente.skill import Contexto, ResultadoDeSkill  # noqa: E402
from agente.skills import superficies  # noqa: E402
from tests.test_agente_goldens import construir_dxf  # noqa: E402

DXF_V2S = os.environ.get("ARCHMUSE_DXF_V2S", "")

SKILL_ID = "superficies.cuadro_de_vivienda"
PERMISO = Autorizaciones.de([ESCRIBE_FICHERO], por="test")


def skill():
    return registro_de_skills(recargar=True).buscar(SKILL_ID)


def contexto(argumentos, *, autorizada=True):
    return Contexto(
        skill(), memoria=MemoriaDeProyecto("p", SustratoEnMemoria()),
        registro=registro(recargar=True),
        autorizaciones=PERMISO if autorizada else None,
        argumentos=argumentos,
    )


# --- 1. Está declarada, y el registro la valida ---------------------------

def test_la_skill_esta_en_el_registro_y_se_valida_al_cargar():
    s = skill()
    assert s.version == "1.0.0"
    assert s.efectos == (ESCRIBE_FICHERO,)
    # El invariante de TL-2: declara el efecto de la capacidad que escribe.
    s.comprobar_registro(registro(recargar=True))


def test_declara_las_capacidades_que_usa_y_solo_esas():
    assert set(skill().capacidades) == {
        "plano.leer_dxf", "plano.superficie_util",
        "plano.cuadro_de_superficies", "plano.escribir_cuadro",
        "plano.cuadro_en_pdf",
    }


def test_el_procedimiento_esta_escrito_para_que_lo_juzgue_un_arquitecto():
    """No es documentación: es lo que se le enseña para que diga si el método
    es el suyo. Un procedimiento de una línea no se puede juzgar."""
    pasos = skill().procedimiento
    assert len(pasos) >= 5
    assert any("unidad" in p for p in pasos), "el primer control tiene que estar escrito"


def test_dice_lo_que_no_hace():
    limitaciones = " ".join(skill().limitaciones)
    assert "normativa" in limitaciones
    assert "tolerancia" in limitaciones      # el aviso informativo, declarado


# --- 2. El orden del procedimiento ----------------------------------------

def test_sin_unidad_determinable_se_para_y_se_pregunta(tmp_path):
    """EL CONTROL QUE VA PRIMERO, Y POR QUÉ VA PRIMERO.

    Un plano en milímetros leído como metros cumple todas las superficies
    mínimas y sale con una puntuación alta y creíble. Si eso no se resuelve, lo
    demás sobra — y sobre todo, no se escribe nada.
    """
    import ezdxf

    from analyzer import parser

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 0
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()
    # Estancias de 0,2 m²: ninguna unidad métrica las explica.
    for i in range(3):
        msp.add_lwpolyline([(0, i), (0.5, i), (0.5, i + 0.4), (0, i + 0.4)], close=True,
                           dxfattribs={"layer": parser.AREA_LAYER})
    ruta = tmp_path / "ambiguo.dxf"
    doc.saveas(str(ruta))

    ctx = contexto({"ruta_dxf": str(ruta), "ruta_destino": str(tmp_path / "copia.dxf")})
    resultado = skill().ejecutar(ctx).resultado

    assert resultado.preguntas, "tenía que preguntar"
    assert resultado.no_hecho
    # No se ha escrito nada.
    assert not (tmp_path / "copia.dxf").exists()
    # Y sólo se invocó la lectura: el cálculo no llegó a ejecutarse.
    assert [i["capacidad"] for i in ctx.invocaciones] == ["plano.leer_dxf"]


def test_lo_que_no_se_ha_producido_sale_UNKNOWN_con_motivo_y_no_ausente(tmp_path):
    """Un hueco mudo se lee como «no aplica», que es la lectura contraria."""
    ruta = construir_dxf(tmp_path)          # sin ACAD_TABLE: el cuadro no se calcula
    ctx = contexto({"ruta_dxf": ruta, "ruta_destino": str(tmp_path / "copia.dxf")})
    resultado = skill().ejecutar(ctx).resultado

    nombres = {a.nombre for a in resultado.afirmaciones}
    assert set(superficies.PRODUCE) <= nombres, "falta declarar algo que se prometió"
    sin_valor = [a for a in resultado.afirmaciones if a.valor is None]
    assert sin_valor, "algo tenía que quedar sin resolver con este DXF"
    for a in sin_valor:
        assert a.motivo is not None, a.nombre


def test_el_cuadro_no_se_calcula_antes_de_medir_la_superficie(tmp_path):
    """El orden no es estético: la superficie útil se mide por su propio camino
    para poder cruzarla contra la suma. Calcularla del cuadro haría que la
    comprobación comprobara que una suma es igual a sí misma."""
    ruta = construir_dxf(tmp_path)
    ctx = contexto({"ruta_dxf": ruta, "ruta_destino": str(tmp_path / "copia.dxf")})
    skill().ejecutar(ctx)
    orden = [i["capacidad"] for i in ctx.invocaciones]
    assert orden.index("plano.superficie_util") < orden.index("plano.cuadro_de_superficies")


# --- 3. La condición de la aprobación: la suma avisa, no bloquea ---------

def test_la_verificacion_de_la_suma_es_informativa_y_no_bloqueante():
    """CONDICIÓN TEXTUAL DE LA APROBACIÓN (Pablo, 2026-08-19).

    Cambiar esto a bloqueante es una decisión de producto —hace falta calibrar
    la tolerancia con al menos diez proyectos reales—, no un ajuste. Este test
    está para que ese cambio sea deliberado.
    """
    suma = next(v for v in skill().verificaciones
                if v.nombre == "la_suma_cuadra_con_la_superficie_medida")
    assert suma.bloqueante is False


def test_un_desajuste_de_la_suma_avisa_con_las_dos_cifras_y_el_porcentaje():
    from agente.afirmacion import calculo

    resultado = ResultadoDeSkill(afirmaciones=(
        calculo("plano.superficie_util_total_m2", 100.0, fuente="t", unidad="m2"),
        calculo("cuadro.celdas", [
            {"campo": "salon_cocina", "texto": "20,00 m²", "estado": "CALCULADO"},
            {"campo": "dormitorio_1", "texto": "12,00 m²", "estado": "CALCULADO"},
        ], fuente="t"),
    ))
    aviso = superficies._suma_cuadra(resultado)
    assert isinstance(aviso, str)
    assert "32.00" in aviso and "100.00" in aviso and "%" in aviso


def test_una_suma_que_cuadra_dentro_de_la_tolerancia_pasa():
    from agente.afirmacion import calculo

    resultado = ResultadoDeSkill(afirmaciones=(
        calculo("plano.superficie_util_total_m2", 32.5, fuente="t", unidad="m2"),
        calculo("cuadro.celdas", [
            {"campo": "salon_cocina", "texto": "20,00 m²", "estado": "CALCULADO"},
            {"campo": "dormitorio_1", "texto": "12,00 m²", "estado": "CALCULADO"},
        ], fuente="t"),
    ))
    assert superficies._suma_cuadra(resultado) is True


def test_los_totales_no_se_suman_dos_veces():
    """Un cuadro trae sus propios totales; sumarlos con las partes duplicaría."""
    from agente.afirmacion import calculo

    resultado = ResultadoDeSkill(afirmaciones=(
        calculo("plano.superficie_util_total_m2", 32.0, fuente="t", unidad="m2"),
        calculo("cuadro.celdas", [
            {"campo": "salon_cocina", "texto": "20,00 m²", "estado": "CALCULADO"},
            {"campo": "dormitorio_1", "texto": "12,00 m²", "estado": "CALCULADO"},
            {"campo": "total_util_interior", "texto": "32,00 m²", "estado": "CALCULADO"},
        ], fuente="t"),
    ))
    assert superficies._suma_cuadra(resultado) is True


def test_una_celda_sin_resolver_con_un_numero_se_detecta():
    """La tercera condición de la aprobación de `TL-2`, comprobada también
    sobre el resultado que se guarda en el acta."""
    from agente.afirmacion import calculo

    resultado = ResultadoDeSkill(afirmaciones=(
        calculo("cuadro.celdas", [
            {"campo": "superficie_construida_cerrada", "texto": "65,40 m²",
             "estado": "NO_DISPONIBLE"},
        ], fuente="t"),
    ))
    fallo = superficies._nada_sin_resolver_lleva_un_numero(resultado)
    assert isinstance(fallo, str) and "no puede pasar" in fallo


def test_una_celda_sin_resolver_con_ND_esta_bien():
    from agente.afirmacion import calculo

    resultado = ResultadoDeSkill(afirmaciones=(
        calculo("cuadro.celdas", [
            {"campo": "superficie_construida_cerrada", "texto": "N/D",
             "estado": "NO_DISPONIBLE"},
        ], fuente="t"),
    ))
    assert superficies._nada_sin_resolver_lleva_un_numero(resultado) is True


def test_cortarse_a_mitad_no_se_presenta_como_un_fallo_del_sistema(tmp_path):
    """«No he podido, y esto es lo que falta» es una RESPUESTA, no un error.

    Cuando el procedimiento se corta —el DXF no traía cuadro— no hay entregable
    y por tanto no hay sello que acreditar. Exigirlo ahí convertiría una
    respuesta legítima en un «resultado no verificado», y el arquitecto leería
    un fallo del sistema donde sólo hay una pregunta.
    """
    ruta = construir_dxf(tmp_path)
    salida = skill().ejecutar(contexto({"ruta_dxf": ruta,
                                        "ruta_destino": str(tmp_path / "copia.dxf")}))
    assert salida.resultado.entregables == ()
    fallidas = [r.nombre for r in salida.dictamen.resultados if r.bloqueante and not r.ok]
    assert fallidas == [], fallidas
    assert not (tmp_path / "copia.dxf").exists()


def test_entregar_sin_acreditar_el_sello_si_es_un_fallo():
    """El reverso: si hay fichero entregado, el sello es obligatorio."""
    from agente.skill import Entregable

    sin_acta = ResultadoDeSkill(
        entregables=(Entregable(nombre="x", tipo="dxf", ruta="/tmp/x.dxf"),),
        notas=("todo bien",),
    )
    fallo = superficies._el_original_no_se_ha_tocado(sin_acta)
    assert isinstance(fallo, str) and "no acredita" in fallo


# --- 4. La autorización ---------------------------------------------------

def test_sin_autorizacion_la_skill_no_se_ejecuta(tmp_path):
    ruta = construir_dxf(tmp_path)
    ctx = contexto({"ruta_dxf": ruta, "ruta_destino": str(tmp_path / "copia.dxf")},
                   autorizada=False)
    with pytest.raises(EfectoNoAutorizado):
        skill().ejecutar(ctx)
    assert ctx.invocaciones == [], "no puede haber ejecutado nada"


# --- 5. El trabajo completo, con el DXF real ----------------------------

@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S para el trabajo completo")
def test_el_trabajo_completo_entrega_el_dxf_relleno_y_dice_lo_que_falta(tmp_path):
    import hashlib

    antes = hashlib.sha256(Path(DXF_V2S).read_bytes()).hexdigest()
    destino = tmp_path / "v2s_relleno.dxf"

    salida = skill().ejecutar(contexto({"ruta_dxf": DXF_V2S, "ruta_destino": str(destino)}))
    resultado = salida.resultado

    assert destino.exists()
    assert resultado.entregables and resultado.entregables[0].tipo == "dxf"
    # C3: no existe entregable que no sea borrador. Lo impide el propio tipo.
    assert resultado.entregables[0].borrador is True
    assert resultado.entregables[0].sello
    # La condición nº1 de la aprobación de TL-2, de punta a punta.
    assert hashlib.sha256(Path(DXF_V2S).read_bytes()).hexdigest() == antes
    assert any("sha256" in n for n in resultado.notas)
    # Lo que no se ha podido calcular, dicho con nombre y motivo.
    assert resultado.no_hecho
    # Y el dictamen existe: sin comprobaciones no hay «verificado».
    assert salida.dictamen.resultados


@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S para el trabajo completo")
def test_un_aviso_de_suma_no_impide_la_entrega(tmp_path):
    """La condición de Pablo, comprobada de punta a punta: si el aviso saltara,
    el entregable sale igual."""
    destino = tmp_path / "v2s.dxf"
    salida = skill().ejecutar(contexto({"ruta_dxf": DXF_V2S, "ruta_destino": str(destino)}))
    assert destino.exists()
    bloqueantes = [r for r in salida.dictamen.resultados if r.bloqueante]
    assert all(r.ok for r in bloqueantes), [r.detalle for r in bloqueantes if not r.ok]


# --- 6. Una pregunta que no se puede contestar no es preguntar ------------
#
# Encontrado sobre `v2s.dxf`. La Skill declara «no resuelve las ambiguedades del
# plano: las pregunta», y devolvia solo el `titulo` de cada solicitud. Como
# redactar la pregunta es cierto para toda Skill y no solo para esta, la pieza
# vive en `agente/skills/_comun.py` y se prueba en `test_agente_skills_comun.py`.
# Lo que se fija AQUI es lo otro: que esta Skill la use de verdad.

@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S: un ACAD_TABLE no se sintetiza")
def test_la_pregunta_sale_entera_del_procedimiento_y_no_solo_su_titulo(tmp_path):
    """De punta a punta sobre el plano real: lo que la Skill entrega es lo que
    se puede contestar.

    Sin esto, `pregunta_legible` podria estar perfecta y no llamarse desde
    ningun sitio, que es como quedan la mitad de las correcciones. Hace falta
    el plano real porque las solicitudes de asignacion nacen de una ambiguedad
    de verdad —dos piezas rotuladas igual, un recinto solapado— y un
    `ACAD_TABLE` no se sintetiza de forma realista.
    """
    destino = tmp_path / "v2s_preguntas.dxf"
    salida = skill().ejecutar(
        contexto({"ruta_dxf": DXF_V2S, "ruta_destino": str(destino)}))

    assert salida.resultado.preguntas, (
        "el plano real tiene ambiguedades: si no pregunta nada, o se han "
        "resuelto solas o se han repartido en silencio")
    for pregunta in salida.resultado.preguntas:
        assert "Para contestar:" in pregunta, (
            "la pregunta «%s» no dice como se contesta" % pregunta)
        assert "Resuelve:" in pregunta, (
            "la pregunta «%s» no dice que hueco del cuadro desbloquea" % pregunta)
