# -*- coding: utf-8 -*-
"""Normativa urbanística real por coordenada — piloto Madrid (PGOUM 97).

PRD: `docs/prd/2026-08-16-integracion-normativa-catastro-pgou.md`. Cliente del
servicio ArcGIS REST real y público del Ayuntamiento de Madrid
(`sigma.madrid.es/hosted/rest/services/pgoum97/...`) — misma familia técnica
que el mosaico de ortofoto ya integrado en `viewer-terreno.js`.

**Verificado en vivo antes de escribir código de producto** (Tarea 1 del plan
del PRD, "spike de verificación técnica", repetido y ampliado el mismo día de
la ejecución porque el spike original del PRD no bastaba para saber si la
Tarea 3 — la tabla de traducción — era siquiera posible con rigor):

1. `PGOUM97/PG_CONDICIONES_EDIFICACION/MapServer/6` SÍ responde con datos
   reales para un punto conocido (Gran Vía 31, Madrid): geometría real
   (reproyectada a EPSG:4326 pidiendo `outSR=4326` — el servicio nativo es
   EPSG:25830, confirmado con la respuesta cruda sin ese parámetro) y campos
   `CODMANZANA`/`NUMORD`/`COND_EDIF`/`COEF_Z` reales, no inventados.
2. **Ese mismo servicio está, por su propio nombre de capa y su propia
   leyenda** (`drawingInfo.renderer` del `MapServer/6`, consultado en vivo),
   **explícitamente acotado a la Norma Zonal 1.5** — la leyenda del valor 6 de
   `COND_EDIF` dice literalmente "Parcelas no reguladas por los parámetros de
   la Norma Zonal 1.5 (remitidas a planeamiento, espacios no edificables)".
   No es una capa "cualquier zona de Madrid".
3. **El servicio que resolvería "en qué Norma Zonal está un punto
   CUALQUIERA"** (`pgoum97/PG_ORDENACION`, el plano de Ordenación general) —
   el prerrequisito real para poder aplicar esta integración a un punto
   arbitrario de Madrid, no solo a los que ya sabemos que caen en Norma Zonal
   1.5 — **sigue devolviendo `"Service not started"` en vivo**, confirmado de
   nuevo el mismo día de esta implementación (mismo hallazgo que ya
   documentaba el PRD en su propia investigación previa, no resuelto todavía
   por el Ayuntamiento).
4. `pgoum97/PG_ORDENACION_SIN_AMBITO` (el servicio "sin ámbito", que sonaba a
   más genérico) **solo contiene, de verdad, una única Norma Zonal: la 1.5**
   (confirmado listando TODAS sus capas) — no es un catálogo de varias
   normas zonales, es un nombre engañoso para el mismo servicio acotado del
   punto 2.
5. **La propia Norma Zonal 1 (que cubre el punto de prueba, Gran Vía) no se
   regula con ocupación/edificabilidad/retranqueos** — investigación
   documental confirma que su modelo real es "fondo edificable + coeficiente
   ponderado de densidad", y que **la altura (número de plantas) NO la fija
   el grado en absoluto**: se determina caso a caso por las alturas de
   cornisa de los edificios colindantes y requiere aprobación de la CIPHAN
   (comisión de patrimonio). Los retranqueos tampoco aplican: es tipología de
   manzana cerrada (edificación a línea de fachada), por definición sin
   retranqueo. Ninguno de los 4 campos que `evaluator.py` espera
   (`ocupacion_maxima_pct`/`edificabilidad_maxima`/`plantas_maximas`/
   `retranqueos_m`) tiene una traducción numérica honesta posible desde
   `COND_EDIF`/`COEF_Z` para esta norma zonal, y no hay forma verificada de
   llegar a una Norma Zonal de tipología unifamiliar (Norma Zonal 8, que SÍ
   usa ocupación/edificabilidad en el sentido clásico) sin el servicio del
   punto 3, que está caído.

**Consecuencia, decisión de alcance tomada aquí, no un recorte silencioso**:
este módulo entrega la Tarea 2 del PRD (cliente real, códigos reales, nunca
inventados) y **deliberadamente NO entrega la Tarea 3** (tabla de traducción
código→número). Rellenar `ocupacion_maxima_pct`/`edificabilidad_maxima`/
`plantas_maximas`/`retranqueos_m` con un valor inventado a partir de
`COND_EDIF` sería exactamente el riesgo que el propio PRD señala como el más
grave de todo el documento (§9: "presentar un dato automático incorrecto
como si fuera fiable") — así que `limites_numericos` de
`normativa_urbanistica_por_coordenadas` es SIEMPRE `None` en este primer
incremento. Lo que sí se entrega es información real y verificada
(referencia catastral normativa, grado, coeficiente) como dato de contexto
en el HUD, con una nota honesta de qué falta y por qué.

Nunca lanza — mismo criterio que `analyzer/sitio.py` (`ErrorDeSitio` interna,
capturada siempre, nunca bloquea el flujo)."""
from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

USER_AGENT = "ArchMuse/1.0 (herramienta de arquitectura; uso interno)"

_URL_CONDICIONES_EDIFICACION = (
    "https://sigma.madrid.es/hosted/rest/services/pgoum97/PG_CONDICIONES_EDIFICACION/MapServer/6/query"
)

#: Bounding box aproximado del término municipal de Madrid -- NO un polígono exacto, un rectángulo de
#: descarte rápido (PRD §7.2: "sin llamar a ningún servicio externo" cuando está claramente fuera).
#: Fuente: Nominatim (`boundingbox` de "Madrid, España", tipo `administrative`/`boundary`, consultado en
#: vivo el mismo día) -- misma infraestructura que ya usa `sitio.geocodificar_direccion`, no un valor de
#: memoria. Al ser un rectángulo y Madrid tener una forma irregular, algún punto de un municipio VECINO
#: (p. ej. Boadilla del Monte) puede caer dentro de este rectángulo sin ser realmente Madrid capital --
#: no es un bug: el rectángulo solo decide si merece la pena llamar al servicio real; la respuesta real
#: del servicio (o su ausencia) es la que decide de verdad, igual que el resto de este módulo.
_BBOX_MADRID = {"lat_min": 40.3119774, "lat_max": 40.6437293, "lon_min": -3.8889539, "lon_max": -3.5183264}

#: Etiquetas reales, tomadas literalmente de la leyenda del propio servicio (`drawingInfo.renderer` de
#: `PG_CONDICIONES_EDIFICACION/MapServer/6`, consultada en vivo) -- nunca una paráfrasis inventada.
_ETIQUETAS_GRADO_NZ_1_5 = {
    1: "Grado 1",
    2: "Grado 2",
    3: "Grado 3",
    4: "Grado 4",
    5: "Grado 5",
    6: "Parcelas no reguladas por los parámetros de la Norma Zonal 1.5 (remitidas a planeamiento, espacios no edificables)",
}


class ErrorDeNormativaMadrid(Exception):
    """Un paso concreto (bbox, red, parseo) falló -- capturado siempre dentro de
    `normativa_urbanistica_por_coordenadas`, nunca se propaga."""


def _dentro_de_bbox_madrid(lat: float, lon: float) -> bool:
    return (_BBOX_MADRID["lat_min"] <= lat <= _BBOX_MADRID["lat_max"]) and (
        _BBOX_MADRID["lon_min"] <= lon <= _BBOX_MADRID["lon_max"]
    )


def _consultar_condiciones_edificacion(lat: float, lon: float, *, timeout: float = 10.0) -> Optional[dict]:
    """Consulta real por punto contra `PG_CONDICIONES_EDIFICACION/MapServer/6` -- `outSR=4326` para que
    ArcGIS reproyecte la geometría de vuelta a WGS84 en el servidor (el servicio nativo es EPSG:25830,
    confirmado en vivo; sin `outSR` la geometría de respuesta viene en metros UTM, no en lat/lon).

    `timeout=10.0` (no 5-6s): medido en vivo durante la implementación, este servicio concreto responde
    con una latencia muy irregular vía `urllib` -- entre 10 y 20+ segundos, con algún timeout real a los
    20s, frente a menos de 1s medido con `curl` para la misma consulta exacta. No se ha identificado la
    causa exacta (posible negociación TLS/keep-alive distinta entre clientes, o el propio servicio bajo
    carga variable) y no merece la pena perseguirla más: es exactamente el tipo de inestabilidad "sin SLA
    conocido" que el PRD (§9) ya anticipaba para la infraestructura municipal de Madrid, ahora confirmada
    independientemente con un segundo cliente HTTP. La llamada es best-effort y no bloqueante (se lanza en
    paralelo al abrir el Sandbox, nunca gatea su barra de progreso), así que un timeout más largo aquí solo
    cambia cuánto tiempo, como mucho, puede tardar en aparecer el aviso/dato -- nunca bloquea nada más.

    Devuelve `None` (no lanza) si no hay ningún resultado para el punto -- eso es información real
    ("esta parcela no está en Norma Zonal 1.5, o está fuera de la cobertura de esta capa"), no un error.
    Lanza `ErrorDeNormativaMadrid` solo ante fallo de red/timeout/respuesta no parseable -- best-effort,
    nunca bloqueante (PRD §6, mismo criterio que Catastro/Overpass en `sitio.py`)."""
    params = urllib.parse.urlencode({
        "geometry": "%s,%s" % (lon, lat), "geometryType": "esriGeometryPoint",
        "inSR": "4326", "outSR": "4326", "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*", "f": "json",
    })
    peticion = urllib.request.Request(
        "%s?%s" % (_URL_CONDICIONES_EDIFICACION, params), headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            crudo = respuesta.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ssl.SSLError) as exc:
        raise ErrorDeNormativaMadrid("PG_CONDICIONES_EDIFICACION: %s" % exc) from exc

    try:
        datos = json.loads(crudo)
    except (ValueError, TypeError) as exc:
        raise ErrorDeNormativaMadrid("PG_CONDICIONES_EDIFICACION: respuesta no es JSON válido: %s" % exc) from exc

    if isinstance(datos, dict) and datos.get("error"):
        # Servicio ArcGIS parado/mal configurado (visto en vivo: "Service not started" en un servicio
        # HERMANO durante la investigación de este módulo) -- se trata igual que un fallo de red: real,
        # pero best-effort, nunca bloqueante.
        raise ErrorDeNormativaMadrid("PG_CONDICIONES_EDIFICACION: %s" % datos["error"].get("message", datos["error"]))

    features = datos.get("features") if isinstance(datos, dict) else None
    if not features:
        return None  # sin resultado real para este punto -- no es un error, ver docstring

    atributos = (features[0] or {}).get("attributes") or {}
    return {
        "codigo_manzana": atributos.get("CODMANZANA"),
        "numero_catalogo": atributos.get("NUMORD"),
        "grado_condicion_edificacion": atributos.get("COND_EDIF"),
        "coeficiente_z": atributos.get("COEF_Z"),
    }


def normativa_urbanistica_por_coordenadas(lat: float, lon: float) -> Dict[str, Any]:
    """Punto de entrada público, único, del módulo. Nunca lanza -- cualquier fallo real (fuera de
    Madrid, servicio caído, timeout, sin resultado) se traduce en `disponible: False` + `motivo`
    legible, jamás en una excepción que rompa el flujo del Sandbox.

    `limites_numericos` es SIEMPRE `None` en este incremento -- ver el docstring del módulo (hallazgo
    5): no existe hoy una traducción verificada de `COND_EDIF`/`COEF_Z` a los 4 campos que
    `evaluator.py` necesita. `referencia` (cuando `disponible` es `True`) es información real de
    contexto -- para mostrar en el HUD como referencia, no para autorrellenar ningún campo numérico."""
    if not _dentro_de_bbox_madrid(lat, lon):
        return {
            "disponible": False,
            "dentro_de_piloto": False,
            "motivo": "Consulta automática de normativa disponible solo en el municipio de Madrid (piloto). Introduce los límites manualmente.",
            "fuente": None,
            "referencia": None,
            "limites_numericos": None,
        }

    try:
        crudo = _consultar_condiciones_edificacion(lat, lon)
    except ErrorDeNormativaMadrid as exc:
        logger.warning("normativa_urbanistica_por_coordenadas: %s", exc)
        return {
            "disponible": False,
            "dentro_de_piloto": True,
            "motivo": "No se ha podido consultar el geoportal urbanístico de Madrid ahora mismo. Introduce los límites manualmente.",
            "fuente": None,
            "referencia": None,
            "limites_numericos": None,
        }

    if crudo is None:
        return {
            "disponible": False,
            "dentro_de_piloto": True,
            "motivo": "No se ha podido determinar la normativa automáticamente para esta zona (fuera de la Norma Zonal 1.5, única cubierta en este piloto) — verifica los límites en el geoportal municipal.",
            "fuente": None,
            "referencia": None,
            "limites_numericos": None,
        }

    grado = crudo["grado_condicion_edificacion"]
    etiqueta_grado = _ETIQUETAS_GRADO_NZ_1_5.get(grado, "Grado %s" % grado if grado is not None else "sin grado")
    return {
        "disponible": True,
        "dentro_de_piloto": True,
        "motivo": (
            "Referencia real del PGOUM 97 encontrada para esta parcela, pero todavía no hay una tabla de "
            "traducción numérica verificada para la Norma Zonal 1.5 (ver detalle en el propio PRD) — "
            "consulta el geoportal municipal para los valores exactos e introdúcelos a mano."
        ),
        "fuente": "PGOUM 97 (Ayuntamiento de Madrid) — Plano de Condiciones de la Edificación, Norma Zonal 1.5",
        "referencia": {
            "norma_zonal": "1.5",
            "codigo_manzana": crudo["codigo_manzana"],
            "numero_catalogo": crudo["numero_catalogo"],
            "grado_condicion_edificacion": grado,
            "grado_etiqueta": etiqueta_grado,
            "coeficiente_z": crudo["coeficiente_z"],
        },
        "limites_numericos": None,
    }
