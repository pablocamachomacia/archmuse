# -*- coding: utf-8 -*-
"""Exportación del edificio de un proyecto a glTF binario (`.glb`), con
materiales PBR básicos según el estilo, y cálculo de su georreferenciación
para el visor Mapbox.

**Lo que este módulo NO hace, dicho por delante y no al final.** El encargo
pide "plantas, cubierta, voladizos, huecos/ventanas". ArchMuse no tiene, en
ningún sitio, datos reales de:

- **Voladizos**: ninguna pieza de la geometría se marca como "vuelo sobre
  la fachada" — `estilo["vuelo_maximo_m"]` (motor de estilos) es una
  directiva de texto para Claude, no una geometría medida. Generar un
  volumen de vuelo aquí sería inventar geometría que no existe en el
  proyecto real.
- **Huecos/ventanas**: confirmado ya en la auditoría de CAP-5 de esta
  sesión ("el modelo no contiene elementos de carpintería") — no hay
  posición de puertas ni ventanas en ningún sitio del payload.
- **Cubierta real**: no hay pendiente, forma ni tipo de cubierta en
  ningún dato del proyecto — solo nº de plantas y altura libre.

Así que esta primera versión exporta **volúmenes sólidos por habitación,
apilados por planta, con una losa de cubierta plana en la última** — una
masa creíble del edificio, no una réplica de sus huecos ni su cubierta
real. Los materiales PBR sí son reales (color/rugosidad/metalicidad según
el primer material compatible del estilo), y si en el futuro se marcan
voladizos/huecos con datos reales, este módulo es donde deberían añadirse
— no antes.

**Segunda implementación de la misma geometría, mismo riesgo ya señalado en
`docs/prd/2026-08-15-exportacion-gltf-visor-mapbox.md`**: `static/viewer-
edificio.js` extruye la misma geometría en el navegador, con three.js, sin
que ningún mecanismo garantice que las dos coincidan si una cambia sin la
otra. Mismo agrupamiento por planta que esa vista (`groupFloors`, regex
`^Planta\\s+(\\d+)`), a propósito, para minimizar la divergencia.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

try:
    import trimesh
    from trimesh.visual.material import PBRMaterial
except ImportError:  # pragma: no cover - mismo patrón que anthropic en otros módulos
    trimesh = None  # type: ignore[assignment]
    PBRMaterial = None  # type: ignore[assignment]

_RE_PLANTA = re.compile(r"^Planta\s+(\d+)", re.IGNORECASE)

#: Heurística determinista nombre-de-material -> PBR. Ninguna de estas
#: cifras viene de una ficha técnica real; son valores razonables de
#: catálogo, igual de "contenido sin revisar" que el resto del motor de
#: estilos (ver docstring de `analyzer/estilos.py`).
_MATERIALES_PBR: Tuple[Tuple[str, dict], ...] = (
    ("vidrio", {"baseColorFactor": [0.65, 0.80, 0.85, 0.35], "roughnessFactor": 0.05, "metallicFactor": 0.0}),
    ("hormigon", {"baseColorFactor": [0.62, 0.62, 0.60, 1.0], "roughnessFactor": 0.85, "metallicFactor": 0.0}),
    ("ladrillo", {"baseColorFactor": [0.55, 0.30, 0.24, 1.0], "roughnessFactor": 0.80, "metallicFactor": 0.0}),
    ("piedra", {"baseColorFactor": [0.68, 0.64, 0.55, 1.0], "roughnessFactor": 0.75, "metallicFactor": 0.0}),
    ("madera", {"baseColorFactor": [0.55, 0.38, 0.22, 1.0], "roughnessFactor": 0.55, "metallicFactor": 0.0}),
    ("acero", {"baseColorFactor": [0.72, 0.72, 0.74, 1.0], "roughnessFactor": 0.25, "metallicFactor": 0.85}),
    ("aluminio", {"baseColorFactor": [0.80, 0.80, 0.82, 1.0], "roughnessFactor": 0.20, "metallicFactor": 0.90}),
    ("metal", {"baseColorFactor": [0.70, 0.70, 0.72, 1.0], "roughnessFactor": 0.30, "metallicFactor": 0.80}),
    ("enlucido", {"baseColorFactor": [0.92, 0.90, 0.85, 1.0], "roughnessFactor": 0.60, "metallicFactor": 0.0}),
    ("estuco", {"baseColorFactor": [0.90, 0.87, 0.80, 1.0], "roughnessFactor": 0.55, "metallicFactor": 0.0}),
    ("teja", {"baseColorFactor": [0.65, 0.30, 0.18, 1.0], "roughnessFactor": 0.70, "metallicFactor": 0.0}),
)
_MATERIAL_POR_DEFECTO = {"baseColorFactor": [0.75, 0.75, 0.75, 1.0], "roughnessFactor": 0.70, "metallicFactor": 0.0}
_MATERIAL_CUBIERTA_POR_DEFECTO = {"baseColorFactor": [0.35, 0.33, 0.32, 1.0], "roughnessFactor": 0.75, "metallicFactor": 0.0}


class ErrorDeExportacionGltf(Exception):
    """Fallo al construir o exportar la geometría — nunca un archivo `.glb`
    a medias o corrupto."""


def _quitar_tildes(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(ch for ch in texto if not unicodedata.combining(ch))


def _material_desde_texto(texto: str, por_defecto: dict) -> "PBRMaterial":
    # BUG real encontrado por el propio test de este módulo (2026-08-15):
    # "hormigón" (con tilde, tal como lo escribe `analyzer/estilos.py`)
    # nunca coincidía con la clave "hormigon" (sin tilde) de
    # `_MATERIALES_PBR` -- todo estilo con materiales acentuados caía
    # siempre al color por defecto, en silencio, sin ningún error que lo
    # delatara. Se normalizan tildes en los dos lados antes de comparar.
    texto_normalizado = _quitar_tildes((texto or "").lower())
    for clave, params in _MATERIALES_PBR:
        if _quitar_tildes(clave) in texto_normalizado:
            return PBRMaterial(**params)
    return PBRMaterial(**por_defecto)


def _material_muros(estilo_dict: Optional[dict]) -> "PBRMaterial":
    """Primer material compatible del estilo -- simplificación deliberada:
    asignar un material distinto por pieza (muro/cubierta/carpintería)
    exigiría saber qué parte de la geometría es cada cosa, y hoy todo es un
    bloque sólido por habitación (ver docstring del módulo)."""
    materiales = (estilo_dict or {}).get("materiales_compatibles") or []
    if not materiales:
        return PBRMaterial(**_MATERIAL_POR_DEFECTO)
    return _material_desde_texto(materiales[0], _MATERIAL_POR_DEFECTO)


def _agrupar_por_planta(viviendas: List[dict]) -> List[List[dict]]:
    """Mismo criterio que `groupFloors` en `static/viewer-edificio.js`:
    planta = primer entero tras "Planta " en el nombre de la vivienda, o 1
    si no hay coincidencia (DXF analizado, sin esa convención de nombre)."""
    por_planta: Dict[int, List[dict]] = {}
    for v in viviendas or []:
        m = _RE_PLANTA.match(v.get("nombre") or "")
        numero = int(m.group(1)) if m else 1
        por_planta.setdefault(numero, []).append(v)
    return [por_planta[n] for n in sorted(por_planta)]


def _extruir_habitacion(habitacion: dict, y_base: float, altura: float) -> Optional["trimesh.Trimesh"]:
    poligono_crudo = habitacion.get("poligono")
    if not poligono_crudo or len(poligono_crudo) < 3:
        return None
    import shapely.geometry as sg

    # Mismo giro de eje que `static/viewer-edificio.js::extractUnitRooms`
    # (`z: -p[1]`): DXF (x, y) de planta -> 3D (x, z) horizontal, y = altura
    # (three.js/glTF, Y arriba) -- para que el modelo exportado no quede
    # espejado respecto al visor en el navegador.
    poligono_2d = sg.Polygon([(p[0], -p[1]) for p in poligono_crudo])
    if not poligono_2d.is_valid or poligono_2d.area <= 0:
        poligono_2d = poligono_2d.buffer(0)
        if poligono_2d.is_empty:
            return None
    try:
        malla = trimesh.creation.extrude_polygon(poligono_2d, height=altura)
    except Exception as exc:  # noqa: BLE001 - una habitación con geometría rara no debe tumbar la exportación entera
        raise ErrorDeExportacionGltf(
            "no se pudo extruir «%s»: %s" % (habitacion.get("nombre", "?"), exc)
        ) from exc
    # `extrude_polygon` extruye en Z; se rota a Y-arriba (convención glTF/
    # three.js) y se traslada a su planta.
    malla.apply_transform(trimesh.transformations.rotation_matrix(-1.5707963267948966, [1, 0, 0]))
    malla.apply_translation([0, y_base, 0])
    return malla


def exportar_proyecto_a_glb(proyecto: dict, estilo_dict: Optional[dict] = None) -> bytes:
    """`proyecto` es el payload ya serializado (`obtener_proyecto()` o el
    de una generación reciente) — necesita `viviendas[].habitaciones[].
    poligono` y, si viene de una generación, `edificio.altura_libre_m`
    (2.8 si no está, mismo valor por defecto que `ai_generator.py`/
    `viewer-edificio.js`).

    Devuelve los bytes `.glb`. Levanta `ErrorDeExportacionGltf` si no hay
    ninguna geometría exportable — nunca un archivo vacío o corrupto
    fingiendo ser válido."""
    if trimesh is None:
        raise ErrorDeExportacionGltf("el paquete «trimesh» no está instalado")

    altura_planta = (proyecto.get("edificio") or {}).get("altura_libre_m") or 2.8
    plantas = _agrupar_por_planta(proyecto.get("viviendas") or [])
    if not plantas:
        raise ErrorDeExportacionGltf("el proyecto no tiene ninguna vivienda con geometría")

    material_muros = _material_muros(estilo_dict)
    material_cubierta = PBRMaterial(**_MATERIAL_CUBIERTA_POR_DEFECTO)

    escena = trimesh.Scene()
    mallas_planta_actual: List["trimesh.Trimesh"] = []
    n_habitaciones_exportadas = 0

    for numero_planta, viviendas_planta in enumerate(plantas):
        y_base = numero_planta * altura_planta
        mallas_planta_actual = []
        for vivienda in viviendas_planta:
            for habitacion in vivienda.get("habitaciones") or []:
                malla = _extruir_habitacion(habitacion, y_base, altura_planta)
                if malla is None:
                    continue
                malla.visual = trimesh.visual.TextureVisuals(material=material_muros)
                nombre_nodo = "planta%d_%s_%s" % (
                    numero_planta, vivienda.get("id", "v"), habitacion.get("nombre", "hab"),
                )
                escena.add_geometry(malla, node_name=nombre_nodo)
                n_habitaciones_exportadas += 1

    if n_habitaciones_exportadas == 0:
        raise ErrorDeExportacionGltf("ninguna habitación tenía un polígono exportable")

    # Cubierta: losa plana sobre el envolvente de TODAS las habitaciones de
    # la última planta, a la altura del techo del último nivel. Simplifica
    # deliberadamente cualquier forma real de cubierta (ver docstring).
    try:
        y_cubierta = len(plantas) * altura_planta
        envolvente = trimesh.util.concatenate([
            _extruir_habitacion(h, 0, 0.15)
            for v in plantas[-1] for h in (v.get("habitaciones") or [])
            if h.get("poligono") and len(h["poligono"]) >= 3
        ])
        envolvente.apply_translation([0, y_cubierta, 0])
        envolvente.visual = trimesh.visual.TextureVisuals(material=material_cubierta)
        escena.add_geometry(envolvente, node_name="cubierta")
    except Exception:  # noqa: BLE001 - la cubierta es un añadido cosmético, nunca bloquea la exportación del edificio real
        pass

    try:
        return escena.export(file_type="glb")
    except Exception as exc:  # noqa: BLE001
        raise ErrorDeExportacionGltf("fallo exportando a glb: %s" % exc) from exc


def calcular_georreferencia(proyecto: dict, sitio_datos: Optional[dict]) -> Optional[dict]:
    """Metadatos de posicionamiento para el visor Mapbox: lat/lon del
    centro de la parcela (de `analyzer.sitio`), altitud (SIEMPRE `None` —
    ni Catastro ni Overpass la traen, ver docstring de `analyzer/sitio.py`;
    nunca se inventa un valor), y heading en grados desde `proyecto.
    norte_grados`.

    `None` si no hay ningún sitio enlazado a este proyecto — nunca unas
    coordenadas inventadas o "por defecto" para que el visor tenga algo
    que mostrar.

    **Sin verificar contra un mapa real**: el heading asume que
    `norte_grados` (grados desde el norte real hasta la parte de arriba
    del plano, sentido horario -- mismo criterio que el resto de ArchMuse)
    es directamente equivalente al `heading`/bearing que espera Threebox
    (grados en sentido horario desde el norte) — es la lectura más directa
    de los dos, pero no se ha comprobado visualmente contra un mapa real
    (hace falta un `MAPBOX_TOKEN`, que este entorno no tiene)."""
    if not sitio_datos:
        return None
    coordenadas = (sitio_datos.get("datos") or {}).get("coordenadas")
    if not coordenadas:
        return None
    return {
        "lat": coordenadas.get("lat"),
        "lon": coordenadas.get("lon"),
        "altitud_m": None,
        "heading_grados": proyecto.get("norte_grados", 0.0),
        "clave_cache_sitio": sitio_datos.get("clave_cache"),
    }
