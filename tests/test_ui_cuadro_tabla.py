# -*- coding: utf-8 -*-
"""Fase 6 — tabla del cuadro de superficies visible en pantalla, modo "Cuadro"
(`static/app.js`). Ejecutar:  python tests/test_ui_cuadro_tabla.py

Mismo patrón que `tests/test_ui_completar_cuadro_superficies.py`: lectura de
fuente + ejecución real de las funciones puras vía `node`. Sin Flask, sin DXF.

Que protege:

1. `PLAN_MODES` incluye el modo "cuadro", y `inspectorModoHtml` lo conecta
   con `toolCuadroSuperficiesHtml`.
2. `ribbonPanelHtml` ya no tiene una rama "salida" separada -- Exportar vive
   dentro de la única pestaña "Vista" (RIBBON_TABS con un solo elemento).
3. `toolCuadroSuperficiesHtml` (ejecución real):
   - sin `cuadro_superficies_detectado` -> mensaje claro, no intenta pedir nada.
   - con cuadro detectado pero sin `archivoAnalizado` (proyecto reabierto de
     la lista) -> mensaje claro, tampoco pide nada al servidor.
   - con ambos, primera vez (`state.cuadroTabla` aún `null`) -> arranca la
     carga (no se comprueba aquí la llamada de red, solo que no revienta).
4. `cuadroTablaHtml` (ejecución real): pinta una fila por celda, distingue
   visualmente las pendientes (`cuadro-fila-pendiente`), y la procedencia
   (`_origenCeldaCuadro`) prioriza declarado > preexistente > pendiente >
   calculado, sin inventar un quinto estado.
5. Ninguna de las funciones nuevas de esta fase reimplementa un patrón de
   habitación -- toda esa lógica sigue viviendo solo en
   `analyzer/cuadro_superficies.py`.
6. Fase 6b (rediseño: "no lo quiero para descargar, quiero verlo en el
   navegador"): aplicar respuestas actualiza `state.cuadroTabla`, nunca
   dispara una descarga; descargar el DXF es una acción APARTE
   (`descargarCuadroCompletoDesdeTabla`), solo visible cuando ya no queda
   ninguna solicitud pendiente.
7. Fase 6c (rediseño: "quiero que se vea como el plano, pero en vez del
   plano el cuadro"): `contenidoCuadroSuperficies` es el cuerpo de la vista
   GRANDE del lienzo principal (`renderCuadroLienzo`, en
   `#cad-cuadro-superficies`, hermano de `#svg-container` dentro de
   `#cad-lienzo`). `aplicarModoLienzo` (llamada desde `setModo`) es la única
   que decide cuál de los dos contenedores está `hidden`, y
   `wireInspectorAcciones` delega también sobre `#cad-cuadro-superficies`
   (no solo `#inspector`), para que los botones de esa vista grande
   funcionen igual.
8. Fase 6d (rediseño: el modal de Fase 5 se retira -- ver
   `tests/test_ui_completar_cuadro_superficies.py` para el detalle):
   `toolCuadroSuperficiesHtml` (panel pequeño del inspector) ya NO repite
   la tabla ni el formulario -- el lienzo grande es la ÚNICA vista con
   contenido real (`contenidoCuadroSuperficies`), evitando dos copias
   editables del mismo formulario que no se sincronizarían entre sí tecla a
   tecla.
9. Fase 6f (petición explícita de Pablo: "borra el dashboard que está a la
   derecha"): `toolCuadroSuperficiesHtml` ya no muestra ni un puntero --
   devuelve directamente cadena vacía, panel del inspector en blanco en
   modo "Cuadro".
"""
import os
import re
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_JS = os.path.join(RAIZ, "static", "app.js")

fallos = []
comprobaciones = 0


def check(ok, etiqueta, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s%s" % ("OK  " if ok else "FALLO", etiqueta, ("  -> " + detalle) if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


with open(APP_JS, encoding="utf-8") as f:
    JS = f.read()

_FUNC_DECL = re.compile(r"\n  function\s+([A-Za-z0-9_]+)\s*\(")


def extraer_var(nombre):
    """`var NOMBRE = { ... };` -- objeto literal plano, sin llaves anidadas
    (como `_GRUPO_CAMPO_CUADRO`), para poder ejecutar en el harness node
    funciones que dependen de él sin reconstruirlo a mano (evita que el
    test y el código real diverjan)."""
    m = re.search(r"\n  var\s+" + re.escape(nombre) + r"\s*=\s*\{[^{}]*\};", JS)
    if not m:
        raise AssertionError("no se encuentra var %s en app.js" % nombre)
    return m.group(0)


def extraer_funcion(nombre):
    posiciones = [(m.start(), m.group(1)) for m in _FUNC_DECL.finditer(JS)]
    for i, (inicio, nom) in enumerate(posiciones):
        if nom == nombre:
            fin = posiciones[i + 1][0] if i + 1 < len(posiciones) else len(JS)
            return JS[inicio:fin]
    raise AssertionError("no se encuentra function %s en app.js" % nombre)


print()
print("A. Estático: wiring correcto")
print("-" * 68)

check('{ id: "cuadro", label: "Cuadro" }' in JS, "PLAN_MODES incluye el modo cuadro")
check('if (state.modo === "cuadro") return toolCuadroSuperficiesHtml(v);' in JS,
      "inspectorModoHtml conecta el modo cuadro con toolCuadroSuperficiesHtml")
check('{ id: "vista", label: "Vista" }' in JS, "RIBBON_TABS sigue teniendo la pestaña Vista")
check('{ id: "salida", label: "Salida" }' not in JS, "y ya NO tiene la pestaña Salida")

fuente_ribbon = extraer_funcion("ribbonPanelHtml")
check('tabId === "salida"' not in fuente_ribbon, "ribbonPanelHtml ya no distingue una rama salida aparte")
check('grupoRibbon("Exportar"' not in fuente_ribbon,
      "el grupo Exportar del ribbon se retiró (Fase 6d) -- todo vive ya en el modo Cuadro")
check('data-accion="completar-cuadro-superficies"' not in JS,
      "no queda ningún botón/acción completar-cuadro-superficies -- el formulario aparece solo, inline")

check("function cargarCuadroTabla()" in JS, "cargarCuadroTabla existe")
check("function toolCuadroSuperficiesHtml(v)" in JS, "toolCuadroSuperficiesHtml existe")
check("function cuadroTablaHtml(celdas)" in JS, "cuadroTablaHtml existe")

check('"aplicar-respuestas-cuadro": function () { aplicarRespuestasCuadroInline(); }' in JS,
      "ACCIONES_CAD conecta aplicar-respuestas-cuadro con aplicarRespuestasCuadroInline")
check('"descargar-cuadro-completo": function () { descargarCuadroCompletoDesdeTabla(); }' in JS,
      "ACCIONES_CAD conecta descargar-cuadro-completo con descargarCuadroCompletoDesdeTabla")
check("function aplicarRespuestasCuadroInline()" in JS,
      "aplicarRespuestasCuadroInline existe (aplica respuestas, no descarga)")
check("function descargarCuadroCompletoDesdeTabla()" in JS,
      "descargarCuadroCompletoDesdeTabla existe (la única acción que sí descarga, y es opcional)")

fuente_contenido = extraer_funcion("contenidoCuadroSuperficies")
check('data-accion="descargar-cuadro-completo"' in fuente_contenido,
      "el botón de descarga opcional vive en contenidoCuadroSuperficies")
check("cuadroFormularioInlineHtml(" in fuente_contenido,
      "y el formulario aparece inline (Fase 6d) cuando falta algo -- sin botón intermedio que lo abra")

fuente_tool_cuadro = extraer_funcion("toolCuadroSuperficiesHtml")
check("contenidoCuadroSuperficies()" not in fuente_tool_cuadro,
      "toolCuadroSuperficiesHtml (vista pequeña, inspector) no repite la tabla/formulario")
check('return "";' in fuente_tool_cuadro,
      "y ya no muestra ni siquiera un puntero -- petición explícita de Pablo, panel vacío del todo")

check("function renderCuadroLienzo()" in JS, "renderCuadroLienzo existe (Fase 6c, vista grande en el lienzo)")
fuente_lienzo_grande = extraer_funcion("renderCuadroLienzo")
check('getElementById("cad-cuadro-superficies")' in fuente_lienzo_grande,
      "renderCuadroLienzo pinta sobre #cad-cuadro-superficies")
check("contenidoCuadroSuperficies()" in fuente_lienzo_grande,
      "renderCuadroLienzo (vista grande) TAMBIÉN reutiliza el mismo cuerpo compartido -- no hay una tercera copia")

check("function aplicarModoLienzo()" in JS, "aplicarModoLienzo existe")
fuente_modo_lienzo = extraer_funcion("aplicarModoLienzo")
check('svgHost.hidden = esCuadro' in fuente_modo_lienzo, "en modo cuadro, el plano (#svg-container) se oculta")
check('cuadroHost.hidden = !esCuadro' in fuente_modo_lienzo,
      "y #cad-cuadro-superficies se muestra -- nunca los dos a la vez")

fuente_set_modo = extraer_funcion("setModo")
check("aplicarModoLienzo();" in fuente_set_modo, "setModo llama a aplicarModoLienzo en cada cambio de modo")

check("function refrescarVistaCuadro()" in JS, "refrescarVistaCuadro existe")
fuente_refrescar = extraer_funcion("refrescarVistaCuadro")
check("renderInspector();" in fuente_refrescar and "renderCuadroLienzo();" in fuente_refrescar,
      "refrescarVistaCuadro actualiza las DOS vistas a la vez tras un cambio async")

fuente_wire_insp = extraer_funcion("wireInspectorAcciones")
check('"#inspector, #cad-cuadro-superficies"' in fuente_wire_insp,
      "wireInspectorAcciones delega también sobre #cad-cuadro-superficies, no solo #inspector")

check('id="cad-cuadro-superficies" class="cad-cuadro-lienzo" hidden' in JS,
      "el contenedor del lienzo grande arranca oculto (el plano se ve por defecto)")

# Bug real reportado ("dentro del cuadro no puedo scrolear bien"): el
# listener de rueda de #cad-lienzo encontraba el <svg> aunque estuviera
# oculto (sigue en el DOM) y llamaba preventDefault() sobre CUALQUIER
# scroll, bloqueando el overflow-y:auto de #cad-cuadro-superficies.
fuente_wire_lienzo = extraer_funcion("wireLienzoCAD")
check('if (state.modo === "cuadro" || !svgActual()) return;' in fuente_wire_lienzo,
      "el zoom por rueda se desactiva en modo Cuadro -- el scroll normal de la tabla ya no se bloquea")

for nombre_funcion in ("toolCuadroSuperficiesHtml", "renderCuadroLienzo", "contenidoCuadroSuperficies",
                        "cuadroTablaHtml", "_origenCeldaCuadro", "cargarCuadroTabla"):
    fuente = extraer_funcion(nombre_funcion)
    for patron_prohibido in ("DORMITORIO", "TENDEDERO", "TERRAZA", "SALON", "PASILLO", "\\bBANO\\b"):
        check(patron_prohibido not in fuente,
              "%s no reimplementa el patrón %r" % (nombre_funcion, patron_prohibido))


print()
print("B. Ejecución real (vía node)")
print("-" * 68)

node_disponible = True
try:
    subprocess.run(["node", "--version"], capture_output=True, check=True)
except (FileNotFoundError, subprocess.CalledProcessError):
    node_disponible = False

if not node_disponible:
    check(False, "node está disponible en el sistema (necesario para esta sección)")
else:
    harness = (
        extraer_funcion("escapeHtml") + "\n" +
        extraer_funcion("etiquetaCampoLegible") + "\n" +
        extraer_funcion("_origenCeldaCuadro") + "\n" +
        extraer_funcion("_origenClaseCuadro") + "\n" +
        extraer_var("_GRUPO_CAMPO_CUADRO") + "\n" +
        extraer_funcion("cuadroTablaHtml") + "\n"
        r"""
        var resultados = [];
        function afirma(cond, etiqueta) { resultados.push([cond, etiqueta]); }

        // --- _origenCeldaCuadro: prioridad de lectura ---------------------
        afirma(_origenCeldaCuadro({estado: "CALCULADO", preexistente: false, declarado_por_usuario: false})
               === "Calculado por ArchMuse", "calculado normal -> 'Calculado por ArchMuse'");
        afirma(_origenCeldaCuadro({estado: "CALCULADO", preexistente: true, declarado_por_usuario: false})
               === "Ya estaba en el DXF", "preexistente -> 'Ya estaba en el DXF' aunque el estado sea CALCULADO");
        afirma(_origenCeldaCuadro({estado: "CERO_REAL", preexistente: false, declarado_por_usuario: true})
               === "Declarado por el arquitecto", "declarado_por_usuario tiene prioridad sobre todo lo demás");
        afirma(_origenCeldaCuadro({estado: "BLOQUEADO", preexistente: false, declarado_por_usuario: false})
               === "Pendiente", "BLOQUEADO sin declarar/preexistente -> 'Pendiente'");
        afirma(_origenCeldaCuadro({estado: "NO_DISPONIBLE", preexistente: false, declarado_por_usuario: false})
               === "Pendiente", "NO_DISPONIBLE sin declarar/preexistente -> 'Pendiente'");

        // --- cuadroTablaHtml: una fila por celda, pendientes distinguidas --
        var celdas = [
          {campo: "salon_cocina", etiqueta: "SALON + COCINA", texto: "21,90 m²", estado: "CALCULADO",
           preexistente: false, declarado_por_usuario: false},
          {campo: "tendedero", etiqueta: "TENDEDERO", texto: "BLOQUEADO", estado: "BLOQUEADO",
           preexistente: false, declarado_por_usuario: false},
          {campo: "vivienda_tipo", etiqueta: "VIVIENDA TIPO", texto: "VT1 /3", estado: "CALCULADO",
           preexistente: true, declarado_por_usuario: false}
        ];
        var html = cuadroTablaHtml(celdas);
        afirma(html.indexOf("<table") !== -1, "renderiza una tabla HTML real");
        afirma(html.indexOf("21,90") !== -1, "el valor calculado aparece tal cual");
        afirma(html.indexOf("VT1 /3") !== -1, "el valor preexistente aparece tal cual");
        afirma(html.indexOf("cuadro-fila-pendiente") !== -1, "la fila pendiente lleva su clase distintiva");
        afirma(/<td>\s*—\s*<\/td>/.test(html) || html.indexOf(">—<") !== -1,
               "la celda pendiente muestra un guion, nunca 'BLOQUEADO' ni un valor inventado");
        afirma(html.indexOf("Ya estaba en el DXF") !== -1, "la procedencia preexistente se ve en la tabla");
        afirma(html.indexOf("Calculado por ArchMuse") !== -1, "la procedencia calculada se ve en la tabla");

        // --- Diseño más profesional (Fase 6e): grupos, insignias, valores alineados ---
        afirma(html.indexOf('class="cuadro-tabla-grupo"') !== -1,
               "las celdas se agrupan visualmente (Interior/Exterior/Totales/Datos de proyecto)");
        afirma(html.indexOf(">Interior<") !== -1, "el grupo de salon_cocina es 'Interior'");
        afirma(html.indexOf(">Datos de proyecto<") !== -1, "el grupo de vivienda_tipo es 'Datos de proyecto'");
        afirma(html.indexOf('class="cuadro-origen-badge cuadro-origen-calculado"') !== -1,
               "la procedencia calculada lleva su insignia de color propia");
        afirma(html.indexOf('class="cuadro-origen-badge cuadro-origen-dxf"') !== -1,
               "la procedencia preexistente lleva su insignia de color propia");
        afirma(html.indexOf('class="cuadro-tabla-valor"') !== -1,
               "la columna de valor lleva su propia clase (alineación a la derecha)");
        // Ningún campo sin grupo declarado se pierde -- respaldo "Otros".
        afirma(cuadroTablaHtml([{campo: "campo_no_mapeado", etiqueta: "X", texto: "1,00 m²", estado: "CALCULADO",
                                  preexistente: false, declarado_por_usuario: false}]).indexOf(">Otros<") !== -1,
               "un campo sin grupo conocido cae en 'Otros', nunca desaparece");

        // Sin celdas -> tabla vacía, no revienta.
        var htmlVacio = cuadroTablaHtml([]);
        afirma(htmlVacio.indexOf("<table") !== -1, "cuadroTablaHtml([]) no revienta, sigue devolviendo una tabla");

        var resultados_filtrados = resultados.filter(function (r) { return !r[0]; });
        resultados.forEach(function (r) {
          console.log((r[0] ? "OK  " : "FALLO") + " " + r[1]);
        });
        process.exit(resultados_filtrados.length ? 1 : 0);
        """
    )
    tmp_js = os.path.join(RAIZ, "tests", "_tmp_cuadro_tabla_harness.js")
    with open(tmp_js, "w", encoding="utf-8") as f:
        f.write(harness)
    try:
        proc = subprocess.run(["node", tmp_js], capture_output=True, text=True, encoding="utf-8")
        for linea in proc.stdout.splitlines():
            print("  [node] " + linea)
        if proc.stderr.strip():
            print("  [node stderr] " + proc.stderr.strip())
        check(proc.returncode == 0, "todas las afirmaciones ejecutadas en node pasan")
    finally:
        try:
            os.remove(tmp_js)
        except OSError:
            pass


print()
print("=" * 68)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
