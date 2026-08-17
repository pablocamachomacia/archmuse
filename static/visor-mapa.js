// Visor georreferenciado (Mapbox GL JS + Threebox) — 2026-08-15.
//
// ADVERTENCIA HONESTA, no un comentario de relleno: este archivo NUNCA se
// ha ejecutado en un navegador real. No hay `MAPBOX_TOKEN` disponible en
// este entorno de desarrollo, y esta sesión no tiene una herramienta de
// navegador activa para probarlo. Está construido sobre el ejemplo oficial
// y verificado de Mapbox para Threebox (docs.mapbox.com/mapbox-gl-js/
// example/add-3d-model-threebox/, comprobado el 2026-08-15 -- no adivinado
// de memoria), pero eso demuestra que la FORMA del código es correcta a
// fecha de hoy, no que este archivo concreto funcione. Antes de confiar en
// él: probarlo con un MAPBOX_TOKEN real y un navegador real.
//
// Convención de nombre: `static/visor-mapa.js`, no `static/js/visor_mapa.js`
// como sugería el encargo -- este proyecto no tiene subcarpeta `js/` bajo
// `static/` (todo vive plano: `app.js`, `entrevista.js`, `viewer-*.js`);
// crear una carpeta nueva para un solo archivo habría roto esa convención
// sin ningún beneficio real.
//
// Mismo patrón de módulo aislado que `viewer-edificio.js`: expone
// funciones públicas (`abrirVisorMapa`, y desde el Paso 3.2 nada más
// nuevo se añade al scope global), nada más se filtra. Nadie llama a estas
// funciones todavía -- ningún botón de `static/app.js` está cableado a
// ellas (fuera del alcance de este encargo; el propio módulo es lo que se
// pidió).
//
// Paso 3.2 (2026-08-15) añade: slider de sol (`static/solar-posicion.js`,
// SÍ verificado con Node — ver `tests/test_solar_posicion.mjs`, la única
// pieza de este archivo que se ha podido probar de verdad) conectado a la
// luz de Threebox y al cielo de Mapbox; y "Vista desde ventana", construida
// sobre `FreeCameraOptions` de Mapbox GL JS (docs.mapbox.com/mapbox-gl-js/
// example/free-camera-point/, comprobado hoy) y `enableSelectingObjects`/
// evento `SelectedChange` de Threebox (github.com/jscastro76/threebox/
// blob/master/docs/Threebox.md, comprobado hoy) -- ninguna de las dos
// verificaciones sustituye probarlo en un navegador real, que sigue sin
// hacerse.

import { posicionSolar } from "./solar-posicion.js";

const MAPBOX_GL_VERSION = "3.28.1";
const THREEBOX_VERSION = "v.2.2.2";
const METROS_POR_GRADO_LAT = 111320; // aproximación esférica -- de sobra para el radio de un edificio

let _mapboxCargado = null;

function _cargarCss(href) {
  if (document.querySelector('link[href="' + href + '"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
}

function _cargarScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector('script[src="' + src + '"]')) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("No se pudo cargar " + src));
    document.head.appendChild(script);
  });
}

// CDN, no vendorizado -- mismo criterio (y la misma deuda ya conocida,
// REFACTOR_MASTERPLAN #20) que three.js en `viewer-edificio.js`. Cargar
// Mapbox GL JS + Threebox es la SEGUNDA dependencia de CDN del proyecto,
// no la primera -- ver la nota de riesgo en
// `docs/prd/2026-08-15-exportacion-gltf-visor-mapbox.md` §9.
function _asegurarMapboxCargado() {
  if (_mapboxCargado) return _mapboxCargado;
  _cargarCss("https://api.mapbox.com/mapbox-gl-js/v" + MAPBOX_GL_VERSION + "/mapbox-gl.css");
  _cargarCss(
    "https://cdn.jsdelivr.net/gh/jscastro76/threebox@" + THREEBOX_VERSION + "/dist/threebox.css"
  );
  _mapboxCargado = _cargarScript(
    "https://api.mapbox.com/mapbox-gl-js/v" + MAPBOX_GL_VERSION + "/mapbox-gl.js"
  ).then(() =>
    _cargarScript(
      "https://cdn.jsdelivr.net/gh/jscastro76/threebox@" + THREEBOX_VERSION + "/dist/threebox.min.js"
    )
  );
  return _mapboxCargado;
}

// El token de Mapbox es público por diseño (se restringe por URL desde el
// panel de Mapbox, no es un secreto de servidor) -- pero como `index.html`
// es un archivo estático sin renderizado de plantillas (`app.py`: "Flask no
// renderiza HTML -- solo sirve el archivo estático"), no hay forma de
// inyectarlo al servir la página. `GET /api/config` (añadido con este
// visor, no pedido explícitamente pero necesario para que el token
// llegue al navegador desde `MAPBOX_TOKEN` del entorno) se lee aquí.
async function _obtenerMapboxToken() {
  const resp = await fetch("/api/config");
  if (!resp.ok) throw new Error("No se pudo leer /api/config");
  const datos = await resp.json();
  if (!datos.mapbox_token) {
    throw new Error("MAPBOX_TOKEN no está configurado en el servidor.");
  }
  return datos.mapbox_token;
}

// Capa de edificios 3D nativa de Mapbox (vector tiles `composite`/`building`,
// NO los colindantes de OpenStreetMap/Overpass de `analyzer/sitio.py` --
// son dos fuentes distintas de "edificios cercanos" con el mismo nombre
// coloquial). Patrón estable y documentado de Mapbox desde hace años, sin
// dependencia de versión de API que pueda haber cambiado.
function _activarEdificios3dNativos(map) {
  map.addLayer({
    id: "archmuse-edificios-3d",
    source: "composite",
    "source-layer": "building",
    filter: ["==", "extrude", "true"],
    type: "fill-extrusion",
    minzoom: 14,
    paint: {
      "fill-extrusion-color": "#aaa",
      "fill-extrusion-height": ["get", "height"],
      "fill-extrusion-base": ["get", "min_height"],
      "fill-extrusion-opacity": 0.65,
    },
  });
}

/**
 * Abre el visor georreferenciado de un proyecto dentro de `contenedorEl`
 * (un elemento del DOM, vacío o no -- este visor pinta un mapa a pantalla
 * completa dentro de él). `proyectoId` debe tener ya un sitio enlazado
 * (`GET /api/proyectos/<id>/georreferencia` -> `georreferenciado: true`);
 * si no, se rechaza la promesa con un mensaje claro ANTES de tocar
 * Mapbox/Threebox -- nunca un mapa centrado en un punto inventado.
 */
export async function abrirVisorMapa(proyectoId, contenedorEl) {
  const georefResp = await fetch("/api/proyectos/" + encodeURIComponent(proyectoId) + "/georreferencia");
  if (!georefResp.ok) throw new Error("No se pudo consultar la georreferencia del proyecto.");
  const georef = await georefResp.json();
  if (!georef.georreferenciado) {
    throw new Error(
      "Este proyecto no tiene ningún sitio (parcela) enlazado todavía -- no hay coordenadas reales que mostrar."
    );
  }

  const token = await _obtenerMapboxToken();
  await _asegurarMapboxCargado();

  // eslint-disable-next-line no-undef -- mapboxgl/Threebox llegan por CDN, no por import
  mapboxgl.accessToken = token;
  contenedorEl.innerHTML = "";
  // eslint-disable-next-line no-undef
  const map = new mapboxgl.Map({
    container: contenedorEl,
    style: "mapbox://styles/mapbox/standard",
    center: { lng: georef.lon, lat: georef.lat },
    zoom: 17,
    pitch: 60,
    bearing: georef.heading_grados || 0,
    antialias: true,
  });

  // `enableSelectingObjects` (confirmado hoy contra la documentación real
  // de Threebox) -- necesario para que "Vista desde ventana" pueda recibir
  // el evento `SelectedChange` al hacer clic en una habitación del modelo.
  // eslint-disable-next-line no-undef
  const tb = new Threebox(map, map.getCanvas().getContext("webgl"), {
    defaultLights: true,
    enableSelectingObjects: true,
  });

  const estadoVisor = { modelo: null, vistaGeneral: null, enVentana: false };

  map.on("style.load", () => {
    _activarEdificios3dNativos(map);

    map.addLayer({
      id: "archmuse-modelo-" + proyectoId,
      type: "custom",
      renderingMode: "3d",
      onAdd: function () {
        const opciones = {
          // Bytes servidos por `GET /api/proyectos/<id>/gltf`
          // (`analyzer.gltf_exporter`) -- el propio endpoint, no un
          // archivo estático: el modelo se genera al vuelo.
          obj: "/api/proyectos/" + encodeURIComponent(proyectoId) + "/gltf",
          type: "gltf",
          scale: { x: 1, y: 1, z: 1 },
          units: "meters",
          rotation: { x: 90, y: 0, z: 0 },
        };
        tb.loadObj(opciones, (modelo) => {
          modelo.setCoords([georef.lon, georef.lat]);
          // Altitud SIEMPRE null hoy (`analyzer/gltf_exporter.py` --
          // ningún servicio de sitio.py la trae): el modelo se posiciona
          // al nivel del terreno de Mapbox, sin ajuste de altitud real.
          modelo.setRotation({ x: 0, y: 0, z: georef.heading_grados || 0 });
          tb.add(modelo);
          estadoVisor.modelo = modelo;
          _cablearSeleccionDeHabitaciones(tb, map, modelo, georef, estadoVisor);
        });
      },
      render: function () {
        tb.update();
      },
    });
  });

  estadoVisor.vistaGeneral = {
    center: { lng: georef.lon, lat: georef.lat },
    zoom: 17,
    pitch: 60,
    bearing: georef.heading_grados || 0,
  };
  _crearPanelSolar(contenedorEl, tb, map, georef);
  _crearBotonVolverVistaGeneral(contenedorEl, map, estadoVisor);

  return map;
}

// --- Paso 3.2, punto 1: simulación solar --------------------------------

//: Los 4 momentos clave que pide el encargo, más "hoy". Fechas fijas de
// 2026 -- un solsticio/equinoccio real puede caer un día antes o después
// según el año (mismo matiz ya documentado en `tests/test_solar_
// posicion.mjs`); son una aproximación de calendario civil, no el instante
// astronómico exacto.
const _MOMENTOS_CLAVE = [
  { id: "hoy", etiqueta: "Hoy", fecha: null }, // se calcula en el momento, ver _fechaDeMomento
  { id: "solsticio_verano", etiqueta: "Solsticio de verano", mes: 5, dia: 21 },
  { id: "solsticio_invierno", etiqueta: "Solsticio de invierno", mes: 11, dia: 21 },
  { id: "equinoccio", etiqueta: "Equinoccio", mes: 2, dia: 20 },
];

function _fechaDeMomento(momento, horaUTC) {
  const ahora = new Date();
  const anio = momento.id === "hoy" ? ahora.getUTCFullYear() : 2026;
  const mes = momento.id === "hoy" ? ahora.getUTCMonth() : momento.mes;
  const dia = momento.id === "hoy" ? ahora.getUTCDate() : momento.dia;
  return new Date(Date.UTC(anio, mes, dia, Math.floor(horaUTC), Math.round((horaUTC % 1) * 60), 0));
}

// Actualiza la luz solar (Threebox) y el cielo (Mapbox) para una posición
// solar dada. `tb.lights` (confirmado hoy contra la documentación real de
// Threebox) contiene las luces direccionales que crea `defaultLights` --
// se reposicionan en vez de crear luces nuevas cada vez.
function _aplicarPosicionSolar(tb, map, lat, lon, fecha) {
  const sol = posicionSolar(lat, lon, fecha);
  const elevRad = (sol.elevacion_grados * Math.PI) / 180;
  const azRad = (sol.azimut_grados * Math.PI) / 180;

  // Vector unitario hacia el sol, en el sistema de coordenadas del modelo
  // (x, y=altura, z) -- mismo giro de eje que `analyzer/gltf_exporter.py`
  // (y arriba). Azimut 0=N, sentido horario; x=Este, z=Sur en esta
  // convención (coherente con cómo `gltf_exporter` gira el eje al
  // exportar).
  const distancia = 500; // unidades del modelo (metros) -- solo dirección, no posición real del sol
  const x = distancia * Math.cos(elevRad) * Math.sin(azRad);
  const y = Math.max(distancia * Math.sin(elevRad), 5); // nunca al nivel del suelo exacto, para no perder la sombra por completo de noche
  const z = -distancia * Math.cos(elevRad) * Math.cos(azRad);

  const luces = (tb.lights && (tb.lights.directionalLights || [tb.lights.directionalLight])) || [];
  luces.filter(Boolean).forEach((luz) => {
    luz.position.set(x, y, z);
    if (luz.target) luz.target.position.set(0, 0, 0);
    // De noche (elevación negativa) se atenúa la luz en vez de apagarla del
    // todo -- una intensidad 0 exacta puede dejar la escena completamente
    // negra si no hay luz ambiente suficiente.
    luz.intensity = sol.elevacion_grados > 0 ? 1.0 : 0.15;
  });

  // Cielo/atmósfera de Mapbox -- `map.setFog` es API estable desde hace
  // varias versiones de Mapbox GL JS (no verificada en vivo hoy, a
  // diferencia del resto de este archivo, por límite de tiempo -- riesgo
  // menor que el resto: si la forma exacta del objeto cambiara, como mucho
  // no se aplicaría el tono de cielo, no rompería el resto del visor).
  const deNoche = sol.elevacion_grados < 0;
  const atardecerAmanecer = sol.elevacion_grados >= 0 && sol.elevacion_grados < 10;
  try {
    map.setFog({
      color: atardecerAmanecer ? "#f4a261" : deNoche ? "#0b1026" : "#e6f0ff",
      "horizon-blend": 0.1,
      "high-color": deNoche ? "#0b1026" : "#add8e6",
      "space-color": deNoche ? "#000010" : "#d8f2ff",
      "star-intensity": deNoche ? 0.3 : 0,
    });
  } catch (err) {
    // best-effort, ver comentario de arriba -- nunca bloquea la sombra/luz
    console.warn("No se pudo aplicar el cielo de Mapbox:", err);
  }

  return sol;
}

function _crearPanelSolar(contenedorEl, tb, map, georef) {
  const panel = document.createElement("div");
  panel.className = "visor-mapa-panel-solar";
  panel.style.cssText =
    "position:absolute;bottom:12px;left:12px;background:rgba(20,20,24,0.85);color:#fff;" +
    "padding:10px 14px;border-radius:8px;font:13px sans-serif;z-index:5;max-width:320px;";

  const etiquetaHora = document.createElement("div");
  const slider = document.createElement("input");
  slider.type = "range";
  slider.min = "0";
  slider.max = "23.983"; // 23:59
  slider.step = "0.25"; // pasos de 15 min
  slider.value = "12";
  slider.style.width = "100%";

  const botones = document.createElement("div");
  botones.style.cssText = "margin-top:6px;display:flex;gap:4px;flex-wrap:wrap;";

  let momentoActual = _MOMENTOS_CLAVE[0]; // "hoy" por defecto

  function refrescar() {
    const horaUTC = parseFloat(slider.value);
    const fecha = _fechaDeMomento(momentoActual, horaUTC);
    const horas = Math.floor(horaUTC);
    const minutos = Math.round((horaUTC - horas) * 60);
    etiquetaHora.textContent =
      momentoActual.etiqueta + " — " + String(horas).padStart(2, "0") + ":" + String(minutos).padStart(2, "0") + " UTC";
    const sol = _aplicarPosicionSolar(tb, map, georef.lat, georef.lon, fecha);
    etiquetaHora.title =
      "Azimut " + sol.azimut_grados.toFixed(1) + "°, elevación " + sol.elevacion_grados.toFixed(1) + "°";
  }

  slider.addEventListener("input", refrescar);
  _MOMENTOS_CLAVE.forEach((momento) => {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.textContent = momento.etiqueta;
    boton.style.cssText = "font-size:11px;padding:2px 6px;cursor:pointer;";
    boton.addEventListener("click", () => {
      momentoActual = momento;
      refrescar();
    });
    botones.appendChild(boton);
  });

  panel.appendChild(etiquetaHora);
  panel.appendChild(slider);
  panel.appendChild(botones);
  contenedorEl.style.position = contenedorEl.style.position || "relative";
  contenedorEl.appendChild(panel);
  refrescar();
}

// --- Paso 3.2, punto 2: "Vista desde ventana" -----------------------------
//
// LIMITACIÓN HONESTA, heredada de `analyzer/gltf_exporter.py` (Paso 3.1):
// no existe geometría real de ventanas/huecos en ningún proyecto de
// ArchMuse -- el modelo exportado son volúmenes sólidos por HABITACIÓN, no
// por hueco de fachada. Esto implementa "clic en una habitación -> cámara
// dentro de ella, a 1.60m, mirando hacia fuera del edificio" -- una
// aproximación razonable dado lo que existe, no literalmente "la ventana".
// La dirección "hacia fuera" es una heurística (vector desde el centro del
// EDIFICIO hacia el centro de la HABITACIÓN, no la orientación real de un
// hueco de fachada, que no se conoce).

function _cablearSeleccionDeHabitaciones(tb, map, modelo, georef, estadoVisor) {
  const centroEdificio = _centroLocalDe(modelo);

  modelo.traverse((hijo) => {
    if (!hijo.isMesh) return;
    hijo.selectable = true; // no confirmado en la documentación de Threebox como flag por-objeto -- best effort
    hijo.addEventListener(
      "SelectedChange",
      (evento) => {
        if (!evento.detail || !evento.detail.selected) return;
        _entrarEnVistaVentana(map, hijo, centroEdificio, georef, estadoVisor);
      },
      false
    );
  });
}

function _centroLocalDe(objeto3d) {
  // eslint-disable-next-line no-undef -- THREE llega con Threebox por CDN
  const caja = new THREE.Box3().setFromObject(objeto3d);
  const centro = caja.getCenter(new THREE.Vector3());
  return centro;
}

function _entrarEnVistaVentana(map, meshHabitacion, centroEdificio, georef, estadoVisor) {
  // eslint-disable-next-line no-undef
  const caja = new THREE.Box3().setFromObject(meshHabitacion);
  // eslint-disable-next-line no-undef
  const centroHabitacion = caja.getCenter(new THREE.Vector3());

  // Dirección "hacia fuera": del centro del edificio al centro de la
  // habitación, en el plano horizontal (x, z) -- heurística, ver docstring
  // de esta sección.
  let dx = centroHabitacion.x - centroEdificio.x;
  let dz = centroHabitacion.z - centroEdificio.z;
  const mag = Math.hypot(dx, dz) || 1;
  dx /= mag;
  dz /= mag;

  // 1.60 m sobre la cota de ESA planta: cada habitación ya está extruida
  // desde su propio suelo (y_base real de `gltf_exporter.py`), así que
  // `caja.min.y` (el suelo de esta habitación en concreto) + 1.60 basta --
  // no hace falta saber en qué planta relativa está.
  const alturaOjosLocal = caja.min.y + 1.6;

  const posOjosLocal = { x: centroHabitacion.x, y: alturaOjosLocal, z: centroHabitacion.z };
  const puntoMiraLocal = { x: centroHabitacion.x + dx * 30, y: alturaOjosLocal, z: centroHabitacion.z + dz * 30 };

  const puntoOjos = _localAGeografico(posOjosLocal, georef);
  const puntoMira = _localAGeografico(puntoMiraLocal, georef);

  // eslint-disable-next-line no-undef -- mapboxgl llega por CDN
  const camara = map.getFreeCameraOptions();
  // eslint-disable-next-line no-undef
  camara.position = mapboxgl.MercatorCoordinate.fromLngLat([puntoOjos.lon, puntoOjos.lat], puntoOjos.altura_m);
  camara.lookAtPoint([puntoMira.lon, puntoMira.lat]);
  map.setFreeCameraOptions(camara);
  estadoVisor.enVentana = true;
}

// (x, y, z) locales del modelo -> {lat, lon, altura_m} reales. Aproximación
// de tierra plana (válida a escala de un edificio, no de un continente):
// gira (x, z) por el heading del modelo y convierte metros a grados con
// `METROS_POR_GRADO_LAT` / su equivalente en longitud según la latitud.
function _localAGeografico(punto, georef) {
  const headingRad = ((georef.heading_grados || 0) * Math.PI) / 180;
  const xGirado = punto.x * Math.cos(headingRad) - punto.z * Math.sin(headingRad);
  const zGirado = punto.x * Math.sin(headingRad) + punto.z * Math.cos(headingRad);

  const metrosPorGradoLon = METROS_POR_GRADO_LAT * Math.cos((georef.lat * Math.PI) / 180);
  return {
    lat: georef.lat + zGirado / METROS_POR_GRADO_LAT,
    lon: georef.lon + xGirado / metrosPorGradoLon,
    // Altitud real del terreno SIEMPRE desconocida (`gltf_exporter.py`) --
    // se usa 0 como referencia de suelo, más la altura local (y). Sin
    // altitud real de Catastro, la cámara puede quedar por debajo/encima
    // del terreno real de Mapbox si la parcela no está a nivel del mar.
    altura_m: punto.y,
  };
}

function _crearBotonVolverVistaGeneral(contenedorEl, map, estadoVisor) {
  const boton = document.createElement("button");
  boton.type = "button";
  boton.textContent = "Volver a vista aérea";
  boton.style.cssText =
    "position:absolute;top:12px;left:12px;z-index:5;padding:6px 12px;border-radius:6px;cursor:pointer;";
  boton.addEventListener("click", () => {
    if (!estadoVisor.vistaGeneral) return;
    // `easeTo` con los parámetros pitch/bearing/zoom/center originales
    // desactiva automáticamente la cámara libre (`FreeCameraOptions`) que
    // pudiera estar activa -- comportamiento documentado de Mapbox GL JS,
    // no verificado en vivo en esta sesión.
    map.easeTo(Object.assign({ duration: 800 }, estadoVisor.vistaGeneral));
    estadoVisor.enVentana = false;
  });
  contenedorEl.style.position = contenedorEl.style.position || "relative";
  contenedorEl.appendChild(boton);
}

// --- Puente con el script clásico (`static/app.js`) -----------------------
//
// Mismo patrón que `window.ArchmuseViewer3D` (`viewer-edificio.js`): este
// archivo es un `<script type="module">`, `app.js` es un script clásico sin
// acceso a sus `import`/`export` -- `window.ArchmuseVisorMapa.open(data)` es
// el único punto de entrada que necesita conocer. Overlay `#viewer-mapa`
// (mismo criterio que `#viewer-3d`: `position:fixed`, clase `.open` para
// mostrar/ocultar) definido en `static/index.html`.

let _mapaActual = null;

function open(data) {
  const overlay = document.getElementById("viewer-mapa");
  const mount = document.getElementById("viewer-mapa-mount");
  const loading = document.getElementById("viewer-mapa-loading");
  if (!overlay || !mount || !loading) return;

  overlay.classList.add("open");
  loading.hidden = false;
  loading.textContent = "Cargando el mapa…";
  Array.prototype.forEach.call(mount.querySelectorAll(".visor-mapa-error"), (el) => el.remove());

  if (!data || !data.proyecto_id) {
    loading.textContent = "Este proyecto todavía no está guardado — no se puede abrir el mapa.";
    return;
  }

  abrirVisorMapa(data.proyecto_id, mount)
    .then((map) => {
      _mapaActual = map;
      loading.hidden = true;
    })
    .catch((err) => {
      loading.hidden = true;
      const mensaje = document.createElement("div");
      mensaje.className = "visor-mapa-error";
      mensaje.style.cssText = "color:#fff;padding:2rem;text-align:center;max-width:480px;margin:0 auto;";
      mensaje.textContent = err && err.message ? err.message : "No se pudo abrir el mapa.";
      mount.appendChild(mensaje);
    });
}

function close() {
  const overlay = document.getElementById("viewer-mapa");
  if (overlay) overlay.classList.remove("open");
  // `.remove()` es el método real y documentado de `mapboxgl.Map` para
  // liberar el contexto WebGL -- sin esto, abrir/cerrar el visor varias
  // veces iría acumulando mapas vivos en memoria.
  if (_mapaActual && typeof _mapaActual.remove === "function") {
    try {
      _mapaActual.remove();
    } catch (err) {
      console.warn("No se pudo liberar el mapa anterior:", err);
    }
  }
  _mapaActual = null;
}

document.addEventListener("DOMContentLoaded", () => {
  const btnCerrar = document.getElementById("btn-cerrar-viewer-mapa");
  if (btnCerrar) btnCerrar.addEventListener("click", close);
});

window.ArchmuseVisorMapa = { open, close };
