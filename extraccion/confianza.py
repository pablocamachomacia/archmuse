"""Cálculo determinista de confianza (§3, puntos 5-6 del diseño).

Ninguna función de este módulo llama a un modelo. Es lo que convierte "si la
confianza no es alta, no promover" de una promesa en algo que un test puede
comprobar con datos inventados, sin gastar un token — el mismo argumento que
`normativa/condiciones.py` ya aplicó a la evaluación de condiciones: la
lógica de decisión vive en código puro, revisable y probable aparte de
cualquier llamada externa.

**Regla de la tabla, sin excepción**: cualquier fallo grave (`Señales.fallos_graves()`)
hunde la confianza a Baja, por muchas señales buenas que haya alrededor. No es
un promedio ni una puntuación ponderada — es la misma disciplina de
"mínimo, nunca media" que `docs/brain/EVIDENCE_MODEL.md` §9 ya fija para la
confianza de una Evidence: una sola cifra inventada no se diluye entre diez
campos correctos.
"""
from __future__ import annotations

from typing import Tuple

from .modelo import Señales

NIVELES = ("Alta", "Media", "Baja")


def calcular_confianza(señales: Señales) -> Tuple[str, bool, Tuple[str, ...]]:
    """Devuelve `(nivel_confianza, revisar_manualmente, motivos_revision)`.

    `revisar_manualmente` es mecánico: `True` en cuanto el nivel no es
    "Alta". No hay ningún otro camino para ponerlo a `False` — ni un campo
    que la IA pueda rellenar, ni una excepción manual dentro de esta función.
    """
    graves = señales.fallos_graves()
    menores = señales.fallos_menores()

    if graves:
        nivel = "Baja"
    elif menores:
        nivel = "Media"
    else:
        nivel = "Alta"

    revisar = nivel != "Alta"
    motivos = graves + menores
    return nivel, revisar, motivos
