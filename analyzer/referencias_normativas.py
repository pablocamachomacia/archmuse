"""Referencia normativa orientativa por código interno de incidencia.

MÓDULO DE TRANSICIÓN. Esta tabla vivía en `static/app.js` (`NORMATIVA_REF`),
donde el navegador afirmaba a qué norma pertenecía cada incidencia sin que el
backend le hubiera enviado esa información. Se ha traído al servidor porque el
frontend es capa de presentación: no decide, ni afirma, contenido normativo.

Qué es y qué NO es:

- Los códigos (`CTE-DB-SUA-1`, `HABITABILIDAD-SUP`, ...) son una convención
  interna de ArchMuse, NO la numeración oficial de apartados de ningún
  Documento Básico. `CTE-DB-SUA-1` no significa "DB-SUA sección 1".
- El texto asociado apunta al documento más afín para que sirva de punto de
  partida al consultar el texto legal. **No es una cita legal certificada**:
  no lleva boletín, ni artículo, ni fecha de vigencia, ni ha sido validada por
  un arquitecto colegiado contra el texto de la norma.
- `docs/audits/NORMATIVE_AUDIT.md` §6.2 documenta 5 discrepancias entre el
  código emitido y la materia que regula ese DB. Traer la tabla aquí no las
  corrige; solo deja de fingir que las decide el navegador.

Sustituto definitivo: el corpus normativo versionado de
`docs/design/NORMATIVE_ENGINE.md` (NormaFuente con boletín, artículo y
vigencia) resuelto territorialmente según `docs/design/NORMATIVE_RESOLUTION.md`.
Cuando la Fase 4 de ese plan transcriba las reglas con su cita real, este
módulo se borra entero. Hasta entonces, `AVISO` acompaña siempre a la tabla
para que ninguna capa superior la presente como algo que no es.
"""
from __future__ import annotations

AVISO = (
    "Referencia orientativa al documento más afín, no una cita legal "
    "certificada: sin artículo, boletín ni fecha de vigencia verificados."
)

REFERENCIA_GENERICA = "Sin referencia normativa directa — criterio de diseño"

REFERENCIAS = {
    "CTE-DB-SUA": "CTE DB-SUA 9 (Accesibilidad) — anchura y pendiente de itinerario",
    "CTE-DB-SUA-1": "CTE DB-SUA 9 (Accesibilidad) — baño accesible / altura libre",
    "CTE-DB-SUA-2-ITIN": "CTE DB-SUA 9 (Accesibilidad) — itinerario accesible ≥1.20m",
    "CTE-DB-SI-3": "CTE DB-SI 3 — evacuación de ocupantes",
    "CTE-DB-HS": "CTE DB-HS 3 — ventilación e iluminación de estancias habitables",
    "CTE-DB-HS3": "CTE DB-HS 3 — caracterización y cuantificación de la ventilación",
    "CTE-DB-HE": "CTE DB-HE 1 — condensaciones y transmitancia térmica",
    "CTE-DB-HE-COND": "CTE DB-HE 1 — control de condensaciones superficiales",
    "CTE-DB-HE-ORIENT": "CTE DB-HE 1 — demanda energética y orientación de huecos",
    "CTE-DB-HR": "CTE DB-HR — aislamiento acústico a ruido aéreo y de impacto",
    "HABITABILIDAD": "Normativa autonómica de habitabilidad — proporción y dimensiones mínimas de pieza",
    "HABITABILIDAD-SUP": "Normativa autonómica de habitabilidad — superficie mínima de dormitorio",
    "HABITABILIDAD-CIRC": "Normativa autonómica de habitabilidad — privacidad e independencia de piezas húmedas",
    "EFICIENCIA": "Criterio de eficiencia proyectual — sin referencia normativa directa",
    "EFICIENCIA-ENE": "CTE DB-HE 0 — limitación del consumo energético (orientación y compacidad)",
    "URBANISMO-OC": "Planeamiento urbanístico municipal — ocupación máxima de parcela",
    "URBANISMO-ED": "Planeamiento urbanístico municipal — edificabilidad máxima",
    "URBANISMO-AL": "Planeamiento urbanístico municipal — altura máxima reguladora",
    "URBANISMO-RETR": "Planeamiento urbanístico municipal — retranqueos mínimos a linderos",
}


def referencia(codigo: str) -> str:
    """Texto orientativo para `codigo`, o `REFERENCIA_GENERICA` si no está
    mapeado. Nunca devuelve None ni cadena vacía: la interfaz muestra siempre
    algo, y ese algo nunca es una cita legal (ver `AVISO`)."""
    return REFERENCIAS.get(codigo or "", REFERENCIA_GENERICA)
