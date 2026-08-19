// Entrevistador arquitectónico — Fase E (UI).
//
// Consume EXCLUSIVAMENTE la API de Fase B (`app.py`, sección "ENTREVISTADOR
// (Fase B)"): POST /api/entrevista, GET /api/entrevista/<id>,
// POST /api/entrevista/<id>/responder, POST /api/entrevista/<id>/finalizar,
// POST /api/entrevista/<id>/especificacion,
// POST /api/entrevista/<id>/valores_expertos (2026-08-13, puente de datos
// técnicos sobre la misma sesión). Ningún módulo de
// `analyzer/interview/*` se importa ni se llama desde aquí — no existe tal
// cosa en JavaScript, pero el principio es el mismo que ya aplican
// `viewer-edificio.js`/`viewer-vivienda.js`: esta capa es tonta.
// API → estado → render. Nunca decide qué pregunta toca (eso lo dice
// `pregunta_actual`, siempre derivado por el servidor), nunca interpreta una
// respuesta, nunca calcula prioridades, nunca resuelve contradicciones por su
// cuenta, nunca compila `params`, nunca aplica normativa, nunca inventa un
// valor por defecto que el usuario no haya dado.
//
// Archivo nuevo y aislado (plan E1: "no se amplía más static/app.js").
// Mismo estilo ES5 + "use strict" que `app.js`, para que ambos se lean como
// el mismo proyecto.
//
// Puente con la shell: `app.js` expone `window.ArchmuseShell` (ver el
// bloque "Puente con el entrevistador" al final de ese archivo) con lo que
// este módulo necesita del resto de la aplicación: limpiar el contexto del
// sidebar, volver a donde estaba el usuario antes de entrar aquí, entregar
// un proyecto ya generado al workspace, y (2026-08-15) mostrar/cerrar la
// pantalla de carga limpia de `app.js` durante `POST /api/generar` en vez
// de reescribir el resumen entero con el texto de un botón cambiado. Este
// módulo nunca toca `document.getElementById("view-root")` de otra forma
// que reescribiendo su `innerHTML` por completo, igual que hace `app.js`
// en cada uno de sus `render*` -- salvo mientras `app.js` tiene el control
// tras `mostrarCargandoGeneracion`, momento en que este módulo no debe
// tocar `view-root` hasta que `finalizarCargandoGeneracion` se lo devuelva.

(function () {
  "use strict";

  var viewRoot = document.getElementById("view-root");

  // --- Utilidades mínimas, copia deliberada de las de app.js --------------
  // (mismo comportamiento exacto; no se comparte código entre ambos
  // archivos a propósito — el principio de aislamiento de la Fase E es que
  // este módulo no dependa de internals privados de `app.js`, solo del
  // puente explícito `window.ArchmuseShell`.)

  function escapeHtml(str) {
    return String(str == null ? "" : str).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function prettify(codigo) {
    if (codigo == null) return "";
    var texto = String(codigo).replace(/_/g, " ");
    return texto.charAt(0).toUpperCase() + texto.slice(1);
  }

  // --- Persistencia local del id de sesión (E9: abandono/reanudación) -----
  // Solo el `sesion_id` — nunca el estado real de la entrevista, que vive
  // siempre en el servidor (`analyzer/storage.py`, Fase A). Esto es
  // deliberado: recargar la página nunca reconstruye nada localmente, solo
  // vuelve a pedirle al servidor "¿qué estado tenías?" vía GET.

  var LS_KEY = "archmuseEntrevistaSesionId";
  var _ID_RE = /^[0-9a-f]{12}$/; // mismo formato que storage._ID_RE en el backend

  function guardarSesion(id) {
    try { localStorage.setItem(LS_KEY, id); } catch (e) { /* almacenamiento no disponible: se sigue sin persistir */ }
  }
  function leerSesionGuardada() {
    try {
      var v = localStorage.getItem(LS_KEY);
      return v && _ID_RE.test(v) ? v : null;
    } catch (e) { return null; }
  }
  function limpiarSesionGuardada() {
    try { localStorage.removeItem(LS_KEY); } catch (e) { /* nada que limpiar */ }
  }

  // --- Historial de parcelas buscadas (2026-08-17, a petición explícita) --------------------------
  // Persistido en localStorage, nunca en el servidor -- es una comodidad de ESTE navegador, no un dato
  // de la parcela en sí (mismo criterio que `LS_KEY` de arriba: solo el id/la referencia mínima para
  // reconstruir la selección, nunca el resultado completo de Catastro, que se vuelve a pedir de
  // verdad al seleccionar una entrada del historial -- nunca se sirve una respuesta de Catastro
  // cacheada localmente como si fuera fresca).
  var PARCELAS_HISTORIAL_KEY = "archmuseParcelasRecientes";
  var PARCELAS_HISTORIAL_MAX = 8;

  function leerHistorialParcelas() {
    try {
      var crudo = localStorage.getItem(PARCELAS_HISTORIAL_KEY);
      var lista = crudo ? JSON.parse(crudo) : [];
      return Array.isArray(lista) ? lista : [];
    } catch (e) { return []; } // JSON corrupto o almacenamiento no disponible: como si no hubiera historial
  }

  //: Deduplicado por coordenadas a 4 decimales (~11m de precisión, mismo redondeo que usa
  //: `app.py:_clave_cache_sitio_de` para la caché de sitios en el servidor) -- volver a seleccionar
  //: prácticamente el mismo punto actualiza su etiqueta/fecha y lo sube arriba, en vez de duplicar la
  //: entrada.
  function guardarEnHistorialParcelas(displayName, lat, lon) {
    if (lat == null || lon == null) return;
    var clave = lat.toFixed(4) + "," + lon.toFixed(4);
    var historial = leerHistorialParcelas().filter(function (h) { return h.clave !== clave; });
    historial.unshift({ clave: clave, displayName: displayName || (lat.toFixed(5) + ", " + lon.toFixed(5)), lat: lat, lon: lon });
    try { localStorage.setItem(PARCELAS_HISTORIAL_KEY, JSON.stringify(historial.slice(0, PARCELAS_HISTORIAL_MAX))); }
    catch (e) { /* almacenamiento lleno o no disponible: se sigue sin persistir, no es un error visible */ }
  }

  function borrarHistorialParcelas() {
    try { localStorage.removeItem(PARCELAS_HISTORIAL_KEY); } catch (e) { /* nada que limpiar */ }
  }

  // --- Cliente HTTP mínimo --------------------------------------------------

  // `timeoutMs` (opcional, fix 2026-08-15 -- bug reportado en vivo "no termina de cargar nada"): sin esto,
  // si el servidor tarda demasiado (Catastro/Overpass lentos, ver `analyzer/sitio.py`) o directamente se
  // cuelga, esta promesa nunca se resuelve ni se rechaza -- cualquier UI que espere su resultado (p. ej. el
  // spinner de "Consultando Catastro") se queda girando para siempre, sin ningún mensaje de error. Con
  // `timeoutMs`, pasado ese tiempo se aborta la petición y se resuelve igual (nunca se deja la promesa
  // colgada), como un fallo de red más -- mismo camino que ya manejaba el `.catch()` de abajo.
  function apiFetch(metodo, ruta, cuerpo, timeoutMs) {
    var opts = { method: metodo, headers: { "Content-Type": "application/json" } };
    if (cuerpo !== undefined) opts.body = JSON.stringify(cuerpo);
    var idTimeout = null;
    if (timeoutMs && window.AbortController) {
      var controlador = new AbortController();
      opts.signal = controlador.signal;
      idTimeout = setTimeout(function () { controlador.abort(); }, timeoutMs);
    }
    return fetch(ruta, opts)
      .then(function (resp) {
        if (idTimeout) clearTimeout(idTimeout);
        return resp.json()
          .catch(function () { return {}; })
          .then(function (body) { return { status: resp.status, body: body, network: false }; });
      })
      .catch(function (err) {
        if (idTimeout) clearTimeout(idTimeout);
        var esTimeout = err && err.name === "AbortError";
        return { status: 0, body: esTimeout ? { error: "la petición tardó demasiado en responder" } : {}, network: true };
      });
  }

  // =========================================================================
  // Catálogo de presentación — etiquetas y formularios de campo
  // =========================================================================
  //
  // Todo lo de este bloque es SOLO texto de interfaz: qué etiqueta legible
  // corresponde a cada `especificacion_id`, y qué tipo de control HTML pinta
  // cada uno en modo experto / en el puente de "faltan datos técnicos"
  // (ver más abajo). No es una segunda fuente de verdad sobre qué es válido
  // — eso lo decide siempre el servidor (`analyzer/interview/compilador.py`,
  // `_CLASIFICACION`/`_ETIQUETAS`, Fase D) cuando responde 200/422 a
  // POST /especificacion. Esta tabla es deliberadamente un duplicado de
  // presentación de esas etiquetas (mismos textos que `compilador._ETIQUETAS`
  // a fecha de esta fase) — si el catálogo del backend cambia, este archivo
  // necesita actualizarse a mano; no hay endpoint de "esquema" en Fase B para
  // evitarlo (ver informe de cierre, punto 6).

  var CATEGORIA_LABELS = {
    contexto_ubicacion: "Contexto y ubicación",
    parcela: "Parcela",
    programa_necesidades: "Programa de necesidades",
    usuarios_forma_vida: "Usuarios y forma de vida",
    prioridades_trade_offs: "Prioridades",
    restricciones_normativas: "Restricciones y normativa",
    entorno_privacidad: "Entorno y privacidad",
    orientacion_clima: "Orientación y clima",
    espacios_exteriores: "Espacios exteriores",
    movilidad_accesos: "Movilidad y accesos",
    sostenibilidad_eficiencia: "Sostenibilidad",
    identidad_arquitectonica: "Identidad y estilo",
    presupuesto: "Presupuesto",
    relaciones_espaciales_circulacion: "Relaciones interiores",
    // Fix 2026-08-16 (a petición explícita): "Estructura (solo modo experto)" era una etiqueta de
    // depuración interna filtrada a producto -- describía de dónde puede venir el dato (una
    // restricción de implementación de Fase D), no qué es el bloque para quien lee el resumen. El
    // dato en sí de "exclusivo de modo experto" sigue visible, pero como nota honesta bajo cada
    // campo (`notaDestino()`, "Campo exclusivo de modo experto; hoy no se usa en la generación."),
    // que es el sitio correcto para ese matiz -- no en el título de la sección entera.
    estructura_sistema_constructivo: "Estructura y sistema constructivo"
  };
  var ORDEN_CATEGORIAS = [
    "contexto_ubicacion", "parcela", "programa_necesidades", "usuarios_forma_vida",
    "prioridades_trade_offs", "restricciones_normativas", "entorno_privacidad",
    "orientacion_clima", "espacios_exteriores", "movilidad_accesos",
    "sostenibilidad_eficiencia", "identidad_arquitectonica", "presupuesto",
    "relaciones_espaciales_circulacion", "estructura_sistema_constructivo"
  ];

  //: Los 8 imprescindibles (PRD v2 §2) — mismo orden y mismos ids que
  //: `analyzer/interview/preguntas.py:IMPRESCINDIBLES`. Solo se usan aquí
  //: para (a) la barra de progreso y (b) marcar el badge "imprescindible" en
  //: modo experto — nunca para decidir si algo puede compilarse, eso lo
  //: sigue diciendo solo el servidor.
  var IMPRESCINDIBLES_IDS = [
    "contexto.ciudad", "programa.tipologia", "solar.superficie_m2", "solar.forma",
    "programa.num_viviendas_mix", "prioridades.trade_off", "usuarios.accesibilidad",
    "orientacion.real_parcela"
  ];

  // tipo: "texto" | "texto_largo" | "numero" | "seleccion" | "mix_viviendas" | "booleano"
  var CAMPO_SCHEMA = {
    "contexto.ciudad": { etiqueta: "Ciudad / municipio", categoria: "contexto_ubicacion", tipo: "texto", placeholder: "Madrid" },
    "programa.tipologia": { etiqueta: "Tipología del edificio", categoria: "programa_necesidades", tipo: "seleccion",
      opciones: [["unifamiliar", "Unifamiliar"], ["plurifamiliar", "Plurifamiliar"], ["otra", "Otro tipo"]] },
    "solar.superficie_m2": { etiqueta: "Superficie del solar (m²)", categoria: "parcela", tipo: "numero", placeholder: "500" },
    "solar.forma": { etiqueta: "Forma del solar", categoria: "parcela", tipo: "texto", placeholder: "rectangular / irregular" },
    "programa.num_viviendas_mix": { etiqueta: "Mix de viviendas", categoria: "programa_necesidades", tipo: "mix_viviendas" },
    "prioridades.trade_off": { etiqueta: "Prioridad ante conflicto", categoria: "prioridades_trade_offs", tipo: "seleccion",
      opciones: [["superficie", "Más superficie"], ["luz", "Más luz natural"], ["coste", "Menor coste"], ["numero_viviendas", "Más viviendas"]] },
    "usuarios.accesibilidad": { etiqueta: "Accesibilidad requerida", categoria: "usuarios_forma_vida", tipo: "seleccion",
      opciones: [["si", "Sí"], ["no", "No"], ["no_lo_sabe", "No lo sabe todavía"]] },
    "orientacion.real_parcela": { etiqueta: "Orientación real de la parcela", categoria: "orientacion_clima", tipo: "seleccion",
      opciones: [["norte", "Norte"], ["sur", "Sur"], ["este", "Este"], ["oeste", "Oeste"], ["noreste", "Noreste"],
        ["noroeste", "Noroeste"], ["sureste", "Sureste"], ["suroeste", "Suroeste"], ["combinacion", "Combinación"]] },
    "edificio.plantas": { etiqueta: "Plantas a construir", categoria: "restricciones_normativas", tipo: "numero", placeholder: "4" },
    "edificio.altura_libre_m": { etiqueta: "Altura libre por planta (m)", categoria: "restricciones_normativas", tipo: "numero", placeholder: "2.8" },
    "edificio.planta_baja_comercial": { etiqueta: "¿Planta baja comercial?", categoria: "restricciones_normativas", tipo: "booleano" },
    "programa.superficie_minima_m2": { etiqueta: "Superficie mínima por vivienda (m²)", categoria: "programa_necesidades", tipo: "numero", placeholder: "45" },
    "restricciones.ocupacion_maxima_pct": { etiqueta: "Ocupación máxima del solar (%)", categoria: "restricciones_normativas", tipo: "numero", placeholder: "70" },
    "restricciones.retranqueos_m": { etiqueta: "Retranqueos (m)", categoria: "restricciones_normativas", tipo: "numero", placeholder: "3" },
    "restricciones.edificabilidad_maxima": { etiqueta: "Edificabilidad máxima (m²/m²)", categoria: "restricciones_normativas", tipo: "numero", placeholder: "2.5" },
    "restricciones.plantas_maximas": { etiqueta: "Plantas máximas (normativa)", categoria: "restricciones_normativas", tipo: "numero", placeholder: "6" },
    "usuarios.destino": { etiqueta: "Para quién es el proyecto", categoria: "usuarios_forma_vida", tipo: "seleccion",
      opciones: [["vivir", "Para vivir yo"], ["vender", "Para vender"], ["alquilar", "Para alquilar"], ["no_lo_sabe", "Todavía no lo sabe"]] },
    "prioridades.no_negociables": { etiqueta: "No negociables", categoria: "prioridades_trade_offs", tipo: "texto_largo" },
    "privacidad.necesidad": { etiqueta: "Necesidad de privacidad", categoria: "entorno_privacidad", tipo: "seleccion",
      opciones: [["mucha", "Mucha"], ["normal", "La normal"], ["le_da_igual", "Le da igual"]] },
    "relaciones_espaciales.cocina": { etiqueta: "Cocina abierta o cerrada", categoria: "relaciones_espaciales_circulacion", tipo: "seleccion",
      opciones: [["abierta", "Abierta (integrada)"], ["cerrada", "Cerrada (separada)"]] },
    "identidad.referencias_esteticas": { etiqueta: "Referencias estéticas / carácter", categoria: "identidad_arquitectonica", tipo: "texto_largo" },
    "prioridades.lo_de_menos_importa": { etiqueta: "Lo que menos importa", categoria: "prioridades_trade_offs", tipo: "texto_largo" },
    "presupuesto.cifra_horquilla": { etiqueta: "Presupuesto", categoria: "presupuesto", tipo: "texto", placeholder: "p.ej. 300.000 - 400.000 €" },
    "sostenibilidad.prioridad": { etiqueta: "Prioridad de sostenibilidad", categoria: "sostenibilidad_eficiencia", tipo: "seleccion",
      opciones: [["ahorro_energetico_largo_plazo", "Ahorrar energía a largo plazo"], ["coste_construccion_bajo", "Coste de construcción bajo"]] },
    "exteriores.preferencia": { etiqueta: "Preferencia de espacios exteriores", categoria: "espacios_exteriores", tipo: "seleccion",
      opciones: [["espacio_exterior_propio", "Espacio exterior propio"], ["aprovechar_metros_interiores", "Aprovechar metros interiores"]] },
    "programa.descripcion_libre": { etiqueta: "Descripción libre del proyecto", categoria: "programa_necesidades", tipo: "texto_largo" },
    "programa.sensacion_buscada": { etiqueta: "Sensación buscada", categoria: "identidad_arquitectonica", tipo: "texto" },
    "parcela.estado_tenencia": { etiqueta: "Estado de tenencia de la parcela", categoria: "parcela", tipo: "seleccion",
      opciones: [["tengo_parcela", "Ya tiene la parcela"], ["buscando_parcela", "Todavía buscando/imaginando"]] },
    "parcela.tipo_intervencion": { etiqueta: "¿La parcela está vacía o ya hay una edificación?", categoria: "parcela", tipo: "seleccion",
      opciones: [["obra_nueva", "Parcela vacía (obra nueva)"],
        ["edificacion_existente", "Edificación existente (rehabilitación / reforma / ampliación)"]] },
    //: Solo tiene sentido si `parcela.tipo_intervencion === "edificacion_existente"` — condicionado en
    //: `vistaExperto()` (no aquí: `CAMPO_SCHEMA` no sabe de dependencias entre campos, solo describe cada
    //: uno por separado).
    "parcela.elementos_a_conservar": { etiqueta: "Qué conservar o demoler de lo existente", categoria: "parcela", tipo: "texto_largo",
      placeholder: "p.ej. Conservar estructura principal y fachadas. Demoler la distribución interior." },
    "estructura.sistema_constructivo": { etiqueta: "Estructura / sistema constructivo", categoria: "estructura_sistema_constructivo", tipo: "texto_largo" }
  };

  //: Traducción de valores codificados a texto legible, para el resumen
  //: (PRD v2 §27) y para prellenar el puente/experto. Mismo principio que
  //: `CAMPO_SCHEMA`: presentación, no una segunda validación.
  var VALOR_LABELS = {};
  Object.keys(CAMPO_SCHEMA).forEach(function (id) {
    var campo = CAMPO_SCHEMA[id];
    if (campo.tipo === "seleccion" && campo.opciones) {
      var mapa = {};
      campo.opciones.forEach(function (par) { mapa[par[0]] = par[1]; });
      VALOR_LABELS[id] = mapa;
    }
  });
  VALOR_LABELS["solar.forma"] = { irregular_decidido_por_sistema: "Irregular — decidido por ArchMuse" };

  function formatearValor(especificacionId, valor) {
    if (valor === null || valor === undefined || valor === "") return "—";
    if (typeof valor === "boolean") return valor ? "Sí" : "No";
    if (especificacionId === "programa.num_viviendas_mix" && typeof valor === "object") {
      return (valor.dorm_1 || 0) + " de 1 dorm., " + (valor.dorm_2 || 0) + " de 2 dorm., " + (valor.dorm_3 || 0) + " de 3 dorm.";
    }
    var mapa = VALOR_LABELS[especificacionId];
    if (mapa && Object.prototype.hasOwnProperty.call(mapa, valor)) return mapa[valor];
    if (typeof valor === "object") return escapeHtml(JSON.stringify(valor));
    return escapeHtml(String(valor));
  }

  //: Etiquetas de las opciones de cada PREGUNTA (no siempre coincide 1:1 con
  //: `especificacion_id` — p. ej. p_trade_off_directo alimenta
  //: `prioridades.trade_off`, cuyas opciones ya están en `CAMPO_SCHEMA`
  //: arriba). Se resuelve por `pregunta_id` primero; si no hay entrada
  //: específica, se cae a `CAMPO_SCHEMA` por el primer especificacion_id de
  //: la pregunta, y si tampoco hay nada, se usa `prettify()`.
  var OPCION_LABELS_POR_PREGUNTA = {
    p2: { vivir: "Para vivir yo", vender: "Para vender", alquilar: "Para alquilar", no_lo_sabe: "Todavía no lo sé" },
    p3: { tengo_parcela: "Ya tengo la parcela", buscando_parcela: "Todavía la estoy buscando/imaginando" },
    p6: { mas_grandes_menos_viviendas: "Viviendas más grandes, y menos", mas_pequenas_mas_viviendas: "Viviendas más pequeñas, y más" },
    p8: { norte: "Norte", sur: "Sur", este: "Este", oeste: "Oeste", noreste: "Noreste", noroeste: "Noroeste",
      sureste: "Sureste", suroeste: "Suroeste", combinacion: "Una combinación" },
    p10: { ahorro_energetico_largo_plazo: "Ahorrar energía a largo plazo", coste_construccion_bajo: "Coste de construcción más bajo ahora" },
    p12: { mucha: "Mucha", normal: "La normal", le_da_igual: "Me da igual" },
    p13: { si: "Sí", no: "No", no_lo_sabe: "No lo sé todavía" },
    p14: { espacio_exterior_propio: "Espacio exterior propio", aprovechar_metros_interiores: "Aprovechar metros interiores" },
    p15: { abierta: "Abierta (integrada)", cerrada: "Cerrada (separada)" },
    p_trade_off_directo: { superficie: "Más superficie", luz: "Más luz", coste: "Menor coste", numero_viviendas: "Más viviendas" },
    p_tipologia_directa: { unifamiliar: "Unifamiliar (una vivienda)", plurifamiliar: "Plurifamiliar (varias)", otra: "Otro tipo" },
    // "Materiales y Calidades" (2026-08-15, a petición explícita) — etiquetas legibles de los chips.
    p_fachada: {
      sate_aislamiento_continuo: "SATE / aislamiento continuo",
      fachada_ventilada_piedra_ceramica: "Fachada ventilada de piedra/cerámica",
      hormigon_visto: "Hormigón visto",
      ladrillo_visto_clasico_moderno: "Ladrillo visto / clásico-moderno",
      madera_exterior_composite: "Madera de exterior / composite"
    },
    p_paleta_colores: {
      tonos_neutros_blanco_arena: "Tonos neutros / blanco / arena",
      tonos_oscuros_gris_antracita_negro: "Tonos oscuros / gris antracita / negro",
      acabados_calidos_madera_piedra: "Acabados cálidos / madera y piedra",
      colores_vivos_contrastes: "Colores vivos / contrastes"
    },
    p_pavimento: {
      parquet_madera_natural: "Parquet / madera natural",
      gres_porcelanico_gran_formato: "Gres porcelánico de gran formato",
      microcemento: "Microcemento",
      suelo_radiante_acabado_ceramico: "Suelo radiante con acabado cerámico"
    },
    p_nivel_calidades: {
      estandar_funcional: "Estándar / funcional",
      alta_calidad_premium: "Alta calidad / premium",
      lujo_a_medida: "Lujo / acabados a medida"
    }
  };

  // Las mismas etiquetas de arriba, reutilizadas en `VALOR_LABELS` (que indexa por especificacion_id, no
  // por pregunta_id) -- sin esto, la pantalla de resumen (`fraseCampo`/`formatearValor`) mostraría el
  // código snake_case crudo ("sate_aislamiento_continuo") en vez del texto legible que sí usan el resto de
  // preguntas cerradas. Un solo sitio con el texto de cada opción, nunca dos copias que puedan desincronizarse.
  VALOR_LABELS["materiales.tipo_fachada"] = OPCION_LABELS_POR_PREGUNTA.p_fachada;
  VALOR_LABELS["materiales.paleta_colores"] = OPCION_LABELS_POR_PREGUNTA.p_paleta_colores;
  VALOR_LABELS["materiales.pavimento"] = OPCION_LABELS_POR_PREGUNTA.p_pavimento;
  VALOR_LABELS["materiales.nivel_calidades"] = OPCION_LABELS_POR_PREGUNTA.p_nivel_calidades;

  function etiquetaOpcion(pregunta, opcion) {
    var porPregunta = OPCION_LABELS_POR_PREGUNTA[pregunta.pregunta_id];
    if (porPregunta && porPregunta[opcion]) return porPregunta[opcion];
    return prettify(opcion);
  }

  //: Placeholders de las preguntas abiertas — texto puramente decorativo
  //: (atributo `placeholder` nativo de HTML), no una "explicación" recogida
  //: del backend: `pregunta_a_dict()` (app.py, Fase B) no expone
  //: `que_pretende_obtener` (ver informe de cierre, punto 6). El propio
  //: texto literal de cada pregunta (PRD v2 §6) ya es conversacional y
  //: autoexplicativo; esto es solo una ayuda extra en las más abiertas.
  var PLACEHOLDER_POR_PREGUNTA = {
    p1: "Por ejemplo: un edificio de 6 viviendas en el centro, luminoso, que se sienta acogedor...",
    p4: "Por ejemplo: que todas las viviendas tengan terraza.",
    p5: "Por ejemplo: el acabado de las fachadas, no me importa mucho.",
    p3_ciudad: "Madrid",
    p3_superficie: "500 m²",
    p9: "Por ejemplo: entre 300.000 y 400.000 €",
    p11: "Por ejemplo: casas nórdicas, ladrillo visto, mucha madera..."
  };

  // =========================================================================
  // Mapeo de errores de compilación a campos — el "puente de datos técnicos"
  // =========================================================================
  //
  // `compilar_params()`/`validar_especificacion()` (Fase D) devuelven texto
  // en español, no códigos de error por campo. Este módulo NUNCA decide si
  // algo es válido a partir de este texto — sigue siendo el servidor quien
  // valida (una nueva llamada a POST /especificacion es la única fuente de
  // verdad) — solo lo usa para decidir QUÉ CONTROL DE FORMULARIO mostrar a
  // continuación, con dos patrones estables ya documentados en
  // `compilador.py`: mensajes de `compilar_params()` empiezan siempre por
  // `"params.<ruta>: "`; mensajes de `validar_especificacion()` citan el
  // `especificacion_id` entre comillas simples (`repr()` de Python). Si un
  // mensaje no encaja en ninguno de los dos patrones, se muestra tal cual,
  // nunca se oculta (principio 11 del turno / punto 11 del encargo).

  var PREFIJO_PARAMS_A_CAMPO = {
    "params.proyecto.ciudad": "contexto.ciudad",
    "params.proyecto.tipologia": "programa.tipologia",
    "params.solar.superficie_m2": "solar.superficie_m2",
    "params.solar.norte_grados": "orientacion.real_parcela",
    "params.edificio.plantas": "edificio.plantas",
    "params.mix_viviendas": "programa.num_viviendas_mix"
  };

  function idsDesdeErrores(errores) {
    var ids = [];
    var sinMapear = [];
    (errores || []).forEach(function (texto) {
      var i, encontrado = null;
      for (i in PREFIJO_PARAMS_A_CAMPO) {
        if (texto.indexOf(i + ":") === 0) { encontrado = PREFIJO_PARAMS_A_CAMPO[i]; break; }
      }
      if (!encontrado) {
        var m = /'([a-z0-9_.]+)'/.exec(texto);
        if (m && CAMPO_SCHEMA[m[1]]) encontrado = m[1];
      }
      if (encontrado) {
        if (ids.indexOf(encontrado) === -1) ids.push(encontrado);
      } else {
        sinMapear.push(texto);
      }
    });
    return { ids: ids, sinMapear: sinMapear };
  }

  // =========================================================================
  // Estado del módulo
  // =========================================================================

  function estadoInicial() {
    return {
      vista: "parcela_inicial", // parcela_inicial | eleccion | recuperando | creando | turno | confirmar_cierre |
                          // puente | experto | generando | resumen | error_red | error_interno
      sesionId: null,
      modoEntrada: null,
      entrevista: null,   // último dict {sesion_id, estado, modo, ..., pregunta_actual, cierre}
      borrador: {},        // pregunta_id -> texto en curso (turno actual, se limpia en cada turno nuevo)
      // Navegación "Anterior" (2026-08-15, a petición explícita): pila LIFO de {respuestas, esResolucion
      // Contradiccion} en el mismo orden que los turnos reales ya enviados a `/responder` -- el servidor
      // (`interview_motor.deshacer_ultimo_turno`) ya sabe deshacer su propio estado sin ayuda de nadie, pero
      // NO conserva el texto/opción cruda que el usuario escribió (deshacer de verdad la borra) -- por eso
      // esta copia vive aquí, en el cliente, para poder rellenar automáticamente los inputs de la pregunta
      // a la que se vuelve (requisito explícito del encargo). Se pierde al recargar la página (no se
      // persiste) -- "Anterior" sigue funcionando tras recargar (el servidor no lo necesita para deshacer),
      // solo deja de poder rellenar la respuesta anterior automáticamente.
      historialRespuestas: [],
      errorTurno: null,    // {tipo, mensaje} banner inline del turno actual
      expertoValores: {},  // especificacion_id -> valor (formulario de modo experto)
      expertoTocados: {},  // especificacion_id -> true, solo los campos que el usuario ha editado de verdad
                            // en ESTA visita al formulario (2026-08-13: distingue "dato ya conocido, mostrado
                            // sin tocar" de "el usuario lo declaró/corrigió aquí" — ver wireExperto()).
      errorExperto: null,
      puente: null,        // {ids, camposBase, erroresCrudos, sinMapear, intentoNum}
      valoresPuente: {},
      confirmarCierre: null, // body de la respuesta 409 de /finalizar sin forzar
      resumen: null,        // {especificacion, avisos, params}
      errorResumen: null,
      cierreBloqueado: null, // cuando se agotan los reintentos del puente
      enviando: false,
      // "Mapa/Parcela Primero" (Paso 0, `vistaParcelaInicial`) -- `null` mientras no se ha elegido/consultado
      // nada. `lat`/`lon` son las coordenadas EXACTAS que se mandaron a `/api/analizar-sitio` (necesarias tal
      // cual, no redondeadas por el propio código, para que `sitio_lat`/`sitio_lon` en `/api/generar` calculen
      // la MISMA clave de caché que `_clave_cache_sitio_de` en `app.py` y el enlace funcione de verdad).
      parcela: null, // {lat, lon, cargandoSitio, sitio, errorSitio, referenciaCatastral, superficieM2, ciudadDetectada}
      // Sólido Capaz persistente (2026-08-17, docs/prd/2026-08-17-solido-capaz-persistente-visor-
      // edificio.md): snapshot que `onGenerar` recibe del Sandbox si el arquitecto calculó un Sólido
      // Capaz allí antes de pulsar "Generar plantas con IA" -- `null` si no lo calculó (el caso
      // mayoritario) o si no pasó por el Sandbox en absoluto. Viaja tal cual hasta `handleGenerar()`,
      // igual que `sitio_lat`/`sitio_lon`: este módulo no lo interpreta, solo lo transporta.
      solidoCapaz: null
    };
  }

  var E = estadoInicial();

  function render() {
    var html;
    switch (E.vista) {
      case "recuperando": html = vistaCargando("Recuperando tu entrevista…"); break;
      case "creando": html = vistaCargando("Preparando la entrevista…"); break;
      case "parcela_inicial": html = vistaParcelaInicial(); break;
      case "eleccion": html = vistaEleccion(); break;
      case "turno": html = vistaTurno(); break;
      case "confirmar_cierre": html = vistaConfirmarCierre(); break;
      case "puente": html = vistaPuente(); break;
      case "experto": html = vistaExperto(); break;
      case "generando": html = vistaCargando("Generando tu proyecto…"); break;
      case "resumen": html = vistaResumen(); break;
      case "cierre_bloqueado": html = vistaCierreBloqueado(); break;
      case "error_red": html = vistaError("Error de red", "No se ha podido contactar con el servidor. Comprueba tu conexión e inténtalo de nuevo."); break;
      default: html = vistaError("Ha ocurrido un error", "Algo no ha ido bien. Puedes volver a intentarlo desde el principio."); break;
    }
    // `.entrevista-screen-mapa` (2026-08-17): SOLO el Paso 0 renuncia al scroll vertical de
    // `.entrevista-screen` -- ver el comentario grande junto a `.entrevista-screen-mapa` en `style.css`
    // sobre por qué esta pantalla concreta necesita encajar exacta en el alto visible.
    var claseEscenaMapa = E.vista === "parcela_inicial" ? " entrevista-screen-mapa" : "";
    viewRoot.innerHTML = '<div class="entrevista-screen bg-technical' + claseEscenaMapa + '">' + html + "</div>";
    wireVistaActual();
  }

  // --- Cabecera compartida por (casi) todas las pantallas ------------------

  function cabecera(titulo, opts) {
    opts = opts || {};
    var volver = opts.ocultarVolver ? "" :
      '<button type="button" class="entrevista-volver" id="ent-volver">&larr; ' + escapeHtml(opts.textoVolver || "Volver") + "</button>";
    var nuevo = opts.ocultarNuevo ? "" :
      '<button type="button" class="entrevista-link-sutil" id="ent-empezar-de-nuevo">Empezar de nuevo</button>';
    var clase = "entrevista-cabecera" + (opts.claseExtra ? " " + opts.claseExtra : "");
    return '<div class="' + clase + '">' + volver +
      '<h1 class="entrevista-titulo">' + escapeHtml(titulo) + "</h1>" + nuevo + "</div>";
  }

  function wireCabeceraComun() {
    var volver = document.getElementById("ent-volver");
    if (volver) volver.addEventListener("click", function () { irAtras(); });
    var nuevo = document.getElementById("ent-empezar-de-nuevo");
    if (nuevo) nuevo.addEventListener("click", function () {
      if (!confirm("¿Empezar una entrevista nueva? Se perderá el progreso de esta.")) return;
      limpiarSesionGuardada();
      E = estadoInicial();
      render();
    });
  }

  function irAtras() {
    // "Modo enfocado" (2026-08-15): se activó en `iniciar()` para todo el flujo de "Generar proyecto"
    // (parcela + preguntas) -- al salir de él (Cancelar/Volver desde la primera pantalla), hay que devolver
    // el sidebar a lo que el usuario tuviera elegido, nunca dejarlo escondido fuera de este flujo.
    if (window.ArchmuseShell && window.ArchmuseShell.restaurarSidebar) window.ArchmuseShell.restaurarSidebar();
    if (window.ArchmuseShell && window.ArchmuseShell.onCancelar) { window.ArchmuseShell.onCancelar(); return; }
    window.location.reload();
  }

  // =========================================================================
  // Pantalla: cargando (creando / recuperando / generando)
  // =========================================================================

  function vistaCargando(texto) {
    return '<div class="entrevista-card entrevista-card-centrado">' +
      '<div class="entrevista-spinner" aria-hidden="true"></div>' +
      '<p class="entrevista-cargando-texto">' + escapeHtml(texto) + "</p></div>";
  }

  // =========================================================================
  // Pantalla: parcela inicial (Paso 0, "Mapa/Parcela Primero") — mapa
  // interactivo + buscador de dirección, ANTES de elegir entrevista guiada
  // o modo experto. Ver `static/map-picker.js` (Leaflet + OSM, sin token)
  // para el mapa en sí; esta pantalla solo lo monta y reacciona a sus
  // eventos con `/api/geocodificar` (buscador) y `/api/analizar-sitio`
  // (Catastro real al elegir un punto).
  //
  // Explícitamente OPCIONAL (link "No sé todavía..."): forzar una parcela
  // atraparía a quien todavía la está buscando/imaginando -- el mismo caso
  // que ya contempla `parcela.estado_tenencia` en modo experto.
  // =========================================================================

  // Presets de direcciones destacadas de Madrid (2026-08-16,
  // docs/prd/2026-08-16-presets-progreso-y-zocalo-sandbox.md): atajos "preparados para proyectos" para
  // no tener que escribir una dirección de memoria en cada demo/prueba -- 4 entornos urbanos distintos
  // a propósito (denso/manzana cerrada/torres/residencial unifamiliar). `query` es lo que se manda a
  // `/api/geocodificar` (con ciudad incluida para minimizar ambigüedad, ver PRD §6); `etiqueta` es lo
  // que se ve en el chip y lo que queda en el input mientras se resuelve.
  var PRESETS_PARCELA = [
    { etiqueta: "Gran Vía, Madrid", query: "Gran Vía, Madrid" },
    { etiqueta: "Calle Velázquez, Madrid", query: "Calle Velázquez, Barrio de Salamanca, Madrid" },
    { etiqueta: "Castellana / AZCA, Madrid", query: "Paseo de la Castellana, AZCA, Madrid" },
    { etiqueta: "La Moraleja, Madrid", query: "La Moraleja, Alcobendas, Madrid" }
  ];

  // Rediseño 2026-08-15 (a petición explícita: "más bonito", "que ocupe mucha más pantalla", "limpio y sin
  // ruido"): el buscador y el estado de Catastro ya no se apilan alrededor del mapa como bloques de texto --
  // flotan ENCIMA de él (overlays, ver `.parcela-buscador`/`.parcela-estado-sitio-flotante` en
  // `style.css`), así el mapa en sí es prácticamente toda la pantalla. Se quita también la intro larga: el
  // propio placeholder del buscador ya explica qué hacer, no hace falta un párrafo aparte.
  //
  // Rediseño 2026-08-17 ("pantalla completa real", a petición explícita -- "sigue viéndose fea",
  // "no queremos arreglos menores de parches"): la tarjeta oscura con marco (`.entrevista-card
  // entrevista-card-mapa`) que encajonaba el mapa DESAPARECE por completo -- el mapa ya no vive DENTRO
  // de una tarjeta, es el fondo de toda la pantalla, borde a borde del área de contenido. La cabecera
  // ("← Cancelar / ¿Dónde está tu parcela?") pasa de bloque en el flujo normal a panel acristalado
  // flotante ANCLADO sobre el mapa (`position: absolute`, ver `.entrevista-cabecera-mapa` en
  // `style.css`) -- por eso ya no empuja nada hacia abajo, y el mapa puede ocupar el 100% del alto
  // disponible en vez de "el alto menos la cabecera". Buscador/presets/estado/acciones siguen siendo
  // overlays acristalados sobre el propio mapa, mismo patrón ya establecido, solo que ahora sin ninguna
  // tarjeta de fondo detrás de ellos.
  function vistaParcelaInicial() {
    return cabecera("¿Dónde está tu parcela?", { ocultarNuevo: true, textoVolver: "Cancelar", claseExtra: "entrevista-cabecera-mapa" }) +
      '<div class="parcela-mapa-envoltorio">' +
      '<div id="parcela-mapa-mount" class="parcela-mapa-mount"></div>' +
      '<div class="parcela-buscador-panel">' +
      '<div class="parcela-buscador">' +
      // Icono de lupa fino (2026-08-17, "iconos finos" pedido explícitamente) en vez del bloque de texto
      // "Buscar" -- decorativo (`aria-hidden`), la acción real sigue siendo el botón de más abajo.
      '<svg class="parcela-buscador-icono" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
      '<circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="1.6"/>' +
      '<line x1="15.8" y1="15.8" x2="20" y2="20" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>' +
      "</svg>" +
      '<input type="text" id="parcela-buscar-input" class="entrevista-input" placeholder="Busca una dirección o haz clic en el mapa…" ' +
      'autocomplete="off" role="combobox" aria-expanded="false" aria-autocomplete="list" aria-controls="parcela-resultados-busqueda">' +
      // Botón "Buscar" reducido a icono de flecha (mismo `id`/wiring de siempre, ver `wireParcelaInicial`)
      // -- un segundo icono de lupa aquí sería redundante con el de arriba; una flecha comunica "ir" sin
      // repetir el mismo glifo dos veces en la misma cápsula.
      '<button type="button" id="parcela-buscar-btn" class="parcela-buscador-btn" aria-label="Buscar">' +
      '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 12h13m0 0l-5.5-5.5M18 12l-5.5 5.5" ' +
      'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
      "</button>" +
      '<div id="parcela-resultados-busqueda" class="parcela-resultados-dropdown" role="listbox" hidden></div>' +
      "</div>" +
      '<div class="parcela-presets" role="group" aria-label="Parcelas de ejemplo en Madrid">' +
      PRESETS_PARCELA.map(function (p, i) {
        return '<button type="button" class="parcela-preset-chip" data-preset-idx="' + i + '">' + escapeHtml(p.etiqueta) + "</button>";
      }).join("") +
      "</div>" +
      "</div>" +
      '<div id="parcela-estado-sitio" class="parcela-estado-sitio-flotante">' + htmlEstadoSitio() + "</div>" +
      '<div class="parcela-acciones-flotantes">' +
      '<button type="button" class="btn-primary" id="parcela-continuar">Continuar</button>' +
      "</div>" +
      "</div>";
  }

  //: Fragmento reutilizado por la carga inicial (`vistaParcelaInicial`, vía render() completo) Y por las
  //: actualizaciones puntuales tras seleccionar un punto (`wireParcelaInicial`, vía innerHTML dirigido a
  //: `#parcela-estado-sitio` -- ver el comentario grande sobre por qué esta pantalla no puede llamar a
  //: `render()` completo tras montar el mapa, al principio de `map-picker.js`).
  //: Progreso real del Paso 0 (2026-08-16, `docs/prd/2026-08-16-resiliencia-catastro-paso0.md`):
  //: `consultarSitio` hace UNA sola petición a `/api/analizar-sitio` -- la espiral de proximidad
  //: (radios 5/10/20m) ya vive dentro del propio backend (`analyzer/sitio.py:_referencia_por_
  //: proximidad`, criterio §8.3: cero llamadas de red adicionales desde el cliente cuando el punto
  //: exacto ya resuelve). Sin streaming/SSE no hay forma honesta de que el cliente reciba hitos
  //: REALES del servidor mientras esa única petición sigue en el aire, así que las 2 fases de abajo
  //: están ancladas a hitos reales del propio cliente, no a un cronómetro que avanza solo:
  //: - Fase 1 ("Conectando con Catastro…"): se dispara en el instante real en que se despacha el
  //:   `fetch`, no antes.
  //: - Fase 2 ("puede estar buscando la parcela más próxima…"): SOLO se dispara si, al llegar el
  //:   umbral, la MISMA petición sigue de verdad pendiente (comprobado con el flag `resuelta` en
  //:   `consultarSitio`) -- si ya resolvió, no se dispara nada. Nunca afirma un hito que no ha
  //:   ocurrido; solo comunica, cuando es cierto, que la espera ya es más larga de lo típico.
  //: - Fase 3 (8s, "Procesando datos de Catastro…") y Fase 4 (25s, "Sigue buscando… no cierre la
  //:   ventana") (2026-08-17, mensajería de paciencia): mismo criterio de honestidad que las dos de
  //:   arriba -- solo piden paciencia mientras la petición sigue de verdad en el aire, nunca afirman
  //:   haber encontrado ni resuelto nada. Con el timeout ampliado a 150s (ver `consultarSitio`), una
  //:   espera larga ya es un caso real y frecuente (Overpass degradado, verificado en vivo hoy mismo),
  //:   no un caso límite -- sin estos avisos el arquitecto se queda con el único mensaje de la Fase 2
  //:   durante más de dos minutos, que es lo que motivó este encargo.
  var UMBRAL_FASE_PROXIMIDAD_MS = 2500;
  var UMBRAL_FASE_PROCESANDO_MS = 8000;
  var UMBRAL_FASE_SIGUE_BUSCANDO_MS = 25000;

  function htmlEstadoSitio() {
    var p = E.parcela;
    if (!p || p.lat == null) return "";
    if (p.cargandoSitio) {
      var pct = p.progresoPct || 20;
      var texto = p.progresoTexto || "Conectando con Catastro…";
      // Sin número de porcentaje (2026-08-17): un "90%" fijo durante más de un minuto de espera real
      // (Overpass degradado) leía como un contador atascado, no como progreso -- ver el barrido
      // `.is-indefinite` de abajo, que reemplaza esa promesa de avance por un indicador honesto de
      // "sigue en marcha" a partir de la Fase 3 (>= 75%, avisos de "Procesando…" / "Sigue buscando…").
      var claseFill = "parcela-progreso-barra-fill" + (pct >= 75 ? " is-indefinite" : "");
      return '<div class="parcela-estado-sitio parcela-estado-sitio-cargando">' +
        '<p class="parcela-progreso-texto"><span class="entrevista-spinner entrevista-spinner-inline" aria-hidden="true"></span> ' +
        escapeHtml(texto) + "</p>" +
        '<div class="parcela-progreso-barra">' +
        '<div class="parcela-progreso-barra-track"><div class="' + claseFill + '" style="width:' + pct + '%"></div></div>' +
        "</div></div>";
    }
    var partes = [];
    // Sin marca de check delante (2026-08-17, pedido explícito: "eliminar todos los emojis... ✓ ✅...");
    // el propio texto ("Referencia catastral: ...") ya dice que es un dato encontrado, sin necesitar un
    // glifo de confirmación al lado.
    if (p.referenciaCatastral) {
      partes.push('<p class="parcela-estado-sitio parcela-estado-sitio-ok">Referencia catastral: <strong>' +
        escapeHtml(p.referenciaCatastral) + "</strong></p>");
    }
    if (p.superficieM2) {
      partes.push('<p class="parcela-estado-sitio parcela-estado-sitio-ok">Superficie obtenida de Catastro: <strong>' +
        escapeHtml(Math.round(p.superficieM2)) + " m²</strong></p>");
    }
    if (p.ciudadDetectada) {
      partes.push('<p class="parcela-estado-sitio parcela-estado-sitio-ok">Municipio: <strong>' + escapeHtml(p.ciudadDetectada) + "</strong></p>");
    }
    if (p.errorSitio) {
      partes.push('<p class="parcela-estado-sitio parcela-estado-sitio-aviso">No hemos podido consultar Catastro para este punto exacto ' +
        "(" + escapeHtml(p.errorSitio) + "). Puedes continuar igual: rellenarás estos datos a mano en el siguiente paso.</p>");
    }
    if (p.sinParcelaEnPunto) {
      // Reformulado (2026-08-16, PRD §8.5): antes esta rama compartía el mismo texto de arriba
      // ("No hemos podido consultar Catastro…"), como si fuera un fallo nuestro de conexión. Este
      // caso es distinto y más frecuente: Catastro respondió con normalidad, y tras la espiral de
      // proximidad del servidor (5/10/20m) sigue sin haber ninguna parcela catastrada aquí --  un
      // hecho real sobre el punto (vía pública, parque…), no un error del sistema. Menos alarmante,
      // igual de honesto: nunca dice que encontró algo que no encontró.
      partes.push('<p class="parcela-estado-sitio parcela-estado-sitio-aviso">No hemos encontrado una parcela catastrada en este punto ni en los alrededores más próximos. ' +
        "Puedes continuar igual: rellenarás estos datos a mano en el siguiente paso.</p>");
    }
    if (!partes.length) {
      partes.push('<p class="parcela-estado-sitio">Punto seleccionado (' + p.lat.toFixed(5) + ", " + p.lon.toFixed(5) + "). Sin más datos de Catastro para este punto.</p>");
    }
    return partes.join("");
  }

  //: Referencia catastral y coordenadas parecen identificar una parcela real, pero `ldt` es texto libre de
  //: Catastro ("CL GRAN VIA 31 MADRID (MADRID)") -- este parseo es un best-effort (el municipio suele ir
  //: entre paréntesis al final), NUNCA se trata como un Hecho verificado. Se pone en Ciudad/municipio como
  //: punto de partida editable, igual que el resto de "Mapa/Parcela Primero".
  function municipioDesdeDireccionCatastro(direccion) {
    if (!direccion || typeof direccion !== "string") return null;
    var m = /\(([^)]+)\)\s*$/.exec(direccion.trim());
    if (!m) return null;
    var texto = m[1].trim();
    if (!texto) return null;
    return texto.charAt(0) + texto.slice(1).toLowerCase();
  }

  function actualizarEstadoSitioEnDom() {
    var el = document.getElementById("parcela-estado-sitio");
    if (el) el.innerHTML = htmlEstadoSitio();
  }

  //: `wireParcelaInicial()` monta el mapa de forma asíncrona (espera a que cargue Leaflet) y guarda su
  //: "handle" en una variable LOCAL a esa función -- pero `consultarSitio` (que necesita ese handle para
  //: dibujar el contorno real de la parcela) se llama tanto desde dentro de `wireParcelaInicial` (clic en el
  //: mapa) como desde fuera (clic en un resultado de búsqueda, mismo sitio) y en ambos casos es la MISMA
  //: pantalla con el MISMO mapa -- de ahí este único handle a nivel de módulo en vez de duplicar la lógica.
  var _mapaHandleParcela = null;

  //: `etiqueta` (opcional, 2026-08-17): el texto legible que se guarda en el historial de búsquedas
  //: recientes -- viene del resultado de Nominatim cuando la selección fue por búsqueda, o falta del
  //: todo en un clic directo sobre el mapa (se rellena entonces con el municipio que devuelva Catastro,
  //: o como último recurso las coordenadas en crudo -- ver el guardado más abajo).
  function consultarSitio(lat, lon, etiqueta) {
    if (!E.parcela) E.parcela = { lat: null, lon: null, cargandoSitio: false, sitio: null, errorSitio: null };
    E.parcela.lat = lat;
    E.parcela.lon = lon;
    E.parcela.cargandoSitio = true;
    E.parcela.errorSitio = null;
    E.parcela.sinParcelaEnPunto = null;
    E.parcela.referenciaCatastral = null;
    E.parcela.superficieM2 = null;
    E.parcela.ciudadDetectada = null;
    // Geometría vectorial real (polígono de Catastro) -- bug reportado en vivo, 2026-08-16: se
    // dibujaba en el mapa del Paso 0 (`dibujarParcela` más abajo) pero nunca se guardaba en `E.parcela`,
    // así que se perdía en cuanto se salía de esta pantalla. Ahora persiste aquí para que
    // `wireEleccion()` pueda pasársela tal cual al Sandbox (ver `window.ArchmuseSandbox.open`) en vez de
    // obligar al Sandbox a volver a pedirla de cero (más lento, y con su propio límite de tiempo que
    // puede no darle tiempo a Catastro/Overpass a responder -- ver `viewer-terreno.js`).
    E.parcela.geometriaParcela = null;
    // Fase 1 real: se fija justo antes de despachar el `fetch` de abajo, no antes (ver comentario grande
    // sobre honestidad del progreso en `htmlEstadoSitio`).
    E.parcela.progresoPct = 20;
    E.parcela.progresoTexto = "Conectando con Catastro…";
    actualizarEstadoSitioEnDom();
    // Borra el contorno de una parcela anterior (si lo había) en cuanto se elige un punto nuevo -- sin esto
    // se quedaría pegado al mapa mostrando la forma de la parcela vieja mientras se resuelve la nueva.
    if (_mapaHandleParcela && _mapaHandleParcela.dibujarParcela) _mapaHandleParcela.dibujarParcela(null);

    var resuelta = false;
    // Fase 2 real (2026-08-16): solo se dispara si esta MISMA petición sigue de verdad pendiente al
    // llegar el umbral -- comprobado con `resuelta` y con que el punto no haya cambiado mientras tanto.
    var idFase2 = setTimeout(function () {
      if (resuelta) return;
      if (E.parcela == null || E.parcela.lat !== lat || E.parcela.lon !== lon) return;
      E.parcela.progresoPct = 60;
      E.parcela.progresoTexto = "Catastro está tardando más de lo habitual — puede estar buscando la parcela más próxima…";
      actualizarEstadoSitioEnDom();
    }, UMBRAL_FASE_PROXIMIDAD_MS);

    // Fase 3 y 4 (2026-08-17, mensajería de paciencia -- ver comentario grande junto a los umbrales):
    // mismo guardián `resuelta` + mismo punto que la Fase 2 de arriba.
    var idFase3 = setTimeout(function () {
      if (resuelta) return;
      if (E.parcela == null || E.parcela.lat !== lat || E.parcela.lon !== lon) return;
      E.parcela.progresoPct = 75;
      E.parcela.progresoTexto = "Procesando datos de Catastro. Por favor, espere un momento…";
      actualizarEstadoSitioEnDom();
    }, UMBRAL_FASE_PROCESANDO_MS);
    var idFase4 = setTimeout(function () {
      if (resuelta) return;
      if (E.parcela == null || E.parcela.lat !== lat || E.parcela.lon !== lon) return;
      E.parcela.progresoPct = 90;
      E.parcela.progresoTexto = "Sigue buscando. Los servicios oficiales están tardando un poco más, por favor no cierre la ventana…";
      actualizarEstadoSitioEnDom();
    }, UMBRAL_FASE_SIGUE_BUSCANDO_MS);

    // Timeout de 150s (ampliado 2026-08-17, era 60s desde el fix 2026-08-15 -- se quedaba corto en la
    // práctica: medido en vivo HOY contra una coordenada real de Montepríncipe con Overpass degradado,
    // `/api/analizar-sitio` tardó 127s en responder (geometría de Catastro resuelta bien, las 4 consultas
    // a Overpass -- colindantes/viales/zonas_verdes/equipamientos -- agotando sus 3 reintentos cada una).
    // 150s da margen real por encima de ese peor caso ya observado, no de una estimación teórica. Nunca
    // vuelve a pagarse dos veces: la respuesta (con o sin errores parciales de Overpass) se cachea de
    // inmediato en SQLite (`app.py:analizar_sitio`), así que un clic posterior sobre el mismo punto
    // responde en <1s sin salir a la red (ver `UMBRAL_FASE_PROXIMIDAD_MS` más arriba para el aviso
    // honesto de "está tardando más de lo habitual" mientras se espera la primera vez).
    apiFetch("POST", "/api/analizar-sitio", { lat: lat, lon: lon }, 150000).then(function (res) {
      resuelta = true;
      clearTimeout(idFase2);
      clearTimeout(idFase3);
      clearTimeout(idFase4);
      // Coherencia elemental: si el usuario ya volvió a hacer clic en otro punto mientras esta petición
      // seguía en el aire, esta respuesta (del punto ANTERIOR) se descarta -- nunca pisa al punto actual.
      if (E.parcela == null || E.parcela.lat !== lat || E.parcela.lon !== lon) return;
      E.parcela.cargandoSitio = false;
      if (res.network || res.status < 200 || res.status >= 300) {
        E.parcela.errorSitio = (res.body && res.body.error) || "error de red o del servidor";
        actualizarEstadoSitioEnDom();
        return;
      }
      var datos = (res.body.sitio && res.body.sitio.datos) || {};
      E.parcela.referenciaCatastral = datos.referencia_catastral || null;
      var geometria = datos.geometria_parcela;
      E.parcela.superficieM2 = (geometria && geometria.superficie_m2) || null;
      E.parcela.ciudadDetectada = municipioDesdeDireccionCatastro(datos.direccion_catastro);
      // Guarda la geometría completa (tipo/coordenadas/superficie_m2/centro), no solo la superficie --
      // es lo que el Sandbox necesita para dibujar el contorno/pad real sin volver a pedirla (ver
      // comentario grande más arriba, junto al reinicio de este mismo campo).
      E.parcela.geometriaParcela = geometria || null;
      // Contorno REAL de la parcela (no solo el punto del clic) -- bug reportado en vivo: "no señala la
      // parcela de donde pincho". `geometria.coordenadas` viene de Catastro (WFS), null si Catastro no tenía
      // ninguna parcela en ese punto exacto -- en ese caso `dibujarParcela(null)` ya la borró arriba.
      if (_mapaHandleParcela && _mapaHandleParcela.dibujarParcela) {
        _mapaHandleParcela.dibujarParcela(geometria && geometria.coordenadas);
      }
      if (!datos.referencia_catastral && (datos.errores || []).length) {
        // Catastro (con o sin espiral de proximidad, `analyzer/sitio.py`) respondió con normalidad y no
        // tenía ninguna parcela ahí -- `obtener_datos_parcela` nunca lanza, así que esto no es un error
        // HTTP. Va a `sinParcelaEnPunto`, no a `errorSitio`: mismo hecho de siempre, tono reformulado
        // (ver PRD §8.5 y el comentario grande en `htmlEstadoSitio`).
        E.parcela.sinParcelaEnPunto = datos.errores[0];
      }
      actualizarEstadoSitioEnDom();
      // Carga asíncrona secundaria (2026-08-17, docs/prd/2026-08-17-desacople-paso0-y-parcela-matriz.md,
      // §14 -- alcance aprobado): la respuesta de arriba ya resolvió SOLO Catastro/WFS (rápido) -- este
      // segundo fetch, disparado justo después de pintar la parcela, pide el entorno de Overpass
      // (colindantes/viales/zonas_verdes/equipamientos) que necesita el checklist de campo más adelante
      // (`/api/proyectos/<id>/checklist-campo`). Nadie espera esta promesa (no hay `cargandoSitio`, ni
      // spinner, ni guardián `resuelta` -- el Paso 0 ya quedó libre para continuar). Solo tiene sentido
      // si de verdad hay una parcela que enriquecer; `apiFetch` nunca lanza (ver su propio comentario),
      // así que un fallo o timeout aquí no muestra nada al arquitecto -- se queda para la próxima vez.
      if (datos.referencia_catastral) {
        apiFetch("POST", "/api/analizar-sitio", { lat: lat, lon: lon, solo_entorno: true }, 150000);
      }
      // Historial de búsquedas recientes (2026-08-17): se guarda en cuanto la petición responde con
      // normalidad (200), tenga o no Catastro parcela en ese punto exacto -- es un historial de
      // "dónde buscaste", no solo de "dónde había parcela". Nunca en el camino de error de red de
      // arriba (ese `return` antes de llegar aquí).
      guardarEnHistorialParcelas(etiqueta || E.parcela.ciudadDetectada, lat, lon);
    });
  }

  function wireParcelaInicial() {
    wireCabeceraComun();
    var mapaHandle = null;
    window.ArchmuseMapPicker.montar(document.getElementById("parcela-mapa-mount"), {
      latInicial: E.parcela ? E.parcela.lat : null,
      lonInicial: E.parcela ? E.parcela.lon : null,
      onClic: function (lat, lon) { consultarSitio(lat, lon); },
    }).then(function (handle) { mapaHandle = handle; _mapaHandleParcela = handle; }).catch(function (err) {
      var mount = document.getElementById("parcela-mapa-mount");
      if (mount) mount.innerHTML = '<p class="parcela-estado-sitio parcela-estado-sitio-aviso">No se ha podido cargar el mapa (' +
        escapeHtml(err.message) + "). Puedes continuar sin seleccionar parcela en el mapa.</p>";
    });

    var inputBuscar = document.getElementById("parcela-buscar-input");
    var cont = document.getElementById("parcela-resultados-busqueda");
    var presetsEl = document.querySelector(".parcela-presets");

    //: Separa el `display_name` que devuelve `/api/geocodificar` ("Gran Vía 31, 28013 Madrid, España")
    //: en una línea PRINCIPAL (la calle/dirección) y una de CONTEXTO (municipio/provincia) -- el encargo
    //: pide distinguir claramente "Calle de los Ciruelos, Boadilla del Monte, Madrid" de "Calle de los
    //: Ciruelos, Alcobendas, Madrid": mismo texto principal, contexto distinto.
    //: La rama del primer segmento numérico viene de la etapa de Nominatim, que ponía el número de
    //: portal como su propio segmento ("31, Gran Vía, ..."). Mapbox (tarea TL-8) ya lo trae unido, así
    //: que hoy no se dispara -- se conserva porque cuesta una línea y protege de que un proveedor
    //: futuro vuelva a partirlo, no porque haga falta ahora.
    function partirDireccion(displayName) {
      var partes = (displayName || "").split(",").map(function (p) { return p.trim(); }).filter(Boolean);
      if (!partes.length) return { principal: displayName || "(sin nombre)", contexto: "" };
      var idx = /^\d+[a-zA-Z]?$/.test(partes[0]) && partes.length > 1 ? 1 : 0;
      var principal = idx === 1 ? partes[0] + " " + partes[1] : partes[0];
      return { principal: principal, contexto: partes.slice(idx + 1).join(", ") };
    }

    // Solapamiento corregido (2026-08-17, "Rediseño buscador estilo Apple Maps"): el desplegable de
    // sugerencias está anclado SOLO a `.parcela-buscador` (la cápsula del input), así que al abrirse
    // pasaba por ENCIMA de los chips de preset de la fila siguiente sin desplazarlos -- se veían las
    // etiquetas de los chips traslúcidas asomando bajo el propio glassmorphism del dropdown. Igual que
    // Apple Maps retira sus accesos directos en cuanto aparecen resultados, los chips se ocultan
    // mientras el dropdown está abierto y vuelven en cuanto se cierra.
    function cerrarDropdown() {
      cont.hidden = true;
      cont.innerHTML = "";
      inputBuscar.setAttribute("aria-expanded", "false");
      if (presetsEl) presetsEl.hidden = false;
    }

    function abrirDropdown(html) {
      cont.innerHTML = html;
      cont.hidden = false;
      inputBuscar.setAttribute("aria-expanded", "true");
      if (presetsEl) presetsEl.hidden = true;
    }

    function mostrarResultados(resultados) {
      if (!resultados.length) { abrirDropdown('<p class="parcela-resultados-vacio muted">Sin resultados.</p>'); return; }
      abrirDropdown(resultados.map(function (r, i) {
        var d = partirDireccion(r.display_name);
        return '<button type="button" class="parcela-resultado-item" role="option" data-resultado-idx="' + i + '">' +
          '<span class="parcela-resultado-principal">' + escapeHtml(d.principal) + "</span>" +
          (d.contexto ? '<span class="parcela-resultado-contexto">' + escapeHtml(d.contexto) + "</span>" : "") +
          "</button>";
      }).join(""));
      Array.prototype.forEach.call(cont.querySelectorAll("[data-resultado-idx]"), function (btn) {
        btn.addEventListener("click", function () {
          var r = resultados[Number(btn.dataset.resultadoIdx)];
          cerrarDropdown();
          inputBuscar.value = r.display_name || "";
          if (mapaHandle) mapaHandle.centrar(r.lat, r.lon);
          consultarSitio(r.lat, r.lon, r.display_name);
        });
      });
    }

    // Historial de búsquedas recientes / parcelas guardadas (2026-08-17, a petición explícita): se
    // muestra al hacer foco en el buscador con el campo todavía vacío, o al borrar el texto hasta
    // dejarlo vacío -- "antes de escribir", tal cual pide el encargo. La primera entrada es siempre la
    // parcela usada más recientemente, ya destacada con su propia etiqueta -- es la "opción para
    // seleccionar rápidamente la última parcela utilizada", sin necesidad de un botón aparte.
    function mostrarHistorial() {
      var historial = leerHistorialParcelas();
      if (!historial.length) { cerrarDropdown(); return; }
      var html = '<div class="parcela-historial-cabecera">Búsquedas recientes</div>' +
        historial.map(function (h, i) {
          return '<button type="button" class="parcela-resultado-item" role="option" data-historial-idx="' + i + '">' +
            '<span class="parcela-resultado-principal">' + escapeHtml(h.displayName) +
            (i === 0 ? ' <span class="parcela-historial-badge">Última</span>' : "") + "</span>" +
            "</button>";
        }).join("") +
        '<button type="button" class="parcela-historial-borrar">Borrar historial</button>';
      abrirDropdown(html);
      Array.prototype.forEach.call(cont.querySelectorAll("[data-historial-idx]"), function (btn) {
        btn.addEventListener("click", function () {
          var h = historial[Number(btn.dataset.historialIdx)];
          cerrarDropdown();
          inputBuscar.value = h.displayName || "";
          if (mapaHandle) mapaHandle.centrar(h.lat, h.lon);
          // Se vuelve a consultar Catastro DE VERDAD -- el historial solo guarda dónde estaba la
          // parcela, nunca su última respuesta de Catastro, que podría haber cambiado.
          consultarSitio(h.lat, h.lon, h.displayName);
        });
      });
      var borrarBtn = cont.querySelector(".parcela-historial-borrar");
      if (borrarBtn) {
        borrarBtn.addEventListener("click", function (ev) {
          ev.stopPropagation();
          borrarHistorialParcelas();
          cerrarDropdown();
        });
      }
    }

    function buscar() {
      var texto = inputBuscar.value.trim();
      if (!texto) { mostrarHistorial(); return; }
      abrirDropdown('<p class="muted">Buscando…</p>');
      var textoDeEstaLlamada = texto;
      apiFetch("GET", "/api/geocodificar?q=" + encodeURIComponent(texto)).then(function (res) {
        // El usuario puede haber seguido escribiendo (o borrado el texto) mientras esta petición seguía en
        // el aire -- una respuesta tardía de una búsqueda ya obsoleta nunca debe pisar al dropdown actual.
        if (inputBuscar.value.trim() !== textoDeEstaLlamada) return;
        if (res.network || res.status < 200 || res.status >= 300) {
          abrirDropdown('<p class="parcela-estado-sitio parcela-estado-sitio-aviso">No se ha podido buscar esa dirección ahora mismo.</p>');
          return;
        }
        mostrarResultados(res.body.resultados || []);
      });
    }
    document.getElementById("parcela-buscar-btn").addEventListener("click", buscar);

    // Presets de direcciones destacadas (2026-08-16, docs/prd/2026-08-16-presets-progreso-y-zocalo-
    // sandbox.md): mismo camino EXACTO que elegir un resultado de `mostrarResultados` -- geocodifica,
    // centra el mapa y llama a `consultarSitio` -- nunca un atajo que se salte Catastro. El botón se
    // deshabilita mientras resuelve para que no se pueda disparar dos veces seguidas la misma consulta.
    function activarPreset(preset, btn) {
      inputBuscar.value = preset.etiqueta;
      cerrarDropdown();
      btn.disabled = true;
      var textoOriginal = btn.textContent;
      btn.textContent = "Buscando…";
      apiFetch("GET", "/api/geocodificar?q=" + encodeURIComponent(preset.query)).then(function (res) {
        btn.disabled = false;
        btn.textContent = textoOriginal;
        if (res.network || res.status < 200 || res.status >= 300) {
          abrirDropdown('<p class="parcela-estado-sitio parcela-estado-sitio-aviso">No se ha podido buscar esa dirección ahora mismo.</p>');
          return;
        }
        var resultados = res.body.resultados || [];
        if (!resultados.length) {
          abrirDropdown('<p class="parcela-resultados-vacio muted">Sin resultados.</p>');
          return;
        }
        var r = resultados[0];
        inputBuscar.value = r.display_name || preset.etiqueta;
        if (mapaHandle) mapaHandle.centrar(r.lat, r.lon);
        consultarSitio(r.lat, r.lon, r.display_name || preset.etiqueta);
      });
    }
    Array.prototype.forEach.call(document.querySelectorAll("[data-preset-idx]"), function (btn) {
      btn.addEventListener("click", function () {
        activarPreset(PRESETS_PARCELA[Number(btn.dataset.presetIdx)], btn);
      });
    });

    // Foco en el buscador con el campo vacío -> historial, "antes de escribir" (encargo explícito).
    inputBuscar.addEventListener("focus", function () {
      if (!inputBuscar.value.trim()) mostrarHistorial();
    });

    // Búsqueda "en tiempo real" mientras se escribe, con espera (debounce) de 400ms tras la última tecla --
    // sin esto, cada pulsación dispararía una llamada a `/api/geocodificar` (y de ahí a Nominatim, que pide
    // explícitamente en su política de uso no bombardearlo con una petición por tecla). 3 caracteres mínimo:
    // menos que eso Nominatim casi nunca devuelve nada útil y solo genera ruido.
    var temporizadorBusqueda = null;
    inputBuscar.addEventListener("input", function () {
      if (temporizadorBusqueda) clearTimeout(temporizadorBusqueda);
      var texto = inputBuscar.value.trim();
      if (!texto) { mostrarHistorial(); return; }
      if (texto.length < 3) { cerrarDropdown(); return; }
      temporizadorBusqueda = setTimeout(buscar, 400);
    });
    inputBuscar.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") { ev.preventDefault(); if (temporizadorBusqueda) clearTimeout(temporizadorBusqueda); buscar(); }
      if (ev.key === "Escape") { cerrarDropdown(); }
    });
    // Cerrar al hacer clic fuera del buscador (fuera del input Y del propio dropdown) -- sin esto, el
    // desplegable se quedaría abierto tapando el mapa hasta la siguiente búsqueda.
    document.addEventListener("click", function (ev) {
      if (cont.hidden) return;
      if (ev.target === inputBuscar || cont.contains(ev.target)) return;
      cerrarDropdown();
    });

    // El botón "Laboratorio — practicar sin una parcela real" se retiró (2026-08-17, pedido
    // explícito) -- no hacía falta como control aparte: "Continuar" ya lleva a la pantalla de
    // elección exista o no una parcela elegida (`E.parcela` sigue como estaba, `null` si el
    // usuario no llegó a tocar el mapa/buscador), así que un clic directo en "Continuar" sin
    // elegir parcela produce exactamente el mismo resultado que tenía "omitir".
    document.getElementById("parcela-continuar").addEventListener("click", function () {
      E.vista = "eleccion";
      render();
    });
  }

  // =========================================================================
  // Pantalla: elección (E1) — entrevista guiada / modo experto
  // =========================================================================

  function vistaEleccion() {
    return cabecera("Generar proyecto con IA", { ocultarNuevo: true, textoVolver: "Cancelar" }) +
      // Intro recortada a una frase y sin emoji en las tres opciones (2026-08-17, pedido
      // explícito: "elimina todos los emojis" + "sin frases largas explicativas, la app debe
      // hablar por sí sola") -- las tres tarjetas ya dicen qué hace cada camino.
      '<div class="entrevista-card">' +
      '<p class="muted entrevista-intro">Elige cómo quieres definir tu proyecto.</p>' +
      '<div class="entrevista-eleccion-grid">' +
      '<button type="button" class="eleccion-opcion" id="ent-elegir-guiada">' +
      "<h3>Entrevista guiada</h3>" +
      '<p class="muted">Te hacemos las preguntas una a una, en lenguaje normal. Ideal si no sabes por dónde empezar.</p>' +
      "</button>" +
      '<button type="button" class="eleccion-opcion" id="ent-elegir-experta">' +
      "<h3>Modo experto</h3>" +
      '<p class="muted">Rellena tú directamente los datos técnicos del proyecto, organizados por categorías. Pensado para arquitectos.</p>' +
      "</button>" +
      '<button type="button" class="eleccion-opcion" id="ent-elegir-sandbox">' +
      "<h3>Lienzo libre</h3>" +
      '<p class="muted">Dibuja volúmenes a mano sobre la parcela real y, cuando quieras, conviértelos en parámetros para generar el proyecto.</p>' +
      "</button>" +
      "</div></div>";
  }

  function wireEleccion() {
    document.getElementById("ent-elegir-guiada").addEventListener("click", function () {
      var parcela = null;
      if (E.parcela && E.parcela.lat != null) {
        parcela = {};
        if (E.parcela.ciudadDetectada) parcela.ciudad = E.parcela.ciudadDetectada;
        if (E.parcela.superficieM2) parcela.superficie_m2 = E.parcela.superficieM2;
      }
      crearEntrevista("entrevista_guiada", null, parcela);
    });
    document.getElementById("ent-elegir-experta").addEventListener("click", function () {
      E.expertoValores = {};
      E.expertoTocados = {};
      E.errorExperto = null;
      // "Mapa/Parcela Primero": si el Paso 0 consultó una parcela real, modo experto arranca con lo que
      // Catastro ya confirmó -- rellenado, no bloqueado (el arquitecto puede corregirlo si Catastro se
      // equivocó de parcela). `solar.forma` NO se rellena: la geometría real de Catastro es un polígono
      // arbitrario, no "rectangular"/"irregular" -- inventar esa etiqueta sería precisamente el tipo de dato
      // fabricado que este proyecto evita en todo el resto del código.
      if (E.parcela && E.parcela.lat != null) {
        if (E.parcela.ciudadDetectada) E.expertoValores["contexto.ciudad"] = E.parcela.ciudadDetectada;
        if (E.parcela.superficieM2) E.expertoValores["solar.superficie_m2"] = Math.round(E.parcela.superficieM2);
      }
      E.vista = "experto";
      render();
    });
    document.getElementById("ent-elegir-sandbox").addEventListener("click", function () {
      // El visor de Sandbox (`static/viewer-sandbox.js`) es un overlay independiente de esta SPA -- se
      // superpone sobre la propia pantalla de elección, que sigue debajo tal cual (por eso `close()` en
      // ese módulo no toca `E.vista`: no hay nada que restaurar). Si no hay parcela real (Paso 0
      // omitido), el visor lo indica él mismo con terreno genérico -- nunca se le miente sobre coordenadas.
      if (!window.ArchmuseSandbox) return; // el módulo del visor no cargó -- fallo silencioso, no hay nada útil que hacer aquí
      window.ArchmuseSandbox.open({
        lat: E.parcela && E.parcela.lat != null ? E.parcela.lat : null,
        lon: E.parcela && E.parcela.lon != null ? E.parcela.lon : null,
        // Geometría real ya resuelta en el Paso 0 (ver `consultarSitio`) -- sincronización estricta,
        // bug reportado en vivo 2026-08-16: el Sandbox pintaba un disco genérico y el HUD decía "sin
        // datos reales de parcela" aunque el Paso 0 SÍ hubiera encontrado la parcela, porque nunca
        // recibía esta geometría y tenía que volver a pedirla entera con un límite de tiempo más corto
        // del que ese mismo pipeline puede tardar de verdad (Catastro + Overpass). `null` si el Paso 0
        // se omitió o Catastro no tenía parcela en ese punto -- el Sandbox lo trata igual que siempre
        // (best-effort, nunca inventa un contorno).
        geometriaParcela: E.parcela && E.parcela.geometriaParcela ? E.parcela.geometriaParcela : null,
        // Referencia catastral (2026-08-17, docs/prd/2026-08-17-normativa-urbanistica-capas-fallback.md,
        // Fase A): clave de persistencia local de los límites urbanísticos que el arquitecto rellene a
        // mano en el Sandbox -- `null` si Catastro no encontró parcela exacta en el punto (mismo
        // criterio best-effort de siempre, nunca se inventa una referencia).
        referenciaCatastral: E.parcela && E.parcela.referenciaCatastral ? E.parcela.referenciaCatastral : null,
        // Municipio ya resuelto en el Paso 0 (`municipioDesdeDireccionCatastro`) -- solo para componer
        // la cabecera del Sandbox ("Parcela RC... — Madrid"); no es un dato normativo, así que no tiene
        // el mismo criterio de honestidad estricta que `limitesUrbanisticos` (nunca se inventa: si no
        // hay municipio detectado, la cabecera simplemente no lo añade).
        ciudadDetectada: E.parcela && E.parcela.ciudadDetectada ? E.parcela.ciudadDetectada : null,
        onGenerar: function (datos) {
          window.ArchmuseSandbox.close();
          E.expertoValores = {};
          E.expertoTocados = {};
          E.errorExperto = null;
          if (E.parcela && E.parcela.lat != null) {
            if (E.parcela.ciudadDetectada) E.expertoValores["contexto.ciudad"] = E.parcela.ciudadDetectada;
          }
          // El volumen dibujado a mano SUSTITUYE la superficie de Catastro (si la había): es la intención
          // explícita del arquitecto, más específica que la superficie bruta de la parcela.
          E.expertoValores["solar.superficie_m2"] = datos.superficie_m2;
          E.expertoValores["solar.forma"] = datos.forma;
          E.expertoValores["edificio.plantas"] = datos.plantas;
          // Programa de Necesidades del Sandbox (2026-08-17, encargo explícito): "viviendas objetivo" +
          // "% distribución por tipología" llegan ya traducidos a `{dorm_1, dorm_2, dorm_3}` (ver
          // `mixViviendasDesdePrograma` en viewer-sandbox.js) -- mismo campo `programa.num_viviendas_mix`
          // que ya rellena la pantalla de edición experta a mano. `undefined`/`null` (el arquitecto no
          // llegó a fijar viviendas objetivo) simplemente no se rellena: el experto lo pide como
          // cualquier otro campo vacío, nunca se inventa un mix aquí.
          if (datos.mix_viviendas) E.expertoValores["programa.num_viviendas_mix"] = datos.mix_viviendas;
          // Sólido Capaz persistente: `datos.solido_capaz` es `null` si el arquitecto no lo calculó en
          // el Sandbox -- no se inventa uno aquí, se transporta tal cual (ver `handleGenerar`).
          E.solidoCapaz = datos.solido_capaz || null;
          E.vista = "experto";
          render();
        }
      });
    });
  }

  // `parcela` (opcional, solo para `entrevista_guiada`): {ciudad, superficie_m2} ya resueltos de verdad en
  // el Paso 0 (Catastro/mapa) -- "Omite las preguntas geográficas redundantes" (2026-08-15, a petición
  // explícita). El servidor los siembra como Hecho ANTES del primer turno (`interview_motor.sembrar_hecho_
  // externo`) para que la propia cola priorizada del motor deje de proponer las preguntas que ya tienen
  // respuesta -- este módulo nunca decide por su cuenta qué pregunta saltarse (mismo principio de siempre:
  // "nunca decide qué pregunta toca").
  function crearEntrevista(modoEntrada, valores, parcela) {
    E.vista = "creando";
    render();
    var cuerpo = modoEntrada === "edicion_experta" ? { modo_entrada: modoEntrada, valores: valores || {} } : { modo_entrada: modoEntrada };
    if (modoEntrada === "entrevista_guiada" && parcela) cuerpo.parcela = parcela;
    apiFetch("POST", "/api/entrevista", cuerpo).then(function (res) {
      if (res.network) { E.vista = "error_red"; render(); return; }
      if (res.status === 201) {
        E.sesionId = res.body.sesion_id;
        guardarSesion(E.sesionId);
        E.entrevista = res.body;
        E.modoEntrada = modoEntrada;
        if (modoEntrada === "edicion_experta") {
          intentarCompilarYMostrarResumen(0);
        } else {
          E.borrador = {};
          E.historialRespuestas = [];
          E.errorTurno = null;
          E.vista = "turno";
          render();
        }
        return;
      }
      // Fallback defensivo — no debería ocurrir con un body bien formado.
      E.vista = "eleccion";
      render();
      var el = document.getElementById("ent-eleccion-error");
      if (el) el.textContent = (res.body && res.body.error) || "No se ha podido crear la entrevista.";
    });
  }

  // =========================================================================
  // Pantalla: turno (E2/E3/E4) — pregunta abierta / cerrada / bloque fijo
  // =========================================================================

  //: Etiqueta contextual del bloque activo (2026-08-15, a petición explícita: reemplaza el contador
  //: numérico "Lo esencial: X/8", que se quedaba clavado en "8/8" en cuanto los 8 imprescindibles quedaban
  //: resueltos aunque la entrevista seguía preguntando cosas opcionales después). Traducción de
  //: `CATEGORIAS_ESPECIFICACION` (`analyzer/interview/modelo.py`) a texto para el usuario -- puro texto de
  //: presentación, nunca decide nada (mismo criterio que el resto de este catálogo de etiquetas).
  var ETIQUETA_POR_CATEGORIA = {
    contexto_ubicacion: "Ubicación",
    parcela: "Detalles del solar",
    programa_necesidades: "Programa de necesidades",
    usuarios_forma_vida: "Quiénes lo van a usar",
    prioridades_trade_offs: "Prioridades",
    restricciones_normativas: "Normativa",
    entorno_privacidad: "Entorno y privacidad",
    orientacion_clima: "Orientación",
    espacios_exteriores: "Espacios exteriores",
    movilidad_accesos: "Accesos",
    sostenibilidad_eficiencia: "Sostenibilidad",
    identidad_arquitectonica: "Estilo y referencias",
    presupuesto: "Presupuesto",
    relaciones_espaciales_circulacion: "Preferencias de espacio",
    estructura_sistema_constructivo: "Estructura"
  };

  function etiquetaBloqueActivo(entrevista) {
    var pregunta = entrevista.pregunta_actual;
    if (!pregunta) return "Últimos detalles";
    if (pregunta.es_resolucion_contradiccion) return "Aclarando una respuesta";
    // Mientras queden imprescindibles (PRD §2) sin resolver, todo es "Lo esencial" -- el bloque fijo inicial
    // en sí mismo mezcla varias categorías (programa/prioridades) y llamarlo por su categoría técnica no
    // ayudaría al usuario; una vez resueltos, cada pregunta opcional se etiqueta por su propia categoría.
    if (entrevista.cierre.imprescindibles_pendientes.length > 0) return "Lo esencial";
    var primera = pregunta.preguntas && pregunta.preguntas[0];
    if (!primera) return "Lo esencial";
    return ETIQUETA_POR_CATEGORIA[primera.categoria] || prettify(primera.categoria);
  }

  //: Barra de progreso PORCENTUAL y dinámica (sustituye al contador "X/8" fijo). `pasos_estimados_totales`
  //: lo calcula el servidor en cada respuesta (`interview_motor.estimar_pasos_totales`) a partir de la
  //: MISMA cola priorizada que decide qué preguntar -- si se saltan preguntas (geográficas ya resueltas por
  //: el Paso 0, activación condicional, presupuesto de IA agotado...), la estimación se recalcula sola,
  //: nunca hay que tocar nada aquí. Nunca decidimos el total a mano en el cliente -- sería la misma
  //: duplicación de lógica que este archivo evita en todo lo demás.
  function barraProgreso() {
    var entrevista = E.entrevista;
    var hechos = entrevista.turnos_totales;
    // `pasos_estimados_totales` puede faltar en una sesión reanudada de una versión anterior de la app
    // (antes de este cambio) -- `hechos + 1` es un mínimo razonable que nunca deja la barra vacía ni la
    // hace parecer completa antes de tiempo.
    var estimado = typeof entrevista.pasos_estimados_totales === "number" ? entrevista.pasos_estimados_totales : hechos + 1;
    var total = Math.max(estimado, hechos, 1);
    var pct = total > 0 ? Math.min(100, Math.round((hechos / total) * 100)) : 0;
    // Sin más preguntas pendientes: llega SUAVEMENTE al 100% (transición CSS ya existente en
    // `.entrevista-progreso-fill`), nunca se queda clavada por debajo aunque la estimación no fuera exacta.
    if (!entrevista.pregunta_actual) pct = 100;
    return '<div class="entrevista-progreso-wrap">' +
      '<div class="entrevista-progreso-texto">' + escapeHtml(etiquetaBloqueActivo(entrevista)) + "</div>" +
      '<div class="entrevista-progreso-bar" role="progressbar" aria-valuenow="' + pct +
      '" aria-valuemin="0" aria-valuemax="100"><div class="entrevista-progreso-fill" style="width:' + pct + '%"></div></div>' +
      "</div>";
  }

  function botonAnteriorHtml() {
    var deshabilitado = E.enviando || !E.entrevista || !E.entrevista.turnos_totales;
    return '<button type="button" class="btn-ghost entrevista-boton-anterior" id="ent-anterior" ' +
      (deshabilitado ? "disabled" : "") + '>&larr; Anterior</button>';
  }

  function vistaTurno() {
    var entrevista = E.entrevista;
    var pregunta = entrevista.pregunta_actual;
    var puedeCerrar = entrevista.cierre.puede_cerrar;

    var html = cabecera("Cuéntanos tu proyecto", { textoVolver: "Cancelar" });
    html += '<div class="entrevista-card">';
    html += barraProgreso();

    if (pregunta && pregunta.es_resolucion_contradiccion) {
      html += cuerpoContradiccion(pregunta);
    } else if (pregunta) {
      if (pregunta.aviso) html += '<div class="entrevista-aviso">' + escapeHtml(pregunta.aviso) + "</div>";
      html += cuerpoPreguntas(pregunta.preguntas);
    } else {
      // "Pantalla Final de Resumen y Acción" (2026-08-15, a petición explícita): antes esto era un
      // callejón sin salida real -- ni "Terminar" ni "Continuar" se pintaban aquí (los dos estaban
      // condicionados a que hubiera `pregunta`, cosa que este caso por definición no tiene), así que un
      // usuario que agotaba las preguntas se quedaba mirando este párrafo sin ningún botón con el que
      // seguir. El desglose REAL categorizado (parcela/programa/estilo) vive en `vistaResumen()`, un paso
      // más adelante, con datos ya compilados de verdad por el servidor (`POST .../especificacion`);
      // fabricar aquí una segunda versión de ese desglose ANTES de tener esos datos habría sido
      // exactamente el tipo de resultado fingido que este proyecto evita.
      html += '<div class="entrevista-fin">' +
        '<p class="entrevista-fin-titulo">¡Todo listo para diseñar tu proyecto!</p>' +
        '<p class="muted">Ya tenemos lo que hace falta para generar una propuesta completa. Puedes revisar y ' +
        "ajustar cualquier respuesta antes de generar, o seguir directamente.</p></div>";
    }

    if (E.errorTurno) html += bannerError(E.errorTurno);

    html += '<div class="entrevista-acciones entrevista-acciones-turno">';
    html += pregunta ? botonAnteriorHtml() : "<span></span>"; // mantiene el layout de 2 grupos (space-between)
    html += '<div class="entrevista-acciones-derecha">';
    if (pregunta) {
      if (!pregunta.es_resolucion_contradiccion) {
        html += '<button type="button" class="btn-ghost" id="ent-terminar" ' + (E.enviando ? "disabled" : "") + ">" +
          (puedeCerrar ? "Terminar y ver resumen" : "Terminar entrevista") + "</button>";
      }
      html += '<button type="button" class="btn-primary" id="ent-continuar" ' + (E.enviando ? "disabled" : "") + ">" +
        (E.enviando ? "Enviando…" : (pregunta.es_resolucion_contradiccion ? "Confirmar" : "Continuar")) + "</button>";
    } else {
      html += '<button type="button" class="btn-ghost" id="ent-revisar" ' + (E.enviando ? "disabled" : "") + ">Revisar o editar respuestas</button>";
      html += '<button type="button" class="btn-primary" id="ent-generar-desde-fin" ' + (E.enviando ? "disabled" : "") + ">" +
        (E.enviando ? "Comprobando…" : "Generar proyecto con IA") + "</button>";
    }
    html += "</div></div></div>";
    return html;
  }

  function cuerpoPreguntas(preguntas) {
    var html = '<div class="entrevista-pregunta-bloque">';
    preguntas.forEach(function (p) {
      html += '<div class="entrevista-pregunta-item" data-pregunta="' + escapeHtml(p.pregunta_id) + '">';
      html += '<div class="entrevista-pregunta-texto">' + escapeHtml(p.texto) + "</div>";
      if (p.tipo === "abierta") {
        html += cuerpoPreguntaAbierta(p);
      } else {
        html += cuerpoPreguntaOpcion(p);
      }
      html += "</div>";
    });
    html += "</div>";
    return html;
  }

  function cuerpoPreguntaAbierta(p) {
    var valorActual = E.borrador[p.pregunta_id] || "";
    var placeholder = PLACEHOLDER_POR_PREGUNTA[p.pregunta_id] || "Escribe tu respuesta…";
    var html = '<textarea class="entrevista-textarea" data-input="' + escapeHtml(p.pregunta_id) + '" rows="3" placeholder="' +
      escapeHtml(placeholder) + '">' + escapeHtml(valorActual) + "</textarea>";
    html += '<button type="button" class="entrevista-delegar-link" data-delegar="' + escapeHtml(p.pregunta_id) + '">' +
      "No lo sé, que decida ArchMuse</button>";
    return html;
  }

  function cuerpoPreguntaOpcion(p) {
    var valorActual = E.borrador[p.pregunta_id];
    var opciones = p.opciones || [];
    // Asesoramiento por opción (2026-08-15, "Materiales y Calidades" -- a petición explícita: "textos
    // breves de ayuda... debajo de cada opción técnica"). Cuando existe, el chip pasa a ser de 2 líneas
    // (etiqueta + ayuda muted) -- clase `.entrevista-opcion-btn-con-ayuda` distingue ese caso en el CSS,
    // el resto de preguntas (sin `asesoramiento`) siguen siendo el botón simple de siempre.
    var html = '<div class="entrevista-opciones-grid' + (p.asesoramiento ? " entrevista-opciones-grid-ayuda" : "") + '">';
    opciones.forEach(function (op) {
      var seleccionada = valorActual === op;
      var ayuda = p.asesoramiento && p.asesoramiento[op];
      html += '<button type="button" class="entrevista-opcion-btn' + (ayuda ? " entrevista-opcion-btn-con-ayuda" : "") +
        (seleccionada ? " seleccionada" : "") + '" data-opcion="' + escapeHtml(p.pregunta_id) + '" data-valor="' + escapeHtml(op) + '">' +
        '<span class="entrevista-opcion-etiqueta">' + escapeHtml(etiquetaOpcion(p, op)) + "</span>" +
        (ayuda ? '<span class="entrevista-opcion-ayuda">' + escapeHtml(ayuda) + "</span>" : "") +
        "</button>";
    });
    html += "</div>";
    var yaHayNoSabe = opciones.indexOf("no_lo_sabe") !== -1;
    if (!yaHayNoSabe && p.tipo === "condicional") {
      // Las condicionales admiten texto libre fuera del catálogo (p3, p8) —
      // se ofrece una caja de texto además de los botones, nunca en vez de.
      html += '<textarea class="entrevista-textarea entrevista-textarea-secundaria" data-input="' + escapeHtml(p.pregunta_id) +
        '" rows="1" placeholder="…o escribe tu propia respuesta">' +
        escapeHtml(typeof valorActual === "string" && opciones.indexOf(valorActual) === -1 ? valorActual : "") + "</textarea>";
    }
    if (!yaHayNoSabe) {
      html += '<button type="button" class="entrevista-delegar-link" data-delegar="' + escapeHtml(p.pregunta_id) + '">' +
        "No lo sé, que decida ArchMuse</button>";
    }
    return html;
  }

  function cuerpoContradiccion(pregunta) {
    var valorActual = E.borrador["__contradiccion__"] || "";
    return '<div class="entrevista-contradiccion-box">' +
      '<div class="entrevista-contradiccion-titulo">Nos diste dos respuestas distintas</div>' +
      "<p>" + escapeHtml(pregunta.texto_resolucion) + "</p>" +
      '<textarea class="entrevista-textarea" data-input="__contradiccion__" rows="2" ' +
      'placeholder="Escribe aquí la respuesta correcta">' + escapeHtml(valorActual) + "</textarea>" +
      "</div>";
  }

  function bannerError(err) {
    return '<div class="error-banner entrevista-error-banner">' + escapeHtml(err.mensaje) +
      (err.reintentar ? ' <button type="button" class="entrevista-link-sutil" id="ent-reintentar-turno">Reintentar</button>' : "") +
      "</div>";
  }

  function wireTurno() {
    wireCabeceraComun();

    Array.prototype.forEach.call(document.querySelectorAll("[data-input]"), function (el) {
      el.addEventListener("input", function () { E.borrador[el.dataset.input] = el.value; });
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-opcion]"), function (btn) {
      btn.addEventListener("click", function () {
        E.borrador[btn.dataset.opcion] = btn.dataset.valor;
        render();
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-delegar]"), function (btn) {
      btn.addEventListener("click", function () {
        E.borrador[btn.dataset.delegar] = "no lo sé, decide tú";
        render();
      });
    });

    var reintentar = document.getElementById("ent-reintentar-turno");
    if (reintentar) reintentar.addEventListener("click", function () { enviarTurno(); });

    var continuar = document.getElementById("ent-continuar");
    if (continuar) continuar.addEventListener("click", function () {
      var pregunta = E.entrevista.pregunta_actual;
      if (pregunta.es_resolucion_contradiccion) { enviarResolucionContradiccion(pregunta); }
      else { enviarTurno(); }
    });

    var terminar = document.getElementById("ent-terminar");
    if (terminar) terminar.addEventListener("click", function () { handleTerminar(false); });

    var anterior = document.getElementById("ent-anterior");
    if (anterior) anterior.addEventListener("click", handleAnterior);

    // Pantalla final ("Revisar o editar respuestas" / "Generar proyecto con IA") -- reutilizan exactamente
    // los mismos caminos ya probados (`handleAnterior`/`handleTerminar`) en vez de duplicar lógica: "revisar"
    // es ir un paso atrás sobre la última respuesta, "generar" es el mismo camino de siempre hacia el
    // resumen ya compilado (que es donde vive el botón real de generación, tras la revisión).
    var revisar = document.getElementById("ent-revisar");
    if (revisar) revisar.addEventListener("click", handleAnterior);
    var generarDesdeFin = document.getElementById("ent-generar-desde-fin");
    if (generarDesdeFin) generarDesdeFin.addEventListener("click", function () { handleTerminar(false); });
  }

  function enviarTurno() {
    var pregunta = E.entrevista.pregunta_actual;
    var respuestas = {};
    pregunta.preguntas.forEach(function (p) { respuestas[p.pregunta_id] = E.borrador[p.pregunta_id] || ""; });
    E.enviando = true;
    E.errorTurno = null;
    render();
    apiFetch("POST", "/api/entrevista/" + E.sesionId + "/responder", { respuestas: respuestas }).then(function (res) {
      E.enviando = false;
      if (res.network) {
        E.errorTurno = { tipo: "red", mensaje: "Error de red. Comprueba tu conexión.", reintentar: true };
        render();
        return;
      }
      if (res.status === 200) {
        // Copia local para "Anterior" (2026-08-15): el servidor ya sabe deshacer su propio estado
        // (`interview_motor.deshacer_ultimo_turno`), pero no conserva el texto/opción cruda que el usuario
        // escribió -- deshacer de verdad la borra. Esta pila es la única forma de rellenar automáticamente
        // la pregunta al volver a ella (requisito explícito del encargo).
        E.historialRespuestas.push({ respuestas: respuestas, esResolucionContradiccion: false });
        E.entrevista = res.body;
        E.borrador = {};
        render();
        return;
      }
      if (res.status === 503) {
        E.errorTurno = { tipo: "ia", mensaje: res.body.error || "No hay ayuda de IA disponible ahora mismo para interpretar esto.", reintentar: true };
        render();
        return;
      }
      if (res.status === 400) {
        E.errorTurno = { tipo: "validacion", mensaje: res.body.error || "Esa respuesta no es válida.", reintentar: false };
        render();
        return;
      }
      if (res.status === 404) { sesionPerdida(); return; }
      if (res.status === 409) {
        // El estado ya no coincide con lo que teníamos (p. ej. una
        // contradicción apareció entre medias) — resincronizamos con el
        // servidor en vez de asumir nada.
        cargarEntrevistaExistente(E.sesionId).then(function () { render(); });
        return;
      }
      E.errorTurno = { tipo: "interno", mensaje: "Ha ocurrido un error inesperado.", reintentar: true };
      render();
    });
  }

  function enviarResolucionContradiccion(pregunta) {
    var valor = (E.borrador["__contradiccion__"] || "").trim();
    if (!valor) {
      E.errorTurno = { tipo: "validacion", mensaje: "Escribe cuál de las dos respuestas es la correcta.", reintentar: false };
      render();
      return;
    }
    E.enviando = true;
    E.errorTurno = null;
    render();
    apiFetch("POST", "/api/entrevista/" + E.sesionId + "/responder", { valor_elegido: valor }).then(function (res) {
      E.enviando = false;
      if (res.network) { E.errorTurno = { tipo: "red", mensaje: "Error de red. Comprueba tu conexión.", reintentar: true }; render(); return; }
      if (res.status === 200) {
        E.historialRespuestas.push({ respuestas: { __contradiccion__: valor }, esResolucionContradiccion: true });
        E.entrevista = res.body;
        E.borrador = {};
        render();
        return;
      }
      if (res.status === 404) { sesionPerdida(); return; }
      E.errorTurno = { tipo: "interno", mensaje: (res.body && res.body.error) || "No se ha podido resolver la contradicción.", reintentar: true };
      render();
    });
  }

  function sesionPerdida() {
    limpiarSesionGuardada();
    E = estadoInicial();
    E.vista = "eleccion";
    render();
  }

  // "Anterior" (2026-08-15, a petición explícita): deshace el turno más reciente -- el servidor
  // (`interview_motor.deshacer_ultimo_turno`, vía `POST .../deshacer`) es quien de verdad revierte el
  // estado (ninguna lógica de "qué pregunta toca" vive aquí, mismo principio de siempre); este módulo solo
  // saca del historial local el texto/opción que el usuario había escrito para esa pregunta y lo deja en
  // `E.borrador`, para que la siguiente `render()` la muestre rellenada automáticamente en vez de en blanco.
  function handleAnterior() {
    if (E.enviando) return;
    if (!E.entrevista || !E.entrevista.turnos_totales) return; // primer paso: nada que deshacer
    var entradaPrevia = E.historialRespuestas.length ? E.historialRespuestas.pop() : null;
    E.enviando = true;
    E.errorTurno = null;
    render();
    apiFetch("POST", "/api/entrevista/" + E.sesionId + "/deshacer", {}).then(function (res) {
      E.enviando = false;
      if (res.network) {
        if (entradaPrevia) E.historialRespuestas.push(entradaPrevia); // no se consumió: se puede reintentar
        E.errorTurno = { tipo: "red", mensaje: "Error de red. Comprueba tu conexión.", reintentar: false };
        render();
        return;
      }
      if (res.status === 200) {
        E.entrevista = res.body;
        // Prefill honesto: si no hay entrada local (p. ej. tras recargar la página, donde este historial no
        // sobrevive), la pregunta a la que se vuelve se muestra en blanco -- nunca se inventa una respuesta.
        E.borrador = entradaPrevia ? entradaPrevia.respuestas : {};
        render();
        return;
      }
      if (res.status === 404) { sesionPerdida(); return; }
      if (entradaPrevia) E.historialRespuestas.push(entradaPrevia);
      E.errorTurno = { tipo: "interno", mensaje: (res.body && res.body.error) || "No se ha podido volver al paso anterior.", reintentar: false };
      render();
    });
  }

  // =========================================================================
  // Terminar / cierre
  // =========================================================================

  function handleTerminar(forzar) {
    E.enviando = true;
    render();
    apiFetch("POST", "/api/entrevista/" + E.sesionId + "/finalizar", { forzar: !!forzar }).then(function (res) {
      E.enviando = false;
      if (res.network) { E.vista = "error_red"; render(); return; }
      if (res.status === 200) { E.entrevista = res.body; intentarCompilarYMostrarResumen(0); return; }
      if (res.status === 404) { sesionPerdida(); return; }
      if (res.status === 409) { E.confirmarCierre = res.body; E.vista = "confirmar_cierre"; render(); return; }
      E.vista = "turno";
      E.errorTurno = { tipo: "interno", mensaje: (res.body && res.body.error) || "No se ha podido terminar la entrevista.", reintentar: true };
      render();
    });
  }

  function vistaConfirmarCierre() {
    var body = E.confirmarCierre;
    var cierre = body.cierre || {};
    var html = cabecera("Todavía falta algo", { textoVolver: "Cancelar" });
    html += '<div class="entrevista-card">';
    html += "<p>" + escapeHtml(body.error) + "</p>";
    if (cierre.imprescindibles_pendientes && cierre.imprescindibles_pendientes.length) {
      html += "<p>Falta por responder:</p><ul class=\"entrevista-lista-pendientes\">";
      cierre.imprescindibles_pendientes.forEach(function (id) {
        var etiqueta = (CAMPO_SCHEMA[id] && CAMPO_SCHEMA[id].etiqueta) || prettify(id.split(".").pop());
        html += "<li>" + escapeHtml(etiqueta) + "</li>";
      });
      html += "</ul>";
    }
    if (cierre.contradicciones_pendientes && cierre.contradicciones_pendientes.length) {
      html += "<p>Además hay una contradicción sin resolver — puedes volver a la entrevista para resolverla.</p>";
    }
    html += '<p class="muted">Puedes seguir respondiendo, o terminar igualmente — lo que falte quedará marcado como pendiente y podrás completarlo en modo experto.</p>';
    html += '<div class="entrevista-acciones">' +
      '<button type="button" class="btn-ghost" id="ent-seguir-respondiendo">Seguir respondiendo</button>' +
      '<button type="button" class="btn-primary" id="ent-terminar-igual">Terminar igualmente</button>' +
      "</div></div>";
    return html;
  }

  function wireConfirmarCierre() {
    wireCabeceraComun();
    document.getElementById("ent-seguir-respondiendo").addEventListener("click", function () {
      E.vista = "turno"; E.errorTurno = null; render();
    });
    document.getElementById("ent-terminar-igual").addEventListener("click", function () { handleTerminar(true); });
  }

  // =========================================================================
  // Compilación → resumen, con el "puente" de datos técnicos si hace falta
  // =========================================================================

  function intentarCompilarYMostrarResumen(intentoNum) {
    E.errorTurno = null; // no arrastrar un banner de error del turno anterior a esta pantalla nueva
    E.vista = "generando"; // reutilizamos la pantalla de carga: "Generando tu proyecto…" no encaja aquí,
    render();               // así que usamos un texto propio.
    viewRoot.querySelector(".entrevista-cargando-texto").textContent = "Comprobando que tenemos todo lo necesario…";
    apiFetch("POST", "/api/entrevista/" + E.sesionId + "/especificacion", {}).then(function (res) {
      if (res.network) { E.vista = "error_red"; render(); return; }
      if (res.status === 200) {
        E.resumen = res.body;
        E.vista = "resumen";
        render();
        return;
      }
      if (res.status === 404) { sesionPerdida(); return; }
      if (res.status === 422) {
        if (intentoNum >= 3) {
          E.cierreBloqueado = res.body;
          E.vista = "cierre_bloqueado";
          render();
          return;
        }
        var analisis = idsDesdeErrores(res.body.errores);
        if (!analisis.ids.length) {
          // No hemos podido mapear ningún error a un campo conocido — se
          // muestra tal cual, nunca se inventa un formulario vacío.
          E.cierreBloqueado = res.body;
          E.vista = "cierre_bloqueado";
          render();
          return;
        }
        var camposBase = {};
        ((res.body.especificacion && res.body.especificacion.campos) || []).forEach(function (c) {
          camposBase[c.especificacion_id] = c.valor;
        });
        E.puente = { ids: analisis.ids, sinMapear: analisis.sinMapear, camposBase: camposBase, intentoNum: intentoNum };
        E.valoresPuente = {};
        E.vista = "puente";
        render();
        return;
      }
      E.vista = "error_interno";
      render();
    });
  }

  // =========================================================================
  // Pantalla: puente de datos técnicos
  // =========================================================================

  function vistaPuente() {
    var html = cabecera("Una última cosa", { textoVolver: "Cancelar" });
    html += '<div class="entrevista-card">';
    html += "<p>Ya casi está. Nos falta confirmar un par de datos técnicos para poder generar el proyecto:</p>";
    html += '<div class="entrevista-experto-grid">';
    E.puente.ids.forEach(function (id) {
      html += campoFormulario(id, E.valoresPuente[id] !== undefined ? E.valoresPuente[id] : E.puente.camposBase[id]);
    });
    html += "</div>";
    if (E.puente.sinMapear.length) {
      html += '<div class="error-banner entrevista-error-banner">';
      E.puente.sinMapear.forEach(function (t) { html += "<div>" + escapeHtml(t) + "</div>"; });
      html += "</div>";
    }
    if (E.errorTurno) html += bannerError(E.errorTurno);
    html += '<div class="entrevista-acciones">' +
      '<button type="button" class="btn-primary" id="ent-continuar-puente" ' + (E.enviando ? "disabled" : "") + ">" +
      (E.enviando ? "Comprobando…" : "Continuar") + "</button></div></div>";
    return html;
  }

  function wirePuente() {
    wireCabeceraComun();
    wireCamposFormulario(E.valoresPuente);
    document.getElementById("ent-continuar-puente").addEventListener("click", function () {
      // Corrección de 2026-08-13 ("trazabilidad epistemológica del
      // puente"): solo se envían los campos que de verdad se están
      // completando/corrigiendo aquí (E.puente.ids — los que causaron el
      // 422), nunca el resto de camposBase sin tocar. Antes se reenviaba
      // TODO camposBase a una sesión nueva vía modo_entrada:"edicion_experta",
      // lo que aplanaba a Hecho cualquier Hipótesis/Inferencia ya recogida
      // por la conversación real. Ahora se llama a /valores_expertos sobre
      // LA MISMA sesión (E.sesionId nunca cambia) — ver
      // `interview_compilador.anadir_valores_expertos()`.
      var valores = {};
      E.puente.ids.forEach(function (id) {
        var v = (E.valoresPuente[id] !== undefined && E.valoresPuente[id] !== "")
          ? E.valoresPuente[id] : E.puente.camposBase[id];
        if (v !== undefined && v !== null && v !== "") valores[id] = v;
      });
      E.enviando = true;
      E.errorTurno = null;
      render();
      apiFetch("POST", "/api/entrevista/" + E.sesionId + "/valores_expertos", { valores: valores }).then(function (res) {
        E.enviando = false;
        if (res.network) { E.vista = "error_red"; render(); return; }
        if (res.status === 200) {
          E.entrevista = res.body;
          intentarCompilarYMostrarResumen(E.puente.intentoNum + 1);
          return;
        }
        if (res.status === 404) { sesionPerdida(); return; }
        E.errorTurno = { tipo: "interno", mensaje: (res.body && res.body.error) || "No se ha podido continuar.", reintentar: false };
        render();
      });
    });
  }

  // =========================================================================
  // Pantalla: cierre bloqueado (no se pudo mapear el error, o 3 intentos)
  // =========================================================================

  function vistaCierreBloqueado() {
    var body = E.cierreBloqueado || {};
    var html = cabecera("No hemos podido generar el proyecto todavía", { textoVolver: "Cancelar" });
    html += '<div class="entrevista-card">';
    html += '<p>Esto es exactamente lo que falta:</p>';
    html += '<div class="error-banner entrevista-error-banner">';
    (body.errores || [body.error]).forEach(function (t) { if (t) html += "<div>" + escapeHtml(t) + "</div>"; });
    html += "</div>";
    html += '<p class="muted">Puedes completarlo directamente en modo experto, con todos los campos a la vista.</p>';
    html += '<div class="entrevista-acciones">' +
      '<button type="button" class="btn-primary" id="ent-ir-a-experto">Abrir modo experto</button></div></div>';
    return html;
  }

  function wireCierreBloqueado() {
    wireCabeceraComun();
    document.getElementById("ent-ir-a-experto").addEventListener("click", function () {
      var body = E.cierreBloqueado || {};
      E.expertoValores = {};
      E.expertoTocados = {};
      ((body.especificacion && body.especificacion.campos) || []).forEach(function (c) {
        E.expertoValores[c.especificacion_id] = c.valor;
      });
      E.errorExperto = null;
      E.vista = "experto";
      render();
    });
  }

  // =========================================================================
  // Pantalla: modo experto (E7) — mismo endpoint, mismo compilador
  // =========================================================================

  // Parseo flexible de un número escrito por el usuario: acepta "500000",
  // "500.000" (miles a la española), "500,5" (decimal a la española),
  // "500,000"/"1,234.56" (miles+decimal a la inglesa), "500.000,50" (miles+
  // decimal a la española), símbolo de moneda y espacios sueltos. Los
  // campos `tipo:"numero"` pasan a ser `<input type="text">` (ver
  // `campoFormulario`) precisamente para que el usuario pueda escribir
  // cualquiera de estas formas -- un `<input type="number">` nativo ya
  // RECHAZA la coma como tecla válida, así que arreglar solo el parseo no
  // habría bastado.
  //
  // Ambigüedad real que esto no puede resolver con certeza: "2.500" podría
  // ser dos mil quinientos (miles) o dos coma cinco (decimal con dos ceros
  // de más, prácticamente inaudito en estos campos). Se asume miles cuando
  // TODOS los grupos tras el separador tienen exactamente 3 dígitos --
  // funciona para "500.000"/"2.500"/"1.234.567", y deja intactos los casos
  // reales de estos campos ("2.8", "2.5", "70") porque ninguno tiene un
  // grupo de exactamente 3 dígitos tras el punto.
  function parseNumeroFlexible(texto) {
    if (texto === null || texto === undefined) return undefined;
    var limpio = String(texto).trim().replace(/[€$\s ]/g, "");
    if (limpio === "") return undefined;

    var tienePunto = limpio.indexOf(".") !== -1;
    var tieneComa = limpio.indexOf(",") !== -1;

    function grupoDeMiles(partes) {
      return partes.length > 1 && partes.slice(1).every(function (p) { return p.length === 3; });
    }

    if (tienePunto && tieneComa) {
      // Los dos presentes: el que aparece EN ÚLTIMO LUGAR es el separador
      // decimal (convención española "1.234,56" o inglesa "1,234.56").
      if (limpio.lastIndexOf(",") > limpio.lastIndexOf(".")) {
        limpio = limpio.replace(/\./g, "").replace(",", ".");
      } else {
        limpio = limpio.replace(/,/g, "");
      }
    } else if (tieneComa) {
      var partesComa = limpio.split(",");
      limpio = grupoDeMiles(partesComa) ? limpio.replace(/,/g, "") : limpio.replace(",", ".");
    } else if (tienePunto) {
      var partesPunto = limpio.split(".");
      if (grupoDeMiles(partesPunto)) limpio = limpio.replace(/\./g, "");
    }

    var valor = parseFloat(limpio);
    return isNaN(valor) ? undefined : valor;
  }

  //: "Mapa/Parcela Primero" (encargo técnico, punto 2): ids DOM explícitos y literales para los tres campos
  //: que el Paso 0 autocompleta, exigidos así por el encargo (`#ciudad`, `#superficie_solar`). No es un
  //: mecanismo genérico -- solo estos dos `data-campo` conocidos ganan un `id=""` además de su `data-campo`
  //: habitual; el resto de campos de `CAMPO_SCHEMA` no lo necesita para nada.
  var IDS_DOM_EXPLICITOS = { "contexto.ciudad": "ciudad", "solar.superficie_m2": "superficie_solar" };

  function campoFormulario(id, valorActual) {
    var campo = CAMPO_SCHEMA[id];
    var esImprescindible = IMPRESCINDIBLES_IDS.indexOf(id) !== -1;
    var idDom = IDS_DOM_EXPLICITOS[id];
    var atrId = idDom ? ' id="' + escapeHtml(idDom) + '"' : "";
    var html = '<div class="entrevista-campo-experto" data-campo-wrap="' + escapeHtml(id) + '">';
    html += '<label class="entrevista-campo-etiqueta">' + escapeHtml(campo.etiqueta) +
      (esImprescindible ? ' <span class="entrevista-badge-imprescindible">imprescindible</span>' : "") + "</label>";

    if (campo.tipo === "seleccion") {
      html += '<select' + atrId + ' class="entrevista-select" data-campo="' + escapeHtml(id) + '">';
      html += '<option value="">— Sin especificar —</option>';
      campo.opciones.forEach(function (par) {
        html += '<option value="' + escapeHtml(par[0]) + '"' + (valorActual === par[0] ? " selected" : "") + ">" +
          escapeHtml(par[1]) + "</option>";
      });
      html += "</select>";
    } else if (campo.tipo === "booleano") {
      html += '<select' + atrId + ' class="entrevista-select" data-campo="' + escapeHtml(id) + '">' +
        '<option value="">— Sin especificar —</option>' +
        '<option value="si"' + (valorActual === true ? " selected" : "") + ">Sí</option>" +
        '<option value="no"' + (valorActual === false ? " selected" : "") + ">No</option>" +
        "</select>";
    } else if (campo.tipo === "numero") {
      // `type="text"` + `inputmode="decimal"`, no `type="number"`: un
      // input number nativo RECHAZA la coma como tecla válida, así que el
      // usuario ni siquiera podría escribir "500,000" o "500,5" para que
      // `parseNumeroFlexible` (`leerCampoSimple`) lo interpretara —
      // `inputmode` conserva el teclado numérico en móvil sin la
      // restricción de teclas del tipo nativo.
      html += '<input' + atrId + ' type="text" inputmode="decimal" class="entrevista-input" data-campo="' + escapeHtml(id) + '" value="' +
        escapeHtml(valorActual == null ? "" : valorActual) + '" placeholder="' + escapeHtml(campo.placeholder || "") + '">';
    } else if (campo.tipo === "texto_largo") {
      html += '<textarea' + atrId + ' class="entrevista-textarea" data-campo="' + escapeHtml(id) + '" rows="2">' +
        escapeHtml(valorActual == null ? "" : valorActual) + "</textarea>";
    } else if (campo.tipo === "mix_viviendas") {
      var mix = (valorActual && typeof valorActual === "object") ? valorActual : {};
      html += '<div class="entrevista-mix-grid">' +
        '<label>1 dorm.<input type="number" min="0" class="entrevista-input" data-campo-mix="' + escapeHtml(id) +
        '" data-mix-parte="dorm_1" value="' + escapeHtml(mix.dorm_1 != null ? mix.dorm_1 : "") + '"></label>' +
        '<label>2 dorm.<input type="number" min="0" class="entrevista-input" data-campo-mix="' + escapeHtml(id) +
        '" data-mix-parte="dorm_2" value="' + escapeHtml(mix.dorm_2 != null ? mix.dorm_2 : "") + '"></label>' +
        '<label>3 dorm.<input type="number" min="0" class="entrevista-input" data-campo-mix="' + escapeHtml(id) +
        '" data-mix-parte="dorm_3" value="' + escapeHtml(mix.dorm_3 != null ? mix.dorm_3 : "") + '"></label>' +
        "</div>";
    } else { // texto
      html += '<input' + atrId + ' type="text" class="entrevista-input" data-campo="' + escapeHtml(id) + '" value="' +
        escapeHtml(valorActual == null ? "" : valorActual) + '" placeholder="' + escapeHtml(campo.placeholder || "") + '">';
    }
    html += "</div>";
    return html;
  }

  function wireCamposFormulario(destino, tocados) {
    // `tocados` es opcional: solo lo usa `wireExperto()` (2026-08-13) para
    // distinguir "el usuario editó este campo de verdad" de "seguía mostrando
    // el valor ya conocido, sin tocar" — el puente (`vistaPuente`) no lo
    // necesita porque ya solo pinta los campos que faltan (`E.puente.ids`).
    Array.prototype.forEach.call(document.querySelectorAll("[data-campo]"), function (el) {
      el.addEventListener("input", function () { leerCampoSimple(el, destino); if (tocados) tocados[el.dataset.campo] = true; });
      el.addEventListener("change", function () {
        leerCampoSimple(el, destino); if (tocados) tocados[el.dataset.campo] = true;
        // Único campo del que depende la visibilidad de otro (ver `vistaExperto()`) -- un
        // re-render completo es seguro aquí porque `campoFormulario` siempre repinta a partir
        // de `E.expertoValores`/`E.valoresPuente`, que ya se acaban de actualizar arriba.
        if (el.dataset.campo === "parcela.tipo_intervencion") render();
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-campo-mix]"), function (el) {
      var actualizar = function () {
        var id = el.dataset.campoMix;
        var actual = (destino[id] && typeof destino[id] === "object") ? destino[id] : {};
        var partes = document.querySelectorAll('[data-campo-mix="' + id + '"]');
        var mix = { dorm_1: 0, dorm_2: 0, dorm_3: 0 };
        Array.prototype.forEach.call(partes, function (p) {
          mix[p.dataset.mixParte] = p.value === "" ? 0 : parseInt(p.value, 10) || 0;
        });
        destino[id] = mix;
        if (tocados) tocados[id] = true;
      };
      el.addEventListener("input", actualizar);
    });
  }

  function leerCampoSimple(el, destino) {
    var id = el.dataset.campo;
    var campo = CAMPO_SCHEMA[id];
    if (campo.tipo === "booleano") {
      destino[id] = el.value === "" ? undefined : el.value === "si";
    } else if (campo.tipo === "numero") {
      destino[id] = el.value === "" ? undefined : parseNumeroFlexible(el.value);
    } else {
      destino[id] = el.value;
    }
  }

  function vistaExperto() {
    var html = cabecera("Modo experto", { textoVolver: "Cancelar" });
    html += '<div class="entrevista-card entrevista-card-ancha">';
    html += '<p class="muted">Rellena directamente los campos que conozcas. Los marcados como ' +
      '<span class="entrevista-badge-imprescindible">imprescindible</span> son necesarios para poder generar el proyecto; ' +
      "el resto es opcional y se guarda igualmente aunque el generador actual todavía no lo use.</p>";

    //: Categorías técnicas avanzadas: nadie sin formación técnica sabe
    //: contestar "¿cuál es tu estructura/sistema constructivo?" sin ayuda, y
    //: obligarlo a verla sin pedirla es justo el "no sé qué es esto" que
    //: esta pantalla intenta evitar. Colapsadas por defecto detrás de un
    //: <details> nativo (accesible, sin JS de apertura/cierre que mantener)
    //: -- solo esta categoría por ahora: es la única que el encargo nombra
    //: explícitamente, y las demás (Presupuesto, Identidad...) sí tienen
    //: sentido para cualquiera que responda la entrevista.
    var CATEGORIAS_AVANZADAS = { estructura_sistema_constructivo: true };
    var htmlAvanzado = "";

    //: `parcela.elementos_a_conservar` solo se muestra cuando el usuario ya declaró
    //: `parcela.tipo_intervencion === "edificacion_existente"` -- mostrarlo siempre sería pedir "qué
    //: conservar de lo existente" incluso en una parcela vacía, que no tiene sentido. `render()` se
    //: vuelve a llamar al cambiar ese selector (ver `wireCamposFormulario`) para que aparezca/desaparezca
    //: sin recargar la página; no hace falta un mecanismo genérico de "campos dependientes" para un solo caso.
    ORDEN_CATEGORIAS.forEach(function (cat) {
      var idsCategoria = Object.keys(CAMPO_SCHEMA).filter(function (id) {
        if (CAMPO_SCHEMA[id].categoria !== cat) return false;
        if (id === "parcela.elementos_a_conservar" && E.expertoValores["parcela.tipo_intervencion"] !== "edificacion_existente") return false;
        return true;
      });
      if (!idsCategoria.length) return;
      var seccion = '<div class="entrevista-experto-seccion">';
      seccion += "<h3>" + escapeHtml(CATEGORIA_LABELS[cat]) + "</h3>";
      // "Mapa/Parcela Primero": si el Paso 0 (`vistaParcelaInicial`) consultó Catastro para un punto real,
      // se muestra aquí lo que se autocompletó -- un indicador de texto plano tipo "Superficie obtenida
      // de Catastro: 444 m²" (sin glifo de check, 2026-08-17), y un campo `#referencia_catastral` en el
      // DOM. La RC no es un `especificacion_id` de `CAMPO_SCHEMA` (no la consume el generador, es solo
      // trazabilidad para el usuario) -- por eso se pinta aparte, no vía `campoFormulario`.
      if (cat === "parcela" && E.parcela && E.parcela.referenciaCatastral) {
        seccion += '<p class="parcela-estado-sitio parcela-estado-sitio-ok">Superficie obtenida de Catastro: <strong>' +
          escapeHtml(Math.round(E.parcela.superficieM2)) + " m²</strong></p>" +
          '<div class="entrevista-campo-experto"><label class="entrevista-campo-etiqueta">Referencia catastral</label>' +
          '<input id="referencia_catastral" type="text" class="entrevista-input" value="' +
          escapeHtml(E.parcela.referenciaCatastral) + '" readonly></div>';
      }
      seccion += '<div class="entrevista-experto-grid">';
      idsCategoria.forEach(function (id) { seccion += campoFormulario(id, E.expertoValores[id]); });
      seccion += "</div></div>";
      if (CATEGORIAS_AVANZADAS[cat]) { htmlAvanzado += seccion; } else { html += seccion; }
    });

    if (htmlAvanzado) {
      html += '<details class="entrevista-avanzado">' +
        '<summary>Parámetros avanzados</summary>' +
        '<p class="muted entrevista-avanzado-nota">Solo si conoces estos datos técnicos — el proyecto se genera igual sin ellos.</p>' +
        htmlAvanzado + "</details>";
    }

    if (E.errorExperto) html += bannerError(E.errorExperto);

    html += '<div class="entrevista-acciones">' +
      '<button type="button" class="btn-primary" id="ent-experto-continuar" ' + (E.enviando ? "disabled" : "") + ">" +
      (E.enviando ? "Comprobando…" : "Continuar") + "</button></div></div>";
    return html;
  }

  function wireExperto() {
    wireCabeceraComun();
    wireCamposFormulario(E.expertoValores, E.expertoTocados);
    document.getElementById("ent-experto-continuar").addEventListener("click", function () {
      // Corrección de 2026-08-13 (mismo principio que el puente,
      // `wirePuente()`): si YA hay una sesión real detrás (`E.sesionId` —
      // entrevista guiada que llegó aquí vía "Editar en modo experto" o vía
      // "Abrir modo experto" tras un cierre bloqueado), esto es una
      // corrección/ampliación sobre ELLA, no una entrevista nueva. Un campo
      // que el usuario NO ha tocado en esta visita (solo se mostraba
      // pre-rellenado con lo que ya se sabía) nunca se reenvía — reenviarlo
      // aplanaría su Hipótesis/Inferencia real a Hecho sin que el usuario lo
      // haya confirmado de verdad. Si NO hay sesión previa (modo experto
      // elegido desde cero en la elección inicial), se envían todos los
      // campos rellenados — comportamiento D7 de siempre, sin cambios.
      var haySesionPrevia = !!E.sesionId;
      var valores = {};
      Object.keys(E.expertoValores).forEach(function (id) {
        if (haySesionPrevia && !E.expertoTocados[id]) return;
        var v = E.expertoValores[id];
        if (v === undefined || v === "") return;
        if (id === "programa.num_viviendas_mix" && (!v.dorm_1 && !v.dorm_2 && !v.dorm_3)) return;
        valores[id] = v;
      });
      if (!haySesionPrevia) {
        crearEntrevista("edicion_experta", valores);
        return;
      }
      if (!Object.keys(valores).length) {
        // Nada tocado de verdad: no hay nada nuevo que declarar, se
        // recompila tal cual sobre lo que ya había.
        intentarCompilarYMostrarResumen(0);
        return;
      }
      continuarModoExpertoSobreSesionExistente(valores);
    });
  }

  function continuarModoExpertoSobreSesionExistente(valores) {
    E.enviando = true;
    E.errorExperto = null;
    render();
    apiFetch("POST", "/api/entrevista/" + E.sesionId + "/valores_expertos", { valores: valores }).then(function (res) {
      E.enviando = false;
      if (res.network) { E.vista = "error_red"; render(); return; }
      if (res.status === 200) {
        E.entrevista = res.body;
        intentarCompilarYMostrarResumen(0);
        return;
      }
      if (res.status === 404) { sesionPerdida(); return; }
      E.errorExperto = { tipo: "interno", mensaje: (res.body && res.body.error) || "No se ha podido continuar.", reintentar: false };
      render();
    });
  }

  // =========================================================================
  // Pantalla: resumen (E5/E6/E8) — plantilla determinista, sin llamadas a IA
  // =========================================================================

  //: Plantilla de procedencia — PRD v2 §27, aplicada aquí literalmente sobre
  //: los campos ya clasificados que devuelve el servidor. Nunca se decide
  //: aquí si un dato es Hecho/Inferencia/Hipótesis: se lee `tipo_dato` +
  //: `confianza`, ya calculados por `compilador.py` (Fase D).
  function fraseCampo(campo) {
    var valor = formatearValor(campo.especificacion_id, campo.valor);
    if (campo.tipo_dato === "inferencia") {
      if (campo.confianza === "Baja") {
        return { frase: "Hemos asumido que " + descripcionCampo(campo) + ": " + valor + ".", aviso: true };
      }
      return { frase: "Entendemos que " + descripcionCampo(campo) + ": " + valor + " (a partir de tus respuestas).", aviso: false };
    }
    return { frase: "Nos dijiste que " + descripcionCampo(campo) + ": " + valor + ".", aviso: false };
  }

  function descripcionCampo(campo) {
    var etiqueta = (CAMPO_SCHEMA[campo.especificacion_id] && CAMPO_SCHEMA[campo.especificacion_id].etiqueta) || campo.etiqueta;
    return etiqueta.charAt(0).toLowerCase() + etiqueta.slice(1);
  }

  function notaDestino(campo) {
    if (campo.destino_generador === "almacenado_sin_uso") {
      return "Esto lo hemos guardado, pero el generador actual todavía no lo usa para diseñar.";
    }
    if (campo.destino_generador === "usado_via_extension_minima") {
      return "Se envía como instrucción adicional al arquitecto IA al generar el proyecto.";
    }
    if (campo.destino_generador === "no_aplica") {
      return "Campo exclusivo de modo experto; hoy no se usa en la generación.";
    }
    return null;
  }

  function vistaResumen() {
    var esp = E.resumen.especificacion;
    var avisos = E.resumen.avisos || [];
    var camposPorCategoria = {};
    esp.campos.forEach(function (c) {
      (camposPorCategoria[c.categoria] = camposPorCategoria[c.categoria] || []).push(c);
    });

    var html = cabecera("Esto es lo que hemos entendido", { textoVolver: "Cancelar" });
    html += '<div class="entrevista-card entrevista-card-ancha">';

    if (avisos.length) {
      html += '<div class="entrevista-aviso">';
      avisos.forEach(function (a) { html += "<div>" + escapeHtml(a) + "</div>"; });
      html += "</div>";
    }

    ORDEN_CATEGORIAS.forEach(function (cat) {
      var campos = camposPorCategoria[cat];
      if (!campos || !campos.length) return;
      html += '<div class="entrevista-resumen-categoria">';
      html += "<h3>" + escapeHtml(CATEGORIA_LABELS[cat]) + "</h3>";
      campos.forEach(function (c) {
        var f = fraseCampo(c);
        var nota = notaDestino(c);
        html += '<div class="entrevista-campo-card' + (f.aviso ? " entrevista-campo-card-aviso" : "") + '">';
        html += "<p>" + escapeHtml(f.frase) + "</p>";
        if (nota) html += '<p class="muted entrevista-nota-destino">' + escapeHtml(nota) + "</p>";
        html += "</div>";
      });
      html += "</div>";
    });

    if (esp.contexto_cualitativo && esp.contexto_cualitativo.directivas && esp.contexto_cualitativo.directivas.length) {
      html += '<div class="entrevista-resumen-categoria">';
      html += "<h3>Instrucciones adicionales para el arquitecto IA</h3>";
      esp.contexto_cualitativo.directivas.forEach(function (d) {
        html += '<div class="entrevista-campo-card">';
        html += '<p><span class="entrevista-badge-' + (d.fuerza === "dura" ? "dura" : "blanda") + '">' +
          (d.fuerza === "dura" ? "Debe cumplirse" : "Preferencia") + "</span> " + escapeHtml(d.texto_origen) + "</p>";
        html += '<p class="muted entrevista-nota-destino">Se envía al arquitecto IA como parte del encargo al generar el proyecto.</p>';
        html += "</div>";
      });
      html += "</div>";
    }

    if (E.errorResumen) html += bannerError(E.errorResumen);

    html += '<div class="entrevista-acciones">' +
      '<button type="button" class="btn-ghost" id="ent-editar-experto">Editar en modo experto</button>' +
      '<button type="button" class="btn-primary" id="ent-generar" ' + (E.enviando ? "disabled" : "") + ">" +
      (E.enviando ? "Generando…" : "Generar proyecto") + "</button></div></div>";
    return html;
  }

  function wireResumen() {
    wireCabeceraComun();
    document.getElementById("ent-editar-experto").addEventListener("click", function () {
      E.expertoValores = {};
      E.expertoTocados = {};
      E.resumen.especificacion.campos.forEach(function (c) { E.expertoValores[c.especificacion_id] = c.valor; });
      E.errorExperto = null;
      E.vista = "experto";
      render();
    });
    document.getElementById("ent-generar").addEventListener("click", function () { handleGenerar(); });
  }

  function handleGenerar() {
    E.enviando = true;
    E.errorResumen = null;
    // Antes: `render()` aquí volvía a pintar el resumen ENTERO (todas las
    // categorías ya rellenadas, avisos, directivas) con solo el botón
    // cambiado a "Generando…" -- el "ruido visual de fondo" durante toda
    // la llamada a `/api/generar`, que puede tardar. Ahora se cede la
    // pantalla a la carga limpia de `app.js` (pasos + barra de progreso),
    // y solo se recupera si hace falta mostrar un error.
    if (window.ArchmuseShell && window.ArchmuseShell.mostrarCargandoGeneracion) {
      window.ArchmuseShell.mostrarCargandoGeneracion("Generando tu proyecto");
    } else {
      render(); // respaldo defensivo si el puente no estuviera disponible -- no debería ocurrir
    }

    // "Mapa/Parcela Primero": `sitio_lat`/`sitio_lon` son las MISMAS coordenadas exactas que
    // `consultarSitio()` (Paso 0) mandó a `/api/analizar-sitio` -- `app.py:_clave_cache_sitio_de` calcula la
    // clave de caché a partir de ellas con el mismo redondeo, así que tienen que llegar tal cual para que
    // `_vincular_sitio_si_corresponde` encuentre el sitio YA cacheado (nunca vuelve a llamar a Catastro/
    // Overpass desde aquí -- eso solo lo dispara `/api/analizar-sitio`, una acción explícita del Paso 0).
    // Funciona igual para modo experto y para entrevista guiada: es una clave nueva y opcional del body de
    // `/api/generar`, ajena a `E.resumen.params` (que ya lo dejó fijado el compilador del servidor).
    var cuerpoGenerar = E.resumen.params;
    if ((E.parcela && E.parcela.lat != null) || E.solidoCapaz) {
      // Copia superficial en vez de mutar `E.resumen.params` directamente: si esta llamada fallara y el
      // usuario reintentara desde el resumen, `E.resumen.params` debe seguir siendo exactamente lo que
      // devolvió el compilador del servidor, sin acumular claves de intentos anteriores.
      cuerpoGenerar = {};
      for (var claveParam in E.resumen.params) { cuerpoGenerar[claveParam] = E.resumen.params[claveParam]; }
      if (E.parcela && E.parcela.lat != null) {
        cuerpoGenerar.sitio_lat = E.parcela.lat;
        cuerpoGenerar.sitio_lon = E.parcela.lon;
      }
      // Sólido Capaz persistente: clave opcional, ajena a `E.resumen.params` (el compilador del
      // servidor no la conoce) -- mismo criterio que `sitio_lat`/`sitio_lon` justo arriba. `app.py:
      // _parse_generar_params` la reenvía tal cual, sin interpretarla, hasta `storage.guardar_proyecto`.
      if (E.solidoCapaz) cuerpoGenerar.solido_capaz = E.solidoCapaz;
    }
    apiFetch("POST", "/api/generar", cuerpoGenerar).then(function (res) {
      E.enviando = false;
      if (res.network) {
        E.errorResumen = { tipo: "red", mensaje: "Error de red al generar el proyecto.", reintentar: true };
        volverAResumenTrasError();
        return;
      }
      if (res.status >= 200 && res.status < 300) {
        limpiarSesionGuardada();
        // "Modo enfocado": el proyecto ya está generado y se va a mostrar el workspace -- restaura el
        // sidebar aquí también (ver `irAtras`), no solo en el camino de Cancelar.
        if (window.ArchmuseShell && window.ArchmuseShell.restaurarSidebar) window.ArchmuseShell.restaurarSidebar();
        var entregar = function () {
          if (window.ArchmuseShell && window.ArchmuseShell.onProyectoGenerado) window.ArchmuseShell.onProyectoGenerado(res.body);
        };
        if (window.ArchmuseShell && window.ArchmuseShell.finalizarCargandoGeneracion) {
          window.ArchmuseShell.finalizarCargandoGeneracion(entregar); // remata la barra al 100% antes de cambiar de pantalla
        } else {
          entregar();
        }
        return;
      }
      E.errorResumen = { tipo: "generacion", mensaje: (res.body && res.body.error) || "No se ha podido generar el proyecto.", reintentar: true };
      volverAResumenTrasError();
    });
  }

  // Cierra la pantalla de carga (limpia los `setInterval` de `app.js` --
  // sin esto seguirían corriendo sobre un DOM que este módulo ya sustituyó)
  // y vuelve a pintar el resumen, ahora con el error visible.
  function volverAResumenTrasError() {
    if (window.ArchmuseShell && window.ArchmuseShell.finalizarCargandoGeneracion) {
      window.ArchmuseShell.finalizarCargandoGeneracion(function () { render(); });
    } else {
      render();
    }
  }

  // =========================================================================
  // Pantalla: error genérico (fallback honesto, nunca oculta el motivo)
  // =========================================================================

  function vistaError(titulo, mensaje) {
    var html = cabecera(titulo, { textoVolver: "Volver" });
    html += '<div class="entrevista-card"><p>' + escapeHtml(mensaje) + "</p>" +
      '<div class="entrevista-acciones"><button type="button" class="btn-primary" id="ent-reintentar-global">Reintentar</button></div></div>';
    return html;
  }

  function wireErrorGenerico() {
    wireCabeceraComun();
    var btn = document.getElementById("ent-reintentar-global");
    if (btn) btn.addEventListener("click", function () {
      if (E.sesionId) { cargarEntrevistaExistente(E.sesionId).then(function () { render(); }); }
      else { E.vista = "eleccion"; render(); }
    });
  }

  // =========================================================================
  // Recuperación tras recarga (E9)
  // =========================================================================

  function cargarEntrevistaExistente(id) {
    return apiFetch("GET", "/api/entrevista/" + id).then(function (res) {
      if (res.network) { E.vista = "error_red"; return res; }
      if (res.status === 200) {
        E.sesionId = id;
        E.entrevista = res.body;
        E.modoEntrada = res.body.modo_entrada;
        if (res.body.estado === "en_curso") {
          E.borrador = {};
          E.errorTurno = null;
          E.vista = "turno";
        } else {
          // "cerrada" (o cualquier otro estado inesperado): lo único que
          // tiene sentido es intentar mostrar el resumen ya compilado, o
          // el puente de datos si aún falta algo — nunca reanudar turnos
          // sobre una entrevista que el servidor ya dio por cerrada.
          intentarCompilarYMostrarResumen(0);
        }
        return res;
      }
      if (res.status === 404) { limpiarSesionGuardada(); E.vista = "eleccion"; return res; }
      E.vista = "error_interno";
      return res;
    });
  }

  // =========================================================================
  // Cableado según vista actual
  // =========================================================================

  function wireVistaActual() {
    switch (E.vista) {
      case "parcela_inicial": wireParcelaInicial(); break;
      case "eleccion": wireEleccion(); break;
      case "turno": wireTurno(); break;
      case "confirmar_cierre": wireConfirmarCierre(); break;
      case "puente": wirePuente(); break;
      case "experto": wireExperto(); break;
      case "resumen": wireResumen(); break;
      case "cierre_bloqueado": wireCierreBloqueado(); break;
      case "error_red": case "error_interno": wireErrorGenerico(); break;
      default: break; // creando / recuperando / generando: sin controles
    }
  }

  // =========================================================================
  // Punto de entrada público
  // =========================================================================

  function iniciar() {
    if (window.ArchmuseShell && window.ArchmuseShell.limpiarContextoSidebar) window.ArchmuseShell.limpiarContextoSidebar();
    // "Modo enfocado" (2026-08-15, a petición explícita): todo el flujo de "Generar proyecto" -- selección
    // de parcela Y las preguntas que vienen después -- oculta el sidebar para que no compita por atención
    // con "seleccionar la ubicación"/responder las preguntas. Se restaura en los dos únicos puntos de salida
    // de este flujo: `irAtras()` (Cancelar/Volver) y tras generar el proyecto con éxito (ver `handleGenerar`).
    if (window.ArchmuseShell && window.ArchmuseShell.enfocarSinSidebar) window.ArchmuseShell.enfocarSinSidebar();
    E = estadoInicial();
    var sesionGuardada = leerSesionGuardada();
    if (sesionGuardada) {
      E.vista = "recuperando";
      render();
      cargarEntrevistaExistente(sesionGuardada).then(function () { render(); });
    } else {
      render();
    }
  }

  window.ArchmuseEntrevista = { iniciar: iniciar };
})();
