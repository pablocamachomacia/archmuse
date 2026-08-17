// Prueba de static/solar-posicion.js — determinista, sin navegador.
//
// Ejecutar:  node tests/test_solar_posicion.mjs
//
// No compara contra ninguna tabla de una librería externa (no hay ninguna
// referencia de terceros instalada) — compara contra HECHOS de astronomía
// esférica bien conocidos y verificables a mano, independientes de este
// algoritmo en concreto:
//   1. La declinación solar en los solsticios es ±23.44° (la oblicuidad
//      del eje terrestre) y 0° en los equinoccios -- por definición de qué
//      es un solsticio/equinoccio, no un resultado de ESTE código.
//   2. La elevación solar al mediodía solar real es exactamente
//      90° − |latitud − declinación| -- geometría esférica básica,
//      independiente del algoritmo de declinación usado.
//   3. Al mediodía solar real el azimut es 180° (sol al sur) en el
//      hemisferio norte, 0°/360° (sol al norte) en el hemisferio sur.

import { diaDelAnioUTC, horasDeSolEnDia, posicionSolar } from "../static/solar-posicion.js";

let fallos = 0;
let total = 0;

function check(nombre, cond, detalle) {
  total++;
  const estado = cond ? "OK  " : "FALLO";
  console.log(`  [${estado}] ${nombre}${detalle !== undefined ? "  -> " + detalle : ""}`);
  if (!cond) fallos++;
}

function cercaDe(valor, esperado, tolerancia) {
  return Math.abs(valor - esperado) <= tolerancia;
}

// Busca el instante de elevación máxima (mediodía solar real) barriendo
// minuto a minuto en una ventana de +/-2h alrededor del mediodía solar
// ESTIMADO por longitud (UTC ~= 12:00 - lon/15 h) -- el mediodía solar real
// no cae a las 12:00 UTC salvo en el meridiano de Greenwich (con la
// primera versión de este test, centrada siempre en las 12:00 UTC, la
// ventana de +/-3h no llegaba a cubrir el mediodía real de Buenos Aires,
// ~15:53 UTC por su longitud -- fallo del test, no del algoritmo).
function mediodiaSolar(lat, lon, fechaDiaUTC) {
  const offsetHorasEstimado = -lon / 15;
  const centroMin = fechaDiaUTC.getTime() + offsetHorasEstimado * 3600000;
  let mejor = { elevacion_grados: -999 };
  for (let min = -150; min <= 150; min++) {
    const instante = new Date(centroMin + min * 60000);
    const p = posicionSolar(lat, lon, instante);
    if (p.elevacion_grados > mejor.elevacion_grados) mejor = p;
  }
  return mejor;
}

console.log("1. diaDelAnioUTC()");
check("1 enero = día 1", diaDelAnioUTC(new Date(Date.UTC(2026, 0, 1))) === 1);
check("31 diciembre 2026 (no bisiesto) = día 365", diaDelAnioUTC(new Date(Date.UTC(2026, 11, 31))) === 365);
check("29 febrero 2028 (bisiesto) existe y el día siguiente es 61", diaDelAnioUTC(new Date(Date.UTC(2028, 2, 1))) === 61);

console.log("\n2. Declinación en solsticios y equinoccios (hecho astronómico: ±23.44° / 0°)");
const MADRID = { lat: 40.4168, lon: -3.7038 };
const solsticioVerano = new Date(Date.UTC(2026, 5, 21, 12, 0, 0));
const solsticioInvierno = new Date(Date.UTC(2026, 11, 21, 12, 0, 0));
const equinoccioPrimavera = new Date(Date.UTC(2026, 2, 20, 12, 0, 0));
const equinoccioOtono = new Date(Date.UTC(2026, 8, 22, 12, 0, 0));

check(
  "solsticio de verano: declinación ≈ +23.44° (tolerancia 0.3°)",
  cercaDe(posicionSolar(MADRID.lat, MADRID.lon, solsticioVerano).declinacion_grados, 23.44, 0.3),
  posicionSolar(MADRID.lat, MADRID.lon, solsticioVerano).declinacion_grados
);
check(
  "solsticio de invierno: declinación ≈ -23.44° (tolerancia 0.3°)",
  cercaDe(posicionSolar(MADRID.lat, MADRID.lon, solsticioInvierno).declinacion_grados, -23.44, 0.3),
  posicionSolar(MADRID.lat, MADRID.lon, solsticioInvierno).declinacion_grados
);
// Tolerancia más ancha que en los solsticios (0.3°) a propósito: el
// instante exacto del equinoccio varía de un año a otro dentro del mismo
// día civil (puede caer de madrugada o de noche en UTC), así que "20/22 de
// marzo/septiembre a las 12:00 UTC" es una aproximación al equinoccio real,
// no el instante exacto -- 1.0° cubre esa incertidumbre de fecha sin dejar
// de detectar un fallo real del algoritmo (que daría muchos grados de más).
check(
  "equinoccio de primavera: declinación ≈ 0° (tolerancia 1.0°, la fecha exacta del equinoccio varía por año)",
  cercaDe(posicionSolar(MADRID.lat, MADRID.lon, equinoccioPrimavera).declinacion_grados, 0, 1.0),
  posicionSolar(MADRID.lat, MADRID.lon, equinoccioPrimavera).declinacion_grados
);
check(
  "equinoccio de otoño: declinación ≈ 0° (tolerancia 1.0°, la fecha exacta del equinoccio varía por año)",
  cercaDe(posicionSolar(MADRID.lat, MADRID.lon, equinoccioOtono).declinacion_grados, 0, 1.0),
  posicionSolar(MADRID.lat, MADRID.lon, equinoccioOtono).declinacion_grados
);

console.log("\n3. Elevación al mediodía solar real = 90° − |lat − declinación| (geometría esférica, no del algoritmo)");
const mdVeranoMadrid = mediodiaSolar(MADRID.lat, MADRID.lon, solsticioVerano);
const elevacionEsperadaVerano = 90 - Math.abs(MADRID.lat - mdVeranoMadrid.declinacion_grados);
check(
  "Madrid, solsticio de verano: elevación máxima ≈ 90° − |40.42° − 23.44°| ≈ 73.0°",
  cercaDe(mdVeranoMadrid.elevacion_grados, elevacionEsperadaVerano, 0.2),
  `obtenida ${mdVeranoMadrid.elevacion_grados.toFixed(2)}°, esperada ${elevacionEsperadaVerano.toFixed(2)}°`
);
check(
  "Madrid, solsticio de verano: azimut al mediodía solar ≈ 180° (sol al sur, hemisferio norte)",
  cercaDe(mdVeranoMadrid.azimut_grados, 180, 1),
  mdVeranoMadrid.azimut_grados.toFixed(2)
);

const mdInviernoMadrid = mediodiaSolar(MADRID.lat, MADRID.lon, solsticioInvierno);
const elevacionEsperadaInvierno = 90 - Math.abs(MADRID.lat - mdInviernoMadrid.declinacion_grados);
check(
  "Madrid, solsticio de invierno: elevación máxima ≈ 90° − |40.42° − (-23.44°)| ≈ 26.1°",
  cercaDe(mdInviernoMadrid.elevacion_grados, elevacionEsperadaInvierno, 0.2),
  `obtenida ${mdInviernoMadrid.elevacion_grados.toFixed(2)}°, esperada ${elevacionEsperadaInvierno.toFixed(2)}°`
);
check(
  "el sol está más bajo al mediodía en invierno que en verano, en Madrid",
  mdInviernoMadrid.elevacion_grados < mdVeranoMadrid.elevacion_grados
);

console.log("\n4. Hemisferio sur: en junio (invierno austral), el sol al mediodía está más bajo que en Madrid");
const BUENOS_AIRES = { lat: -34.6, lon: -58.4 };
const mdBAInvierno = mediodiaSolar(BUENOS_AIRES.lat, BUENOS_AIRES.lon, solsticioVerano); // "verano" boreal = invierno austral
check(
  "Buenos Aires, 21 de junio: azimut al mediodía ≈ 0°/360° (sol al norte, hemisferio sur)",
  cercaDe(mdBAInvierno.azimut_grados, 0, 1) || cercaDe(mdBAInvierno.azimut_grados, 360, 1),
  mdBAInvierno.azimut_grados.toFixed(2)
);
const elevacionEsperadaBA = 90 - Math.abs(BUENOS_AIRES.lat - mdBAInvierno.declinacion_grados);
check(
  "Buenos Aires, 21 de junio: elevación máxima ≈ 90° − |−34.6° − 23.44°| ≈ 32.0°",
  cercaDe(mdBAInvierno.elevacion_grados, elevacionEsperadaBA, 0.2),
  `obtenida ${mdBAInvierno.elevacion_grados.toFixed(2)}°`
);

console.log("\n5. Ecuador en equinoccio: el sol pasa casi por el cenit al mediodía (elevación ≈ 90°)");
const mdEcuador = mediodiaSolar(0, 0, equinoccioPrimavera);
check("elevación > 88° en el ecuador en equinoccio", mdEcuador.elevacion_grados > 88, mdEcuador.elevacion_grados.toFixed(2));

console.log("\n6. De noche, elevación negativa (sol bajo el horizonte)");
const madrugadaInvierno = new Date(Date.UTC(2026, 11, 21, 3, 0, 0)); // 03:00 UTC ~ 04:00 hora de Madrid en invierno
const posMadrugada = posicionSolar(MADRID.lat, MADRID.lon, madrugadaInvierno);
check("elevación < 0 a las 3:00 UTC en pleno invierno", posMadrugada.elevacion_grados < 0, posMadrugada.elevacion_grados.toFixed(2));

console.log("\n7. horasDeSolEnDia() — más horas de sol en verano que en invierno, en Madrid");
const horasVerano = horasDeSolEnDia(MADRID.lat, MADRID.lon, new Date(Date.UTC(2026, 5, 21, 0, 0, 0)));
const horasInvierno = horasDeSolEnDia(MADRID.lat, MADRID.lon, new Date(Date.UTC(2026, 11, 21, 0, 0, 0)));
check(
  `verano (${horasVerano.toFixed(1)}h) > invierno (${horasInvierno.toFixed(1)}h)`,
  horasVerano > horasInvierno
);
check("verano: entre 14 y 16 horas de sol (Madrid, latitud ~40°N)", horasVerano >= 14 && horasVerano <= 16, horasVerano.toFixed(2));
check("invierno: entre 8 y 10 horas de sol (Madrid, latitud ~40°N)", horasInvierno >= 8 && horasInvierno <= 10, horasInvierno.toFixed(2));

console.log("\n" + "=".repeat(55));
if (fallos > 0) {
  console.log(`FALLOS (${fallos} de ${total})`);
  process.exit(1);
}
console.log(`Todas las comprobaciones OK (${total})`);
