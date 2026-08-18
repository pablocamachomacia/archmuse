/* map-picker.js — "Mapa/Parcela Primero": mapa interactivo de clic-para-
 * seleccionar-parcela, reutilizado por `entrevista.js` (Paso 0 del flujo de
 * "Generar proyecto"). Script clásico (sin `type="module"`), igual que
 * `entrevista.js`/`app.js` -- NO puede ser un módulo ES porque expone su
 * API como global (`window.ArchmuseMapPicker`) para que `entrevista.js` la
 * llame igual que llama a `window.ArchmuseShell`.
 *
 * Deliberadamente Leaflet + OpenStreetMap, NO Mapbox/Threebox (a
 * diferencia de `visor-mapa.js`, que sí usa Mapbox): este entorno de
 * desarrollo no tiene `MAPBOX_TOKEN` configurado (confirmado en vivo con
 * `GET /api/config` en una fase anterior de esta sesión -- devuelve
 * `mapbox_token: null`), así que un picker con Mapbox no se podría probar
 * de verdad aquí. Leaflet + tiles de OSM no necesitan ninguna clave y son
 * genuinamente verificables en este entorno.
 *
 * Por qué el mapa vive en su PROPIO módulo y no como HTML dentro de
 * `entrevista.js`: `entrevista.js` repinta la pantalla entera
 * (`viewRoot.innerHTML = ...`) en cada cambio de estado -- un mapa Leaflet
 * es una instancia con estado real (tiles cargados, listeners internos)
 * que NO sobrevive a que se destruya y reconstruya su contenedor desde una
 * cadena de texto. Por eso `montar()` se llama UNA sola vez por pantalla
 * (`wireParcelaInicial()`), sobre un contenedor que a partir de ahí nunca
 * vuelve a pasar por `innerHTML` -- el resto de la pantalla (resultados de
 * búsqueda, estado de la consulta a Catastro) se actualiza aparte, con DOM
 * directo, precisamente para no arrastrar el mapa por delante. */
(function () {
  "use strict";

  // Servido desde el propio origen (tarea 20 del REFACTOR_MASTERPLAN). Antes
  // venia de unpkg.com. `leaflet.css` referencia sus iconos con rutas
  // relativas (`images/marker-icon.png`), asi que la carpeta `images/` tiene
  // que seguir colgando del mismo sitio que el CSS.
  var LEAFLET_JS = "/vendor/leaflet/1.9.4/leaflet.js";
  var LEAFLET_CSS = "/vendor/leaflet/1.9.4/leaflet.css";

  // Centro por defecto (Madrid) -- solo para que el mapa no arranque
  // centrado en el punto (0,0) del Atlántico cuando no hay ninguna pista de
  // dónde está el usuario. Nunca se usa como si fuera un dato real de la
  // parcela.
  var LAT_DEFECTO = 40.4168;
  var LON_DEFECTO = -3.7038;
  var ZOOM_DEFECTO = 6;
  var ZOOM_CON_PUNTO_INICIAL = 17;
  var ZOOM_AL_SELECCIONAR = 18;

  var promesaLeaflet = null;

  function cargarLeaflet() {
    if (window.L) return Promise.resolve(window.L);
    if (promesaLeaflet) return promesaLeaflet;
    promesaLeaflet = new Promise(function (resolve, reject) {
      if (!document.querySelector("link[data-archmuse-leaflet-css]")) {
        var link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = LEAFLET_CSS;
        link.setAttribute("data-archmuse-leaflet-css", "1");
        document.head.appendChild(link);
      }
      var script = document.createElement("script");
      script.src = LEAFLET_JS;
      script.onload = function () {
        if (window.L) resolve(window.L);
        else reject(new Error("Leaflet se cargó pero window.L no está definido."));
      };
      script.onerror = function () {
        promesaLeaflet = null; // permite reintentar en una llamada futura, no queda atascado en un rechazo viejo
        reject(new Error("No se pudo cargar Leaflet desde el CDN (unpkg.com). Comprueba la conexión a internet."));
      };
      document.head.appendChild(script);
    });
    return promesaLeaflet;
  }

  /* Monta un mapa Leaflet dentro de `contenedorEl` (debe existir ya en el
   * DOM, con una altura CSS explícita -- Leaflet no calcula tamaño de un
   * contenedor sin dimensiones). `opciones`:
   *   - latInicial/lonInicial: si se pasan, centra ahí y pone un marcador
   *     ya puesto (p. ej. al reabrir esta pantalla con una parcela ya
   *     elegida antes).
   *   - onClic(lat, lon): se llama cuando el usuario hace clic en el mapa
   *     (el marcador ya se ha movido/creado ANTES de llamar a onClic).
   *
   * Devuelve una Promise de un "handle" con `ponerMarcador`/`centrar`/
   * `destruir` -- asíncrono porque la primera vez tiene que esperar a que
   * el script de Leaflet termine de cargar del CDN. */
  // --- Capa base: satélite -----------------------------------------------
  // A petición explícita (2026-08-15): solo satélite, sin el toggle "Mapa"
  // (CartoDB Dark Matter) que había antes -- una imagen real de la parcela
  // es más útil aquí que un mapa vectorial, y quitar el toggle es parte de
  // "todo limpio y sin ruido". Imagen de Esri (sin etiquetas) + su capa de
  // referencia oficial (nombres de calle/ciudad) superpuesta, combinadas en
  // UN grupo -- URLs comprobadas en vivo (curl, 200 OK) antes de escribir
  // este código.
  function crearCapaSatelite(L) {
    var imagen = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { attribution: "Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community", maxZoom: 19 }
    );
    var etiquetas = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 19 }
    );
    return L.layerGroup([imagen, etiquetas]);
  }

  function montar(contenedorEl, opciones) {
    opciones = opciones || {};
    return cargarLeaflet().then(function (L) {
      var tieneInicial = opciones.latInicial != null && opciones.lonInicial != null;
      var mapa = L.map(contenedorEl, { zoomControl: false }).setView(
        [tieneInicial ? opciones.latInicial : LAT_DEFECTO, tieneInicial ? opciones.lonInicial : LON_DEFECTO],
        tieneInicial ? ZOOM_CON_PUNTO_INICIAL : ZOOM_DEFECTO
      );
      // Zoom control reubicado a "bottomright" a propósito: por defecto Leaflet lo pone en "topleft", donde
      // queda más cerca de donde ya mira el usuario tras hacer clic en el mapa, y lejos del buscador
      // flotante (arriba a la izquierda, ver `style.css:.parcela-buscador`).
      L.control.zoom({ position: "bottomright" }).addTo(mapa);

      crearCapaSatelite(L).addTo(mapa);

      // Cobertura total del contenedor (bug reportado en vivo, 2026-08-17: "franjas blancas o vacíos
      // en los laterales"): Leaflet mide el tamaño de `contenedorEl` en el instante SÍNCRONO de
      // `L.map(...)` -- si en ese instante el layout flex del contenedor (`.parcela-mapa-mount`,
      // `height: 100%` sobre una cadena de `flex: 1`) todavía no ha terminado de asentarse, o si la
      // hoja de Leaflet inyectada por `cargarLeaflet()` aún no ha aplicado sus reglas (`link` añadido
      // al `<head>` justo antes del `<script>`, sin esperar a su `load`), Leaflet calcula la rejilla de
      // baldosas sobre un tamaño equivocado y dedica el resto del contenedor a gris/blanco vacío hasta
      // el siguiente evento que dispare un recálculo interno. Tres llamadas a `invalidateSize()`, cada
      // una cubriendo una causa distinta: inmediata (por si ya medía bien y esto es un no-op), un
      // `requestAnimationFrame` (el layout ya asentado tras el primer frame real) y un resize de
      // ventana (el contenedor puede cambiar de tamaño después, con el sidebar colapsándose/expandiéndose).
      mapa.invalidateSize();
      requestAnimationFrame(function () { mapa.invalidateSize(); });
      var alRedimensionar = function () { mapa.invalidateSize(); };
      window.addEventListener("resize", alRedimensionar);

      var marcador = null;
      function ponerMarcador(lat, lon) {
        if (marcador) marcador.setLatLng([lat, lon]);
        else marcador = L.marker([lat, lon]).addTo(mapa);
      }
      if (tieneInicial) ponerMarcador(opciones.latInicial, opciones.lonInicial);

      // Contorno REAL de la parcela devuelto por Catastro (bug reportado en vivo: un clic solo dejaba un
      // punto, nunca la forma real de la parcela). `coordenadas` (opcional) llega como [[lon, lat], ...] --
      // mismo orden GeoJSON que devuelve `analyzer/sitio.py:_geometria_parcela_catastro` -- Leaflet quiere
      // [lat, lon], de ahí el intercambio. Pasar null/vacío borra el contorno anterior sin dibujar uno
      // nuevo (p. ej. al hacer clic en un punto nuevo mientras se resuelve, o si Catastro no encontró nada).
      var poligonoParcela = null;
      function dibujarParcela(coordenadas) {
        if (poligonoParcela) { mapa.removeLayer(poligonoParcela); poligonoParcela = null; }
        if (!coordenadas || !coordenadas.length) return;
        var anillo = coordenadas.map(function (c) { return [c[1], c[0]]; });
        poligonoParcela = L.polygon(anillo, { color: "#2e86de", weight: 2, fillColor: "#2e86de", fillOpacity: 0.18 }).addTo(mapa);
      }

      mapa.on("click", function (e) {
        ponerMarcador(e.latlng.lat, e.latlng.lng);
        if (opciones.onClic) opciones.onClic(e.latlng.lat, e.latlng.lng);
      });

      return {
        ponerMarcador: ponerMarcador,
        dibujarParcela: dibujarParcela,
        centrar: function (lat, lon, zoom) {
          ponerMarcador(lat, lon);
          mapa.setView([lat, lon], zoom || ZOOM_AL_SELECCIONAR);
        },
        destruir: function () {
          window.removeEventListener("resize", alRedimensionar);
          mapa.remove();
        },
      };
    });
  }

  window.ArchmuseMapPicker = { montar: montar };
})();
