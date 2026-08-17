# -*- coding: utf-8 -*-
"""Fase 6d — formulario "Datos necesarios para completar el cuadro", INLINE
en la tabla (`static/app.js`). Sustituye al modal de Fase 5 (Pablo: "sigue
sin verse el cuadro en la web, se me descarga y no quiero descargarlo quiero
verlo" -- el modal era justo el paso de indirección que causaba la
confusión).

Ejecutar:  python tests/test_ui_completar_cuadro_superficies.py

Mismo patrón que `tests/test_ui_cuadro_tabla.py`: lectura de fuente +
ejecución real de las funciones puras vía `node`. Sin Flask, sin DXF.

Que protege:

1. El modal de Fase 5 (`abrirModalCompletarCuadro`, `cerrarModalCuadro`,
   `wireModalCuadro`, `renderModalCuadro`, `cuadroFormularioHtml`,
   `#cuadro-solicitudes-modal`) ya NO EXISTE -- si alguien lo reintroduce
   sin querer, este test lo detecta.
2. `ACCIONES_CAD` conecta `aplicar-respuestas-cuadro` con
   `aplicarRespuestasCuadroInline` -- éste es el bug real que se encontró
   verificando en el navegador durante este mismo rediseño (el botón
   "Aplicar respuestas" no hacía NADA porque faltaba esta entrada) y que
   este test deja cubierto para que no vuelva a colarse en silencio.
3. `aplicarRespuestasCuadroInline` lee de `state.cuadroTabla` (no de un
   `state.cuadroFormulario` aparte, que ya no existe) y llama a
   `/api/cuadro-superficies/estado` -- nunca a
   `/api/exportar-cuadro-superficies-completo` (esa es
   `descargarCuadroCompletoDesdeTabla`, la única función que descarga algo,
   y es una acción aparte y opcional).
4. Las funciones puras del formulario (ejecución real vía node):
   - `respuestaNumericaValida` acepta números (con coma o punto) y rechaza
     vacío/negativo/no numérico.
   - `asignacionTieneDuplicados` detecta una misma pieza asignada a dos
     huecos a la vez (misma regla que el backend, del lado cliente).
   - `todasLasSolicitudesResueltas` solo exige texto en las numéricas -- una
     de asignación ya tiene un valor válido por defecto ("sin asignar").
   - `construirRespuestasCuadro` produce EXACTAMENTE la forma que espera
     `aplicar_respuestas` en el backend (mismos nombres de clave).
   - `cuadroFormularioInlineHtml` renderiza las solicitudes DIRECTAMENTE
     (sin envoltorio de modal), deshabilita el botón de aplicar mientras
     falte una respuesta numérica, y muestra el conflicto sin perder lo ya
     escrito.
5. Ninguna de estas funciones reimplementa un patrón de habitación -- toda
   esa lógica sigue viviendo solo en `analyzer/cuadro_superficies.py`.
6. `descargarPdf`/`exportarCSV`/`descargarDxfRelleno` (exportaciones ya
   existentes, ocultas del ribbon pero con la capacidad intacta) siguen
   presentes sin cambios de firma.
"""
import os
import re
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_JS = os.path.join(RAIZ, "static", "app.js")
INDEX_HTML = os.path.join(RAIZ, "static", "index.html")

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
with open(INDEX_HTML, encoding="utf-8") as f:
    HTML = f.read()

_FUNC_DECL = re.compile(r"\n  function\s+([A-Za-z0-9_]+)\s*\(")


def extraer_funcion(nombre):
    posiciones = [(m.start(), m.group(1)) for m in _FUNC_DECL.finditer(JS)]
    for i, (inicio, nom) in enumerate(posiciones):
        if nom == nombre:
            fin = posiciones[i + 1][0] if i + 1 < len(posiciones) else len(JS)
            return JS[inicio:fin]
    raise AssertionError("no se encuentra function %s en app.js" % nombre)


print()
print("A. El modal de Fase 5 ya no existe -- reemplazado por el formulario inline")
print("-" * 68)

for nombre_muerto in ("abrirModalCompletarCuadro", "cerrarModalCuadro", "wireModalCuadro",
                       "renderModalCuadro", "cuadroFormularioHtml", "aplicarRespuestasCuadro",
                       "botonCompletarCuadroHtml"):
    check(("function %s(" % nombre_muerto) not in JS,
          "%s ya no existe (modal retirado, Fase 6d)" % nombre_muerto)

check("cuadro-solicitudes-modal" not in HTML, "el nodo del modal ya no está en index.html")
check("cuadro-solicitudes-modal" not in JS, "y app.js tampoco lo referencia")

print()
print("B. Wiring correcto del formulario inline")
print("-" * 68)

check('"aplicar-respuestas-cuadro": function () { aplicarRespuestasCuadroInline(); }' in JS,
      "ACCIONES_CAD conecta aplicar-respuestas-cuadro con aplicarRespuestasCuadroInline -- "
      "bug real encontrado en el navegador: sin esta línea, el botón no hacía nada")
check('"descargar-cuadro-completo": function () { descargarCuadroCompletoDesdeTabla(); }' in JS,
      "ACCIONES_CAD sigue conectando descargar-cuadro-completo (acción aparte y opcional)")
check('"exportar-pdf": function () { descargarPdf(); }' in JS, "exportar-pdf sigue intacto")
check('"exportar-csv": function () { exportarCSV(); }' in JS, "exportar-csv sigue intacto")

fuente_inline = extraer_funcion("aplicarRespuestasCuadroInline")
check("state.cuadroTabla" in fuente_inline,
      "aplicarRespuestasCuadroInline lee de state.cuadroTabla (no de un state.cuadroFormulario aparte)")
check('"/api/cuadro-superficies/estado"' in fuente_inline,
      "y llama a /api/cuadro-superficies/estado (cálculo puro)")
check('"/api/exportar-cuadro-superficies-completo"' not in fuente_inline,
      "NUNCA al endpoint que genera un DXF -- aplicar respuestas no descarga nada")

check("function descargarPdf()" in JS, "descargarPdf sigue existiendo")
check("function exportarCSV()" in JS, "exportarCSV sigue existiendo")
check("function descargarDxfRelleno()" in JS, "descargarDxfRelleno (Fase 4) sigue existiendo")

for nombre_funcion in ("cuadroSolicitudBloqueHtml", "cuadroFormularioInlineHtml", "construirRespuestasCuadro",
                        "aplicarRespuestasCuadroInline", "descargarCuadroCompletoDesdeTabla", "etiquetaCampoLegible"):
    fuente = extraer_funcion(nombre_funcion)
    for patron_prohibido in ("DORMITORIO", "TENDEDERO", "TERRAZA", "SALON", "PASILLO", "\\bBANO\\b"):
        check(patron_prohibido not in fuente,
              "%s no reimplementa el patrón %r" % (nombre_funcion, patron_prohibido))


print()
print("C. Ejecución real (vía node): las funciones puras del formulario")
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
        extraer_funcion("respuestaNumericaValida") + "\n" +
        extraer_funcion("asignacionTieneDuplicados") + "\n" +
        extraer_funcion("todasLasSolicitudesResueltas") + "\n" +
        extraer_funcion("construirRespuestasCuadro") + "\n" +
        extraer_funcion("cuadroSolicitudBloqueHtml") + "\n" +
        extraer_funcion("cuadroFormularioInlineHtml") + "\n"
        r"""
        var resultados = [];
        function afirma(cond, etiqueta) { resultados.push([cond, etiqueta]); }

        // --- respuestaNumericaValida -------------------------------------
        afirma(respuestaNumericaValida("70,5") === true, "70,5 (coma) es válido");
        afirma(respuestaNumericaValida("70.5") === true, "70.5 (punto) es válido");
        afirma(respuestaNumericaValida("0") === true, "0 es válido (un cero real declarado)");
        afirma(respuestaNumericaValida("") === false, "vacío no es válido");
        afirma(respuestaNumericaValida(undefined) === false, "undefined no es válido");
        afirma(respuestaNumericaValida("abc") === false, "texto no numérico no es válido");
        afirma(respuestaNumericaValida("-3") === false, "negativo no es válido");

        // --- asignacionTieneDuplicados -----------------------------------
        afirma(asignacionTieneDuplicados({tendedero: "cand_0", terraza_1: "cand_1", terraza_2: null}) === false,
               "sin repetidos -> false");
        afirma(asignacionTieneDuplicados({tendedero: "cand_0", terraza_1: "cand_0", terraza_2: null}) === true,
               "misma pieza en dos huecos -> true (conflicto detectado en cliente)");
        afirma(asignacionTieneDuplicados({tendedero: null, terraza_1: null, terraza_2: null}) === false,
               "todo sin asignar -> false (no hay elegidos, no hay conflicto)");

        // --- todasLasSolicitudesResueltas ---------------------------------
        var solicitudes = [
          {id: "asignacion_exterior", tipo: "asignacion", campos: ["tendedero", "terraza_1", "terraza_2"],
           titulo: "t", ayuda: "a", candidatos: [
             {id: "cand_0", etiqueta: "Tendedero", area_m2: 4.22, x: 1, y: 2},
             {id: "cand_1", etiqueta: "Tendedero", area_m2: 8.63, x: 3, y: 4},
             {id: "cand_2", etiqueta: "Terraza", area_m2: 3.32, x: 5, y: 6}
           ]},
          {id: "superficie_construida_cerrada", tipo: "numerico", campos: ["superficie_construida_cerrada"],
           titulo: "t2", ayuda: "a2", unidad: "m²"}
        ];
        afirma(todasLasSolicitudesResueltas(solicitudes, {}, {}) === false,
               "sin rellenar la numérica -> NO resuelto (aunque la asignación por defecto sí lo esté)");
        afirma(todasLasSolicitudesResueltas(solicitudes, {superficie_construida_cerrada: "70,5"}, {}) === true,
               "con la numérica rellena y la asignación en su valor por defecto -> resuelto");
        afirma(todasLasSolicitudesResueltas(
                 solicitudes, {superficie_construida_cerrada: "70,5"},
                 {asignacion_exterior: {tendedero: "cand_0", terraza_1: "cand_0"}}) === false,
               "con una pieza repetida en la asignación -> NO resuelto");

        // --- construirRespuestasCuadro: misma forma que aplicar_respuestas ---
        var respuestas = construirRespuestasCuadro(
          solicitudes, {superficie_construida_cerrada: "70,5"},
          {asignacion_exterior: {tendedero: "cand_0", terraza_1: "cand_2", terraza_2: ""}});
        afirma(respuestas.length === 2, "una respuesta por solicitud (2)");
        var rNum = respuestas.filter(function (r) { return r.tipo === "numerico"; })[0];
        afirma(rNum.campo === "superficie_construida_cerrada" && rNum.valor === 70.5,
               "respuesta numérica: campo + valor numérico (coma -> punto)");
        var rAsig = respuestas.filter(function (r) { return r.tipo === "asignacion"; })[0];
        afirma(rAsig.solicitud_id === "asignacion_exterior", "respuesta de asignación: solicitud_id correcto");
        afirma(rAsig.asignaciones.tendedero === "cand_0" && rAsig.asignaciones.terraza_1 === "cand_2",
               "asignaciones elegidas viajan tal cual");
        afirma(rAsig.asignaciones.terraza_2 === null,
               "un hueco sin asignar (\"\") se envía como null, nunca como cadena vacía");

        // --- cuadroFormularioInlineHtml: render + gating + conflicto, SIN modal ---
        var htmlSinResponder = cuadroFormularioInlineHtml(solicitudes, {}, {}, {});
        afirma(htmlSinResponder.indexOf("Datos necesarios para completar el cuadro") !== -1,
               "el formulario lleva el título exacto pedido por Pablo");
        afirma(htmlSinResponder.indexOf('class="cuadro-formulario-inline"') !== -1,
               "se renderiza como bloque inline, no como modal");
        afirma(htmlSinResponder.indexOf("disabled") !== -1,
               "sin la numérica rellena, el botón de aplicar sale deshabilitado");
        afirma(htmlSinResponder.indexOf("Tendedero") !== -1 && htmlSinResponder.indexOf("4.22") !== -1,
               "muestra los candidatos reales (nombre + superficie)");
        afirma(htmlSinResponder.indexOf("no se descarga nada") !== -1,
               "el formulario deja claro que esto NO descarga nada (petición explícita de Pablo)");

        var htmlCompleto = cuadroFormularioInlineHtml(
          solicitudes, {superficie_construida_cerrada: "70,5"}, {}, {});
        afirma(/id="btn-aplicar-respuestas-cuadro"[^>]*>/.test(htmlCompleto) &&
               !/id="btn-aplicar-respuestas-cuadro"[^>]*disabled/.test(htmlCompleto),
               "con todo resuelto, el botón de aplicar YA NO sale deshabilitado");

        var htmlConflicto = cuadroFormularioInlineHtml(
          solicitudes, {superficie_construida_cerrada: "70,5"}, {},
          {tendedero: "Conflicto: el DXF ya tiene otro valor en esta celda."});
        afirma(htmlConflicto.indexOf("cuadro-conflicto") !== -1 && htmlConflicto.indexOf("Conflicto:") !== -1,
               "un conflicto pasado en pendientesPorCampo se muestra en el formulario");
        afirma(htmlConflicto.indexOf("Tendedero") !== -1,
               "y las respuestas ya dadas (candidatos, valores) se siguen mostrando -- no se pierden");

        var resultados_filtrados = resultados.filter(function (r) { return !r[0]; });
        resultados.forEach(function (r) {
          console.log((r[0] ? "OK  " : "FALLO") + " " + r[1]);
        });
        process.exit(resultados_filtrados.length ? 1 : 0);
        """
    )
    tmp_js = os.path.join(RAIZ, "tests", "_tmp_completar_cuadro_harness.js")
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
