// Programa de Necesidades (2026-08-17, docs/prd/2026-08-17-programa-de-necesidades.md, aprobado con
// 4 decisiones explícitas de Pablo -- ver el bloque "Decisión" al pie de ese PRD):
//   1. La validación de edificabilidad usa SIEMPRE la del Sólido Capaz de la parcela REAL cargada. La
//      cifra de un preset (p.ej. 6.250 m²e de Berrocales) es la META deseada del usuario, nunca el
//      techo contra el que se compara -- si la parcela cargada no es literalmente esa parcela, los dos
//      números pueden no coincidir, y eso es correcto, no un bug.
//   2. Ratio Construida/Útil: editable, por defecto 1.42 (1.45 al cargar el preset Berrocales).
//   3. "Viviendas que caben": puntos medios de cada tipología (1D 45m² / 2D 55m² / 3D 70m² / 4D 90m²),
//      con edición secundaria de esas superficies medias.
//   4. Nº de plantas se AUTORRELLENA desde el Sólido Capaz mientras el usuario no lo haya tocado a
//      mano; en cuanto lo toca (o carga un preset), deja de sobrescribirse en silencio -- en su lugar
//      se valida contra el máximo del Sólido Capaz y se avisa si lo supera (mismo criterio "nunca
//      convertir/recortar en silencio" que ya usa el resto del Sandbox para ocupación/edificabilidad).
//
// Módulo de cliente puro (sin three.js) -- un panel HUD más del Sandbox, mismo patrón modular que
// viewer-terreno.js/viewer-materials.js: `viewer-sandbox.js` lo importa por namespace y lo monta/
// desmonta dentro de su propio open()/teardown(), y le informa del resultado del Sólido Capaz cada vez
// que se recalcula (`actualizarSolidoCapaz`) -- nunca al revés, este módulo no conoce three.js ni la
// escena.

export var TIPOLOGIAS = ["1d", "2d", "3d", "4d"];
var ETIQUETAS_TIPOLOGIA = { "1d": "1 Dorm.", "2d": "2 Dorm.", "3d": "3 Dorm.", "4d": "4 Dorm." };

// Preset del concurso EMVS "Berrocales 01" (RC.2.8.1 Los Berrocales, Madrid) -- cifras literales del
// encargo de Pablo, usadas como caso de prueba/preset por defecto en desarrollo. `edificabilidadMetaM2`
// es la meta del pliego (decisión 1: nunca el techo de validación, solo referencia informativa).
export var PRESET_BERROCALES_01 = {
  nombre: "Berrocales 01",
  tipologiaEdificio: "manzana_cerrada",
  plantas: 6, // PB + 5
  viviendasObjetivo: 83,
  terciarioPlantaBajaM2: 234.66,
  edificabilidadMetaM2: 6250,
  mix: { "1d": 20, "2d": 60, "3d": 20, "4d": 0 },
  // Puntos medios de los rangos del pliego: 1D 45m² (fijo); 2D 50-60m² -> 55; 3D 65-75m² -> 70.
  superficiesMediasM2: { "1d": 45, "2d": 55, "3d": 70, "4d": 90 },
  ratioConstruidaUtil: 1.45
};

function estadoPorDefecto() {
  return {
    tipologiaEdificio: "manzana_cerrada",
    plantas: null, // null = todavía sin tocar -- se autorrellena desde el Sólido Capaz (decisión 4)
    plantasTocadaPorUsuario: false,
    viviendasObjetivo: null,
    terciarioPlantaBajaM2: null,
    edificabilidadMetaM2: null, // meta informativa (preset o manual) -- nunca el techo de validación
    mix: { "1d": 20, "2d": 60, "3d": 20, "4d": 0 },
    superficiesMediasM2: { "1d": 45, "2d": 55, "3d": 70, "4d": 90 },
    ratioConstruidaUtil: 1.42
  };
}

var estado = estadoPorDefecto();

// Contexto que informa `viewer-sandbox.js` tras cada `calcularSolidoCapaz()` -- nunca se recalcula
// aquí de forma reactiva, mismo criterio que el propio Sólido Capaz ("solo al pulsar el botón").
// `null` en cualquier campo = "sólido capaz todavía no calculado para esta parcela".
var contextoSolidoCapaz = { superficieParcelaM2: null, edificabilidadMaximaM2: null, plantasMaximasSolidoCapaz: null };

var mount = null;
var panelEl = null;
var referenciaCatastralActual = null;
var els = {}; // referencias a inputs/celdas del panel, capturadas en `render()`

// Sentido inverso al de `contextoSolidoCapaz` (2026-08-17, docs/prd/2026-08-17-segmentacion-plantas-
// programa-necesidades.md, aprobado): hasta ahora el flujo Sandbox → Programa era el único que existía
// ("informa tras cada calcularSolidoCapaz(), nunca al revés", comentario de arriba). La capa roja de
// exceso del Sólido Capaz necesita el sentido contrario -- que el Sandbox se entere en cuanto cambien
// las plantas del programa (preset, edición manual, o el autorrelleno de `actualizarSolidoCapaz`) para
// poder recalcular qué niveles sobran, SIN volver a llamar a `calcularSolidoCapaz()` (el Sólido Capaz
// legal no cambia por esto, ver decisión del PRD). `null` si `viewer-sandbox.js` no pasó callback.
var onCambioPlantasCallback = null;
function notificarCambioPlantas() {
  if (typeof onCambioPlantasCallback === "function") onCambioPlantasCallback(estado.plantas);
}

// --- Persistencia (localStorage por parcela, mismo patrón que `limitesUrbanisticos` en viewer-sandbox.js) --

function claveLocalStorage() {
  return referenciaCatastralActual ? "programa_necesidades_" + referenciaCatastralActual : null;
}

function restaurarLocal() {
  var clave = claveLocalStorage();
  if (!clave) return;
  try {
    var crudo = window.localStorage.getItem(clave);
    if (!crudo) return;
    var guardado = JSON.parse(crudo);
    if (typeof guardado.tipologiaEdificio === "string") estado.tipologiaEdificio = guardado.tipologiaEdificio;
    if (typeof guardado.plantas === "number" && isFinite(guardado.plantas)) estado.plantas = guardado.plantas;
    estado.plantasTocadaPorUsuario = !!guardado.plantasTocadaPorUsuario;
    ["viviendasObjetivo", "terciarioPlantaBajaM2", "edificabilidadMetaM2", "ratioConstruidaUtil"].forEach(function (campo) {
      if (typeof guardado[campo] === "number" && isFinite(guardado[campo])) estado[campo] = guardado[campo];
    });
    if (guardado.mix) TIPOLOGIAS.forEach(function (t) {
      if (typeof guardado.mix[t] === "number" && isFinite(guardado.mix[t])) estado.mix[t] = guardado.mix[t];
    });
    if (guardado.superficiesMediasM2) TIPOLOGIAS.forEach(function (t) {
      if (typeof guardado.superficiesMediasM2[t] === "number" && isFinite(guardado.superficiesMediasM2[t])) {
        estado.superficiesMediasM2[t] = guardado.superficiesMediasM2[t];
      }
    });
  } catch (err) { /* localStorage no disponible o JSON corrupto -- se queda con los valores por defecto */ }
}

function guardarLocal() {
  var clave = claveLocalStorage();
  if (!clave) return;
  try {
    window.localStorage.setItem(clave, JSON.stringify(estado));
  } catch (err) { /* cuota agotada / modo privado -- el arquitecto sigue pudiendo trabajar, solo no se recuerda */ }
}

// --- Cálculo (puro, sin DOM -- mismo criterio que `calcularMetricasUrbanisticas` en viewer-sandbox.js) --

function calcularMetricas() {
  var sumaMixPct = TIPOLOGIAS.reduce(function (acc, t) { return acc + (estado.mix[t] || 0); }, 0);
  var mixValido = Math.abs(sumaMixPct - 100) < 0.5;

  // Superficie útil media ponderada por el mix (decisión 3: puntos medios editables por tipología),
  // usando el mix tal cual aunque no sume exactamente 100 -- el aviso de suma inválida ya se muestra
  // aparte; no bloquear el resto de los cálculos por eso.
  var promedioUtilPonderadoM2 = TIPOLOGIAS.reduce(function (acc, t) {
    return acc + (estado.mix[t] || 0) / 100 * (estado.superficiesMediasM2[t] || 0);
  }, 0);

  var construidaResidencialObjetivoM2 = (estado.viviendasObjetivo || 0) * promedioUtilPonderadoM2 * estado.ratioConstruidaUtil;
  var construidaTotalObjetivoM2 = construidaResidencialObjetivoM2 + (estado.terciarioPlantaBajaM2 || 0);

  var edificabilidadMaximaM2 = contextoSolidoCapaz.edificabilidadMaximaM2;
  var excesoEdificabilidadM2 = edificabilidadMaximaM2 != null ? construidaTotalObjetivoM2 - edificabilidadMaximaM2 : null;

  var viviendasQueCaben = null;
  if (edificabilidadMaximaM2 != null && promedioUtilPonderadoM2 > 0) {
    var disponibleResidencialM2 = Math.max(0, edificabilidadMaximaM2 - (estado.terciarioPlantaBajaM2 || 0));
    var utilDisponibleM2 = disponibleResidencialM2 / estado.ratioConstruidaUtil;
    viviendasQueCaben = Math.floor(utilDisponibleM2 / promedioUtilPonderadoM2);
  }

  var plantasMaximasSolidoCapaz = contextoSolidoCapaz.plantasMaximasSolidoCapaz;
  var plantasExcede = estado.plantas != null && plantasMaximasSolidoCapaz != null && estado.plantas > plantasMaximasSolidoCapaz;

  return {
    sumaMixPct: sumaMixPct, mixValido: mixValido,
    promedioUtilPonderadoM2: promedioUtilPonderadoM2,
    construidaResidencialObjetivoM2: construidaResidencialObjetivoM2,
    construidaTotalObjetivoM2: construidaTotalObjetivoM2,
    edificabilidadMaximaM2: edificabilidadMaximaM2,
    excesoEdificabilidadM2: excesoEdificabilidadM2,
    superaEdificabilidad: excesoEdificabilidadM2 != null && excesoEdificabilidadM2 > 0.5,
    viviendasQueCaben: viviendasQueCaben,
    plantasMaximasSolidoCapaz: plantasMaximasSolidoCapaz,
    plantasExcede: plantasExcede
  };
}

// --- DOM ------------------------------------------------------------------------------------------

function filaMix(t) {
  return (
    '<div class="sandbox-hud-programa-mix-fila" data-tipologia="' + t + '">' +
    '<span class="sandbox-hud-programa-mix-label">' + ETIQUETAS_TIPOLOGIA[t] + "</span>" +
    '<input type="number" class="sandbox-hud-programa-mix-pct" data-campo="pct" data-tipologia="' + t + '" min="0" max="100" step="1">' +
    '<span class="sandbox-hud-programa-mix-signo">%</span>' +
    '<input type="number" class="sandbox-hud-programa-mix-sup" data-campo="sup" data-tipologia="' + t + '" min="1" step="1">' +
    '<span class="sandbox-hud-programa-mix-signo">m²</span>' +
    "</div>"
  );
}

function render() {
  panelEl = document.createElement("details");
  panelEl.className = "sandbox-hud-programa";
  panelEl.id = "sandbox-hud-programa";
  panelEl.open = true; // colapsable, pero visible por defecto -- es la acción principal de esta pantalla
  panelEl.innerHTML =
    '<summary class="sandbox-hud-programa-titulo">Programa de necesidades</summary>' +
    '<div class="sandbox-hud-programa-cuerpo">' +
    '<button type="button" id="btn-programa-preset-berrocales" class="sandbox-hud-boton sandbox-hud-boton-secundario">Cargar preset Berrocales 01</button>' +
    '<div class="sandbox-hud-limite-campo"><label for="programa-tipologia">Tipología de edificio</label>' +
    '<select id="programa-tipologia">' +
    '<option value="manzana_cerrada">Manzana cerrada</option>' +
    '<option value="bloque_exento">Bloque exento</option>' +
    '<option value="unifamiliar">Unifamiliar</option>' +
    "</select></div>" +
    '<div class="sandbox-hud-limite-campo"><label for="programa-plantas">Nº de plantas</label>' +
    '<input type="number" id="programa-plantas" min="1" step="1" placeholder="—"></div>' +
    '<div class="sandbox-hud-fila excede" id="programa-plantas-aviso" hidden>' +
    '<span class="sandbox-hud-fila-label">Plantas</span><span class="sandbox-hud-fila-valor" data-programa="plantas-aviso"></span></div>' +
    '<div class="sandbox-hud-limite-campo"><label for="programa-viviendas">Viviendas objetivo</label>' +
    '<input type="number" id="programa-viviendas" min="0" step="1" placeholder="ej. 83"></div>' +
    '<div class="sandbox-hud-limite-campo"><label for="programa-terciario">Terciario PB (m²)</label>' +
    '<input type="number" id="programa-terciario" min="0" step="0.01" placeholder="ej. 234.66"></div>' +
    '<div class="sandbox-hud-limite-campo"><label for="programa-ratio">Ratio construida/útil</label>' +
    '<input type="number" id="programa-ratio" min="1" step="0.01" placeholder="1.42"></div>' +
    '<div class="sandbox-hud-programa-mix-titulo">Distribución por tipología <span id="programa-mix-suma"></span></div>' +
    '<div class="sandbox-hud-programa-mix" id="programa-mix">' +
    TIPOLOGIAS.map(filaMix).join("") +
    "</div>" +
    '<div id="sandbox-hud-programa-resultado">' +
    '<div class="sandbox-hud-fila"><span class="sandbox-hud-fila-label">Construida objetivo</span><span class="sandbox-hud-fila-valor" data-programa="construida"></span></div>' +
    '<div class="sandbox-hud-fila"><span class="sandbox-hud-fila-label">Viviendas que caben</span><span class="sandbox-hud-fila-valor" data-programa="viviendas-caben"></span></div>' +
    "</div>" +
    '<p class="sandbox-hud-programa-alerta" id="sandbox-hud-programa-alerta" hidden></p>' +
    "</div>";
  mount.appendChild(panelEl);

  els.tipologia = panelEl.querySelector("#programa-tipologia");
  els.plantas = panelEl.querySelector("#programa-plantas");
  els.plantasAviso = panelEl.querySelector("#programa-plantas-aviso");
  els.viviendas = panelEl.querySelector("#programa-viviendas");
  els.terciario = panelEl.querySelector("#programa-terciario");
  els.ratio = panelEl.querySelector("#programa-ratio");
  els.mixSuma = panelEl.querySelector("#programa-mix-suma");
  els.resultado = panelEl.querySelector("#sandbox-hud-programa-resultado");
  els.alerta = panelEl.querySelector("#sandbox-hud-programa-alerta");
  els.btnPreset = panelEl.querySelector("#btn-programa-preset-berrocales");
  els.mixPct = {}; els.mixSup = {};
  TIPOLOGIAS.forEach(function (t) {
    els.mixPct[t] = panelEl.querySelector('.sandbox-hud-programa-mix-pct[data-tipologia="' + t + '"]');
    els.mixSup[t] = panelEl.querySelector('.sandbox-hud-programa-mix-sup[data-tipologia="' + t + '"]');
  });

  wireInputs();
  rellenarCamposDesdeEstado();
  actualizarUI();
}

function rellenarCamposDesdeEstado() {
  els.tipologia.value = estado.tipologiaEdificio;
  els.plantas.value = estado.plantas != null ? estado.plantas : "";
  els.viviendas.value = estado.viviendasObjetivo != null ? estado.viviendasObjetivo : "";
  els.terciario.value = estado.terciarioPlantaBajaM2 != null ? estado.terciarioPlantaBajaM2 : "";
  els.ratio.value = estado.ratioConstruidaUtil;
  TIPOLOGIAS.forEach(function (t) {
    els.mixPct[t].value = estado.mix[t];
    els.mixSup[t].value = estado.superficiesMediasM2[t];
  });
}

function wireInputs() {
  els.tipologia.addEventListener("change", function () {
    estado.tipologiaEdificio = els.tipologia.value;
    guardarLocal();
  });
  els.plantas.addEventListener("input", function () {
    estado.plantas = els.plantas.value === "" ? null : parseInt(els.plantas.value, 10);
    estado.plantasTocadaPorUsuario = true; // decisión 4: en cuanto el usuario toca esto, deja de autorrellenarse
    guardarLocal();
    actualizarUI();
    notificarCambioPlantas();
  });
  els.viviendas.addEventListener("input", function () {
    estado.viviendasObjetivo = els.viviendas.value === "" ? null : parseInt(els.viviendas.value, 10);
    guardarLocal();
    actualizarUI();
  });
  els.terciario.addEventListener("input", function () {
    estado.terciarioPlantaBajaM2 = els.terciario.value === "" ? null : parseFloat(els.terciario.value);
    guardarLocal();
    actualizarUI();
  });
  els.ratio.addEventListener("input", function () {
    var v = parseFloat(els.ratio.value);
    estado.ratioConstruidaUtil = isFinite(v) && v > 0 ? v : estado.ratioConstruidaUtil;
    guardarLocal();
    actualizarUI();
  });
  TIPOLOGIAS.forEach(function (t) {
    els.mixPct[t].addEventListener("input", function () {
      var v = parseFloat(els.mixPct[t].value);
      estado.mix[t] = isFinite(v) ? v : 0;
      guardarLocal();
      actualizarUI();
    });
    els.mixSup[t].addEventListener("input", function () {
      var v = parseFloat(els.mixSup[t].value);
      estado.superficiesMediasM2[t] = isFinite(v) && v > 0 ? v : estado.superficiesMediasM2[t];
      guardarLocal();
      actualizarUI();
    });
  });
  els.btnPreset.addEventListener("click", cargarPresetBerrocales);
}

function cargarPresetBerrocales() {
  estado.tipologiaEdificio = PRESET_BERROCALES_01.tipologiaEdificio;
  estado.plantas = PRESET_BERROCALES_01.plantas;
  estado.plantasTocadaPorUsuario = true; // el preset es una elección explícita, no un autorrelleno silencioso
  estado.viviendasObjetivo = PRESET_BERROCALES_01.viviendasObjetivo;
  estado.terciarioPlantaBajaM2 = PRESET_BERROCALES_01.terciarioPlantaBajaM2;
  estado.edificabilidadMetaM2 = PRESET_BERROCALES_01.edificabilidadMetaM2;
  estado.ratioConstruidaUtil = PRESET_BERROCALES_01.ratioConstruidaUtil;
  TIPOLOGIAS.forEach(function (t) {
    estado.mix[t] = PRESET_BERROCALES_01.mix[t];
    estado.superficiesMediasM2[t] = PRESET_BERROCALES_01.superficiesMediasM2[t];
  });
  rellenarCamposDesdeEstado();
  guardarLocal();
  actualizarUI();
  notificarCambioPlantas();
}

function actualizarUI() {
  if (!panelEl) return;
  var m = calcularMetricas();

  els.mixSuma.textContent = "(" + m.sumaMixPct.toFixed(0) + "%)";
  els.mixSuma.classList.toggle("invalida", !m.mixValido);

  var filaConstruida = els.resultado.querySelector('[data-programa="construida"]').closest(".sandbox-hud-fila");
  var textoConstruida = m.construidaTotalObjetivoM2.toFixed(0) + " m²";
  if (m.edificabilidadMaximaM2 != null) {
    textoConstruida += " de " + m.edificabilidadMaximaM2.toFixed(0) + " m² disponibles (Sólido Capaz)";
  } else {
    textoConstruida += " (calcula el Sólido Capaz para comparar)";
  }
  els.resultado.querySelector('[data-programa="construida"]').textContent = textoConstruida;
  filaConstruida.classList.toggle("excede", m.superaEdificabilidad);

  els.resultado.querySelector('[data-programa="viviendas-caben"]').textContent =
    m.viviendasQueCaben != null ? String(m.viviendasQueCaben) : "—";

  // Alerta de exceso (encargo explícito: "Supera edificabilidad permitida en +X m²", rojo de acento
  // limpio -- mismo tono #f2a3a3 ya usado en el resto del HUD, sin un rojo nuevo).
  if (m.superaEdificabilidad) {
    els.alerta.hidden = false;
    els.alerta.textContent = "Supera edificabilidad permitida en +" + m.excesoEdificabilidadM2.toFixed(0) + " m².";
  } else {
    els.alerta.hidden = true;
  }

  // Aviso de plantas (decisión 4): solo si hay un máximo real del Sólido Capaz Y el valor introducido
  // lo supera -- nunca se recorta el campo en silencio, solo se avisa.
  if (m.plantasExcede) {
    els.plantasAviso.hidden = false;
    els.plantasAviso.classList.add("excede");
    els.plantasAviso.querySelector('[data-programa="plantas-aviso"]').textContent =
      estado.plantas + " / " + m.plantasMaximasSolidoCapaz + " máx. (Sólido Capaz)";
  } else {
    els.plantasAviso.hidden = true;
  }
}

// --- API pública (namespace import desde viewer-sandbox.js) ---------------------------------------

// `onCambioPlantas` (2026-08-17, Fase 3): callback opcional, `function(plantas)` -- ver comentario
// grande junto a `onCambioPlantasCallback` más arriba. `viewer-sandbox.js` es el único llamador real
// hoy; queda opcional para no romper ningún otro consumidor futuro que monte este panel sin él.
export function montar(mountEl, referenciaCatastral, onCambioPlantas) {
  mount = mountEl;
  referenciaCatastralActual = referenciaCatastral || null;
  estado = estadoPorDefecto();
  contextoSolidoCapaz = { superficieParcelaM2: null, edificabilidadMaximaM2: null, plantasMaximasSolidoCapaz: null };
  onCambioPlantasCallback = typeof onCambioPlantas === "function" ? onCambioPlantas : null;
  restaurarLocal();
  render();
  // Si esta parcela ya tenía plantas guardadas de una sesión anterior, el Sandbox debe saberlo desde
  // ya -- aunque el Sólido Capaz todavía no exista en este instante (`montar()` se llama ANTES de que
  // `open()` resuelva la geometría real, ver `viewer-sandbox.js`), el callback no hace nada si no hay
  // nada con qué comparar todavía; en cuanto el Sólido Capaz se calcule, vuelve a compararse solo.
  notificarCambioPlantas();
}

export function desmontar() {
  if (panelEl && panelEl.parentNode) panelEl.parentNode.removeChild(panelEl);
  panelEl = null; mount = null; els = {}; referenciaCatastralActual = null;
  estado = estadoPorDefecto();
  contextoSolidoCapaz = { superficieParcelaM2: null, edificabilidadMaximaM2: null, plantasMaximasSolidoCapaz: null };
  onCambioPlantasCallback = null;
}

// Llamado por `viewer-sandbox.js` tras CADA `calcularSolidoCapaz()` (nunca reactivo a otra cosa) --
// ver decisión 1 (edificabilidad real siempre manda) y decisión 4 (autorrelleno de plantas).
export function actualizarSolidoCapaz(contexto) {
  contextoSolidoCapaz = contexto || { superficieParcelaM2: null, edificabilidadMaximaM2: null, plantasMaximasSolidoCapaz: null };
  if (!estado.plantasTocadaPorUsuario && contextoSolidoCapaz.plantasMaximasSolidoCapaz != null) {
    estado.plantas = contextoSolidoCapaz.plantasMaximasSolidoCapaz;
    if (els.plantas) els.plantas.value = estado.plantas;
  }
  actualizarUI();
  // No hace falta `notificarCambioPlantas()` aquí en el caso de autorrelleno (arriba): el valor que
  // acaba de tomar `estado.plantas` es EXACTAMENTE `contextoSolidoCapaz.plantasMaximasSolidoCapaz` --
  // por definición no puede haber exceso frente a sí mismo. Si el usuario YA había tocado el campo a
  // mano (`plantasTocadaPorUsuario`), ese valor no cambia aquí, así que tampoco hay nada nuevo que
  // notificar -- se mantiene la comparación ya hecha por su propio `input` listener.
}

// Resalta en rojo un instante el campo "Viviendas objetivo" (2026-08-17, encargo explícito): llamado
// por `viewer-sandbox.js` cuando el arquitecto pulsa "Generar plantas con IA" con la Construida
// objetivo en 0 m² -- es este módulo quien toca su propio DOM, nunca al revés (mismo criterio de
// dirección única que el resto del archivo, ver cabecera). No hace nada si el panel no está montado
// (`els.viviendas` no existe todavía).
export function resaltarCampoViviendasObjetivo() {
  if (!els.viviendas) return;
  els.viviendas.classList.remove("sandbox-resaltar-error"); // reinicia la animación si ya estaba en marcha
  void els.viviendas.offsetWidth; // fuerza reflow para que el navegador registre el remove antes del add
  els.viviendas.classList.add("sandbox-resaltar-error");
  els.viviendas.focus();
}

// Estado + métricas expuestos para consumo externo (encargo explícito: "que el futuro motor de
// distribución por IA pueda consumer este JSON"). Forma documentada en docs/prd/2026-08-17-programa-
// de-necesidades.md §8. `null` si el panel no está montado.
export function getEstado() {
  if (!panelEl) return null;
  var m = calcularMetricas();
  return {
    referenciaCatastral: referenciaCatastralActual,
    tipologiaEdificio: estado.tipologiaEdificio,
    plantas: estado.plantas,
    viviendasObjetivo: estado.viviendasObjetivo,
    terciarioPlantaBajaM2: estado.terciarioPlantaBajaM2,
    edificabilidadMetaM2: estado.edificabilidadMetaM2,
    ratioConstruidaUtil: estado.ratioConstruidaUtil,
    mix: Object.assign({}, estado.mix),
    superficiesMediasM2: Object.assign({}, estado.superficiesMediasM2),
    metricas: m
  };
}
