"""API REST de Archmuse: `POST /api/analizar` analiza un DXF subido y
`POST /api/generar` genera un proyecto residencial completo con IA a partir
de unos parámetros (solar, edificio, mix de viviendas, normativa) — ambos
devuelven JSON puro con la misma forma (ver `analyzer/api_serializer.py`),
consumido por la SPA (`static/index.html`) en el navegador. Flask no
renderiza HTML — solo sirve el archivo estático de la SPA y la API.

Uso:
    python app.py

Luego abre http://127.0.0.1:5000 en el navegador.
"""
from __future__ import annotations

import dataclasses
import io
import json
import logging
import os
import shutil
import tempfile
from typing import Optional

from flask import Flask, Response, jsonify, request
from werkzeug.utils import secure_filename

from analyzer.ai_analyst import AIAnalysis, analyze_with_ai, build_viviendas_payload_from_proyecto
from analyzer.ai_generator import GenerationError, generate_project, derivar_mixes_alternativos
from analyzer.comparador_opciones import calcular_metricas_opcion
from analyzer.altura_evacuacion import normalizar_declaracion_altura
from analyzer.altura_evacuacion import resolver_altura_evacuacion
from analyzer.api_serializer import serialize_ai_analysis, serialize_analysis
from analyzer.avisos_altura_evacuacion import avisos_altura_evacuacion
from analyzer.checklist_campo import generar_checklist_campo
from analyzer.cte_zonas import get_densidad_urbana, resolver_zona_cte
# Fase 4 (cuadro de superficies): se reutilizan tal cual las dos piezas de
# las Fases 2/3 -- este módulo no reimplementa ninguna detección ni cálculo
# de superficie, solo las expone por HTTP.
from analyzer.cuadro_superficies import detectar_cuadro_superficies
from analyzer.cuadro_superficies_export import exportar_cuadro_relleno, obtener_estado_cuadro, obtener_solicitudes
from analyzer.dxf_export import exportar_planta_dxf
from analyzer.dossier_pdf import generar_dossier_pdf
from analyzer.ifc_export import exportar_espacios_ifc
from analyzer.feasibility import (
    CostesPromotor,
    analisis_sensibilidad,
    calcular_cash_flow_estatico,
    calcular_margen_promotor,
    ratio_eficiencia_superficie,
)
from analyzer.evaluator import (
    _PLANTA_NAME_PATTERN,
    asignar_envolvente_cerrada,
    asignar_superficies_exteriores,
    classify_problems,
    compute_floor_areas,
    compute_floor_perimeter_m,
    evaluate_advanced,
    evaluate_advanced_for_units,
    evaluate_buildability,
    evaluate_building_compactness,
    evaluate_building_orientation_ratio,
    evaluate_ceiling_height,
    evaluate_max_floors,
    evaluate_retranqueos,
    evaluate_solar_occupation,
)
from analyzer.entorno import cargar_dotenv
from analyzer.escala import factor_de_unidad
from analyzer.parser import (
    CAPA_CONSTRUIDA_CERRADA,
    CAPA_CONSTRUIDA_EXTERIOR,
    CAPA_UTIL_EXTERIOR,
    CAPA_UTIL_INTERIOR,
    CAPAS_AM_OPERATIVAS,
    CapaIndeterminada,
    EscalaIndeterminada,
    leer_plano,
    load_document,
)
from analyzer.validacion_capas import validar_capas_am
from analyzer.pdf_report import generate_pdf
from analyzer.ocupacion import ocupacion as calcular_ocupacion
from analyzer.planta import ORIGEN_CONVENCION_NOMBRE
from analyzer.planta import ORIGEN_DECLARADO
from analyzer.planta import normalizar_declaracion_planta
from analyzer.planta import planta as calcular_planta
from analyzer.sectorizacion import limite_superficie_sector
from analyzer.superficie_util import superficie_util_db_si, superficie_util_ocupable_db_si
from analyzer.uso_previsto import ZonaDeUso, usos_por_zona
from analyzer.storage import (
    borrar_proyecto,
    guardar_entrevista,
    guardar_pliego,
    guardar_proyecto,
    guardar_sitio,
    guardar_traza_generacion,
    init_db,
    listar_pliegos,
    listar_proyectos,
    obtener_entrevista,
    obtener_pliego,
    obtener_proyecto,
    obtener_solido_capaz,
    obtener_sitio_de_proyecto,
    obtener_sitio_por_clave,
    vincular_pliego_proyecto,
    vincular_sitio_proyecto,
)
from analyzer.pliego_extractor import ErrorDeExtraccionPliego, extraer_parametros_pliego
from analyzer.pliego_verificador import verificar_cumplimiento
from analyzer.pliego_conector import pliego_a_params
from analyzer.sitio import (
    ErrorDeSitio, GeocodificacionNoConfigurada, edificios_colindantes_geometria,
    entorno_overpass_por_coordenadas, geocodificar_direccion,
    geometria_parcela_por_coordenadas, obtener_datos_parcela,
)
from analyzer.normativa_madrid import normativa_urbanistica_por_coordenadas
from analyzer.estilos import CATALOGO_ESTILOS, DEFAULT_ESTILO, ErrorDeEstilo, obtener_estilo
from analyzer.gltf_exporter import ErrorDeExportacionGltf, calcular_georreferencia, exportar_proyecto_a_glb
from analyzer.hechos import hecho_a_dict
from modelo import constructor as modelo_constructor

# --- Entrevistador (Fase B) --------------------------------------------
#
# Import aislado a propósito, mismo principio que las Fases A/C/D: `app.py`
# nunca importa `anthropic` directamente ni construye lógica de motor/
# compilador propia — solo adapta HTTP <-> `analyzer.interview.*`, que ya
# hace todo el trabajo real. Ver `_construir_interprete_entrevista()` más
# abajo para el único punto donde se construye (o no) un cliente de Claude.
from analyzer.interview import compilador as interview_compilador
from analyzer.interview import modelo as interview_modelo
from analyzer.interview import motor as interview_motor
from analyzer.interview.claude_interprete import ClienteAnthropicInterprete, InterpretacionError

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB

logger = logging.getLogger(__name__)

# El `.env` local, antes de que nada mire el entorno: `init_db()` ya consulta
# ARCHMUSE_DATA_DIR, y los endpoints leen ANTHROPIC_API_KEY y MAPBOX_TOKEN.
# Lo ya exportado en el shell gana sobre el archivo -- ver analyzer/entorno.py.
cargar_dotenv()

init_db()


@app.after_request
def _sin_cache_en_estaticos(response):
    """Herramienta interna en desarrollo activo: `app.js`/`style.css`/
    `index.html` cambian varias veces por sesión, y el caché heurístico del
    navegador (sin `Cache-Control` explícito, Flask solo manda ETag/
    Last-Modified) ha hecho más de una vez que el navegador siguiera
    sirviendo una versión vieja tras recargar -- confusión real ya vivida
    en esta misma sesión ("no hace nada", "sigue sin...", cuando el cambio
    ya estaba hecho, solo que el navegador no lo había pedido de nuevo).
    `no-store` para que cada carga sea siempre la versión real del disco."""
    if request.path == "/" or request.path.endswith((".js", ".css", ".html")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/")
def index():
    """Desde el 2026-08-19 (noche 5, petición directa de Pablo) "/" abre
    directamente el panel de conversación, no la portada de subir/analizar
    un plano -- el usuario no encontraba el botón "Preguntar a ArchMuse"
    dentro del ribbon. Es el mismo `index.html` que `/proyectos`: la
    decisión de qué se ve primero la toma el JS por `location.pathname`
    (ver el arranque de `static/app.js`), para no mantener dos copias de la
    SPA. `/api/preguntar` y la Skill no cambian -- esto es sólo qué se sirve
    en la raíz."""
    return app.send_static_file("index.html")


@app.route("/proyectos")
def proyectos():
    """La portada clásica (subir DXF, analizar, navegar el listado de
    viviendas): vivía en "/" hasta hoy. Mismo fichero que "/" -- ver el
    docstring de `index()`."""
    return app.send_static_file("index.html")


@app.route("/mvp")
def mvp():
    """La vista de tres zonas del informe ejecutivo del 2026-08-19.

    Ruta aparte y NO en `/`: la SPA de siempre sigue siendo la puerta de
    entrada mientras esta vista se prueba con arquitectos. Cambiar `/` es una
    decision de producto, y se toma cuando la prueba del §7 del informe diga
    que merece la pena.
    """
    return app.send_static_file("mvp.html")


@app.route("/api/config", methods=["GET"])
def config():
    """Configuración pública que el navegador necesita y `index.html` no
    puede llevar incrustada (es un archivo estático, sin renderizado de
    plantillas -- ver docstring del módulo). Hoy, un único valor:
    `MAPBOX_TOKEN` del entorno, para `static/visor-mapa.js`. Un token de
    Mapbox es público por diseño (se restringe por URL desde el panel de
    Mapbox, no es un secreto de servidor) -- `null` si no está configurado,
    nunca un valor inventado."""
    return jsonify(mapbox_token=os.environ.get("MAPBOX_TOKEN"))


@app.route("/api/proyectos", methods=["GET"])
def proyectos_lista():
    """Metadatos de todos los proyectos guardados, del más reciente al más
    antiguo. No incluye el payload: la parrilla del Inicio no necesita 288 KB
    por tarjeta."""
    return jsonify(proyectos=listar_proyectos())


@app.route("/api/proyectos/<proyecto_id>", methods=["GET"])
def proyecto_detalle(proyecto_id: str):
    """Payload completo, idéntico al que devolvió `/api/analizar` al crearlo.
    No parsea el DXF, no reevalúa reglas y no llama a la IA.

    Sólido Capaz persistente: si el proyecto tiene un snapshot guardado
    (`solido_capaz`, columna propia -- nunca dentro de `payload` en disco),
    se añade aquí a la respuesta. `None` en la columna (el caso mayoritario
    hoy) no añade la clave -- comportamiento idéntico al de antes de este
    PRD."""
    payload = obtener_proyecto(proyecto_id)
    if payload is None:
        return jsonify(error="Ese proyecto no existe o no se puede abrir."), 404
    solido_capaz = obtener_solido_capaz(proyecto_id)
    if solido_capaz is not None:
        payload = dict(payload, solido_capaz=solido_capaz)
    return jsonify(payload)


@app.route("/api/proyectos/<proyecto_id>", methods=["DELETE"])
def proyecto_borrar(proyecto_id: str):
    if not borrar_proyecto(proyecto_id):
        return jsonify(error="Ese proyecto no existe."), 404
    return jsonify(ok=True)


@app.route("/api/proyectos/<proyecto_id>/diagnostico-ia", methods=["POST"])
def proyecto_diagnostico_ia(proyecto_id: str):
    """Única vía para pedir el diagnóstico narrativo de IA (`ai_analyst.
    analyze_with_ai`) sobre un proyecto ya analizado -- `/api/analizar` y
    `/api/generar` ya no lo llaman solos. Se reconstruye la entrada desde
    el payload YA guardado (`build_viviendas_payload_from_proyecto`): no
    parsea el DXF ni reevalúa reglas, solo la llamada a Claude que el
    arquitecto ha pedido explícitamente al pulsar el botón.

    No se persiste en `storage` -- reabrir el proyecto sigue sin llamar a
    la IA (invariante de `storage.py`); si se quiere el diagnóstico otra
    vez, se vuelve a pedir. Deliberado: mantiene esta llamada como la
    única vía "bajo demanda", sin una segunda ruta silenciosa que la
    dispare al reabrir."""
    payload = obtener_proyecto(proyecto_id)
    if payload is None:
        return jsonify(error="Ese proyecto no existe o no se puede abrir."), 404

    viviendas_payload = build_viviendas_payload_from_proyecto(payload)
    if not viviendas_payload["viviendas"]:
        return jsonify(error="Este proyecto no tiene viviendas que analizar."), 400

    ai_analysis = analyze_with_ai(viviendas_payload)
    if ai_analysis is None:
        return jsonify(
            error="No se pudo generar el diagnóstico de IA (revisa ANTHROPIC_API_KEY o vuelve a intentarlo)."
        ), 502

    return jsonify(analisis_ia=serialize_ai_analysis(ai_analysis))


@app.route("/api/extraer-pliego", methods=["POST"])
def extraer_pliego():
    """Sube un PDF de pliego de concurso y devuelve sus parámetros
    extraídos (`analyzer.pliego_extractor`, una única llamada a Claude
    sobre el PDF completo). Se guarda de inmediato (`guardar_pliego`) como
    borrador SIN `proyecto_id` -- el botón vive en la pantalla de "nuevo
    proyecto", antes de que exista ningún proyecto que enlazar. Reabrirlo
    (`GET /api/pliegos/<id>`) nunca vuelve a llamar a la IA.

    No conecta con `ai_generator.py`/el entrevistador todavía -- eso es un
    PRD aparte (`docs/prd/2026-08-15-extractor-parametros-pliego.md` §14),
    sin aprobar."""
    file = request.files.get("pliego")
    if file is None or file.filename == "":
        return jsonify(error="Selecciona un archivo PDF antes de importar."), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify(error="El archivo debe tener extensión .pdf."), 400

    filename = secure_filename(file.filename) or "pliego.pdf"
    pdf_bytes = file.read()

    try:
        resultado = extraer_parametros_pliego(pdf_bytes, filename)
    except ErrorDeExtraccionPliego as exc:
        return jsonify(
            error="No se pudo extraer el pliego (%s). Revisa ANTHROPIC_API_KEY o vuelve a intentarlo." % exc
        ), 502

    parametros = {nombre: hecho_a_dict(h) for nombre, h in resultado.hechos.items()}
    if not resultado.es_pliego:
        return jsonify(
            error="Este PDF no parece un pliego de condiciones de concurso.",
            es_pliego=False,
            parametros=parametros,
        ), 400

    meta = guardar_pliego(filename, pdf_bytes, parametros, es_pliego=True)
    return jsonify(pliego=meta)


@app.route("/api/pliegos/<pliego_id>", methods=["GET"])
def pliego_detalle(pliego_id: str):
    """Un pliego ya extraído, idéntico a lo que devolvió `/api/extraer-pliego`
    al crearlo. No vuelve a llamar a la IA."""
    pliego = obtener_pliego(pliego_id)
    if pliego is None:
        return jsonify(error="Ese pliego no existe o no se puede abrir."), 404
    return jsonify(pliego=pliego)


@app.route("/api/pliegos", methods=["GET"])
def pliegos_lista():
    """Metadatos de todos los pliegos guardados (sin parámetros ni PDF) —
    para el selector "verificar contra un pliego" del panel de proyecto."""
    return jsonify(pliegos=listar_pliegos())


@app.route("/api/proyectos/<proyecto_id>/verificar-pliego/<pliego_id>", methods=["GET"])
def proyecto_verificar_pliego(proyecto_id: str, pliego_id: str):
    """Verifica un proyecto (analizado o generado) contra un pliego ya
    extraído -- `analyzer.pliego_verificador`, determinista, sin IA. No
    requiere que el proyecto se haya generado a partir de ese pliego."""
    proyecto = obtener_proyecto(proyecto_id)
    if proyecto is None:
        return jsonify(error="Ese proyecto no existe o no se puede abrir."), 404
    pliego = obtener_pliego(pliego_id)
    if pliego is None:
        return jsonify(error="Ese pliego no existe o no se puede abrir."), 404

    verificacion = verificar_cumplimiento(proyecto, pliego["parametros"])
    return jsonify(verificacion=dataclasses.asdict(verificacion))


@app.route("/api/geocodificar", methods=["GET"])
def geocodificar():
    """"Mapa/Parcela Primero": buscador de dirección/municipio del
    MapPicker (`static/map-picker.js`). Proxy fino sobre `analyzer.sitio.
    geocodificar_direccion`, que desde la tarea `TL-8` llama a Mapbox y no a
    Nominatim (cuya instancia pública prohíbe el uso comercial).

    Sigue pasando por el servidor y no por el navegador para que el filtro por
    país y el tope de resultados los ponga ArchMuse, no el frontend: es la
    cuota de Mapbox que paga ArchMuse la que se está gastando.

    Sin caché propia: a diferencia de `/api/analizar-sitio` (Catastro/Overpass,
    mucho más lento y con rate limiting observado en vivo), el geocodificador
    responde rápido y cachear "cada texto que alguien tecleó mientras buscaba"
    no aporta lo mismo que cachear por parcela.

    Sin `MAPBOX_TOKEN` responde **501, no 502**: no es que el servicio haya
    fallado, es que este despliegue no tiene buscador — y el arquitecto puede
    seguir señalando la parcela en el mapa. Un 502 le haría reintentar para
    siempre algo que nunca va a funcionar."""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify(resultados=[])
    try:
        resultados = geocodificar_direccion(q)
    except GeocodificacionNoConfigurada as exc:
        return jsonify(error=str(exc), configurado=False), 501
    except ErrorDeSitio as exc:
        return jsonify(error=str(exc)), 502
    return jsonify(resultados=resultados)


@app.route("/api/analizar-sitio", methods=["POST"])
def analizar_sitio():
    """Datos reales del entorno de una parcela (`analyzer.sitio`) --
    Catastro + OpenStreetMap. Acción explícita, nunca automática (ni al
    importar un pliego con referencia catastral, ni al analizar/generar un
    proyecto): cada llamada es una decisión del arquitecto, mismo criterio
    que ya se aplicó al diagnóstico de IA y sigue el PRD (§9, "no repetir
    el patrón corregido hoy mismo para el diagnóstico de IA").

    Cacheado por parcela (`storage.sitios`), no por proyecto: la misma
    referencia catastral (o las mismas coordenadas manuales, redondeadas a
    ~11 m) consultada dos veces no vuelve a llamar a Catastro/Overpass.

    Respuesta rápida + entorno aparte (2026-08-17, docs/prd/2026-08-17-desacople-paso0-y-parcela-
    matriz.md, §14 -- alcance aprobado): la llamada normal (sin `solo_entorno`) resuelve SOLO Catastro/
    WFS (`incluir_overpass=False`) -- lo único que hace falta para dibujar la parcela en el Paso 0 --,
    en vez de esperar también a las 4 consultas de Overpass (colindantes/viales/zonas_verdes/
    equipamientos), mucho más lentas (127s medidos en vivo con Overpass degradado, PRD del 17-ago
    anterior). El cliente (`static/entrevista.js`), en cuanto pinta la parcela con esa respuesta rápida,
    dispara un SEGUNDO fetch con `solo_entorno: true` que rellena el entorno de Overpass en la MISMA
    fila de caché -- sin bloquear nada, y sin inventar ninguna cola/worker en el servidor (`REFACTOR_
    MASTERPLAN.md` excluye explícitamente eso). `/api/proyectos/<id>/checklist-campo`, que lee
    colindantes/viales/zonas_verdes de esta misma caché, los recibe completos si ese segundo fetch ya
    terminó para cuando el arquitecto llega a ese paso -- y sigue degradando con normalidad si no
    (`analyzer/checklist_campo.py` ya trata esos campos como opcionales)."""
    body = request.get_json(silent=True) or {}
    referencia_catastral = (body.get("referencia_catastral") or "").strip() or None
    municipio = (body.get("municipio") or "").strip() or None
    direccion = (body.get("direccion") or "").strip() or None
    lat = body.get("lat")
    lon = body.get("lon")
    solo_entorno = bool(body.get("solo_entorno"))

    if referencia_catastral:
        clave_cache = referencia_catastral
    elif lat is not None and lon is not None:
        clave_cache = "%.4f,%.4f" % (float(lat), float(lon))  # ~11 m de precisión, suficiente para cachear
    else:
        return jsonify(error="Indica una referencia catastral o unas coordenadas."), 400

    if solo_entorno:
        # Fetch no bloqueante del Paso 0 (ver docstring de arriba): solo tiene sentido con coordenadas
        # (Overpass no admite RC) y solo si ya existe la fila rápida que crear -- si el arquitecto ya
        # cerró la pestaña o cambió de punto antes de que esta petición llegara, no hay nada que rellenar.
        if lat is None or lon is None:
            return jsonify(error="'solo_entorno' requiere 'lat'/'lon'."), 400
        cacheado = obtener_sitio_por_clave(clave_cache)
        if cacheado is None:
            return jsonify(error="No hay una consulta previa de esta parcela que completar.", entorno_agregado=False), 404
        datos_previos = cacheado["datos"]
        if datos_previos.get("entorno_consultado"):
            # Ya se completó antes (p. ej. reapertura del Paso 0 sobre un punto ya resuelto del todo) --
            # no repetir las 4 consultas de Overpass, mismo criterio de no gastar red sin necesidad que
            # ya usa el resto de esta caché.
            return jsonify(sitio=cacheado, cache=True, entorno_agregado=True)
        entorno = entorno_overpass_por_coordenadas(float(lat), float(lon))
        datos_mergeados = dict(datos_previos)
        datos_mergeados.update(entorno)
        meta = guardar_sitio(clave_cache, datos_mergeados)
        return jsonify(sitio=meta, cache=False, entorno_agregado=True)

    cacheado = obtener_sitio_por_clave(clave_cache)
    if cacheado is not None:
        return jsonify(sitio=cacheado, cache=True)

    datos = obtener_datos_parcela(
        referencia_catastral=referencia_catastral, municipio=municipio, direccion=direccion,
        lat=lat, lon=lon, incluir_overpass=False,
    )
    meta = guardar_sitio(clave_cache, datos)
    return jsonify(sitio=meta, cache=False)


@app.route("/api/analizar", methods=["POST"])
def analizar():
    file = request.files.get("dxf")
    if file is None or file.filename == "":
        return jsonify(error="Selecciona un archivo DXF antes de analizar."), 400
    if not file.filename.lower().endswith(".dxf"):
        return jsonify(error="El archivo debe tener extensión .dxf."), 400

    try:
        norte_grados = float(request.form.get("norte", "0") or 0)
    except ValueError:
        norte_grados = 0.0

    filename = secure_filename(file.filename) or "plano.dxf"

    with tempfile.TemporaryDirectory(prefix="archmuse_") as tmp_dir:
        tmp_path = os.path.join(tmp_dir, filename)
        file.save(tmp_path)

        try:
            doc = load_document(tmp_path)
        except (FileNotFoundError, ValueError) as exc:
            return jsonify(error=str(exc)), 400

        # Qué capa y qué unidad se resuelven fuera del `try` general de abajo:
        # que un plano no diga en qué unidad está, o que sus estancias no estén
        # donde ArchMuse las busca, no es "no se pudo analizar el plano". Son
        # dos preguntas concretas con respuesta concreta, y el arquitecto
        # merece leerlas tal cual —y poder contestarlas— en vez de recibirlas
        # envueltas en un mensaje genérico.
        try:
            plano = leer_plano(
                doc,
                layer=(request.form.get("capa") or "").strip() or None,
                factor_escala=factor_de_unidad(request.form.get("escala") or ""),
            )
        except CapaIndeterminada as exc:
            return jsonify(
                error=str(exc),
                capa={
                    "pedida": exc.pedida,
                    "candidatas": [
                        {
                            "nombre": c.nombre,
                            "poligonos": c.n_poligonos,
                            "rotuladas": round(c.proporcion_rotulada * 100),
                            "motivo": c.motivo,
                        }
                        for c in exc.candidatas[:8]
                    ],
                },
            ), 400
        except EscalaIndeterminada as exc:
            return jsonify(
                error=exc.deteccion.mensaje,
                escala={
                    "origen": exc.deteccion.origen,
                    "sugerencia": exc.deteccion.sugerencia,
                    "unidad_cabecera": exc.deteccion.unidad_cabecera,
                    "opciones": ["metros", "centímetros", "milímetros", "decímetros"],
                },
            ), 400

        try:
            rooms = plano.rooms
            unit_labels = plano.unit_labels

            # E2 (docs/prd/2026-08-11-e2-persistencia-modelo.md, C-E2.3): el
            # modelo arquitectónico común se construye AQUÍ, una sola vez por
            # análisis — antes se reconstruía hasta 12 veces (una por cada
            # llamada a `evaluate_circulation`, dos por vivienda). El resultado
            # no participa en ningún cálculo de este endpoint (el payload no
            # cambia, C-E2.4): sólo se guarda al final, y `circulation.py` lo
            # reutiliza a través de la memoización de `modelo/compat.py`
            # (misma vivienda -> mismo objeto `Unit` -> un solo grafo).
            #
            # Best-effort, deliberadamente: si construir el modelo fallara
            # sobre un DXF real que hoy sí analiza (invariante violado, forma
            # inesperada), el análisis debe seguir devolviendo el mismo
            # resultado que antes de E2, no un 400 nuevo. Persistir el modelo
            # es la mejora; dejar de analizar no lo es.
            try:
                grafo = modelo_constructor.construir(plano, fichero=filename)
            except Exception:  # noqa: BLE001 - best-effort, ver comentario de arriba
                grafo = None

            tipologia = request.form.get("tipologia") or "plurifamiliar"
            # CAP-2. Eje distinto de `tipologia`, y sin valor por defecto a
            # propósito: si no viene, el hecho sale ESTIMATED (inferido de la
            # tipología) o UNKNOWN, nunca un Residencial Vivienda silencioso.
            # `evaluate_advanced` no lo recibe: esta fase sólo publica el
            # hecho, ninguna regla lo consume todavía.
            uso_previsto_declarado = (request.form.get("uso_previsto") or "").strip() or None
            ciudad = request.form.get("ciudad", "")
            # Tarea 6: la zona sigue replegando a "C" cuando no se resuelve el
            # municipio, pero ahora se sabe si es dato o suposición, y se dice
            # en `limitaciones`. `resolver_zona_cte("")` ya devuelve
            # ("C", False), así que el `if ciudad` sobraba.
            zona_cte, zona_cte_resuelta = resolver_zona_cte(ciudad)
            densidad_urbana = get_densidad_urbana(ciudad) if ciudad else "media"

            advanced = evaluate_advanced(
                rooms,
                unit_labels=unit_labels,
                norte_grados=norte_grados,
                tipologia=tipologia,
                zona_cte=zona_cte,
                densidad_urbana=densidad_urbana,
            )

            # Cierre de la integración AM_* (contrato de clasificación DXF,
            # Fases 1-3): `evaluate_advanced` construye `advanced.units` sin
            # conocer envolvente/superficies exteriores -- se asignan AQUÍ,
            # sobre las `Unit` ya formadas, reutilizando tal cual las
            # funciones de `evaluator.py` (no se reimplementa nada de su
            # lógica de unicidad/ambigüedad). `unit_score.unit` se actualiza
            # en el mismo orden que `advanced.units` (misma lista, mismo
            # índice -- `evaluate_advanced_for_units` construye los dos a la
            # vez, por eso el `zip` es seguro) para que
            # `api_serializer._serialize_unit` vea el dato ya asignado sin
            # tener que recibir `advanced.units` aparte.
            #
            # En un plano sin `AM_CONS_CER`/`AM_UTIL_EXT`/`AM_CONS_EXT` o sin
            # etiquetas de vivienda ('VT<n>/<m>'), las dos funciones devuelven
            # `units` sin cambios (ver sus propios docstrings) -- el modo
            # heredado queda bit a bit intacto.
            advanced.units = asignar_envolvente_cerrada(
                advanced.units, plano.envolventes_cerradas, unit_labels
            )
            advanced.units = asignar_superficies_exteriores(
                advanced.units, plano.superficies_utiles_exteriores,
                plano.envolventes_exteriores, unit_labels,
            )
            # `strict=True` (tarea 7): el comentario de arriba dice que las dos
            # listas se construyen a la vez y por eso el emparejado es seguro.
            # Esto lo convierte de promesa en comprobacion -- si alguna vez
            # dejan de tener el mismo largo, salta aqui en vez de asignar
            # `unit` a la vivienda equivocada y seguir como si nada.
            for unit_score, unit_con_am in zip(advanced.unit_scores, advanced.units, strict=True):
                unit_score.unit = unit_con_am

            # Diagnósticos de conformidad (Fase 2, `validacion_capas.py`), NO
            # bloqueantes: nunca cambian `advanced`, `plano` ni el resultado
            # del análisis, solo se cuelgan del payload (`serialize_analysis`
            # más abajo). Un plano sin ninguna capa `AM_*` en uso sigue
            # devolviendo una lista vacía -- ver docstring del módulo.
            #
            # Best-effort, mismo criterio que `modelo_constructor.construir`
            # más arriba: `validar_capas_am` necesita el `doc` de ezdxf
            # completo (no solo `plano`) para dos de sus comprobaciones, y
            # nada garantiza que todo objeto `doc` que llegue aquí tenga esa
            # forma -- un análisis que hoy responde 200 no puede empezar a
            # fallar porque un diagnóstico NO bloqueante no se haya podido
            # calcular.
            try:
                diagnosticos_capas_am = validar_capas_am(doc, plano, advanced.units)
            except Exception:  # noqa: BLE001 - best-effort, ver comentario de arriba
                diagnosticos_capas_am = []

            # Fase 4: solo se DETECTA aquí (`cuadro_superficies.py`, solo
            # lectura, mismo `doc` de ezdxf ya cargado) para decidir si la SPA
            # muestra el botón "Descargar DXF rellenado" en la pestaña
            # Salida. El cálculo/relleno de verdad vive en
            # `/api/exportar-cuadro-superficies`, sobre un upload nuevo -- ver
            # el docstring de esa ruta para por qué no se reutiliza este
            # mismo `doc`. Best-effort, mismo criterio que
            # `diagnosticos_capas_am`: un DXF sin cuadro reconocible no puede
            # convertir un análisis que hoy responde 200 en un error.
            try:
                cuadro_superficies_hecho = detectar_cuadro_superficies(doc)
            except Exception:  # noqa: BLE001 - best-effort, ver comentario de arriba
                cuadro_superficies_hecho = None

            issues = classify_problems(
                advanced, fire_compartmentation=advanced.fire_compartmentation, tipologia=tipologia
            )
            # El diagnóstico de IA ya NO se pide aquí automáticamente -- cada
            # análisis de un DXF disparaba una llamada de pago aunque nadie
            # fuera a leer el diagnóstico narrativo (el escenario típico
            # durante el desarrollo del propio analizador: subir el mismo
            # plano una y otra vez solo para probar reglas de `evaluator.py`
            # no tiene nada que ver con la IA). Ahora se pide bajo demanda
            # desde `POST /api/proyectos/<id>/diagnostico-ia`, una vez que el
            # arquitecto lo pide explícitamente. `analisis_ia` sale `null`
            # aquí, exactamente igual que cuando fallaba por falta de
            # ANTHROPIC_API_KEY -- el resto del informe ya sabía convivir con
            # eso.
            ai_analysis = None

            # CAP-2 y CAP-3 comparten el mismo orden que `advanced.unit_scores`:
            # el uso de cada zona se calcula una vez y se reutiliza para
            # derivar su ocupacion, en vez de recalcularlo.
            usos_hechos = usos_por_zona(
                [ZonaDeUso(nombre="vivienda %s" % us.unit.name)
                 for us in advanced.unit_scores],
                tipologia=tipologia,
                uso_principal=uso_previsto_declarado,
            )
            # CAP-4. Campo de texto libre, opcional, sin valor por defecto: si
            # no se rellena o no se puede interpretar, el hecho `planta` sale
            # UNKNOWN — nunca se asume una planta. `normalizar_declaracion_planta`
            # es la única vía de entrada de texto; no hay ningún camino que
            # infiera planta desde el nombre de la vivienda (VT<n>/<n>, que no
            # tiene relación semántica con la posición en el edificio) ni desde
            # geometría (`docs/prd/2026-08-09-cap4-modelo-de-planta.md` §4, §6).
            planta_declarada_texto = (request.form.get("planta") or "").strip() or None
            planta_normalizada = normalizar_declaracion_planta(planta_declarada_texto)
            if planta_normalizada is not None:
                numero_planta, sobre_rasante_planta = planta_normalizada
                origen_planta = ORIGEN_DECLARADO
                motivo_planta_no_disponible = None
            else:
                numero_planta = None
                sobre_rasante_planta = None
                origen_planta = None
                # Se distingue "no se ha escrito nada" (motivo genérico de
                # `planta()`) de "se ha escrito algo y no se ha entendido" — son
                # dos causas distintas para el arquitecto, aunque el estado sea
                # UNKNOWN en los dos casos.
                if planta_declarada_texto is None:
                    motivo_planta_no_disponible = None
                else:
                    motivo_planta_no_disponible = (
                        "La planta declarada («%s») no se ha podido interpretar. "
                        "Usa un formato como «Planta baja», «Planta 3» o «Sótano 1»."
                        % planta_declarada_texto
                    )

            # Un único hecho `planta` por proyecto (v1: `/api/analizar` analiza
            # una sola planta por análisis), replicado por vivienda con el
            # mismo criterio que `usos_hechos` — cada vivienda es su propio
            # ámbito, aunque el valor declarado sea idéntico para todas.
            planta_hechos = [
                calcular_planta(
                    "vivienda %s" % us.unit.name,
                    numero=numero_planta,
                    sobre_rasante=sobre_rasante_planta,
                    origen=origen_planta,
                    motivo_no_disponible=motivo_planta_no_disponible,
                )
                for us in advanced.unit_scores
            ]

            # CAP-3. Fact derivado, sin veredicto: la ocupacion no se cumple ni
            # se incumple (docs/design/DB-SI_FACT_MODEL.md P3). El ámbito es
            # planta cuando CAP-4 la conoce (KNOWN/ESTIMATED); si no, sigue
            # emitida por vivienda, marcada como agregado no normativo — ver
            # `analyzer/ocupacion.py`.
            ocupacion_hechos = [
                calcular_ocupacion(
                    superficie_util_ocupable_db_si(us.unit), uso_hecho,
                    planta=planta_hecho,
                )
                # `strict=True` (tarea 7): tres listas construidas por
                # separado y emparejadas por posicion. Un desajuste calcularia
                # la ocupacion de una vivienda con el uso de otra.
                for us, uso_hecho, planta_hecho in zip(
                    advanced.unit_scores, usos_hechos, planta_hechos, strict=True
                )
            ]

            # CAP-4, C01 (`analyzer/sectorizacion.py`): límite de 2.500 m² de
            # superficie por planta. Consume `superficie_util_db_si` — NO
            # `superficie_util_ocupable_db_si`, que es la que usa `ocupacion()`
            # y excluye zonas de ocupación nula; un límite de sector no tiene
            # motivo para excluirlas (§4ter del PRD). No se reutiliza ningún
            # hecho de ocupación: C01 y CAP-3 comparten `planta`, no la
            # superficie que consumen.
            sup_db_si_hechos = [
                superficie_util_db_si(us.unit) for us in advanced.unit_scores
            ]
            sectorizacion_hechos = limite_superficie_sector(sup_db_si_hechos, planta_hechos)

            # CAP-5. Un unico hecho de ambito EDIFICIO (no uno por vivienda,
            # a diferencia de planta/ocupacion/C01): la altura de evacuacion
            # es una magnitud del edificio entero por definicion del Anejo
            # SI A, y replicarla por vivienda sugeriria que cada una tiene la
            # suya. En este flujo la unica fuente posible es la declaracion
            # directa: `resolver_altura_evacuacion` se llama SIN
            # `plantas`/`altura_libre_m` porque `/api/analizar` no tiene
            # ningun equivalente a esos datos — la ausencia de hipotesis aqui
            # es estructural, no una comprobacion en tiempo de ejecucion
            # (PRD §4quater, criterio de aceptacion 5).
            altura_declarada_texto = (
                request.form.get("altura_evacuacion_m") or ""
            ).strip() or None
            altura_declarada_m = normalizar_declaracion_altura(altura_declarada_texto)
            if altura_declarada_m is None and altura_declarada_texto is not None:
                # Mismo criterio que `planta`: "no se ha escrito nada" y "se
                # ha escrito algo y no se ha entendido" son dos causas
                # distintas para el arquitecto, aunque el estado sea UNKNOWN
                # en los dos casos.
                motivo_altura = (
                    "La altura de evacuacion declarada («%s») no se ha podido "
                    "interpretar. Escribe un numero de metros mayor que cero, "
                    "por ejemplo «17,5»." % altura_declarada_texto
                )
            else:
                motivo_altura = None
            altura_hecho = resolver_altura_evacuacion(
                "edificio",
                valor_declarado_m=altura_declarada_m,
                motivo_no_disponible=motivo_altura,
            )
            # Avisos informativos de C11/C15/C18. NO son reglas: no llevan
            # `passed`, no entran en `classify_problems` y no tocan
            # `evaluator.py`. Un hecho UNKNOWN no dispara ninguno.
            avisos_evacuacion = avisos_altura_evacuacion(altura_hecho)

            payload = serialize_analysis(
                filename=filename,
                rooms=rooms,
                advanced=advanced,
                norte_grados=norte_grados,
                ai_analysis=ai_analysis,
                proyecto={
                    "tipologia": tipologia,
                    # Se guarda lo DECLARADO (o `None`), no el uso resuelto: el
                    # proyecto tiene que poder decir si el arquitecto lo dijo o
                    # si lo supuso ArchMuse. Fusionarlos borraría esa
                    # distinción justo en el sitio donde importa.
                    "uso_previsto_declarado": uso_previsto_declarado,
                    "usos": [
                        {
                            "ambito": h.ambito,
                            "uso": h.valor,
                            "estado": h.estado,
                            "confianza": h.confianza,
                            "origen": (h.diagnostico or {}).get("origen"),
                            "explicacion": h.explicacion,
                        }
                        for h in usos_hechos
                    ],
                    # Se guarda lo DECLARADO (o `None`), mismo criterio que
                    # `uso_previsto_declarado`: el proyecto tiene que poder decir
                    # si el arquitecto la escribió, no solo el resultado.
                    "planta_declarada": planta_declarada_texto,
                    "planta": _serializar_planta_hechos(planta_hechos),
                    "ocupacion": [
                        {
                            "ambito": h.ambito,
                            "personas": h.valor,
                            "presentacion_personas": (h.diagnostico or {}).get("presentacion_personas"),
                            "estado": h.estado,
                            "confianza": h.confianza,
                            "motivo": h.motivo_principal.detalle if h.motivo_principal else None,
                            "explicacion": h.explicacion,
                            "ambito_normativo": (h.diagnostico or {}).get("ambito_normativo"),
                            "ambito_emitido": (h.diagnostico or {}).get("ambito_emitido"),
                            "agregado_no_normativo": (h.diagnostico or {}).get("agregado_no_normativo"),
                        }
                        for h in ocupacion_hechos
                    ],
                    # C01 (analyzer/sectorizacion.py): límite de 2.500 m² por
                    # planta, DB-SI 1 ap. 1. `veredicto` nunca es "PASS" — ver
                    # docstring de `_serializar_sectorizacion_hechos`.
                    "sectorizacion": _serializar_sectorizacion_hechos(sectorizacion_hechos),
                    # CAP-5. Mismo criterio que `planta_declarada`: se guarda
                    # lo que escribio el arquitecto, no solo el resultado.
                    "altura_evacuacion_declarada": altura_declarada_texto,
                    "altura_evacuacion": _serializar_altura_evacuacion(altura_hecho),
                    "avisos_evacuacion": _serializar_avisos_evacuacion(avisos_evacuacion),
                    "zona_cte": zona_cte,
                    # Tarea 6. Un proyecto guardado tiene que poder decir si su
                    # zona climática es un dato o el valor por defecto: de ella
                    # dependen condensaciones, horas de sol y compacidad, y
                    # hasta hoy la suposición era indistinguible del dato.
                    "zona_cte_supuesta": not zona_cte_resuelta,
                    "ciudad": ciudad,
                    # Un proyecto guardado tiene que poder explicar de dónde
                    # salieron sus superficies: de qué capa, en qué unidad, y
                    # quién lo decidió, si el archivo o el arquitecto.
                    "escala": {"unidad": plano.escala.unidad, "origen": plano.escala.origen},
                    "capa": plano.layer,
                    # Fase 4: la SPA lo usa solo para decidir si muestra el
                    # botón de descarga -- no lleva las celdas ni los valores,
                    # eso se recalcula en `/api/exportar-cuadro-superficies`
                    # a partir del DXF real, nunca desde este booleano.
                    "cuadro_superficies_detectado": cuadro_superficies_hecho is not None,
                },
                capas_am_detectadas=_capas_am_detectadas(plano),
                geometria_no_leida=plano.geometria_no_leida,
                diagnosticos_clasificacion=diagnosticos_capas_am,
            )
        except Exception as exc:  # noqa: BLE001 - límite del sistema: DXF arbitrario subido por el usuario
            return jsonify(error=f"No se pudo analizar el plano: {exc}"), 400

    # Se guarda solo si el análisis llegó hasta el final: un DXF que no parsea
    # no crea proyecto (§6 del PRD de persistencia). `guardar_proyecto` inyecta
    # `proyecto_id` en el payload antes de serializarlo, así que lo que se
    # devuelve aquí y lo que queda en disco son el mismo objeto.
    #
    # `grafo` (E2): el modelo construido más arriba, o `None` si la
    # construcción falló (best-effort) — `guardar_proyecto` ya sabe guardar
    # `None` sin romper nada.
    guardar_proyecto(payload, origen="dxf", grafo=grafo)
    return jsonify(payload)


def _capas_am_detectadas(plano) -> list:
    """Qué capas `AM_*` operativas están realmente en uso en este `plano` --
    con contenido válido (rooms/envolventes/superficies) O con alguna entidad
    descartada en ellas (una capa con solo geometría inválida sigue siendo
    una capa que el arquitecto ha usado, aunque `leer_plano` no haya podido
    aprovechar nada de ella).

    Solo lectura sobre `PlanoLeido`: no recalcula nada que no haya calculado
    ya `parser.leer_plano`."""
    detectadas = set()
    if any(r.layer == CAPA_UTIL_INTERIOR for r in plano.rooms):
        detectadas.add(CAPA_UTIL_INTERIOR)
    if plano.envolventes_cerradas:
        detectadas.add(CAPA_CONSTRUIDA_CERRADA)
    if plano.superficies_utiles_exteriores:
        detectadas.add(CAPA_UTIL_EXTERIOR)
    if plano.envolventes_exteriores:
        detectadas.add(CAPA_CONSTRUIDA_EXTERIOR)
    detectadas.update(
        d.capa for d in plano.geometria_no_leida if d.capa in CAPAS_AM_OPERATIVAS
    )
    return sorted(detectadas)


def _planta_desde_nombre_unidad(unit_name: str, ambito: str):
    """CAP-4 en `/api/generar`: lee la planta del prefijo `Planta <n> · <nombre>`
    que ya usa `ai_generator._unit_from_dict` (`floor_label`), reutilizando el
    patrón `_PLANTA_NAME_PATTERN` de `evaluator.py` — no se duplica la regex,
    ni se toca `evaluator.py`.

    **Nunca `KNOWN`.** Es una convención de texto sobre el nombre de la
    unidad, no una declaración explícita del arquitecto — la misma distinción
    que separa `ORIGEN_DECLARADO` de `ORIGEN_CONVENCION_NOMBRE` en
    `analyzer/planta.py`. Si el nombre no casa el patrón (incluido cualquier
    `VT<n>/<n>`, que no tiene relación semántica con planta), el resultado es
    `UNKNOWN` — nunca se infiere nada del nombre por otra vía.
    """
    match = _PLANTA_NAME_PATTERN.match(unit_name)
    if not match:
        return calcular_planta(ambito, numero=None)
    numero = int(match.group(1))
    return calcular_planta(
        ambito, numero=numero, sobre_rasante=numero > 0,
        origen=ORIGEN_CONVENCION_NOMBRE,
    )


def _serializar_planta_hechos(hechos) -> list:
    """La misma forma de `proyecto.planta` para `/api/analizar` y
    `/api/generar` — un único contrato, no dos parecidos."""
    return [
        {
            "ambito": h.ambito,
            "numero": h.valor,
            "sobre_rasante": (h.diagnostico or {}).get("sobre_rasante"),
            "estado": h.estado,
            "confianza": h.confianza,
            "origen": (h.diagnostico or {}).get("origen"),
            "motivo": h.motivo_principal.detalle if h.motivo_principal else None,
            "explicacion": h.explicacion,
        }
        for h in hechos
    ]


def _serializar_sectorizacion_hechos(hechos) -> list:
    """`proyecto.sectorizacion` — el veredicto de `C01` (límite de 2.500 m²
    por planta, `analyzer/sectorizacion.py`), un elemento por vivienda de
    entrada (mismo contrato que `limite_superficie_sector`: no se filtra
    nada, las viviendas de una misma planta comparten el mismo veredicto).

    Solo lectura de campos ya calculados — esta función no decide FAIL ni
    UNKNOWN, no reimplementa el límite ni la agregación por planta. `estado`
    y `veredicto` viajan siempre juntos: `veredicto` es `None` salvo cuando
    `estado == KNOWN`, y entonces **siempre** es `"FAIL"` — nunca `"PASS"`,
    por diseño de `sectorizacion.limite_superficie_sector` (§4ter del PRD).
    """
    return [
        {
            "ambito": h.ambito,
            "planta_numero": (h.diagnostico or {}).get("planta_numero"),
            "superficie_acumulada_m2": h.valor,
            "limite_m2": (h.diagnostico or {}).get("limite_m2"),
            "estado": h.estado,
            "veredicto": (h.diagnostico or {}).get("veredicto"),
            "confianza": h.confianza,
            "codigo": (h.diagnostico or {}).get("codigo_regla"),
            "motivo": h.motivo_principal.detalle if h.motivo_principal else None,
            "explicacion": h.explicacion,
            "unidades_computadas": (h.diagnostico or {}).get("unidades_computadas"),
            "unidades_sin_superficie": (h.diagnostico or {}).get("unidades_sin_superficie"),
        }
        for h in hechos
    ]


def _serializar_altura_evacuacion(hecho) -> dict:
    """`proyecto.altura_evacuacion` — un objeto, no una lista: el hecho es de
    ambito edificio y hay exactamente uno por analisis (CAP-5, PRD §4).

    Misma forma en `/api/analizar` y `/api/generar`, un unico contrato. Solo
    lectura de campos ya calculados: esta funcion no decide estado, no aplica
    la formula y no elige entre fuentes — eso vive entero en
    `analyzer/altura_evacuacion.py`.
    """
    diag = hecho.diagnostico or {}
    return {
        "ambito": hecho.ambito,
        "altura_m": hecho.valor,
        "estado": hecho.estado,
        "confianza": hecho.confianza,
        "origen": diag.get("origen"),
        "formula": diag.get("formula"),
        "plantas": diag.get("plantas"),
        "altura_libre_m": diag.get("altura_libre_m"),
        "hipotesis_descartada": diag.get("hipotesis_descartada"),
        "referencia_normativa": hecho.referencia_normativa,
        "motivo": hecho.motivo_principal.detalle if hecho.motivo_principal else None,
        "explicacion": hecho.explicacion,
        "procedencia": list(hecho.procedencia),
    }


def _serializar_avisos_evacuacion(avisos) -> list:
    """`proyecto.avisos_evacuacion` — hasta tres avisos informativos (C11,
    C15, C18), o una lista vacia.

    **No son incidencias.** No llevan `passed` ni `severity`, no salen de
    `classify_problems` y no deben pintarse como un `IssueReport`: el campo
    `es_aviso` esta aqui para que ningun consumidor futuro los confunda con
    un FAIL (PRD §7).
    """
    return [
        {
            "es_aviso": True,
            "codigo": a.codigo,
            "regla": a.regla,
            "titulo": a.titulo,
            "localizador": a.localizador,
            "umbral_m": a.umbral_m,
            "altura_m": a.altura_m,
            "altura_estimada": a.altura_estimada,
            "mensaje": a.mensaje,
        }
        for a in avisos
    ]


def _num(source: dict, key: str, default: float, cast=float):
    try:
        return cast(source.get(key, default))
    except (TypeError, ValueError):
        return default


def _optional_num(source: dict, key: str, cast=float):
    value = source.get(key)
    if value in (None, ""):
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def _resolver_estilo(body: dict) -> Optional[dict]:
    """`body["estilo"]` (clave de catálogo o texto libre), opcional, por
    defecto `DEFAULT_ESTILO` ("racionalista") -- una clave de catálogo, así
    que ningún llamador que no pida estilo explícito dispara nunca una
    llamada a la IA (`obtener_estilo` resuelve por diccionario antes de
    tocar la red).

    Best-effort, igual que `modelo_constructor.construir` en `/api/analizar`:
    si interpretar un estilo de texto libre fallara (red, API), la
    generación del proyecto no debe bloquearse por una capa que es una
    mejora, no un requisito -- se registra en el log y se sigue sin bloque
    de estilo, nunca con un 502 por esto."""
    clave_o_descripcion = (body.get("estilo") or DEFAULT_ESTILO).strip() or DEFAULT_ESTILO
    try:
        return obtener_estilo(clave_o_descripcion)
    except ErrorDeEstilo as exc:
        logger.warning("No se pudo resolver el estilo %r: %s -- se genera sin bloque de estilo.",
                        clave_o_descripcion, exc)
        return None


def _clave_cache_sitio_de(body: dict) -> Optional[str]:
    """Misma clave de caché que ya usa `/api/analizar-sitio` (referencia
    catastral tal cual, o `"lat,lon"` a 4 decimales) — para que un sitio ya
    analizado con una de esas dos formas se reconozca aquí sin volver a
    pedirle nada al arquitecto. `None` si el body no trae ninguna de las
    dos, nunca una clave inventada."""
    referencia_catastral = (body.get("referencia_catastral") or "").strip()
    if referencia_catastral:
        return referencia_catastral
    lat, lon = body.get("sitio_lat"), body.get("sitio_lon")
    if lat is not None and lon is not None:
        try:
            return "%.4f,%.4f" % (float(lat), float(lon))
        except (TypeError, ValueError):
            return None
    return None


def _vincular_sitio_si_corresponde(clave_cache: Optional[str], proyecto_id: str) -> None:
    """Paso 3.2: "si existe un sitio analizado previamente... se invoque
    vincular_sitio_proyecto() al generar el proyecto". Solo enlaza un sitio
    que YA esté en caché (`obtener_sitio_por_clave`) -- nunca dispara una
    consulta nueva a Catastro/Overpass desde el flujo de generación (eso
    seguiría siendo una acción explícita del arquitecto, `/api/analizar-
    sitio`, mismo criterio que el resto de la sesión de hoy con la IA).
    Best-effort: un fallo aquí no debe tumbar una generación que ya
    funcionó -- mismo criterio que `vincular_pliego_proyecto` en
    `generar_desde_pliego`."""
    if not clave_cache:
        return
    try:
        if obtener_sitio_por_clave(clave_cache) is not None:
            vincular_sitio_proyecto(clave_cache, proyecto_id)
    except Exception:  # noqa: BLE001
        pass


def _parse_generar_params(payload: dict) -> dict:
    """Valida y normaliza el JSON recibido en `POST /api/generar`. Lanza
    `ValueError` (con un mensaje apto para el usuario) si faltan datos
    imprescindibles."""
    proyecto_in = payload.get("proyecto") or {}
    solar_in = payload.get("solar") or {}
    edificio_in = payload.get("edificio") or {}
    mix_in = payload.get("mix_viviendas") or {}
    normativa_in = payload.get("normativa") or {}

    forma = solar_in.get("forma")
    if forma not in ("rectangular", "irregular"):
        forma = "rectangular"

    tipologia = proyecto_in.get("tipologia")
    if tipologia not in ("plurifamiliar", "unifamiliar", "rehabilitacion"):
        tipologia = "plurifamiliar"

    proyecto = {
        "ciudad": str(proyecto_in.get("ciudad") or "").strip(),
        "tipologia": tipologia,
    }

    solar = {
        "superficie_m2": _num(solar_in, "superficie_m2", 0.0),
        "forma": forma,
        "ancho_m": _num(solar_in, "ancho_m", 0.0) or None,
        "largo_m": _num(solar_in, "largo_m", 0.0) or None,
        "norte_grados": _num(solar_in, "norte_grados", 0.0),
    }
    edificio = {
        "plantas": max(1, int(_num(edificio_in, "plantas", 1, int))),
        "altura_libre_m": _num(edificio_in, "altura_libre_m", 2.8),
        "planta_baja_comercial": bool(edificio_in.get("planta_baja_comercial", False)),
    }
    mix_viviendas = {
        "dorm_1": max(0, int(_num(mix_in, "dorm_1", 0, int))),
        "dorm_2": max(0, int(_num(mix_in, "dorm_2", 0, int))),
        "dorm_3": max(0, int(_num(mix_in, "dorm_3", 0, int))),
        "superficie_minima_m2": _num(mix_in, "superficie_minima_m2", 45.0),
    }
    normativa = {
        "ocupacion_maxima_pct": _num(normativa_in, "ocupacion_maxima_pct", 70.0),
        "retranqueos_m": _num(normativa_in, "retranqueos_m", 3.0),
        "edificabilidad_maxima": _optional_num(normativa_in, "edificabilidad_maxima"),
        "plantas_maximas": _optional_num(normativa_in, "plantas_maximas", int),
    }

    if solar["superficie_m2"] <= 0:
        raise ValueError("Indica la superficie del solar.")
    if mix_viviendas["dorm_1"] + mix_viviendas["dorm_2"] + mix_viviendas["dorm_3"] <= 0:
        raise ValueError("Indica al menos una vivienda en el mix de viviendas.")

    resultado = {
        "solar": solar,
        "edificio": edificio,
        "mix_viviendas": mix_viviendas,
        "normativa": normativa,
        "proyecto": proyecto,
        # CAP-5 (P5.2): el campo de entrada vive en `edificio` del JSON del
        # cliente, pero se guarda FUERA de `params["edificio"]` a proposito —
        # ese dict se serializa entero dentro del prompt de
        # `ai_generator._build_user_message`, y CAP-5 no debe alterar el
        # prompt de generacion (`ai_generator.py` esta fuera de alcance).
        # `None` si no se declara: no hay valor por defecto, igual que en
        # `uso_previsto` y en `planta`.
        "altura_evacuacion_m": normalizar_declaracion_altura(
            edificio_in.get("altura_evacuacion_m")
        ),
    }

    # Fase F (integración con el generador), tarea E: clave nueva y
    # OPCIONAL, contrato §5-§6.2. Se reenvía tal cual, sin validar aquí su
    # forma interna — `ai_generator._validar_directivas()` es quien decide
    # qué directiva es aceptable antes de que llegue al prompt (regla
    # explícita de esta fase: "no pasar al prompt... sin haber pasado por
    # el compilador"); duplicar esa validación aquí sería una segunda
    # fuente de verdad sobre lo mismo. Si el body no la trae (el 100% de
    # las llamadas de antes de esta fase, y el formulario técnico de
    # `renderGenerarForm` que sigue sin enviarla), la clave ni siquiera se
    # añade al dict — comportamiento bit a bit idéntico al de siempre.
    contexto_cualitativo = payload.get("contexto_cualitativo")
    if isinstance(contexto_cualitativo, dict):
        resultado["contexto_cualitativo"] = contexto_cualitativo

    # "Editar / Intervenir edificación existente": clave nueva y OPCIONAL,
    # mismo criterio de reenvío tal cual que `contexto_cualitativo` justo
    # arriba -- quien decide si el bloque es válido antes de tocar el
    # prompt es `ai_generator._compilar_bloque_intervencion()`, no este
    # parseo. La produce `analyzer.interview.compilador.compilar_params()`
    # (modo experto, vía `parcela.tipo_intervencion`/`parcela.elementos_
    # a_conservar`) o puede llegar directamente en el body de un caller
    # que hable con `/api/generar` sin pasar por el entrevistador. Si no
    # viene, la clave ni se añade -- comportamiento bit a bit idéntico al
    # de siempre para el 100% de las llamadas anteriores a esta capacidad.
    intervencion_existente = payload.get("intervencion_existente")
    if isinstance(intervencion_existente, dict):
        resultado["intervencion_existente"] = intervencion_existente

    # Motor de estilos (`analyzer.estilos`), opcional, por defecto
    # "racionalista" -- una clave de catálogo, así que una petición que no
    # pide estilo nunca dispara una llamada a la IA por esto. Resuelto AQUÍ
    # (no en `ai_generator.py`) porque es donde ya se resuelven el resto de
    # entradas opcionales del body -- `ai_generator._build_user_message`
    # solo aplica la plantilla ya resuelta, nunca decide ni llama a Claude.
    resultado["estilo_dict"] = _resolver_estilo(payload)

    # Sólido Capaz persistente (`docs/prd/2026-08-17-solido-capaz-
    # persistente-visor-edificio.md`): clave nueva y OPCIONAL, mismo criterio
    # de reenvío tal cual que `contexto_cualitativo`/`intervencion_existente`
    # más arriba -- es un snapshot que ya calculó el Sandbox
    # (`viewer-sandbox.js:calcularSolidoCapaz`), no algo que este parseo
    # deba validar ni interpretar. NUNCA llega al prompt de generación
    # (`ai_generator.py` no la lee): solo se guarda junto al proyecto para
    # que el visor 3D la consuma después. Si el body no la trae (el 100% de
    # las llamadas de antes de este PRD, y de todo proyecto generado sin
    # pasar antes por el Sandbox), la clave ni se añade.
    solido_capaz = payload.get("solido_capaz")
    if isinstance(solido_capaz, dict):
        resultado["solido_capaz"] = solido_capaz

    return resultado


@app.route("/api/generar", methods=["POST"])
def generar():
    body = request.get_json(silent=True) or {}
    try:
        params = _parse_generar_params(body)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    respuesta = _generar_proyecto_desde_params(params)
    if not isinstance(respuesta, tuple):
        _vincular_sitio_si_corresponde(_clave_cache_sitio_de(body), respuesta.get_json()["proyecto_id"])
    return respuesta


def _generar_proyecto_desde_params(params: dict, project=None):
    """Todo lo que `/api/generar` hacía a partir de un `params` ya
    construido y validado -- extraído (2026-08-15) para que `/api/generar-
    desde-pliego` (`analyzer.pliego_conector`) lo reutilice sin duplicar
    evaluación/serialización. Refactor puro: mismo comportamiento bit a
    bit que antes, solo reorganizado en dos funciones.

    `project`: opcional (docs/prd/2026-08-17-optimizacion-generativa-multi-
    opcion.md) -- si `/api/generar-opciones` ya llamó a `generate_project`
    por su cuenta (para poder calcular las métricas comparativas ANTES de
    decidir si persiste cada opción), lo pasa aquí para que esta función
    reutilice ese resultado en vez de volver a llamar a Claude. `None`
    (el caso de siempre) mantiene el comportamiento exacto de antes."""
    zona_resuelta, zona_es_dato = resolver_zona_cte(params["proyecto"]["ciudad"])
    params["proyecto"]["zona_cte"] = zona_resuelta
    # Tarea 6: mismo aviso que en `/api/analizar`. Un proyecto generado por IA
    # sin ciudad se evalúa igualmente contra una zona climática por defecto.
    params["proyecto"]["zona_cte_supuesta"] = not zona_es_dato
    params["proyecto"]["densidad_urbana"] = get_densidad_urbana(params["proyecto"]["ciudad"])

    if project is None:
        try:
            project = generate_project(params)
        except GenerationError as exc:
            return jsonify(error=str(exc)), 502

    norte_grados = params["solar"]["norte_grados"]
    zona_cte = params["proyecto"]["zona_cte"]
    tipologia = params["proyecto"]["tipologia"]
    densidad_urbana = params["proyecto"]["densidad_urbana"]
    advanced = evaluate_advanced_for_units(
        project.units,
        project.rooms,
        norte_grados=norte_grados,
        zona_cte=zona_cte,
        tipologia=tipologia,
        densidad_urbana=densidad_urbana,
    )
    ai_analysis = AIAnalysis(conclusion_ejecutiva=project.justificacion)

    # CAP-4. Cada `Unit` generada se llama "Planta <n> · <nombre>"
    # (`ai_generator._unit_from_dict`); se lee de ahí con el mismo patrón que
    # ya usa el urbanismo del Bloque 6 más abajo, sin declaración adicional
    # del arquitecto — por eso es ESTIMATED, nunca KNOWN. NOTA: este bloque
    # usa `sobre_rasante = numero > 0`, la misma regla que
    # `analyzer/planta.py` (planta 0/negativa no está sobre rasante). El
    # urbanismo de más abajo (`floor_areas.get(1, ...)`) trata la planta "1"
    # como planta baja — una convención propia de `ai_generator`, anterior a
    # CAP-4 y que este PRD no toca (tocarla exige `evaluator.py`, fuera de
    # alcance). Puede haber lecturas distintas de qué planta es "la baja"
    # entre este hecho y ese cálculo urbanístico; se deja constancia aquí en
    # vez de intentar armonizarlas por iniciativa propia.
    params["proyecto"]["planta"] = _serializar_planta_hechos([
        _planta_desde_nombre_unidad(u.name, "vivienda %s" % u.name)
        for u in project.units
    ])

    # CAP-5. El unico flujo con una segunda fuente posible: si el arquitecto
    # no declara la altura, se estima como `(plantas - 1) x altura_libre_m`
    # (ESTIMATED, confianza Baja). La precedencia declaracion > hipotesis
    # vive entera en `resolver_altura_evacuacion`, no aqui.
    #
    # `plantas - 1` y no `plantas`: `edificio.plantas` INCLUYE la planta baja
    # en todo este endpoint — `ai_generator` numera desde "planta": 1 y resta
    # 1 cuando la baja es comercial, y `floor_areas.get(1, 0.0)` se usa unas
    # lineas mas abajo literalmente como `superficie_planta_baja`. Con la
    # planta 1 a cota de rasante, el origen de evacuacion mas alto queda a
    # (N - 1) alturas libres sobre la salida de edificio. (La SPA rotula ese
    # campo «Plantas sobre rasante», lo que contradice esta semantica: es la
    # misma familia de deuda de numeracion que CAP-4 dejo registrada, y
    # tocarla exige `evaluator.py`/`ai_generator.py`, fuera de alcance.)
    altura_hecho = resolver_altura_evacuacion(
        "edificio",
        valor_declarado_m=params["altura_evacuacion_m"],
        plantas=params["edificio"]["plantas"],
        altura_libre_m=params["edificio"]["altura_libre_m"],
    )
    avisos_evacuacion = avisos_altura_evacuacion(altura_hecho)
    params["proyecto"]["altura_evacuacion"] = _serializar_altura_evacuacion(altura_hecho)
    params["proyecto"]["avisos_evacuacion"] = _serializar_avisos_evacuacion(avisos_evacuacion)

    # Urbanismo a nivel de edificio (Bloque 6): ocupación en planta baja,
    # edificabilidad total y altura máxima frente al solar y la normativa.
    floor_areas = compute_floor_areas(project.units)
    superficie_solar = params["solar"]["superficie_m2"]
    superficie_planta_baja = floor_areas.get(1, 0.0)
    superficie_total_construida = sum(floor_areas.values())

    occupation_result = evaluate_solar_occupation(superficie_planta_baja, superficie_solar, params["normativa"])
    buildability_result = evaluate_buildability(superficie_total_construida, superficie_solar, params["normativa"])
    max_floors_result = evaluate_max_floors(params["edificio"], params["normativa"])
    ceiling_height_result = evaluate_ceiling_height(params["edificio"]["altura_libre_m"])

    problemas_edificio = []
    if occupation_result and not occupation_result.passed:
        problemas_edificio.append(occupation_result.message)
    if buildability_result and not buildability_result.passed:
        problemas_edificio.append(buildability_result.message)
    if max_floors_result and not max_floors_result.passed:
        problemas_edificio.append(max_floors_result.message)
    if ceiling_height_result and not ceiling_height_result.passed:
        problemas_edificio.append(ceiling_height_result.message)

    # Eficiencia energética (Bloque 10): compacidad del edificio y % de
    # superficie habitable orientada a sur/sureste/suroeste.
    perimetro_planta_baja = compute_floor_perimeter_m(project.units, floor=1)
    compactness_result = evaluate_building_compactness(
        superficie_total_construida, perimetro_planta_baja, params["edificio"]["altura_libre_m"], zona_cte
    )
    orientation_ratio_result = evaluate_building_orientation_ratio(advanced.orientation)

    if compactness_result and not compactness_result.passed:
        problemas_edificio.append(compactness_result.message)
    if orientation_ratio_result and not orientation_ratio_result.passed:
        problemas_edificio.append(orientation_ratio_result.message)

    # Retranqueos (proxy simple, sin geometría real de solar): resta
    # 2×retranqueos_m del ancho/largo del solar y comprueba la huella
    # resultante. Solo evaluable si el solar es rectangular con
    # ancho_m/largo_m informados.
    retranqueos_result = evaluate_retranqueos(params["solar"], params["normativa"])
    if retranqueos_result is not None:
        problemas_edificio.append(retranqueos_result.message)

    payload = serialize_analysis(
        filename="Proyecto generado",
        rooms=project.rooms,
        advanced=advanced,
        norte_grados=norte_grados,
        ai_analysis=ai_analysis,
        # Presente únicamente para proyectos generados: el número de plantas
        # y la altura libre son parámetros que el arquitecto ha indicado (no
        # hay forma de inferirlos de un DXF analizado), y son los que usa el
        # visor 3D de la SPA para extrudir y apilar cada planta del edificio.
        edificio={
            "plantas": params["edificio"]["plantas"],
            "altura_libre_m": params["edificio"]["altura_libre_m"],
            "planta_baja_comercial": params["edificio"]["planta_baja_comercial"],
            "edificabilidad_maxima": params["normativa"].get("edificabilidad_maxima"),
            "plantas_maximas": params["normativa"].get("plantas_maximas"),
        },
        advertencias=project.advertencias,
        problemas_edificio=problemas_edificio,
        superficie_solar_m2=superficie_solar,
        superficie_total_construida_m2=superficie_total_construida,
        normativa=params["normativa"],
        solar_occupation=occupation_result,
        buildability=buildability_result,
        max_floors=max_floors_result,
        compactness=compactness_result,
        building_orientation=orientation_ratio_result,
        retranqueos=retranqueos_result,
        ceiling_height=ceiling_height_result,
        proyecto=params["proyecto"],
        solar=params["solar"],
    )
    # Sólido Capaz persistente: snapshot opcional ya calculado en el Sandbox
    # (ver `_parse_generar_params`), guardado en su propia columna -- nunca
    # dentro de `payload` en disco (mismo criterio que `modelo`). Se añade
    # a la RESPUESTA (no al objeto que se serializa a la BD) para que quien
    # generó el proyecto lo tenga sin tener que hacer un segundo GET.
    solido_capaz = params.get("solido_capaz")
    guardar_proyecto(payload, origen="generado", solido_capaz=solido_capaz)
    _guardar_traza_de_generacion(params, project, payload["proyecto_id"])
    if solido_capaz is not None:
        payload = dict(payload, solido_capaz=solido_capaz)
    return jsonify(payload)


@app.route("/api/generar-opciones", methods=["POST"])
def generar_opciones():
    """`docs/prd/2026-08-17-optimizacion-generativa-multi-opcion.md`
    (aprobado 2026-08-17: 2 opciones, interpretación FUERTE -- cada una con
    un `mix_viviendas` distinto derivado del mismo `superficie_objetivo_m2`,
    `analyzer.ai_generator.derivar_mixes_alternativos`).

    Mismo `params` que `/api/generar` más `superficie_objetivo_m2` (la
    Construida objetivo del Programa de Necesidades, ya en memoria del
    cliente). Genera las 2 opciones con llamadas independientes a Claude
    (`generate_project`, UNA vez por opción -- nunca dos, para no duplicar
    el coste ya señalado como riesgo en el PRD §9) y, para cada una que se
    genere con éxito, reutiliza `_generar_proyecto_desde_params` para
    serializarla y guardarla EXACTAMENTE igual que `/api/generar` -- cada
    opción queda como un proyecto propio y navegable, no un estado
    especial. Si una opción falla, la otra se devuelve igualmente
    (criterio de aceptación §8.6 del PRD)."""
    body = request.get_json(silent=True) or {}
    try:
        params_base = _parse_generar_params(body)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    superficie_objetivo = _num(body, "superficie_objetivo_m2", 0.0)
    superficie_minima = params_base["mix_viviendas"].get("superficie_minima_m2", 45.0)
    mixes = derivar_mixes_alternativos(superficie_objetivo, superficie_minima)
    if not mixes:
        return jsonify(error="Indica la superficie construida objetivo para derivar las 2 opciones."), 400

    zona_base, zona_base_es_dato = resolver_zona_cte(params_base["proyecto"]["ciudad"])
    params_base["proyecto"]["zona_cte"] = zona_base
    params_base["proyecto"]["zona_cte_supuesta"] = not zona_base_es_dato  # tarea 6
    params_base["proyecto"]["densidad_urbana"] = get_densidad_urbana(params_base["proyecto"]["ciudad"])

    ratio_m2 = _optional_num(body, "ratioM2")
    coste_suelo = _optional_num(body, "costeSuelo")
    precio_venta = _optional_num(body, "precioVenta")

    opciones = {}
    for etiqueta, mix in mixes.items():
        params_opcion = dict(params_base)
        params_opcion["mix_viviendas"] = mix
        try:
            project = generate_project(params_opcion)
        except GenerationError as exc:
            opciones[etiqueta] = {"error": str(exc), "mix_viviendas": mix}
            continue

        metricas = calcular_metricas_opcion(
            etiqueta, project, mix, ratio_m2=ratio_m2, coste_suelo=coste_suelo, precio_venta=precio_venta,
        )
        respuesta = _generar_proyecto_desde_params(params_opcion, project=project)
        if isinstance(respuesta, tuple):
            error_json = respuesta[0].get_json() or {}
            opciones[etiqueta] = {"error": error_json.get("error", "No se pudo guardar esta opción."), "mix_viviendas": mix}
            continue

        payload = respuesta.get_json()
        opciones[etiqueta] = {
            "proyecto_id": payload.get("proyecto_id"),
            "mix_viviendas": mix,
            "metricas": {
                "repercusion_zonas_comunes_pct": metricas.repercusion_zonas_comunes_pct,
                "pct_fachada_aprovechada": metricas.pct_fachada_aprovechada,
                "margen_estimado": {
                    "inversion_total": metricas.margen_estimado.inversion_total,
                    "margen_eur": metricas.margen_estimado.margen_eur,
                    "margen_pct": metricas.margen_estimado.margen_pct,
                },
            },
        }

    return jsonify(opciones=opciones)


@app.route("/api/generar-desde-pliego", methods=["POST"])
def generar_desde_pliego():
    """Genera un proyecto directamente desde un pliego ya extraído --
    `analyzer.pliego_conector.pliego_a_params()` traduce lo que el pliego
    ya resolvió; el resto es EXACTAMENTE `/api/generar`
    (`_generar_proyecto_desde_params`, reutilizada sin duplicar nada).
    Alcance mínimo a propósito (encargo de Pablo, 2026-08-15): sin
    entrevistador, sin informe de cumplimiento -- eso es el PRD más amplio,
    todavía sin aprobar.

    El pliego nunca trae la superficie del solar (no es uno de sus 17
    campos) -- hace falta para que la validación de siempre
    (`_parse_generar_params`) no rechace la petición, y para convertir
    correctamente `edificabilidad_maxima_m2` (cota absoluta del pliego) al
    ratio que espera `normativa.edificabilidad_maxima`. Se acepta de dos
    formas, ambas válidas: `superficie_solar_m2` suelto en el body (el
    nombre que pide esta especificación), o `solar.superficie_m2` anidado
    (si además se quieren indicar `forma`/`ancho_m`/`largo_m`/
    `norte_grados` del solar) -- si se dan los dos, el anidado gana, por
    ser el más específico. Sin ninguno de los dos, 400 claro, igual que ya
    le pasa a `/api/generar` hoy sin superficie -- ningún caso nuevo."""
    body = request.get_json(silent=True) or {}
    pliego_id = body.get("pliego_id")
    if not pliego_id:
        return jsonify(error='Indica el id del pliego ("pliego_id").'), 400

    pliego = obtener_pliego(pliego_id)
    if pliego is None:
        return jsonify(error="Ese pliego no existe o no se puede abrir."), 404

    solar_override = dict(body.get("solar") or {})
    if "superficie_m2" not in solar_override and body.get("superficie_solar_m2") is not None:
        solar_override["superficie_m2"] = body.get("superficie_solar_m2")
    superficie_solar = _optional_num(solar_override, "superficie_m2")
    body_generado = pliego_a_params(pliego["parametros"], superficie_solar_m2=superficie_solar)
    body_generado["solar"].update(solar_override)
    # `pliego_a_params()` no conoce "estilo" (no es un campo del pliego) --
    # se traspasa del body original tal cual, mismo mecanismo que ya usa
    # `_parse_generar_params` en `/api/generar` para resolverlo.
    if "estilo" in body:
        body_generado["estilo"] = body["estilo"]

    try:
        params = _parse_generar_params(body_generado)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    respuesta = _generar_proyecto_desde_params(params)
    if isinstance(respuesta, tuple):
        return respuesta  # error ya formado (p.ej. 502 de GenerationError) -- se devuelve tal cual

    # Único llamador real de `vincular_pliego_proyecto` hasta hoy (existía
    # desde el extractor, sin usar). Best-effort: si fallara, el proyecto
    # ya se generó y guardó -- no tiene sentido convertir eso en un error.
    proyecto_id = respuesta.get_json()["proyecto_id"]
    try:
        vincular_pliego_proyecto(pliego_id, proyecto_id)
    except Exception:  # noqa: BLE001
        pass

    # Paso 3.2: si el propio pliego trae una referencia catastral KNOWN
    # (no siempre la trae -- el pliego real de Berrocales probado hoy no
    # tenía ninguna, solo un código urbanístico) y ya hay un sitio
    # analizado para ella, se enlaza sola -- además de la clave explícita
    # que pudiera venir en el body (`_clave_cache_sitio_de`), que tiene
    # prioridad por ser más específica (el arquitecto la dio a propósito).
    clave_cache = _clave_cache_sitio_de(body)
    if not clave_cache:
        rc_pliego = pliego["parametros"].get("referencia_catastral") or {}
        if not rc_pliego.get("no_encontrado"):
            clave_cache = rc_pliego.get("valor")
    _vincular_sitio_si_corresponde(clave_cache, proyecto_id)
    return respuesta


@app.route("/api/estilos", methods=["GET"])
def estilos_lista():
    """Los 14 estilos base del motor de estilos (`analyzer.estilos`), para
    que la SPA los muestre como catálogo -- sin IA, `CATALOGO_ESTILOS` es
    un dict fijo del propio módulo."""
    return jsonify(estilos=CATALOGO_ESTILOS, estilo_por_defecto=DEFAULT_ESTILO)


@app.route("/api/proyectos/<proyecto_id>/gltf", methods=["GET"])
def proyecto_gltf(proyecto_id: str):
    """Exporta el edificio del proyecto a `.glb` (`analyzer.gltf_exporter`)
    -- volúmenes sólidos por habitación apilados por planta + una losa de
    cubierta plana, con material PBR según `?estilo=` (clave de catálogo o
    texto libre, mismo `obtener_estilo` del motor de estilos; sin
    parámetro, material por defecto sin ningún estilo aplicado).

    ArchMuse no guarda todavía qué estilo (si alguno) se usó al GENERAR el
    proyecto -- `estilo` aquí es una elección puramente de exportación, no
    un recuerdo de lo que se pidió al crear el proyecto."""
    proyecto = obtener_proyecto(proyecto_id)
    if proyecto is None:
        return jsonify(error="Ese proyecto no existe o no se puede abrir."), 404

    estilo_dict = None
    estilo_param = request.args.get("estilo")
    if estilo_param:
        try:
            estilo_dict = obtener_estilo(estilo_param)
        except ErrorDeEstilo as exc:
            return jsonify(error="No se pudo resolver el estilo pedido: %s" % exc), 400

    try:
        datos_glb = exportar_proyecto_a_glb(proyecto, estilo_dict=estilo_dict)
    except ErrorDeExportacionGltf as exc:
        return jsonify(error=str(exc)), 502

    respuesta = Response(datos_glb, mimetype="model/gltf-binary")
    respuesta.headers["Content-Disposition"] = 'attachment; filename="proyecto-%s.glb"' % proyecto_id
    return respuesta


@app.route("/api/proyectos/<proyecto_id>/georreferencia", methods=["GET"])
def proyecto_georreferencia(proyecto_id: str):
    """Coordenadas/orientación reales del proyecto para el visor Mapbox --
    `analyzer.gltf_exporter.calcular_georreferencia`, a partir del sitio
    que esté enlazado a este proyecto (`storage.obtener_sitio_de_proyecto`).

    Enlazar un sitio a un proyecto ES automático desde `/api/generar`
    (`_vincular_sitio_si_corresponde`, más abajo) cuando la generación venía
    con `sitio_lat`/`sitio_lon` -- así que esto devuelve `georreferenciado:
    false` solo para proyectos que de verdad no tienen ningún sitio
    enlazado (generados sin parcela real, p. ej. "Laboratorio"), no como
    caso de error."""
    proyecto = obtener_proyecto(proyecto_id)
    if proyecto is None:
        return jsonify(error="Ese proyecto no existe o no se puede abrir."), 404

    sitio = obtener_sitio_de_proyecto(proyecto_id)
    georreferencia = calcular_georreferencia(proyecto, sitio)
    if georreferencia is None:
        return jsonify(georreferenciado=False)
    return jsonify(georreferenciado=True, **georreferencia)


@app.route("/api/proyectos/<proyecto_id>/entorno-3d", methods=["GET"])
def proyecto_entorno_3d(proyecto_id: str):
    """Contexto urbano real para el visor 3D (2026-08-16, a petición explícita): centro real de la
    parcela + huellas de los edificios colindantes (geometría completa, `analyzer.sitio.edificios_
    colindantes_geometria`), a partir del mismo sitio enlazado que ya usa `/georreferencia` -- mismo
    criterio de "no disponible, no error" que ese endpoint: un proyecto sin sitio enlazado devuelve
    `disponible: false`, nunca un 404 ni datos inventados.

    Devuelve lat/lon crudos (nunca convertidos a metros aquí) -- la conversión a ejes locales
    este/norte y la rotación por `norte_grados` viven en el cliente (`static/viewer-edificio.js`),
    porque ese mismo cliente ya necesita la misma fórmula para encajar el mosaico de ortofoto; tenerla
    en un único sitio evita que las dos (edificios y ortofoto) puedan desalinearse entre sí.

    La consulta a Overpass es best-effort: si falla (caído, rate-limited -- ya observado en vivo en
    esta misma sesión de trabajo), esto NUNCA hace fallar el endpoint entero -- el centro real de la
    parcela ya es útil por sí solo (ortofoto sin edificios colindantes sigue siendo mucho mejor que el
    suelo sintético de siempre)."""
    proyecto = obtener_proyecto(proyecto_id)
    if proyecto is None:
        return jsonify(error="Ese proyecto no existe o no se puede abrir."), 404

    sitio = obtener_sitio_de_proyecto(proyecto_id)
    coordenadas = ((sitio or {}).get("datos") or {}).get("coordenadas")
    if not coordenadas or coordenadas.get("lat") is None or coordenadas.get("lon") is None:
        return jsonify(disponible=False)

    return jsonify(_entorno_3d_para(coordenadas["lat"], coordenadas["lon"], proyecto.get("norte_grados", 0.0)))


@app.route("/api/proyectos/<proyecto_id>/checklist-campo", methods=["GET"])
def proyecto_checklist_campo(proyecto_id: str):
    """Checklist de inspección en campo (2026-08-16, docs/prd/2026-08-16-checklist-inspeccion-campo.md):
    junta `proyecto` (ciudad/tipología/zona CTE/densidad urbana/orientación, ya guardados con el
    proyecto) + `sitio.datos` (superficie/colindantes/viales/zonas verdes reales de Catastro/Overpass,
    SI el proyecto tiene un sitio enlazado -- mismo patrón exacto que `proyecto_entorno_3d` arriba) en
    un único `datos_parcela`, y llama a la función pura `generar_checklist_campo`.

    Nunca 404 por falta de sitio enlazado (a diferencia de `proyecto_entorno_3d`, que sí necesita
    coordenadas para renderizar un visor 3D) -- un proyecto sin sitio real sigue recibiendo el
    checklist completo, con notas contextuales de menos (`generar_checklist_campo` ya está preparado
    para eso). Solo 404 si el proyecto en sí no existe."""
    proyecto = obtener_proyecto(proyecto_id)
    if proyecto is None:
        return jsonify(error="Ese proyecto no existe o no se puede abrir."), 404

    sitio = obtener_sitio_de_proyecto(proyecto_id)
    sitio_datos = (sitio or {}).get("datos") or {}
    geometria_parcela = sitio_datos.get("geometria_parcela") or {}

    datos_parcela = {
        "ciudad": proyecto.get("ciudad"),
        "tipologia": proyecto.get("tipologia"),
        "zona_cte": proyecto.get("zona_cte"),
        "densidad_urbana": proyecto.get("densidad_urbana"),
        "norte_grados": proyecto.get("norte_grados"),
        "superficie_m2": geometria_parcela.get("superficie_m2"),
        "referencia_catastral": sitio_datos.get("referencia_catastral"),
        "colindantes": sitio_datos.get("colindantes") or [],
        "viales": sitio_datos.get("viales") or [],
        "zonas_verdes": sitio_datos.get("zonas_verdes") or [],
    }
    return jsonify(bloques=generar_checklist_campo(datos_parcela), tiene_sitio_real=sitio is not None)


_ENTORNO_3D_RADIO_M = 180


def _entorno_3d_para(lat: float, lon: float, heading_grados: float) -> dict:
    """Cuerpo compartido de `/api/proyectos/<id>/entorno-3d` y `/api/entorno-3d-punto` (2026-08-17,
    Modo Sandbox): el primero resuelve lat/lon a partir del sitio enlazado a un proyecto ya existente,
    el segundo los recibe directos (en Sandbox todavía no hay ningún proyecto guardado) -- a partir de
    ahí es exactamente el mismo trabajo, así que vive en un único sitio."""
    avisos: list = []
    try:
        edificios = edificios_colindantes_geometria(lat, lon, radio_m=_ENTORNO_3D_RADIO_M)
    except ErrorDeSitio as exc:
        edificios = []
        avisos.append("No se pudieron consultar los edificios colindantes: %s" % exc)

    # Contorno real de parcela (2026-08-16, docs/prd/2026-08-16-sandbox-navegacion-profesional-y-lindes.md):
    # aditivo y best-effort, mismo criterio "no disponible, no error" que el resto de este endpoint --
    # Catastro no siempre tiene una parcela exacta en el punto dado (ver docstring de
    # `geometria_parcela_por_coordenadas`), y eso no debe romper el resto del contexto urbano.
    try:
        geometria_parcela = geometria_parcela_por_coordenadas(lat, lon)
    except ErrorDeSitio as exc:
        geometria_parcela = None
        avisos.append("No se pudo obtener el contorno real de la parcela: %s" % exc)

    return dict(
        disponible=True,
        centro={"lat": lat, "lon": lon},
        heading_grados=heading_grados,
        radio_m=_ENTORNO_3D_RADIO_M,
        edificios_colindantes=edificios,
        geometria_parcela=geometria_parcela,
        avisos=avisos,
    )


@app.route("/api/entorno-3d-punto", methods=["GET"])
def entorno_3d_punto():
    """Igual que `/api/proyectos/<id>/entorno-3d` pero por coordenadas directas, sin ningún proyecto
    de por medio -- Modo Sandbox (2026-08-17): el usuario está dibujando volúmenes sobre una parcela
    real ANTES de que exista ningún proyecto que enlazar. `lat`/`lon` son las mismas coordenadas
    exactas que ya eligió en el Paso 0 (Mapa/Parcela Primero), tal cual, sin redondear -- mismo
    criterio que el resto de ArchMuse sobre no perder precisión en un paso intermedio.

    Cacheado (2026-08-17, docs/prd/2026-08-17-resiliencia-catastro-cache-y-reintentos.md, §14): mismo
    mecanismo SQLite que ya usa `/api/analizar-sitio` (`storage.sitios`, vía `guardar_sitio`/
    `obtener_sitio_por_clave`), NO una caché nueva -- pero con su PROPIO espacio de claves
    (`"entorno3d:%.4f,%.4f"`, prefijo `entorno3d:`), porque el payload de este endpoint (edificios
    colindantes con huella completa a 180 m, `edificios_colindantes_geometria`) es una forma de dato
    distinta de la que cachea `/api/analizar-sitio` bajo la clave sin prefijo (colindantes ligeros a
    80 m, `_colindantes_overpass`) -- reusar la misma clave mezclaría dos formas de "colindantes" bajo
    el mismo nombre de campo.

    Solo se cachea un resultado SIN `avisos` (corregido 2026-08-17, bug crítico reportado en vivo:
    "faltan los colindantes en el visor 3D"). Antes se cacheaba tal cual, avisos incluidos -- medido en
    vivo hoy mismo, Overpass puede tardar hasta 126s y fallar del todo (rate limit/degradado), y ese
    resultado vacío (`edificios_colindantes: []` + aviso de fallo) quedaba grabado en SQLite como si
    fuera un hecho permanente: la siguiente vez que se abriera el Sandbox sobre ESA MISMA parcela, la
    caché servía el hueco vacío en <1s en vez de volver a intentarlo, aunque Overpass ya hubiera vuelto
    a funcionar. Con `_post_overpass` ahora mucho más rápido (espejos + timeouts cortos, ver
    `analyzer/sitio.py`) fallar del todo debería ser raro, pero cuando ocurre de verdad, no cachear
    permite que la SIGUIENTE apertura lo reintente en vez de repetir el fallo para siempre -- mismo
    criterio ya aplicado a `entorno_overpass_por_coordenadas` (flag `entorno_consultado`)."""
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return _error("Faltan 'lat'/'lon' (numéricos) en la petición.", "respuesta_invalida", 400)
    clave_cache = "entorno3d:%.4f,%.4f" % (lat, lon)
    cacheado = obtener_sitio_por_clave(clave_cache)
    if cacheado is not None:
        respuesta = dict(cacheado["datos"])
        respuesta["cache"] = True
        return jsonify(respuesta)
    datos = _entorno_3d_para(lat, lon, 0.0)
    if not datos.get("avisos"):
        guardar_sitio(clave_cache, datos)
    respuesta = dict(datos)
    respuesta["cache"] = False
    return jsonify(respuesta)


@app.route("/api/normativa-urbanistica-punto", methods=["GET"])
def normativa_urbanistica_punto():
    """Normativa urbanística real por coordenada -- piloto Madrid (2026-08-16,
    `docs/prd/2026-08-16-integracion-normativa-catastro-pgou.md`). Mismo patrón que
    `/api/entorno-3d-punto`: GET por lat/lon directos, sin proyecto de por medio (se llama desde el
    Sandbox, en paralelo, no bloqueante). `normativa_urbanistica_por_coordenadas` nunca lanza -- ver su
    propio docstring para el porqué de que `limites_numericos` sea siempre `None` en este incremento.

    Cacheado (2026-08-17, docs/prd/2026-08-17-resiliencia-catastro-cache-y-reintentos.md, §14): mismo
    mecanismo y mismo criterio que `entorno_3d_punto` de arriba -- propio prefijo de clave
    (`"normativa_madrid:%.4f,%.4f"`) porque, otra vez, es una forma de dato distinta (referencia PGOUM
    de Madrid) de lo que ya cachea `/api/analizar-sitio`."""
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return _error("Faltan 'lat'/'lon' (numéricos) en la petición.", "respuesta_invalida", 400)
    clave_cache = "normativa_madrid:%.4f,%.4f" % (lat, lon)
    cacheado = obtener_sitio_por_clave(clave_cache)
    if cacheado is not None:
        respuesta = dict(cacheado["datos"])
        respuesta["cache"] = True
        return jsonify(respuesta)
    datos = normativa_urbanistica_por_coordenadas(lat, lon)
    guardar_sitio(clave_cache, datos)
    respuesta = dict(datos)
    respuesta["cache"] = False
    return jsonify(respuesta)


def _resultado_evaluador_a_dict(resultado):
    """Serializa un resultado de `evaluator.py` (`SolarOccupationResult`/`BuildabilityResult`/
    `MaxFloorsResult`, todos `@dataclass` simples con una propiedad `.message`) a un dict JSON-able, o
    `None` tal cual si la regla no era evaluable -- mismo criterio de honestidad que el propio
    `evaluator.py` (`Optional[...]`, nunca un 0 inventado en su lugar)."""
    if resultado is None:
        return None
    return dict(dataclasses.asdict(resultado), message=resultado.message)


@app.route("/api/validar-urbanismo", methods=["POST"])
def validar_urbanismo():
    """Reconciliación de las métricas urbanísticas que el Sandbox (`viewer-sandbox.js`) ya calcula en
    cliente para respuesta instantánea, contra las MISMAS funciones reales de `evaluator.py`
    (2026-08-16, docs/prd/2026-08-16-conexion-3d-hallazgos-motor-reglas.md) -- ninguna regla normativa
    nueva se define aquí, solo se reutilizan `evaluate_solar_occupation`/`evaluate_buildability`/
    `evaluate_max_floors` tal cual ya usa `/api/generar`.

    Body: {"superficie_solar_m2": float, "volumenes": [{"largo", "ancho", "plantas"}, ...],
    "normativa": {"ocupacion_maxima_pct", "edificabilidad_maxima", "plantas_maximas"}}. `volumenes` y
    `normativa` son opcionales/pueden venir vacíos (Sandbox sin ningún volumen todavía, o sin ningún
    límite informado) -- en ese caso las funciones de `evaluator.py` ya devuelven `None` por su cuenta,
    no hay que replicar esa lógica aquí.

    Ocupación/edificabilidad se calculan como SUMA de huellas (`largo * ancho` por volumen), no como
    unión geométrica real -- misma aproximación explícita que usa el cliente (PRD §6/§9): si dos
    volúmenes se solapan, este endpoint sobreestima igual que el cliente, a propósito, para que
    "reconciliar" compare lo mismo en los dos sitios."""
    body = request.get_json(silent=True) or {}
    superficie_solar_m2 = body.get("superficie_solar_m2")
    volumenes = body.get("volumenes") or []
    normativa = body.get("normativa") or {}

    if not isinstance(volumenes, list):
        return _error("'volumenes' debe ser una lista.", "respuesta_invalida", 400)

    superficie_planta_baja_m2 = 0.0
    superficie_total_construida_m2 = 0.0
    plantas_max_volumen = 0
    for vol in volumenes:
        largo = float(vol.get("largo") or 0)
        ancho = float(vol.get("ancho") or 0)
        plantas = int(vol.get("plantas") or 0)
        huella = largo * ancho
        superficie_planta_baja_m2 += huella
        superficie_total_construida_m2 += huella * plantas
        plantas_max_volumen = max(plantas_max_volumen, plantas)

    ocupacion = evaluate_solar_occupation(superficie_planta_baja_m2, superficie_solar_m2, normativa)
    edificabilidad = evaluate_buildability(superficie_total_construida_m2, superficie_solar_m2, normativa)
    plantas = evaluate_max_floors({"plantas": plantas_max_volumen}, normativa)

    return jsonify(
        ocupacion=_resultado_evaluador_a_dict(ocupacion),
        edificabilidad=_resultado_evaluador_a_dict(edificabilidad),
        plantas=_resultado_evaluador_a_dict(plantas),
    )


def _guardar_traza_de_generacion(params: dict, project, proyecto_id: str) -> None:
    """Fase F, tarea D: conecta `TrazaDeGeneracion` (diseñada en Fase A,
    nunca escrita hasta ahora) con una generación real. Solo se construye y
    persiste cuando el request de verdad venía del entrevistador — la señal
    es `contexto_cualitativo.especificacion_id`, el único dato que
    identifica DE QUÉ Especificación salió esta generación; sin él no hay
    nada real que trazar (`TrazaDeGeneracion.especificacion_id` es
    obligatorio en el esquema de Fase A, y este módulo no inventa uno).
    Una llamada del formulario técnico antiguo, o con `contexto_cualitativo`
    ausente/mal formado, no escribe ninguna fila — mismo comportamiento
    exacto que antes de esta fase.

    No revalida nada de lo que ya validó `ai_generator.py` (directivas,
    verificaciones): solo traduce lo que `project` ya trae a las
    dataclasses de `analyzer.interview.modelo` y llama a
    `guardar_traza_generacion()`, ya implementada desde la Fase A."""
    contexto_cualitativo = params.get("contexto_cualitativo")
    if not isinstance(contexto_cualitativo, dict):
        return
    especificacion_id = contexto_cualitativo.get("especificacion_id")
    if not isinstance(especificacion_id, str) or not especificacion_id.strip():
        return

    traza = interview_modelo.TrazaDeGeneracion(
        traza_id=interview_modelo.nuevo_id(),
        especificacion_id=especificacion_id.strip(),
        proyecto_id=proyecto_id,
        directivas_enviadas=[
            interview_modelo.DirectivaCualitativa(
                especificacion_id=d["especificacion_id"],
                categoria=d["categoria"],
                fuerza=d["fuerza"],
                texto_origen=d["texto_origen"],
                texto_prompt=d["texto_prompt"],
                verificable_geometricamente=d["verificable_geometricamente"],
            )
            for d in project.directivas_aplicadas
        ],
        respuesta_ia=interview_modelo.RespuestaIAResumen(
            justificacion=project.justificacion,
            referencias_especificacion=project.referencias_especificacion,
        ),
        verificaciones_deterministas=[
            interview_modelo.VerificacionDeterminista(
                especificacion_id=v["especificacion_id"], metodo=v["metodo"], resultado=v["resultado"],
            )
            for v in project.verificaciones_directivas
        ],
        reintento_disparado=project.reintento_disparado_por is not None,
        motivo_reintento=project.reintento_disparado_por,
    )
    # No lanza ni bloquea la respuesta HTTP si el proyecto ya no existiera
    # por algún motivo (`guardar_traza_generacion` devuelve False, nunca
    # levanta) — la generación en sí ya tuvo éxito y ya se devolvió/guardó;
    # perder la traza es peor que no perder el proyecto, nunca al revés.
    guardar_traza_generacion(traza)


# =============================================================================
# ENTREVISTADOR (Fase B) — adaptadores HTTP puros sobre analyzer.interview.*
# =============================================================================
#
# Ningún endpoint de esta sección decide una pregunta, interpreta una
# respuesta, detecta una contradicción, ni compila un `params` a mano: eso ya
# lo hacen `interview_motor`/`interview_compilador` (Fases C/D, ya cerradas y
# auditadas). Este bloque solo: valida forma del body, traduce
# `EstadoEntrevista`/`ResultadoCierre`/`PreguntaSiguiente` a JSON, persiste
# tras cada transición, y traduce las excepciones/resultados del motor a
# códigos HTTP — nada más.
#
# Deliberadamente NO implementado en esta fase (ver informe de cierre):
# - `PATCH /api/entrevista/<id>/especificacion` (corrección con invalidación
#   en cascada, B6 del plan) — no está entre los 6 mínimos de este encargo.
# - Extender `_parse_generar_params` con la clave `contexto_cualitativo`
#   (B8 del plan) — nada en esta fase hace una llamada HTTP real a
#   `/api/generar` con ese dato; el cliente (Fase E) compone `params` +
#   `contexto_cualitativo` (ambos ya disponibles por separado en la
#   respuesta de `/especificacion`) cuando de verdad haga esa llamada. No se
#   ha tocado `ai_generator.py` ni `_parse_generar_params` en absoluto.


def _construir_interprete_entrevista():
    """El único punto de `app.py` que llega a construir un cliente de
    Claude para el entrevistador — mismo patrón de guarda que
    `ai_generator.generate_project()` ya usa para el generador: si
    `anthropic` no está instalado o falta `ANTHROPIC_API_KEY`,
    `ClienteAnthropicInterprete()` lanza `InterpretacionError` en el
    constructor; aquí se convierte en `None` — `interview_motor.responder()`
    ya sabe qué hacer con `interprete=None` (fallar solo si de verdad hacía
    falta, nunca si el turno era 100% determinista)."""
    try:
        return ClienteAnthropicInterprete()
    except InterpretacionError:
        return None


def _pregunta_a_dict(p) -> dict:
    return {
        "pregunta_id": p.pregunta_id,
        "categoria": p.categoria,
        "tipo": p.tipo,
        "texto": p.texto,
        "opciones": list(p.opciones) if p.opciones else None,
        # "Materiales y Calidades" (2026-08-15): asesoramiento breve por opción (`preguntas.Pregunta.
        # asesoramiento`), `None` para cualquier pregunta que no lo tenga -- la inmensa mayoría.
        "asesoramiento": dict(p.asesoramiento) if p.asesoramiento else None,
    }


def _pregunta_siguiente_a_dict(ps):
    if ps is None:
        return None
    if ps.es_resolucion_contradiccion:
        return {
            "es_resolucion_contradiccion": True,
            "contradiccion_id": ps.contradiccion_id,
            "texto_resolucion": ps.texto_resolucion,
        }
    return {
        "es_resolucion_contradiccion": False,
        "preguntas": [_pregunta_a_dict(p) for p in ps.preguntas],
        "aviso": ps.aviso,
    }


def _cierre_a_dict(rc) -> dict:
    return {
        "puede_cerrar": rc.puede_cerrar,
        "imprescindibles_pendientes": list(rc.imprescindibles_pendientes),
        "contradicciones_pendientes": list(rc.contradicciones_pendientes),
        "limite_turnos_alcanzado": rc.limite_turnos_alcanzado,
        "limite_llamadas_alcanzado": rc.limite_llamadas_alcanzado,
        "motivo": rc.motivo,
    }


def _entrevista_a_dict(estado: interview_modelo.EstadoEntrevista) -> dict:
    """Estado público de una sesión — `GET /api/entrevista/<id>` y la
    respuesta de `POST .../responder` devuelven exactamente esto: cubre a
    la vez "obtener estado" y "obtener siguiente pregunta" (`pregunta_actual`
    se deriva en el momento con `siguiente_pregunta()`, puro y determinista,
    nunca se persiste por separado)."""
    return {
        "sesion_id": estado.sesion_id,
        "estado": estado.estado,
        "modo": estado.modo,
        "modo_entrada": estado.modo_entrada,
        "turnos_totales": estado.turnos_totales,
        "llamadas_ia_consumidas": estado.llamadas_ia_consumidas,
        "pregunta_actual": _pregunta_siguiente_a_dict(interview_motor.siguiente_pregunta(estado)),
        "cierre": _cierre_a_dict(interview_motor.evaluar_cierre(estado)),
        "pasos_estimados_totales": interview_motor.estimar_pasos_totales(estado),
        "puede_deshacer": interview_motor.puede_deshacer(estado),
    }


def _error(mensaje: str, codigo: str, http_status: int, **extra):
    return jsonify(error=mensaje, error_code=codigo, **extra), http_status


@app.route("/api/entrevista", methods=["POST"])
def entrevista_crear():
    """B2 del plan. Body opcional: `{"modo_entrada": "entrevista_guiada" |
    "edicion_experta", "valores": {...}}` — `valores` solo se usa si
    `modo_entrada == "edicion_experta"` (Decisión Pablo #6 / D7: el mismo
    compilador, aquí simplemente se elige qué función construye el
    `EstadoEntrevista` inicial, `interview_motor.iniciar_entrevista()` o
    `interview_compilador.estado_desde_valores_expertos()` — no hay una
    segunda ruta de endpoints para modo experto, es un parámetro de esta
    misma)."""
    body = request.get_json(silent=True) or {}
    modo_entrada = body.get("modo_entrada", "entrevista_guiada")
    if modo_entrada not in interview_modelo.MODOS_ENTREVISTA:
        return _error(
            "modo_entrada debe ser uno de %s." % (interview_modelo.MODOS_ENTREVISTA,), "respuesta_invalida", 400
        )

    if modo_entrada == "edicion_experta":
        valores = body.get("valores") or {}
        if not isinstance(valores, dict):
            return _error("'valores' debe ser un objeto {especificacion_id: valor}.", "respuesta_invalida", 400)
        estado = interview_compilador.estado_desde_valores_expertos(valores)
    else:
        estado = interview_motor.iniciar_entrevista(modo_entrada=modo_entrada)
        # "Omite las preguntas geográficas redundantes" (2026-08-15, a petición explícita): si el Paso 0
        # ("Mapa/Parcela Primero") ya resolvió ciudad/superficie con Catastro real, se siembran como Hecho
        # ANTES del primer turno -- así la cola priorizada del motor (`_candidatas_adaptativas`) las
        # descarta sola, sin ningún filtrado especial aquí. Nunca con `anadir_valores_expertos()` (mutaría
        # `estado.modo`); ver `interview_motor.sembrar_hecho_externo`. Si el usuario eligió "Laboratorio"
        # (sin parcela real) en el Paso 0, el frontend simplemente no manda `parcela` y esto no hace nada --
        # las preguntas geográficas siguen su curso normal.
        parcela = body.get("parcela")
        if isinstance(parcela, dict):
            ciudad = parcela.get("ciudad")
            if isinstance(ciudad, str) and ciudad.strip():
                interview_motor.sembrar_hecho_externo(
                    estado, "contexto.ciudad", ciudad.strip(),
                    "ciudad/municipio detectada automáticamente en el Paso 0 (Catastro/mapa)",
                )
            superficie = parcela.get("superficie_m2")
            if isinstance(superficie, (int, float)) and not isinstance(superficie, bool) and superficie > 0:
                interview_motor.sembrar_hecho_externo(
                    estado, "solar.superficie_m2", float(superficie),
                    "superficie real de la parcela obtenida de Catastro en el Paso 0",
                )

    guardar_entrevista(estado)
    return jsonify(_entrevista_a_dict(estado)), 201


@app.route("/api/entrevista/<sesion_id>", methods=["GET"])
def entrevista_obtener(sesion_id: str):
    """B4 del plan. Reanudar tras un reinicio del proceso produce
    exactamente el mismo estado: no hay nada en memoria del proceso que
    `obtener_entrevista()` no reconstruya desde SQLite."""
    datos = obtener_entrevista(sesion_id)
    if datos is None:
        return _error("Esa entrevista no existe.", "entrevista_inexistente", 404)
    return jsonify(_entrevista_a_dict(datos["estado"]))


@app.route("/api/entrevista/<sesion_id>/responder", methods=["POST"])
def entrevista_responder(sesion_id: str):
    """B3 del plan. Body: `{"respuestas": {pregunta_id: valor, ...}}` para
    un turno normal, o `{"valor_elegido": ...}` cuando lo pendiente es
    resolver una contradicción (`pregunta_actual.es_resolucion_contradiccion
    == true` en la última respuesta de `GET`/`responder`) — este endpoint
    nunca decide cuál de los dos toca: se lo pregunta a
    `interview_motor.siguiente_pregunta()` y actúa en consecuencia."""
    datos = obtener_entrevista(sesion_id)
    if datos is None:
        return _error("Esa entrevista no existe.", "entrevista_inexistente", 404)
    estado = datos["estado"]
    if estado.estado != "en_curso":
        return _error(
            "La entrevista no está en curso (estado=%r); no se puede responder." % estado.estado,
            "estado_incompatible", 409,
        )

    ps = interview_motor.siguiente_pregunta(estado)
    if ps is None:
        return _error(
            "No queda ninguna pregunta pendiente; usa /finalizar para cerrar la entrevista.",
            "estado_incompatible", 409,
        )

    body = request.get_json(silent=True) or {}

    if ps.es_resolucion_contradiccion:
        if "valor_elegido" not in body:
            return _error(
                "Hay una contradicción pendiente (contradiccion_id=%s); el body debe incluir 'valor_elegido'."
                % ps.contradiccion_id,
                "contradiccion_pendiente", 409, contradiccion_id=ps.contradiccion_id,
            )
        interview_motor.responder_contradiccion(estado, ps.contradiccion_id, body["valor_elegido"])
    else:
        respuestas_crudas = body.get("respuestas")
        if not isinstance(respuestas_crudas, dict):
            return _error("El body debe incluir 'respuestas': {pregunta_id: valor, ...}.", "respuesta_invalida", 400)
        try:
            interview_motor.responder(estado, ps, respuestas_crudas, interprete=_construir_interprete_entrevista())
        except interview_motor.InterpretacionRequeridaError:
            return _error(
                "Esta respuesta necesita interpretación de IA y no hay ninguna disponible ahora mismo "
                "(configura ANTHROPIC_API_KEY).", "ia_no_disponible", 503,
            )

    # `datos["especificacion"]` se preserva tal cual: este endpoint nunca
    # recompila ni borra una especificación ya confirmada (ver
    # `guardar_entrevista`: sin esto, el upsert la pondría a NULL).
    guardar_entrevista(estado, especificacion=datos.get("especificacion"))
    return jsonify(_entrevista_a_dict(estado))


@app.route("/api/entrevista/<sesion_id>/deshacer", methods=["POST"])
def entrevista_deshacer(sesion_id: str):
    """Navegación hacia atrás en la Entrevista Guiada (2026-08-15, a petición explícita): deshace el turno
    más reciente -- ver `interview_motor.deshacer_ultimo_turno`. Sin body. Nunca llama a Claude (es la
    operación inversa exacta de lo que `responder()` ya escribió), así que a diferencia de `/responder` no
    puede devolver 503 por falta de IA."""
    datos = obtener_entrevista(sesion_id)
    if datos is None:
        return _error("Esa entrevista no existe.", "entrevista_inexistente", 404)
    estado = datos["estado"]
    if estado.estado != "en_curso":
        return _error(
            "La entrevista no está en curso (estado=%r); no se puede deshacer nada." % estado.estado,
            "estado_incompatible", 409,
        )
    if not interview_motor.puede_deshacer(estado):
        return _error(
            "No hay ningún turno anterior al que volver.", "estado_incompatible", 409,
        )

    interview_motor.deshacer_ultimo_turno(estado)
    # Mismo criterio que `/responder`: la especificación ya confirmada (si la hay) no se toca aquí.
    guardar_entrevista(estado, especificacion=datos.get("especificacion"))
    return jsonify(_entrevista_a_dict(estado))


@app.route("/api/entrevista/<sesion_id>/finalizar", methods=["POST"])
def entrevista_finalizar(sesion_id: str):
    """B5 del plan. Body opcional: `{"forzar": bool}`. Sin `forzar`, cerrar
    una entrevista que no cumple el criterio de `evaluar_cierre()` es un
    error explícito (409), nunca un cierre silencioso con huecos."""
    datos = obtener_entrevista(sesion_id)
    if datos is None:
        return _error("Esa entrevista no existe.", "entrevista_inexistente", 404)
    estado = datos["estado"]
    if estado.estado != "en_curso":
        return _error(
            "La entrevista no está en curso (estado=%r)." % estado.estado, "estado_incompatible", 409,
        )

    body = request.get_json(silent=True) or {}
    forzar = bool(body.get("forzar", False))

    resultado_cierre = interview_motor.evaluar_cierre(estado)
    if not resultado_cierre.puede_cerrar and not forzar:
        codigo = "contradiccion_pendiente" if resultado_cierre.contradicciones_pendientes else "entrevista_incompleta"
        return _error(
            "La entrevista todavía no se puede cerrar: %s" % resultado_cierre.motivo, codigo, 409,
            cierre=_cierre_a_dict(resultado_cierre),
        )

    interview_motor.cerrar_entrevista(estado, forzado=forzar)
    guardar_entrevista(estado, especificacion=datos.get("especificacion"))
    return jsonify(_entrevista_a_dict(estado))


@app.route("/api/entrevista/<sesion_id>/valores_expertos", methods=["POST"])
def entrevista_valores_expertos(sesion_id: str):
    """Puente de datos técnicos — corrección de 2026-08-13 (hallazgo
    "trazabilidad epistemológica del puente" de la auditoría del
    entrevistador). Body: `{"valores": {especificacion_id: valor}}`.

    A diferencia de `POST /api/entrevista {modo_entrada: "edicion_experta"}`
    (que sigue existiendo tal cual, sin cambios, para quien empieza en modo
    experto desde el principio — B2), este endpoint **añade** valores a una
    sesión YA EXISTENTE en vez de crear una nueva: es la corrección para el
    "puente" que aparece cuando `/especificacion` devuelve 422 con una
    entrevista guiada real detrás. Ver
    `interview_compilador.anadir_valores_expertos()` para el porqué —
    resumen: crear una sesión sintética nueva ahí (como se hacía antes)
    aplanaba a Hecho toda Hipótesis/Inferencia ya recogida por la
    conversación real, y dejaba la sesión original huérfana en `en_curso`
    para siempre. Con este endpoint no hay "sesión original" que abandonar:
    es la misma sesión, de principio a fin.

    Deliberadamente no exige `estado.estado == "en_curso"` (mismo motivo que
    `anadir_valores_expertos()`): en el flujo real, `/finalizar` ya se llamó
    antes de que el puente pueda aparecer."""
    datos = obtener_entrevista(sesion_id)
    if datos is None:
        return _error("Esa entrevista no existe.", "entrevista_inexistente", 404)
    estado = datos["estado"]

    body = request.get_json(silent=True) or {}
    valores = body.get("valores")
    if not isinstance(valores, dict) or not valores:
        return _error(
            "El body debe incluir 'valores': {especificacion_id: valor, ...}, no vacío.",
            "respuesta_invalida", 400,
        )

    interview_compilador.anadir_valores_expertos(estado, valores)
    # Igual que en /responder: la especificación ya confirmada (si la
    # hubiera) se preserva tal cual, nunca se borra por un upsert sin ella.
    guardar_entrevista(estado, especificacion=datos.get("especificacion"))
    return jsonify(_entrevista_a_dict(estado))


@app.route("/api/entrevista/<sesion_id>/especificacion", methods=["POST"])
def entrevista_especificacion(sesion_id: str):
    """"Obtener/confirmar especificación" del encargo — un único endpoint:
    siempre compila y valida (funciona con la entrevista todavía en_curso,
    para poder mostrar un resumen parcial); solo cuando compila params
    también sin errores se considera "confirmada" y se persiste. Nunca
    responde 200 con una especificación incompleta u óptimamente
    compilada (regla explícita del encargo) — inválida o sin params
    compilables son ambas 422, con el detalle exacto de qué falta."""
    datos = obtener_entrevista(sesion_id)
    if datos is None:
        return _error("Esa entrevista no existe.", "entrevista_inexistente", 404)
    estado = datos["estado"]

    especificacion = interview_compilador.compilar_especificacion(estado)
    validacion = interview_compilador.validar_especificacion(especificacion)
    if not validacion.valida:
        return _error(
            "La especificación no es válida todavía.", "especificacion_invalida", 422,
            errores=validacion.errores, avisos=validacion.avisos, especificacion=especificacion.a_dict(),
        )

    resultado_params = interview_compilador.compilar_params(especificacion)
    if resultado_params.params is None:
        return _error(
            "La especificación es válida pero no se puede compilar a params todavía.", "error_compilacion", 422,
            errores=resultado_params.errores, avisos=validacion.avisos, especificacion=especificacion.a_dict(),
        )

    guardar_entrevista(estado, especificacion=especificacion)
    return jsonify(especificacion=especificacion.a_dict(), avisos=validacion.avisos, params=resultado_params.params)


@app.route("/api/informe-pdf", methods=["POST"])
def informe_pdf():
    data = request.get_json(silent=True) or {}
    try:
        pdf_bytes = generate_pdf(data)
    except Exception as exc:  # noqa: BLE001 - JSON arbitrario enviado por el cliente
        return jsonify(error=f"No se pudo generar el informe PDF: {exc}"), 400

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=informe.pdf"},
    )


@app.route("/api/exportar-cuadro-superficies", methods=["POST"])
def exportar_cuadro_superficies_endpoint():
    """Fase 4 -- recibe otra vez el DXF ya analizado (mismo campo `dxf` que
    `/api/analizar`) y devuelve como descarga la copia con el cuadro de
    superficies relleno (`analyzer/cuadro_superficies_export.py`, Fase 3).

    **Por qué se vuelve a subir el archivo, en vez de reutilizar el `doc` de
    `/api/analizar`:** ArchMuse no persiste el DXF original en ningún sitio
    (`analyzer/storage.py` solo guarda el JSON del análisis, nunca los bytes
    del plano) -- guardarlo aparte para esto habría sido almacenamiento
    permanente nuevo, justo lo que el encargo prohíbe. La SPA ya tiene el
    `File` en memoria desde que se analizó (`state.archivoAnalizado`,
    `static/app.js`), así que reenviarlo es gratis y no exige tocar
    `analyzer/storage.py` ni el esquema de la base de datos.

    Todo lo que se escribe vive en un directorio temporal del sistema
    (`tempfile.mkdtemp`, nunca el repositorio ni la carpeta del usuario), y se
    borra de forma SÍNCRONA antes de responder -- se lee la copia entera a
    memoria primero y se sirve desde ahí. (`response.call_on_close` se probó
    primero y no es fiable aquí: con `send_file` en modo passthrough, en
    Windows, el archivo puede seguir abierto cuando el callback se dispara,
    y `shutil.rmtree` falla o no llega a ejecutarse -- verificado con una
    fuga real de directorio temporal antes de este cambio.) El único
    resultado que persiste es el que el propio navegador guarda, donde el
    usuario decida.

    No duplica ningún cálculo: `exportar_cuadro_relleno` (Fase 3) ya hace la
    detección, el cálculo del borrador (`cuadro_superficies.py`, Fase 2) y la
    escritura -- esta vista solo gestiona el upload/descarga HTTP.
    """
    file = request.files.get("dxf")
    if file is None or file.filename == "":
        return jsonify(error="Selecciona un archivo DXF antes de exportar."), 400
    if not file.filename.lower().endswith(".dxf"):
        return jsonify(error="El archivo debe tener extensión .dxf."), 400

    filename = secure_filename(file.filename) or "plano.dxf"
    nombre_salida = filename[:-4] + "_ArchMuse_relleno.dxf"  # ya se comprobó que termina en .dxf

    tmp_dir = tempfile.mkdtemp(prefix="archmuse_cuadro_")
    try:
        origen = os.path.join(tmp_dir, filename)
        file.save(origen)
        destino = os.path.join(tmp_dir, nombre_salida)
        resultado = exportar_cuadro_relleno(origen, destino)
    except ValueError as exc:
        # Sin cuadro reconocible, sin vivienda única, o cualquier otra
        # condición ya validada por `exportar_cuadro_relleno`: mensaje claro,
        # nada tocado -- el análisis ya mostrado en la SPA no depende de esta
        # llamada en absoluto.
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify(error=str(exc)), 400
    except Exception as exc:  # noqa: BLE001 - límite del sistema: DXF arbitrario reenviado por el cliente
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify(error=f"No se pudo generar el DXF rellenado: {exc}"), 400

    try:
        with open(resultado.ruta_destino, "rb") as f:
            contenido = f.read()
    finally:
        # Síncrono, antes de responder -- ver docstring. `contenido` ya está
        # en memoria, así que no hace falta que el archivo siga vivo.
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return Response(
        contenido,
        mimetype="application/dxf",
        headers={"Content-Disposition": 'attachment; filename="%s"' % nombre_salida},
    )


@app.route("/api/exportar-dxf-planta", methods=["POST"])
def exportar_dxf_planta():
    """`docs/prd/2026-08-17-viabilidad-economica-y-exportacion-dxf.md`, tarea
    2 del plan de implementación -- botón "Descargar DXF / CAD" de la planta
    activa. A diferencia de `/api/exportar-cuadro-superficies` (que exige
    volver a subir un DXF real ya existente), esta exportación construye un
    `.dxf` DESDE CERO a partir de los contornos de habitación que la SPA ya
    tiene en memoria para la planta que se está viendo -- vale igual para un
    proyecto generado por IA (sin ningún DXF de origen) que para uno
    analizado desde un DXF real, porque en ambos casos el dato de entrada es
    el mismo: `habitaciones` con su `poligono`/`nombre` (el mismo formato que
    ya consume `analyzer/plan_svg.py`, ver `api_serializer.py`). Por eso no
    hace falta ni `proyecto_id` ni ningún fichero: la vivienda no tiene por
    qué estar guardada todavía.

    Nunca persiste nada -- se construye el documento en memoria
    (`exportar_planta_dxf`, función pura) y se sirve directamente, mismo
    criterio de "nada se queda en el servidor" que el resto de descargas
    DXF."""
    body = request.get_json(silent=True) or {}
    habitaciones = body.get("habitaciones")
    if not isinstance(habitaciones, list) or not habitaciones:
        return jsonify(error="No hay ninguna planta activa con habitaciones que exportar."), 400

    nombre_vivienda = str(body.get("nombre_vivienda") or "planta").strip() or "planta"
    nombre_archivo = secure_filename(nombre_vivienda) or "planta"
    nombre_salida = f"{nombre_archivo}_ArchMuse_contornos.dxf"

    try:
        doc = exportar_planta_dxf(habitaciones)
    except Exception as exc:  # noqa: BLE001 - límite del sistema: datos de planta arbitrarios reenviados por el cliente
        return jsonify(error=f"No se pudo generar el DXF ({exc})."), 400

    buffer = io.StringIO()
    doc.write(buffer)
    contenido = buffer.getvalue().encode("utf-8")

    return Response(
        contenido,
        mimetype="application/dxf",
        headers={"Content-Disposition": 'attachment; filename="%s"' % nombre_salida},
    )


@app.route("/api/exportar-ifc-planta", methods=["POST"])
def exportar_ifc_planta():
    """`docs/prd/2026-08-17-exportacion-bim-ifc.md` (aprobado 2026-08-17,
    opción A de §14) -- botón "Exportar Espacios BIM (.IFC)" de la planta
    activa. Mismo patrón que `/api/exportar-dxf-planta`: sin `proyecto_id`,
    construye el `.ifc` en memoria a partir de los contornos que la SPA ya
    tiene (`habitaciones` con `poligono`/`nombre`/`area_m2`/`tipo`), sin
    persistir nada en el servidor.

    Exportación ESTRICTA de `IfcSpace` (`analyzer/ifc_export.py`) -- nunca
    `IfcWall`/`IfcSlab`/`IfcDoor`/`IfcWindow` ficticios."""
    body = request.get_json(silent=True) or {}
    habitaciones = body.get("habitaciones")
    if not isinstance(habitaciones, list) or not habitaciones:
        return jsonify(error="No hay ninguna planta activa con habitaciones que exportar."), 400

    nombre_vivienda = str(body.get("nombre_vivienda") or "planta").strip() or "planta"
    nombre_archivo = secure_filename(nombre_vivienda) or "planta"
    nombre_salida = f"{nombre_archivo}_ArchMuse_espacios.ifc"

    try:
        doc = exportar_espacios_ifc(habitaciones, nombre_planta=nombre_vivienda)
    except Exception as exc:  # noqa: BLE001 - límite del sistema: datos de planta arbitrarios reenviados por el cliente
        return jsonify(error=f"No se pudo generar el IFC ({exc})."), 400

    contenido = doc.to_string().encode("utf-8")

    return Response(
        contenido,
        mimetype="application/x-step",
        headers={"Content-Disposition": 'attachment; filename="%s"' % nombre_salida},
    )


@app.route("/api/dossier-pdf", methods=["POST"])
def dossier_pdf():
    """`docs/prd/2026-08-17-dossier-inversion-pdf.md` (aprobado 2026-08-17)
    -- botón "Generar Dossier de Inversión". Sin `proyecto_id` obligatorio
    (mismo criterio que `/api/exportar-dxf-planta`/`/api/exportar-ifc-
    planta`): el cliente manda todo lo que ya tiene en memoria (urbanismo,
    viviendas, viabilidad ya calculada) más, opcionalmente, `proyecto_id`
    para recuperar el Sólido Capaz ya persistido si no llegó ya resuelto.

    El render 3D (`render_3d_base64`) lo captura el propio cliente de su
    `<canvas>` -- este endpoint nunca renderiza 3D. El mapa de ubicación se
    pide aquí mismo a Mapbox Static Images con el `MAPBOX_TOKEN` ya
    disponible en el servidor (`app.py:161`, hasta ahora solo expuesto al
    cliente para el visor 3D)."""
    body = request.get_json(silent=True) or {}

    solido_capaz = body.get("solido_capaz")
    proyecto_id = body.get("proyecto_id")
    if solido_capaz is None and proyecto_id:
        solido_capaz = obtener_solido_capaz(proyecto_id)

    datos = {
        "nombre_proyecto": body.get("nombre_proyecto"),
        "nombre_promotora": body.get("nombre_promotora"),
        "logo_base64": body.get("logo_base64"),
        "ubicacion": body.get("ubicacion"),
        "mapbox_token": os.environ.get("MAPBOX_TOKEN"),
        "solido_capaz": solido_capaz,
        "superficie_solar_m2": body.get("superficie_solar_m2"),
        "superficie_total_construida_m2": body.get("superficie_total_construida_m2"),
        "viviendas": body.get("viviendas"),
        "viabilidad": body.get("viabilidad"),
        "render_3d_base64": body.get("render_3d_base64"),
    }

    try:
        pdf_bytes = generar_dossier_pdf(datos)
    except Exception as exc:  # noqa: BLE001 - límite del sistema: datos de proyecto arbitrarios reenviados por el cliente
        return jsonify(error=f"No se pudo generar el dossier ({exc})."), 400

    nombre_archivo = secure_filename(str(datos["nombre_proyecto"] or "proyecto")) or "proyecto"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="%s_Dossier_ArchMuse.pdf"' % nombre_archivo},
    )


@app.route("/api/viabilidad-financiera", methods=["POST"])
def viabilidad_financiera():
    """`docs/prd/2026-08-17-analisis-de-viabilidad-financiera.md` (aprobado
    2026-08-17) -- bloque "Análisis Avanzado" de la pestaña de Viabilidad
    Económica: Margen Promotor (%), Cash Flow estático, Ratio de Eficiencia
    de Superficie y sensibilidad ±10% de coste.

    Mismo criterio que `/api/exportar-dxf-planta`: sin `proyecto_id`, sin
    persistencia -- el cliente manda los datos que ya tiene en memoria
    (superficies) más los que el propio usuario ha introducido en el
    formulario (costes/precio), y aquí solo se calcula. Toda la lógica
    numérica vive en `analyzer/feasibility.py` (módulo puro), reutilizado
    también por `analyzer/dossier_pdf.py` para que el PDF nunca pueda
    mostrar un número distinto al que ya vio el usuario en pantalla.

    Cualquier campo ausente o no numérico se trata como "no introducido
    todavía" (`None`), nunca como 0 -- ver `_num_o_none`."""
    body = request.get_json(silent=True) or {}

    def _num_o_none(clave):
        valor = body.get(clave)
        if valor is None or valor == "":
            return None
        try:
            return float(valor)
        except (TypeError, ValueError):
            return None

    costes = CostesPromotor(
        pem=_num_o_none("pem"),
        coste_suelo=_num_o_none("costeSuelo"),
        costes_indirectos_pct=_num_o_none("costesIndirectosPct"),
        licencias_pct=_num_o_none("licenciasPct"),
        honorarios_pct=_num_o_none("honorariosPct"),
        coste_financiero_pct=_num_o_none("costeFinancieroPct"),
    )
    ingresos_venta = _num_o_none("precioVenta")

    margen = calcular_margen_promotor(costes, ingresos_venta)
    cash_flow = calcular_cash_flow_estatico(costes, ingresos_venta)
    sensibilidad = analisis_sensibilidad(costes, ingresos_venta)
    ratio_eficiencia = ratio_eficiencia_superficie(
        _num_o_none("superficieUtilM2"), _num_o_none("superficieConstruidaM2"),
    )

    return jsonify(
        margen_promotor={
            "inversion_total": margen.inversion_total,
            "ingresos_venta": margen.ingresos_venta,
            "margen_eur": margen.margen_eur,
            "margen_pct": margen.margen_pct,
        },
        cash_flow=[{"concepto": f.concepto, "importe": f.importe} for f in cash_flow],
        sensibilidad=[
            {
                "variacion_coste_pct": e.variacion_coste_pct,
                "margen_eur": e.margen.margen_eur,
                "margen_pct": e.margen.margen_pct,
            }
            for e in sensibilidad
        ],
        ratio_eficiencia_superficie=ratio_eficiencia,
    )


def _serializar_solicitud(s) -> dict:
    """`cuadro_superficies.Solicitud`/`CandidatoAsignacion` -> JSON. Solo
    lectura de campos ya calculados -- no decide qué preguntar, eso vive
    entero en `analyzer/cuadro_superficies.detectar_solicitudes` (Fase 5a)."""
    return {
        "id": s.id,
        "tipo": s.tipo,
        "campos": list(s.campos),
        "titulo": s.titulo,
        "ayuda": s.ayuda,
        "unidad": s.unidad,
        "candidatos": [
            {"id": c.id, "etiqueta": c.room_label, "area_m2": c.area_m2, "x": c.x, "y": c.y}
            for c in s.candidatos
        ],
    }


@app.route("/api/cuadro-superficies/solicitudes", methods=["POST"])
def cuadro_superficies_solicitudes_endpoint():
    """Fase 5b -- dado el mismo DXF ya analizado (campo `dxf`, igual que
    `/api/exportar-cuadro-superficies`), qué hay que preguntarle al
    arquitecto para poder completar el cuadro entero
    (`cuadro_superficies_export.obtener_solicitudes`, que reutiliza
    `detectar_solicitudes` de la Fase 5a sin duplicar nada). Solo lectura:
    no escribe nada, no ofrece descarga. Lista vacía = el cuadro ya se
    puede descargar completo sin preguntar nada (caso automático)."""
    file = request.files.get("dxf")
    if file is None or file.filename == "":
        return jsonify(error="Selecciona un archivo DXF antes de continuar."), 400
    if not file.filename.lower().endswith(".dxf"):
        return jsonify(error="El archivo debe tener extensión .dxf."), 400

    tmp_dir = tempfile.mkdtemp(prefix="archmuse_cuadro_")
    try:
        filename = secure_filename(file.filename) or "plano.dxf"
        origen = os.path.join(tmp_dir, filename)
        file.save(origen)
        solicitudes = obtener_solicitudes(origen)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception as exc:  # noqa: BLE001 - límite del sistema: DXF arbitrario reenviado por el cliente
        return jsonify(error=f"No se pudo analizar el cuadro de superficies: {exc}"), 400
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return jsonify(solicitudes=[_serializar_solicitud(s) for s in solicitudes])


def _serializar_celda_relleno(r) -> dict:
    """`cuadro_superficies.CeldaRelleno` -> JSON, para pintar la tabla en
    pantalla (Fase 6). Solo lectura de lo que ya calculó
    `calcular_relleno_cuadro`; no decide nada nuevo aquí. `etiqueta` sale de
    la celda destino cuando existe (el texto real del DXF, p. ej. "S.
    CONSTRUIDA CERRADA"); si el cuadro no trae celda para ese campo (caso
    límite, un cuadro más pequeño), se usa el propio nombre de campo como
    respaldo -- nunca se inventa una redacción."""
    return {
        "campo": r.campo,
        "etiqueta": r.celda.etiqueta if r.celda is not None else r.campo,
        "columna": r.celda.columna if r.celda is not None else None,
        "texto": r.texto,
        "estado": r.estado,
        "motivo": r.motivo,
        "preexistente": r.preexistente,
        "declarado_por_usuario": r.declarado_por_usuario,
    }


@app.route("/api/cuadro-superficies/estado", methods=["POST"])
def cuadro_superficies_estado_endpoint():
    """Fase 6 -- el borrador COMPLETO del cuadro (las 18 celdas, resueltas o
    no) más las solicitudes pendientes sobre ese mismo cálculo, para
    pintarlo en pantalla sin necesidad de descargar nada
    (`obtener_estado_cuadro`, que reutiliza `detectar_solicitudes` de la
    Fase 5a -- ningún cálculo se repite ni se reimplementa aquí). Mismo
    campo `dxf` y mismo patrón de temporal que el resto de endpoints de
    cuadro de superficies.

    Fase 6b -- campo `respuestas` opcional (mismo JSON que
    `/api/exportar-cuadro-superficies-completo`): si se manda, la tabla
    devuelta ya refleja esas respuestas (p. ej. qué pieza real es cada
    espacio exterior) -- ESTE endpoint nunca escribe ni descarga un DXF,
    solo recalcula en memoria. Es la vía para "quiero verlo resuelto en el
    navegador", no un paso previo obligatorio a exportar nada."""
    file = request.files.get("dxf")
    if file is None or file.filename == "":
        return jsonify(error="Selecciona un archivo DXF antes de continuar."), 400
    if not file.filename.lower().endswith(".dxf"):
        return jsonify(error="El archivo debe tener extensión .dxf."), 400

    respuestas_raw = request.form.get("respuestas", "[]")
    try:
        respuestas = json.loads(respuestas_raw)
        if not isinstance(respuestas, list):
            raise ValueError("`respuestas` debe ser una lista JSON.")
    except (TypeError, ValueError) as exc:
        return jsonify(error=f"`respuestas` no es JSON válido: {exc}"), 400

    tmp_dir = tempfile.mkdtemp(prefix="archmuse_cuadro_")
    try:
        filename = secure_filename(file.filename) or "plano.dxf"
        origen = os.path.join(tmp_dir, filename)
        file.save(origen)
        resultado, solicitudes = obtener_estado_cuadro(origen, respuestas=respuestas)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception as exc:  # noqa: BLE001 - límite del sistema: DXF/respuestas arbitrarios reenviados por el cliente
        return jsonify(error=f"No se pudo leer el cuadro de superficies: {exc}"), 400
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return jsonify(
        celdas=[_serializar_celda_relleno(r) for r in resultado],
        solicitudes=[_serializar_solicitud(s) for s in solicitudes],
    )


@app.route("/api/exportar-cuadro-superficies-completo", methods=["POST"])
def exportar_cuadro_superficies_completo_endpoint():
    """Fase 5c -- recibe otra vez el DXF (campo `dxf`) más las respuestas del
    formulario "Datos necesarios para completar el cuadro" (campo
    `respuestas`, JSON: lista de objetos con la forma que espera
    `cuadro_superficies.aplicar_respuestas` -- `{"tipo": "numerico", "campo":
    ..., "valor": ...}` o `{"tipo": "asignacion", "solicitud_id": ...,
    "asignaciones": {...}}`).

    Si con esas respuestas el cuadro queda completo -> 200 y la descarga,
    igual que `/api/exportar-cuadro-superficies` (Fase 4) pero sin ningún
    `N/D`. Si queda algo pendiente -- una pregunta sin responder, o una
    respuesta en conflicto con una celda ya presente en el DXF -- -> 409 con
    el detalle de qué falta o qué contradice, y NO se ofrece descarga: el
    encargo es explícito, "el botón de descarga final solo se habilita
    cuando todas las celdas tienen un valor real calculado o declarado".

    Mismo patrón de temporales y de lectura síncrona a memoria antes de
    responder que el endpoint de borrador -- ver su docstring para el porqué
    (fuga real de directorio temporal en Windows con `call_on_close`,
    corregida ahí y reutilizada aquí sin repetir la explicación)."""
    file = request.files.get("dxf")
    if file is None or file.filename == "":
        return jsonify(error="Selecciona un archivo DXF antes de exportar."), 400
    if not file.filename.lower().endswith(".dxf"):
        return jsonify(error="El archivo debe tener extensión .dxf."), 400

    respuestas_raw = request.form.get("respuestas", "[]")
    try:
        respuestas = json.loads(respuestas_raw)
        if not isinstance(respuestas, list):
            raise ValueError("`respuestas` debe ser una lista JSON.")
    except (TypeError, ValueError) as exc:
        return jsonify(error=f"`respuestas` no es JSON válido: {exc}"), 400

    filename = secure_filename(file.filename) or "plano.dxf"
    nombre_salida = filename[:-4] + "_ArchMuse_completo.dxf"  # ya se comprobó que termina en .dxf

    tmp_dir = tempfile.mkdtemp(prefix="archmuse_cuadro_")
    try:
        origen = os.path.join(tmp_dir, filename)
        file.save(origen)
        destino = os.path.join(tmp_dir, nombre_salida)
        resultado = exportar_cuadro_relleno(origen, destino, respuestas=respuestas)
    except ValueError as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify(error=str(exc)), 400
    except Exception as exc:  # noqa: BLE001 - límite del sistema: DXF/respuestas arbitrarios reenviados por el cliente
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify(error=f"No se pudo generar el DXF completo: {exc}"), 400

    if resultado.campos_sin_resolver:
        # Ya se escribió una copia con N/D en lo pendiente (misma regla de
        # escritura de la Fase 3), pero no se ofrece -- el encargo prohíbe
        # descargar la "versión final" mientras quede algo sin resolver.
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify(
            error="El cuadro todavía no está completo -- responde o resuelve los conflictos indicados.",
            pendientes=resultado.detalles_sin_resolver,
        ), 409

    try:
        with open(resultado.ruta_destino, "rb") as f:
            contenido = f.read()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return Response(
        contenido,
        mimetype="application/dxf",
        headers={"Content-Disposition": 'attachment; filename="%s"' % nombre_salida},
    )


# --- Las cuatro alternativas parametricas (CP-5) ---------------------------
#
# `ARCHMUSE_SPEC.md` §8, redaccion del 2026-08-19: la generacion de alternativas
# esta permitida cuando la geometria se deriva de parametros comprobables, y
# cada alternativa lleva la procedencia de los parametros que la producen.
#
# **Por que este endpoint es distinto de `/api/generar-opciones`.** Aquel llama
# al generador --el modelo coloca estancias dentro de cada planta-- y eso es
# "distribucion interior libre", que el mismo §8 deja fuera. Este NO llama a
# ningun modelo: multiplica y compara lo que el arquitecto declaro. Es
# instantaneo, no cuesta un token, y cada cifra vuelve con su formula.
#
# Se deja el otro endpoint intacto: que hacer con la colocacion de estancias es
# una decision de Pablo, no una que se tome borrando codigo.


@app.route("/api/alternativas", methods=["POST"])
def alternativas():
    """Las cuatro alternativas del informe, derivadas de parametros comprobables.

    Sin llamadas al modelo. Si falta un parametro urbanistico **no se devuelve
    ninguna alternativa** y se dice cual falta: repartir un techo que no se ha
    podido calcular seria inventar la cifra de la que cuelga todo lo demas.
    """
    from analyzer.alternativas import derivar_alternativas

    body = request.get_json(silent=True) or {}
    parametros = body.get("parametros") or body
    envolvente, alts = derivar_alternativas(parametros)

    return jsonify(
        envolvente=envolvente.a_dict(),
        alternativas=[a.a_dict() for a in alts.values()],
        # Lo que falta para poder derivarlas, en cristiano y no como claves.
        faltan=list(envolvente.faltan),
    )


# --- Copiloto: el chat que MODIFICA el proyecto (pieza 5 del MVP) ----------
#
# PRD: `docs/prd/2026-08-19-copiloto-que-modifica-el-proyecto.md`.
#
# **La regla fundamental del informe ejecutivo, cumplida por construccion.** El
# modelo no calcula: elige que herramienta invocar y con que argumentos, y los
# motores hacen el resto. Aqui eso se hace cumplir de dos formas:
#
# 1. **El registro que ve el copiloto es estrecho.** Solo
#    `proyecto.ajustar_programa`. No puede leer un DXF, ni escribir un fichero,
#    ni consultar normativa por su cuenta -- no porque se le pida que no, sino
#    porque esas herramientas no estan en la lista que recibe.
# 2. **Una pregunta no necesita ninguna herramienta.** El estado del proyecto
#    viaja en la peticion, asi que "cual tiene mejor rentabilidad" se contesta
#    leyendo, con cero invocaciones. Es lo que hace trivial garantizar que
#    preguntar no modifica nada (criterio de aceptacion n2 del PRD).

#: Lo que el copiloto puede tocar. Una sola capacidad, a proposito.
_CAPACIDADES_DEL_COPILOTO = ("proyecto.ajustar_programa",)

_SISTEMA_COPILOTO = (
    "Eres el copiloto de ArchMuse, dentro de la aplicacion que un arquitecto esta usando.\n"
    "\n"
    "QUE ERES\n"
    "Un arquitecto junior muy rapido que trabaja DENTRO de ArchMuse. No eres un chat sobre\n"
    "arquitectura: cuando te piden un cambio, lo aplicas con la herramienta.\n"
    "\n"
    "LO QUE NO HACES, y es lo mas importante\n"
    "- NO calculas. No sumas superficies, no estimas margenes, no deduces cuantas viviendas\n"
    "  caben. Los motores de ArchMuse calculan; tu eliges que invocar.\n"
    "- NO das ninguna cifra que no venga del estado del proyecto que se te ha pasado o del\n"
    "  resultado de una herramienta. Ni una.\n"
    "- NO afirmas nada sobre normativa: el corpus del CTE de ArchMuse esta practicamente\n"
    "  vacio. Si te preguntan si algo cumple, di que ArchMuse hoy comprueba los parametros\n"
    "  urbanisticos (edificabilidad, ocupacion, altura, retranqueos) con aritmetica exacta,\n"
    "  y que el resto son indicadores de diseno, no verificacion normativa.\n"
    "- NO decides que proyecto es mejor. Puedes decir que alternativa puntua mas alto en un\n"
    "  indicador concreto, citando el indicador.\n"
    "\n"
    "DISTINGUE UNA PREGUNTA DE UNA ORDEN\n"
    "- Cual tiene mejor rentabilidad? es una PREGUNTA: contesta leyendo el estado. NO\n"
    "  invoques ninguna herramienta.\n"
    "- Elimina una vivienda es una ORDEN: invoca proyecto.ajustar_programa.\n"
    "- Si dudas, pregunta antes de modificar. Deshacer le cuesta tiempo al arquitecto.\n"
    "\n"
    "SI NO SABES HACER ALGO, DILO\n"
    "Solo puedes ajustar: el numero de viviendas por tipo, el numero de plantas y la\n"
    "superficie construida objetivo. Cualquier otra cosa --orientar una estancia, mover un\n"
    "tabique, cambiar la forma del solar-- NO la sabes hacer. Dilo y ofrece lo que si puedes\n"
    "hacer. No la aproximes con las herramientas que tienes.\n"
    "\n"
    "COMO HABLAS\n"
    "Castellano de estudio de arquitectura, breve y concreto. Cuando cambies algo, di que\n"
    "habia antes y que hay ahora. Sin emojis y sin entusiasmo comercial."
)


def _estado_para_el_copiloto(parametros: dict, alternativas: list) -> str:
    """El proyecto actual, en texto, para que una PREGUNTA no necesite tocar nada.

    Va dentro de la intencion --no del prompt de sistema-- a proposito:
    `agente/respaldo.py` considera respaldado lo que venia en la peticion, asi
    que una cifra que el copiloto repita de aqui se puede rastrear. Metido en el
    sistema, el detector marcaria como inventada cualquier cifra del estado.
    """
    mix = (parametros or {}).get("mix_viviendas") or {}
    edificio = (parametros or {}).get("edificio") or {}
    solar = (parametros or {}).get("solar") or {}
    proyecto = (parametros or {}).get("proyecto") or {}
    lineas = [
        "ESTADO ACTUAL DEL PROYECTO (las cifras de aqui son datos, no estimaciones tuyas):",
        "- Ciudad: %s" % (proyecto.get("ciudad") or "sin declarar"),
        "- Solar: %s m2" % (solar.get("superficie_m2") or "sin declarar"),
        "- Plantas: %s" % (edificio.get("plantas") or "sin declarar"),
        "- Viviendas: %s de 1 dormitorio, %s de 2, %s de 3"
        % (mix.get("dorm_1", 0), mix.get("dorm_2", 0), mix.get("dorm_3", 0)),
        "- Superficie construida objetivo: %s m2"
        % ((parametros or {}).get("superficie_objetivo_m2") or "sin declarar"),
    ]
    for alt in (alternativas or []):
        metricas = (alt or {}).get("metricas") or {}
        margen = metricas.get("margen_estimado") or {}
        lineas.append(
            "- Alternativa %s: zonas comunes %s %%, fachada aprovechada %s %%, margen %s %%"
            % (alt.get("etiqueta", "?"),
               metricas.get("repercusion_zonas_comunes_pct", "sin dato"),
               metricas.get("pct_fachada_aprovechada", "sin dato"),
               margen.get("margen_pct", "sin dato")))
    return "\n".join(lineas)


@app.route("/api/copiloto", methods=["POST"])
def copiloto():
    """Atiende una peticion en lenguaje natural sobre el proyecto en pantalla.

    Devuelve SIEMPRE el texto y la traza. Devuelve `parametros` nuevos solo si
    de verdad se aplico un cambio -- una pregunta no los trae, y eso es lo que
    el cliente usa para saber si tiene que regenerar.
    """
    body = request.get_json(silent=True) or {}
    peticion = str(body.get("peticion") or "").strip()
    if not peticion:
        return jsonify(error="Escribe que quieres que haga."), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return jsonify(
            error=("El copiloto necesita ANTHROPIC_API_KEY. El resto de ArchMuse "
                   "--parcela, analisis, alternativas y comparador-- funciona sin ella."),
            codigo="ia_no_disponible",
        ), 503

    parametros = body.get("parametros") or {}
    alternativas = body.get("alternativas") or []

    from agente import acta as _acta
    from agente import nucleo as _nucleo
    from agente.registro import Registro
    from agente.registro import registro as _registro_completo
    from ia.cliente import crear_cliente

    completo = _registro_completo()
    try:
        estrecho = Registro(tuple(completo.buscar(i) for i in _CAPACIDADES_DEL_COPILOTO))
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("copiloto: registro incompleto")
        return jsonify(error="El copiloto no esta disponible: %s" % exc), 500

    intencion = _estado_para_el_copiloto(parametros, alternativas) + "\n\n" + peticion
    try:
        respuesta = _nucleo.ejecutar(
            intencion, crear_cliente(api_key), reg=estrecho,
            sistema=_SISTEMA_COPILOTO, max_iteraciones=4,
        )
    except Exception as exc:  # noqa: BLE001 - se traduce, no se traga
        app.logger.exception("copiloto: fallo del bucle")
        return jsonify(error="No he podido atender la peticion: %s" % exc), 502

    # Lo que cambio, si cambio algo. Se lee de la TRAZA y no de lo que el modelo
    # diga que ha hecho: lo unico que demuestra que un cambio ocurrio es que la
    # herramienta se invoco y devolvio ok.
    cambio = None
    for paso in respuesta.pasos:
        if paso.capacidad == "proyecto.ajustar_programa" and paso.ok:
            cambio = paso.resultado

    salida = {
        "texto": respuesta.texto,
        "parada": respuesta.parada,
        "hubo_cambio": cambio is not None,
        "cifras_sin_respaldo": list(respuesta.cifras_sin_respaldo),
        "pasos": [
            {"capacidad": p.capacidad, "argumentos": p.argumentos, "ok": p.ok}
            for p in respuesta.pasos
        ],
        "limitaciones": list(respuesta.limitaciones),
    }
    if cambio is not None:
        salida["parametros"] = cambio.get("parametros")
        salida["antes"] = cambio.get("antes")
        salida["despues"] = cambio.get("despues")
        salida["hay_que_regenerar"] = bool(cambio.get("hay_que_regenerar"))

    # Criterio de aceptación 7 del PRD de este endpoint
    # (docs/prd/2026-08-19-copiloto-que-modifica-el-proyecto.md): "Toda
    # modificación queda en el acta: petición, herramienta, argumentos,
    # resultado." No había proyecto_id real que levantar (el copiloto opera
    # sobre `parametros` en memoria del cliente, no sobre un `Project`
    # persistido) -- si el cliente manda uno, se usa; si no, se sintetiza uno
    # estable a partir de la petición, mismo criterio que `nucleo.ejecutar()`
    # usa para su propio `ejecucion_id` por defecto.
    proyecto_id = str(body.get("proyecto_id") or ("copiloto-%d" % abs(hash(intencion))))
    ejecucion_id = "copiloto-%d" % abs(hash(peticion + repr(len(respuesta.pasos))))
    salida["acta"] = _acta.levantar_de_pasos(
        peticion, respuesta.pasos, capacidades=estrecho,
        proyecto_id=proyecto_id, ejecucion_id=ejecucion_id,
    ).a_dict()
    return jsonify(salida)


class _FalloDeMedicion(Exception):
    """La Skill de medición no ha podido completarse. El mensaje ya es el
    que se le enseña al usuario -- ver dónde se captura, en cada endpoint."""


class _ConfirmacionRequerida(Exception):
    """`SEG-1` (`docs/AGENTE_BACKLOG.md` §11): la Skill necesita un efecto
    (`agente/efectos.py`) que nadie ha autorizado todavía -- hoy, crear el
    fichero temporal del informe de medición. El ejecutor ya se detiene solo
    y sin escribir nada (`PENDIENTE_DE_AUTORIZACION`, ver `agente/ejecucion.py`);
    lo que faltaba era que el backend dejara de concederlo por su cuenta y
    en su lugar preguntara. `efectos` son los pendientes tal como los
    devuelve `ResultadoDeEjecucion.efectos_pendientes` -- nunca inventados
    aquí."""

    def __init__(self, quien: str, efectos) -> None:
        from agente.efectos import DESCRIPCIONES
        self.quien = quien
        self.efectos = tuple(efectos)
        super().__init__(
            "ArchMuse necesita tu autorización para: %s. No se ha escrito nada."
            % "; ".join(DESCRIPCIONES.get(e, e) for e in self.efectos)
        )


def _medir_planta_y_levantar_acta(file, filename: str, capa: Optional[str],
                                   factor_escala, *, quien: str,
                                   autorizar_efectos: bool = False) -> dict:
    """El DXF subido -> Skill real `superficies.medicion_de_planta` -> acta
    de procedencia (`Acta.a_dict()`).

    **Único sitio del backend que ejecuta esta Skill.** `/api/acta-legible`,
    `/api/preguntar` y `/api/memoria-superficies` llaman aquí (vía
    `_medir_planta_y_renderizar_acta` los dos primeros) -- ninguno reimplementa
    el camino Ejecutor -> `agente.acta.levantar()` por su cuenta (mismo camino
    que `scripts/medir_planta.py`).

    Mismo patrón de subida que `/api/analizar`: el DXF no se persiste en
    ningún sitio, sólo se procesa en un directorio temporal que se borra al
    salir de esta función. Levanta `_FalloDeMedicion` con un mensaje ya listo
    para el usuario si la Skill no puede completarse -- nunca deja pasar la
    excepción original del ejecutor tal cual.

    **`SEG-1`:** la Skill declara `escribe_fichero` (escribe el informe PDF
    intermedio de su propio procedimiento, `ruta_informe`, antes de esta
    tarea autorizado en nombre del arquitecto sin preguntarle). Con
    `autorizar_efectos=False` (el valor por defecto en la primera llamada de
    cada endpoint) no se concede nada; si la Skill lo necesita, el ejecutor
    se detiene solo, sin escribir nada, y esta función lo traduce a
    `_ConfirmacionRequerida` -- nunca a `_FalloDeMedicion`, que es un error,
    no una pregunta. El llamador reintenta con `autorizar_efectos=True` sólo
    si el arquitecto dijo que sí.
    """
    from agente import acta as _acta
    from agente.efectos import ESCRIBE_FICHERO, NINGUNA, Autorizaciones
    from agente.ejecucion import Ejecutor, Paso, Plan
    from agente.memoria import MemoriaDeProyecto, SustratoEnMemoria
    from agente.registro import registro, registro_de_skills

    with tempfile.TemporaryDirectory(prefix="archmuse_acta_") as tmp_dir:
        ruta_dxf = os.path.join(tmp_dir, filename)
        file.save(ruta_dxf)
        ruta_informe = os.path.join(tmp_dir, "medicion.pdf")

        argumentos = {"ruta_dxf": ruta_dxf, "ruta_informe": ruta_informe}
        if capa:
            argumentos["capa"] = capa
        if factor_escala is not None:
            argumentos["factor_escala"] = factor_escala

        raiz = os.path.splitext(filename)[0] or "plano"
        capacidades = registro(recargar=True)
        skills = registro_de_skills(recargar=True)
        memoria = MemoriaDeProyecto("acta-legible-%s" % raiz, SustratoEnMemoria())
        plan = Plan(
            objetivo="Medir %s y levantar su acta legible" % filename,
            proyecto_id=memoria.proyecto_id,
            pasos=(Paso(id="medir", skill="superficies.medicion_de_planta",
                        argumentos=argumentos),),
        )
        autorizaciones = (
            Autorizaciones.de((ESCRIBE_FICHERO,), por=quien)
            if autorizar_efectos else NINGUNA
        )

        try:
            resultado = Ejecutor(capacidades=capacidades, skills=skills).ejecutar(
                plan, memoria, ejecucion_id="api-%s" % raiz, autorizaciones=autorizaciones)
        except Exception as exc:  # noqa: BLE001 - límite del sistema: DXF arbitrario subido por el usuario
            app.logger.exception("medicion: fallo al ejecutar la Skill")
            raise _FalloDeMedicion("No se pudo medir el plano: %s" % exc) from exc

        if resultado.efectos_pendientes:
            # Ni un byte escrito: el paso se quedó en PENDIENTE_DE_AUTORIZACION
            # y `Ejecutor` no llegó a invocar la capacidad que escribe.
            raise _ConfirmacionRequerida(quien, resultado.efectos_pendientes)

        documento = _acta.levantar(resultado, capacidades=capacidades, skills=skills)
        return documento.a_dict()


def _medir_planta_y_renderizar_acta(file, filename: str, capa: Optional[str],
                                     factor_escala, *, quien: str,
                                     autorizar_efectos: bool = False) -> str:
    """`_medir_planta_y_levantar_acta` -> página HTML legible
    (`analyzer.acta_legible.render()`). Separada de ella (MJ-2/`/api/memoria-superficies`,
    2026-08-19) para que un consumidor que quiera el acta y no HTML -- el PDF
    del apartado de superficies -- no tenga que parsear la página de vuelta."""
    from analyzer import acta_legible as _acta_legible
    return _acta_legible.render(_medir_planta_y_levantar_acta(
        file, filename, capa, factor_escala,
        quien=quien, autorizar_efectos=autorizar_efectos))


def _respuesta_confirmacion_requerida(exc: "_ConfirmacionRequerida"):
    """`SEG-1`: la forma única en la que un efecto pendiente de autorización
    llega a la interfaz -- 428 (Precondition Required, no 400: no es un
    error del arquitecto) con la lista estructurada de `agente.efectos.solicitud`,
    la misma que usaría cualquier otro llamador (CLI, MCP) para preguntar."""
    from agente.efectos import solicitud
    return jsonify(
        error=str(exc),
        confirmacion_requerida=True,
        solicitud=solicitud(exc.quien, exc.efectos),
    ), 428


@app.route("/api/acta-legible", methods=["POST"])
def acta_legible_endpoint():
    """`DOC-1` (`docs/AGENTE_BACKLOG.md` §10) -- ejecuta de verdad la Skill
    `superficies.medicion_de_planta` sobre el DXF subido y devuelve su acta de
    procedencia como página HTML legible. Ver `_medir_planta_y_renderizar_acta`
    -- este endpoint sólo valida la subida y le pasa el trabajo.
    """
    file = request.files.get("dxf")
    if file is None or file.filename == "":
        return jsonify(error="Selecciona un archivo DXF antes de continuar."), 400
    if not file.filename.lower().endswith(".dxf"):
        return jsonify(error="El archivo debe tener extensión .dxf."), 400

    filename = secure_filename(file.filename) or "plano.dxf"
    capa = (request.form.get("capa") or "").strip() or None
    factor_escala = factor_de_unidad(request.form.get("escala") or "")
    autorizar_efectos = (request.form.get("autorizar_efectos") or "") == "1"

    try:
        pagina = _medir_planta_y_renderizar_acta(
            file, filename, capa, factor_escala,
            quien="api:acta-legible", autorizar_efectos=autorizar_efectos)
    except _FalloDeMedicion as exc:
        return jsonify(error=str(exc)), 400
    except _ConfirmacionRequerida as exc:
        return _respuesta_confirmacion_requerida(exc)

    return Response(pagina, mimetype="text/html")


@app.route("/api/memoria-superficies", methods=["POST"])
def memoria_superficies_endpoint():
    """MJ-3 (`docs/prd/2026-08-19-memoria-justificativa-automatica.md`) --
    ejecuta la misma Skill real que `/api/acta-legible` sobre el DXF subido y
    devuelve el apartado de superficies como PDF descargable
    (`analyzer.memoria_justificativa.generar_memoria_pdf`), en vez de la
    página HTML de verificación.

    Mismo contrato de subida que `/api/acta-legible`: nada se persiste, el
    DXF se procesa en un directorio temporal que se borra al salir de
    `_medir_planta_y_levantar_acta`. Si esa ejecución no produjo ningún dato
    (p. ej. el plano no tiene recintos legibles), no hay memoria que
    generar: 422, no un PDF vacío."""
    file = request.files.get("dxf")
    if file is None or file.filename == "":
        return jsonify(error="Selecciona un archivo DXF antes de continuar."), 400
    if not file.filename.lower().endswith(".dxf"):
        return jsonify(error="El archivo debe tener extensión .dxf."), 400

    filename = secure_filename(file.filename) or "plano.dxf"
    capa = (request.form.get("capa") or "").strip() or None
    factor_escala = factor_de_unidad(request.form.get("escala") or "")
    autorizar_efectos = (request.form.get("autorizar_efectos") or "") == "1"

    try:
        acta = _medir_planta_y_levantar_acta(
            file, filename, capa, factor_escala,
            quien="api:memoria-superficies", autorizar_efectos=autorizar_efectos)
    except _FalloDeMedicion as exc:
        return jsonify(error=str(exc)), 400
    except _ConfirmacionRequerida as exc:
        return _respuesta_confirmacion_requerida(exc)

    from analyzer.memoria_justificativa import ActaSinDatos, generar_memoria_pdf
    try:
        pdf_bytes = generar_memoria_pdf(acta)
    except ActaSinDatos as exc:
        return jsonify(error=str(exc)), 422

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=apartado_de_superficies.pdf"},
    )


#: La única capacidad que hoy puede ofrecer `/api/preguntar`. Un `dict` y no
#: una constante suelta porque el día que haya una segunda, la lista crece
#: en una línea y el prompt del clasificador se construye solo -- no hay que
#: tocar la lógica del endpoint para añadir una Skill más.
_SKILLS_DISPONIBLES_PARA_PREGUNTAR = {
    "superficies.medicion_de_planta": (
        "Medir las superficies útiles de una planta a partir de un DXF, "
        "vivienda por vivienda, y mostrar el acta de procedencia de esa "
        "medición (qué se ha establecido y qué no se ha podido comprobar)."
    ),
}

_NOMBRE_HERRAMIENTA_CLASIFICADOR = "clasificar_pregunta"

#: `tool_choice` fuerza al modelo a devolver exactamente este esquema -- no
#: hay rama en la que "conteste con texto libre" en vez de clasificar. La
#: única salida posible es `capacidad` (uno de los ids de arriba, o `null`).
def _herramienta_clasificador() -> dict:
    ids = list(_SKILLS_DISPONIBLES_PARA_PREGUNTAR)
    return {
        "name": _NOMBRE_HERRAMIENTA_CLASIFICADOR,
        "description": "Decide si la pregunta del usuario coincide con una capacidad de ArchMuse ya registrada.",
        "input_schema": {
            "type": "object",
            "properties": {
                "capacidad": {
                    "type": ["string", "null"],
                    "enum": ids + [None],
                    "description": (
                        "El id de la capacidad que resuelve la pregunta, EXACTAMENTE "
                        "uno de %s -- o `null` si ninguna la resuelve. Nunca inventes "
                        "un id que no esté en esa lista." % ids
                    ),
                },
            },
            "required": ["capacidad"],
        },
    }


def _capacidad_que_coincide(pregunta: str, api_key: str) -> Optional[str]:
    """La ÚNICA decisión que toma el LLM en `/api/preguntar`: ¿qué capacidad
    ya registrada resuelve esta pregunta, si es que hay alguna?

    No es una conversación: es una llamada forzada a una herramienta con un
    `enum` cerrado a las capacidades de `_SKILLS_DISPONIBLES_PARA_PREGUNTAR`
    -- el modelo no puede devolver un id que no esté en esa lista, así que no
    puede "inventar" que existe una capacidad que no existe. Nunca redacta
    contenido: sólo elige un id, o `null`.
    """
    from ia.cliente import crear_cliente
    from ia import modelos

    catalogo = "\n".join(
        "- `%s`: %s" % (id_, desc) for id_, desc in _SKILLS_DISPONIBLES_PARA_PREGUNTAR.items())
    sistema = (
        "Eres el clasificador de intención de ArchMuse. Estas son TODAS las "
        "capacidades que existen hoy, registradas y ejecutables de verdad:\n\n"
        + catalogo +
        "\n\nTu único trabajo es decidir si la pregunta del usuario coincide "
        "con alguna de ellas. Si coincide, aunque sea parcialmente, devuelve su "
        "id. Si no coincide con ninguna -- incluida cualquier pregunta sobre "
        "coste, normativa, plazos, estructura, instalaciones o cualquier otra "
        "cosa que suene a arquitectura pero no esté en la lista -- devuelve "
        "`null`. No expliques, no sugieras, no rellenes huecos: sólo clasifica."
    )

    cliente = crear_cliente(api_key)
    respuesta = cliente.messages.create(
        model=modelos.para("clasificacion"),
        max_tokens=200,
        system=sistema,
        tools=[_herramienta_clasificador()],
        tool_choice={"type": "tool", "name": _NOMBRE_HERRAMIENTA_CLASIFICADOR},
        messages=[{"role": "user", "content": pregunta}],
    )
    bloque = next((b for b in respuesta.content if getattr(b, "type", "") == "tool_use"), None)
    if bloque is None:
        return None
    capacidad = (bloque.input or {}).get("capacidad")
    # Defensa en profundidad: aunque el `enum` ya lo impide del lado del
    # modelo, nunca se confía en el string que vuelve sin comprobarlo contra
    # el catálogo real -- así una respuesta rara del modelo nunca puede
    # colarse como si fuera una capacidad registrada.
    return capacidad if capacidad in _SKILLS_DISPONIBLES_PARA_PREGUNTAR else None


_MENSAJE_SIN_CAPACIDAD = (
    "ArchMuse no tiene todavía una capacidad registrada para esto. Hoy sólo "
    "sabe medir las superficies útiles de una planta a partir de un DXF y "
    "mostrar el acta de procedencia de esa medición -- nada más. No voy a "
    "intentar responder con conocimiento general del modelo: eso es "
    "exactamente lo que ArchMuse existe para no hacer."
)


@app.route("/api/preguntar", methods=["POST"])
def preguntar():
    """La primera puerta de conversación real: intención -> ¿hay una Skill
    registrada que la resuelva? -> se ejecuta de verdad -> se responde con lo
    que esa Skill produjo. Nada más.

    El LLM interpreta la frase UNA sola vez y para UNA sola cosa: elegir,
    de una lista cerrada, qué capacidad ya registrada (si alguna) resuelve la
    pregunta (`_capacidad_que_coincide`). Si hay match, la ejecución pasa por
    el mismo camino que `/api/acta-legible`
    (`_medir_planta_y_renderizar_acta`) -- nada se reimplementa. Si no hay
    match, la respuesta lo dice explícitamente: el modelo nunca contesta con
    su conocimiento general, ni aquí ni en ninguna otra rama de esta función.
    """
    pregunta = (request.form.get("pregunta") or "").strip()
    if not pregunta:
        return jsonify(error="Escribe qué quieres saber."), 400

    file = request.files.get("dxf")
    if file is None or file.filename == "":
        return jsonify(error="Selecciona un archivo DXF antes de continuar."), 400
    if not file.filename.lower().endswith(".dxf"):
        return jsonify(error="El archivo debe tener extensión .dxf."), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return jsonify(
            error=("Esta puerta necesita ANTHROPIC_API_KEY para interpretar la "
                   "pregunta. El resto de ArchMuse funciona sin ella."),
            codigo="ia_no_disponible",
        ), 503

    try:
        capacidad = _capacidad_que_coincide(pregunta, api_key)
    except Exception as exc:  # noqa: BLE001 - límite del sistema: la API de Anthropic puede fallar
        app.logger.exception("preguntar: fallo al clasificar la intención")
        return jsonify(error="No he podido interpretar la pregunta: %s" % exc), 502

    if capacidad is None:
        return jsonify(coincide=False, mensaje=_MENSAJE_SIN_CAPACIDAD)

    filename = secure_filename(file.filename) or "plano.dxf"
    capa = (request.form.get("capa") or "").strip() or None
    factor_escala = factor_de_unidad(request.form.get("escala") or "")
    autorizar_efectos = (request.form.get("autorizar_efectos") or "") == "1"

    try:
        pagina = _medir_planta_y_renderizar_acta(
            file, filename, capa, factor_escala,
            quien="api:preguntar", autorizar_efectos=autorizar_efectos)
    except _FalloDeMedicion as exc:
        return jsonify(error=str(exc)), 400
    except _ConfirmacionRequerida as exc:
        return _respuesta_confirmacion_requerida(exc)

    return jsonify(coincide=True, capacidad=capacidad, html=pagina)


#: Puerto por defecto. `PORT` lo sobreescribe (es la convención que espera
#: cualquier PaaS, y no cuesta nada admitirla).
PUERTO_POR_DEFECTO = 5000

#: Sólo escucha en la interfaz local. El túnel de Cloudflare que se usa para
#: enseñar la aplicación fuera se conecta a `127.0.0.1`, así que abrir a
#: `0.0.0.0` no aportaría nada y expondría el puerto a toda la red local.
HOST_POR_DEFECTO = "127.0.0.1"

#: Waitress atiende varias peticiones a la vez con este número de hilos. Es el
#: sustituto de `threaded=True` (fix 2026-08-15, bug reportado en vivo): sin
#: concurrencia, mientras `/api/analizar-sitio` espera a Catastro/Overpass
#: (puede tardar bastantes segundos, ver `analyzer/sitio.py`),
#: `/api/geocodificar` --el buscador de direcciones-- se queda en cola detrás
#: aunque no tenga nada que ver. Eso es lo que se reportó como "cuando pongo
#: una calle tarda mucho en darme opciones".
HILOS_WAITRESS = 8

_VERDADEROS = {"1", "true", "on", "yes", "si", "sí"}


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", PUERTO_POR_DEFECTO))
    modo_desarrollo = os.environ.get("FLASK_DEBUG", "").strip().lower() in _VERDADEROS

    if modo_desarrollo:
        # Servidor de desarrollo de Flask: autorecarga al guardar y depurador
        # interactivo. El depurador de Werkzeug permite ejecutar código Python
        # arbitrario desde el navegador, así que esta rama NO es un valor por
        # defecto: hay que pedirla a mano con FLASK_DEBUG=1, y sólo en local.
        logger.warning(
            "Arrancando en MODO DESARROLLO (FLASK_DEBUG activo): depurador interactivo "
            "de Werkzeug expuesto en http://%s:%d -- no uses este modo en nada accesible "
            "desde fuera de esta máquina.", HOST_POR_DEFECTO, puerto,
        )
        app.run(debug=True, host=HOST_POR_DEFECTO, port=puerto, threaded=True)
    else:
        # Camino por defecto: servidor WSGI de verdad. `waitress` y no
        # `gunicorn` porque gunicorn no funciona en Windows, que es donde se
        # desarrolla y se enseña ArchMuse.
        try:
            from waitress import serve
        except ImportError:
            raise SystemExit(
                "Falta `waitress`, que es como arranca ArchMuse por defecto.\n"
                "  Instálalo:  pip install -r requirements.txt\n"
                "  O arranca en modo desarrollo:  FLASK_DEBUG=1 python app.py"
            )
        print("ArchMuse en http://%s:%d  (waitress, %d hilos)" % (
            HOST_POR_DEFECTO, puerto, HILOS_WAITRESS))
        print("Para desarrollar con autorecarga y depurador:  FLASK_DEBUG=1 python app.py")
        serve(app, host=HOST_POR_DEFECTO, port=puerto, threads=HILOS_WAITRESS)
