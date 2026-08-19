# -*- coding: utf-8 -*-
"""El botón "Descargar apartado de superficies" del panel de conversación
(MJ-4). Sesión 2026-08-19, noche 11.

Ejecutar:  pytest tests/test_conversacion_memoria_superficies.py

Mismo criterio que el resto de los guardianes estáticos de `static/app.js`
en esta sesión: lee el fuente, no renderiza la página.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
JS = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")


def test_el_boton_solo_aparece_cuando_hay_datos_reales():
    """El botón nunca es incondicional: sólo se ofrece si el acta trajo
    algo que documentar (`parsed.datos.length`), mismo criterio que
    `ActaSinDatos` en `analyzer/memoria_justificativa.py`."""
    inicio = JS.index("function convTarjetaHallazgo(capacidad, htmlActa) {")
    fin = JS.index("function convDescargarMemoria(archivo, boton) {", inicio)
    cuerpo = JS[inicio:fin]
    assert "data-descargar-memoria" in cuerpo
    assert "parsed.datos.length" in cuerpo


def test_descargar_memoria_llama_al_endpoint_real():
    inicio = JS.index("function convDescargarMemoria(archivo, boton) {")
    fin = JS.index("\n  }", inicio)
    cuerpo = JS[inicio:fin]
    assert '"/api/memoria-superficies"' in cuerpo
    assert 'formData.append("dxf", archivo)' in cuerpo
    # Descarga por blob, mismo patrón que `descargarPdf()` -- nunca
    # `document.write` ni HTML en crudo con el nombre del fichero sin escapar.
    assert "URL.createObjectURL(blob)" in cuerpo
    assert "URL.revokeObjectURL(url)" in cuerpo


def test_el_archivo_de_la_descarga_es_el_de_esta_medicion_no_el_actual():
    """El bug que este test evita: si el arquitecto adjunta un plano
    distinto entre ver la respuesta y pulsar "Descargar", la memoria tiene
    que seguir siendo la del plano que se midió, no
    `convState.archivoAdjunto` en el momento del clic."""
    inicio = JS.index('var botonMemoria = nodo && nodo.querySelector("[data-descargar-memoria]")')
    fin = JS.index("\n        }\n      })", inicio)
    cuerpo = JS[inicio:fin]
    assert "convDescargarMemoria(archivo, botonMemoria)" in cuerpo
    # Sin comentarios: el propio comentario de este bloque MENCIONA
    # `convState.archivoAdjunto` para explicar por qué no se usa -- lo que
    # importa es que no aparezca en código real, no en la explicación.
    cuerpo_sin_comentarios = re.sub(r"//[^\n]*", "", cuerpo)
    assert "convState.archivoAdjunto" not in cuerpo_sin_comentarios


if __name__ == "__main__":  # pragma: no cover
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
