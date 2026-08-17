// Núcleo compartido de los dos visores 3D (`viewer-edificio.js` y
// `viewer-vivienda.js`). Creado el 2026-08-12 al unificar el motor 3D (Fase 1).
//
// Qué es y qué NO es:
//   - Es la "sesión de render": renderer, cámara activa, OrbitControls, bucle
//     de animación, redimensionado, listeners del canvas y el desmontaje
//     ordenado de todo eso. Es la maquinaria que los dos visores escribían
//     por duplicado, línea por línea, con el riesgo de que un `teardown()`
//     olvidara quitar algo en uno de los dos.
//   - NO es un "visor genérico configurable". La escena, los materiales, la
//     geometría, el postprocesado, los paneles y los modos de cámara siguen
//     siendo responsabilidad de cada visor: son justo lo que los diferencia.
//     Si algo solo lo usa un visor, no debe subir aquí.
//
// El dueño de la escena sigue siendo cada visor: `dispose()` desmonta la
// sesión, pero liberar la geometría/materiales de la escena se hace aparte
// con `disposeSceneResources()`, porque cada visor decide cuándo su escena
// deja de ser válida.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

// Libera geometrías y materiales de un árbol de escena. Estaba solo en el
// visor de edificio (`disposeScene`); el de vivienda se limitaba a poner
// `scene = null`, con lo que la GPU se quedaba la geometría de la vivienda
// anterior en cada apertura del visor.
export function disposeSceneResources(root) {
  if (!root) return;
  root.traverse(function (child) {
    if (child.geometry) child.geometry.dispose();
    if (child.material) {
      if (Array.isArray(child.material)) child.material.forEach(function (m) { m.dispose(); });
      else child.material.dispose();
    }
  });
}

// Coloca un tooltip flotante junto al cursor sin que se salga del viewport:
// si no cabe a la derecha/abajo, se dibuja al otro lado del puntero. El visor
// de edificio ya lo hacía así y su propio comentario señalaba que estaba
// duplicando el criterio de otro módulo; el de vivienda no clampaba y el
// tooltip podía quedar cortado en el borde de la pantalla.
export function positionTooltip(el, clientX, clientY, pad) {
  if (!el || el.hidden) return;
  var margin = pad == null ? 14 : pad;
  var left = clientX + margin;
  var top = clientY + margin;
  var rect = el.getBoundingClientRect();
  if (left + rect.width > window.innerWidth - 8) left = clientX - rect.width - margin;
  if (top + rect.height > window.innerHeight - 8) top = clientY - rect.height - margin;
  el.style.left = left + "px";
  el.style.top = top + "px";
}

// Crea la sesión de render sobre `mount`.
//
// options:
//   mount           HTMLElement contenedor (obligatorio).
//   insertBefore    Nodo hijo de `mount` ante el cual insertar el canvas; si
//                   no se pasa, se añade al final. El visor de vivienda lo
//                   necesita para que el canvas quede por debajo de su capa
//                   de "Generando el modelo 3D…".
//   renderer        { alpha, clearColor, toneMapping, toneMappingExposure,
//                     outputColorSpace }. Sombras PCFSoft y pixel ratio
//                     limitado a 2 son comunes a ambos visores y van fijos.
//   camera          { fov, near, far, position } de la PerspectiveCamera
//                   inicial. `position` (Vector3) se aplica ANTES de crear los
//                   OrbitControls: si la cámara siguiera en el origen —que es
//                   también el target por defecto— el `update()` inicial de
//                   los controles partiría de un offset de longitud cero.
//   controls        Propiedades a volcar en OrbitControls. `target` se aplica
//                   con `.copy()` (es un Vector3, no se puede reasignar).
export function createViewerSession(options) {
  var mount = options.mount;
  var width = mount.clientWidth || 800;
  var height = mount.clientHeight || 600;

  var rendererCfg = options.renderer || {};
  var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: !!rendererCfg.alpha });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(width, height);
  if (rendererCfg.clearColor != null) renderer.setClearColor(rendererCfg.clearColor);
  if (rendererCfg.clearAlpha != null) renderer.setClearAlpha(rendererCfg.clearAlpha);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  if (rendererCfg.toneMapping != null) {
    renderer.toneMapping = rendererCfg.toneMapping;
    if (rendererCfg.toneMappingExposure != null) renderer.toneMappingExposure = rendererCfg.toneMappingExposure;
  }
  if (rendererCfg.outputColorSpace != null) renderer.outputColorSpace = rendererCfg.outputColorSpace;

  if (options.insertBefore && options.insertBefore.parentNode === mount) {
    mount.insertBefore(renderer.domElement, options.insertBefore);
  } else {
    mount.appendChild(renderer.domElement);
  }

  var cameraCfg = options.camera || {};
  var camera = new THREE.PerspectiveCamera(
    cameraCfg.fov == null ? 45 : cameraCfg.fov,
    width / height,
    cameraCfg.near == null ? 0.1 : cameraCfg.near,
    cameraCfg.far == null ? 1000 : cameraCfg.far
  );
  if (cameraCfg.position) camera.position.copy(cameraCfg.position);

  var controls = new OrbitControls(camera, renderer.domElement);
  var controlsCfg = options.controls || {};
  Object.keys(controlsCfg).forEach(function (key) {
    if (key === "target") controls.target.copy(controlsCfg.target);
    else controls[key] = controlsCfg[key];
  });
  controls.update();

  var domListeners = [];
  var resizeCallbacks = [];
  var resizeObserver = null;
  var animationId = null;
  var startTime = null;
  var lastFrameTime = null;

  var session = {
    renderer: renderer,
    controls: controls,
    camera: camera,

    // Cámara activa. El visor de edificio alterna entre perspectiva y
    // ortográfica (Planta/Alzado/Lateral) y la sesión necesita saber cuál es
    // para no tocar el `aspect` de una cámara ortográfica al redimensionar.
    setCamera: function (nextCamera) {
      camera = nextCamera;
      session.camera = nextCamera;
      controls.object = nextCamera;
    },

    // Listener sobre el canvas que se retira solo en `dispose()`. Los dos
    // visores registraban pointermove/pointerleave (y click, el de edificio)
    // y tenían que acordarse de quitarlos a mano en su `teardown()`.
    addDomListener: function (type, handler) {
      renderer.domElement.addEventListener(type, handler);
      domListeners.push({ type: type, handler: handler });
    },

    // Registra trabajo EXTRA a hacer al redimensionar. El ajuste del renderer
    // y del aspect de la cámara en perspectiva ya lo hace la sesión sola
    // (ver el ResizeObserver más abajo, activo desde su creación); esto es
    // para lo que añade cada visor — el composer de postprocesado y el
    // reencuadre del frustum ortográfico, en el caso del edificio.
    onResize: function (callback) {
      resizeCallbacks.push(callback);
    },

    // Bucle de render. `frame(now, dt, elapsed)`: `now` es el timestamp de
    // requestAnimationFrame (misma base que `performance.now()`, de la que
    // dependen las tweens del visor de edificio), `dt` el delta en segundos
    // acotado a 0.1 para que un cambio de pestaña no dé un salto enorme, y
    // `elapsed` los segundos desde `start()` (sustituye al `THREE.Clock` que
    // usaba el visor de vivienda para el pulso de los contornos).
    // El propio `frame` hace el render: uno de los visores dibuja con
    // `renderer.render()` y el otro con `composer.render()`.
    start: function (frame) {
      startTime = null;
      lastFrameTime = null;
      var step = function (now) {
        animationId = requestAnimationFrame(step);
        if (startTime === null) startTime = now;
        var dt = lastFrameTime === null ? 1 / 60 : Math.min(0.1, (now - lastFrameTime) / 1000);
        lastFrameTime = now;
        frame(now, dt, (now - startTime) / 1000);
      };
      animationId = requestAnimationFrame(step);
    },

    stop: function () {
      if (animationId) cancelAnimationFrame(animationId);
      animationId = null;
    },

    // Coordenadas normalizadas (-1..1) del puntero sobre el canvas, o null si
    // el cursor cae fuera. Ambos visores calculaban esto igual a partir de
    // `getBoundingClientRect()`.
    pointerToNDC: function (clientX, clientY) {
      var rect = renderer.domElement.getBoundingClientRect();
      if (!rect.width || !rect.height) return null;
      var x = ((clientX - rect.left) / rect.width) * 2 - 1;
      var y = -((clientY - rect.top) / rect.height) * 2 + 1;
      if (x < -1 || x > 1 || y < -1 || y > 1) return null;
      return { x: x, y: y };
    },

    // Desmonta todo lo que posee la sesión. La escena NO se libera aquí: eso
    // lo decide cada visor con `disposeSceneResources()`.
    dispose: function () {
      session.stop();
      if (resizeObserver) { resizeObserver.disconnect(); resizeObserver = null; }
      resizeCallbacks = [];
      domListeners.forEach(function (l) { renderer.domElement.removeEventListener(l.type, l.handler); });
      domListeners = [];
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement);
    }
  };

  // Redimensionado por ResizeObserver sobre el contenedor (el visor de
  // vivienda escuchaba `window.resize`, que no detecta cambios de layout del
  // propio panel). Se observa desde la creación: cualquier visor necesita al
  // menos que el renderer siga al contenedor, tenga o no trabajo extra que
  // registrar con `onResize()`.
  resizeObserver = new ResizeObserver(function () {
    var w = mount.clientWidth;
    var h = mount.clientHeight;
    if (!w || !h) return;
    if (camera.isPerspectiveCamera) {
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
    renderer.setSize(w, h);
    resizeCallbacks.forEach(function (cb) { cb(w, h); });
  });
  resizeObserver.observe(mount);

  return session;
}
