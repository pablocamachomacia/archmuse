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
from tests.test_agente_goldens import construir_dxf, construir_dxf_de_planta  # noqa: E402

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
    assert s.version == "2.0.0"      # 2026-09-13: la tabla es la plantilla fija
    assert s.efectos == (ESCRIBE_FICHERO,)
    # El invariante de TL-2: declara el efecto de la capacidad que escribe.
    s.comprobar_registro(registro(recargar=True))


def test_declara_las_capacidades_que_usa_y_solo_esas():
    # plano.cuadro_en_pdf se fusionó en plano.entregable_en_pdf (Prompt 1.7,
    # cierre de C4, 2026-08-21).
    assert set(skill().capacidades) == {
        "plano.leer_dxf", "plano.superficie_util",
        "plano.cuadro_de_superficies", "plano.escribir_cuadro",
        "plano.entregable_en_pdf",
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
    # Dos viviendas: la tabla no se calcula. Hasta el 2026-09-13 servía el piso sin
    # `ACAD_TABLE`; la plantilla fija ya no necesita el cuadro del arquitecto.
    ruta = construir_dxf_de_planta(tmp_path)
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


#: Las filas de la tabla, con la forma que devuelve `plano.cuadro_de_superficies`
#: desde la 2.0.0 (plantilla fija, 2026-09-13).
def _fila(rotulo, valor, ambito="interior", tiene_fila=True):
    return {"rotulo": rotulo, "valor": valor, "ambito": ambito, "tiene_fila": tiene_fila}


def _resultado(filas, medida=None, sin_resolver=()):
    from agente.afirmacion import calculo

    afirmaciones = [calculo("cuadro.celdas", list(filas), fuente="t"),
                    calculo("cuadro.celdas_sin_resolver", list(sin_resolver), fuente="t")]
    if medida is not None:
        afirmaciones.append(
            calculo("plano.superficie_util_total_m2", medida, fuente="t", unidad="m2"))
    return ResultadoDeSkill(afirmaciones=tuple(afirmaciones))


DOS_FILAS = (_fila("Salón/cocina", "20,00 m²"), _fila("Dormitorio 1", "12,00 m²"))


def test_un_desajuste_de_la_suma_avisa_con_las_dos_cifras_y_el_porcentaje():
    aviso = superficies._suma_cuadra(_resultado(DOS_FILAS, medida=100.0))
    assert isinstance(aviso, str)
    assert "32.00" in aviso and "100.00" in aviso and "%" in aviso


def test_una_suma_que_cuadra_dentro_de_la_tolerancia_pasa():
    assert superficies._suma_cuadra(_resultado(DOS_FILAS, medida=32.5)) is True


def test_una_pieza_sin_fila_con_un_numero_se_detecta():
    """La tercera condición de la aprobación de `TL-2`, comprobada también
    sobre el resultado que se guarda en el acta."""
    resultado = _resultado([_fila("Trastero", "2,70 m²", ambito=None, tiene_fila=False)])
    fallo = superficies._nada_sin_resolver_lleva_un_numero(resultado)
    assert isinstance(fallo, str) and "no puede pasar" in fallo


def test_una_fila_con_su_nota_no_puede_llevar_cifra():
    """Si la tabla dice por qué un hueco está vacío, ese hueco no puede tener número."""
    resultado = _resultado(
        [_fila("Terraza", "4,50 m²", ambito="exterior")],
        sin_resolver=[{"etiqueta": "Terraza", "motivo": "se solapa con otra pieza"}])
    fallo = superficies._nada_sin_resolver_lleva_un_numero(resultado)
    assert isinstance(fallo, str) and "Terraza" in fallo


def test_un_cero_se_detecta_aunque_la_capacidad_lo_dejara_pasar():
    fallo = superficies._nada_sin_resolver_lleva_un_numero(
        _resultado([_fila("Pasillo", "0,00 m²")]))
    assert isinstance(fallo, str) and "D-13" in fallo


def test_las_filas_con_cifra_y_los_huecos_vacios_estan_bien():
    resultado = _resultado(
        DOS_FILAS + (_fila("Terraza", "", ambito="exterior"),),
        sin_resolver=[{"etiqueta": "Terraza", "motivo": "se solapa con otra pieza"},
                      {"etiqueta": "TOTAL S. UTIL(m2)", "motivo": "C-1"}])
    assert superficies._nada_sin_resolver_lleva_un_numero(resultado) is True


def test_cortarse_a_mitad_no_se_presenta_como_un_fallo_del_sistema(tmp_path):
    """«No he podido, y esto es lo que falta» es una RESPUESTA, no un error.

    Cuando el procedimiento se corta —el DXF no traía cuadro— no hay entregable
    y por tanto no hay sello que acreditar. Exigirlo ahí convertiría una
    respuesta legítima en un «resultado no verificado», y el arquitecto leería
    un fallo del sistema donde sólo hay una pregunta.
    """
    ruta = construir_dxf_de_planta(tmp_path)          # dos viviendas: se corta
    salida = skill().ejecutar(contexto({"ruta_dxf": ruta,
                                        "ruta_destino": str(tmp_path / "copia.dxf")}))
    assert salida.resultado.entregables == ()
    fallidas = [r.nombre for r in salida.dictamen.resultados if r.bloqueante and not r.ok]
    assert fallidas == [], fallidas
    assert not (tmp_path / "copia.dxf").exists()


def test_el_trabajo_completo_sale_entero_sin_el_plano_real(tmp_path):
    """De punta a punta sobre el piso sintético, sin `v2s.dxf`.

    Hasta el 2026-09-13 esto sólo se podía comprobar con el plano del cliente,
    porque la 1.x necesitaba un `ACAD_TABLE`. La plantilla fija no lo necesita:
    el camino bueno entero —medir, construir la tabla, escribir la copia y el
    PDF, decir qué ha quedado vacío— corre ahora en CI.
    """
    import hashlib

    ruta = construir_dxf(tmp_path)
    antes = hashlib.sha256(Path(ruta).read_bytes()).hexdigest()
    destino = tmp_path / "copia.dxf"

    salida = skill().ejecutar(contexto({"ruta_dxf": ruta, "ruta_destino": str(destino)}))
    resultado = salida.resultado

    assert destino.exists() and destino.with_suffix(".pdf").exists()
    assert [e.tipo for e in resultado.entregables] == ["dxf", "pdf"]
    assert all(e.borrador and e.sello for e in resultado.entregables)
    assert hashlib.sha256(Path(ruta).read_bytes()).hexdigest() == antes
    # Lo que se ha dejado vacío, con nombre y motivo: al menos el número de
    # unidades (C-8). La útil total ya no: con la medición limpia la escribe
    # `C-14`, y decirla «no hecha» sería mentir sobre lo entregado.
    assert any("NUMERO UDS" in n for n in resultado.no_hecho), resultado.no_hecho
    assert not any("TOTAL S. UTIL" in n for n in resultado.no_hecho), resultado.no_hecho
    bloqueantes = [r for r in salida.dictamen.resultados if r.bloqueante]
    assert bloqueantes and all(r.ok for r in bloqueantes), [r.detalle for r in bloqueantes]
    # Y la suma cuadra: la tabla se ha cruzado de verdad contra la superficie medida.
    suma = next(r for r in salida.dictamen.resultados
                if r.nombre == "la_suma_cuadra_con_la_superficie_medida")
    assert suma.ok, suma.detalle


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

@pytest.mark.skip(reason=(
    "CADUCADO el 2026-09-13: describe las preguntas de asignación de la 1.x sobre "
    "v2s.dxf. Con la plantilla fija la única pregunta es interior/exterior por "
    "familia (probada en test_agente_skills_comun). Se reescribe cuando v2s.dxf se "
    "pueda ejecutar."))
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
