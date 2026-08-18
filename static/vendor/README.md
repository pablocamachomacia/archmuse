# `static/vendor/` — librerías de terceros servidas desde el propio origen

Todo lo que hay aquí lo descarga `vendorizar.py`. **No se edita a mano.**

```bash
python static/vendor/vendorizar.py             # trae lo que falte
python static/vendor/vendorizar.py --forzar    # vuelve a bajarlo todo
python static/vendor/vendorizar.py --verificar # solo comprueba el manifiesto
```

## Qué hay y de dónde viene

| Carpeta | Versión | Origen | Quién lo usa |
|---|---|---|---|
| `three/` | 0.160.0 | unpkg.com | `viewer-edificio.js`, `viewer-vivienda.js`, `viewer-sandbox.js`, `visor-mapa.js` |
| `leaflet/` | 1.9.4 | unpkg.com | `map-picker.js` (selector de parcela) |
| `mapbox-gl/` | 3.28.1 | api.mapbox.com | `visor-mapa.js` |
| `threebox/` | v.2.2.2 | cdn.jsdelivr.net/**gh**/jscastro76 | `visor-mapa.js` |
| `fuentes/` | Inter (v20) | fonts.googleapis.com + fonts.gstatic.com | `index.html` |

De `three` **no está el paquete entero**: están los 16 módulos que el grafo de
`import` alcanza desde los 7 addons que el frontend usa de verdad
(`OrbitControls`, `RoomEnvironment` y los cinco de `postprocessing`). Añadir un
addon nuevo y volver a ejecutar el script trae lo que haga falta.

## Por qué (tarea 20 del `REFACTOR_MASTERPLAN.md`)

Dos problemas, y el segundo es el que importa:

1. **Disponibilidad.** Con la CDN caída, el visor 3D no arranca. Normalmente en
   la demo.
2. **Ejecución de código.** Un `<script src>` de un tercero ejecuta lo que ese
   tercero sirva, con acceso completo a la página, y ninguna de las cuatro
   cargas llevaba `integrity`. La peor con diferencia era **threebox**: se
   cargaba de `cdn.jsdelivr.net/gh/jscastro76/threebox@v.2.2.2`, es decir de
   una **etiqueta de git de un repositorio personal**. Una etiqueta se mueve.

## Lo que esto NO arregla

`server.arcgisonline.com` (teselas de ortofoto) y `api.mapbox.com` (estilos y
teselas) siguen siendo peticiones de red en tiempo de ejecución. No se pueden
vendorizar porque son **el servicio**, no una librería. La diferencia con lo
anterior es real de todos modos: una tesela es un PNG que se pinta, no un
script que se ejecuta.

## `MANIFEST.json`

sha256, tamaño y URL de origen de cada fichero.
`tests/test_vendor_frontend.py` lo comprueba en cada ejecución de la suite.
Sin él, vendorizar solo cambiaría de quién te fías —de unpkg a quien pueda
escribir en esta carpeta—; con él, ese cambio se nota.

## Cómo subir una versión

1. Cambia la constante `VERSION_*` en `vendorizar.py`.
2. `python static/vendor/vendorizar.py --forzar`.
3. Borra a mano la carpeta de la versión vieja.
4. Actualiza la ruta en quien la use (`index.html` para `three`,
   `map-picker.js` para leaflet; `visor-mapa.js` lee sus dos versiones de
   constantes propias, `MAPBOX_GL_VERSION` y `THREEBOX_VERSION`).
5. `pytest tests/test_vendor_frontend.py`, y abre el visor 3D a mano: ningún
   test automático comprueba que un shader siga compilando.
