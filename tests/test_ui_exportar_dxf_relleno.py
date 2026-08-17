# -*- coding: utf-8 -*-
"""Fase 4 — botón "Descargar DXF rellenado" en `static/app.js` (pestaña Salida).

Ejecutar:  python tests/test_ui_exportar_dxf_relleno.py

Mismo patrón que `tests/test_ui_hechos.py`: lectura de fuente + ejecución
real de las funciones puras vía `node` (ya instalado, sin Jest/Playwright).
Sin Flask, sin DXF.

Que protege:

1. El botón solo aparece con `cuadro_superficies_detectado === true` Y
   `state.archivoAnalizado` presente -- las dos condiciones, no una sola
   (ejecución real, sección B).
2. `state.archivoAnalizado` se limpia en `irAInicio` y `abrirProyecto`, para
   que un proyecto reabierto de la lista no herede el `File` de un análisis
   anterior y ofrezca descargar el DXF equivocado.
3. `ACCIONES_CAD` conecta `exportar-dxf-relleno` con `descargarDxfRelleno`,
   sin tocar las entradas ya existentes (`exportar-pdf`, `exportar-csv`).
4. `descargarDxfRelleno` no duplica ningún cálculo de superficies: no
   contiene ninguna cadena de familia de habitación (los patrones viven
   solo en `analyzer/cuadro_superficies.py`) -- solo hace `fetch` +
   descarga de blob, igual que `descargarPdf`.
5. `descargarPdf`/`exportarCSV` (exportaciones ya existentes) siguen
   presentes sin cambios de firma.
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


def extraer_funcion(nombre):
    posiciones = [(m.start(), m.group(1)) for m in _FUNC_DECL.finditer(JS)]
    for i, (inicio, nom) in enumerate(posiciones):
        if nom == nombre:
            fin = posiciones[i + 1][0] if i + 1 < len(posiciones) else len(JS)
            return JS[inicio:fin]
    raise AssertionError("no se encuentra function %s en app.js" % nombre)


print()
print("A. Estático: wiring correcto, sin tocar lo existente")
print("-" * 68)

check('"exportar-dxf-relleno": function () { descargarDxfRelleno(); }' in JS,
      "ACCIONES_CAD conecta exportar-dxf-relleno con descargarDxfRelleno")
check('"exportar-pdf": function () { descargarPdf(); }' in JS,
      "exportar-pdf sigue intacto")
check('"exportar-csv": function () { exportarCSV(); }' in JS,
      "exportar-csv sigue intacto")

fuente_boton = extraer_funcion("botonDescargaDxfRellenoHtml")
check("cuadro_superficies_detectado" in fuente_boton,
      "el botón consulta cuadro_superficies_detectado (calculado en el backend)")
check("archivoAnalizado" in fuente_boton,
      "y también exige que exista state.archivoAnalizado")

fuente_descarga = extraer_funcion("descargarDxfRelleno")
check("/api/exportar-cuadro-superficies" in fuente_descarga,
      "descargarDxfRelleno llama al endpoint nuevo")
check("state.archivoAnalizado" in fuente_descarga,
      "y reenvía state.archivoAnalizado, no un archivo distinto")
# No duplica lógica de cálculo: ninguno de los patrones de habitación de
# analyzer/cuadro_superficies.py (dormitorio, tendedero, terraza, baño...)
# debe aparecer aquí -- toda esa lógica vive solo en Python.
for patron_prohibido in ("DORMITORIO", "TENDEDERO", "TERRAZA", "SALON", "PASILLO"):
    check(patron_prohibido not in fuente_descarga,
          "descargarDxfRelleno no reimplementa el patrón %r" % patron_prohibido)

fuente_iraInicio = extraer_funcion("irAInicio")
check("state.archivoAnalizado = null;" in fuente_iraInicio,
      "irAInicio limpia state.archivoAnalizado")

fuente_abrirProyecto = extraer_funcion("abrirProyecto")
check("state.archivoAnalizado = null;" in fuente_abrirProyecto,
      "abrirProyecto limpia state.archivoAnalizado (proyecto reabierto de la lista)")

# Las exportaciones ya existentes siguen ahí, sin que este cambio las toque.
check("function descargarPdf()" in JS, "descargarPdf sigue existiendo")
check("function exportarCSV()" in JS, "exportarCSV sigue existiendo")


print()
print("B. Ejecución real (vía node): las dos condiciones del botón")
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
        extraer_funcion("botonRibbon") + "\n" +
        extraer_funcion("botonDescargaDxfRellenoHtml") + "\n"
        r"""
        var resultados = [];
        function afirma(cond, etiqueta) { resultados.push([cond, etiqueta]); }

        // Caso 1: sin datos en absoluto -> nada.
        state = {};
        afirma(botonDescargaDxfRellenoHtml() === "", "sin state.data -> string vacío");

        // Caso 2: cuadro detectado, pero SIN archivo en memoria (proyecto
        // reabierto de la lista) -> tampoco debe aparecer.
        state = { data: { proyecto: { cuadro_superficies_detectado: true } }, archivoAnalizado: null };
        afirma(botonDescargaDxfRellenoHtml() === "",
               "cuadro_superficies_detectado=true PERO sin archivoAnalizado -> string vacío");

        // Caso 3: archivo en memoria, pero SIN cuadro detectado -> tampoco.
        state = { data: { proyecto: { cuadro_superficies_detectado: false } }, archivoAnalizado: {name: "x.dxf"} };
        afirma(botonDescargaDxfRellenoHtml() === "",
               "archivoAnalizado presente PERO cuadro_superficies_detectado=false -> string vacío");

        // Caso 4: las dos condiciones a la vez -> SÍ aparece el botón.
        state = { data: { proyecto: { cuadro_superficies_detectado: true } }, archivoAnalizado: {name: "v2s.dxf"} };
        var html = botonDescargaDxfRellenoHtml();
        afirma(html.length > 0, "las dos condiciones a la vez -> el botón SÍ aparece");
        afirma(html.indexOf("Descargar DXF rellenado") !== -1, "con el texto correcto");
        afirma(html.indexOf('data-accion="exportar-dxf-relleno"') !== -1, "y el data-accion correcto");

        var falla = resultados.filter(function (r) { return !r[0]; });
        resultados.forEach(function (r) {
          console.log((r[0] ? "OK  " : "FALLO") + " " + r[1]);
        });
        process.exit(falla.length ? 1 : 0);
        """
    )
    tmp_js = os.path.join(RAIZ, "tests", "_tmp_exportar_dxf_harness.js")
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
