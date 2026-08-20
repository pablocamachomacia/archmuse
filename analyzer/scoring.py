"""Sistema de puntuación desglosado y accionable — ADITIVO al existente
(`evaluator.UnitScore.score_pct`/`score_rating`, que se mantiene intacto en
paralelo, sin tocar). Este módulo no recalcula ningún resultado ni vuelve a
detectar problemas: parte de los `IssueReport` que ya construye
`evaluator.classify_problems` (Bloque 12) y los reinterpreta en 3 capas:

1. `compute_scoring_breakdown` — reparte esos issues en 6 categorías fijas
   con peso propio (`CATEGORY_WEIGHTS`), cada una puntuada de 100 hacia
   abajo según la severidad de sus issues, y suma ponderada como
   puntuación total. La categoría de un issue se deriva de su propio
   `codigo` (prefijo/fragmento), de más específico a más genérico — mismo
   criterio de "prioridad: específico antes que el cajón de sastre" que ya
   usa `disciplinaFor` en el frontend (`static/index.html`) para agrupar
   por disciplina el panel de "Problemas detectados", adaptado aquí a las
   6 categorías de puntuación (distintas de las 6 disciplinas de ese
   panel: aquello agrupa para FILTRAR, esto para PUNTUAR con pesos).
2. `compute_puntos_ganados` — para cada issue, cuánto subiría la
   puntuación total si se corrigiera solo ese (y ningún otro). Se recalcula
   el desglose completo sin ese issue en vez de restar su deducción a
   mano, porque el suelo en 0 de cada categoría puede hacer que la
   ganancia real sea menor que la deducción nominal si esa categoría ya
   estaba saturada por otros issues de la misma categoría.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .evaluator import IssueReport, score_rating

# ---------------------------------------------------------------------------
# 1. Puntuación desglosada por categoría
# ---------------------------------------------------------------------------

# Los pesos suman 1.0 exactamente — `compute_scoring_breakdown` no los
# normaliza, así que si se retocan aquí deben seguir sumando 1.0.
CATEGORY_WEIGHTS: Dict[str, float] = {
    "Normativa CTE": 0.25,
    "Habitabilidad y confort": 0.20,
    "Accesibilidad": 0.15,
    "Eficiencia espacial": 0.15,
    "Iluminación y ventilación": 0.15,
    "Seguridad contra incendios": 0.10,
}

DEDUCTION_BY_SEVERITY: Dict[str, float] = {
    "CRITICO": 15.0,
    "IMPORTANTE": 7.0,
    "RECOMENDACION": 2.0,
}


def categoria_for(issue: IssueReport) -> str:
    """Categoría de puntuación de `issue` según su `codigo` — de más
    específico a más genérico, para que un código como "CTE-DB-SUA-2-ITIN"
    caiga en Accesibilidad y no en el cajón de sastre "Normativa CTE" antes
    de llegar a la regla que sí lo distingue:

    - "-SI-"/"INCENDIO" en el código → Seguridad contra incendios
      (CTE-DB-SI-3: evacuación).
    - Prefijo "CTE-DB-SUA" (cualquier variante) → Accesibilidad — el
      Documento Básico SUA es "Seguridad de Utilización y Accesibilidad".
    - Prefijo "CTE-DB-HS" → Iluminación y ventilación (Salubridad: cruzada,
      factor de luz natural, huecos 1/8, profundidad de habitación...).
    - Cualquier otro "CTE-DB-*" (HE, HE-COND, HE-ORIENT, HR) → Normativa
      CTE, como cajón de sastre CTE genérico.
    - Prefijo "EFICIENCIA" (incl. "EFICIENCIA-ENE") → Eficiencia espacial.
    - Cualquier otro código (HABITABILIDAD*, URBANISMO*...) → Habitabilidad
      y confort, cajón de sastre final.
    """
    codigo = (issue.codigo or "").upper()
    if "-SI-" in codigo or "INCENDIO" in codigo:
        return "Seguridad contra incendios"
    if codigo.startswith("CTE-DB-SUA"):
        return "Accesibilidad"
    if codigo.startswith("CTE-DB-HS"):
        return "Iluminación y ventilación"
    if codigo.startswith("CTE-DB"):
        return "Normativa CTE"
    if codigo.startswith("EFICIENCIA"):
        return "Eficiencia espacial"
    return "Habitabilidad y confort"


@dataclass
class CategoryScore:
    nombre: str
    peso: float
    puntuacion: float  # 0-100, ya con el suelo en 0 aplicado


@dataclass
class ScoringBreakdown:
    categorias: List[CategoryScore] = field(default_factory=list)
    puntuacion_total: float = 100.0
    valoracion: str = "verde"


def compute_scoring_breakdown(issues: List[IssueReport]) -> ScoringBreakdown:
    """Cada categoría arranca en 100 y resta `DEDUCTION_BY_SEVERITY` por
    cada issue de esa categoría (sin bajar de 0); la puntuación total es la
    suma ponderada por `CATEGORY_WEIGHTS`. Issues cuyo `codigo` no se
    reconoce (no debería pasar con los códigos actuales de `evaluator.py`/
    `chain_effects.py`) caen en "Habitabilidad y confort" vía el cajón de
    sastre de `categoria_for`, nunca se pierden silenciosamente."""
    deducciones = dict.fromkeys(CATEGORY_WEIGHTS, 0.0)
    for issue in issues:
        deducciones[categoria_for(issue)] += DEDUCTION_BY_SEVERITY.get(issue.severity, 0.0)

    categorias: List[CategoryScore] = []
    total = 0.0
    for nombre, peso in CATEGORY_WEIGHTS.items():
        puntuacion = max(0.0, 100.0 - deducciones[nombre])
        categorias.append(CategoryScore(nombre=nombre, peso=peso, puntuacion=round(puntuacion, 1)))
        total += puntuacion * peso

    return ScoringBreakdown(categorias=categorias, puntuacion_total=round(total, 1), valoracion=score_rating(total))


def compute_project_breakdown(issues: List[IssueReport], unit_names: List[str]) -> ScoringBreakdown:
    """Desglose de un proyecto entero, agregando por vivienda.

    `compute_scoring_breakdown` arranca cada categoría en 100 y resta. Pasarle
    de golpe los issues de todas las viviendas aplica **un solo techo de 100
    puntos a los problemas de todas**: seis viviendas con dos incidencias de
    la misma categoría cada una hunden esa categoría igual que una sola
    vivienda con doce. El resultado es que un proyecto puntúa peor cuanto más
    grande es, aunque cada vivienda por separado esté bien.

    No es una diferencia menor. Medido sobre `ejemplo.dxf`: el desglose global
    daba 69,7 («rojo») mientras la media de las seis viviendas era 93,8
    («verde»), y la categoría «Iluminación y ventilación» salía a 0,0 sin que
    ninguna vivienda la tuviera a 0.

    Aquí cada vivienda se puntúa por separado y después se promedia por
    categoría. Los problemas de edificio —los que no pertenecen a ninguna
    vivienda: ocupación del solar, edificabilidad, altura— se restan **una
    sola vez** sobre el promedio, porque afectan al proyecto una vez, no una
    por vivienda.
    """
    if not unit_names:
        return compute_scoring_breakdown(issues)

    de_vivienda = {nombre: [] for nombre in unit_names}
    de_edificio: List[IssueReport] = []
    for issue in issues:
        if issue.unit_name in de_vivienda:
            de_vivienda[issue.unit_name].append(issue)
        else:
            de_edificio.append(issue)

    por_vivienda = [compute_scoring_breakdown(de_vivienda[n]) for n in unit_names]
    deduccion_edificio = dict.fromkeys(CATEGORY_WEIGHTS, 0.0)
    for issue in de_edificio:
        deduccion_edificio[categoria_for(issue)] += DEDUCTION_BY_SEVERITY.get(issue.severity, 0.0)

    categorias: List[CategoryScore] = []
    total = 0.0
    for indice, (nombre, peso) in enumerate(CATEGORY_WEIGHTS.items()):
        media = sum(b.categorias[indice].puntuacion for b in por_vivienda) / len(por_vivienda)
        puntuacion = max(0.0, media - deduccion_edificio[nombre])
        categorias.append(CategoryScore(nombre=nombre, peso=peso, puntuacion=round(puntuacion, 1)))
        total += puntuacion * peso

    return ScoringBreakdown(
        categorias=categorias, puntuacion_total=round(total, 1), valoracion=score_rating(total))


def serialize_breakdown(breakdown: ScoringBreakdown) -> dict:
    return {
        "categorias": [
            {"nombre": c.nombre, "peso": c.peso, "puntuacion": c.puntuacion} for c in breakdown.categorias
        ],
        "puntuacion_total": breakdown.puntuacion_total,
        "valoracion": breakdown.valoracion,
    }


# ---------------------------------------------------------------------------
# 2. Potencial de mejora por issue
# ---------------------------------------------------------------------------


def compute_puntos_ganados(issues: List[IssueReport]) -> None:
    """Rellena `IssueReport.puntos_ganados` de cada issue de `issues` in
    place: la diferencia entre `puntuacion_total` sin ese issue y con él.
    O(n²) en el número de issues (recalcula el desglose completo por cada
    uno) — asumible porque un proyecto real tiene decenas de issues, no
    miles."""
    if not issues:
        return
    referencia = compute_scoring_breakdown(issues).puntuacion_total
    for i, issue in enumerate(issues):
        resto = issues[:i] + issues[i + 1:]
        total_sin_este = compute_scoring_breakdown(resto).puntuacion_total
        issue.puntos_ganados = round(total_sin_este - referencia, 1)
