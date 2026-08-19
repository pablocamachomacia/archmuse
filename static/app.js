// Extraido de index.html el 2026-08-02 al dividir el archivo unico de
// 5.779 lineas. Contenido intacto: solo cambio de ubicacion.

(function () {
  "use strict";

  // `filtros` vive en `state` (no se reconstruye al cambiar de vivienda en
  // `selectVivienda`) para que los toggles de severidad/disciplina del panel
  // de "Problemas detectados" sean persistentes mientras se navega entre
  // plantas — Requisito 2 ("Los filtros deben ser persistentes...").
  var state = {
    data: null, selectedId: null,
    // Fase 4 (cuadro de superficies): el `File` que se subió a `/api/analizar`,
    // conservado para poder reenviarlo a `/api/exportar-cuadro-superficies`
    // sin que ArchMuse tenga que guardar el DXF original en ningún sitio.
    // Solo vive mientras dura la sesión de un análisis recién hecho -- se
    // limpia en `irAInicio`/`abrirProyecto`, así que un proyecto guardado
    // reabierto de la lista nunca lo hereda de un análisis anterior.
    archivoAnalizado: null,
    // Fase 6 (modo "Cuadro", visible en pantalla sin descargar nada):
    // `null` hasta que se visita el modo por primera vez -- entonces se
    // pide una vez a `/api/cuadro-superficies/estado` y se cachea aquí
    // ({ celdas, solicitudes, cargando, error, respuestasAplicadas,
    // valores, asignaciones, pendientes } -- los tres últimos son el
    // borrador del formulario inline, Fase 6d). Mismo motivo de limpieza
    // que `archivoAnalizado`: se vacía en `irAInicio`/`abrirProyecto`/al
    // analizar un DXF nuevo, para no arrastrar nada de un análisis anterior.
    cuadroTabla: null,
    // Modo "IA" (`modoDiagnosticoHtml`): el diagnóstico narrativo ya NO se
    // pide automáticamente al analizar (ver `app.py` `/api/analizar` y el
    // nuevo endpoint bajo demanda `/api/proyectos/<id>/diagnostico-ia`) --
    // `null` en reposo, `"cargando"` mientras se pide, o `{error}` si falló.
    // El resultado en sí no vive aquí: se escribe directo en
    // `state.data.analisis_ia`, así que se limpia solo con cada `state.data`
    // nuevo. Mismo motivo de limpieza que `cuadroTabla`: se vacía en
    // `irAInicio`/`abrirProyecto`/al analizar un DXF nuevo.
    diagnosticoIaEstado: null,
    // Extractor de pliegos (`POST /api/extraer-pliego`, pantalla "Generar
    // proyecto"): `pliegoEstado` es `null` en reposo, `"cargando"` mientras
    // se extrae, o `{error}` si falló. `pliegoImportado` es la respuesta ya
    // guardada ({id, nombre_archivo, parametros, ...}) una vez extraída --
    // se muestra como tabla de revisión, pero todavía NO se aplica a los
    // campos del formulario de abajo (conector con `ai_generator.py`, PRD
    // aparte, sin aprobar). Mismo motivo de limpieza que `cuadroTabla`: se
    // vacía en `irAInicio`/`abrirProyecto`/al analizar un DXF nuevo/al
    // cancelar el formulario de generación.
    pliegoEstado: null,
    pliegoImportado: null,
    // Error de "Generar proyecto desde este pliego" (Pieza 4) -- aparte de
    // `pliegoEstado.error` (que es de la EXTRACCIÓN) porque son dos fallos
    // de naturaleza distinta y reutilizar el mismo campo habría mezclado
    // sus significados.
    pliegoGenerarError: null,
    // Verificador de cumplimiento (modo "Concurso", `GET /api/proyectos/<id>/
    // verificar-pliego/<pliego_id>`): `pliegosDisponibles` es la lista de
    // `GET /api/pliegos` (null hasta la primera visita al modo, luego un
    // array -- no depende del proyecto abierto, no se limpia con él).
    // `verificacionPliego` sí es por proyecto: null en reposo, `"cargando"`,
    // `{error}`, o `{pliegoId, resultado}` -- mismo motivo de limpieza que
    // `diagnosticoIaEstado`.
    pliegosDisponibles: null,
    verificacionPliego: null,
    // Checklist de inspección en campo (2026-08-16, docs/prd/2026-08-16-checklist-inspeccion-campo.md,
    // `GET /api/proyectos/<id>/checklist-campo`): `null` en reposo, `"cargando"` mientras se pide,
    // `{error}` si falla, o `{bloques, tieneSitioReal, marcados, notas}` una vez cargado --
    // `marcados`/`notas` son el estado INTERACTIVO de las casillas/texto libre (claves = id de ítem),
    // vive solo en memoria del navegador (decisión explícita del PRD §14, no persistido) -- se pierde
    // al recargar o al reabrir el checklist, mismo motivo de limpieza que `verificacionPliego`.
    checklistCampo: null,
    // Selector de estilo (Pieza 4, formulario "Generar proyecto"):
    // `estilosDisponibles` es el catálogo de `GET /api/estilos` (null hasta
    // la primera visita, no depende del proyecto -- mismo criterio que
    // `pliegosDisponibles`). `estiloSeleccionado` es la clave elegida (o
    // `"__personalizado__"`); `estiloPersonalizadoTexto`, el texto libre si
    // se eligió esa opción -- los dos sobreviven a un repintado parcial de
    // la sección para no perder lo ya elegido/escrito.
    estilosDisponibles: null,
    estiloSeleccionado: null,
    estiloPersonalizadoTexto: "",
    // Metadatos de los proyectos guardados (`GET /api/proyectos`). No llevan
    // payload: alimentan la parrilla del Inicio y los recientes del sidebar,
    // que solo necesitan nombre, puntuación, nº de viviendas y miniatura.
    proyectos: [],
    // --- Máquina de estados de la pantalla (iteración 3) ------------------
    // Un solo eje con dos niveles. `modo` SIEMPRE está poblado: "resumen" |
    // "espacio" | "luz" | "normativa" | "problemas" | "ia". Desaparece el
    // estado "ninguna herramienta" de la iteración anterior, porque ahora
    // "resumen" no es la ausencia de modo sino un modo con contenido propio
    // (el informe ejecutivo).
    modo: "resumen",
    // `seleccion` es el FOCO dentro del modo, y tiene prioridad sobre él:
    // null | {tipo:"problema", idx} | {tipo:"habitacion", idx}. Se abandona
    // con Escape, con "volver" o pulsando el vacío del plano — tres salidas
    // al mismo sitio, porque salir nunca debe costar pensar.
    seleccion: null,
    // Lista unificada de problemas de la vivienda activa, calculada una vez
    // en `selectVivienda`. El inspector la indexa por posición, así que no
    // debe reordenarse después de asignarla.
    problemas: [],
    // Índices (dentro de `problemas`) de los 3 puntos del informe ejecutivo,
    // en su orden de presentación. Es lo que empareja el 1-2-3 de la columna
    // derecha con los puntos numerados sobre el plano.
    top3: [],
    // --- Workspace tipo AutoCAD -------------------------------------------
    // `capas` lo fija el modo activo (`presetCapasDeModo`); la línea de
    // comandos (CAPA, ver COMANDOS) permite desviarse, pero esa desviación
    // no sobrevive a un cambio de modo, para que no queden estados
    // contradictorios pegados.
    capas: { rellenos: false, etiquetas: true, norte: true },
    ribbonTab: "vista",
    vistaActiva: "modelo",
    // Panel derecho plegado (especificacion §7.4, Ctrl+2). Se recuerda
    // entre sesiones, igual que el colapso del sidebar.
    inspectorPlegado: false,
    // Barra espaciadora mantenida: habilita el paneo con botón izquierdo,
    // para ratones y trackpads sin botón central.
    espacioPulsado: false,
    filtrosAbiertos: false,
    filtros: {
      severidades: { CRITICO: true, IMPORTANTE: true, RECOMENDACION: true },
      disciplinas: {
        "Normativa CTE": true, "Habitabilidad": true, "Accesibilidad": true,
        "Circulación": true, "Calidad Espacial": true, "Incendios": true
      }
    }
  };

  // ===========================================================================
  // Shell: sidebar lateral persistente
  // Especificación `docs/design/2026-08-01-especificacion-shell.md` v3 §2, §5-6.
  // Estos nodos se buscan UNA vez y no se vuelven a montar nunca: `renderInicio`
  // y `renderWorkspace` solo reescriben `#view-root` y `#sidebar-contexto`.
  // ===========================================================================

  var viewRoot = document.getElementById("view-root");
  var sidebar = document.getElementById("sidebar");
  var sidebarBrand = document.getElementById("sidebar-brand");
  var sidebarCollapse = document.getElementById("sidebar-collapse");
  var sidebarNuevo = document.getElementById("sidebar-nuevo");
  var sidebarInicio = document.getElementById("sidebar-inicio");
  var sidebarContexto = document.getElementById("sidebar-contexto");
  var tooltip = document.getElementById("room-tooltip");
  var loadingTimer = null;
  var loadingStageTimer = null;

  // --- Normativa: el cliente NO la conoce -------------------------------
  // Aquí vivía `CIUDAD_A_CCAA` + `SUPERFICIE_MIN_CCAA` (16 comunidades ->
  // superficie útil mínima) y con ellas `toolNormativaHtml` emitía un
  // veredicto literal "cumple"/"no cumple" desde el navegador. Se han
  // eliminado por tres motivos, en orden de gravedad:
  //
  //   1. Las cifras venían de fuentes secundarias (prensa/portales), sin
  //      verificar contra el texto de ningún decreto, y aun así producían
  //      una afirmación de cumplimiento legal.
  //   2. Contradecían al backend en la misma pantalla: `evaluator.py`
  //      resuelve la superficie mínima por TIPOLOGÍA (30/40/24 m²) y esta
  //      tabla lo hacía por COMUNIDAD (40/36/30...). Para una plurifamiliar
  //      en Madrid: 30 m² según el backend, 40 m² según el navegador.
  //   3. El frontend es capa de presentación. Ningún juicio normativo se
  //      calcula aquí: se pinta el que envía el backend.
  //
  // La superficie mínima aplicada la envía ahora el backend por vivienda
  // en `normativa_aplicada` (`analyzer/api_serializer.py`), que es la que
  // `evaluator.py` ha usado de verdad para puntuar. Diseño del sustituto
  // definitivo (corpus territorial versionado): docs/design/
  // NORMATIVE_RESOLUTION.md y NORMATIVE_ENGINE.md.

  // El triángulo de aviso que precedía a cada línea de problema en los dos
  // tooltips se ha eliminado: eran N iconos idénticos repetidos dentro de
  // una caja cuyo contenido ya son, todo él, problemas.

  // Flecha encadenada: marca en "Problemas detectados" qué problema tiene
  // efectos derivados (`analyzer/chain_effects.py`) y encabeza esa sección
  // dentro del detalle expandido.
  var CHAIN_ICON = "→";

  // Icono por orientación cardinal (Bloque 4, `orientacion_cardinal`): sur/
  // este/sureste reciben más horas de sol directo (☀️), oeste/suroeste/
  // noroeste sol de tarde más tangencial (🌤️), y norte/noreste apenas sol
  // directo (🌙).
  var ORIENT_RATING_LABEL = { "óptima": "Óptima", "aceptable": "Aceptable", "penalizada": "Desfavorable" };
  var ORIENT_RATING_CLASS = { "óptima": "orient-badge-optima", "aceptable": "orient-badge-aceptable", "penalizada": "orient-badge-desfavorable" };

  // Overlay semitransparente del plano SVG en modo "Ver luz natural" —
  // mismos 3 niveles que `ORIENT_RATING_LABEL`/`ORIENT_RATING_CLASS", pero
  // como relleno de plano en vez de badge de texto. Las habitaciones sin
  // regla de orientación ("sin regla") no se colorean.
  var LUZ_OVERLAY_COLOR = {
    "óptima": "#22c55e20", "aceptable": "#eab30820", "penalizada": "#f9731620"
  };

  // Leyenda visible del modo "Luz" (auditoría UX, P0-3): mismos 3 niveles y
  // mismos colores semánticos que `ORIENT_RATING_LABEL`/`ORIENT_RATING_CLASS`
  // (`--color-success`/`--color-warning`/`--color-critical`, vía
  // `.legend-dot-*` en style.css) — no inventa una cuarta paleta, solo hace
  // legible la que ya pinta el plano.
  var LUZ_LEGEND = [
    ["legend-dot-optima", "Óptima"],
    ["legend-dot-aceptable", "Aceptable"],
    ["legend-dot-desfavorable", "Desfavorable"]
  ];

  // Leyenda visible del modo "Espacio" (auditoría UX, P0-3): mismo color por
  // tipo de uso que `analyzer/plan_svg.py::_ROOM_TYPES` — si esa tabla
  // cambia de colores o de categorías, esta debe actualizarse con ella.
  var ESPACIO_LEGEND = [
    ["#d4edda", "Salón / Cocina"],
    ["#dce8f5", "Dormitorio"],
    ["#fdf3e3", "Baño / Aseo"],
    ["#fce8d5", "Terraza"],
    ["#ede8f5", "Tendedero"],
    ["#E9EAEE", "Otro"]
  ];

  // `swatch` es una clase CSS (colores semánticos, ya definidos para los
  // badges de orientación) o, si no existe esa clase, un color hex literal
  // (la paleta fija de `_ROOM_TYPES`, que no depende del tema).
  function legendHtml(items) {
    return '<div class="modo-legend">' +
      items.map(function (it) {
        var esClase = it[0].charAt(0) !== "#";
        var swatch = esClase
          ? '<span class="legend-dot ' + it[0] + '"></span>'
          : '<span class="legend-dot" style="background:' + it[0] + '"></span>';
        return '<span class="legend-item">' + swatch + escapeHtml(it[1]) + "</span>";
      }).join("") +
      "</div>";
  }

  // Techo de "factor de luz natural" (Bloque 15, `factor_luz_natural_pct`)
  // que se considera 100/100 en el badge de calidad lumínica. El CTE DB-HE
  // solo define un mínimo (1.5%, `evaluator.MIN_NATURAL_LIGHT_FACTOR_PCT`),
  // no un techo "excelente" — este valor es puramente una escala 0-100 para
  // el badge (no un recálculo del propio factor), elegida para que una
  // habitación holgadamente por encima del mínimo (habitaciones normales
  // suelen rondar 5-9%) puntúe alto sin saturar de inmediato a 100.
  var LUZ_BADGE_CEIL_PCT = 9.0;

  // El desglose de puntuación por categoría (`analyzer/scoring.py`,
  // `data.desglose_puntuacion.categorias`) vivía solo en el popover del
  // header (`CATEGORY_COLORS`/`renderScoreBreakdownPopover`), retirado con
  // la Shell (`docs/design/2026-08-01-especificacion-shell.md` — la
  // puntuación vive en el informe ejecutivo, no en la barra de aplicación).
  // Ese desglose por categoría no tiene hoy otro sitio en la interfaz: se
  // pierde con este cambio, no se traslada — señalado explícitamente al
  // usuario en el informe de este paso.

  // Umbrales del semáforo — deben coincidir con
  // `evaluator.SCORE_GREEN_THRESHOLD`/`SCORE_YELLOW_THRESHOLD` (85/70).
  var SEMAFORO_INFO = {
    verde: { label: "Verde", desc: "≥85% — buen cumplimiento normativo y de habitabilidad." },
    amarillo: { label: "Amarillo", desc: "70-84% — aceptable, con problemas que conviene corregir." },
    rojo: { label: "Rojo", desc: "<70% — incumplimientos importantes, corrección prioritaria." }
  };
  // Mismo umbral que arriba (70), aislado en su propio número: sirve para
  // decidir si conviene explicar un veredicto "rojo" que la puntuación por
  // sí sola no explicaría — ver `necesitaExplicacionVeredicto` más abajo.
  var SCORE_YELLOW_THRESHOLD = 70;

  function semaforoTitle(valoracion) {
    var info = SEMAFORO_INFO[valoracion];
    return info ? info.label + " (" + info.desc + ")" : "";
  }

  // "Plan de acción" — issues de esta vivienda (o de edificio,
  // sin vivienda propia) de `data.issues_por_impacto` (ya viene ordenado
  // por `puntos_ganados` descendente desde el backend), excluyendo los que
  // no aportan ganancia real (p. ej. su categoría ya estaba a 0 por otros
  // issues — ver `scoring.compute_puntos_ganados`).

  // ---------------------------------------------------------------------
  // Panel "Problemas detectados": agrupación por disciplina, filtros,
  // severidad/coste heurísticos para spatial_quality/circulacion (que no
  // traen esos campos) y referencias de normativa/soluciones — todo esto es
  // una capa de presentación en el frontend, no toca `IssueReport` ni ningún
  // otro dataclass del backend.
  // ---------------------------------------------------------------------

  var DISCIPLINAS = ["Normativa CTE", "Habitabilidad", "Accesibilidad", "Circulación", "Calidad Espacial", "Incendios"];

  // `evaluator.py`/`chain_effects.py` no clasifican sus `IssueReport` por
  // disciplina, solo por `codigo` (p. ej. "CTE-DB-SUA-1") — se deriva aquí
  // buscando fragmentos de texto en `codigo + " " + titulo`. El orden
  // importa: las disciplinas más específicas (Accesibilidad, Incendios,
  // Habitabilidad) se comprueban ANTES que el cajón genérico "Normativa
  // CTE", porque casi todos esos códigos también empiezan por "CTE-DB" y si
  // se comprobara esa regla primero las más específicas no se alcanzarían
  // nunca. "EFICIENCIA*"/"URBANISMO*" no encajan en ninguna de las 6
  // disciplinas del enunciado — caen en "Habitabilidad" como cajón de
  // sastre por ser, como esa disciplina, criterios de bienestar/proyecto
  // sin ser CTE ni accesibilidad ni incendios.
  function _sinAcentos(s) {
    return s.normalize("NFD").replace(/[̀-ͯ]/g, "");
  }

  function disciplinaFor(item) {
    if (item.source === "spatial_quality") return "Calidad Espacial";
    if (item.source === "circulacion") return "Circulación";
    var texto = _sinAcentos((item.codigo + " " + item.titulo).toUpperCase());
    if (texto.indexOf("SUA-2") !== -1 || texto.indexOf("ACCESIB") !== -1 ||
        texto.indexOf("ADAPTAD") !== -1 || texto.indexOf("MOVILIDAD REDUCIDA") !== -1) return "Accesibilidad";
    if (texto.indexOf("-SI-") !== -1 || texto.indexOf("INCENDIO") !== -1 || texto.indexOf("EVACUACION") !== -1) return "Incendios";
    if (texto.indexOf("HABITABILIDAD") !== -1) return "Habitabilidad";
    if (texto.indexOf("CTE-DB") !== -1) return "Normativa CTE";
    return "Habitabilidad";
  }

  // Ni `SpatialIssue` (spatial_quality.py) ni `CirculationRoute`
  // (circulation.py) llevan severidad CRITICO/IMPORTANTE/RECOMENDACION
  // (la primera usa ALTO/MEDIO/BAJO; la segunda no tiene severidad, solo
  // `tipo`) — se traducen aquí a la escala común del panel.
  var SPATIAL_SEVERITY_MAP = { ALTO: "CRITICO", MEDIO: "IMPORTANTE", BAJO: "RECOMENDACION" };

  // Severidad por tipo de recorrido, coherente con cómo clasifica
  // `evaluator.classify_problems` comprobaciones equivalentes: evacuación
  // comparte familia con `evaluate_evacuation_distance` (CRITICO,
  // CTE-DB-SI-3); recorrido absurdo/espacio de paso/baño sin antesala son
  // de habitabilidad (IMPORTANTE, igual que la mayoría de comprobaciones de
  // Bloque 12); pasillo sobredimensionado comparte familia con
  // `circulation_efficiency_result` (RECOMENDACION).
  var CIRC_SEVERITY = {
    recorrido_absurdo: "IMPORTANTE", espacio_de_paso: "IMPORTANTE", bano_sin_antesala: "IMPORTANTE",
    pasillo_sobredimensionado: "RECOMENDACION", evacuacion: "CRITICO"
  };
  var CIRC_TITULO = {
    recorrido_absurdo: "Recorrido cruza una pieza social",
    espacio_de_paso: "Habitación usada como paso obligado",
    bano_sin_antesala: "Baño con acceso directo desde el salón",
    pasillo_sobredimensionado: "Pasillo sobredimensionado",
    evacuacion: "Recorrido de evacuación interior excesivo"
  };
  var CIRC_IMPACTO = {
    recorrido_absurdo: "Obliga a atravesar una pieza social para llegar al baño, restando intimidad al recorrido nocturno.",
    espacio_de_paso: "La habitación pierde privacidad y utilidad real al servir de paso obligado hacia otras piezas.",
    bano_sin_antesala: "El baño queda expuesto directamente a la zona social, sin transición que amortigüe ruido y visibilidad.",
    pasillo_sobredimensionado: "Resta superficie útil aprovechable a la vivienda sin aportar valor de habitabilidad.",
    evacuacion: "En caso de emergencia, el recorrido interior hasta el pasillo o la salida es más largo de lo recomendable."
  };
  var CIRC_SOLUCIONES = {
    recorrido_absurdo: [
      "Reorganizar la distribución para que el baño sea accesible directamente desde la zona de noche.",
      "Añadir un pasillo o distribuidor que conecte los dormitorios con el baño sin cruzar el salón."
    ],
    espacio_de_paso: [
      "Reorganizar la distribución para que esta habitación no quede en el camino entre otras dos piezas.",
      "Dotar a la vivienda de un pasillo o distribuidor dedicado que absorba la circulación."
    ],
    bano_sin_antesala: [
      "Introducir un vestíbulo o antesala entre el salón y el baño.",
      "Reubicar el acceso al baño desde un pasillo o la zona de noche en vez de desde el salón."
    ],
    pasillo_sobredimensionado: [
      "Reducir la longitud o anchura del pasillo hasta el mínimo funcional exigido.",
      "Reorganizar la distribución para absorber ese espacio en una habitación adyacente."
    ],
    evacuacion: [
      "Acercar la pieza más alejada al pasillo o a una salida de la vivienda.",
      "Replantear la distribución para acortar el recorrido interior hasta el punto de evacuación."
    ]
  };

  var SPATIAL_TITULO = {
    tubo: "Habitación con proporción \"tubo\"",
    iluminacion_profunda: "Profundidad de iluminación excesiva",
    escala_humana: "Escala humana inadecuada",
    espacio_muerto: "Espacio muerto o recoveco",
    jerarquia: "Jerarquía espacial deficiente"
  };
  var SPATIAL_IMPACTO = {
    tubo: "Dificulta amueblar la estancia con criterios funcionales y reduce el confort de uso.",
    iluminacion_profunda: "La zona más alejada de la ventana queda con luz natural insuficiente gran parte del día.",
    escala_humana: "La relación entre superficie y altura libre resulta incómoda para el uso previsto de la pieza.",
    espacio_muerto: "El recoveco resultante es difícil de amueblar o aprovechar, y suele acumular desorden.",
    jerarquia: "La distribución no refleja una jerarquía espacial clara entre piezas principales y secundarias."
  };
  var SPATIAL_SOLUCIONES = {
    tubo: [
      "Ajustar la geometría de la habitación para acercar la proporción largo/corto a 1:2.5 o menos.",
      "Fusionar la pieza con una adyacente para lograr una proporción más equilibrada."
    ],
    iluminacion_profunda: [
      "Ampliar el hueco de ventana en fachada para aumentar la penetración de luz natural.",
      "Añadir un segundo hueco (patio, lucernario) que ilumine la zona más profunda de la pieza."
    ],
    escala_humana: [
      "Redimensionar la superficie de la pieza para ajustarla a su altura libre real.",
      "Revisar la altura libre de proyecto si la superficie no puede modificarse."
    ],
    espacio_muerto: [
      "Simplificar el contorno de la habitación para eliminar el recoveco.",
      "Integrar el recoveco en un armario empotrado u otro elemento fijo que lo aproveche."
    ],
    jerarquia: [
      "Redimensionar las piezas para que el salón/cocina sea la de mayor superficie de la vivienda.",
      "Revisar la asignación de usos si la jerarquía de superficies no puede modificarse."
    ]
  };

  // Aquí vivía `NORMATIVA_REF`: 20 códigos internos -> texto normativo,
  // afirmado por el navegador sin que el backend lo enviara. Movido a
  // `analyzer/referencias_normativas.py` y servido por incidencia en
  // `issue.referencia_normativa` (+ `data.normativa_aviso`). El cliente
  // solo lo pinta.

  // Segunda alternativa de solución para problemas de `data.issues`
  // (Bloque 12): `IssueReport.solucion` solo trae una — esta es una vía
  // distinta a esa (p. ej. redistribuir en vez de ampliar), pensada para
  // encajar con cualquier comprobación que comparta el mismo `codigo`.
  var ALT_SOLUCION_GENERICA = "Consultar con un técnico competente otras alternativas de diseño antes de descartar la solución indicada.";
  var ALT_SOLUCION = {
    "CTE-DB-SUA": "Redistribuir la circulación interior para que el itinerario más corto entre piezas cumpla el ancho mínimo.",
    "CTE-DB-SUA-1": "Intercambiar la posición del baño con otra pieza de mayor superficie de la vivienda.",
    "CTE-DB-SUA-2-ITIN": "Fusionar dos estancias de circulación en un único pasillo más ancho.",
    "CTE-DB-SI-3": "Añadir una segunda salida o acortar el recorrido reorganizando la distribución.",
    "CTE-DB-HS": "Añadir un patio o hueco adicional que dé fachada exterior a la estancia.",
    "CTE-DB-HS3": "Instalar un sistema de ventilación mecánica que compense la carencia de ventilación cruzada o natural.",
    "CTE-DB-HE": "Reforzar el aislamiento térmico de la fachada afectada en vez de reorientar la pieza.",
    "CTE-DB-HE-COND": "Instalar carpintería con rotura de puente térmico en la fachada norte afectada.",
    "CTE-DB-HE-ORIENT": "Reforzar el aislamiento térmico de la fachada norte si reorientar el dormitorio no es viable.",
    "CTE-DB-HR": "Reforzar el aislamiento acústico del cerramiento en vez de modificar la distribución.",
    "HABITABILIDAD": "Fusionar la pieza con una adyacente para lograr una proporción más funcional.",
    "HABITABILIDAD-SUP": "Redistribuir superficie desde una pieza adyacente hacia el dormitorio.",
    "HABITABILIDAD-CIRC": "Reorganizar el acceso al baño desde otra zona de la vivienda distinta del salón.",
    "EFICIENCIA": "Redistribuir la vivienda para reducir la superficie de circulación sin tocar piezas habitables.",
    "EFICIENCIA-ENE": "Simplificar la geometría del edificio para reducir la envolvente expuesta al norte.",
    "URBANISMO-OC": "Redistribuir la superficie construida en más plantas para reducir la huella en planta baja.",
    "URBANISMO-ED": "Reducir el número de plantas manteniendo la huella en planta baja.",
    "URBANISMO-AL": "Reducir la altura de planta o el número de plantas hasta cumplir la altura reguladora.",
    "URBANISMO-RETR": "Aumentar las dimensiones de la parcela o revisar el planeamiento aplicable con el ayuntamiento."
  };

  // Estimación de coste (Requisito 3): si el problema ya tiene un efecto en
  // cadena (`chain_effects.py`), ese coste ya es específico del caso real y
  // se prioriza; si no, se usa esta heurística por severidad — coherente
  // con `chain_effects.py`, donde CRITICO tiende a implicar redistribución/
  // obra (Alto), IMPORTANTE ajustes de diseño (Medio) y RECOMENDACION
  // retoques menores (Bajo).
  var COSTE_POR_SEVERIDAD = { CRITICO: "Alto >3000€", IMPORTANTE: "Medio 500-3000€", RECOMENDACION: "Bajo <500€" };

  function costeEstimadoDe(item) {
    if (item.chain && item.chain.impacto_coste_estimado) return item.chain.impacto_coste_estimado;
    return COSTE_POR_SEVERIDAD[item.severity] || COSTE_POR_SEVERIDAD.IMPORTANTE;
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function fadeSwap(el, updateFn) {
    if (!el) { updateFn(); return; }
    el.style.opacity = "0";
    setTimeout(function () {
      updateFn();
      requestAnimationFrame(function () { el.style.opacity = "1"; });
    }, 150);
  }

  // --- Pantalla de upload ------------------------------------------------

  // El archivo elegido vive fuera de `wireUploadScreen` porque la pantalla se
  // vuelve a pintar entera al fallar el análisis. Antes eso obligaba a
  // seleccionar el DXF otra vez, lo cual era una molestia con un error de red
  // y es inaceptable ahora que el "error" puede ser una pregunta —«¿en qué
  // unidad está el plano?»— que el arquitecto tiene que poder contestar sin
  // repetir nada.
  var archivoPendiente = null;

  // Controles de lectura ofrecidos tras un 400 de /api/analizar: la capa de
  // estancias, la unidad, o las dos. Ver `parser.CapaIndeterminada` y
  // `escala.EscalaDetectada`.
  function ajusteLecturaHtml(ajuste) {
    if (!ajuste) return "";
    var bloques = "";

    if (ajuste.capa && ajuste.capa.candidatas && ajuste.capa.candidatas.length) {
      var opciones = ajuste.capa.candidatas.map(function (c) {
        // Sin recuento cuando es la capa que ya se eligió en un intento
        // anterior: ahí no venía del servidor y no hay cifras que enseñar.
        return [c.nombre, c.poligonos
          ? c.nombre + " · " + c.poligonos + " polilíneas, " + c.rotuladas + "% rotuladas"
          : c.nombre];
      });
      var nota = ajuste.capa.candidatas[0].motivo;
      bloques +=
        formSelect("Capa de estancias", "analizar-capa", opciones, opciones[0][0]) +
        (nota ? '<p class="ajuste-nota">' + escapeHtml(nota) + "</p>" : "");
    }

    if (ajuste.escala && ajuste.escala.opciones) {
      var unidades = ajuste.escala.opciones.map(function (u) { return [u, u]; });
      bloques +=
        formSelect("Unidad del dibujo", "analizar-escala", unidades,
          ajuste.escala.sugerencia || "metros");
    }

    if (!bloques) return "";
    return '<div class="ajuste-lectura"><div class="ajuste-lectura-titulo">Ajusta la lectura del plano</div>' +
      bloques + "</div>";
  }

  function renderUpload(errorMsg, ajuste) {
    updateSidebarContext(null);
    viewRoot.innerHTML =
      '<div class="upload-screen bg-technical"><div class="upload-card">' +
      // El subtítulo bajo el título se retiró (2026-08-17, pedido explícito: "la app debe hablar
      // por sí sola") -- era literalmente el mismo mensaje que ya dice el propio dropzone
      // ("Arrastra tu archivo DXF aquí"), justo debajo.
      "<h1>Analiza tu plano</h1>" +
      '<div class="dropzone" id="dropzone" tabindex="0" role="button" aria-label="Seleccionar archivo DXF">' +
      '<div class="dropzone-icon"><svg width="34" height="34" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M12 3v12m0 0l-4-4m4 4l4-4M5 21h14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></div>' +
      '<div class="dropzone-text">Arrastra tu archivo <strong>DXF</strong> aquí</div>' +
      '<div class="dropzone-sub">o haz clic para elegirlo</div>' +
      '<div class="dropzone-file" id="dropzone-file"></div>' +
      '<input type="file" id="dxf-input" accept=".dxf" hidden>' +
      "</div>" +
      '<div class="form-row"><label for="norte-input">Orientación norte</label>' +
      '<div class="input-wrap"><input type="number" id="norte-input" value="0" step="1"><span>&deg;</span></div></div>' +
      '<p class="form-field-ayuda form-row-ayuda">Grados desde el norte real hasta la parte de arriba de tu plano. Si no lo sabes, deja 0.</p>' +
      '<div class="upload-context">' +
      formField("Ciudad", "analizar-ciudad", "text", "", "Madrid",
        "Determina la zona climática y los umbrales normativos que aplica el análisis.") +
      formSelect("Tipología", "analizar-tipologia",
        [["plurifamiliar", "Plurifamiliar"], ["unifamiliar", "Unifamiliar"], ["rehabilitacion", "Rehabilitación"]],
        "plurifamiliar",
        "Vivienda en bloque, unifamiliar o una reforma — cambia los mínimos que exige la normativa.") +
      // Eje distinto de la tipología: es la clave con la que el DB-SI entra en
      // sus tablas. Se deja vacío por defecto y NO se preselecciona vivienda:
      // un uso supuesto y uno declarado no valen lo mismo, y el informe lo dice.
      // El rótulo pasa a lenguaje llano (encargo P0-4 de la auditoría UX):
      // "DB-SI" ya no es el nombre del campo, es la ayuda que explica para
      // qué se usa — se conserva, no se elimina.
      formSelect("¿Para qué se usará el edificio?", "analizar-uso-previsto",
        [["", "Sin declarar"],
         ["RESIDENCIAL_VIVIENDA", "Residencial Vivienda"],
         ["ADMINISTRATIVO", "Administrativo"],
         ["COMERCIAL", "Comercial"],
         ["DOCENTE", "Docente"],
         ["HOSPITALARIO", "Hospitalario"],
         ["RESIDENCIAL_PUBLICO", "Residencial Público"],
         ["PUBLICA_CONCURRENCIA", "Pública Concurrencia"],
         ["APARCAMIENTO", "Aparcamiento"],
         ["ALMACEN", "Almacén"],
         ["OTRO", "Otro"]],
        "",
        "Determina qué exigencias de seguridad aplica el análisis (documento CTE DB-SI). Si no lo sabes, deja «Sin declarar».") +
      "</div>" +
      (errorMsg ? '<div class="error-banner">' + escapeHtml(errorMsg) + "</div>" : "") +
      ajusteLecturaHtml(ajuste) +
      '<button id="btn-analizar" class="btn-primary" disabled>Analizar plano</button>' +
      // Antes el botón deshabilitado no decía por qué: mismo texto exacto
      // aparece/desaparece con `btn.disabled` en `setFile` — nunca hay que
      // sincronizar dos sitios porque solo hay un sitio.
      '<p id="analizar-hint" class="form-field-ayuda form-hint-boton">Sube un archivo DXF para continuar</p>' +
      // Segunda vía de entrada, deliberadamente discreta: la acción
      // principal de esta pantalla es "Analizar plano" (botón primario de
      // arriba), pero un usuario nuevo sin ningún DXF a mano también tiene
      // que poder encontrar "Generar proyecto" sin abrir el sidebar.
      '<p class="upload-alt-link">¿No tienes un plano todavía? ' +
      '<a href="#" id="upload-link-generar">Genera un proyecto con IA</a></p>' +
      "</div></div>";
    var linkGenerar = document.getElementById("upload-link-generar");
    if (linkGenerar) {
      linkGenerar.addEventListener("click", function (e) {
        e.preventDefault();
        renderGenerarForm();
      });
    }
    wireUploadScreen();
  }

  function wireUploadScreen() {
    var dropzone = document.getElementById("dropzone");
    var input = document.getElementById("dxf-input");
    var fileChip = document.getElementById("dropzone-file");
    var btn = document.getElementById("btn-analizar");
    var hint = document.getElementById("analizar-hint");
    var norteInput = document.getElementById("norte-input");
    var selectedFile = null;

    var fileIcon =
      '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M4 1.5h5.5L12.5 4.5V14.5H4V1.5z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>' +
      '<path d="M9.3 1.5V4.5H12.5" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/></svg>';
    var checkIcon =
      '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M3 8.5l3.2 3.2L13 4.8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';

    function setFile(file) {
      if (!file) return;
      if (!/\.dxf$/i.test(file.name)) {
        fileChip.className = "dropzone-file visible file-error";
        fileChip.innerHTML = fileIcon + "<span>Solo se admiten archivos .dxf</span>";
        btn.disabled = true;
        selectedFile = null;
        if (hint) hint.hidden = false;
        return;
      }
      selectedFile = file;
      archivoPendiente = file;
      fileChip.className = "dropzone-file visible";
      fileChip.innerHTML = checkIcon + "<span>" + escapeHtml(file.name) + " · " + formatBytes(file.size) + "</span>";
      btn.disabled = false;
      if (hint) hint.hidden = true;
    }

    // Tras un error, el archivo sigue elegido: contestar a la pregunta y
    // pulsar "Analizar" tiene que bastar.
    if (archivoPendiente) setFile(archivoPendiente);

    dropzone.addEventListener("click", function () { input.click(); });
    dropzone.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
    });
    dropzone.addEventListener("dragover", function (e) { e.preventDefault(); dropzone.classList.add("dragover"); });
    dropzone.addEventListener("dragleave", function () { dropzone.classList.remove("dragover"); });
    dropzone.addEventListener("drop", function (e) {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      setFile(e.dataTransfer.files[0]);
    });
    input.addEventListener("change", function () { setFile(input.files[0]); });

    btn.addEventListener("click", function () {
      if (!selectedFile) return;
      var formData = new FormData();
      formData.append("dxf", selectedFile);
      formData.append("norte", norteInput.value || "0");
      formData.append("ciudad", document.getElementById("analizar-ciudad").value.trim());
      formData.append("tipologia", document.getElementById("analizar-tipologia").value);
      var usoSel = document.getElementById("analizar-uso-previsto");
      if (usoSel && usoSel.value) formData.append("uso_previsto", usoSel.value);

      // Solo van si el intento anterior las pidió. Mientras ArchMuse sepa
      // deducirlas, el formulario no las enseña: son la respuesta a una
      // pregunta, no dos campos más que rellenar cada vez.
      var capaSel = document.getElementById("analizar-capa");
      if (capaSel) formData.append("capa", capaSel.value);
      var escalaSel = document.getElementById("analizar-escala");
      if (escalaSel) formData.append("escala", escalaSel.value);

      renderLoading();
      fetch("/api/analizar", { method: "POST", body: formData })
        .then(function (resp) {
          return resp.json().then(function (json) { return { ok: resp.ok, json: json }; });
        })
        .then(function (result) {
          if (!result.ok) {
            var ajuste = null;
            if (result.json.capa || result.json.escala) {
              // Se conserva lo ya contestado: si primero preguntó por la capa
              // y ahora pregunta por la unidad, la capa elegida no se pierde.
              ajuste = {
                capa: result.json.capa || (capaSel ? { candidatas: [
                  { nombre: capaSel.value, poligonos: 0, rotuladas: 0, motivo: "" }] } : null),
                escala: result.json.escala
              };
            }
            finishLoading(function () {
              renderUpload(result.json.error || "No se pudo analizar el plano.", ajuste);
            });
            return;
          }
          // Se conserva el `File` (Fase 4) antes de soltar `archivoPendiente`:
          // es la única copia en memoria del DXF original, y
          // "Descargar DXF rellenado" lo necesita para reenviarlo tal cual.
          state.archivoAnalizado = archivoPendiente;
          archivoPendiente = null;
          state.cuadroTabla = null; // análisis nuevo -- cualquier tabla cacheada era de otro DXF
          state.diagnosticoIaEstado = null;
          state.pliegoEstado = null;
          state.pliegoImportado = null;
          state.pliegoGenerarError = null;
          state.verificacionPliego = null;
          state.checklistCampo = null;
          state.data = result.json;
          state.selectedId = null;
          finishLoading(function () { renderWorkspace(); });
        })
        .catch(function () {
          finishLoading(function () { renderUpload("Error de red al analizar el plano."); });
        });
    });
  }

  // --- Formulario "Generar proyecto" ----------------------------------------

  // `ayuda` es opcional y por defecto no imprime nada: los call sites que no
  // lo pasan (el formulario de "Generar proyecto") se quedan exactamente
  // igual que antes.
  function formField(label, id, type, value, placeholder, ayuda) {
    var placeholderAttr = placeholder ? ' placeholder="' + escapeHtml(placeholder) + '"' : "";
    return '<div class="form-field"><label for="' + id + '">' + escapeHtml(label) + '</label>' +
      '<input type="' + type + '" id="' + id + '" value="' + escapeHtml(String(value)) + '"' + placeholderAttr + '>' +
      (ayuda ? '<p class="form-field-ayuda">' + escapeHtml(ayuda) + '</p>' : "") +
      '</div>';
  }

  function formSelect(label, id, options, selectedValue, ayuda) {
    return '<div class="form-field"><label for="' + id + '">' + escapeHtml(label) + '</label><select id="' + id + '">' +
      options.map(function (o) {
        var sel = o[0] === selectedValue ? " selected" : "";
        return '<option value="' + o[0] + '"' + sel + ">" + escapeHtml(o[1]) + "</option>";
      }).join("") +
      "</select>" +
      (ayuda ? '<p class="form-field-ayuda">' + escapeHtml(ayuda) + '</p>' : "") +
      "</div>";
  }

  function renderGenerarForm(prefill) {
    var p = prefill || {};
    var proyecto = p.proyecto || {};
    var solar = p.solar || {};
    var edificio = p.edificio || {};
    var mix = p.mix_viviendas || {};
    var normativa = p.normativa || {};

    viewRoot.innerHTML =
      '<div class="generar-screen bg-technical"><div class="generar-card">' +
      // Recortado a una frase (2026-08-17, pedido explícito: sin frases largas explicativas) --
      // conserva solo lo que el formulario de abajo no dice por sí solo (qué tres cosas hay que
      // definir), no la explicación de qué hace la IA con ellas después.
      "<h1>Generar proyecto con IA</h1>" +
      '<p class="muted">Define el solar, el edificio y el mix de viviendas.</p>' +
      '<div id="generar-error"></div>' +

      '<div class="form-section" id="pliego-section"><h3>Pliego de concurso</h3>' + pliegoImportarHtml() + "</div>" +

      '<div class="form-section"><h3>Proyecto</h3><div class="form-grid">' +
      formField("Ciudad", "g-ciudad", "text", proyecto.ciudad || "", "Madrid") +
      formSelect("Tipología", "g-tipologia",
        [["plurifamiliar", "Plurifamiliar"], ["unifamiliar", "Unifamiliar"], ["rehabilitacion", "Rehabilitación"]],
        proyecto.tipologia || "plurifamiliar") +
      "</div></div>" +

      '<div class="form-section"><h3>Solar</h3><div class="form-grid">' +
      formField("Superficie del solar (m²)", "g-superficie", "number", solar.superficie_m2 || 500) +
      formSelect("Forma del solar", "g-forma", [["rectangular", "Rectangular"], ["irregular", "Irregular"]], solar.forma || "rectangular") +
      '<div class="form-field-full" id="g-dims-wrap"><div class="form-grid">' +
      formField("Ancho (m)", "g-ancho", "number", solar.ancho_m || 20) +
      formField("Largo (m)", "g-largo", "number", solar.largo_m || 25) +
      "</div></div>" +
      formField("Orientación norte (°)", "g-norte", "number", solar.norte_grados || 0) +
      "</div></div>" +

      '<div class="form-section"><h3>Edificio</h3><div class="form-grid">' +
      formField("Plantas sobre rasante", "g-plantas", "number", edificio.plantas || 4) +
      formField("Altura libre por planta (m)", "g-altura", "number", edificio.altura_libre_m || 2.8) +
      formSelect("¿Planta baja comercial?", "g-comercial", [["no", "No"], ["si", "Sí"]], edificio.planta_baja_comercial ? "si" : "no") +
      "</div></div>" +

      '<div class="form-section"><h3>Mix de viviendas</h3><div class="form-grid">' +
      formField("Viviendas de 1 dormitorio", "g-dorm1", "number", mix.dorm_1 || 2) +
      formField("Viviendas de 2 dormitorios", "g-dorm2", "number", mix.dorm_2 || 4) +
      formField("Viviendas de 3 dormitorios", "g-dorm3", "number", mix.dorm_3 || 2) +
      formField("Superficie mínima por vivienda (m²)", "g-supmin", "number", mix.superficie_minima_m2 || 45) +
      "</div></div>" +

      '<div class="form-section"><h3>Normativa</h3><div class="form-grid">' +
      formField("Ocupación máxima del solar (%)", "g-ocupacion", "number", normativa.ocupacion_maxima_pct || 70) +
      formField("Retranqueos (m)", "g-retranqueo", "number", normativa.retranqueos_m || 3) +
      formField("Edificabilidad máxima (m²/m²)", "g-edificabilidad", "number",
        normativa.edificabilidad_maxima != null ? normativa.edificabilidad_maxima : "", "p.ej. 2.5") +
      formField("Plantas máximas (normativa)", "g-plantas-maximas", "number",
        normativa.plantas_maximas != null ? normativa.plantas_maximas : "", "p.ej. 6") +
      "</div></div>" +

      '<div class="form-section" id="estilo-section"><h3>Estilo arquitectónico</h3>' + estiloSelectorHtml() + "</div>" +

      '<div class="generar-actions">' +
      '<button id="g-cancelar" class="btn-ghost">Cancelar</button>' +
      '<button id="g-submit" class="btn-primary">Generar con IA</button>' +
      "</div>" +
      "</div></div>";

    wireGenerarForm();
  }

  // --- Selector de estilo (Pieza 4, 2026-08-15) -----------------------------
  // Mismo patrón de carga perezosa + repintado parcial que la sección de
  // pliego: `state.estilosDisponibles` es `null` hasta la primera visita,
  // `{}` mientras llega la respuesta (evita relanzar la petición en cada
  // repintado), luego el catálogo real de `GET /api/estilos`.

  function estiloSelectorHtml() {
    if (state.estilosDisponibles === null) {
      cargarEstilosDisponibles();
      return '<p class="muted">Cargando estilos…</p>';
    }
    var seleccionado = state.estiloSeleccionado || "racionalista";
    var claves = Object.keys(state.estilosDisponibles).sort();
    var opciones = claves.map(function (clave) {
      var nombre = (state.estilosDisponibles[clave] || {}).nombre_estilo || clave;
      var sel = clave === seleccionado ? " selected" : "";
      return '<option value="' + clave + '"' + sel + ">" + escapeHtml(nombre) + "</option>";
    }).join("");
    var esPersonalizado = seleccionado === "__personalizado__";
    return '<div class="form-grid">' +
      '<div class="form-field"><label for="g-estilo">Estilo arquitectónico</label><select id="g-estilo">' +
      opciones +
      '<option value="__personalizado__"' + (esPersonalizado ? " selected" : "") +
      ">Estilo personalizado (texto libre)</option>" +
      "</select>" +
      '<p class="form-field-ayuda">Influye en la propuesta como preferencia estética — nunca por encima de la normativa.</p>' +
      "</div>" +
      '<div class="form-field-full" id="g-estilo-personalizado-wrap"' + (esPersonalizado ? "" : ' style="display:none"') + ">" +
      '<label for="g-estilo-texto">Describe el estilo</label>' +
      '<input type="text" id="g-estilo-texto" placeholder="p.ej. brutalismo mediterráneo" value="' +
      escapeHtml(state.estiloPersonalizadoTexto || "") + '">' +
      "</div>" +
      "</div>";
  }

  function cargarEstilosDisponibles() {
    state.estilosDisponibles = {};
    fetch("/api/estilos")
      .then(function (resp) { return resp.json(); })
      .then(function (json) {
        state.estilosDisponibles = json.estilos || {};
        repintarSeccionEstilo();
      })
      .catch(function () {
        state.estilosDisponibles = {};
        repintarSeccionEstilo();
      });
  }

  function repintarSeccionEstilo() {
    var seccion = document.getElementById("estilo-section");
    if (!seccion) return;
    seccion.innerHTML = "<h3>Estilo arquitectónico</h3>" + estiloSelectorHtml();
    wireEstiloSection();
  }

  function wireEstiloSection() {
    var select = document.getElementById("g-estilo");
    if (!select) return;
    select.addEventListener("change", function () {
      state.estiloSeleccionado = select.value;
      var wrap = document.getElementById("g-estilo-personalizado-wrap");
      if (wrap) wrap.style.display = select.value === "__personalizado__" ? "" : "none";
    });
    var textoInput = document.getElementById("g-estilo-texto");
    if (textoInput) {
      textoInput.addEventListener("input", function () {
        state.estiloPersonalizadoTexto = textoInput.value;
      });
    }
  }

  // Estilo a mandar en el body de /api/generar o /api/generar-desde-pliego
  // -- centralizado aquí porque los dos botones de generación (el
  // principal y "Generar desde este pliego") lo necesitan igual.
  function estiloParaEnviar() {
    if (state.estiloSeleccionado === "__personalizado__") {
      var texto = document.getElementById("g-estilo-texto");
      return texto ? texto.value.trim() : "";
    }
    return state.estiloSeleccionado || "racionalista";
  }

  // Valor de un parámetro extraído, listo para mostrarse en el input de
  // revisión -- `p.valor` puede ser una lista (mix_tipologias,
  // normativa_aplicable, criterios_sostenibilidad) o un escalar.
  function pliegoValorTexto(p) {
    if (p.no_encontrado || p.valor == null) return "";
    return typeof p.valor === "object" ? JSON.stringify(p.valor) : String(p.valor);
  }

  function pliegoImportarHtml() {
    var estado = state.pliegoEstado;
    var pliego = state.pliegoImportado;
    var errorHtml = estado && estado.error
      ? '<p class="cuadro-conflicto">' + escapeHtml(estado.error) + "</p>" : "";

    if (estado === "cargando") {
      return '<p class="muted">Extrayendo parámetros del pliego (puede tardar unos segundos)…</p>';
    }
    if (!pliego) {
      return errorHtml +
        '<p class="muted">Importa el PDF del pliego de condiciones del concurso para ver aquí sus parámetros.</p>' +
        '<input type="file" id="pliego-input" accept=".pdf" hidden>' +
        '<button type="button" class="btn-reveal" id="btn-importar-pliego">Importar pliego PDF</button>';
    }
    var filas = Object.keys(pliego.parametros).map(function (nombre) {
      var p = pliego.parametros[nombre];
      var badge = p.no_encontrado
        ? '<span class="cuadro-conflicto">No encontrado</span>'
        : escapeHtml(p.confianza || "");
      return "<tr><td>" + escapeHtml(nombre) + "</td>" +
        '<td><input type="text" class="pliego-valor-input" data-campo="' + nombre + '" value="' +
        escapeHtml(pliegoValorTexto(p)) + '"' +
        (p.no_encontrado ? ' placeholder="No encontrado en el pliego"' : "") + "></td>" +
        "<td>" + badge + "</td>" +
        '<td class="muted">' + escapeHtml(p.motivo || p.cita || "") + "</td></tr>";
    }).join("");
    var errorGenerarHtml = state.pliegoGenerarError
      ? '<p class="cuadro-conflicto">' + escapeHtml(state.pliegoGenerarError) + "</p>" : "";
    return errorHtml +
      '<p class="muted">Extraído de «' + escapeHtml(pliego.nombre_archivo) +
      '». Revisa y corrige lo que haga falta — estos valores todavía no se aplican solos al formulario de abajo.</p>' +
      '<div class="cuadro-tabla-wrap"><table class="cuadro-tabla"><thead><tr>' +
      "<th>Parámetro</th><th>Valor</th><th>Confianza</th><th>Motivo / cita</th>" +
      "</tr></thead><tbody>" + filas + "</tbody></table></div>" +
      '<button type="button" class="btn-ghost" id="btn-reimportar-pliego">Importar otro pliego</button> ' +
      '<button type="button" class="btn-primary" id="btn-generar-desde-pliego">Generar proyecto desde este pliego</button>' +
      '<p class="form-field-ayuda">Usa la superficie del solar de la sección «Solar» de abajo — el pliego no la trae.</p>' +
      errorGenerarHtml;
  }

  function repintarSeccionPliego() {
    var seccion = document.getElementById("pliego-section");
    if (!seccion) return;
    seccion.innerHTML = "<h3>Pliego de concurso</h3>" + pliegoImportarHtml();
    wirePliegoSection();
  }

  function wirePliegoSection() {
    var btnImportar = document.getElementById("btn-importar-pliego");
    var btnReimportar = document.getElementById("btn-reimportar-pliego");
    var input = document.getElementById("pliego-input");
    if (input) {
      input.addEventListener("change", function () {
        var file = input.files[0];
        if (!file) return;
        state.pliegoEstado = "cargando";
        repintarSeccionPliego();

        var formData = new FormData();
        formData.append("pliego", file);
        fetch("/api/extraer-pliego", { method: "POST", body: formData })
          .then(function (resp) {
            return resp.json().then(function (json) { return { ok: resp.ok, json: json }; });
          })
          .then(function (result) {
            if (!result.ok) {
              state.pliegoEstado = { error: result.json.error || "No se pudo extraer el pliego." };
              state.pliegoImportado = null;
              repintarSeccionPliego();
              return;
            }
            state.pliegoEstado = null;
            state.pliegoImportado = result.json.pliego;
            repintarSeccionPliego();
          })
          .catch(function () {
            state.pliegoEstado = { error: "Error de red al importar el pliego." };
            repintarSeccionPliego();
          });
      });
    }
    if (btnImportar) btnImportar.addEventListener("click", function () { input.click(); });
    if (btnReimportar) {
      btnReimportar.addEventListener("click", function () {
        state.pliegoImportado = null;
        state.pliegoEstado = null;
        state.pliegoGenerarError = null;
        repintarSeccionPliego();
      });
    }
    // Edición manual de un valor extraído: se guarda solo en memoria local
    // (revisión en pantalla). El conector con `ai_generator.py` SÍ existe
    // ya (`POST /api/generar-desde-pliego`, Pieza 4), pero lee el pliego
    // fresco de la base de datos por `pliego_id` -- esta corrección local
    // sigue sin llegarle. Corregir de verdad exige un endpoint que
    // reescriba `pliegos.parametros` en la base de datos, que no existe
    // todavía; se deja anotado aquí, no escondido.
    document.querySelectorAll(".pliego-valor-input").forEach(function (el) {
      el.addEventListener("change", function () {
        var campo = el.getAttribute("data-campo");
        if (state.pliegoImportado && state.pliegoImportado.parametros[campo]) {
          state.pliegoImportado.parametros[campo].valor = el.value;
          state.pliegoImportado.parametros[campo].no_encontrado = false;
        }
      });
    });

    var btnGenerarDesdePliego = document.getElementById("btn-generar-desde-pliego");
    if (btnGenerarDesdePliego) {
      btnGenerarDesdePliego.addEventListener("click", function () {
        state.pliegoGenerarError = null;
        var superficieInput = document.getElementById("g-superficie");
        var superficie = superficieInput ? parseFloat(superficieInput.value) : 0;
        if (!superficie || superficie <= 0) {
          state.pliegoGenerarError = "Indica la superficie del solar (sección «Solar» de abajo) — el pliego no la trae.";
          repintarSeccionPliego();
          return;
        }
        var pliegoId = state.pliegoImportado.id;
        // Instantánea del resto del formulario, para no perderla si hay que
        // volver a pintarlo tras un error -- mismo criterio que ya usa el
        // botón "Generar con IA" principal (`renderGenerarForm(body)`).
        var prefillSiFalla = {
          proyecto: { ciudad: document.getElementById("g-ciudad").value, tipologia: document.getElementById("g-tipologia").value },
          solar: {
            superficie_m2: superficie, forma: document.getElementById("g-forma").value,
            ancho_m: numVal("g-ancho"), largo_m: numVal("g-largo"), norte_grados: numVal("g-norte")
          },
          edificio: {
            plantas: numVal("g-plantas"), altura_libre_m: numVal("g-altura"),
            planta_baja_comercial: document.getElementById("g-comercial").value === "si"
          },
          mix_viviendas: {
            dorm_1: numVal("g-dorm1"), dorm_2: numVal("g-dorm2"), dorm_3: numVal("g-dorm3"),
            superficie_minima_m2: numVal("g-supmin")
          },
          normativa: {
            ocupacion_maxima_pct: numVal("g-ocupacion"), retranqueos_m: numVal("g-retranqueo"),
            edificabilidad_maxima: optNumVal("g-edificabilidad"), plantas_maximas: optNumVal("g-plantas-maximas")
          }
        };

        renderLoading("Generando tu proyecto desde el pliego", GENERATE_STEPS);
        fetch("/api/generar-desde-pliego", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            pliego_id: pliegoId,
            superficie_solar_m2: superficie,
            estilo: estiloParaEnviar()
          })
        })
          .then(function (resp) {
            return resp.json().then(function (json) { return { ok: resp.ok, json: json }; });
          })
          .then(function (result) {
            if (!result.ok) {
              state.pliegoGenerarError = result.json.error || "No se pudo generar el proyecto desde el pliego.";
              finishLoading(function () { renderGenerarForm(prefillSiFalla); });
              return;
            }
            state.data = result.json;
            state.selectedId = null;
            finishLoading(function () { renderWorkspace(); });
          })
          .catch(function () {
            state.pliegoGenerarError = "Error de red al generar el proyecto desde el pliego.";
            finishLoading(function () { renderGenerarForm(prefillSiFalla); });
          });
      });
    }
  }

  function numVal(id) {
    var v = parseFloat(document.getElementById(id).value);
    return isNaN(v) ? 0 : v;
  }

  function optNumVal(id) {
    var raw = document.getElementById(id).value;
    if (raw === "" || raw === null) return null;
    var v = parseFloat(raw);
    return isNaN(v) ? null : v;
  }

  function showGenerarError(msg) {
    var el = document.getElementById("generar-error");
    if (el) el.innerHTML = '<div class="error-banner">' + escapeHtml(msg || "No se pudo generar el proyecto.") + "</div>";
  }

  function wireGenerarForm() {
    wirePliegoSection();
    wireEstiloSection();

    var formaSelect = document.getElementById("g-forma");
    var dimsWrap = document.getElementById("g-dims-wrap");
    function syncDims() { dimsWrap.style.display = formaSelect.value === "rectangular" ? "" : "none"; }
    formaSelect.addEventListener("change", syncDims);
    syncDims();

    document.getElementById("g-cancelar").addEventListener("click", function () {
      state.pliegoEstado = null;
      state.pliegoImportado = null;
      state.pliegoGenerarError = null;
      if (state.data) { renderWorkspace(); } else { renderUpload(); }
    });

    document.getElementById("g-submit").addEventListener("click", function () {
      var body = {
        proyecto: {
          ciudad: document.getElementById("g-ciudad").value.trim(),
          tipologia: document.getElementById("g-tipologia").value
        },
        solar: {
          superficie_m2: numVal("g-superficie"),
          forma: formaSelect.value,
          ancho_m: numVal("g-ancho"),
          largo_m: numVal("g-largo"),
          norte_grados: numVal("g-norte")
        },
        edificio: {
          plantas: numVal("g-plantas"),
          altura_libre_m: numVal("g-altura"),
          planta_baja_comercial: document.getElementById("g-comercial").value === "si"
        },
        mix_viviendas: {
          dorm_1: numVal("g-dorm1"),
          dorm_2: numVal("g-dorm2"),
          dorm_3: numVal("g-dorm3"),
          superficie_minima_m2: numVal("g-supmin")
        },
        normativa: {
          ocupacion_maxima_pct: numVal("g-ocupacion"),
          retranqueos_m: numVal("g-retranqueo"),
          edificabilidad_maxima: optNumVal("g-edificabilidad"),
          plantas_maximas: optNumVal("g-plantas-maximas")
        },
        estilo: estiloParaEnviar()
      };

      if (body.solar.superficie_m2 <= 0 || (body.mix_viviendas.dorm_1 + body.mix_viviendas.dorm_2 + body.mix_viviendas.dorm_3) <= 0) {
        showGenerarError("Indica la superficie del solar y al menos una vivienda en el mix.");
        return;
      }

      renderLoading("Generando tu proyecto", GENERATE_STEPS);
      fetch("/api/generar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      })
        .then(function (resp) {
          return resp.json().then(function (json) { return { ok: resp.ok, json: json }; });
        })
        .then(function (result) {
          if (!result.ok) {
            finishLoading(function () {
              renderGenerarForm(body);
              showGenerarError(result.json.error || "No se pudo generar el proyecto.");
            });
            return;
          }
          state.data = result.json;
          state.selectedId = null;
          finishLoading(function () { renderWorkspace(); });
        })
        .catch(function () {
          finishLoading(function () {
            renderGenerarForm(body);
            showGenerarError("Error de red al generar el proyecto.");
          });
        });
    });
  }

  // --- Pantalla de carga ---------------------------------------------------

  var LOADING_STEPS = ["Leyendo plano...", "Detectando habitaciones...", "Evaluando calidad...", "Generando análisis IA..."];
  var GENERATE_STEPS = ["Analizando el solar...", "Distribuyendo viviendas por planta...", "Dimensionando habitaciones...", "Redactando la justificación..."];

  function renderLoading(title, steps) {
    updateSidebarContext(null);
    var useSteps = steps || LOADING_STEPS;
    viewRoot.innerHTML =
      '<div class="loading-screen bg-technical">' +
      '<div class="loading-title">' + escapeHtml(title || "Analizando tu plano") + "</div>" +
      '<div class="loading-steps">' +
      useSteps.map(function (label, i) {
        return '<div class="loading-step" data-step="' + i + '"><span class="loading-step-icon"></span><span>' + label + "</span></div>";
      }).join("") +
      "</div>" +
      '<div class="loading-bar"><div class="loading-bar-fill" id="loading-bar-fill"></div></div></div>';

    var steps = Array.prototype.slice.call(document.querySelectorAll(".loading-step"));
    var fillEl = document.getElementById("loading-bar-fill");
    var idx = 0;
    var pct = 6;

    function activate(i) {
      steps.forEach(function (s, si) {
        s.classList.toggle("done", si < i);
        s.classList.toggle("active", si === i);
      });
    }
    activate(0);
    fillEl.style.width = pct + "%";

    loadingStageTimer = setInterval(function () {
      idx = Math.min(idx + 1, steps.length - 1);
      activate(idx);
    }, 1300);

    loadingTimer = setInterval(function () {
      pct += (92 - pct) * 0.1;
      fillEl.style.width = Math.min(pct, 92) + "%";
    }, 200);
  }

  function finishLoading(onDone) {
    clearInterval(loadingTimer);
    clearInterval(loadingStageTimer);
    var steps = document.querySelectorAll(".loading-step");
    steps.forEach(function (s) { s.classList.add("done"); s.classList.remove("active"); });
    var fillEl = document.getElementById("loading-bar-fill");
    if (fillEl) fillEl.style.width = "100%";
    setTimeout(onDone, fillEl ? 320 : 0);
  }

  // --- Header: solo tipología --------------------------------------------
  // El contador de issues por severidad que ocupaba la franja bajo el header
  // se ha eliminado (iteración 3). Era información sin decisión asociada:
  // "5 importantes" no dice cuáles ni dónde, y ocupaba la banda por la que
  // pasa la mirada antes de llegar al plano. Su sustituto es el informe
  // ejecutivo, que sí nombra los tres puntos y los localiza.

  // `semaforoColorVar` (coloreaba la cifra de puntuación por semáforo) se
  // retiró el 2026-08-17 junto con sus tres únicos consumidores —
  // `.report-flag`, `.sidebar-fila.tiene-aviso` y `.proyecto-card-aviso` —
  // al pasar las puntuaciones a texto plano sin badge de color.

  // Las pestañas de planta del header se eliminaron en el rediseño
  // "visual hierarchy first": duplicaban exactamente el selector de
  // vivienda del riel izquierdo (mismos datos, misma acción
  // `selectVivienda`, ambos visibles siempre) y eran N pastillas con borde
  // y puntuación en color justo en la zona donde aterriza la mirada al
  // abrir la pantalla. Se conserva el selector del riel izquierdo, que es
  // el más informativo (puntuación + superficie + barra de categorías).

  // `renderHeaderTipologia`/`renderDashboard` (ciudad/tipología/zona CTE de
  // proyectos generados, badge de puntuación + popover de desglose) se
  // retiran con la Shell junto con los nodos del header que rellenaban —
  // ninguno tiene hoy un sitio nuevo en la interfaz (la puntuación global sí
  // lo tiene, en el informe ejecutivo del Workspace; el resumen de
  // ciudad/tipología/zona CTE y el desglose por categoría, no). Señalado
  // igual que el desglose de puntuación más arriba: se pierde con este paso,
  // no se traslada.

  // --- Workspace (tres paneles) ---------------------------------------------

  function renderWorkspace() {
    var data = state.data;
    updateSidebarContext(data);

    if (!data.viviendas.length) {
      viewRoot.innerHTML =
        '<div class="upload-screen bg-technical"><div class="upload-card">' +
        "<h1>Sin habitaciones detectadas</h1>" +
        '<p class="muted">No se han encontrado habitaciones en el layer de áreas de este DXF.</p>' +
        "</div></div>";
      return;
    }

    // Ya no hay `panel-left`: el riel de viviendas vive en la zona contextual
    // del sidebar (v3 §6), que es el mismo elemento que estaba ahí antes de
    // abrir el proyecto — un solo panel izquierdo en toda la aplicación.
    // El nombre del proyecto y Exportar pasan a un encabezado dentro de la
    // columna del lienzo: son datos del documento abierto, no de la
    // aplicación, y se van con él.
    viewRoot.innerHTML =
      '<div class="workspace">' +
      '<section class="panel-center">' +

      // Barra de título: nombre del documento abierto. Exportar ya no vive
      // aquí — se mudó a la pestaña "Salida" del ribbon, que es donde un
      // usuario de AutoCAD la busca.
      '<div class="proyecto-header">' +
      '<span class="proyecto-header-nombre">' + escapeHtml(data.archivo || "Proyecto") + "</span>" +
      '<span class="cad-titulo-vivienda" id="center-title"></span>' +
      "</div>" +

      // Ribbon: 3 pestañas con contenido real. No son las 7 de AutoCAD
      // porque ArchMuse no dibuja: 5 estarían vacías, que es peor que no
      // tenerlas (mismo criterio que borró Herramientas y Cuenta).
      '<div class="cad-ribbon">' +
      '<div class="cad-ribbon-tabs" id="cad-ribbon-tabs">' +
      RIBBON_TABS.map(function (t, i) {
        return '<button type="button" class="cad-ribbon-tab' + (i === 0 ? " is-activa" : "") +
          '" data-tab="' + t.id + '">' + escapeHtml(t.label) + "</button>";
      }).join("") +
      "</div>" +
      '<div class="cad-ribbon-panel" id="cad-ribbon-panel"></div>' +
      "</div>" +

      '<div class="cad-lienzo" id="cad-lienzo">' +
      '<div id="svg-container" class="svg-container"></div>' +
      '<div class="cad-crosshair" id="cad-crosshair" hidden>' +
      '<div class="cad-crosshair-h"></div><div class="cad-crosshair-v"></div>' +
      "</div>" +
      // Fase 6c: en modo "Cuadro" esto sustituye al plano en el LIENZO
      // PRINCIPAL (no en el inspector lateral, que es donde vivía antes) --
      // petición explícita: "quiero que se vea como el plano, pero en vez
      // del plano el cuadro". `hidden` por defecto: `aplicarModoLienzo`
      // (llamada desde `setModo`) decide cuál de los dos se ve.
      '<div id="cad-cuadro-superficies" class="cad-cuadro-lienzo" hidden></div>' +
      "</div>" +

      // Línea de comandos: caja real con catálogo real (ver COMANDOS).
      '<div class="cad-comando">' +
      '<label for="cad-comando-input">Comando:</label>' +
      '<input type="text" id="cad-comando-input" autocomplete="off" spellcheck="false">' +
      '<span class="cad-comando-eco" id="cad-comando-eco"></span>' +
      "</div>" +

      '<div class="cad-statusbar">' +
      '<div class="cad-tabs" id="cad-tabs">' +
      '<button type="button" class="cad-tab is-activa" data-vista="modelo">Modelo</button>' +
      '<button type="button" class="cad-tab" data-vista="3d">3D</button>' +
      // Pieza 4 (2026-08-15): solo si el proyecto está guardado
      // (`proyecto_id`) -- sin él no hay nada que georreferenciar. Puede
      // estar sin sitio enlazado todavía; en ese caso `visor-mapa.js`
      // muestra un mensaje claro al abrir, no oculta la pestaña (el
      // arquitecto puede querer saber que existe esta función aunque hoy
      // no tenga datos).
      (data.proyecto_id ? '<button type="button" class="cad-tab" data-vista="mapa">Mapa</button>' : "") +
      "</div>" +
      '<span class="cad-coords" id="cad-coords">—</span>' +
      '<span class="cad-status-flags" id="cad-status-flags"></span>' +
      "</div>" +

      "</section>" +
      '<aside class="panel-right"><div id="inspector"></div></aside>' +
      "</div>";

    aplicarInspectorPlegado();
    wireLienzoCAD();
    wireRibbon();
    wireVistaTabs(data);
    wireComando();
    wireVer3d(data);
    wireInspector();
    wireSalidaFoco();
    selectVivienda(data.viviendas[0].id);
  }

  // Exportar dejó de ser un trigger de la barra superior y es un botón del
  // encabezado de proyecto. Sigue abriendo el mismo desplegable de dos
  // opciones que ya existía — mismo mecanismo, distinto anclaje.
  function wireExportar() {
    var btn = document.getElementById("btn-exportar");
    if (!btn) return;
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (shellOpen && shellOpen.trigger === btn) { closeShellMenu(); return; }
      openShellMenu(btn, [
        { label: "Informe PDF", action: "exportar-pdf" },
        { label: "Datos CSV", action: "exportar-csv" }
      ]);
    });
  }

  // --- Zona contextual del sidebar: viviendas --------------------------------

  // El riel dejó de filtrar y de resumir: solo lista viviendas para navegar
  // entre ellas. La superficie y el desglose por categorías, que antes iban
  // impresos en cada fila, siguen disponibles en el tooltip al pasar el
  // ratón (Nivel 3) — el dato no se pierde, deja de estar siempre a la vista.
  //
  // Desde la v3 de la Shell esto ya no pinta en un `panel-left` propio del
  // workspace, sino en `#sidebar-contexto`, que sobrevive a la navegación.
  function renderViviendaList() {
    if (!state.data) return;
    sidebarContexto.innerHTML =
      '<div class="sidebar-seccion">Viviendas</div>' +
      // Tres correcciones sobre la fila anterior, que pintaba `92%` en verde
      // saturado:
      //   1. No es un porcentaje de nada. Es un índice 0-100, y el "%" lo
      //      hacía leer como "92% de algo".
      //   2. Con una puntuación en color por fila, seis viviendas son seis
      //      luces de semáforo encendidas a la vez en el lateral, compitiendo
      //      con el plano. El color deja de marcar el estado normal y pasa a
      //      marcar solo la excepción: barra de 2px en el borde izquierdo de
      //      las viviendas que NO están en verde. Sin marca = correcta, que
      //      es la convención de cualquier herramienta de revisión.
      //   3. La cifra va en tinta terciaria y tabular: es un dato de apoyo,
      //      no el contenido de la fila.
      // Barra de color por semáforo retirada (2026-08-17, "sin colores de
      // semáforo" / puntuaciones en texto plano) — la valoración sigue
      // disponible como texto en el `title` de la cifra, ya no como color.
      state.data.viviendas.map(function (v) {
        return '<button type="button" class="sidebar-fila" data-id="' + v.id + '">' +
          '<span class="sidebar-fila-nombre">' + escapeHtml(v.nombre) + "</span>" +
          '<span class="sidebar-fila-meta" title="' +
          escapeHtml(semaforoTitle(v.valoracion)) + '">' + v.puntuacion + "</span>" +
          "</button>";
      }).join("") +
      // Entrada de PROYECTO de los diagnósticos de capas AM_* sin vivienda
      // (docs/prd/2026-08-13-visualizacion-diagnosticos-capas-am.md §8.2,
      // opción D): vive en el riel, no en el inspector por-vivienda, porque
      // es visible sin depender de qué vivienda esté seleccionada — y
      // porque `_capas_casi_correctas`/`_capas_reservadas_en_uso`/geometría
      // descartada no tienen ninguna vivienda a la que anclarse (§6.2 del
      // PRD). Silencioso si no hay ninguno.
      diagCapasEntradaProyectoHtml() +
      // Entrada de "Hechos del edificio" (CAP-5, altura_evacuacion +
      // avisos_evacuacion), mismo motivo que la anterior: no depende de
      // qué vivienda esté seleccionada.
      hechosEdificioEntradaProyectoHtml();

    Array.prototype.forEach.call(sidebarContexto.querySelectorAll(".sidebar-fila"), function (fila) {
      fila.classList.toggle("is-activa", fila.dataset.id === state.selectedId);
      fila.addEventListener("click", function () { selectVivienda(fila.dataset.id); });
      fila.addEventListener("mouseenter", function () {
        var v = state.data.viviendas.filter(function (x) { return x.id === fila.dataset.id; })[0];
        if (!v) return;
        tooltip.querySelector(".tooltip-title").textContent = v.nombre;
        tooltip.querySelector(".tooltip-area").textContent =
          v.valoracion + " · " + v.puntuacion + "% · " + v.superficie_total_m2.toFixed(2) + " m² · " +
          v.habitaciones.length + " habitaciones";
        var probEl = tooltip.querySelector(".tooltip-problems");
        probEl.innerHTML = (v.problemas_vivienda || []).map(function (p) {
          return "<div><span>" + escapeHtml(p) + "</span></div>";
        }).join("");
        tooltip.hidden = false;
      });
      fila.addEventListener("mousemove", function (e) { positionTooltip(e.clientX, e.clientY); });
      fila.addEventListener("mouseleave", function () { tooltip.hidden = true; });
    });

    var btnDiagProyecto = document.getElementById("btn-diag-capas-am-proyecto");
    if (btnDiagProyecto) {
      btnDiagProyecto.addEventListener("click", function () {
        abrirPanelFlotante("diagnosticos-capas-am", "proyecto");
      });
    }

    var btnHechosEdificio = document.getElementById("btn-hechos-edificio-proyecto");
    if (btnHechosEdificio) {
      btnHechosEdificio.addEventListener("click", function () {
        abrirPanelFlotante("hechos-edificio", "proyecto");
      });
    }
  }

  function diagCapasEntradaProyectoHtml() {
    var diagnosticos = diagnosticosCapasAmSinVivienda();
    if (!diagnosticos.length) return "";
    return '<button type="button" class="btn-reveal diag-capas-entrada-proyecto" ' +
      'id="btn-diag-capas-am-proyecto">' +
      diagCapasConteoHtml(diagnosticos) +
      " Diagnósticos de capas AM_* (plano)</button>";
  }

  function csvField(value) {
    var str = String(value);
    if (/["\n,]/.test(str)) return '"' + str.replace(/"/g, '""') + '"';
    return str;
  }

  // Cuenta issues por severidad (Bloque 12, `data.issues`) en vez de
  // `problemas_vivienda` (lista de mensajes sin severidad) — es la única
  // fuente del JSON que trae CRITICO/IMPORTANTE/RECOMENDACION por vivienda.
  function exportarCSV() {
    var issues = state.data.issues || [];
    var rows = state.data.viviendas.map(function (v) {
      var criticos = 0, importantes = 0, recomendaciones = 0;
      issues.forEach(function (issue) {
        if (issue.unit_name !== v.nombre) return;
        if (issue.severity === "CRITICO") criticos++;
        else if (issue.severity === "IMPORTANTE") importantes++;
        else if (issue.severity === "RECOMENDACION") recomendaciones++;
      });
      return [
        v.id, v.nombre, v.valoracion, v.puntuacion == null ? "" : v.puntuacion,
        criticos, importantes, recomendaciones
      ].map(csvField).join(",");
    });

    var csv = "id,nombre,valoracion,puntuacion,criticos,importantes,recomendaciones\n" + rows.join("\n");

    var blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "archmuse_export.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // --- Botón "Ver en 3D" ------------------------------------------------
  // Dos visores distintos según el tipo de proyecto:
  // - Con `data.edificio` (proyecto generado con IA, con plantas/altura
  //   libre conocidas): el visor de EDIFICIO COMPLETO existente
  //   (`window.ArchmuseViewer3D`), sin cambios.
  // - Sin `data.edificio` (DXF analizado — antes el botón se ocultaba aquí,
  //   porque ese visor no sabe construir un edificio sin esos datos): el
  //   visor nuevo, más simple, que extruye las habitaciones de la VIVIENDA
  //   ACTUALMENTE SELECCIONADA a partir de su `poligono` real
  //   (`window.ArchmuseRoomViewer3D`, ver el `<script type="module">` al
  //   final del documento) — ya no hace falta ocultar el botón en este caso.

  // Pestañas Modelo / 3D. AutoCAD tiene aquí Modelo/Presentación, pero
  // ArchMuse no traza láminas ni tiene layouts: reproducirlas seria decorado.
  // Modelo y 3D sí son dos representaciones reales del mismo proyecto, y de
  // paso el visor 3D deja de ser un botón descolgado al final de los modos.
  function wireVistaTabs(data) {
    var tabs = document.getElementById("cad-tabs");
    if (!tabs) return;
    tabs.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-vista]");
      if (!btn) return;
      if (btn.dataset.vista === "3d") {
        abrirVisor3d(data);
        return; // el visor es un overlay: se cierra y vuelves a Modelo
      }
      if (btn.dataset.vista === "mapa") {
        // `window.ArchmuseVisorMapa` lo expone `visor-mapa.js` (`<script
        // type="module">`, sin acceso directo desde este script clásico) --
        // mismo puente que `window.ArchmuseViewer3D` para el 3D.
        if (window.ArchmuseVisorMapa) window.ArchmuseVisorMapa.open(data);
        return; // overlay, mismo criterio que el 3D
      }
      state.vistaActiva = "modelo";
    });
  }

  function wireVer3d(data) {
    // El disparo del 3D vive ahora en la pestaña `3D` de la barra de estado
    // (`wireVistaTabs`); esta función solo conserva la lógica de decidir
    // cuál de los dos visores abrir, que no cambia.
    void data;
  }

  function abrirVisor3d(data) {
    (function () {
      if (data.edificio) {
        if (window.ArchmuseViewer3D) {
          window.ArchmuseViewer3D.open(data);
        } else {
          var overlay = document.getElementById("viewer-3d");
          var loading = document.getElementById("viewer-3d-loading");
          var title = document.getElementById("viewer-3d-title-text");
          title.textContent = "Edificio completo";
          loading.hidden = false;
          loading.textContent = "No se pudo cargar el visor 3D (revisa tu conexión a internet).";
          overlay.classList.add("open");
        }
        return;
      }

      var v = state.data.viviendas.filter(function (x) { return x.id === state.selectedId; })[0];
      if (!v) return;
      if (window.ArchmuseRoomViewer3D) {
        // Habitaciones con algún problema CRITICO/IMPORTANTE (Requisito 5,
        // toggle "Ver problemas") — se reutiliza `buildUnifiedProblems`, ya
        // usado por el panel "Problemas detectados", en vez de recalcular
        // severidades aquí.
        var criticas = buildUnifiedProblems(v)
          .filter(function (it) { return (it.severity === "CRITICO" || it.severity === "IMPORTANTE") && it.room_label; })
          .map(function (it) { return it.room_label; });
        window.ArchmuseRoomViewer3D.open(v, state.data.norte_grados || 0, criticas);
      } else {
        var overlay2 = document.getElementById("room-viewer-3d");
        var loading2 = document.getElementById("room-viewer-loading");
        loading2.hidden = false;
        loading2.textContent = "No se pudo cargar el visor 3D (revisa tu conexión a internet).";
        overlay2.classList.add("open");
      }
    })();
  }

  // --- Botón toggle "Ver luz natural" ------------------------------------
  // Colorea cada habitación del plano con un overlay semitransparente según
  // su valoración de orientación (Bloque 4, `orientacion_valoracion`) — se
  // añaden `<polygon>` extra por encima de los ya dibujados por el backend
  // (mismos puntos, sin trazo) en vez de sobrescribir su `fill`, así el
  // color original por tipo de habitación queda intacto debajo y basta con
  // quitar el overlay para "desactivarlo".

  // =======================================================================
  // Modos de análisis
  // =======================================================================
  // "Resumen" abre la lista porque es el estado inicial y el destino al que
  // se vuelve. "IA" pasó a llamarse "Diagnóstico": el usuario no elige una
  // tecnología, elige una lectura del proyecto.
  //
  // Los contadores que cada herramienta llevaba al lado del nombre se han
  // quitado: eran seis cifras permanentes en la banda inferior compitiendo
  // con el informe, y la única que importaba de verdad (cuántos problemas
  // hay) ya la responde el propio informe ejecutivo.
  var PLAN_MODES = [
    { id: "resumen", label: "Resumen" },
    { id: "espacio", label: "Espacio" },
    { id: "luz", label: "Luz" },
    { id: "normativa", label: "Normativa" },
    // "Hechos": CAP-1..5 (usos/planta/ocupacion/sectorizacion), distinto de
    // "Normativa" (regla LOE hardcodeada, v.normativa_aplicada) -- ver
    // toolHechosHtml. PRD "Tabla de hechos CAP-1..5" (2026-08-14).
    { id: "hechos", label: "Hechos" },
    // Fase 6 (2026-08-14): la tabla del cuadro de superficies visible en
    // pantalla, sin tener que descargar nada -- ver toolCuadroSuperficiesHtml.
    { id: "cuadro", label: "Cuadro" },
    { id: "problemas", label: "Problemas" },
    { id: "ia", label: "Diagnóstico" },
    // Verificador de cumplimiento de pliego (2026-08-15): a nivel de
    // proyecto completo, no por vivienda -- `modoConcursoHtml` ignora `v`
    // salvo para mantener la firma común de `inspectorModoHtml`.
    { id: "concurso", label: "Concurso" }
  ];

  // =======================================================================
  // Ribbon
  // =======================================================================
  // Dos pestañas, no las siete de AutoCAD. AutoCAD tiene siete porque tiene
  // cientos de comandos de dibujo; ArchMuse lee y no dibuja, así que cinco
  // estarían vacías — y una pestaña vacía es exactamente lo que se borró al
  // eliminar Herramientas y Cuenta. Cada grupo de aquí abajo ejecuta una
  // acción que ya existía en el producto.
  // Pestaña "Salida" retirada a petición de Pablo (2026-08-14): "Exportar"
  // pasa a ser un grupo más dentro de "Vista", que se queda como única
  // pestaña -- ver `ribbonPanelHtml`.
  var RIBBON_TABS = [
    { id: "vista", label: "Vista" }
  ];

  // Capas de análisis: son capas de ARCHMUSE, no del DXF (el parser solo lee
  // la capa "00 areas", así que un panel de capas del DXF real no tendría
  // nada que mostrar). Cada una apaga elementos que existen de verdad en el
  // SVG, por eso el backend les puso clase: `plan-label`, `plan-north`.
  var CAPAS = [
    { id: "rellenos", label: "Rellenos", on: true },
    { id: "etiquetas", label: "Etiquetas", on: true },
    { id: "norte", label: "Norte", on: true }
  ];

  function ribbonPanelHtml(tabId) {
    // "Informe PDF", "Datos CSV" y "Descargar DXF rellenado" (borrador con
    // N/D) se quitaron del grupo Exportar a petición de Pablo -- las
    // funciones y sus acciones en `ACCIONES_CAD` siguen intactas (no se ha
    // tocado ningún endpoint ni se ha decidido retirar la capacidad, solo
    // dejaron de mostrarse aquí), por si se vuelven a exponer más adelante.
    // "Completar cuadro" tampoco hace falta ya como botón de ribbon: el
    // modo "Cuadro" (Fase 6d) muestra el formulario EN LA PROPIA TABLA en
    // cuanto hace falta, sin un botón aparte que haya que encontrar antes.
    return grupoRibbon("Modos", PLAN_MODES.map(function (m) {
      return botonRibbon(m.label, 'data-modo="' + m.id + '"',
        state.modo === m.id);
    }).join("")) +
      grupoRibbon("Encuadre",
        botonRibbon("Encuadrar", 'data-accion="zoom-extents"') +
        botonRibbon("Acercar", 'data-accion="zoom-mas"') +
        botonRibbon("Alejar", 'data-accion="zoom-menos"')) +
      // Afordancia visible del plegado. `Ctrl+2` sin botón no lo descubre
      // nadie: un atajo es un acelerador para quien ya sabe que existe,
      // nunca la única puerta a una función.
      // "Inspector" y no "Diagnóstico": ya hay un MODO llamado Diagnóstico
      // en esta misma pestaña, y dos botones con el mismo nombre y
      // significados distintos a diez centímetros uno de otro es una
      // trampa. Es además el nombre que usa la especificación (§7.2).
      grupoRibbon("Paneles",
        botonRibbon("Inspector", 'data-accion="alternar-inspector" title="Plegar o desplegar el inspector (Ctrl+2)"',
          !state.inspectorPlegado)) +
      // "Checklist de visita" (2026-08-16, docs/prd/2026-08-16-checklist-inspeccion-campo.md): solo
      // con `proyecto_id` -- mismo criterio exacto que la pestaña "Mapa" (`app.js:1302`), que depende
      // del mismo requisito (necesita un proyecto GUARDADO para poder pedir su checklist/su sitio).
      ((state.data && state.data.proyecto_id)
        ? grupoRibbon("Campo", botonRibbon("Checklist de visita", 'data-accion="abrir-checklist-campo" id="btn-checklist-campo"'))
        : "") +
      // "Viabilidad Económica y Exportación" (2026-08-17, docs/prd/2026-08-17-viabilidad-economica-y-
      // exportacion-dxf.md): a diferencia del Checklist de visita, no exige `proyecto_id` -- funciona
      // igual con un proyecto recién analizado/generado que todavía no se ha guardado, porque todo lo
      // que necesita (superficie construida, habitaciones de la vivienda activa) ya está en memoria.
      ((state.data)
        ? grupoRibbon("Viabilidad", botonRibbon("Viabilidad y exportación", 'data-accion="abrir-viabilidad-economica" id="btn-viabilidad-economica"'))
        : "") +
      // Checklist de Cumplimiento CTE (2026-08-17, docs/prd/2026-08-17-checklist-cumplimiento-cte.md):
      // mismo criterio que Viabilidad -- no exige `proyecto_id`, solo que haya al menos una vivienda
      // con `checklist_cte` ya calculado por el backend (`api_serializer.py`).
      ((state.data && (state.data.viviendas || []).length)
        ? grupoRibbon("CTE", botonRibbon("Checklist CTE", 'data-accion="abrir-checklist-cte" id="btn-checklist-cte"'))
        : "") +
      // Acta de procedencia legible (`DOC-1`, docs/AGENTE_BACKLOG.md §10,
      // 2026-08-19): sólo si el `File` original sigue en memoria
      // (`state.archivoAnalizado`) -- mismo motivo que "Descargar DXF
      // rellenado", ver el comentario de `botonDescargaDxfRellenoHtml`. No
      // depende de `cuadro_superficies_detectado`: la Skill de medición mide
      // lo que hay dibujado, no necesita ningún cuadro reconocible en el DXF.
      (state.archivoAnalizado
        ? grupoRibbon("Acta", botonRibbon("Acta de procedencia legible", 'data-accion="abrir-acta-legible" id="btn-acta-legible"'))
        : "") +
      // Conversación con ArchMuse (sesión 2026-08-19, noche 4): misma
      // condición que "Acta de procedencia legible" -- necesita un DXF en
      // memoria porque `/api/preguntar` lo exige hoy (la única capacidad
      // registrada, medición de superficies, no funciona sin plano). Grupo
      // aparte y no fundido con "Acta": una es "ver el documento", esta es
      // "preguntar en tus palabras".
      (state.archivoAnalizado
        ? grupoRibbon("Conversación", botonRibbon("Preguntar a ArchMuse", 'data-accion="abrir-conversacion" id="btn-conversacion"'))
        : "");
  }

  // Fase 4: solo aparece si el backend detectó un cuadro de superficies
  // reconocible en ESTE análisis (`proyecto.cuadro_superficies_detectado`,
  // calculado en `/api/analizar` con `cuadro_superficies.detectar_cuadro_
  // superficies` -- nunca se recalcula en el cliente) Y si el `File`
  // original sigue en memoria (`state.archivoAnalizado`): un proyecto
  // reabierto de la lista de guardados no lo trae, así que ahí no se
  // ofrece -- no hay DXF que reenviar.
  function botonDescargaDxfRellenoHtml() {
    var proyecto = (state.data && state.data.proyecto) || {};
    if (!proyecto.cuadro_superficies_detectado || !state.archivoAnalizado) return "";
    return botonRibbon("Descargar DXF rellenado", 'data-accion="exportar-dxf-relleno" id="btn-exportar-dxf-relleno"');
  }

  function grupoRibbon(titulo, contenido) {
    return '<div class="cad-ribbon-grupo"><div class="cad-ribbon-botones">' + contenido +
      '</div><div class="cad-ribbon-grupo-titulo">' + escapeHtml(titulo) + "</div></div>";
  }

  function botonRibbon(label, attrs, activo) {
    return '<button type="button" class="cad-ribbon-btn' + (activo ? " is-activa" : "") + '" ' +
      attrs + ">" + escapeHtml(label) + "</button>";
  }

  function renderRibbonPanel() {
    var panel = document.getElementById("cad-ribbon-panel");
    if (panel) panel.innerHTML = ribbonPanelHtml(state.ribbonTab);
  }

  function wireRibbon() {
    var tabs = document.getElementById("cad-ribbon-tabs");
    var panel = document.getElementById("cad-ribbon-panel");
    if (!tabs || !panel) return;

    tabs.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-tab]");
      if (!btn) return;
      state.ribbonTab = btn.dataset.tab;
      Array.prototype.forEach.call(tabs.querySelectorAll("[data-tab]"), function (b) {
        b.classList.toggle("is-activa", b.dataset.tab === state.ribbonTab);
      });
      renderRibbonPanel();
    });

    panel.addEventListener("click", function (e) {
      var btn = e.target.closest("button");
      if (!btn) return;
      if (btn.dataset.modo) { setModo(btn.dataset.modo); return; }
      var accion = ACCIONES_CAD[btn.dataset.accion];
      if (accion) accion();
    });

    renderRibbonPanel();
  }

  // --- Plegado del panel derecho (especificación §7.4) ------------------------
  // Especificado desde la v2 y nunca implementado: hasta ahora no había forma
  // de recuperar sus 320px. Con el workspace CAD el lienzo se quedaba en el
  // 45% de la ventana (61% del ancho x 74% del alto), y la regla del producto
  // es que el plano manda.
  var INSPECTOR_KEY = "archmuse:inspector-plegado";

  function aplicarInspectorPlegado() {
    var ws = document.querySelector(".workspace");
    if (ws) ws.classList.toggle("sin-inspector", !!state.inspectorPlegado);
  }

  function alternarInspector() {
    state.inspectorPlegado = !state.inspectorPlegado;
    try { localStorage.setItem(INSPECTOR_KEY, state.inspectorPlegado ? "1" : "0"); } catch (e) { /* modo privado */ }
    aplicarInspectorPlegado();
    renderRibbonPanel();
  }

  function restaurarInspectorPlegado() {
    try { state.inspectorPlegado = localStorage.getItem(INSPECTOR_KEY) === "1"; } catch (e) { /* modo privado */ }
  }

  var ACCIONES_CAD = {
    "alternar-inspector": function () { alternarInspector(); },
    "zoom-extents": function () { zoomExtents(); },
    "zoom-mas": function () { zoomPorFactor(1.25); },
    "zoom-menos": function () { zoomPorFactor(1 / 1.25); },
    "exportar-pdf": function () { descargarPdf(); },
    "exportar-csv": function () { exportarCSV(); },
    "exportar-dxf-relleno": function () { descargarDxfRelleno(); },
    "aplicar-respuestas-cuadro": function () { aplicarRespuestasCuadroInline(); },
    "descargar-cuadro-completo": function () { descargarCuadroCompletoDesdeTabla(); },
    "abrir-checklist-campo": function () { abrirChecklistCampo(); },
    "abrir-viabilidad-economica": function () { abrirViabilidadEconomica(); },
    "abrir-checklist-cte": function () { abrirChecklistCte(); },
    "abrir-acta-legible": function () { abrirActaLegible(); },
    "abrir-conversacion": function () { abrirConversacion(); }
  };

  // --- Capas -----------------------------------------------------------------
  // Jerarquía modo ↔ capas (el riesgo nº1 del PRD): el MODO manda y fija el
  // preset; el panel permite desviarse de él. Cambiar de modo restablece el
  // preset, así que nunca se queda un estado contradictorio pegado de un modo
  // anterior sin que el usuario lo haya pedido explícitamente.
  function presetCapasDeModo(modo) {
    return {
      rellenos: modo !== "resumen" && modo !== "normativa",
      etiquetas: modo !== "ia",
      norte: true
    };
  }

  function alternarCapa(id) {
    state.capas[id] = !state.capas[id];
    aplicarCapas();
    renderRibbonPanel();
    renderStatusFlags();
  }

  function aplicarCapas() {
    var cont = document.getElementById("svg-container");
    if (!cont) return;
    var svg = cont.querySelector("svg");
    if (!svg) return;
    svg.classList.toggle("sin-etiquetas", !state.capas.etiquetas);
    svg.classList.toggle("sin-norte", !state.capas.norte);
    svg.classList.toggle("sin-rellenos", !state.capas.rellenos);
  }

  // Siempre hay un modo activo, así que esto nunca recibe null: volver a
  // pulsar el modo activo no lo apaga, solo suelta el foco (que es lo que
  // el usuario quiere decir cuando repite el clic).
  function setModo(modo) {
    state.modo = modo;
    // Cambiar de modo descarta el foco: lo que el inspector mostraba
    // pertenecía al contexto anterior.
    state.seleccion = null;
    cerrarPanelFlotante();

    // El modo fija el preset de capas (ver `presetCapasDeModo`). Desviarse
    // es cosa de la línea de comandos (CAPA), y esa desviación no sobrevive
    // a un cambio de modo: si lo hiciera, el usuario acabaría en estados
    // como "modo Espacio con los rellenos apagados" sin saber por qué.
    state.capas = presetCapasDeModo(modo);

    Array.prototype.forEach.call(document.querySelectorAll(".cad-ribbon-btn[data-modo]"), function (b) {
      b.classList.toggle("is-activa", b.dataset.modo === modo);
    });

    pintarPlano();
    aplicarCapas();
    renderRibbonPanel();
    renderStatusFlags();
    renderInspector();
    aplicarModoLienzo();
  }

  // Fase 6c: qué ocupa el LIENZO PRINCIPAL (donde siempre vivió el plano) --
  // en todos los modos salvo "cuadro" es el plano de siempre; en "cuadro" es
  // la tabla completa, a tamaño real, en el mismo sitio donde estaría el
  // plano -- no un panel lateral aparte. `#cad-cuadro-superficies` empieza
  // `hidden` en la plantilla; esta función es la única que la muestra u
  // oculta, siempre junto con `#svg-container`, nunca los dos a la vez.
  function aplicarModoLienzo() {
    var svgHost = document.getElementById("svg-container");
    var cuadroHost = document.getElementById("cad-cuadro-superficies");
    var crosshair = document.getElementById("cad-crosshair");
    if (!svgHost || !cuadroHost) return;
    var esCuadro = state.modo === "cuadro";
    svgHost.hidden = esCuadro;
    if (esCuadro && crosshair) crosshair.hidden = true;
    cuadroHost.hidden = !esCuadro;
    if (esCuadro) renderCuadroLienzo();
  }

  function viviendaActual() {
    return (state.data.viviendas || []).filter(function (x) { return x.id === state.selectedId; })[0];
  }

  // =======================================================================
  // El plano
  // =======================================================================
  // Toda la apariencia del plano se decide aquí, sobre el SVG que ya mandó
  // el backend. Deliberadamente no se toca `analyzer/plan_svg.py`: ese mismo
  // SVG lo consumen el informe HTML del CLI y el PDF, y un cambio de estética
  // de la SPA no debe propagarse ahí.

  // Contorno real de todo lo dibujado, calculado a partir de los atributos
  // (`points` de los polígonos, `cx/cy/r` de la rosa de los vientos) en vez
  // de con `getBBox()`. Es más largo pero no depende de que el navegador haya
  // hecho layout: funciona igual antes del primer pintado y en un DOM
  // headless, que es lo que permite verificar el reencuadre en el test.
  function contenidoBBox(svg) {
    var minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;

    Array.prototype.forEach.call(svg.querySelectorAll("polygon"), function (poly) {
      (poly.getAttribute("points") || "").trim().split(/\s+/).forEach(function (par) {
        var xy = par.split(",");
        var x = parseFloat(xy[0]), y = parseFloat(xy[1]);
        if (isNaN(x) || isNaN(y)) return;
        if (x < minx) minx = x; if (x > maxx) maxx = x;
        if (y < miny) miny = y; if (y > maxy) maxy = y;
      });
    });

    Array.prototype.forEach.call(svg.querySelectorAll("circle"), function (c) {
      var cx = parseFloat(c.getAttribute("cx")), cy = parseFloat(c.getAttribute("cy"));
      var r = parseFloat(c.getAttribute("r"));
      if (isNaN(cx) || isNaN(cy) || isNaN(r)) return;
      // La "N" de la rosa se dibuja por encima del círculo: 14px extra
      // arriba para que el reencuadre no la corte.
      if (cx - r < minx) minx = cx - r; if (cx + r > maxx) maxx = cx + r;
      if (cy - r - 14 < miny) miny = cy - r - 14; if (cy + r > maxy) maxy = cy + r;
    });

    if (minx === Infinity || maxx <= minx || maxy <= miny) return null;
    return { x: minx, y: miny, w: maxx - minx, h: maxy - miny };
  }

  // Reencuadre: el backend escala cada vivienda a un viewBox fijo de 800x600
  // con 40px de margen, y el <svg> se estira al contenedor. Una vivienda
  // alargada quedaba así encajada en un 4:3 dentro de un panel 16:9, con
  // bandas vacías por los cuatro lados — esa era la causa real de la
  // sensación de lienzo vacío, no el padding del contenedor.
  function ajustarViewBox(svg) {
    var b = contenidoBBox(svg);
    if (!b) return;
    var m = Math.max(b.w, b.h) * 0.04;
    var vb = [(b.x - m), (b.y - m), (b.w + m * 2), (b.h + m * 2)]
      .map(function (n) { return n.toFixed(2); }).join(" ");
    svg.setAttribute("viewBox", vb);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    // Encuadre de referencia: al soltar el foco se vuelve exactamente aquí.
    svg.setAttribute("data-base-viewbox", vb);
  }

  // Rectángulo de una habitación en coordenadas del plano, por el mismo
  // camino que `contenidoBBox` y por el mismo motivo.
  function bboxHabitacion(g) {
    var minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
    Array.prototype.forEach.call(g.querySelectorAll("polygon"), function (poly) {
      (poly.getAttribute("points") || "").trim().split(/\s+/).forEach(function (par) {
        var xy = par.split(",");
        var x = parseFloat(xy[0]), y = parseFloat(xy[1]);
        if (isNaN(x) || isNaN(y)) return;
        if (x < minx) minx = x; if (x > maxx) maxx = x;
        if (y < miny) miny = y; if (y > maxy) maxy = y;
      });
    });
    if (minx === Infinity) return null;
    return { x: minx, y: miny, w: maxx - minx, h: maxy - miny };
  }

  // Severidad máxima por nombre de habitación, desde la lista unificada ya
  // calculada para la vivienda activa.
  function severidadPorHabitacion() {
    var rank = { CRITICO: 3, IMPORTANTE: 2, RECOMENDACION: 1 };
    var out = {};
    state.problemas.forEach(function (p) {
      if (!p.room_label) return;
      var actual = out[p.room_label];
      if (!actual || rank[p.severity] > rank[actual]) out[p.room_label] = p.severity;
    });
    return out;
  }

  // Habitaciones con algún problema de disciplina normativa, para el modo
  // "Normativa". Se deriva de `disciplinaFor`, que ya clasifica cada
  // problema por su código — no se añade ninguna regla nueva.
  function habitacionesConIncumplimiento() {
    var out = {};
    state.problemas.forEach(function (p) {
      if (p.room_label && p.disciplina === "Normativa CTE") out[p.room_label] = true;
    });
    return out;
  }

  // Regla dura de esta iteración: NINGÚN modo deja el plano igual. Si un
  // modo solo cambiara la columna derecha, sería una pestaña disfrazada de
  // vista. Aquí se decide relleno, trazo y opacidad de cada habitación.
  function pintarPlano() {
    var container = document.getElementById("svg-container");
    var v = viviendaActual();
    if (!container || !v) return;
    var svg = container.querySelector("svg");
    if (!svg) return;

    var modo = state.modo;
    var severidad = modo === "problemas" ? severidadPorHabitacion() : null;
    var incumple = modo === "normativa" ? habitacionesConIncumplimiento() : null;

    // "Diagnóstico" atenúa el plano entero: en ese modo el protagonista es
    // el texto, y el plano se queda de telón de fondo.
    svg.style.opacity = modo === "ia" ? "0.5" : "";

    Array.prototype.forEach.call(container.querySelectorAll(".plan-room"), function (g) {
      var idx = parseInt(g.getAttribute("data-room"), 10);
      var room = v.habitaciones[idx];
      var fill = "var(--plan-room)";
      var stroke = "var(--plan-wall)";
      // Píxeles de pantalla, no unidades de viewBox: los polígonos llevan
      // `vector-effect: non-scaling-stroke` (ver style.css), así que este
      // número ya no lo multiplica el zoom. 1 px para la partición, contra
      // los 2,2 px de la envolvente: la jerarquía es de grosor, no de color.
      var width = "1";

      if (modo === "espacio") {
        // Cadena vacía = se cae al atributo `fill` que trae el SVG del
        // backend, que es el color por tipo de uso. La lectura por uso no
        // se perdió al volver neutro el plano: vive aquí.
        fill = "";
      } else if (severidad && room && severidad[room.nombre]) {
        var critico = severidad[room.nombre] === "CRITICO";
        fill = critico ? "var(--plan-problem)" : "var(--plan-warning)";
        stroke = critico ? "var(--color-critical)" : "var(--color-important)";
        width = "1.6";
      } else if (incumple && room && incumple[room.nombre]) {
        fill = "var(--plan-warning)";
        stroke = "var(--color-important)";
        width = "1.6";
      }

      Array.prototype.forEach.call(g.querySelectorAll("polygon"), function (poly) {
        if (poly.classList.contains("luz-overlay-poly")) return;
        poly.style.fill = fill;
        poly.style.stroke = stroke;
        poly.style.strokeWidth = width;
      });
    });

    renderLuzNaturalOverlay(container, v, modo === "luz");
    pintarPins(container, v);
  }

  function renderLuzNaturalOverlay(svgContainer, vivienda, activo) {
    Array.prototype.forEach.call(svgContainer.querySelectorAll(".plan-room"), function (g) {
      Array.prototype.forEach.call(g.querySelectorAll(".luz-overlay-poly"), function (old) {
        old.remove();
      });
      if (!activo) return;

      var idx = parseInt(g.getAttribute("data-room"), 10);
      var room = vivienda.habitaciones[idx];
      var color = room && LUZ_OVERLAY_COLOR[room.orientacion_valoracion];
      if (!color) return;

      Array.prototype.forEach.call(g.querySelectorAll("polygon"), function (poly) {
        var overlay = poly.cloneNode(false);
        overlay.setAttribute("fill", color);
        overlay.removeAttribute("stroke");
        overlay.style.fill = color;
        overlay.style.stroke = "none";
        overlay.classList.add("luz-overlay-poly");
        overlay.style.pointerEvents = "none";
        g.appendChild(overlay);
      });
    });
  }

  // Los puntos 1-2-3 del informe ejecutivo, dibujados sobre el plano. Solo
  // en el modo Resumen: son la traducción visual del informe, no una capa
  // permanente. Un punto sin habitación resoluble sencillamente no se
  // dibuja — su línea del informe se queda sin marca, que es honesto.
  function pintarPins(container, vivienda) {
    var svg = container.querySelector("svg");
    if (!svg) return;
    Array.prototype.forEach.call(svg.querySelectorAll(".plan-pin"), function (p) { p.remove(); });
    if (state.modo !== "resumen") return;

    var escala = escalaPin(svg);
    state.top3.forEach(function (idxProblema, orden) {
      var it = state.problemas[idxProblema];
      if (!it) return;
      var roomIdx = indiceHabitacion(vivienda, it.room_label);
      if (roomIdx === -1) return;
      var g = svg.querySelector('.plan-room[data-room="' + roomIdx + '"]');
      if (!g) return;
      var b = bboxHabitacion(g);
      if (!b) return;

      var pin = document.createElementNS("http://www.w3.org/2000/svg", "g");
      pin.setAttribute("class", "plan-pin");
      pin.setAttribute("data-pin", String(idxProblema));
      var cx = b.x + b.w / 2, cy = b.y + b.h / 2;
      pin.innerHTML =
        '<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="' + (9 * escala).toFixed(1) + '"/>' +
        '<text x="' + cx.toFixed(1) + '" y="' + cy.toFixed(1) + '" text-anchor="middle" ' +
        'dominant-baseline="central" style="font-size:' + (11 * escala).toFixed(1) + 'px">' + (orden + 1) + "</text>";
      svg.appendChild(pin);
    });
  }

  // El reencuadre cambia la escala del viewBox, así que un radio fijo en
  // coordenadas de plano se vería enorme en una vivienda pequeña y diminuto
  // en una grande. Se normaliza contra el viewBox de referencia (800 de
  // ancho) para que el punto salga siempre del mismo tamaño en pantalla.
  function escalaPin(svg) {
    var vb = (svg.getAttribute("viewBox") || "").split(/\s+/).map(Number);
    var ancho = vb.length === 4 && vb[2] > 0 ? vb[2] : 800;
    return Math.max(0.35, Math.min(2.5, ancho / 800));
  }

  // --- Badge de calidad lumínica de la vivienda --------------------------
  // Media del "factor de luz natural" (Bloque 15) de sus habitaciones
  // habitables, ponderada por superficie. Las habitaciones sin ese dato
  // (baños, aseos, tendederos, pasillos, terrazas — `factor_luz_natural_pct`
  // es null para todas ellas, ver `api_serializer._serialize_room`) quedan
  // excluidas del cálculo sin necesidad de listarlas por tipo aquí.

  function calcularCalidadLuminica(habitaciones) {
    var sumaPonderada = 0;
    var areaTotal = 0;
    habitaciones.forEach(function (r) {
      if (r.factor_luz_natural_pct == null) return;
      var area = r.area_m2 || 0;
      var puntuacion = Math.max(0, Math.min(100, (r.factor_luz_natural_pct / LUZ_BADGE_CEIL_PCT) * 100));
      sumaPonderada += puntuacion * area;
      areaTotal += area;
    });
    if (areaTotal === 0) return null;
    return Math.round(sumaPonderada / areaTotal);
  }

  function selectVivienda(id) {
    state.selectedId = id;
    var v = state.data.viviendas.filter(function (x) { return x.id === id; })[0];
    if (!v) return;

    // El riel vive ahora en el sidebar (`#sidebar-contexto`) y sobrevive a la
    // navegación, así que se repinta entero: es barato (6 filas) y evita
    // tener que sincronizar a mano una lista que puede no estar montada
    // todavía la primera vez que se selecciona una vivienda.
    renderViviendaList();

    // Abrir una vivienda entra SIEMPRE en Resumen, sin foco. El modo no se
    // hereda de la vivienda anterior: el informe ejecutivo es la puerta.
    state.modo = "resumen";
    state.seleccion = null;
    cerrarPanelFlotante();
    // Bug encontrado y corregido: este selector apuntaba a `.plan-mode`, la
    // barra de modos de antes del rediseño del ribbon (ver comentario junto
    // a `.cad-ribbon-btn` en style.css: "`.plan-modebar` desaparece"). Ya no
    // existe ningún elemento con esa clase, así que este `forEach` nunca
    // tocaba nada: `state.modo` SÍ volvía a "resumen" y el contenido SÍ se
    // repintaba (correcto), pero el botón de modo que estuviera activo
    // antes de cambiar de vivienda se quedaba visualmente resaltado -- p.
    // ej. "Hechos" seguía marcado aunque el panel ya mostrara Resumen.
    // Mismo selector y clase que usa `setModo` (arriba) para el mismo fin.
    Array.prototype.forEach.call(document.querySelectorAll(".cad-ribbon-btn[data-modo]"), function (b) {
      b.classList.toggle("is-activa", b.dataset.modo === "resumen");
    });

    // Los problemas y el top 3 se calculan ANTES de repintar: el plano los
    // necesita ya montados para dibujar sus puntos numerados.
    state.problemas = buildUnifiedProblems(v);
    state.top3 = topTresProblemas(state.problemas);

    var svgContainer = document.getElementById("svg-container");
    fadeSwap(svgContainer, function () {
      document.getElementById("center-title").textContent = v.nombre;

      svgContainer.classList.remove("has-focus");
      svgContainer.innerHTML = v.svg || '<div class="empty-state">Sin geometría para esta vivienda.</div>';
      var svg = svgContainer.querySelector("svg");
      if (svg) ajustarViewBox(svg);
      wireRoomTooltips(svgContainer, v);
      wireRoomSelection(svgContainer, v);
      pintarPlano();
      // El SVG es nuevo, así que las capas y los indicadores hay que
      // reaplicarlos: viven en clases del propio `<svg>`, no en el estado.
      aplicarCapas();
      renderStatusFlags();
    });

    renderInspector();
  }

  // Los tres puntos del informe ejecutivo. El criterio, por orden:
  //   1. Severidad (crítico antes que importante antes que recomendación).
  //   2. Impacto real en la puntuación: `issues_por_impacto` trae los issues
  //      del evaluador ordenados por `puntos_ganados` (cuánto subiría la nota
  //      al corregir solo ese). Se usa para ORDENAR, nunca para mostrar la
  //      cifra: `puntos_ganados` pertenece al desglose de `scoring.py`, que
  //      es un cálculo distinto del `puntuacion` que muestra el informe, y
  //      escribir "+4,2" bajo un "86" sería aritmética falsa.
  //   3. A igualdad, primero el que tiene habitación asociada: un punto que
  //      se puede señalar en el plano vale más que uno que no.
  //
  // Ojo con `room_label`: en los issues de vivienda completa el backend lo
  // rellena con el NOMBRE DE LA VIVIENDA ("VT1/3"), no con una habitación.
  // Por eso no basta con comprobar que no esté vacío — hay que resolverlo
  // contra las habitaciones reales, o el informe acabaría diciendo "Baño ·
  // VT1/3" y prometiendo un punto en el plano que no existe.
  function indiceHabitacion(v, label) {
    if (!label) return -1;
    return v.habitaciones.findIndex(function (r) { return r.nombre === label; });
  }

  function topTresProblemas(merged) {
    var v = viviendaActual();
    var impacto = {};
    (state.data.issues_por_impacto || []).forEach(function (i, pos) {
      impacto[i.codigo + "|" + i.titulo + "|" + (i.room_label || "")] = pos;
    });

    return merged.map(function (it, idx) { return { it: it, idx: idx }; })
      .sort(function (a, b) {
        var sa = ISSUE_SEVERITY_ORDER.indexOf(a.it.severity);
        var sb = ISSUE_SEVERITY_ORDER.indexOf(b.it.severity);
        if (sa === -1) sa = 98; if (sb === -1) sb = 98;
        if (sa !== sb) return sa - sb;
        var ia = impacto[a.it.codigo + "|" + a.it.titulo + "|" + (a.it.room_label || "")];
        var ib = impacto[b.it.codigo + "|" + b.it.titulo + "|" + (b.it.room_label || "")];
        if (ia == null) ia = 999; if (ib == null) ib = 999;
        if (ia !== ib) return ia - ib;
        var la = indiceHabitacion(v, a.it.room_label) === -1 ? 1 : 0;
        var lb = indiceHabitacion(v, b.it.room_label) === -1 ? 1 : 0;
        if (la !== lb) return la - lb;
        return a.idx - b.idx;
      })
      .slice(0, 3)
      .map(function (x) { return x.idx; });
  }

  // Índice del problema más grave: primero por severidad (CRITICO >
  // IMPORTANTE > RECOMENDACION), y dentro de la misma severidad el primero
  // que llegó — `buildUnifiedProblems` ya entrega los issues del evaluador
  // antes que las heurísticas de calidad espacial y circulación.
  // =======================================================================
  // Panel derecho
  // =======================================================================
  // Una sola función decide qué se ve, con esta prioridad:
  //   1. Hay foco (un problema o una habitación) -> su detalle.
  //   2. Si no, el panel del modo activo. "resumen" -> informe ejecutivo.
  // Ya no existe un tercer caso "reposo sin modo": el reposo ES el modo
  // Resumen, y tiene contenido propio.

  function renderInspector() {
    var host = document.getElementById("inspector");
    var v = viviendaActual();
    if (!host || !v) return;

    // El inspector es la confirmación inmediata de un cambio de modo. No se
    // debe vaciar durante los 150 ms de `fadeSwap`: al pulsar "Hechos" eso
    // dejaba una ventana visible con la pestaña activa y el área en blanco.
    // El plano conserva su transición; el contenido del inspector se pinta
    // sincrónicamente para que estado y contenido no se separen nunca.
    var sel = state.seleccion;
    if (sel && sel.tipo === "problema") host.innerHTML = inspectorProblemaHtml(sel.idx);
    else if (sel && sel.tipo === "habitacion") host.innerHTML = inspectorHabitacionHtml(v, sel.idx);
    else host.innerHTML = inspectorModoHtml(v);
  }

  // Frase del veredicto. La API entrega `valoracion` como "verde" /
  // "amarillo" / "rojo", que es un nombre de color, no un juicio — el panel
  // lo imprimía tal cual. Aquí se traduce a lo que un arquitecto diría.
  //
  // Decía "Calidad espacial buena / mejorable / insuficiente", y eso tenía
  // dos problemas. Uno de registro: un adjetivo suelto sobre un número
  // grande de color es una nota escolar, no la conclusión de una revisión.
  // Y otro de exactitud: la puntuación NO mide calidad espacial. Su propia
  // definición (`SEMAFORO_INFO`, umbrales de `evaluator`) es "cumplimiento
  // normativo y de habitabilidad", y de hecho los tres puntos que encabezan
  // hoy el informe de ejemplo son todos de accesibilidad DB-SUA. El
  // veredicto pasa al registro de un informe de revisión y nombra lo que
  // realmente se ha medido.
  var VEREDICTO = {
    verde: "Cumplimiento correcto",
    amarillo: "Cumplimiento con reservas",
    rojo: "Cumplimiento insuficiente"
  };

  // Recuento por severidad de los problemas ya unificados de la vivienda
  // (`state.problemas`, la misma lista que cuenta el pie "Ver las N
  // incidencias"). Es lo que sustituye al adjetivo: un revisor no dice
  // "buena", dice cuántas y de qué gravedad.
  function recuentoSeveridad(problemas) {
    var n = { CRITICO: 0, IMPORTANTE: 0, RECOMENDACION: 0 };
    problemas.forEach(function (it) { if (n[it.severity] != null) n[it.severity]++; });
    var partes = [];
    if (n.CRITICO) partes.push(n.CRITICO + (n.CRITICO === 1 ? " crítica" : " críticas"));
    if (n.IMPORTANTE) partes.push(n.IMPORTANTE + (n.IMPORTANTE === 1 ? " importante" : " importantes"));
    if (n.RECOMENDACION) partes.push(n.RECOMENDACION + (n.RECOMENDACION === 1 ? " recomendación" : " recomendaciones"));
    return partes.join(" · ");
  }

  // El impacto se expresa en palabras, no en puntos. Ver la nota de
  // `topTresProblemas`: la cifra de `puntos_ganados` pertenece a otro
  // cálculo de puntuación distinto del 86 que encabeza el informe, y
  // mezclarlos daría una suma que no cuadra.
  var IMPACTO_LABEL = { CRITICO: "Impacto alto", IMPORTANTE: "Impacto medio", RECOMENDACION: "Impacto bajo" };

  // --- Informe ejecutivo (modo Resumen) --------------------------------
  // La conclusión del análisis, escrita antes de que el usuario pregunte:
  // qué calidad tiene, qué es lo más importante que corregir, y —vía los
  // puntos numerados del plano— dónde está.
  //
  // Exactamente 3 puntos, y sin contador de resto: tres elementos
  // jerarquizados son una conclusión; doce con filtros son una lista, y en
  // cuanto aparece un "y 9 más" vuelve a leerse como lista truncada.
  function informeEjecutivoHtml(v) {
    // El número deja de ser un trofeo. Antes: 45px, semibold y pintado del
    // color del semáforo, o sea el elemento más grande y más saturado de
    // toda la pantalla — en una herramienta cuya regla es "el plano manda",
    // el marcador no puede gritar más que el dibujo. Ahora es una magnitud
    // en tinta normal, y el semáforo sobrevive como una barra de 3px al
    // lado: sigue estando, deja de ser lo primero que se ve.
    //
    // La escala va en el rótulo ("ÍNDICE DE CALIDAD  0–100") y no colgando
    // de la cifra ("92 /100"). Hace falta —92 a secas no dice sobre
    // cuánto—, pero como sufijo obligaba a elegir entre dos alineaciones
    // malas: centrada flota, y a línea base compite con el número. En el
    // rótulo es lo que es, una unidad, y la cifra se queda sola.
    var recuento = recuentoSeveridad(state.problemas);

    // El veredicto puede salir "rojo" con una puntuación que, sola, no lo
    // explicaría: `rating_con_severidad` (evaluator.py) fuerza rojo ante
    // cualquier incidencia CRÍTICA, sin importar cuánto puntúe el resto —
    // "un crítico es, por definición, algo que puede bloquear el visado;
    // promediarlo con aciertos no lo hace menos bloqueante" (ver docstring
    // de esa función). Aquí solo se hace visible una regla que el backend
    // ya aplicaba en silencio (auditoría UX, P0-5) — no se recalcula nada.
    var nCriticos = state.problemas.filter(function (it) { return it.severity === "CRITICO"; }).length;
    var necesitaExplicacion = v.valoracion === "rojo" && nCriticos > 0 && v.puntuacion >= SCORE_YELLOW_THRESHOLD;
    var notaVeredicto = necesitaExplicacion
      ? (nCriticos === 1
          ? "Una incidencia crítica determina el veredicto: puede bloquear el visado, y la puntuación no la compensa."
          : nCriticos + " incidencias críticas determinan el veredicto: pueden bloquear el visado, y la puntuación no las compensa.")
      : "";

    var cabecera =
      '<div class="report-eyebrow">Índice de calidad' +
      '<span class="report-eyebrow-escala">0–100</span></div>' +
      '<div class="report-score-row">' +
      /* Puntuación en texto plano (2026-08-17, pedido explícito: "no como
         badges de colores") — la barra de color por semáforo se retira; el
         `title` que llevaba conserva la valoración como texto accesible. */
      '<span class="report-score" title="' + escapeHtml(semaforoTitle(v.valoracion)) + '">' + v.puntuacion + "</span>" +
      "</div>" +
      '<p class="report-state">' + escapeHtml(VEREDICTO[v.valoracion] || v.valoracion) + "</p>" +
      (recuento ? '<p class="report-tally">' + escapeHtml(recuento) + "</p>" : "") +
      (notaVeredicto ? '<p class="report-veredicto-nota">' + escapeHtml(notaVeredicto) + "</p>" : "");

    if (!state.top3.length) {
      return cabecera + '<hr class="report-rule">' +
        '<p class="inspector-empty">Sin incidencias detectadas en esta vivienda.</p>';
    }

    // "3 puntos que reducen la puntuación" describía el mecanismo interno
    // del cálculo; "Prioridad de intervención" describe para qué sirve la
    // lista, que es lo que el arquitecto necesita saber. Además, como
    // rótulo de sección ya no necesita concordancia de número.
    var lead = "Prioridad de intervención";

    return cabecera +
      '<hr class="report-rule">' +
      '<p class="report-lead">' + lead + "</p>" +
      '<ul class="report-points">' +
      state.top3.map(function (idx, orden) {
        var it = state.problemas[idx];
        // Solo se nombra la habitación si es una habitación de verdad (ver
        // `indiceHabitacion`): si el problema es de vivienda completa, la
        // línea se queda con su impacto y sin marca en el plano.
        var hab = indiceHabitacion(v, it.room_label) === -1 ? "" : it.room_label;
        return '<li><button type="button" class="report-point" data-problema="' + idx + '" ' +
          'data-orden="' + orden + '" data-room-label="' + escapeHtml(hab) + '">' +
          '<span class="report-point-num">' + (orden + 1) + "</span>" +
          '<span class="report-point-body">' +
          '<span class="report-point-title">' + escapeHtml(it.titulo) + "</span>" +
          '<span class="report-point-meta">' + escapeHtml(IMPACTO_LABEL[it.severity] || "") +
          (hab ? " · " + escapeHtml(hab) : "") + "</span>" +
          "</span></button></li>";
      }).join("") +
      "</ul>" +
      '<button type="button" class="report-exit" data-modo-ir="problemas">Ver las ' +
      state.problemas.length + " incidencias →</button>";
  }

  function inspectorProblemaHtml(idx) {
    var it = state.problemas[idx];
    if (!it) return '<p class="inspector-empty">Ese problema ya no está disponible.</p>';
    return '<button type="button" class="inspector-back">← Volver</button>' +
      '<p class="inspector-title">' + escapeHtml(it.titulo) + "</p>" +
      '<p class="inspector-sub">' +
      '<span style="color:' + ISSUE_SEVERITY_COLOR[it.severity] + '">' + escapeHtml(ISSUE_SEVERITY_LABEL[it.severity]) + "</span>" +
      " · " + escapeHtml(it.disciplina) + (it.room_label ? " · " + escapeHtml(it.room_label) : "") + "</p>" +
      detailBlock("Normativa afectada",
        escapeHtml(it.referencia_normativa || "") +
        (state.data.normativa_aviso
          ? '<p class="inspector-note">' + escapeHtml(state.data.normativa_aviso) + "</p>"
          : "")) +
      detailBlock("Explicación", escapeHtml(it.descripcion)) +
      detailBlock("Impacto", escapeHtml(it.impacto)) +
      detailBlock("Solución propuesta",
        "<ol>" + it.soluciones.map(function (s) { return "<li>" + escapeHtml(s) + "</li>"; }).join("") + "</ol>") +
      // Nivel 3: lo técnico (código, coste, efectos en cadena) plegado.
      '<button type="button" class="detail-more" data-more="1">Detalles técnicos</button>' +
      '<div class="detail-more-body" hidden>' +
      detailBlock("Código", escapeHtml(it.codigo)) +
      detailBlock("Coste estimado", escapeHtml(it.costeEstimado || "—")) +
      (it.chain ? chainEffectHtml(it.chain) : "") +
      "</div>";
  }

  function detailBlock(label, valueHtml) {
    return '<div class="detail-block"><div class="detail-block-label">' + escapeHtml(label) + "</div>" +
      '<div class="detail-block-value">' + valueHtml + "</div></div>";
  }

  function inspectorHabitacionHtml(v, idx) {
    var r = v.habitaciones[idx];
    if (!r) return '<p class="inspector-empty">Habitación no encontrada.</p>';
    var propios = state.problemas.filter(function (it) { return it.room_label === r.nombre; });
    return '<button type="button" class="inspector-back">← Volver</button>' +
      '<p class="inspector-title">' + escapeHtml(r.nombre) + "</p>" +
      '<p class="inspector-sub">' + r.area_m2.toFixed(2) + " m²" +
      (r.orientacion_cardinal ? " · " + escapeHtml(r.orientacion_cardinal) : "") + "</p>" +
      (propios.length
        ? '<div class="inspector-label">Problemas (' + propios.length + ")</div>" + listaProblemasHtml(propios)
        : '<p class="inspector-empty">Sin incidencias en esta habitación.</p>');
  }

  // Lista compacta: punto de severidad + título. Sin acordeón — pulsar
  // lleva al detalle, como en Linear. Cada fila lleva su índice dentro de
  // `state.problemas` para poder navegar al detalle sin volver a buscar.
  function listaProblemasHtml(items) {
    return '<ul class="issues-list">' + items.map(function (it) {
      var idx = state.problemas.indexOf(it);
      return '<li class="issue-item">' +
        '<button type="button" class="issue-summary" data-problema="' + idx + '" ' +
        'style="--issue-color:' + ISSUE_SEVERITY_COLOR[it.severity] + '" ' +
        'data-room-label="' + escapeHtml(it.room_label || "") + '">' +
        '<span class="issue-titulo">' + escapeHtml(it.titulo) +
        (it.chain ? ' <span class="chain-icon" title="Tiene efectos derivados">' + CHAIN_ICON + "</span>" : "") + "</span>" +
        '<span class="issue-meta"><span>' + escapeHtml(it.disciplina) + "</span>" +
        (it.room_label ? "<span>" + escapeHtml(it.room_label) + "</span>" : "") + "</span>" +
        "</button></li>";
    }).join("") + "</ul>";
  }

  function inspectorModoHtml(v) {
    if (state.modo === "resumen") return informeEjecutivoHtml(v);
    if (state.modo === "espacio") return modoEspacioHtml(v);
    if (state.modo === "luz") return toolLuzHtml(v);
    if (state.modo === "normativa") return toolNormativaHtml(v);
    if (state.modo === "hechos") return toolHechosHtml(v);
    if (state.modo === "cuadro") return toolCuadroSuperficiesHtml(v);
    if (state.modo === "problemas") return toolProblemasHtml(v);
    if (state.modo === "ia") return modoDiagnosticoHtml(v);
    if (state.modo === "concurso") return modoConcursoHtml(v);
    return informeEjecutivoHtml(v);
  }

  // Espacio: cifras agregadas + botón que abre la lista completa en un
  // panel flotante. La lista de habitaciones ya no vive abierta en ningún
  // sitio.
  function modoEspacioHtml(v) {
    return '<div class="inspector-label">Espacio</div>' +
      // El plano se colorea por tipo de uso en este modo (`pintarPlano`,
      // `modo === "espacio"`) — la leyenda dice qué es cada color, sin
      // cambiar ni el cálculo ni la paleta (auditoría UX, P0-3).
      legendHtml(ESPACIO_LEGEND) +
      detailBlock("Superficie total", v.superficie_total_m2.toFixed(2) + " m²") +
      // BUG corregido (auditoría de tablas AM_*, 2026-08-13): esta línea
      // recalculaba la misma cifra sumando en JS los `area_m2` YA
      // redondeados a 2 decimales de cada habitación
      // (`v.habitaciones.reduce(...)`), en vez de leer
      // `v.superficie_total_m2` (que el backend calcula como
      // `round(suma_de_areas_SIN_redondear, 2)`, `evaluator.Unit.
      // total_area_m2` — ver `analyzer/api_serializer.py`). "Superficie
      // total" y "Suma de habitaciones" son, por definición, EXACTAMENTE
      // la misma magnitud (`total_area_m2` ya es la suma de `rooms`, nunca
      // incluye envolvente/exteriores) — sumar por separado en el cliente
      // solo reintroducía el error de redondeo "suma de redondeados !=
      // redondeo de la suma". Confirmado sobre `ejemplo.dxf` real: VT3/3
      // mostraba "66.5 m²" y "66.6 m²" a la vez en el mismo panel para el
      // mismo dato. Ahora las dos líneas leen el mismo campo — coinciden
      // siempre, por construcción, no por coincidencia.
      detailBlock("Suma de habitaciones", v.superficie_total_m2.toFixed(2) + " m²") +
      capasAmHtml(v) +
      '<div class="detail-block"><div class="detail-block-label">Habitaciones (' + v.habitaciones.length + ")</div></div>" +
      '<button type="button" class="btn-reveal" data-panel="habitaciones">Ver habitaciones</button>';
  }

  // Cierre de la integración del contrato de clasificación DXF (capas
  // `AM_UTIL_INT`/`AM_CONS_CER`/`AM_UTIL_EXT`/`AM_CONS_EXT`,
  // `analyzer/parser.py`): "Superficie total"/"Suma de habitaciones" de
  // arriba siguen siendo SOLO la suma de `habitaciones` (AM_UTIL_INT en un
  // plano con capas AM_*, sin tocar) — esta función añade, aparte, lo que
  // esas dos cifras nunca han incluido: la envolvente construida cerrada y
  // las superficies exteriores. Vacío -sin bloques- en cualquier vivienda
  // sin ningún dato AM_* que mostrar, mismo criterio "silencioso" que ya
  // aplica `validacion_capas.py` en el backend: un plano heredado no recibe
  // ningún bloque nuevo.
  function capasAmHtml(v) {
    var bloques = "";
    if (v.envolvente_cerrada_m2 != null) {
      bloques += detailBlock("Superficie construida cerrada", v.envolvente_cerrada_m2.toFixed(2) + " m²");
    }
    if (v.superficie_util_exterior_m2) {
      bloques += detailBlock("Superficie útil exterior", v.superficie_util_exterior_m2.toFixed(2) + " m²");
    }
    if (v.envolvente_exterior_m2) {
      bloques += detailBlock("Superficie construida exterior", v.envolvente_exterior_m2.toFixed(2) + " m²");
    }
    if (v.clasificacion_capas === "am") {
      bloques += detailBlock("Origen de clasificación", "Capas AM_* (contrato de clasificación DXF)");
    }
    // Diagnósticos de conformidad (Fase 2, `validacion_capas.py`), cierre de
    // la integración `AM_*` (docs/prd/2026-08-13-visualizacion-diagnosticos-
    // capas-am.md). Entrada LOCAL: solo los diagnósticos propios de ESTA
    // vivienda (`d.vivienda === v.nombre`) — los que no tienen vivienda
    // (capa casi correcta, capa reservada, geometría descartada...) no se
    // absorben aquí a propósito (§13 del PRD: no hay forma fiable de saber
    // a qué vivienda "pertenecerían" sin adivinar), tienen su propia entrada
    // de proyecto en `renderViviendaList()`. Silencioso si esta vivienda no
    // tiene ningún diagnóstico propio.
    var diagnosticosPropios = diagnosticosCapasAmDeVivienda(v);
    if (diagnosticosPropios.length) {
      bloques += '<button type="button" class="btn-reveal diag-capas-entrada" ' +
        'data-panel="diagnosticos-capas-am" data-panel-alcance="vivienda">' +
        diagCapasConteoHtml(diagnosticosPropios) +
        " Diagnósticos de capas AM_*</button>";
    }
    return bloques;
  }

  // --- Diagnósticos de capas AM_* (Fase 2, `validacion_capas.py`) --------
  // Informativos, NUNCA normativos: no generan `IssueReport`, no tocan
  // `score_pct`/`puntuacion`/`valoracion`/el semáforo de cumplimiento, y no
  // bloquean ninguna acción (guardar, reanalizar, exportar). Solo explican
  // por qué una capa `AM_*` no se ha podido usar tal cual estaba dibujada.

  // Mismo patrón de filtrado en JS que ya usa el resto de la SPA para listas
  // planas etiquetadas por vivienda (`issue.unit_name === v.nombre` en el
  // plan de acción, `ai.diagnosticos`/`calidad_espacial`/`circulacion`
  // filtrados por `.vivienda === v.nombre`) — no hace falta que
  // `api_serializer.py` preagrupe `diagnosticos_clasificacion` por vivienda,
  // sería la misma operación hecha dos veces (PRD §13, decisión 2).
  function diagnosticosCapasAm() {
    return (state.data && state.data.diagnosticos_clasificacion) || [];
  }

  function diagnosticosCapasAmDeVivienda(v) {
    return diagnosticosCapasAm().filter(function (d) { return d.vivienda === v.nombre; });
  }

  // Entrada de PROYECTO: todo diagnóstico que la entrada local de ninguna
  // vivienda va a mostrar nunca — sin `vivienda` (la mayoría de los
  // códigos: capa casi correcta, capa reservada en uso, geometría
  // descartada) o con una `vivienda` que ya no corresponde a ninguna Unit
  // final (`ENVOLVENTE_SIN_VIVIENDA` cuando la etiqueta VT no agrupó
  // ninguna habitación) — sin esta segunda vía esos diagnósticos no
  // aparecerían en ningún sitio de la SPA.
  function diagnosticosCapasAmSinVivienda() {
    var nombres = (state.data && state.data.viviendas || []).map(function (v) { return v.nombre; });
    return diagnosticosCapasAm().filter(function (d) {
      return !d.vivienda || nombres.indexOf(d.vivienda) === -1;
    });
  }

  var DIAG_CAPAS_SEVERIDAD_LABEL = { ERROR: "Error", WARNING: "Aviso", INFO: "Información" };

  // Deliberadamente NO reutiliza --color-critical/--color-warning/
  // --color-success (el semáforo de cumplimiento CTE, `orient-badge-*`,
  // `problems-counter`...): un aviso de higiene de capas no es un
  // incumplimiento normativo y compartir tinta los haría indistinguibles
  // en pantalla (PRD §8.1/§9). Clases nuevas en `style.css`.
  function diagCapasSeveridadClase(severidad) {
    return "diag-capas-sev-" + (severidad || "info").toLowerCase();
  }

  function diagCapasPeorSeveridad(diagnosticos) {
    if (diagnosticos.some(function (d) { return d.severidad === "ERROR"; })) return "ERROR";
    if (diagnosticos.some(function (d) { return d.severidad === "WARNING"; })) return "WARNING";
    return "INFO";
  }

  function diagCapasConteoHtml(diagnosticos) {
    var peor = diagCapasPeorSeveridad(diagnosticos);
    return '<span class="diag-capas-conteo ' + diagCapasSeveridadClase(peor) + '">' +
      diagnosticos.length + "</span>";
  }

  // Único renderer del listado: lo usan las dos puertas de entrada (local y
  // de proyecto) a través de `abrirPanelFlotante`, nunca se duplica.
  function listaDiagnosticosCapasAmHtml(diagnosticos) {
    if (!diagnosticos.length) return '<p class="inspector-empty">Sin diagnósticos.</p>';
    return '<ul class="diag-capas-list">' + diagnosticos.map(function (d) {
      var clase = diagCapasSeveridadClase(d.severidad);
      var etiqueta = DIAG_CAPAS_SEVERIDAD_LABEL[d.severidad] || d.severidad;
      return '<li class="diag-capas-item ' + clase + '">' +
        '<span class="diag-capas-badge ' + clase + '">' + escapeHtml(etiqueta) + "</span>" +
        '<span class="diag-capas-mensaje">' + escapeHtml(d.mensaje) + "</span>" +
        (d.capa ? '<span class="diag-capas-meta">Capa: ' + escapeHtml(d.capa) + "</span>" : "") +
        (d.vivienda ? '<span class="diag-capas-meta">Vivienda: ' + escapeHtml(d.vivienda) + "</span>" : "") +
        "</li>";
    }).join("") + "</ul>";
  }

  function toolLuzHtml(v) {
    var calidad = calcularCalidadLuminica(v.habitaciones);
    return '<div class="inspector-label">Luz natural</div>' +
      // El overlay del plano usa estos mismos 3 niveles (`renderLuzNaturalOverlay`,
      // `LUZ_OVERLAY_COLOR`) — la leyenda solo los nombra (auditoría UX, P0-3).
      legendHtml(LUZ_LEGEND) +
      (calidad == null ? "" : detailBlock("Calidad lumínica", calidad + " / 100")) +
      '<button type="button" class="btn-reveal" data-panel="orientacion">Ver orientación por habitación</button>';
  }

  // Pinta lo que el backend ya ha evaluado. No calcula nada: el veredicto
  // ("cumple"/"no cumple") lo decide `evaluator.evaluate_unit_minimum_area`
  // y viaja en `v.normativa_aplicada`. Antes se recalculaba aquí contra una
  // tabla propia que contradecía al backend (ver cabecera del fichero).
  function toolNormativaHtml(v) {
    var n = v.normativa_aplicada;
    if (!n) {
      return '<div class="inspector-label">Normativa</div>' +
        '<p class="inspector-empty">El análisis no incluye normativa aplicada.</p>';
    }
    var html = '<div class="inspector-label">Normativa</div>';
    (n.reglas || []).forEach(function (r) {
      var ok = r.cumple;
      html += detailBlock(escapeHtml(r.nombre),
        '<span style="color:' + (ok ? "var(--color-success)" : "var(--color-critical)") + '">' +
        escapeHtml(r.valor) + " · " + (ok ? "cumple" : "no cumple") + "</span>") +
        '<p class="inspector-note">' + escapeHtml(r.base) + "</p>";
    });
    if (n.aviso) html += '<p class="inspector-note">' + escapeHtml(n.aviso) + "</p>";
    return html;
  }

  // =======================================================================
  // "Hechos": CAP-1..5 tal cual los devuelve `/api/analizar` en
  // `proyecto.usos/planta/ocupacion/sectorizacion` -- sin recalcular nada,
  // sin convertir UNKNOWN/ESTIMATED en incumplimiento. PRD "Tabla de
  // hechos CAP-1..5" (2026-08-14). No confundir con `toolNormativaHtml`
  // (arriba): esa es una regla LOE distinta, hardcodeada.
  // =======================================================================

  var HECHO_ESTADO_LABEL = { KNOWN: "Declarado", ESTIMATED: "Estimado", UNKNOWN: "No determinado" };
  var HECHO_ESTADO_CLASE = {
    KNOWN: "hecho-badge-known", ESTIMATED: "hecho-badge-estimated", UNKNOWN: "hecho-badge-unknown"
  };

  function hechoBadgeHtml(estado) {
    var clase = HECHO_ESTADO_CLASE[estado] || "hecho-badge-unknown";
    var etiqueta = HECHO_ESTADO_LABEL[estado] || estado;
    return '<span class="hecho-badge ' + clase + '">' + escapeHtml(etiqueta) + "</span>";
  }

  // `confianza` solo se pinta si existe -- un hecho UNKNOWN la trae `null`
  // (contrato de `analyzer/hechos.py`), y no hay ninguna confianza que
  // mostrar sobre un dato que no se conoce.
  function hechoConfianzaHtml(confianza) {
    return confianza ? '<span class="hecho-confianza">Confianza: ' + escapeHtml(confianza) + "</span>" : "";
  }

  // `motivo` solo se pinta si aporta algo distinto de `explicacion`: en
  // los hechos reales a veces son el mismo texto (p. ej. `ocupacion`), y
  // repetirlo sería ruido, no fidelidad.
  function hechoExplicacionHtml(explicacion, motivo) {
    var html = '<p class="inspector-note">' + escapeHtml(explicacion || "") + "</p>";
    if (motivo && motivo !== explicacion) {
      html += '<p class="inspector-note hecho-motivo">' + escapeHtml(motivo) + "</p>";
    }
    return html;
  }

  function hechosDeVivienda(lista, v) {
    var ambito = "vivienda " + v.nombre;
    return (lista || []).filter(function (h) { return h.ambito === ambito; });
  }

  function hechoBlockHtml(titulo, h, valorTexto, notaExtraHtml) {
    var cuerpo = hechoBadgeHtml(h.estado) + hechoConfianzaHtml(h.confianza) +
      (valorTexto ? '<p class="hecho-valor">' + valorTexto + "</p>" : "") +
      hechoExplicacionHtml(h.explicacion, h.motivo) +
      (notaExtraHtml || "");
    return detailBlock(titulo, cuerpo);
  }

  function hechoUsoHtml(h) {
    var valor = h.estado !== "UNKNOWN" && h.uso ? escapeHtml(h.uso.replace(/_/g, " ")) : "";
    return hechoBlockHtml("Uso previsto", h, valor);
  }

  function hechoPlantaHtml(h) {
    var valor = "";
    if (h.estado !== "UNKNOWN" && h.numero != null) {
      valor = "Planta " + h.numero +
        (h.sobre_rasante === true ? " (sobre rasante)" : h.sobre_rasante === false ? " (bajo rasante)" : "");
    }
    return hechoBlockHtml("Planta", h, valor);
  }

  function hechoOcupacionHtml(h) {
    var valor = "";
    if (h.estado !== "UNKNOWN" && h.personas != null) {
      valor = escapeHtml(h.presentacion_personas || (h.personas + " personas"));
    }
    // `agregado_no_normativo` ya lo declara el propio backend
    // (`analyzer/ocupacion.py`): el ámbito normativo real es la planta, no
    // la vivienda. Se pinta tal cual, no se oculta.
    var nota = h.agregado_no_normativo
      ? '<p class="inspector-note hecho-nota">Agregado por vivienda: el ámbito normativo real es la planta' +
        (h.ambito_normativo ? " (" + escapeHtml(h.ambito_normativo) + ")" : "") + ".</p>"
      : "";
    return hechoBlockHtml("Ocupación", h, valor, nota);
  }

  function hechoSectorizacionHtml(h) {
    var valor = "";
    if (h.estado !== "UNKNOWN" && h.veredicto) {
      valor = escapeHtml(h.veredicto) +
        (h.superficie_acumulada_m2 != null
          ? " — " + h.superficie_acumulada_m2.toFixed(2) + " m² acumulados (límite " + h.limite_m2 + " m²)"
          : "");
    }
    return hechoBlockHtml("Sectorización (C01)", h, valor);
  }

  // Solo pinta las familias de hecho presentes en la respuesta (p. ej.
  // `/api/generar` no trae `usos`/`ocupacion`/`sectorizacion`, solo
  // `planta` -- ver `app.py`). Ninguna fila se inventa cuando el campo no
  // existe.
  function toolHechosHtml(v) {
    var proyecto = (state.data && state.data.proyecto) || {};
    var bloques = [];
    hechosDeVivienda(proyecto.usos, v).forEach(function (h) { bloques.push(hechoUsoHtml(h)); });
    hechosDeVivienda(proyecto.planta, v).forEach(function (h) { bloques.push(hechoPlantaHtml(h)); });
    hechosDeVivienda(proyecto.ocupacion, v).forEach(function (h) { bloques.push(hechoOcupacionHtml(h)); });
    hechosDeVivienda(proyecto.sectorizacion, v).forEach(function (h) { bloques.push(hechoSectorizacionHtml(h)); });

    var html = '<div class="inspector-label">Hechos (' + escapeHtml(v.nombre) + ")</div>";
    if (!bloques.length) {
      return html + '<p class="inspector-empty">Este análisis no publica hechos CAP-1..5 para esta vivienda.</p>';
    }
    return html + bloques.join("");
  }

  // ---------------------------------------------------------------------
  // Fase 6: la tabla del cuadro de superficies visible en pantalla, sin
  // descargar nada. Pide una vez `/api/cuadro-superficies/estado`
  // (reenviando `state.archivoAnalizado`, igual que el resto de Fase 4/5) y
  // cachea el resultado en `state.cuadroTabla` -- no recalcula nada aquí:
  // solo pinta lo que ya devolvió `calcular_relleno_cuadro` en el backend.
  // ---------------------------------------------------------------------

  // Prioridad de lectura: un valor declarado por el usuario o ya presente en
  // el DXF siempre se etiqueta así, sin importar en qué ESTADO cerrado
  // (CALCULADO/CERO_REAL/...) haya quedado. La clase CSS es una función
  // aparte de la etiqueta -- mismo criterio de prioridad, para la
  // "insignia" de color (ver `.cuadro-origen-*` en style.css).
  function _origenCeldaCuadro(c) {
    if (c.declarado_por_usuario) return "Declarado por el arquitecto";
    if (c.preexistente) return "Ya estaba en el DXF";
    if (c.estado === "BLOQUEADO" || c.estado === "NO_DISPONIBLE") return "Pendiente";
    return "Calculado por ArchMuse";
  }

  function _origenClaseCuadro(c) {
    if (c.declarado_por_usuario) return "cuadro-origen-declarado";
    if (c.preexistente) return "cuadro-origen-dxf";
    if (c.estado === "BLOQUEADO" || c.estado === "NO_DISPONIBLE") return "cuadro-origen-pendiente";
    return "cuadro-origen-calculado";
  }

  // Agrupación puramente VISUAL, por el mismo `campo` que ya identifica
  // cada celda (no una segunda clasificación de habitaciones -- eso sigue
  // viviendo solo en analyzer/cuadro_superficies.py). Solo ordena y titula
  // lo que el backend ya devolvió; ningún campo sin grupo aquí se pierde
  // ("Otros" de respaldo, nunca una celda invisible por un campo nuevo).
  var _GRUPO_CAMPO_CUADRO = {
    salon_cocina: "Interior", pasillo: "Interior", dormitorio_1: "Interior", dormitorio_2: "Interior",
    dormitorio_3: "Interior", bano: "Interior", aseo: "Interior", vestibulo: "Interior",
    tendedero: "Exterior", terraza_1: "Exterior", terraza_2: "Exterior",
    total_util_interior: "Totales", total_util_exterior: "Totales", total_util: "Totales",
    superficie_construida_cerrada: "Datos de proyecto", superficie_construida_exterior: "Datos de proyecto",
    numero_unidades: "Datos de proyecto", vivienda_tipo: "Datos de proyecto",
  };

  function cuadroTablaHtml(celdas) {
    var grupoAnterior = null;
    var filas = (celdas || []).map(function (c) {
      var grupo = _GRUPO_CAMPO_CUADRO[c.campo] || "Otros";
      var cabecera = "";
      if (grupo !== grupoAnterior) {
        cabecera = '<tr class="cuadro-tabla-grupo"><td colspan="3">' + escapeHtml(grupo) + "</td></tr>";
        grupoAnterior = grupo;
      }
      var pendiente = c.estado === "BLOQUEADO" || c.estado === "NO_DISPONIBLE";
      return cabecera + '<tr class="' + (pendiente ? "cuadro-fila-pendiente" : "") + '">' +
        "<td>" + escapeHtml(c.etiqueta || etiquetaCampoLegible(c.campo)) + "</td>" +
        '<td class="cuadro-tabla-valor">' + escapeHtml(pendiente ? "—" : c.texto) + "</td>" +
        '<td class="cuadro-tabla-origen"><span class="cuadro-origen-badge ' + _origenClaseCuadro(c) + '">' +
        escapeHtml(_origenCeldaCuadro(c)) + "</span></td>" +
        "</tr>";
    }).join("");
    return '<div class="cuadro-tabla-wrap"><table class="cuadro-tabla">' +
      "<thead><tr><th>Campo</th><th>Valor</th><th>Procedencia</th></tr></thead>" +
      "<tbody>" + filas + "</tbody></table></div>";
  }

  // Cuerpo compartido por las dos vistas del cuadro: la pequeña del
  // inspector (`toolCuadroSuperficiesHtml`, se conserva) y la GRANDE del
  // lienzo principal (`renderCuadroLienzo`, Fase 6c -- "quiero que se vea
  // como el plano, pero en vez del plano el cuadro"). Una sola función
  // decide qué mostrar según el estado; ninguna de las dos vistas
  // reimplementa la lógica de carga/error/pie por separado.
  function contenidoCuadroSuperficies() {
    var proyecto = (state.data && state.data.proyecto) || {};
    if (!proyecto.cuadro_superficies_detectado) {
      return '<p class="inspector-empty">No se ha detectado ningún "CUADRO DE SUPERFICIES POR ' +
        'TIPO DE VIVIENDA" en este DXF.</p>';
    }
    if (!state.archivoAnalizado) {
      return '<p class="inspector-empty">Solo disponible justo después de analizar -- ArchMuse no ' +
        "guarda el DXF original, así que un proyecto reabierto de la lista no puede volver a leerlo. Vuelve a " +
        "subir el archivo para ver el cuadro.</p>";
    }
    var t = state.cuadroTabla;
    if (!t) {
      cargarCuadroTabla();
      return '<p class="muted">Leyendo el cuadro del plano…</p>';
    }
    if (t.cargando) return '<p class="muted">Leyendo el cuadro del plano…</p>';
    if (t.error) return '<p class="cuadro-conflicto">' + escapeHtml(t.error) + "</p>";
    // Sin lo de tendedero/terraza/superficies exteriores resuelto, el
    // formulario se pinta AQUÍ MISMO, debajo de la tabla -- no hay botón
    // que abra un modal aparte que haya que descubrir primero (Fase 6d:
    // "quiero que sea posible rellenarlo todo desde ArchMuse", "quiero
    // verlo, no descargarlo"). ArchMuse no lo adivina (dos piezas reales
    // etiquetadas "Tendedero" en v2s.dxf para tres huecos: no hay una
    // asignación única sin que lo diga el arquitecto). Aplicar respuestas
    // actualiza esta misma tabla, nunca descarga nada por sí solo.
    var pie = t.solicitudes.length
      ? cuadroFormularioInlineHtml(t.solicitudes, t.valores, t.asignaciones, t.pendientes)
      : '<p class="muted">Todas las celdas tienen un valor real.</p>' +
        '<button type="button" class="btn-reveal" id="btn-descargar-cuadro-completo" ' +
        'data-accion="descargar-cuadro-completo">Descargar cuadro completo (DXF)</button>';
    return cuadroTablaHtml(t.celdas) + pie;
  }

  // Panel pequeño del inspector: vacío a propósito (petición explícita de
  // Pablo -- el puntero "La tabla completa... se ve en el lienzo
  // principal" sobraba). La vista real y completa (incluido el formulario
  // inline cuando falta algo) es la GRANDE, en el lienzo principal
  // (`renderCuadroLienzo`) -- repetirla aquí, aunque fuera solo un aviso,
  // ya no aporta nada que el propio lienzo no diga por sí solo.
  function toolCuadroSuperficiesHtml(v) {
    return "";
  }

  // Fase 6c: la vista GRANDE, en el lienzo principal -- mismo sitio donde
  // vive el plano en el resto de modos (ver `aplicarModoLienzo`). Es la
  // ÚNICA vista con la tabla real y el formulario inline.
  function renderCuadroLienzo() {
    var host = document.getElementById("cad-cuadro-superficies");
    if (!host) return;
    host.innerHTML = '<div class="cad-cuadro-grande"><h1>Cuadro de superficies</h1>' +
      contenidoCuadroSuperficies() + "</div>";
  }

  // Refresca las DOS vistas a la vez tras un cambio asíncrono (llegada de
  // datos, respuestas aplicadas) -- solo si el modo "cuadro" sigue activo
  // (si el arquitecto ya se fue a otro modo, no hay nada que repintar).
  function refrescarVistaCuadro() {
    if (state.modo !== "cuadro") return;
    renderInspector();
    renderCuadroLienzo();
  }

  // El diagnóstico de IA se pide bajo demanda -- nunca automáticamente al
  // analizar/reabrir un proyecto (ver `app.py`, `/api/proyectos/<id>/
  // diagnostico-ia`) -- este botón (`modoDiagnosticoHtml`) es la única vía.
  // `proyectoId` se captura al lanzar la petición y se comprueba de nuevo
  // al recibir la respuesta: si el arquitecto ya cambió de proyecto
  // mientras tanto, la respuesta se descarta en vez de escribirse sobre el
  // proyecto equivocado (mismo cuidado que `abrirProyecto`/`irAInicio` al
  // limpiar `archivoAnalizado`/`cuadroTabla`).
  function generarDiagnosticoIA() {
    if (!state.data || !state.data.proyecto_id) return;
    if (state.diagnosticoIaEstado === "cargando") return;
    var proyectoId = state.data.proyecto_id;
    state.diagnosticoIaEstado = "cargando";
    renderInspector();

    fetch("/api/proyectos/" + encodeURIComponent(proyectoId) + "/diagnostico-ia", { method: "POST" })
      .then(function (resp) {
        return resp.json().then(function (json) { return { ok: resp.ok, json: json }; });
      })
      .then(function (result) {
        if (!state.data || state.data.proyecto_id !== proyectoId) return; // ya no aplica
        if (!result.ok) {
          state.diagnosticoIaEstado = { error: result.json.error || "No se pudo generar el diagnóstico de IA." };
          renderInspector();
          return;
        }
        state.data.analisis_ia = result.json.analisis_ia;
        state.diagnosticoIaEstado = null;
        renderInspector();
      })
      .catch(function () {
        if (!state.data || state.data.proyecto_id !== proyectoId) return;
        state.diagnosticoIaEstado = { error: "No se pudo generar el diagnóstico de IA." };
        renderInspector();
      });
  }

  // --- Checklist de inspección en campo (2026-08-16,
  // docs/prd/2026-08-16-checklist-inspeccion-campo.md) ------------------------------------------
  // Overlay a pantalla completa, mismo patrón que `#room-viewer-3d`/`#viewer-sandbox` (este proyecto
  // no tiene modales) -- pero cableado y renderizado ENTERAMENTE desde este archivo (a diferencia de
  // esos dos, no necesita three.js ni ningún módulo aparte, es DOM plano). El botón del ribbon que lo
  // abre (`abrir-checklist-campo`, `ACCIONES_CAD`) solo existe con `proyecto_id` (`ribbonPanelHtml`),
  // así que `abrirChecklistCampo` puede asumir que `state.data.proyecto_id` existe.

  function abrirChecklistCampo() {
    if (!state.data || !state.data.proyecto_id) return;
    var overlay = document.getElementById("checklist-campo");
    if (!overlay) return;
    overlay.classList.add("open");
    // Se pide una vez por apertura -- reabrir siempre vuelve a pedir al backend (el estado
    // interactivo de casillas/notas no se persiste, decisión explícita del PRD §14/§6).
    pedirChecklistCampo();
  }

  function cerrarChecklistCampo() {
    var overlay = document.getElementById("checklist-campo");
    if (overlay) overlay.classList.remove("open");
  }

  // Mismo patrón defensivo que `generarDiagnosticoIA`: `proyectoId` se captura al lanzar la
  // petición y se vuelve a comprobar al recibir la respuesta -- si el arquitecto ya cerró este
  // proyecto o abrió otro mientras tanto, la respuesta se descarta en vez de escribirse encima del
  // proyecto equivocado.
  function pedirChecklistCampo() {
    if (!state.data || !state.data.proyecto_id) return;
    var proyectoId = state.data.proyecto_id;
    state.checklistCampo = "cargando";
    renderChecklistCampo();

    fetch("/api/proyectos/" + encodeURIComponent(proyectoId) + "/checklist-campo")
      .then(function (resp) {
        return resp.json().then(function (json) { return { ok: resp.ok, json: json }; });
      })
      .then(function (result) {
        if (!state.data || state.data.proyecto_id !== proyectoId) return; // ya no aplica
        if (!result.ok) {
          state.checklistCampo = { error: result.json.error || "No se pudo cargar el checklist de visita." };
          renderChecklistCampo();
          return;
        }
        // `marcados`/`notas`: estado interactivo, vacío al recibir la respuesta -- se rellena solo
        // con lo que el arquitecto vaya marcando/escribiendo durante ESTA apertura del overlay.
        state.checklistCampo = {
          bloques: result.json.bloques, tieneSitioReal: result.json.tiene_sitio_real,
          marcados: {}, notas: {}
        };
        renderChecklistCampo();
      })
      .catch(function () {
        if (!state.data || state.data.proyecto_id !== proyectoId) return;
        state.checklistCampo = { error: "No se pudo cargar el checklist de visita." };
        renderChecklistCampo();
      });
  }

  function checklistCampoHtml() {
    var c = state.checklistCampo;
    if (c === "cargando") return '<p class="checklist-campo-estado">Cargando checklist…</p>';
    if (!c) return "";
    if (c.error) return '<p class="checklist-campo-estado checklist-campo-error">' + escapeHtml(c.error) + "</p>";

    var aviso = !c.tieneSitioReal
      ? '<p class="checklist-campo-aviso">Este proyecto no tiene una parcela real enlazada — las comprobaciones son generales, sin notas de Catastro/entorno para esta parcela concreta.</p>'
      : "";

    return aviso + c.bloques.map(function (bloque) {
      return '<section class="checklist-campo-bloque">' +
        '<h3 class="checklist-campo-bloque-titulo">' + escapeHtml(bloque.titulo) + "</h3>" +
        '<ul class="checklist-campo-items">' +
        bloque.items.map(function (item) {
          var marcado = !!c.marcados[item.id];
          var nota = c.notas[item.id] || "";
          return '<li class="checklist-campo-item' + (marcado ? " is-marcado" : "") + '">' +
            '<label class="checklist-campo-item-cabecera">' +
            '<input type="checkbox" data-checklist-item="' + escapeHtml(item.id) + '"' + (marcado ? " checked" : "") + ">" +
            "<span>" + escapeHtml(item.texto) + "</span>" +
            "</label>" +
            (item.nota ? '<p class="checklist-campo-item-nota">' + escapeHtml(item.nota) + "</p>" : "") +
            '<textarea class="checklist-campo-item-libre" data-checklist-nota="' + escapeHtml(item.id) +
            '" placeholder="Nota de campo (opcional)">' + escapeHtml(nota) + "</textarea>" +
            "</li>";
        }).join("") +
        "</ul></section>";
    }).join("");
  }

  function renderChecklistCampo() {
    var cont = document.getElementById("checklist-campo-contenido");
    if (cont) cont.innerHTML = checklistCampoHtml();
  }

  // Cableado UNA sola vez (mismo criterio que `wireSidebar`/los puentes de `document` al final del
  // archivo): casilla y nota libre actualizan `state.checklistCampo` SIN repintar todo el overlay
  // (repintar en cada tecla de la nota le robaría el foco/cursor al textarea al usuario a media
  // frase) -- solo se alterna a mano la clase `is-marcado` del `<li>` correspondiente.
  function wireChecklistCampo() {
    var cerrar = document.getElementById("btn-checklist-campo-cerrar");
    if (cerrar) cerrar.addEventListener("click", cerrarChecklistCampo);
    var imprimir = document.getElementById("btn-checklist-campo-imprimir");
    if (imprimir) imprimir.addEventListener("click", function () { window.print(); });

    var cont = document.getElementById("checklist-campo-contenido");
    if (!cont) return;
    cont.addEventListener("change", function (e) {
      var chk = e.target.closest("[data-checklist-item]");
      if (!chk || !state.checklistCampo || state.checklistCampo === "cargando" || state.checklistCampo.error) return;
      state.checklistCampo.marcados[chk.dataset.checklistItem] = chk.checked;
      var li = chk.closest(".checklist-campo-item");
      if (li) li.classList.toggle("is-marcado", chk.checked);
    });
    cont.addEventListener("input", function (e) {
      var area = e.target.closest("[data-checklist-nota]");
      if (!area || !state.checklistCampo || state.checklistCampo === "cargando" || state.checklistCampo.error) return;
      state.checklistCampo.notas[area.dataset.checklistNota] = area.value;
    });
  }

  // --- "Viabilidad económica y exportación" ---------------------------------
  //
  // `docs/prd/2026-08-17-viabilidad-economica-y-exportacion-dxf.md`. Mismo
  // patrón de overlay que el Checklist de campo (arriba): panel a pantalla
  // completa, se abre/cierra con una clase `.open`, y el `input` de los 3
  // campos actualiza `state.viabilidad` + repinta SOLO el bloque de
  // resultados (nunca el panel entero) para no robarle el foco al usuario
  // a media escritura. A diferencia del Checklist, no necesita `proyecto_id`
  // -- funciona igual con un proyecto recién generado/analizado que aún no
  // se ha guardado, porque todo lo que usa (superficie construida, y las
  // habitaciones de la vivienda activa) ya está en memoria en `state.data`.

  function superficieConstruidaTotal() {
    var u = state.data && state.data.urbanismo;
    if (u && typeof u.superficie_total_construida_m2 === "number") {
      return u.superficie_total_construida_m2;
    }
    // Proyecto analizado desde DXF (sin solar declarado): no hay dato de
    // urbanismo -- se aproxima sumando la superficie de las viviendas ya
    // presentes, el mismo dato que ya se muestra en otras partes de la UI.
    var viviendas = (state.data && state.data.viviendas) || [];
    if (!viviendas.length) return null;
    return viviendas.reduce(function (sum, v) { return sum + (v.superficie_total_m2 || 0); }, 0);
  }

  // Suma de `superficie_util_m2` (dato real DB-SI, ver `api_serializer.py`)
  // de todas las viviendas -- para el Ratio de Eficiencia de Superficie del
  // bloque "Análisis Avanzado" (docs/prd/2026-08-17-analisis-de-viabilidad-
  // financiera.md). A diferencia de `superficieConstruidaTotal()`, no tiene
  // fallback de urbanismo: la superficie útil solo existe por vivienda ya
  // analizada/generada, nunca a nivel de solar.
  function superficieUtilTotal() {
    var viviendas = (state.data && state.data.viviendas) || [];
    if (!viviendas.length) return null;
    var conocida = viviendas.filter(function (v) { return typeof v.superficie_util_m2 === "number"; });
    if (!conocida.length) return null;
    return conocida.reduce(function (sum, v) { return sum + v.superficie_util_m2; }, 0);
  }

  function numeroOVacio(texto) {
    if (texto === "" || texto == null) return null;
    var n = Number(String(texto).replace(",", "."));
    return isFinite(n) ? n : null;
  }

  function formatoM2(n) {
    return n == null ? "--" : n.toLocaleString("es-ES", { maximumFractionDigits: 0 }) + " m²";
  }

  function formatoEuros(n) {
    return n == null ? "--" : n.toLocaleString("es-ES", { maximumFractionDigits: 0 }) + " €";
  }

  function formatoPct(n, decimales) {
    return n == null ? "--" : n.toLocaleString("es-ES", { maximumFractionDigits: decimales == null ? 1 : decimales }) + "%";
  }

  function campoViabilidad(campo, etiqueta, valor) {
    return (
      '<label class="viabilidad-campo">' +
        '<span>' + etiqueta + '</span>' +
        '<input type="text" inputmode="decimal" data-viabilidad-campo="' + campo + '" value="' +
          (valor == null ? "" : String(valor).replace(/"/g, "&quot;")) + '">' +
      "</label>"
    );
  }

  function filaResultado(etiqueta, valor) {
    return (
      '<div class="viabilidad-resultado-fila">' +
        '<span>' + etiqueta + '</span>' +
        '<strong>' + valor + '</strong>' +
      "</div>"
    );
  }

  function calcularResultadosViabilidad() {
    var v = state.viabilidad || {};
    var superficie = superficieConstruidaTotal();
    var ratio = numeroOVacio(v.ratioM2);
    var costeSuelo = numeroOVacio(v.costeSuelo);
    var precioVenta = numeroOVacio(v.precioVenta);

    var pem = (superficie != null && ratio != null) ? superficie * ratio : null;
    var repercusionSuelo = (costeSuelo != null && superficie) ? costeSuelo / superficie : null;
    var margenBruto = (precioVenta != null && pem != null && costeSuelo != null)
      ? precioVenta - pem - costeSuelo
      : null;

    return { superficie: superficie, pem: pem, repercusionSuelo: repercusionSuelo, margenBruto: margenBruto };
  }

  function viabilidadResultadosHtml() {
    var r = calcularResultadosViabilidad();
    return (
      '<div class="viabilidad-resultados">' +
        filaResultado("PEM orientativo", formatoEuros(r.pem)) +
        filaResultado("Repercusión de suelo (€/m²)", r.repercusionSuelo == null ? "--" : formatoEuros(r.repercusionSuelo)) +
        filaResultado("Margen bruto orientativo", formatoEuros(r.margenBruto)) +
      "</div>"
    );
  }

  // --- "Análisis Avanzado" (docs/prd/2026-08-17-analisis-de-viabilidad-
  // financiera.md, aprobado 2026-08-17 con alcance recortado: SIN TIR) -----
  //
  // Bloque plegable dentro de la misma pestaña de Viabilidad Económica, no
  // una pestaña nueva (decisión de Pablo al aprobar el PRD). A diferencia
  // del resto del panel, estos 3 resultados (Margen Promotor, Cash Flow,
  // sensibilidad) se calculan en el SERVIDOR (`/api/viabilidad-financiera`,
  // `analyzer/feasibility.py`) en vez de en JS -- es la misma fórmula que
  // usará `analyzer/dossier_pdf.py` para el Dossier de Inversión, y quien
  // calcula debe ser una única fuente para que el PDF nunca pueda mostrar
  // un número distinto al que el usuario ya vio aquí. El Ratio de
  // Eficiencia de Superficie viaja en la misma llamada aunque no dependa de
  // ningún coste -- es el único resultado de este bloque que es un dato
  // REAL (no estimación), así que se pinta sin badge de "estimación tuya".

  var _analisisAvanzadoTimer = null;

  function campoAnalisisAvanzado(campo, etiqueta, valor) {
    return (
      '<label class="viabilidad-campo">' +
        '<span>' + etiqueta + '</span>' +
        '<input type="text" inputmode="decimal" data-viabilidad-campo="' + campo + '" value="' +
          (valor == null ? "" : String(valor).replace(/"/g, "&quot;")) + '">' +
      "</label>"
    );
  }

  function analisisAvanzadoResultadosHtml() {
    var a = state.analisisAvanzado;
    if (!a || a.cargando) {
      return '<p class="viabilidad-avanzado-estado">Introduce al menos el ratio de coste de construcción para calcular.</p>';
    }
    if (a.error) {
      return '<p class="viabilidad-avanzado-estado">No se pudo calcular: ' + a.error + '</p>';
    }
    var r = a.resultado;
    var filasCashFlow = (r.cash_flow || []).map(function (f) {
      return filaResultado(f.concepto, formatoEuros(f.importe));
    }).join("");
    var filasSensibilidad = (r.sensibilidad || []).map(function (e) {
      var etiqueta = e.variacion_coste_pct === 0
        ? "Coste base"
        : (e.variacion_coste_pct > 0 ? "+" : "") + e.variacion_coste_pct + "% coste construcción";
      return filaResultado(etiqueta, formatoPct(e.margen_pct));
    }).join("");

    return (
      '<div class="viabilidad-resultados">' +
        filaResultado(
          "Ratio de eficiencia (útil / construida)",
          r.ratio_eficiencia_superficie == null ? "--" : formatoPct(r.ratio_eficiencia_superficie * 100, 0)
        ) +
        filaResultado("Margen Promotor (%)", formatoPct(r.margen_promotor.margen_pct)) +
        filaResultado("Margen Promotor (€)", formatoEuros(r.margen_promotor.margen_eur)) +
      "</div>" +
      (filasCashFlow
        ? '<div class="viabilidad-resultados viabilidad-cash-flow"><h4>Cash Flow estático</h4>' + filasCashFlow + "</div>"
        : "") +
      (filasSensibilidad
        ? '<div class="viabilidad-resultados viabilidad-sensibilidad"><h4>Sensibilidad al coste de construcción</h4>' + filasSensibilidad + "</div>"
        : "")
    );
  }

  function analisisAvanzadoHtml() {
    var v = state.viabilidad || {};
    return (
      '<details class="viabilidad-avanzado">' +
        '<summary>Análisis Avanzado</summary>' +
        '<p class="viabilidad-badge">Margen Promotor y Cash Flow: estimación tuya. Ratio de eficiencia: dato real.</p>' +
        '<div class="viabilidad-campos">' +
          campoAnalisisAvanzado("costesIndirectosPct", "Costes indirectos (% del PEM)", v.costesIndirectosPct) +
          campoAnalisisAvanzado("licenciasPct", "Licencias (% del PEM)", v.licenciasPct) +
          campoAnalisisAvanzado("honorariosPct", "Honorarios técnicos (% del PEM)", v.honorariosPct) +
          campoAnalisisAvanzado("costeFinancieroPct", "Coste financiero (% del PEM)", v.costeFinancieroPct) +
        "</div>" +
        '<div id="viabilidad-avanzado-resultados">' + analisisAvanzadoResultadosHtml() + "</div>" +
      "</details>"
    );
  }

  function actualizarAnalisisAvanzadoResultados() {
    var cont = document.getElementById("viabilidad-avanzado-resultados");
    if (cont) cont.innerHTML = analisisAvanzadoResultadosHtml();
  }

  function solicitarAnalisisAvanzado() {
    var r = calcularResultadosViabilidad();
    var v = state.viabilidad || {};
    // Sin PEM (superficie o ratio aún sin introducir) no hay nada que
    // calcular -- se queda en el estado inicial en vez de lanzar una
    // petición que solo devolvería `None` en todo.
    if (r.pem == null) {
      state.analisisAvanzado = null;
      actualizarAnalisisAvanzadoResultados();
      return;
    }
    state.analisisAvanzado = { cargando: true };
    var payload = {
      pem: r.pem,
      costeSuelo: numeroOVacio(v.costeSuelo),
      precioVenta: numeroOVacio(v.precioVenta),
      costesIndirectosPct: numeroOVacio(v.costesIndirectosPct),
      licenciasPct: numeroOVacio(v.licenciasPct),
      honorariosPct: numeroOVacio(v.honorariosPct),
      costeFinancieroPct: numeroOVacio(v.costeFinancieroPct),
      superficieUtilM2: superficieUtilTotal(),
      superficieConstruidaM2: superficieConstruidaTotal(),
    };
    fetch("/api/viabilidad-financiera", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (resp) { return resp.json(); })
      .then(function (resultado) {
        state.analisisAvanzado = { resultado: resultado };
        actualizarAnalisisAvanzadoResultados();
      })
      .catch(function () {
        state.analisisAvanzado = { error: "fallo de red." };
        actualizarAnalisisAvanzadoResultados();
      });
  }

  function programarAnalisisAvanzado() {
    if (_analisisAvanzadoTimer) clearTimeout(_analisisAvanzadoTimer);
    _analisisAvanzadoTimer = setTimeout(solicitarAnalisisAvanzado, 400);
  }

  function viabilidadEconomicaHtml() {
    var v = state.viabilidad || {};
    var superficie = superficieConstruidaTotal();
    var vivienda = viviendaActual();

    return (
      '<section class="viabilidad-seccion">' +
        '<h3>Viabilidad económica</h3>' +
        '<p class="viabilidad-badge">Estimación tuya, no un dato de mercado de ArchMuse</p>' +
        '<div class="viabilidad-campo-solo-lectura">' +
          '<span>Superficie construida total</span><strong>' + formatoM2(superficie) + '</strong>' +
        "</div>" +
        '<div class="viabilidad-campos">' +
          campoViabilidad("ratioM2", "Ratio de coste de construcción (€/m²)", v.ratioM2) +
          campoViabilidad("costeSuelo", "Coste de suelo estimado (€)", v.costeSuelo) +
          campoViabilidad("precioVenta", "Precio de venta estimado (€)", v.precioVenta) +
        "</div>" +
        viabilidadResultadosHtml() +
        analisisAvanzadoHtml() +
      "</section>" +
      '<section class="viabilidad-seccion">' +
        '<h3>Exportación</h3>' +
        (vivienda
          ? (
            '<p>Descarga los contornos de la planta activa ("' + (vivienda.nombre || vivienda.id || "planta") +
              '") en un archivo DXF -- polilíneas de habitación por capa, listas para abrir en cualquier CAD. ' +
              'No incluye muros, puertas ni huecos: solo el contorno de cada estancia, que es el único dato que ArchMuse guarda.</p>' +
            '<button type="button" id="btn-viabilidad-descargar-dxf" class="viabilidad-btn-exportar">Descargar DXF / CAD</button>' +
            '<p class="viabilidad-badge" style="display:block;margin-top:var(--space-4)">Exportación BIM: solo espacios, sin muros ni puertas ficticios</p>' +
            '<p>Exporta las mismas estancias como <code>IfcSpace</code> (IFC4) -- superficie y nombre reales, ' +
              'sin muros, puertas ni ventanas: ArchMuse no tiene esa geometría en ningún proyecto, y un IFC con ' +
              'esos elementos inventados podría confundirse con datos reales en Revit/ArchiCAD/Solibri.</p>' +
            '<button type="button" id="btn-viabilidad-descargar-ifc" class="viabilidad-btn-exportar">Exportar Espacios BIM (.IFC)</button>' +
            '<div class="viabilidad-dossier">' +
              '<h4>Dossier de Inversión (PDF)</h4>' +
              '<p>Portada con mapa de ubicación (y render 3D si tienes el visor 3D abierto en esta sesión), ' +
                'ficha técnica urbanística, planos de distribución y el cuadro de viabilidad de arriba.</p>' +
              '<div class="viabilidad-campos">' +
                '<label class="viabilidad-campo"><span>Nombre de la promotora/estudio (opcional)</span>' +
                  '<input type="text" id="dossier-nombre-promotora"></label>' +
                '<label class="viabilidad-campo"><span>Logotipo (opcional, PNG/JPG)</span>' +
                  '<input type="file" id="dossier-logo" accept="image/png,image/jpeg"></label>' +
              "</div>" +
              '<button type="button" id="btn-viabilidad-descargar-dossier" class="viabilidad-btn-exportar">Generar Dossier de Inversión</button>' +
            "</div>"
          )
          : '<p>Selecciona primero una vivienda en el visor para poder exportar su planta a DXF.</p>'
        ) +
      "</section>"
    );
  }

  function renderViabilidadEconomica() {
    var cont = document.getElementById("viabilidad-economica-contenido");
    if (cont) cont.innerHTML = viabilidadEconomicaHtml();
  }

  function actualizarResultadosViabilidad() {
    var cont = document.getElementById("viabilidad-economica-contenido");
    var bloque = cont && cont.querySelector(".viabilidad-resultados");
    if (bloque) bloque.outerHTML = viabilidadResultadosHtml();
  }

  function abrirViabilidadEconomica() {
    state.viabilidad = {
      ratioM2: "", costeSuelo: "", precioVenta: "",
      costesIndirectosPct: "", licenciasPct: "", honorariosPct: "", costeFinancieroPct: "",
    };
    state.analisisAvanzado = null;
    renderViabilidadEconomica();
    var overlay = document.getElementById("viabilidad-economica");
    if (overlay) overlay.classList.add("open");
  }

  function cerrarViabilidadEconomica() {
    var overlay = document.getElementById("viabilidad-economica");
    if (overlay) overlay.classList.remove("open");
  }

  function descargarDxfPlantaActiva() {
    var vivienda = viviendaActual();
    if (!vivienda) return;
    var habitaciones = (vivienda.habitaciones || []).map(function (h) {
      return { nombre: h.nombre, poligono: h.poligono };
    });
    fetch("/api/exportar-dxf-planta", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre_vivienda: vivienda.nombre || vivienda.id, habitaciones: habitaciones })
    })
      .then(function (resp) {
        if (!resp.ok) return resp.json().then(function (j) { throw new Error(j.error || "Error al exportar."); });
        return resp.blob();
      })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = (vivienda.nombre || vivienda.id || "planta") + "_ArchMuse_contornos.dxf";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      })
      .catch(function (err) {
        alert(err.message || "No se pudo exportar el DXF.");
      });
  }

  // "Exportar Espacios BIM (.IFC)" (docs/prd/2026-08-17-exportacion-bim-
  // ifc.md, aprobado 2026-08-17 -- opción A de §14: SOLO IfcSpace, nunca
  // muros/puertas ficticios). Mismo patrón que `descargarDxfPlantaActiva`,
  // con `area_m2`/`tipo` añadidos al payload -- son los únicos datos extra
  // que el IfcSpace necesita (superficie real y uso real, ya calculados).
  function descargarIfcPlantaActiva() {
    var vivienda = viviendaActual();
    if (!vivienda) return;
    var habitaciones = (vivienda.habitaciones || []).map(function (h) {
      return { nombre: h.nombre, poligono: h.poligono, area_m2: h.area_m2, tipo: h.tipo };
    });
    fetch("/api/exportar-ifc-planta", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre_vivienda: vivienda.nombre || vivienda.id, habitaciones: habitaciones })
    })
      .then(function (resp) {
        if (!resp.ok) return resp.json().then(function (j) { throw new Error(j.error || "Error al exportar."); });
        return resp.blob();
      })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = (vivienda.nombre || vivienda.id || "planta") + "_ArchMuse_espacios.ifc";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      })
      .catch(function (err) {
        alert(err.message || "No se pudo exportar el IFC.");
      });
  }

  // "Generar Dossier de Inversión" (docs/prd/2026-08-17-dossier-inversion-pdf.md, aprobado
  // 2026-08-17). Reúne datos que YA existen en `state` -- nada se recalcula aquí, el PDF muestra
  // exactamente lo mismo que ya ve el usuario en esta pestaña. El render 3D es opcional y best-
  // effort (`window.ArchmuseViewer3D.capturarImagen()`, `null` si el visor 3D no está abierto en
  // esta sesión); el logo, si se adjunta, se lee como base64 en el propio navegador (nunca se sube a
  // ningún sitio salvo al propio endpoint del dossier).
  function leerArchivoComoBase64(file) {
    return new Promise(function (resolve) {
      if (!file) { resolve(null); return; }
      var reader = new FileReader();
      reader.onload = function () { resolve(reader.result); };
      reader.onerror = function () { resolve(null); };
      reader.readAsDataURL(file);
    });
  }

  function descargarDossierPdf() {
    var boton = document.getElementById("btn-viabilidad-descargar-dossier");
    var inputLogo = document.getElementById("dossier-logo");
    var inputPromotora = document.getElementById("dossier-nombre-promotora");
    var archivoLogo = inputLogo && inputLogo.files && inputLogo.files[0];

    if (boton) { boton.disabled = true; boton.textContent = "Generando…"; }

    leerArchivoComoBase64(archivoLogo).then(function (logoBase64) {
      var r = calcularResultadosViabilidad();
      var v = state.viabilidad || {};
      var avanzado = state.analisisAvanzado && state.analisisAvanzado.resultado;
      var solidoCapaz = (state.data && state.data.solido_capaz) || null;
      var urbanismo = (state.data && state.data.urbanismo) || {};
      var viviendas = ((state.data && state.data.viviendas) || []).map(function (viv) {
        return {
          nombre: viv.nombre || viv.id,
          habitaciones: (viv.habitaciones || []).map(function (h) {
            return { nombre: h.nombre, poligono: h.poligono };
          })
        };
      });

      var cuerpo = {
        proyecto_id: (state.data && state.data.proyecto_id) || null,
        nombre_proyecto: (state.data && (state.data.nombre || state.data.filename)) || "Proyecto ArchMuse",
        nombre_promotora: (inputPromotora && inputPromotora.value.trim()) || null,
        logo_base64: logoBase64,
        ubicacion: solidoCapaz && solidoCapaz.origen_lat != null
          ? { lat: solidoCapaz.origen_lat, lon: solidoCapaz.origen_lon } : null,
        solido_capaz: solidoCapaz,
        superficie_solar_m2: urbanismo.superficie_solar_m2 || null,
        superficie_total_construida_m2: r.superficie,
        viviendas: viviendas,
        render_3d_base64: (window.ArchmuseViewer3D && window.ArchmuseViewer3D.capturarImagen)
          ? window.ArchmuseViewer3D.capturarImagen() : null,
        viabilidad: (r.pem == null && numeroOVacio(v.ratioM2) == null) ? null : {
          superficie: r.superficie, ratioM2: numeroOVacio(v.ratioM2), costeSuelo: numeroOVacio(v.costeSuelo),
          precioVenta: numeroOVacio(v.precioVenta), pem: r.pem, repercusionSuelo: r.repercusionSuelo,
          margenBruto: r.margenBruto,
          margenPromotorPct: avanzado ? avanzado.margen_promotor.margen_pct : null,
          ratioEficienciaSuperficie: avanzado ? avanzado.ratio_eficiencia_superficie : null
        }
      };

      return fetch("/api/dossier-pdf", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo)
      });
    }).then(function (resp) {
      if (!resp.ok) return resp.json().then(function (j) { throw new Error(j.error || "Error al generar el dossier."); });
      return resp.blob();
    }).then(function (blob) {
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "Dossier_ArchMuse.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }).catch(function (err) {
      alert(err.message || "No se pudo generar el dossier.");
    }).then(function () {
      if (boton) { boton.disabled = false; boton.textContent = "Generar Dossier de Inversión"; }
    });
  }

  function wireViabilidadEconomica() {
    var cerrar = document.getElementById("btn-viabilidad-economica-cerrar");
    if (cerrar) cerrar.addEventListener("click", cerrarViabilidadEconomica);

    var cont = document.getElementById("viabilidad-economica-contenido");
    if (!cont) return;
    cont.addEventListener("input", function (e) {
      var campo = e.target.closest("[data-viabilidad-campo]");
      if (!campo) return;
      state.viabilidad = state.viabilidad || {};
      state.viabilidad[campo.dataset.viabilidadCampo] = campo.value;
      actualizarResultadosViabilidad();
      programarAnalisisAvanzado();
    });
    cont.addEventListener("click", function (e) {
      if (e.target.closest("#btn-viabilidad-descargar-dxf")) descargarDxfPlantaActiva();
      if (e.target.closest("#btn-viabilidad-descargar-ifc")) descargarIfcPlantaActiva();
      if (e.target.closest("#btn-viabilidad-descargar-dossier")) descargarDossierPdf();
    });
  }

  // --- Checklist de Cumplimiento CTE (docs/prd/2026-08-17-checklist-
  // cumplimiento-cte.md, aprobado 2026-08-17) -------------------------------
  //
  // Mismo patrón de overlay que Viabilidad Económica. El checklist en sí
  // (`checklist_cte`) ya llega calculado por vivienda en `state.data` --
  // este panel solo pinta lo que el backend ya decidió (`analyzer/
  // cte_checker.py`), nunca recalcula un estado verde/rojo aquí. La ÚNICA
  // interacción del cliente es la casilla "el edificio tiene dos salidas
  // de evacuación": una afirmación del propio usuario que SOLO cambia qué
  // umbral (25/50 m) se muestra en el texto informativo de evacuación --
  // nunca cambia su estado, que sigue siendo "no evaluable" siempre (ver
  // docstring de `cte_checker._item_evacuacion`: ArchMuse no puede emitir
  // ese veredicto con los datos que tiene, con o sin la casilla marcada).

  var ESTADO_CTE_ETIQUETA = { cumple: "Cumple", no_cumple: "No cumple", no_evaluable: "No evaluable" };

  function textoEvacuacionConUmbral(item, dosSalidas) {
    if (!item.datos) return item.detalle;
    var umbral = dosSalidas ? item.datos.umbral_2_salidas_m : item.datos.umbral_1_salida_m;
    var salidasTxt = dosSalidas ? "dos salidas (confirmado por el usuario)" : "una única salida";
    return (
      "No evaluable contra la norma real: recorrido interior más largo hasta la puerta de la " +
      "vivienda " + item.datos.distancia_m + " m (pieza '" + item.datos.pieza + "'). El umbral del " +
      "DB-SI para " + salidasTxt + " sería " + umbral + " m, pero ese límite se mide hasta la salida " +
      "del EDIFICIO (con la ocupación real y la geometría de portal/escalera), datos que ArchMuse no " +
      "tiene. La cifra mostrada es solo el recorrido interior, no un veredicto de cumplimiento."
    );
  }

  function checklistCteItemHtml(item, dosSalidas) {
    var detalle = item.titulo === "Distancia de evacuación" ? textoEvacuacionConUmbral(item, dosSalidas) : item.detalle;
    return (
      '<li class="checklist-cte-item checklist-cte-item--' + item.estado + '">' +
        '<div class="checklist-cte-item-cabecera">' +
          '<span class="checklist-cte-indicador" aria-hidden="true"></span>' +
          '<strong>' + item.titulo + '</strong>' +
          '<span class="checklist-cte-estado">' + (ESTADO_CTE_ETIQUETA[item.estado] || item.estado) + '</span>' +
        "</div>" +
        '<p class="checklist-cte-item-detalle">' + detalle + '</p>' +
        '<p class="checklist-cte-item-referencia">' + item.referencia + '</p>' +
      "</li>"
    );
  }

  function checklistCteHtml() {
    var vivienda = viviendaActual();
    if (!vivienda) {
      return '<p class="checklist-campo-estado">Selecciona primero una vivienda en el visor.</p>';
    }
    var items = vivienda.checklist_cte || [];
    if (!items.length) {
      return '<p class="checklist-campo-estado">Esta vivienda no tiene checklist CTE calculado.</p>';
    }
    var dosSalidas = !!state.checklistCteDosSalidas;
    return (
      '<label class="checklist-cte-dos-salidas">' +
        '<input type="checkbox" id="checklist-cte-dos-salidas"' + (dosSalidas ? " checked" : "") + '>' +
        '<span>Confirmo que el edificio tiene dos salidas de evacuación independientes ' +
          '(afirmación tuya, ArchMuse no lo comprueba)</span>' +
      "</label>" +
      '<ul class="checklist-cte-items">' +
        items.map(function (it) { return checklistCteItemHtml(it, dosSalidas); }).join("") +
      "</ul>"
    );
  }

  function renderChecklistCte() {
    var cont = document.getElementById("checklist-cte-contenido");
    if (cont) cont.innerHTML = checklistCteHtml();
  }

  function abrirChecklistCte() {
    state.checklistCteDosSalidas = false;
    renderChecklistCte();
    var overlay = document.getElementById("checklist-cte");
    if (overlay) overlay.classList.add("open");
  }

  function cerrarChecklistCte() {
    var overlay = document.getElementById("checklist-cte");
    if (overlay) overlay.classList.remove("open");
  }

  function wireChecklistCte() {
    var cerrar = document.getElementById("btn-checklist-cte-cerrar");
    if (cerrar) cerrar.addEventListener("click", cerrarChecklistCte);

    var cont = document.getElementById("checklist-cte-contenido");
    if (!cont) return;
    cont.addEventListener("change", function (e) {
      if (e.target.id !== "checklist-cte-dos-salidas") return;
      state.checklistCteDosSalidas = e.target.checked;
      renderChecklistCte();
    });
  }

  // --- Modo "Concurso": verificador de cumplimiento de pliego --------------
  //
  // A nivel de proyecto completo (no por vivienda, a diferencia del resto de
  // modos) -- `analyzer.pliego_verificador`, 100% determinista, sin IA.
  // Compara el proyecto abierto contra CUALQUIER pliego ya importado, sin
  // que el proyecto se haya generado a partir de él (el conector que haría
  // eso automático es un PRD aparte, sin aprobar).

  function cargarPliegosDisponibles() {
    state.pliegosDisponibles = []; // evita relanzar la petición en cada repintado mientras llega
    fetch("/api/pliegos")
      .then(function (resp) { return resp.json(); })
      .then(function (json) {
        state.pliegosDisponibles = json.pliegos || [];
        if (state.modo === "concurso") renderInspector();
      })
      .catch(function () {
        state.pliegosDisponibles = [];
        if (state.modo === "concurso") renderInspector();
      });
  }

  // Mismo cuidado de carrera que `generarDiagnosticoIA`: `proyectoId` se
  // captura al lanzar la petición y se revalida al recibir la respuesta.
  function ejecutarVerificacionPliego(pliegoId) {
    if (!state.data || !state.data.proyecto_id || !pliegoId) return;
    var proyectoId = state.data.proyecto_id;
    state.verificacionPliego = "cargando";
    renderInspector();

    fetch("/api/proyectos/" + encodeURIComponent(proyectoId) + "/verificar-pliego/" + encodeURIComponent(pliegoId))
      .then(function (resp) {
        return resp.json().then(function (json) { return { ok: resp.ok, json: json }; });
      })
      .then(function (result) {
        if (!state.data || state.data.proyecto_id !== proyectoId) return;
        if (!result.ok) {
          state.verificacionPliego = { pliegoId: pliegoId, error: result.json.error || "No se pudo verificar el proyecto." };
          renderInspector();
          return;
        }
        state.verificacionPliego = { pliegoId: pliegoId, resultado: result.json.verificacion };
        renderInspector();
      })
      .catch(function () {
        if (!state.data || state.data.proyecto_id !== proyectoId) return;
        state.verificacionPliego = { pliegoId: pliegoId, error: "Error de red al verificar el proyecto." };
        renderInspector();
      });
  }

  var CUMPLE_COLOR = { true: "#16a34a", false: "#dc2626" }; // false de verdad; "no verificable" (null) usa gris aparte

  function checkCumplimientoHtml(c) {
    var color = c.cumple === true ? CUMPLE_COLOR.true : c.cumple === false ? CUMPLE_COLOR.false : "#9ca3af";
    var etiqueta = c.cumple === true ? "Cumple" : c.cumple === false ? "No cumple" : "No verificable";
    var cifras = c.valor_exigido != null || c.valor_proyecto != null
      ? '<div class="muted">Exigido: ' + escapeHtml(JSON.stringify(c.valor_exigido)) +
        " · Proyecto: " + escapeHtml(JSON.stringify(c.valor_proyecto)) + "</div>"
      : "";
    return '<div class="detail-block" style="border-left:3px solid ' + color + ';padding-left:var(--space-2)">' +
      '<div class="detail-block-value"><strong>' + escapeHtml(c.parametro) + "</strong> — " + etiqueta + "</div>" +
      cifras +
      (c.motivo ? '<div class="muted">' + escapeHtml(c.motivo) + "</div>" : "") +
      "</div>";
  }

  function modoConcursoHtml(v) {
    var html = '<div class="inspector-label">Concurso</div>';
    if (!state.data || !state.data.proyecto_id) {
      return html + '<p class="inspector-empty">Este proyecto todavía no está guardado — vuelve a analizarlo o generarlo primero.</p>';
    }
    if (state.pliegosDisponibles === null) {
      cargarPliegosDisponibles();
      return html + '<p class="muted">Cargando pliegos disponibles…</p>';
    }
    if (!state.pliegosDisponibles.length) {
      return html + '<p class="inspector-empty">No tienes ningún pliego importado todavía. Impórtalo desde "Generar proyecto".</p>';
    }

    html += '<div class="form-field"><label for="concurso-pliego-select">Verificar contra</label><select id="concurso-pliego-select">' +
      '<option value="">Elige un pliego…</option>' +
      state.pliegosDisponibles.map(function (p) {
        var sel = state.verificacionPliego && state.verificacionPliego.pliegoId === p.id ? " selected" : "";
        return '<option value="' + p.id + '"' + sel + ">" + escapeHtml(p.nombre_archivo) + "</option>";
      }).join("") +
      "</select></div>";

    var vp = state.verificacionPliego;
    if (vp === "cargando") return html + '<p class="muted">Verificando…</p>';
    if (vp && vp.error) return html + '<p class="cuadro-conflicto">' + escapeHtml(vp.error) + "</p>";
    if (!vp || !vp.resultado) return html;

    var r = vp.resultado;
    html += '<p class="detail-block-value" style="margin: var(--space-3) 0">' + escapeHtml(r.resumen_ejecutivo) + "</p>";
    if (r.score_cumplimiento != null) {
      html += detailBlock("Puntuación de cumplimiento", r.score_cumplimiento + " / 100");
    }
    if (r.blockers && r.blockers.length) {
      html += '<div class="detail-block-label" style="color:#dc2626">Bloqueadores — excluirían del concurso</div>' +
        r.blockers.map(checkCumplimientoHtml).join("");
    }
    html += '<div class="detail-block-label" style="margin-top: var(--space-4)">Todas las comprobaciones</div>' +
      r.checks.map(checkCumplimientoHtml).join("");
    return html;
  }

  function cargarCuadroTabla() {
    if (!state.archivoAnalizado || state.cuadroTabla) return;
    state.cuadroTabla = {
      celdas: [], solicitudes: [], cargando: true, error: null,
      respuestasAplicadas: [], valores: {}, asignaciones: {}, pendientes: {},
    };

    var formData = new FormData();
    formData.append("dxf", state.archivoAnalizado);
    fetch("/api/cuadro-superficies/estado", { method: "POST", body: formData })
      .then(function (resp) {
        if (!resp.ok) {
          return resp.json().then(function (j) { throw new Error(j.error || "No se pudo leer el cuadro de superficies."); });
        }
        return resp.json();
      })
      .then(function (payload) {
        state.cuadroTabla = {
          celdas: payload.celdas || [], solicitudes: payload.solicitudes || [],
          cargando: false, error: null, respuestasAplicadas: [],
          valores: {}, asignaciones: {}, pendientes: {},
        };
        refrescarVistaCuadro();
      })
      .catch(function (err) {
        state.cuadroTabla = {
          celdas: [], solicitudes: [], cargando: false, respuestasAplicadas: [],
          valores: {}, asignaciones: {}, pendientes: {},
          error: (err && err.message) || "No se pudo leer el cuadro de superficies.",
        };
        refrescarVistaCuadro();
      });
  }

  // ---------------------------------------------------------------------
  // Bloque de ámbito EDIFICIO: `altura_evacuacion` + `avisos_evacuacion`
  // (CAP-5). Vive fuera del inspector por-vivienda (mismo motivo que
  // `diagCapasEntradaProyectoHtml`, más abajo): la altura de evacuación es
  // del edificio entero, no de una vivienda -- ponerla junto a los datos
  // de vivienda sugeriría, falso, que cada una tiene la suya.
  // ---------------------------------------------------------------------

  function hechosEdificioEntradaProyectoHtml() {
    var proyecto = (state.data && state.data.proyecto) || {};
    if (!proyecto.altura_evacuacion) return "";
    return '<button type="button" class="btn-reveal diag-capas-entrada-proyecto" ' +
      'id="btn-hechos-edificio-proyecto">Hechos del edificio</button>';
  }

  // Los avisos de C11/C15/C18 NO son incidencias -- el propio backend los
  // marca `es_aviso: true` (`app.py::_serializar_avisos_evacuacion`) para
  // que ningún consumidor los confunda con un FAIL. Por eso este renderer
  // es propio, deliberadamente sin `severity` ni las tintas de
  // `.problems-counter`/`.issue-titulo`, y `buildUnifiedProblems` (más
  // abajo) no lo toca.
  function avisosEvacuacionListHtml(avisos) {
    if (!avisos || !avisos.length) return "";
    return '<div class="inspector-label">Avisos informativos</div>' +
      '<ul class="aviso-evacuacion-list">' + avisos.map(function (a) {
        return '<li class="aviso-evacuacion-item">' +
          '<span class="aviso-evacuacion-badge">' + escapeHtml(a.regla || a.codigo || "") + "</span>" +
          '<span class="aviso-evacuacion-mensaje">' + escapeHtml(a.mensaje) + "</span>" +
          (a.localizador ? '<span class="aviso-evacuacion-meta">' + escapeHtml(a.localizador) + "</span>" : "") +
          "</li>";
      }).join("") + "</ul>";
  }

  function hechosEdificioHtml() {
    var proyecto = (state.data && state.data.proyecto) || {};
    var h = proyecto.altura_evacuacion;
    if (!h) return '<p class="inspector-empty">Este análisis no publica hechos de edificio.</p>';

    var valor = h.estado !== "UNKNOWN" && h.altura_m != null ? h.altura_m.toFixed(2) + " m" : "";
    return hechoBlockHtml("Altura de evacuación", h, valor) +
      avisosEvacuacionListHtml(proyecto.avisos_evacuacion);
  }

  function toolProblemasHtml(v) {
    var merged = state.problemas;
    if (!merged.length) return '<div class="inspector-label">Problemas</div>' +
      '<p class="inspector-empty">Sin incidencias detectadas.</p>';

    var visibles = merged.filter(function (it) {
      return state.filtros.severidades[it.severity] && state.filtros.disciplinas[it.disciplina];
    });
    var counts = { CRITICO: 0, IMPORTANTE: 0, RECOMENDACION: 0 };
    merged.forEach(function (it) { counts[it.severity] = (counts[it.severity] || 0) + 1; });

    return '<div class="inspector-label">Problemas (' + merged.length + ")</div>" +
      '<div class="problems-counter">' +
      '<span class="count-critico">' + counts.CRITICO + " críticos</span>" +
      '<span class="count-sep">·</span>' +
      '<span class="count-importante">' + counts.IMPORTANTE + " importantes</span>" +
      '<span class="count-sep">·</span>' +
      '<span class="count-recomendacion">' + counts.RECOMENDACION + " rec</span>" +
      "</div>" +
      '<button type="button" id="btn-toggle-filtros" class="btn-toggle-filtros" aria-expanded="' +
      (state.filtrosAbiertos ? "true" : "false") + '">' +
      (state.filtrosAbiertos ? "Ocultar filtros" : "Filtrar") + "</button>" +
      filtrosHtml(merged) +
      (visibles.length
        ? listaProblemasHtml(visibles)
        : '<p class="inspector-empty">Ningún problema coincide con los filtros activos.</p>') +
      planAccionHtml(v);
  }

  function filtrosHtml(merged) {
    var sev = { CRITICO: 0, IMPORTANTE: 0, RECOMENDACION: 0 };
    var disc = {};
    DISCIPLINAS.forEach(function (d) { disc[d] = 0; });
    merged.forEach(function (it) {
      sev[it.severity] = (sev[it.severity] || 0) + 1;
      disc[it.disciplina] = (disc[it.disciplina] || 0) + 1;
    });
    var chip = function (tipo, valor, label, count, activo) {
      return '<button type="button" class="filter-chip' + (activo ? " active" : "") +
        '" data-tipo="' + tipo + '" data-valor="' + escapeHtml(valor) + '">' +
        escapeHtml(label) + ' <span class="filter-chip-count">' + count + "</span></button>";
    };
    return '<div class="problems-filters" id="problems-filters"' + (state.filtrosAbiertos ? "" : " hidden") + ">" +
      '<div class="filter-row">' +
      ISSUE_SEVERITY_ORDER.map(function (s) {
        return chip("severidad", s, ISSUE_SEVERITY_LABEL[s], sev[s] || 0, state.filtros.severidades[s]);
      }).join("") +
      "</div>" +
      '<div class="filter-row">' +
      DISCIPLINAS.map(function (d) {
        return chip("disciplina", d, d, disc[d] || 0, state.filtros.disciplinas[d]);
      }).join("") +
      "</div>" +
      '<button type="button" id="btn-reset-filtros" class="btn-reset-filtros">Resetear filtros</button>' +
      "</div>";
  }

  // El plan de acción vive dentro de la herramienta "Problemas", no como
  // sección propia. Se eliminó el percentil comparativo que lo acompañaba:
  // salía de una tabla de referencia inventada (`scoring.TIPOLOGIA_BENCHMARKS`),
  // no de datos reales agregados, y presentarlo como percentil de mercado
  // era deshonesto — ver PROJECT_AUDIT.md y TECH_REVIEW.md.
  function planAccionHtml(v) {
    var items = (state.data.issues_por_impacto || []).filter(function (i) {
      return (i.unit_name === v.nombre || i.unit_name === "") && i.puntos_ganados > 0;
    });
    if (!items.length) return "";
    return '<div class="detail-block" style="margin-top: var(--space-6)">' +
      '<div class="detail-block-label">Mayor impacto primero</div>' +
      '<ol class="action-plan-list">' +
      items.map(function (i) {
        return '<li class="action-plan-item">' +
          '<span class="action-plan-titulo">' + escapeHtml(i.titulo) + "</span>" +
          '<span class="action-plan-pts">+' + i.puntos_ganados.toFixed(1) + "</span></li>";
      }).join("") +
      "</ol></div>";
  }

  // El modo se llama "Diagnóstico", no "IA": el arquitecto elige una lectura
  // del proyecto, no una tecnología. Por eso el texto del diagnóstico va
  // directo bajo el rótulo del modo, sin un segundo epígrafe "Diagnóstico"
  // que repitiera la misma palabra a dos líneas de distancia.
  function modoDiagnosticoHtml(v) {
    var ai = state.data.analisis_ia;
    if (!ai) {
      var estado = state.diagnosticoIaEstado;
      if (estado === "cargando") {
        return '<div class="inspector-label">Diagnóstico</div>' +
          '<p class="muted">Generando diagnóstico con IA…</p>';
      }
      return '<div class="inspector-label">Diagnóstico</div>' +
        '<p class="inspector-empty">Este proyecto no tiene diagnóstico generado.</p>' +
        (estado && estado.error ? '<p class="cuadro-conflicto">' + escapeHtml(estado.error) + "</p>" : "") +
        '<button type="button" class="btn-reveal" id="btn-generar-diagnostico-ia">Generar diagnóstico IA</button>';
    }
    var diag = ai.diagnosticos.filter(function (d) { return d.vivienda === v.nombre; })[0];
    return '<div class="inspector-label">Diagnóstico</div>' +
      (diag ? '<p class="detail-block-value" style="margin-bottom: var(--space-4)">' + escapeHtml(diag.diagnostico) + "</p>" : "") +
      ((ai.mejoras_prioritarias || []).length
        ? detailBlock("Mejoras prioritarias",
            "<ol>" + ai.mejoras_prioritarias.map(function (m) { return "<li>" + escapeHtml(m) + "</li>"; }).join("") + "</ol>")
        : "") +
      (ai.conclusion_ejecutiva ? detailBlock("Conclusión", escapeHtml(ai.conclusion_ejecutiva)) : "");
  }

  var ISSUE_SEVERITY_ORDER = ["CRITICO", "IMPORTANTE", "RECOMENDACION"];
  // Mismos hex que --color-critical/--color-important/--color-recommendation
  // del sistema de diseño (CSS) — duplicados aquí porque este valor se
  // inyecta como `style="color:...` inline en HTML generado por JS, no vía
  // clase CSS.
  var ISSUE_SEVERITY_COLOR = { CRITICO: "#dc2626", IMPORTANTE: "#d97706", RECOMENDACION: "#2e86de" };
  var ISSUE_SEVERITY_LABEL = { CRITICO: "Crítico", IMPORTANTE: "Importante", RECOMENDACION: "Recomendación" };
  var CHAIN_URGENCIA_LABEL = { INMEDIATA: "Inmediata", ANTES_OBRA: "Antes de obra", EN_PROYECTO: "En proyecto" };

  // Alias de código: la regla 3 de `chain_effects.py` ("baño sin antesala")
  // reutiliza la MISMA detección de `circulation._check_bathroom_access`
  // que ya llega aquí como problema de origen "circulacion" (mismo título
  // exacto, distinto `codigo` sintético) — sin este alias, el mismo
  // problema real se duplicaría en el panel: una vez como "circulacion" y
  // otra como "issue" (efecto en cadena).
  var CHAIN_CODIGO_ALIAS = { "HABITABILIDAD-CIRC": "CIRC-bano_sin_antesala" };

  // Clave para emparejar un `issue` (de `data.issues`, Bloque 12, o de un
  // `problema_origen` de `efectos_cadena`) con el problema ya presente en la
  // lista unificada de la misma vivienda — ambos son `IssueReport`
  // construidos por separado (no comparten identidad de objeto), así que se
  // emparejan por contenido, pasando el `codigo` por `CHAIN_CODIGO_ALIAS`.
  function issueKey(issue) {
    var codigo = CHAIN_CODIGO_ALIAS[issue.codigo] || issue.codigo;
    return codigo + "|" + issue.titulo + "|" + issue.room_label;
  }

  function chainEffectHtml(chain) {
    var items = chain.efectos_derivados.map(function (e) {
      return "<li>" + escapeHtml(e.titulo) + " (" + escapeHtml(e.normativa_relacionada) + ")</li>";
    }).join("");
    return '<div class="issue-detail-section">' +
      '<div class="issue-detail-label">Efectos derivados</div>' +
      '<ul class="chain-effects-list">' + items + "</ul>" +
      '<div class="issue-detail-value">Impacto estimado: ' + escapeHtml(chain.impacto_coste_estimado) +
      " · Urgencia: " + escapeHtml(CHAIN_URGENCIA_LABEL[chain.urgencia] || chain.urgencia) + "</div>" +
      "</div>";
  }

  // Combina las 3 fuentes de "problema" de una vivienda (`data.issues` del
  // Bloque 12, `data.calidad_espacial` de `spatial_quality.py` y
  // `data.circulacion` de `circulation.py`) en una única lista con forma
  // común — Requisitos 1 y 3. Ninguna de las tres estructuras de datos del
  // backend se toca: esto es puramente una capa de normalización en el
  // frontend para poder agrupar/filtrar/expandir todo junto.
  function buildUnifiedProblems(vivienda) {
    var items = [];

    (state.data.issues || []).forEach(function (issue) {
      if (issue.unit_name !== vivienda.nombre && issue.unit_name !== "") return;
      items.push({
        source: "issue", severity: issue.severity, codigo: issue.codigo, titulo: issue.titulo,
        descripcion: issue.descripcion, impacto: issue.impacto,
        soluciones: [issue.solucion, ALT_SOLUCION[issue.codigo] || ALT_SOLUCION_GENERICA],
        room_label: issue.room_label
      });
    });

    var calidad = (state.data.calidad_espacial || []).filter(function (c) { return c.vivienda === vivienda.nombre; })[0];
    if (calidad) {
      var spatialIssues = [];
      calidad.habitaciones.forEach(function (h) { spatialIssues = spatialIssues.concat(h.problemas); });
      spatialIssues = spatialIssues.concat(calidad.problemas_vivienda || []);
      spatialIssues.forEach(function (p) {
        items.push({
          source: "spatial_quality",
          severity: SPATIAL_SEVERITY_MAP[p.severidad] || "RECOMENDACION",
          codigo: "SPATIAL-" + p.tipo,
          titulo: SPATIAL_TITULO[p.tipo] || p.tipo,
          descripcion: p.mensaje,
          impacto: SPATIAL_IMPACTO[p.tipo] || "",
          soluciones: SPATIAL_SOLUCIONES[p.tipo] || [ALT_SOLUCION_GENERICA, ALT_SOLUCION_GENERICA],
          room_label: p.room_label || ""
        });
      });
    }

    var circ = (state.data.circulacion || []).filter(function (c) { return c.vivienda === vivienda.nombre; })[0];
    if (circ) {
      (circ.recorridos || []).forEach(function (r) {
        if (r.correcto) return;
        var recorrido = r.recorrido || [];
        items.push({
          source: "circulacion",
          severity: CIRC_SEVERITY[r.tipo] || "IMPORTANTE",
          codigo: "CIRC-" + r.tipo,
          titulo: CIRC_TITULO[r.tipo] || r.tipo,
          descripcion: r.mensaje,
          impacto: CIRC_IMPACTO[r.tipo] || "",
          soluciones: CIRC_SOLUCIONES[r.tipo] || [ALT_SOLUCION_GENERICA, ALT_SOLUCION_GENERICA],
          room_label: recorrido.length ? recorrido[recorrido.length - 1] : ""
        });
      });
    }

    // Efectos en cadena: se adjuntan a cualquier item ya presente que
    // coincida por (codigo, título, room_label); si un origen de cadena no
    // tiene equivalente en ninguna de las tres fuentes anteriores (p. ej.
    // baño sin antesala u orientación norte, que `classify_problems` no
    // clasifica como "problema") se añade como problema nuevo — si no,
    // nunca se vería en el panel ni su flecha de efectos derivados.
    var byKey = {};
    items.forEach(function (it) { byKey[issueKey(it)] = it; });
    (vivienda.efectos_cadena || []).forEach(function (ce) {
      var o = ce.problema_origen;
      var key = issueKey(o);
      var existing = byKey[key];
      if (existing) {
        existing.chain = ce;
      } else {
        var nuevo = {
          source: "issue", severity: o.severity, codigo: o.codigo, titulo: o.titulo,
          descripcion: o.descripcion, impacto: o.impacto,
          soluciones: [o.solucion, ALT_SOLUCION[o.codigo] || ALT_SOLUCION_GENERICA],
          room_label: o.room_label, chain: ce
        };
        items.push(nuevo);
        byKey[key] = nuevo;
      }
    });

    items.forEach(function (it) {
      it.disciplina = disciplinaFor(it);
      it.costeEstimado = costeEstimadoDe(it);
    });

    return items;
  }

  // =======================================================================
  // Cableado del inspector
  // =======================================================================
  // Un único listener delegado sobre `#inspector`, instalado una sola vez en
  // `renderWorkspace`. Es delegado a propósito: el contenido del inspector se
  // reconstruye entero cada vez que cambia la selección o la herramienta, así
  // que cualquier listener colgado de un botón concreto moriría en el primer
  // repintado.
  function wireInspector() {
    var host = document.getElementById("inspector");
    if (!host) return;

    host.addEventListener("click", function (e) {
      var irModo = e.target.closest("[data-modo-ir]");
      if (irModo) { setModo(irModo.dataset.modoIr); return; }

      var volver = e.target.closest(".inspector-back");
      if (volver) { soltarFoco(); return; }

      var problema = e.target.closest("[data-problema]");
      if (problema) {
        var idx = parseInt(problema.dataset.problema, 10);
        state.seleccion = { tipo: "problema", idx: idx };
        // Localizar la habitación en el plano al seleccionar el problema:
        // la relación entre el dato y el dibujo debe ser inmediata.
        if (problema.dataset.roomLabel) {
          localizarHabitacion(document.getElementById("svg-container"), viviendaActual(), problema.dataset.roomLabel);
        }
        renderInspector();
        return;
      }

      var panel = e.target.closest("[data-panel]");
      if (panel) { abrirPanelFlotante(panel.dataset.panel, panel.dataset.panelAlcance); return; }

      var more = e.target.closest(".detail-more");
      if (more) {
        var body = host.querySelector(".detail-more-body");
        if (body) {
          body.hidden = !body.hidden;
          more.textContent = body.hidden ? "Detalles técnicos" : "Ocultar detalles técnicos";
        }
        return;
      }

      var generarIa = e.target.closest("#btn-generar-diagnostico-ia");
      if (generarIa) { generarDiagnosticoIA(); return; }

      var toggle = e.target.closest("#btn-toggle-filtros");
      if (toggle) { state.filtrosAbiertos = !state.filtrosAbiertos; renderInspector(); return; }

      var reset = e.target.closest("#btn-reset-filtros");
      if (reset) {
        var f = state.filtros;
        Object.keys(f.severidades).forEach(function (k) { f.severidades[k] = true; });
        Object.keys(f.disciplinas).forEach(function (k) { f.disciplinas[k] = true; });
        renderInspector();
        return;
      }

      var chip = e.target.closest(".filter-chip");
      if (chip) {
        var bucket = chip.dataset.tipo === "severidad" ? state.filtros.severidades : state.filtros.disciplinas;
        bucket[chip.dataset.valor] = !bucket[chip.dataset.valor];
        renderInspector();
      }
    });

    // Emparejamiento informe <-> plano. Pasar el ratón por un punto del
    // informe realza su marca numerada sobre el plano, y al revés. Es el
    // detalle que hace que las dos columnas se lean como una sola cosa —
    // un diagnóstico— en vez de como un dibujo al lado de una tabla.
    host.addEventListener("mouseover", function (e) {
      var punto = e.target.closest(".report-point");
      if (punto) realzarPin(punto.dataset.problema, true);
    });
    host.addEventListener("mouseout", function (e) {
      var punto = e.target.closest(".report-point");
      if (punto) realzarPin(punto.dataset.problema, false);
    });
  }

  function realzarPin(idxProblema, on) {
    var svg = document.querySelector("#svg-container svg");
    if (!svg) return;
    var pin = svg.querySelector('.plan-pin[data-pin="' + idxProblema + '"]');
    if (pin) pin.classList.toggle("pin-hi", !!on);
  }

  function realzarPuntoInforme(idxProblema, on) {
    var btn = document.querySelector('#inspector .report-point[data-problema="' + idxProblema + '"]');
    if (btn) btn.classList.toggle("hi", !!on);
  }

  // --- Salir del foco --------------------------------------------------------
  // Tres caminos al mismo sitio (Escape, "volver", y el vacío del plano)
  // porque salir de un detalle nunca debe costar pensar cuál era el gesto.

  function soltarFoco() {
    state.seleccion = null;
    limpiarFoco();
    renderInspector();
  }

  function wireSalidaFoco() {
    var container = document.getElementById("svg-container");
    if (!container) return;
    container.addEventListener("click", function (e) {
      // Un clic en el lienzo pero fuera de cualquier habitación o marca.
      if (e.target.closest(".plan-room") || e.target.closest(".plan-pin")) return;
      if (state.seleccion) soltarFoco();
    });
  }

  // --- Selección de habitación desde el propio plano -------------------------
  // La navegación va del plano al inspector, no al revés: pulsar una
  // habitación la selecciona y el inspector pasa a describirla.

  function wireRoomSelection(container, vivienda) {
    Array.prototype.forEach.call(container.querySelectorAll(".plan-room"), function (g) {
      g.addEventListener("click", function () {
        var idx = parseInt(g.getAttribute("data-room"), 10);
        if (isNaN(idx) || !vivienda.habitaciones[idx]) return;
        // Un clic en el plano siempre gana: selecciona esa habitación sea
        // cual sea el modo activo, y el inspector pasa a describirla sin
        // abandonar el modo.
        state.seleccion = { tipo: "habitacion", idx: idx };
        enfocarHabitacion(idx);
        renderInspector();
      });
    });

    // Los puntos numerados del informe son pulsables desde el propio plano:
    // el emparejamiento funciona en los dos sentidos.
    var svg = container.querySelector("svg");
    if (!svg) return;
    svg.addEventListener("click", function (e) {
      var pin = e.target.closest(".plan-pin");
      if (!pin) return;
      e.stopPropagation();
      var idxProblema = parseInt(pin.dataset.pin, 10);
      var it = state.problemas[idxProblema];
      if (!it) return;
      state.seleccion = { tipo: "problema", idx: idxProblema };
      if (it.room_label) localizarHabitacion(container, vivienda, it.room_label);
      renderInspector();
    });
    svg.addEventListener("mouseover", function (e) {
      var pin = e.target.closest(".plan-pin");
      if (pin) realzarPuntoInforme(pin.dataset.pin, true);
    });
    svg.addEventListener("mouseout", function (e) {
      var pin = e.target.closest(".plan-pin");
      if (pin) realzarPuntoInforme(pin.dataset.pin, false);
    });
  }

  // --- Panel flotante --------------------------------------------------------
  // Para listas que se consultan y se cierran (habitaciones, orientación,
  // diagnósticos de capas AM_*). No desplaza el plano, se cierra con Escape
  // o pulsando fuera. `alcance` solo lo usa `"diagnosticos-capas-am"`:
  // "vivienda" (entrada local, `capasAmHtml`) filtra a la vivienda actual;
  // "proyecto" (entrada de `renderViviendaList`) muestra los diagnósticos
  // sin vivienda asignable — mismo panel, mismo renderer, dos alcances.

  var panelFlotanteEl = null;
  var panelFlotanteBackdrop = null;

  function abrirPanelFlotante(tipo, alcance) {
    cerrarPanelFlotante();
    var v = viviendaActual();
    if (!v) return;

    var titulo, cuerpo;
    if (tipo === "habitaciones") {
      titulo = "Habitaciones (" + v.habitaciones.length + ")";
      cuerpo = listaHabitacionesHtml(v);
    } else if (tipo === "diagnosticos-capas-am") {
      var diagnosticos = alcance === "proyecto" ? diagnosticosCapasAmSinVivienda() : diagnosticosCapasAmDeVivienda(v);
      titulo = alcance === "proyecto"
        ? "Diagnósticos de capas AM_* (plano)"
        : "Diagnósticos de capas AM_* — " + v.nombre;
      cuerpo = listaDiagnosticosCapasAmHtml(diagnosticos);
    } else if (tipo === "hechos-edificio") {
      titulo = "Hechos del edificio";
      cuerpo = hechosEdificioHtml();
    } else {
      titulo = "Orientación y luz";
      cuerpo = listaOrientacionHtml(v.habitaciones);
    }

    panelFlotanteBackdrop = document.createElement("div");
    panelFlotanteBackdrop.className = "float-panel-backdrop";
    panelFlotanteBackdrop.addEventListener("click", cerrarPanelFlotante);

    panelFlotanteEl = document.createElement("div");
    panelFlotanteEl.className = "float-panel";
    panelFlotanteEl.innerHTML = '<div class="float-panel-title">' + escapeHtml(titulo) + "</div>" + cuerpo;

    // Pulsar una habitación de la lista la localiza en el plano y cierra el
    // panel: la lista es un índice para llegar al plano, no un destino.
    panelFlotanteEl.addEventListener("click", function (e) {
      var fila = e.target.closest("[data-room-idx]");
      if (!fila) return;
      var idx = parseInt(fila.dataset.roomIdx, 10);
      var room = v.habitaciones[idx];
      cerrarPanelFlotante();
      if (!room) return;
      state.seleccion = { tipo: "habitacion", idx: idx };
      renderInspector();
      localizarHabitacion(document.getElementById("svg-container"), v, room.nombre);
    });

    document.body.appendChild(panelFlotanteBackdrop);
    document.body.appendChild(panelFlotanteEl);
    document.addEventListener("keydown", onPanelFlotanteKey);
  }

  function onPanelFlotanteKey(e) {
    if (e.key === "Escape") cerrarPanelFlotante();
  }

  function cerrarPanelFlotante() {
    if (panelFlotanteEl) { panelFlotanteEl.remove(); panelFlotanteEl = null; }
    if (panelFlotanteBackdrop) { panelFlotanteBackdrop.remove(); panelFlotanteBackdrop = null; }
    document.removeEventListener("keydown", onPanelFlotanteKey);
  }

  // Sin icono por fila: la etiqueta ya dice "Dormitorio", el pictograma no
  // añadía comprensión (ver criterio de iconos del rediseño).
  function listaHabitacionesHtml(v) {
    return '<ul class="room-list">' + v.habitaciones.map(function (r, i) {
      return '<li data-room-idx="' + i + '">' +
        '<span class="room-name">' + escapeHtml(r.nombre) + "</span>" +
        (r.problemas.length ? '<span class="room-problem-dot"></span>' : "") +
        '<span class="room-area">' + r.area_m2.toFixed(2) + " m²</span></li>";
    }).join("") + "</ul>";
  }

  function listaOrientacionHtml(habitaciones) {
    var rows = habitaciones.filter(function (r) { return r.orientacion_cardinal; });
    if (!rows.length) return '<p class="inspector-empty">Sin datos de orientación.</p>';
    return '<ul class="orientation-list">' + rows.map(function (r) {
      var ratingLabel = ORIENT_RATING_LABEL[r.orientacion_valoracion];
      var badge = ratingLabel
        ? '<span class="orient-badge ' + ORIENT_RATING_CLASS[r.orientacion_valoracion] + '">' + ratingLabel + "</span>"
        : '<span class="orient-neutral">Sin regla</span>';
      var luz = r.factor_luz_natural_pct != null
        ? '<span class="orient-luz">FLN ' + r.factor_luz_natural_pct.toFixed(1) + "%</span>"
        : "";
      return "<li>" +
        '<span class="orient-name">' + escapeHtml(r.nombre) + "</span>" +
        '<span class="orient-compass">' + escapeHtml(r.orientacion_cardinal) + "</span>" +
        badge + luz +
        "</li>";
    }).join("") + "</ul>";
  }

  // =======================================================================
  // Lienzo CAD: paneo, zoom al cursor, encuadre, crosshair y coordenadas
  // =======================================================================
  // Sustituye al zoom anterior, que era un `transform: scale()` centrado,
  // topado a 3x y SIN paneo — un arquitecto acostumbrado a AutoCAD intenta
  // arrastrar con el botón central en el primer minuto y no pasaba nada.
  //
  // Todo opera ahora sobre el `viewBox` del propio `<svg>`, no sobre
  // `transform`, por tres razones: es el mismo mecanismo que ya usaba la
  // localización de habitación (`animarViewBox`), permite anclar el zoom al
  // cursor con aritmética simple, y deja que `getScreenCTM()` haga la
  // conversión pantalla→plano sin que haya que replicarla a mano.

  function svgActual() {
    var cont = document.getElementById("svg-container");
    return cont ? cont.querySelector("svg") : null;
  }

  // Punto del cursor en coordenadas del viewBox, vía la matriz del propio
  // SVG: sobrevive a cualquier escalado CSS del contenedor.
  function puntoEnPlano(svg, clientX, clientY) {
    var ctm = svg.getScreenCTM();
    if (!ctm) return null;
    var p = svg.createSVGPoint();
    p.x = clientX;
    p.y = clientY;
    return p.matrixTransform(ctm.inverse());
  }

  function zoomEnPunto(factor, clientX, clientY) {
    var svg = svgActual();
    if (!svg) return;
    var vb = currentViewBoxOf(svg);
    var p = puntoEnPlano(svg, clientX, clientY);
    if (!p) return;
    var nw = vb[2] / factor;
    // El alto se DERIVA del ancho conservando la relación de aspecto exacta.
    // Calcularlo por separado (`vb[3] / factor`) y redondear ambos hacía que
    // la relación variara en el último decimal en cada paso; con
    // `preserveAspectRatio="meet"` eso reencuadra un poco el dibujo y el
    // punto bajo el cursor derivaba visiblemente tras varios zooms.
    var nh = nw * (vb[3] / vb[2]);
    // Límites amplios pero finitos: sin ellos, la rueda puede dejar el plano
    // en un estado del que solo se sale con Encuadrar.
    if (nw < 4 || nw > 40000) return;
    // El punto bajo el cursor no se mueve: esa es toda la definición de
    // "zoom al cursor", y es comprobable numéricamente (ver tests).
    escribirViewBox(svg, [
      p.x - (p.x - vb[0]) / factor,
      p.y - (p.y - vb[1]) / factor,
      nw, nh
    ]);
  }

  // 6 decimales: a 3, el redondeo acumulado de sucesivos zooms/paneos era
  // perceptible como deriva del punto anclado.
  function escribirViewBox(svg, vb) {
    svg.setAttribute("viewBox", vb.map(function (n) { return n.toFixed(6); }).join(" "));
  }

  function zoomPorFactor(factor) {
    var svg = svgActual();
    if (!svg) return;
    var r = svg.getBoundingClientRect();
    zoomEnPunto(factor, r.left + r.width / 2, r.top + r.height / 2);
  }

  // Encuadre = el ZE de AutoCAD. Vuelve al viewBox de referencia que
  // `ajustarViewBox` guardó al montar la vivienda.
  function zoomExtents() {
    var svg = svgActual();
    if (!svg) return;
    var base = svg.getAttribute("data-base-viewbox");
    if (base) svg.setAttribute("viewBox", base);
  }

  function wireLienzoCAD() {
    var lienzo = document.getElementById("cad-lienzo");
    var cont = document.getElementById("svg-container");
    if (!lienzo || !cont) return;

    lienzo.addEventListener("wheel", function (e) {
      // En modo "Cuadro" el plano está oculto (`aplicarModoLienzo`) pero
      // `svgActual()` lo sigue encontrando -- sigue en el DOM, solo
      // `display: none` -- así que sin esta guarda, CUALQUIER scroll dentro
      // de `#cad-cuadro-superficies` disparaba `preventDefault()` e
      // intentaba hacer zoom sobre un plano invisible, bloqueando el
      // scroll normal de la tabla (bug real reportado: "dentro del cuadro
      // no puedo scrolear bien").
      if (state.modo === "cuadro" || !svgActual()) return;
      e.preventDefault();
      zoomEnPunto(e.deltaY > 0 ? 1 / 1.12 : 1.12, e.clientX, e.clientY);
      actualizarCoordenadas(e.clientX, e.clientY);
    }, { passive: false });

    // Paneo por dos vías, a propósito: el botón central no existe en muchos
    // portátiles y trackpads, así que barra espaciadora + arrastre es la
    // alternativa (misma convención que AutoCAD y que casi todo el software
    // de diseño). El botón IZQUIERDO no panea nunca: sigue seleccionando
    // habitación, que es una función que ya existía y no se puede robar.
    var paneo = null;

    lienzo.addEventListener("mousedown", function (e) {
      var esCentral = e.button === 1;
      var esEspacio = e.button === 0 && state.espacioPulsado;
      if (!esCentral && !esEspacio) return;
      var svg = svgActual();
      if (!svg) return;
      e.preventDefault();
      paneo = { x: e.clientX, y: e.clientY, vb: currentViewBoxOf(svg) };
      lienzo.classList.add("is-paneando");
    });

    window.addEventListener("mousemove", function (e) {
      if (!paneo) return;
      var svg = svgActual();
      if (!svg) return;
      var r = svg.getBoundingClientRect();
      // Píxel de pantalla → unidad de plano, usando la escala real del
      // encuadre actual: así el plano sigue al cursor exactamente.
      var kx = paneo.vb[2] / r.width;
      var ky = paneo.vb[3] / r.height;
      escribirViewBox(svg, [
        paneo.vb[0] - (e.clientX - paneo.x) * kx,
        paneo.vb[1] - (e.clientY - paneo.y) * ky,
        paneo.vb[2], paneo.vb[3]
      ]);
    });

    window.addEventListener("mouseup", function () {
      if (!paneo) return;
      paneo = null;
      lienzo.classList.remove("is-paneando");
    });

    // Doble clic en vacío = encuadrar. Sobre una habitación no, que ahí ya
    // hay otro gesto con dueño.
    lienzo.addEventListener("dblclick", function (e) {
      if (e.target.closest(".plan-room")) return;
      zoomExtents();
    });

    lienzo.addEventListener("mousemove", function (e) {
      moverCrosshair(e.clientX, e.clientY);
      actualizarCoordenadas(e.clientX, e.clientY);
    });
    lienzo.addEventListener("mouseenter", function () {
      var ch = document.getElementById("cad-crosshair");
      if (ch) ch.hidden = false;
    });
    lienzo.addEventListener("mouseleave", function () {
      var ch = document.getElementById("cad-crosshair");
      if (ch) ch.hidden = true;
      var el = document.getElementById("cad-coords");
      if (el) el.textContent = "—";
    });
  }

  function moverCrosshair(clientX, clientY) {
    var lienzo = document.getElementById("cad-lienzo");
    var ch = document.getElementById("cad-crosshair");
    if (!lienzo || !ch) return;
    var r = lienzo.getBoundingClientRect();
    ch.querySelector(".cad-crosshair-h").style.top = (clientY - r.top) + "px";
    ch.querySelector(".cad-crosshair-v").style.left = (clientX - r.left) + "px";
  }

  // Coordenadas en metros REALES del DXF. La conversión no es deducible del
  // SVG por sí sola: `plan_svg._compact_clusters` y `_grid_layout` trasladan
  // habitaciones para que una vivienda dispersa sea legible. Por eso el
  // backend publica la transformación (`data-escala`, `data-ox`, `data-oy`,
  // `data-minx`, `data-maxy`) y, por habitación, su desplazamiento
  // (`data-dx`, `data-dy`). Ver `tests/test_plan_coords.py`.
  function actualizarCoordenadas(clientX, clientY) {
    var el = document.getElementById("cad-coords");
    var svg = svgActual();
    if (!el || !svg) return;
    var p = puntoEnPlano(svg, clientX, clientY);
    var escala = parseFloat(svg.getAttribute("data-escala"));
    if (!p || !escala) { el.textContent = "—"; return; }

    var mx = (p.x - parseFloat(svg.getAttribute("data-ox"))) / escala +
      parseFloat(svg.getAttribute("data-minx"));
    var my = parseFloat(svg.getAttribute("data-maxy")) -
      (p.y - parseFloat(svg.getAttribute("data-oy"))) / escala;

    // Fuera de una habitación, en un plano compactado, no existe UNA
    // coordenada real correcta: cada grupo se movió por su cuenta. Se usa el
    // desplazamiento de la habitación bajo el cursor cuando la hay, y se
    // marca el valor con ~ cuando no lo hay y el plano no es fiel.
    var g = document.elementFromPoint(clientX, clientY);
    g = g ? g.closest(".plan-room") : null;
    var fiel = svg.getAttribute("data-fiel") === "1";
    var aprox = "";
    if (g) {
      mx += parseFloat(g.getAttribute("data-dx")) || 0;
      my += parseFloat(g.getAttribute("data-dy")) || 0;
    } else if (!fiel) {
      aprox = "~";
    }
    el.textContent = aprox + mx.toFixed(3) + ", " + my.toFixed(3) + " m";
  }

  // Indicadores de la barra de estado: solo se muestran los que dicen algo.
  // Un indicador permanentemente apagado es el mismo error que un menú vacío.
  function renderStatusFlags() {
    var el = document.getElementById("cad-status-flags");
    if (!el) return;
    var flags = [];
    var svg = svgActual();
    if (svg && svg.getAttribute("data-fiel") === "0") {
      flags.push('<span class="cad-flag" title="Esta vivienda tiene grupos de habitaciones separados que se han acercado entre sí para que el plano sea legible. Dentro de cada habitación las coordenadas son reales; fuera se marcan con ~.">COMPACTADO</span>');
    }
    // Solo se señalan las capas que se DESVÍAN del preset del modo activo.
    // Marcar toda capa apagada pondría "RELLENOS OFF" permanentemente en
    // Resumen, que es su estado normal: un indicador que nunca cambia no
    // informa de nada y solo añade ruido a la barra.
    var preset = presetCapasDeModo(state.modo);
    CAPAS.forEach(function (c) {
      if (state.capas[c.id] === preset[c.id]) return;
      flags.push('<span class="cad-flag is-apagada">' + escapeHtml(c.label.toUpperCase()) +
        (state.capas[c.id] ? " ON" : " OFF") + "</span>");
    });
    el.innerHTML = flags.join("");
  }

  // =======================================================================
  // Línea de comandos
  // =======================================================================
  // Solo se sostiene si es honesta. Un usuario de AutoCAD escribirá LINE o
  // TRIM en los primeros treinta segundos: la respuesta no puede ser un
  // error genérico, tiene que explicar que ArchMuse analiza y no dibuja.
  // Todos los comandos de aquí ejecutan una acción que ya existía.

  var COMANDOS = [
    { nombre: "ENCUADRAR", alias: ["ZE", "Z"], fn: function () { zoomExtents(); return "Encuadrado."; } },
    { nombre: "ZOOM+", alias: ["ZM"], fn: function () { zoomPorFactor(1.25); return null; } },
    { nombre: "ZOOM-", alias: ["ZL"], fn: function () { zoomPorFactor(1 / 1.25); return null; } },
    { nombre: "CAPA", alias: ["LA"], fn: function (arg) {
      if (!arg) return "Uso: CAPA RELLENOS | ETIQUETAS | NORTE";
      var id = arg.toLowerCase();
      if (!(id in state.capas)) return 'Capa desconocida "' + arg + '".';
      alternarCapa(id);
      return "Capa " + arg.toUpperCase() + (state.capas[id] ? " activada." : " desactivada.");
    } },
    { nombre: "PDF", alias: [], fn: function () { descargarPdf(); return "Generando PDF…"; } },
    { nombre: "CSV", alias: [], fn: function () { exportarCSV(); return "CSV exportado."; } },
    { nombre: "3D", alias: [], fn: function () { abrirVisor3d(state.data); return null; } },
    { nombre: "INICIO", alias: [], fn: function () { irAInicio(); return null; } }
  ];

  // Los 6 modos también son comandos, sin duplicar el catálogo a mano.
  PLAN_MODES.forEach(function (m) {
    COMANDOS.push({
      nombre: m.label.toUpperCase(), alias: [],
      fn: function () { setModo(m.id); return null; }
    });
  });

  // Comandos de dibujo de AutoCAD que el usuario escribirá por instinto. No
  // se dejan caer en "comando desconocido": merecen una respuesta que
  // explique en qué se diferencia esta herramienta.
  var COMANDOS_DIBUJO = ["LINE", "L", "TRIM", "OFFSET", "COPY", "MOVE", "ERASE", "E",
    "CIRCLE", "C", "ARC", "PLINE", "PL", "HATCH", "DIM", "MTEXT", "EXTEND", "FILLET",
    "ROTATE", "SCALE", "MIRROR", "ARRAY", "BLOCK", "INSERT", "LAYER", "PLOT", "SAVE"];

  function ejecutarComando(texto) {
    var partes = String(texto || "").trim().split(/\s+/);
    var nombre = (partes[0] || "").toUpperCase();
    var arg = partes.slice(1).join(" ");
    if (!nombre) return null;

    if (nombre === "?" || nombre === "AYUDA" || nombre === "HELP") {
      return "Comandos: " + COMANDOS.map(function (c) {
        return c.nombre + (c.alias.length ? " (" + c.alias.join(", ") + ")" : "");
      }).join(" · ");
    }

    var cmd = COMANDOS.filter(function (c) {
      return c.nombre === nombre || c.alias.indexOf(nombre) !== -1;
    })[0];
    if (cmd) return cmd.fn(arg);

    if (COMANDOS_DIBUJO.indexOf(nombre) !== -1) {
      return "ArchMuse analiza planos, no los dibuja: " + nombre +
        " no existe aquí. Escribe ? para ver lo que sí puedes hacer.";
    }
    return 'Comando desconocido "' + nombre + '". Escribe ? para ver la lista.';
  }

  function wireComando() {
    var input = document.getElementById("cad-comando-input");
    var eco = document.getElementById("cad-comando-eco");
    if (!input || !eco) return;
    input.addEventListener("keydown", function (e) {
      // La caja se come los atajos globales mientras tiene el foco: si no,
      // escribir un comando dispararía otras cosas por el camino.
      e.stopPropagation();
      if (e.key === "Escape") { input.value = ""; input.blur(); return; }
      if (e.key !== "Enter") return;
      var texto = input.value;
      input.value = "";
      var respuesta = ejecutarComando(texto);
      eco.textContent = respuesta || "";
    });
  }

  // --- Localización de habitación desde "Problemas detectados" (Requisito 4) -

  // --- Localización de habitación desde "Problemas detectados" (Requisito 4) -

  function currentViewBoxOf(svg) {
    var vb = svg.getAttribute("viewBox");
    var parts = vb ? vb.split(/\s+/).map(Number) : [];
    return parts.length === 4 && parts.every(function (n) { return !isNaN(n); }) ? parts : [0, 0, 800, 600];
  }

  // Anima el `viewBox` del propio `<svg>` de `from` a `to` en `duration` ms
  // (easing suave) — se usa el `viewBox`, no `transform: scale()`, porque
  // `viewBox` opera en las coordenadas reales del plano (0-800 x 0-600)
  // independientemente del tamaño en pantalla del contenedor, así el
  // encuadre queda centrado en la habitación real sin cálculos de píxeles.
  function animateViewBox(svg, from, to, duration) {
    var start = null;
    function step(ts) {
      if (start === null) start = ts;
      var t = Math.min((ts - start) / duration, 1);
      var ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      var cur = [0, 1, 2, 3].map(function (i) { return from[i] + (to[i] - from[i]) * ease; });
      svg.setAttribute("viewBox", cur.join(" "));
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // Foco sobre una habitación. Sustituye al borde azul pulsante de 2s de la
  // versión anterior: aquí no se ilumina el objeto, se ATENÚA el contexto
  // (`.has-focus` en el contenedor, ver CSS). Es la diferencia entre un
  // visor profesional y una aplicación que hace parpadear cosas.
  function enfocarHabitacion(roomIndex) {
    var container = document.getElementById("svg-container");
    var svg = container && container.querySelector("svg");
    if (!svg) return;
    var g = svg.querySelector('.plan-room[data-room="' + roomIndex + '"]');
    if (!g) return;

    Array.prototype.forEach.call(svg.querySelectorAll(".plan-room.room-focus"), function (o) {
      o.classList.remove("room-focus");
    });
    g.classList.add("room-focus");
    container.classList.add("has-focus");

    var b = bboxHabitacion(g);
    if (!b) return;

    // Encuadre generoso: la habitación enfocada ocupa como mucho un tercio
    // del ancho, porque el arquitecto necesita seguir viendo dónde está esa
    // habitación dentro de la vivienda. Un zoom cerrado la aislaría del
    // contexto que da sentido al problema.
    var base = baseViewBoxOf(svg);
    var aspect = base[2] / base[3];
    var targetW = Math.max(b.w * 3, base[2] * 0.45);
    var targetH = targetW / aspect;
    if (targetH < b.h * 3) { targetH = b.h * 3; targetW = targetH * aspect; }
    var cx = b.x + b.w / 2, cy = b.y + b.h / 2;

    // Desde el workspace CAD, el zoom de rueda y el paneo también operan
    // sobre `viewBox`, así que ya no hay dos mecanismos que separar: basta
    // con animar hasta el encuadre destino. Se limpia cualquier `transform`
    // heredado por si quedara de una sesión anterior del navegador.
    svg.style.transform = "";
    animateViewBox(svg, currentViewBoxOf(svg), [cx - targetW / 2, cy - targetH / 2, targetW, targetH], 350);
  }

  function limpiarFoco() {
    var container = document.getElementById("svg-container");
    var svg = container && container.querySelector("svg");
    if (!container || !svg) return;
    container.classList.remove("has-focus");
    Array.prototype.forEach.call(svg.querySelectorAll(".plan-room.room-focus"), function (o) {
      o.classList.remove("room-focus");
    });
    animateViewBox(svg, currentViewBoxOf(svg), baseViewBoxOf(svg), 350);
  }

  // Encuadre de referencia que dejó `ajustarViewBox`; si por lo que sea no
  // está, se cae al viewBox fijo del backend.
  function baseViewBoxOf(svg) {
    var raw = svg.getAttribute("data-base-viewbox");
    var parts = raw ? raw.split(/\s+/).map(Number) : [];
    return parts.length === 4 && parts.every(function (n) { return !isNaN(n); }) ? parts : [0, 0, 800, 600];
  }

  // Enfoca la habitación llamada `roomLabel`. Si no coincide con ninguna
  // (problemas de vivienda completa, sin habitación asociada — p. ej.
  // itinerario accesible o baño adaptado) no hace nada: esa línea del
  // informe se queda sin marca en el plano, que es lo honesto.
  function localizarHabitacion(svgContainer, vivienda, roomLabel) {
    var roomIndex = indiceHabitacion(vivienda, roomLabel);
    if (roomIndex === -1) return;
    enfocarHabitacion(roomIndex);
  }

  // --- Tooltip flotante sobre el plano SVG ---------------------------------

  // Con 400ms de retardo: el tooltip aparecía al instante y bastaba cruzar
  // el plano con el ratón para que saltaran cinco cajas seguidas. Un retardo
  // corto distingue "estoy mirando esta habitación" de "estoy pasando por
  // encima". Sin el icono de aviso por línea: eran N triángulos repetidos
  // dentro de una caja que ya está diciendo que son problemas.
  var TOOLTIP_DELAY_MS = 400;

  function wireRoomTooltips(container, vivienda) {
    var timer = null;
    Array.prototype.forEach.call(container.querySelectorAll(".plan-room"), function (g) {
      var idx = parseInt(g.getAttribute("data-room"), 10);
      var room = vivienda.habitaciones[idx];
      if (!room) return;

      g.addEventListener("mouseenter", function () {
        clearTimeout(timer);
        timer = setTimeout(function () {
          tooltip.querySelector(".tooltip-title").textContent = room.nombre;
          tooltip.querySelector(".tooltip-area").textContent = room.area_m2.toFixed(2) + " m²";
          tooltip.querySelector(".tooltip-problems").innerHTML = room.problemas.map(function (p) {
            return "<div><span>" + escapeHtml(p) + "</span></div>";
          }).join("");
          tooltip.hidden = false;
        }, TOOLTIP_DELAY_MS);
      });
      g.addEventListener("mousemove", function (e) { positionTooltip(e.clientX, e.clientY); });
      g.addEventListener("mouseleave", function () { clearTimeout(timer); tooltip.hidden = true; });
    });
  }

  // El tinte de severidad por habitación (antes `aplicarSeveridadHabitaciones`)
  // ha pasado a `pintarPlano()`, que decide relleno Y trazo de una sola vez
  // según el modo activo. Tenerlo separado obligaba a que dos funciones se
  // pusieran de acuerdo sobre el mismo polígono.

  function positionTooltip(x, y) {
    var pad = 14;
    var left = x + pad;
    var top = y + pad;
    var rect = tooltip.getBoundingClientRect();
    if (left + rect.width > window.innerWidth - 8) left = x - rect.width - pad;
    if (top + rect.height > window.innerHeight - 8) top = y - rect.height - pad;
    tooltip.style.left = left + "px";
    tooltip.style.top = top + "px";
  }

  // --- Shell: desplegables de menú --------------------------------------------
  // Único mecanismo para los 5 triggers de la barra: abre con click, cambia
  // con hover una vez hay uno abierto (barra de menú de escritorio), cierra
  // con Escape/click-fuera/selección. Sin animación de entrada — un menú de
  // aplicación debe sentirse instantáneo. Los ítems con `items` anidados
  // (hoy solo "Nuevo" en Proyecto) abren un flyout a la derecha con el mismo
  // mecanismo, no una lista aplanada.

  var shellOpen = null;   // { trigger, el } | null — desplegable de primer nivel
  var shellFlyout = null; // { parentBtn, el } | null — submenú, como mucho uno
  var flyoutCloseTimer = null; // margen de tolerancia al cruzar en diagonal hacia el flyout

  function cancelFlyoutClose() {
    if (flyoutCloseTimer) { clearTimeout(flyoutCloseTimer); flyoutCloseTimer = null; }
  }

  function scheduleFlyoutClose() {
    cancelFlyoutClose();
    flyoutCloseTimer = setTimeout(function () { closeShellFlyout(); }, 300);
  }

  function shellItemHtml(item, idx) {
    if (item.sep) return '<div class="shell-dropdown-sep"></div>';
    var check = item.checked ? "✓" : "";
    var arrow = item.items ? '<span class="shell-dropdown-item-arrow">▸</span>' : "";
    // `desc` es opcional (solo lo usa el menú "Nuevo"): sin ella el ítem
    // queda pixel-igual a como estaba (una línea, mismo alto de siempre),
    // así que Exportar y los demás menús no cambian de aspecto.
    var desc = item.desc ? '<span class="shell-dropdown-item-desc">' + escapeHtml(item.desc) + "</span>" : "";
    return '<button type="button" class="shell-dropdown-item' + (item.desc ? " has-desc" : "") + '" data-idx="' + idx + '"' +
      (item.disabled ? " disabled" : "") + ">" +
      '<span class="shell-dropdown-item-check">' + check + "</span>" +
      '<span class="shell-dropdown-item-body">' +
      '<span class="shell-dropdown-item-label">' + escapeHtml(item.label) + "</span>" + desc +
      "</span>" + arrow +
      "</button>";
  }

  function closeShellFlyout() {
    cancelFlyoutClose();
    if (!shellFlyout) return;
    shellFlyout.el.remove();
    shellFlyout = null;
  }

  function closeShellMenu() {
    closeShellFlyout();
    if (!shellOpen) return;
    shellOpen.trigger.setAttribute("aria-expanded", "false");
    shellOpen.el.remove();
    shellOpen = null;
  }

  function buildShellDropdown(items, top, left) {
    var el = document.createElement("div");
    el.className = "shell-dropdown";
    el.style.top = top + "px";
    el.style.left = left + "px";
    el.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-idx]");
      if (!btn || btn.disabled) return;
      var item = items[parseInt(btn.dataset.idx, 10)];
      if (item.items) return; // el hover ya abrió el flyout; el click no hace nada más aquí
      closeShellMenu();
      var handler = SHELL_ACTIONS[item.action];
      if (handler) handler();
    });
    el.addEventListener("mouseover", function (e) {
      var btn = e.target.closest("[data-idx]");
      if (!btn) return;
      var item = items[parseInt(btn.dataset.idx, 10)];
      if (!item.items) {
        // Ítem hermano en el menú padre sin submenú: no cerrar de inmediato.
        // Al llegar en diagonal desde el trigger hasta un ítem del flyout, el
        // cursor puede pasar un instante por aquí — dar margen a que el
        // mouseenter del flyout (más abajo) cancele el cierre a tiempo.
        if (shellFlyout && shellFlyout.el !== el) scheduleFlyoutClose();
        return;
      }
      cancelFlyoutClose();
      if (shellFlyout && shellFlyout.parentBtn === btn) return;
      var rect = btn.getBoundingClientRect();
      closeShellFlyout();
      var flyoutEl = buildShellDropdown(item.items, rect.top, rect.right + 2);
      flyoutEl.addEventListener("mouseenter", cancelFlyoutClose);
      document.body.appendChild(flyoutEl);
      shellFlyout = { parentBtn: btn, el: flyoutEl };
    });
    el.innerHTML = items.map(shellItemHtml).join("");
    return el;
  }

  function openShellMenu(trigger, items) {
    closeShellMenu();
    if (trigger.disabled) return;
    var rect = trigger.getBoundingClientRect();
    var el = buildShellDropdown(items, rect.bottom + 4, rect.left);
    document.body.appendChild(el);
    trigger.setAttribute("aria-expanded", "true");
    shellOpen = { trigger: trigger, el: el };
  }

  var SHELL_ACTIONS = {
    "nuevo-analizar": function () { renderUpload(); },
    // Fase E: "Generar proyecto" abre ahora el entrevistador conversacional
    // (`entrevista.js`, E1) en vez del formulario técnico directo. El
    // formulario (`renderGenerarForm`, arriba en este archivo) se conserva
    // sin tocar — nada más lo invoca ya desde este menú, pero sigue siendo
    // código válido por si hiciera falta revertir este cambio de entrada.
    "nuevo-generar": function () {
      if (window.ArchmuseEntrevista) { window.ArchmuseEntrevista.iniciar(); }
      else { renderGenerarForm(); } // entrevista.js no cargó: no dejar el menú sin acción
    },
    "exportar-pdf": function () { descargarPdf(); },
    "exportar-csv": function () { exportarCSV(); }
  };

  // --- Puente con el entrevistador (Fase E) --------------------------------
  // `entrevista.js` es un módulo aislado (plan E1: "no se amplía más
  // static/app.js") que nunca toca `state` ni el DOM de la shell
  // directamente — solo a través de esta superficie mínima, mismo principio
  // de aislamiento que ya separa `viewer-edificio.js`/`viewer-vivienda.js`
  // del resto de la app. Tres funciones, nada más: limpiar el contexto del
  // sidebar al entrar, volver a donde estaba el usuario al cancelar, y
  // entregar un proyecto ya generado al workspace (mismo efecto que el
  // `.then()` de éxito de `wireGenerarForm` más arriba).
  window.ArchmuseShell = {
    limpiarContextoSidebar: function () { updateSidebarContext(null); },
    // Bug corregido (2026-08-17, reportado en vivo): mandaba SIEMPRE a `renderUpload()` ("Analizar
    // plano") cuando no había un proyecto ya cargado en memoria (`state.data`) -- que es el caso normal
    // al cancelar desde "+ Nuevo proyecto" → "Generar proyecto" → Paso 0, sin haber abierto antes ningún
    // proyecto. Cancelar terminaba derivando al usuario a la OTRA función de creación (subir DXF), no al
    // Dashboard. `renderInicio()` es la función correcta -- ya decide ella misma, según si el usuario
    // tiene proyectos guardados o no (`cargarProyectos()`), si mostrar la parrilla o caer a `renderUpload`
    // (v3 §2.2/§8.2, comportamiento intencional para cuentas nuevas sin nada guardado) -- así que delegar
    // en ella cubre los dos casos sin duplicar esa lógica aquí. `closeShellMenu()` al entrar: defensivo
    // (el desplegable de "+ Nuevo proyecto" ya se cierra solo al elegir un ítem, ver `buildShellDropdown`)
    // pero explícito, para no depender de que ese otro camino siga cerrándolo si cambia en el futuro.
    onCancelar: function () { closeShellMenu(); if (state.data) { renderWorkspace(); } else { renderInicio(); } },
    onProyectoGenerado: function (json) {
      state.data = json;
      state.selectedId = null;
      renderWorkspace();
    },
    // Dos añadidos (2026-08-15) a los "tres únicos" que el propio
    // encabezado del archivo documentaba: el botón "Generar proyecto" de
    // `entrevista.js` (`handleGenerar`) volvía a pintar el resumen ENTERO
    // (todas las categorías ya rellenadas) con solo el texto del botón
    // cambiado a "Generando…" mientras esperaba a `/api/generar` -- la
    // pantalla de carga limpia que ya tenía `app.js` (`renderLoading`,
    // pasos + barra de progreso) nunca se usaba desde ahí. En vez de
    // duplicar esa lógica dentro de `entrevista.js`, se expone aquí.
    mostrarCargandoGeneracion: function (titulo) {
      renderLoading(titulo || "Generando tu proyecto", GENERATE_STEPS);
    },
    // `entrevista.js` debe llamar a esto (nunca reescribir `#view-root` por
    // su cuenta) antes de volver a su propia vista tras `mostrarCargando
    // Generacion` -- `finishLoading` limpia los `setInterval` de la barra/
    // pasos; sin esto quedarían corriendo indefinidamente sobre un DOM ya
    // sustituido.
    finalizarCargandoGeneracion: function (onDone) { finishLoading(onDone); },
    // "Modo enfocado" (2026-08-15, a petición explícita): oculta el sidebar SIN tocar la preferencia
    // guardada del usuario (`colapsoManual`/localStorage) -- es un colapso temporal solo mientras dura el
    // flujo de "Generar proyecto" (selección de parcela + entrevista), para centrar toda la atención ahí.
    // `restaurarSidebar` vuelve a aplicar lo que el usuario tenía elegido (o el criterio automático por
    // ancho de ventana) -- nunca deja el sidebar colapsado pegado tras salir del flujo.
    enfocarSinSidebar: function () { aplicarColapso(true); },
    restaurarSidebar: function () { ajustarColapsoAlAncho(); }
  };

  // Las dos únicas formas de empezar un proyecto (mejora de UX de esta
  // noche): antes el desplegable "Nuevo" solo tenía la etiqueta, sin decir
  // qué hace cada opción. Se comparte entre el trigger del sidebar y el
  // botón del propio Inicio — un solo sitio donde cambiar el texto.
  var NUEVO_MENU_ITEMS = [
    { label: "Analizar plano", desc: "Sube un DXF existente y recibe un diagnóstico de calidad normativa.", action: "nuevo-analizar" },
    { label: "Generar proyecto", desc: "La IA distribuye un proyecto residencial completo desde cero, a partir de tus parámetros.", action: "nuevo-generar" }
  ];

  function abrirMenuNuevo(trigger) {
    if (shellOpen && shellOpen.trigger === trigger) { closeShellMenu(); return; }
    openShellMenu(trigger, NUEVO_MENU_ITEMS);
  }

  // --- Sidebar ----------------------------------------------------------------
  // Sustituye a la barra superior y a sus cinco menús (v3 de la
  // especificación de Shell). De aquellos cinco: Proyecto se reduce a
  // "+ Nuevo" + "Inicio", Exportar se muda al encabezado de proyecto, y
  // Herramientas, Ventana y Cuenta se eliminan — llevaban `disabled` desde que
  // se escribieron y portarlas habría sido trasladar deuda a un sidebar nuevo.

  var COLAPSO_KEY = "archmuse:sidebar-colapsado";
  var ANCHO_COLAPSO_AUTO = 900;
  var colapsoManual = null; // preferencia explícita del usuario; null = sin tocar

  function aplicarColapso(colapsado) {
    sidebar.classList.toggle("is-colapsado", !!colapsado);
    sidebarCollapse.setAttribute("aria-label", colapsado ? "Expandir panel" : "Colapsar panel");
  }

  function alternarColapso() {
    colapsoManual = !sidebar.classList.contains("is-colapsado");
    try { localStorage.setItem(COLAPSO_KEY, colapsoManual ? "1" : "0"); } catch (e) { /* modo privado */ }
    aplicarColapso(colapsoManual);
  }

  // Por debajo del umbral se fuerza el colapso, pero SIN pisar la preferencia
  // guardada: al volver a una ventana ancha se recupera lo que el usuario
  // había elegido, no lo que impuso el tamaño de la ventana.
  function ajustarColapsoAlAncho() {
    if (window.innerWidth < ANCHO_COLAPSO_AUTO) { aplicarColapso(true); return; }
    aplicarColapso(colapsoManual === null ? false : colapsoManual);
  }

  function restaurarColapso() {
    var guardado = null;
    try { guardado = localStorage.getItem(COLAPSO_KEY); } catch (e) { /* modo privado */ }
    if (guardado !== null) colapsoManual = guardado === "1";
    ajustarColapsoAlAncho();
  }

  // Zona contextual (§6): con proyecto abierto lista sus viviendas; sin
  // proyecto, hasta 5 recientes. Nunca las dos cosas, nunca una sección vacía.
  function updateSidebarContext(data) {
    if (data) { renderViviendaList(); return; }
    var recientes = state.proyectos.slice(0, 5);
    if (!recientes.length) { sidebarContexto.innerHTML = ""; return; }
    sidebarContexto.innerHTML =
      '<div class="sidebar-seccion">Recientes</div>' +
      recientes.map(function (p) {
        return '<button type="button" class="sidebar-fila" data-proyecto="' + escapeHtml(p.id) + '">' +
          '<span class="sidebar-fila-nombre">' + escapeHtml(p.nombre) + "</span>" +
          "</button>";
      }).join("");
    Array.prototype.forEach.call(sidebarContexto.querySelectorAll("[data-proyecto]"), function (fila) {
      fila.addEventListener("click", function () { abrirProyecto(fila.dataset.proyecto); });
    });
  }

  function wireSidebar() {
    sidebarBrand.addEventListener("click", irAInicio);
    sidebarInicio.addEventListener("click", irAInicio);
    sidebarCollapse.addEventListener("click", alternarColapso);

    sidebarNuevo.addEventListener("click", function (e) {
      e.stopPropagation();
      abrirMenuNuevo(sidebarNuevo);
    });

    window.addEventListener("resize", ajustarColapsoAlAncho);

    document.addEventListener("click", function (e) {
      if (!shellOpen) return;
      var dentroMenu = shellOpen.el.contains(e.target) || e.target === shellOpen.trigger;
      var dentroFlyout = shellFlyout && shellFlyout.el.contains(e.target);
      if (!dentroMenu && !dentroFlyout) closeShellMenu();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && shellOpen) { closeShellMenu(); return; }
      if (e.ctrlKey && e.key === "1") { e.preventDefault(); alternarColapso(); return; }
      if (e.ctrlKey && e.key === "2") { e.preventDefault(); alternarInspector(); }
    });

    // Barra espaciadora mantenida = paneo con botón izquierdo, la segunda
    // vía para ratones y trackpads sin botón central (§6 del PRD). Se ignora
    // mientras se escribe en un campo, o escribir un espacio en la línea de
    // comandos armaría el paneo sin querer.
    document.addEventListener("keydown", function (e) {
      if (e.code !== "Space" || escribiendoEnCampo(e.target)) return;
      state.espacioPulsado = true;
      var lienzo = document.getElementById("cad-lienzo");
      if (lienzo) lienzo.classList.add("is-paneable");
      e.preventDefault(); // si no, la barra desplaza la página
    });
    document.addEventListener("keyup", function (e) {
      if (e.code !== "Space") return;
      state.espacioPulsado = false;
      var lienzo = document.getElementById("cad-lienzo");
      if (lienzo) lienzo.classList.remove("is-paneable");
    });
    // Al perder el foco de la ventana con la barra pulsada, el `keyup` nunca
    // llega y el lienzo se quedaría armado para siempre.
    window.addEventListener("blur", function () {
      state.espacioPulsado = false;
      var lienzo = document.getElementById("cad-lienzo");
      if (lienzo) lienzo.classList.remove("is-paneable");
    });
  }

  function escribiendoEnCampo(el) {
    if (!el) return false;
    var tag = el.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
  }

  // --- Inicio: parrilla de proyectos guardados --------------------------------

  function irAInicio() {
    state.data = null;
    state.selectedId = null;
    state.archivoAnalizado = null;
    state.cuadroTabla = null;
    state.diagnosticoIaEstado = null;
    state.pliegoEstado = null;
    state.pliegoImportado = null;
    state.pliegoGenerarError = null;
    state.verificacionPliego = null;
    state.checklistCampo = null;
    renderInicio();
  }

  function renderInicio() {
    updateSidebarContext(null);
    viewRoot.innerHTML =
      '<div class="inicio-screen bg-technical">' +
      '<div class="inicio-cabecera">' +
      // El subtítulo explicativo se retiró (2026-08-17, pedido explícito: "la app debe hablar por
      // sí sola") -- "+ Nuevo proyecto" y las tarjetas ya debajo dicen lo que hace la pantalla sin
      // necesitar una frase de eslogan encima.
      '<div class="inicio-titulo">' +
      "<h1>ArchMuse</h1>" +
      "</div>" +
      '<button type="button" class="btn-primary inicio-btn-nuevo" id="inicio-btn-nuevo">+ Nuevo proyecto</button>' +
      "</div>" +
      // Oculta hasta saber si hay algo que listar: con 0 proyectos esta
      // pantalla ni siquiera llega a verse (cae a renderUpload más abajo), y
      // sin el `hidden` parpadearía una etiqueta de sección sobre una
      // parrilla vacía durante el fetch.
      '<div class="inicio-seccion-label" id="inicio-seccion-label" hidden>Tus proyectos</div>' +
      '<div class="inicio-parrilla" id="inicio-parrilla"></div>' +
      "</div>";

    var btnNuevo = document.getElementById("inicio-btn-nuevo");
    if (btnNuevo) {
      btnNuevo.addEventListener("click", function (e) {
        e.stopPropagation();
        abrirMenuNuevo(btnNuevo);
      });
    }

    cargarProyectos().then(function (proyectos) {
      // Sin nada guardado, el Inicio NO es una parrilla vacía con un texto de
      // consuelo: es la pantalla de creación, que es lo único que un usuario
      // nuevo puede hacer (v3 §2.2 y §8.2).
      if (!proyectos.length) { renderUpload(); return; }
      var label = document.getElementById("inicio-seccion-label");
      if (label) label.hidden = false;
      pintarParrilla(proyectos);
    });
  }

  function cargarProyectos() {
    return fetch("/api/proyectos")
      .then(function (r) { return r.ok ? r.json() : { proyectos: [] }; })
      .then(function (body) {
        state.proyectos = body.proyectos || [];
        updateSidebarContext(state.data);
        return state.proyectos;
      })
      .catch(function () { state.proyectos = []; return []; });
  }

  function pintarParrilla(proyectos) {
    var parrilla = document.getElementById("inicio-parrilla");
    if (!parrilla) return;
    parrilla.innerHTML = proyectos.map(function (p) {
      // Sin miniatura no se pone un icono de relleno: se deja el hueco con el
      // motivo, que es información y no decoración (§6 del PRD).
      var mini = p.miniatura
        ? '<div class="proyecto-card-mini">' + p.miniatura + "</div>"
        : '<div class="proyecto-card-mini is-vacia">Sin plano dibujable</div>';
      // Tarjeta reducida a lo mínimo (2026-08-17, pedido explícito: "solo
      // la imagen del plano, el nombre y la fecha. Sin métricas adicionales
      // en la tarjeta") — la puntuación, el aviso de semáforo y el recuento
      // de viviendas que llevaba antes se retiran de aquí; la puntuación
      // sigue disponible dentro del proyecto (riel de viviendas e informe).
      return '<div class="proyecto-card" data-id="' + escapeHtml(p.id) + '" role="button" tabindex="0">' +
        mini +
        '<div class="proyecto-card-cuerpo">' +
        '<span class="proyecto-card-nombre">' + escapeHtml(p.nombre) + "</span>" +
        '<span class="proyecto-card-meta">' + fechaCorta(p.modificado_en) + "</span>" +
        "</div>" +
        '<button type="button" class="proyecto-card-borrar" data-borrar="' + escapeHtml(p.id) +
        '" aria-label="Borrar proyecto" title="Borrar proyecto">&times;</button>' +
        "</div>";
    }).join("");

    Array.prototype.forEach.call(parrilla.querySelectorAll(".proyecto-card"), function (card) {
      card.addEventListener("click", function (e) {
        if (e.target.closest("[data-borrar]")) return;
        abrirProyecto(card.dataset.id);
      });
      card.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abrirProyecto(card.dataset.id); }
      });
    });
    Array.prototype.forEach.call(parrilla.querySelectorAll("[data-borrar]"), function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        borrarProyecto(btn.dataset.borrar);
      });
    });
  }

  function fechaCorta(iso) {
    if (!iso) return "";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString("es-ES", { day: "numeric", month: "short" });
  }

  function abrirProyecto(id) {
    fetch("/api/proyectos/" + encodeURIComponent(id))
      .then(function (r) {
        if (!r.ok) throw new Error("no disponible");
        return r.json();
      })
      .then(function (payload) {
        state.data = payload;
        state.selectedId = null;
        // Un proyecto reabierto de la lista no trae el `File` original en
        // memoria (nunca se subió en esta sesión) -- si quedara el de un
        // análisis anterior, "Descargar DXF rellenado" descargaría el DXF
        // equivocado. Ver comentario junto a `archivoAnalizado` en `state`.
        state.archivoAnalizado = null;
        state.cuadroTabla = null;
        state.diagnosticoIaEstado = null;
        state.pliegoEstado = null;
        state.pliegoImportado = null;
        state.pliegoGenerarError = null;
        state.verificacionPliego = null;
        state.checklistCampo = null;
        renderWorkspace();
      })
      .catch(function () {
        alert("No se pudo abrir ese proyecto.");
      });
  }

  function borrarProyecto(id) {
    var p = state.proyectos.filter(function (x) { return x.id === id; })[0];
    if (!confirm("¿Borrar " + (p ? p.nombre : "este proyecto") + "? No se puede deshacer.")) return;
    fetch("/api/proyectos/" + encodeURIComponent(id), { method: "DELETE" })
      .then(function () { renderInicio(); });
  }

  // --- Exportación ------------------------------------------------------------

  function descargarPdf() {
    if (!state.data) return;
    var btn = document.getElementById("btn-exportar");
    if (btn) btn.disabled = true;
    fetch("/api/informe-pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.data)
    })
      .then(function (resp) {
        if (!resp.ok) throw new Error("No se pudo generar el informe.");
        return resp.blob();
      })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = "informe.pdf";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      })
      .catch(function () {
        alert("No se pudo generar el informe PDF.");
      })
      .then(function () {
        if (btn) btn.disabled = false;
      });
  }

  // Fase 4: reenvía el `File` original (`state.archivoAnalizado`, ver
  // `state`) a `/api/exportar-cuadro-superficies` y descarga la respuesta.
  // No calcula nada: todo el trabajo (detección, borrador de relleno,
  // escritura de la copia) vive en `analyzer/cuadro_superficies*.py`
  // (Fases 2/3), reutilizado tal cual desde esa ruta.
  function descargarDxfRelleno() {
    if (!state.archivoAnalizado) return;
    var btn = document.getElementById("btn-exportar-dxf-relleno");
    if (btn) btn.disabled = true;

    var nombreDescarga = state.archivoAnalizado.name.replace(/\.dxf$/i, "") + "_ArchMuse_relleno.dxf";
    var formData = new FormData();
    formData.append("dxf", state.archivoAnalizado);

    fetch("/api/exportar-cuadro-superficies", { method: "POST", body: formData })
      .then(function (resp) {
        if (!resp.ok) {
          return resp.json()
            .then(function (json) { throw new Error(json.error || "No se pudo generar el DXF rellenado."); })
            .catch(function (err) { throw err instanceof Error ? err : new Error("No se pudo generar el DXF rellenado."); });
        }
        return resp.blob();
      })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = nombreDescarga;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      })
      .catch(function (err) {
        // El análisis que ya se ve en pantalla no depende de esta llamada
        // en absoluto (es un upload/descarga aparte, ver docstring del
        // endpoint) -- el único efecto de un fallo es este aviso.
        alert((err && err.message) || "No se pudo generar el DXF rellenado.");
      })
      .then(function () {
        if (btn) btn.disabled = false;
      });
  }

  // `DOC-1` (docs/AGENTE_BACKLOG.md §10, sesión 2026-08-19): reenvía el
  // `File` original (`state.archivoAnalizado`, mismo patrón que
  // `descargarDxfRelleno`) a `/api/acta-legible`, que ejecuta de verdad la
  // Skill `superficies.medicion_de_planta` y devuelve HTML ya renderizado
  // por `analyzer/acta_legible.py` -- nada se traduce ni se recalcula aquí.
  // Se abre en pestaña nueva (no se descarga) porque es una página para
  // leer, no un fichero para guardar.
  function abrirActaLegible() {
    if (!state.archivoAnalizado) return;
    var btn = document.getElementById("btn-acta-legible");
    if (btn) btn.disabled = true;

    var formData = new FormData();
    formData.append("dxf", state.archivoAnalizado);

    fetch("/api/acta-legible", { method: "POST", body: formData })
      .then(function (resp) {
        if (!resp.ok) {
          return resp.json()
            .then(function (json) { throw new Error(json.error || "No se pudo levantar el acta."); })
            .catch(function (err) { throw err instanceof Error ? err : new Error("No se pudo levantar el acta."); });
        }
        return resp.text();
      })
      .then(function (html) {
        // Blob + URL.createObjectURL, no `document.write`: mismo patrón que
        // ya usa `exportarCSV` en este fichero para el CSV, aquí con
        // `text/html` para que el navegador la muestre en vez de descargarla.
        var blob = new Blob([html], { type: "text/html;charset=utf-8;" });
        var url = URL.createObjectURL(blob);
        var ventana = window.open(url, "_blank");
        if (!ventana) {
          alert("El navegador ha bloqueado la pestaña nueva. Permite las ventanas emergentes para ver el acta.");
        }
        setTimeout(function () { URL.revokeObjectURL(url); }, 30000);
      })
      .catch(function (err) {
        // Igual que `descargarDxfRelleno`: el análisis en pantalla no
        // depende de esta llamada, es una petición aparte.
        alert((err && err.message) || "No se pudo levantar el acta.");
      })
      .then(function () {
        if (btn) btn.disabled = false;
      });
  }

  // =========================================================================
  // Conversación con ArchMuse (sesión 2026-08-19, noche 4)
  // =========================================================================
  //
  // La primera puerta de conversación real: en tus palabras, con o sin DXF
  // adjunto, y la respuesta es siempre trazable hasta una Skill real. Este
  // bloque NO decide nada por su cuenta -- llama a `/api/preguntar`, que ya
  // hace la única decisión que importa (`_capacidad_que_coincide`, en
  // `app.py`), y sólo presenta lo que vuelve. Cero cálculo, cero criterio
  // nuevo: es una tarea de interfaz, tal como se encargó.
  //
  // Dos preguntas de ejemplo, no una lista de "capacidades" inventada: son
  // literalmente formas de pedir lo único que la única Skill registrada hoy
  // sabe hacer (`superficies.medicion_de_planta`) -- si mañana hay una
  // segunda Skill, esta lista crece, no se inventa una entrada nueva sin
  // Skill detrás.
  var CONV_EJEMPLOS = [
    "¿Cuánta superficie útil tiene esta planta?",
    "Enséñame el acta de procedencia de este plano"
  ];
  // Áreas del mapa del producto que HOY no tienen ninguna capacidad
  // registrada -- nunca una cifra, nunca un check, sólo la palabra y la
  // misma etiqueta "todavía no" que ya usa el sidebar (`sidebar-badge-
  // proximamente`) para lo mismo. Ver HAZ #5 del encargo.
  var CONV_ROADMAP = ["Normativa (CTE)", "Presupuesto", "Geometría 3D"];

  var convState = {
    archivoAdjunto: null,
    // Últimos DXF adjuntados en ESTA sesión (noche 7): un navegador no
    // puede rastrear el disco por seguridad, así que "recordar" sólo puede
    // significar "seguir sujetando el `File` ya concedido" -- se pierde al
    // recargar la página, nunca sobrevive entre sesiones. Máximo 5, más
    // reciente primero.
    historialArchivos: [],
    // Última entidad (vivienda/estancia) que salió en una respuesta real
    // -- sólo para la sugerencia en línea, ver `convTarjetaHallazgo` y
    // `CONV_SUGERENCIAS_POR_CAPACIDAD`.
    ultimoContexto: null,
    sugerenciaActual: null
  };

  // Saludo o frase suelta, no una pregunta de medición (sesión 2026-08-19,
  // noche 6, petición directa de Pablo): "hola" no debería chocar con el
  // mismo bloqueo que protege la regla de oro ("Adjunta un DXF antes de
  // preguntar"), porque no es una pregunta que el backend pudiera
  // responder mal por falta de plano -- no es una pregunta. Función PURA
  // (sin DOM, sin `escapeHtml`) a propósito: sólo texto, para poder
  // extraerla y probarla aislada -- ver tests/test_conversacion_saludo.py.
  // Se compara el mensaje ENTERO (normalizado), nunca una subcadena: "hola,
  // ¿cuánta superficie tiene esto?" contiene "hola" pero es una pregunta
  // real y debe seguir bloqueando sin DXF, tal como pide el encargo.
  var CONV_SALUDOS = [
    "hola", "hey", "holi", "buenas", "buenos dias", "buenas tardes", "buenas noches",
    "que tal", "como estas", "como andas", "como va", "saludos", "hi", "hello",
    "hey archmuse", "hola archmuse", "gracias", "adios", "hasta luego"
  ];
  function _convEsSaludo(pregunta) {
    var t = (pregunta || "")
      .toLowerCase()
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "") // quita acentos: "qué" -> "que"
      .replace(/[¿?¡!.;:]/g, "") // la coma NO se quita aquí -- separa saludos, ver abajo
      .trim();
    if (!t) return false;
    // Un saludo real cabe en pocas palabras -- una pregunta larga que
    // empiece por "hola" no debe colar sólo por ser corta de más.
    if (t.split(/\s+/).length > 8) return false;
    // Cada trozo separado por coma tiene que ser, ÉL SOLO, un saludo
    // conocido ("hola, buenas" sí; "hola, ¿cuánta superficie...?" no,
    // porque el segundo trozo no está en `CONV_SALUDOS`). Así una pregunta
    // real que empiece con un saludo sigue bloqueando sin DXF, tal como
    // pide la regla de oro.
    var partes = t.split(",").map(function (p) {
      return p.replace(/\s+/g, " ").trim();
    }).filter(Boolean);
    return partes.length > 0 && partes.every(function (p) {
      return CONV_SALUDOS.indexOf(p) !== -1;
    });
  }

  function convMensajeSaludo() {
    return convState.archivoAdjunto
      ? "Hola, soy ArchMuse. Ya tienes " + convState.archivoAdjunto.name +
        " adjunto -- ¿qué quieres que mida?"
      : "Hola, soy ArchMuse. ¿Analizamos un plano? Adjunta un DXF y pregúntame lo que necesites medir.";
  }

  // Adjuntar hablando (sesión 2026-08-19, noche 7, petición directa de
  // Pablo). Un navegador no puede rastrear el disco del usuario por
  // seguridad -- la solución real es que ArchMuse dispare el selector
  // NATIVO del sistema desde la propia respuesta, en vez de exigir el
  // botón "Adjuntar DXF" aparte. Detector PURO (sin DOM), mismo criterio
  // que `_convEsSaludo`: nunca dispara sobre una pregunta real (si lleva
  // "?", no es una orden de adjuntar, es una pregunta -- y una pregunta
  // real sin DXF sigue bloqueando, tal como pide la regla de oro).
  var CONV_VERBOS_ADJUNTAR = [
    "abre", "abrir", "adjunta", "adjuntar", "sube", "subir", "carga", "cargar",
    "selecciona", "seleccionar", "elige", "elegir", "importa", "importar", "anade", "anadir", "pon",
    "analiza", "analizar"
  ];
  var CONV_SUSTANTIVOS_ARCHIVO = ["plano", "planos", "dxf", "archivo", "ficheros", "fichero", "documento"];
  function _convEsIntencionDeAdjuntar(pregunta) {
    var t = (pregunta || "")
      .toLowerCase()
      .normalize("NFD").replace(/[̀-ͯ]/g, "")
      .trim();
    if (!t || t.indexOf("?") !== -1) return false;
    var tieneVerbo = CONV_VERBOS_ADJUNTAR.some(function (v) {
      return new RegExp("\\b" + v + "\\b").test(t);
    });
    var tieneSustantivo = CONV_SUSTANTIVOS_ARCHIVO.some(function (s) {
      return new RegExp("\\b" + s + "\\b").test(t);
    });
    return tieneVerbo && tieneSustantivo;
  }

  // Recuerda el `File` (no sólo el nombre) -- así una elección posterior
  // desde el chat reutiliza los bytes ya concedidos, sin repetir el
  // selector nativo. Deduplicado por nombre, más reciente primero, tope 5.
  function convRegistrarArchivoUsado(file) {
    if (!file) return;
    convState.historialArchivos = convState.historialArchivos.filter(function (item) {
      return item.name !== file.name;
    });
    convState.historialArchivos.unshift({ name: file.name, file: file });
    convState.historialArchivos = convState.historialArchivos.slice(0, 5);
  }

  function abrirConversacion() {
    var overlay = document.getElementById("conversacion-archmuse");
    if (!overlay) return;
    // El DXF ya analizado se ofrece como punto de partida (mismo criterio
    // que "Acta de procedencia legible"), pero sigue siendo reemplazable
    // dentro del propio panel -- adjuntar aquí no toca `state.archivoAnalizado`.
    if (!convState.archivoAdjunto && state.archivoAnalizado) {
      convState.archivoAdjunto = state.archivoAnalizado;
    }
    renderConvAdjunto();
    overlay.classList.add("open");
    var textarea = document.getElementById("conv-pregunta");
    if (textarea) textarea.focus();
  }

  function cerrarConversacion() {
    var overlay = document.getElementById("conversacion-archmuse");
    if (overlay) overlay.classList.remove("open");
  }

  function renderConvAdjunto() {
    var cont = document.getElementById("conv-adjunto");
    if (cont) {
      if (!convState.archivoAdjunto) {
        cont.hidden = true;
        cont.innerHTML = "";
      } else {
        cont.hidden = false;
        cont.innerHTML = '<span class="conv-adjunto-chip">' + escapeHtml(convState.archivoAdjunto.name) +
          '<button type="button" class="conv-adjunto-quitar" id="conv-adjunto-quitar" aria-label="Quitar plano adjunto">&times;</button></span>';
      }
    }
    // Barra de estado: el mismo hecho (nombre de fichero adjunto o no) que
    // el chip de arriba, sólo que siempre visible -- nunca un dato nuevo.
    var dot = document.getElementById("conv-statusbar-dot");
    var nombre = document.getElementById("conv-statusbar-proyecto");
    if (dot) dot.classList.toggle("conv-statusbar-dot-activo", !!convState.archivoAdjunto);
    if (nombre) {
      nombre.textContent = convState.archivoAdjunto
        ? convState.archivoAdjunto.name
        : "Sin plano adjunto";
    }
  }

  // Fila "próximamente" de las acciones rápidas -- misma lista que "En el
  // mapa, todavía no" (`CONV_ROADMAP`), nunca un catálogo aparte. Cada
  // tarjeta es un `<div>`, no un `<button>`: no hay nada que pulsar, es un
  // estado, no una acción.
  function renderConvAccionesRapidasResto() {
    var cont = document.getElementById("conv-acciones-rapidas-resto");
    if (!cont) return;
    cont.innerHTML = CONV_ROADMAP.map(function (r) {
      return '<div class="conv-accion-card conv-accion-card-proximamente">' +
        '<span class="conv-accion-titulo">' + escapeHtml(r) +
        '<span class="sidebar-badge-proximamente">próximamente</span></span>' +
        '<span class="conv-accion-sub">Todavía no hay una capacidad real para esto</span></div>';
    }).join("");
  }

  // El `<summary>` de cada `<details class="limitacion">` lleva la etiqueta
  // Y el texto técnico juntos (ver `analyzer/acta_legible.py`) -- aquí se
  // separan leyendo sólo los nodos de texto, sin recalcular ni reinterpretar
  // nada de lo que la Skill ya decidió.
  function _convParsearActa(html) {
    var doc = new DOMParser().parseFromString(html, "text/html");
    var datos = Array.prototype.map.call(doc.querySelectorAll(".dato"), function (n) {
      return n.textContent.trim();
    }).filter(Boolean);
    var limitaciones = Array.prototype.map.call(doc.querySelectorAll("details.limitacion"), function (n) {
      var resumen = n.querySelector("summary");
      var textoResumen = "";
      if (resumen) {
        Array.prototype.forEach.call(resumen.childNodes, function (nodo) {
          if (nodo.nodeType === 3) textoResumen += nodo.textContent;
        });
      }
      var porque = n.querySelector(".porque");
      var cifra = n.querySelector(".cifra");
      return {
        comprobado: !!n.querySelector(".etiqueta-comprobado"),
        texto: textoResumen.trim(),
        porque: porque ? porque.textContent.trim() : null,
        cifra: cifra ? cifra.textContent.trim() : null
      };
    });
    return { datos: datos, limitaciones: limitaciones };
  }

  // Tarjeta de un hallazgo real: jerarquía "lo principal primero" (HAZ #3
  // del encargo) -- el caso comprobado (si lo hay) es el titular, el resto
  // de limitaciones (los "TODO, sin caso real" internos) quedan siempre
  // detrás de un `<details>` cerrado, nunca visibles por defecto.
  function convTarjetaHallazgo(capacidad, htmlActa) {
    var parsed = _convParsearActa(htmlActa);
    var comprobadas = parsed.limitaciones.filter(function (l) { return l.comprobado; });
    var pendientes = parsed.limitaciones.filter(function (l) { return !l.comprobado; });

    var badge, titulo, cuerpo;
    if (comprobadas.length) {
      var principal = comprobadas[0];
      var entidad = (principal.texto.match(/«([^»]+)»/) || [])[1];
      // Contexto para la sugerencia en línea (noche 7): la próxima
      // sugerencia puede referirse a esta misma entidad ("¿cuánta
      // superficie tiene VT1/3?") -- ver `CONV_SUGERENCIAS_POR_CAPACIDAD`.
      // Se sobrescribe en cada respuesta real: sólo el hallazgo MÁS
      // reciente puede sugerirse, nunca uno de una pregunta anterior.
      if (entidad) convState.ultimoContexto = { entidadMencionada: entidad };
      badge = '<span class="conv-badge conv-badge-hallazgo">Hallazgo</span>';
      titulo = entidad ? "Problema encontrado en «" + escapeHtml(entidad) + "»" : "Problema encontrado";
      cuerpo = '<p class="conv-cuerpo">' + escapeHtml(principal.porque || principal.texto) + "</p>" +
        (principal.cifra ? '<span class="conv-cifra">' + escapeHtml(principal.cifra) + "</span>" : "");
    } else {
      badge = '<span class="conv-badge conv-badge-limpio">Sin incidencias</span>';
      titulo = "No se ha encontrado ningún problema en esta medición";
      cuerpo = '<p class="conv-cuerpo">' + escapeHtml(parsed.datos.join(" ")) + "</p>";
    }

    var etiquetaDetalle = pendientes.length
      ? "Ver alcance completo de esta comprobación (" + pendientes.length + " punto(s) más, sin caso real todavía)"
      : "Ver el acta de procedencia completa";

    // Botón de la memoria (MJ-4, sesión 2026-08-19 noche 11): sólo cuando de
    // verdad hay algo que documentar -- mismo criterio que
    // `ActaSinDatos` en `analyzer/memoria_justificativa.py`, comprobado aquí
    // con la misma señal que ya usa el resto de la tarjeta (`parsed.datos`,
    // los `.dato` que trajo el acta HTML). El `data-` lleva la capacidad
    // para que quien conecte el clic sepa qué Skill la produjo, sin tener
    // que volver a mirar `htmlActa`.
    var botonMemoria = parsed.datos.length
      ? '<button type="button" class="btn-ghost conv-btn-memoria" data-descargar-memoria="1">' +
        "Descargar apartado de superficies (PDF)</button>"
      : "";

    return '<div class="conv-tarjeta">' + badge +
      '<h3 class="conv-titulo">' + titulo + "</h3>" + cuerpo +
      '<details class="conv-detalle"><summary>' + escapeHtml(etiquetaDetalle) + "</summary>" +
      '<iframe class="conv-acta-frame" title="Acta de procedencia completa"></iframe>' +
      "</details>" +
      botonMemoria +
      '<div class="conv-procedencia">' + escapeHtml(capacidad) + "</div>" +
      "</div>";
  }

  // Reenvía el MISMO `File` que se acaba de medir -- nunca
  // `convState.archivoAdjunto` en el momento del clic, que puede haber
  // cambiado si el arquitecto adjuntó otro plano entre la respuesta y la
  // descarga. Mismo patrón de descarga por blob que `descargarPdf()`
  // (`/api/informe-pdf`, más arriba en este fichero).
  function convDescargarMemoria(archivo, boton) {
    if (!archivo) return;
    if (boton) boton.disabled = true;
    var formData = new FormData();
    formData.append("dxf", archivo);
    fetch("/api/memoria-superficies", { method: "POST", body: formData })
      .then(function (resp) {
        if (!resp.ok) {
          return resp.json().then(function (j) {
            throw new Error(j.error || "No se pudo generar la memoria de superficies.");
          });
        }
        return resp.blob();
      })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = "apartado_de_superficies.pdf";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      })
      .catch(function (exc) {
        alert(exc.message || "No se pudo generar la memoria de superficies.");
      })
      .then(function () {
        if (boton) boton.disabled = false;
      });
  }

  // El estado "sin capacidad" -- la parte más difícil de acertar del
  // encargo. Decisión de diseño: se trata exactamente como ArchMuse trata
  // cualquier otro dato que no tiene (ver `.hecho-badge-unknown` en
  // style.css: "no determinado no es un error ni un aviso, es que ArchMuse
  // no tiene el dato"). Mismo registro tranquilo, mismo gris neutro, misma
  // ausencia de disculpa -- nunca rojo, nunca un tono de error.
  function convTarjetaFueraDeAlcance(mensaje) {
    // Sesión 2026-08-19, noche 7 (petición directa de Pablo): los chips
    // "Prueba en su lugar" desaparecen de aquí -- la sugerencia de qué
    // preguntar ahora vive en línea, en la propia caja de texto (fantasma +
    // TAB, ver `convActualizarSugerencia`), no como chips que sólo
    // aparecían tras un intento fallido. `CONV_EJEMPLOS` sigue viva: es la
    // base de esa sugerencia en línea para `superficies.medicion_de_planta`
    // (ver `CONV_SUGERENCIAS_POR_CAPACIDAD`), un solo catálogo de preguntas
    // reales, no dos que se puedan desincronizar.
    var roadmap = CONV_ROADMAP.map(function (r) {
      return '<span class="conv-en-el-mapa-item">' + escapeHtml(r) +
        '<span class="sidebar-badge-proximamente">todavía no</span></span>';
    }).join("");
    return '<div class="conv-tarjeta conv-tarjeta-fuera">' +
      '<span class="conv-badge conv-badge-fuera">Fuera de alcance hoy</span>' +
      '<h3 class="conv-titulo">Esto no lo mide ArchMuse todavía</h3>' +
      '<p class="conv-cuerpo">' + escapeHtml(mensaje) + "</p>" +
      '<div class="conv-en-el-mapa"><span class="conv-en-el-mapa-titulo">En el mapa, todavía no</span>' +
      roadmap + "</div>" +
      "</div>";
  }

  function convTarjetaError(mensaje) {
    return '<div class="conv-tarjeta conv-tarjeta-error">' +
      '<span class="conv-badge conv-badge-error">Error</span>' +
      '<p class="conv-cuerpo">' + escapeHtml(mensaje) + "</p></div>";
  }

  // Sin insignia a propósito: no es un hallazgo, no es un error, es sólo
  // el agente respondiendo -- la misma tarjeta de vidrio que el resto,
  // pero sin la anatomía de estado (ver .conv-badge-*) que las otras
  // llevan siempre. "Cálida" es esto: nada que gritar, sólo texto.
  function convTarjetaSaludo(mensaje) {
    return '<div class="conv-tarjeta conv-tarjeta-saludo">' +
      '<p class="conv-cuerpo">' + escapeHtml(mensaje) + "</p></div>";
  }

  // Ofrece los DXF ya usados en esta sesión como opciones rápidas -- así
  // "abre el plano" no repite el selector nativo si ya se subió. Cada chip
  // reutiliza el `File` guardado en `convState.historialArchivos`
  // directamente (mismos bytes, sin volver a pedirlos al sistema).
  function convTarjetaOfrecerRecientes() {
    var chips = convState.historialArchivos.map(function (item, i) {
      return '<button type="button" class="conv-chip" data-adjuntar-historial="' + i + '">' +
        escapeHtml(item.name) + "</button>";
    }).join("");
    var reciente = convState.historialArchivos[0];
    return '<div class="conv-tarjeta conv-tarjeta-saludo">' +
      '<p class="conv-cuerpo">¿Te refieres a ' + escapeHtml(reciente.name) +
      ", que usaste antes en esta sesión? Elige uno de los que ya adjuntaste, o uno nuevo.</p>" +
      '<div class="conv-sugerencias">' + chips +
      '<button type="button" class="conv-chip" data-adjuntar-otro="1">Elegir otro archivo…</button>' +
      "</div></div>";
  }

  // Si hay planos recientes en esta sesión, los ofrece en vez de repetir el
  // selector nativo; si no hay ninguno, no queda otra que pedírselo al
  // sistema -- y se abre directamente, en la misma pila de ejecución del
  // clic/Enter que disparó `convEnviarPregunta` (gesto de usuario todavía
  // "caliente"), para que el navegador lo permita sin bloquearlo.
  function convOfrecerAdjuntar() {
    if (convState.historialArchivos.length) {
      convAnadirRespuesta(convTarjetaOfrecerRecientes());
      return;
    }
    convAnadirRespuesta(convTarjetaSaludo(
      "Voy a abrir el selector de archivos -- elige el plano que quieras analizar."));
    var inputDxf = document.getElementById("conv-dxf");
    if (inputDxf) inputDxf.click();
  }

  // Sugerencia en línea, estilo autocompletado de buscador (noche 7,
  // petición directa de Pablo): SIEMPRE plantillas locales, cero llamada a
  // la API del modelo sólo por escribir en la caja. Registrada POR
  // CAPACIDAD -- el día que se registre una segunda Skill real, esto crece
  // con una entrada nueva en este objeto, nunca tocando `_convSugerirCompletado`
  // ni `convActualizarSugerencia`. Nunca normativa/coste/3D: no hay
  // entrada aquí para ninguna de esas, así que no hay nada que sugerir
  // hacia ellas -- prometerlo como sugerencia sería la misma alucinación
  // que prometerlo como respuesta.
  var CONV_SUGERENCIAS_POR_CAPACIDAD = {
    "superficies.medicion_de_planta": function (ctx) {
      var candidatas = CONV_EJEMPLOS.slice();
      if (ctx.entidadMencionada) {
        candidatas.unshift("¿cuánta superficie tiene " + ctx.entidadMencionada + "?");
      }
      return candidatas;
    }
  };

  function _convCandidatasDeSugerencia() {
    var ctx = convState.ultimoContexto || {};
    var candidatas = [];
    Object.keys(CONV_SUGERENCIAS_POR_CAPACIDAD).forEach(function (cap) {
      candidatas = candidatas.concat(CONV_SUGERENCIAS_POR_CAPACIDAD[cap](ctx));
    });
    return candidatas;
  }

  // Función PURA (sin DOM): dado lo ya escrito y una lista de preguntas
  // candidatas, devuelve la primera cuyo prefijo coincide, con el resto
  // por completar. `null` si nada encaja todavía -- no hay sugerencia que
  // forzar. La comparación ignora mayúsculas, acentos ("cuanta" encaja con
  // "¿Cuánta...", de sobra habitual al escribir rápido) y un "¿"/"¡" inicial
  // de la candidata (el usuario no empieza a teclear por la apertura) --
  // pero el `resto` que se muestra y el `completo` que TAB inserta
  // conservan la candidata tal cual, acentos y apertura incluidos.
  function _convSinAcentos(s) {
    return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "");
  }
  function _convSugerirCompletado(escrito, candidatas) {
    var t = _convSinAcentos((escrito || "").toLowerCase());
    if (!t || !candidatas) return null;
    for (var i = 0; i < candidatas.length; i++) {
      var c = candidatas[i];
      var cSinApertura = c.replace(/^[¿¡]+/, "");
      var cComparable = _convSinAcentos(cSinApertura.toLowerCase());
      if (cComparable.indexOf(t) === 0 && cSinApertura.length > escrito.length) {
        return { completo: c, resto: cSinApertura.slice(escrito.length) };
      }
    }
    return null;
  }

  function convActualizarSugerencia() {
    var textarea = document.getElementById("conv-pregunta");
    var fantasma = document.getElementById("conv-sugerencia-fantasma");
    if (!textarea || !fantasma) return;
    var escrito = textarea.value;
    if (!escrito) {
      convState.sugerenciaActual = null;
      fantasma.innerHTML = "";
      return;
    }
    // Sin plano adjunto, la sugerencia anima a adjuntar uno -- nunca a
    // preguntar algo que hoy no se podría responder sin él.
    var candidatas = convState.archivoAdjunto
      ? _convCandidatasDeSugerencia()
      : ["adjunta un plano dxf para que pueda medir algo real"];
    var sugerencia = _convSugerirCompletado(escrito, candidatas);
    convState.sugerenciaActual = sugerencia;
    fantasma.innerHTML = sugerencia
      ? '<span class="conv-sugerencia-tipeado">' + escapeHtml(escrito) + "</span>" +
        '<span class="conv-sugerencia-resto">' + escapeHtml(sugerencia.resto) + "</span>"
      : "";
  }

  function convAnadirFilaUsuario(pregunta, nombreArchivo) {
    var log = document.getElementById("conv-log");
    if (!log) return;
    var vacio = log.querySelector(".conv-vacio");
    if (vacio) vacio.remove();
    var fila = document.createElement("div");
    fila.className = "conv-fila conv-fila-usuario";
    var burbuja = document.createElement("div");
    burbuja.className = "conv-usuario";
    burbuja.innerHTML = escapeHtml(pregunta) +
      (nombreArchivo ? '<span class="conv-usuario-adjunto">' + escapeHtml(nombreArchivo) + "</span>" : "");
    fila.appendChild(burbuja);
    log.appendChild(fila);
    log.scrollTop = log.scrollHeight;
  }

  // Devuelve el nodo insertado -- quien llama rellena el `<iframe>` (si lo
  // hay) con `.srcdoc` como PROPIEDAD, nunca como atributo de la cadena de
  // HTML: evita cualquier problema de escapado del acta completa dentro de
  // un atributo. La burbuja del asistente lleva su identidad encima en
  // texto (`.conv-burbuja-marca`, "ArchMuse") -- logo + tipografía, nunca un
  // avatar (PROHIBIDO del encargo).
  function convAnadirRespuesta(htmlTarjeta) {
    var log = document.getElementById("conv-log");
    if (!log) return null;
    var fila = document.createElement("div");
    fila.className = "conv-fila conv-fila-asistente";
    var marca = document.createElement("div");
    marca.className = "conv-burbuja-marca";
    marca.textContent = "ArchMuse";
    var envoltorio = document.createElement("div");
    envoltorio.className = "conv-respuesta";
    envoltorio.innerHTML = htmlTarjeta;
    fila.appendChild(marca);
    fila.appendChild(envoltorio);
    log.appendChild(fila);
    log.scrollTop = log.scrollHeight;
    return envoltorio;
  }

  function convEnviarPregunta(pregunta) {
    var btn = document.getElementById("conv-btn-enviar");
    var textarea = document.getElementById("conv-pregunta");
    var archivo = convState.archivoAdjunto;

    // Un saludo no es una pregunta -- se responde y se sale ANTES de
    // llegar al bloqueo de "sin DXF" (regla de oro) y ANTES de tocar la
    // red: no hay nada que `/api/preguntar` pueda decidir sobre "hola".
    if (_convEsSaludo(pregunta)) {
      convAnadirFilaUsuario(pregunta, archivo ? archivo.name : null);
      convAnadirRespuesta(convTarjetaSaludo(convMensajeSaludo()));
      if (textarea) textarea.value = "";
      convActualizarSugerencia();
      return;
    }

    // "Abre el plano de mi escritorio" tampoco es una pregunta de medición
    // -- es una orden de adjuntar. Mismo criterio que el saludo: se
    // atiende y se sale antes del bloqueo y antes de la red.
    if (_convEsIntencionDeAdjuntar(pregunta)) {
      convAnadirFilaUsuario(pregunta, archivo ? archivo.name : null);
      if (textarea) textarea.value = "";
      convActualizarSugerencia();
      convOfrecerAdjuntar();
      return;
    }

    if (!archivo) {
      convAnadirFilaUsuario(pregunta, null);
      convAnadirRespuesta(convTarjetaError(
        "Adjunta un DXF antes de preguntar -- hoy ArchMuse sólo puede medir lo que hay dibujado en un plano real."));
      return;
    }

    convRegistrarArchivoUsado(archivo); // idempotente -- ya puede estar en el historial
    convAnadirFilaUsuario(pregunta, archivo.name);
    if (btn) btn.disabled = true;
    if (textarea) textarea.value = "";
    convActualizarSugerencia();

    var log = document.getElementById("conv-log");
    var estado = document.createElement("div");
    estado.className = "conv-estado";
    estado.id = "conv-estado-actual";
    estado.textContent = "Interpretando la pregunta…";
    if (log) { log.appendChild(estado); log.scrollTop = log.scrollHeight; }

    var formData = new FormData();
    formData.append("pregunta", pregunta);
    formData.append("dxf", archivo);

    fetch("/api/preguntar", { method: "POST", body: formData })
      .then(function (resp) {
        return resp.json().then(function (json) { return { ok: resp.ok, json: json }; });
      })
      .then(function (r) {
        var actual = document.getElementById("conv-estado-actual");
        if (actual) actual.remove();
        if (!r.ok) {
          convAnadirRespuesta(convTarjetaError(r.json.error || "No se pudo atender la pregunta."));
          return;
        }
        if (!r.json.coincide) {
          convAnadirRespuesta(convTarjetaFueraDeAlcance(r.json.mensaje || "ArchMuse no tiene esa capacidad todavía."));
          return;
        }
        var nodo = convAnadirRespuesta(convTarjetaHallazgo(r.json.capacidad, r.json.html));
        var iframe = nodo && nodo.querySelector(".conv-acta-frame");
        if (iframe) iframe.srcdoc = r.json.html;
        var botonMemoria = nodo && nodo.querySelector("[data-descargar-memoria]");
        if (botonMemoria) {
          // `archivo` es el `File` de ESTA medición (cierre de
          // `convEnviarPregunta`), no `convState.archivoAdjunto` -- ver el
          // comentario de `convDescargarMemoria`.
          botonMemoria.addEventListener("click", function () {
            convDescargarMemoria(archivo, botonMemoria);
          });
        }
      })
      .catch(function () {
        var actual = document.getElementById("conv-estado-actual");
        if (actual) actual.remove();
        convAnadirRespuesta(convTarjetaError("Error de red al atender la pregunta."));
      })
      .then(function () {
        if (btn) btn.disabled = false;
        if (textarea) textarea.focus();
      });
  }

  function wireConversacion() {
    renderConvAccionesRapidasResto();
    renderConvAdjunto(); // pinta la barra de estado también en el arranque, sin adjunto todavía.

    var cerrar = document.getElementById("btn-conversacion-cerrar");
    if (cerrar) cerrar.addEventListener("click", cerrarConversacion);

    // Acciones rápidas: la única tarjeta real (`data-pregunta`) se comporta
    // exactamente como una sugerencia del panel "fuera de alcance" -- si ya
    // hay un DXF adjunto, pregunta directamente; si no, sólo rellena el
    // campo y deja que el arquitecto adjunte primero. Las tarjetas
    // "próximamente" no llevan `data-pregunta`, así que no hacen nada al
    // pulsarlas -- ni falta que hace, `cursor: not-allowed` ya lo dice.
    var accionesRapidas = document.getElementById("conv-acciones-rapidas");
    if (accionesRapidas) accionesRapidas.addEventListener("click", function (e) {
      var tarjeta = e.target.closest("[data-pregunta]");
      if (!tarjeta) return;
      var pregunta = tarjeta.dataset.pregunta || "";
      var textarea = document.getElementById("conv-pregunta");
      if (textarea) textarea.value = pregunta;
      if (convState.archivoAdjunto) {
        convEnviarPregunta(pregunta);
      } else if (textarea) {
        textarea.focus();
      }
    });

    var form = document.getElementById("conv-form");
    if (form) form.addEventListener("submit", function (e) {
      e.preventDefault();
      var textarea = document.getElementById("conv-pregunta");
      var pregunta = textarea ? textarea.value.trim() : "";
      if (!pregunta) return;
      convEnviarPregunta(pregunta);
    });

    var btnAdjuntar = document.getElementById("conv-btn-adjuntar");
    var inputDxf = document.getElementById("conv-dxf");
    if (btnAdjuntar && inputDxf) {
      btnAdjuntar.addEventListener("click", function () { inputDxf.click(); });
      inputDxf.addEventListener("change", function () {
        if (inputDxf.files && inputDxf.files[0]) {
          convState.archivoAdjunto = inputDxf.files[0];
          convState.ultimoContexto = null; // plano nuevo: el contexto del anterior ya no aplica
          convRegistrarArchivoUsado(inputDxf.files[0]);
          renderConvAdjunto();
          convActualizarSugerencia();
        }
      });
    }

    var adjuntoCont = document.getElementById("conv-adjunto");
    if (adjuntoCont) adjuntoCont.addEventListener("click", function (e) {
      if (!e.target.closest("#conv-adjunto-quitar")) return;
      convState.archivoAdjunto = null;
      renderConvAdjunto();
      convActualizarSugerencia();
    });

    var log = document.getElementById("conv-log");
    if (log) log.addEventListener("click", function (e) {
      // Chip de un DXF ya usado en esta sesión (respuesta a "abre el
      // plano..."): reutiliza el `File` guardado, nunca vuelve a pedirlo
      // al sistema.
      var histBtn = e.target.closest("[data-adjuntar-historial]");
      if (histBtn) {
        var item = convState.historialArchivos[Number(histBtn.dataset.adjuntarHistorial)];
        if (item) {
          convState.archivoAdjunto = item.file;
          convState.ultimoContexto = null;
          convRegistrarArchivoUsado(item.file);
          renderConvAdjunto();
          convActualizarSugerencia();
          convAnadirRespuesta(convTarjetaSaludo("Adjunté " + item.name + ". ¿Qué quieres que mida?"));
        }
        return;
      }
      // "Elegir otro archivo…": aquí sí hace falta el selector nativo.
      if (e.target.closest("[data-adjuntar-otro]")) {
        var inputDxf = document.getElementById("conv-dxf");
        if (inputDxf) inputDxf.click();
        return;
      }
      var chip = e.target.closest(".conv-chip[data-pregunta]");
      if (!chip) return;
      var pregunta = chip.dataset.pregunta || "";
      var textarea = document.getElementById("conv-pregunta");
      if (textarea) textarea.value = pregunta;
      if (convState.archivoAdjunto) {
        convEnviarPregunta(pregunta);
      } else if (textarea) {
        textarea.focus();
      }
    });

    // El `<textarea>` crece con el contenido (una línea de sobra, nunca
    // scroll interno) -- mismo criterio que cualquier campo de pregunta
    // libre: el arquitecto ve lo que ha escrito entero.
    var textarea = document.getElementById("conv-pregunta");
    if (textarea) {
      textarea.addEventListener("input", function () {
        textarea.style.height = "auto";
        textarea.style.height = Math.min(textarea.scrollHeight, 160) + "px";
        convActualizarSugerencia();
      });
      textarea.addEventListener("keydown", function (e) {
        // TAB acepta la sugerencia en línea (si hay una) -- se queda en el
        // campo para seguir editando antes de enviar, nunca envía sola.
        if (e.key === "Tab" && convState.sugerenciaActual) {
          e.preventDefault();
          textarea.value = convState.sugerenciaActual.completo;
          convActualizarSugerencia();
          return;
        }
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          if (form) form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { cancelable: true }));
        }
      });
    }
  }

  // --- Fase 5: formulario "Datos necesarios para completar el cuadro" --------
  //
  // Nada de esto calcula superficies ni decide qué preguntar: eso vive
  // entero en `analyzer/cuadro_superficies.py` (`detectar_solicitudes`,
  // `aplicar_respuestas`), consumido a través de los dos endpoints de Fase
  // 5b/5c. Este bloque solo construye el formulario a partir de lo que el
  // backend ya decidió, recoge las respuestas y las reenvía tal cual.

  function etiquetaCampoLegible(campo) {
    return campo.replace(/_/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function respuestaNumericaValida(valorTexto) {
    if (valorTexto === undefined || valorTexto === null) return false;
    var texto = String(valorTexto).trim().replace(",", ".");
    if (texto === "") return false;
    var n = Number(texto);
    return isFinite(n) && !isNaN(n) && n >= 0;
  }

  function asignacionTieneDuplicados(asigParaEsta) {
    var elegidos = Object.keys(asigParaEsta || {})
      .map(function (k) { return asigParaEsta[k]; })
      .filter(function (v) { return v; });
    return new Set(elegidos).size !== elegidos.length;
  }

  // Puede llamarse antes de que el usuario toque nada: una solicitud de
  // asignación siempre tiene ya un valor válido por defecto (cada `<select>`
  // arranca en "-- Ninguna pieza real --", una respuesta explícita, no una
  // ausencia) -- solo las numéricas necesitan que el arquitecto escriba algo.
  function todasLasSolicitudesResueltas(solicitudes, valores, asignaciones) {
    return (solicitudes || []).every(function (s) {
      if (s.tipo === "numerico") {
        return respuestaNumericaValida(valores[s.campos[0]]);
      }
      return !asignacionTieneDuplicados((asignaciones || {})[s.id] || {});
    });
  }

  // (solicitudes, valores-por-campo-numerico, asignaciones-por-solicitud) ->
  // el mismo array de dicts que espera `aplicar_respuestas` en el backend.
  function construirRespuestasCuadro(solicitudes, valores, asignaciones) {
    return (solicitudes || []).map(function (s) {
      if (s.tipo === "numerico") {
        var campo = s.campos[0];
        var texto = String(valores[campo] || "").trim().replace(",", ".");
        return { tipo: "numerico", campo: campo, valor: Number(texto) };
      }
      var asigParaEsta = (asignaciones || {})[s.id] || {};
      var asignacionesFinal = {};
      s.campos.forEach(function (campo) {
        asignacionesFinal[campo] = asigParaEsta[campo] || null;
      });
      return { tipo: "asignacion", solicitud_id: s.id, asignaciones: asignacionesFinal };
    });
  }

  function cuadroSolicitudBloqueHtml(s, valores, asignaciones, pendientesPorCampo) {
    var motivoConflicto = s.campos.map(function (c) { return (pendientesPorCampo || {})[c]; })
      .filter(Boolean)[0];
    var conflictoHtml = motivoConflicto
      ? '<div class="cuadro-conflicto">' + escapeHtml(motivoConflicto) + "</div>" : "";

    if (s.tipo === "numerico") {
      var campo = s.campos[0];
      var valorActual = valores[campo] || "";
      return (
        '<div class="cuadro-solicitud-bloque">' +
        '<label class="cuadro-solicitud-titulo">' + escapeHtml(s.titulo) + "</label>" +
        '<p class="cuadro-solicitud-ayuda muted">' + escapeHtml(s.ayuda) + "</p>" +
        '<div class="cuadro-solicitud-input-row">' +
        '<input type="number" step="0.01" min="0" class="cuadro-input-numerico" ' +
        'data-campo="' + escapeHtml(campo) + '" value="' + escapeHtml(valorActual) + '">' +
        '<span class="cuadro-unidad">' + escapeHtml(s.unidad || "") + "</span>" +
        "</div>" + conflictoHtml + "</div>"
      );
    }

    var asigParaEsta = (asignaciones || {})[s.id] || {};
    var filas = s.campos.map(function (campo) {
      var seleccionado = asigParaEsta[campo] || "";
      var opciones = '<option value="">-- Ninguna pieza real --</option>' +
        (s.candidatos || []).map(function (c) {
          return '<option value="' + escapeHtml(c.id) + '"' + (c.id === seleccionado ? " selected" : "") + ">" +
            escapeHtml(c.etiqueta) + " — " + c.area_m2.toFixed(2) + " m² (x=" + c.x.toFixed(2) + ", y=" + c.y.toFixed(2) + ")" +
            "</option>";
        }).join("");
      return (
        '<div class="cuadro-asignacion-fila">' +
        "<label>" + escapeHtml(etiquetaCampoLegible(campo)) + "</label>" +
        '<select data-solicitud="' + escapeHtml(s.id) + '" data-campo="' + escapeHtml(campo) + '">' + opciones + "</select>" +
        "</div>"
      );
    }).join("");
    return (
      '<div class="cuadro-solicitud-bloque">' +
      '<div class="cuadro-solicitud-titulo">' + escapeHtml(s.titulo) + "</div>" +
      '<p class="cuadro-solicitud-ayuda muted">' + escapeHtml(s.ayuda) + "</p>" +
      filas + conflictoHtml + "</div>"
    );
  }

  // Fase 6d: el formulario ya NO vive en un modal aparte -- se pinta EN LA
  // PROPIA TABLA (`contenidoCuadroSuperficies`, dentro del lienzo grande)
  // en cuanto queda algo pendiente. "Quiero que sea posible rellenarlo todo
  // desde ArchMuse" + "quiero verlo, no descargarlo": todo en una pantalla,
  // sin un botón que abra un popup que haya que encontrar primero.
  function cuadroFormularioInlineHtml(solicitudes, valores, asignaciones, pendientesPorCampo) {
    if (!solicitudes || !solicitudes.length) return "";
    var bloques = solicitudes.map(function (s) {
      return cuadroSolicitudBloqueHtml(s, valores, asignaciones, pendientesPorCampo);
    }).join("");
    var habilitado = todasLasSolicitudesResueltas(solicitudes, valores, asignaciones);
    return (
      '<div class="cuadro-formulario-inline">' +
      "<h2>Datos necesarios para completar el cuadro</h2>" +
      '<p class="muted">ArchMuse ya ha calculado todo lo que se puede deducir del plano. Responde esto para ' +
      "ver el cuadro completo aquí mismo -- no se descarga nada.</p>" +
      bloques +
      '<button type="button" class="viewer-walk-btn active" id="btn-aplicar-respuestas-cuadro" ' +
      'data-accion="aplicar-respuestas-cuadro"' + (habilitado ? "" : " disabled") + ">Aplicar respuestas</button>" +
      "</div>"
    );
  }

  function actualizarBotonAplicarCuadro() {
    var t = state.cuadroTabla;
    var btn = document.getElementById("btn-aplicar-respuestas-cuadro");
    if (!t || !btn) return;
    btn.disabled = !todasLasSolicitudesResueltas(t.solicitudes, t.valores, t.asignaciones);
  }

  // Fase 6b/6d: aplica las respuestas del formulario inline SOBRE LA TABLA
  // EN PANTALLA, vía `/api/cuadro-superficies/estado` (cálculo puro, nunca
  // escribe ni descarga un DXF -- para eso está
  // `descargarCuadroCompletoDesdeTabla`, aparte y opcional). Las respuestas
  // se acumulan en `state.cuadroTabla.respuestasAplicadas`: cada llamada
  // reenvía el DXF entero desde cero (esta app no guarda el archivo en el
  // servidor), así que hay que volver a mandar también lo ya contestado.
  function aplicarRespuestasCuadroInline() {
    if (!state.archivoAnalizado || !state.cuadroTabla) return;
    var t = state.cuadroTabla;
    var respuestasNuevas = construirRespuestasCuadro(t.solicitudes, t.valores, t.asignaciones);
    var btn = document.getElementById("btn-aplicar-respuestas-cuadro");
    if (btn) btn.disabled = true;

    var respuestasAcumuladas = (t.respuestasAplicadas || []).concat(respuestasNuevas);
    var formData = new FormData();
    formData.append("dxf", state.archivoAnalizado);
    formData.append("respuestas", JSON.stringify(respuestasAcumuladas));

    fetch("/api/cuadro-superficies/estado", { method: "POST", body: formData })
      .then(function (resp) {
        if (!resp.ok) {
          return resp.json().then(function (j) { throw new Error(j.error || "No se pudieron aplicar las respuestas."); });
        }
        return resp.json();
      })
      .then(function (payload) {
        state.cuadroTabla = {
          celdas: payload.celdas || [], solicitudes: payload.solicitudes || [],
          cargando: false, error: null, respuestasAplicadas: respuestasAcumuladas,
          valores: {}, asignaciones: {}, pendientes: {},
        };
        refrescarVistaCuadro();
      })
      .catch(function (err) {
        alert((err && err.message) || "No se pudieron aplicar las respuestas.");
      })
      .then(function () {
        if (btn) btn.disabled = false;
      });
  }

  // Acción APARTE y opcional (petición explícita de Pablo: responder el
  // formulario no debe forzar una descarga) -- solo aparece en el modo
  // "Cuadro" cuando ya no queda ninguna solicitud pendiente. Reenvía las
  // mismas `respuestasAplicadas` que ya se ven en la tabla; `exportar-
  // cuadro-superficies-completo` (Fase 5c) es el único sitio que escribe
  // de verdad una copia del DXF.
  function descargarCuadroCompletoDesdeTabla() {
    if (!state.archivoAnalizado || !state.cuadroTabla) return;
    var respuestas = state.cuadroTabla.respuestasAplicadas || [];
    var btn = document.getElementById("btn-descargar-cuadro-completo");
    if (btn) btn.disabled = true;

    var nombreDescarga = state.archivoAnalizado.name.replace(/\.dxf$/i, "") + "_ArchMuse_completo.dxf";
    var formData = new FormData();
    formData.append("dxf", state.archivoAnalizado);
    formData.append("respuestas", JSON.stringify(respuestas));

    fetch("/api/exportar-cuadro-superficies-completo", { method: "POST", body: formData })
      .then(function (resp) {
        if (!resp.ok) {
          return resp.json()
            .then(function (j) { throw new Error(j.error || "No se pudo generar el DXF completo."); })
            .catch(function (e) { throw e instanceof Error ? e : new Error("No se pudo generar el DXF completo."); });
        }
        return resp.blob();
      })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = nombreDescarga;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      })
      .catch(function (err) {
        alert((err && err.message) || "No se pudo generar el DXF completo.");
      })
      .then(function () {
        if (btn) btn.disabled = false;
      });
  }

  // `#inspector` y `#cad-cuadro-superficies` se reconstruyen enteros cada
  // vez que `renderWorkspace()` rehace `viewRoot.innerHTML` (no son nodos
  // estables) -- así que nada dentro de ellos puede cablearse una vez por
  // id/clase de la forma habitual. Delegación sobre `viewRoot` (ese sí es
  // estable, ver su declaración), cableada una sola vez:
  //   - click: acciones (`data-accion`, vía `ACCIONES_CAD`) -- filtrado a
  //     estos dos contenedores para no disparar dos veces las del ribbon
  //     (que ya gestiona su propio listener en `wireRibbon`).
  //   - input/change: el formulario inline del cuadro (Fase 6d -- ya no
  //     vive en un modal aparte), SOLO dentro de `#cad-cuadro-superficies`
  //     (la vista pequeña del inspector no repite el formulario, ver
  //     `toolCuadroSuperficiesHtml`).
  function wireInspectorAcciones() {
    viewRoot.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-accion]");
      if (!btn || !btn.closest("#inspector, #cad-cuadro-superficies")) return;
      var accion = ACCIONES_CAD[btn.dataset.accion];
      if (accion) accion();
    });

    viewRoot.addEventListener("input", function (e) {
      var t = state.cuadroTabla;
      if (!t || !e.target.closest("#cad-cuadro-superficies") || !e.target.matches(".cuadro-input-numerico")) return;
      t.valores[e.target.dataset.campo] = e.target.value;
      actualizarBotonAplicarCuadro();
    });

    viewRoot.addEventListener("change", function (e) {
      if (e.target.id === "concurso-pliego-select") {
        if (e.target.value) ejecutarVerificacionPliego(e.target.value);
        return;
      }
      var t = state.cuadroTabla;
      if (!t || !e.target.closest("#cad-cuadro-superficies") ||
          e.target.tagName !== "SELECT" || !e.target.dataset.solicitud) return;
      var sid = e.target.dataset.solicitud;
      t.asignaciones[sid] = t.asignaciones[sid] || {};
      t.asignaciones[sid][e.target.dataset.campo] = e.target.value;
      actualizarBotonAplicarCuadro();
    });
  }

  wireInspectorAcciones();
  wireSidebar();
  wireChecklistCampo();
  wireViabilidadEconomica();
  wireChecklistCte();
  wireConversacion();

  // Fase 6 (sesión 2026-08-19, noche 5, petición directa de Pablo): "/"
  // abre la conversación sola, sin ningún clic previo -- el usuario no
  // encontraba el botón dentro del ribbon. `/proyectos` conserva la
  // portada clásica (subir DXF, analizar, listado de viviendas) intacta;
  // es el mismo `index.html` en ambas rutas (ver `app.py`), así que la
  // única diferencia de arranque es esta. El panel ya trae su propio
  // selector de DXF (`#conv-dxf`) y funciona sin ningún proyecto
  // analizado -- `abrirConversacion()` no depende de `state.archivoAnalizado`.
  if (window.location.pathname === "/") {
    abrirConversacion();
  }

  restaurarColapso();
  restaurarInspectorPlegado();

  // Puente cross-módulo: el visor de edificio completo (`ArchmuseViewer3D`,
  // otro `<script type="module">`, sin acceso a este scope) dispara este evento al hacer
  // click en una habitación durante el hover 3D (NAVEGACIÓN) — aquí se
  // traduce a "seleccionar esa vivienda y bajar al panel de problemas".
  // Cableado una sola vez sobre `document`, mismo motivo que `wireSidebar`.
  document.addEventListener("archmuse-3d-select-room", function (e) {
    var viviendaId = e.detail && e.detail.viviendaId;
    if (!viviendaId || !state.data) return;
    selectVivienda(viviendaId);
    // Con el inspector contextual ya no hay a dónde hacer scroll: se abre
    // directamente el modo "Problemas", que es el destino que este puente
    // buscaba.
    setModo("problemas");
  });

  // Escape: cierra el panel flotante si lo hay, y si no suelta el foco. Es
  // una de las tres salidas del foco (las otras son "volver" y el vacío del
  // plano). Cableado una sola vez sobre `document` por el mismo motivo que
  // los dos puentes de arriba.
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    if (document.querySelector(".float-panel")) return;  // lo gestiona el propio panel
    if (state.data && state.seleccion) soltarFoco();
  });

  // Arranque: el Inicio es la parrilla de proyectos, no el formulario de
  // subida (v3 §2.2). `renderInicio` cae a `renderUpload` por sí solo cuando
  // no hay nada guardado — un usuario nuevo entra directo a lo único que
  // puede hacer, sin ver una parrilla vacía por el camino.
  renderInicio();
})();
