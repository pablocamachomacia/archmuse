"""Punto de entrada: analiza un plano DXF y genera un informe de calidad en
consola y en HTML (junto al propio DXF, como "informe.html").

Uso:
    python main.py [ruta_al_archivo.dxf] [norte_grados]

- ruta_al_archivo.dxf: si no se indica, usa DXF_PATH.
- norte_grados: azimut (grados, sentido horario, 0=Norte) hacia el que
  apunta 'arriba' (+Y) en el plano. Por defecto 0 (arriba = Norte).
"""
from __future__ import annotations

import sys
from pathlib import Path

from analyzer.ai_analyst import analyze_with_ai, build_viviendas_payload
from analyzer.evaluator import evaluate_advanced, evaluate_rooms
from analyzer.parser import CapaIndeterminada, EscalaIndeterminada, leer_plano, load_document
from analyzer.reporter import print_advanced_report, print_report, write_html_report

DXF_PATH = r"C:\Users\<usuario>\Desktop\Pablo\Archmuse\ejemplo.dxf"
AREA_LAYER = "00 areas"
NORTE_GRADOS = 0.0


def _fix_console_encoding() -> None:
    """Evita caracteres corruptos (á, ñ, ²...) en consolas de Windows con codepage heredado."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main() -> int:
    _fix_console_encoding()
    dxf_path = sys.argv[1] if len(sys.argv) > 1 else DXF_PATH
    norte_grados = float(sys.argv[2]) if len(sys.argv) > 2 else NORTE_GRADOS

    try:
        doc = load_document(dxf_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    try:
        plano = leer_plano(doc, layer=AREA_LAYER)
    except CapaIndeterminada as exc:
        print(f"Error: {exc}")
        return 1
    except EscalaIndeterminada as exc:
        print(f"Error: {exc}")
        if exc.deteccion.sugerencia:
            print(f"Sugerencia: el plano parece estar en {exc.deteccion.sugerencia}.")
        return 1

    rooms = plano.rooms
    unit_labels = plano.unit_labels
    if plano.escala.origen != "acuerdo":
        print(f"Escala: {plano.escala.mensaje}")

    results = evaluate_rooms(rooms)
    print_report(rooms, results)

    advanced = evaluate_advanced(rooms, unit_labels=unit_labels, norte_grados=norte_grados)
    print_advanced_report(advanced)

    print()
    print("=" * 60)
    print("ANÁLISIS EXPERTO IA")
    print("=" * 60)
    viviendas_payload = build_viviendas_payload(advanced.unit_scores)
    ai_analysis = analyze_with_ai(viviendas_payload)
    print(
        "Análisis IA incluido en el informe HTML."
        if ai_analysis is not None
        else "Análisis IA no disponible (ver aviso anterior)."
    )

    html_output = Path(dxf_path).resolve().parent / "informe.html"
    written_path = write_html_report(
        output_path=str(html_output),
        dxf_path=dxf_path,
        rooms=rooms,
        results=results,
        advanced=advanced,
        norte_grados=norte_grados,
        ai_analysis=ai_analysis,
    )
    print(f"\nInforme HTML generado en: {written_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
