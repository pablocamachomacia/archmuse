# -*- coding: utf-8 -*-
"""`_convHallazgosDesdeDatos` y el titular de `convTarjetaHallazgo` para
`revision.coherencia_del_plano` (Bloque 1, 2026-08-20).

Ejecutar:  pytest tests/test_conversacion_hallazgos_coherencia.py

**El bug que este fichero existe para no dejar volver.** Los hallazgos de
coherencia viven en "Qué se ha establecido" (`revision.hallazgos`, un
`calculo()`), no en "Qué no se ha comprobado" como el "sin total" de
medición (`sin_producir()`). `comprobadas.length` -- la señal que
`convTarjetaHallazgo` ya usaba para decidir si titular "Hallazgo" -- sale
siempre 0 para coherencia, así que sin `_convHallazgosDesdeDatos` un plano
con solapes reales se titularía "Sin incidencias". Mismo criterio que el
resto de guardianes estáticos de `static/app.js` en esta sesión: ejecuta la
función real en Node, no la reimplementa en Python.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
JS = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")

_INICIO = "function _convHallazgosDesdeDatos(datos) {"
_FIN = "\n  }\n\n  // Tarjeta de un hallazgo real"


def _extraer_funcion_pura() -> str:
    inicio = JS.index(_INICIO)
    fin = JS.index(_FIN, inicio)
    return JS[inicio:fin + len("\n  }")]


FUNCION_JS = _extraer_funcion_pura()


def _ejecutar(datos):
    programa = FUNCION_JS + "\nconsole.log(JSON.stringify(_convHallazgosDesdeDatos(%s)));" % json.dumps(datos)
    resultado = subprocess.run(
        ["node", "-e", programa],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert resultado.returncode == 0, "node falló: %s" % resultado.stderr
    return json.loads(resultado.stdout)


def test_sin_datos_no_hay_hallazgo():
    assert _ejecutar([]) is None


def test_un_dato_sin_el_prefijo_de_hallazgos_no_cuenta():
    assert _ejecutar(["4 recinto(s) leído(s) en el plano."]) is None


def test_cero_hallazgos_no_se_titula_como_hallazgo():
    """El propio formateador de Python dice "No se ha encontrado ningún
    hallazgo..." cuando la lista está vacía -- nunca "0 hallazgo(s):", pero
    esta función se defiende igual si algún día lo hiciera."""
    assert _ejecutar(["0 hallazgo(s): .", "No se ha encontrado ningún hallazgo en esta revisión."]) is None


def test_un_hallazgo_real_se_detecta_con_su_texto_completo():
    dato = "1 hallazgo(s): solape_entre_recintos en Salon+Terraza 2.00 m2."
    resultado = _ejecutar(["4 recinto(s) leído(s) en el plano.", dato])
    assert resultado == {"n": 1, "texto": dato}


def test_varios_hallazgos_devuelve_el_recuento_correcto():
    dato = "3 hallazgo(s): solape en A+B; rótulo repetido en C; contorno cerrado por suposición en D."
    assert _ejecutar([dato])["n"] == 3


def test_convtarjetahallazgo_usa_hallazgosdatos_cuando_no_hay_caso_conocido():
    """`convTarjetaHallazgo` depende de `DOMParser` (API de navegador, sin
    polyfill en este repo -- `_convParsearActa` es justo la función que la
    usa), así que este test es de fuente, no de ejecución en Node, mismo
    criterio que `tests/test_conversacion_memoria_superficies.py` para
    funciones que tocan el DOM. Comprueba la forma del código, no lo
    reimplementa: la rama `else if (hallazgosDatos)` existe, va ANTES de la
    rama "Sin incidencias", y titula con `conv-badge-hallazgo`."""
    inicio = JS.index("function convTarjetaHallazgo(capacidad, htmlActa) {")
    fin = JS.index("\n  // Reenvía el MISMO", inicio)
    cuerpo = JS[inicio:fin]

    pos_comprobadas = cuerpo.index("if (comprobadas.length) {")
    pos_hallazgos_datos = cuerpo.index("else if (hallazgosDatos) {")
    pos_sin_incidencias = cuerpo.index("Sin incidencias")
    assert pos_comprobadas < pos_hallazgos_datos < pos_sin_incidencias
    assert "conv-badge-hallazgo" in cuerpo[pos_hallazgos_datos:pos_sin_incidencias]

    # Bloque 2: el límite de normativa, visible en el propio resultado --
    # construido y concatenado ANTES del `<details>` de la traza completa
    # (`conv-detalle`), no dentro ni después de él.
    assert "conv-aviso-normativa" in cuerpo
    pos_aviso = cuerpo.index("conv-aviso-normativa")
    pos_return = cuerpo.index("return '<div class=\"conv-tarjeta\">'")
    pos_avisonormativa_en_return = cuerpo.index("avisoNormativa", pos_return)
    pos_detalle_en_return = cuerpo.index("conv-detalle", pos_return)
    assert pos_aviso < pos_return
    assert pos_avisonormativa_en_return < pos_detalle_en_return

    # Bloque 1: el botón de memoria sólo para medición -- no incondicional.
    pos_boton = cuerpo.index("var botonMemoria =")
    fin_boton = cuerpo.index(";", cuerpo.index("conv-btn-memoria", pos_boton))
    assert 'capacidad === "superficies.medicion_de_planta"' in cuerpo[pos_boton:fin_boton]


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
