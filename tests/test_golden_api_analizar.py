# -*- coding: utf-8 -*-
"""G6 — golden del CONTRATO DE LA API: `POST /api/analizar`.

Ejecutar:  python tests/test_golden_api_analizar.py

Congela lo que ve la SPA: las claves de primer nivel del payload, y por
vivienda su nombre, número de habitaciones, puntuación, valoración y la lista
ordenada de títulos de problema. Es el único golden que recorre el pipeline
entero de extremo a extremo, HTTP incluido.

**Qué NO se congela, y por qué cada exclusión:**

- `proyecto_id`: es un `uuid4` nuevo en cada ejecución (`storage.guardar_proyecto`).
- `svg` y `miniatura`: presentación. Un retoque de estilo en `plan_svg.py` no
  puede romper la red de seguridad del modelo.
- `analisis_ia`: se comprueba que sea **`null`**, que es lo que devuelve
  `ai_analyst.analyze_with_ai` sin `ANTHROPIC_API_KEY` — `tests/golden.py` la
  borra del entorno antes de importar nada. Congelar un texto generado por un
  modelo sería congelar ruido.
- `descripcion`/`solucion` de cada issue: prosa. Se congela el `titulo`, el
  `codigo` y la `severity`, que es lo que clasifica.

`ARCHMUSE_DATA_DIR` apunta a un temporal desde `tests/golden.py`: este golden
escribe un proyecto en la base de datos al terminar, y no puede ser la de
desarrollo (mismo patrón que `tests/test_storage.py`).
"""
from io import BytesIO

import golden

from analyzer import storage

storage.init_db()

import app as app_module  # noqa: E402  (después de fijar ARCHMUSE_DATA_DIR)

CLIENTE = app_module.app.test_client()


def _analizar():
    with open(golden.DXF, "rb") as fh:
        datos = {"dxf": (BytesIO(fh.read()), "ejemplo.dxf")}
    respuesta = CLIENTE.post("/api/analizar", data=datos,
                             content_type="multipart/form-data")
    if respuesta.status_code != 200:
        raise AssertionError("esperaba 200, obtuvo %d: %s" % (
            respuesta.status_code, respuesta.get_data(as_text=True)[:400]))
    return respuesta.get_json()


def construir():
    payload = _analizar()
    proyecto = payload.get("proyecto") or {}

    return {
        "http": 200,
        "claves_primer_nivel": sorted(payload.keys()),
        "analisis_ia_es_null": payload.get("analisis_ia") is None,
        "puntuacion_global": payload.get("puntuacion"),
        "valoracion_global": payload.get("valoracion"),
        "n_viviendas": len(payload.get("viviendas") or []),
        "viviendas": [
            {
                "nombre": v.get("nombre"),
                "n_habitaciones": len(v.get("habitaciones") or []),
                "puntuacion": v.get("puntuacion"),
                "valoracion": v.get("valoracion"),
                "superficie_total_m2": v.get("superficie_total_m2"),
                "habitaciones": sorted(
                    [{"nombre": h.get("nombre"), "area_m2": h.get("area_m2"),
                      "tipo": h.get("tipo")} for h in (v.get("habitaciones") or [])],
                    key=lambda h: (h["nombre"] or "", h["area_m2"] or 0.0),
                ),
                "problemas_vivienda": sorted(v.get("problemas_vivienda") or []),
            }
            for v in (payload.get("viviendas") or [])
        ],
        "issues": {
            "n": len(payload.get("issues") or []),
            "por_severidad": {
                sev: sum(1 for i in (payload.get("issues") or []) if i.get("severity") == sev)
                for sev in ("CRITICO", "IMPORTANTE", "RECOMENDACION")
            },
            "titulos": sorted(
                "%s | %s | %s | %s" % (i.get("severity"), i.get("codigo"),
                                       i.get("unit_name") or "-", i.get("titulo"))
                for i in (payload.get("issues") or [])
            ),
        },
        "proyecto": {
            "tipologia": proyecto.get("tipologia"),
            "zona_cte": proyecto.get("zona_cte"),
            "capa": proyecto.get("capa"),
            "escala": proyecto.get("escala"),
            "planta_declarada": proyecto.get("planta_declarada"),
            "estados_planta": [h.get("estado") for h in (proyecto.get("planta") or [])],
            "ocupacion": sorted(
                [{"ambito": h.get("ambito"), "personas": h.get("personas"),
                  "estado": h.get("estado"), "confianza": h.get("confianza"),
                  "ambito_emitido": h.get("ambito_emitido"),
                  "agregado_no_normativo": h.get("agregado_no_normativo")}
                 for h in (proyecto.get("ocupacion") or [])],
                key=lambda h: h["ambito"] or "",
            ),
            "sectorizacion_veredictos": sorted(
                (h.get("veredicto") or "") for h in (proyecto.get("sectorizacion") or [])
            ),
            "altura_evacuacion_estado": (proyecto.get("altura_evacuacion") or {}).get("estado"),
            "n_avisos_evacuacion": len(proyecto.get("avisos_evacuacion") or []),
        },
    }


def ejecutar_golden() -> int:
    return golden.ejecutar("G6_api_analizar", construir,
                           "POST /api/analizar de extremo a extremo")


if __name__ == "__main__":
    raise SystemExit(ejecutar_golden())
