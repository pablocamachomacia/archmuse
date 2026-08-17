// Extraido de index.html el 2026-08-02 al dividir el archivo unico de
// 5.779 lineas. Contenido intacto: solo cambio de ubicacion.

// Visor 3D: reconstruye el EDIFICIO COMPLETO (todas las plantas, con todas
// sus viviendas) a partir de los polígonos de habitaciones en metros reales
// que manda la API. Cada planta se agrupa a partir del nombre de vivienda
// ("Planta N · ..."), sus viviendas se recolocan una junto a otra (en el
// JSON generado cada vivienda vive en su propio "carril" X muy alejado de
// las demás — ver `ai_generator.UNIT_OFFSET_M` — así que aquí se cierra ese
// hueco para formar la planta física completa). Cada vivienda de cada planta
// es un BLOQUE independiente: su footprint es el rectángulo (AABB) de sus
// habitaciones, no un envolvente convexo — así el edificio se lee como
// paralelepípedos arquitectónicos limpios, con un Box por bloque/ala en vez
// de una única forma orgánica. Cada muro exterior lleva un hueco de ventana
// REAL (jambas + antepecho + dintel, no una caja ciega) con vidrio +
// marco montados encima, para una lectura de maqueta arquitectónica
// profesional (hormigón claro, vidrio translúcido, contexto urbano). Las
// particiones interiores se dibujan como líneas finas sobre la losa de cada
// bloque, no como muros propios. Las plantas se apilan con la altura libre
// configurada, y el panel flotante (`buildFloorPanel`) permite aislar una
// planta: su techo se oculta (lectura en sección horizontal) y las plantas
// superiores se atenúan. Solo se invoca con proyectos generados
// (`data.edificio` no nulo); el resto de la SPA vive en el script clásico
// de más arriba — este módulo solo expone `window.ArchmuseViewer3D`.
// Desde 2026-08-12 (unificación del motor 3D, Fase 1) la maquinaria de render
// —renderer, cámara, controles, bucle, redimensionado y desmontaje— vive en
// `viewer-core.js`, compartida con el visor de vivienda; aquí solo queda lo
// propio de este visor: la arquitectura sintética del edificio, el entorno
// urbano, el postprocesado, las vistas técnicas y el modo Paseo.
import * as THREE from "three";
import { createViewerSession, disposeSceneResources, positionTooltip } from "./viewer-core.js";
import { extrudeFootprint, directionFromAzimuthElevation, orbitPosition } from "./viewer-geometry.js";
// Contexto urbano real (2026-08-16, a petición explícita): posición solar real (mismo módulo puro
// que ya usa `visor-mapa.js`, sin duplicar el algoritmo) para sustituir el sol de estudio fijo
// (135°/55°) por la posición real del sol para las coordenadas y el instante de apertura del visor.
import { posicionSolar } from "./solar-posicion.js";
// Terreno real (2026-08-17): extraído a `viewer-terreno.js` para que `viewer-sandbox.js` (Modo
// Sandbox/Lienzo Libre) lo reutilice sin duplicar la matemática de tiles/proyección -- mismo
// contenido exacto que tenía este archivo, solo cambia de sitio.
import {
  construirMosaicoOrtofoto, construirPlanoOrtofoto, construirEdificiosColindantes, pedirEntorno3D,
  construirTerrenoOrganico
} from "./viewer-terreno.js";
// Desde 2026-08-12 (Fase 2, "3D Premium") el material de fachada/losa/cubierta
// /vidrio y el entorno PBR/iluminación/tone mapping vienen de
// `viewer-materials.js`, compartido con el visor de vivienda (antes de Fase 2
// tenía la única versión "buena" de todo esto; ahora las dos parten de la
// misma fábrica). Mismos valores numéricos que antes en todos los casos —
// esto es solo dejar de duplicar la construcción, no un cambio visual.
import {
  createWallMaterial, createFloorMaterial, createCeilingMaterial, createGlassMaterial,
  buildPBREnvironment, presentationRendererSettings, createSunLight, createFillLights
} from "./viewer-materials.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { SSAOPass } from "three/addons/postprocessing/SSAOPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

(function () {
  "use strict";

  var WALL_THICKNESS = 0.15;
  var SLAB_THICKNESS = 0.15;
  var INTERIOR_LINE_HEIGHT = 0.06;
  var INTERIOR_LINE_THICKNESS = 0.05;
  // Separación horizontal entre viviendas contiguas de una misma planta al
  // recolocarlas (representa el hueco de un muro medianero/rellano).
  var UNIT_GAP = 1.4;
  var DEFAULT_FLOOR_HEIGHT = 2.8;
  // Límite defensivo: un número de plantas disparatado en el formulario no
  // debería poder congelar la pestaña generando miles de muros.
  var MAX_FLOORS = 60;

  // Opacidad base del vidrio (MeshStandardMaterial): se reutiliza al
  // restaurar una planta atenuada, ver `setMeshOpacity`.
  var GLASS_OPACITY = 0.7;

  // Material de la envolvente del Sólido Capaz (Sólido Capaz persistente, 2026-08-17): MISMO color y
  // opacidad exactos que `MAT_SOLIDO_CAPAZ` en `viewer-sandbox.js` -- es el mismo volumen de referencia,
  // solo en otro visor, y debe leerse como tal, no como un elemento nuevo con su propio lenguaje visual.
  var MAT_ENVOLVENTE_SOLIDO_CAPAZ = new THREE.MeshStandardMaterial({
    color: 0x6B8CAE, transparent: true, opacity: 0.3, roughness: 1, metalness: 0, depthWrite: false
  });
  var MAT_BORDE_ENVOLVENTE_SOLIDO_CAPAZ = new THREE.LineBasicMaterial({ color: 0xFFFFFF, transparent: true, opacity: 0.6 });

  var SKY_VERTEX_SHADER =
    "varying vec3 vWorldPosition;\n" +
    "void main() {\n" +
    "  vec4 worldPosition = modelMatrix * vec4(position, 1.0);\n" +
    "  vWorldPosition = worldPosition.xyz;\n" +
    "  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);\n" +
    "}\n";
  var SKY_FRAGMENT_SHADER =
    "uniform vec3 topColor;\n" +
    "uniform vec3 bottomColor;\n" +
    "uniform float offset;\n" +
    "uniform float exponent;\n" +
    "varying vec3 vWorldPosition;\n" +
    "void main() {\n" +
    "  float h = normalize(vWorldPosition + offset).y;\n" +
    "  gl_FragColor = vec4(mix(bottomColor, topColor, max(pow(max(h, 0.0), exponent), 0.0)), 1.0);\n" +
    "}\n";

  var mount = document.getElementById("viewer-3d-mount");
  var loadingEl = document.getElementById("viewer-3d-loading");
  var overlayEl = document.getElementById("viewer-3d");
  var titleEl = document.getElementById("viewer-3d-title-text");
  var metaEl = document.getElementById("viewer-3d-meta-text");
  var closeBtn = document.getElementById("btn-volver-plano");
  var walkBtn = document.getElementById("btn-paseo");

  // `session` es la dueña real del renderer/cámara/controles (ver
  // `viewer-core.js`); `renderer`/`camera`/`controls` son alias locales a sus
  // objetos, que es como los sigue usando todo el código de este visor. Al
  // cambiar de cámara (perspectiva ↔ ortográfica) hay que actualizar AMBOS:
  // el alias de aquí y `session.setCamera()` — ver `switchCameraType`.
  var session = null;
  var renderer = null;
  var scene = null;
  var camera = null;
  var controls = null;
  var composer = null;
  var envTexture = null;
  // Cámara activa vs. las dos instancias posibles (NAVEGACIÓN): `camera`
  // siempre apunta a una de las dos. `perspCamera` se crea en `open()`;
  // `orthoCamera` se crea perezosamente la primera vez que se pide una
  // vista Planta/Alzado/Lateral (`fitOrthoFrustum`/`switchCameraType`).
  // `renderPassRef`/`ssaoPassRef` guardan los passes del composer para
  // poder reapuntar su `.camera` al cambiar de tipo sin reconstruir el
  // pipeline de postprocesado entero.
  var perspCamera = null;
  var orthoCamera = null;
  var renderPassRef = null;
  var ssaoPassRef = null;
  // Vista ortográfica activa ("top"/"front"/"side") o null si la cámara
  // activa es la perspectiva — controla la visibilidad de la escala
  // gráfica y el reencuadre del frustum al redimensionar.
  var currentOrthoView = null;
  // Una entrada por planta con los meshes que la componen (losas, muros,
  // ventanas, líneas interiores y, en la última, la cubierta) — el panel de
  // plantas los usa para aislar/atenuar niveles sin reconstruir la escena.
  var levels = [];
  var currentFloorSelection = null;
  var ambientLight = null;
  var hemisphereLight = null;
  var sunLight = null;
  var groundMesh = null;
  // Acera/bordillo (referencia guardada desde 2026-08-16, navegación fluida): la necesita el
  // recentrado por doble clic (`onDblClickRecenter`) como uno de los objetivos válidos de raycast,
  // igual que `groundMesh`/`entornoGroup` — antes solo era una variable local de `buildGround`.
  var sidewalkMesh = null;
  // Contexto urbano real (2026-08-16, a petición explícita): ortofoto real + volúmenes de edificios
  // colindantes, cuando el proyecto tiene un sitio real enlazado (Paso 0). `entornoGroup` cuelga de
  // `scene` como CUALQUIER otro grupo (nunca sustituye `groundMesh`/`buildSky`, que siguen existiendo
  // como fondo de seguridad si la carga real falla o el proyecto no está georreferenciado) --
  // `entornoFetchToken` es la guarda de "esta respuesta ya no aplica" (mismo patrón que usa
  // `entrevista.js` para peticiones obsoletas): si se abre/cierra el visor mientras la petición
  // sigue en el aire, la respuesta tardía nunca toca una escena que ya no existe.
  var entornoGroup = null;
  var entornoUrbanoDisponible = false;
  // Sólido Capaz persistente (2026-08-17, docs/prd/2026-08-17-solido-capaz-persistente-visor-
  // edificio.md): malla translúcida de referencia con la envolvente legal calculada en el Sandbox antes
  // de generar, si el proyecto trae `solido_capaz` (snapshot opcional, columna propia -- ver
  // `construirEnvolventeSolidoCapaz`). `null` si el proyecto no la trae, el caso mayoritario hoy.
  var solidoCapazEnvolvente = null;
  var sombrasActivas = true;
  var entornoFetchToken = 0;
  var btnEntorno = document.getElementById("btn-toggle-entorno");
  var btnSombras = document.getElementById("btn-toggle-sombras");
  // Resultado de la última `buildScene()` (center/buildingSize/buildingGroup/
  // treeGroups) — lo usan los botones de vista de cámara (CAMBIO 1) y el
  // modo paseo (CAMBIO 4), que viven fuera de `open()` y necesitan datos de
  // la escena actual sin reconstruirla.
  var lastInfo = null;
  // Tween de cámara en curso (botones de vista) — ver `animateCameraTo`.
  var camTween = null;
  // Cola de animaciones de entrada (CAMBIO 3) — ver `scheduleTween`.
  var introTweens = [];

  // Modo paseo (CAMBIO 4, experimental) — ver `enterWalkMode`/`updateWalkMode`.
  var WALK_HEIGHT = 1.7;
  var WALK_SPEED = 3.2;
  var WALK_COLLIDE_RADIUS = 0.35;
  var walkActive = false;
  var walkKeys = Object.create(null);
  var walkYaw = 0;
  var walkPitch = 0;
  var walkSavedCamPos = null;
  var walkSavedTarget = null;
  var walkRaycaster = new THREE.Raycaster();
  // Caché de "colisionables" para el Paseo (corrección de 2026-08-12): antes,
  // `updateWalkMode` llamaba `walkRaycaster.intersectObject(buildingGroup,
  // true)` DOS veces por frame — una para el avance, otra (SIEMPRE, aunque no
  // haya movimiento) para la altura sobre el suelo — recorriendo TODA la
  // jerarquía del edificio (fachadas con hueco de ventana real: jambas,
  // vierteaguas, dintel, vidrio y marco por cada ventana → fácilmente
  // >1.000 mallas) en cada una. `walkColliders` es un array plano
  // {mesh, center, radius} (esfera envolvente en coordenadas de mundo)
  // construido UNA vez por edificio en `buildWalkColliders`; cada frame se
  // descartan por distancia los candidatos que el rayo no puede alcanzar
  // antes de lanzar el raycast de verdad — mismo resultado, sin recorrer la
  // jerarquía ni testear mallas que están fuera de rango.
  var walkColliders = null;
  var walkCollidersFor = null;
  // HUD de nombre de habitación (evita reescribir el DOM si no cambió de
  // habitación entre frames) y el timeout del overlay de instrucciones.
  var walkCurrentRoomName = null;
  var walkInstructionsTimer = null;

  // HOVER sobre habitaciones (NAVEGACIÓN): raycasting por frame contra
  // `lastInfo.roomHitGroup` (mallas invisibles pero detectables, ver
  // `buildScene`). `pointerClientXY` guarda solo la posición bruta del
  // ratón (actualizada por evento); el raycast en sí se hace una vez por
  // frame en `animate()` — así una tween de cámara en curso con el ratón
  // quieto también actualiza el hover, no solo el propio `mousemove`.
  var hoverRaycaster = new THREE.Raycaster();
  var pointerClientXY = null;
  var hoveredRoomMesh = null;
  var hoverOutlineMesh = null;

  function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }
  function easeInOutCubic(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }

  // Cola mínima de tweens "de entrada" (CAMBIO 3): cada uno arranca en su
  // propio `startAt` (timestamp de `requestAnimationFrame`) y llama a
  // `onUpdate(t)` con `t` lineal 0..1 — cada llamador aplica su propio
  // easing. Sin librerías externas, todo sobre el rAF que ya existe.
  function scheduleTween(startAt, duration, onUpdate) {
    introTweens.push({ startAt: startAt, duration: duration, onUpdate: onUpdate, done: false });
  }
  function stepIntroTweens(now) {
    if (!introTweens.length) return;
    introTweens.forEach(function (tw) {
      if (tw.done || now < tw.startAt) return;
      var t = tw.duration > 0 ? Math.min(1, (now - tw.startAt) / tw.duration) : 1;
      tw.onUpdate(t);
      if (t >= 1) tw.done = true;
    });
    introTweens = introTweens.filter(function (tw) { return !tw.done; });
  }

  // Tween de cámara "GSAP-like" para los botones de vista (CAMBIO 1): sin
  // GSAP, interpolación manual enganchada al mismo rAF del render loop.
  function animateCameraTo(toPos, toTarget, duration) {
    if (!camera || !controls) return;
    camTween = {
      fromPos: camera.position.clone(),
      toPos: toPos.clone(),
      fromTarget: controls.target.clone(),
      toTarget: toTarget.clone(),
      start: performance.now(),
      duration: duration || 900
    };
    controls.enabled = false;
  }
  function stepCamTween(now) {
    var t = Math.min(1, (now - camTween.start) / camTween.duration);
    var e = easeInOutCubic(t);
    camera.position.lerpVectors(camTween.fromPos, camTween.toPos, e);
    controls.target.lerpVectors(camTween.fromTarget, camTween.toTarget, e);
    if (t >= 1) {
      camTween = null;
      controls.enabled = !walkActive;
    }
  }

  function teardown() {
    if (walkActive) exitWalkMode();
    camTween = null;
    introTweens = [];
    lastInfo = null;
    // La sesión se lleva por delante el bucle de render, el ResizeObserver,
    // los listeners del canvas, los OrbitControls y el propio renderer.
    if (session) { session.dispose(); session = null; }
    controls = null;
    if (composer) { composer.dispose(); composer = null; }
    if (envTexture) { envTexture.dispose(); envTexture = null; }
    if (scene) { disposeSceneResources(scene); scene = null; }
    ambientLight = null;
    hemisphereLight = null;
    sunLight = null;
    groundMesh = null;
    sidewalkMesh = null;
    // `disposeSceneResources(scene)` ya liberó la geometría/material de todo lo que colgara de
    // `entornoGroup` (era hijo de `scene`) -- aquí solo se sueltan las referencias y se oculta la UI,
    // nunca se libera nada dos veces.
    entornoGroup = null;
    entornoUrbanoDisponible = false;
    // Mismo criterio: `disposeSceneResources(scene)` ya liberó su geometría/material (era hijo de
    // `scene`), aquí solo se suelta la referencia.
    solidoCapazEnvolvente = null;
    sombrasActivas = true; // `createViewerSession` siempre arranca con `shadowMap.enabled = true`
    entornoFetchToken += 1; // invalida cualquier fetch de entorno-3d todavía en vuelo
    if (btnEntorno) { btnEntorno.hidden = true; btnEntorno.classList.remove("active"); }
    if (btnSombras) { btnSombras.hidden = true; }
    clearHover();
    pointerClientXY = null;
    renderer = null;
    camera = null;
    perspCamera = null;
    orthoCamera = null;
    renderPassRef = null;
    ssaoPassRef = null;
    currentOrthoView = null;
    levels = [];
    currentFloorSelection = null;
    var panel = document.getElementById("floor-panel");
    if (panel && panel.parentNode) panel.parentNode.removeChild(panel);
    var compass = document.getElementById("viewer-compass");
    if (compass && compass.parentNode) compass.parentNode.removeChild(compass);
    var scaleBar = document.getElementById("viewer-scale-bar");
    if (scaleBar && scaleBar.parentNode) scaleBar.parentNode.removeChild(scaleBar);
    ["viewer-crosshair", "viewer-room-hud", "viewer-walk-instructions", "viewer-minimap", "viewer-nav-hud"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el && el.parentNode) el.parentNode.removeChild(el);
    });
    if (walkInstructionsTimer) { clearTimeout(walkInstructionsTimer); walkInstructionsTimer = null; }
    walkCurrentRoomName = null;
    walkColliders = null;
    walkCollidersFor = null;
    var introFade = document.querySelector(".viewer-intro-fade");
    if (introFade && introFade.parentNode) introFade.parentNode.removeChild(introFade);
  }

  // Ray casting en el plano XZ (habitaciones vecinas, no altura) — sirve
  // tanto para saber si un muro es exterior o medianero como para orientar
  // su normal hacia "fuera" de su propia habitación.
  function pointInPolygon(pt, pts) {
    var inside = false;
    for (var i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      var xi = pts[i].x, zi = pts[i].z, xj = pts[j].x, zj = pts[j].z;
      var intersect = (zi > pt.z) !== (zj > pt.z) &&
        pt.x < ((xj - xi) * (pt.z - zi)) / (zj - zi) + xi;
      if (intersect) inside = !inside;
    }
    return inside;
  }

  // Habitación (registro de `lastInfo.roomIndex`) que contiene el punto
  // mundo `(x, y, z)`, o null — usado por el HUD de nombre de habitación en
  // modo Paseo (altura de la cámara decide la planta, XZ decide la
  // habitación dentro de ella).
  function roomAtPoint(x, y, z) {
    if (!lastInfo || !lastInfo.roomIndex) return null;
    for (var i = 0; i < lastInfo.roomIndex.length; i++) {
      var r = lastInfo.roomIndex[i];
      if (y < r.floorBaseY - 0.5 || y > r.floorTop + 0.5) continue;
      if (pointInPolygon({ x: x, z: z }, r.poly)) return r;
    }
    return null;
  }

  // --- Geometría 2D auxiliar (todo en el plano XZ de la escena) -------------

  function pointSegDist(p, a, b) {
    var abx = b.x - a.x, abz = b.z - a.z;
    var len2 = abx * abx + abz * abz;
    var t = len2 > 1e-9 ? ((p.x - a.x) * abx + (p.z - a.z) * abz) / len2 : 0;
    t = Math.max(0, Math.min(1, t));
    var cx = a.x + abx * t, cz = a.z + abz * t;
    return Math.hypot(p.x - cx, p.z - cz);
  }

  function distToPolygonBoundary(p, poly) {
    var min = Infinity;
    for (var i = 0; i < poly.length; i++) {
      var d = pointSegDist(p, poly[i], poly[(i + 1) % poly.length]);
      if (d < min) min = d;
    }
    return min;
  }

  // Losa de forjado con la huella de `pts` (metros, mismo sistema XZ que
  // los muros), con su cara superior a la altura `y`. La inversión de la Z al
  // construir la forma y el `rotateX(-90°)` para tumbarla los resuelve
  // `extrudeFootprint` (ver `viewer-geometry.js`).
  function buildSlab(pts, y, material) {
    var geometry = extrudeFootprint(pts, SLAB_THICKNESS);
    // Material clonado por mesh: el panel de plantas atenúa/oculta losas de
    // una planta sin afectar a las demás, que comparten el material base.
    var mesh = new THREE.Mesh(geometry, material.clone());
    mesh.position.y = y - SLAB_THICKNESS;
    mesh.receiveShadow = true;
    mesh.castShadow = true;
    return mesh;
  }

  // Canto de forjado (CAMBIO 2): una banda fina por arista del rectángulo
  // de la losa, flush con la cara exterior del muro (mismo offset hacia
  // fuera que usan los muros) y con la misma altura que el grosor de la
  // losa — simula el borde del forjado visto desde fuera, en vez de un
  // canto invisible/coincidente con el muro. `collector`, si se pasa,
  // recibe cada mesh para que el panel de plantas lo atenúe con su losa.
  function buildSlabEdges(group, rectPts, y, material, collector) {
    var n = rectPts.length;
    var edgeWidth = 0.025;
    for (var i = 0; i < n; i++) {
      var p1 = rectPts[i], p2 = rectPts[(i + 1) % n];
      var dx = p2.x - p1.x, dz = p2.z - p1.z;
      var len = Math.sqrt(dx * dx + dz * dz);
      if (len < 0.05) continue;

      var mid = { x: (p1.x + p2.x) / 2, z: (p1.z + p2.z) / 2 };
      var nx = dz / len, nz = -dx / len;
      if (pointInPolygon({ x: mid.x + nx * 0.05, z: mid.z + nz * 0.05 }, rectPts)) {
        nx = -nx; nz = -nz;
      }
      var angle = Math.atan2(-dz, dx);
      var offset = WALL_THICKNESS / 2 + edgeWidth / 2;
      var edge = new THREE.Mesh(new THREE.BoxGeometry(len, SLAB_THICKNESS, edgeWidth), material.clone());
      edge.position.set(mid.x + nx * offset, y - SLAB_THICKNESS / 2, mid.z + nz * offset);
      edge.rotation.y = angle;
      edge.castShadow = true;
      edge.receiveShadow = true;
      group.add(edge);
      if (collector) collector.push(edge);
    }
  }

  // Muros exteriores de un bloque: uno por arista de su rectángulo (AABB),
  // no por habitación — cada bloque/ala es así un único paralelepípedo con
  // cuatro muros a 90°, nunca una forma orgánica. Cada arista larga lleva un
  // hueco de ventana REAL en la geometría (CAMBIO 1): en vez de un único Box
  // ciego, el muro se descompone en dos jambas + antepecho + dintel que
  // dejan un rectángulo vacío, sobre el que se monta el vidrio + marco,
  // flush con la fachada. `collector`, si se pasa, recibe cada mesh
  // generado para que el panel de plantas pueda atenuarlo/ocultarlo más
  // tarde sin tocar los de otras plantas.
  function buildFacadeWalls(group, rectPts, baseY, height, MAT, collector) {
    var n = rectPts.length;
    for (var i = 0; i < n; i++) {
      var p1 = rectPts[i];
      var p2 = rectPts[(i + 1) % n];
      var dx = p2.x - p1.x, dz = p2.z - p1.z;
      var len = Math.sqrt(dx * dx + dz * dz);
      if (len < 0.05) continue;

      var mid = { x: (p1.x + p2.x) / 2, z: (p1.z + p2.z) / 2 };
      var dirX = dx / len, dirZ = dz / len;
      var nx = dz / len, nz = -dx / len;
      if (pointInPolygon({ x: mid.x + nx * 0.05, z: mid.z + nz * 0.05 }, rectPts)) {
        nx = -nx; nz = -nz;
      }
      var angle = Math.atan2(-dz, dx);

      // Pieza de muro (jamba/antepecho/dintel/muro ciego): centrada en
      // `lenOffset` a lo largo de la arista y `hCenter` sobre `baseY`. Cada
      // panel lleva una variación de lightness ±3% (CAMBIO 2) generada al
      // construir, para que la fachada no se lea como un blanco uniforme
      // sin necesidad de texturas reales.
      function addWallPiece(lenOffset, pieceLen, hCenter, pieceHeight) {
        var panelMat = MAT.facade.clone();
        var hsl = { h: 0, s: 0, l: 0 };
        panelMat.color.getHSL(hsl);
        panelMat.color.setHSL(hsl.h, hsl.s, THREE.MathUtils.clamp(hsl.l + (Math.random() * 2 - 1) * 0.03, 0, 1));
        var mesh = new THREE.Mesh(new THREE.BoxGeometry(pieceLen, pieceHeight, WALL_THICKNESS), panelMat);
        mesh.position.set(mid.x + dirX * lenOffset, baseY + hCenter, mid.z + dirZ * lenOffset);
        mesh.rotation.y = angle;
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        group.add(mesh);
        if (collector) collector.push(mesh);
      }

      if (len <= 1.2) {
        // Muro ciego: demasiado corto para una ventana legible.
        addWallPiece(0, len, height / 2, height);
        continue;
      }

      var winW = Math.min(len * 0.55, len - 0.5);
      var winH = height * 0.5;
      var winVCenter = height * 0.55;
      var winBottom = winVCenter - winH / 2;
      var winTop = winVCenter + winH / 2;
      var pierLen = (len - winW) / 2;

      addWallPiece(-(len + winW) / 4, pierLen, height / 2, height); // jamba izquierda
      addWallPiece((len + winW) / 4, pierLen, height / 2, height); // jamba derecha
      addWallPiece(0, winW, winBottom / 2, winBottom); // antepecho
      addWallPiece(0, winW, winTop + (height - winTop) / 2, height - winTop); // dintel

      // Vidrio + marco, flush con la fachada (mismo offset que antes usaba
      // la ventana opaca) — ya NO tapan un muro ciego: detrás hay un hueco
      // real, así que el vidrio deja entrever el interior.
      var flushOffset = WALL_THICKNESS / 2 + 0.03;
      var glassDepth = WALL_THICKNESS * 0.3;
      var glass = new THREE.Mesh(new THREE.BoxGeometry(winW * 0.94, winH * 0.94, glassDepth), MAT.glass.clone());
      glass.userData.kind = "glass";
      glass.position.set(mid.x + nx * flushOffset, baseY + winVCenter, mid.z + nz * flushOffset);
      glass.rotation.y = angle;
      glass.castShadow = true;
      glass.receiveShadow = true;
      group.add(glass);
      if (collector) collector.push(glass);

      var frameT = 0.06;
      function addFrameStrip(lenOffset, pieceLen, hCenter, pieceHeight) {
        var strip = new THREE.Mesh(new THREE.BoxGeometry(pieceLen, pieceHeight, glassDepth * 1.1), MAT.frame.clone());
        strip.position.set(
          mid.x + dirX * lenOffset + nx * flushOffset,
          baseY + hCenter,
          mid.z + dirZ * lenOffset + nz * flushOffset
        );
        strip.rotation.y = angle;
        strip.castShadow = true;
        strip.receiveShadow = true;
        group.add(strip);
        if (collector) collector.push(strip);
      }
      addFrameStrip(0, winW + frameT, winBottom, frameT); // marco inferior
      addFrameStrip(0, winW + frameT, winTop, frameT); // marco superior
      addFrameStrip(-winW / 2, frameT, winVCenter, winH + frameT); // marco izquierdo
      addFrameStrip(winW / 2, frameT, winVCenter, winH + frameT); // marco derecho
    }
  }

  // Particiones interiores de una planta: una línea fina por cada arista de
  // habitación que NO coincide con el casco exterior (esas ya están
  // representadas por el muro real) — se dibujan sobre la losa, no como
  // muros propios, para que la planta se lea como un volumen unificado con
  // las divisiones marcadas encima, no como bloques separados.
  function buildInteriorLines(group, rooms, hullPts, baseY, material, collector) {
    var seen = {};
    rooms.forEach(function (room) {
      var pts = room.pts, n = pts.length;
      for (var i = 0; i < n; i++) {
        var p1 = pts[i], p2 = pts[(i + 1) % n];
        var dx = p2.x - p1.x, dz = p2.z - p1.z;
        var len = Math.sqrt(dx * dx + dz * dz);
        if (len < 0.05) continue;

        var mid = { x: (p1.x + p2.x) / 2, z: (p1.z + p2.z) / 2 };
        if (distToPolygonBoundary(mid, hullPts) < 0.2) continue;

        // Dos habitaciones vecinas comparten la misma arista (mismo punto
        // medio): se dibuja una única línea, no dos superpuestas.
        var key = Math.round(mid.x * 20) + "," + Math.round(mid.z * 20);
        if (seen[key]) continue;
        seen[key] = true;

        var angle = Math.atan2(-dz, dx);
        var line = new THREE.Mesh(
          new THREE.BoxGeometry(len, INTERIOR_LINE_HEIGHT, INTERIOR_LINE_THICKNESS),
          material.clone()
        );
        line.position.set(mid.x, baseY + INTERIOR_LINE_HEIGHT / 2 + 0.01, mid.z);
        line.rotation.y = angle;
        line.receiveShadow = true;
        group.add(line);
        if (collector) collector.push(line);
      }
    });
  }

  // Agrupa las viviendas del proyecto por número de planta (a partir del
  // nombre "Planta N · ..." que genera `ai_generator.py`).
  function groupFloors(viviendas) {
    var byFloor = {};
    (viviendas || []).forEach(function (v) {
      var m = /^Planta\s+(\d+)/i.exec(v.nombre || "");
      var floorNum = m ? parseInt(m[1], 10) : 1;
      (byFloor[floorNum] = byFloor[floorNum] || []).push(v);
    });
    var floorNums = Object.keys(byFloor).map(Number).sort(function (a, b) { return a - b; });
    return floorNums.map(function (n) { return byFloor[n]; });
  }

  // Núcleo de comunicación vertical (2026-08-17, docs/prd/2026-08-17-nucleo-comunicacion-fachada-
  // generador.md): `analyzer/ai_generator.py` añade una unidad "vacía" por planta con ≥2 viviendas
  // (mismo patrón que "Local comercial", ya existente para planta baja comercial) para poder dibujar
  // el núcleo como estancia propia en el plano 2D -- pero ninguna de las dos es una vivienda de
  // verdad, así que ningún recuento de "N viviendas" (header, panel de plantas) debe incluirla. Mismo
  // criterio de detección que `ai_generator._es_unidad_residencial` en el backend: una vivienda con
  // una única habitación cuyo nombre sea exactamente uno de estos dos no es residencial.
  var NOMBRES_HABITACION_NO_RESIDENCIAL = ["Local comercial", "Núcleo de comunicación"];
  function esViviendaResidencial(v) {
    var habs = v.habitaciones || [];
    return !(habs.length === 1 && NOMBRES_HABITACION_NO_RESIDENCIAL.indexOf(habs[0].nombre) !== -1);
  }

  // Polígonos de una vivienda, desplazados a su propio origen local
  // (min→0) — sin posicionarla aún respecto a las demás viviendas ni
  // plantas: eso lo decide `computeFloorBlocks` con el footprint GLOBAL del
  // edificio (PROBLEMA 1). Devuelve también su ancho/fondo "natural" (antes
  // de encajarla en el carril global), que es lo que `computeFloorBlocks`
  // necesita para dimensionar cada carril.
  function extractUnitRooms(vivienda) {
    var unitRooms = (vivienda.habitaciones || [])
      .filter(function (r) { return r.poligono && r.poligono.length >= 3; })
      .map(function (r) {
        return {
          tipo: r.tipo, nombre: r.nombre, area_m2: r.area_m2, problemas: r.problemas || [],
          viviendaId: vivienda.id, viviendaNombre: vivienda.nombre,
          pts: r.poligono.map(function (p) { return { x: p[0], z: -p[1] }; })
        };
      });
    if (!unitRooms.length) return null;

    var minX = Infinity, minZ = Infinity, maxX = -Infinity, maxZ = -Infinity;
    unitRooms.forEach(function (r) {
      r.pts.forEach(function (p) {
        minX = Math.min(minX, p.x); minZ = Math.min(minZ, p.z);
        maxX = Math.max(maxX, p.x); maxZ = Math.max(maxZ, p.z);
      });
    });
    unitRooms.forEach(function (r) {
      r.pts = r.pts.map(function (p) { return { x: p.x - minX, z: p.z - minZ }; });
    });
    return { rooms: unitRooms, width: maxX - minX, depth: maxZ - minZ };
  }

  // PROBLEMA 1 — el edificio salía escalonado lateralmente: cada planta se
  // maquetaba con su propio cursor/AABB independiente (`layoutFloorRooms`
  // original), y como cada planta trae un plano distinto (la IA genera cada
  // nivel por separado), el ancho real de "la vivienda A" variaba de una
  // planta a otra — el mismo carril X terminaba en un sitio distinto según
  // la planta.
  //
  // Fix: el ancho y el fondo de cada CARRIL (posición dentro de la lista de
  // viviendas de la planta — 0="A", 1="B", ...) se fijan UNA SOLA VEZ para
  // todo el edificio, como el máximo de esa posición en todas las plantas.
  // Esa medida global —no el AABB de la vivienda de esa planta en
  // concreto— es el footprint real (`rect`) de cada bloque: la vivienda
  // real se centra dentro de él. Con carriles idénticos en cada planta, el
  // footprint total de cada planta es bit a bit el mismo en X/Z — solo Y
  // (la altura acumulada) varía, y el edificio es un prisma recto.
  function computeFloorBlocks(floorGroups) {
    var rawFloors = floorGroups.map(function (viviendasOnFloor) {
      return viviendasOnFloor.map(extractUnitRooms).filter(Boolean);
    });

    var slotCount = rawFloors.reduce(function (max, units) { return Math.max(max, units.length); }, 0);
    var slotWidth = new Array(slotCount).fill(0);
    var slotDepth = new Array(slotCount).fill(0);
    rawFloors.forEach(function (units) {
      units.forEach(function (u, i) {
        slotWidth[i] = Math.max(slotWidth[i], u.width);
        slotDepth[i] = Math.max(slotDepth[i], u.depth);
      });
    });

    var slotOffsetX = new Array(slotCount).fill(0);
    for (var i = 1; i < slotCount; i++) {
      slotOffsetX[i] = slotOffsetX[i - 1] + slotWidth[i - 1] + UNIT_GAP;
    }

    return rawFloors.map(function (units) {
      return units.map(function (u, i) {
        // Vivienda real centrada dentro de su carril global (en X y en Z),
        // no pegada a una esquina — así el margen sobrante (cuando esa
        // planta trae una vivienda más pequeña que el máximo del carril)
        // queda repartido, no volcado a un lado.
        var dx = slotOffsetX[i] + (slotWidth[i] - u.width) / 2;
        var dz = (slotDepth[i] - u.depth) / 2;
        var rooms = u.rooms.map(function (r) {
          return {
            tipo: r.tipo, nombre: r.nombre, area_m2: r.area_m2, problemas: r.problemas,
            viviendaId: r.viviendaId, viviendaNombre: r.viviendaNombre,
            pts: r.pts.map(function (p) { return { x: p.x + dx, z: p.z + dz }; })
          };
        });
        var rect = [
          { x: slotOffsetX[i], z: 0 },
          { x: slotOffsetX[i] + slotWidth[i], z: 0 },
          { x: slotOffsetX[i] + slotWidth[i], z: slotDepth[i] },
          { x: slotOffsetX[i], z: slotDepth[i] }
        ];
        return { rooms: rooms, rect: rect };
      });
    });
  }

  // Cuadrícula arquitectónica del suelo, generada 100% por código con
  // CanvasTexture (sin imagen externa): un tile cuadrado con un borde fino
  // en su esquina superior/izquierda que, repetido con `RepeatWrapping` y
  // `texture.repeat` = tamaño del suelo en metros, dibuja una línea cada 1m
  // reales del modelo sin depender de la resolución del canvas.
  function buildGridTexture(bgColor, lineColor) {
    var tile = 128;
    var canvas = document.createElement("canvas");
    canvas.width = tile;
    canvas.height = tile;
    var ctx = canvas.getContext("2d");
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, tile, tile);
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0.5, 0);
    ctx.lineTo(0.5, tile);
    ctx.moveTo(0, 0.5);
    ctx.lineTo(tile, 0.5);
    ctx.stroke();
    var texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }

  function buildScene(project) {
    var edificio = project.edificio || {};
    var altura = edificio.altura_libre_m > 0 ? edificio.altura_libre_m : DEFAULT_FLOOR_HEIGHT;

    // Una entrada por planta (ordenadas); los bloques de cada planta vienen
    // de `computeFloorBlocks`, que los alinea a un footprint GLOBAL común a
    // todo el edificio (PROBLEMA 1) — cada planta trae su propio plano
    // (generado por separado por la IA), pero el carril de cada vivienda
    // ocupa siempre el mismo rectángulo en X/Z sea cual sea la planta.
    var floorGroups = groupFloors(project.viviendas).slice(0, MAX_FLOORS);
    var floorBlocks = computeFloorBlocks(floorGroups);
    var floorData = floorBlocks.map(function (blocks, idx) {
      return { baseY: idx * altura, blocks: blocks };
    }).filter(function (f) { return f.blocks.length > 0; });

    if (!floorData.length) return null;

    scene = new THREE.Scene();

    // Sistema de materiales de maqueta arquitectónica (CAMBIO
    // materiales/entorno): fachada clara, losa/cubierta en gris técnico y
    // vidrio semitransparente (MeshStandardMaterial + opacity), no agujeros
    // negros. `interiorLine` no forma parte del encargo pero sigue haciendo
    // falta para las particiones interiores — un gris cálido claro, para
    // leer como junta fina sobre fachada clara y no como raya negra.
    // `scene.environment` (más abajo, en `open()`) se aplica por defecto a
    // TODOS los materiales PBR de la escena, no solo al vidrio — cada
    // material que no fija su propio `envMapIntensity` hereda 1.0, lo que
    // lava fachada/losa/suelo/árboles con el reflejo del interior genérico.
    // Solo el vidrio (CAMBIO 2) debe recibirlo; el resto lo pone a 0 para
    // no perder su color/textura propios.
    // `facade`/`slab`/`roof`/`glass` construidos con las fábricas compartidas
    // de `viewer-materials.js` (mismos parámetros exactos de antes: sin
    // cambio visual). `slabEdge`/`frame`/`sidewalk`/`interiorLine` no
    // corresponden a ninguna de las 6 categorías del sistema compartido
    // (canto de forjado, marco metálico, pavimento urbano, junta de
    // partición) y se quedan como `MeshStandardMaterial` propios de este
    // visor, igual que antes.
    var MAT = {
      facade: createWallMaterial({ color: 0xF5F4F2, roughness: 0.85, metalness: 0.0, envMapIntensity: 0.3 }),
      slab: createFloorMaterial({ color: 0xE8E7E5, roughness: 0.9, metalness: 0.0, envMapIntensity: 0 }),
      // Canto de forjado (CAMBIO 2): banda fina más oscura que la losa, en
      // el perímetro de cada planta — simula el borde visto del forjado.
      slabEdge: new THREE.MeshStandardMaterial({ color: 0xA8A4A0, roughness: 0.85, metalness: 0.0, envMapIntensity: 0 }),
      // Ventanas: MeshStandardMaterial semitransparente (no MeshPhysicalMaterial
      // con transmisión) — encargo explícito de material/tinte fijo en vez de
      // refracción real.
      glass: createGlassMaterial({ color: 0x7BA7BC, roughness: 0.1, metalness: 0.1, opacity: 0.7, envMapIntensity: 0.8 }),
      frame: new THREE.MeshStandardMaterial({ color: 0x2A2A2A, roughness: 0.4, metalness: 0.8, envMapIntensity: 0 }),
      // Acera/bordillo (CAMBIO 3): ligeramente más clara que la plaza, para
      // separar visualmente la parcela del edificio de la calle/plaza. El
      // suelo en sí ya no usa un material fijo aquí — ver `buildGround`
      // (cuadrícula procedural con CanvasTexture).
      sidewalk: new THREE.MeshStandardMaterial({ color: 0x2A2A2A, roughness: 0.9, metalness: 0.0, envMapIntensity: 0 }),
      roof: createCeilingMaterial({ color: 0xD4D3D1, roughness: 0.95, metalness: 0.0, envMapIntensity: 0 }),
      interiorLine: new THREE.MeshStandardMaterial({ color: 0xACA89E, roughness: 0.95, metalness: 0.0, envMapIntensity: 0 })
    };

    // Por planta, un Box independiente por bloque/ala: losa (huella = su
    // rectángulo), cuatro muros con huecos de ventana reales y las
    // particiones interiores como líneas sobre la losa. `levels[i]` guarda
    // los meshes de cada planta para que el panel de plantas (CAMBIO 2)
    // pueda atenuarlos/ocultarlos.
    var building = new THREE.Group();
    levels = floorData.map(function (f) {
      var floorSlabs = [], walls = [], interiorLines = [];
      f.blocks.forEach(function (b) {
        var slab = buildSlab(b.rect, f.baseY, MAT.slab);
        building.add(slab);
        floorSlabs.push(slab);
        buildSlabEdges(building, b.rect, f.baseY, MAT.slabEdge, floorSlabs);
        buildFacadeWalls(building, b.rect, f.baseY, altura, MAT, walls);
        buildInteriorLines(building, b.rooms, b.rect, f.baseY, MAT.interiorLine, interiorLines);
      });
      return { floorSlabs: floorSlabs, walls: walls, interiorLines: interiorLines, roofSlabs: [] };
    });

    // Cubierta: una losa por bloque de la última planta, a la altura del
    // techo del edificio — material `roof` (gris técnico), distinto del de
    // las losas intermedias.
    var topFloor = floorData[floorData.length - 1];
    var topLevel = levels[levels.length - 1];
    topFloor.blocks.forEach(function (b) {
      var roof = buildSlab(b.rect, topFloor.baseY + altura, MAT.roof);
      building.add(roof);
      topLevel.roofSlabs.push(roof);
      buildSlabEdges(building, b.rect, topFloor.baseY + altura, MAT.slabEdge, topLevel.roofSlabs);
    });
    scene.add(building);

    // Índice de habitaciones + malla de impacto invisible (HOVER/Paseo): una
    // extrusión por habitación (huella real, no el rectángulo del bloque),
    // desde el suelo de su planta hasta el techo, con material totalmente
    // transparente (`opacity:0`, `colorWrite:false` — no `visible:false`,
    // que el Raycaster ignora por completo) para que sea invisible pero
    // siga siendo detectable por raycasting. `roomIndex` (mismos registros,
    // sin geometría) sirve además para el nombre de habitación en modo
    // Paseo vía `pointInPolygon`, sin necesidad de raycasting ahí.
    var roomIndex = [];
    var roomHitGroup = new THREE.Group();
    floorData.forEach(function (f) {
      f.blocks.forEach(function (b) {
        b.rooms.forEach(function (r) {
          var record = {
            nombre: r.nombre, tipo: r.tipo, area_m2: r.area_m2, problemas: r.problemas || [],
            viviendaId: r.viviendaId, viviendaNombre: r.viviendaNombre,
            floorBaseY: f.baseY, floorTop: f.baseY + altura, poly: r.pts
          };
          roomIndex.push(record);

          var geometry = extrudeFootprint(r.pts, altura);
          var hitMesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
            transparent: true, opacity: 0, depthWrite: false, colorWrite: false
          }));
          hitMesh.position.y = f.baseY;
          hitMesh.userData.roomRecord = record;
          roomHitGroup.add(hitMesh);
        });
      });
    });
    scene.add(roomHitGroup);

    // buildingSize/centro reales (CAMBIO 4, notas de implementación): la
    // diagonal y el centro del bounding box del edificio YA construido, no
    // una estimación a partir del footprint — de aquí cuelgan la escala de
    // la iluminación, la plaza, los árboles, el cielo y la cámara.
    var box = new THREE.Box3().setFromObject(building);
    var center = box.getCenter(new THREE.Vector3());
    var buildingSize = box.getSize(new THREE.Vector3()).length();

    buildGround(MAT.sidewalk, center, buildingSize, box);
    var treeGroups = buildTrees(center, buildingSize);
    buildSky(center, buildingSize);
    // Niebla atmosférica sutil (CAMBIO materiales/entorno): solo se nota en
    // el horizonte, densidad muy baja.
    scene.fog = new THREE.FogExp2(0x0A0A0A, 0.008);
    buildStudioLighting(center, buildingSize, floorData, altura, project.norte_grados || 0);

    // Punto de partida de la animación de entrada (CAMBIO 3): el edificio
    // arranca hundido bajo el terreno y `open()` lo anima hasta Y=0 — se
    // deja ya colocado aquí para que el primer frame renderizado (antes de
    // que arranque el tween) no muestre un parpadeo del edificio completo
    // en su posición final.
    building.position.y = -buildingSize;

    return {
      center: center, buildingSize: buildingSize, floorsCount: floorData.length,
      buildingGroup: building, treeGroups: treeGroups,
      roomIndex: roomIndex, roomHitGroup: roomHitGroup,
      // Extensión real (ancho X / alto Y / fondo Z) del bounding box, para
      // encuadrar el frustum de las cámaras ortográficas (CAMBIO
      // navegación) — `buildingSize` (la diagonal) no basta para eso.
      boxSize: box.getSize(new THREE.Vector3())
    };
  }

  // --- Escena y contexto urbano (CAMBIO 3) -----------------------------------

  // Aplana a mano el centro de una malla de terreno orgánico ya construida (multiplica la altura de
  // cada vértice por un factor 0→1 en función de su distancia al centro local, con transición suave
  // `smoothstep`) — dentro de `radioSeguro` queda perfectamente plano, entre `radioSeguro` y
  // `radioSeguro+banda` el relieve entra en rampa, más allá queda sin tocar. Los ejes locales X/Y de
  // la geometría (antes de `mesh.rotation.x=-90°`) son los mismos que usa `alturaTerrenoOrganico`
  // internamente para el ruido -- su distancia al origen coincide con la distancia real en el plano
  // XZ de mundo una vez posicionada la malla en `center` (ver llamadas más abajo). Vive aquí (no en
  // `viewer-terreno.js`) para no tocar el módulo que comparte el Sandbox — ver §0/§14 del PRD DEM.
  function aplanarCentroTerreno(mesh, radioSeguro, banda) {
    if (!mesh) return;
    var pos = mesh.geometry.attributes.position;
    for (var i = 0; i < pos.count; i++) {
      var lx = pos.getX(i), ly = pos.getY(i);
      var distancia = Math.sqrt(lx * lx + ly * ly);
      var t = banda > 0 ? THREE.MathUtils.clamp((distancia - radioSeguro) / banda, 0, 1) : (distancia > radioSeguro ? 1 : 0);
      var factor = t * t * (3 - 2 * t); // smoothstep
      pos.setZ(i, pos.getZ(i) * factor);
    }
    pos.needsUpdate = true;
    mesh.geometry.computeVertexNormals();
  }

  function buildGround(sidewalkMaterial, center, buildingSize, box) {
    // "radio" buildingSize*4 (PROBLEMA 2: antes *8, el edificio quedaba
    // pequeño) → lado completo de la plaza buildingSize*8.
    var groundSize = buildingSize * 8;

    // Acera/bordillo (CAMBIO 3): footprint real del edificio + 3m de margen
    // por lado, algo por encima del terreno para taparlo en su zona — así
    // el terreno solo se lee como entorno exterior, nunca como relieve
    // sobre la propia parcela del edificio.
    var margin = 3;
    var sidewalkW = (box.max.x - box.min.x) + margin * 2;
    var sidewalkD = (box.max.z - box.min.z) + margin * 2;
    var sidewalkCenterX = (box.min.x + box.max.x) / 2;
    var sidewalkCenterZ = (box.min.z + box.max.z) / 2;

    // Terreno con relieve orgánico (alternativa sintética del PRD DEM, §14, aprobada 2026-08-16):
    // mismo generador que ya usa el Sandbox (`construirTerrenoOrganico`, sin dependencias nuevas, sin
    // llamada al backend), con la misma cuadrícula procedural de siempre como material — cambia la
    // GEOMETRÍA (deja de ser un plano perfecto), no el material/aspecto general del visor. La parcela
    // real del edificio (acera de arriba) se mantiene siempre plana: aquí solo se aplana un margen de
    // seguridad mínimo alrededor de ella (`radioSeguroBase`). Si más tarde llega una ortofoto REAL
    // (proyecto con sitio vinculado), `aplanarTerrenoBajoOrtofoto` vuelve a aplanar hasta cubrir su
    // extensión real exacta — nunca debe quedar relieve inventado bajo una foto real (ver Riesgos §9
    // del PRD). Con eso, un proyecto sin sitio real (el caso más común) muestra relieve visible cerca
    // del edificio; uno con sitio real prioriza la foto real intacta sobre el relieve decorativo.
    var gridTexture = buildGridTexture("#111111", "#1a1a1a");
    gridTexture.repeat.set(groundSize, groundSize);
    var groundMaterial = new THREE.MeshStandardMaterial({ map: gridTexture, roughness: 0.95, metalness: 0.0, envMapIntensity: 0 });
    var radioSeguroBase = Math.max(Math.hypot(sidewalkW, sidewalkD) / 2 + 5, 15);
    var ground = construirTerrenoOrganico({
      radio: groundSize / 2,
      material: groundMaterial,
      amplitud: 2.2
    });
    aplanarCentroTerreno(ground, radioSeguroBase, 15);
    ground.position.set(center.x, -0.05, center.z);
    scene.add(ground);
    groundMesh = ground;

    var sidewalk = new THREE.Mesh(new THREE.PlaneGeometry(sidewalkW, sidewalkD), sidewalkMaterial.clone());
    sidewalk.rotation.x = -Math.PI / 2;
    sidewalk.position.set(sidewalkCenterX, -0.04, sidewalkCenterZ);
    sidewalk.receiveShadow = true;
    scene.add(sidewalk);
    sidewalkMesh = sidewalk;
  }

  // Vuelve a aplanar `groundMesh` hasta cubrir la extensión REAL del mosaico de ortofoto recién
  // cargado (2026-08-16, alternativa sintética del PRD DEM) -- se llama solo cuando la ortofoto real
  // ya está disponible (ver `cargarEntornoUrbano`), nunca antes: hasta entonces el terreno solo se
  // aplana un margen mínimo de seguridad (ver `buildGround`), porque no hay ninguna foto real que
  // proteger todavía. `esquinaNoroeste`/`esquinaSureste` son metros este/norte reales desde el centro
  // del sitio (mismo origen que usa `construirPlanoOrtofoto`) -- una rotación no cambia la distancia
  // al origen, así que no hace falta `rotarAEjesLocales` para saber el radio real del mosaico.
  function aplanarTerrenoBajoOrtofoto(mosaico) {
    if (!groundMesh) return;
    var radioOrtofoto = Math.hypot(mosaico.esquinaNoroeste.este, mosaico.esquinaNoroeste.norte);
    aplanarCentroTerreno(groundMesh, radioOrtofoto + 8, 25);
  }

  function makeTree(x, z, height) {
    height = height || 4;
    var group = new THREE.Group();

    var trunk = new THREE.Mesh(
      new THREE.CylinderGeometry(0.08, 0.12, height * 0.3, 6),
      new THREE.MeshStandardMaterial({ color: 0x8B6914, roughness: 0.9, metalness: 0.0, envMapIntensity: 0 })
    );
    trunk.position.y = height * 0.15;
    trunk.castShadow = true;
    trunk.receiveShadow = true;

    var foliage = new THREE.Mesh(
      new THREE.SphereGeometry(height * 0.28, 7, 5),
      new THREE.MeshStandardMaterial({ color: 0x4A7C59, roughness: 0.9, metalness: 0.0, envMapIntensity: 0 })
    );
    foliage.scale.y = 0.75;
    foliage.position.y = height * 0.55;
    foliage.castShadow = true;
    foliage.receiveShadow = true;

    group.add(trunk, foliage);
    group.position.set(x, 0, z);
    return group;
  }

  // PROBLEMA 3 — 10 árboles fijos en anillo alrededor del edificio, ya sin
  // invadirlo: ángulos base repartidos a partes iguales (360°/10) con
  // jitter de ±15°, radio nominal en el punto medio de [buildingSize*0.9,
  // buildingSize*1.8] con jitter de ±20% (y recortado a ese rango como red
  // de seguridad). Ningún árbol se coloca a menos de 3 unidades de otro ya
  // colocado — hasta 20 intentos por árbol antes de omitirlo (defensivo:
  // para un buildingSize patológicamente pequeño, mejor un árbol de menos
  // que colgar la pestaña buscando un hueco que no existe).
  function buildTrees(center, buildingSize) {
    var count = 10;
    var minR = buildingSize * 0.9;
    var maxR = buildingSize * 1.8;
    var nominalR = (minR + maxR) / 2;
    var baseAngleStep = (Math.PI * 2) / count;
    var minSeparation = 3;
    var placed = [];
    var trees = [];

    for (var i = 0; i < count; i++) {
      var candidate = null;
      for (var attempt = 0; attempt < 20; attempt++) {
        var angle = i * baseAngleStep + THREE.MathUtils.degToRad((Math.random() * 2 - 1) * 15);
        var r = THREE.MathUtils.clamp(nominalR * (1 + (Math.random() * 2 - 1) * 0.2), minR, maxR);
        var x = center.x + Math.cos(angle) * r;
        var z = center.z + Math.sin(angle) * r;
        var tooClose = placed.some(function (p) { return Math.hypot(p.x - x, p.z - z) < minSeparation; });
        if (!tooClose) { candidate = { x: x, z: z }; break; }
      }
      if (!candidate) continue;
      placed.push(candidate);
      var height = 3 + Math.random() * 2.5;
      var tree = makeTree(candidate.x, candidate.z, height);
      // Variación de escala (0.8-1.2x) y rotación en Y (CAMBIO
      // materiales/entorno): para que los árboles no se lean como copias
      // idénticas repetidas alrededor del edificio.
      tree.scale.setScalar(0.8 + Math.random() * 0.4);
      tree.rotation.y = Math.random() * Math.PI * 2;
      scene.add(tree);
      trees.push(tree);
    }
    return trees;
  }

  function buildSky(center, buildingSize) {
    var skyGeo = new THREE.SphereGeometry(buildingSize * 15, 16, 8);
    var skyMat = new THREE.ShaderMaterial({
      side: THREE.BackSide,
      uniforms: {
        topColor: { value: new THREE.Color(0x87CEEB) },
        bottomColor: { value: new THREE.Color(0xE8F4F8) },
        offset: { value: 5 },
        exponent: { value: 0.4 }
      },
      vertexShader: SKY_VERTEX_SHADER,
      fragmentShader: SKY_FRAGMENT_SHADER
    });
    var sky = new THREE.Mesh(skyGeo, skyMat);
    sky.position.copy(center);
    scene.add(sky);
  }

  // --- Iluminación de estudio arquitectónico (CAMBIO materiales/entorno) -----
  // Azimut del sol: un ángulo base de estudio (135°, SE) rotado por el norte
  // real del proyecto (`norteGrados`) con el mismo criterio de conversión
  // "azimut real → sistema local del edificio" que usa el visor de vivienda
  // (`sunDirectionFor`: se resta `norte`) — así el sol entra por la fachada
  // que corresponde a la orientación declarada, no siempre por la misma
  // esquina del mundo 3D. El vector resultante se trata como dirección desde
  // el CENTRO real del edificio (no el origen del mundo) y se escala con
  // `buildingSize`; por eso hace falta un `sun.target` explícito apuntando
  // al centro — sin él, un DirectionalLight apunta por defecto al origen.

  function buildStudioLighting(center, buildingSize, floorData, altura, norteGrados) {
    // `createFillLights`/`createSunLight` (Fase 2, `viewer-materials.js`):
    // mismos valores exactos que antes (mismo color/intensidad/frustum de
    // sombra) — solo se deja de duplicar la construcción con el visor de
    // vivienda, que ahora arranca de la misma fábrica.
    var fill = createFillLights({ ambientColor: 0x1A2030, ambientIntensity: 0.2, hemisphereIntensity: 0.6 });
    ambientLight = fill.ambient;
    scene.add(ambientLight);
    // Referencia a nivel de módulo (2026-08-16, contexto urbano real): `fill.hemisphere` ya se añadía
    // a la escena más abajo (`scene.add(fill.hemisphere)`) -- esto solo guarda la MISMA instancia en
    // `hemisphereLight` para poder afinar su intensidad si hiciera falta, sin tocar la línea original.
    hemisphereLight = fill.hemisphere;

    var baseAzimuthDeg = 135;
    var elevationDeg = 55;
    var sunDir = directionFromAzimuthElevation(baseAzimuthDeg - (norteGrados || 0), elevationDeg);

    sunLight = createSunLight({
      color: 0xFFF8F0, intensity: 1.2, shadowHalfSize: buildingSize * 2,
      shadowMapSize: 2048, shadowNear: 1, shadowFar: 200, shadowBias: -0.0005, shadowNormalBias: 0.02, shadowRadius: 8
    });
    sunLight.position.copy(center).addScaledVector(sunDir, buildingSize * 3);
    sunLight.target.position.copy(center);
    scene.add(sunLight);
    scene.add(sunLight.target);
    sunLight.shadow.updateMatrices(sunLight);

    scene.add(fill.hemisphere);

    // Luz interior sutil por planta: un PointLight tenue en el centro de
    // cada nivel construido, simula luz interior filtrada por las ventanas.
    (floorData || []).forEach(function (f) {
      var floorLight = new THREE.PointLight(0xFFF5E0, 0.1);
      floorLight.position.set(center.x, f.baseY + altura / 2, center.z);
      scene.add(floorLight);
    });
  }

  // Recoloca el sol ya existente (creado en `buildStudioLighting`) a un azimut/elevación real, sin
  // reconstruir la luz ni su cámara de sombra -- mismo patrón "azimut real - norteGrados" que ya usa
  // `buildStudioLighting` para el sol de estudio (ver el comentario grande encima de esa función).
  // `elevationDeg` se acota a un mínimo de 8° (2026-08-16): un sol real por debajo del horizonte
  // (noche, en la hora real de quien esté probando esto) apuntaría literalmente desde bajo tierra --
  // geometría del todo correcta, pero una escena completamente a oscuras no es lo que pide el encargo
  // ("iluminación natural"); el acotado es una salvaguarda de renderizado explícita, nunca se presenta
  // como si fuera la elevación real (ver aviso que construye `cargarEntornoUrbano`).
  function actualizarDireccionSol(center, buildingSize, azimuthDegReal, elevationDegReal, norteGrados) {
    if (!sunLight) return;
    var elevationDeg = Math.max(elevationDegReal, 8);
    var sunDir = directionFromAzimuthElevation(azimuthDegReal - (norteGrados || 0), elevationDeg);
    sunLight.position.copy(center).addScaledVector(sunDir, buildingSize * 3);
    sunLight.target.position.copy(center);
    sunLight.shadow.updateMatrices(sunLight);
  }

  // --- Contexto urbano real (2026-08-16, a petición explícita) ---------------------------------------
  // Ortofoto real (Esri World Imagery) + volúmenes extruidos de los edificios colindantes reales
  // (Overpass, vía `/api/proyectos/<id>/entorno-3d`) + posición solar real para las coordenadas de la
  // parcela. Todo esto es ADITIVO: nunca sustituye `buildGround`/`buildSky`/el sol de estudio fijo, que
  // siguen construyéndose siempre primero (ver `buildScene`) como fondo de seguridad -- si no hay
  // sitio real enlazado, si Overpass falla, o si las tiles no cargan, el visor sigue exactamente como
  // era antes de este cambio, nunca a medio construir ni con un error visible al usuario. La
  // matemática de tiles/proyección/edificios en sí vive en `viewer-terreno.js` (2026-08-17,
  // compartida con `viewer-sandbox.js` -- Modo Sandbox), importada arriba.

  // Sólido Capaz persistente (2026-08-17, docs/prd/2026-08-17-solido-capaz-persistente-visor-edificio.md):
  // malla translúcida de referencia con la envolvente legal que el arquitecto calculó en el Sandbox antes
  // de generar este proyecto. `solidoCapaz` es el snapshot tal cual lo guardó `analyzer/storage.py`
  // (`poligono_final_local`, `altura_max_m`) -- `null`/geometría insuficiente devuelve `null`, nunca inventa
  // un envolvente.
  //
  // Posicionamiento (decisión explícita, ver §9/§14 del PRD): el edificio generado NO tiene coordenadas
  // absolutas propias -- `ai_generator.py` lo construye en un sistema local propio, sin relación con la
  // parcela real (unificar eso es el riesgo técnico más alto que señala el PRD, y aquí se evita a
  // propósito). En vez de intentar un anclaje geográfico exacto, la envolvente se RECENTRA sobre su propio
  // centroide y se coloca en el mismo punto (`center`, el centro real del bounding box del edificio ya
  // construido) que ya usan `buildGround`/`buildTrees`/`buildSky` -- es honesto en lo que puede serlo hoy:
  // muestra la FORMA y ESCALA reales del Sólido Capaz (superficie, altura) alrededor del edificio, no una
  // superposición geodésicamente exacta que el dato disponible no permite garantizar todavía.
  function construirEnvolventeSolidoCapaz(solidoCapaz, center) {
    if (!solidoCapaz || !Array.isArray(solidoCapaz.poligono_final_local) || solidoCapaz.poligono_final_local.length < 3) {
      return null;
    }
    var alturaMax = Number(solidoCapaz.altura_max_m);
    if (!(alturaMax > 0)) return null;

    var puntos = solidoCapaz.poligono_final_local.map(function (par) { return { x: par[0], z: par[1] }; });
    var sx = 0, sz = 0;
    puntos.forEach(function (p) { sx += p.x; sz += p.z; });
    var centroide = { x: sx / puntos.length, z: sz / puntos.length };
    var puntosCentrados = puntos.map(function (p) { return { x: p.x - centroide.x, z: p.z - centroide.z }; });

    var geometry = extrudeFootprint(puntosCentrados, alturaMax);
    var mesh = new THREE.Mesh(geometry, MAT_ENVOLVENTE_SOLIDO_CAPAZ);
    mesh.renderOrder = 10; // por delante de terreno/ortofoto en el orden de dibujado de transparencias, igual que el Sandbox
    mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry), MAT_BORDE_ENVOLVENTE_SOLIDO_CAPAZ));
    mesh.position.set(center.x, 0, center.z);
    return mesh;
  }

  // Orquesta la carga del contexto urbano real: pide `/api/proyectos/<id>/entorno-3d`, y si hay algo
  // que mostrar, construye ortofoto + edificios + sol real EN PARALELO a que el usuario ya esté viendo
  // el edificio (la escena de siempre ya se renderizó antes de llamar a esto, ver `open()`) -- nunca
  // bloquea la apertura del visor, todo esto llega "de refresco" unos segundos después.
  function cargarEntornoUrbano(proyectoId, center, buildingSize, norteGrados) {
    var miToken = ++entornoFetchToken;
    pedirEntorno3D(proyectoId)
      .then(function (body) {
        if (miToken !== entornoFetchToken || !scene) return; // el visor se cerró/reabrió mientras tanto
        if (!body || !body.disponible) return; // proyecto sin sitio real enlazado -- nada que hacer, sin avisos

        var centro = body.centro;
        var grupo = new THREE.Group();
        grupo.name = "entorno-urbano-real";

        var pendientes = [];
        pendientes.push(
          construirMosaicoOrtofoto(centro.lat, centro.lon).then(function (mosaico) {
            if (miToken !== entornoFetchToken || !scene) return;
            grupo.add(construirPlanoOrtofoto(mosaico, center, norteGrados));
            aplanarTerrenoBajoOrtofoto(mosaico);
          }).catch(function () { /* mosaico best-effort: sin ortofoto real, el suelo sintético sigue ahí debajo */ })
        );

        if ((body.edificios_colindantes || []).length) {
          grupo.add(construirEdificiosColindantes(body.edificios_colindantes, centro, center, norteGrados));
        }

        Promise.all(pendientes).then(function () {
          if (miToken !== entornoFetchToken || !scene) return;
          scene.add(grupo);
          entornoGroup = grupo;
          entornoUrbanoDisponible = true;
          if (btnEntorno) { btnEntorno.hidden = false; btnEntorno.classList.toggle("active", true); }
          if (btnSombras) { btnSombras.hidden = false; btnSombras.classList.toggle("active", sombrasActivas); }
        });

        // Sol real (2026-08-16): se actualiza en cuanto se sabe lat/lon, sin esperar a la ortofoto/los
        // edificios (son peticiones independientes) -- "ahora mismo", hora real del navegador de quien
        // mira el visor, convertida a UTC dentro de `posicionSolar` (ver `solar-posicion.js`). No hay
        // control de hora/estación en la UI todavía (fuera del alcance de este cambio, ver informe de
        // cierre) -- usar el instante real es la aproximación más honesta disponible sin él.
        var posSol = posicionSolar(centro.lat, centro.lon, new Date());
        actualizarDireccionSol(center, buildingSize, posSol.azimut_grados, posSol.elevacion_grados, norteGrados);
      })
      .catch(function () { /* red caída / endpoint no disponible: el visor se queda tal cual estaba */ });
  }

  function aplicarVisibilidadEntorno(visible) {
    if (entornoGroup) entornoGroup.visible = visible;
    if (btnEntorno) btnEntorno.classList.toggle("active", visible);
  }

  function aplicarSombrasActivas(activo) {
    sombrasActivas = activo;
    if (renderer) renderer.shadowMap.enabled = activo;
    if (sunLight) sunLight.castShadow = activo;
    if (btnSombras) btnSombras.classList.toggle("active", activo);
  }

  // --- Panel selector de plantas (CAMBIO 2) ----------------------------------
  // Aísla visualmente una planta: oculta el techo/losa inmediatamente
  // superior (para que se lea como una sección horizontal, con muros y
  // habitaciones visibles) y atenúa (opacity 0.15, transparente) todo lo que
  // hay por encima. Las plantas inferiores quedan opacas normales, tal cual.

  function allLevelMeshes(level) {
    return level.floorSlabs.concat(level.walls, level.interiorLines, level.roofSlabs);
  }

  function setMeshOpacity(mesh, dimmed) {
    var m = mesh.material;
    if (mesh.userData.kind === "glass") {
      m.opacity = dimmed ? 0.1 : GLASS_OPACITY;
    } else {
      m.transparent = dimmed;
      m.opacity = dimmed ? 0.15 : 1;
      m.depthWrite = !dimmed;
    }
    m.needsUpdate = true;
  }

  function restoreAllLevels() {
    levels.forEach(function (level) {
      allLevelMeshes(level).forEach(function (mesh) {
        mesh.visible = true;
        setMeshOpacity(mesh, false);
      });
    });
  }

  function applyFloorMode(selectedIdx) {
    restoreAllLevels();
    levels.forEach(function (level, i) {
      if (i <= selectedIdx) return;
      allLevelMeshes(level).forEach(function (mesh) { setMeshOpacity(mesh, true); });
    });
    // La "ceiling" de la planta seleccionada es la losa de la planta
    // siguiente (o la cubierta, si es la última planta) — se oculta del
    // todo para poder mirar dentro de la planta seleccionada desde arriba.
    var ceiling = (selectedIdx + 1 < levels.length) ? levels[selectedIdx + 1].floorSlabs : levels[selectedIdx].roofSlabs;
    ceiling.forEach(function (mesh) { mesh.visible = false; });
    currentFloorSelection = selectedIdx;
  }

  function resetFloorMode() {
    restoreAllLevels();
    currentFloorSelection = null;
  }

  // Viviendas y superficie total por planta (CAMBIO 2), a partir del
  // proyecto en memoria — no de la geometría 3D. Reutiliza `groupFloors`
  // (misma convención "Planta N · ...") para que el índice de cada entrada
  // coincida con el `idx` que usa `applyFloorMode`/`levels`.
  function computeFloorStats(project) {
    return groupFloors(project.viviendas).map(function (viviendasOnFloor) {
      var reales = viviendasOnFloor.filter(esViviendaResidencial);
      var superficie = reales.reduce(function (sum, v) { return sum + (v.superficie_total_m2 || 0); }, 0);
      return { viviendas: reales.length, superficieM2: superficie };
    });
  }

  // Panel de plantas (CAMBIO 2): lista vertical, planta más alta arriba,
  // cada fila con nº de planta/viviendas/superficie; flechas ▲▼ para subir
  // o bajar una planta sin tener que apuntar a una fila concreta.
  function buildFloorPanel(floorsCount, floorStats) {
    var panel = document.createElement("div");
    panel.className = "floor-panel";
    panel.id = "floor-panel";

    var label = document.createElement("div");
    label.className = "floor-panel-label";
    label.textContent = "Plantas";
    panel.appendChild(label);

    var rowButtons = [];

    function setActiveRow(idx) {
      rowButtons.forEach(function (b, i) { b.classList.toggle("active", i === idx); });
      resetBtn.classList.remove("active");
      upBtn.disabled = idx >= floorsCount - 1;
      downBtn.disabled = idx <= 0;
    }

    function selectFloor(idx) {
      applyFloorMode(idx);
      setActiveRow(idx);
    }

    var upBtn = document.createElement("button");
    upBtn.type = "button";
    upBtn.className = "floor-panel-step step-up";
    upBtn.textContent = "▲";
    upBtn.setAttribute("aria-label", "Planta superior");
    upBtn.addEventListener("click", function () {
      var next = currentFloorSelection === null ? floorsCount - 1 : Math.min(floorsCount - 1, currentFloorSelection + 1);
      selectFloor(next);
    });
    panel.appendChild(upBtn);

    var list = document.createElement("div");
    list.className = "floor-panel-list";
    for (var i = floorsCount - 1; i >= 0; i--) {
      (function (idx) {
        var stats = (floorStats && floorStats[idx]) || { viviendas: 0, superficieM2: 0 };
        var row = document.createElement("button");
        row.type = "button";
        row.className = "floor-panel-row";
        row.innerHTML =
          '<span class="floor-row-dot"></span>' +
          '<span class="floor-row-label">P' + (idx + 1) + '</span>' +
          '<span class="floor-row-meta">' + stats.viviendas + ' viv · ' + Math.round(stats.superficieM2) + 'm²</span>';
        row.addEventListener("click", function () { selectFloor(idx); });
        rowButtons[idx] = row;
        list.appendChild(row);
      })(i);
    }
    panel.appendChild(list);

    var downBtn = document.createElement("button");
    downBtn.type = "button";
    downBtn.className = "floor-panel-step step-down";
    downBtn.textContent = "▼";
    downBtn.setAttribute("aria-label", "Planta inferior");
    downBtn.addEventListener("click", function () {
      var next = currentFloorSelection === null ? 0 : Math.max(0, currentFloorSelection - 1);
      selectFloor(next);
    });
    panel.appendChild(downBtn);

    var resetBtn = document.createElement("button");
    resetBtn.type = "button";
    resetBtn.className = "floor-panel-reset active";
    resetBtn.textContent = "Edificio completo";
    resetBtn.addEventListener("click", function () {
      resetFloorMode();
      rowButtons.forEach(function (b) { b.classList.remove("active"); });
      resetBtn.classList.add("active");
      upBtn.disabled = false;
      downBtn.disabled = false;
    });
    panel.appendChild(resetBtn);

    upBtn.disabled = false;
    downBtn.disabled = false;
    mount.appendChild(panel);
  }

  // Brújula minimalista (CAMBIO 5): una "N" con flecha, esquina superior
  // izquierda, que rota con `controls.addEventListener('change', ...)` para
  // seguir señalando el norte del mundo (-Z, ver convención de
  // `buildStudioLighting`/comentario original de iluminación) según orbita
  // la cámara.
  function buildCompass(orbitControls) {
    var compass = document.createElement("div");
    compass.className = "viewer-compass";
    compass.id = "viewer-compass";
    compass.title = "Volver al norte";
    compass.setAttribute("aria-label", "Volver al norte");
    compass.innerHTML =
      '<div class="viewer-compass-needle" id="viewer-compass-needle">' +
      '<svg viewBox="0 0 52 52" xmlns="http://www.w3.org/2000/svg">' +
      '<circle cx="26" cy="26" r="24" fill="none" stroke="rgba(255,255,255,0.35)" stroke-width="1"/>' +
      '<path d="M26 6 L31 26 L26 22 L21 26 Z" fill="#fff"/>' +
      '<text x="26" y="17" text-anchor="middle" font-size="9" font-weight="700" fill="#fff">N</text>' +
      "</svg></div>";
    mount.appendChild(compass);

    var needle = compass.querySelector("#viewer-compass-needle");
    function update() {
      var dx = camera.position.x - orbitControls.target.x;
      var dz = camera.position.z - orbitControls.target.z;
      var deg = Math.atan2(dx, dz) * 180 / Math.PI;
      needle.style.transform = "rotate(" + -deg + "deg)";
    }
    orbitControls.addEventListener("change", update);
    update();

    // Clic en la brújula (navegación fluida, 2026-08-16): recupera el norte (aguja apuntando arriba,
    // `deg=0` en `update()` de arriba → cámara en el eje +Z local respecto al target, sin `dx`) sin
    // tocar el radio (zoom) ni la elevación actuales -- mismo mecanismo de tween que ya usan los
    // botones de vista (`animateCameraTo`), verificado seguro con cambios directos de
    // `camera.position` (`switchCameraType`/`getCameraPose` ya lo hacían).
    compass.addEventListener("click", function () {
      if (!camera || !controls || walkActive) return;
      var offset = camera.position.clone().sub(controls.target);
      var radioHorizontal = Math.sqrt(Math.max(0, offset.x * offset.x + offset.z * offset.z));
      var nuevaPos = controls.target.clone().add(new THREE.Vector3(0, offset.y, radioHorizontal));
      animateCameraTo(nuevaPos, controls.target.clone(), 600);
    });
  }

  // --- Cámara ortográfica + escala gráfica (NAVEGACIÓN) -----------------------
  // Planta/Alzado/Lateral cambian de `PerspectiveCamera` a una única
  // `OrthographicCamera` reutilizada entre las tres (su frustum se
  // recalcula cada vez, ver `fitOrthoFrustum`) — "sin perspectiva" tal
  // cual pide el encargo, con el edificio real (no la diagonal del
  // bounding box) llenando el 80% de la pantalla en cada eje.

  var SCALE_BAR_CANDIDATES_M = [0.5, 1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000];
  var SCALE_BAR_TARGET_PX = 110;

  // Overlays fijos del modo Paseo (crosshair, HUD de habitación, aviso de
  // controles, minimap): se crean una vez por `open()` y solo se
  // muestran/ocultan (`.visible`) al entrar/salir de `enterWalkMode` —
  // mismo patrón que la brújula/escala gráfica, sin reconstruir DOM en
  // cada toggle del botón "Paseo".
  function buildWalkOverlays() {
    var crosshair = document.createElement("div");
    crosshair.className = "viewer-crosshair";
    crosshair.id = "viewer-crosshair";
    mount.appendChild(crosshair);

    var hud = document.createElement("div");
    hud.className = "viewer-room-hud";
    hud.id = "viewer-room-hud";
    mount.appendChild(hud);

    var instructions = document.createElement("div");
    instructions.className = "viewer-walk-instructions";
    instructions.id = "viewer-walk-instructions";
    instructions.textContent = "WASD mover · Ratón girar · ESC salir";
    mount.appendChild(instructions);

    var minimap = document.createElement("div");
    minimap.className = "viewer-minimap";
    minimap.id = "viewer-minimap";
    minimap.innerHTML = '<canvas id="viewer-minimap-canvas" width="120" height="120"></canvas>';
    mount.appendChild(minimap);
  }

  // HUD de zoom +/- y recentrar (navegación fluida, 2026-08-16): botones fijos, creados una vez por
  // `open()` igual que la brújula/escala gráfica. El zoom/recentrar reposicionan la cámara con el
  // mismo tween manual (`animateCameraTo`) que ya usan los botones de vista — sin instrucciones nuevas
  // a OrbitControls, solo mover `camera.position`/`controls.target` y dejar que `controls.update()`
  // (llamado cada frame) recalcule su estado interno a partir de la posición ya animada.
  function buildNavHud() {
    var hud = document.createElement("div");
    hud.className = "viewer-nav-hud";
    hud.id = "viewer-nav-hud";
    hud.innerHTML =
      '<button type="button" class="viewer-nav-btn" id="viewer-nav-zoom-in" title="Acercar" aria-label="Acercar">+</button>' +
      '<button type="button" class="viewer-nav-btn" id="viewer-nav-zoom-out" title="Alejar" aria-label="Alejar">&minus;</button>' +
      '<button type="button" class="viewer-nav-btn viewer-nav-btn-recentrar" id="viewer-nav-recentrar" title="Recentrar" aria-label="Recentrar">&#8982;</button>';
    mount.appendChild(hud);

    function dolly(factor) {
      if (!camera || !controls || walkActive) return;
      var offset = camera.position.clone().sub(controls.target);
      var distanciaActual = offset.length();
      if (distanciaActual < 1e-6) return;
      var distancia = THREE.MathUtils.clamp(distanciaActual * factor, controls.minDistance, controls.maxDistance);
      var nuevaPos = controls.target.clone().add(offset.multiplyScalar(distancia / distanciaActual));
      animateCameraTo(nuevaPos, controls.target.clone(), 350);
    }
    document.getElementById("viewer-nav-zoom-in").addEventListener("click", function () { dolly(0.72); });
    document.getElementById("viewer-nav-zoom-out").addEventListener("click", function () { dolly(1.38); });
    document.getElementById("viewer-nav-recentrar").addEventListener("click", function () {
      if (!lastInfo || walkActive) return;
      if (camera !== perspCamera) {
        switchCameraType(false);
        Array.prototype.forEach.call(document.querySelectorAll(".cam-btn"), function (b) {
          b.classList.toggle("active", b.dataset.view === "perspective");
        });
      }
      var pose = getCameraPose("perspective", lastInfo);
      animateCameraTo(pose.pos, pose.target, 700);
    });
  }

  // Recentrado por doble clic sobre terreno/entorno urbano (navegación fluida, 2026-08-16, Google
  // Earth-like): raycast SOLO contra `groundMesh`/`sidewalkMesh`/`entornoGroup` (terreno orgánico,
  // acera, ortofoto real y colindantes reales) — deliberadamente NO incluye `roomHitGroup`/el edificio
  // del proyecto. Motivo (decisión explícita de Pablo, 2026-08-16): un solo clic sobre una habitación
  // visible ya la selecciona y CIERRA el visor (`onPointerClickBuilding`) — con el edificio como
  // objetivo válido, el primer clic de cualquier doble clic ahí desmontaría la escena antes de que el
  // segundo pudiera recentrar nada. Preserva el offset cámara↔target actual (mismo radio/ángulo,
  // nuevo pivote) en vez de forzar un zoom — "recentra el pivote", no "salta a una vista nueva".
  var dblClickRaycaster = new THREE.Raycaster();
  function onDblClickRecenter(e) {
    if (!camera || !controls || walkActive || currentOrthoView) return;
    var ndc = session.pointerToNDC(e.clientX, e.clientY);
    if (!ndc) return;
    var objetivos = [];
    if (groundMesh) objetivos.push(groundMesh);
    if (sidewalkMesh) objetivos.push(sidewalkMesh);
    if (entornoGroup) objetivos.push(entornoGroup);
    if (!objetivos.length) return;
    dblClickRaycaster.setFromCamera(ndc, camera);
    var hits = dblClickRaycaster.intersectObjects(objetivos, true);
    if (!hits.length) return;
    var punto = hits[0].point;
    var offset = camera.position.clone().sub(controls.target);
    animateCameraTo(punto.clone().add(offset), punto.clone(), 550);
  }

  function buildScaleBar() {
    var el = document.createElement("div");
    el.className = "viewer-scale-bar";
    el.id = "viewer-scale-bar";
    el.innerHTML = '<div class="scale-bar-label" id="scale-bar-label">10 m</div><div class="scale-bar-line" id="scale-bar-line"></div>';
    mount.appendChild(el);
  }

  function updateScaleBar() {
    var el = document.getElementById("viewer-scale-bar");
    if (!el) return;
    if (!currentOrthoView || !orthoCamera) { el.classList.remove("visible"); return; }
    var width = mount.clientWidth || 800;
    var worldWidth = (orthoCamera.right - orthoCamera.left) / (orthoCamera.zoom || 1);
    if (!(worldWidth > 0)) return;
    var pxPerMeter = width / worldWidth;
    var best = SCALE_BAR_CANDIDATES_M[0];
    SCALE_BAR_CANDIDATES_M.forEach(function (m) {
      if (Math.abs(m * pxPerMeter - SCALE_BAR_TARGET_PX) < Math.abs(best * pxPerMeter - SCALE_BAR_TARGET_PX)) best = m;
    });
    document.getElementById("scale-bar-line").style.width = Math.round(best * pxPerMeter) + "px";
    document.getElementById("scale-bar-label").textContent = best + " m";
    el.classList.add("visible");
  }

  // Frustum del `OrthographicCamera` para que la proyección REAL del
  // edificio en ese plano (no la diagonal 3D) llene el 80% de pantalla,
  // respetando el aspect ratio del visor (letterbox en el eje sobrante).
  // `resetZoom=false` (redimensionado de ventana) conserva el zoom manual
  // del usuario en vez de recentrar la vista.
  function fitOrthoFrustum(view, info, resetZoom) {
    if (!orthoCamera || !info) return;
    var width = mount.clientWidth || 800, height = mount.clientHeight || 600;
    var aspect = width / height;
    var size = info.boxSize;
    var pw, ph;
    if (view === "top") { pw = size.x; ph = size.z; }
    else if (view === "front") { pw = size.x; ph = size.y; }
    else { pw = size.z; ph = size.y; }
    var FILL = 0.8;
    var halfW = Math.max(pw, 0.5) / 2 / FILL;
    var halfH = Math.max(ph, 0.5) / 2 / FILL;
    if (halfW / halfH > aspect) halfH = halfW / aspect; else halfW = halfH * aspect;
    orthoCamera.left = -halfW;
    orthoCamera.right = halfW;
    orthoCamera.top = halfH;
    orthoCamera.bottom = -halfH;
    orthoCamera.near = 0.1;
    orthoCamera.far = Math.max(1000, info.buildingSize * 20 + 100);
    if (resetZoom !== false) orthoCamera.zoom = 1;
    orthoCamera.updateProjectionMatrix();
    currentOrthoView = view;
    updateScaleBar();
  }

  // Cambia la cámara activa (`camera`) entre la perspectiva construida en
  // `open()` y la ortográfica compartida, reapuntando controles y los
  // passes del composer que guardan su propia referencia a la cámara —
  // sin esto el SSAO/RenderPass seguirían leyendo la cámara anterior tras
  // el cambio. Las vistas ortográficas bloquean la rotación de órbita
  // (`enableRotate=false`): son lecturas técnicas "sin perspectiva",
  // pensadas para no salir de su ángulo recto, no vistas orbitables más.
  function switchCameraType(toOrtho) {
    if (!controls || !camera) return;
    var width = mount.clientWidth || 800, height = mount.clientHeight || 600;
    // Conserva la posición de la cámara saliente: si no, la entrante (sobre
    // todo `orthoCamera` recién creada) arrancaría en (0,0,0) y el salto se
    // vería en vez de quedar disimulado por el tween de `animateCameraTo`
    // que el llamador encadena justo después.
    var prevPos = camera.position.clone();
    if (toOrtho) {
      if (!orthoCamera) orthoCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 2000);
      camera = orthoCamera;
      controls.enableRotate = false;
      // `minPolarAngle`/`maxPolarAngle` (5°-85°, encargo) protegen la órbita
      // libre de Perspectiva del cénit/subsuelo — pero Planta ES el cénit
      // (polar ~0°) y Alzado/Lateral SON el horizonte (polar 90°), así que
      // en las vistas técnicas se sueltan del todo (sin efecto real, porque
      // `enableRotate=false` ya impide que el usuario orbite) para que
      // `controls.update()` no le "arrastre" la pose forzada de vuelta al
      // rango pensado para Perspectiva.
      controls.minPolarAngle = 0;
      controls.maxPolarAngle = Math.PI;
    } else {
      camera = perspCamera;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      controls.enableRotate = true;
      controls.minPolarAngle = THREE.MathUtils.degToRad(5);
      controls.maxPolarAngle = THREE.MathUtils.degToRad(85);
      currentOrthoView = null;
      updateScaleBar();
    }
    camera.position.copy(prevPos);
    // Mantiene sincronizados el alias local y la cámara activa de la sesión
    // (de la que dependen el `aspect` al redimensionar y `pointerToNDC`).
    session.setCamera(camera);
    if (renderPassRef) renderPassRef.camera = camera;
    if (ssaoPassRef) ssaoPassRef.camera = camera;
    controls.update();
  }

  // --- Modo paseo (CAMBIO 4, experimental) -----------------------------------
  // Primera persona básico: Pointer Lock para mirar con el ratón, WASD para
  // moverse. Colisión "básica" tal como se pidió: un raycast horizontal en
  // la dirección de movimiento bloquea avanzar si hay un muro/losa a menos
  // de `WALK_COLLIDE_RADIUS`, y un raycast vertical hacia abajo mantiene la
  // altura de persona sobre lo que haya debajo (losa de planta baja si se
  // está dentro del edificio, terreno si se está fuera) — no es una física
  // de colisión completa, pero cumple "no atravesar los meshes del edificio".

  function onWalkKeyDown(e) {
    walkKeys[e.code] = true;
    // Salida alternativa a ESC (encargo): ESC ya la consume el Pointer
    // Lock (`onPointerLockChange` → `exitWalkMode`), "E" sale explícitamente
    // sin depender de eso.
    if (e.code === "KeyE") exitWalkMode();
  }
  function onWalkKeyUp(e) { walkKeys[e.code] = false; }

  function onWalkMouseMove(e) {
    if (!walkActive) return;
    var sensitivity = 0.0025;
    walkYaw -= e.movementX * sensitivity;
    walkPitch = THREE.MathUtils.clamp(walkPitch - e.movementY * sensitivity, -Math.PI * 0.48, Math.PI * 0.48);
  }

  function onPointerLockChange() {
    if (walkActive && document.pointerLockElement !== renderer.domElement) exitWalkMode();
  }

  function enterWalkMode() {
    if (!camera || !controls || walkActive) return;
    // El paseo en primera persona no tiene sentido con una cámara
    // ortográfica (Planta/Alzado/Lateral) — se fuerza la perspectiva antes
    // de entrar, igual que si se hubiera pulsado "Perspectiva" a mano.
    if (camera !== perspCamera) {
      switchCameraType(false);
      Array.prototype.forEach.call(document.querySelectorAll(".cam-btn"), function (b) {
        b.classList.toggle("active", b.dataset.view === "perspective");
      });
    }
    walkActive = true;
    walkSavedCamPos = camera.position.clone();
    walkSavedTarget = controls.target.clone();
    controls.enabled = false;

    var dir = new THREE.Vector3();
    camera.getWorldDirection(dir);
    walkYaw = Math.atan2(dir.x, dir.z);
    walkPitch = 0;
    camera.position.y = WALK_HEIGHT;

    walkKeys = Object.create(null);
    document.addEventListener("keydown", onWalkKeyDown);
    document.addEventListener("keyup", onWalkKeyUp);
    document.addEventListener("mousemove", onWalkMouseMove);
    document.addEventListener("pointerlockchange", onPointerLockChange);
    var lockResult = renderer.domElement.requestPointerLock();
    if (lockResult && lockResult.catch) lockResult.catch(function () {});

    var btn = document.getElementById("btn-paseo");
    if (btn) btn.classList.add("active");

    // Overlays del modo Paseo: crosshair + minimap fijos mientras dure el
    // paseo; el panel de plantas se oculta (no tiene sentido aislar plantas
    // en primera persona y comparte esquina con el minimap) y se restaura
    // al salir. Las instrucciones se desvanecen solas a los 3s.
    var crosshair = document.getElementById("viewer-crosshair");
    if (crosshair) crosshair.classList.add("visible");
    var minimap = document.getElementById("viewer-minimap");
    if (minimap) minimap.classList.add("visible");
    var panel = document.getElementById("floor-panel");
    if (panel) panel.style.display = "none";
    var hud = document.getElementById("viewer-room-hud");
    walkCurrentRoomName = null;
    if (hud) hud.classList.remove("visible");

    var instructions = document.getElementById("viewer-walk-instructions");
    if (instructions) {
      instructions.classList.add("visible");
      if (walkInstructionsTimer) clearTimeout(walkInstructionsTimer);
      walkInstructionsTimer = setTimeout(function () {
        instructions.classList.remove("visible");
        walkInstructionsTimer = null;
      }, 3000);
    }
  }

  function exitWalkMode() {
    if (!walkActive) return;
    walkActive = false;
    document.removeEventListener("keydown", onWalkKeyDown);
    document.removeEventListener("keyup", onWalkKeyUp);
    document.removeEventListener("mousemove", onWalkMouseMove);
    document.removeEventListener("pointerlockchange", onPointerLockChange);
    if (document.pointerLockElement) document.exitPointerLock();
    if (camera && walkSavedCamPos) camera.position.copy(walkSavedCamPos);
    if (controls && walkSavedTarget) {
      controls.target.copy(walkSavedTarget);
      controls.enabled = true;
      controls.update();
    }
    var btn = document.getElementById("btn-paseo");
    if (btn) btn.classList.remove("active");

    var crosshair = document.getElementById("viewer-crosshair");
    if (crosshair) crosshair.classList.remove("visible");
    var minimap = document.getElementById("viewer-minimap");
    if (minimap) minimap.classList.remove("visible");
    var hud = document.getElementById("viewer-room-hud");
    if (hud) hud.classList.remove("visible");
    var instructions = document.getElementById("viewer-walk-instructions");
    if (instructions) instructions.classList.remove("visible");
    if (walkInstructionsTimer) { clearTimeout(walkInstructionsTimer); walkInstructionsTimer = null; }
    var panel = document.getElementById("floor-panel");
    if (panel) panel.style.display = "";
  }

  // Recorre `buildingGroup` UNA vez y cachea, por malla, su esfera envolvente
  // en coordenadas de mundo (centro + radio). `buildingGroup` solo se traslada
  // en Y durante la animación de entrada (ver `building.position.y` en
  // `buildScene` y el tween en `open()`) y esa animación ya ha terminado
  // cuando se puede pulsar "Paseo", así que world-space es estable mientras
  // dure el paseo sobre este mismo edificio.
  function buildWalkColliders(buildingGroup) {
    var list = [];
    buildingGroup.updateMatrixWorld(true);
    var scale = new THREE.Vector3();
    var pos = new THREE.Vector3();
    var quat = new THREE.Quaternion();
    buildingGroup.traverse(function (obj) {
      if (!obj.isMesh || !obj.geometry) return;
      var geo = obj.geometry;
      if (!geo.boundingSphere) geo.computeBoundingSphere();
      if (!geo.boundingSphere) return;
      obj.matrixWorld.decompose(pos, quat, scale);
      var center = geo.boundingSphere.center.clone().applyMatrix4(obj.matrixWorld);
      var radius = geo.boundingSphere.radius * Math.max(scale.x, scale.y, scale.z);
      list.push({ mesh: obj, center: center, radius: radius });
    });
    return list;
  }

  // Mismo resultado que `walkRaycaster.intersectObject(buildingGroup, true)`,
  // pero sin recorrer la jerarquía: cualquier malla cuya esfera envolvente
  // esté a más de `far + radio` del origen no puede cortar un rayo de
  // longitud `far` desde ese origen caiga como caiga su dirección, así que
  // descartarla de antemano no cambia qué se golpea — solo evita testearla.
  function raycastColliders(origin, direction, far) {
    if (!walkColliders || !walkColliders.length) return [];
    var candidates = [];
    for (var i = 0; i < walkColliders.length; i++) {
      var c = walkColliders[i];
      if (origin.distanceTo(c.center) <= far + c.radius) candidates.push(c.mesh);
    }
    if (!candidates.length) return [];
    walkRaycaster.set(origin, direction);
    walkRaycaster.far = far;
    return walkRaycaster.intersectObjects(candidates, false);
  }

  function updateWalkMode(buildingGroup, dt) {
    if (!walkActive || !camera) return;

    if (buildingGroup && walkCollidersFor !== buildingGroup) {
      walkColliders = buildWalkColliders(buildingGroup);
      walkCollidersFor = buildingGroup;
    }

    camera.quaternion.setFromEuler(new THREE.Euler(walkPitch, walkYaw, 0, "YXZ"));

    var forward = new THREE.Vector3(Math.sin(walkYaw), 0, Math.cos(walkYaw));
    var right = new THREE.Vector3(forward.z, 0, -forward.x);
    var move = new THREE.Vector3();
    if (walkKeys.KeyW || walkKeys.ArrowUp) move.sub(forward);
    if (walkKeys.KeyS || walkKeys.ArrowDown) move.add(forward);
    if (walkKeys.KeyD || walkKeys.ArrowRight) move.add(right);
    if (walkKeys.KeyA || walkKeys.ArrowLeft) move.sub(right);

    if (move.lengthSq() > 0) {
      move.normalize().multiplyScalar(WALK_SPEED * dt);
      var blocked = false;
      if (buildingGroup) {
        var moveFar = WALK_COLLIDE_RADIUS + move.length();
        var hits = raycastColliders(camera.position, move.clone().normalize(), moveFar);
        blocked = hits.length > 0 && hits[0].distance < moveFar;
      }
      if (!blocked) camera.position.add(move);
    }

    // Altura de "persona" sobre lo que haya debajo, no una altura fija: sin
    // esto, caminar dentro del edificio dejaría la cámara flotando a la
    // altura de la planta baja aunque el suelo real (terreno) esté a otra
    // cota, o viceversa.
    var groundY = 0;
    if (buildingGroup) {
      var groundOrigin = new THREE.Vector3(camera.position.x, camera.position.y + 5, camera.position.z);
      var groundHits = raycastColliders(groundOrigin, new THREE.Vector3(0, -1, 0), 20);
      if (groundHits.length) groundY = groundHits[0].point.y;
    }
    camera.position.y = groundY + WALK_HEIGHT;

    updateWalkRoomHud();
    updateMinimap();
  }

  // Nombre de la habitación bajo la cámara (Paseo), por `pointInPolygon`
  // contra `lastInfo.roomIndex` — más barato y robusto por frame que
  // raycasting contra la malla de impacto (HOVER usa esa vía en su lugar,
  // ver `onPointerMoveBuilding`), y evita reescribir el DOM si no cambió.
  function updateWalkRoomHud() {
    var hud = document.getElementById("viewer-room-hud");
    if (!hud) return;
    var room = roomAtPoint(camera.position.x, camera.position.y, camera.position.z);
    var name = room ? room.nombre : null;
    if (name === walkCurrentRoomName) return;
    walkCurrentRoomName = name;
    if (name) {
      hud.textContent = name;
      hud.classList.add("visible");
    } else {
      hud.classList.remove("visible");
    }
  }

  // Minimap 2D (Paseo, esquina inferior derecha): silueta simplificada de
  // las habitaciones (`lastInfo.roomIndex`, ya en coordenadas mundo XZ) más
  // un punto azul con una marca de rumbo para la posición/orientación
  // actual de la cámara — Canvas 2D plano, no un segundo viewport 3D.
  function updateMinimap() {
    var canvas = document.getElementById("viewer-minimap-canvas");
    if (!canvas || !lastInfo || !camera) return;
    var ctx = canvas.getContext("2d");
    var W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    var half = Math.max(lastInfo.boxSize.x, lastInfo.boxSize.z, 1) / 2 * 1.2;
    var cx = lastInfo.center.x, cz = lastInfo.center.z;
    function toXY(x, z) {
      return { x: ((x - cx) / half) * (W / 2) + W / 2, y: ((z - cz) / half) * (H / 2) + H / 2 };
    }

    ctx.fillStyle = "rgba(255, 255, 255, 0.55)";
    (lastInfo.roomIndex || []).forEach(function (r) {
      if (!r.poly || r.poly.length < 3) return;
      ctx.beginPath();
      r.poly.forEach(function (p, i) {
        var pt = toXY(p.x, p.z);
        if (i === 0) ctx.moveTo(pt.x, pt.y); else ctx.lineTo(pt.x, pt.y);
      });
      ctx.closePath();
      ctx.fill();
    });

    var camXY = toXY(camera.position.x, camera.position.z);
    ctx.strokeStyle = "#2e86de";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(camXY.x, camXY.y);
    ctx.lineTo(camXY.x + Math.sin(walkYaw) * 10, camXY.y + Math.cos(walkYaw) * 10);
    ctx.stroke();

    ctx.fillStyle = "#2e86de";
    ctx.beginPath();
    ctx.arc(camXY.x, camXY.y, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "rgba(255, 255, 255, 0.9)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // --- Hover sobre habitaciones (NAVEGACIÓN) -----------------------------------

  function onPointerMoveBuilding(e) { pointerClientXY = { x: e.clientX, y: e.clientY }; }
  function onPointerLeaveBuilding() { pointerClientXY = null; }

  function showRoomTooltip(record, clientX, clientY) {
    var tooltip = document.getElementById("room-tooltip");
    if (!tooltip) return;
    tooltip.querySelector(".tooltip-title").textContent = record.nombre || "";
    var areaTxt = record.area_m2 != null ? record.area_m2.toFixed(2) + " m²" : "";
    tooltip.querySelector(".tooltip-area").textContent =
      record.viviendaNombre ? areaTxt + " · " + record.viviendaNombre : areaTxt;
    var n = (record.problemas || []).length;
    var probEl = tooltip.querySelector(".tooltip-problems");
    probEl.innerHTML = '<div style="color:' + (n > 0 ? "#dc2626" : "#16a34a") + '">' +
      (n > 0 ? n + (n === 1 ? " problema detectado" : " problemas detectados") : "Sin problemas detectados") +
      "</div>";
    tooltip.hidden = false;
    positionRoomTooltip(clientX, clientY);
  }
  function positionRoomTooltip(clientX, clientY) {
    positionTooltip(document.getElementById("room-tooltip"), clientX, clientY);
  }
  function hideRoomTooltip() {
    var tooltip = document.getElementById("room-tooltip");
    if (tooltip) tooltip.hidden = true;
  }

  function clearHoverOutline() {
    if (!hoverOutlineMesh) return;
    if (hoverOutlineMesh.parent) hoverOutlineMesh.parent.remove(hoverOutlineMesh);
    hoverOutlineMesh.children[0].material.dispose();
    hoverOutlineMesh = null;
  }

  function clearHover() {
    if (!hoveredRoomMesh) return;
    hoveredRoomMesh = null;
    clearHoverOutline();
    hideRoomTooltip();
  }

  // Outline sutil (encargo: "segunda geometría ligeramente escalada con
  // material de lado trasero", técnica estándar): reutiliza la MISMA
  // geometría del mesh de impacto (sin clonarla) dentro de un `Group`
  // "pivote" cuyo `position`/`scale` se calculan para que el escalado
  // ocurra alrededor del centroide REAL de la habitación, no del origen
  // local de la geometría (que son las coordenadas mundo XZ del polígono
  // tal cual, muy lejos de (0,0) — escalar el mesh directamente desplazaría
  // el contorno en vez de "engordarlo").
  function setHoveredRoom(mesh) {
    clearHoverOutline();
    hoveredRoomMesh = mesh;
    var record = mesh.userData.roomRecord;

    var cx = 0, cz = 0;
    record.poly.forEach(function (p) { cx += p.x; cz += p.z; });
    cx /= record.poly.length; cz /= record.poly.length;

    var s = 1.015;
    var pivot = new THREE.Group();
    pivot.position.set(cx * (1 - s), mesh.position.y, cz * (1 - s));
    pivot.scale.setScalar(s);
    var outlineMat = new THREE.MeshBasicMaterial({
      color: 0x2563eb, side: THREE.BackSide, transparent: true, opacity: 0.6, depthWrite: false
    });
    pivot.add(new THREE.Mesh(mesh.geometry, outlineMat));
    mesh.parent.add(pivot);
    hoverOutlineMesh = pivot;
  }

  function updateHover() {
    if (!lastInfo || !lastInfo.roomHitGroup || !camera || !session || walkActive || !pointerClientXY) {
      clearHover();
      return;
    }
    // `pointerToNDC` devuelve null si el cursor cae fuera del canvas.
    var ndc = session.pointerToNDC(pointerClientXY.x, pointerClientXY.y);
    if (!ndc) { clearHover(); return; }
    hoverRaycaster.setFromCamera(ndc, camera);
    var hits = hoverRaycaster.intersectObjects(lastInfo.roomHitGroup.children, false);
    if (!hits.length) { clearHover(); return; }
    var mesh = hits[0].object;
    if (mesh !== hoveredRoomMesh) setHoveredRoom(mesh);
    showRoomTooltip(mesh.userData.roomRecord, pointerClientXY.x, pointerClientXY.y);
  }

  // Click sobre habitación (encargo): selecciona la vivienda en el panel
  // izquierdo y baja al panel de problemas — ese panel vive en el script
  // clásico (otro scope), así que se avisa con un evento de `document`
  // y se cierra el visor 3D para que el efecto sea visible.
  function onPointerClickBuilding() {
    if (!hoveredRoomMesh) return;
    var record = hoveredRoomMesh.userData.roomRecord;
    if (!record || !record.viviendaId) return;
    document.dispatchEvent(new CustomEvent("archmuse-3d-select-room", { detail: { viviendaId: record.viviendaId } }));
    close();
  }

  // --- Vistas de cámara (CAMBIO 1) --------------------------------------------
  // Posición/target de cámara para cada botón de vista, a partir del centro
  // y tamaño reales del edificio (`lastInfo`). "Perspectiva" es la misma
  // fórmula que la posición inicial del visor, factorizada aquí para no
  // duplicarla.
  function getCameraPose(view, info) {
    var c = info.center, s = info.buildingSize;
    if (view === "top") {
      // Un pelín desplazada del eje vertical puro: mirar exactamente hacia
      // abajo por el eje Y degenera la matriz "up" de OrbitControls.
      return { pos: new THREE.Vector3(c.x + s * 0.001, c.y + s * 1.8, c.z), target: c.clone() };
    }
    if (view === "front") {
      return { pos: new THREE.Vector3(c.x, c.y, c.z + s * 2.2), target: c.clone() };
    }
    if (view === "side") {
      return { pos: new THREE.Vector3(c.x + s * 2.2, c.y, c.z), target: c.clone() };
    }
    // "perspective" (por defecto): 35° de elevación, 225° de azimut (SO,
    // misma convención de "azimut horario desde el norte = -Z" que usa el
    // visor de vivienda — `sunDirectionFor`/cámara inicial en el segundo
    // módulo de este archivo, `bearingRad = 225 - norte`). El azimut de 45°
    // que había aquí antes correspondía en realidad a la esquina SE, no SO.
    return { pos: orbitPosition(c, 225, 35, s * 2.5), target: c.clone() };
  }

  function open(project) {
    teardown();
    overlayEl.classList.add("open");
    titleEl.textContent = "Edificio completo";
    loadingEl.hidden = false;
    loadingEl.textContent = "Construyendo el edificio…";

    var info;
    try {
      info = buildScene(project);
    } catch (err) {
      loadingEl.textContent = "No se pudo construir el modelo 3D.";
      return;
    }
    if (!info) {
      loadingEl.textContent = "Este proyecto no tiene geometría para mostrar en 3D.";
      return;
    }
    loadingEl.hidden = true;
    lastInfo = info;
    titleEl.textContent = "Edificio completo";

    // Header informativo (CAMBIO 1): plantas/viviendas/habitaciones del
    // proyecto en memoria — no hace falta recorrer la geometría 3D, esos
    // datos ya vienen en `project`.
    //
    // Núcleo de comunicación vertical / Local comercial: excluidos del recuento -- ver
    // `esViviendaResidencial` (junto a `groupFloors`).
    var viviendasCount = (project.viviendas || []).filter(esViviendaResidencial).length;
    var habCount = typeof project.total_habitaciones === "number"
      ? project.total_habitaciones
      : (project.viviendas || []).reduce(function (sum, v) { return sum + (v.habitaciones ? v.habitaciones.length : 0); }, 0);
    metaEl.textContent =
      info.floorsCount + (info.floorsCount === 1 ? " planta · " : " plantas · ") +
      viviendasCount + (viviendasCount === 1 ? " vivienda · " : " viviendas · ") +
      habCount + " hab.";

    // Contexto urbano real (2026-08-16, a petición explícita): solo si este proyecto tiene un sitio
    // real enlazado (mismo campo que ya usa `app.js` para decidir si mostrar la pestaña "Mapa" del
    // visor georreferenciado, `data.proyecto_id`) -- nunca bloquea la apertura del visor, llega de
    // refresco unos segundos después (ver `cargarEntornoUrbano`).
    if (project.proyecto_id) {
      cargarEntornoUrbano(project.proyecto_id, info.center, info.buildingSize, project.norte_grados || 0);
    }

    // Sólido Capaz persistente: aditivo, nunca bloquea la apertura del visor -- si el proyecto no trae
    // `solido_capaz` (el caso mayoritario hoy), `construirEnvolventeSolidoCapaz` devuelve `null` y nada
    // cambia respecto al visor de antes de este PRD.
    var envolvente = construirEnvolventeSolidoCapaz(project.solido_capaz, info.center);
    if (envolvente) {
      scene.add(envolvente);
      solidoCapazEnvolvente = envolvente;
    }

    var width = mount.clientWidth || 800;
    var height = mount.clientHeight || 600;
    // Suelo de 1000 (encargo) combinado con el margen dinámico existente:
    // un edificio grande necesita más far-plane que 1000 para no recortar
    // la cúpula de cielo (radio `buildingSize * 15`, ver `buildSky`).
    var far = Math.max(1000, info.buildingSize * 20 + 100);

    // Vista isométrica de esquina: 35° de elevación, 225° de azimut (SO),
    // orbitando alrededor del centroide REAL del edificio (no del origen
    // del mundo) — misma fórmula que el botón "Perspectiva" (CAMBIO 1).
    var initialPose = getCameraPose("perspective", info);

    // Límites adaptativos (navegación fluida, 2026-08-16): antes eran fijos (10-300m) sin relación
    // con el tamaño real del edificio/parcela — un edificio grande no dejaba alejar lo suficiente para
    // verlo entero (con el terreno orgánico nuevo, tampoco para ver su entorno), y uno pequeño podía
    // acercar la cámara hasta atravesar la fachada. Se derivan de `info.buildingSize` con el mismo
    // criterio que ya usa `far` unas líneas más arriba, con un suelo/techo razonable para no degenerar
    // en un edificio patológicamente pequeño/grande.
    var minDist = THREE.MathUtils.clamp(info.buildingSize * 0.3, 6, 60);
    var maxDist = Math.max(300, info.buildingSize * 6);

    session = createViewerSession({
      mount: mount,
      // Fase 2: mismos valores exactos que antes (`presentationRendererSettings`,
      // `viewer-materials.js`), ahora compartidos con el visor de vivienda.
      renderer: presentationRendererSettings({ alpha: true, clearColor: 0xE8F4F8, toneMappingExposure: 1.1 }),
      camera: { fov: 45, near: 0.1, far: far, position: initialPose.pos },
      controls: {
        target: info.center,
        enableDamping: true,
        dampingFactor: 0.05,
        minDistance: minDist,
        maxDistance: maxDist,
        minPolarAngle: THREE.MathUtils.degToRad(5),
        maxPolarAngle: THREE.MathUtils.degToRad(85),
        enablePan: true,
        screenSpacePanning: true,
        zoomSpeed: 0.8
      }
    });
    renderer = session.renderer;
    camera = session.camera;
    controls = session.controls;
    perspCamera = camera;

    session.addDomListener("pointermove", onPointerMoveBuilding);
    session.addDomListener("pointerleave", onPointerLeaveBuilding);
    session.addDomListener("click", onPointerClickBuilding);
    session.addDomListener("dblclick", onDblClickRecenter);

    // Environment map procedural (CAMBIO 2): un interior genérico simple
    // (cielo + suelo, `RoomEnvironment`) precompilado a un cubemap PMREM —
    // es lo que hace que el vidrio (`envMapIntensity`) tenga un reflejo
    // creíble en vez de leer como un color plano semitransparente.
    // `buildPBREnvironment` (Fase 2, `viewer-materials.js`): misma
    // construcción exacta, ahora compartida con el visor de vivienda.
    envTexture = buildPBREnvironment(renderer);
    scene.environment = envTexture;

    // Postprocesado (CAMBIO 1): SSAO para sombras de contacto en esquinas y
    // juntas (jambas/antepechos/dinteles, canto de forjado) y un bloom muy
    // sutil que solo despunta en el vidrio, el punto más brillante de la
    // escena. `OutputPass` va el último: aplica el tone mapping/espacio de
    // color configurados en el renderer al resultado ya compuesto — sin él,
    // el postprocesado se vería en espacio lineal, lavado.
    composer = new EffectComposer(renderer);
    var renderPass = new RenderPass(scene, camera);
    composer.addPass(renderPass);
    renderPassRef = renderPass;

    var ssaoPass = new SSAOPass(scene, camera, width, height);
    ssaoPass.kernelRadius = 0.4;
    ssaoPass.minDistance = 0.001;
    ssaoPass.maxDistance = 0.05;
    composer.addPass(ssaoPass);
    ssaoPassRef = ssaoPass;

    var bloomPass = new UnrealBloomPass(new THREE.Vector2(width, height), 0.15, 0.4, 0.85);
    composer.addPass(bloomPass);

    composer.addPass(new OutputPass());

    // Escala gráfica (Planta/Alzado/Lateral): se recalcula en cada cambio
    // de zoom/pan de OrbitControls, no solo al pulsar el botón de vista.
    controls.addEventListener("change", updateScaleBar);

    // La sesión ya ajusta el renderer y el `aspect` de la cámara en
    // perspectiva; aquí solo va lo propio de este visor.
    session.onResize(function (w, h) {
      if (!camera.isPerspectiveCamera && currentOrthoView) {
        // `resetZoom=false`: conserva el zoom manual del usuario, solo
        // adapta el frustum al nuevo aspect ratio del contenedor.
        fitOrthoFrustum(currentOrthoView, lastInfo, false);
      }
      if (composer) composer.setSize(w, h);
      updateScaleBar();
    });

    buildFloorPanel(info.floorsCount, computeFloorStats(project));
    buildCompass(controls);
    buildScaleBar();
    buildWalkOverlays();
    buildNavHud();

    // Los botones de vista son HTML estático (fuera de este `open()`, ver
    // el wiring al final del módulo) — al reabrir el visor, "Perspectiva"
    // vuelve a ser la vista activa.
    Array.prototype.forEach.call(document.querySelectorAll(".cam-btn"), function (b) {
      b.classList.toggle("active", b.dataset.view === "perspective");
    });

    // Secuencia de entrada (CAMBIO 3): fondo negro que se desvanece
    // revelando cielo/suelo ya renderizados (0.3s) → el edificio emerge
    // desde bajo tierra (0.8s, easeOutCubic) → los árboles aparecen con
    // delay escalonado (+0.05s cada uno) → el panel de plantas y la
    // brújula hacen fade in al final (0.2s de margen). Todo enganchado al
    // mismo rAF del render loop, sin librerías externas.
    var introFade = document.createElement("div");
    introFade.className = "viewer-intro-fade";
    mount.appendChild(introFade);
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { introFade.style.opacity = "0"; });
    });
    setTimeout(function () {
      if (introFade.parentNode) introFade.parentNode.removeChild(introFade);
    }, 400);

    var introStart = performance.now();
    var buildingGroup = info.buildingGroup;
    var buildingRiseStart = introStart + 300;
    var buildingRiseDuration = 800;
    scheduleTween(buildingRiseStart, buildingRiseDuration, function (t) {
      buildingGroup.position.y = THREE.MathUtils.lerp(-info.buildingSize, 0, easeOutCubic(t));
    });

    info.treeGroups.forEach(function (tree, i) {
      tree.scale.setScalar(0.001);
      scheduleTween(buildingRiseStart + i * 50, 350, function (t) {
        tree.scale.setScalar(Math.max(0.001, easeOutCubic(t)));
      });
    });

    var overlaysFadeAt = buildingRiseStart + buildingRiseDuration + 200;
    setTimeout(function () {
      var panelEl = document.getElementById("floor-panel");
      var compassEl = document.getElementById("viewer-compass");
      if (panelEl) panelEl.classList.add("intro-in");
      if (compassEl) compassEl.classList.add("intro-in");
    }, overlaysFadeAt - introStart);

    session.start(function (now, dt) {
      stepIntroTweens(now);
      if (walkActive) {
        updateWalkMode(buildingGroup, dt);
      } else {
        if (camTween) stepCamTween(now);
        controls.update();
        updateHover();
      }
      composer.render();
    });
  }

  function close() {
    teardown();
    overlayEl.classList.remove("open");
  }

  // Captura de la vista 3D actual (docs/prd/2026-08-17-dossier-inversion-pdf.md, aprobado
  // 2026-08-17 -- opción A de §14: el CLIENTE captura su propio canvas, ArchMuse nunca renderiza 3D
  // en el servidor). `composer.render()` fuerza un frame fresco justo antes de leer el canvas -- sin
  // esto, `toDataURL()` puede devolver el buffer de un instante anterior o en blanco, según cuándo
  // caiga la llamada respecto al bucle de `requestAnimationFrame` de `session.start` de arriba.
  // `null` (nunca una excepción) si el visor no está abierto o si el canvas está "tainted" (motivo
  // real de `toDataURL`, p. ej. una textura cross-origin sin CORS) -- el PDF se compone sin esta
  // imagen en ese caso, no se bloquea la generación del dossier por esto.
  function capturarImagen() {
    if (!renderer || !composer) return null;
    try {
      composer.render();
      return renderer.domElement.toDataURL("image/png");
    } catch (e) {
      return null;
    }
  }

  closeBtn.addEventListener("click", close);
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape" || !overlayEl.classList.contains("open")) return;
    // En modo paseo, ESC lo consume el Pointer Lock (dispara `pointerlockchange`
    // → `exitWalkMode`) y solo debe salir del paseo, no cerrar el visor entero.
    if (walkActive) return;
    close();
  });

  // Botones de vista de cámara (CAMBIO 1): HTML estático, listeners
  // enganchados una sola vez aquí — `getCameraPose`/`animateCameraTo` leen
  // el estado vivo (`lastInfo`, `camera`, `controls`) en cada clic, así que
  // no hace falta reconectar nada cuando el visor se cierra y se reabre.
  Array.prototype.forEach.call(document.querySelectorAll(".cam-btn"), function (btn) {
    btn.addEventListener("click", function () {
      if (!lastInfo || walkActive) return;
      var view = btn.dataset.view;
      // Planta/Alzado/Lateral: sin perspectiva (OrthographicCamera).
      // Perspectiva: PerspectiveCamera original.
      var wantOrtho = view !== "perspective";
      if (wantOrtho !== (camera === orthoCamera)) switchCameraType(wantOrtho);
      if (wantOrtho) fitOrthoFrustum(view, lastInfo);
      var pose = getCameraPose(view, lastInfo);
      animateCameraTo(pose.pos, pose.target, 1200);
      Array.prototype.forEach.call(document.querySelectorAll(".cam-btn"), function (b) {
        b.classList.toggle("active", b === btn);
      });
    });
  });

  if (walkBtn) {
    walkBtn.addEventListener("click", function () {
      if (walkActive) exitWalkMode(); else enterWalkMode();
    });
  }

  // Toggles "Entorno urbano"/"Sombras" (2026-08-16): botones fijos del HTML, `hidden` hasta que
  // `cargarEntornoUrbano` confirme que de verdad hay algo real que mostrar (ver `open()`/`teardown()`)
  // -- se cablean una sola vez aquí, igual que `walkBtn`, no en cada apertura del visor.
  if (btnEntorno) {
    btnEntorno.addEventListener("click", function () {
      aplicarVisibilidadEntorno(!(entornoGroup && entornoGroup.visible));
    });
  }
  if (btnSombras) {
    btnSombras.addEventListener("click", function () {
      aplicarSombrasActivas(!sombrasActivas);
    });
  }

  window.ArchmuseViewer3D = { open: open, close: close, capturarImagen: capturarImagen };
})();
