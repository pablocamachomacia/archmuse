# -*- coding: utf-8 -*-
"""Datos reales del entorno de una parcela — Catastro + OpenStreetMap.

PRD: `docs/prd/2026-08-15-analisis-de-sitio.md`. Primer incremento
(2026-08-15): geometría/superficie real de la parcela por referencia
catastral (servicio WFS/INSPIRE del Catastro) + colindantes, viales, zonas
verdes y equipamientos (Overpass API sobre OpenStreetMap). Determinista, sin
IA — es lectura de dos registros públicos, no interpretación.

Segundo incremento (mismo día, "Mapa/Parcela Primero"): `obtener_datos_
parcela(lat=..., lon=...)` sin `referencia_catastral` ya no se queda solo
con Overpass -- primero resuelve la RC real por coordenadas
(`_referencia_desde_coordenadas`, `Consulta_RCCOOR`) y, si lo consigue,
encadena la misma geometría/superficie que el caso "RC ya conocida". Este
servicio estaba validado en la PoC original (ver hallazgo 1 más abajo) pero
hasta ahora no tenía ninguna función que lo usara de verdad.

**Validado contra los servicios reales antes de escribir este módulo**
(tarea 1 del plan del PRD — "prueba de concepto acotada"), con la Referencia
Catastral real `1446401VK4714E` (Palacio de Cibeles, Madrid). Tres hallazgos
que ESTE módulo existe para no repetir a ciegas:

1. El endpoint JSON de coordenadas (`COVCCoordenadas.svc/json/Consulta_RCCOOR`)
   usa los parámetros `CoorX`/`CoorY` — NO `Coordenada_X`/`Coordenada_Y`
   (esos son de la variante ASMX/SOAP, un servicio distinto con el mismo
   nombre de operación).
2. **La geometría WFS/INSPIRE viene en orden lat, lon** dentro de
   `gml:posList` (srsName EPSG:4326 en su variante "compliant"), al revés
   del orden lon, lat que `shapely`/GeoJSON esperan. Sin este dato,
   `_parsear_poligono_gml` habría colocado cualquier parcela en el punto
   simétrico equivocado, sin lanzar ningún error — exactamente el riesgo
   que el PRD (§6) advertía sin haberlo comprobado todavía.
3. `cp:areaValue` en la respuesta WFS da la superficie de la parcela
   directamente (m²) — no hace falta calcularla del polígono, y es más
   fiable que hacerlo (la fuente es la misma Dirección General del
   Catastro).

**Lo que este incremento NO cubre todavía**, deliberadamente, no por
descuido:

- **Resolución de "municipio + dirección" a una referencia catastral.**
  Los intentos de la PoC contra `Consulta_DNPRC`/`Consulta_DNPPP` (datos
  alfanuméricos por RC/por polígono-parcela rústica) no dieron con la forma
  correcta de parámetros en el tiempo disponible — a diferencia del caso de
  coordenadas, que sí quedó resuelto y probado. Confirma lo que el PRD ya
  advertía (§0): esta vía no es simétrica a la de referencia catastral, y
  puede merecer su propia PoC aparte antes de prometerla.
- **Caché por parcela** (PRD §4/§8): vive en `analyzer/storage.py`/`app.py`,
  no aquí — este módulo es una función pura, sin estado.
- **Altitud de la parcela** (para refinar zona climática CTE, PRD de
  análisis solar): ninguno de los dos servicios usados aquí la trae.

Todo fallo de red o de parseo se recoge en `sitio_data["errores"]` y NUNCA
se propaga como excepción desde `obtener_datos_parcela` — regla explícita
del encargo ("nunca bloquear el flujo principal").
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import math
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

USER_AGENT = "ArchMuse/1.0 (herramienta de arquitectura; uso interno)"

_URL_COORDENADAS = "https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCoordenadas.svc/json/Consulta_RCCOOR"
_URL_WFS_PARCELA = "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
_URL_OVERPASS = "https://overpass-api.de/api/interpreter"
# Espejos públicos de Overpass (2026-08-17, bug crítico reportado en vivo -- "colgado"/"tarda
# demasiado" en el visor 3D): medido en vivo hoy mismo con `curl`, `overpass-api.de` en solitario
# tardó 126s en fallar del todo (3 intentos × hasta 20-25s + esperas de 2/4/8s) para una consulta de
# colindantes -- muy por encima de cualquier presupuesto razonable de UI, y encima ese resultado
# vacío se cacheaba (ver `entorno_overpass_por_coordenadas`/`app.py:entorno_3d_punto`) como si fuera
# un hecho permanente ("aquí no hay vecinos"), no un fallo transitorio de un servicio degradado.
# `_post_overpass` ahora prueba estos espejos EN ORDEN antes de rendirse -- son otras instancias
# públicas de la misma API (documentadas en wiki.openstreetmap.org/wiki/Overpass_API), así que un
# fallo/rate-limit del host principal ya no significa "sin colindantes", solo "prueba el siguiente".
_URLS_OVERPASS = (
    _URL_OVERPASS,
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
)
#: Geocodificador. **Mapbox, no Nominatim** (tarea `TL-8` del backlog).
#:
#: La política de uso de la instancia pública de Nominatim prohíbe el uso
#: comercial (`operations.osmfoundation.org/policies/nominatim/`). Mientras
#: ArchMuse fue una demostración, llamarla era discutible; en cuanto se cobra
#: por el producto es un incumplimiento, y no de los que se arreglan pidiendo
#: perdón: el bloqueo llega por IP y sin aviso. Se sustituye ANTES de cobrar,
#: no después, porque lo segundo significa descubrirlo con clientes dentro.
#:
#: Mapbox ya está en el producto (el visor, el terreno y el mapa del dossier
#: PDF), así que esto no añade un proveedor: usa el que ya se paga.
_URL_MAPBOX_GEOCODING = "https://api.mapbox.com/search/geocode/v6/forward"

_NS_GML = "{http://www.opengis.net/gml/3.2}"
_NS_CP = "{http://inspire.ec.europa.eu/schemas/cp/4.0}"


class ErrorDeSitio(Exception):
    """Un paso concreto (Catastro o Overpass) falló — red, HTTP, o
    respuesta con forma inesperada. Se captura siempre dentro de
    `obtener_datos_parcela`; existe como tipo propio para que los tests
    puedan distinguir "este paso falló" de un bug real de programación."""


def _es_error_de_certificado(exc: BaseException) -> bool:
    """`ssl.SSLError` puede llegar directo, o envuelto como `.reason` de un
    `urllib.error.URLError` -- según en qué punto de la conexión falle.
    Se comprueban las dos formas para no dejar pasar ninguna como un
    fallo de red genérico."""
    if isinstance(exc, ssl.SSLError):
        return True
    return isinstance(getattr(exc, "reason", None), ssl.SSLError)


def _mensaje_error_certificado(url: str, exc: BaseException) -> str:
    return (
        "Error de certificado SSL al conectar con %s. Esto casi siempre significa que el "
        "almacén de certificados de ESTE sistema no reconoce la cadena de confianza de "
        "Catastro -- no que Catastro esté caído. Revisa que `certifi` (o los certificados "
        "raíz del sistema operativo) estén instalados y actualizados. Detalle: %s" % (url, exc)
    )


def _es_timeout(exc: BaseException) -> bool:
    """`True` solo para un timeout de red real -- ni un 404/500 (`HTTPError`, respuesta real del
    servidor) ni un error de certificado (ya tratado aparte). `urllib` reporta un timeout de socket
    como `URLError(reason=TimeoutError(...))` (o, más raro, como `TimeoutError` directo) -- nunca
    como `HTTPError`, que sí tiene una respuesta HTTP real detrás y no debe reintentarse igual."""
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, urllib.error.HTTPError):
        return False  # tiene código de estado real -- no es un timeout, aunque herede de URLError
    return isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, TimeoutError)


def _get(url: str, *, timeout: float = 15.0, intentos_ante_timeout: int = 1) -> bytes:
    """`intentos_ante_timeout` (2026-08-17, docs/prd/2026-08-17-resiliencia-catastro-cache-y-
    reintentos.md, §14): por defecto 1 -- sin cambio de comportamiento para el resto de llamadores de
    esta función. Solo `_geometria_parcela_catastro` pide más de 1: un timeout de red al descargar el
    polígono WFS es, por experiencia real en esta sesión, a menudo transitorio (congestión momentánea
    del servicio de Catastro) -- un segundo intento CON EL MISMO `timeout` (nunca un buffer/radio
    creciente: esto es una descarga por referencia catastral exacta, no una búsqueda por área que
    admita ese concepto) resuelve el caso transitorio sin cambiar el comportamiento ante un fallo real
    (404/certificado/DNS), que sigue sin reintentarse."""
    peticion = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    intentos = max(1, intentos_ante_timeout)
    for intento in range(intentos):
        try:
            with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
                return respuesta.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ssl.SSLError) as exc:
            if _es_error_de_certificado(exc):
                mensaje = _mensaje_error_certificado(url, exc)
                logger.warning(mensaje)
                raise ErrorDeSitio(mensaje) from exc
            if _es_timeout(exc) and intento < intentos - 1:
                logger.info("Timeout en %s (intento %d/%d) -- reintentando...", url, intento + 1, intentos)
                continue
            raise ErrorDeSitio("GET %s: %s" % (url, exc)) from exc


#: Rehecho 2026-08-17 (bug crítico, ver comentario junto a `_URLS_OVERPASS`): antes eran 3 intentos
#: CONTRA EL MISMO host con esperas 2/4/8s (hasta ~90s solo en esperas+timeouts de 20-25s cada uno,
#: 126s medidos en vivo). Ahora se prueba cada espejo de `_URLS_OVERPASS` UNA vez, con un timeout por
#: intento mucho más corto (`_OVERPASS_TIMEOUT_S`) -- "timeouts más agresivos, fallback rápido" pedido
#: explícitamente. Espera corta y fija entre espejos (no escalonada: no tiene sentido un backoff largo
#: cuando el siguiente intento ya es a UN HOST DISTINTO, no una repetición contra el mismo servicio
#: posiblemente saturado).
_OVERPASS_TIMEOUT_S = 10.0
_OVERPASS_ESPERA_ENTRE_ESPEJOS_S = 1.5


def _post_overpass(query: str, *, timeout: float = _OVERPASS_TIMEOUT_S) -> dict:
    datos = urllib.parse.urlencode({"data": query}).encode("utf-8")
    ultimo_error: Optional[BaseException] = None

    for indice, url in enumerate(_URLS_OVERPASS):
        peticion = urllib.request.Request(
            url, data=datos,
            headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
                crudo = respuesta.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ssl.SSLError) as exc:
            ultimo_error = exc
            if indice < len(_URLS_OVERPASS) - 1:
                logger.warning(
                    "Overpass (%s) falló (espejo %d/%d): %s -- probando el siguiente espejo en %.1fs",
                    url, indice + 1, len(_URLS_OVERPASS), exc, _OVERPASS_ESPERA_ENTRE_ESPEJOS_S,
                )
                time.sleep(_OVERPASS_ESPERA_ENTRE_ESPEJOS_S)
            continue

        try:
            return json.loads(crudo)
        except (ValueError, TypeError) as exc:
            # Respuesta recibida pero no es JSON válido: no es un fallo de
            # red transitorio, reintentar no lo arreglaría -- se lanza de
            # inmediato, sin gastar los otros espejos.
            raise ErrorDeSitio("Overpass: respuesta no es JSON válido: %s" % exc) from exc

    mensaje = "Overpass: los %d espejos fallaron. Último error: %s" % (len(_URLS_OVERPASS), ultimo_error)
    logger.warning(mensaje)
    raise ErrorDeSitio(mensaje)


# --- Geocodificación: buscar una dirección/municipio por texto libre -------

# Normalización del número de portal (2026-08-17, "Rediseño buscador estilo Apple
# Maps"): un geocodificador indexa "Gran Vía 31", no "Gran Vía número 31" -- escribir la
# palabra completa ("numero"/"número"), la abreviatura con ordinal ("nº"/"n°") o
# "num"/"nro" delante del número deja el texto peor puntuado (o sin resultados) que
# omitirla directamente. `\b` + lookahead de dígito evita comerse palabras que
# simplemente EMPIEZAN por esas letras ("numeroso"), y el separador opcional
# (espacio/punto) entre la palabra y el número cubre "nº1", "n.º 1" y "num. 1" a la vez.
_RE_NUMERO_PORTAL = re.compile(
    r"\b(?:n(?:[uú]mero|ro|\.?[º°])|num)\.?\s*(?=\d)", re.IGNORECASE,
)


def _normalizar_texto_busqueda(texto: str) -> str:
    """Limpia variantes de "número de portal" ("numero 1", "nº 1", "num. 1") antes
    de mandar el texto al geocodificador -- ver `_RE_NUMERO_PORTAL` arriba.

    Se conserva tal cual de la etapa de Nominatim: la normalización es del
    castellano escrito por un humano, no del proveedor, y Mapbox puntúa peor
    exactamente igual cuando le llega "n.º" delante del portal."""
    texto = _RE_NUMERO_PORTAL.sub("", texto)
    return re.sub(r"\s+", " ", texto).strip()


class GeocodificacionNoConfigurada(ErrorDeSitio):
    """No hay `MAPBOX_TOKEN` y por tanto no hay buscador de direcciones.

    Es un tipo propio, y no un `ErrorDeSitio` cualquiera, porque la respuesta
    correcta es distinta: no es «el servicio ha fallado, vuelve a intentarlo»
    sino «esto no está configurado en este despliegue». Confundirlas haría que
    el arquitecto reintentara para siempre una búsqueda que nunca va a
    funcionar.
    """


def _token_mapbox() -> str:
    """El token, leído del entorno en cada llamada.

    En cada llamada y no en el import: cambiar `.env` no puede exigir
    reiniciar el proceso para probarlo — mismo criterio que `ia/cliente.py`
    con sus timeouts.
    """
    return (os.environ.get("MAPBOX_TOKEN") or "").strip()


def _resultados_de_mapbox(datos: Any) -> List[dict]:
    """Traduce la respuesta de Mapbox a la forma que ya consume el frontend.

    Acepta las dos formas documentadas —v6 (`properties.coordinates` +
    `properties.full_address`) y la v5 clásica (`center` + `place_name`)—
    porque la clave de despliegue decide cuál contesta y una diferencia de
    versión no puede dejar el buscador mudo. Lo que **no** se hace es
    inventar coordenadas: una entrada sin ellas se descarta.
    """
    if not isinstance(datos, dict) or not isinstance(datos.get("features"), list):
        raise ErrorDeSitio(
            "Mapbox: respuesta con forma inesperada (se esperaba un GeoJSON con «features»)")

    resultados: List[dict] = []
    for item in datos["features"]:
        if not isinstance(item, dict):
            continue
        propiedades = item.get("properties") or {}
        geometria = item.get("geometry") or {}
        coordenadas = (
            propiedades.get("coordinates")
            or geometria.get("coordinates")
            or item.get("center")
        )
        lon = lat = None
        if isinstance(coordenadas, dict):
            lon, lat = coordenadas.get("longitude"), coordenadas.get("latitude")
        elif isinstance(coordenadas, (list, tuple)) and len(coordenadas) >= 2:
            lon, lat = coordenadas[0], coordenadas[1]     # GeoJSON: (lon, lat)
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            continue        # sin coordenadas utilizables: se descarta, no se inventa
        nombre = (propiedades.get("full_address") or propiedades.get("place_formatted")
                  or propiedades.get("name") or item.get("place_name"))
        resultados.append({"lat": lat, "lon": lon, "display_name": nombre})
    return resultados


def geocodificar_direccion(texto: str, *, limite: int = 5) -> List[dict]:
    """Busca una dirección o municipio escrito en texto libre, vía **Mapbox**.

    Cubre el sentido texto -> coordenadas del buscador del MapPicker (el otro
    sentido, coordenadas -> referencia catastral, ya lo cubre Catastro).

    **Por qué esta función vive en el servidor y no se llama desde el
    navegador.** Por el mismo motivo que Catastro y Overpass, más uno propio:
    el token de Mapbox que sirve el backend es público, pero acotar la
    búsqueda a España y limitar el número de resultados aquí evita que el
    frontend pueda pedir cualquier cosa contra la cuota que paga ArchMuse.

    Nunca lanza por «sin resultados» (una lista vacía es una respuesta válida).
    Sin `MAPBOX_TOKEN` lanza `GeocodificacionNoConfigurada`: **no hay repliegue
    a Nominatim**, cuya instancia pública prohíbe el uso comercial. Un repliegue
    «temporal» a un servicio que no se puede usar es la clase de atajo que
    sobrevive tres años.
    """
    texto = _normalizar_texto_busqueda(texto or "")
    if not texto:
        return []
    token = _token_mapbox()
    if not token:
        raise GeocodificacionNoConfigurada(
            "El buscador de direcciones necesita MAPBOX_TOKEN y este despliegue no lo "
            "tiene configurado. Se puede seguir señalando la parcela en el mapa."
        )
    params = urllib.parse.urlencode({
        "q": texto,
        "limit": max(1, min(limite, 10)),
        "country": "es",
        "language": "es",
        "access_token": token,
    })
    cuerpo = _get("%s?%s" % (_URL_MAPBOX_GEOCODING, params))
    try:
        datos = json.loads(cuerpo)
    except (ValueError, TypeError) as exc:
        raise ErrorDeSitio("Mapbox: respuesta no es JSON válido: %s" % exc) from exc
    return _resultados_de_mapbox(datos)


# --- Catastro: geometría real de la parcela --------------------------------


def _parsear_poligono_gml(cuerpo_xml: bytes) -> Tuple[List[Tuple[float, float]], Optional[float]]:
    """`cuerpo_xml` es la respuesta del WFS `GetParcel`. Devuelve
    `(anillo_exterior, superficie_m2)` — el anillo en (lon, lat), ya
    corregido del orden (lat, lon) nativo del servicio (ver docstring del
    módulo, hallazgo 2).

    Solo el anillo EXTERIOR del primer `gml:Surface` — una parcela urbana
    normal es un polígono simple. Una parcela con huecos (patio interior
    declarado como anillo propio) o multi-superficie perdería esa parte;
    no se ha encontrado ningún caso así todavía para justificar el coste de
    soportarlo (documentado como limitación, no corregido en silencio)."""
    try:
        raiz = ET.fromstring(cuerpo_xml)
    except ET.ParseError as exc:
        raise ErrorDeSitio("geometría WFS: XML no parseable: %s" % exc) from exc

    area_el = raiz.find(".//%sareaValue" % _NS_CP)
    superficie_m2 = float(area_el.text) if area_el is not None and area_el.text else None

    pos_list_el = raiz.find(".//%sexterior//%sposList" % (_NS_GML, _NS_GML))
    if pos_list_el is None or not pos_list_el.text:
        raise ErrorDeSitio("geometría WFS: no se encontró ningún gml:posList (¿referencia catastral inexistente?)")

    valores = [float(v) for v in pos_list_el.text.split()]
    if len(valores) < 6 or len(valores) % 2 != 0:
        raise ErrorDeSitio("geometría WFS: posList con un número de valores inesperado (%d)" % len(valores))

    # (lat, lon) -> (lon, lat): hallazgo 2 del docstring del módulo.
    anillo = [(valores[i + 1], valores[i]) for i in range(0, len(valores), 2)]
    return anillo, superficie_m2


def _centroide(anillo: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Centroide simple (media aritmética de vértices), no el centroide de
    área real de un polígono irregular — suficiente para centrar las
    consultas de Overpass (radio de decenas/cientos de metros), no para
    ningún cálculo de precisión geométrica."""
    lon = sum(p[0] for p in anillo) / len(anillo)
    lat = sum(p[1] for p in anillo) / len(anillo)
    return lat, lon


def _referencia_desde_coordenadas(lat: float, lon: float, *, timeout: float = 15.0) -> dict:
    """Resuelve una Referencia Catastral real a partir de una coordenada
    (clic en el mapa), vía `Consulta_RCCOOR` -- el servicio que el
    docstring del módulo documentaba como validado en la PoC (`CoorX`/
    `CoorY`/`SRS`, no `Coordenada_X`/`Coordenada_Y`) pero que hasta ahora
    no estaba conectado a ninguna función real de este módulo.

    Validado en vivo para esta tarea con coordenadas reales de Madrid
    (Gran Vía 31 y Calle Barco 8): la respuesta de éxito trae
    `coordenadas.coord[0].pc.{pc1,pc2}` (la RC es `pc1 + pc2`, 14
    caracteres) y `.ldt` (dirección/municipio en texto libre, ej. "CL
    GRAN VIA 31 MADRID (MADRID)"). Cuando Catastro no tiene ninguna
    parcela en el punto exacto (comprobado en vivo: código de error 16,
    "PARA ESAS COORDENADAS NO HAY REFERENCIA DISPONIBLE" -- ocurre con
    coordenadas a pocos metros de una parcela real, no solo en zonas sin
    catastrar), la respuesta trae `control.cuerr` en vez de `control.
    cucoor` -- se traduce a `ErrorDeSitio`, nunca se inventa una RC.

    `timeout` (2026-08-16, `docs/prd/2026-08-16-resiliencia-catastro-paso0.md`):
    la espiral de proximidad (`_referencia_por_proximidad`) llama a esta
    función hasta 12 veces seguidas -- con el timeout por defecto de `_get`
    (15s) un peor caso de "todos los intentos tardan al límite" volvería a
    introducir el mismo tipo de bloqueo largo que este mismo PRD documenta
    haber corregido en el Sandbox (§0). La espiral pasa un timeout más
    corto por intento; el punto exacto (caso mayoritario) sigue usando el
    valor por defecto, sin cambiar su comportamiento de hoy."""
    params = urllib.parse.urlencode({"CoorX": lon, "CoorY": lat, "SRS": "EPSG:4326"})
    cuerpo = _get("%s?%s" % (_URL_COORDENADAS, params), timeout=timeout)
    try:
        datos = json.loads(cuerpo)
    except (ValueError, TypeError) as exc:
        raise ErrorDeSitio("Consulta_RCCOOR: respuesta no es JSON válido: %s" % exc) from exc

    resultado = datos.get("Consulta_RCCOORResult") or {}
    control = resultado.get("control") or {}
    if control.get("cuerr"):
        errores = resultado.get("lerr") or []
        descripciones = "; ".join(e.get("des", "") for e in errores if isinstance(e, dict))
        raise ErrorDeSitio(
            "Consulta_RCCOOR: %s" % (descripciones or "Catastro no tiene ninguna parcela en esas coordenadas")
        )

    coords = ((resultado.get("coordenadas") or {}).get("coord")) or []
    if not coords:
        raise ErrorDeSitio("Consulta_RCCOOR: respuesta de éxito sin 'coordenadas.coord' (forma inesperada)")
    pc = (coords[0] or {}).get("pc") or {}
    pc1, pc2 = pc.get("pc1"), pc.get("pc2")
    if not pc1 or not pc2:
        raise ErrorDeSitio("Consulta_RCCOOR: respuesta de éxito sin pc1/pc2 (forma inesperada)")
    return {"referencia_catastral": pc1 + pc2, "direccion": coords[0].get("ldt")}


#: Espiral de proximidad (2026-08-16, `docs/prd/2026-08-16-resiliencia-catastro-paso0.md`):
#: 4 direcciones × 3 radios = 12 puntos por defecto, deliberadamente pequeño (el PRD §9
#: descarta explícitamente empezar con 8×3=24) -- se amplía solo si la verificación en vivo
#: demuestra que 12 se queda corto. Vectores unitarios (este, norte); NE/NO/SE/SO quedan
#: fuera del primer incremento por el mismo motivo (mantener el peor caso barato).
_RADIOS_PROXIMIDAD_M: Tuple[int, ...] = (5, 10, 20)
_DIRECCIONES_PROXIMIDAD: Tuple[Tuple[float, float], ...] = ((1, 0), (0, 1), (-1, 0), (0, -1))

#: Techo de tiempo TOTAL para toda la espiral (todos los puntos, todos los radios) -- no un
#: timeout por intento. Con `_TIMEOUT_INTENTO_PROXIMIDAD_S` de sobra para completar los 12
#: intentos si todos fallan rápido (código de error 16, respuesta típica en <1s), este techo
#: solo actúa de verdad cuando Catastro está lento, cortando la espiral en vez de dejarla
#: acumular hasta 12 × timeout -- exactamente el riesgo que el PRD §9 pide mitigar.
_PRESUPUESTO_TOTAL_PROXIMIDAD_S = 9.0
_TIMEOUT_INTENTO_PROXIMIDAD_S = 4.0


def _desplazar_metros(lat: float, lon: float, este_m: float, norte_m: float) -> Tuple[float, float]:
    """Desplaza `(lat, lon)` por `(este_m, norte_m)` metros -- aproximación equirectangular
    (mismo criterio que ya usa `metrosEsteNorteDesde` en el cliente, `viewer-terreno.js`, para
    el mismo tipo de conversión). Válida para los radios pequeños (≤20m) de la espiral de
    proximidad; NO pensada para desplazamientos grandes (el error crece con la distancia y con
    la latitud, por la proyección plana)."""
    dlat = norte_m / 111_320.0
    coseno_lat = math.cos(math.radians(lat))
    dlon = este_m / (111_320.0 * coseno_lat) if abs(coseno_lat) > 1e-9 else 0.0
    return lat + dlat, lon + dlon


def _referencia_por_proximidad(lat: float, lon: float, *, error_del_punto_exacto: ErrorDeSitio) -> dict:
    """Fallback cuando `_referencia_desde_coordenadas(lat, lon)` ya falló en el punto exacto --
    reintenta en una pequeña espiral de puntos cercanos (radios crecientes, `_RADIOS_
    PROXIMIDAD_M`) antes de darse por vencido. Devuelve la primera referencia catastral real
    que encuentre (mismo criterio del PRD §6: "se toma la primera que resuelva, en el orden de
    radio creciente" -- no se intenta decidir cuál es "la correcta" si varias resolviesen).

    Si el presupuesto total de tiempo se agota, o si los 12 puntos fallan todos, relanza
    `error_del_punto_exacto` (el error ORIGINAL del punto exacto, no un error genérico de la
    espiral) -- quien llama ya sabe tratar ese tipo de error, y el mensaje sigue siendo honesto:
    "no hay parcela aquí", no "la espiral falló"."""
    inicio = time.monotonic()
    for radio_m in _RADIOS_PROXIMIDAD_M:
        for este_unit, norte_unit in _DIRECCIONES_PROXIMIDAD:
            if time.monotonic() - inicio > _PRESUPUESTO_TOTAL_PROXIMIDAD_S:
                logger.warning(
                    "Espiral de proximidad: presupuesto de tiempo (%.1fs) agotado antes de probar "
                    "todos los puntos -- se abandona con el error del punto exacto.",
                    _PRESUPUESTO_TOTAL_PROXIMIDAD_S,
                )
                raise error_del_punto_exacto
            lat_probar, lon_probar = _desplazar_metros(lat, lon, este_unit * radio_m, norte_unit * radio_m)
            try:
                return _referencia_desde_coordenadas(
                    lat_probar, lon_probar, timeout=_TIMEOUT_INTENTO_PROXIMIDAD_S
                )
            except ErrorDeSitio:
                continue
    logger.info(
        "Espiral de proximidad: los %d puntos (radios %s) no encontraron ninguna parcela "
        "catastrada cerca de (%.6f, %.6f) -- probablemente un punto genuinamente sin catastrar "
        "(vía pública, parque...), no un fallo del propio servicio.",
        len(_RADIOS_PROXIMIDAD_M) * len(_DIRECCIONES_PROXIMIDAD), _RADIOS_PROXIMIDAD_M, lat, lon,
    )
    raise error_del_punto_exacto


def _referencia_desde_coordenadas_resiliente(lat: float, lon: float) -> dict:
    """Punto de entrada resiliente para el Paso 0 y el visor 3D: intenta el punto exacto
    primero (caso mayoritario hoy, cero coste añadido -- PRD §6 "el punto exacto SÍ resuelve a
    la primera") y solo si falla, prueba la espiral de proximidad. Si el punto exacto YA
    resuelve, esta función no dispara ninguna llamada de red adicional (criterio de aceptación
    §8.3 del PRD)."""
    try:
        return _referencia_desde_coordenadas(lat, lon)
    except ErrorDeSitio as error_punto_exacto:
        return _referencia_por_proximidad(lat, lon, error_del_punto_exacto=error_punto_exacto)


def _geometria_parcela_catastro(referencia_catastral: str) -> dict:
    params = urllib.parse.urlencode({
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "StoredQuery_ID": "GetParcel", "REFCAT": referencia_catastral, "srsname": "EPSG::4326",
    })
    # `intentos_ante_timeout=2` (2026-08-17, ver docstring de `_get`): un reintento simple, mismo
    # timeout, ante un timeout de red real -- NUNCA ante "esa referencia catastral no tiene polígono"
    # (eso seguiría siendo un fallo real a la primera, `_es_timeout` lo distingue).
    cuerpo = _get("%s?%s" % (_URL_WFS_PARCELA, params), intentos_ante_timeout=2)
    anillo, superficie_m2 = _parsear_poligono_gml(cuerpo)
    lat, lon = _centroide(anillo)
    return {
        "tipo": "Polygon",
        "coordenadas": [[round(lon, 7), round(lat, 7)] for lon, lat in anillo],
        "superficie_m2": superficie_m2,
        "centro": {"lat": round(lat, 7), "lon": round(lon, 7)},
    }


# --- Overpass: colindantes, viales, zonas verdes, equipamientos -----------

_EQUIPAMIENTOS_RELEVANTES = (
    'node["amenity"~"^(school|hospital|clinic|pharmacy|kindergarten)$"]',
    'node["shop"~"^(supermarket|convenience)$"]',
    'node["railway"~"^(station|subway_entrance)$"]',
    'node["highway"="bus_stop"]',
)


def _mapear_colindantes(elements: List[dict]) -> List[dict]:
    colindantes = []
    for el in elements:
        tags = el.get("tags") or {}
        niveles = tags.get("building:levels")
        nombre = tags.get("name")
        if not nombre and tags.get("addr:housenumber"):
            nombre = ("%s %s" % (tags.get("addr:street", ""), tags.get("addr:housenumber", ""))).strip()
        colindantes.append({
            "nombre": nombre or None,
            "altura_plantas": int(niveles) if niveles and niveles.isdigit() else None,
            "lat": (el.get("center") or {}).get("lat"),
            "lon": (el.get("center") or {}).get("lon"),
        })
    return colindantes


def _mapear_viales(elements: List[dict]) -> List[dict]:
    return [
        {
            "nombre": (el.get("tags") or {}).get("name"),
            "tipo": (el.get("tags") or {}).get("highway"),
            "ancho_m": _a_float((el.get("tags") or {}).get("width")),
        }
        for el in elements
    ]


def _mapear_zonas_verdes(elements: List[dict]) -> List[dict]:
    return [
        {"nombre": (el.get("tags") or {}).get("name") or "(sin nombre en OSM)"}
        for el in elements
    ]


def _mapear_equipamientos(elements: List[dict]) -> List[dict]:
    equipamientos = []
    for el in elements:
        tags = el.get("tags") or {}
        equipamientos.append({
            "nombre": tags.get("name") or "(sin nombre en OSM)",
            "categoria": tags.get("amenity") or tags.get("shop") or tags.get("railway") or tags.get("highway"),
        })
    return equipamientos


def _colindantes_overpass(lat: float, lon: float, radio_m: int = 80) -> List[dict]:
    query = (
        "[out:json][timeout:20];(way(around:%d,%s,%s)[\"building\"];);out tags center;"
        % (radio_m, lat, lon)
    )
    return _mapear_colindantes(_post_overpass(query).get("elements") or [])


def _viales_overpass(lat: float, lon: float, radio_m: int = 80) -> List[dict]:
    query = (
        "[out:json][timeout:20];(way(around:%d,%s,%s)[\"highway\"];);out tags center;"
        % (radio_m, lat, lon)
    )
    return _mapear_viales(_post_overpass(query).get("elements") or [])


def _zonas_verdes_overpass(lat: float, lon: float, radio_m: int = 500) -> List[dict]:
    query = (
        "[out:json][timeout:20];("
        "way(around:%d,%s,%s)[\"leisure\"=\"park\"];"
        "way(around:%d,%s,%s)[\"landuse\"~\"^(forest|grass|recreation_ground)$\"];"
        ");out tags center;" % (radio_m, lat, lon, radio_m, lat, lon)
    )
    return _mapear_zonas_verdes(_post_overpass(query).get("elements") or [])


def _equipamientos_overpass(lat: float, lon: float, radio_m: int = 1000) -> List[dict]:
    ramas = "".join("%s(around:%d,%s,%s);" % (r, radio_m, lat, lon) for r in _EQUIPAMIENTOS_RELEVANTES)
    query = "[out:json][timeout:25];(%s);out tags;" % ramas
    return _mapear_equipamientos(_post_overpass(query).get("elements") or [])


def _estimar_altura_edificio(tags: dict) -> Tuple[float, str]:
    """La altura de un edificio colindante NUNCA viene medida de verdad con fiabilidad sistemática
    (ni Catastro ni OSM la traen siempre) -- se estima, por este orden: (1) `height`/`building:height`
    si el propio OSM ya trae una medida en metros, (2) `building:levels` × 3.2m/planta (2026-08-17,
    ajuste explícito de Pablo -- antes 3.0m, misma convención de altura libre que usaba el resto de
    ArchMuse; este valor queda propio de la estimación de edificios colindantes, no toca
    `ALTURA_PLANTA_M`/`DEFAULT_FLOOR_HEIGHT` del generador real), (3) 7m por defecto si no hay ningún
    dato (2026-08-17, antes 9m). `origen_altura` en el resultado dice de cuál de los tres vino -- nunca
    se presenta una estimación como si fuera una medida."""
    height_tag = _a_float(tags.get("height") or tags.get("building:height"))
    if height_tag:
        return height_tag, "medida_osm"
    niveles = tags.get("building:levels")
    if niveles and str(niveles).isdigit():
        return int(niveles) * 3.2, "estimada_por_plantas"
    return 7.0, "estimada_por_defecto"


def edificios_colindantes_geometria(lat: float, lon: float, radio_m: int = 180) -> List[dict]:
    """Huella (footprint) REAL de los edificios colindantes -- a diferencia de `_colindantes_overpass`
    (que solo trae el centroide, `out tags center;`), esto pide la geometría completa del polígono
    (`out body geom;`) para poder extruir un volumen 3D real en el visor, no una caja genérica.

    Usada por `/api/proyectos/<id>/entorno-3d` (2026-08-16, "contexto urbano realista en el visor
    3D") -- vive aquí, no en `app.py`, por el mismo principio que el resto de este módulo: es lectura
    determinista de un registro público, no una decisión de presentación. La conversión a metros
    locales (este/norte) y la rotación por `norte_grados` del proyecto se hacen en el cliente
    (`static/viewer-edificio.js`), no aquí -- esta función solo devuelve lat/lon reales, igual que el
    resto del módulo."""
    query = (
        "[out:json][timeout:25];(way(around:%d,%s,%s)[\"building\"];);out body geom;"
        % (radio_m, lat, lon)
    )
    elements = _post_overpass(query).get("elements") or []
    edificios = []
    for el in elements:
        geometria = el.get("geometry")
        if not geometria or len(geometria) < 3:
            continue
        vertices = [
            [p.get("lat"), p.get("lon")] for p in geometria
            if p.get("lat") is not None and p.get("lon") is not None
        ]
        if len(vertices) >= 2 and vertices[0] == vertices[-1]:
            vertices = vertices[:-1]  # anillo cerrado: el último nodo repite el primero
        if len(vertices) < 3:
            continue
        altura_m, origen_altura = _estimar_altura_edificio(el.get("tags") or {})
        edificios.append({"vertices": vertices, "altura_m": altura_m, "origen_altura": origen_altura})
    return edificios


def geometria_parcela_por_coordenadas(lat: float, lon: float) -> dict:
    """Contorno real de la parcela (Catastro) a partir de una coordenada, para el visor 3D
    (2026-08-16, `docs/prd/2026-08-16-sandbox-navegacion-profesional-y-lindes.md`) -- reutiliza
    exactamente los dos pasos que ya usa `obtener_datos_parcela` (resolver Referencia Catastral por
    coordenadas, luego pedir su geometría WFS), pero SIN las 4 consultas de Overpass en paralelo
    (colindantes/viales/zonas_verdes/equipamientos) que trae `obtener_datos_parcela` -- el visor 3D ya
    hace su propia consulta de colindantes, más ligera, con `edificios_colindantes_geometria`; llamar
    aquí a la función pesada duplicaría ese trabajo y añadiría ~4 peticiones a Overpass innecesarias
    solo para dibujar un contorno.

    Deja subir `ErrorDeSitio` tal cual (mismo criterio que `edificios_colindantes_geometria`): quien
    llama decide si lo trata como "no disponible, no error" -- aquí no se sabe si el llamador quiere
    seguir sin contorno o propagar el fallo."""
    rc_info = _referencia_desde_coordenadas_resiliente(lat, lon)
    return _geometria_parcela_catastro(rc_info["referencia_catastral"])


# --- Procedencia (Fase A, PRD 2026-08-20-procedencia-y-fecha-de-datos-de-
# parcela.md) --------------------------------------------------------------
#
# Recomendación técnica del PRD (§9): NO se reutiliza `agente.afirmacion.
# Afirmacion` -- su campo `fuente` exige `capacidad_id@version`, es decir,
# que quien produce el dato esté registrado como `Capacidad` en `agente/
# registro.py`. Este módulo vive fuera del vertical `agente/` por completo
# (lo llama un endpoint Flask directo, sin Ejecutor/Plan/Skill de por
# medio); registrarlo tocaría el techo de C4, expresamente fuera de
# alcance. Se sigue en su lugar el mismo espíritu que ya usa `normativa.
# ambito.Procedencia` (ningún valor viaja desnudo) con la forma más simple
# que encaja en un módulo que ya es 100% dicts sin estado -- ninguna clase
# nueva, un dict con forma fija.


def _ahora_iso() -> str:
    """Mismo formato que `analyzer/storage.py::_ahora()` -- ISO 8601 UTC,
    segundos. Dos funciones porque este módulo es deliberadamente una
    función pura sin estado (ver docstring del módulo): no importa nada de
    `storage.py`, que sí toca disco."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _procedencia(fuente: str) -> dict:
    """El bloque de procedencia que viaja pegado a `geometria_parcela`/
    `referencia_catastral` en el resultado. `de_cache` nace siempre en
    `False` aquí: este módulo no sabe si se está sirviendo una respuesta ya
    guardada -- eso lo decide `app.py`, que sí conoce el estado de la caché
    (`analyzer/storage.py`), y lo marca `True` justo antes de responder en
    el camino de caché. `consultado_en`, en cambio, SÍ debe congelarse aquí:
    una vez guardado en `analyzer/storage.py`, un acierto de caché
    devuelve el mismo dict tal cual, así que la fecha que lleva dentro seguirá
    siendo la de la consulta ORIGINAL sin que nadie tenga que recordarlo
    (criterio de aceptación del PRD, §8.3)."""
    return {"fuente": fuente, "consultado_en": _ahora_iso(), "de_cache": False}


def _a_float(valor) -> Optional[float]:
    if not valor:
        return None
    m = re.search(r"[\d.,]+", str(valor))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


# --- Orquestador -------------------------------------------------------


#: Extraído de `obtener_datos_parcela` (2026-08-17, docs/prd/2026-08-17-desacople-paso0-y-parcela-
#: matriz.md, §14 -- alcance aprobado): las 4 consultas de Overpass en paralelo, ahora reutilizables
#: por separado desde `entorno_overpass_por_coordenadas` (fetch no bloqueante que el cliente dispara
#: DESPUÉS de pintar la parcela con los datos rápidos de Catastro) sin duplicar la lógica de
#: paralelismo ni sus mensajes de error -- una sola fuente de verdad para las dos formas de pedirlas.
def _entorno_overpass(lat: float, lon: float) -> Tuple[Dict[str, list], List[str]]:
    resultado: Dict[str, list] = {"colindantes": [], "viales": [], "zonas_verdes": [], "equipamientos": []}
    errores: List[str] = []
    tareas = (
        ("colindantes", _colindantes_overpass, 80),
        ("viales", _viales_overpass, 80),
        ("zonas_verdes", _zonas_verdes_overpass, 500),
        ("equipamientos", _equipamientos_overpass, 1000),
    )
    # Fix urgente (2026-08-15, "no termina de cargar nada" reportado en vivo): estas 4 consultas son
    # independientes entre sí, pero se lanzaban una detrás de otra -- con los 3 reintentos y las esperas
    # de `_post_overpass`, CADA una puede tardar hasta ~90s en el peor caso (Overpass lento/con rate
    # limit, ya observado en vivo en esta misma sesión), así que en serie el peor caso rondaba los
    # 5-6 minutos con el spinner "Consultando Catastro" sin ninguna señal de que algo iba mal. En
    # paralelo, el peor caso se acerca a lo que tarda LA MÁS LENTA de las 4, no la suma de las 4.
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(tareas)) as ejecutor:
        futuros = {ejecutor.submit(fn, lat, lon, radio): nombre for nombre, fn, radio in tareas}
        for futuro in concurrent.futures.as_completed(futuros):
            nombre = futuros[futuro]
            try:
                resultado[nombre] = futuro.result()
            except ErrorDeSitio as exc:
                errores.append("Overpass (%s): %s" % (nombre, exc))
    return resultado, errores


def entorno_overpass_por_coordenadas(lat: float, lon: float) -> Dict[str, Any]:
    """Punto de entrada público para pedir SOLO el entorno de Overpass (colindantes/viales/zonas_verdes/
    equipamientos) por coordenadas, sin repetir la resolución de Catastro -- usado por el fetch no
    bloqueante que `/api/analizar-sitio` (`app.py`, parámetro `solo_entorno`) dispara desde el propio
    cliente DESPUÉS de que el Paso 0 ya pintó la parcela con la respuesta rápida (RC + geometría).
    Nunca lanza, mismo criterio que `obtener_datos_parcela`: cualquier fallo de una consulta concreta
    se recoge en `errores`, nunca bloquea a las demás.

    `entorno_consultado` (corregido 2026-08-17, bug crítico reportado en vivo): antes se ponía a
    `True` SIEMPRE, incluso cuando las 4 consultas fallaban del todo (Overpass degradado) -- y
    `app.py:analizar_sitio` (rama `solo_entorno`) usa exactamente este flag para decidir si vale la
    pena volver a intentarlo (`if datos_previos.get("entorno_consultado"): ... no repetir`). El efecto
    real, verificado en vivo: una parcela que tuviera la mala suerte de coincidir con Overpass caído
    quedaba con colindantes/viales/zonas_verdes/equipamientos vacíos PARA SIEMPRE (cacheado en SQLite),
    aunque Overpass se recuperase segundos después -- exactamente el "faltan los colindantes" reportado.
    Ahora solo cuenta como "consultado" un intento SIN errores; con algún error, sigue `False` para que
    la próxima vez que se pida este mismo punto (reapertura del Paso 0, o el propio `entorno_3d_punto`
    de más abajo si comparte este criterio) se reintente de verdad en vez de repetir el hueco vacío."""
    datos, errores = _entorno_overpass(lat, lon)
    datos["errores"] = errores
    datos["entorno_consultado"] = not errores
    return datos


def obtener_datos_parcela(
    referencia_catastral: Optional[str] = None,
    municipio: Optional[str] = None,
    direccion: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    incluir_overpass: bool = True,
) -> Dict[str, Any]:
    """Datos reales del entorno de una parcela. Nunca lanza — cualquier
    fallo de un paso concreto se anota en `errores` y el resto de pasos que
    sí puedan seguir (p. ej. Overpass con coordenadas ya conocidas) se
    intentan igual.

    `lat`/`lon` (no pedidos en el encargo original, añadidos aquí) son la
    vía de "entrada manual de coordenadas" que el encargo exige como
    respaldo cuando Catastro falla — sin ellos, un fallo de Catastro no
    tendría ninguna forma de seguir hasta Overpass con una coordenada dada
    a mano por el arquitecto.

    `municipio`/`direccion` **no resuelven todavía** a una referencia
    catastral (ver docstring del módulo) — se aceptan en la firma para no
    romper el contrato pedido, pero producen un error explícito en
    `errores`, nunca un intento silencioso que finja funcionar.

    `incluir_overpass` (2026-08-17, docs/prd/2026-08-17-desacople-paso0-y-parcela-matriz.md, §14 --
    alcance aprobado): por defecto `True`, sin cambio de comportamiento para los llamadores existentes
    (tests, y cualquier uso directo de esta función). `/api/analizar-sitio` (`app.py`) lo pone a
    `False` en su respuesta rápida del Paso 0 -- Catastro/WFS (RC + polígono + superficie) es lo único
    que hace falta para dibujar la parcela; las 4 consultas de Overpass, mucho más lentas y con más
    fallos observados en vivo, se piden después por separado (`entorno_overpass_por_coordenadas`)."""
    resultado: Dict[str, Any] = {
        "referencia_catastral": referencia_catastral,
        "direccion_catastro": None,
        "coordenadas": None,
        "geometria_parcela": None,
        # `None` hasta que se obtenga un dato REAL de Catastro más abajo -- nunca un valor de
        # relleno: la ausencia de procedencia es tan informativa como su presencia (Fase A del
        # PRD de parcela, 2026-08-20).
        "procedencia": None,
        "colindantes": [],
        "viales": [],
        "zonas_verdes": [],
        "equipamientos": [],
        "errores": [],
        # `False` hasta que el bloque de Overpass de abajo se ejecute de verdad -- distingue "todavía no
        # se ha pedido el entorno" (`incluir_overpass=False`, respuesta rápida del Paso 0) de "se pidió y
        # no encontró nada" (listas vacías con `entorno_consultado=True`). Lo usa `/api/analizar-sitio`
        # (`app.py`, `solo_entorno`) para no repetir las 4 consultas de Overpass si ya se completaron.
        "entorno_consultado": False,
    }

    centro_lat, centro_lon = lat, lon

    if referencia_catastral:
        try:
            geometria = _geometria_parcela_catastro(referencia_catastral)
            resultado["geometria_parcela"] = geometria
            resultado["coordenadas"] = geometria["centro"]
            resultado["procedencia"] = _procedencia(
                "Catastro (Sede Electrónica, WFS/INSPIRE — GetParcel por referencia catastral)"
            )
            centro_lat, centro_lon = geometria["centro"]["lat"], geometria["centro"]["lon"]
        except ErrorDeSitio as exc:
            resultado["errores"].append("Catastro (geometría de parcela): %s" % exc)
    elif lat is not None and lon is not None:
        # Clic en el mapa (sin RC todavía): resuelve la Referencia Catastral
        # real por coordenadas ANTES de pedir la geometría -- `_geometria_
        # parcela_catastro` exige una RC, no admite lat/lon directamente.
        # Si Catastro no tiene parcela en ese punto exacto (frecuente a
        # pocos metros de la real, ver docstring de la función), se sigue
        # igual con las coordenadas crudas para Overpass más abajo: un
        # fallo de Catastro nunca bloquea el resto del flujo.
        try:
            rc_info = _referencia_desde_coordenadas_resiliente(lat, lon)
            resultado["referencia_catastral"] = rc_info["referencia_catastral"]
            resultado["direccion_catastro"] = rc_info["direccion"]
            try:
                geometria = _geometria_parcela_catastro(rc_info["referencia_catastral"])
                resultado["geometria_parcela"] = geometria
                resultado["coordenadas"] = geometria["centro"]
                resultado["procedencia"] = _procedencia(
                    "Catastro (Sede Electrónica: Consulta_RCCOOR por coordenadas + "
                    "WFS/INSPIRE GetParcel)"
                )
                centro_lat, centro_lon = geometria["centro"]["lat"], geometria["centro"]["lon"]
            except ErrorDeSitio as exc:
                resultado["errores"].append("Catastro (geometría de parcela): %s" % exc)
        except ErrorDeSitio as exc:
            resultado["errores"].append("Catastro (referencia catastral por coordenadas): %s" % exc)
    elif municipio or direccion:
        resultado["errores"].append(
            "Resolución de municipio/dirección a referencia catastral no implementada todavía "
            "(ver docstring del módulo) — introduce coordenadas manualmente."
        )

    if centro_lat is not None and centro_lon is not None:
        if resultado["coordenadas"] is None:
            resultado["coordenadas"] = {"lat": centro_lat, "lon": centro_lon}
        if incluir_overpass:
            entorno, errores_overpass = _entorno_overpass(centro_lat, centro_lon)
            resultado["colindantes"] = entorno["colindantes"]
            resultado["viales"] = entorno["viales"]
            resultado["zonas_verdes"] = entorno["zonas_verdes"]
            resultado["equipamientos"] = entorno["equipamientos"]
            resultado["errores"].extend(errores_overpass)
            resultado["entorno_consultado"] = True
        # `incluir_overpass=False`: se deja `colindantes`/`viales`/`zonas_verdes`/`equipamientos` en
        # sus valores por defecto (listas vacías) y `entorno_consultado` en `False` -- NUNCA se anota
        # como error ("Overpass no consultado" no es un fallo, es la respuesta rápida a propósito, ver
        # docstring de arriba).
    elif not resultado["errores"]:
        resultado["errores"].append("Sin coordenadas (ni de Catastro ni introducidas a mano): no se consultó Overpass.")

    return resultado
