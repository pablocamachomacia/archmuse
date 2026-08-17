// Modo Sandbox / Lienzo Libre (2026-08-17, a petición explícita): visor 3D PROPIO, independiente de
// `viewer-edificio.js` (que asume siempre un edificio ya generado) -- aquí el punto de partida es una
// parcela vacía (con ortofoto real si hay coordenadas del Paso 0, terreno genérico si no) sobre la
// que el arquitecto coloca volúmenes simples (cajas: largo/ancho/plantas/rotación) y, cuando quiere,
// los convierte en parámetros reales para el generador de IA de ArchMuse (`onGenerar`, ver `open()`).
//
// Deliberadamente NO intenta convertir el volumen dibujado en la geometría EXACTA del edificio
// generado -- `ai_generator.py` genera su propia distribución de habitaciones a partir de
// superficie/forma/plantas, no a partir de una malla 3D literal (eso sería una capacidad nueva y
// mucho mayor, fuera del alcance de este cambio). Lo que sí es real: las dimensiones del volumen
// dibujado se convierten en parámetros reales (`solar.superficie_m2`, `solar.forma`, `edificio.
// plantas`) que sí llegan tal cual al generador real, vía Modo Experto -- nunca una promesa de "esto
// se convierte en tu edificio pixel a pixel" que este módulo no puede cumplir.
import * as THREE from "three";
import { createViewerSession, disposeSceneResources } from "./viewer-core.js?v=20260817_atmosfera_impacto";
import { directionFromAzimuthElevation, extrudeFootprint } from "./viewer-geometry.js";
import {
  createFillLights, createSunLight, configureSunShadow, presentationRendererSettings,
  createConcreteMaterial, createPhysicalGlassMaterial, buildPBREnvironment
} from "./viewer-materials.js?v=20260817_atmosfera_impacto";
import { posicionSolar } from "./solar-posicion.js";
import {
  construirMosaicoOrtofoto, construirPlanoOrtofoto, construirEdificiosColindantes, pedirEntorno3DPorCoordenadas,
  construirContornoParcela, construirZocaloTerreno,
  metrosEsteNorteDesde, rotarAEjesLocales, pedirNormativaUrbanisticaPunto, poligonoAutointersecta,
  poligonosSeIntersectan
} from "./viewer-terreno.js?v=20260817_edificio_en_parcela_vecinos_ajustes2";
// Programa de Necesidades (2026-08-17, docs/prd/2026-08-17-programa-de-necesidades.md, aprobado):
// namespace import deliberado (no desestructurado) -- `viewer-sandbox.js` solo llama a su API pública
// (`montar`/`desmontar`/`actualizarSolidoCapaz`/`getEstado`), el módulo no conoce three.js ni la escena.
import * as ProgramaNecesidades from "./programa-necesidades.js?v=20260817_segmentacion_plantas";

(function () {
  "use strict";

  var ALTURA_PLANTA_M = 2.8; // mismo criterio que `DEFAULT_FLOOR_HEIGHT` de viewer-edificio.js

  var overlayEl = document.getElementById("viewer-sandbox");
  var mount = document.getElementById("sandbox-mount");
  var loadingEl = document.getElementById("sandbox-loading");
  var loadingTextoEl = document.getElementById("sandbox-loading-texto");
  var titleEl = document.getElementById("sandbox-title-text");
  var metaEl = document.getElementById("sandbox-meta-text");
  var etiquetaAlturaSolidoCapazEl = document.getElementById("sandbox-etiqueta-altura-solido-capaz");
  var panelEl = document.getElementById("sandbox-panel");
  var panelIndiceEl = document.getElementById("sandbox-panel-indice");
  var inputLargo = document.getElementById("sandbox-largo");
  var inputAncho = document.getElementById("sandbox-ancho");
  var inputPlantas = document.getElementById("sandbox-plantas");
  var inputRotacion = document.getElementById("sandbox-rotacion");
  var valorLargo = document.getElementById("sandbox-largo-valor");
  var valorAncho = document.getElementById("sandbox-ancho-valor");
  var valorPlantas = document.getElementById("sandbox-plantas-valor");
  var valorRotacion = document.getElementById("sandbox-rotacion-valor");
  var btnAnadir = document.getElementById("btn-sandbox-anadir");
  var btnGenerar = document.getElementById("btn-sandbox-generar");
  // "Generar 2 opciones" (2026-08-17, docs/prd/2026-08-17-optimizacion-generativa-multi-opcion.md,
  // aprobado -- 2 opciones, mix derivado del mismo total de superficie construida objetivo).
  var btnGenerarOpciones = document.getElementById("btn-sandbox-generar-opciones");
  var comparadorOverlayEl = document.getElementById("comparador-opciones");
  var comparadorContenidoEl = document.getElementById("comparador-opciones-contenido");
  var btnCerrar = document.getElementById("btn-sandbox-cerrar");
  var btnBorrarVolumen = document.getElementById("btn-sandbox-borrar-volumen");

  // Materiales base (2026-08-16, PRD de mejora visual): un volumen ya no es una caja gris
  // translúcida uniforme -- las caras "ancho" (los extremos cortos, ver `geometriaVolumen`) llevan
  // hormigón/blanco arquitectónico y las caras "largo" (la fachada principal) llevan vidrio con
  // transmisión física real. Cada volumen clona su propia instancia (`crearMaterialesVolumen`) para
  // no compartir estado entre volúmenes, igual que hacía el `MAT_VOLUMEN.clone()` anterior.
  var MAT_CONCRETO_BASE = createConcreteMaterial();
  var MAT_VIDRIO_BASE = createPhysicalGlassMaterial();
  // Opacidad subida de 0.55 a 0.85 (2026-08-16, verificado en navegador real: a 0.55 la línea se
  // confundía con el sombreado natural del propio cubo y era difícil distinguirla como borde
  // marcado). El z-fighting contra la cara del volumen se corrige aparte con `polygonOffset` en
  // `createConcreteMaterial`/`createPhysicalGlassMaterial` (`viewer-materials.js`).
  var MAT_BORDES = new THREE.LineBasicMaterial({ color: 0x1A1A18, transparent: true, opacity: 0.85 });
  var MAT_VOLUMEN_SELECCIONADO = new THREE.MeshStandardMaterial({
    color: 0xF2C94C, roughness: 0.7, metalness: 0.05, emissive: 0x332600, emissiveIntensity: 0.3
  });
  // Materiales de aviso urbanístico (2026-08-16, docs/prd/2026-08-16-conexion-3d-hallazgos-motor-
  // reglas.md): dos estados distintos con distinta gravedad -- rojo para un incumplimiento PRECISO y
  // localizado (el propio volumen invade la banda de retranqueo del polígono real de la parcela);
  // naranja para el volumen al que se ATRIBUYE (heurística: el último tocado, ver §7/§9 del PRD) un
  // exceso AGREGADO de ocupación/edificabilidad, que por naturaleza no tiene un único "culpable" real.
  var MAT_VOLUMEN_RETRANQUEO = new THREE.MeshStandardMaterial({
    color: 0xE0523F, roughness: 0.7, metalness: 0.05, emissive: 0x3A1208, emissiveIntensity: 0.35
  });
  var MAT_VOLUMEN_AGREGADO = new THREE.MeshStandardMaterial({
    color: 0xF2994A, roughness: 0.7, metalness: 0.05, emissive: 0x3A2408, emissiveIntensity: 0.3
  });
  // Pad/plinto de la parcela real (2026-08-16, arreglo crítico de persistencia): un volumen extruido
  // fino sobre el contorno real de Catastro, no solo la línea de `MAT_CONTORNO_PARCELA` -- bug
  // reportado en vivo, "el visor muestra un disco verdoso 2D plano sin contexto". Tono cálido/tierra,
  // deliberadamente distinto del verde genérico de `crearGroundNeutro()` para que se lea como "esto es
  // tu parcela real", no como el terreno de relleno de alrededor.
  // Color ajustado a `#D4C9B0` (2026-08-17, decisión explícita de Pablo -- antes `0xC9B896`); grosor
  // 0.15m sin cambios (ya era el valor pedido).
  var MAT_PAD_PARCELA = new THREE.MeshStandardMaterial({ color: 0xD4C9B0, roughness: 0.95, metalness: 0 });
  var GROSOR_PAD_PARCELA_M = 0.15;

  // Extrusión real (ExtrudeGeometry, vía `extrudeFootprint`) del contorno de la parcela -- ya no una
  // simple línea sobre un disco plano. `puntosLocal` es el mismo array `{x,z}` que ya usa
  // `construirContornoParcela`/`parcelaPoligonoLocal`, así que pad y línea quedan siempre alineados.
  function construirPadParcela(puntosLocal) {
    if (!puntosLocal || puntosLocal.length < 3) return null;
    var geometry;
    try {
      geometry = extrudeFootprint(puntosLocal, GROSOR_PAD_PARCELA_M);
    } catch (err) {
      return null; // footprint degenerado (autointersección, colineal...) -- mismo criterio que construirEdificiosColindantes
    }
    var mesh = new THREE.Mesh(geometry, MAT_PAD_PARCELA);
    mesh.receiveShadow = true;
    return mesh;
  }

  function crearMaterialesVolumen() {
    var concreto = MAT_CONCRETO_BASE.clone();
    var vidrio = MAT_VIDRIO_BASE.clone();
    // Orden de caras de `THREE.BoxGeometry`: +x,-x,+y,-y,+z,-z. Con
    // `geometriaVolumen(ancho, altura, largo)` (width=ancho, depth=largo), las caras ±x son los
    // extremos "ancho" (hormigón, como un testero ciego) y las ±z son la fachada "largo" (vidrio).
    return [concreto, concreto, concreto, concreto, vidrio, vidrio];
  }

  var session = null, renderer = null, scene = null, camera = null, controls = null, sunLight = null, raycaster = null;
  var envTexture = null;
  // Altura del terreno bajo un volumen, en función de (x, z) de mundo -- desde 2026-08-17 siempre 0
  // (terreno técnico plano en los dos casos, con o sin parcela real; ver `crearGroundNeutro`/`open()`).
  var funcionAlturaTerreno = function () { return 0; };
  var volumenes = []; // { mesh, bordes, materialesNormales, largo, ancho, plantas, rotacionDeg }
  var seleccionado = null; // índice en `volumenes`, o null
  var onGenerarCallback = null;

  // --- Urbanismo (2026-08-16, docs/prd/2026-08-16-conexion-3d-hallazgos-motor-reglas.md) ----------
  // `parcelaSuperficieM2`/`parcelaPoligonoLocal`: se rellenan en `open()`, con dos fuentes posibles --
  // (a) `opts.geometriaParcela`, ya resuelta de verdad en el Paso 0 y disponible SÍNCRONAMENTE al
  // abrir (arreglo 2026-08-16, ver comentario grande en `open()`), o (b) si esa no llegó, cuando
  // responda `body.geometria_parcela` de `/api/entorno-3d-punto` (Catastro, best-effort, puede
  // quedarse en `null` si no hay parcela real exacta en el punto). SIN ninguna de las dos no hay con
  // qué calcular ocupación/edificabilidad/retranqueos, y el HUD lo dice explícitamente (nunca un 0%
  // inventado, mismo criterio que `evaluator.py`).
  var parcelaSuperficieM2 = null;
  var parcelaPoligonoLocal = null; // [{x, z}, ...] en los mismos ejes locales que `construirContornoParcela`
  // Origen real (lat/lon) del sistema de ejes locales de esta sesión de Sandbox -- el mismo punto que
  // `open(opts)` recibe como `opts.lat`/`opts.lon` (Paso 0) y que `metrosEsteNorteDesde` usa como (0,0)
  // para proyectar `parcelaPoligonoLocal`. Sólido Capaz persistente (2026-08-17, docs/prd/2026-08-17-
  // solido-capaz-persistente-visor-edificio.md): se guarda aquí (antes solo vivía en el closure de
  // `open()`) para que `serializarSolidoCapaz()` pueda anclar el polígono que transporta a un punto real
  // -- es la MISMA referencia que `sitio_lat`/`sitio_lon` que `entrevista.js` ya manda a `/api/generar`.
  var parcelaOrigenLat = null;
  var parcelaOrigenLon = null;
  // Edificio existente vs. vecinos (2026-08-17, docs/prd/2026-08-17-edificio-existente-y-vecinos-
  // sandbox.md, aprobado): `null` = todavía no evaluado (sin parcela real, o colindantes aún no
  // llegaron); `true`/`false` = sí se evaluó -- `false` dispara el aviso "sin edificación registrada".
  var hayEdificioEnParcela = null;
  // Mismos 4 campos que el formulario de Modo Experto (`static/app.js:755-760`) -- no es un dato
  // nuevo, es el mismo dato, disponible más temprano en el flujo (el Sandbox se abre siempre ANTES de
  // Modo Experto, nunca después). Valores por defecto: `null` en los 4 (2026-08-17, docs/prd/2026-08-
  // 17-normativa-urbanistica-capas-fallback.md, Fase A, decisión explícita de Pablo -- antes 70/3 aquí
  // mismo, ya NO coincide con Modo Experto a propósito): "si no hay normativa detectada, los campos
  // aparecen vacíos" -- `restaurarLimitesUrbanisticos()`, más abajo, los rellena desde `localStorage`
  // si esta parcela ya los tenía guardados de una sesión anterior.
  var limitesUrbanisticos = {
    ocupacion_maxima_pct: null, retranqueos_m: null, edificabilidad_maxima: null, plantas_maximas: null,
    // `altura_maxima_m` (2026-08-17, docs/prd/2026-08-17-solido-capaz-sandbox.md, aprobado): campo
    // NUEVO, independiente de `plantas_maximas` -- decisión explícita de Pablo de no convertir en
    // silencio entre plantas y metros, mostrar los dos campos por separado. Solo lo usa el sólido
    // capaz (más abajo); `evaluator.py`/`calcularMetricasUrbanisticas` siguen usando `plantas_maximas`
    // tal cual, sin cambios.
    altura_maxima_m: null
  };

  // Perfil de ejemplo (2026-08-17, encargo explícito posterior -- "Fase 1: generación volumétrica
  // automática y valores por defecto"): revierte a propósito, para una parcela real activa, la
  // decisión de arriba de dejar los 4 campos vacíos -- pedido explícitamente por Pablo tras confirmar
  // el riesgo (ver AskUserQuestion de esta misma sesión: "Perfil de ejemplo, marcado como tal"). Los 5
  // números son literalmente los mismos que ya aparecían como placeholder ("ej. 70", "ej. 13"...) --
  // NUNCA normativa real de la parcela cargada, así que `limitesSonEjemplo` marca ese origen para que
  // el HUD lo distinga visualmente (mismo badge `.hecho-badge-estimated` que ya usa el resto de la app
  // para "estimado, no verificado", ver `renderizarBadgeLimitesEjemplo` más abajo). Deja de ser cierto
  // en cuanto el arquitecto edita cualquiera de los 5 campos a mano -- a partir de ahí es una elección
  // suya, se persiste igual que siempre (`guardarLimitesUrbanisticosLocal`).
  var PERFIL_EJEMPLO_URBANISTICO = {
    ocupacion_maxima_pct: 70, altura_maxima_m: 13, retranqueos_m: 3, edificabilidad_maxima: 2.0, plantas_maximas: 4
  };
  var limitesSonEjemplo = false;

  // Persistencia local de `limitesUrbanisticos` por parcela (2026-08-17, Fase A de normativa,
  // decisión explícita: `localStorage`, clave `"normativa_" + referencia_catastral`) -- solo los 4
  // campos que pide el encargo, nunca `plantas_maximas` (no forma parte de "los 4 campos" de esta
  // fase, sigue siendo un dato aparte). Nunca lanza: `localStorage` puede no estar disponible (modo
  // privado, cuota agotada) o el JSON guardado puede estar corrupto -- ninguno de los dos casos debe
  // romper la apertura del Sandbox, mismo criterio "best-effort, nunca bloqueante" del resto del
  // proyecto.
  function claveLocalStorageNormativa() {
    return referenciaCatastralActual ? "normativa_" + referenciaCatastralActual : null;
  }
  function restaurarLimitesUrbanisticosLocal() {
    var clave = claveLocalStorageNormativa();
    if (!clave) return;
    try {
      var crudo = window.localStorage.getItem(clave);
      if (!crudo) return;
      var guardado = JSON.parse(crudo);
      ["ocupacion_maxima_pct", "retranqueos_m", "edificabilidad_maxima", "altura_maxima_m"].forEach(function (campo) {
        if (typeof guardado[campo] === "number" && isFinite(guardado[campo])) limitesUrbanisticos[campo] = guardado[campo];
      });
    } catch (err) { /* localStorage no disponible o JSON corrupto -- se queda con los valores por defecto */ }
  }
  function guardarLimitesUrbanisticosLocal() {
    var clave = claveLocalStorageNormativa();
    if (!clave) return;
    try {
      window.localStorage.setItem(clave, JSON.stringify({
        ocupacion_maxima_pct: limitesUrbanisticos.ocupacion_maxima_pct,
        retranqueos_m: limitesUrbanisticos.retranqueos_m,
        edificabilidad_maxima: limitesUrbanisticos.edificabilidad_maxima,
        altura_maxima_m: limitesUrbanisticos.altura_maxima_m
      }));
    } catch (err) { /* cuota agotada / modo privado -- el arquitecto sigue pudiendo trabajar, solo no se recuerda para la próxima vez */ }
  }

  // Repinta los 5 inputs de "Límites urbanísticos" + el badge "Ejemplo" desde `limitesUrbanisticos`/
  // `limitesSonEjemplo` -- no-op seguro si el HUD todavía no existe (`construirHudUrbanismo` no se ha
  // llamado o el Sandbox ya cerró). `null` deja el campo vacío (placeholder "ej. X"), igual que antes.
  function rellenarCamposLimites() {
    if (campoLimOcupacionEl) campoLimOcupacionEl.value = limitesUrbanisticos.ocupacion_maxima_pct != null ? limitesUrbanisticos.ocupacion_maxima_pct : "";
    if (campoLimRetranqueosEl) campoLimRetranqueosEl.value = limitesUrbanisticos.retranqueos_m != null ? limitesUrbanisticos.retranqueos_m : "";
    if (campoLimEdificabilidadEl) campoLimEdificabilidadEl.value = limitesUrbanisticos.edificabilidad_maxima != null ? limitesUrbanisticos.edificabilidad_maxima : "";
    if (campoLimPlantasEl) campoLimPlantasEl.value = limitesUrbanisticos.plantas_maximas != null ? limitesUrbanisticos.plantas_maximas : "";
    if (campoLimAlturaEl) campoLimAlturaEl.value = limitesUrbanisticos.altura_maxima_m != null ? limitesUrbanisticos.altura_maxima_m : "";
    if (badgeLimitesEjemploEl) badgeLimitesEjemploEl.hidden = !limitesSonEjemplo;
  }

  function apagarBadgeEjemplo() {
    if (!limitesSonEjemplo) return;
    limitesSonEjemplo = false;
    if (badgeLimitesEjemploEl) badgeLimitesEjemploEl.hidden = true;
  }

  // Perfil de ejemplo + autocálculo del sólido capaz (2026-08-17, encargo explícito -- "Fase 1:
  // generación volumétrica automática"): se llama desde `open()`, en los dos puntos donde
  // `parcelaPoligonoLocal` queda resuelto para una parcela real (geometría ya traída del Paso 0, o la
  // respuesta de `/api/entorno-3d-punto`) -- nunca antes, `calcularSolidoCapaz()` no tiene nada que
  // extruir sin polígono. Solo aplica el perfil si NINGUNO de los 4 campos tiene ya un valor (real,
  // restaurado de `localStorage` de una visita anterior a esta misma parcela) -- nunca pisa un dato que
  // ya estuviera ahí, sea de origen real o una elección guardada del propio arquitecto.
  function aplicarPerfilEjemploYAutocalcular() {
    var sinNingunLimiteDefinido = limitesUrbanisticos.ocupacion_maxima_pct == null &&
      limitesUrbanisticos.retranqueos_m == null && limitesUrbanisticos.edificabilidad_maxima == null &&
      limitesUrbanisticos.altura_maxima_m == null;
    if (sinNingunLimiteDefinido) {
      limitesUrbanisticos.ocupacion_maxima_pct = PERFIL_EJEMPLO_URBANISTICO.ocupacion_maxima_pct;
      limitesUrbanisticos.altura_maxima_m = PERFIL_EJEMPLO_URBANISTICO.altura_maxima_m;
      limitesUrbanisticos.retranqueos_m = PERFIL_EJEMPLO_URBANISTICO.retranqueos_m;
      limitesUrbanisticos.edificabilidad_maxima = PERFIL_EJEMPLO_URBANISTICO.edificabilidad_maxima;
      limitesUrbanisticos.plantas_maximas = PERFIL_EJEMPLO_URBANISTICO.plantas_maximas;
      limitesSonEjemplo = true;
      rellenarCamposLimites();
      // Deliberadamente NO se persiste en `localStorage` aquí (`guardarLimitesUrbanisticosLocal` queda
      // sin llamar) -- es un relleno sintético, no una elección del arquitecto; se guarda recién cuando
      // él edite algo a mano (ver los `addEventListener` de `construirHudUrbanismo`).
    }
    actualizarUrbanismo();
    calcularSolidoCapaz(); // no-op seguro si aún falta algo (p.ej. sin polígono real) -- mismo guard de siempre
  }

  var ultimoVolumenTocado = null; // referencia directa al objeto de `volumenes` que causó el último cambio agregado
  var hudUrbanismoEl = null, hudMetricasEl = null, avisoSinEdificioEl = null, resumenContextoEdificiosEl = null;
  // Referencias a los 5 inputs de "Límites urbanísticos" + su badge de "ejemplo" (perfil de ejemplo,
  // más arriba) -- capturadas en `construirHudUrbanismo`, reutilizadas por `rellenarCamposLimites`
  // para poder repintarlas más tarde, cuando `parcelaPoligonoLocal` ya esté listo (los inputs se crean
  // ANTES de eso en `open()`).
  var campoLimOcupacionEl = null, campoLimAlturaEl = null, campoLimRetranqueosEl = null,
    campoLimEdificabilidadEl = null, campoLimPlantasEl = null, badgeLimitesEjemploEl = null;
  // Sólido capaz (2026-08-17, docs/prd/2026-08-17-solido-capaz-sandbox.md, aprobado): estado propio,
  // independiente de `volumenes` -- es un volumen de REFERENCIA, no algo que el arquitecto pueda
  // seleccionar/arrastrar/borrar como sus propios volúmenes. `solidoCapazMesh` se sustituye entera en
  // cada cálculo (nunca se acumulan varias); los elementos del DOM se capturan en
  // `construirHudUrbanismo` igual que el resto del HUD.
  var solidoCapazMesh = null;
  var btnSolidoCapazEl = null, estadoSolidoCapazEl = null, resultadoSolidoCapazEl = null;
  // Referencia catastral de la parcela abierta (2026-08-17, docs/prd/2026-08-17-normativa-urbanistica-
  // capas-fallback.md, Fase A): clave de persistencia de `limitesUrbanisticos` en `localStorage`.
  // `null` si Catastro no encontró parcela exacta (Paso 0 omitido o sin resultado) -- en ese caso no se
  // persiste ni se restaura nada (una referencia inventada mezclaría los límites de parcelas distintas).
  var referenciaCatastralActual = null;
  var ciudadDetectadaActual = "";

  // Normativa urbanística real -- piloto Madrid (2026-08-16, docs/prd/2026-08-16-integracion-normativa-
  // catastro-pgou.md): `normativaMadridEl` es una nota de CONTEXTO, no un campo editable -- deliberado
  // (ver el docstring de `analyzer/normativa_madrid.py`, hallazgo 5): hoy no existe una traducción
  // numérica verificada de "Grado de Condición de Edificación" a ocupación/edificabilidad/retranqueos
  // para la Norma Zonal 1.5 (la única con datos reales encontrada), así que este piloto NUNCA
  // autorrellena `limitesUrbanisticos` -- inventar esos 4 números sería exactamente el riesgo que el
  // propio PRD (§9) señala como el más grave de todo el documento. Lo que sí se muestra es la
  // referencia real (grado, norma zonal, coeficiente) para que el arquitecto la use al consultar el
  // geoportal municipal él mismo.
  var normativaMadridEl = null;

  // Navegación fluida (2026-08-16, docs/prd/2026-08-16-sandbox-navegacion-profesional-y-lindes.md):
  // tween manual de cámara, mismo patrón que ya usa `viewer-edificio.js` (`animateCameraTo`/
  // `camTween`) -- aquí no existía ninguno todavía (el Sandbox solo tenía saltos instantáneos de
  // cámara). Reutilizado por el recentrado de doble clic y los dos accesos de la barra de
  // herramientas (Isométrica/Planta).
  var camTween = null;
  function easeInOutCubic(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  function animarCamaraA(toPos, toTarget, duracion) {
    if (!camera || !controls) return;
    camTween = {
      fromPos: camera.position.clone(), toPos: toPos.clone(),
      fromTarget: controls.target.clone(), toTarget: toTarget.clone(),
      start: performance.now(), duration: duracion || 600
    };
    controls.enabled = false;
  }
  // Overlay de carga (2026-08-17, corrección en caliente -- "se queda bloqueado al 10%"): reemplaza
  // la barra de progreso con % (docs/prd/2026-08-16-presets-progreso-y-zocalo-sandbox.md), que medía
  // hitos reales del pipeline pero mantenía al usuario mirando un número parado mientras Catastro/
  // Overpass tardaban -- confuso incluso siendo honesto ("10%" durante 30s+ se lee como colgado). Un
  // spinner simple (texto fijado directamente en `open()`, ver `loadingTextoEl` más abajo) no promete
  // un avance que no puede medir con precisión, y el propio `open()` oculta el overlay en cuanto la
  // PARCELA (no los colindantes ni la ortofoto) es visible.

  function avanzarTweenCamara(now) {
    if (!camTween) return;
    var t = Math.min(1, (now - camTween.start) / camTween.duration);
    var e = easeInOutCubic(t);
    camera.position.lerpVectors(camTween.fromPos, camTween.toPos, e);
    controls.target.lerpVectors(camTween.fromTarget, camTween.toTarget, e);
    if (t >= 1) { camTween = null; controls.enabled = true; }
  }

  // --- Construcción de la escena ------------------------------------------------------------------

  // Terreno técnico único (2026-08-17, "estilo estudio BIM" a petición explícita -- "un site plan
  // técnico de arquitectura, no un objeto 3D básico"): ANTES el Sandbox tenía DOS terrenos distintos --
  // este disco plano solo con parcela real, y un relieve orgánico (`construirTerrenoOrganico`,
  // colinas/ruido) en Laboratorio sin coordenadas. El encargo pide que el caso SIN parcela real
  // también lea como plano técnico, no como paisaje -- así que ambos casos usan ya el MISMO terreno
  // (`crearGroundNeutro`, ver la llamada única en `open()` más abajo); `construirTerrenoOrganico`/
  // `alturaTerrenoOrganico` dejan de usarse aquí (siguen existiendo y siguen usándose tal cual en
  // `viewer-edificio.js`, que no ha pedido este cambio -- no se han tocado esas funciones compartidas).
  function crearGroundNeutro() {
    // Disco con perfil ligeramente troncocónico (radio superior 150 m, inferior 148.6 m, 0.35 m de
    // canto) en vez de un `CircleGeometry` plano de grosor cero -- el "bisel" pedido explícitamente: un
    // borde con volumen real que la luz del sol recorta con una línea de sombra propia, en vez de un
    // disco de papel sin espesor. Color gris técnico neutro (antes verde-oliva, leía como "césped", no
    // como una superficie CAD) y `roughness` moderado para recoger algo del entorno PBR sin brillar.
    var geo = new THREE.CylinderGeometry(150, 148.6, 0.35, 64);
    var mat = new THREE.MeshStandardMaterial({ color: 0x6E7573, roughness: 0.8, metalness: 0.05 });
    var mesh = new THREE.Mesh(geo, mat);
    mesh.position.y = -0.18; // la cara superior del cilindro queda a y≈-0.005 (mitad del canto), casi a ras
    mesh.receiveShadow = true;
    mesh.castShadow = true; // el propio canto biselado proyecta una sombra fina sobre sí mismo -- refuerzo del "bisel"
    var grupo = new THREE.Group();
    grupo.add(mesh);
    grupo.add(construirCuadriculaEscala());
    return grupo;
  }

  // Cuadrícula de escala/contexto (2026-08-17, "perfectamente visible e integrada" pedido
  // explícitamente -- versión anterior, más discreta, quedaba casi invisible). `GridHelper` ya se
  // dibuja PLANO en XZ por defecto -- NO necesita ninguna rotación (a diferencia del disco de
  // `crearGroundNeutro`, que si la necesita); se añade como HERMANA del disco (mismo grupo, no como
  // hijo suyo) precisamente para no heredar esa rotación sin querer. Separación de línea cada 10 m (30
  // divisiones sobre 300 m de lado, mismo diámetro que el disco de radio 150) -- a la escala de una
  // parcela normal (unas pocas decenas de metros) da suficientes referencias sin llenar la escena de
  // líneas. Dos tonos (2026-08-17): el eje central (X/Z por el origen local, que es siempre el centro
  // de la parcela) en un azul-gris más claro -- convención CAD de marcar los ejes principales distinto
  // del resto de la rejilla -- y el resto en un gris más suave pero ya claramente visible (opacidad
  // 0.12 → 0.32).
  function construirCuadriculaEscala() {
    var grid = new THREE.GridHelper(300, 30, 0xA9C4CE, 0x9BA8A6);
    // y = -0.002: por encima de la cara superior del disco (≈-0.005) pero por DEBAJO del plano de
    // ortofoto real que puede llegar después (2026-08-17: bajado a casi Y=0 -- encargo explícito, ver
    // `construirPlanoOrtofoto(..., 0.03)` más abajo en `open()`) -- así que en cuanto la foto de
    // satélite real carga, la cubre y la rejilla queda oculta por profundidad normal, sin tener que
    // rastrearla ni quitarla a mano cuando deja de hacer falta.
    grid.position.y = -0.002;
    grid.material.transparent = true;
    grid.material.opacity = 0.32;
    return grid;
  }

  function geometriaVolumen(largo, ancho, plantas) {
    return new THREE.BoxGeometry(ancho, Math.max(plantas, 1) * ALTURA_PLANTA_M, largo);
  }

  function crearVolumen(indice) {
    var largo = 12, ancho = 10, plantas = 3;
    var x = indice * 16, z = 0; // en fila para no apilarse exactamente
    var mesh = new THREE.Mesh(geometriaVolumen(largo, ancho, plantas), crearMaterialesVolumen());
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    var alturaTerreno = funcionAlturaTerreno(x, z);
    mesh.position.set(x, alturaTerreno + plantas * ALTURA_PLANTA_M / 2, z);
    // Bordes sutiles (encargo explícito): `EdgesGeometry` solo genera las aristas "duras" del cubo
    // (no una línea por triángulo), como hijo del mesh para heredar su posición/rotación sin
    // sincronizarlas a mano en cada cambio de slider.
    var bordes = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry), MAT_BORDES);
    mesh.add(bordes);
    scene.add(mesh);
    return {
      mesh: mesh, bordes: bordes, materialesNormales: mesh.material,
      largo: largo, ancho: ancho, plantas: plantas, rotacionDeg: 0
    };
  }

  function actualizarGeometriaVolumen(vol) {
    vol.mesh.geometry.dispose();
    vol.mesh.geometry = geometriaVolumen(vol.largo, vol.ancho, vol.plantas);
    vol.bordes.geometry.dispose();
    vol.bordes.geometry = new THREE.EdgesGeometry(vol.mesh.geometry);
    var alturaNueva = vol.plantas * ALTURA_PLANTA_M;
    var alturaTerreno = funcionAlturaTerreno(vol.mesh.position.x, vol.mesh.position.z);
    vol.mesh.position.y = alturaTerreno + alturaNueva / 2;
    vol.mesh.rotation.y = THREE.MathUtils.degToRad(vol.rotacionDeg);
  }

  function aplicarMaterialesArchVizATodos() {
    // Red de seguridad (encargo explícito, 2026-08-16): re-aplica hormigón/vidrio + bordes a TODOS
    // los volúmenes ya existentes en la escena, sin condición de si hay parcela real/ortofoto de
    // por medio. `crearVolumen` ya asigna estos materiales sin ninguna condición desde el principio
    // -- no hay, ni ha habido, ningún camino de código en este archivo que cree un volumen con el
    // material gris antiguo (`MAT_VOLUMEN`, retirado en la mejora ArchViz anterior) -- así que esto
    // es un refuerzo idempotente por si en el futuro se añadiera algún camino que sí lo hiciera, no
    // la corrección de un bug encontrado ahora mismo. Se llama al recibir datos reales de la
    // parcela (ver `open()`), que es el momento que pide este encargo.
    volumenes.forEach(function (vol, idx) {
      vol.materialesNormales.forEach(function (m) { m.dispose(); });
      vol.materialesNormales = crearMaterialesVolumen();
      if (seleccionado !== idx) vol.mesh.material = vol.materialesNormales;
      vol.bordes.geometry.dispose();
      vol.bordes.geometry = new THREE.EdgesGeometry(vol.mesh.geometry);
    });
  }

  // Radio de contexto: 80m desde el centroide (2026-08-17, decisión explícita de Pablo -- antes 220m).
  // El backend sigue consultando Overpass a 180m (`_ENTORNO_3D_RADIO_M` en app.py, compartido con
  // `viewer-edificio.js` -- deliberadamente sin tocar, ver PRD §10 "NO toca app.py"); este filtro
  // sigue siendo puramente del cliente, ahora más estricto que antes sobre ese mismo conjunto ya
  // descargado -- "radio de contexto" es cuánto se DIBUJA, no cuánto se PIDE a Overpass.
  var RADIO_UTIL_COLINDANTES_M = 80;

  // Margen para la llamada de colindantes/ortofoto cuando el Paso 0 YA trajo la geometría real de la
  // parcela: 6s (2026-08-17, decisión explícita de Pablo -- "timeout de 6 segundos para Overpass";
  // antes 8s). En ese caso la parcela ya está dibujada de forma síncrona (`geometriaInicial`, más
  // abajo en `open()`) y esta llamada de red pasa a ser puro contexto adicional (colindantes +
  // ortofoto), nunca la fuente de la parcela en sí -- no tiene sentido que el usuario espere el margen
  // completo de `TIMEOUT_ENTORNO_3D_MS` (45s en `viewer-terreno.js`) por algo que ya no bloquea nada
  // visible. Si pasan los 6s sin respuesta, simplemente no llegan colindantes/ortofoto esta vez, sin
  // ningún mensaje de error (encargo explícito) -- la parcela real que ya tenía el Paso 0 nunca se
  // vuelve a pedir ni se descarta.
  var TIMEOUT_ENTORNO_CON_GEOMETRIA_PREVIA_MS = 6000;

  // `poligonoParcela` (2026-08-17, decisión explícita de Pablo -- "colindancia = intersección de
  // polígonos O centroide a menos de 80m"): un edificio se incluye en el contexto si su footprint
  // INTERSECTA la parcela (caso medianero: puede tener su centroide bastante más lejos que el radio si
  // el edificio es grande, y aun así seguir tocando la linde) O si su centroide cae dentro del radio de
  // contexto -- el criterio de radio puro de antes (solo centroide) se queda como el caso común, la
  // intersección es la red de seguridad para el caso límite que el criterio de radio por sí solo
  // podría dejar fuera. Opcional: sin `poligonoParcela` (parcela no resuelta todavía) se comporta
  // exactamente como antes, solo por radio.
  function filtrarColindantesPorRadio(edificios, centro, radioM, poligonoParcela) {
    return (edificios || []).filter(function (edificio) {
      var vertices = edificio.vertices || [];
      if (!vertices.length) return false;
      var puntosLocales = vertices.map(function (v) {
        var m = metrosEsteNorteDesde(centro.lat, centro.lon, v[0], v[1]);
        return rotarAEjesLocales(m.este, m.norte, 0);
      });
      var sumaEste = 0, sumaNorte = 0;
      puntosLocales.forEach(function (p) { sumaEste += p.x; sumaNorte += p.z; });
      var dentroDelRadio = Math.hypot(sumaEste / puntosLocales.length, sumaNorte / puntosLocales.length) <= radioM;
      if (dentroDelRadio) return true;
      return poligonoParcela ? poligonosSeIntersectan(puntosLocales, poligonoParcela) : false;
    });
  }

  // Distingue "Overpass respondió y no hay edificios" de "Overpass falló" (2026-08-17, PRD edificio-
  // existente-y-vecinos §6 -- los dos casos NO deben verse iguales: el primero es un solar vacío real,
  // el segundo es un dato que simplemente no llegó). `_entorno_3d_para` (`app.py`) deja `edificios=[]`
  // en ambos casos, pero solo añade un aviso de texto a `body.avisos` en el segundo -- ver su docstring.
  function huboFalloOverpass(avisos) {
    return (avisos || []).some(function (texto) {
      return typeof texto === "string" && texto.indexOf("edificios colindantes") !== -1;
    });
  }

  // Resumen "X edificios en contexto · X m² construidos" (2026-08-17, encargo explícito, línea gris
  // discreta bajo el panel Urbanismo): cuenta TODOS los edificios ya filtrados por
  // `filtrarColindantesPorRadio` (en-parcela + vecinos, los que de verdad se van a dibujar) y estima su
  // superficie construida total -- huella real (`areaPoligono`, shoelace, misma función que ya usa
  // Sólido capaz) × plantas estimadas (`altura_m / ALTURA_PLANTA_M`, redondeado, mínimo 1), sumado.
  // Estimación honesta (no una medida de Catastro), mismo criterio que el resto de alturas de este
  // módulo -- nunca se presenta como un dato oficial, y por eso el texto no lleva ninguna etiqueta de
  // "aprox." de más: ya lo dice el propio panel de Urbanismo para el resto de cifras estimadas.
  function calcularResumenContextoEdificios(edificios, centro) {
    var totalM2 = 0;
    (edificios || []).forEach(function (edificio) {
      var vertices = edificio.vertices || [];
      if (vertices.length < 3) return;
      var puntosLocales = vertices.map(function (v) {
        var m = metrosEsteNorteDesde(centro.lat, centro.lon, v[0], v[1]);
        return rotarAEjesLocales(m.este, m.norte, 0);
      });
      var plantas = Math.max(1, Math.round((edificio.altura_m || ALTURA_PLANTA_M) / ALTURA_PLANTA_M));
      totalM2 += areaPoligono(puntosLocales) * plantas;
    });
    return { cantidad: (edificios || []).length, m2Construidos: totalM2 };
  }

  // Sin ningún edificio (`cantidad === 0`), la línea no aparece (encargo explícito: "si no hay
  // edificios, no mostrar nada") -- ni un texto alternativo, ni un "0 edificios".
  function actualizarResumenContextoEdificios(resumen) {
    if (!resumenContextoEdificiosEl) return;
    if (!resumen || !resumen.cantidad) { resumenContextoEdificiosEl.hidden = true; return; }
    resumenContextoEdificiosEl.hidden = false;
    var etiqueta = resumen.cantidad === 1 ? " edificio en contexto · " : " edificios en contexto · ";
    resumenContextoEdificiosEl.textContent = resumen.cantidad + etiqueta + Math.round(resumen.m2Construidos) + " m² construidos";
  }

  // --- Métricas urbanísticas reactivas (2026-08-16, docs/prd/2026-08-16-conexion-3d-hallazgos-
  // motor-reglas.md) --------------------------------------------------------------------------------
  // Réplica en cliente, a propósito ("arquitectura ligera", encargo explícito), de las MISMAS fórmulas
  // que `analyzer/evaluator.py` ya usa en `/api/generar` -- cada función de aquí lleva en su comentario
  // la referencia cruzada exacta a la función Python que replica, y `POST /api/validar-urbanismo`
  // (nuevo, reutiliza esas funciones reales) sirve para detectar pronto si algún día divergen (mismo
  // riesgo, documentado en el PRD §9, que ya causó un bug real en este proyecto entre `evaluator.
  // _is_adjacent` y `circulation._rooms_are_connected`).

  // Distancia mínima de un punto (px,pz) al segmento (ax,az)-(bx,bz) -- geometría 2D estándar, sin
  // ninguna librería: se proyecta el punto sobre la recta del segmento, se recorta la proyección al
  // propio segmento (t entre 0 y 1) y se mide la distancia al punto recortado.
  function distanciaPuntoASegmento(px, pz, ax, az, bx, bz) {
    var dx = bx - ax, dz = bz - az;
    var largoCuadrado = dx * dx + dz * dz;
    var t = largoCuadrado > 0 ? ((px - ax) * dx + (pz - az) * dz) / largoCuadrado : 0;
    t = Math.max(0, Math.min(1, t));
    var cx = ax + t * dx, cz = az + t * dz;
    return Math.hypot(px - cx, pz - cz);
  }

  // Ray casting estándar (paridad de cruces con un rayo horizontal) para saber si (px,pz) cae dentro
  // del polígono real de la parcela -- necesario porque un volumen puede quedar FUERA del solar (peor
  // que "dentro pero cerca del borde"), y en ese caso la distancia al borde más cercano no basta por
  // sí sola para distinguir los dos casos.
  function puntoDentroPoligono(px, pz, poligono) {
    var dentro = false;
    for (var i = 0, j = poligono.length - 1; i < poligono.length; j = i++) {
      var xi = poligono[i].x, zi = poligono[i].z, xj = poligono[j].x, zj = poligono[j].z;
      var cruza = (zi > pz) !== (zj > pz) && px < (xj - xi) * (pz - zi) / (zj - zi) + xi;
      if (cruza) dentro = !dentro;
    }
    return dentro;
  }

  // Distancia de (px,pz) al borde del polígono (mínimo sobre todas sus aristas) -- independiente de
  // si el punto está dentro o fuera; se combina con `puntoDentroPoligono` en `volumenInvadeRetranqueo`.
  function distanciaAlBordePoligono(px, pz, poligono) {
    var minima = Infinity;
    for (var i = 0, j = poligono.length - 1; i < poligono.length; j = i++) {
      minima = Math.min(minima, distanciaPuntoASegmento(px, pz, poligono[i].x, poligono[i].z, poligono[j].x, poligono[j].z));
    }
    return minima;
  }

  // --- Sólido capaz (2026-08-17, docs/prd/2026-08-17-solido-capaz-sandbox.md, aprobado) ------------

  function centroidePoligono(poligono) {
    var sx = 0, sz = 0;
    poligono.forEach(function (p) { sx += p.x; sz += p.z; });
    return { x: sx / poligono.length, z: sz / poligono.length };
  }

  // Área con signo (fórmula del cordón/shoelace) -- el signo por sí solo no importa aquí (no dependemos
  // de una convención de sentido horario/antihorario concreta), solo su magnitud para detectar un
  // polígono colapsado (área ~0) y, indirectamente, para poder comparar "¿el offset dejó algo
  // razonable?" en `offsetPoligonoInterior`.
  function areaPoligono(poligono) {
    var area = 0;
    for (var i = 0, j = poligono.length - 1; i < poligono.length; j = i++) {
      area += (poligono[j].x + poligono[i].x) * (poligono[i].z - poligono[j].z);
    }
    return Math.abs(area) / 2;
  }

  // Intersección de dos RECTAS infinitas (no segmentos) -- `null` si son paralelas (o casi, con
  // tolerancia numérica). Cada `linea` es `{ax, az, bx, bz}` (dos puntos que la definen).
  function interseccionDeRectas(l1, l2) {
    var x1 = l1.ax, z1 = l1.az, x2 = l1.bx, z2 = l1.bz;
    var x3 = l2.ax, z3 = l2.az, x4 = l2.bx, z4 = l2.bz;
    var denom = (x1 - x2) * (z3 - z4) - (z1 - z2) * (x3 - x4);
    if (Math.abs(denom) < 1e-9) return null;
    var t = ((x1 - x3) * (z3 - z4) - (z1 - z3) * (x3 - x4)) / denom;
    return { x: x1 + t * (x2 - x1), z: z1 + t * (z2 - z1) };
  }

  // Offset hacia dentro (erosión) de un polígono real por una distancia uniforme -- implementación
  // ACOTADA a propósito (PRD §9/§14): por cada arista se calcula su línea desplazada hacia el
  // CENTROIDE del polígono (no se asume un sentido de giro concreto, funciona con el polígono tal cual
  // llega de Catastro) y el nuevo vértice es la intersección de las dos líneas desplazadas adyacentes.
  // Es el método simple, no una erosión general robusta (straight skeleton) -- funciona bien en
  // parcelas convexas o casi-convexas (la mayoría), y puede fallar (autointersección, líneas
  // paralelas) en parcelas muy cóncavas. NUNCA se usa un resultado sin validar -- ver `calcularSolidoCapaz`,
  // que aquí solo construye el candidato, la validación vive en el llamador (mismo criterio que
  // `construirEdificiosColindantes`: separar "calcular" de "decidir si el resultado es válido").
  function offsetPoligonoInterior(poligono, distancia) {
    if (!poligono || poligono.length < 3 || !(distancia > 0)) return poligono;
    var centro = centroidePoligono(poligono);
    var n = poligono.length;
    var lineas = [];
    for (var i = 0; i < n; i++) {
      var a = poligono[i], b = poligono[(i + 1) % n];
      var dx = b.x - a.x, dz = b.z - a.z;
      var largo = Math.hypot(dx, dz);
      if (largo < 1e-9) return null; // arista de longitud ~0 -- vértices duplicados, no se puede desplazar
      var nx = -dz / largo, nz = dx / largo; // perpendicular candidata
      var mx = (a.x + b.x) / 2, mz = (a.z + b.z) / 2;
      // ¿esta normal apunta hacia el centroide? si no, se invierte -- así el método no depende de si
      // el anillo viene en sentido horario o antihorario.
      if ((centro.x - mx) * nx + (centro.z - mz) * nz < 0) { nx = -nx; nz = -nz; }
      lineas.push({ ax: a.x + nx * distancia, az: a.z + nz * distancia, bx: b.x + nx * distancia, bz: b.z + nz * distancia });
    }
    var resultado = [];
    for (var k = 0; k < n; k++) {
      var punto = interseccionDeRectas(lineas[(k - 1 + n) % n], lineas[k]);
      if (!punto) return null; // aristas consecutivas paralelas tras el desplazamiento -- caso degenerado
      resultado.push(punto);
    }
    return resultado;
  }

  // Material del sólido capaz -- volumen de REFERENCIA (encargo explícito): semitransparente para no
  // competir con los volúmenes reales que el arquitecto coloque, nunca los sustituye ni los oculta.
  var MAT_SOLIDO_CAPAZ = new THREE.MeshStandardMaterial({
    color: 0x6B8CAE, transparent: true, opacity: 0.3, roughness: 1, metalness: 0, depthWrite: false
  });
  var MAT_BORDE_SOLIDO_CAPAZ = new THREE.LineBasicMaterial({ color: 0xFFFFFF, transparent: true, opacity: 0.6 });
  // Forjado por planta (2026-08-17, Fase 3, docs/prd/2026-08-17-segmentacion-plantas-programa-
  // necesidades.md, aprobado): losa delgada y más opaca que la fachada de cristal -- es lo que hace
  // que el volumen se LEA como plantas apiladas de verdad (forjado + fachada), no un bloque único con
  // líneas finas encima (eso era la Fase 2 anterior -- `construirLineasPlantas`/
  // `MAT_LINEAS_PLANTAS_SOLIDO_CAPAZ` quedan retiradas aquí, sustituidas por geometría real segmentada).
  var MAT_FORJADO_SOLIDO_CAPAZ = new THREE.MeshStandardMaterial({
    color: 0xC9CCCF, transparent: true, opacity: 0.85, roughness: 0.9, metalness: 0, depthWrite: false
  });
  var ESPESOR_FORJADO_M = 0.15;
  // Niveles que el Programa de Necesidades pide por encima del Sólido Capaz legal (Fase 3): mismo rojo
  // de aviso que ya usa el resto del HUD (`#f2a3a3`, `.sandbox-hud-fila.excede`/`.sandbox-hud-programa-
  // alerta` en style.css) -- nunca un rojo nuevo. Esta capa NUNCA sustituye ni redimensiona
  // `MAT_SOLIDO_CAPAZ`/`MAT_FORJADO_SOLIDO_CAPAZ` -- es un añadido aparte, gestionado por
  // `actualizarCapaExcesoPrograma()` (más abajo), independiente de cuándo se recalcula el Sólido Capaz
  // legal (decisión explícita del PRD: el programa nunca redimensiona el envolvente legal).
  var MAT_EXCESO_SOLIDO_CAPAZ = new THREE.MeshStandardMaterial({
    color: 0xF2A3A3, transparent: true, opacity: 0.35, roughness: 1, metalness: 0, depthWrite: false
  });
  var MAT_BORDE_EXCESO_SOLIDO_CAPAZ = new THREE.LineBasicMaterial({ color: 0xF2A3A3, transparent: true, opacity: 0.8 });
  // Separación vertical fija en la vista "Plantas Explosionadas" (Fase 3) -- transición simple
  // (interpolación de posición, sin física), decisión explícita del PRD §11/§14 para no arriesgar FPS
  // ni sobredimensionar el alcance.
  var SEPARACION_EXPLOSIONADA_M = 1.4;
  var vistaExplosionadaActiva = false;

  // Una "planta" del Sólido Capaz = forjado (losa opaca, `ESPESOR_FORJADO_M` de canto) + fachada de
  // cristal (el resto de la altura de planta), ambas con el mismo footprint (`poligono`, el
  // `poligonoFinal` ya resuelto por `calcularSolidoCapaz`, con o sin retranqueo). Nacen como hijas de
  // un único `THREE.Group` por planta para poder moverse juntas en la vista explosionada
  // (`aplicarModoVistaSolidoCapaz`, más abajo). `conForjado=false` para la porción de sobrante final
  // (cuando `alturaMax` no es múltiplo exacto de `ALTURA_PLANTA_M`) si además queda demasiado fina
  // para un forjado completo -- ver guarda `alturaPiso > ESPESOR_FORJADO_M + 0.05` más abajo, un
  // forjado ahí leería como una planta más que no existe de verdad.
  function construirPisoSolidoCapaz(poligono, alturaPiso, conForjado) {
    var grupo = new THREE.Group();
    var geometrias = [];
    var yFachada = 0;
    if (conForjado && alturaPiso > ESPESOR_FORJADO_M + 0.05) {
      var geoForjado = extrudeFootprint(poligono, ESPESOR_FORJADO_M);
      var forjado = new THREE.Mesh(geoForjado, MAT_FORJADO_SOLIDO_CAPAZ);
      forjado.castShadow = true; forjado.receiveShadow = true;
      grupo.add(forjado);
      geometrias.push(geoForjado);
      yFachada = ESPESOR_FORJADO_M;
    }
    var geoFachada = extrudeFootprint(poligono, alturaPiso - yFachada);
    var fachada = new THREE.Mesh(geoFachada, MAT_SOLIDO_CAPAZ);
    fachada.position.y = yFachada;
    fachada.castShadow = true; fachada.receiveShadow = true;
    fachada.renderOrder = 10; // por delante del pad/contorno/ortofoto en el orden de dibujado de transparencias
    var bordesGeo = new THREE.EdgesGeometry(geoFachada);
    fachada.add(new THREE.LineSegments(bordesGeo, MAT_BORDE_SOLIDO_CAPAZ));
    grupo.add(fachada);
    geometrias.push(geoFachada, bordesGeo);
    return { grupo: grupo, geometrias: geometrias };
  }

  // Todas las plantas legales del Sólido Capaz, desde planta baja hasta `alturaMax` -- misma altura
  // total que la extrusión única de antes (nunca se recorta a un múltiplo exacto de `ALTURA_PLANTA_M`,
  // para que la vista "Volumen Total" se siga viendo igual que antes de esta pieza), solo que ahora
  // troceada en piezas reales por planta en vez de una sola malla.
  function construirPlantasLegales(poligono, alturaMax) {
    var pisos = [], geometrias = [], y = 0;
    while (y < alturaMax - 0.01) {
      var alturaPiso = Math.min(ALTURA_PLANTA_M, alturaMax - y);
      var piso = construirPisoSolidoCapaz(poligono, alturaPiso, true);
      piso.grupo.position.y = y;
      piso.grupo.userData.floorBaseY = y;
      pisos.push(piso.grupo);
      geometrias = geometrias.concat(piso.geometrias);
      y += alturaPiso;
    }
    return { pisos: pisos, geometrias: geometrias };
  }

  // Vista "Plantas Explosionadas" (Fase 3, encargo explícito): separa verticalmente cada planta ya
  // construida un hueco fijo -- reposiciona grupos existentes, nunca reconstruye geometría, así que
  // alternar el modo es barato. Incluye la capa roja de exceso del programa (`aplicarModoVistaExceso`)
  // para que el despiece se vea continuo -- si no, "Plantas Explosionadas" separaría las plantas
  // legales pero dejaría las rojas pegadas al bloque compacto.
  function aplicarModoVistaSolidoCapaz() {
    if (!solidoCapazMesh || !solidoCapazMesh.userData.pisos) return;
    solidoCapazMesh.userData.pisos.forEach(function (piso) {
      var extra = vistaExplosionadaActiva ? (piso.userData.floorBaseY / ALTURA_PLANTA_M) * SEPARACION_EXPLOSIONADA_M : 0;
      piso.position.y = piso.userData.floorBaseY + extra;
    });
    aplicarModoVistaExceso();
  }

  function aplicarModoVistaExceso() {
    if (!solidoCapazMesh || !solidoCapazMesh.userData.pisosExceso) return;
    var plantasLegales = solidoCapazMesh.userData.plantasLegales;
    solidoCapazMesh.userData.pisosExceso.forEach(function (piso, indice) {
      var extra = vistaExplosionadaActiva ? (plantasLegales + indice) * SEPARACION_EXPLOSIONADA_M : 0;
      piso.position.y = piso.userData.floorBaseY + extra;
    });
  }

  function alternarVistaExplosionada() {
    vistaExplosionadaActiva = !vistaExplosionadaActiva;
    aplicarModoVistaSolidoCapaz();
  }

  // Capa roja de niveles que el Programa de Necesidades pide por encima del Sólido Capaz legal (Fase
  // 3, encargo explícito -- "sin alterar el volumen legal base"). Llamada (a) al final de
  // `calcularSolidoCapaz()`, con las plantas YA guardadas del programa; (b) desde el callback que
  // `programa-necesidades.js` dispara en cuanto cambian sus plantas (preset, edición manual) -- ver
  // `ProgramaNecesidades.montar(..., actualizarCapaExcesoPrograma)` en `open()`. En NINGÚN caso relanza
  // `calcularSolidoCapaz()`: el Sólido Capaz legal es fijo, esto solo añade o quita una capa encima.
  function actualizarCapaExcesoPrograma(plantasPrograma) {
    if (!solidoCapazMesh) return; // sin Sólido Capaz legal calculado, no hay contra qué comparar -- nunca se inventa un exceso
    if (solidoCapazMesh.userData.grupoExceso) {
      solidoCapazMesh.remove(solidoCapazMesh.userData.grupoExceso);
      solidoCapazMesh.userData.geometriasExceso.forEach(function (g) { g.dispose(); });
      solidoCapazMesh.userData.grupoExceso = null;
      solidoCapazMesh.userData.geometriasExceso = [];
      solidoCapazMesh.userData.pisosExceso = [];
    }
    var plantasLegales = solidoCapazMesh.userData.plantasLegales;
    if (plantasPrograma == null || !(plantasPrograma > plantasLegales)) return; // sin exceso, nada que dibujar

    var poligono = solidoCapazMesh.userData.poligonoFinal;
    var grupoExceso = new THREE.Group();
    var geometrias = [], pisosExceso = [];
    for (var i = plantasLegales; i < plantasPrograma; i++) {
      var geo = extrudeFootprint(poligono, ALTURA_PLANTA_M);
      var mesh = new THREE.Mesh(geo, MAT_EXCESO_SOLIDO_CAPAZ);
      mesh.castShadow = true; mesh.receiveShadow = true;
      mesh.renderOrder = 10;
      var bordesGeo = new THREE.EdgesGeometry(geo);
      mesh.add(new THREE.LineSegments(bordesGeo, MAT_BORDE_EXCESO_SOLIDO_CAPAZ));
      var pisoGrupo = new THREE.Group();
      pisoGrupo.add(mesh);
      pisoGrupo.position.y = plantasLegales * ALTURA_PLANTA_M + (i - plantasLegales) * ALTURA_PLANTA_M;
      pisoGrupo.userData.floorBaseY = pisoGrupo.position.y;
      grupoExceso.add(pisoGrupo);
      pisosExceso.push(pisoGrupo);
      geometrias.push(geo, bordesGeo);
    }
    solidoCapazMesh.add(grupoExceso);
    solidoCapazMesh.userData.grupoExceso = grupoExceso;
    solidoCapazMesh.userData.geometriasExceso = geometrias;
    solidoCapazMesh.userData.pisosExceso = pisosExceso;
    aplicarModoVistaExceso();
  }

  // Las 4 esquinas del footprint de un volumen, YA rotadas y en coordenadas de mundo (x,z) -- réplica
  // de la misma geometría que usa `geometriaVolumen`/`BoxGeometry(ancho, altura, largo)`: semi-ancho
  // en el eje local X, semi-largo en el eje local Z, giradas por `vol.rotacionDeg` alrededor de Y.
  function esquinasVolumen(vol) {
    var hx = vol.ancho / 2, hz = vol.largo / 2;
    var rad = THREE.MathUtils.degToRad(vol.rotacionDeg);
    var cos = Math.cos(rad), sin = Math.sin(rad);
    var cx = vol.mesh.position.x, cz = vol.mesh.position.z;
    return [[hx, hz], [hx, -hz], [-hx, -hz], [-hx, hz]].map(function (p) {
      var lx = p[0], lz = p[1];
      return { x: cx + lx * cos + lz * sin, z: cz - lx * sin + lz * cos };
    });
  }

  // `true` si CUALQUIER esquina del volumen cae fuera del polígono real de la parcela, o dentro pero
  // a menos de `retranqueos_m` de su borde -- `null`/`false` (no evaluable) si falta el polígono real
  // o no hay retranqueo informado, mismo criterio de "no evaluable, no inventado" que
  // `evaluator.evaluate_retranqueos` (que aquí se MEJORA, no se reutiliza: usa el polígono real de
  // Catastro en vez del proxy rectangular ancho/largo del solar declarado -- ver PRD §9).
  function volumenInvadeRetranqueo(vol) {
    if (!parcelaPoligonoLocal || parcelaPoligonoLocal.length < 3) return false;
    var retranqueo = limitesUrbanisticos.retranqueos_m;
    if (retranqueo == null) return false;
    return esquinasVolumen(vol).some(function (esq) {
      if (!puntoDentroPoligono(esq.x, esq.z, parcelaPoligonoLocal)) return true;
      return distanciaAlBordePoligono(esq.x, esq.z, parcelaPoligonoLocal) < retranqueo;
    });
  }

  // Réplica de `evaluate_solar_occupation`/`evaluate_buildability`/`evaluate_max_floors`
  // (`analyzer/evaluator.py`): ocupación/edificabilidad se calculan como SUMA de huellas
  // (`largo * ancho` por volumen), no como unión geométrica real -- aproximación explícita (PRD §6/§9)
  // que sobreestima si hay volúmenes solapados; el mismo criterio se replica en
  // `POST /api/validar-urbanismo` para que "reconciliar" compare lo mismo en los dos sitios.
  function calcularMetricasUrbanisticas() {
    var superficiePlantaBaja = 0, superficieConstruida = 0, plantasMax = 0;
    volumenes.forEach(function (vol) {
      var huella = vol.largo * vol.ancho;
      superficiePlantaBaja += huella;
      superficieConstruida += huella * vol.plantas;
      plantasMax = Math.max(plantasMax, vol.plantas);
    });

    function ocupacion() {
      // Réplica de `evaluate_solar_occupation`.
      if (!parcelaSuperficieM2) return null;
      var maximo = limitesUrbanisticos.ocupacion_maxima_pct;
      if (maximo == null) return null;
      var pct = superficiePlantaBaja / parcelaSuperficieM2 * 100;
      return { valor: pct, maximo: maximo, passed: pct <= maximo };
    }
    function edificabilidad() {
      // Réplica de `evaluate_buildability`.
      if (!parcelaSuperficieM2) return null;
      var maximo = limitesUrbanisticos.edificabilidad_maxima;
      if (maximo == null) return null;
      var real = superficieConstruida / parcelaSuperficieM2;
      return { valor: real, maximo: maximo, passed: real <= maximo };
    }
    function plantas() {
      // Réplica de `evaluate_max_floors`.
      var maximo = limitesUrbanisticos.plantas_maximas;
      if (maximo == null) return null;
      return { valor: plantasMax, maximo: maximo, passed: plantasMax <= maximo };
    }

    return { ocupacion: ocupacion(), edificabilidad: edificabilidad(), plantas: plantas() };
  }

  function formatearFilaHud(id, etiqueta, resultado, formatoValor, formatoMaximo, unidad) {
    var el = hudMetricasEl && hudMetricasEl.querySelector('[data-hud-fila="' + id + '"]');
    if (!el) return;
    if (!resultado) {
      el.hidden = true;
      return;
    }
    el.hidden = false;
    el.classList.toggle("excede", !resultado.passed);
    var valorEl = el.querySelector(".sandbox-hud-fila-valor");
    if (valorEl) {
      valorEl.textContent = formatoValor(resultado.valor) + " / " + formatoMaximo(resultado.maximo) + unidad;
    }
  }

  // Orquestador: recalcula métricas + retranqueos, actualiza el HUD y los materiales de los
  // volúmenes -- se llama tras CUALQUIER cambio que pueda afectar al resultado (añadir/borrar/escalar/
  // rotar un volumen, o editar un límite urbanístico), siempre en cliente, nunca detrás de una
  // llamada de red (esa solo existe como reconciliación puntual, ver `reconciliarConBackend`).
  function actualizarUrbanismo() {
    if (!hudUrbanismoEl) return;
    actualizarBotonSolidoCapaz();
    var metricas = calcularMetricasUrbanisticas();

    if (!parcelaSuperficieM2) {
      if (hudMetricasEl) hudMetricasEl.hidden = true;
      var avisoEl = hudUrbanismoEl.querySelector(".sandbox-hud-aviso");
      if (avisoEl) avisoEl.hidden = false;
    } else {
      if (hudMetricasEl) hudMetricasEl.hidden = false;
      var avisoEl2 = hudUrbanismoEl.querySelector(".sandbox-hud-aviso");
      if (avisoEl2) avisoEl2.hidden = true;
      formatearFilaHud("ocupacion", "Ocupación", metricas.ocupacion,
        function (v) { return v.toFixed(0) + "%"; }, function (v) { return v.toFixed(0) + "%"; }, "");
      formatearFilaHud("edificabilidad", "Edificabilidad", metricas.edificabilidad,
        function (v) { return v.toFixed(2); }, function (v) { return v.toFixed(2); }, " m²/m²");
      formatearFilaHud("plantas", "Plantas", metricas.plantas,
        function (v) { return String(v); }, function (v) { return String(v); }, "");
    }

    // Aviso "sin edificación registrada" (2026-08-17, PRD aprobado): solo tiene sentido si SÍ hay
    // parcela real (si no, ya se ve el otro aviso de arriba) y la clasificación de colindantes ya
    // corrió y no encontró ningún edificio dentro -- `hayEdificioEnParcela === false` explícito, no
    // solo "falsy", para no mostrarlo mientras sigue en `null` (todavía no evaluado, o Overpass falló).
    if (avisoSinEdificioEl) {
      avisoSinEdificioEl.hidden = !(parcelaSuperficieM2 && hayEdificioEnParcela === false);
    }

    // Exceso AGREGADO (ocupación o edificabilidad): no hay un único volumen "culpable" -- se atribuye
    // al último tocado (heurística explícita, PRD §7/§9), nunca a todos a la vez.
    var excedeAgregado = (metricas.ocupacion && !metricas.ocupacion.passed) ||
      (metricas.edificabilidad && !metricas.edificabilidad.passed);

    // Prioridad de materiales, de mayor a menor: seleccionado (amarillo) > retranqueo (rojo, PRECISO
    // y por volumen) > agregado atribuido (naranja, heurística) > normal.
    volumenes.forEach(function (vol, idx) {
      if (seleccionado === idx) { vol.mesh.material = MAT_VOLUMEN_SELECCIONADO; return; }
      if (volumenInvadeRetranqueo(vol)) { vol.mesh.material = MAT_VOLUMEN_RETRANQUEO; return; }
      if (excedeAgregado && vol === ultimoVolumenTocado) { vol.mesh.material = MAT_VOLUMEN_AGREGADO; return; }
      vol.mesh.material = vol.materialesNormales;
    });
  }

  // Qué falta para poder pulsar "Calcular sólido capaz" -- los 3 datos son necesarios juntos (PRD §6):
  // ocupación/edificabilidad son solo informativas para este cálculo (decisión explícita de Pablo), no
  // hace falta esperarlas.
  function datosFaltantesSolidoCapaz() {
    var faltan = [];
    if (!parcelaPoligonoLocal) faltan.push("parcela real");
    if (limitesUrbanisticos.retranqueos_m == null) faltan.push("retranqueos");
    if (!(limitesUrbanisticos.altura_maxima_m > 0)) faltan.push("altura máxima");
    return faltan;
  }

  function actualizarBotonSolidoCapaz() {
    if (!btnSolidoCapazEl) return;
    var faltan = datosFaltantesSolidoCapaz();
    btnSolidoCapazEl.disabled = faltan.length > 0;
    // Mientras no haya ya un sólido dibujado, el aviso de "qué falta" es el único contenido de
    // `estadoSolidoCapazEl` -- en cuanto se calcula un sólido (`calcularSolidoCapaz`), ese aviso pasa a
    // reflejar el RESULTADO del cálculo (p. ej. "retranqueo no aplicable"), y editar otro límite sin
    // volver a pulsar el botón no lo pisa (PRD §6: recálculo solo al pulsar, nunca reactivo).
    if (!solidoCapazMesh && estadoSolidoCapazEl) {
      // El aviso de "falta esto" nunca es el aviso de bloqueo de "Generar plantas con IA" (rojo,
      // `mostrarBloqueoGenerar`) -- si quedó puesto de un intento anterior, se limpia aquí.
      estadoSolidoCapazEl.classList.remove("es-error");
      estadoSolidoCapazEl.hidden = faltan.length === 0;
      if (faltan.length > 0) {
        estadoSolidoCapazEl.textContent = "Para calcular el sólido capaz hace falta: " + faltan.join(", ") + ".";
      }
    }
  }

  // Reposiciona la etiqueta de altura sobre la pantalla cada fotograma (Fase 2, encargo explícito) --
  // no hay `CSS2DRenderer` en este visor, así que es proyección manual: `Vector3.project(camera)` da
  // coordenadas NDC (-1..1), se convierten a píxeles sobre `#sandbox-mount`. Oculta sin sólido capaz
  // calculado, o si el punto anclado queda detrás de la cámara (`z > 1` tras la división de
  // perspectiva) -- nunca una etiqueta pegada sin sentido en una esquina.
  function actualizarEtiquetaAlturaSolidoCapaz() {
    if (!etiquetaAlturaSolidoCapazEl) return;
    var ancla = solidoCapazMesh && solidoCapazMesh.userData.etiquetaAnclaLocal;
    if (!ancla || !camera || !mount) { etiquetaAlturaSolidoCapazEl.hidden = true; return; }
    var proyectado = ancla.clone().project(camera);
    if (proyectado.z > 1) { etiquetaAlturaSolidoCapazEl.hidden = true; return; }
    var ancho = mount.clientWidth, alto = mount.clientHeight;
    etiquetaAlturaSolidoCapazEl.style.left = ((proyectado.x * 0.5 + 0.5) * ancho) + "px";
    etiquetaAlturaSolidoCapazEl.style.top = ((1 - (proyectado.y * 0.5 + 0.5)) * alto) + "px";
    etiquetaAlturaSolidoCapazEl.textContent = "H: " + solidoCapazMesh.userData.alturaTotalM.toFixed(1) + " m";
    etiquetaAlturaSolidoCapazEl.hidden = false;
  }

  // Cálculo + dibujado del sólido capaz (2026-08-17, docs/prd/2026-08-17-solido-capaz-sandbox.md,
  // aprobado con las siguientes decisiones explícitas de Pablo, no las propuestas originales del PRD):
  // - La ocupación máxima es SOLO una métrica informativa del panel -- nunca recorta esta planta. El
  //   único recorte geométrico es el retranqueo.
  // - Si el offset autointersecta (parcela cóncava), se usa la parcela ORIGINAL sin offset y se avisa
  //   con el texto exacto "Retranqueo no aplicable en zonas cóncavas" -- nunca ninguna geometría rota,
  //   nunca "no se dibuja nada" (eso era la propuesta original del PRD, sustituida por esta decisión).
  function calcularSolidoCapaz() {
    if (!scene || datosFaltantesSolidoCapaz().length > 0) return;
    // Cualquier cálculo nuevo (éxito o fallo) deja atrás el aviso rojo de "Generar plantas con IA" de
    // un intento anterior, si lo había -- el arquitecto acaba de pulsar el botón que ese aviso le pedía.
    if (estadoSolidoCapazEl) estadoSolidoCapazEl.classList.remove("es-error");
    var retranqueo = limitesUrbanisticos.retranqueos_m;
    var alturaMax = limitesUrbanisticos.altura_maxima_m;

    // Nunca se acumulan varios sólidos -- cada cálculo sustituye entero al anterior (encargo: "se
    // superpone sobre la parcela", un sólido de referencia a la vez). `solidoCapazMesh` es un
    // `THREE.Group` desde la Fase 3 (antes una única `THREE.Mesh`) -- quitarlo de la escena retira
    // TODAS sus plantas (legales + capa de exceso) de un solo golpe, pero sus geometrías individuales
    // no se liberan solas (`geometriasParaDisponer`, reunidas en un único array al construirlo).
    if (solidoCapazMesh) {
      scene.remove(solidoCapazMesh);
      solidoCapazMesh.userData.geometriasParaDisponer.forEach(function (g) { g.dispose(); });
      if (solidoCapazMesh.userData.geometriasExceso) {
        solidoCapazMesh.userData.geometriasExceso.forEach(function (g) { g.dispose(); });
      }
      solidoCapazMesh = null;
    }

    var candidato = offsetPoligonoInterior(parcelaPoligonoLocal, retranqueo);
    var poligonoFinal = parcelaPoligonoLocal, retranqueoAplicable = false;
    if (candidato && !poligonoAutointersecta(candidato) && areaPoligono(candidato) > 1) {
      poligonoFinal = candidato;
      retranqueoAplicable = true;
    }

    var plantas;
    try {
      plantas = construirPlantasLegales(poligonoFinal, alturaMax);
    } catch (err) {
      // Ni siquiera la parcela original (que ya se usa sin problemas en `construirPadParcela`) debería
      // llegar aquí -- red de seguridad, no un camino esperado.
      if (estadoSolidoCapazEl) { estadoSolidoCapazEl.hidden = false; estadoSolidoCapazEl.textContent = "No se ha podido calcular el sólido capaz para esta parcela."; }
      if (resultadoSolidoCapazEl) resultadoSolidoCapazEl.hidden = true;
      actualizarBotonGenerar(); // `solidoCapazMesh` sigue en `null` (ver arriba) -- puede volver a deshabilitar el botón
      return;
    }

    // `solidoCapazMesh` es un `THREE.Group` desde la Fase 3 (segmentación en plantas) -- contiene una
    // sub-`Group` por planta legal (`plantas.pisos`, forjado + fachada cada una, ver
    // `construirPlantasLegales`), más la capa roja de exceso del programa cuando aplica
    // (`actualizarCapaExcesoPrograma`, añadida como hija aparte). El resto del visor (etiqueta de
    // altura, disposal, `scene.add`/`remove`) trata este grupo igual que trataba antes la malla única.
    var grupo = new THREE.Group();
    plantas.pisos.forEach(function (piso) { grupo.add(piso); });
    grupo.userData.pisos = plantas.pisos;
    grupo.userData.geometriasParaDisponer = plantas.geometrias;
    grupo.userData.poligonoFinal = poligonoFinal;
    // Cota de altura total (Fase 2, encargo explícito): DOM 2D, se ancla por separado en cada
    // fotograma (`actualizarEtiquetaAlturaSolidoCapaz`, en el bucle de render de `open()`) porque no
    // hay ningún `CSS2DRenderer` en este visor todavía.
    var centroide = centroidePoligono(poligonoFinal);
    grupo.userData.alturaTotalM = alturaMax;
    grupo.userData.etiquetaAnclaLocal = new THREE.Vector3(centroide.x, alturaMax, centroide.z);
    scene.add(grupo);
    solidoCapazMesh = grupo;

    // Métricas del SÓLIDO calculado (no de los volúmenes que el arquitecto haya colocado a mano --
    // esos ya tienen su propia fila en el HUD, `calcularMetricasUrbanisticas`). `plantasEstimadas`:
    // división entera por `ALTURA_PLANTA_M` (2.8m, misma constante que el resto del Sandbox) -- una
    // planta parcial no cuenta como planta completa. Sigue siendo el MISMO cálculo numérico de
    // siempre (independiente de cuántas piezas de geometría se hayan construido arriba, que puede
    // incluir una porción sobrante final que no cuenta como planta completa -- ver
    // `construirPlantasLegales`).
    var superficieOcupada = areaPoligono(poligonoFinal);
    var plantasEstimadas = Math.max(1, Math.floor(alturaMax / ALTURA_PLANTA_M));
    var edificabilidadUsada = superficieOcupada * plantasEstimadas;
    grupo.userData.plantasLegales = plantasEstimadas; // usado por la capa de exceso (Fase 3) para saber a partir de qué planta pintar en rojo
    aplicarModoVistaSolidoCapaz(); // nace ya en el modo de vista activo (Volumen Total / Plantas Explosionadas), sin parpadeo

    if (resultadoSolidoCapazEl) {
      resultadoSolidoCapazEl.hidden = false;
      var elSuperficie = resultadoSolidoCapazEl.querySelector('[data-solido-capaz="superficie"]');
      var elEdificabilidad = resultadoSolidoCapazEl.querySelector('[data-solido-capaz="edificabilidad"]');
      var elPlantas = resultadoSolidoCapazEl.querySelector('[data-solido-capaz="plantas"]');
      if (elSuperficie) {
        var textoSuperficie = superficieOcupada.toFixed(0) + " m²";
        if (parcelaSuperficieM2 && limitesUrbanisticos.ocupacion_maxima_pct > 0) {
          var maxOcupacion = parcelaSuperficieM2 * limitesUrbanisticos.ocupacion_maxima_pct / 100;
          if (maxOcupacion > 0) textoSuperficie += " (" + (superficieOcupada / maxOcupacion * 100).toFixed(0) + "% del máximo permitido)";
        }
        elSuperficie.textContent = textoSuperficie;
      }
      if (elEdificabilidad) {
        var textoEdificabilidad = edificabilidadUsada.toFixed(0) + " m²";
        if (parcelaSuperficieM2 && limitesUrbanisticos.edificabilidad_maxima != null) {
          textoEdificabilidad += " de " + (parcelaSuperficieM2 * limitesUrbanisticos.edificabilidad_maxima).toFixed(0) + " m² permitidos";
        }
        elEdificabilidad.textContent = textoEdificabilidad;
      }
      if (elPlantas) elPlantas.textContent = String(plantasEstimadas);
    }

    if (estadoSolidoCapazEl) {
      estadoSolidoCapazEl.hidden = retranqueoAplicable;
      if (!retranqueoAplicable) estadoSolidoCapazEl.textContent = "Retranqueo no aplicable en zonas cóncavas.";
    }
    actualizarBotonGenerar(); // `solidoCapazMesh` ya calculado -- puede habilitar "Generar plantas con IA" aunque no haya ningún volumen dibujado a mano

    // Programa de Necesidades (2026-08-17, PRD aprobado, decisión 1): informa al panel de la
    // edificabilidad REAL de esta parcela -- `null` si no hay `edificabilidad_maxima` declarada (el
    // panel lo trata como "sin techo todavía conocido", nunca como 0). `plantasEstimadas` alimenta el
    // autorrelleno/validación de "Nº de plantas" (decisión 4).
    ProgramaNecesidades.actualizarSolidoCapaz({
      superficieParcelaM2: parcelaSuperficieM2,
      edificabilidadMaximaM2: (parcelaSuperficieM2 && limitesUrbanisticos.edificabilidad_maxima != null)
        ? parcelaSuperficieM2 * limitesUrbanisticos.edificabilidad_maxima : null,
      plantasMaximasSolidoCapaz: plantasEstimadas
    });
    // Capa roja de exceso (Fase 3): recalcula contra las plantas YA guardadas del programa (si las
    // hay) para este Sólido Capaz recién calculado -- `getEstado()` devuelve `null` solo si el panel
    // no está montado, lo que no puede pasar aquí (`calcularSolidoCapaz` solo se llama con el Sandbox
    // abierto, que ya montó `ProgramaNecesidades` en `open()`).
    var estadoPrograma = ProgramaNecesidades.getEstado();
    actualizarCapaExcesoPrograma(estadoPrograma ? estadoPrograma.plantas : null);
  }

  // Sólido Capaz persistente (2026-08-17, docs/prd/2026-08-17-solido-capaz-persistente-visor-
  // edificio.md, tarea 2 de §11): serializa el Sólido Capaz ACTIVO (`solidoCapazMesh`) a un snapshot
  // JSON plano, listo para viajar en el body de `/api/generar` y guardarse junto al proyecto. `null` si
  // no se ha calculado ninguno todavía (el arquitecto pulsó "Generar plantas con IA" sin pasar antes por
  // "Calcular Sólido Capaz") o si falta el origen real lat/lon (sin él, el polígono en metros locales no
  // se podría volver a anclar a coordenadas reales desde otro visor) -- nunca se inventa ninguno de los
  // dos. `poligono_final_local` queda en los MISMOS ejes locales que `parcelaPoligonoLocal`
  // (`metrosEsteNorteDesde` + `rotarAEjesLocales` desde `origen_lat`/`origen_lon`), para que quien lo
  // reconstruya use exactamente la misma proyección, no una propia.
  function serializarSolidoCapaz() {
    if (!solidoCapazMesh || parcelaOrigenLat == null || parcelaOrigenLon == null) return null;
    var poligono = solidoCapazMesh.userData.poligonoFinal || [];
    return {
      origen_lat: parcelaOrigenLat,
      origen_lon: parcelaOrigenLon,
      poligono_final_local: poligono.map(function (p) { return [p.x, p.z]; }),
      altura_max_m: solidoCapazMesh.userData.alturaTotalM,
      plantas_estimadas: solidoCapazMesh.userData.plantasLegales,
      superficie_ocupada_m2: areaPoligono(poligono),
      calculado_en: new Date().toISOString()
    };
  }

  function construirHudUrbanismo() {
    var hud = document.createElement("div");
    hud.className = "sandbox-hud-urbanismo";
    hud.id = "sandbox-hud-urbanismo";
    hud.innerHTML =
      '<div class="sandbox-hud-titulo">Urbanismo</div>' +
      '<p class="sandbox-hud-aviso" hidden>Sin datos reales de parcela (Catastro) para esta ubicación — no se puede calcular ocupación, edificabilidad ni retranqueos.</p>' +
      // Edificio existente vs. vecinos (2026-08-17, PRD aprobado): aviso INDEPENDIENTE del de arriba
      // -- ese dice "no hay contorno real de parcela"; este dice "sí hay parcela real, pero ningún
      // edificio de Catastro/OSM cae dentro de ella" (solar vacío). Nunca se muestran los dos a la vez
      // (ver `actualizarUrbanismo`): sin parcela real no hay nada que clasificar todavía.
      '<p class="sandbox-hud-aviso" id="sandbox-hud-aviso-sin-edificio" hidden>Sin edificación registrada en esta parcela.</p>' +
      '<div id="sandbox-hud-metricas" hidden>' +
      '<div class="sandbox-hud-fila" data-hud-fila="ocupacion" hidden><span class="sandbox-hud-fila-label">Ocupación</span><span class="sandbox-hud-fila-valor"></span></div>' +
      '<div class="sandbox-hud-fila" data-hud-fila="edificabilidad" hidden><span class="sandbox-hud-fila-label">Edificabilidad</span><span class="sandbox-hud-fila-valor"></span></div>' +
      '<div class="sandbox-hud-fila" data-hud-fila="plantas" hidden><span class="sandbox-hud-fila-label">Plantas</span><span class="sandbox-hud-fila-valor"></span></div>' +
      "</div>" +
      '<p class="sandbox-hud-normativa-madrid" id="sandbox-hud-normativa-madrid" hidden></p>' +
      // Límites urbanísticos: SIEMPRE expandido, nunca colapsado (2026-08-17, docs/prd/2026-08-17-
      // normativa-urbanistica-capas-fallback.md, Fase A, decisión explícita de Pablo -- antes
      // `<details>` colapsado por defecto). Los 4 campos que pide el encargo llevan placeholders "ej.
      // X" (referencia orientativa, nunca un valor real precargado) cuando no hay dato -- "Plantas
      // máx." no es uno de esos 4 campos, sigue con su placeholder "—" de siempre, sin cambios.
      '<div class="sandbox-hud-limites">' +
      '<div class="sandbox-hud-limites-titulo">Límites urbanísticos ' +
      // Badge de "perfil de ejemplo" (2026-08-17, encargo explícito -- ver `PERFIL_EJEMPLO_URBANISTICO`
      // más arriba): reutiliza LITERALMENTE `.hecho-badge`/`.hecho-badge-estimated`, el mismo lenguaje
      // visual que ya usa el resto de la app para "estimado, no verificado" -- sin CSS nuevo. Oculto por
      // defecto; `rellenarCamposLimites()` lo muestra solo mientras `limitesSonEjemplo` sea `true`.
      '<span class="hecho-badge hecho-badge-estimated" id="sandbox-lim-badge-ejemplo" hidden ' +
      'title="Perfil de ejemplo, no son datos normativos reales de esta parcela -- edítalos con los valores reales antes de decidir nada">Ejemplo</span>' +
      "</div>" +
      '<div class="sandbox-hud-limites-campos">' +
      '<div class="sandbox-hud-limite-campo"><label for="sandbox-lim-ocupacion">Ocupación máx. (%)</label>' +
      '<input type="number" id="sandbox-lim-ocupacion" min="0" max="100" step="1" placeholder="ej. 70"></div>' +
      '<div class="sandbox-hud-limite-campo"><label for="sandbox-lim-altura">Altura máxima (m)</label>' +
      '<input type="number" id="sandbox-lim-altura" min="0" step="0.5" placeholder="ej. 13"></div>' +
      '<div class="sandbox-hud-limite-campo"><label for="sandbox-lim-retranqueos">Retranqueos (m)</label>' +
      '<input type="number" id="sandbox-lim-retranqueos" min="0" step="0.5" placeholder="ej. 3"></div>' +
      '<div class="sandbox-hud-limite-campo"><label for="sandbox-lim-edificabilidad">Edificabilidad (m²/m²)</label>' +
      '<input type="number" id="sandbox-lim-edificabilidad" min="0" step="0.1" placeholder="ej. 2.0"></div>' +
      '<div class="sandbox-hud-limite-campo"><label for="sandbox-lim-plantas">Plantas máx.</label>' +
      '<input type="number" id="sandbox-lim-plantas" min="1" step="1" placeholder="—"></div>' +
      "</div></div>" +
      // Sólido capaz (2026-08-17, PRD aprobado): botón + estado + resultado, fuera del bloque de
      // límites de arriba -- es la acción principal del panel, no debe empezar oculta. `.sandbox-hud-boton`
      // reutiliza el mismo lenguaje visual plano ya establecido (sin gradiente, hover sutil); el
      // resultado reutiliza literalmente las clases `.sandbox-hud-fila*` ya existentes -- mismo texto
      // plano sin badges que el resto del panel, sin CSS nuevo para esas filas.
      '<button type="button" id="btn-sandbox-solido-capaz" class="sandbox-hud-boton" disabled>Calcular sólido capaz</button>' +
      '<p class="sandbox-hud-aviso" id="sandbox-hud-solido-capaz-estado" hidden></p>' +
      '<div id="sandbox-hud-solido-capaz-resultado" hidden>' +
      '<div class="sandbox-hud-fila"><span class="sandbox-hud-fila-label">Superficie ocupada</span><span class="sandbox-hud-fila-valor" data-solido-capaz="superficie"></span></div>' +
      '<div class="sandbox-hud-fila"><span class="sandbox-hud-fila-label">Edificabilidad usada</span><span class="sandbox-hud-fila-valor" data-solido-capaz="edificabilidad"></span></div>' +
      '<div class="sandbox-hud-fila"><span class="sandbox-hud-fila-label">Plantas estimadas</span><span class="sandbox-hud-fila-valor" data-solido-capaz="plantas"></span></div>' +
      "</div>" +
      // "X edificios en contexto · X m² construidos" (2026-08-17, encargo explícito): línea discreta al
      // pie del panel, oculta hasta que la clasificación de colindantes termine y encuentre al menos
      // un edificio -- ver `actualizarResumenContextoEdificios`.
      '<p class="sandbox-hud-contexto-edificios" id="sandbox-hud-contexto-edificios" hidden></p>';
    mount.appendChild(hud);
    hudUrbanismoEl = hud;
    hudMetricasEl = hud.querySelector("#sandbox-hud-metricas");
    avisoSinEdificioEl = hud.querySelector("#sandbox-hud-aviso-sin-edificio");
    normativaMadridEl = hud.querySelector("#sandbox-hud-normativa-madrid");
    resumenContextoEdificiosEl = hud.querySelector("#sandbox-hud-contexto-edificios");

    var campoOcupacion = hud.querySelector("#sandbox-lim-ocupacion");
    var campoRetranqueos = hud.querySelector("#sandbox-lim-retranqueos");
    var campoEdificabilidad = hud.querySelector("#sandbox-lim-edificabilidad");
    var campoPlantas = hud.querySelector("#sandbox-lim-plantas");
    var campoAltura = hud.querySelector("#sandbox-lim-altura");
    campoLimOcupacionEl = campoOcupacion; campoLimRetranqueosEl = campoRetranqueos;
    campoLimEdificabilidadEl = campoEdificabilidad; campoLimPlantasEl = campoPlantas; campoLimAlturaEl = campoAltura;
    badgeLimitesEjemploEl = hud.querySelector("#sandbox-lim-badge-ejemplo");
    // Refleja `limitesUrbanisticos` en los 5 inputs + el badge de "ejemplo" -- se llama aquí (con lo
    // que ya haya, típicamente de `restaurarLimitesUrbanisticosLocal()`) y otra vez después, si
    // `aplicarPerfilEjemploYAutocalcular()` rellena el perfil de ejemplo una vez que la parcela real
    // esté resuelta (ver `open()`, más abajo -- los inputs se crean ANTES de eso).
    rellenarCamposLimites();

    // `null` explícito con el campo vacío (no `NaN`/`0`) -- mismo criterio de "no evaluable" que el
    // resto de este PRD: un campo en blanco significa "sin límite declarado", no "límite cero".
    // Los 4 campos de la Fase A (todos menos "Plantas máx.") también guardan en `localStorage` en cada
    // cambio -- tiempo real, sin botón "Aplicar", encargo explícito. Cualquier edición manual también
    // apaga `limitesSonEjemplo`/el badge (2026-08-17): a partir de ese toque el valor es una elección
    // real del arquitecto, no el perfil de ejemplo -- nunca se queda el badge puesto sobre un dato que
    // el arquitecto ya corrigió.
    campoOcupacion.addEventListener("input", function () {
      limitesUrbanisticos.ocupacion_maxima_pct = campoOcupacion.value === "" ? null : parseFloat(campoOcupacion.value);
      apagarBadgeEjemplo();
      guardarLimitesUrbanisticosLocal();
      actualizarUrbanismo();
    });
    campoRetranqueos.addEventListener("input", function () {
      limitesUrbanisticos.retranqueos_m = campoRetranqueos.value === "" ? null : parseFloat(campoRetranqueos.value);
      apagarBadgeEjemplo();
      guardarLimitesUrbanisticosLocal();
      actualizarUrbanismo();
    });
    campoEdificabilidad.addEventListener("input", function () {
      limitesUrbanisticos.edificabilidad_maxima = campoEdificabilidad.value === "" ? null : parseFloat(campoEdificabilidad.value);
      apagarBadgeEjemplo();
      guardarLimitesUrbanisticosLocal();
      actualizarUrbanismo();
    });
    campoPlantas.addEventListener("input", function () {
      // No es uno de "los 4 campos" de la Fase A -- no se persiste en `localStorage`, sin cambios de
      // comportamiento respecto a como ya funcionaba.
      limitesUrbanisticos.plantas_maximas = campoPlantas.value === "" ? null : parseInt(campoPlantas.value, 10);
      apagarBadgeEjemplo();
      actualizarUrbanismo();
    });
    campoAltura.addEventListener("input", function () {
      limitesUrbanisticos.altura_maxima_m = campoAltura.value === "" ? null : parseFloat(campoAltura.value);
      apagarBadgeEjemplo();
      guardarLimitesUrbanisticosLocal();
      actualizarUrbanismo(); // recalcula si el botón puede activarse -- NO recalcula el sólido ya dibujado (§6 del PRD: solo al pulsar)
    });

    // Sólido capaz: captura de elementos + cableado del botón.
    btnSolidoCapazEl = hud.querySelector("#btn-sandbox-solido-capaz");
    estadoSolidoCapazEl = hud.querySelector("#sandbox-hud-solido-capaz-estado");
    resultadoSolidoCapazEl = hud.querySelector("#sandbox-hud-solido-capaz-resultado");
    btnSolidoCapazEl.addEventListener("click", calcularSolidoCapaz);
  }

  // Nota de contexto real, no un campo editable (ver comentario grande en la declaración de
  // `normativaMadridEl` sobre por qué este piloto nunca autorrellena los 4 campos numéricos de arriba).
  // Silenciosa cuando la parcela está claramente fuera de Madrid (`dentro_de_piloto: false`) -- avisar
  // en cada apertura del Sandbox de que "esto no aplica aquí" para cualquier proyecto fuera de Madrid
  // sería ruido permanente sin ninguna acción que el arquitecto pueda tomar con ese aviso.
  function renderizarNormativaMadrid(datos) {
    if (!normativaMadridEl || !datos) return;
    // Solo se muestra cuando SÍ hay un dato real encontrado (Fase A de normativa, 2026-08-17, encargo
    // explícito: "sin mensajes de error, sin alertas, sin textos técnicos explicando por qué no se
    // encontró normativa" -- antes este `else` mostraba `datos.motivo`). Sin dato real: silencio, los
    // 4 campos de "Límites urbanísticos" (siempre visibles ahora, ver `construirHudUrbanismo`) ya son
    // el único mensaje que hace falta.
    if (!datos.dentro_de_piloto || !datos.disponible || !datos.referencia) { normativaMadridEl.hidden = true; return; }
    var ref = datos.referencia;
    normativaMadridEl.textContent = "PGOUM 97 (Madrid), Norma Zonal " + ref.norma_zonal + ", " +
      ref.grado_etiqueta + " — sin traducción numérica verificada todavía; consulta el geoportal " +
      "municipal para los valores exactos.";
    normativaMadridEl.hidden = false;
  }

  // Reconciliación puntual con el backend (2026-08-16, PRD §7.6/§9): las mismas funciones REALES de
  // `evaluator.py`, vía `POST /api/validar-urbanismo`, contra los mismos números que ya muestra el
  // HUD -- fire-and-forget, nunca bloquea `onGenerarCallback` (que sigue llamándose exactamente igual
  // que antes, en el mismo sitio). Cualquier discrepancia se registra en consola para depuración, no
  // se le muestra al arquitecto (sería ruido: el cliente ya es la fuente de verdad de la interacción).
  function reconciliarConBackend() {
    if (!parcelaSuperficieM2) return;
    var payload = {
      superficie_solar_m2: parcelaSuperficieM2,
      volumenes: volumenes.map(function (vol) { return { largo: vol.largo, ancho: vol.ancho, plantas: vol.plantas }; }),
      normativa: limitesUrbanisticos
    };
    // Nombre del campo real de cada dataclass de `evaluator.py` (`SolarOccupationResult.ocupacion_pct`
    // / `BuildabilityResult.edificabilidad_real` / `MaxFloorsResult.plantas`) -- distinto por métrica,
    // de ahí el mapa explícito en vez de un único nombre genérico.
    var CAMPO_VALOR_BACKEND = { ocupacion: "ocupacion_pct", edificabilidad: "edificabilidad_real", plantas: "plantas" };
    fetch("/api/validar-urbanismo", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    }).then(function (resp) { return resp.json(); }).then(function (real) {
      var cliente = calcularMetricasUrbanisticas();
      Object.keys(CAMPO_VALOR_BACKEND).forEach(function (clave) {
        var c = cliente[clave], r = real[clave];
        var difieren = (c == null) !== (r == null) ||
          (c != null && r != null && Math.abs(c.valor - r[CAMPO_VALOR_BACKEND[clave]]) > 0.01);
        if (difieren) console.warn("[Sandbox urbanismo] Discrepancia cliente/backend en '" + clave + "':", c, r);
      });
    }).catch(function () { /* red caída: la reconciliación es best-effort, nunca bloquea el flujo real */ });
  }

  function colocarSol(azimuthDeg, elevationDeg) {
    if (!sunLight) return;
    var dir = directionFromAzimuthElevation(azimuthDeg, Math.max(elevationDeg, 8));
    sunLight.position.copy(dir).multiplyScalar(150);
    sunLight.target.position.set(0, 0, 0);
    sunLight.shadow.updateMatrices(sunLight);
  }

  // --- Selección de volumen (clic sobre el canvas, raycaster) -------------------------------------

  function seleccionarVolumen(idx) {
    // La asignación real del material (seleccionado/retranqueo/agregado/normal) vive por completo en
    // `actualizarUrbanismo()` (2026-08-16, prioridad de materiales) -- aquí solo se cambia `seleccionado`
    // y se llama a esa función, en vez de asignar el material a mano dos veces con lógica duplicada.
    seleccionado = idx;
    if (idx == null) { panelEl.hidden = true; actualizarUrbanismo(); return; }
    var vol = volumenes[idx];
    panelIndiceEl.textContent = String(idx + 1);
    inputLargo.value = vol.largo; valorLargo.textContent = vol.largo.toFixed(1) + " m";
    inputAncho.value = vol.ancho; valorAncho.textContent = vol.ancho.toFixed(1) + " m";
    inputPlantas.value = vol.plantas; valorPlantas.textContent = String(vol.plantas);
    inputRotacion.value = vol.rotacionDeg; valorRotacion.textContent = vol.rotacionDeg + "°";
    panelEl.hidden = false;
    actualizarUrbanismo();
  }

  function alClicEnMount(ev) {
    if (!session || !volumenes.length) return;
    var ndc = session.pointerToNDC(ev.clientX, ev.clientY);
    if (!ndc) return;
    raycaster.setFromCamera(new THREE.Vector2(ndc.x, ndc.y), camera);
    var meshes = volumenes.map(function (v) { return v.mesh; });
    var hits = raycaster.intersectObjects(meshes, false);
    if (hits.length) seleccionarVolumen(meshes.indexOf(hits[0].object));
  }

  // --- Ciclo de vida --------------------------------------------------------------------------

  // "Generar plantas con IA" tiene DOS caminos independientes hacia los mismos 3 parámetros
  // (superficie/forma/plantas), no solo uno (2026-08-17, corrección: antes esta función solo miraba
  // `volumenes`, así que el botón se quedaba deshabilitado -- "Añade al menos un volumen primero" --
  // aunque el arquitecto ya hubiera calculado un Sólido Capaz real y rellenado el Programa de
  // Necesidades entero, sin haber dibujado ningún volumen a mano):
  //   1. Un volumen dibujado a mano con "+ Añadir volumen" (camino original, Objetivo 3).
  //   2. Un Sólido Capaz calculado sobre la parcela real (camino añadido por su propio PRD encima del
  //      anterior) -- ver la rama `!seleccionado && !volumenes.length` en el propio `click` de abajo.
  function actualizarBotonGenerar() {
    var hay = volumenes.length > 0 || !!solidoCapazMesh;
    btnGenerar.disabled = !hay;
    btnGenerar.title = hay ? "" : "Añade un volumen o calcula el sólido capaz primero";
    if (btnGenerarOpciones) {
      btnGenerarOpciones.disabled = !hay;
      btnGenerarOpciones.title = hay ? "" : "Añade un volumen o calcula el sólido capaz primero";
    }
  }

  // Validación al pulsar "Generar plantas con IA" (2026-08-17, encargo explícito): hacen falta DOS
  // cosas, y son dos campos distintos con dos causas distintas -- nunca el mismo texto genérico para
  // las dos, decirle al arquitecto que pulse un botón que no arregla su problema real sería peor que no
  // decir nada:
  //   1. Un Sólido Capaz calculado (`solidoCapazMesh`) -- define el límite legal contra el que
  //      comparar. Sin él, "Calcular sólido capaz" es la acción que falta.
  //   2. Al menos una vivienda objetivo en el Programa de Necesidades -- sin eso, "Construida objetivo"
  //      se queda en 0 m² (no depende del Sólido Capaz, ver `calcularMetricas()` en programa-
  //      necesidades.js) y no hay nada real que pedirle a la IA que reparta en plantas.
  // Vuelve `null` si puede generar, o `{texto, campo}` con el motivo concreto si no.
  function motivoBloqueoGenerar() {
    if (!solidoCapazMesh) {
      return { texto: "Pulsa «Calcular sólido capaz» antes de generar plantas con IA.", campo: "solido-capaz" };
    }
    var estadoPrograma = ProgramaNecesidades.getEstado();
    var construida = estadoPrograma && estadoPrograma.metricas ? estadoPrograma.metricas.construidaTotalObjetivoM2 : 0;
    if (!(construida > 0)) {
      return {
        texto: "Indica cuántas «Viviendas objetivo» quieres en el Programa de Necesidades -- la Construida objetivo sigue en 0 m².",
        campo: "viviendas-objetivo"
      };
    }
    return null;
  }

  // Feedback visual inmediato del bloqueo de arriba -- nunca un `alert()` bloqueante: aviso de texto en
  // rojo (mismo tono que ya marca "excede el máximo" en las filas de urbanismo) + resaltado momentáneo
  // del control concreto que falta por rellenar/pulsar.
  function mostrarBloqueoGenerar(motivo) {
    if (estadoSolidoCapazEl) {
      estadoSolidoCapazEl.hidden = false;
      estadoSolidoCapazEl.textContent = motivo.texto;
      estadoSolidoCapazEl.classList.add("es-error");
    }
    if (motivo.campo === "solido-capaz" && btnSolidoCapazEl) {
      btnSolidoCapazEl.classList.remove("sandbox-resaltar-error");
      void btnSolidoCapazEl.offsetWidth; // reflow: fuerza a reiniciar la animación si ya estaba en marcha
      btnSolidoCapazEl.classList.add("sandbox-resaltar-error");
    } else if (motivo.campo === "viviendas-objetivo") {
      ProgramaNecesidades.resaltarCampoViviendasObjetivo();
    }
  }

  // Traduce el mix de 4 tipologías en % del Programa de Necesidades (1D/2D/3D/4D, PRD propio del panel)
  // al formato de 3 cubos en NÚMERO de viviendas que ya entiende `/api/generar` (`dorm_1/dorm_2/dorm_3`,
  // ver `_parse_generar_params` en app.py). El backend no tiene un 4º cubo: 4D se suma dentro de
  // `dorm_3` (la vivienda más grande que el modelo actual sabe representar) en vez de perderse en
  // silencio. `null` si no hay viviendas objetivo declaradas -- nunca se inventa un mix.
  function mixViviendasDesdePrograma(estadoPrograma) {
    if (!estadoPrograma || !estadoPrograma.viviendasObjetivo) return null;
    var total = estadoPrograma.viviendasObjetivo;
    var mix = estadoPrograma.mix || {};
    return {
      dorm_1: Math.round(total * (mix["1d"] || 0) / 100),
      dorm_2: Math.round(total * (mix["2d"] || 0) / 100),
      dorm_3: Math.round(total * ((mix["3d"] || 0) + (mix["4d"] || 0)) / 100)
    };
  }

  // --- Encuadre automático de cámara y frustum de sombra --------------------------------------
  // (docs/prd/2026-08-16-sandbox-encuadre-camara-y-sombra.md): antes la cámara arrancaba siempre en
  // una posición fija (45,38,45) y la sombra del sol en un frustum fijo de 120 m, sin relación con
  // el tamaño real de lo cargado -- el mosaico de ortofoto puede llegar a cubrir ~580 m de lado, y
  // el radio de colindantes que consulta el backend (`_ENTORNO_3D_RADIO_M` en app.py) es 180 m,
  // ambos mayores que esos 120 m fijos. Se calcula aquí el `Box3` real de la escena (terreno u
  // ortofoto + colindantes + volúmenes) y se usa tanto para encuadrar la cámara como para
  // dimensionar la sombra, así las dos cosas quedan siempre coherentes entre sí y con el contenido
  // real -- no dos valores fijos adivinados por separado.

  function radioHorizontalEscena() {
    if (!scene) return 150;
    var caja = new THREE.Box3().setFromObject(scene);
    if (caja.isEmpty()) return 150;
    var tam = caja.getSize(new THREE.Vector3());
    // Radio horizontal (plano XZ): la altura (Y) de los volúmenes no debe ensanchar el frustum de
    // sombra ni alejar la cámara más de lo que hace falta para ver la parcela en planta.
    return Math.max(Math.max(tam.x, tam.z) / 2, 20);
  }

  function encuadrarCamaraAContenido() {
    if (!scene || !camera || !controls) return;
    var caja = new THREE.Box3().setFromObject(scene);
    if (caja.isEmpty()) return;
    var centro = caja.getCenter(new THREE.Vector3());
    // Vista de estudio a 45° de azimut / 45° de elevación (encargo explícito), a una distancia
    // proporcional al radio real del contenido -- `R / tan(fov/2)` es la distancia mínima para que
    // un contenido de radio R quepa entero en el encuadre vertical (fov=50° en `createViewerSession`
    // más abajo), con un margen del 10% para no dejarlo pegado al borde.
    var distancia = THREE.MathUtils.clamp(radioHorizontalEscena() / Math.tan(THREE.MathUtils.degToRad(25)) * 1.1, 30, controls.maxDistance);
    var offset = directionFromAzimuthElevation(45, 45).multiplyScalar(distancia);
    camera.position.set(centro.x + offset.x, centro.y + offset.y, centro.z + offset.z);
    controls.target.copy(centro);
    controls.update();
  }

  // Igual que `encuadrarCamaraAContenido()`, pero acotado al polígono real de la parcela (sus propios
  // puntos `{x,z}`, ya en ejes locales) en vez de al `Box3` de toda la escena -- ver comentario grande
  // en `open()` sobre por qué el encuadre general no basta como primera impresión cuando ya hay
  // geometría real que mostrar. `radio` con suelo de 10 m: una parcela minúscula tampoco debe dejar la
  // cámara pegada encima del polígono.
  function encuadrarCamaraAPoligono(puntosLocal) {
    if (!camera || !controls || !puntosLocal || !puntosLocal.length) return;
    var radio = 10;
    puntosLocal.forEach(function (p) { radio = Math.max(radio, Math.hypot(p.x, p.z)); });
    var distancia = THREE.MathUtils.clamp(radio / Math.tan(THREE.MathUtils.degToRad(25)) * 1.15, 18, controls.maxDistance);
    var offset = directionFromAzimuthElevation(45, 45).multiplyScalar(distancia);
    camera.position.set(offset.x, offset.y, offset.z);
    controls.target.set(0, 0, 0);
    controls.update();
  }

  // Límites de `OrbitControls`/cámara adaptativos (2026-08-16, docs/prd/2026-08-16-sandbox-
  // navegacion-profesional-y-lindes.md): antes `minDistance`/`maxDistance`/`near`/`far` eran
  // constantes fijas (5/550/0.1/2000) sin relación con lo cargado -- suficientes para no romper nada,
  // pero ni impiden que la cámara se meta bajo el suelo en una escena diminuta (un único volumen
  // pequeño) ni garantizan ver una escena mucho más grande que la parcela de prueba habitual. Se
  // recalculan sobre el mismo `Box3` real que ya usa `encuadrarCamaraAContenido`/
  // `ajustarFrustumSombra`, en los mismos puntos de llamada -- nunca de forma más frecuente, mismo
  // criterio de "no mover/recortar la experiencia mientras el usuario solo está orbitando".
  function ajustarLimitesCamara() {
    if (!scene || !camera || !controls) return;
    var caja = new THREE.Box3().setFromObject(scene);
    if (caja.isEmpty()) return;
    var radio = radioHorizontalEscena();
    var diagonal = caja.getSize(new THREE.Vector3()).length();
    controls.minDistance = THREE.MathUtils.clamp(radio * 0.05, 3, 15);
    controls.maxDistance = Math.max(550, radio * 2.2);
    camera.near = Math.max(0.05, controls.minDistance * 0.1);
    camera.far = Math.max(2000, diagonal * 4 + 200);
    camera.updateProjectionMatrix();
  }

  function ajustarFrustumSombra() {
    if (!sunLight) return;
    // Nunca menos que el radio de colindantes que consulta el backend (180 m) aunque la escena
    // todavía no tenga nada cargado a esa distancia -- evita un frustum que se quede corto justo
    // cuando lleguen los colindantes. +40 m de margen sobre el borde real detectado.
    var mitadLado = Math.max(180, radioHorizontalEscena()) + 40;
    configureSunShadow(sunLight, mitadLado, {
      shadowMapSize: 4096, // antes 2048 (encargo explícito): nitidez en los bordes de los
      // edificios sobre la ortofoto, ahora que el frustum cubre un área mucho mayor.
      shadowNear: 1, shadowFar: mitadLado * 4 + 50, shadowBias: -0.0005, shadowNormalBias: 0.02, shadowRadius: 8
    });
  }

  // --- Gizmo de orientación, doble clic y barra de herramientas (2026-08-16, docs/prd/2026-08-16-
  // sandbox-navegacion-profesional-y-lindes.md) -----------------------------------------------------
  // Mismo patrón ya construido y verificado hoy en `viewer-edificio.js` (`buildCompass`/
  // `onDblClickRecenter`), adaptado aquí: en Sandbox no hay conflicto con ninguna selección que cierre
  // el visor (el clic simple solo selecciona un volumen para editarlo, `alClicEnMount`), así que el
  // doble clic SÍ puede recentrar sobre terreno/ortofoto/colindantes/contorno -- se excluyen
  // explícitamente los volúmenes propios del arquitecto (raycast contra `scene.children` completo,
  // filtrando cualquier hit cuyo ancestro sea uno de `volumenes`) para no interferir con
  // `seleccionarVolumen`, que es la interacción principal de este modo.

  function construirGizmoNorte() {
    var gizmo = document.createElement("div");
    gizmo.className = "viewer-compass";
    gizmo.id = "sandbox-compass";
    gizmo.title = "Volver al norte";
    gizmo.setAttribute("aria-label", "Volver al norte");
    gizmo.innerHTML =
      '<div class="viewer-compass-needle" id="sandbox-compass-needle">' +
      '<svg viewBox="0 0 52 52" xmlns="http://www.w3.org/2000/svg">' +
      '<circle cx="26" cy="26" r="24" fill="none" stroke="rgba(255,255,255,0.35)" stroke-width="1"/>' +
      '<path d="M26 6 L31 26 L26 22 L21 26 Z" fill="#fff"/>' +
      '<text x="26" y="17" text-anchor="middle" font-size="9" font-weight="700" fill="#fff">N</text>' +
      "</svg></div>";
    // `.viewer-compass` (reutilizada de `viewer-edificio.js`) trae de fábrica `opacity:0` con un fade
    // de entrada que solo ese otro visor completa (`compassEl.classList.add("intro-in")`, en su propia
    // secuencia de aparición escalonada) -- el Sandbox no tiene esa coreografía, así que sin esto el
    // gizmo quedaría invisible para siempre pese a existir en el DOM.
    gizmo.classList.add("intro-in");
    mount.appendChild(gizmo);

    var needle = gizmo.querySelector("#sandbox-compass-needle");
    function actualizar() {
      if (!camera || !controls) return;
      var dx = camera.position.x - controls.target.x;
      var dz = camera.position.z - controls.target.z;
      var deg = Math.atan2(dx, dz) * 180 / Math.PI;
      needle.style.transform = "rotate(" + -deg + "deg)";
    }
    controls.addEventListener("change", actualizar);
    actualizar();

    gizmo.addEventListener("click", function () {
      if (!camera || !controls) return;
      var offset = camera.position.clone().sub(controls.target);
      var radioHorizontal = Math.sqrt(Math.max(0, offset.x * offset.x + offset.z * offset.z));
      var nuevaPos = controls.target.clone().add(new THREE.Vector3(0, offset.y, radioHorizontal));
      animarCamaraA(nuevaPos, controls.target.clone(), 600);
    });
  }

  var dblClickRaycaster = new THREE.Raycaster();
  function onDblClickRecenter(e) {
    if (!camera || !controls || !scene) return;
    var ndc = session.pointerToNDC(e.clientX, e.clientY);
    if (!ndc) return;
    dblClickRaycaster.setFromCamera(new THREE.Vector2(ndc.x, ndc.y), camera);
    var hits = dblClickRaycaster.intersectObjects(scene.children, true);
    var volumenMeshes = volumenes.map(function (v) { return v.mesh; });
    var hit = null;
    for (var i = 0; i < hits.length && !hit; i++) {
      var pertenece = false;
      for (var p = hits[i].object; p; p = p.parent) {
        if (volumenMeshes.indexOf(p) !== -1) { pertenece = true; break; }
      }
      if (!pertenece) hit = hits[i];
    }
    if (!hit) return;
    var punto = hit.point;
    var offset = camera.position.clone().sub(controls.target);
    animarCamaraA(punto.clone().add(offset), punto.clone(), 500);
  }

  // Vista "Planta / Norte arriba" (encargo explícito): sin cámara ortográfica propia (a diferencia de
  // `viewer-edificio.js`) -- una perspectiva casi cenital (89°, no 90°: exactamente el mismo motivo
  // que documenta `getCameraPose("top", ...)` en el otro visor, evita degenerar el vector "up" de
  // los controles) es coherente con mantener el Sandbox más simple, sin una segunda cámara que
  // gestionar.
  function poseVistaPlanta(centro, radio) {
    var distancia = THREE.MathUtils.clamp(radio / Math.tan(THREE.MathUtils.degToRad(25)) * 1.1, 30, controls.maxDistance);
    var dir = directionFromAzimuthElevation(0, 89);
    return {
      pos: new THREE.Vector3(centro.x + distancia * 0.001, centro.y + dir.y * distancia, centro.z + distancia * 0.001),
      target: centro.clone()
    };
  }

  function construirBarraHerramientas() {
    var barra = document.createElement("div");
    barra.className = "sandbox-toolbar";
    barra.id = "sandbox-toolbar";
    barra.innerHTML =
      '<button type="button" class="sandbox-toolbar-btn" id="sandbox-tb-iso">Isométrica</button>' +
      '<button type="button" class="sandbox-toolbar-btn" id="sandbox-tb-planta">Planta · Norte arriba</button>' +
      '<button type="button" class="sandbox-toolbar-btn" id="sandbox-tb-sombras">Sombras</button>' +
      // Toggle "Plantas Explosionadas" (Fase 3, encargo explícito): mismo lenguaje visual plano que el
      // resto de la barra (`.sandbox-toolbar-btn`/`.active`), sin control nuevo fuera de este patrón.
      '<button type="button" class="sandbox-toolbar-btn" id="sandbox-tb-explosion">Plantas explosionadas</button>';
    mount.appendChild(barra);

    document.getElementById("sandbox-tb-iso").addEventListener("click", function () {
      if (!scene || !camera || !controls) return;
      var caja = new THREE.Box3().setFromObject(scene);
      if (caja.isEmpty()) return;
      var centro = caja.getCenter(new THREE.Vector3());
      var distancia = THREE.MathUtils.clamp(radioHorizontalEscena() / Math.tan(THREE.MathUtils.degToRad(25)) * 1.1, 30, controls.maxDistance);
      var offset = directionFromAzimuthElevation(45, 45).multiplyScalar(distancia);
      animarCamaraA(new THREE.Vector3(centro.x + offset.x, centro.y + offset.y, centro.z + offset.z), centro, 700);
    });
    document.getElementById("sandbox-tb-planta").addEventListener("click", function () {
      if (!scene || !camera || !controls) return;
      var caja = new THREE.Box3().setFromObject(scene);
      if (caja.isEmpty()) return;
      var centro = caja.getCenter(new THREE.Vector3());
      var pose = poseVistaPlanta(centro, radioHorizontalEscena());
      animarCamaraA(pose.pos, pose.target, 700);
    });
    var btnSombrasToolbar = document.getElementById("sandbox-tb-sombras");
    btnSombrasToolbar.classList.add("active");
    btnSombrasToolbar.addEventListener("click", function () {
      if (!sunLight || !renderer) return;
      var activo = !sunLight.castShadow;
      sunLight.castShadow = activo;
      renderer.shadowMap.enabled = activo;
      btnSombrasToolbar.classList.toggle("active", activo);
    });
    // Toggle "Plantas Explosionadas" / "Volumen Total" (Fase 3): reposiciona las plantas ya
    // construidas del Sólido Capaz (si lo hay) -- funciona igual con o sin sólido calculado todavía
    // (`aplicarModoVistaSolidoCapaz` no hace nada si `solidoCapazMesh` es `null`, el modo simplemente
    // queda activo para cuando SÍ se calcule).
    var btnExplosionToolbar = document.getElementById("sandbox-tb-explosion");
    btnExplosionToolbar.addEventListener("click", function () {
      alternarVistaExplosionada();
      btnExplosionToolbar.classList.toggle("active", vistaExplosionadaActiva);
    });
  }

  function open(opts) {
    // Diagnóstico (2026-08-16, a petición explícita): confirma desde DevTools (F12 → Console) que
    // el código que se está ejecutando de verdad es esta versión, con materiales ArchViz y bordes --
    // no es una comprobación funcional, solo trazabilidad frente a caché del navegador.
    console.log("[Sandbox PBR] Renderizando volúmenes con materiales ArchViz v2");
    opts = opts || {};
    teardown();
    overlayEl.classList.add("open");
    loadingEl.hidden = false;
    onGenerarCallback = typeof opts.onGenerar === "function" ? opts.onGenerar : null;
    parcelaOrigenLat = opts.lat != null ? opts.lat : null;
    parcelaOrigenLon = opts.lon != null ? opts.lon : null;
    // Referencia catastral + restauración de límites urbanísticos guardados (2026-08-17, Fase A de
    // normativa): ANTES de `construirHudUrbanismo()` (más abajo), que lee `limitesUrbanisticos` para
    // rellenar los campos del panel al crearlos.
    referenciaCatastralActual = opts.referenciaCatastral || null;
    // "Generar 2 opciones" necesita `ciudad` para el mismo campo que ya rellena el resto del flujo
    // (`proyecto.ciudad`, zona CTE/densidad urbana) -- capturado aquí porque este botón no pasa por
    // `entrevista.js` (llama a `/api/generar-opciones` directamente), así que no hay otro sitio donde
    // ya viva este dato dentro del propio Sandbox.
    ciudadDetectadaActual = opts.ciudadDetectada || "";
    // Reinicio explícito (2026-08-17, corrección junto al perfil de ejemplo -- `teardown()` nunca
    // limpiaba `limitesUrbanisticos`, así que abrir una segunda parcela en la misma sesión sin recargar
    // la página heredaba en silencio los límites que el arquitecto hubiera tocado a mano en la
    // ANTERIOR): sin este reinicio, `aplicarPerfilEjemploYAutocalcular()` (más abajo) vería campos ya
    // "definidos" y nunca aplicaría el perfil de ejemplo para la parcela nueva, ni avisaría de que esos
    // números eran de otro sitio. `restaurarLimitesUrbanisticosLocal()`, justo debajo, ya se encarga de
    // rellenar lo que sí sea real de ESTA parcela si lo hubiera.
    limitesUrbanisticos.ocupacion_maxima_pct = null; limitesUrbanisticos.retranqueos_m = null;
    limitesUrbanisticos.edificabilidad_maxima = null; limitesUrbanisticos.plantas_maximas = null;
    limitesUrbanisticos.altura_maxima_m = null;
    restaurarLimitesUrbanisticosLocal();
    var tieneParcelaReal = opts.lat != null && opts.lon != null;
    metaEl.textContent = tieneParcelaReal
      ? "Sobre la parcela real seleccionada en el Paso 0"
      : "Sin parcela real seleccionada — terreno genérico (vuelve al Paso 0 para elegir una)";
    // Cabecera dinámica (2026-08-17, encargo explícito -- "en lugar de 'Lienzo libre', la cabecera
    // debe reflejar la RC/dirección de la parcela real activa"): "Lienzo libre" se queda como
    // fallback SOLO para el caso sin parcela real (Paso 0 omitido), que es exactamente lo que ese
    // nombre describe -- un lienzo sin referencia real todavía. Con referencia catastral real se
    // antepone "Parcela " + RC, con el municipio detectado como coletilla si lo hay (mismo criterio
    // best-effort que `ciudadDetectada` en el resto del flujo: nunca se inventa si no llegó).
    if (titleEl) {
      if (referenciaCatastralActual) {
        titleEl.textContent = "Parcela " + referenciaCatastralActual +
          (opts.ciudadDetectada ? " — " + opts.ciudadDetectada : "");
      } else if (tieneParcelaReal) {
        titleEl.textContent = "Parcela sin referencia catastral";
      } else {
        titleEl.textContent = "Lienzo libre";
      }
    }
    // Texto del overlay de carga: sin parcela real no hay nada que descargar (el terreno orgánico
    // es puramente local), así que no hace falta el mensaje de "cargando entorno".
    if (loadingTextoEl) {
      loadingTextoEl.textContent = tieneParcelaReal
        ? "Cargando parcela…"
        : "Preparando el lienzo…";
    }

    scene = new THREE.Scene();
    session = createViewerSession({
      mount: mount,
      // Mismo criterio que `#viewer-3d`/`viewer-edificio.js`: alpha true, el degradado de cielo lo
      // pinta el propio CSS del contenedor (`#viewer-sandbox`), no una cúpula 3D aparte. `clearAlpha: 0`
      // (2026-08-17, corrección de estética -- ver el comentario grande en `presentationRendererSettings`,
      // `viewer-materials.js`): sin esto el canvas quedaba OPACO con un relleno plano de `clearColor`, y el
      // degradado atmosférico de `#viewer-sandbox` (ver `style.css`) nunca llegaba a verse -- era el "azul/
      // gris plano" reportado. `clearColor` se deja en un tono oscuro neutro como respaldo (compositing con
      // alpha 0 en teoría lo hace irrelevante, pero cubre cualquier borde de antialiasing que no promedie a
      // alpha puro).
      renderer: presentationRendererSettings({ alpha: true, clearColor: 0x0d1117, clearAlpha: 0, toneMappingExposure: 1.1 }),
      // Vista isométrica/aérea de estudio (encargo explícito, 2026-08-16): posición y target fijos
      // aquí y reafirmados explícitamente más abajo (`controls.target.set` + `controls.update()`)
      // tras montar toda la escena, para que el primer fotograma ya salga centrado en el origen
      // local -- que es siempre el centro de la parcela, tenga o no coordenadas reales (ver
      // `construirPlanoOrtofoto`/`construirTerrenoOrganico`, ambos centrados en (0,0,0)).
      camera: { fov: 50, near: 0.1, far: 2000, position: new THREE.Vector3(45, 38, 45) },
      controls: {
        target: new THREE.Vector3(0, 0, 0), enableDamping: true, dampingFactor: 0.05,
        // 550 (subido de 400, encargo explícito 2026-08-16): el mosaico de ortofoto puede llegar a
        // cubrir ~580 m de lado en total (~290 m de radio) -- con el techo anterior de 400 el
        // encuadre automático de más abajo no podía alejarse lo suficiente para mostrarlo completo.
        minDistance: 5, maxDistance: 550,
        // Math.PI/2.1 (~85.7°), no 90°: evita que la cámara pueda meterse por debajo del horizonte
        // del terreno y quedar a ras de suelo mirando de canto -- exactamente el encargo explícito.
        maxPolarAngle: Math.PI / 2.1,
        enablePan: true, screenSpacePanning: true, zoomSpeed: 0.8
      }
    });
    renderer = session.renderer; camera = session.camera; controls = session.controls;

    // Encuadre inicial de respaldo (posición fija, sustituida por `encuadrarCamaraAContenido()` en
    // cuanto se añade el terreno/ground unas líneas más abajo): evita un primer fotograma con la
    // cámara en el origen absoluto (0,0,0) mientras la escena todavía no tiene nada que encuadrar.
    camera.position.set(45, 38, 45);
    controls.target.set(0, 0, 0);
    controls.update();

    // Gizmo de norte + barra de herramientas (2026-08-16, navegación fluida): creados una vez por
    // `open()`, igual que el panel de plantas/brújula de `viewer-edificio.js` -- `teardown()` los
    // retira del DOM.
    construirGizmoNorte();
    construirBarraHerramientas();
    construirHudUrbanismo();
    actualizarUrbanismo(); // estado inicial: sin volúmenes, sin parcela todavía (llega más abajo si hay coordenadas)
    // Programa de Necesidades (2026-08-17, PRD aprobado): panel independiente del HUD de urbanismo,
    // montado sobre el mismo `mount` -- restaura su propio estado guardado para esta referencia
    // catastral (si la hay) y arranca sin contexto de Sólido Capaz (`actualizarSolidoCapaz` lo rellena
    // en cuanto el arquitecto pulse "Calcular sólido capaz").
    ProgramaNecesidades.montar(mount, referenciaCatastralActual, actualizarCapaExcesoPrograma);

    // Entorno PBR (2026-08-16): sin `scene.environment`, el vidrio con `transmission` de
    // `createPhysicalGlassMaterial` no tiene nada que refractar/reflejar y se ve como un cristal
    // plano sin profundidad -- mismo criterio ya usado en `viewer-edificio.js`.
    envTexture = buildPBREnvironment(renderer);
    scene.environment = envTexture;

    // Oclusión ambiental sutil vía HemisphereLight (2026-08-17, pedido explícito -- "SSAO/HemisphereLight"
    // como alternativas equivalentes: un verdadero SSAO necesitaría postprocesado (`EffectComposer` +
    // `SSAOPass`), una pieza nueva de infraestructura que este visor no tiene y que se sale de alcance de
    // un pase de estética; `HemisphereLight` ya lo ofrece el propio helper, así que se ajusta EN VEZ de
    // añadir un pipeline nuevo). `skyColor`/`groundColor` alineados con el degradado "estudio" oscuro y
    // el nuevo gris técnico del terreno (antes eran el cielo azul claro/tierra clara por defecto, pensados
    // para el degradado diurno anterior) -- el relleno ahora se siente parte del mismo ambiente oscuro en
    // vez de aportar luz de "mediodía" contradictoria.
    var fill = createFillLights({
      ambientColor: 0x141A20, ambientIntensity: 0.3,
      skyColor: 0x3A4A56, groundColor: 0x2E322F, hemisphereIntensity: 0.55
    });
    scene.add(fill.ambient);
    scene.add(fill.hemisphere);
    // shadowHalfSize inicial = 150: el radio real de `crearGroundNeutro()`/`construirTerrenoOrganico()`
    // que se añaden dos líneas más abajo -- `ajustarFrustumSombra()`, llamada justo después de
    // añadirlos, ya lo recalcula sobre el `Box3` real de la escena; este valor solo cubre el
    // instante entre crear la luz y añadir el terreno.
    sunLight = createSunLight({
      color: 0xFFF8F0, intensity: 1.2, shadowHalfSize: 150,
      // shadowRadius: bajado de 8 a 2 en el encargo anterior ("sombras nítidas", el borde quedaba
      // difuminado como "mancha"); subido a 3 en este ("sombras suaves") -- valor de compromiso entre
      // los dos encargos: sigue leyendo como borde de sombra limpio, no vago, pero con un extremo lo
      // bastante suavizado como para no verse serrado/duro a esta escala. Ni el extremo original (8,
      // demasiado difuso) ni el 2 anterior (algo más duro de lo que "suaves" pide).
      shadowMapSize: 4096, shadowNear: 1, shadowFar: 650, shadowBias: -0.0005, shadowNormalBias: 0.02, shadowRadius: 3
    });
    scene.add(sunLight);
    scene.add(sunLight.target);
    colocarSol(135, 55); // sol de estudio por defecto -- se sustituye por la posición real más abajo si hay coordenadas

    // Terreno técnico único, con o sin parcela real (2026-08-17, ver el comentario grande junto a
    // `crearGroundNeutro`, más arriba, sobre por qué el relieve orgánico anterior para el caso "sin
    // parcela real" deja de usarse aquí). Siempre plano (`funcionAlturaTerreno` a cero) -- con parcela
    // real porque encima va una ortofoto real (una imagen plana no puede alinearse con relieve, PRD
    // §14 de la mejora original), y sin parcela real porque un "site plan" técnico ES plano por
    // definición, no un paisaje.
    funcionAlturaTerreno = function () { return 0; };
    scene.add(crearGroundNeutro());
    // Zócalo de maqueta física (2026-08-16, docs/prd/2026-08-16-presets-progreso-y-zocalo-sandbox.md):
    // mismo radio (150 m) que usa por defecto `crearGroundNeutro` -- `alturaSuperior` único ahora (antes
    // había un valor más bajo específico para las hondonadas del relieve orgánico, ya no aplica al
    // usarse siempre el mismo terreno plano).
    scene.add(construirZocaloTerreno(150, { alturaSuperior: -0.4 }));

    // Sincronización estricta con el Paso 0 (arreglo crítico, 2026-08-16 -- "al pasar al Sandbox se
    // pierde el objeto de parcela"): si `entrevista.js` ya resolvió una geometría real de Catastro
    // segundos antes (Paso 0), se dibuja YA -- contorno + pad extruido + HUD -- sin esperar la
    // respuesta de `pedirEntorno3DPorCoordenadas()` de más abajo. Esa llamada de red puede tardar más
    // que su propio límite de tiempo (Catastro + Overpass en serie, ver `TIMEOUT_ENTORNO_3D_MS` en
    // `viewer-terreno.js`), y antes ESA era la única vía para tener parcela real en el Sandbox -- si
    // no llegaba a tiempo, se quedaba el disco neutro liso y el HUD decía "sin datos reales de
    // parcela" aunque el Paso 0 SÍ hubiera encontrado la parcela. La llamada de red sigue haciéndose
    // más abajo (trae colindantes reales y ortofoto, que esto no trae), pero ya no es la única fuente.
    var geometriaInicial = opts.geometriaParcela && opts.geometriaParcela.coordenadas &&
      opts.geometriaParcela.coordenadas.length >= 3 ? opts.geometriaParcela : null;
    var contornoParcelaYaDibujado = false;
    if (geometriaInicial) {
      var centroInicial = { lat: opts.lat, lon: opts.lon };
      parcelaSuperficieM2 = geometriaInicial.superficie_m2 || null;
      parcelaPoligonoLocal = geometriaInicial.coordenadas.map(function (par) {
        var m = metrosEsteNorteDesde(centroInicial.lat, centroInicial.lon, par[1], par[0]);
        return rotarAEjesLocales(m.este, m.norte, 0);
      });
      var contornoInicial = construirContornoParcela(geometriaInicial, centroInicial, new THREE.Vector3(0, 0, 0), 0);
      if (contornoInicial) scene.add(contornoInicial);
      var padInicial = construirPadParcela(parcelaPoligonoLocal);
      if (padInicial) scene.add(padInicial);
      contornoParcelaYaDibujado = true;
      // Perfil de ejemplo + sólido capaz automático (2026-08-17, Fase 1, encargo explícito): la
      // parcela real ya tiene polígono aquí -- este es uno de los dos únicos puntos de `open()` donde
      // eso pasa (ver comentario grande junto a `aplicarPerfilEjemploYAutocalcular`). Sustituye a la
      // llamada simple a `actualizarUrbanismo()` de antes -- esa función ya la incluye.
      aplicarPerfilEjemploYAutocalcular();
      // La parcela ya es visible -- el overlay de carga desaparece YA, sin esperar a colindantes ni
      // ortofoto (encargo explícito, 2026-08-17): esos siguen cargando en segundo plano más abajo.
      loadingEl.hidden = true;
    }

    // Primer encuadre real (encargo explícito, 2026-08-16): con el terreno ya en la escena, la
    // cámara y el frustum de sombra se calculan sobre su tamaño real -- sustituye la posición fija
    // de más arriba. Con parcela real esto se recalcula otra vez cuando lleguen los colindantes y la
    // ortofoto (más abajo), que normalmente son más grandes que el terreno neutro inicial.
    encuadrarCamaraAContenido();
    ajustarFrustumSombra();
    ajustarLimitesCamara();
    // Con geometría real ya dibujada, el encuadre general de arriba queda dominado por el disco neutro
    // de 150 m -- la parcela real (normalmente unas pocas decenas de metros) se ve diminuta en el
    // centro, dando la sensación de "plano" que se reportó aunque ya haya un pad/contorno real. Este
    // segundo encuadre, ceñido solo al polígono real, es la "perspectiva 3D volumétrica de inmediato"
    // pedida explícitamente -- el encuadre general vuelve a aplicarse al final del pipeline de abajo
    // (colindantes + ortofoto), cuando de verdad hace falta ver más allá de la propia parcela.
    if (geometriaInicial) encuadrarCamaraAPoligono(parcelaPoligonoLocal);

    if (tieneParcelaReal) {
      // En paralelo, no bloqueante -- nunca gatea el overlay de carga de arriba (ver `viewer-terreno.js`,
      // `TIMEOUT_NORMATIVA_MADRID_MS`, sobre por qué esta consulta puede tardar bastante más que el resto
      // del pipeline sin que eso deba retrasar nada más de la apertura del Sandbox).
      pedirNormativaUrbanisticaPunto(opts.lat, opts.lon).then(function (datos) {
        if (!scene) return; // Sandbox ya cerrado cuando llegó la respuesta -- no tocar un HUD que ya no existe
        renderizarNormativaMadrid(datos);
      });

      // Colindantes reales + ortofoto (2026-08-17, corrección en caliente -- "se queda bloqueado al
      // 10%"): la parcela YA está en pantalla en este punto -- síncronamente si el Paso 0 trajo su
      // geometría (`geometriaInicial`, más arriba, que ya ocultó el overlay), o se dibuja aquí mismo si
      // no. A partir de aquí todo es contexto ADICIONAL (colindantes de OSM + foto satélite), así que
      // corre en segundo plano de verdad -- nunca vuelve a mostrar el overlay ni bloquea el visor, tenga
      // o no éxito. `timeoutEntorno`: 8s cuando ya había geometría previa (solo se espera contexto, no
      // la parcela en sí -- encargo explícito), el margen normal (45s) cuando esta llamada es la única
      // fuente posible de la parcela.
      var timeoutEntorno = geometriaInicial ? TIMEOUT_ENTORNO_CON_GEOMETRIA_PREVIA_MS : undefined;
      pedirEntorno3DPorCoordenadas(opts.lat, opts.lon, timeoutEntorno).then(function (body) {
        // Si no había geometría previa del Paso 0, esta respuesta es la única fuente posible de la
        // parcela -- el overlay se oculta aquí (éxito o "sin datos"), sin esperar a colindantes/ortofoto,
        // que siguen abajo en segundo plano. Con geometría previa el overlay ya se ocultó antes.
        if (!contornoParcelaYaDibujado) loadingEl.hidden = true;
        if (!scene || !body || !body.disponible) return;
        // Al recibir datos reales de la parcela (encargo explícito, 2026-08-16): refuerza que los
        // volúmenes que ya hubiera (creados antes de que esta respuesta llegase) sigan en ArchViz.
        aplicarMaterialesArchVizATodos();
        var centro = body.centro;

        // Contorno + pad real de parcela (2026-08-16, docs/prd/2026-08-16-sandbox-navegacion-
        // profesional-y-lindes.md): `body.geometria_parcela` es aditivo -- `null` cuando Catastro no
        // tenía parcela exacta en esas coordenadas (best effort, sin aviso de error, mismo criterio que
        // colindantes). Solo se dibuja aquí si el Paso 0 NO había mandado ya una geometría (ver
        // `geometriaInicial`/`contornoParcelaYaDibujado` más arriba) -- evita duplicar la línea/pad
        // cuando las dos fuentes coinciden (lo normal), y sirve de respaldo real si el Sandbox se abrió
        // sin pasar por el Paso 0 pero esta consulta sí encuentra parcela.
        //
        // Se procesa ANTES que los colindantes (2026-08-17, reordenado a propósito, PRD edificio-
        // existente-y-vecinos): la clasificación "¿este edificio de Overpass está dentro de mi
        // parcela?" necesita `parcelaPoligonoLocal` ya resuelto -- si el Paso 0 no trajo geometría
        // previa, este es el único sitio donde se calcula.
        if (!contornoParcelaYaDibujado) {
          var contorno = construirContornoParcela(body.geometria_parcela, centro, new THREE.Vector3(0, 0, 0), 0);
          if (contorno) scene.add(contorno);

          // Datos reales para el HUD de urbanismo (2026-08-16, docs/prd/2026-08-16-conexion-3d-
          // hallazgos-motor-reglas.md): mismo criterio "aditivo, best-effort" que el contorno visual de
          // arriba -- si `geometria_parcela` es `null` (Catastro sin parcela exacta en el punto), el HUD
          // se queda sin datos y lo dice explícitamente (`actualizarUrbanismo`), nunca inventa un 0.
          // Reutiliza la MISMA proyección (`metrosEsteNorteDesde`/`rotarAEjesLocales`, `centro` como
          // referencia común) que ya usa `construirContornoParcela`, para que el polígono local del
          // chequeo de retranqueos esté exactamente alineado con la línea amarilla que ya se ve en pantalla.
          if (body.geometria_parcela && body.geometria_parcela.coordenadas && body.geometria_parcela.coordenadas.length >= 3) {
            parcelaSuperficieM2 = body.geometria_parcela.superficie_m2 || null;
            parcelaPoligonoLocal = body.geometria_parcela.coordenadas.map(function (par) {
              var m = metrosEsteNorteDesde(centro.lat, centro.lon, par[1], par[0]);
              return rotarAEjesLocales(m.este, m.norte, 0);
            });
            var pad = construirPadParcela(parcelaPoligonoLocal);
            if (pad) scene.add(pad);
            // Perfil de ejemplo + sólido capaz automático (2026-08-17, Fase 1, encargo explícito):
            // segundo (y último) punto de `open()` donde `parcelaPoligonoLocal` queda resuelto -- solo
            // se llega aquí cuando el Paso 0 NO trajo geometría previa (`contornoParcelaYaDibujado`
            // seguía en `false`), así que Path A (más arriba) todavía no lo había aplicado.
            aplicarPerfilEjemploYAutocalcular();
          }
        }

        // Filtro por radio de contexto (2026-08-17, ajustado a 80m -- ver `RADIO_UTIL_COLINDANTES_M`):
        // Overpass (`around:180` en el backend) devuelve un edificio si TIENE UN nodo dentro de 180 m,
        // aunque el resto de su fachada esté mucho más lejos -- un edificio grande cerca del borde del
        // radio de contexto puede llegar con media planta fuera. Se incluye si su centroide cae dentro
        // del radio, O si su footprint intersecta la parcela (`poligonoParcela`, ver comentario junto a
        // `filtrarColindantesPorRadio`); nunca se recorta un edificio real a la mitad. Se añaden a la
        // escena YA construida, sin recrear nada de lo que ya se ve (encargo explícito: "que la parcela
        // aparezca primero y los edificios se añadan cuando estén listos").
        var colindantesFiltrados = filtrarColindantesPorRadio(
          body.edificios_colindantes, centro, RADIO_UTIL_COLINDANTES_M, parcelaPoligonoLocal
        );
        // "X edificios en contexto · X m² construidos" (2026-08-17, encargo explícito): se calcula
        // sobre el mismo conjunto YA filtrado, se muestre o no haya ninguno (el propio helper oculta la
        // línea si `cantidad` es 0).
        actualizarResumenContextoEdificios(calcularResumenContextoEdificios(colindantesFiltrados, centro));
        if (colindantesFiltrados.length) {
          // `parcelaPoligonoLocal` (2026-08-17, PRD edificio-existente-y-vecinos, aprobado): si hay
          // polígono real de parcela, `construirEdificiosColindantes` clasifica cada edificio y pinta
          // el/los que caen dentro con `MAT_EDIFICIO_EN_PARCELA` (+ borde) en vez del gris de vecino.
          var grupoColindantes = construirEdificiosColindantes(
            colindantesFiltrados, centro, new THREE.Vector3(0, 0, 0), 0, parcelaPoligonoLocal
          );
          scene.add(grupoColindantes);
          if (parcelaPoligonoLocal) {
            hayEdificioEnParcela = grupoColindantes.children.some(function (m) { return m.userData.enParcela; });
          }
        } else if (parcelaPoligonoLocal && !huboFalloOverpass(body.avisos)) {
          // Sin ningún edificio en el radio útil, Y Overpass sí respondió (no es el caso de abajo) --
          // con parcela real conocida, eso SÍ es "solar vacío" de verdad, no un fallo de red (PRD §6:
          // los dos casos no deben verse iguales).
          hayEdificioEnParcela = false;
        }
        actualizarUrbanismo();

        var posSol = posicionSolar(centro.lat, centro.lon, new Date());
        colocarSol(posSol.azimut_grados, posSol.elevacion_grados);

        // Ortofoto: último dato real que falta por llegar. Puramente cosmética a partir de aquí -- ya
        // no gatea el overlay de carga (encargo explícito, 2026-08-17: antes el overlay esperaba a
        // esto entero, que es justo lo que hacía sentir "bloqueado" el visor).
        construirMosaicoOrtofoto(centro.lat, centro.lon).then(function (mosaico) {
          if (!scene) return;
          // `norteGrados = 0`: en Sandbox todavía no hay ningún plano con orientación propia -- los
          // ejes locales de la escena son directamente Este/Norte reales (ver `_entorno_3d_para` en
          // app.py, mismo criterio).
          // `y = 0.03` (2026-08-17, corrección explícita -- "debe estar exactamente a Y=0"): la base
          // de los edificios extruidos (`extrudeFootprint`, `viewer-geometry.js`) siempre arranca en
          // Y=0 por diseño; con los 2cm que tenía antes, esa franja de la base de cada edificio quedaba
          // tapada por la foto y se leía como "el edificio flota". PROBADO EN VIVO en 3 pasos: Y=0 exacto
          // primero -- en zonas densas (muchos edificios colindantes reales) produce ACNÉ DE SOMBRA real
          // (franjas grises parpadeantes en forma de estrella sobre la ortofoto, capturado con Chrome);
          // Y=0.01 seguía sin ser suficiente margen; Y=0.05 lo quitaba del todo. El sospechoso real es
          // `shadowNormalBias: 0.02` del sol de este mismo archivo (más abajo, `createSunLight`) --
          // geometría a menos de ese margen del plano que recibe su propia sombra puede autosombrearse.
          // 0.03 queda con margen cómodo por encima de ese bias, sigue siendo indistinguible de "a ras
          // de suelo" a la escala de este visor (decenas-cientos de metros).
          // `0.45` de opacidad (Fase 2, encargo explícito -- "atenúa el terreno satelital... base de
          // maqueta arquitectónica"): antes 1 (opaca), tapaba del todo la rejilla técnica de
          // `crearGroundNeutro()` -- exactamente lo contrario de la estética CAD/BIM que pide este
          // encargo. Atenuada en vez de quitada del todo: sigue dando contexto real de la parcela (el
          // motivo por el que se añadió, 2026-08-16, a petición explícita de Pablo), pero ya no
          // domina sobre la base técnica gris/rejilla, que ahora se ve A TRAVÉS de la foto.
          scene.add(construirPlanoOrtofoto(mosaico, new THREE.Vector3(0, 0, 0), 0, 0.03, 0.45));
        }).catch(function () { /* mosaico best-effort: sin ortofoto real, el suelo neutro sigue ahí debajo */ })
          .then(function () {
            // Encuadre final (encargo explícito, 2026-08-16): se hace UNA sola vez aquí, con todo lo
            // que iba a llegar ya cargado (colindantes + ortofoto, o solo colindantes si el mosaico
            // falló) -- no en cada pieza por separado, para no mover la cámara dos veces seguidas
            // delante del usuario. Ya no toca el overlay -- lleva oculto desde que la parcela apareció.
            if (!scene) return;
            encuadrarCamaraAContenido();
            ajustarFrustumSombra();
            ajustarLimitesCamara();
          });
      }).catch(function () {
        // red caída / timeout / endpoint no disponible: se queda con el terreno neutro (o con la
        // parcela real ya dibujada desde el Paso 0, si la había) y el sol de estudio -- nunca se
        // reintenta pedir lo que ya se tenía.
        if (!contornoParcelaYaDibujado) loadingEl.hidden = true;
      });
    } else {
      loadingEl.hidden = true; // sin parcela real no hay ninguna descarga que esperar
    }

    raycaster = new THREE.Raycaster();
    session.addDomListener("click", alClicEnMount);
    session.addDomListener("dblclick", onDblClickRecenter);
    session.start(function (now) {
      avanzarTweenCamara(now);
      controls.update();
      renderer.render(scene, camera);
      actualizarEtiquetaAlturaSolidoCapaz();
    });

    actualizarBotonGenerar();
  }

  function teardown() {
    if (session) { session.dispose(); session = null; }
    if (scene) { disposeSceneResources(scene); scene = null; }
    if (envTexture) { envTexture.dispose(); envTexture = null; }
    volumenes = [];
    seleccionado = null;
    panelEl.hidden = true;
    renderer = null; camera = null; controls = null; sunLight = null; raycaster = null;
    onGenerarCallback = null;
    camTween = null;
    ["sandbox-compass", "sandbox-toolbar", "sandbox-hud-urbanismo"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el && el.parentNode) el.parentNode.removeChild(el);
    });
    hudUrbanismoEl = null; hudMetricasEl = null; normativaMadridEl = null; avisoSinEdificioEl = null;
    resumenContextoEdificiosEl = null;
    // Perfil de ejemplo: nunca debe sobrevivir a la parcela para la que se aplicó -- la siguiente
    // `open()` empieza limpia, sin badge ni referencias a inputs que `teardown()` ya retiró del DOM.
    campoLimOcupacionEl = null; campoLimAlturaEl = null; campoLimRetranqueosEl = null;
    campoLimEdificabilidadEl = null; campoLimPlantasEl = null; badgeLimitesEjemploEl = null;
    limitesSonEjemplo = false;
    // El propio mesh ya se retira de la escena al vaciarse `scene` en `teardown()`/`disposeSceneResources`
    // -- aquí solo se limpia la referencia, para no arrastrarla a la siguiente apertura del Sandbox.
    solidoCapazMesh = null;
    // Vista explosionada (Fase 3): nunca se arrastra de una parcela a la siguiente -- cada `open()`
    // arranca en "Volumen Total" (mismo criterio que el resto del estado efímero del Sandbox, p. ej.
    // `seleccionado`). El botón de la barra de herramientas se recrea sin clase `.active` en cada
    // `construirBarraHerramientas()`, así que solo hace falta resetear el booleano aquí.
    vistaExplosionadaActiva = false;
    btnSolidoCapazEl = null; estadoSolidoCapazEl = null; resultadoSolidoCapazEl = null;
    // La etiqueta de altura es un elemento ESTÁTICO del HTML (no se crea/destruye con la escena, ver
    // `index.html`) -- sin este `hidden` explícito se quedaría pegada en su última posición de
    // pantalla, encima de un `#sandbox-mount` vacío, hasta el primer fotograma de la próxima `open()`.
    if (etiquetaAlturaSolidoCapazEl) etiquetaAlturaSolidoCapazEl.hidden = true;
    // Programa de Necesidades: se desmonta entero (su propio DOM + estado interno) -- la siguiente
    // `open()` lo vuelve a montar desde cero con la referencia catastral de la parcela nueva.
    ProgramaNecesidades.desmontar();
    referenciaCatastralActual = null;
    parcelaSuperficieM2 = null; parcelaPoligonoLocal = null; ultimoVolumenTocado = null;
    parcelaOrigenLat = null; parcelaOrigenLon = null;
    hayEdificioEnParcela = null;
    funcionAlturaTerreno = function () { return 0; };
    actualizarBotonGenerar();
  }

  function close() {
    teardown();
    overlayEl.classList.remove("open");
  }

  // --- Cableado (una sola vez, igual que closeBtn/walkBtn en viewer-edificio.js) ------------------

  btnCerrar.addEventListener("click", close);

  btnAnadir.addEventListener("click", function () {
    if (!scene) return;
    var vol = crearVolumen(volumenes.length);
    volumenes.push(vol);
    ultimoVolumenTocado = vol; // atribución del exceso agregado (PRD §7): el volumen recién añadido
    seleccionarVolumen(volumenes.length - 1); // ya llama a `actualizarUrbanismo()` internamente
    actualizarBotonGenerar();
    // Reencuadre (encargo explícito, 2026-08-16): los volúmenes se colocan en fila (`x = indice *
    // 16`, ver `crearVolumen`), así que a partir de unos pocos pueden salirse del encuadre inicial
    // de la parcela -- se recalcula solo al añadir/borrar, no en cada arrastre de slider (eso
    // movería la cámara mientras el usuario está ajustando tamaño/rotación, que es peor experiencia).
    encuadrarCamaraAContenido();
    ajustarFrustumSombra();
    ajustarLimitesCamara();
  });

  btnBorrarVolumen.addEventListener("click", function () {
    if (seleccionado == null || !scene) return;
    var vol = volumenes[seleccionado];
    scene.remove(vol.mesh);
    vol.mesh.geometry.dispose();
    // `vol.mesh.material` en este momento es el resaltado de selección compartido
    // (MAT_VOLUMEN_SELECCIONADO, reutilizado para lo que se seleccione cada vez, ver
    // `seleccionarVolumen`) -- se liberan sus materiales PROPIOS (`materialesNormales`, clonados en
    // `crearMaterialesVolumen`), nunca el compartido, o la siguiente selección se quedaría sin
    // material.
    vol.materialesNormales.forEach(function (m) { m.dispose(); });
    // `vol.bordes.material` es MAT_BORDES, compartido por los bordes de TODOS los volúmenes (no hay
    // estado por volumen que justifique clonarlo) -- solo se libera su geometría propia.
    vol.bordes.geometry.dispose();
    // Si el volumen borrado era el atribuido al exceso agregado (PRD §6, caso límite), deja de haber
    // uno concreto que señalar -- el HUD puede seguir en rojo si el resto de volúmenes ya suma de
    // sobra, pero ningún volumen se resalta por ESE motivo hasta el siguiente cambio.
    if (ultimoVolumenTocado === vol) ultimoVolumenTocado = null;
    volumenes.splice(seleccionado, 1);
    seleccionarVolumen(null); // ya llama a `actualizarUrbanismo()` internamente
    actualizarBotonGenerar();
    // Mismo criterio que al añadir: el radio real de la escena puede reducirse al borrar el
    // volumen más alejado -- se reencuadra para no dejar la cámara más alejada de lo necesario.
    encuadrarCamaraAContenido();
    ajustarFrustumSombra();
    ajustarLimitesCamara();
  });

  // Los 4 sliders comparten el mismo cierre de urbanismo (2026-08-16, docs/prd/2026-08-16-conexion-
  // 3d-hallazgos-motor-reglas.md): tocar cualquiera de largo/ancho/plantas/rotación marca este volumen
  // como el atribuido a un posible exceso agregado (PRD §7) Y recalcula el HUD + los materiales de
  // TODOS los volúmenes (el retranqueo de otros volúmenes no cambia, pero recalcularlos todos es
  // barato -- son solo números, sin llamada de red -- y más simple que rastrear cuáles hace falta
  // tocar). No mueve la cámara (a diferencia de añadir/borrar): un slider es un ajuste fino, no un
  // cambio de composición de la escena.
  inputLargo.addEventListener("input", function () {
    if (seleccionado == null) return;
    var vol = volumenes[seleccionado];
    vol.largo = parseFloat(inputLargo.value);
    valorLargo.textContent = vol.largo.toFixed(1) + " m";
    actualizarGeometriaVolumen(vol);
    ultimoVolumenTocado = vol;
    actualizarUrbanismo();
  });
  inputAncho.addEventListener("input", function () {
    if (seleccionado == null) return;
    var vol = volumenes[seleccionado];
    vol.ancho = parseFloat(inputAncho.value);
    valorAncho.textContent = vol.ancho.toFixed(1) + " m";
    actualizarGeometriaVolumen(vol);
    ultimoVolumenTocado = vol;
    actualizarUrbanismo();
  });
  inputPlantas.addEventListener("input", function () {
    if (seleccionado == null) return;
    var vol = volumenes[seleccionado];
    vol.plantas = parseInt(inputPlantas.value, 10);
    valorPlantas.textContent = String(vol.plantas);
    actualizarGeometriaVolumen(vol);
    ultimoVolumenTocado = vol;
    actualizarUrbanismo();
  });
  inputRotacion.addEventListener("input", function () {
    if (seleccionado == null) return;
    var vol = volumenes[seleccionado];
    vol.rotacionDeg = parseInt(inputRotacion.value, 10);
    valorRotacion.textContent = vol.rotacionDeg + "°";
    vol.mesh.rotation.y = THREE.MathUtils.degToRad(vol.rotacionDeg);
    // La rotación no cambia ocupación/edificabilidad (misma huella, solo girada), pero SÍ puede
    // cambiar si el volumen invade el retranqueo -- se recalcula igual que los demás sliders.
    ultimoVolumenTocado = vol;
    actualizarUrbanismo();
  });

  // "Exportar/Generar plantas a partir del volumen dibujado" (encargo, Objetivo 3): el volumen
  // SELECCIONADO (o el primero si no hay ninguno seleccionado) se convierte en parámetros reales --
  // ver el docstring de cabecera de este archivo sobre qué es honesto prometer aquí y qué no.
  //
  // Segundo camino sin volumen (2026-08-17, corrección: `motivoBloqueoGenerar`/`actualizarBotonGenerar`
  // ya permiten llegar aquí con la huella del Sólido Capaz calculado y NINGÚN volumen dibujado a mano
  // -- antes era imposible, el botón se quedaba deshabilitado). Cuando no hay volumen, la huella/plantas
  // salen del propio `solidoCapazMesh` en vez de inventar un volumen que no existe.
  btnGenerar.addEventListener("click", function () {
    if (!onGenerarCallback) return;
    if (!volumenes.length && !solidoCapazMesh) return; // el botón debería estar deshabilitado -- red de seguridad, no un camino esperado
    // Validación (2026-08-17, encargo explícito): sin Sólido Capaz calculado o sin viviendas objetivo
    // en el Programa de Necesidades no hay nada real que generar -- se avisa en el sitio y se corta
    // aquí, antes de tocar el backend ni de llamar a `onGenerarCallback`.
    var motivo = motivoBloqueoGenerar();
    if (motivo) { mostrarBloqueoGenerar(motivo); return; }
    // Reconciliación con el backend (2026-08-16, PRD §7.6): fire-and-forget, se dispara ANTES pero
    // nunca se espera -- `onGenerarCallback` de abajo se llama exactamente igual y en el mismo
    // instante que antes de este PRD, la llamada de red es puramente informativa (consola).
    reconciliarConBackend();
    var vol = volumenes.length ? volumenes[seleccionado != null ? seleccionado : 0] : null;
    // `getEstado()` no puede devolver `null` aquí: exige el panel montado, y el panel solo se monta con
    // el Sandbox abierto (`open()`), que es el único sitio desde el que se puede llegar a este click.
    var estadoPrograma = ProgramaNecesidades.getEstado();
    onGenerarCallback({
      // Camino 1 (volumen a mano) si hay alguno; camino 2 (huella del propio Sólido Capaz) si no --
      // `motivoBloqueoGenerar()` ya garantiza que si `vol` es `null` entonces `solidoCapazMesh` existe
      // (es su primera condición de bloqueo).
      superficie_m2: vol
        ? Math.round(vol.largo * vol.ancho * 10) / 10
        : Math.round(areaPoligono(solidoCapazMesh.userData.poligonoFinal) * 10) / 10,
      // "Irregular -- decidido por ArchMuse" (mismo valor ya usado en `entrevista.js:VALOR_LABELS`) para
      // el camino 2: la huella del Sólido Capaz es el contorno de la parcela con o sin retranqueo, casi
      // nunca literalmente rectangular como sí lo es siempre un volumen dibujado a mano.
      forma: vol ? "rectangular" : "irregular_decidido_por_sistema",
      // Preferimos el nº de plantas fijado en el Programa de Necesidades (autorrellenado desde el propio
      // Sólido Capaz, o editado a mano) sobre el del volumen de boceto concreto o el de la propia malla:
      // son controles distintos, y el del Programa es el que de verdad representa la intención del
      // edificio completo, no solo de un volumen de boceto o del límite legal en bruto.
      plantas: (estadoPrograma && estadoPrograma.plantas != null)
        ? estadoPrograma.plantas
        : (vol ? vol.plantas : solidoCapazMesh.userData.plantasLegales),
      // Sólido Capaz persistente: adjunta el snapshot del Sólido Capaz ACTIVO, si lo hay -- independiente
      // del volumen concreto que se acaba de convertir en superficie/forma/plantas arriba. `null` si no
      // se calculó ninguno (comportamiento idéntico al de antes de este PRD).
      solido_capaz: serializarSolidoCapaz(),
      // Programa de Necesidades (2026-08-17, encargo explícito): "viviendas objetivo" + "% distribución
      // por tipología" viajan como `mix_viviendas`, el mismo campo que ya entiende `/api/generar`.
      mix_viviendas: mixViviendasDesdePrograma(estadoPrograma)
    });
  });

  // "Generar 2 opciones" (docs/prd/2026-08-17-optimizacion-generativa-multi-opcion.md, aprobado
  // 2026-08-17). A diferencia de "Generar plantas con IA", este botón NO pasa por `entrevista.js`
  // (no hay Modo Experto que editar: las 2 opciones se derivan automáticamente) -- llama directamente
  // a `/api/generar-opciones` con los mismos 3 parámetros base que ya usa `btnGenerar` más
  // `superficie_objetivo_m2` (la Construida objetivo del Programa de Necesidades) y los límites
  // urbanísticos ya rellenados en este mismo panel (`limitesUrbanisticos`). Mismo bloqueo previo que
  // "Generar plantas con IA" -- sin Sólido Capaz o sin Programa de Necesidades resuelto no hay nada
  // real que comparar.
  if (btnGenerarOpciones) btnGenerarOpciones.addEventListener("click", function () {
    if (!volumenes.length && !solidoCapazMesh) return; // red de seguridad, el botón debería estar deshabilitado
    var motivo = motivoBloqueoGenerar();
    if (motivo) { mostrarBloqueoGenerar(motivo); return; }

    var estadoPrograma = ProgramaNecesidades.getEstado();
    var superficieObjetivo = estadoPrograma && estadoPrograma.metricas
      ? estadoPrograma.metricas.construidaTotalObjetivoM2 : null;
    if (!superficieObjetivo) {
      mostrarBloqueoGenerar("Indica primero la Construida objetivo en el Programa de Necesidades.");
      return;
    }

    var vol = volumenes.length ? volumenes[seleccionado != null ? seleccionado : 0] : null;
    var cuerpo = {
      solar: {
        superficie_m2: vol ? Math.round(vol.largo * vol.ancho * 10) / 10
          : Math.round(areaPoligono(solidoCapazMesh.userData.poligonoFinal) * 10) / 10,
        forma: vol ? "rectangular" : "irregular",
        norte_grados: 0
      },
      edificio: {
        plantas: (estadoPrograma && estadoPrograma.plantas != null)
          ? estadoPrograma.plantas
          : (vol ? vol.plantas : solidoCapazMesh.userData.plantasLegales),
        altura_libre_m: 2.8, planta_baja_comercial: false
      },
      // Base para la superficie mínima de vivienda -- las 2 opciones sustituyen dorm_1/2/3 por su
      // propio reparto derivado (`derivar_mixes_alternativos`), pero conservan este mínimo.
      mix_viviendas: mixViviendasDesdePrograma(estadoPrograma),
      normativa: {
        ocupacion_maxima_pct: limitesUrbanisticos.ocupacion_maxima_pct || 70,
        retranqueos_m: limitesUrbanisticos.retranqueos_m || 3,
        edificabilidad_maxima: limitesUrbanisticos.edificabilidad_maxima,
        plantas_maximas: limitesUrbanisticos.plantas_maximas
      },
      // "plurifamiliar" siempre: esta acción existe precisamente para comparar mixes de VARIAS
      // viviendas -- no tiene sentido con las otras 2 tipologías (unifamiliar/rehabilitación no
      // aceptan un mix de tamaños que optimizar).
      proyecto: { ciudad: ciudadDetectadaActual, tipologia: "plurifamiliar" },
      superficie_objetivo_m2: superficieObjetivo
    };

    mostrarComparadorCargando();
    fetch("/api/generar-opciones", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo)
    })
      .then(function (resp) { return resp.json(); })
      .then(function (json) { mostrarComparadorOpciones(json.opciones || {}); })
      .catch(function () { mostrarComparadorError("Error de red al generar las opciones."); });
  });

  function formatoPctComparador(n) {
    return n == null ? "--" : n.toLocaleString("es-ES", { maximumFractionDigits: 1 }) + "%";
  }
  function formatoEurosComparador(n) {
    return n == null ? "--" : n.toLocaleString("es-ES", { maximumFractionDigits: 0 }) + " €";
  }

  function tarjetaOpcionHtml(etiqueta, op) {
    var titulo = etiqueta === "A" ? "Opción A — compacta (más viviendas, menores)" : "Opción B — amplia (menos viviendas, mayores)";
    if (op.error) {
      return (
        '<div class="comparador-opcion-card">' +
          "<h3>" + titulo + "</h3>" +
          '<p class="comparador-opcion-error">No se pudo generar: ' + op.error + "</p>" +
        "</div>"
      );
    }
    var mix = op.mix_viviendas || {};
    var m = op.metricas || {};
    return (
      '<div class="comparador-opcion-card">' +
        "<h3>" + titulo + "</h3>" +
        '<p class="comparador-opcion-mix">Mix: ' + (mix.dorm_1 || 0) + " · 1 dorm, " + (mix.dorm_2 || 0) +
          " · 2 dorm, " + (mix.dorm_3 || 0) + " · 3 dorm</p>" +
        '<div class="comparador-opcion-metricas">' +
          '<div class="comparador-opcion-metrica"><span>Repercusión zonas comunes</span><strong>' +
            formatoPctComparador(m.repercusion_zonas_comunes_pct) + "</strong></div>" +
          '<div class="comparador-opcion-metrica"><span>% fachada aprovechada</span><strong>' +
            formatoPctComparador(m.pct_fachada_aprovechada) + "</strong></div>" +
          '<div class="comparador-opcion-metrica"><span>Margen estimado</span><strong>' +
            formatoEurosComparador(m.margen_estimado && m.margen_estimado.margen_eur) + "</strong></div>" +
        "</div>" +
        '<button type="button" class="comparador-opcion-aplicar" data-proyecto-id="' + (op.proyecto_id || "") +
          '">Aplicar esta opción</button>' +
      "</div>"
    );
  }

  function mostrarComparadorCargando() {
    if (!comparadorContenidoEl || !comparadorOverlayEl) return;
    comparadorContenidoEl.innerHTML = '<p class="checklist-campo-estado">Generando las 2 opciones… puede tardar.</p>';
    comparadorOverlayEl.classList.add("open");
  }

  function mostrarComparadorError(mensaje) {
    if (!comparadorContenidoEl) return;
    comparadorContenidoEl.innerHTML = '<p class="checklist-campo-error">' + mensaje + "</p>";
  }

  function mostrarComparadorOpciones(opciones) {
    if (!comparadorContenidoEl) return;
    var etiquetas = Object.keys(opciones);
    if (!etiquetas.length) {
      mostrarComparadorError("No se pudo generar ninguna opción.");
      return;
    }
    comparadorContenidoEl.innerHTML =
      '<div class="comparador-opciones-grid">' +
        etiquetas.map(function (e) { return tarjetaOpcionHtml(e, opciones[e]); }).join("") +
      "</div>";
  }

  if (comparadorContenidoEl) comparadorContenidoEl.addEventListener("click", function (e) {
    var btn = e.target.closest(".comparador-opcion-aplicar");
    if (!btn || !btn.dataset.proyectoId) return;
    var id = btn.dataset.proyectoId;
    btn.disabled = true;
    btn.textContent = "Abriendo…";
    fetch("/api/proyectos/" + encodeURIComponent(id))
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (payload) {
        if (comparadorOverlayEl) comparadorOverlayEl.classList.remove("open");
        close(); // cierra también el Sandbox -- el workspace pasa a mostrar el proyecto elegido
        if (window.ArchmuseShell && window.ArchmuseShell.onProyectoGenerado) {
          window.ArchmuseShell.onProyectoGenerado(payload);
        }
      })
      .catch(function () {
        btn.disabled = false;
        btn.textContent = "Aplicar esta opción";
        alert("No se pudo abrir ese proyecto.");
      });
  });

  var btnComparadorCerrar = document.getElementById("btn-comparador-opciones-cerrar");
  if (btnComparadorCerrar) btnComparadorCerrar.addEventListener("click", function () {
    if (comparadorOverlayEl) comparadorOverlayEl.classList.remove("open");
  });

  // `getProgramaNecesidades` (2026-08-17, PRD aprobado, §8): expone el JSON documentado del Programa
  // de Necesidades para consumo externo (futuro motor de distribución por IA) -- delega entero en
  // `ProgramaNecesidades.getEstado()`, que ya devuelve `null` si el panel no está montado.
  window.ArchmuseSandbox = { open: open, close: close, getProgramaNecesidades: ProgramaNecesidades.getEstado };
})();
