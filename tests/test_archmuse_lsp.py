# -*- coding: utf-8 -*-
"""Lo que se puede comprobar de `autocad/archmuse.lsp` sin AutoCAD delante.

**Qué es esto y qué NO es.** No prueba que el script funcione: eso sólo lo dice
AutoCAD, y hasta que haya licencia no se puede. Prueba las tres cosas que sí se
pueden verificar desde aquí y que son, con diferencia, las que más veces rompen
un fichero de AutoLISP el primer día:

1. **Los paréntesis y las comillas cuadran.** Un paréntesis de más y `APPLOAD`
   falla sin cargar nada. Es el fallo nº1 del paso 1 del checklist.
2. **Ninguna función llamada está mal escrita.** Cada símbolo en posición de
   función tiene que ser una primitiva de AutoLISP contrastada contra la
   referencia oficial, o una función definida en el propio fichero. Un
   `vla-SetTex` en vez de `vla-SetText` no se ve leyendo y revienta en la línea
   de comandos con el plano ya abierto.
3. **Las promesas del PRD que son texto siguen ahí:** la marca de borrador de
   `C3`, la URL del endpoint, y que no se llama a `read` sobre la respuesta.

**Por qué la lista de primitivas está escrita a mano.** Es el registro de qué se
verificó y contra qué. Añadir una función al script obliga a añadirla aquí, y
eso obliga a mirar su firma en la documentación antes de usarla — que es
exactamente la disciplina que este fichero existe para imponer.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

LSP = Path(__file__).parent.parent / "autocad" / "archmuse.lsp"

#: Primitivas de AutoLISP y de la extensión ActiveX (`vl`/`vla`/`vlax`) usadas
#: por el script, contrastadas una a una contra la referencia de Autodesk el
#: 2026-09-09. Si añades una llamada al script, añádela aquí después de mirar su
#: firma, no antes.
PRIMITIVAS = {
    # Núcleo
    "defun", "setq", "if", "cond", "while", "foreach", "progn", "quote", "lambda",
    "and", "or", "not", "null", "list", "cons", "car", "cdr", "cadr", "caddr",
    "cadddr", "assoc", "subst", "reverse", "length", "apply", "mapcar", "princ",
    "exit", "wcmatch", "strcase",
    # Cadenas y números
    "strcat", "strlen", "substr", "itoa", "rtos", "distof", "1+", "+", "-", "*",
    "/", "=", "/=", "<", ">", "<=", ">=",
    # Entidades y selección
    "entget", "ssget", "ssname", "sslength", "getvar", "setvar",
    # Interacción
    "getstring", "getpoint",
    # Visual LISP
    "vl-load-com", "vl-string-search", "vl-string-subst", "vl-catch-all-apply",
    "vl-catch-all-error-p", "vl-catch-all-error-message",
    # ActiveX
    "vlax-get-acad-object", "vlax-create-object", "vlax-release-object",
    "vlax-invoke-method", "vlax-get-property", "vlax-3d-point",
    "vla-get-ActiveDocument", "vla-get-ModelSpace", "vla-AddTable",
    "vla-SetText", "vla-SetColumnWidth", "vla-MergeCells",
    "vla-put-RegenerateTableSuppressed",
}


#: Símbolos que aparecen en primera posición de una lista y **no son llamadas**:
#: son la condición de una cláusula de `cond`, que es una expresión, no una
#: función. Se enumeran a mano en vez de intentar reconocer `cond` con una
#: expresión regular — la lista es corta y obliga a mirar cada añadido, que es
#: preferible a un reconocedor que se equivoque en silencio.
CONDICIONES_DE_COND = {"T", "escapado"}


@pytest.fixture(scope="module")
def fuente() -> str:
    return LSP.read_text(encoding="utf-8")


def _sin_comentarios_ni_cadenas(fuente: str) -> str:
    """El código desnudo: fuera los comentarios `;` y el contenido de las
    cadenas. Se hace carácter a carácter porque un `;` dentro de una cadena no
    abre un comentario y una comilla dentro de un comentario no abre una cadena
    — las dos confusiones dan un recuento de paréntesis falso.
    """
    salida = []
    en_cadena = False
    en_comentario = False
    escapado = False
    for ch in fuente:
        if en_comentario:
            if ch == "\n":
                en_comentario = False
                salida.append(ch)
            continue
        if en_cadena:
            if escapado:
                escapado = False
            elif ch == "\\":
                escapado = True
            elif ch == '"':
                en_cadena = False
                salida.append(" ")
            continue
        if ch == ";":
            en_comentario = True
            continue
        if ch == '"':
            en_cadena = True
            continue
        salida.append(ch)
    if en_cadena:
        raise AssertionError("el fichero acaba dentro de una cadena sin cerrar")
    return "".join(salida)


def test_los_parentesis_cuadran(fuente):
    """Un paréntesis descuadrado y `APPLOAD` no carga nada."""
    codigo = _sin_comentarios_ni_cadenas(fuente)
    nivel = 0
    linea = 1
    for ch in codigo:
        if ch == "\n":
            linea += 1
        elif ch == "(":
            nivel += 1
        elif ch == ")":
            nivel -= 1
            assert nivel >= 0, "paréntesis de cierre de más en la línea %d" % linea
    assert nivel == 0, "faltan %d paréntesis de cierre al final del fichero" % nivel


def test_cada_defun_esta_al_nivel_cero(fuente):
    """Un `defun` anidado por accidente dentro de otro no se define hasta que se
    ejecuta el de fuera, y el comando «no existe» sin decir por qué.

    La única excepción legítima es `*error*`, que se define dentro del comando a
    propósito para que sólo esté vigente mientras el comando corre.
    """
    codigo = _sin_comentarios_ni_cadenas(fuente)
    nivel = 0
    for m in re.finditer(r"[()]|\(defun\s+([A-Za-z0-9:*<>=/+*-]+)", codigo):
        if m.group(0) == "(":
            nivel += 1
            continue
        if m.group(0) == ")":
            nivel -= 1
            continue
        nombre = m.group(1)
        if nombre != "*error*":
            assert nivel == 0, "«%s» está definido dentro de otra función" % nombre
        nivel += 1


def test_ninguna_funcion_llamada_esta_mal_escrita(fuente):
    """El guardián de las erratas.

    `vla-SetTex` en vez de `vla-SetText` no se ve leyendo y sólo se manifiesta
    en la línea de comandos con el plano del cliente ya abierto.
    """
    codigo = _sin_comentarios_ni_cadenas(fuente)
    definidas = set(re.findall(r"\(defun\s+([A-Za-z0-9:*<>=/+*-]+)", codigo))
    # `*error*` se define y lo llama AutoCAD, no el script.
    definidas.add("*error*")

    # Fuera las cabeceras de `defun`: su lista de argumentos va entre paréntesis
    # y sus nombres se leerían como llamadas a funciones que no existen.
    sin_cabeceras = re.sub(r"\(defun\s+[^()]+\([^()]*\)", " ", codigo)
    llamadas = set(re.findall(r"\(([A-Za-z][A-Za-z0-9:<>=/+*.-]*)", sin_cabeceras))
    desconocidas = sorted(llamadas - PRIMITIVAS - definidas - CONDICIONES_DE_COND)
    assert desconocidas == [], (
        "estas funciones no están ni en la lista de primitivas verificadas ni "
        "definidas en el fichero: %s" % desconocidas)


def test_todas_las_funciones_propias_se_usan(fuente):
    """Una función muerta en un fichero que nadie puede ejecutar es una función
    que nadie va a descubrir que sobra."""
    codigo = _sin_comentarios_ni_cadenas(fuente)
    definidas = set(re.findall(r"\(defun\s+(am:[A-Za-z0-9:>-]+)", codigo))
    for nombre in sorted(definidas):
        # La definición no cuenta: en `(defun am:x (...))` el paréntesis va
        # antes de `defun`, no del nombre. Así que una sola aparición ya es una
        # llamada de verdad.
        usos = len(re.findall(r"\(%s[\s)]" % re.escape(nombre), codigo))
        assert usos >= 1, "«%s» se define y no se llama nunca" % nombre


# --- Las promesas del PRD que son texto ------------------------------------

def test_la_marca_de_borrador_esta_y_es_la_misma_del_resto_del_producto(fuente):
    """`C3` es innegociable y la tabla se queda dentro del plano que se visa.

    Y tiene que ser la MISMA frase que estampa el resto de entregables: dos
    redacciones distintas de la misma advertencia se leen como dos advertencias
    distintas.
    """
    from analyzer.marca_borrador import LEYENDA

    assert LEYENDA in fuente, (
        "la leyenda de la tabla no coincide con `analyzer/marca_borrador.LEYENDA`")
    assert "vla-MergeCells" in fuente, "la marca tiene que ocupar la fila entera"


def test_no_hay_forma_de_desactivar_la_marca(fuente):
    """Sin parámetro, sin variable de entorno y sin pregunta al usuario."""
    codigo = _sin_comentarios_ni_cadenas(fuente)
    # La leyenda se escribe en la tabla sin pasar por ninguna condición: se
    # comprueba que su `vla-SetText` no está dentro de un `if`/`cond` que la
    # pudiera saltar, mirando que sea la última escritura de la tabla.
    assert "*am:leyenda-borrador*" in codigo
    posicion = codigo.rindex("*am:leyenda-borrador*")
    resto = codigo[posicion:]
    assert "if" not in resto.split("(vla-put-RegenerateTableSuppressed")[0], (
        "la marca se escribe bajo una condición: tiene que ser incondicional")


def test_apunta_al_endpoint_de_geometria_y_pide_la_sexpresion(fuente):
    assert "/api/medicion-geometria" in fuente
    assert "formato=lisp" in fuente


def test_no_se_usa_read_sobre_la_respuesta(fuente):
    """`read` tiene un tope de ~2.300 caracteres y la respuesta de una planta de
    tres viviendas ocupa 6.564. Usarlo funcionaría con un plano de juguete y
    fallaría con el primero de verdad, que es la peor forma de fallar."""
    codigo = _sin_comentarios_ni_cadenas(fuente)
    assert not re.search(r"\(read[\s)]", codigo), (
        "el script llama a `read`: no cabe la respuesta de un plano real")


def test_no_reimplementa_el_criterio_de_rotulo(fuente):
    """`D-7`: un criterio profesional, una sola implementación. El script manda
    los textos en crudo; emparejar rótulo y recinto es del servidor.

    Se vigila por lo que NO puede aparecer: cualquier cálculo de distancia entre
    un texto y un polígono sería ese criterio, reescrito aquí.
    """
    codigo = _sin_comentarios_ni_cadenas(fuente)
    for prohibido in ("distance", "vlax-curve-getclosestpointto", "inters",
                      "vlax-curve-getdistatpoint"):
        assert prohibido not in codigo.lower(), (
            "«%s» sugiere que el script está emparejando rótulos por su cuenta" % prohibido)


def test_declara_por_escrito_que_nunca_se_ha_ejecutado(fuente):
    """Mientras no haya corrido en AutoCAD, el fichero tiene que decirlo en su
    propia cabecera. El día que se ejecute, este test se cambia a mano y ese
    cambio queda en el diff."""
    assert "ESTE FICHERO NUNCA SE HA EJECUTADO" in fuente
