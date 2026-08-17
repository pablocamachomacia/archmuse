// Matemática pura compartida por los dos visores 3D (`viewer-edificio.js` y
// `viewer-vivienda.js`). Creado el 2026-08-12 al unificar el motor 3D (Fase 1):
// aquí solo vive código que ANTES estaba literalmente duplicado en ambos
// ficheros, nunca utilidades "por si acaso" — si una función solo la usa un
// visor, se queda en su módulo.
//
// Convención de coordenadas de los dos visores (no cambiarla sin tocar ambos):
//   - El mundo 3D usa el sistema local del plano: X del plano = X del mundo,
//     Y del plano = Z del mundo, Y del mundo = altura.
//   - Los azimuts son horarios desde el norte (0 = Norte, 90 = Este, 180 = Sur,
//     270 = Oeste), igual que el campo `norte_grados` del backend.
//   - Ese sistema local solo coincide con el norte REAL cuando `norte_grados`
//     es 0, así que quien necesite un azimut real resta `norte` ANTES de
//     llamar aquí. Se deja fuera de estas funciones a propósito: los dos
//     visores no lo aplican igual (el sol sí lo resta en ambos; la cámara
//     inicial lo resta en vivienda pero no en edificio), y esconderlo dentro
//     de un parámetro opcional haría fácil cambiar ese comportamiento sin
//     darse cuenta.
import * as THREE from "three";

// `THREE.Shape` a partir de puntos `{x, z}` en metros del mundo. Shape trabaja
// en un plano XY local que después se tumba con `rotateX(-90°)`: hay que
// pasarle la Z del mundo NEGADA para que, tras la rotación, la forma no quede
// reflejada respecto al resto de la geometría (que sí usa la Z del mundo tal
// cual). Esta inversión es la razón de que exista esta función y no se llame
// a `new THREE.Shape(...)` directamente en cada sitio.
export function shapeFromXZ(points) {
  return new THREE.Shape(points.map(function (p) { return new THREE.Vector2(p.x, -p.z); }));
}

// Extrusión vertical de una huella `{x, z}` con `height` metros de alto, ya
// tumbada al plano XZ del mundo. Es el patrón "Shape → ExtrudeGeometry →
// rotateX" que los dos visores repetían: losas y mallas de impacto por
// habitación en `viewer-edificio.js`, volumen por habitación en
// `viewer-vivienda.js`. La geometría queda con su base en Y=0, así que el
// llamador la coloca con `mesh.position.y`.
export function extrudeFootprint(points, height) {
  var geometry = new THREE.ExtrudeGeometry(shapeFromXZ(points), { depth: height, bevelEnabled: false });
  geometry.rotateX(-Math.PI / 2);
  return geometry;
}

// Vector unitario para un azimut/elevación en grados, en el sistema XZ de los
// visores. Lo usan tanto la dirección del sol (`buildStudioLighting` en
// edificio, `sunDirectionFor` en vivienda) como la pose de cámara — era la
// misma fórmula escrita cuatro veces.
export function directionFromAzimuthElevation(azimuthDeg, elevationDeg) {
  var bearingRad = THREE.MathUtils.degToRad(azimuthDeg);
  var elevationRad = THREE.MathUtils.degToRad(elevationDeg);
  var horiz = Math.cos(elevationRad);
  return new THREE.Vector3(
    horiz * Math.sin(bearingRad),
    Math.sin(elevationRad),
    horiz * Math.cos(bearingRad)
  );
}

// Posición de cámara orbitando `center` a `distance` metros, con el azimut y
// la elevación dados. `center` puede ser el origen (visor de vivienda, que
// centra su geometría en 0,0,0) o el centroide real del edificio.
export function orbitPosition(center, azimuthDeg, elevationDeg, distance) {
  return directionFromAzimuthElevation(azimuthDeg, elevationDeg)
    .multiplyScalar(distance)
    .add(center);
}
