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
    "exit", "wcmatch", "strcase", "repeat",
    # Cadenas y números
    "strcat", "strlen", "substr", "itoa", "rtos", "distof", "1+", "+", "-", "*",
    "/", "=", "/=", "<", ">", "<=", ">=", "max", "fix", "float", "numberp",
    # Entidades y selección
    "entget", "ssget", "ssname", "sslength", "getvar", "setvar",
    # Interacción
    "getstring", "getpoint",
    # La vista previa del segundo clic (3.9.4, 2026-09-16), firmas de la referencia de
    # AutoLISP: (grread [track [allkeys [curtype]]]) → (tipo valor), 2 tecla, 3 clic,
    # 5 cursor con track; (grvecs vlist [trans]) con (color desde hasta …) y matriz
    # 4×4; (redraw [ename [modo]]) repinta y borra los vectores temporales.
    "grread", "grvecs", "redraw",
    # Visual LISP
    "vl-load-com", "vl-string-search", "vl-string-subst", "vl-catch-all-apply",
    "vl-catch-all-error-p", "vl-catch-all-error-message",
    # ActiveX
    "vlax-get-acad-object", "vlax-create-object", "vlax-release-object",
    "vlax-invoke-method", "vlax-get-property", "vlax-3d-point",
    "vla-get-ActiveDocument", "vla-get-ModelSpace", "vla-AddTable",
    "vla-SetText", "vla-SetColumnWidth", "vla-MergeCells",
    "vla-put-RegenerateTableSuppressed",
    # Formato de la tabla. Añadidas el 2026-09-10, al arreglar el ancho de
    # columna que partía el texto letra a letra en la primera ejecución real.
    # Las tres primeras se invocan dentro de `vl-catch-all-apply`: si una
    # versión de AutoCAD no las tuviera, la tabla se dibuja con lo que traiga su
    # estilo en vez de abortar el comando con el plano ya medido.
    "vla-SetTextHeight", "vla-put-HorzCellMargin", "vla-put-VertCellMargin",
    "vla-SetRowHeight", "vla-GetCellTextHeight", "vla-GetCellTextStyle",
    "vla-get-TextStyles", "vla-Item", "vla-get-Height",
    # Rellenar el cuadro DEL ARQUITECTO (2026-09-10). `vla-GetText` lee sus
    # celdas y `vla-SetText` escribe en ellas; el resto es encontrar la tabla y
    # poner la marca de borrador en su propia capa.
    "vla-GetText", "vla-get-Rows", "vla-get-Columns", "vlax-ename->vla-object",
    "vla-get-Layers", "vla-Add", "vla-AddMText", "vla-put-Layer", "vla-Move",
    "vla-get-InsertionPoint", "vlax-safearray->list", "vlax-variant-value",
    "logand", "member", "initget", "getkword", "atoi", "vla-put-Height",
    # Colocar la marca de borrador debajo del cuadro (2026-09-11).
    # `vla-GetBoundingBox` devuelve sus dos esquinas POR REFERENCIA, en
    # dos símbolos citados que luego hay que sacar del variant.
    "vla-GetBoundingBox", "getvar",
    # `type` y `listp` para distinguir una variante de un safearray:
    # `vla-get-InsertionPoint` devuelve lo primero y `vla-GetBoundingBox`
    # escribe lo segundo, y pasar uno por el otro tumbó el comando.
    "type", "listp", "command",
    # Esperar la respuesta de WinHttp a trozos (3.8.1, 2026-09-15): `eq`
    # compara el `:vlax-true` que devuelve `WaitForResponse` (dos símbolos,
    # identidad; `=` es para números y cadenas).
    "eq",
    # Un solo grupo de deshacer para todo lo que se escribe en el plano
    # del arquitecto: un `UNDO` lo quita entero, y se puede retirar en
    # bloque si la marca de borrador no se llega a poner.
    "vla-StartUndoMark", "vla-EndUndoMark",
    # Elegir la capa de recintos de una lista numerada (2026-09-11). `nth`
    # indexa desde 0, de ahi el `(1- n)` sobre el numero que se le ensena a el,
    # que empieza en 1. `vl-sort` se descarto a proposito: elimina los elementos
    # que su comparacion considera iguales, y dos capas con el mismo recuento
    # son justo el caso en el que hay que ensenar las dos.
    "nth",
    # El registro local y ARCHMUSE-INFORME (2026-09-11, T6 del PRD de la beta).
    # Contrastadas una a una contra la referencia de AutoLISP:
    #   `open` / `close` / `write-line` -- E/S de fichero. `open` en modo "a"
    #       anade al final y crea el fichero si no existe; devuelve nil si no
    #       se puede, de ahi la comprobacion antes de escribir.
    #   `getenv` -- variables de entorno de Windows (%LOCALAPPDATA%).
    #   `vl-mkdir` -- crea UN nivel de directorio, no la cadena entera: por eso
    #       se crea primero `ArchMuse` y despues `ArchMuse\registro`.
    #   `vl-file-directory-p` / `vl-file-size` / `vl-directory-files` -- existe,
    #       cuanto ocupa, y que hay dentro (modo 1 = solo ficheros).
    #   `menucmd` con "M=$(edtime,...)" -- la UNICA forma de formatear una fecha
    #       en AutoLISP sin aritmetica sobre el real de CDATE, que pierde los
    #       segundos por redondeo de coma flotante.
    #   `startapp` -- lanza un proceso y NO espera. De ahi que el comando diga
    #       "en unos segundos aparecera" y no "hecho": no puede saberlo.
    "open", "close", "write-line", "getenv", "vl-mkdir", "vl-file-directory-p",
    "vl-file-size", "vl-directory-files", "menucmd", "startapp",
    # (vl-file-delete fichero) → T si lo borra, nil si no existe o no puede (2026-09-16:
    # ARCHMUSE-ACTUALIZAR borra el resultado de una búsqueda anterior antes de buscar).
    "vl-file-delete",
    # El arrastre del segundo clic (3.9.6): (entlast) → la última entidad principal o nil;
    # (ssadd [ename [ss]]) → un conjunto nuevo, o el conjunto con ename añadido;
    # (ssmemb ename ss) → ename si está en el conjunto, nil si no.
    "entlast", "ssadd", "ssmemb",
    # (equal a b [margen]) → T si son iguales, con margen numérico opcional.
    "equal",
    # Beta, T4 (2026-09-13): leer `servidor.json` para saber el puerto.
    #   `read-line` -- (read-line [descriptor]) devuelve la siguiente línea del
    #       fichero abierto con `open ... "r"`, sin el salto, o nil al final. Es
    #       la única lectura de ficheros de texto de AutoLISP.
    "read-line",
    # Plantilla fija y D-14 (2026-09-13): la ventana y la tabla con las medidas
    # del servidor. Contrastadas contra la referencia de AutoLISP y ActiveX:
    #   `getcorner` -- (getcorner punto [mensaje]) pide la esquina opuesta de un
    #       rectángulo que se dibuja desde `punto`; nil si cancela.
    #   `getint` -- (getint [mensaje]) un entero; con `initget 6`, ni 0 ni negativo.
    #   `atof` -- (atof cadena) el real de una cadena, 0.0 si no lo es.
    #   `vla-put-FontFile` -- la fuente (.ttf o .shx) de un TextStyle.
    #   `vla-SetCellTextStyle` / `vla-SetCellTextHeight` -- (tabla fila col valor):
    #       estilo y altura de texto de UNA celda.
    #   `vla-put-StyleName` -- el estilo de texto de un MText.
    "getcorner", "getint", "atof", "vla-put-FontFile", "vla-SetCellTextStyle",
    "vla-SetCellTextHeight", "vla-put-StyleName",
    # Estilo de tabla, capa y color propios (3.3.0, 2026-09-13). Contrastadas
    # contra la referencia de ActiveX, **sin ejecutar en AutoCAD**:
    #   `vla-get-Dictionaries` -- la colección de diccionarios del documento; el
    #       de los estilos de tabla es «ACAD_TABLESTYLE».
    #   `vla-AddObject` -- (diccionario nombre "AcDbTableStyle") crea un estilo.
    #   `vla-SetTextStyle` -- (estilo-de-tabla tipos-de-fila estilo-de-texto).
    #   `vla-put-Color` -- el color de un objeto (256 = PorCapa) o de una capa.
    "vla-get-Dictionaries", "vla-AddObject", "vla-SetTextStyle", "vla-put-Color",
    # Anchos medidos en AutoCAD (3.5.0, 2026-09-13). Contrastada contra la
    # referencia de AutoLISP, **sin ejecutar en AutoCAD**:
    #   `textbox` -- (textbox lista-de-entidad) la caja ((x1 y1 z) (x2 y2 z)) que
    #       ocuparía un TEXT con los códigos dados: 1 texto, 7 estilo, 40 altura.
    "textbox",
    # `C-15`, referencias externas (3.7.0, 2026-09-15). Contrastadas contra la
    # referencia de AutoLISP **y ejecutadas en AutoCAD Core Console 2027** sobre
    # copias de DWG reales (ver `docs/PROGRESS.md`, 2026-09-15):
    #   `tblnext` -- (tblnext tabla [rebobinar]) la siguiente entrada de una tabla
    #       de símbolos como lista DXF; con T empieza por la primera.
    #   `tblobjname` -- (tblobjname tabla nombre) el ename de esa entrada; para un
    #       bloque, `entnext` desde ahí recorre su definición.
    #   `entnext` -- (entnext [ename]) la entidad siguiente; nil al acabar.
    #   `vl-filename-base` / `vl-filename-extension` -- el nombre sin carpeta ni
    #       extensión, y la extensión con su punto (nil si no tiene).
    "tblnext", "tblobjname", "entnext", "vl-filename-base", "vl-filename-extension",
    # `C-16`, dejar AutoCAD como estaba (3.7.1, 2026-09-15). Contrastada contra la
    # referencia de AutoLISP, **sin ejecutar en AutoCAD**:
    #   `command-s` -- como `command`, pero admitida dentro de *error* (desde
    #       AutoCAD 2015 `command` ahí da error). Deshace lo dibujado tras un Esc.
    "command-s",
    # Reconocer la tabla que dibujó ArchMuse (3.7.2, 2026-09-15). Contrastadas
    # contra la referencia de ActiveX, **sin ejecutar en AutoCAD**:
    #   `vla-get-Layer` -- la capa de un objeto, como cadena.
    #   `vla-get-StyleName` -- en una AcadTable, el nombre de su estilo de tabla.
    "vla-get-Layer", "vla-get-StyleName",
    # Aviso de actualización (3.8.0, 2026-09-15). Contrastadas contra la
    # referencia de AutoLISP, **sin ejecutar en AutoCAD**:
    #   `defun-q` -- define una función como lista, que es lo que `S::STARTUP`
    #       necesita para poder añadirle algo con `append` sin pisar lo de otros.
    #   `append` -- une listas.
    #   `vl-bb-ref` / `vl-bb-set` -- la pizarra común a todos los dibujos abiertos:
    #       preguntar una sola vez por sesión, no una por dibujo.
    "defun-q", "append", "vl-bb-ref", "vl-bb-set",
}


#: Símbolos que aparecen en primera posición de una lista y **no son llamadas**:
#: son la condición de una cláusula de `cond`, que es una expresión, no una
#: función. Se enumeran a mano en vez de intentar reconocer `cond` con una
#: expresión regular — la lista es corta y obliga a mirar cada añadido, que es
#: preferible a un reconocedor que se equivoque en silencio.
#: Y los símbolos citados que se comparan contra `(type …)`: `'variant` y
#: `'safearray` son nombres de tipo de AutoLISP, no funciones.
CONDICIONES_DE_COND = {"T", "escapado", "variant", "safearray"}


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

    # **Y lo que se llama CITADO.** Media docena de llamadas de este fichero van
    # como `(vl-catch-all-apply 'vla-SetText (list …))`, para que el fallo de una
    # celda no tumbe las diez siguientes. Ahí el nombre no va tras un paréntesis,
    # así que el patrón de arriba no lo veía: `vla-GetBoundingBox` entró el
    # 2026-09-11 sin que este test la reclamara, y una errata en un nombre citado
    # habría llegado igual de lejos — hasta la línea de comandos, con el plano
    # del cliente abierto.
    llamadas |= set(re.findall(r"'([a-z][A-Za-z0-9:<>=/+*.-]*)", sin_cabeceras))
    # Fuera las variables locales: un símbolo citado puede no ser una llamada.
    # `(vla-GetBoundingBox obj 'minp 'maxp)` cita dos variables porque la función
    # devuelve las esquinas POR REFERENCIA, escribiéndolas ahí. Son locales
    # declaradas en la cabecera de su `defun`, no funciones que puedan estar mal
    # escritas.
    locales = set()
    for nombre in re.findall(r"\(defun\s+([A-Za-z0-9:*<>=/+*-]+)", codigo):
        cabecera = re.search(r"\(defun\s+%s\s*\(([^)]*)\)" % re.escape(nombre),
                             codigo, re.S)
        if cabecera and "/" in cabecera.group(1):
            locales |= set(cabecera.group(1).split("/", 1)[1].split())

    desconocidas = sorted(
        llamadas - PRIMITIVAS - definidas - CONDICIONES_DE_COND - locales)
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
        "la leyenda no coincide con `analyzer/marca_borrador.LEYENDA`")
    # Desde el 2026-09-10 la marca **no toca la tabla**: es un MTEXT en su
    # propia capa, debajo del cuadro. Añadirle una fila a la tabla del
    # arquitecto le cambia la maquetación, que es exactamente lo que ha pedido
    # que no hagamos; una capa propia la puede apagar para imprimir sin borrar
    # nada. Aprobado así en `docs/prd/2026-09-10-rellenar-el-cuadro-del-arquitecto.md`.
    assert "ARCHMUSE - BORRADOR" in fuente, (
        "la marca tiene que ir en su propia capa, para que se pueda apagar")
    assert "vla-AddMText" in fuente, "la marca se escribe como MTEXT, no como celda"


def _formas_que_envuelven(codigo: str, indice: int) -> list[str]:
    """Los nombres de las formas abiertas y todavía sin cerrar en `indice`.

    `(defun x () (if a (progn (vla-SetText …))))` devuelve
    `["defun", "if", "progn"]`. Sirve para preguntar por lo que rodea a una
    llamada, que es más fiable que buscar la palabra `if` en el texto de
    alrededor: cualquier condición vecina, aunque no la envuelva, daba un falso
    positivo.
    """
    pila: list[str] = []
    for i in range(indice):
        ch = codigo[i]
        if ch == "(":
            nombre = re.match(r"\s*([^\s()]*)", codigo[i + 1:])
            pila.append(nombre.group(1) if nombre else "")
        elif ch == ")" and pila:
            pila.pop()
    return pila


def test_no_hay_forma_de_desactivar_la_marca(fuente):
    """Sin parámetro, sin variable de entorno y sin pregunta al usuario.

    Dos comprobaciones: que a su `vla-SetText` no lo envuelve ninguna condición
    que lo pudiera saltar, y que es **la última celda que se escribe**, que es
    lo que la coloca al final de la tabla.
    """
    codigo = _sin_comentarios_ni_cadenas(fuente)
    assert "*am:leyenda-borrador*" in codigo

    # Se busca **dentro de `am:marcar-borrador`**. Hasta el 2026-09-13 el primer
    # `vla-AddMText` del fichero era el de la marca; desde la plantilla fija las
    # notas al pie también son MText y van antes, en `am:dibujar-cuadro`. Lo que
    # se vigila no cambia: el MText de la marca escribe la leyenda y no depende
    # de ninguna condición.
    escritura_pos = codigo.find("vla-AddMText", codigo.index("(defun am:marcar-borrador"))
    assert escritura_pos >= 0, "la leyenda no se escribe en ninguna parte"
    assert "*am:leyenda-borrador*" in codigo[escritura_pos:escritura_pos + 200], (
        "el MTEXT que se escribe no es la leyenda de `C3`")

    class _P:
        start = staticmethod(lambda: escritura_pos)
    escritura = _P()

    # Lo que importa no es qué formas la envuelven, sino que ninguna sea una
    # CONDICIÓN: la marca no puede depender de nada.
    envolturas = set(_formas_que_envuelven(codigo, escritura.start()))
    assert not (envolturas & {"if", "cond", "while"}), (
        "la marca se escribe dentro de %s: tiene que ser incondicional"
        % sorted(envolturas & {"if", "cond", "while"}))

    # Y se llama SIEMPRE que se escribe algo: la llamada a `am:marcar-borrador`
    # está en el camino que sigue a rellenar el cuadro, sin condición delante.
    llamada = codigo.index("(am:marcar-borrador")
    envolturas_llamada = set(_formas_que_envuelven(codigo, llamada))
    assert not (envolturas_llamada & {"if", "cond", "while"}), (
        "la marca se pone bajo condición: %s"
        % sorted(envolturas_llamada & {"if", "cond", "while"}))


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


def test_declara_por_escrito_cuando_se_ejecuto_de_verdad(fuente):
    """Corrió el 2026-09-09 en AutoCAD 2027, y desde ese día la cabecera dice
    eso y no lo contrario.

    Este test es el que antes exigía la frase «ESTE FICHERO NUNCA SE HA
    EJECUTADO». Se cambió a mano el 2026-09-10, que es exactamente lo que su
    versión anterior mandaba hacer el día que el script corriera; el cambio está
    en el diff, junto con lo que la ejecución encontró.
    """
    assert "ESTE FICHERO NUNCA SE HA EJECUTADO" not in fuente, (
        "el fichero ya se ha ejecutado: la cabecera no puede seguir diciendo "
        "que no")
    assert "EJECUTADO POR PRIMERA VEZ EL 2026-09-09, EN AUTOCAD 2027" in fuente


def test_el_cliente_no_escribe_ni_un_texto_que_no_venga_del_servidor(fuente):
    """El guardián del reparto de responsabilidades, y el que más importa ahora.

    Desde el 2026-09-10 este script **rellena el cuadro del arquitecto**. Lo que
    escribe en cada celda lo decide `analyzer/reparto_cuadro.py`; aquí sólo se
    transporta. Un `vla-SetText` con un literal sería ArchMuse decidiendo desde
    el cliente qué pone en el documento de alguien — una segunda implementación
    del criterio, que es lo que prohíbe `D-7`, y encima en el sitio donde no hay
    tests que la vigilen.

    Se comprueba sobre el código sin cadenas: si el argumento del texto ha
    quedado en blanco tras quitarlas, es que era un literal.
    """
    codigo = _sin_comentarios_ni_cadenas(fuente)

    assert "vla-SetText" in codigo, "el script ya no escribe en el cuadro"

    # Sobre la fuente CON las cadenas: una llamada a `vla-SetText` que lleve
    # comillas cerca es un texto literal, y eso es ArchMuse decidiendo desde el
    # cliente qué pone en el documento de alguien.
    for m in re.finditer(r"vla-SetText", fuente):
        vecindad = fuente[m.start():m.start() + 160]
        # Se corta en el cierre de la llamada para no leer el comentario de al
        # lado, que sí puede llevar comillas.
        vecindad = vecindad.split(chr(10))[0]
        assert '"' not in vecindad, (
            "`vla-SetText` con un texto literal: %r. Lo que se escribe tiene "
            "que venir del reparto que manda el servidor" % vecindad[:80])


def test_el_cuadro_se_busca_por_su_titulo_no_por_donde_este(fuente):
    """El cuadro se mueve de sitio entre planos; su título no cambia. Buscarlo
    por coordenadas o por tamaño sería atarse a un plano concreto."""
    assert "*am:titulo-del-cuadro*" in fuente
    codigo = _sin_comentarios_ni_cadenas(fuente)
    assert "am:es-el-cuadro" in codigo


def test_no_se_escribe_nunca_en_el_cuadro_del_arquitecto(fuente):
    """**El invariante del 2026-09-12, y la vuelta que dio el del 2026-09-10.**

    Hasta el 2026-09-12 este test decía lo contrario: prohibía `vla-AddTable`,
    porque entonces el objetivo era **rellenar** el cuadro del arquitecto y una
    tabla propia al lado se consideró que no le ahorraba trabajo. El arquitecto
    dictaminó lo contrario —ArchMuse entrega siempre su cuadro, y el suyo no se
    toca nunca— y con eso el riesgo cambia de lado: ya no es dibujar de más, es
    **escribir en su documento**.

    El test no se borra: se le da la vuelta, y se deja escrito lo que decía
    antes. Un guardián que desaparece se lleva con él el motivo por el que
    existía, y dentro de tres meses nadie sabrá que esto se probó de las dos
    maneras.

    Lo que se comprueba ahora es estructural y no depende de la buena voluntad
    de quien escriba el código: **todos los `vla-SetText` del fichero viven
    dentro de `am:dibujar-cuadro`**, que escribe en una tabla que ha creado él
    mismo dos líneas antes. Si aparece uno fuera, está escribiendo en una tabla
    de otro.
    """
    codigo = _sin_comentarios_ni_cadenas(fuente)

    assert "vla-AddTable" in codigo, (
        "el comando ha dejado de dibujar su cuadro")
    assert "am:rellenar-cuadro" not in codigo, (
        "ha vuelto la función que escribe en el cuadro del arquitecto")

    ini = codigo.index("(defun am:dibujar-cuadro")
    fin = codigo.index("(defun ", ini + 10)
    cuerpo = codigo[ini:fin]

    # El símbolo exacto, no la subcadena: `vla-SetTextStyle` y `vla-SetTextHeight`
    # (3.3.0, `am:estilo-de-tabla`) configuran el estilo de tabla de ArchMuse y no
    # escriben en ninguna celda. Contar la subcadena los tomaba por escrituras.
    exacto = re.compile(r"vla-SetText(?![A-Za-z-])")
    fuera = len(exacto.findall(codigo)) - len(exacto.findall(cuerpo))
    assert fuera == 0, (
        "hay %d `vla-SetText` fuera de `am:dibujar-cuadro`: alguien escribe en "
        "una tabla que ArchMuse no ha creado" % fuera)


def test_marcar_el_punto_es_decir_que_si_y_lo_dibujado_se_deshace_de_una_vez(fuente):
    """Se dibuja en el plano abierto del arquitecto, no en una copia.

    Hasta la 3.7.0 la red era preguntar «¿Te dibujo el cuadro de ArchMuse?
    [Si/No] <No>» justo antes de dibujar. Pablo la quitó el 2026-09-15: marcar
    el punto ya es decir que sí, y un Enter sin leer se quedaba en el <No>, no
    dibujaba nada y parecía un fallo. La red son ahora dos cosas: el punto se
    pide antes de dibujar (Esc ahí no dibuja nada) y todo lo que se escribe va en
    un grupo de deshacer. Este test impide que vuelva la pregunta sin decidirlo.

    **Con dos clics (2026-09-16)** la tabla se dibuja tras medir y se coloca
    arrastrándola en el segundo clic (3.9.6): entre abrir el grupo de deshacer y
    cerrarlo, pasando por el arrastre, no hay ninguna pregunta."""
    codigo = _sin_comentarios_ni_cadenas(fuente)
    comando = codigo[codigo.index("(defun c:ARCHMUSE ("):]
    dibujar = comando.index("(am:dibujar-cuadro")
    abrir = comando.rindex("vla-StartUndoMark", 0, dibujar)
    arrastrar = comando.index("(am:arrastrar-cuadro", dibujar)
    cerrar = comando.index("vla-EndUndoMark", comando.index("(am:maquetar", arrastrar))
    assert "getkword" not in comando[abrir:cerrar], (
        "ha vuelto una pregunta entre dibujar la tabla y colocarla")
    assert abrir < dibujar < arrastrar < cerrar, "se dibuja o se arrastra fuera del grupo de deshacer"


def test_el_ssget_de_recintos_no_lleva_mas_filtro_que_la_capa(fuente):
    """`C-7`, la pieza 3: el cliente no puede filtrar lo que manda.

    `ssget` sólo sabe mirar el bit de «cerrada» del código 70, y ese bit está
    mal puesto en los cinco planos reales del arquitecto — en `v1plantas.dxf`,
    en el salón. Filtrar aquí borra superficie **antes** de que el servidor
    pueda recuperarla, y el servidor no puede echar de menos lo que nunca vio:
    la medición sale limpia y el `0,00 m²` se escribe en el cuadro que él firma.

    Se vigila la selección de recintos de `am:recolectar`: puede filtrar por
    tipo de entidad y por capa, y por nada más.

    **Honestidad sobre este test:** se escribió el 2026-09-10 después de una
    prueba en AutoCAD que dio cero celdas, y **no habría cazado ese fallo** —
    el `ssget` ya estaba sin filtrar. Caza el siguiente, que es para lo que
    sirve un guardián.
    """
    codigo = _sin_comentarios_ni_cadenas(fuente)

    ini = codigo.index("(defun am:recolectar")
    fin = codigo.index("(defun ", ini + 10)
    cuerpo = codigo[ini:fin]

    seleccion = re.search(r"\(ssget[^\n]*\n?[^\n]*", cuerpo)
    assert seleccion, "`am:recolectar` ya no selecciona recintos"
    texto = seleccion.group(0)

    assert "70" not in texto, (
        "el `ssget` de recintos filtra por el código 70: eso deja fuera las "
        "polilíneas con el flag de cerrada mal puesto, que en los planos reales "
        "son hasta un 17%%. Manda todas y deja decidir a "
        "`parser._esta_cerrada`. Línea: %s" % texto.strip())
    assert "-4" not in texto, (
        "el `ssget` de recintos lleva un operador de filtro (`-4`): sólo puede "
        "filtrar por tipo y por capa. Línea: %s" % texto.strip())


def _locales_de(codigo, nombre):
    """Los símbolos declarados tras la `/` en la cabecera de un `defun`."""
    m = re.search(r"\(defun\s+%s\s*\(([^)]*)\)" % re.escape(nombre), codigo, re.S)
    if not m:
        return None
    cabecera = m.group(1)
    if "/" not in cabecera:
        return set()
    return set(cabecera.split("/", 1)[1].split())


def test_el_comando_no_usa_variables_locales_de_otra_funcion(fuente):
    """AutoLISP tiene alcance dinámico, y eso engaña.

    Una local de `c:ARCHMUSE` SÍ se ve dentro de lo que `c:ARCHMUSE` llama. Al
    revés no: cuando `am:recolectar` termina, sus locales dejan de existir. Usar
    una de ellas más tarde no da un error de compilación — da `nil`, y `(itoa
    nil)` revienta en la línea de comandos con el plano del cliente abierto.

    Pasó el 2026-09-11: el mensaje de error del comando usaba `n-celdas`, local
    de `am:recolectar`, y habría reventado **justo en el camino de fallo**, que
    es donde menos se puede permitir. Se arregló con una global declarada.
    """
    codigo = _sin_comentarios_ni_cadenas(fuente)

    ini = codigo.index("(defun c:ARCHMUSE")
    cuerpo = codigo[ini:]
    propias = _locales_de(codigo, r"c:ARCHMUSE") or set()

    ajenas = set()
    for nombre in re.findall(r"\(defun\s+(am:[A-Za-z0-9:>-]+)", codigo):
        locales = _locales_de(codigo, nombre)
        if locales:
            ajenas |= locales

    # Los símbolos que el comando usa y no ha declarado. Globales (`*…*`) y
    # funciones quedan fuera: las primeras existen a propósito, las segundas no
    # son variables.
    # `lookahead`/`lookbehind`, y no clases de caracteres normales: `re.findall`
    # no solapa coincidencias, así que con `[\\s(]…[\\s)]` la de `(itoa ` se comía
    # el espacio que el símbolo siguiente necesitaba como delimitador —y el símbolo
    # que se escapaba era justo el que había que cazar. Comprobado: con la versión
    # anterior este test pasaba con el fallo dentro.
    usados = set(re.findall(r"(?<=[\s(])([a-z][A-Za-z0-9-]*)(?=[\s)])", cuerpo))
    definidas = set(re.findall(r"\(defun\s+([A-Za-z0-9:*<>=/+*-]+)", codigo))

    colados = sorted((usados & ajenas) - propias - definidas - PRIMITIVAS)
    assert colados == [], (
        "el comando usa variables que son locales de otra función y ya no "
        "existen cuando llega ahí: %s. Declárala en `c:ARCHMUSE` o hazla "
        "global." % colados)


def test_nunca_se_dejan_numeros_sin_marca_de_borrador(fuente):
    """`C-3` en su forma más dura: si la marca no se puede poner, lo escrito se
    retira.

    Un cuadro con cifras y sin la advertencia de borrador es **peor que un
    cuadro vacío**: parece definitivo. Pasó el 2026-09-11 —la marca reventó
    después de escribir las diez celdas— y el plano se quedó con los números y
    sin advertencia. Si el arquitecto no llega a mirar la línea de comandos, no
    se entera de nada.

    Tres cosas, y las tres hacen falta:

    1. `am:marcar-borrador` **devuelve si ha marcado**, no traga el fallo.
    2. El comando **mira esa respuesta**.
    3. Y si es que no, **deshace** lo escrito.
    """
    codigo = _sin_comentarios_ni_cadenas(fuente)

    ini = codigo.index("(defun am:marcar-borrador")
    fin = codigo.index("(defun ", ini + 10) if "(defun " in codigo[ini + 10:] else len(codigo)
    cuerpo_marca = codigo[ini:fin]
    assert "vl-catch-all-error-p" in cuerpo_marca, (
        "`am:marcar-borrador` no comprueba si ha fallado: el comando no puede "
        "saber si hay marca")

    ini_cmd = codigo.index("(defun c:ARCHMUSE")
    comando = codigo[ini_cmd:]

    assert "(setq marcado (am:marcar-borrador" in comando, (
        "el comando llama a la marca sin quedarse con la respuesta")

    escritura = comando.index("(am:dibujar-cuadro")
    marca = comando.index("(am:marcar-borrador")
    assert escritura < marca, "la marca se pone antes de dibujar el cuadro"

    posterior = comando[marca:]
    assert "(null marcado)" in posterior, (
        "nadie comprueba que la marca se haya puesto")
    # Sobre la FUENTE y no sobre el código desnudo: `"_.U"` es una cadena, y
    # `_sin_comentarios_ni_cadenas` se lleva su contenido por delante.
    cola = fuente[fuente.index("(am:marcar-borrador tabla"):]
    assert '"_.U"' in cola, (
        "si la marca falla no se deshace lo escrito: el plano se queda con "
        "cifras sin advertencia, que es lo que `C-3` prohíbe")


def _fin_de_forma(codigo: str, ini: int) -> int:
    """Dónde acaba la expresión que empieza en `ini`. Sobre código sin cadenas,
    así que contar paréntesis basta."""
    profundidad = 0
    for i in range(ini, len(codigo)):
        if codigo[i] == "(":
            profundidad += 1
        elif codigo[i] == ")":
            profundidad -= 1
            if profundidad == 0:
                return i + 1
    raise AssertionError("paréntesis sin cerrar desde %d" % ini)


def test_lo_escrito_va_en_un_solo_grupo_de_deshacer(fuente):
    """Un `UNDO` tiene que quitarlo todo —celdas y marca—, no una celda cada vez.

    Es lo que se le promete al arquitecto por pantalla, y además es lo que hace
    posible retirar el trabajo en bloque cuando la marca no se puede poner.
    """
    codigo = _sin_comentarios_ni_cadenas(fuente)
    comando = codigo[codigo.index("(defun c:ARCHMUSE ("):]
    # **Sin `*error*`.** Desde `C-16` también cierra el grupo, y como se define
    # al principio del comando su cierre aparece en el texto antes de abrirlo.
    # Aquí se mira el flujo; *error* lo mira `test_lsp_deja_autocad_como_estaba`.
    ini_error = comando.index("(defun *error*")
    comando = comando[:ini_error] + comando[_fin_de_forma(comando, ini_error):]

    inicio = comando.index("vla-StartUndoMark")
    # **El último cierre, no el primero.** Desde el 2026-09-12 hay dos:
    # `am:dibujar-cuadro` puede fallar, y esa rama cierra el grupo y sale antes
    # de llegar a la marca. Mirar el primero daría rojo por la rama de fallo,
    # que es precisamente la que SÍ está bien cerrada.
    fin = comando.rindex("vla-EndUndoMark")
    escritura = comando.index("(am:dibujar-cuadro")
    marca = comando.index("(am:marcar-borrador")

    assert inicio < escritura, "se dibuja fuera del grupo de deshacer"
    assert marca < fin, "la marca queda fuera del grupo de deshacer"
    # Y ningún cierre puede estar antes de empezar a dibujar: eso dejaría la
    # tabla fuera del grupo y harían falta dos `UNDO`.
    assert inicio < comando.index("vla-EndUndoMark"), (
        "hay un cierre del grupo de deshacer antes de abrirlo")
