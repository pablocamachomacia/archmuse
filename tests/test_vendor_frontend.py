# -*- coding: utf-8 -*-
"""Tarea 20 — el frontend no carga código de terceros en tiempo de ejecución.

Ejecutar:  pytest tests/test_vendor_frontend.py

Hasta el 2026-08-18 el navegador del arquitecto se bajaba `three.js` y
`leaflet` de unpkg.com, `mapbox-gl` de api.mapbox.com y `threebox` de una
**etiqueta de git de un repositorio personal** servida por jsDelivr, sin
`integrity` en ninguna. Eso es una CDN caída = visor 3D que no arranca, y
—peor— cuatro terceros con permiso para ejecutar lo que quieran dentro de la
página.

Los tres test de aquí vigilan las tres cosas que pueden deshacerlo:

1. Que no vuelva a aparecer una carga remota en `static/`.
2. Que lo vendorizado siga siendo lo que se vendorizó (sha256 del manifiesto).
3. Que Flask sirva de verdad cada ruta `/vendor/...` que el HTML pide — un
   `404` deja el visor tan roto como una CDN caída, solo que sin excusa.

**Lo que NO se puede vendorizar, y por eso está en la lista blanca:** las
teselas de `server.arcgisonline.com` y los estilos/teselas de `api.mapbox.com`
son el servicio, no una librería. Se piden en tiempo de ejecución por
definición. La diferencia con lo anterior es que una tesela es un PNG que se
pinta, no un `<script>` que se ejecuta.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

DIR_STATIC = RAIZ / "static"
DIR_VENDOR = DIR_STATIC / "vendor"
MANIFIESTO = DIR_VENDOR / "MANIFEST.json"

# Servicios, no librerías: se piden en ejecución porque son el producto que se
# consume. Cualquier host NUEVO que aparezca aquí tiene que justificarse.
HOSTS_DE_SERVICIO = (
    "server.arcgisonline.com",  # teselas de ortofoto
    "api.mapbox.com",           # estilos y teselas de Mapbox
)

# Ficheros de `static/` que el navegador ejecuta o interpreta. `vendor/` queda
# fuera: son las librerías ya traídas, y sus comentarios están llenos de URLs
# de documentación que no son cargas.
def _fuentes_propias():
    for ruta in sorted(DIR_STATIC.rglob("*")):
        if ruta.is_dir() or DIR_VENDOR in ruta.parents or ruta == DIR_VENDOR:
            continue
        if ruta.suffix in (".html", ".js", ".css"):
            yield ruta


_CARGA_REMOTA = re.compile(
    r"""["'](https?://[^"']+)["']"""
)


def test_static_no_carga_nada_remoto():
    """Ninguna URL absoluta en el código propio, salvo los dos servicios."""
    culpables = []
    for ruta in _fuentes_propias():
        texto = ruta.read_text(encoding="utf-8", errors="replace")
        # Fuera comentarios de línea: explicar de dónde SALIÓ algo está bien.
        codigo = re.sub(r"^\s*(//|\*|<!--).*$", "", texto, flags=re.M)
        for url in _CARGA_REMOTA.findall(codigo):
            if any(host in url for host in HOSTS_DE_SERVICIO):
                continue
            if "www.w3.org" in url:  # espacios de nombres de SVG/XML
                continue
            culpables.append("%s: %s" % (ruta.relative_to(RAIZ).as_posix(), url))
    assert not culpables, (
        "el frontend ha vuelto a cargar de un tercero. Vendorizalo con "
        "`python static/vendor/vendorizar.py` y apunta a /vendor/...:\n  "
        + "\n  ".join(culpables)
    )


def test_lo_vendorizado_es_lo_que_dice_el_manifiesto():
    """sha256 de cada fichero contra `MANIFEST.json`.

    Sin esto, vendorizar solo cambia de quién te fías: de unpkg a quien pueda
    escribir en `static/vendor/`. El manifiesto hace que ese cambio se note.
    """
    assert MANIFIESTO.is_file(), "falta static/vendor/MANIFEST.json"
    manifiesto = json.loads(MANIFIESTO.read_text(encoding="utf-8"))

    problemas = []
    for relativa, esperado in sorted(manifiesto["ficheros"].items()):
        ruta = DIR_VENDOR / relativa
        if not ruta.is_file():
            problemas.append("%s: falta el fichero" % relativa)
            continue
        real = hashlib.sha256(ruta.read_bytes()).hexdigest()
        if real != esperado["sha256"]:
            problemas.append("%s: sha256 %s, el manifiesto dice %s"
                             % (relativa, real[:16], esperado["sha256"][:16]))
    assert not problemas, "\n  ".join([""] + problemas)


def test_flask_sirve_cada_ruta_vendor_que_el_html_pide():
    """Un 404 aquí deja el visor tan roto como una CDN caída."""
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.setdefault("ARCHMUSE_DATA_DIR", tempfile.mkdtemp(prefix="archmuse_vendor_"))
    import app as app_module

    cliente = app_module.app.test_client()
    html = cliente.get("/").get_data(as_text=True)

    rutas = {r for r in re.findall(r'"(/vendor/[^"]+)"', html) if not r.endswith("/")}
    # El import map declara `three/addons/` como PREFIJO de carpeta, así que no
    # aparece ningún módulo concreto en el HTML. Se comprueba uno real: si el
    # prefijo estuviera mal, ningún addon cargaría.
    rutas.add("/vendor/three/0.160.0/examples/jsm/controls/OrbitControls.js")
    # Y lo que cargan los módulos JS, que tampoco está en el HTML.
    rutas.update("/vendor/" + p for p in (
        "leaflet/1.9.4/leaflet.js",
        "leaflet/1.9.4/leaflet.css",
        "leaflet/1.9.4/images/marker-icon.png",
        "mapbox-gl/3.28.1/mapbox-gl.js",
        "mapbox-gl/3.28.1/mapbox-gl.css",
        "threebox/v.2.2.2/threebox.min.js",
        "threebox/v.2.2.2/threebox.css",
        "fuentes/inter.css",
    ))

    assert rutas, "el HTML no pide ni una ruta /vendor/: el import map se ha perdido"

    malas = []
    for ruta in sorted(rutas):
        respuesta = cliente.get(ruta)
        if respuesta.status_code != 200 or not respuesta.get_data():
            malas.append("%s -> %d" % (ruta, respuesta.status_code))
    assert not malas, "\n  ".join([""] + malas)
