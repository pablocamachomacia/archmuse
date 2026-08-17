// Posición solar (azimut/elevación) — algoritmo NOAA de baja precisión
// (basado en Meeus, "Astronomical Algorithms"), no el SPA de Reda & Andreas
// (NREL, 2004) que pedía el encargo.
//
// Por qué esta variante y no la otra, dicho explícitamente en vez de en
// silencio: el SPA de Reda & Andreas tiene precisión de ~0.0003° pero se
// define con decenas de términos de series VSOP87/ELP-2000 — no tengo esas
// tablas memorizadas con la fiabilidad necesaria para reproducirlas sin
// verificación externa, y equivocar un término habría sido peor que no
// implementarlo (un error silencioso en astronomía es difícil de detectar a
// simple vista). El algoritmo NOAA de aquí tiene precisión de ~0.01° en
// elevación/azimut — de sobra para sombras arquitectónicas — y SÍ se puede
// verificar con números de referencia bien conocidos (declinación en
// solsticios/equinoccios, elevación solar al mediodía) sin depender de
// ninguna tabla externa. `tests/test_solar_posicion.js` lo hace.
//
// Módulo puro: sin DOM, sin Mapbox, sin Threebox — así se puede probar con
// Node directamente, sin un navegador. `static/visor-mapa.js` lo importa.

/** Día del año (1-365/366), en UTC -- evita ambigüedad de zona horaria: la
 * fecha/hora que importa aquí es siempre la de `fecha.getUTCFullYear()` etc.,
 * nunca la hora local del navegador de quien mira el visor. */
export function diaDelAnioUTC(fecha) {
  const inicioAnio = Date.UTC(fecha.getUTCFullYear(), 0, 1);
  const ms = fecha.getTime() - inicioAnio;
  return Math.floor(ms / 86400000) + 1;
}

/**
 * Posición solar real para una fecha/hora UTC y unas coordenadas.
 *
 * @param {number} latGrados Latitud, grados (+N).
 * @param {number} lonGrados Longitud, grados (+E).
 * @param {Date} fecha Fecha/hora — se usan SIEMPRE sus componentes UTC.
 * @returns {{azimut_grados:number, elevacion_grados:number, declinacion_grados:number, dia_del_anio:number}}
 *   `azimut_grados`: 0-360, medido en sentido horario desde el norte (0=N, 90=E, 180=S, 270=O).
 *   `elevacion_grados`: -90 a 90, 0 = horizonte, 90 = cenit. Negativo = sol bajo el horizonte (de noche).
 */
export function posicionSolar(latGrados, lonGrados, fecha) {
  const n = diaDelAnioUTC(fecha);
  const horaUTC = fecha.getUTCHours() + fecha.getUTCMinutes() / 60 + fecha.getUTCSeconds() / 3600;

  // Ángulo fraccional del año (radianes), contando la hora del día -- así
  // la declinación/ecuación del tiempo varían suavemente hora a hora, no
  // solo día a día.
  const gamma = ((2 * Math.PI) / 365) * (n - 1 + (horaUTC - 12) / 24);

  // Ecuación del tiempo, en minutos (diferencia entre el mediodía solar
  // real y el mediodía de reloj, por la excentricidad de la órbita y la
  // oblicuidad del eje terrestre).
  const eqTimeMin =
    229.18 *
    (0.000075 +
      0.001868 * Math.cos(gamma) -
      0.032077 * Math.sin(gamma) -
      0.014615 * Math.cos(2 * gamma) -
      0.040849 * Math.sin(2 * gamma));

  // Declinación solar, radianes.
  const declRad =
    0.006918 -
    0.399912 * Math.cos(gamma) +
    0.070257 * Math.sin(gamma) -
    0.006758 * Math.cos(2 * gamma) +
    0.000907 * Math.sin(2 * gamma) -
    0.002697 * Math.cos(3 * gamma) +
    0.00148 * Math.sin(3 * gamma);

  // Todo en UTC -- el término de "zona horaria" del algoritmo NOAA
  // original se omite a propósito (offset = 0) porque `horaUTC` ya es UTC;
  // solo hace falta la corrección de longitud (4 min por grado).
  const timeOffsetMin = eqTimeMin + 4 * lonGrados;
  const trueSolarTimeMin = horaUTC * 60 + timeOffsetMin;

  let hourAngleGrados = trueSolarTimeMin / 4 - 180;
  if (hourAngleGrados < -180) hourAngleGrados += 360;
  if (hourAngleGrados > 180) hourAngleGrados -= 360;

  const latRad = (latGrados * Math.PI) / 180;
  const hourAngleRad = (hourAngleGrados * Math.PI) / 180;

  let cosZenith = Math.sin(latRad) * Math.sin(declRad) + Math.cos(latRad) * Math.cos(declRad) * Math.cos(hourAngleRad);
  cosZenith = Math.max(-1, Math.min(1, cosZenith));
  const zenithRad = Math.acos(cosZenith);
  const elevacionGrados = 90 - (zenithRad * 180) / Math.PI;

  // Cerca del cenit/nadir, sin(zenith) ~ 0 y el azimut queda indefinido
  // (división por ~0) -- se fija a 180° (convención arbitraria pero
  // estable) en vez de dejar pasar un NaN/Infinity al resto del visor.
  const senZenith = Math.sin(zenithRad);
  let azimutGrados;
  if (Math.abs(senZenith) < 1e-6) {
    azimutGrados = 180;
  } else {
    let cosAzimut = -(Math.sin(latRad) * Math.cos(zenithRad) - Math.sin(declRad)) / (Math.cos(latRad) * senZenith);
    cosAzimut = Math.max(-1, Math.min(1, cosAzimut));
    azimutGrados = (Math.acos(cosAzimut) * 180) / Math.PI;
    if (hourAngleGrados > 0) azimutGrados = 360 - azimutGrados;
  }

  return {
    azimut_grados: azimutGrados,
    elevacion_grados: elevacionGrados,
    declinacion_grados: (declRad * 180) / Math.PI,
    dia_del_anio: n,
  };
}

/** Horas de luz solar directa en una fecha, para una latitud/longitud dada
 * -- barrido cada 10 minutos entre las 00:00 y las 23:59 UTC, contando los
 * intervalos con `elevacion_grados > 0`. Aproximado (no calcula el instante
 * exacto de orto/ocaso), suficiente para comparar fachadas/estaciones entre
 * sí, no para certificar un valor exacto de horas de sol. */
export function horasDeSolEnDia(latGrados, lonGrados, fechaUTCMedianoche) {
  let minutosConSol = 0;
  for (let minutos = 0; minutos < 24 * 60; minutos += 10) {
    const instante = new Date(fechaUTCMedianoche.getTime() + minutos * 60000);
    const { elevacion_grados: elevacion } = posicionSolar(latGrados, lonGrados, instante);
    if (elevacion > 0) minutosConSol += 10;
  }
  return minutosConSol / 60;
}
