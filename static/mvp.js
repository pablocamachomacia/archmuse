// La vista de tres zonas del MVP (informe ejecutivo del 2026-08-19).
//
// Regla de este fichero: **no calcula nada**. Pide, pinta y vuelve a pedir.
// Cualquier cifra que aparezca en pantalla viene de un endpoint; si alguna vez
// hace falta una que no venga, lo que falta es un endpoint, no una linea aqui.
//
// La separacion de la pestana Normativa --comprobado contra estimado-- es una
// decision de producto de Pablo del 2026-08-19, no una eleccion de formato:
// los parametros urbanisticos se comprueban con aritmetica exacta contra lo que
// el usuario introdujo; las reglas de `evaluator.py` llevan umbrales que no
// salen de ninguna fuente citada, asi que se ensenan como indicadores de
// diseno. Presentar las segundas como cumplimiento normativo es el modo de
// fallo nº1 del producto.

const $ = (id) => document.getElementById(id);
const estado = { parametros: null, alternativas: [], parametricas: [],
                 envolvente: null, seleccionada: null, ocupado: false };

const num = (id) => Number($(id).value) || 0;

// Todo lo que se interpola en `innerHTML` pasa por aqui. No es paranoia de
// libro: los nombres de estancia los redacta el generador (un modelo de
// lenguaje) y la ciudad la escribe el usuario, asi que ninguno de los dos es
// texto de confianza. El unico HTML que se inserta sin escapar es el SVG del
// plano, que lo produce `analyzer/plan_svg.py` a partir de geometria --no de
// texto libre-- y va marcado abajo donde se usa.
const esc = (v) => (v == null ? "" : String(v).replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])));

function leerParametros() {
  return {
    proyecto: { ciudad: $("ciudad").value.trim(), tipologia: "plurifamiliar" },
    solar: {
      superficie_m2: num("solar"), forma: "rectangular",
      ancho_m: num("ancho"), largo_m: num("largo"), norte_grados: num("norte"),
    },
    edificio: { plantas: num("plantas"), altura_libre_m: 2.8, planta_baja_comercial: false },
    mix_viviendas: {
      dorm_1: num("d1"), dorm_2: num("d2"), dorm_3: num("d3"),
      superficie_minima_m2: num("supmin"),
    },
    normativa: {
      ocupacion_maxima_pct: num("ocupacion"), retranqueos_m: num("retranqueos"),
      edificabilidad_maxima: num("edificabilidad") || null,
      plantas_maximas: num("plantasmax") || null,
    },
    superficie_objetivo_m2: num("objetivo"),
  };
}

function escribirParametros(p) {
  if (!p) return;
  const m = p.mix_viviendas || {}, e = p.edificio || {};
  if (m.dorm_1 != null) $("d1").value = m.dorm_1;
  if (m.dorm_2 != null) $("d2").value = m.dorm_2;
  if (m.dorm_3 != null) $("d3").value = m.dorm_3;
  if (e.plantas != null) $("plantas").value = e.plantas;
  if (p.superficie_objetivo_m2 != null) $("objetivo").value = p.superficie_objetivo_m2;
}

// --- Chat ------------------------------------------------------------------

function decir(texto, clase) {
  const d = document.createElement("div");
  d.className = "msg " + (clase || "am");
  d.textContent = texto;
  $("chat").appendChild(d);
  $("chat").scrollTop = $("chat").scrollHeight;
  return d;
}

// --- Pestanas --------------------------------------------------------------

$("pestanas").addEventListener("click", (ev) => {
  const b = ev.target.closest("button[data-p]");
  if (!b) return;
  for (const otro of $("pestanas").children) otro.setAttribute("aria-selected", String(otro === b));
  for (const p of ["alternativas", "distribucion", "analisis", "normativa", "costes", "exportar"]) {
    $("p-" + p).classList.toggle("oculto", p !== b.dataset.p);
  }
});

// --- Generacion ------------------------------------------------------------

$("btnGenerar").addEventListener("click", async () => {
  if (estado.ocupado) return;
  estado.parametros = leerParametros();
  if (!estado.parametros.solar.superficie_m2) { alert("Indica la superficie del solar."); return; }
  // Primero las CUATRO alternativas parametricas: son aritmetica sobre lo que
  // el arquitecto acaba de introducir, salen al instante y no cuestan un token.
  // La colocacion de estancias --que si llama al modelo y tarda-- va despues y
  // es opcional.
  await derivarAlternativas();
});

async function derivarAlternativas() {
  $("estado").textContent = "Derivando alternativas…";
  try {
    const r = await fetch("/api/alternativas", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parametros: estado.parametros }),
    });
    const datos = await r.json();
    estado.envolvente = datos.envolvente || null;
    estado.parametricas = datos.alternativas || [];
    pintarParametricas(datos);
    $("estado").textContent = estado.parametricas.length
      ? estado.parametricas.length + " alternativa(s) derivadas"
      : "Faltan parámetros";
  } catch (exc) {
    $("p-alternativas").innerHTML = '<div class="vacio">No se han podido derivar: ' +
      esc(exc.message || exc) + "</div>";
  }
}

function pintarParametricas(datos) {
  const cont = $("p-alternativas");
  const env = datos.envolvente || {};
  let html = "<h2>Envolvente edificable</h2>";
  if (!env.techo_construible_m2) {
    html += "<div class='nota'>No se puede calcular la envolvente. Falta: <b>" +
      esc((datos.faltan || []).join(", ")) + "</b>. Sin ella no se deriva ninguna " +
      "alternativa: repartir un techo que no se ha podido calcular sería inventar " +
      "la cifra de la que cuelga todo lo demás.</div>";
    cont.innerHTML = html;
    return;
  }
  html += "<div class='tarjeta'><div class='metricas'>" +
    "<div class='metrica'><div class='v'>" + esc(env.superficie_ocupable_m2) +
    "</div><div class='e'>huella ocupable m²</div></div>" +
    "<div class='metrica'><div class='v'>" + esc(env.superficie_edificable_m2) +
    "</div><div class='e'>techo edificab. m²</div></div>" +
    "<div class='metrica'><div class='v'>" + esc(env.techo_construible_m2) +
    "</div><div class='e'>construible m²</div></div>" +
    "</div><details style='margin-top:10px'><summary style='cursor:pointer;font-size:12px;color:var(--tenue)'>" +
    "de dónde sale cada cifra</summary><ul class='lista' style='margin-top:8px'>" +
    (env.procedencia || []).map((x) => "<li>" + esc(x) + "</li>").join("") +
    "</ul></details></div>";

  html += "<h2>Alternativas</h2><div class='alternativas'>";
  for (const a of datos.alternativas || []) {
    const m = a.mix_viviendas || {};
    html += "<div class='tarjeta'><h3>" + esc(a.etiqueta) + " · " + esc(a.titulo) +
      "<span>" + esc(a.viviendas) + " viviendas</span></h3>" +
      "<div class='metricas'>" +
      "<div class='metrica'><div class='v'>" + esc(m.dorm_1 || 0) +
      "</div><div class='e'>1 dorm.</div></div>" +
      "<div class='metrica'><div class='v'>" + esc(m.dorm_2 || 0) +
      "</div><div class='e'>2 dorm.</div></div>" +
      "<div class='metrica'><div class='v'>" + esc(m.dorm_3 || 0) +
      "</div><div class='e'>3 dorm.</div></div></div>" +
      "<div style='font-size:12px;color:var(--tenue);margin-top:8px'>" +
      esc(a.superficie_repartida_m2) + " m² repartidos</div>" +
      "<details style='margin-top:8px'><summary style='cursor:pointer;font-size:11.5px;color:var(--tenue)'>" +
      "procedencia</summary><ul class='lista' style='margin-top:6px'>" +
      (a.procedencia || []).map((x) => "<li style='font-size:11.5px'>" + esc(x) + "</li>").join("") +
      "</ul></details></div>";
  }
  html += "</div>";
  html += "<div class='nota'>Estas cuatro salen de <b>multiplicar y comparar los parámetros " +
    "que has introducido</b>. Ni una llamada a un modelo, ni una decisión de diseño. " +
    "La distribución de estancias dentro de cada planta es otra cosa y no está aquí.</div>";
  cont.innerHTML = html;
}

async function generar(mensaje) {
  estado.ocupado = true;
  $("btnGenerar").disabled = true;
  $("estado").textContent = mensaje;
  $("p-distribucion").innerHTML = FRANJA_SIN_AUDITAR + '<div class="vacio">' + mensaje +
    " Cada alternativa es una llamada al generador, así que tarda.</div>";
  try {
    const r = await fetch("/api/generar-opciones", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(estado.parametros),
    });
    const datos = await r.json();
    if (!r.ok) throw new Error(datos.error || "no se han podido generar las alternativas");
    estado.alternativas = Object.entries(datos.opciones || {}).map(([etiqueta, o]) =>
      Object.assign({ etiqueta }, o));
    if (!estado.alternativas.length) throw new Error("el generador no ha devuelto ninguna opción");
    estado.seleccionada = estado.alternativas.find((a) => !a.error) || null;
    await cargarSeleccionada();
    pintarTodo();
    $("estado").textContent = estado.alternativas.length + " alternativa(s)";
  } catch (exc) {
    $("p-distribucion").innerHTML = FRANJA_SIN_AUDITAR + '<div class="vacio">No se ha podido generar: ' +
      esc(exc.message || exc) + "</div>";
    $("estado").textContent = "Error";
  } finally {
    estado.ocupado = false;
    $("btnGenerar").disabled = false;
  }
}

async function cargarSeleccionada() {
  // El proyecto completo (planos, viviendas, urbanismo) se pide aparte: el
  // endpoint de opciones solo devuelve el id y las metricas comparativas.
  if (!estado.seleccionada || !estado.seleccionada.proyecto_id) return;
  const r = await fetch("/api/proyectos/" + estado.seleccionada.proyecto_id);
  if (r.ok) estado.seleccionada.payload = await r.json();
}

// --- Pintado ---------------------------------------------------------------

const pct = (v) => (v == null ? "—" : Number(v).toFixed(1) + " %");

// La franja que acompana a TODO lo que sale del generador. Esta en una constante
// y no repetida a mano porque el dia que se retoque, se retoca en los cinco
// sitios a la vez o deja de estar en alguno --y el que se quede sin ella es el
// que enganara a alguien--.
const FRANJA_SIN_AUDITAR =
  "<div class='franja-sin-auditar'><b>Sin auditar.</b> Esto lo ha colocado un " +
  "modelo de lenguaje: la distribución de estancias es criterio propio del " +
  "generador y <b>no se deriva de ningún parámetro comprobable</b>, así que no " +
  "lleva procedencia y ArchMuse no responde de ella. Las alternativas de la " +
  "pestaña <b>Alternativas</b> son otra cosa: aritmética sobre lo que has " +
  "introducido, con la procedencia de cada cifra.</div>";

function pintarTodo() {
  pintarDistribucion();
  pintarAnalisis();
  pintarNormativa();
  pintarCostes();
  pintarExportar();
}

function pintarDistribucion() {
  // OJO: `#p-distribucion`, NO `#p-alternativas`. Lo que se pinta aqui sale de
  // `analyzer/ai_generator.py` --el modelo coloca las estancias-- y lo que se
  // pinta alli sale de `analyzer/alternativas.py` --aritmetica con procedencia--.
  // Compartieron contenedor hasta el 2026-08-19 y el segundo borraba al primero
  // sin decirlo: cuatro tarjetas identicas, respaldos distintos.
  const cont = $("p-distribucion");
  cont.innerHTML = FRANJA_SIN_AUDITAR + "<h2>Distribución propuesta por el generador</h2>";
  const grid = document.createElement("div");
  grid.className = "alternativas";
  for (const alt of estado.alternativas) {
    const t = document.createElement("div");
    t.className = "tarjeta" + (alt === estado.seleccionada ? " sel" : "");
    if (alt.error) {
      t.innerHTML = "<h3>" + esc(alt.etiqueta) + "</h3><div class='malo'>" + esc(alt.error) + "</div>";
    } else {
      const m = alt.metricas || {}, mg = m.margen_estimado || {};
      const mix = alt.mix_viviendas || {};
      const viv = (mix.dorm_1 || 0) + (mix.dorm_2 || 0) + (mix.dorm_3 || 0);
      t.innerHTML =
        "<h3>" + esc(alt.etiqueta) + "<span>" + viv + " viviendas</span></h3>" +
        "<div class='metricas'>" +
        "<div class='metrica'><div class='v'>" + pct(m.repercusion_zonas_comunes_pct) +
        "</div><div class='e'>zonas comunes</div></div>" +
        "<div class='metrica'><div class='v'>" + pct(m.pct_fachada_aprovechada) +
        "</div><div class='e'>fachada útil</div></div>" +
        "<div class='metrica'><div class='v'>" + pct(mg.margen_pct) +
        "</div><div class='e'>margen est.</div></div>" +
        "</div>";
      t.style.cursor = "pointer";
      t.addEventListener("click", async () => {
        estado.seleccionada = alt;
        await cargarSeleccionada();
        pintarTodo();
      });
    }
    grid.appendChild(t);
  }
  cont.appendChild(grid);

  const p = estado.seleccionada && estado.seleccionada.payload;
  if (p && p.viviendas) {
    const planos = document.createElement("div");
    planos.className = "planos";
    for (const v of p.viviendas.slice(0, 6)) {
      const d = document.createElement("div");
      d.className = "plano";
      // El SVG viene de `plan_svg.py`, generado desde geometria, no desde texto
      // libre: es el unico HTML que se inserta sin escapar, y a proposito.
      d.innerHTML = (v.svg || "") + "<div class='pie'>" + esc(v.nombre || "Vivienda") +
        " · " + (v.superficie_util_m2 != null ? esc(v.superficie_util_m2) + " m²" : "") + "</div>";
      planos.appendChild(d);
    }
    cont.appendChild(planos);
  }
  const aviso = document.createElement("div");
  aviso.className = "nota";
  aviso.textContent = "El margen estimado usa los precios que introduzcas tú. " +
    "ArchMuse no conoce ningún dato de mercado y no se inventa ninguno.";
  cont.appendChild(aviso);
}

function pintarAnalisis() {
  const p = estado.seleccionada && estado.seleccionada.payload;
  const c = $("p-analisis");
  if (!p) { c.innerHTML = '<div class="vacio">Genera una alternativa.</div>'; return; }
  const u = p.urbanismo || {};
  c.innerHTML = FRANJA_SIN_AUDITAR +
    "<h2>Análisis automático</h2><div class='tarjeta'><div class='metricas'>" +
    "<div class='metrica'><div class='v'>" + esc(u.superficie_solar_m2 ?? "—") +
    "</div><div class='e'>solar m²</div></div>" +
    "<div class='metrica'><div class='v'>" + esc(u.superficie_total_construida_m2 ?? "—") +
    "</div><div class='e'>construida m²</div></div>" +
    "<div class='metrica'><div class='v'>" + esc(u.edificabilidad_real ?? "—") +
    "</div><div class='e'>edificabilidad</div></div>" +
    "</div></div>" +
    "<h2>Viviendas</h2><ul class='lista'>" +
    (p.viviendas || []).map((v) =>
      "<li><b>" + esc(v.nombre || "Vivienda") + "</b> — " +
      (v.habitaciones || []).length + " piezas" +
      (v.superficie_util_m2 != null ? " · " + esc(v.superficie_util_m2) + " m² útiles" : "") +
      "</li>").join("") + "</ul>";
}

function pintarNormativa() {
  const p = estado.seleccionada && estado.seleccionada.payload;
  const c = $("p-normativa");
  if (!p) { c.innerHTML = '<div class="vacio">Genera una alternativa.</div>'; return; }

  // COMPROBADO: aritmetica exacta contra los parametros que introdujo el
  // usuario. Aqui si se puede decir "cumple" o "no cumple".
  const edificio = p.problemas_edificio || [];
  // Matiz que hay que decir y no es evidente: la comprobacion urbanistica SI es
  // aritmetica exacta, pero se aplica sobre una geometria que propuso el
  // generador. El calculo esta auditado; lo que se mide, no.
  let html = FRANJA_SIN_AUDITAR +
    "<h2>Comprobado — parámetros urbanísticos</h2>" +
    "<div class='nota'>Aritmética exacta <b>sobre la distribución que propuso el " +
    "generador</b>: el cálculo está auditado, la geometría que mide no. Si cambias " +
    "de distribución, estas cifras cambian.</div>";
  html += edificio.length
    ? "<ul class='lista'>" + edificio.map((x) =>
        "<li><span class='pill malo'>revisar</span>" + esc(x.mensaje || x) + "</li>").join("") + "</ul>"
    : "<ul class='lista'><li><span class='pill ok'>cumple</span>" +
      "Ocupación, edificabilidad y número de plantas dentro de lo que has declarado.</li></ul>";

  // INDICADORES: las reglas de `evaluator.py`. Sus umbrales NO salen de una
  // fuente citada, asi que no se presentan como cumplimiento normativo.
  const problemas = [];
  for (const v of p.viviendas || []) {
    for (const h of v.habitaciones || []) {
      for (const pr of h.problemas || []) {
        problemas.push(String(v.nombre || "Vivienda") + " · " + String(h.nombre || "") + ": " + String(pr));
      }
    }
  }
  html += "<h2>Indicadores de diseño — no es verificación normativa</h2>" +
    "<div class='nota'>Estos umbrales están en el código de ArchMuse y <b>no llevan cita " +
    "de fuente oficial</b>. Son criterios de diseño útiles, no cumplimiento del CTE. " +
    "El corpus normativo de ArchMuse tiene hoy una regla y está sin firmar por un " +
    "colegiado, así que ArchMuse no afirma nada sobre normativa.</div>";
  html += problemas.length
    ? "<ul class='lista'>" + problemas.slice(0, 40).map((x) =>
        "<li><span class='pill aviso'>indicador</span>" + esc(x) + "</li>").join("") + "</ul>"
    : "<ul class='lista'><li>Ningún indicador de diseño ha saltado.</li></ul>";

  const limitaciones = p.limitaciones || [];
  if (limitaciones.length) {
    html += "<h2>No se ha podido comprobar</h2><ul class='lista'>" +
      limitaciones.map((x) => "<li>" + esc(x.mensaje || x) + "</li>").join("") + "</ul>";
  }
  c.innerHTML = html;
}

function pintarCostes() {
  const c = $("p-costes");
  if (!estado.alternativas.length) { c.innerHTML = '<div class="vacio">Genera una alternativa.</div>'; return; }
  c.innerHTML = FRANJA_SIN_AUDITAR + "<h2>Comparativa económica</h2>" +
    "<div class='nota'>Todas las cifras salen de los precios que introduzcas. " +
    "ArchMuse no conoce el mercado y no inventa un valor por defecto.</div>" +
    "<ul class='lista'>" + estado.alternativas.filter((a) => !a.error).map((a) => {
      const mg = (a.metricas || {}).margen_estimado || {};
      return "<li><b>" + esc(a.etiqueta) + "</b> — margen " + pct(mg.margen_pct) +
        " · inversión " + esc(mg.inversion_total ?? "—") + "</li>";
    }).join("") + "</ul>";
}

function pintarExportar() {
  const p = estado.seleccionada && estado.seleccionada.payload;
  const c = $("p-exportar");
  if (!p) { c.innerHTML = '<div class="vacio">Genera una alternativa.</div>'; return; }
  // Los exportadores existen (`/api/exportar-ifc-planta`, `/api/dossier-pdf`,
  // `/api/exportar-cuadro-superficies`) pero son POST con su propio cuerpo, y
  // cablearlos bien es mas trabajo del que cabe aqui. Se dice lo que hay y lo
  // que falta: un enlace roto en una demo cuesta mas que un apartado honesto.
  c.innerHTML = FRANJA_SIN_AUDITAR +
    "<h2>Exportar</h2>" +
    "<ul class='lista'>" +
    "<li><b>Espacios IFC4 (BIM)</b> — disponible en ArchMuse, aún no conectado a esta vista</li>" +
    "<li><b>Dossier de inversión en PDF</b> — disponible, aún no conectado a esta vista</li>" +
    "<li><b>Cuadro de superficies sobre DXF</b> — disponible, aún no conectado a esta vista</li>" +
    "</ul>" +
    "<div class='nota'>Todo lo que ArchMuse genera sale marcado como <b>borrador para " +
    "revisión de un arquitecto colegiado</b>, sin opción de quitarlo. ArchMuse asesora; " +
    "no firma.</div>";
}

// --- Copiloto --------------------------------------------------------------

$("entrada").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const texto = $("peticion").value.trim();
  if (!texto || estado.ocupado) return;
  $("peticion").value = "";
  decir(texto, "yo");

  if (!estado.parametros) { decir("Primero genera unas alternativas.", "am"); return; }

  const pensando = decir("…", "am");
  try {
    const r = await fetch("/api/copiloto", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        peticion: texto,
        parametros: estado.parametros,
        alternativas: estado.alternativas.map((a) => ({
          etiqueta: a.etiqueta, metricas: a.metricas,
        })),
      }),
    });
    const datos = await r.json();
    if (!r.ok) { pensando.textContent = datos.error || "No he podido atender la petición."; return; }
    pensando.textContent = datos.texto || "(sin respuesta)";

    // Lo que se ejecuto, dicho. Un cambio de proyecto no ocurre en silencio.
    for (const paso of datos.pasos || []) {
      decir((paso.ok ? "✓ " : "✗ ") + paso.capacidad + " · " +
        JSON.stringify(paso.argumentos.argumentos || {}), "sis");
    }
    if (datos.cifras_sin_respaldo && datos.cifras_sin_respaldo.length) {
      decir("Aviso: hay cifras en esa respuesta que no he podido rastrear hasta " +
        "una herramienta (" + datos.cifras_sin_respaldo.join(", ") + "). No te fíes de ellas.", "sis");
    }

    if (datos.hubo_cambio && datos.parametros) {
      estado.parametros = datos.parametros;
      escribirParametros(datos.parametros);
      // Primero lo auditado: si no se rederiva, la pestana Alternativas se
      // queda enseñando el reparto del encargo ANTERIOR sin decirlo.
      await derivarAlternativas();
      if (datos.hay_que_regenerar) {
        decir("Regenerando con el cambio…", "sis");
        await generar("Regenerando…");
      }
    }
  } catch (exc) {
    pensando.textContent = "Error: " + String(exc.message || exc);
  }
});
