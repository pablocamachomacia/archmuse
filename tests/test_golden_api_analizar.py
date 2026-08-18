# -*- coding: utf-8 -*-
"""G6 — golden del CONTRATO DE LA API: `POST /api/analizar`.

Ejecutar:  python tests/test_golden_api_analizar.py

Congela lo que ve la SPA: las claves de primer nivel del payload, y por
vivienda su nombre, número de habitaciones, puntuación, valoración y la lista
ordenada de títulos de problema. Es el único golden que recorre el pipeline
entero de extremo a extremo, HTTP incluido.

**Cuatro escenarios, no uno (desde 2026-08-18).** Hasta la Fase 2 este golden
subía el DXF sin `tipologia` ni `ciudad`, así que congelaba **un solo punto**
del espacio de entrada: el de los valores por defecto. Eso dejaba sin red la
corrección del Bug #1 (tarea 5 del `REFACTOR_MASTERPLAN.md`), donde
`/api/analizar` ignoraba la tipología y la zona climática declaradas y
analizaba todo como plurifamiliar en zona C. Con un solo escenario, volver a
romperlo no habría cambiado ni un byte de este fixture.

Los cuatro, y qué vigila cada uno:

| id | Entrada | Qué protege |
|---|---|---|
| `por_defecto` | sin campos | El contrato histórico, byte a byte |
| `unifamiliar_zona_d` | `unifamiliar` + Madrid (zona D) | Que la tipología y la zona **llegan** al motor |
| `rehabilitacion_zona_a` | `rehabilitacion` + Málaga (zona A) | Un segundo punto, con el otro extremo climático |
| `ciudad_no_reconocida` | Cuenca | El repliegue silencioso a zona C, y su aviso |

Los tres primeros salen de la ficha de la tarea 18. El cuarto lo añade la
tarea 6: Cuenca no está en la tabla de zonas climáticas, así que el análisis
usa "C" como **suposición**, y el arquitecto tiene que enterarse.

El bloque `sensibilidad` es la parte legible del golden. En vez de obligar a
comparar tres huellas casi idénticas a ojo, dice directamente en qué difieren
los escenarios respecto al de por defecto. Si alguien vuelve a desconectar la
tipología o la zona del motor, `analisis_identico_al_defecto` se pone a `true`
donde hoy es `false` y el fallo se lee en una línea.

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
- El **texto** de cada limitación: también prosa, y larga. Se congela su
  etiqueta (lo que va antes de los dos puntos), que es lo que identifica de
  qué comprobación habla. Un retoque de redacción no rompe el golden; una
  limitación que aparece o desaparece, sí.

`ARCHMUSE_DATA_DIR` apunta a un temporal desde `tests/golden.py`: este golden
escribe un proyecto en la base de datos por cada escenario, y no puede ser la
de desarrollo (mismo patrón que `tests/test_storage.py`).
"""
from io import BytesIO

import golden

from analyzer import storage

storage.init_db()

import app as app_module  # noqa: E402  (después de fijar ARCHMUSE_DATA_DIR)

CLIENTE = app_module.app.test_client()

# (id, campos del formulario, para qué está)
#
# Las ciudades no son intercambiables: Madrid y Málaga son los dos extremos
# climáticos que la tabla de `normativa/geografia/es/derivados/` cubre (D y A),
# y Cuenca es un municipio que esa tabla NO tiene, que es justo el caso que
# dispara el repliegue. Cambiar cualquiera de las tres cambia lo que este
# golden vigila, no solo sus números.
ESCENARIOS = (
    ("por_defecto", {},
     "sin tipologia ni ciudad: plurifamiliar + zona C, el contrato historico"),
    ("unifamiliar_zona_d", {"tipologia": "unifamiliar", "ciudad": "Madrid"},
     "tipologia y zona climatica declaradas, extremo frio"),
    ("rehabilitacion_zona_a", {"tipologia": "rehabilitacion", "ciudad": "Malaga"},
     "tipologia y zona climatica declaradas, extremo calido"),
    ("ciudad_no_reconocida", {"ciudad": "Cuenca"},
     "municipio fuera de la tabla: zona C por suposicion, no por dato"),
)

DEFECTO = ESCENARIOS[0][0]


def _analizar(campos):
    with open(golden.DXF, "rb") as fh:
        datos = {"dxf": (BytesIO(fh.read()), "ejemplo.dxf")}
    datos.update(campos)
    respuesta = CLIENTE.post("/api/analizar", data=datos,
                             content_type="multipart/form-data")
    if respuesta.status_code != 200:
        raise AssertionError("esperaba 200, obtuvo %d: %s" % (
            respuesta.status_code, respuesta.get_data(as_text=True)[:400]))
    return respuesta.get_json()


def _etiqueta_limitacion(texto):
    """Lo que va antes de los dos puntos: "Altura libre: no evaluable — …"
    -> "Altura libre". Identifica de qué comprobación habla la limitación sin
    congelar su redacción."""
    return (texto or "").split(":", 1)[0].strip()


def _titulos(payload):
    return sorted(
        "%s | %s | %s | %s" % (i.get("severity"), i.get("codigo"),
                               i.get("unit_name") or "-", i.get("titulo"))
        for i in (payload.get("issues") or [])
    )


def _analisis(payload):
    """La parte del payload que depende del MOTOR, no de lo que se declaró.

    Es lo que se compara entre escenarios para saber si la tipología y la zona
    están llegando de verdad a `evaluate_advanced`. Deja fuera `proyecto`, que
    devuelve lo declarado y por tanto difiere siempre, incluso si el motor lo
    ignorase por completo — que es exactamente como el Bug #1 pasó
    desapercibido.
    """
    return {
        "puntuacion_global": payload.get("puntuacion_global"),
        "valoracion_global": payload.get("valoracion_global"),
        "viviendas": [
            {"nombre": v.get("nombre"), "puntuacion": v.get("puntuacion"),
             "valoracion": v.get("valoracion"),
             "problemas_vivienda": sorted(v.get("problemas_vivienda") or [])}
            for v in (payload.get("viviendas") or [])
        ],
        "titulos": _titulos(payload),
    }


def _huella(payload):
    proyecto = payload.get("proyecto") or {}
    limitaciones = payload.get("limitaciones") or []

    return {
        "http": 200,
        "claves_primer_nivel": sorted(payload.keys()),
        "analisis_ia_es_null": payload.get("analisis_ia") is None,
        # Estas dos claves se leían mal (`puntuacion`/`valoracion`, que el
        # payload no tiene), así que el fixture congelaba `null` en los dos
        # números más importantes que devuelve la API: un cambio de 90 a 40 en
        # la puntuación de proyecto no habría roto este golden. Corregido con
        # la Fase 2; es parte de por qué el fixture se recaptura.
        "puntuacion_global": payload.get("puntuacion_global"),
        "valoracion_global": payload.get("valoracion_global"),
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
            "titulos": _titulos(payload),
        },
        # Tarea 6: las limitaciones son el canal de transparencia del proyecto.
        # Se congela cuántas hay y qué comprobaciones nombran, no su prosa.
        "limitaciones": {
            "n": len(limitaciones),
            "etiquetas": sorted({_etiqueta_limitacion(l) for l in limitaciones}),
        },
        "proyecto": {
            "tipologia": proyecto.get("tipologia"),
            "ciudad": proyecto.get("ciudad"),
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


def _sensibilidad(payloads):
    """Qué cambia, y qué no, al declarar tipología y ciudad.

    Este bloque no aporta información que no esté ya en `escenarios` — la
    aporta *legible*. Un diff de tres huellas de 3.000 líneas no dice "la
    tipología ha dejado de importar"; estas cuatro claves sí.
    """
    base = _analisis(payloads[DEFECTO])
    titulos_base = set(base["titulos"])

    otros = [nombre for nombre, _, _ in ESCENARIOS if nombre != DEFECTO]

    return {
        "tipologia": {n: (payloads[n].get("proyecto") or {}).get("tipologia")
                      for n, _, _ in ESCENARIOS},
        "zona_cte": {n: (payloads[n].get("proyecto") or {}).get("zona_cte")
                     for n, _, _ in ESCENARIOS},
        "puntuacion_global": {n: payloads[n].get("puntuacion_global")
                              for n, _, _ in ESCENARIOS},
        # El canario del Bug #1. Hoy es `false` para los dos escenarios que
        # declaran tipología y zona: el motor los trata distinto. Si alguna vez
        # se pone a `true`, la declaración ha vuelto a caer en saco roto.
        # `ciudad_no_reconocida` es `true` A PROPÓSITO: repliega a los mismos
        # valores que el escenario por defecto, así que debe analizar igual.
        "analisis_identico_al_defecto": {
            n: _analisis(payloads[n]) == base for n in otros
        },
        "titulos_solo_en_este": {
            n: sorted(set(_titulos(payloads[n])) - titulos_base) for n in otros
        },
        "titulos_que_faltan_frente_al_defecto": {
            n: sorted(titulos_base - set(_titulos(payloads[n]))) for n in otros
        },
    }


def construir():
    payloads = {nombre: _analizar(campos) for nombre, campos, _ in ESCENARIOS}

    return {
        "n_escenarios": len(ESCENARIOS),
        "entradas": {nombre: {"campos": campos, "para_que": para_que}
                     for nombre, campos, para_que in ESCENARIOS},
        "escenarios": {nombre: _huella(payloads[nombre])
                       for nombre, _, _ in ESCENARIOS},
        "sensibilidad": _sensibilidad(payloads),
    }


def ejecutar_golden() -> int:
    return golden.ejecutar("G6_api_analizar", construir,
                           "POST /api/analizar de extremo a extremo, 4 escenarios")


if __name__ == "__main__":
    raise SystemExit(ejecutar_golden())
