# -*- coding: utf-8 -*-
"""La medición de una planta con varias viviendas, de punta a punta.

**Qué se está protegiendo aquí, y no es «que el cálculo dé bien».** Una
medición de superficies es un documento que un arquitecto copia a su proyecto y
acaba firmando. Los dos modos de fallo que importan no son que la suma salga
mal —eso se ve— sino los dos que no se ven:

1. **Que una pieza desaparezca.** Un total que se deja fuera una habitación
   parece razonable, cuadra consigo mismo y está mal. Aquí se comprueba que
   toda pieza dibujada aparece y que todo total publicado las contiene todas.
2. **Que se publique un total que no se puede afirmar.** Piezas solapadas,
   reparto dudoso entre viviendas o una pieza que no se sabe si es interior o
   exterior. La regla es que basta uno para que no haya total, y hay un test que
   comprueba que la verificación **falla de verdad** cuando se cruza — un
   guardián que nadie ha visto morder no es un guardián.

Los casos sintéticos usan superficies redondas (20, 12, 9, 4 m²) para que
cualquier diferencia se lea a simple vista. Los dos planos reales del cliente
—uno de una vivienda con solapes, otro de tres viviendas limpias— se prueban
con sus cifras exactas y se saltan con motivo si no están sus variables.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from agente import efectos as _efectos  # noqa: E402
from agente.ejecucion import BitacoraEnMemoria, Ejecutor, Paso, Plan  # noqa: E402
from agente.memoria import MemoriaDeProyecto, SustratoEnMemoria  # noqa: E402
from agente.registro import registro, registro_de_skills  # noqa: E402
from analyzer import medicion as _medicion  # noqa: E402
from analyzer.medicion import (  # noqa: E402
    AMBITO_EXTERIOR,
    AMBITO_INTERIOR,
    AMBITO_SIN_CLASIFICAR,
    POR_PROXIMIDAD,
    POR_ROTULOS,
    medir_planta,
)

DXF_V2S = os.environ.get("ARCHMUSE_DXF_V2S", "")
DXF_PLANTA = os.environ.get("ARCHMUSE_DXF_PLANTA", "")

SKILL = "superficies.medicion_de_planta"


# --- Construcción de planos de prueba ---------------------------------------

def construir(destino: Path, piezas, etiquetas_de_vivienda=(), nombre="planta.dxf") -> str:
    """Un DXF en metros con los rectángulos y las etiquetas que se le pidan.

    `piezas` es una secuencia de `(rótulo, (x0, y0), (x1, y1))`; las etiquetas de
    vivienda son `(texto, x, y)`. Nada más: los casos se leen enteros desde el
    test que los usa, sin tener que ir a mirar un fixture compartido.
    """
    import ezdxf

    from analyzer import parser

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6                    # metros
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()
    for etiqueta, (x0, y0), (x1, y1) in piezas:
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                           dxfattribs={"layer": parser.AREA_LAYER})
        msp.add_mtext(etiqueta, dxfattribs={"layer": parser.AREA_LAYER}).set_location(
            ((x0 + x1) / 2.0, (y0 + y1) / 2.0))
    for texto, x, y in etiquetas_de_vivienda:
        msp.add_mtext(texto, dxfattribs={"layer": parser.AREA_LAYER}).set_location((x, y))
    ruta = destino / nombre
    doc.saveas(str(ruta))
    return str(ruta)


def leer(ruta: str):
    import ezdxf

    from analyzer import parser

    return parser.leer_plano(ezdxf.readfile(ruta))


#: Dos viviendas idénticas de 45 m² útiles, separadas 20 m — muy por encima de
#: lo que exige la holgura de reparto, para que el caso base no dependa de ella.
DOS_VIVIENDAS = (
    ("Salón/cocina", (0.0, 0.0), (5.0, 4.0)),      # 20
    ("Dormitorio 1", (0.0, 4.0), (4.0, 7.0)),      # 12
    ("Baño", (5.0, 0.0), (7.0, 2.0)),              # 4
    ("Terraza", (5.0, 3.0), (8.0, 6.0)),           # 9  (exterior)
    ("Salón/cocina", (30.0, 0.0), (35.0, 4.0)),
    ("Dormitorio 1", (30.0, 4.0), (34.0, 7.0)),
    ("Baño", (35.0, 0.0), (37.0, 2.0)),
    ("Terraza", (35.0, 3.0), (38.0, 6.0)),
)
ETIQUETAS_DOS = (("VT1/1", 4.0, -3.0), ("VT2/1", 34.0, -3.0))

#: Una vivienda con un solape de 2 m² exactos entre el salón y el dormitorio.
#: Cuatro piezas y no dos: con menos, el lector del DXF no reúne evidencia
#: suficiente para decidir cuál es la capa de recintos y se niega a seguir —que
#: es lo correcto, pero convierte el caso en otra prueba distinta.
SOLAPE = (
    ("Salón/cocina", (0.0, 0.0), (5.0, 4.0)),      # 20
    ("Dormitorio 1", (4.0, 0.0), (7.0, 2.0)),      # 6, pisa 2 del salón
    ("Baño", (10.0, 0.0), (12.0, 2.0)),            # 4
    ("Terraza", (10.0, 3.0), (13.0, 6.0)),         # 9
)
#: Con su rótulo de vivienda: sin él, el baño y la terraza quedan a más de dos
#: metros del resto y la agrupación por proximidad los separaría en una segunda
#: vivienda — correcto para esa heurística, pero convierte el caso en otro.
SOLAPE_ETIQUETAS = (("VT1/1", 6.0, -3.0),)


# --- El reparto en viviendas ------------------------------------------------

def test_una_planta_con_dos_viviendas_se_separa_en_dos(tmp_path):
    """Lo que el producto no sabía hacer hasta hoy: no rendirse ante la segunda."""
    medicion = medir_planta(leer(construir(tmp_path, DOS_VIVIENDAS, ETIQUETAS_DOS)))
    assert [v.nombre for v in medicion.viviendas] == ["VT1/1", "VT2/1"]
    assert medicion.agrupacion == POR_ROTULOS


def test_ninguna_pieza_dibujada_se_pierde(tmp_path):
    """El modo de fallo más caro: una habitación que no está en ninguna tabla."""
    medicion = medir_planta(leer(construir(tmp_path, DOS_VIVIENDAS, ETIQUETAS_DOS)))
    assert medicion.piezas == len(DOS_VIVIENDAS)
    rotulos = sorted(p.nombre for v in medicion.viviendas for p in v.piezas)
    assert rotulos == sorted(etiqueta for etiqueta, _a, _b in DOS_VIVIENDAS)


def test_sin_rotulos_de_vivienda_se_agrupa_por_proximidad_y_se_dice(tmp_path):
    """Agrupar por geometría es legítimo; hacerlo sin avisar, no."""
    medicion = medir_planta(leer(construir(tmp_path, DOS_VIVIENDAS)))
    assert medicion.agrupacion == POR_PROXIMIDAD
    assert len(medicion.viviendas) == 2


def test_un_rotulo_de_vivienda_sin_piezas_se_declara(tmp_path):
    """Puede ser una leyenda o una vivienda sin medir, y ArchMuse no lo decide."""
    etiquetas = ETIQUETAS_DOS + (("VT9/1", 500.0, 500.0),)
    medicion = medir_planta(leer(construir(tmp_path, DOS_VIVIENDAS, etiquetas)))
    assert medicion.rotulos_sin_piezas == ("VT9/1",)


# --- Los totales, y cuándo NO hay ------------------------------------------

def test_el_total_es_interior_mas_exterior_y_suma_todas_las_piezas(tmp_path):
    medicion = medir_planta(leer(construir(tmp_path, DOS_VIVIENDAS, ETIQUETAS_DOS)))
    vivienda = medicion.viviendas[0]
    assert vivienda.interior_m2 == 36.0            # 20 + 12 + 4
    assert vivienda.exterior_m2 == 9.0             # la terraza
    assert vivienda.total_util_m2 == 45.0
    assert vivienda.total_util_m2 == vivienda.suma_de_piezas_m2
    assert vivienda.impedimentos == ()


def test_dos_piezas_solapadas_dejan_la_vivienda_sin_total(tmp_path):
    """La regla dura: un total que puede estar mal es peor que no darlo."""
    vivienda = medir_planta(leer(construir(tmp_path, SOLAPE, SOLAPE_ETIQUETAS))).viviendas[0]
    assert vivienda.total_util_m2 is None
    assert len(vivienda.solapes) == 1
    assert vivienda.solapes[0].area_m2 == 2.0
    assert vivienda.diferencia_con_la_union_m2 == 2.0
    assert "dos veces" in vivienda.impedimentos[0]


def test_compartir_un_borde_no_es_solaparse(tmp_path):
    """Dos habitaciones contiguas son lo normal, no un hallazgo.

    Si esto fallara, cualquier plano bien dibujado saldría lleno de avisos
    falsos y sin un solo total — que es la forma más rápida de que nadie vuelva
    a abrir el documento.
    """
    piezas = (
        ("Salón/cocina", (0.0, 0.0), (5.0, 4.0)),   # 20
        ("Dormitorio 1", (5.0, 0.0), (8.0, 4.0)),   # 12, pegada y sin pisar
        ("Baño", (8.0, 0.0), (10.0, 2.0)),          # 4, pegada al dormitorio
        ("Terraza", (8.0, 2.0), (11.0, 5.0)),       # 9, pegada al baño
    )
    vivienda = medir_planta(leer(construir(tmp_path, piezas))).viviendas[0]
    assert vivienda.solapes == ()
    assert vivienda.total_util_m2 == 45.0


def test_una_pieza_de_rotulo_desconocido_no_se_asigna_a_ningun_ambito(tmp_path):
    """No se fuerza a interior «porque casi todas lo son»: se enseña y se pregunta."""
    piezas = (
        ("Salón/cocina", (0.0, 0.0), (5.0, 4.0)),
        ("Dormitorio 1", (0.0, 5.0), (4.0, 8.0)),
        ("Baño", (6.0, 0.0), (8.0, 2.0)),
        ("Trastero", (6.0, 5.0), (8.0, 7.0)),       # 4 m², y nadie sabe de qué ámbito
    )
    vivienda = medir_planta(leer(construir(tmp_path, piezas))).viviendas[0]
    sueltas = vivienda.sin_clasificar
    assert [p.nombre for p in sueltas] == ["Trastero"]
    assert sueltas[0].ambito == AMBITO_SIN_CLASIFICAR
    assert vivienda.total_util_m2 is None
    assert "4,00 m²" in vivienda.impedimentos[0]    # su superficie va en el motivo
    # Y la pieza sigue medida y visible: bloquear el total no es esconderla.
    assert sueltas[0].area_m2 == 4.0


def test_un_reparto_apretado_entre_dos_viviendas_se_declara(tmp_path):
    """Dos viviendas medianeras: el reparto por cercanía deja de ser afirmable.

    La pieza se sigue asignando —el reparto lo hace `evaluator` y no cambia—,
    pero la vivienda se queda sin total y el motivo dice a qué distancia está de
    cada etiqueta. Es la diferencia entre medir y adivinar.
    """
    piezas = (
        ("Salón/cocina", (0.0, 1.0), (5.0, 5.0)),
        ("Dormitorio 1", (0.0, 6.0), (4.0, 9.0)),
        ("Baño", (0.0, 10.0), (2.0, 12.0)),
        # Justo en medio de las dos viviendas: se asigna a la primera por un
        # metro de diferencia, y ese metro no es una medición.
        ("Terraza", (28.0, 0.0), (31.0, 3.0)),
    )
    etiquetas = (("VT1/1", 0.0, 0.0), ("VT2/1", 60.0, 0.0))
    medicion = medir_planta(leer(construir(tmp_path, piezas, etiquetas)))
    dudosos = [d for v in medicion.viviendas for d in v.repartos_dudosos]
    assert [d.pieza for d in dudosos] == ["Terraza"]
    assert all(v.total_util_m2 is None for v in medicion.viviendas
               if v.repartos_dudosos)


def test_un_reparto_holgado_no_se_declara(tmp_path):
    """El reverso: en un plano normal esto no puede producir un solo aviso."""
    medicion = medir_planta(leer(construir(tmp_path, DOS_VIVIENDAS, ETIQUETAS_DOS)))
    assert all(v.repartos_dudosos == () for v in medicion.viviendas)
    assert medicion.viviendas_con_total == 2


# --- La clasificación por rótulo -------------------------------------------

@pytest.mark.parametrize("rotulo,ambito", [
    ("Salón/cocina", AMBITO_INTERIOR),
    ("Dormitorio 4", AMBITO_INTERIOR),             # más allá del 3 del cuadro
    ("Baño", AMBITO_INTERIOR),
    ("Aseo", AMBITO_INTERIOR),
    ("Pasillo", AMBITO_INTERIOR),
    ("Vestíbulo", AMBITO_INTERIOR),
    ("Terraza", AMBITO_EXTERIOR),
    ("Tendedero", AMBITO_EXTERIOR),
    ("Trastero", AMBITO_SIN_CLASIFICAR),
    ("", AMBITO_SIN_CLASIFICAR),
])
def test_el_ambito_sale_del_rotulo(rotulo, ambito):
    assert _medicion.clasificar(rotulo)[1] == ambito


def test_una_terraza_es_exterior_aunque_su_rotulo_nombre_la_cocina():
    """El orden del catálogo, comprobado: el patrón de salón+cocina es ancho.

    Sin esto, «Terraza cocina» entraría como superficie interior y el total de
    esa vivienda saldría mal sin que nada avisara.
    """
    assert _medicion.clasificar("Terraza cocina")[1] == AMBITO_EXTERIOR


# --- Las capacidades --------------------------------------------------------

def test_la_capacidad_de_medir_no_escribe_nada(tmp_path):
    ruta = construir(tmp_path, DOS_VIVIENDAS, ETIQUETAS_DOS)
    antes = set(os.listdir(tmp_path))
    resultado = registro(recargar=True).buscar("plano.medicion_de_la_planta").invocar(
        {"ruta": ruta}, None)
    assert resultado["ok"] is True
    assert len(resultado["viviendas"]) == 2
    assert set(os.listdir(tmp_path)) == antes


def test_el_pdf_sin_autorizacion_no_se_escribe(tmp_path):
    """El portero de efectos, sobre la capacidad nueva."""
    ruta = construir(tmp_path, DOS_VIVIENDAS, ETIQUETAS_DOS)
    destino = str(tmp_path / "medicion.pdf")
    capacidad = registro(recargar=True).buscar("plano.medicion_en_pdf")
    with pytest.raises(_efectos.EfectoNoAutorizado):
        capacidad.invocar({"ruta": ruta, "ruta_destino": destino}, None)
    assert not os.path.exists(destino)


def test_el_destino_no_puede_ser_el_propio_plano(tmp_path):
    ruta = construir(tmp_path, DOS_VIVIENDAS, ETIQUETAS_DOS)
    capacidad = registro(recargar=True).buscar("plano.medicion_en_pdf")
    permisos = _efectos.Autorizaciones.de(capacidad.efectos, por="test")
    resultado = capacidad.invocar({"ruta": ruta, "ruta_destino": ruta}, permisos)
    assert resultado["ok"] is False
    assert resultado["error"] == "destino_es_el_origen"


def test_el_destino_no_sobrescribe_un_fichero_que_ya_existe(tmp_path):
    ruta = construir(tmp_path, DOS_VIVIENDAS, ETIQUETAS_DOS)
    destino = tmp_path / "medicion.pdf"
    destino.write_bytes(b"un entregable anterior")
    capacidad = registro(recargar=True).buscar("plano.medicion_en_pdf")
    permisos = _efectos.Autorizaciones.de(capacidad.efectos, por="test")
    resultado = capacidad.invocar({"ruta": ruta, "ruta_destino": str(destino)}, permisos)
    assert resultado["ok"] is False
    assert resultado["error"] == "destino_ya_existe"
    assert destino.read_bytes() == b"un entregable anterior"


def test_el_pdf_se_escribe_y_el_original_conserva_su_sello(tmp_path):
    import hashlib

    ruta = construir(tmp_path, DOS_VIVIENDAS, ETIQUETAS_DOS)
    antes = hashlib.sha256(Path(ruta).read_bytes()).hexdigest()
    destino = str(tmp_path / "medicion.pdf")
    capacidad = registro(recargar=True).buscar("plano.medicion_en_pdf")
    permisos = _efectos.Autorizaciones.de(capacidad.efectos, por="test")
    resultado = capacidad.invocar({"ruta": ruta, "ruta_destino": destino}, permisos)

    assert resultado["ok"] is True
    assert resultado["origen_intacto"] is True
    assert resultado["sello_origen_sha256"] == antes
    assert hashlib.sha256(Path(ruta).read_bytes()).hexdigest() == antes
    assert Path(destino).read_bytes()[:4] == b"%PDF"


# --- La Skill ---------------------------------------------------------------

def _ejecutar_skill(ruta: str, destino: str):
    capacidades = registro(recargar=True)
    skills = registro_de_skills(recargar=True)
    memoria = MemoriaDeProyecto("p-medicion", SustratoEnMemoria())
    plan = Plan(objetivo="Mide la planta", proyecto_id=memoria.proyecto_id,
                pasos=(Paso(id="medir", skill=SKILL, argumentos={
                    "ruta_dxf": ruta, "ruta_informe": destino}),))
    permisos = _efectos.Autorizaciones.de(
        skills.buscar(SKILL).efectos, por="test", alcance="ejecucion")
    ejecutor = Ejecutor(capacidades=capacidades, skills=skills,
                        bitacora=BitacoraEnMemoria())
    return ejecutor.ejecutar(plan, memoria, autorizaciones=permisos,
                             ejecucion_id="test-medicion")


def test_la_skill_entrega_el_documento_y_pasa_sus_comprobaciones(tmp_path):
    ruta = construir(tmp_path, DOS_VIVIENDAS, ETIQUETAS_DOS)
    destino = str(tmp_path / "medicion.pdf")
    resultado = _ejecutar_skill(ruta, destino)

    assert resultado.completa is True
    paso = resultado.pasos[0]
    dictamen = paso.salida["dictamen"]
    assert dictamen["verificado"] is True
    fallidas = [c["nombre"] for c in dictamen["comprobaciones"] if not c["ok"]]
    assert fallidas == []
    entregables = paso.salida["resultado"]["entregables"]
    assert [e["ruta"] for e in entregables] == [destino]
    assert entregables[0]["borrador"] is True


def test_la_skill_declara_lo_que_no_ha_podido_totalizar(tmp_path):
    """Una vivienda sin total no desaparece del acta: sale con su motivo."""
    ruta = construir(tmp_path, SOLAPE, SOLAPE_ETIQUETAS)
    resultado = _ejecutar_skill(ruta, str(tmp_path / "medicion.pdf"))
    no_hecho = resultado.pasos[0].salida["resultado"]["no_hecho"]
    assert any("no lleva superficie útil total" in n for n in no_hecho)


# --- Que los guardianes muerdan --------------------------------------------
#
# Una verificación que nadie ha visto fallar es una verificación que puede estar
# rota desde hace meses. Estas dos la ejercen con un resultado fabricado a
# propósito: si dejan de fallar, la garantía se ha ido sin que nadie lo note.

def _skill():
    return registro_de_skills(recargar=True).buscar(SKILL)


def _resultado_con(viviendas):
    from agente.afirmacion import calculo
    from agente.skill import ResultadoDeSkill

    return ResultadoDeSkill(
        afirmaciones=(calculo("medicion.viviendas", viviendas, fuente="test"),))


def _comprobar(nombre: str, resultado):
    for verificacion in _skill().verificaciones:
        if verificacion.nombre == nombre:
            return verificacion.funcion(resultado)
    raise AssertionError("no existe la verificación «%s»" % nombre)


def test_un_total_publicado_con_impedimento_hace_fallar_la_verificacion():
    salida = _comprobar("ningun_total_publicado_con_impedimento", _resultado_con([
        {"vivienda": "VT1/1", "total_util_m2": 45.0, "piezas": [],
         "impedimentos": ["hay 2,00 m² dibujados dos veces"]},
    ]))
    assert salida is not True
    assert "peor que la ausencia de total" in str(salida)


def test_un_total_que_no_suma_todas_sus_piezas_hace_fallar_la_verificacion():
    salida = _comprobar("todo_total_suma_todas_sus_piezas", _resultado_con([
        {"vivienda": "VT1/1", "total_util_m2": 45.0, "impedimentos": [],
         "piezas": [{"area_m2": 20.0}, {"area_m2": 12.0}]},
    ]))
    assert salida is not True
    assert "no está en el total" in str(salida)


def test_calificar_la_gravedad_hace_fallar_la_verificacion():
    """La frontera con `D-7`, comprobada y no prometida.

    Mientras esto pase, la Skill mide. El día que alguien la haga fallar,
    ArchMuse ha empezado a opinar sobre el trabajo de un colegiado, y eso es una
    decisión de producto y no un ajuste de formato.
    """
    salida = _comprobar("la_medicion_no_califica", _resultado_con([
        {"vivienda": "VT1/1", "total_util_m2": None, "piezas": [],
         "impedimentos": ["hay un solape grave entre dos piezas"]},
    ]))
    assert salida is not True
    assert "el criterio lo pone el arquitecto" in str(salida)


def test_una_pieza_sin_capa_hace_fallar_la_verificacion():
    salida = _comprobar("toda_pieza_dice_donde_esta", _resultado_con([
        {"vivienda": "VT1/1", "total_util_m2": None, "impedimentos": [],
         "piezas": [{"rotulo": "Salón", "area_m2": 20.0, "capa": ""}]},
    ]))
    assert salida is not True
    assert "no se puede comprobar" in str(salida)


# --- Contra los planos reales del cliente -----------------------------------

@pytest.mark.skipif(not DXF_PLANTA,
                    reason="define ARCHMUSE_DXF_PLANTA con una planta de varias viviendas")
def test_la_planta_real_de_tres_viviendas_se_mide_entera():
    """El caso que motivó todo esto: tres viviendas y ningún cuadro dibujado.

    Las cifras van escritas a propósito. Un test que sólo comprobara «hay tres
    viviendas» seguiría pasando el día que el reparto asignara una habitación a
    la vivienda de al lado.
    """
    medicion = medir_planta(leer(DXF_PLANTA))
    assert medicion.agrupacion == POR_ROTULOS
    totales = {v.nombre: v.total_util_m2 for v in medicion.viviendas}
    assert totales == {"VT1/3": 66.32, "VT2/2": 58.44, "VT3/3": 66.56}
    assert medicion.piezas == 22
    assert all(v.solapes == () and v.repartos_dudosos == ()
               for v in medicion.viviendas)


@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S para el plano real")
def test_el_plano_real_con_solapes_no_lleva_total():
    """El otro plano real: sus 7,08 m² duplicados impiden totalizar.

    Los mismos 7,08 m² que encuentra la revisión de coherencia por su cuenta
    (4,00 entre los dos tendederos y 3,08 entre terraza y tendedero). Que dos
    caminos independientes den la misma cifra es lo que hace creíble a los dos.
    """
    vivienda = medir_planta(leer(DXF_V2S)).viviendas[0]
    assert vivienda.total_util_m2 is None
    assert vivienda.diferencia_con_la_union_m2 == 7.08
    assert sorted(s.area_m2 for s in vivienda.solapes) == [3.08, 4.0]
    # Las nueve piezas siguen medidas: bloquear el total no borra el trabajo.
    assert len(vivienda.piezas) == 9
    assert vivienda.interior_m2 == 58.78
