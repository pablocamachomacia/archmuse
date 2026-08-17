# -*- coding: utf-8 -*-
"""Pestaña "Hechos" (CAP-1..5) y bloque de edificio en `static/app.js`.

Ejecutar:  python tests/test_ui_hechos.py

Rapido (<2 s): lectura de fuente + ejecucion real de las funciones puras
via `node` (ya presente en el sistema, no se instala nada nuevo, no es
Jest/Playwright). Sin Flask, sin DXF.

Que protege, PRD "Tabla de hechos CAP-1..5" (2026-08-14):

1. `avisos_evacuacion` NUNCA entra en `buildUnifiedProblems` -- el riesgo
   central del PRD (§5): que un aviso informativo se lea como un
   incumplimiento porque comparte el pipeline de `issues`/"Problemas".
2. `hechoConfianzaHtml(null)` no genera ningun texto de confianza.
3. El badge de UNKNOWN nunca usa la tinta de severidad CRITICO, ni en JS
   ni en CSS -- verificado en las dos capas por separado.
4. `hechoExplicacionHtml` no duplica el texto cuando `motivo === explicacion`.
5. La pestaña "Hechos" existe y es distinta de "Normativa" (que sigue
   apuntando a `toolNormativaHtml`, la regla LOE, sin tocar).
"""
import os
import re
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_JS = os.path.join(RAIZ, "static", "app.js")
STYLE_CSS = os.path.join(RAIZ, "static", "style.css")

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

with open(STYLE_CSS, encoding="utf-8") as f:
    CSS = f.read()


# ---------------------------------------------------------------------------
# Extraccion de funciones de nivel superior por rango de linea: `app.js`
# declara todas sus funciones como `\n  function nombre(...) {` con 2
# espacios de indentacion -- no hace falta un parser JS, basta con
# localizar el siguiente `\n  function ` para saber donde termina cada una.
# ---------------------------------------------------------------------------
_FUNC_DECL = re.compile(r"\n  function\s+([A-Za-z0-9_]+)\s*\(")


def extraer_funcion(nombre):
    posiciones = [(m.start(), m.group(1)) for m in _FUNC_DECL.finditer(JS)]
    for i, (inicio, nom) in enumerate(posiciones):
        if nom == nombre:
            fin = posiciones[i + 1][0] if i + 1 < len(posiciones) else len(JS)
            return JS[inicio:fin]
    raise AssertionError("no se encuentra function %s en app.js" % nombre)


def extraer_var(nombre):
    m = re.search(r"\n  var\s+" + re.escape(nombre) + r"\s*=\s*\{.*?\};", JS, re.S)
    if not m:
        raise AssertionError("no se encuentra var %s en app.js" % nombre)
    return m.group(0)


print()
print("A. `avisos_evacuacion` nunca entra en el pipeline de Problemas")
print("-" * 68)

fuente_unificado = extraer_funcion("buildUnifiedProblems")
check("avisos_evacuacion" not in fuente_unificado,
      "buildUnifiedProblems no lee proyecto.avisos_evacuacion")
check("altura_evacuacion" not in fuente_unificado,
      "buildUnifiedProblems no lee proyecto.altura_evacuacion")

fuente_avisos = extraer_funcion("avisosEvacuacionListHtml")
check("severity" not in fuente_avisos and "severidad" not in fuente_avisos,
      "avisosEvacuacionListHtml no asigna ninguna severidad")
check("CRITICO" not in fuente_avisos and "IMPORTANTE" not in fuente_avisos,
      "avisosEvacuacionListHtml no usa ninguna etiqueta de severidad CTE")

fuente_edificio = extraer_funcion("hechosEdificioHtml")
check("issues" not in fuente_edificio and "problemas" not in fuente_edificio.lower(),
      "hechosEdificioHtml no toca la lista de issues/problemas")


print()
print("B. Badge de UNKNOWN: nunca la tinta de CRITICO, ni en JS ni en CSS")
print("-" * 68)

fuente_badge = extraer_funcion("hechoBadgeHtml")
check("color-critical" not in fuente_badge, "hechoBadgeHtml no referencia --color-critical")

m_css = re.search(r"\.hecho-badge-unknown\s*\{([^}]*)\}", CSS)
check(m_css is not None, "existe la regla CSS .hecho-badge-unknown")
if m_css:
    cuerpo_css = m_css.group(1)
    check("--color-critical" not in cuerpo_css,
          "la regla CSS de UNKNOWN no usa --color-critical", cuerpo_css.strip())
    check("--text-tertiary" in cuerpo_css,
          "la regla CSS de UNKNOWN usa el tono neutro --text-tertiary")


print()
print("C. Pestaña 'Hechos' existe y es distinta de 'Normativa'")
print("-" * 68)

check('{ id: "hechos", label: "Hechos" }' in JS, "PLAN_MODES incluye la pestaña Hechos")
check('{ id: "normativa", label: "Normativa" }' in JS,
      "PLAN_MODES conserva Normativa sin tocar (no se fusionan)")
check('if (state.modo === "hechos") return toolHechosHtml(v);' in JS,
      "inspectorModoHtml despacha 'hechos' a toolHechosHtml, no a toolNormativaHtml")

fuente_render_inspector = extraer_funcion("renderInspector")
check("fadeSwap(host" not in fuente_render_inspector,
      "renderInspector no deja el panel vacío durante la transición")
check("host.innerHTML = inspectorModoHtml(v);" in fuente_render_inspector,
      "renderInspector pinta el contenido del modo inmediatamente")


print()
print("C-bis. Cambiar de vivienda desactiva el resaltado de 'Hechos' (regresion)")
print("-" * 68)

# Bug real encontrado al verificar visualmente: `selectVivienda` SI volvia
# state.modo a "resumen" al cambiar de vivienda (correcto), pero el
# `forEach` que debia quitar el resaltado visual del boton de modo
# anterior (p. ej. "Hechos") usaba un selector muerto (`.plan-mode`, de la
# barra de modos que el propio `style.css` ya documenta como eliminada) en
# vez de `.cad-ribbon-btn`, el que de verdad usan los botones del ribbon
# (ver `setModo`, unas lineas mas arriba en el propio archivo). Resultado:
# "Hechos" se quedaba marcado como activo aunque el panel ya mostrara
# Resumen -- el usuario pulsaba una vivienda distinta y el area de
# "Hechos" parecia vacia/incorrecta sin haber tocado esa pestaña.
fuente_select = extraer_funcion("selectVivienda")
check('querySelectorAll(".plan-mode' not in fuente_select,
      "selectVivienda ya no usa el selector muerto .plan-mode (el string solo vive en el comentario explicativo)")
check('.cad-ribbon-btn[data-modo]' in fuente_select,
      "selectVivienda usa el mismo selector que setModo (.cad-ribbon-btn[data-modo])")
check('classList.toggle("is-activa"' in fuente_select,
      "selectVivienda usa la misma clase que setModo (is-activa, no 'active')")


print()
print("D. Ejecucion real de las funciones puras (via node, sin Jest/Playwright)")
print("-" * 68)

node_disponible = True
try:
    subprocess.run(["node", "--version"], capture_output=True, check=True)
except (FileNotFoundError, subprocess.CalledProcessError):
    node_disponible = False

if not node_disponible:
    check(False, "node esta disponible en el sistema (necesario para esta seccion)")
else:
    harness = (
        extraer_var("HECHO_ESTADO_LABEL") + "\n" +
        extraer_var("HECHO_ESTADO_CLASE") + "\n" +
        extraer_funcion("escapeHtml") + "\n" +
        extraer_funcion("hechoBadgeHtml") + "\n" +
        extraer_funcion("hechoConfianzaHtml") + "\n" +
        extraer_funcion("hechoExplicacionHtml") + "\n"
        r"""
        var assert = require('assert');
        var resultados = [];
        function afirma(cond, etiqueta) { resultados.push([cond, etiqueta]); }

        // confianza: null -> ningun texto de confianza (PRD, criterio explicito)
        afirma(hechoConfianzaHtml(null) === "", "confianza null -> string vacio");
        afirma(hechoConfianzaHtml(undefined) === "", "confianza undefined -> string vacio");
        afirma(hechoConfianzaHtml("Alta").indexOf("Alta") !== -1, "confianza Alta se muestra");

        // badge UNKNOWN: etiqueta neutra, clase neutra, nunca 'critical'
        var bUnknown = hechoBadgeHtml("UNKNOWN");
        afirma(bUnknown.indexOf("hecho-badge-unknown") !== -1, "UNKNOWN usa la clase neutra");
        afirma(bUnknown.indexOf("No determinado") !== -1, "UNKNOWN se etiqueta 'No determinado'");
        afirma(bUnknown.toLowerCase().indexOf("critical") === -1, "UNKNOWN no menciona 'critical'");

        var bKnown = hechoBadgeHtml("KNOWN");
        afirma(bKnown.indexOf("hecho-badge-known") !== -1, "KNOWN usa su propia clase");
        var bEst = hechoBadgeHtml("ESTIMATED");
        afirma(bEst.indexOf("hecho-badge-estimated") !== -1, "ESTIMATED usa su propia clase");

        // explicacion/motivo: no se duplica cuando son el mismo texto
        var mismos = hechoExplicacionHtml("mismo texto", "mismo texto");
        var apariciones = mismos.split("mismo texto").length - 1;
        afirma(apariciones === 1, "motivo == explicacion -> se muestra una sola vez, no dos");

        var distintos = hechoExplicacionHtml("explicacion X", "motivo Y");
        afirma(distintos.indexOf("explicacion X") !== -1 && distintos.indexOf("motivo Y") !== -1,
               "motivo != explicacion -> se muestran los dos");

        var sinMotivo = hechoExplicacionHtml("solo explicacion", null);
        afirma(sinMotivo.indexOf("solo explicacion") !== -1 && sinMotivo.indexOf("hecho-motivo") === -1,
               "motivo null -> no se pinta ninguna linea de motivo");

        var falla = resultados.filter(function (r) { return !r[0]; });
        resultados.forEach(function (r) {
          console.log((r[0] ? "OK  " : "FALLO") + " " + r[1]);
        });
        process.exit(falla.length ? 1 : 0);
        """
    )
    with open(os.path.join(RAIZ, "tests", "_tmp_hechos_harness.js"), "w", encoding="utf-8") as f:
        f.write(harness)
    try:
        proc = subprocess.run(
            ["node", os.path.join(RAIZ, "tests", "_tmp_hechos_harness.js")],
            capture_output=True, text=True,
        )
        for linea in proc.stdout.splitlines():
            print("  [node] " + linea)
        if proc.stderr.strip():
            print("  [node stderr] " + proc.stderr.strip())
        check(proc.returncode == 0, "todas las afirmaciones ejecutadas en node pasan")
    finally:
        try:
            os.remove(os.path.join(RAIZ, "tests", "_tmp_hechos_harness.js"))
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
