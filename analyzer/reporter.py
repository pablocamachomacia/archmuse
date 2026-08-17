"""Generación de informes: consola y HTML.

`print_report` / `print_advanced_report` escriben en consola. `write_html_report`
genera un informe HTML autocontenido (sin dependencias externas) con tabla
resumen de viviendas, detalle por vivienda y resumen ejecutivo con colores.
"""
from __future__ import annotations

import datetime
import html as html_lib
from pathlib import Path
from typing import List, Optional

from .ai_analyst import AIAnalysis
from .evaluator import AdvancedAnalysis, RuleResult, UnitScore, score_rating
from .parser import Room
from .plan_svg import render_plan_section


def print_report(rooms: List[Room], results: List[RuleResult]) -> None:
    print("=" * 60)
    print("INFORME DE HABITACIONES DETECTADAS")
    print("=" * 60)

    if not rooms:
        print("No se detectaron habitaciones (polilíneas cerradas) en el layer indicado.")
    else:
        for i, room in enumerate(rooms, start=1):
            label = room.label or "(sin etiqueta asociada)"
            print(f"{i:>2}. {label:<25} {room.area_m2:>8.2f} m²")

    print()
    print("=" * 60)
    print("PROBLEMAS DE CALIDAD DETECTADOS")
    print("=" * 60)

    problems = [r for r in results if not r.passed]
    if not problems:
        print("No se han detectado incumplimientos de las reglas configuradas.")
    else:
        for problem in problems:
            print(f"  x {problem.message}")

    print()
    print(f"Total habitaciones: {len(rooms)}")
    print(f"Reglas evaluadas:   {len(results)}")
    print(f"Problemas:          {len(problems)}")
    print("=" * 60)


def print_advanced_report(analysis: AdvancedAnalysis) -> None:
    """Imprime el análisis avanzado: viviendas, proporciones, jerarquía,
    eficiencia, orientación y puntuación por vivienda."""
    print()
    print("=" * 60)
    print("VIVIENDAS DETECTADAS")
    print("=" * 60)
    for u in analysis.units:
        labels = ", ".join(r.label or "(sin etiqueta)" for r in u.rooms)
        print(f"{u.name} ({len(u.rooms)} habitaciones, {u.total_area_m2:.2f} m²): {labels}")

    print()
    print("=" * 60)
    print("1. PROPORCIONES DE HABITACIONES (máximo 1:2.5)")
    print("=" * 60)
    tubo_rooms = [p for p in analysis.proportions if not p.passed]
    if not tubo_rooms:
        print("Ninguna habitación supera la proporción máxima permitida.")
    else:
        for p in tubo_rooms:
            print(f"  x {p.message}")
    print(f"Habitaciones evaluadas: {len(analysis.proportions)}  |  problemas: {len(tubo_rooms)}")

    print()
    print("=" * 60)
    print("2. JERARQUÍA DE DORMITORIOS (Dormitorio 1 > 2 > 3, por vivienda)")
    print("=" * 60)
    if not analysis.hierarchy:
        print("No hay suficientes dormitorios etiquetados en la misma vivienda para comparar.")
    else:
        for h in analysis.hierarchy:
            marker = " " if h.passed else "x"
            print(f"  {marker} {h.message}")
    hierarchy_problems = [h for h in analysis.hierarchy if not h.passed]
    print(f"Comparaciones evaluadas: {len(analysis.hierarchy)}  |  problemas: {len(hierarchy_problems)}")

    print()
    print("=" * 60)
    print("3. EFICIENCIA DE LA VIVIENDA (útil/total >= 80%)")
    print("=" * 60)
    if not analysis.efficiency:
        print("No se pudo calcular la eficiencia de ninguna vivienda.")
    else:
        for e in analysis.efficiency:
            marker = " " if e.passed else "x"
            print(f"  {marker} {e.message}")
    efficiency_problems = [e for e in analysis.efficiency if not e.passed]

    print()
    print("=" * 60)
    print("4. ORIENTACIÓN SOLAR")
    print("=" * 60)
    penalized_orientation = [o for o in analysis.orientation if o.rating == "penalizada"]
    if not analysis.orientation:
        print("No se pudo calcular la orientación de ninguna habitación.")
    else:
        for o in analysis.orientation:
            marker = "x" if o.rating == "penalizada" else " "
            print(f"  {marker} {o.message}")
    print(
        f"Habitaciones evaluadas: {len(analysis.orientation)}  |  "
        f"penalizadas: {len(penalized_orientation)}"
    )

    print()
    print("=" * 60)
    print("PUNTUACIÓN POR VIVIENDA")
    print("=" * 60)
    for u in analysis.unit_scores:
        print(
            f"  {u.unit.name}: {u.score_pct:.0f}% "
            f"({u.passed_checks}/{u.total_checks} comprobaciones) — {u.rating.upper()}"
        )

    print()
    print("=" * 60)
    print("RESUMEN ANÁLISIS AVANZADO")
    print("=" * 60)
    print(f"Viviendas detectadas:       {len(analysis.units)}")
    print(f"Habitaciones 'tubo':        {len(tubo_rooms)}")
    print(f"Incumplimientos jerarquía:  {len(hierarchy_problems)}")
    print(f"Viviendas bajo eficiencia:  {len(efficiency_problems)}")
    print(f"Orientaciones penalizadas:  {len(penalized_orientation)}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Informe HTML
# ---------------------------------------------------------------------------

_CSS = """
:root {
  color-scheme: light dark;
  --bg: #f7f7f9;
  --fg: #1a1a1a;
  --card-bg: #ffffff;
  --border: #e0e0e5;
  --muted: #6b7280;
  --green: #1a7f37;
  --green-bg: #d9f2e3;
  --yellow: #9a6700;
  --yellow-bg: #fff3cd;
  --red: #b42318;
  --red-bg: #fde2e1;
  --neutral: #4b5563;
  --neutral-bg: #e5e7eb;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14161a;
    --fg: #e6e6e6;
    --card-bg: #1e2126;
    --border: #2d3038;
    --muted: #9aa0a6;
    --green-bg: #0f3d24;
    --yellow-bg: #4a3a05;
    --red-bg: #4a1512;
    --neutral-bg: #2d3038;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 2rem;
  background: var(--bg); color: var(--fg);
  font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  line-height: 1.5;
}
header h1 { margin-bottom: 0.25rem; }
.meta { color: var(--muted); margin-top: 0; }
.summary { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1.5rem 0 2rem; }
.card {
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 10px; padding: 1rem 1.5rem; min-width: 160px;
}
.card-label { color: var(--muted); font-size: 0.85rem; }
.card-value { font-size: 1.8rem; font-weight: 600; margin-top: 0.25rem; }
section { margin-bottom: 2rem; }
h2 { border-bottom: 1px solid var(--border); padding-bottom: 0.4rem; }
.unit-detail {
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 10px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem;
}
table { border-collapse: collapse; width: 100%; margin: 0.5rem 0 1.25rem; display: block; overflow-x: auto; }
th, td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid var(--border); white-space: nowrap; }
th { color: var(--muted); font-weight: 600; font-size: 0.85rem; }
.badge {
  display: inline-block; padding: 0.15rem 0.6rem; border-radius: 999px;
  font-size: 0.8rem; font-weight: 600;
}
.badge-green { color: var(--green); background: var(--green-bg); }
.badge-yellow { color: var(--yellow); background: var(--yellow-bg); }
.badge-red { color: var(--red); background: var(--red-bg); }
.badge-neutral { color: var(--neutral); background: var(--neutral-bg); }
.ai-section {
  border: 2px solid #3b82f6;
  border-radius: 12px;
  padding: 1.5rem 1.75rem;
  background: linear-gradient(180deg, rgba(59, 130, 246, 0.06), transparent 60%);
}
@media (prefers-color-scheme: dark) {
  .ai-section { background: linear-gradient(180deg, rgba(59, 130, 246, 0.14), transparent 60%); }
}
.ai-section h2 { border-bottom-color: #3b82f6; }
.ai-section h3 { margin-bottom: 0.3rem; }
.ai-section p { margin-top: 0.2rem; }
.ai-badge {
  display: inline-block; padding: 0.15rem 0.6rem; border-radius: 999px;
  font-size: 0.75rem; font-weight: 700; letter-spacing: 0.03em;
  color: #ffffff; background: #3b82f6; text-transform: uppercase;
  margin-left: 0.5rem; vertical-align: middle;
}
.ai-missing {
  border: 1px dashed var(--border); border-radius: 10px; padding: 1rem 1.25rem;
  color: var(--muted);
}
.plan-units { display: flex; flex-direction: column; gap: 1.75rem; margin-top: 1rem; }
.plan-unit {
  border: 1px solid var(--border); border-radius: 12px; overflow: hidden;
}
.plan-unit-header {
  display: flex; align-items: center; justify-content: space-between; gap: 0.75rem;
  padding: 0.85rem 1.25rem; background: #12151E;
}
.plan-unit-header h3 { margin: 0; font-size: 1.02rem; color: #ffffff; font-weight: 600; }
.plan-svg-wrap {
  background: #13151f; padding: 1rem; overflow-x: auto; width: 100%;
}
.plan-svg-wrap svg { display: block; width: 100%; height: auto; }
.plan-legend {
  display: flex; flex-wrap: wrap; gap: 0.5rem 1.5rem; margin-top: 1.5rem;
  padding-top: 1rem; border-top: 1px solid var(--border);
  font-size: 0.85rem; color: var(--muted);
}
.plan-legend-item { display: inline-flex; align-items: center; gap: 0.45rem; }
.plan-legend-swatch {
  width: 14px; height: 14px; border-radius: 4px; border: 1px solid #2a2d3a; flex-shrink: 0;
}
.plan-legend-swatch--problem { background: transparent; border: 1.5px solid #EF4444; }
"""

_SCORE_BADGE_CLASS = {"verde": "badge-green", "amarillo": "badge-yellow", "rojo": "badge-red"}
_ORIENTATION_BADGE_CLASS = {
    "óptima": "badge-green",
    "aceptable": "badge-yellow",
    "penalizada": "badge-red",
    "sin regla": "badge-neutral",
}


def _bool_badge(passed: bool) -> str:
    cls = "badge-green" if passed else "badge-red"
    text = "OK" if passed else "FALLO"
    return f'<span class="badge {cls}">{text}</span>'


def _esc(text: str) -> str:
    return html_lib.escape(text)


def _ai_analysis_html(ai_analysis: Optional[AIAnalysis]) -> str:
    """Sección 'Análisis experto IA': destacada visualmente (borde azul).

    Si no hay análisis de IA disponible (sin ANTHROPIC_API_KEY, fallo de
    llamada, etc.), se muestra un aviso en su lugar en vez de omitir la
    sección por completo.
    """
    if ai_analysis is None:
        return (
            '<section class="ai-missing">'
            "Configure ANTHROPIC_API_KEY para activar el análisis experto con IA."
            "</section>"
        )

    parts = ['<section class="ai-section">']
    parts.append('<h2>Análisis experto <span class="ai-badge">IA</span></h2>')

    if ai_analysis.diagnosticos:
        parts.append("<h3>Diagnóstico por vivienda</h3>")
        for d in ai_analysis.diagnosticos:
            parts.append(f"<p><strong>{_esc(d.vivienda)}:</strong> {_esc(d.diagnostico)}</p>")

    if ai_analysis.mejoras_prioritarias:
        parts.append("<h3>Mejoras más importantes</h3><ol>")
        for m in ai_analysis.mejoras_prioritarias:
            parts.append(f"<li>{_esc(m)}</li>")
        parts.append("</ol>")

    if ai_analysis.comparativa:
        parts.append("<h3>Comparativa entre viviendas</h3>")
        parts.append(f"<p>{_esc(ai_analysis.comparativa)}</p>")

    if ai_analysis.conclusion_ejecutiva:
        parts.append("<h3>Conclusión ejecutiva</h3>")
        parts.append(f"<p>{_esc(ai_analysis.conclusion_ejecutiva)}</p>")

    parts.append("</section>")
    return "\n".join(parts)


def render_report_content(
    dxf_path: str,
    rooms: List[Room],
    results: List[RuleResult],
    advanced: AdvancedAnalysis,
    norte_grados: float = 0.0,
    ai_analysis: Optional[AIAnalysis] = None,
) -> str:
    """Construye el contenido del informe (cabecera, resumen, detalle por
    vivienda y análisis IA) como fragmento HTML, sin `<html>/<head>/<style>`.

    Reutilizado tanto por `write_html_report` (informe HTML autocontenido
    para uso por CLI) como por la app web, que lo embebe en su propia
    plantilla con `static/style.css`.
    """
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    unit_scores = advanced.unit_scores
    global_score = (
        sum(u.score_pct for u in unit_scores) / len(unit_scores) if unit_scores else 0.0
    )
    global_rating = score_rating(global_score)

    total_problems = (
        sum(1 for r in results if not r.passed)
        + sum(1 for p in advanced.proportions if not p.passed)
        + sum(1 for h in advanced.hierarchy if not h.passed)
        + sum(1 for e in advanced.efficiency if not e.passed)
        + sum(1 for o in advanced.orientation if o.rating == "penalizada")
    )

    parts: List[str] = [
        "<header>",
        "<h1>Informe de calidad arquitectónica</h1>",
        f'<p class="meta">Generado el {generated_at} · DXF: {_esc(dxf_path)} · '
        f"Norte: {norte_grados:.0f}° respecto a 'arriba' del plano</p>",
        "</header>",
        '<section class="summary">',
        '<div class="card"><div class="card-label">Puntuación global</div>'
        f'<div class="card-value"><span class="badge {_SCORE_BADGE_CLASS[global_rating]}">'
        f"{global_score:.0f}%</span></div></div>",
        '<div class="card"><div class="card-label">Viviendas analizadas</div>'
        f'<div class="card-value">{len(advanced.units)}</div></div>',
        '<div class="card"><div class="card-label">Habitaciones detectadas</div>'
        f'<div class="card-value">{len(rooms)}</div></div>',
        '<div class="card"><div class="card-label">Problemas totales</div>'
        f'<div class="card-value">{total_problems}</div></div>',
        "</section>",
    ]

    # --- Plano analizado (SVG, una fila por vivienda) -------------------
    plan_content = render_plan_section(unit_scores, norte_grados=norte_grados)
    if plan_content:
        parts.append('<section class="plan-section">')
        parts.append("<h2>Plano analizado</h2>")
        parts.append(plan_content)
        parts.append("</section>")

    # --- Tabla resumen de viviendas -----------------------------------
    parts.append("<section><h2>Resumen por vivienda</h2><table>")
    parts.append(
        "<tr><th>Vivienda</th><th>Habitaciones</th><th>Superficie total</th>"
        "<th>Puntuación</th><th>Estado</th></tr>"
    )
    for u in unit_scores:
        badge = _SCORE_BADGE_CLASS[u.rating]
        parts.append(
            f"<tr><td>{_esc(u.unit.name)}</td>"
            f"<td>{len(u.unit.rooms)}</td>"
            f"<td>{u.unit.total_area_m2:.2f} m²</td>"
            f"<td>{u.score_pct:.0f}% ({u.passed_checks}/{u.total_checks})</td>"
            f'<td><span class="badge {badge}">{u.rating.upper()}</span></td></tr>'
        )
    parts.append("</table></section>")

    # --- Detalle por vivienda ------------------------------------------
    for u in unit_scores:
        parts.append('<section class="unit-detail">')
        parts.append(
            f"<h2>{_esc(u.unit.name)} "
            f'<span class="badge {_SCORE_BADGE_CLASS[u.rating]}">{u.score_pct:.0f}%</span></h2>'
        )

        parts.append("<h3>Habitaciones</h3><table><tr><th>Habitación</th><th>Área</th></tr>")
        for r in u.unit.rooms:
            parts.append(
                f"<tr><td>{_esc(r.label or '(sin etiqueta)')}</td>"
                f"<td>{r.area_m2:.2f} m²</td></tr>"
            )
        parts.append("</table>")

        if u.basic_results:
            parts.append(
                "<h3>Reglas de superficie mínima</h3><table>"
                "<tr><th>Habitación</th><th>Regla</th><th>Área</th><th>Estado</th></tr>"
            )
            for r in u.basic_results:
                parts.append(
                    f"<tr><td>{_esc(r.room_label or '')}</td>"
                    f"<td>{_esc(r.rule_name)}</td>"
                    f"<td>{r.area_m2:.2f} m² (mín. {r.min_area_m2:.0f})</td>"
                    f"<td>{_bool_badge(r.passed)}</td></tr>"
                )
            parts.append("</table>")

        if u.proportion_results:
            parts.append(
                "<h3>Proporciones</h3><table>"
                "<tr><th>Habitación</th><th>Proporción</th><th>Dimensiones</th><th>Estado</th></tr>"
            )
            for p in u.proportion_results:
                parts.append(
                    f"<tr><td>{_esc(p.room_label or '')}</td>"
                    f"<td>{p.ratio_str}</td>"
                    f"<td>{p.long_side_m:.2f} x {p.short_side_m:.2f} m</td>"
                    f"<td>{_bool_badge(p.passed)}</td></tr>"
                )
            parts.append("</table>")

        if u.hierarchy_results:
            parts.append("<h3>Jerarquía de dormitorios</h3><table><tr><th>Comparación</th><th>Estado</th></tr>")
            for h in u.hierarchy_results:
                comp = (
                    f"{_esc(h.higher_name)} ({h.higher_area_m2:.2f} m²) &gt; "
                    f"{_esc(h.lower_name)} ({h.lower_area_m2:.2f} m²)"
                )
                parts.append(f"<tr><td>{comp}</td><td>{_bool_badge(h.passed)}</td></tr>")
            parts.append("</table>")

        if u.efficiency_result:
            e = u.efficiency_result
            parts.append(
                "<h3>Eficiencia</h3><table>"
                "<tr><th>Útil</th><th>Total</th><th>Ratio</th><th>Estado</th></tr>"
            )
            parts.append(
                f"<tr><td>{e.useful_area_m2:.2f} m²</td><td>{e.total_area_m2:.2f} m²</td>"
                f"<td>{e.ratio * 100:.1f}%</td><td>{_bool_badge(e.passed)}</td></tr>"
            )
            parts.append("</table>")

        if u.orientation_results:
            parts.append(
                "<h3>Orientación solar</h3><table>"
                "<tr><th>Habitación</th><th>Fachada larga</th><th>Valoración</th><th>Detalle</th></tr>"
            )
            for o in u.orientation_results:
                rating_class = _ORIENTATION_BADGE_CLASS[o.rating]
                parts.append(
                    f"<tr><td>{_esc(o.room_label)}</td>"
                    f"<td>{o.compass} ({o.bearing_deg:.0f}°)</td>"
                    f'<td><span class="badge {rating_class}">{_esc(o.rating)}</span></td>'
                    f"<td>{_esc(o.note)}</td></tr>"
                )
            parts.append("</table>")

        parts.append("</section>")

    parts.append(_ai_analysis_html(ai_analysis))

    return "\n".join(parts)


def write_html_report(
    output_path: str,
    dxf_path: str,
    rooms: List[Room],
    results: List[RuleResult],
    advanced: AdvancedAnalysis,
    norte_grados: float = 0.0,
    ai_analysis: Optional[AIAnalysis] = None,
) -> Path:
    """Genera un informe HTML autocontenido (con su propio `<style>`) y lo
    escribe en `output_path`. Devuelve la ruta escrita."""
    content = render_report_content(
        dxf_path=dxf_path,
        rooms=rooms,
        results=results,
        advanced=advanced,
        norte_grados=norte_grados,
        ai_analysis=ai_analysis,
    )
    html = "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="es">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>Informe de calidad arquitectónica — arquitecto-ai</title>",
            f"<style>{_CSS}</style>",
            "</head>",
            "<body>",
            content,
            "</body></html>",
        ]
    )

    path = Path(output_path)
    path.write_text(html, encoding="utf-8")
    return path
