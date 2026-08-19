# -*- coding: utf-8 -*-
"""TL-8 — fuera Nominatim, y Overpass caído degrada en vez de romper.

Ejecutar:  pytest tests/test_geocodificacion_y_overpass.py

**Por qué esto es una tarea y no una manía.** La política de uso de la
instancia pública de Nominatim prohíbe el uso comercial. Mientras ArchMuse fue
una demostración, llamarla era discutible; el día que se cobra es un
incumplimiento, y el modo de fallo es un bloqueo por IP sin aviso previo — o
sea, el buscador de parcelas dejando de funcionar para todos los clientes a la
vez, sin nada que tocar para arreglarlo. Se sustituye **antes** de cobrar.

Las dos propiedades que se fijan aquí:

1. **Ninguna llamada del producto va a `nominatim.openstreetmap.org`.** No se
   comprueba «el geocodificador funciona» —eso lo hace `tests/test_sitio.py`—
   sino que el dominio prohibido no reaparezca por ninguna puerta: ni una
   URL nueva, ni un repliegue «temporal» cuando falte el token.
2. **Overpass caído degrada con mensaje.** Los cuatro espejos fallando
   producen `errores` poblados y `entorno_consultado: False`, nunca una
   excepción que tumbe el análisis ni —peor— un entorno vacío cacheado como si
   fuera un hecho («aquí no hay colindantes»), que es el bug que ya se vivió
   en producción el 17 de agosto.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest import mock

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from analyzer import sitio  # noqa: E402

#: Dónde se busca el dominio prohibido. Código de producto, no documentación:
#: un `docs/` que explique por qué se retiró Nominatim tiene que poder
#: nombrarlo.
FUENTES = tuple(
    p for patron in ("*.py", "*.js")
    for p in list((RAIZ / "analyzer").rglob(patron))
    + list((RAIZ / "static").rglob(patron))
    + list((RAIZ / "agente").rglob(patron))
    + [RAIZ / "app.py"]
)

#: Sólo la llamada, no la palabra: el comentario que documenta de dónde salió
#: un dato consultado una vez en 2026 es procedencia, y borrarlo empeoraría el
#: repositorio.
LLAMADA_PROHIBIDA = re.compile(r"nominatim\.openstreetmap\.org")


def test_ningun_fichero_de_producto_llama_a_nominatim():
    culpables = [
        str(p.relative_to(RAIZ))
        for p in FUENTES
        if p.is_file() and LLAMADA_PROHIBIDA.search(p.read_text(encoding="utf-8"))
    ]
    assert culpables == [], (
        "la instancia pública de Nominatim prohíbe el uso comercial; estos ficheros "
        "la llaman: %s" % culpables
    )


def test_sin_token_no_hay_repliegue_a_nominatim(monkeypatch):
    """El atajo que esta tarea existe para impedir.

    Un repliegue «mientras tanto» a un servicio que no se puede usar
    comercialmente es exactamente la clase de decisión que sobrevive tres años
    y se descubre con clientes dentro.
    """
    monkeypatch.delenv("MAPBOX_TOKEN", raising=False)
    with mock.patch("analyzer.sitio._get", side_effect=AssertionError("no se llama a nadie")):
        with pytest.raises(sitio.GeocodificacionNoConfigurada):
            sitio.geocodificar_direccion("Gran Vía 31 Madrid")


def test_el_error_de_falta_de_configuracion_se_distingue_de_un_fallo_de_red():
    """Son dos conversaciones distintas con el arquitecto: «vuelve a
    intentarlo» y «esto no está montado aquí»."""
    assert issubclass(sitio.GeocodificacionNoConfigurada, sitio.ErrorDeSitio)
    assert sitio.GeocodificacionNoConfigurada is not sitio.ErrorDeSitio


def test_la_url_del_geocodificador_es_de_mapbox():
    assert "api.mapbox.com" in sitio._URL_MAPBOX_GEOCODING


# --- Overpass ---------------------------------------------------------------

def test_con_todos_los_espejos_caidos_el_entorno_degrada_con_mensaje(monkeypatch):
    """EL BUG DEL 17 DE AGOSTO, cerrado con un test.

    Con Overpass degradado, el análisis tiene que seguir y decir qué falta. Lo
    que no puede pasar es que el hueco se dé por bueno: `entorno_consultado`
    en `False` es lo que hace que la próxima vez se reintente en vez de servir
    para siempre un «aquí no hay colindantes» que nadie midió.
    """
    monkeypatch.setattr(sitio, "_OVERPASS_ESPERA_ENTRE_ESPEJOS_S", 0)
    monkeypatch.setattr(sitio, "_post_overpass",
                        mock.Mock(side_effect=sitio.ErrorDeSitio("Overpass: los espejos fallaron")))

    datos = sitio.entorno_overpass_por_coordenadas(40.42, -3.70)

    assert datos["entorno_consultado"] is False
    assert datos["errores"], "un fallo total tiene que dejar rastro legible"
    assert all("Overpass" in e for e in datos["errores"])


def test_una_consulta_caida_no_arrastra_a_las_demas(monkeypatch):
    """Las cuatro consultas son independientes: que falle la de equipamientos
    no puede borrar los colindantes que sí se obtuvieron."""
    monkeypatch.setattr(sitio, "_colindantes_overpass", lambda *a, **k: [{"nombre": "vecino"}])
    monkeypatch.setattr(sitio, "_viales_overpass", lambda *a, **k: [])
    monkeypatch.setattr(sitio, "_zonas_verdes_overpass", lambda *a, **k: [])

    def revienta(*_a, **_k):
        raise sitio.ErrorDeSitio("Overpass: equipamientos fuera de servicio")

    monkeypatch.setattr(sitio, "_equipamientos_overpass", revienta)

    datos = sitio.entorno_overpass_por_coordenadas(40.42, -3.70)

    assert datos["colindantes"] == [{"nombre": "vecino"}]
    assert any("equipamientos" in e for e in datos["errores"])
    assert datos["entorno_consultado"] is False


def test_hay_mas_de_un_espejo_de_overpass():
    """Un solo host es un punto único de fallo para el visor de entorno, y ya
    se midió en vivo: 126 s hasta rendirse."""
    assert len(sitio._URLS_OVERPASS) >= 2
    assert len(set(sitio._URLS_OVERPASS)) == len(sitio._URLS_OVERPASS)
