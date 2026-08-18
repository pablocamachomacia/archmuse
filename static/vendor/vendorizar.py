# -*- coding: utf-8 -*-
"""Descarga las dependencias de terceros del frontend a `static/vendor/`.

    python static/vendor/vendorizar.py            # descarga lo que falte
    python static/vendor/vendorizar.py --forzar   # vuelve a descargar todo
    python static/vendor/vendorizar.py --verificar # solo comprueba el manifiesto

**Por qué existe** (tarea 20 del `REFACTOR_MASTERPLAN.md`). Hasta el
2026-08-18 el frontend cargaba en tiempo de ejecución, desde CDN de terceros,
todo el código del visor 3D y del mapa: `three.js` y `leaflet` de unpkg.com,
`mapbox-gl` de api.mapbox.com, y `threebox` de **una etiqueta de un
repositorio personal de GitHub** servida por jsDelivr. Eso son dos problemas
distintos, y el segundo es el grave:

1. **Disponibilidad.** Si la CDN está caída, el visor 3D no arranca. Justo en
   la demo.
2. **Ejecución de código.** Un `<script src>` de tercero ejecuta lo que ese
   tercero decida servir, con acceso completo a la página. Una etiqueta de git
   se puede mover; un paquete de npm se puede republicar. No hay `integrity`
   en ninguna de esas cargas, así que tampoco había nada que lo detectara.

Vendorizar cierra los dos. Lo que este script NO puede cerrar son los
servicios: las teselas de `api.mapbox.com` y de `server.arcgisonline.com` son
el servicio en sí, no una librería, y siguen siendo peticiones de red en tiempo
de ejecución por definición.

**Cómo se resuelve el grafo de `three`.** No se baja el paquete entero (los
`examples/jsm` pesan decenas de MB). Se parte de los 7 módulos que el
frontend importa de verdad y se sigue cada `import`/`export ... from` relativo
hasta cerrar el grafo. Así lo vendorizado es exactamente lo que se ejecuta, y
si mañana alguien añade un addon nuevo el script lo trae solo.

**El manifiesto no es decorativo.** `MANIFEST.json` guarda el sha256 y el
tamaño de cada fichero descargado, junto a la URL de origen. `--verificar` los
recomprueba, y `tests/test_vendor_frontend.py` lo ejecuta en la suite: si un
fichero vendorizado cambia sin que cambie el manifiesto, salta. Es la parte que
hace que esto siga siendo auditable dentro de un año.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

DIR_VENDOR = Path(__file__).resolve().parent
MANIFIESTO = DIR_VENDOR / "MANIFEST.json"

TIMEOUT_S = 60

# Un User-Agent de navegador es obligatorio para Google Fonts: con el de
# urllib devuelve `.ttf` (compatibilidad con navegadores viejos) en vez de
# `.woff2`, que es lo que el CSS de producción referencia.
UA_NAVEGADOR = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

VERSION_THREE = "0.160.0"
VERSION_LEAFLET = "1.9.4"
VERSION_MAPBOX_GL = "3.28.1"
VERSION_THREEBOX = "v.2.2.2"

BASE_THREE = "https://unpkg.com/three@%s/" % VERSION_THREE

# Los módulos de `three/addons/` que importa `static/*.js`. El resto del grafo
# se descubre solo.
ADDONS_THREE = (
    "examples/jsm/controls/OrbitControls.js",
    "examples/jsm/environments/RoomEnvironment.js",
    "examples/jsm/postprocessing/EffectComposer.js",
    "examples/jsm/postprocessing/RenderPass.js",
    "examples/jsm/postprocessing/SSAOPass.js",
    "examples/jsm/postprocessing/UnrealBloomPass.js",
    "examples/jsm/postprocessing/OutputPass.js",
)

# (url, ruta relativa dentro de static/vendor/) de lo que no es un grafo ESM.
SUELTOS: Tuple[Tuple[str, str], ...] = (
    ("https://unpkg.com/leaflet@%s/dist/leaflet.js" % VERSION_LEAFLET,
     "leaflet/%s/leaflet.js" % VERSION_LEAFLET),
    ("https://unpkg.com/leaflet@%s/dist/leaflet.css" % VERSION_LEAFLET,
     "leaflet/%s/leaflet.css" % VERSION_LEAFLET),
    ("https://api.mapbox.com/mapbox-gl-js/v%s/mapbox-gl.js" % VERSION_MAPBOX_GL,
     "mapbox-gl/%s/mapbox-gl.js" % VERSION_MAPBOX_GL),
    ("https://api.mapbox.com/mapbox-gl-js/v%s/mapbox-gl.css" % VERSION_MAPBOX_GL,
     "mapbox-gl/%s/mapbox-gl.css" % VERSION_MAPBOX_GL),
    ("https://cdn.jsdelivr.net/gh/jscastro76/threebox@%s/dist/threebox.min.js" % VERSION_THREEBOX,
     "threebox/%s/threebox.min.js" % VERSION_THREEBOX),
    ("https://cdn.jsdelivr.net/gh/jscastro76/threebox@%s/dist/threebox.css" % VERSION_THREEBOX,
     "threebox/%s/threebox.css" % VERSION_THREEBOX),
)

# La familia que `static/index.html` pedía a Google Fonts.
CSS_FUENTES = "https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700&display=swap"
DIR_FUENTES = "fuentes"

# `url(...)` de un CSS, sin comillas ni data: URI.
_URL_CSS = re.compile(r"url\(\s*['\"]?(?!data:)([^'\")]+?)['\"]?\s*\)")

# `from "..."` / `import "..."` de un módulo ESM.
_IMPORT_ESM = re.compile(
    r"""(?:^|\s)(?:import|export)\b[^;'"]*?['"]([^'"]+)['"]""", re.M | re.S
)


def _descargar(url: str) -> bytes:
    peticion = urllib.request.Request(url, headers={"User-Agent": UA_NAVEGADOR})
    with urllib.request.urlopen(peticion, timeout=TIMEOUT_S) as respuesta:
        return respuesta.read()


def _escribir(relativa: str, datos: bytes) -> None:
    destino = DIR_VENDOR / relativa
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(datos)


def _sha(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _resolver_grafo_esm(base: str, entradas: List[str]) -> Dict[str, str]:
    """{ruta relativa al paquete: url} de todo el grafo alcanzable.

    Los imports desnudos (`"three"`) NO se siguen: los resuelve el import map
    del navegador contra `build/three.module.js`, que ya está en las entradas.
    """
    pendientes = list(entradas)
    vistos: Dict[str, str] = {}
    while pendientes:
        ruta = pendientes.pop()
        if ruta in vistos:
            continue
        url = base + ruta
        try:
            datos = _descargar(url)
        except urllib.error.HTTPError as exc:
            raise SystemExit("no se pudo descargar %s: %s" % (url, exc))
        vistos[ruta] = url
        texto = datos.decode("utf-8", errors="replace")
        for destino in _IMPORT_ESM.findall(texto):
            if not destino.startswith("."):
                continue  # import desnudo: lo resuelve el import map
            pendientes.append(posixpath.normpath(posixpath.join(posixpath.dirname(ruta), destino)))
    return vistos


def _vendorizar_three(manifiesto: dict, forzar: bool) -> None:
    entradas = ["build/three.module.js"] + list(ADDONS_THREE)
    print("three %s: resolviendo el grafo de imports..." % VERSION_THREE)
    grafo = _resolver_grafo_esm(BASE_THREE, entradas)
    print("  %d modulos alcanzables desde los %d puntos de entrada"
          % (len(grafo), len(entradas)))
    for ruta, url in sorted(grafo.items()):
        relativa = "three/%s/%s" % (VERSION_THREE, ruta)
        _registrar(manifiesto, relativa, url, forzar)


def _vendorizar_sueltos(manifiesto: dict, forzar: bool) -> None:
    for url, relativa in SUELTOS:
        datos = _registrar(manifiesto, relativa, url, forzar)
        if not relativa.endswith(".css"):
            continue
        # Un CSS puede arrastrar imagenes (leaflet lo hace: marker-icon.png y
        # compania). Se traen junto a el, con su misma ruta relativa.
        texto = datos.decode("utf-8", errors="replace")
        base_url = url.rsplit("/", 1)[0] + "/"
        base_rel = relativa.rsplit("/", 1)[0] + "/"
        for referencia in sorted(set(_URL_CSS.findall(texto))):
            # `%23clip` es un `#clip`: `mapbox-gl.css` referencia asi fragmentos
            # SVG internos. No es un fichero, y pedirlo devuelve un 404.
            suelta = urllib.parse.unquote(referencia)
            if suelta.startswith(("http://", "https://", "//", "#")):
                continue
            limpia = suelta.split("?")[0].split("#")[0]
            if not limpia:
                continue
            _registrar(manifiesto,
                       posixpath.normpath(base_rel + limpia),
                       urllib.parse.urljoin(base_url, limpia),
                       forzar)


def _vendorizar_fuentes(manifiesto: dict, forzar: bool) -> None:
    """El CSS de Google Fonts, con sus woff2 traidos y las URLs reescritas."""
    print("fuentes: descargando la hoja de Google Fonts...")
    css = _descargar(CSS_FUENTES).decode("utf-8")
    ficheros: Dict[str, str] = {}
    for url in sorted(set(_URL_CSS.findall(css))):
        if not url.startswith("https://fonts.gstatic.com/"):
            raise SystemExit("URL de fuente inesperada, revisar a mano: %s" % url)
        nombre = url.rsplit("/", 2)
        nombre = "%s-%s" % (nombre[-2], nombre[-1])  # hash de Google + fichero
        ficheros[url] = nombre
        _registrar(manifiesto, "%s/%s" % (DIR_FUENTES, nombre), url, forzar)
    for url, nombre in ficheros.items():
        css = css.replace(url, nombre)
    datos = css.encode("utf-8")
    relativa = "%s/inter.css" % DIR_FUENTES
    _escribir(relativa, datos)
    manifiesto["ficheros"][relativa] = {
        "origen": CSS_FUENTES + "  (URLs de gstatic reescritas a locales)",
        "sha256": _sha(datos),
        "bytes": len(datos),
    }
    print("  [OK] %s (%d bytes, %d fuentes locales)" % (relativa, len(datos), len(ficheros)))


def _registrar(manifiesto: dict, relativa: str, url: str, forzar: bool) -> bytes:
    destino = DIR_VENDOR / relativa
    if destino.is_file() and not forzar:
        datos = destino.read_bytes()
        manifiesto["ficheros"].setdefault(relativa, {
            "origen": url, "sha256": _sha(datos), "bytes": len(datos)})
        return datos
    datos = _descargar(url)
    _escribir(relativa, datos)
    manifiesto["ficheros"][relativa] = {
        "origen": url, "sha256": _sha(datos), "bytes": len(datos)}
    print("  [OK] %s (%d bytes)" % (relativa, len(datos)))
    return datos


def verificar() -> int:
    if not MANIFIESTO.is_file():
        print("no existe %s. Ejecuta el script sin --verificar." % MANIFIESTO)
        return 1
    manifiesto = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    problemas = []
    for relativa, esperado in sorted(manifiesto["ficheros"].items()):
        ruta = DIR_VENDOR / relativa
        if not ruta.is_file():
            problemas.append("%s: FALTA" % relativa)
            continue
        datos = ruta.read_bytes()
        if _sha(datos) != esperado["sha256"]:
            problemas.append("%s: sha256 distinto del manifiesto" % relativa)
    total = sum(f["bytes"] for f in manifiesto["ficheros"].values())
    print("%d ficheros, %.1f MB" % (len(manifiesto["ficheros"]), total / 1e6))
    if problemas:
        print("PROBLEMAS (%d):" % len(problemas))
        for p in problemas:
            print("  %s" % p)
        return 1
    print("Todos coinciden con el manifiesto.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--forzar", action="store_true",
                        help="vuelve a descargar aunque el fichero ya exista")
    parser.add_argument("--verificar", action="store_true",
                        help="solo comprueba el sha256 de lo ya descargado")
    args = parser.parse_args()

    if args.verificar:
        return verificar()

    manifiesto = {"ficheros": {}, "versiones": {
        "three": VERSION_THREE, "leaflet": VERSION_LEAFLET,
        "mapbox-gl": VERSION_MAPBOX_GL, "threebox": VERSION_THREEBOX,
    }}
    _vendorizar_three(manifiesto, args.forzar)
    print("librerias sueltas:")
    _vendorizar_sueltos(manifiesto, args.forzar)
    _vendorizar_fuentes(manifiesto, args.forzar)

    MANIFIESTO.write_text(
        json.dumps(manifiesto, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    total = sum(f["bytes"] for f in manifiesto["ficheros"].values())
    print("\n%d ficheros, %.1f MB. Manifiesto en %s"
          % (len(manifiesto["ficheros"]), total / 1e6, MANIFIESTO.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
