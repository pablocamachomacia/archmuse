# -*- coding: utf-8 -*-
"""El cuadro propio de ArchMuse: se calcula siempre, y el suyo no se toca.

PRD `docs/prd/2026-09-12-el-cuadro-propio-de-archmuse.md`.

**Qué vigila este fichero, en una frase:** que ArchMuse mida el plano y entregue
su cuadro **independientemente de lo que el arquitecto tenga escrito**, y que lo
que él tenga escrito no entre nunca en el cuadro de ArchMuse.

Hasta el 2026-09-12 esas dos cosas eran la misma regla, y por eso el producto se
quedaba mudo: «nunca sobrescribir» estaba implementado como «no calcular». Sobre
`plantasimple.dxf`, de las 396 celdas de sus 22 cuadros, ArchMuse afirmaba 74 —y
73 eran `0,00 m²`—. Calculando sobre la plantilla afirma 232, de las cuales
**158 son cifras reales**.

### Por qué el cuadro de estos tests se construye con `cuadro_desde_celdas`

Por dos razones, y la segunda es la importante:

1. **Ningún fixture del repositorio tiene un `ACAD_TABLE`** —medido el
   2026-09-12: de los DXF versionados, cero—. Todo lo que se probara leyendo un
   DXF se saltaría en CI y sólo correría en esta máquina.
2. **Es la vía que usa el comando de verdad.** Desde AutoCAD el cliente manda
   las celdas y el servidor construye el cuadro con `cuadro_desde_celdas`, no
   leyendo el DXF. Probar sólo la lectura del DXF dejaría sin vigilancia el
   camino por el que entra el trabajo real — el hueco exacto donde ya se han
   colado tres divergencias `C-9`.

Las celdas de `_CUADRO_DEL_ESTUDIO` son las de `v1plantas.dxf`, copiadas de la
estructura real: dos pares etiqueta/valor por fila, la errata del arquitecto
incluida.
"""
from __future__ import annotations

import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import cuadro_superficies as cs  # noqa: E402
from analyzer import evaluator, medicion, parser  # noqa: E402
from analyzer import reparto_cuadro as rc  # noqa: E402

FIXTURES = os.path.join(RAIZ, "tests", "fixtures", "reales")
MATERIAL = os.path.join(os.path.dirname(RAIZ), "_material")

PLANTA = os.path.join(FIXTURES, "planta_tres_viviendas.dxf")
PLANTASIMPLE = os.path.join(MATERIAL, "plantasimple.dxf")
V5 = os.path.join(MATERIAL, "V5.dxf")

#: El cuadro del estudio tal como llega desde AutoCAD: `(fila, columna, texto)`.
#: La columna 0 y la 2 llevan etiquetas; la 1 y la 3, valores. Las cifras que
#: aparecen aquí son **las que el arquitecto escribió**, con su formato (punto
#: decimal, `m²` pegado), que es justo lo que no puede salir en el cuadro de
#: ArchMuse.
_CUADRO_DEL_ESTUDIO = [
    (0, 0, "EXPACIOS INTERORES"), (0, 1, "SUPERFICIES UTILES"),
    (0, 2, "ESPACIOS EXTERIORES"), (0, 3, "SUPERFICIES UTILES"),
    (1, 0, "salón + cocina"), (1, 1, "21.90m²"),
    (1, 2, "tendedero"), (1, 3, ""),
    (2, 0, "dormitorio 1"), (2, 1, ""),
    (2, 2, "terraza 1"), (2, 3, ""),
    (3, 0, "dormitorio 2"), (3, 1, "8.48m²"),
    (4, 0, "baño"), (4, 1, ""),
    (5, 0, "aseo"), (5, 1, ""),
    (6, 0, "TOTAL SUP. INTERIOR (m2)"), (6, 1, ""),
    (6, 2, "TOTAL SUP. EXTERIOR (m2)"), (6, 3, ""),
    (7, 0, "TOTAL S. UTIL(m2)"), (7, 1, ""),
    (8, 0, "S. CONSTRUIDA C."), (8, 1, "72.70m²"),
    (9, 0, "VIVIENDA TIPO"), (9, 1, "VT1 /3"),
    (9, 2, "NUMERO UDS:"), (9, 3, "6"),
]


def _cuadro_del_estudio() -> cs.CuadroSuperficies:
    cuadro = cs.cuadro_desde_celdas(_CUADRO_DEL_ESTUDIO)
    assert cuadro is not None, "el cuadro de prueba ha dejado de reconocerse"
    return cuadro


def _medido(ruta, capa=None, alinear=False):
    doc = parser.load_document(ruta)
    plano = parser.leer_plano(doc, layer=capa, alinear_rotulos=alinear)
    unidades = evaluator.evaluate_advanced(plano.rooms, plano.unit_labels).units
    viviendas = {v.nombre: v for v in medicion.medir_planta(plano).viviendas}
    return doc, plano, unidades, viviendas


def _reparto(unidad, cuadro, viviendas):
    vivienda = viviendas.get(unidad.name)
    impedimentos = tuple(vivienda.impedimentos) if vivienda is not None else ()
    return rc.calcular_reparto(unidad, cuadro, unidad.rooms,
                               medicion_limpia=not impedimentos,
                               impedimentos=impedimentos)


def _skip_si_falta(ruta):
    if not os.path.isfile(ruta):
        pytest.skip("%s no está en esta máquina" % os.path.basename(ruta))
    return ruta


@pytest.fixture(scope="module")
def plano_medido():
    return _medido(PLANTA)


# --- 1. El núcleo: calcular siempre ----------------------------------------

def test_la_plantilla_vacia_todas_las_celdas_y_conserva_las_filas():
    """`como_plantilla` vacía el valor, no la forma."""
    cuadro = _cuadro_del_estudio()
    plantilla = cuadro.como_plantilla()

    assert any(c.texto_actual for c in cuadro.celdas), (
        "el cuadro de prueba ya no trae celdas rellenas: dejaría de probar nada")
    assert not any(c.texto_actual for c in plantilla.celdas)
    assert [c.campo for c in plantilla.celdas] == [c.campo for c in cuadro.celdas]
    assert plantilla.filas == tuple(cuadro.filas)


def test_sobre_la_plantilla_se_calcula_lo_que_el_arquitecto_ya_habia_escrito(
        plano_medido):
    """**El cambio entero, en un test.**

    La misma celda, el mismo plano y la misma medición: con su cuadro tal cual,
    ArchMuse no la calcula; sobre la plantilla, sí.
    """
    _doc, _plano, unidades, viviendas = plano_medido
    cuadro = _cuadro_del_estudio()
    unidad = unidades[0]

    con_su_cuadro = _reparto(unidad, cuadro, viviendas)
    con_plantilla = _reparto(unidad, cuadro.como_plantilla(), viviendas)

    preexistentes = {n.campo for n in con_su_cuadro.no_escritas
                     if "Ya había un valor" in (n.motivo or "")}
    assert preexistentes, "el cuadro de prueba no tiene celdas preexistentes"

    calculadas = {c.campo for c in con_plantilla.celdas}
    assert preexistentes & calculadas, (
        "ninguna de las celdas que él tenía escritas se calcula ahora")
    assert len(con_plantilla.celdas) > len(con_su_cuadro.celdas)


# --- `C-11` · ninguna cifra que no haya medido él -------------------------
#
# **Criterio firmado por Pablo el 2026-09-12**, ver
# `docs/design/2026-09-08-criterios-firmados-de-medicion.md`.
#
# El fallo que lo motiva es el peor que puede tener esta capacidad, y no porque
# falte un dato: ArchMuse **firmaría un número que no ha medido**. Y como el
# número vendría de él, coincidiría con su documentación y no chirriaría nada.
#
# **Los dos tests de abajo NO comparan textos**, y eso es deliberado. El fallo
# real se vio porque los formatos difieren —él escribe `21.90m²`, ArchMuse
# `21,90 m²`—, y eso fue **suerte**: si él usara coma, la cifra copiada habría
# pasado por buena. Comparar cadenas además daría un falso positivo el día que
# ArchMuse midiera exactamente lo mismo que él escribió, que es el caso bueno.
#
# Se comprueba por **procedencia y de forma cerrada**: todo texto del cuadro
# dibujado tiene que ser una etiqueta, un valor calculado, una marca de nota o
# el título. Cualquier quinta cosa es un fallo, venga de donde venga.


def _origenes_legitimos(cuadro, reparto, dibujable):
    """Las cuatro únicas procedencias que puede tener un texto del cuadro."""
    return {
        "etiqueta": {f.etiqueta.strip() for f in cuadro.filas},
        "valor medido": {c.texto.strip() for c in reparto.celdas},
        "marca de nota": {n.marca.strip() for n in dibujable.notas},
        "titulo": {dibujable.celdas[0].texto.strip()},
    }


def test_ningun_texto_del_cuadro_tiene_origen_desconocido(plano_medido):
    """`C-11`, en su forma general: vocabulario cerrado.

    No mira de qué se parece cada texto: mira **de dónde sale**. Si mañana
    alguien lee las celdas de su tabla de otra manera y por ahí se cuela algo
    suyo, este test falla aunque el formato coincida al milímetro.
    """
    _doc, _plano, unidades, viviendas = plano_medido
    cuadro = _cuadro_del_estudio()
    reparto = _reparto(unidades[0], cuadro.como_plantilla(), viviendas)
    dibujable = rc.cuadro_dibujable(reparto, cuadro)

    legitimos = _origenes_legitimos(cuadro, reparto, dibujable)
    todos = set().union(*legitimos.values())

    huerfanos = [c for c in dibujable.celdas if c.texto.strip() not in todos]
    assert not huerfanos, (
        "hay texto en el cuadro de ArchMuse sin procedencia conocida "
        "(no es etiqueta, ni valor medido, ni marca, ni título): %s"
        % [(c.fila, c.columna, c.texto) for c in huerfanos])


def test_toda_cifra_del_cuadro_sale_de_la_medicion(plano_medido):
    """`C-11` sobre las cifras, que es donde duele.

    Una celda que contenga una superficie tiene que ser **exactamente** una de
    las que ha producido el cálculo. Que el texto se parezca a una superficie no
    basta, y que se parezca a la suya no vale.
    """
    _doc, _plano, unidades, viviendas = plano_medido
    cuadro = _cuadro_del_estudio()
    reparto = _reparto(unidades[0], cuadro.como_plantilla(), viviendas)
    dibujable = rc.cuadro_dibujable(reparto, cuadro)

    medidas = {c.texto.strip() for c in reparto.celdas}
    etiquetas = {f.etiqueta.strip() for f in cuadro.filas}

    intrusas = []
    for celda in dibujable.celdas:
        texto = celda.texto.strip()
        if texto in medidas or texto in etiquetas:
            continue
        if cs.superficie_en_m2(texto) is not None:
            intrusas.append((celda.fila, celda.columna, texto))
    assert not intrusas, (
        "hay cifras en el cuadro de ArchMuse que no salen de su medición: %s"
        % intrusas)


def test_el_guardian_de_C11_caza_una_cifra_suya_colada(plano_medido):
    """**El guardián, probado contra el fallo de verdad.**

    Un test que nunca ha estado rojo no prueba que vigile algo. Aquí se
    reintroduce el fallo del 2026-09-12 —una celda de valor suya colada como si
    fuera una fila— y se comprueba que salta.

    Y se cuela **con el formato de ArchMuse, con coma**, que es el caso que la
    comparación de textos no habría cazado.
    """
    import dataclasses

    _doc, _plano, unidades, viviendas = plano_medido
    cuadro = _cuadro_del_estudio()
    reparto = _reparto(unidades[0], cuadro.como_plantilla(), viviendas)

    colada = cs.FilaDeCuadro(fila=3, etiqueta="99,99 m²", campo=None,
                             columna_etiqueta=3, columna_valor=3)
    envenenado = dataclasses.replace(
        cuadro, filas=tuple(cuadro.filas) + (colada,))
    dibujable = rc.cuadro_dibujable(reparto, envenenado)

    medidas = {c.texto.strip() for c in reparto.celdas}
    assert "99,99 m²" not in medidas, "el fixture ha coincidido con una medición"
    intrusas = [c.texto for c in dibujable.celdas
                if cs.superficie_en_m2(c.texto.strip()) is not None
                and c.texto.strip() not in medidas]
    assert intrusas == ["99,99 m²"], (
        "el guardián de `C-11` no caza una cifra ajena colada como etiqueta")


def test_las_cifras_del_arquitecto_no_viajan_como_filas():
    """Una celda de valor suya no es una fila de su cuadro."""
    cuadro = _cuadro_del_estudio()
    valores_suyos = {(c.texto_actual or "").strip()
                     for c in cuadro.celdas if c.texto_actual}
    etiquetas = {f.etiqueta.strip() for f in cuadro.filas}
    assert valores_suyos, "el cuadro de prueba no trae valores"
    assert not (valores_suyos & etiquetas), sorted(valores_suyos & etiquetas)


# --- 2. Se copian sus filas, literales -------------------------------------

def test_las_filas_se_copian_con_su_redaccion_y_su_errata():
    """`EXPACIOS INTERORES` se copia con su errata.

    Corregirla sería editarle el documento por la puerta de atrás, y romper lo
    único que hace útil poner los dos cuadros juntos: que la fila N de uno esté
    a la altura de la fila N del otro.
    """
    etiquetas = [f.etiqueta for f in _cuadro_del_estudio().filas]
    assert "EXPACIOS INTERORES" in etiquetas
    assert "TOTAL S. UTIL(m2)" in etiquetas


def test_los_encabezados_de_columna_sobreviven_al_filtro_de_valores():
    """«SUPERFICIES UTILES» vive en una columna de valor y **no es un valor**.

    El filtro que quita sus cifras es por posición —la celda de valor de un
    campo reconocido— y no por aspecto, justamente para que un encabezado que
    caiga en esa columna no desaparezca.
    """
    etiquetas = [f.etiqueta for f in _cuadro_del_estudio().filas]
    assert etiquetas.count("SUPERFICIES UTILES") == 2


def test_la_rejilla_propia_respeta_las_posiciones_de_su_cuadro(plano_medido):
    """Dos pares etiqueta/valor por fila, como el suyo: es lo que permite
    leerlos a la misma altura cuando se dibujan uno al lado del otro."""
    _doc, _plano, unidades, viviendas = plano_medido
    cuadro = _cuadro_del_estudio()
    dibujable = rc.cuadro_dibujable(
        _reparto(unidades[0], cuadro.como_plantilla(), viviendas), cuadro)

    assert dibujable.n_columnas == 4
    por_posicion = {(c.fila, c.columna): c.texto for c in dibujable.celdas}
    # La fila 0 de su cuadro es la 1 de la nuestra: la 0 es el título.
    assert por_posicion[(1, 0)] == "EXPACIOS INTERORES"
    assert por_posicion[(1, 2)] == "ESPACIOS EXTERIORES"
    assert "BORRADOR" in por_posicion[(0, 0)]


# --- 3. Los N cuadros -------------------------------------------------------

def test_se_leen_los_25_cuadros_no_uno():
    """El límite que ArchMuse tenía y no declaraba."""
    _skip_si_falta(PLANTASIMPLE)
    doc = parser.load_document(PLANTASIMPLE)
    assert len(cs.detectar_cuadros_superficies(doc)) == 25


def test_el_singular_sigue_devolviendo_el_primero():
    """Los llamantes antiguos no cambian de comportamiento."""
    _skip_si_falta(PLANTASIMPLE)
    doc = parser.load_document(PLANTASIMPLE)
    uno = cs.detectar_cuadro_superficies(doc)
    todos = cs.detectar_cuadros_superficies(doc)
    assert uno is not None and todos
    assert [c.campo for c in uno.celdas] == [c.campo for c in todos[0].celdas]


def test_un_plano_sin_ninguna_tabla_devuelve_lista_vacia_no_error():
    doc = parser.load_document(PLANTA)
    assert cs.detectar_cuadros_superficies(doc) == []


# --- 4. La cifra del criterio de aceptación ---------------------------------

def test_la_cifra_del_PRD_sobre_plantasimple():
    """§8 del PRD: 232 celdas con valor, 158 de ellas cifras reales.

    Es el criterio de aceptación del cambio entero y la razón por la que se
    hizo. Si esta cifra baja, alguien ha vuelto a dejar que lo que el arquitecto
    tiene escrito suprima el cálculo.

    **`D-13` (2026-09-13) cambia la primera cifra y no la segunda.** Las 74 celdas
    que eran `0,00 m²` ya no se escriben —ninguna habitación mide cero—; las 158
    cifras reales siguen siendo 158. Escritas: 158. Ceros: ninguno.
    """
    _skip_si_falta(PLANTASIMPLE)
    doc, _plano, unidades, viviendas = _medido(
        PLANTASIMPLE, capa="00 areas", alinear=True)

    escritas = ceros = emparejados = 0
    for cuadro in cs.detectar_cuadros_superficies(doc):
        unidad, _ = rc.elegir_vivienda(unidades, cuadro)
        if unidad is None:
            continue
        emparejados += 1
        reparto = _reparto(unidad, cuadro.como_plantilla(), viviendas)
        escritas += len(reparto.celdas)
        ceros += sum(1 for c in reparto.celdas if c.texto.startswith("0,00"))

    assert emparejados == 22
    assert ceros == 0, ceros
    # **`C-18` (firmado por Pablo, 2026-09-15) la baja a 157, y a propósito.** Medido
    # ese día comparando celda a celda con el código anterior: con los rótulos
    # alineados, `plantasimple.dxf` tiene en VT6/2 un recinto de 11,55 m² con
    # «Terraza» y «Tendedero» dentro. Se llamaba como el primero que llegara; dos
    # nombres distintos ya no se eligen, la pieza queda sin fila y el total interior
    # de VT6/2 (46,23) deja de escribirse. Es la única celda que cambia. No es lo que
    # este test vigila: lo escrito por el arquitecto sigue sin suprimir el cálculo.
    #
    # **Y no puede subir.** Una primera versión de `C-18` dio 159: «aseo 73,07 m²» y
    # «baño 52,11 m²», envolventes que heredaban el nombre de una pieza de dentro.
    # Dos cifras falsas con aspecto de buenas. Si esto vuelve a pasar de 157, mirar
    # qué celdas son nuevas antes de cambiar el número.
    assert escritas == 157, escritas


# --- 5. El plano sin cuadro (CU-A) -----------------------------------------

def test_la_plantilla_canonica_tiene_los_18_campos():
    plantilla = cs.plantilla_canonica()
    assert {c.campo for c in plantilla.celdas} == set(cs.CAMPOS_DEL_CUADRO)
    assert not any(c.texto_actual for c in plantilla.celdas)
    assert plantilla.filas


def test_un_plano_sin_cuadro_entrega_igual():
    """`V5.dxf` es el que mejor mide del lote y el que se rendía."""
    _skip_si_falta(V5)
    doc, _plano, unidades, viviendas = _medido(V5)
    assert cs.detectar_cuadros_superficies(doc) == []

    plantilla = cs.plantilla_canonica()
    dibujable = rc.cuadro_dibujable(
        _reparto(unidades[0], plantilla, viviendas), plantilla,
        origen=rc.ORIGEN_CANONICO)
    assert "BORRADOR" in dibujable.celdas[0].texto
    assert any("21,90" in c.texto for c in dibujable.celdas), (
        "el salón de 21,90 m² no aparece en el cuadro que se dibujaría")


# --- 6. Las notas -----------------------------------------------------------

def test_cada_celda_sin_cifra_remite_a_una_nota_y_ninguna_queda_muda(plano_medido):
    _doc, _plano, unidades, viviendas = plano_medido
    cuadro = _cuadro_del_estudio()
    dibujable = rc.cuadro_dibujable(
        _reparto(unidades[0], cuadro.como_plantilla(), viviendas), cuadro)

    marcas_usadas = {c.texto for c in dibujable.celdas
                     if c.texto.startswith("(") and c.texto.endswith(")")}
    marcas_declaradas = {n.marca for n in dibujable.notas}
    assert marcas_usadas, "ninguna celda remite a una nota: ¿se han quedado mudas?"
    assert marcas_usadas <= marcas_declaradas, (
        "hay celdas que remiten a una nota que no existe: %s"
        % sorted(marcas_usadas - marcas_declaradas))
    assert all(n.texto.strip() for n in dibujable.notas)


def test_dos_celdas_con_el_mismo_motivo_comparten_una_sola_nota(plano_medido):
    """Un pie que repite párrafos palabra por palabra se deja de leer, y estas
    notas son la mitad del valor del entregable."""
    _doc, _plano, unidades, viviendas = plano_medido
    cuadro = _cuadro_del_estudio()
    dibujable = rc.cuadro_dibujable(
        _reparto(unidades[0], cuadro.como_plantilla(), viviendas), cuadro)
    textos = [n.texto for n in dibujable.notas]
    assert len(textos) == len(set(textos))
