// Terreno real compartido por los visores 3D (2026-08-17, al extraer este bloque de
// `viewer-edificio.js` para que `viewer-sandbox.js` -- Modo Sandbox/Lienzo Libre -- lo reutilice sin
// duplicar ~150 líneas de matemática de tiles/proyección). Mismo criterio que `viewer-geometry.js`/
// `viewer-materials.js`: código puro compartido, sin DOM propio más allá de un `<canvas>` interno
// para ensamblar el mosaico.
//
// Ortofoto real (Esri World Imagery) + volúmenes extruidos de edificios colindantes reales
// (Overpass, vía `/api/proyectos/<id>/entorno-3d`). Ningún visor que use esto debe DEPENDER de que
// cargue: siempre es un extra sobre un terreno/cielo/luz de respaldo que ya exista antes de llamar
// aquí -- si no hay coordenadas reales, si Overpass falla, o si las tiles no cargan, quien llame se
// queda con lo que ya tenía, nunca a medio construir.
//
// También vive aquí (2026-08-16) el terreno orgánico LOCAL sin datos reales (`construirTerrenoOrganico`/
// `alturaTerrenoOrganico`, al final del archivo) que usa `viewer-sandbox.js` como relieve de relleno.
// Decisión de arquitectura explícita: la integración de elevación real (DEM/MDT -- IGN, Copernicus,
// Mapbox Terrain-RGB) queda RESERVADA EXCLUSIVAMENTE para `viewer-edificio.js`, que ya tiene el
// pipeline de sitio georreferenciado real de este mismo archivo (`pedirEntorno3D`/
// `construirPlanoOrtofoto`/`construirEdificiosColindantes`). El Sandbox no la usa ni la necesita: por
// diseño puede no tener ninguna parcela real vinculada (ver cabecera de `viewer-sandbox.js`), así que
// un DEM real no siempre tendría de qué coordenada pedir datos. Ver
// docs/prd/2026-08-16-visor-sandbox-terreno-real-y-materiales-archviz.md §14.
import * as THREE from "three";
import { extrudeFootprint } from "./viewer-geometry.js";

var EARTH_RADIUS_M = 6371000;
// Radio de imagen fijo (Esri World Imagery). Con 5×5 tiles a zoom 18, el mosaico cubre justo por
// encima de 200m de lado en la latitud media de España -- "al menos 100-200 metros alrededor de la
// parcela" del encargo original (2026-08-16), con margen.
var ORTOFOTO_ZOOM = 18;
var ORTOFOTO_TILES_POR_LADO = 5;
var ORTOFOTO_TILE_PX = 256;

// Metros este/norte REALES (no todavía en ejes del plano) desde (lat0,lon0) hasta (lat,lon) --
// aproximación equirectangular de tangente local, válida al nivel de precisión que hace falta aquí
// (cientos de metros, no kilómetros). Compartida por el mosaico de ortofoto y los edificios
// colindantes para que los dos usen EXACTAMENTE la misma proyección y no puedan desalinearse entre sí
// por una diferencia de fórmula.
export function metrosEsteNorteDesde(lat0, lon0, lat, lon) {
  var lat0Rad = THREE.MathUtils.degToRad(lat0);
  var este = THREE.MathUtils.degToRad(lon - lon0) * Math.cos(lat0Rad) * EARTH_RADIUS_M;
  var norte = THREE.MathUtils.degToRad(lat - lat0) * EARTH_RADIUS_M;
  return { este: este, norte: norte };
}

// Rotación 2D de un vector este/norte REAL a los ejes locales X/Z del plano -- "resta norteGrados
// antes de usar los ejes del plano", misma convención que documenta `viewer-geometry.js` y que ya
// aplica el sol de estudio (`baseAzimuthDeg - norteGrados`). Verificado a mano: con norteGrados=90
// (el eje +Z del plano apunta al Este real), un punto real al Este (este=D, norte=0) cae en local
// (x=0, z=D) = +Z del plano. Única fórmula de rotación de todo este módulo -- ground y edificios la
// comparten.
export function rotarAEjesLocales(este, norte, norteGrados) {
  var rad = THREE.MathUtils.degToRad(norteGrados || 0);
  return {
    x: este * Math.cos(rad) - norte * Math.sin(rad),
    z: este * Math.sin(rad) + norte * Math.cos(rad)
  };
}

// Tile XYZ (Web Mercator/Slippy Map) que contiene (lat,lon) a un zoom dado -- fórmula estándar OSM.
function tileParaLonLat(lon, lat, zoom) {
  var n = Math.pow(2, zoom);
  var x = Math.floor(((lon + 180) / 360) * n);
  var latRad = THREE.MathUtils.degToRad(lat);
  var y = Math.floor(((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n);
  return { x: x, y: y };
}

// Esquina noroeste (lat,lon) de un tile XYZ -- inversa de `tileParaLonLat`, para conocer los límites
// geográficos reales del mosaico ya ensamblado (hace falta para encajar sus 4 esquinas en metros).
function esquinaNoroesteTile(x, y, zoom) {
  var n = Math.pow(2, zoom);
  var lon = (x / n) * 360 - 180;
  var latRad = Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / n)));
  return { lat: THREE.MathUtils.radToDeg(latRad), lon: lon };
}

// Descarga UN tile de Esri World Imagery como `<img>` (CORS habilitado, comprobado en vivo con curl
// antes de escribir esto: `Access-Control-Allow-Origin: *`) -- nunca revienta el mosaico entero: un
// tile que falle se resuelve con `ok:false` y `construirMosaicoOrtofoto` lo rellena de gris liso.
function cargarTileOrtofoto(x, y, zoom) {
  return new Promise(function (resolve) {
    var img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = function () { resolve({ ok: true, img: img }); };
    img.onerror = function () { resolve({ ok: false, img: null }); };
    img.src = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/" + zoom + "/" + y + "/" + x;
  });
}

// Ensambla el mosaico N×N en un <canvas>, y devuelve la textura ya lista más las 4 esquinas del
// mosaico en metros este/norte REALES (sin rotar todavía -- quien llame aplica `rotarAEjesLocales`
// al construir la geometría, igual que con los edificios).
export function construirMosaicoOrtofoto(lat0, lon0) {
  var centro = tileParaLonLat(lon0, lat0, ORTOFOTO_ZOOM);
  var mitad = Math.floor(ORTOFOTO_TILES_POR_LADO / 2);
  var xMin = centro.x - mitad, yMin = centro.y - mitad;
  var lado = ORTOFOTO_TILES_POR_LADO * ORTOFOTO_TILE_PX;
  var canvas = document.createElement("canvas");
  canvas.width = lado;
  canvas.height = lado;
  var ctx = canvas.getContext("2d");
  ctx.fillStyle = "#3a3a3a"; // relleno de respaldo si algún tile falla -- nunca un hueco transparente
  ctx.fillRect(0, 0, lado, lado);

  var descargas = [];
  for (var fila = 0; fila < ORTOFOTO_TILES_POR_LADO; fila++) {
    for (var col = 0; col < ORTOFOTO_TILES_POR_LADO; col++) {
      (function (fila, col) {
        descargas.push(
          cargarTileOrtofoto(xMin + col, yMin + fila, ORTOFOTO_ZOOM).then(function (res) {
            if (res.ok) ctx.drawImage(res.img, col * ORTOFOTO_TILE_PX, fila * ORTOFOTO_TILE_PX, ORTOFOTO_TILE_PX, ORTOFOTO_TILE_PX);
          })
        );
      })(fila, col);
    }
  }

  return Promise.all(descargas).then(function () {
    var texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.needsUpdate = true;
    var noroeste = esquinaNoroesteTile(xMin, yMin, ORTOFOTO_ZOOM);
    var sureste = esquinaNoroesteTile(xMin + ORTOFOTO_TILES_POR_LADO, yMin + ORTOFOTO_TILES_POR_LADO, ORTOFOTO_ZOOM);
    return {
      texture: texture,
      esquinaNoroeste: metrosEsteNorteDesde(lat0, lon0, noroeste.lat, noroeste.lon),
      esquinaSureste: metrosEsteNorteDesde(lat0, lon0, sureste.lat, sureste.lon)
    };
  });
}

// Plano de ortofoto: geometría propia (no `PlaneGeometry` + `.rotateY()`) para que sus 4 esquinas
// pasen por la MISMA `rotarAEjesLocales` que los edificios colindantes -- evita depender de acertar a
// mano la convención de signo de la rotación nativa de Three.js. `y` (opcional, por defecto -0.03):
// altura del plano -- cada visor lo ajusta para ganar el z-fight contra su propio suelo de respaldo.
// `opacidad` (opcional, 2026-08-17, Fase 2 -- "atenúa el terreno satelital para que se lea como
// maqueta CAD/BIM"): por defecto 1 (opaco, comportamiento de siempre) -- SOLO `viewer-sandbox.js` pasa
// un valor menor; `viewer-edificio.js` (el otro llamador) sigue recibiendo la foto satelital opaca de
// siempre, sin cambios, porque ahí la ortofoto real fue un encargo explícito aparte (2026-08-16).
export function construirPlanoOrtofoto(mosaico, center, norteGrados, y, opacidad) {
  var altura = typeof y === "number" ? y : -0.03;
  var alfa = typeof opacidad === "number" ? opacidad : 1;
  var no = rotarAEjesLocales(mosaico.esquinaNoroeste.este, mosaico.esquinaNoroeste.norte, norteGrados);
  var se = rotarAEjesLocales(mosaico.esquinaSureste.este, mosaico.esquinaSureste.norte, norteGrados);
  // NO=(no.x,no.z), SE=(se.x,se.z); NE y SO son las otras dos combinaciones -- un rectángulo en ejes
  // locales (el mosaico es cuadrado en ejes este/norte reales; tras rotar por norteGrados sigue
  // siendo el mismo rectángulo, solo girado).
  var ne = { x: se.x, z: no.z };
  var so = { x: no.x, z: se.z };
  var geometry = new THREE.BufferGeometry();
  var positions = new Float32Array([
    no.x, altura, no.z, so.x, altura, so.z, se.x, altura, se.z,
    no.x, altura, no.z, se.x, altura, se.z, ne.x, altura, ne.z
  ]);
  var uvs = new Float32Array([0, 1, 0, 0, 1, 0, 0, 1, 1, 0, 1, 1]);
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("uv", new THREE.BufferAttribute(uvs, 2));
  geometry.computeVertexNormals();
  // `side: DoubleSide`: evita depender de acertar a mano el orden de bobinado de los 2 triángulos de
  // arriba -- un suelo nunca se ve por detrás, así que no hay coste real en renderizar las dos caras,
  // y sí un riesgo real de "suelo invisible" si el bobinado saliera al revés para alguna combinación
  // de norteGrados.
  var material = new THREE.MeshStandardMaterial({
    map: mosaico.texture, roughness: 1, metalness: 0, envMapIntensity: 0, side: THREE.DoubleSide,
    transparent: alfa < 1, opacity: alfa
  });
  var mesh = new THREE.Mesh(geometry, material);
  mesh.position.set(center.x, 0, center.z);
  mesh.receiveShadow = true;
  return mesh;
}

// Volúmenes extruidos de los edificios colindantes reales -- geometría simplificada (solo el
// contorno real de Catastro/OSM, extruido a la altura estimada; sin cubierta a dos aguas, aleros ni
// huecos). Opaco, sin transparencia (2026-08-17, corrección explícita: la transparencia anterior
// producía artefactos de orden de dibujado al solaparse con la ortofoto y con otros edificios
// colindantes) -- gris neutro mate (`MeshLambertMaterial`, sin componente especular) para que siga
// leyéndose como contexto de fondo frente al edificio/volumen que se esté diseñando, ahora por
// contraste de color y sin brillo, no por transparencia.
export var MAT_EDIFICIO_COLINDANTE = new THREE.MeshLambertMaterial({ color: 0xAAAAAA });

// Edificio existente dentro de la parcela, distinto de los vecinos (2026-08-17,
// docs/prd/2026-08-17-edificio-existente-y-vecinos-sandbox.md, aprobado): mismo tipo de material que
// el de arriba (opaco, mate, sin componente especular), color cálido propio para que destaque como
// "esto es lo que ya está construido en TU solar" frente al gris neutro de los vecinos.
export var MAT_EDIFICIO_EN_PARCELA = new THREE.MeshLambertMaterial({ color: 0xD4C5A9 });
// Borde sutil (encargo explícito, "1px más oscuro"): mismo tono que el relleno al 60% de brillo --
// derivado del color de arriba, no un valor inventado aparte, para que quede coherente si el color
// de relleno cambia en el futuro. 0xD4C5A9 × 0.6 ≈ 0x7F7765.
export var MAT_BORDE_EDIFICIO_EN_PARCELA = new THREE.LineBasicMaterial({ color: 0x7F7765 });

// Punto-en-polígono por ray-casting (algoritmo del número de cruces), en el plano local XZ -- misma
// convención `{x, z}` que ya usan `parcelaPoligonoLocal`/`construirContornoParcela`. Estándar, sin
// dependencias nuevas: no hace falta una librería de geometría solo para esta comprobación.
function puntoDentroDePoligono(punto, poligono) {
  var dentro = false;
  for (var i = 0, j = poligono.length - 1; i < poligono.length; j = i++) {
    var xi = poligono[i].x, zi = poligono[i].z;
    var xj = poligono[j].x, zj = poligono[j].z;
    var cruza = (zi > punto.z) !== (zj > punto.z) &&
      punto.x < (xj - xi) * (punto.z - zi) / (zj - zi) + xi;
    if (cruza) dentro = !dentro;
  }
  return dentro;
}

// Clasificación "en-parcela" vs. "vecino" (2026-08-17, ajuste explícito de Pablo -- sustituye el
// criterio anterior de "solo centroide dentro del polígono", que el propio PRD dejaba como
// refinamiento futuro pendiente para el caso de medianera): TRUE si el footprint del edificio
// INTERSECTA de verdad el polígono de la parcela -- solape parcial (medianera real, pared compartida
// con el footprint cruzando la linde) o contención total (edificio completo dentro). Ya no basta con
// que el centroide caiga dentro: un edificio medianero con la mayor parte de su masa fuera pero una
// esquina real solapando la parcela ahora sí se clasifica "en-parcela", que es el caso que el PRD
// original identificaba como su propio límite.
function poligonosSeIntersectan(poligonoA, poligonoB) {
  if (!poligonoA || poligonoA.length < 3 || !poligonoB || poligonoB.length < 3) return false;
  for (var i = 0; i < poligonoA.length; i++) {
    var a1 = poligonoA[i], a2 = poligonoA[(i + 1) % poligonoA.length];
    for (var j = 0; j < poligonoB.length; j++) {
      var b1 = poligonoB[j], b2 = poligonoB[(j + 1) % poligonoB.length];
      if (segmentosSeCruzan(a1, a2, b1, b2)) return true;
    }
  }
  // Ningún borde cruza -- o están completamente separados, o uno contiene al otro entero (sin que
  // ningún borde se toque). Un solo vértice de sonda de cada lado basta para distinguir los dos casos.
  if (puntoDentroDePoligono(poligonoA[0], poligonoB)) return true;
  if (puntoDentroDePoligono(poligonoB[0], poligonoA)) return true;
  return false;
}

// Exportada (2026-08-17): `viewer-sandbox.js` la reutiliza para el filtro de "colindancia" (radio de
// contexto + solape con la parcela, ver `filtrarColindantesPorRadio`) -- mismo criterio de
// intersección, una sola función, no una copia.
export { poligonosSeIntersectan };

// Detección de autointersección (2026-08-17, corrección en caliente -- encontrada verificando en vivo
// la alineación de colindantes en una zona densa de Madrid, Gran Vía): el comentario de más abajo, en
// `construirEdificiosColindantes`, YA decía "footprint degenerado (autointersección, colineal...) --
// se omite ese edificio" desde que se escribió, pero el único guardián real era el `try/catch`
// alrededor de `extrudeFootprint` -- y `THREE.ExtrudeGeometry`/su triangulador NO lanzan excepción con
// un anillo autointersecante (algunos edificios reales de Overpass, con patio interior o geometría
// compleja, llegan como un único anillo mal formado en vez de exterior+agujero): triangulan igualmente,
// produciendo una malla en zigzag que "dispara" fuera de la huella real del edificio -- exactamente lo
// que se vio en vivo (franjas grises radiando desde el centro de la escena, muy por fuera de cualquier
// edificio real). Con esto, ese caso pasa a detectarse ANTES de extruir y se omite de verdad, cerrando
// el hueco entre lo que el comentario decía y lo que el código hacía.
// Caso "puente/ojo de cerradura" (2026-08-17, corrección en caliente -- encontrado verificando en vivo
// un edificio grande y real de Gran Vía con el radio de contexto ya a 80m): un edificio con patio
// interior mapeado en OSM como UNA SOLA `way` (no como relación multipolígono con agujero) suele
// unir el anillo exterior con el anillo interior mediante un "puente" -- va y vuelve por la MISMA
// línea. Dos aristas así son colineales (el producto cruzado de la orientación da 0 en las 4
// combinaciones), así que el test de cruce de arriba, que exige las 4 orientaciones DISTINTAS DE
// CERO, nunca las marca como intersección -- el hueco exacto que dejaba pasar este caso real (visto
// en vivo: una malla en zigzag negra atravesando un edificio grande, más contenida que el "starburst"
// que ya arregló `poligonoAutointersecta`, pero la misma familia de bug). Aquí se cubre ese hueco:
// solo se llama cuando las 4 orientaciones ya dieron 0 (colineales) -- comprueba si los dos segmentos,
// proyectados sobre esa misma recta, se solapan en más que un punto de contacto.
function segmentosColinealesSeSolapan(p1, p2, p3, p4) {
  var dx = p2.x - p1.x, dz = p2.z - p1.z;
  var largoCuadrado = dx * dx + dz * dz;
  if (largoCuadrado < 1e-12) return false; // p1===p2, no define una recta
  function proyeccion(p) { return ((p.x - p1.x) * dx + (p.z - p1.z) * dz) / largoCuadrado; }
  var t3 = proyeccion(p3), t4 = proyeccion(p4);
  var loSolape = Math.max(Math.min(t3, t4), 0);
  var hiSolape = Math.min(Math.max(t3, t4), 1);
  return hiSolape - loSolape > 1e-6; // solape real a lo largo de la recta, no solo un extremo compartido
}

function segmentosSeCruzan(p1, p2, p3, p4) {
  function orientacion(a, b, c) {
    var v = (b.x - a.x) * (c.z - a.z) - (b.z - a.z) * (c.x - a.x);
    if (Math.abs(v) < 1e-9) return 0;
    return v > 0 ? 1 : -1;
  }
  var o1 = orientacion(p1, p2, p3), o2 = orientacion(p1, p2, p4);
  var o3 = orientacion(p3, p4, p1), o4 = orientacion(p3, p4, p2);
  if (o1 === 0 && o2 === 0 && o3 === 0 && o4 === 0) return segmentosColinealesSeSolapan(p1, p2, p3, p4);
  return o1 !== o2 && o3 !== o4 && o1 !== 0 && o2 !== 0 && o3 !== 0 && o4 !== 0;
}

// Exportada (2026-08-17, docs/prd/2026-08-17-solido-capaz-sandbox.md): `viewer-sandbox.js` la
// reutiliza para validar el polígono interior tras aplicar el offset de retranqueos -- misma función,
// no una copia, para que "qué cuenta como footprint degenerado" tenga un único criterio en todo el
// visor.
export function poligonoAutointersecta(puntos) {
  var n = puntos.length;
  if (n < 4) return false; // un triángulo nunca puede autointersecarse
  for (var i = 0; i < n; i++) {
    var a1 = puntos[i], a2 = puntos[(i + 1) % n];
    for (var j = i + 1; j < n; j++) {
      // aristas adyacentes (comparten un vértice, incluida la que cierra el anillo) no cuentan como cruce
      if (j === i || (i + 1) % n === j || (j + 1) % n === i) continue;
      var b1 = puntos[j], b2 = puntos[(j + 1) % n];
      if (segmentosSeCruzan(a1, a2, b1, b2)) return true;
    }
  }
  return false;
}

// `poligonoParcela` (2026-08-17, PRD edificio-existente-y-vecinos, aprobado): opcional -- si se pasa
// (mismos ejes locales `{x, z}` que `parcelaPoligonoLocal` en viewer-sandbox.js), cada edificio se
// clasifica y el que cae dentro se pinta con `MAT_EDIFICIO_EN_PARCELA` + borde en vez del gris de
// vecino. Sin este parámetro (como sigue llamando `viewer-edificio.js`, que no tiene concepto de
// "parcela propia" -- es el visor de un edificio ya modelado) el comportamiento es EXACTAMENTE el de
// antes: todos los edificios "vecino", sin ninguna clasificación -- cero regresión para ese visor.
export function construirEdificiosColindantes(edificios, centro, center, norteGrados, poligonoParcela) {
  var grupo = new THREE.Group();
  (edificios || []).forEach(function (edificio) {
    var puntos = (edificio.vertices || []).map(function (v) {
      var m = metrosEsteNorteDesde(centro.lat, centro.lon, v[0], v[1]);
      var r = rotarAEjesLocales(m.este, m.norte, norteGrados);
      return { x: center.x + r.x, z: center.z + r.z };
    });
    if (puntos.length < 3) return;
    if (poligonoAutointersecta(puntos)) return; // ver comentario junto a la función -- footprint mal formado real
    var altura = edificio.altura_m > 0 ? edificio.altura_m : 7; // 2026-08-17: 7m por defecto (antes 9), mismo valor que ya usa el backend (`_estimar_altura_edificio`) -- red de seguridad, no la fuente real
    var geometry;
    try {
      geometry = extrudeFootprint(puntos, altura);
    } catch (err) {
      return; // footprint degenerado (colineal, área nula...) -- se omite ese edificio, no se cuelga el visor
    }
    var enParcela = poligonoParcela ? poligonosSeIntersectan(puntos, poligonoParcela) : false;
    var mesh = new THREE.Mesh(geometry, enParcela ? MAT_EDIFICIO_EN_PARCELA : MAT_EDIFICIO_COLINDANTE);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    // `userData.enParcela`: así `viewer-sandbox.js` puede saber, tras la llamada, si encontró algún
    // edificio en la parcela (para el aviso "sin edificación registrada") sin tener que reclasificar
    // nada por su cuenta -- una sola fuente de verdad para el criterio de clasificación.
    mesh.userData.enParcela = enParcela;
    if (enParcela) {
      var bordes = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), MAT_BORDE_EDIFICIO_EN_PARCELA);
      mesh.add(bordes);
      // Base a Y=0.05 (2026-08-17, encargo explícito "sobre el pad de parcela"): `extrudeFootprint`
      // arranca siempre en Y=0 -- este desplazamiento es lo único que distingue verticalmente al
      // edificio propio del vecino (que se queda en Y=0, encargo explícito §3). Con el pad real a
      // [0, 0.15] (`GROSOR_PAD_PARCELA_M` en viewer-sandbox.js) los 0.10m entre 0.05 y 0.15 quedan
      // embebidos dentro del propio pad opaco -- sin hueco ni solape visible, igual que ya pasaba
      // antes con la base a Y=0 exacto.
      mesh.position.y = 0.05;
    }
    grupo.add(mesh);
  });
  return grupo;
}

// Línea de contorno real de la parcela (2026-08-16,
// docs/prd/2026-08-16-sandbox-navegacion-profesional-y-lindes.md): `geometriaParcela` es el campo
// aditivo del mismo nombre que devuelve `_entorno_3d_para` (`app.py`) -- `{tipo, coordenadas:
// [[lon,lat],...], superficie_m2, centro}` o `null` si Catastro no tenía parcela en ese punto (best
// effort, "no disponible, no error", mismo criterio que `construirEdificiosColindantes`). Reutiliza
// exactamente la misma proyección (`metrosEsteNorteDesde`/`rotarAEjesLocales`) que la ortofoto y los
// colindantes -- con `centro` (el punto de referencia común, no `geometriaParcela.centro`, que puede
// diferir ligeramente por venir del centroide propio del polígono) alinea sin desplazamiento.
export var MAT_CONTORNO_PARCELA = new THREE.LineBasicMaterial({ color: 0xFFC857, linewidth: 2 });

export function construirContornoParcela(geometriaParcela, centro, center, norteGrados, y) {
  if (!geometriaParcela || !geometriaParcela.coordenadas || geometriaParcela.coordenadas.length < 3) return null;
  var altura = typeof y === "number" ? y : 0.05;
  var puntos = geometriaParcela.coordenadas.map(function (par) {
    var lon = par[0], lat = par[1];
    var m = metrosEsteNorteDesde(centro.lat, centro.lon, lat, lon);
    var r = rotarAEjesLocales(m.este, m.norte, norteGrados);
    return new THREE.Vector3(center.x + r.x, altura, center.z + r.z);
  });
  var geometry = new THREE.BufferGeometry().setFromPoints(puntos);
  return new THREE.LineLoop(geometry, MAT_CONTORNO_PARCELA); // cierra el anillo sin duplicar el primer punto
}

// Corte de tiempo del lado del cliente (2026-08-16, corrección en caliente: verificado en vivo que
// `/api/entorno-3d-punto` puede tardar más de 120s de verdad -- no un supuesto, medido con `curl -m
// 120` contra el propio servidor local, que ni siquiera llegó a responder en ese margen -- cuando
// Overpass está degradado (`_post_overpass` en `analyzer/sitio.py` ya reintenta 3 veces con esperas
// de 2/4/8s, cada intento con SU PROPIO timeout de 20s: caso peor ~74s solo ahí, más la resolución de
// Catastro después). Ninguno de los dos `fetch` de abajo tenía antes ningún límite de tiempo propio
// -- el Sandbox podía quedarse el HUD/overlay de carga esperando ese peor caso entero, sintiéndose
// "colgado" aunque el servidor siguiera trabajando de verdad.
//
// Subido de 12000 a 45000 (arreglo crítico, 2026-08-16): con 12s, esta llamada abortaba ANTES de que
// Overpass respondiera en el caso normal-lento (no solo en el patológico) -- verificado en vivo esta
// misma sesión con tiempos reales de 40-90s+. Antes eso también se llevaba por delante el contorno de
// la parcela (`body.geometria_parcela`), porque era la ÚNICA fuente del Sandbox para "hay parcela
// real aquí" -- de ahí el bug reportado "se pierde el objeto de parcela al pasar al Sandbox". Ahora
// `viewer-sandbox.js` puede sembrar contorno/pad/HUD SÍNCRONAMENTE desde la geometría que ya trajo el
// Paso 0 (`opts.geometriaParcela`), así que esta llamada deja de ser crítica para esa parte -- solo
// trae colindantes reales y habilita la ortofoto. Con eso desacoplado, dar más margen aquí ya no
// arriesga nada más que tardar un poco más en mostrar los colindantes; pasado el margen, se trata
// exactamente igual que cualquier otro fallo de red: NUNCA se inventa una parcela/contorno de repuesto
// (eso sería indistinguible en pantalla de datos reales de Catastro, justo lo que este proyecto evita
// en todo el resto del código) -- se degrada a `{disponible:false}`, el mismo camino honesto que ya
// maneja `viewer-sandbox.js` (sin colindantes/ortofoto, pero SÍ con la parcela real si el Paso 0 la
// trajo).
var TIMEOUT_ENTORNO_3D_MS = 45000;

function _fetchConTimeout(url, timeoutMs) {
  var controlador = new AbortController();
  var temporizador = setTimeout(function () { controlador.abort(); }, timeoutMs);
  return fetch(url, { signal: controlador.signal }).then(
    function (resp) { clearTimeout(temporizador); return resp; },
    function (err) { clearTimeout(temporizador); throw err; }
  );
}

// Pide `/api/proyectos/<id>/entorno-3d` y devuelve directamente el JSON (o `{disponible:false}` si
// la petición falla) -- envoltorio mínimo compartido para no repetir el `fetch`/`catch` en cada
// visor. NUNCA lanza: un fallo de red (o un timeout, ver `TIMEOUT_ENTORNO_3D_MS` arriba) es
// indistinguible de "no disponible" para quien llama.
export function pedirEntorno3D(proyectoId) {
  return _fetchConTimeout("/api/proyectos/" + encodeURIComponent(proyectoId) + "/entorno-3d", TIMEOUT_ENTORNO_3D_MS)
    .then(function (resp) { return resp.json().catch(function () { return {}; }); })
    .catch(function () { return { disponible: false }; });
}

// Igual que `pedirEntorno3D`, pero para el Modo Sandbox (2026-08-17): parte solo de lat/lon (todavía
// no hay ningún proyecto guardado con el que enlazar un sitio) -- pide `/api/entorno-3d-punto`, que
// no depende de ningún `proyecto_id`.
//
// `timeoutMs` opcional (2026-08-17, corrección en caliente -- "Lienzo libre tarda demasiado, se queda
// bloqueado al 10%"): por defecto usa `TIMEOUT_ENTORNO_3D_MS` (45s), pero `viewer-sandbox.js` pasa un
// margen mucho más corto (8s) cuando el Paso 0 YA trajo la geometría real de la parcela -- en ese caso
// esta llamada solo aporta colindantes/ortofoto de contexto, nunca la parcela en sí, así que no tiene
// sentido bloquear nada esperándola tanto como antes.
export function pedirEntorno3DPorCoordenadas(lat, lon, timeoutMs) {
  var qs = "lat=" + encodeURIComponent(lat) + "&lon=" + encodeURIComponent(lon);
  return _fetchConTimeout("/api/entorno-3d-punto?" + qs, timeoutMs || TIMEOUT_ENTORNO_3D_MS)
    .then(function (resp) { return resp.json().catch(function () { return {}; }); })
    .catch(function () { return { disponible: false }; });
}

// Normativa urbanística real por coordenada -- piloto Madrid (2026-08-16,
// docs/prd/2026-08-16-integracion-normativa-catastro-pgou.md). Timeout propio, más largo que
// `TIMEOUT_ENTORNO_3D_MS`: medido en vivo, el servicio ArcGIS municipal (`sigma.madrid.es`) responde con
// una latencia irregular (10-20s+, ver `analyzer/normativa_madrid.py`) -- como esta llamada se lanza en
// paralelo, no bloqueante, y nunca gatea la barra de progreso del Sandbox, un timeout más largo aquí solo
// cambia cuánto puede tardar en aparecer el dato/aviso, nunca bloquea nada más.
var TIMEOUT_NORMATIVA_MADRID_MS = 15000;

export function pedirNormativaUrbanisticaPunto(lat, lon) {
  var qs = "lat=" + encodeURIComponent(lat) + "&lon=" + encodeURIComponent(lon);
  return _fetchConTimeout("/api/normativa-urbanistica-punto?" + qs, TIMEOUT_NORMATIVA_MADRID_MS)
    .then(function (resp) { return resp.json().catch(function () { return {}; }); })
    .catch(function () { return { disponible: false, dentro_de_piloto: false, motivo: null, referencia: null, limites_numericos: null }; });
}

// --- Terreno orgánico local (2026-08-16, docs/prd/2026-08-16-visor-sandbox-terreno-real-y-
// materiales-archviz.md) -----------------------------------------------------------------------
//
// Relieve de RELLENO VISUAL, no información geográfica: ruido determinista calculado en el
// cliente, sin ninguna llamada de red ni dependencia externa. Deliberadamente NO intenta
// aproximar la elevación real de ningún punto concreto -- si eso hiciera falta algún día, la
// integración de un DEM real (IGN/Copernicus/Mapbox Terrain-RGB) queda reservada exclusivamente
// para `viewer-edificio.js`, que ya tiene el pipeline de sitio georreferenciado real
// (`pedirEntorno3D`/`construirPlanoOrtofoto` de más arriba); el Sandbox, por diseño (ver cabecera
// de `viewer-sandbox.js`), puede no tener ninguna parcela real vinculada, así que un DEM real no
// siempre tendría de qué punto pedir datos.

// Ruido de valor 2D (grid hash + interpolación smoothstep) -- no es simplex/Perlin "de libro", es
// la variante más simple que da un resultado orgánico sin arrastrar ninguna librería nueva.
// Determinista: la misma (x, y, semilla) da siempre la misma altura, así el terreno no "tiembla"
// entre fotogramas ni cambia si se reabre el Sandbox con la misma semilla.
function hashGrid2D(ix, iy, semilla) {
  var h = (ix * 374761393 + iy * 668265263 + semilla * 2147483647) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h = (h ^ (h >>> 16)) >>> 0;
  return h / 4294967295; // [0, 1)
}

function smoothstep01(t) { return t * t * (3 - 2 * t); }

function ruidoValor2D(x, y, semilla) {
  var ix = Math.floor(x), iy = Math.floor(y);
  var fx = smoothstep01(x - ix), fy = smoothstep01(y - iy);
  var v00 = hashGrid2D(ix, iy, semilla), v10 = hashGrid2D(ix + 1, iy, semilla);
  var v01 = hashGrid2D(ix, iy + 1, semilla), v11 = hashGrid2D(ix + 1, iy + 1, semilla);
  var a = v00 + (v10 - v00) * fx;
  var b = v01 + (v11 - v01) * fx;
  return a + (b - a) * fy; // [0, 1)
}

// Suma de varias octavas de `ruidoValor2D` (frecuencia creciente, amplitud decreciente): una sola
// octava se ve como colinas regulares y "de juguete"; 4 octavas rompen esa regularidad sin que el
// resultado deje de ser suave.
function ruidoFractal2D(x, y, semilla, octavas) {
  var total = 0, amplitud = 1, frecuencia = 1, maxAmplitud = 0;
  for (var i = 0; i < octavas; i++) {
    total += ruidoValor2D(x * frecuencia, y * frecuencia, semilla + i * 101) * amplitud;
    maxAmplitud += amplitud;
    amplitud *= 0.5;
    frecuencia *= 2;
  }
  return total / maxAmplitud; // [0, 1)
}

// Altura del terreno orgánico en coordenadas de MUNDO (x, z), en metros. Misma función que usa
// `construirTerrenoOrganico` para desplazar los vértices de su malla -- se expone aparte para que
// quien coloque objetos sobre el terreno (los volúmenes del Sandbox) pueda apoyarlos a la altura
// real del relieve en su (x, z) en vez de asumir y=0.
export function alturaTerrenoOrganico(x, z, opts) {
  var v = opts || {};
  var escala = v.escala != null ? v.escala : 0.035; // "tamaño" de las colinas: más bajo = colinas más anchas
  var amplitud = v.amplitud != null ? v.amplitud : 1.6; // metros, pico a pico aprox.
  var radio = v.radio != null ? v.radio : 150;
  var semilla = v.semilla != null ? v.semilla : 1337;

  var distancia = Math.sqrt(x * x + z * z);
  // Atenúa el relieve hacia el borde del disco de terreno para que no quede un escalón visible en
  // el límite: el último 20% del radio interpola linealmente a 0.
  var borde = radio * 0.8;
  var atenuacion = distancia <= borde ? 1 : Math.max(0, 1 - (distancia - borde) / (radio - borde));
  var ruidoCentrado = ruidoFractal2D(x * escala, z * escala, semilla, 4) - 0.5;
  return ruidoCentrado * amplitud * atenuacion;
}

// Disco subdividido en anillos concéntricos -- `THREE.CircleGeometry` no sirve de base porque solo
// tiene un abanico de triángulos desde el centro (sin anillos intermedios): desplazar sus vértices
// daría un relieve "de paraguas" picudo desde el centro, no colinas suaves. Construido a mano, plano
// en el plano XY (igual que `THREE.CircleGeometry`) para que el criterio de rotarlo a horizontal
// (`mesh.rotation.x = -Math.PI/2`) sea el mismo que ya usa el resto de este módulo.
function construirDiscoSubdividido(radio, segmentosRadiales, anillos) {
  var positions = [], uvs = [], indices = [];
  positions.push(0, 0, 0);
  uvs.push(0.5, 0.5);
  for (var anillo = 1; anillo <= anillos; anillo++) {
    var r = radio * (anillo / anillos);
    for (var seg = 0; seg < segmentosRadiales; seg++) {
      var theta = (seg / segmentosRadiales) * Math.PI * 2;
      var x = Math.cos(theta) * r, y = Math.sin(theta) * r;
      positions.push(x, y, 0);
      uvs.push(x / (2 * radio) + 0.5, y / (2 * radio) + 0.5);
    }
  }
  for (var s = 0; s < segmentosRadiales; s++) {
    indices.push(0, 1 + s, 1 + ((s + 1) % segmentosRadiales));
  }
  for (var anilloExt = 1; anilloExt < anillos; anilloExt++) {
    var baseInt = 1 + (anilloExt - 1) * segmentosRadiales;
    var baseExt = 1 + anilloExt * segmentosRadiales;
    for (var s2 = 0; s2 < segmentosRadiales; s2++) {
      var s2n = (s2 + 1) % segmentosRadiales;
      var i0 = baseInt + s2, i1 = baseInt + s2n, i2 = baseExt + s2, i3 = baseExt + s2n;
      indices.push(i0, i2, i1);
      indices.push(i1, i2, i3);
    }
  }
  var geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  geo.setIndex(indices);
  return geo;
}

// Malla de terreno con relieve orgánico local, lista para `scene.add(...)`. Fallback para cuando no
// hay (o no se usan) datos de elevación reales -- ver nota de reserva de DEM real más arriba.
export function construirTerrenoOrganico(opts) {
  var v = opts || {};
  var radio = v.radio != null ? v.radio : 150;
  var geo = construirDiscoSubdividido(radio, v.segmentosRadiales != null ? v.segmentosRadiales : 64, v.anillos != null ? v.anillos : 40);

  var pos = geo.attributes.position;
  for (var i = 0; i < pos.count; i++) {
    var lx = pos.getX(i), ly = pos.getY(i);
    // Antes de rotar -90° en X, el eje local Z pasa a ser la altura (Y) de mundo, y el eje local Y
    // pasa a ser -Z de mundo -- por eso se evalúa el ruido en (lx, -ly): así coincide con las
    // coordenadas de mundo (x, z) que usa `alturaTerrenoOrganico` cuando se llama desde fuera (para
    // apoyar los volúmenes del Sandbox a la altura real del relieve bajo ellos).
    pos.setZ(i, alturaTerrenoOrganico(lx, -ly, v));
  }
  pos.needsUpdate = true;
  geo.computeVertexNormals();

  var material = v.material || new THREE.MeshStandardMaterial({
    color: v.color != null ? v.color : 0x6E7A5E, roughness: 1, metalness: 0
  });
  var mesh = new THREE.Mesh(geo, material);
  mesh.rotation.x = -Math.PI / 2;
  mesh.receiveShadow = true;
  return mesh;
}

// Zócalo de maqueta física (2026-08-16, docs/prd/2026-08-16-presets-progreso-y-zocalo-sandbox.md):
// cilindro neutro bajo el terreno/ortofoto del Sandbox, para que se lea como un objeto físico con
// espesor (una maqueta de estudio) en vez de una lámina 2D flotando sobre el vacío. `radio` debe
// coincidir con el radio real del terreno/suelo que va encima (150 m por defecto en
// `crearGroundNeutro`/`construirTerrenoOrganico` de `viewer-sandbox.js`) -- un radio menor dejaría
// asomar el borde del terreno por fuera del zócalo. `alturaSuperior` (y del borde superior del
// zócalo) la decide quien llama: con terreno orgánico debe quedar por debajo del punto más bajo del
// relieve en TODO el radio (si no, se vería el "fondo" del terreno asomando en las zonas más
// hundidas); con suelo plano (parcela real + ortofoto) basta un margen pequeño bajo y=0.
export function construirZocaloTerreno(radio, opts) {
  var v = opts || {};
  var grosor = v.grosor != null ? v.grosor : 3; // metros -- "2 a 5 m" del encargo
  var alturaSuperior = v.alturaSuperior != null ? v.alturaSuperior : -0.5;
  var segmentos = v.segmentos != null ? v.segmentos : 64;
  var geo = new THREE.CylinderGeometry(radio, radio, grosor, segmentos, 1, false);
  var material = v.material || new THREE.MeshStandardMaterial({
    color: v.color != null ? v.color : 0xC9C4B8, roughness: 0.9, metalness: 0.05
  });
  var mesh = new THREE.Mesh(geo, material);
  // El cilindro nace centrado en su propio origen ([-grosor/2, +grosor/2]) -- se desplaza para que su
  // cara SUPERIOR quede exactamente en `alturaSuperior`, no su centro.
  mesh.position.y = alturaSuperior - grosor / 2;
  // `castShadow: false` (deliberado): el zócalo queda cubierto por el terreno/ortofoto del mismo
  // radio que va encima -- su única cara realmente visible es la lateral, que basta con que RECIBA
  // luz/sombra de forma correcta, sin necesidad de que además proyecte su propia sombra sobre nada.
  mesh.receiveShadow = true;
  mesh.castShadow = false;
  return mesh;
}
