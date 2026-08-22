#!/usr/bin/env python3
"""Ejecuta un script de ArchMuse contra cada DXF del banco de tortura.

Uso, desde la raiz del repo archmuse:
    python correr_banco.py scripts/revisar_plano.py dxf_tortura/
    python correr_banco.py scripts/cuadro_de_superficies.py dxf_tortura/

Clasifica cada ejecucion:
    OK       salio con codigo 0
    AVISO    salio con codigo != 0 pero SIN traceback (rechazo controlado: bien)
    CRASH    traceback de Python -> esto es un bug que arreglar

Al final imprime el resumen y guarda el detalle en resultados_banco.md.
Exito del dia 1 = cero CRASH. (OK y AVISO son ambos aceptables:
lo que ArchMuse promete no es tragar con todo, es no reventar nunca.)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TIMEOUT_S = 120


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    script = Path(sys.argv[1])
    banco = Path(sys.argv[2])
    dxfs = sorted(banco.glob("*.dxf"))
    if not dxfs:
        print(f"No hay .dxf en {banco}")
        sys.exit(1)

    filas = []
    for dxf in dxfs:
        try:
            r = subprocess.run(
                [sys.executable, str(script), str(dxf)],
                capture_output=True, text=True, timeout=TIMEOUT_S,
            )
            salida = (r.stdout + r.stderr)
            if "Traceback (most recent call last)" in salida:
                estado = "CRASH"
                detalle = salida.strip().splitlines()[-1][:120]
            elif r.returncode == 0:
                estado = "OK"
                detalle = salida.strip().splitlines()[-1][:120] if salida.strip() else ""
            else:
                estado = "AVISO"
                detalle = salida.strip().splitlines()[-1][:120] if salida.strip() else f"rc={r.returncode}"
        except subprocess.TimeoutExpired:
            estado, detalle = "CRASH", f"timeout > {TIMEOUT_S}s (posible bucle)"
        filas.append((dxf.name, estado, detalle))
        marca = {"OK": " ", "AVISO": "?", "CRASH": "X"}[estado]
        print(f"[{marca}] {estado:5s}  {dxf.name:45s} {detalle}")

    crashes = sum(1 for _, e, _ in filas if e == "CRASH")
    avisos = sum(1 for _, e, _ in filas if e == "AVISO")
    oks = sum(1 for _, e, _ in filas if e == "OK")
    print(f"\nResumen {script.name}: {oks} OK, {avisos} AVISO, {crashes} CRASH de {len(filas)}")
    if crashes:
        print(">>> Hay CRASH: cada uno contradice la promesa 'nunca revienta, pregunta'.")

    with open("resultados_banco.md", "a", encoding="utf-8") as f:
        f.write(f"\n## {script.name}\n\n| DXF | Estado | Ultima linea |\n|---|---|---|\n")
        for nombre, estado, detalle in filas:
            f.write(f"| `{nombre}` | {estado} | {detalle} |\n")

    sys.exit(1 if crashes else 0)


if __name__ == "__main__":
    main()
