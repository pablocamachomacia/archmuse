// Sistema de materiales/iluminación PBR compartido entre los dos visores 3D
// (`viewer-edificio.js` y `viewer-vivienda.js`). Creado el 2026-08-12 —
// Fase 2 ("3D Premium"): salto visual del visor de vivienda reutilizando
// exactamente la calidad de entorno/iluminación que ya tenía el visor de
// edificio, en vez de reinventarla por duplicado.
//
// Qué es y qué NO es (mismo criterio que `viewer-core.js`): esto fabrica
// `THREE.Material`/luces ya configurados con buenos valores por defecto para
// una estética de visualización arquitectónica — mate, PBR, coherente bajo
// tone mapping ACES — pero NO decide la geometría ni qué material lleva cada
// malla. Eso lo sigue decidiendo cada visor.
//
// Seis categorías reconocibles (encargo Fase 2): muros/interior, suelo,
// techo, vidrio, circulación y elementos destacados por diagnóstico. Todas
// menos la de diagnóstico son `MeshStandardMaterial` — reaccionan de verdad a
// `scene.environment` (`buildPBREnvironment`) y a las luces de
// `createSunLight`/`createFillLights`. La de diagnóstico es deliberadamente
// NO PBR: ver `createDiagnosticMaterial`.
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

function withDefaults(opts, defaults) {
  var out = {};
  Object.keys(defaults).forEach(function (key) {
    out[key] = opts && opts[key] != null ? opts[key] : defaults[key];
  });
  return out;
}

// Muros / particiones interiores. `roughness` alto (mate) a propósito: una
// pared pintada no debe leer como plástico.
export function createWallMaterial(opts) {
  var v = withDefaults(opts, {
    color: 0xF5F4F2, roughness: 0.85, metalness: 0.0, envMapIntensity: 0.3,
    transparent: false, opacity: 1
  });
  return new THREE.MeshStandardMaterial(v);
}

// Suelo. Algo más rugoso que el muro y con menos realce del entorno: el
// suelo normalmente está más lejos de la luz reflejada del entorno genérico
// que las paredes verticales.
export function createFloorMaterial(opts) {
  var v = withDefaults(opts, {
    color: 0xC8C4BC, roughness: 0.92, metalness: 0.0, envMapIntensity: 0.12,
    transparent: false, opacity: 1
  });
  return new THREE.MeshStandardMaterial(v);
}

// Techo / cubierta. La cara que más luz ambiental de cielo recibe (mira
// hacia arriba): algo menos rugosa que el suelo para que se note.
export function createCeilingMaterial(opts) {
  var v = withDefaults(opts, {
    color: 0xE8E7E5, roughness: 0.95, metalness: 0.0, envMapIntensity: 0.1,
    transparent: false, opacity: 1
  });
  return new THREE.MeshStandardMaterial(v);
}

// Vidrio. MeshStandardMaterial semitransparente con tinte fijo (no
// MeshPhysicalMaterial con transmisión real) — mismo criterio ya usado en el
// visor de edificio: material/tinte fijo, no refracción física.
export function createGlassMaterial(opts) {
  var v = withDefaults(opts, {
    color: 0x7BA7BC, roughness: 0.1, metalness: 0.1, opacity: 0.7, envMapIntensity: 0.8
  });
  return new THREE.MeshStandardMaterial({
    color: v.color, roughness: v.roughness, metalness: v.metalness,
    transparent: true, opacity: v.opacity, side: THREE.DoubleSide, depthWrite: false,
    envMapIntensity: v.envMapIntensity
  });
}

// --- Materiales ArchViz del Visor Sandbox (2026-08-16, docs/prd/2026-08-16-visor-sandbox-terreno-
// real-y-materiales-archviz.md) -------------------------------------------------------------------
//
// Deliberadamente aparte de `createGlassMaterial`/`createWallMaterial` de más arriba, no en su
// lugar: esos siguen siendo, sin tocar, los materiales de `viewer-edificio.js`/`viewer-vivienda.js`
// -- el PRD que aprobó esto acota el cambio al Sandbox. `transmission` (vidrio físico real) es más
// caro de renderizar que la transparencia simple de `createGlassMaterial` (pase adicional a un
// buffer de fondo); no se generaliza a los otros visores sin medir antes ese coste ahí.

// Vidrio con refracción física real. `roughness`/`metalness` bajos (encargo explícito) para que siga
// leyéndose como vidrio pulido, no como plástico esmerilado.
//
// `clearcoat`/`clearcoatRoughness` añadidos (2026-08-16, verificado en navegador real: la
// `transmission` por sí sola se leía como un panel azulado plano, no como vidrio, cuando detrás no
// hay mucho contraste que refractar -- p.ej. una ortofoto de fondo oscura/uniforme). El barniz
// especular del `clearcoat` da un reflejo brillante propio que se nota SIEMPRE, independientemente
// de lo que haya detrás, así que el material se lee como vidrio incluso en escenas de poco
// contraste -- la `transmission` real se mantiene para cuando sí hay algo vistoso que refractar.
export function createPhysicalGlassMaterial(opts) {
  var v = withDefaults(opts, {
    color: 0x9DC3D6, roughness: 0.1, metalness: 0.1, transmission: 0.9,
    thickness: 0.3, ior: 1.5, envMapIntensity: 1.0, clearcoat: 1.0, clearcoatRoughness: 0.08
  });
  var mat = new THREE.MeshPhysicalMaterial({
    color: v.color, roughness: v.roughness, metalness: v.metalness,
    transmission: v.transmission, thickness: v.thickness, ior: v.ior,
    envMapIntensity: v.envMapIntensity, clearcoat: v.clearcoat, clearcoatRoughness: v.clearcoatRoughness,
    side: THREE.DoubleSide
  });
  mat.polygonOffset = true;
  mat.polygonOffsetFactor = 1;
  mat.polygonOffsetUnits = 1;
  return mat;
}

// Hormigón/blanco arquitectónico para volúmenes sólidos, en vez del gris translúcido plano que
// tenía el Sandbox. `MeshStandardMaterial` (no `MeshPhysicalMaterial`): un paramento de hormigón no
// necesita capa clearcoat ni transmisión, y así se mantiene el mismo tipo de material que
// `createWallMaterial`/`createFloorMaterial` de más arriba -- más barato de renderizar sin perder
// realismo perceptible en esta pieza.
//
// `polygonOffset` (2026-08-16, verificado en navegador real): sin esto, los bordes sutiles
// (`EdgesGeometry`+`LineSegments`, ver `viewer-sandbox.js`) compiten en profundidad exactamente con
// la cara del volumen que los contiene -- coplanares de verdad, no solo visualmente -- y el
// z-fighting resultante los hace parpadear o desaparecer según el ángulo de cámara. Empujar la cara
// sólida ligeramente "hacia atrás" en el buffer de profundidad deja la línea siempre por delante.
// Se aplica igual en `createPhysicalGlassMaterial` de arriba, porque las 6 caras del volumen llevan
// bordes por igual, no solo las de hormigón.
export function createConcreteMaterial(opts) {
  var v = withDefaults(opts, { color: 0xEDEAE3, roughness: 0.9, metalness: 0.02, envMapIntensity: 0.35 });
  var mat = new THREE.MeshStandardMaterial(v);
  mat.polygonOffset = true;
  mat.polygonOffsetFactor = 1;
  mat.polygonOffsetUnits = 1;
  return mat;
}

// Elementos de circulación (pasillos, zonas de paso). Mismo tipo de material
// que un muro pero deliberadamente más apagado (`envMapIntensity` bajo, más
// rugoso): un pasillo no debe competir visualmente con las estancias.
export function createCirculationMaterial(opts) {
  var v = withDefaults(opts, {
    color: 0xE0DED8, roughness: 0.97, metalness: 0.0, envMapIntensity: 0.05,
    transparent: false, opacity: 1
  });
  return new THREE.MeshStandardMaterial(v);
}

// Elementos destacados por diagnóstico (avisos de problema). A propósito
// NO usa MeshStandardMaterial: un aviso de "aquí hay un problema" tiene que
// leerse igual de rojo esté la escena en sombra o al sol — si reaccionara a
// la luz (como el resto de materiales PBR de este módulo) podría apagarse
// justo en la habitación en sombra, que es lo último que le conviene a un
// indicador de alerta. `MeshBasicMaterial` (no iluminado) es aquí la opción
// correcta, no una que falte por "mejorar" a PBR.
export function createDiagnosticMaterial(opts) {
  var v = withDefaults(opts, { color: 0xdc2626, opacity: 0.32 });
  return new THREE.MeshBasicMaterial({
    color: v.color, transparent: true, opacity: v.opacity, side: THREE.DoubleSide, depthWrite: false
  });
}

// Reparte en dos el grupo de "tapas" (suelo+techo combinados) que genera
// `ExtrudeGeometry` con bevel desactivado —el caso de `extrudeFootprint`,
// ver `viewer-geometry.js`—: three.js siempre triangula primero la tapa de
// abajo y después la de arriba, las dos con el mismo número de triángulos
// (misma triangulación para ambas), así que el grupo se puede partir en dos
// mitades iguales sin inspeccionar posiciones de vértices. Sin esto, suelo y
// techo de un mismo volumen comparten un único `materialIndex` y no se
// pueden pintar con materiales distintos.
//
// Deja la geometría con 3 grupos — 0: suelo, 1: techo, 2: paredes (laterales
// de la extrusión) — pensados para usarse con
// `mesh.material = [floorMat, ceilingMat, wallMat]`.
export function splitExtrudeCapGroups(geometry) {
  var groups = geometry.groups;
  if (!groups || groups.length < 2) return geometry;
  var caps = groups[0];
  var sides = groups[1];
  var half = caps.count / 2;
  geometry.groups = [
    { start: caps.start, count: half, materialIndex: 0 },
    { start: caps.start + half, count: half, materialIndex: 1 },
    { start: sides.start, count: sides.count, materialIndex: 2 }
  ];
  return geometry;
}

// Environment PBR genérico (interior simple: cielo + suelo, `RoomEnvironment`)
// precompilado a un cubemap PMREM — sin él, `envMapIntensity` no tiene nada
// que reflejar y todo material PBR con realce de entorno queda como un color
// plano sin más. `renderer` hace falta para compilar el shader del PMREM; el
// `THREE.Texture` devuelto se asigna a `scene.environment` y cada visor debe
// liberarlo (`texture.dispose()`) en su propio teardown.
export function buildPBREnvironment(renderer) {
  var pmremGenerator = new THREE.PMREMGenerator(renderer);
  pmremGenerator.compileEquirectangularShader();
  var texture = pmremGenerator.fromScene(new RoomEnvironment(), 0.04).texture;
  pmremGenerator.dispose();
  return texture;
}

// Ajustes de renderer para una presentación "de visualización arquitectónica"
// (tone mapping ACES + espacio de color sRGB) — los mismos que ya usaba el
// visor de edificio, pensados para pasar tal cual a
// `createViewerSession({renderer: ...})`.
// `clearAlpha` (2026-08-17, opt-in -- default 1, mismo comportamiento opaco de siempre para quien no
// lo pase): con `alpha: true` el canvas YA es técnicamente capaz de transparencia, pero
// `renderer.setClearColor()` por sí solo deja el alpha de borrado en 1 (opaco) -- el degradado de cielo
// que pinta el propio CSS del contenedor (`#viewer-sandbox`/`#viewer-3d`, ver `style.css`) queda
// entonces TAPADO por un relleno plano del color de `clearColor`, nunca visible. Bug real confirmado en
// vivo en el Sandbox: el "cielo" que se veía era un azul/gris LISO (`clearColor` opaco), no el degradado
// que el propio CSS ya llevaba escrito. `viewer-sandbox.js` es el primer visor que pasa `clearAlpha: 0`
// a propósito; los demás (`viewer-edificio.js`/`viewer-vivienda.js`) no lo pasan y se quedan exactamente
// como estaban.
export function presentationRendererSettings(opts) {
  var v = withDefaults(opts, { alpha: true, clearColor: 0xE8F4F8, clearAlpha: 1, toneMappingExposure: 1.1 });
  return {
    alpha: v.alpha,
    clearColor: v.clearColor,
    clearAlpha: v.clearAlpha,
    toneMapping: THREE.ACESFilmicToneMapping,
    toneMappingExposure: v.toneMappingExposure,
    outputColorSpace: THREE.SRGBColorSpace
  };
}

// DirectionalLight "sol" con sombra ya configurada y con `.target` creado
// (un `Object3D` propio, sin añadir a ninguna escena todavía). Ni la
// posición del sol ni la del target se fijan aquí: eso depende del centro y
// tamaño de CADA escena, y en el visor de vivienda cambia en cada movimiento
// del slider de hora — ver `configureSunShadow` para el frustum de sombra.
export function createSunLight(opts) {
  var v = withDefaults(opts, { color: 0xFFF8F0, intensity: 1.3 });
  var light = new THREE.DirectionalLight(v.color, v.intensity);
  light.castShadow = true;
  light.target = new THREE.Object3D();
  configureSunShadow(light, (opts && opts.shadowHalfSize) || 10, opts);
  return light;
}

// Frustum/calidad de la cámara de sombra del sol, en función del tamaño real
// de la escena (`halfSize`, metros — la mitad del lado del área a cubrir):
// una vivienda de pocos metros y un edificio de decenas de metros no deben
// compartir la misma distancia de recorte absoluta, o la sombra pierde
// resolución efectiva (se malgasta mapa de sombra en área vacía) en la
// escena pequeña, o se recorta en la grande.
export function configureSunShadow(light, halfSize, opts) {
  var v = withDefaults(opts, {
    shadowMapSize: 2048, shadowNear: 0.5, shadowFar: halfSize * 6 + 20,
    shadowBias: -0.0005, shadowNormalBias: 0.02, shadowRadius: 4
  });
  light.shadow.mapSize.width = v.shadowMapSize;
  light.shadow.mapSize.height = v.shadowMapSize;
  light.shadow.camera.near = v.shadowNear;
  light.shadow.camera.far = v.shadowFar;
  light.shadow.camera.left = -halfSize;
  light.shadow.camera.right = halfSize;
  light.shadow.camera.top = halfSize;
  light.shadow.camera.bottom = -halfSize;
  light.shadow.bias = v.shadowBias;
  light.shadow.normalBias = v.shadowNormalBias;
  // Nota (ya válida en el visor de edificio): con `PCFSoftShadowMap` activo
  // (fijo en `viewer-core.js`) three.js aplica su propio blur y
  // `shadow.radius` es un no-op — se deja tal cual por si se cambiara el tipo
  // de mapa de sombra en el futuro.
  light.shadow.radius = v.shadowRadius;
  light.shadow.camera.updateProjectionMatrix();
}

// Luz ambiental + hemisferio "de relleno": un ambiente frío y tenue más un
// hemisferio cielo/suelo, para que las caras que no toca el sol no se vayan
// a negro puro. No se añaden a ninguna escena aquí.
export function createFillLights(opts) {
  var v = withDefaults(opts, {
    ambientColor: 0x1A2030, ambientIntensity: 0.2,
    skyColor: 0xB1D5F5, groundColor: 0xD4C5A9, hemisphereIntensity: 0.5
  });
  return {
    ambient: new THREE.AmbientLight(v.ambientColor, v.ambientIntensity),
    hemisphere: new THREE.HemisphereLight(v.skyColor, v.groundColor, v.hemisphereIntensity)
  };
}
