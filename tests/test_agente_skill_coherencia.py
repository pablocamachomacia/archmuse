# -*- coding: utf-8 -*-
"""La Skill de revision de coherencia del plano (`CO-5`).

Ejecutar:  pytest tests/test_agente_skill_coherencia.py

PRD: `docs/prd/2026-08-19-revision-de-coherencia-del-plano.md`. La logica de las
comprobaciones se prueba en `tests/test_coherencia.py`; aqui se fija lo que es
propio de la Skill:

1. Esta declarada, el registro la valida al cargar, y **no declara ninguna
   capacidad de normativa** — que es la forma mecanica de garantizar el
   criterio de aceptacion nº4: este entregable no depende del corpus.
2. **No emite criterio profesional.** La verificacion `ningun_hallazgo_lleva_gravedad`
   es bloqueante, y es lo que mantiene esta Skill fuera del bloqueo de `D-7`.
   Su test comprueba que **falla de verdad**: una verificacion que no puede
   fallar no comprueba nada.
3. Sin autorizacion no se ejecuta, y sin poder leer el plano se pregunta en vez
   de suponer.
4. Sobre el plano real: entrega, el original no se toca, y el informe existe.
"""
from __future__ import annotations

import hashlib
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
from agente.skills import coherencia as skill_coherencia  # noqa: E402
from tests.test_coherencia import construir  # noqa: E402

DXF_V2S = os.environ.get("ARCHMUSE_DXF_V2S", "")

SKILL_ID = "revision.coherencia_del_plano"
PERMISO = Autorizaciones.de([ESCRIBE_FICHERO], por="test")

PIEZAS_LIMPIAS = (
    ("Salon", (0.0, 0.0), (4.0, 3.0)),
    ("Cocina", (5.0, 0.0), (8.0, 3.0)),
    ("Dormitorio 1", (0.0, 5.0), (4.0, 8.0)),
)


def skill():
    return registro_de_skills(recargar=True).buscar(SKILL_ID)


def contexto(argumentos, *, autorizada=True):
    return Contexto(
        skill(), memoria=MemoriaDeProyecto("p", SustratoEnMemoria()),
        registro=registro(recargar=True),
        autorizaciones=PERMISO if autorizada else None,
        argumentos=argumentos,
    )


def _resultado_con(hallazgos):
    """Un `ResultadoDeSkill` con los hallazgos que se le pidan, para probar las
    verificaciones sin ejecutar la Skill entera."""
    from agente.afirmacion import calculo

    return ResultadoDeSkill(
        afirmaciones=(calculo("revision.hallazgos", hallazgos, fuente="t@1.0.0"),))


# --- 1. Declarada, validada, y sin normativa -----------------------------

def test_la_skill_esta_en_el_registro_y_se_valida_al_cargar():
    s = skill()
    assert s.version == "1.0.0"
    assert s.dominio == "revision"
    assert ESCRIBE_FICHERO in s.efectos


def test_no_declara_ninguna_capacidad_de_normativa():
    """**El criterio de aceptacion nº4, comprobado mecanicamente.**

    Este entregable existe porque no depende del corpus. Que no dependa no se
    garantiza con una promesa en la documentacion: se garantiza porque el
    `Contexto` se niega a dar una capacidad que la Skill no declare, asi que
    basta con que no declare ninguna de normativa.
    """
    assert set(skill().capacidades) == {"plano.coherencia", "plano.informe_de_coherencia"}
    assert not [c for c in skill().capacidades if c.startswith("normativa.")]


def test_dice_lo_que_no_hace_y_ninguna_limitacion_es_normativa():
    limitaciones = " ".join(skill().limitaciones).lower()
    assert "no comprueba normativa" in limitaciones
    assert "no gradúa" in limitaciones or "no gradua" in limitaciones


def test_el_procedimiento_empieza_por_la_unidad_del_dibujo():
    """El mismo orden que `SK-1`, y por el mismo motivo: medir un solape sin
    saber la unidad produce una cifra de siete digitos que parece un hallazgo
    enorme y no significa nada."""
    primero = skill().procedimiento[0].lower()
    assert "unidad" in primero
    assert "parar" in primero or "preguntar" in primero


# --- 2. La frontera con el criterio profesional --------------------------

def test_la_verificacion_de_gravedad_falla_cuando_un_hallazgo_califica():
    """Una verificacion que no puede fallar no comprueba nada.

    Este es el guardian de la frontera de `D-7`: mientras pase, esta Skill
    mide; el dia que alguien la haga fallar, ArchMuse ha empezado a opinar sobre
    el trabajo de un colegiado.
    """
    fallo = skill_coherencia._ningun_hallazgo_lleva_gravedad(_resultado_con([
        {"tipo": "solape_entre_recintos", "entidad": "a + b",
         "descripcion": "Esto es un error grave que hay que corregir."},
    ]))
    assert fallo is not True
    assert "grave" in str(fallo)


def test_la_verificacion_de_gravedad_falla_si_aparece_un_campo_de_severidad():
    fallo = skill_coherencia._ningun_hallazgo_lleva_gravedad(_resultado_con([
        {"tipo": "solape_entre_recintos", "entidad": "a + b",
         "descripcion": "se solapan 4,00 m2", "severidad": "ALTA"},
    ]))
    assert fallo is not True
    assert "gravedad" in str(fallo)


def test_un_hallazgo_que_solo_mide_pasa_la_verificacion():
    assert skill_coherencia._ningun_hallazgo_lleva_gravedad(_resultado_con([
        {"tipo": "solape_entre_recintos", "entidad": "Salon + Terraza",
         "descripcion": "«Salon» y «Terraza» se solapan 2.00 m² (el 33 % de la "
                        "pieza menor). Esa superficie se está contando dos veces."},
    ])) is True


def test_un_hallazgo_sin_entidad_hace_fallar_la_verificacion():
    fallo = skill_coherencia._ningun_hallazgo_sin_entidad(_resultado_con([
        {"tipo": "solape_entre_recintos", "entidad": "  ", "descripcion": "x"},
    ]))
    assert fallo is not True
    assert "dónde" in str(fallo)


# --- 3. Autorizacion y negativas ----------------------------------------

def test_sin_autorizacion_la_skill_no_se_ejecuta(tmp_path):
    ruta = construir(PIEZAS_LIMPIAS, destino=tmp_path)
    with pytest.raises(EfectoNoAutorizado):
        skill().ejecutar(contexto(
            {"ruta_dxf": str(ruta), "ruta_informe": str(tmp_path / "i.pdf")},
            autorizada=False))


def test_un_fichero_que_no_existe_se_pregunta_y_no_se_escribe_nada(tmp_path):
    destino = tmp_path / "i.pdf"
    salida = skill().ejecutar(contexto(
        {"ruta_dxf": str(tmp_path / "no_existe.dxf"), "ruta_informe": str(destino)}))
    assert not destino.exists()
    assert salida.resultado.preguntas
    # Lo prometido y no producido sale UNKNOWN con motivo, nunca ausente.
    nombres = {a.nombre for a in salida.resultado.afirmaciones}
    assert nombres == set(skill_coherencia.PRODUCE)
    assert all(a.estado == "UNKNOWN" for a in salida.resultado.afirmaciones)


def test_el_informe_no_puede_escribirse_sobre_el_propio_plano(tmp_path):
    """Escribir el informe encima del DXF lo destruiria, y es un error de dedo
    perfectamente posible en una linea de ordenes."""
    ruta = construir(PIEZAS_LIMPIAS, destino=tmp_path)
    antes = ruta.read_bytes()
    salida = skill().ejecutar(contexto(
        {"ruta_dxf": str(ruta), "ruta_informe": str(ruta)}))
    assert ruta.read_bytes() == antes
    assert not salida.resultado.entregables
    assert salida.resultado.preguntas


# --- 4. El trabajo completo ---------------------------------------------

def test_un_plano_limpio_entrega_informe_y_dice_que_ha_comprobado(tmp_path):
    ruta = construir(PIEZAS_LIMPIAS, destino=tmp_path)
    destino = tmp_path / "informe.pdf"
    salida = skill().ejecutar(contexto(
        {"ruta_dxf": str(ruta), "ruta_informe": str(destino)}))

    assert destino.exists() and destino.stat().st_size > 0
    assert salida.verificado, [r.detalle for r in salida.dictamen.resultados if not r.ok]
    entregable = salida.resultado.entregables[0]
    assert entregable.tipo == "pdf"
    # C3: no existe entregable que no sea borrador. Lo impide el propio tipo.
    assert entregable.borrador is True and entregable.sello

    hallazgos = next(a.valor for a in salida.resultado.afirmaciones
                     if a.nombre == "revision.hallazgos")
    assert hallazgos == []
    comprobado = next(a.valor for a in salida.resultado.afirmaciones
                      if a.nombre == "revision.comprobado")
    assert comprobado, "sin esto, «no se ha encontrado nada» no significa nada"


@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S para el plano real")
def test_el_trabajo_completo_sobre_el_plano_real(tmp_path):
    """De punta a punta sobre el DXF del cliente: entrega, y no lo toca."""
    antes = hashlib.sha256(Path(DXF_V2S).read_bytes()).hexdigest()
    destino = tmp_path / "v2s_revision.pdf"

    salida = skill().ejecutar(contexto(
        {"ruta_dxf": DXF_V2S, "ruta_informe": str(destino)}))

    assert destino.exists() and destino.stat().st_size > 0
    assert salida.verificado, [r.detalle for r in salida.dictamen.resultados if not r.ok]
    # La condicion que se le exige a toda escritura desde `TL-2`.
    assert hashlib.sha256(Path(DXF_V2S).read_bytes()).hexdigest() == antes
    assert any("sha256" in n for n in salida.resultado.notas)

    hallazgos = next(a.valor for a in salida.resultado.afirmaciones
                     if a.nombre == "revision.hallazgos")
    assert len(hallazgos) == 9
    for h in hallazgos:
        assert h["entidad"].strip(), "un hallazgo sin dónde mirarlo no sirve"
    # Y ninguno califica: el acta que se guarda es la que se comprueba.
    assert skill_coherencia._ningun_hallazgo_lleva_gravedad(salida.resultado) is True


# --- 5. Los tres contratos de `agente/` que Terminal 1 encontro sin cumplir --

def test_la_capacidad_que_escribe_usa_los_guardianes_COMPARTIDOS():
    """No basta con proteger: hay que proteger **con la pieza compartida**.

    La primera version reimplementaba «algo parecido» a `_destino_seguro` y a
    `_con_sello_intacto` dentro del propio modulo. Funcionaba, y ese es el
    problema: el dia que se endurezca la proteccion —porque se pierda el plano
    de un cliente— se endurece en un sitio y la copia se queda como estaba, sin
    que nadie lo note. `tests/test_agente_escritura.py` lo vigila sobre el
    fuente; esto lo fija ademas sobre el comportamiento, que es lo que cambio.
    """
    from agente.herramientas import coherencia as h
    from agente.herramientas import plano

    assert h._destino_seguro is plano._destino_seguro
    assert h._con_sello_intacto is plano._con_sello_intacto


def test_no_se_sobrescribe_un_informe_anterior(tmp_path):
    """Un informe ya escrito puede estar revisado y anotado. La segunda pasada
    no lo pisa: pide otro nombre."""
    ruta = construir(PIEZAS_LIMPIAS, destino=tmp_path)
    destino = tmp_path / "informe.pdf"
    primera = skill().ejecutar(contexto(
        {"ruta_dxf": str(ruta), "ruta_informe": str(destino)}))
    assert primera.resultado.entregables
    bytes_primera = destino.read_bytes()

    segunda = skill().ejecutar(contexto(
        {"ruta_dxf": str(ruta), "ruta_informe": str(destino)}))
    assert destino.read_bytes() == bytes_primera, "ha pisado el informe anterior"
    assert not segunda.resultado.entregables
    assert segunda.resultado.preguntas


def test_las_dos_capacidades_devuelven_un_dict_con_ok_tambien_al_fallar():
    """El contrato de salida del registro, en el camino de fallo — que es el que
    se olvida."""
    from agente.registro import registro as _registro

    reg = _registro(recargar=True)
    for identificador, argumentos in (
        ("plano.coherencia", {"ruta": "no_existe.dxf"}),
        ("plano.informe_de_coherencia", {"ruta": "no_existe.dxf",
                                         "ruta_destino": "tampoco.pdf"}),
    ):
        salida = reg.buscar(identificador).funcion(**argumentos)
        assert isinstance(salida, dict)
        assert salida.get("ok") is False
        assert salida.get("error") and salida.get("pregunta")
