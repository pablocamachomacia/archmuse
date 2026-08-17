// Extraido de index.html el 2026-08-02 al dividir el archivo unico de
// 5.779 lineas. Contenido intacto: solo cambio de ubicacion.

// Visor 3D simple de la VIVIENDA seleccionada: extruye cada habitación a
// partir de su `poligono` real en metros (mismo campo que ya devuelve
// `api_serializer._serialize_room` para el visor de edificio completo),
// sin generar muros/ventanas/tejado — un volumen sólido por habitación tal
// cual se detectó en el plano. Deliberadamente mucho más simple que el otro
// visor (`window.ArchmuseViewer3D`, más arriba): ese reconstruye un
// EDIFICIO GENERADO completo con arquitectura sintética y solo tiene
// sentido para proyectos de IA (`data.edificio`); este funciona para
// CUALQUIER vivienda con habitaciones (DXF analizado o generado) — ver
// `wireVer3d` en el script clásico, que decide cuál de los dos abrir.
// Desde 2026-08-12 (unificación del motor 3D, Fase 1) la maquinaria de render
// —renderer, cámara, controles, bucle, redimensionado y desmontaje— vive en
// `viewer-core.js`, compartida con el visor de edificio; aquí solo queda lo
// propio de este visor: la extrusión de habitaciones, el sol por hora del día
// y los avisos de problemas.
//
// Desde 2026-08-12 (Fase 2, "3D Premium") los materiales/entorno/iluminación
// vienen de `viewer-materials.js`, la misma calidad PBR que ya tenía el
// visor de edificio (antes este visor usaba `MeshLambertMaterial` plano, sin
// entorno ni tone mapping). El slider de hora sigue moviendo el sol real
// (`updateSun`) — Fase 2 no toca esa mecánica, solo cómo se ve la luz.
import * as THREE from "three";
import { createViewerSession, disposeSceneResources, positionTooltip } from "./viewer-core.js";
import { shapeFromXZ, extrudeFootprint, directionFromAzimuthElevation, orbitPosition } from "./viewer-geometry.js";
import {
  createWallMaterial, createFloorMaterial, createCeilingMaterial, createCirculationMaterial,
  createDiagnosticMaterial, splitExtrudeCapGroups, buildPBREnvironment, presentationRendererSettings,
  createSunLight, createFillLights
} from "./viewer-materials.js";

var ROOM_HEIGHT_M = 2.5; // altura normativa de vivienda
var PASILLO_HEIGHT_M = 2.2;

// Mismos colores que `plan_svg._ROOM_TYPES` (backend) — Requisito 2
// ("mismo código de color por tipo de habitación que en 2D"). Duplicado a
// propósito: son 6 valores y este módulo no comparte scope con el script
// clásico (dos `<script>` independientes) — si la paleta cambia en el
// backend, hay que actualizarla aquí también.
var ROOM_TYPE_COLOR = {
  salon_cocina: 0xd4edda, dormitorio: 0xdce8f5, bano: 0xfdf3e3,
  terraza: 0xfce8d5, tendedero: 0xede8f5, otro: 0xe9eaee
};

var overlayEl = document.getElementById("room-viewer-3d");
var mountEl = document.getElementById("room-viewer-mount");
var loadingEl = document.getElementById("room-viewer-loading");
var titleEl = document.getElementById("room-viewer-title");
var tooltipEl = document.getElementById("room-viewer-tooltip");
var closeBtn = document.getElementById("btn-room-viewer-cerrar");
var problemasBtn = document.getElementById("btn-room-viewer-problemas");
var horaSlider = document.getElementById("room-viewer-hora-slider");
var horaValorEl = document.getElementById("room-viewer-hora-valor");

var session = null, scene = null, raycaster = null;
var sun = null, sunTarget = null;
var envTexture = null; // textura PMREM de `buildPBREnvironment` — se libera en `teardown()`
var roomMeshes = []; // { mesh, room, outline, overlay }
var norteGrados = 0;
var footprintSize = 10;
var mostrandoProblemas = false;

function _sinAcentos(s) {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "");
}
function esPasillo(nombre) {
  return !!nombre && _sinAcentos(nombre).toUpperCase().indexOf("PASILLO") !== -1;
}
function escapeHtmlLocal(str) {
  return String(str).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

// Azimut solar (0=Norte, sentido horario, misma convención que
// `norte_grados`): 6h→90°(Este) ... 13h→180°(Sur) ... 20h→270°(Oeste),
// interpolación lineal. Elevación: arco simple que va de 0° en los
// extremos a un máximo a mediodía — no hay fecha/estación en los datos del
// proyecto, así que se usa un pico fijo razonable para latitud española en
// vez de un cálculo astronómico completo (fuera de alcance aquí).
function sunDirectionFor(hour, norte) {
  var azimuthSun = 90 + (hour - 6) * (180 / 14);
  var elevationDeg = Math.max(55 * Math.sin(Math.PI * (hour - 6) / 14), 2);
  // El mundo 3D usa el sistema de coordenadas propio del plano (mundo +Z =
  // +Y del plano), que solo coincide con el norte real si `norte==0` — se
  // resta `norte` para expresar el azimut real en ese sistema local.
  return directionFromAzimuthElevation(azimuthSun - norte, elevationDeg);
}

function teardown() {
  if (session) { session.dispose(); session = null; }
  if (envTexture) { envTexture.dispose(); envTexture = null; }
  disposeSceneResources(scene);
  roomMeshes = [];
  scene = null;
  tooltipEl.hidden = true;
}

function buildScene(vivienda, criticalRoomLabels) {
  var group = new THREE.Group();
  var rooms = (vivienda.habitaciones || []).filter(function (r) { return r.poligono && r.poligono.length >= 3; });
  if (!rooms.length) return null;

  var minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
  rooms.forEach(function (r) {
    r.poligono.forEach(function (p) {
      if (p[0] < minX) minX = p[0];
      if (p[0] > maxX) maxX = p[0];
      if (p[1] < minZ) minZ = p[1];
      if (p[1] > maxZ) maxZ = p[1];
    });
  });
  var cx = (minX + maxX) / 2, cz = (minZ + maxZ) / 2;
  var size = Math.max(maxX - minX, maxZ - minZ, 1);

  rooms.forEach(function (r) {
    var points = r.poligono.map(function (p) { return { x: p[0] - cx, z: p[1] - cz }; });
    var xs = points.map(function (p) { return p.x; });
    var zs = points.map(function (p) { return p.z; });
    var width = Math.max.apply(null, xs) - Math.min.apply(null, xs);
    var length = Math.max.apply(null, zs) - Math.min.apply(null, zs);
    var height = esPasillo(r.nombre) ? PASILLO_HEIGHT_M : ROOM_HEIGHT_M;

    var geometry = extrudeFootprint(points, height);
    var color = ROOM_TYPE_COLOR[r.tipo] != null ? ROOM_TYPE_COLOR[r.tipo] : ROOM_TYPE_COLOR.otro;
    // Requisito 2 (color por tipo de habitación) se conserva íntegro: las
    // tres caras — suelo/techo/paredes — llevan el MISMO color de tipo, solo
    // cambia su acabado PBR (rugosidad/realce de entorno) entre una y otra.
    // Así cada volumen se sigue leyendo, de un vistazo, como su color de
    // tipo — pero ahora con relieve real bajo la luz en vez de un plano
    // uniforme sin sombreado (Fase 2, "3D Premium": ver `viewer-materials.js`).
    splitExtrudeCapGroups(geometry);
    var floorMat = createFloorMaterial({ color: color, envMapIntensity: 0.05, opacity: 0.93, transparent: true });
    var ceilingMat = createCeilingMaterial({ color: color, envMapIntensity: 0.05, opacity: 0.93, transparent: true });
    var wallMat = esPasillo(r.nombre)
      ? createCirculationMaterial({ color: color, opacity: 0.93, transparent: true })
      : createWallMaterial({ color: color, roughness: 0.75, metalness: 0.0, envMapIntensity: 0.12, opacity: 0.93, transparent: true });
    var mesh = new THREE.Mesh(geometry, [floorMat, ceilingMat, wallMat]);
    mesh.castShadow = true;
    mesh.receiveShadow = true;

    // Requisito 2: borde rojo pulsante en habitaciones con algún problema
    // detectado (igual que `.room-list li.has-problem`/el tinte rojo del
    // plano 2D en `plan_svg.py` — aquí cualquier `problemas.length`, no
    // solo CRITICO/IMPORTANTE, que es el subconjunto más estricto del
    // Requisito 5).
    var outline = null;
    if ((r.problemas || []).length > 0) {
      var outlineMat = new THREE.LineBasicMaterial({ color: 0xdc2626, transparent: true, opacity: 1 });
      outline = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), outlineMat);
      mesh.add(outline);
    }

    // Requisito 5: plano semitransparente rojo sobre habitaciones con algún
    // problema CRITICO/IMPORTANTE, oculto hasta que se activa el toggle.
    var overlay = null;
    if (criticalRoomLabels.indexOf(r.nombre) !== -1) {
      var overlayGeo = new THREE.ShapeGeometry(shapeFromXZ(points));
      overlayGeo.rotateX(-Math.PI / 2);
      var overlayMat = createDiagnosticMaterial({ color: 0xdc2626, opacity: 0.32 });
      overlay = new THREE.Mesh(overlayGeo, overlayMat);
      overlay.position.y = height + 0.02;
      overlay.visible = mostrandoProblemas;
      mesh.add(overlay);
    }

    group.add(mesh);
    roomMeshes.push({ mesh: mesh, room: r, outline: outline, overlay: overlay, width: width, length: length });
  });

  var floor = new THREE.Mesh(
    new THREE.PlaneGeometry(size * 4, size * 4),
    createFloorMaterial({ color: 0xc8c4bc })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.02;
  floor.receiveShadow = true;
  group.add(floor);

  return { group: group, size: size };
}

function updateSun(hour) {
  if (!sun) return;
  var dir = sunDirectionFor(hour, norteGrados);
  sun.position.copy(dir).multiplyScalar(footprintSize * 4 + 10);
  sunTarget.position.set(0, 0, 0);
  if (horaValorEl) {
    var h = Math.floor(hour);
    var m = Math.round((hour - h) * 60);
    horaValorEl.textContent = (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m;
  }
}

function onPointerMove(e) {
  if (!session || !roomMeshes.length) return;
  var ndc = session.pointerToNDC(e.clientX, e.clientY);
  if (!ndc) { tooltipEl.hidden = true; return; }
  raycaster.setFromCamera(ndc, session.camera);
  var hits = raycaster.intersectObjects(roomMeshes.map(function (rm) { return rm.mesh; }), false);
  if (!hits.length) { tooltipEl.hidden = true; return; }
  var rm = roomMeshes.filter(function (x) { return x.mesh === hits[0].object; })[0];
  if (!rm) { tooltipEl.hidden = true; return; }
  // Requisito 6: cota de anchura x longitud de la habitación bajo el cursor.
  tooltipEl.innerHTML = "<strong>" + escapeHtmlLocal(rm.room.nombre) + "</strong><br>" +
    rm.width.toFixed(2) + " × " + rm.length.toFixed(2) + " m";
  tooltipEl.hidden = false;
  positionTooltip(tooltipEl, e.clientX, e.clientY);
}
function onPointerLeave() { tooltipEl.hidden = true; }

function open(vivienda, norte, criticalRoomLabels) {
  teardown();
  overlayEl.classList.add("open");
  loadingEl.hidden = false;
  loadingEl.textContent = "Generando el modelo 3D…";
  titleEl.textContent = vivienda.nombre || "Vivienda";
  norteGrados = norte || 0;
  mostrandoProblemas = false;
  if (problemasBtn) problemasBtn.classList.remove("active");

  var built;
  try {
    built = buildScene(vivienda, criticalRoomLabels || []);
  } catch (err) {
    loadingEl.textContent = "No se pudo construir el modelo 3D de esta vivienda.";
    return;
  }
  if (!built) {
    loadingEl.textContent = "Esta vivienda no tiene geometría de habitaciones para mostrar en 3D.";
    return;
  }
  loadingEl.hidden = true;
  footprintSize = built.size;

  scene = new THREE.Scene();
  scene.add(built.group);

  // Fase 2 ("3D Premium"): mismo esquema de luz de relleno que el visor de
  // edificio (ambiente frío tenue + hemisferio cielo/suelo) en vez de un
  // ambiente/hemisferio blancos sin matiz — con esto y el entorno PBR de
  // abajo, las caras que no toca el sol ya no se quedan lisas y sin
  // gradiente.
  var fill = createFillLights({ ambientIntensity: 0.25, hemisphereIntensity: 0.55 });
  scene.add(fill.ambient);
  scene.add(fill.hemisphere);

  // Requisito 4 (preexistente, intacto): iluminación solar según el azimut
  // norte del proyecto y la hora del slider — `updateSun` (más abajo) sigue
  // siendo quien mueve `sun.position`/`sunTarget.position` en cada cambio de
  // hora; aquí solo cambia CÓMO se construye la luz (calidad de sombra
  // adaptada al tamaño real de la vivienda, no una distancia fija).
  sun = createSunLight({
    color: 0xfff8f0, intensity: 1.35, shadowHalfSize: footprintSize * 1.5 + 2,
    shadowFar: footprintSize * 10 + 20, shadowNear: 0.5, shadowBias: -0.0006, shadowNormalBias: 0.015
  });
  sunTarget = sun.target;
  scene.add(sunTarget);
  scene.add(sun);
  updateSun(parseFloat(horaSlider ? horaSlider.value : 13));

  // Requisito 3: vista inicial isométrica desde suroeste (225°) a 45° de
  // elevación — igual que el sol, referida al sistema local del plano (de ahí
  // el `- norteGrados`). La geometría se centra en el origen, así que la
  // cámara orbita alrededor de (0,0,0).
  var dist = footprintSize * 2.2 + 4;
  var origin = new THREE.Vector3(0, 0, 0);

  session = createViewerSession({
    mount: mountEl,
    // El canvas va por debajo de la capa de "Generando el modelo 3D…".
    insertBefore: loadingEl,
    // Fase 2: mismo tone mapping ACES + espacio de color del visor de
    // edificio — antes este visor no fijaba ninguno (tone mapping plano por
    // defecto), la razón principal por la que se veía "plano" frente al otro.
    renderer: presentationRendererSettings(),
    camera: {
      fov: 45,
      near: 0.05,
      far: footprintSize * 30 + 60,
      position: orbitPosition(origin, 225 - norteGrados, 45, dist)
    },
    controls: {
      target: origin,
      enableDamping: true,
      dampingFactor: 0.08,
      maxPolarAngle: Math.PI * 0.495,
      minDistance: 0.5,
      maxDistance: footprintSize * 8 + 30
    }
  });

  // Entorno PBR (Fase 2): sin esto, `envMapIntensity` de los materiales de
  // `viewer-materials.js` no tiene nada que reflejar. Requiere el renderer ya
  // creado (`session.renderer`), por eso va después de `createViewerSession`.
  envTexture = buildPBREnvironment(session.renderer);
  scene.environment = envTexture;

  raycaster = new THREE.Raycaster();
  session.addDomListener("pointermove", onPointerMove);
  session.addDomListener("pointerleave", onPointerLeave);

  session.start(function (now, dt, elapsed) {
    var pulse = 0.55 + 0.45 * Math.sin(elapsed * 3.0);
    roomMeshes.forEach(function (rm) {
      if (rm.outline) rm.outline.material.opacity = pulse;
    });
    session.controls.update();
    session.renderer.render(scene, session.camera);
  });
}

function close() {
  overlayEl.classList.remove("open");
  teardown();
}

if (closeBtn) closeBtn.addEventListener("click", close);
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape" && overlayEl.classList.contains("open")) close();
});
if (problemasBtn) {
  problemasBtn.addEventListener("click", function () {
    mostrandoProblemas = !mostrandoProblemas;
    problemasBtn.classList.toggle("active", mostrandoProblemas);
    roomMeshes.forEach(function (rm) { if (rm.overlay) rm.overlay.visible = mostrandoProblemas; });
  });
}
if (horaSlider) {
  horaSlider.addEventListener("input", function () { updateSun(parseFloat(horaSlider.value)); });
}

window.ArchmuseRoomViewer3D = { open: open, close: close };
