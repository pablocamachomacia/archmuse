"""Herramienta de depuración interna: analiza un plano DXF por línea de
comandos y vuelca un informe de calidad en consola y en HTML (junto al propio
DXF, como "informe.html").

**Esto no es el producto.** ArchMuse es `app.py` + la SPA de `static/`; este
script existe para poder mirar el resultado del motor de reglas sobre un DXF
sin levantar el servidor. Si dudas de cuál de los dos toca modificar, es
`app.py`.

Uso:
    python main.py [ruta_al_archivo.dxf] [norte_grados]

- ruta_al_archivo.dxf: si no se indica, usa `ejemplo.dxf` (ver `DXF_POR_DEFECTO`).
- norte_grados: azimut (grados, sentido horario, 0=Norte) hacia el que
  apunta 'arriba' (+Y) en el plano. Por defecto 0 (arriba = Norte).
"""
from __future__ import annotations

import sys
from pathlib import Path

from analyzer.ai_analyst import analyze_with_ai, build_viviendas_payload
from analyzer.entorno import cargar_dotenv
from analyzer.evaluator import evaluate_advanced, evaluate_rooms
from analyzer.parser import CapaIndeterminada, EscalaIndeterminada, leer_plano, load_document
from analyzer.reporter import print_advanced_report, print_report, write_html_report

#: `ejemplo.dxf` es un plano real y vive JUNTO al repositorio, no dentro (por
#: eso no está versionado). Se deriva de la ubicación de este fichero y nunca
#: de una ruta personal: es la misma convención que ya usan `tests/golden.py` y
#: el resto de los tests, y evita que la carpeta de nadie acabe publicada.
DXF_POR_DEFECTO = str(Path(__file__).resolve().parents[1] / "ejemplo.dxf")
AREA_LAYER = "00 areas"
NORTE_GRADOS = 0.0


def _fix_console_encoding() -> None:
    """Evita caracteres corruptos (á, ñ, ²...) en consolas de Windows con codepage heredado."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main() -> int:
    _fix_console_encoding()
    # El `.env` local, si lo hay: esta CLI llega hasta `analyze_with_ai()`,
    # que necesita ANTHROPIC_API_KEY. Ver analyzer/entorno.py.
    cargar_dotenv()
    dxf_path = sys.argv[1] if len(sys.argv) > 1 else DXF_POR_DEFECTO
    norte_grados = float(sys.argv[2]) if len(sys.argv) > 2 else NORTE_GRADOS

    if not Path(dxf_path).exists():
        print("Error: no se encuentra el DXF a analizar: %s" % dxf_path)
        if len(sys.argv) <= 1:
            print("  Ese es el valor por defecto: `ejemplo.dxf` junto al repositorio.")
            print("  Indica una ruta:  python main.py ruta\\a\\tu\\plano.dxf")
        return 1

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
