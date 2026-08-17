"""Completa el registro geográfico con el fichero oficial del INE.

Hoy `normativa/geografia/es/municipios.yaml` es una SEMILLA MANUAL de 31
municipios escritos a mano y sin verificar. Este script la sustituye por los
8.131 reales y marca el registro como verificado.

QUÉ NO ES: no es un crawler ni un importador de normativa. Lee un fichero que
el usuario ha descargado a mano del portal del INE. La condición de "sin
scraping ni importación masiva de normativa" se refiere al CORPUS NORMATIVO,
que se transcribe y valida persona a persona (Fase 1, tarea 18 del PRD). Esto
es geografía administrativa: dato público, estable y verificable de un vistazo.

USO
    1. Descargar del INE la relación de municipios con su código
       (fichero "Relación de municipios y códigos por provincias").
       Exportar a CSV con, al menos, código de provincia, código de municipio
       y nombre.
    2. Ejecutar:

           venv/Scripts/python.exe scripts/actualizar_registro_ine.py ruta.csv

    3. Revisar el diff en git ANTES de commitear. Un registro geográfico
       equivocado es tan silencioso como un umbral equivocado.

El script NO toca el corpus normativo ni el manifiesto de cobertura: añadir
municipios al registro amplía lo que el sistema RECONOCE, nunca lo que
AFIRMA. Un municipio recién reconocido sigue sin cobertura hasta que alguien
transcriba su normativa.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "normativa" / "geografia" / "es" / "municipios.yaml"
REGISTRO = RAIZ / "normativa" / "geografia" / "es" / "_registro.yaml"

CABECERA = """\
# Registro de municipios de España, por código INE.
#
# GENERADO por scripts/actualizar_registro_ine.py a partir del fichero oficial
# del INE. No editar a mano: cualquier corrección debe venir del fichero
# oficial, o volverá a perderse en la siguiente actualización.
#
# `codigo` es la identidad (5 dígitos: 2 de provincia + 3 de municipio).
# `nombre` es una etiqueta; las variantes escritas se resuelven en alias.yaml.
#
# Un municipio ausente NO produce repliegue a otro: produce AmbitoDesconocido.
# Y estar aquí no implica tener normativa cargada: reconocer un municipio y
# tener su corpus son dos cosas distintas (ver cobertura/manifiesto.yaml).

version: {version}
municipios:
"""


def normalizar_cabecera(nombre: str) -> str:
    n = unicodedata.normalize("NFKD", nombre or "")
    n = "".join(c for c in n if not unicodedata.combining(c))
    return n.lower().strip().replace(" ", "_")


def detectar_columnas(campos: list) -> dict:
    """Localiza las columnas relevantes sin exigir un formato exacto: el INE
    publica el mismo dato con cabeceras distintas según el año y la exportación."""
    normalizados = {normalizar_cabecera(c): c for c in campos}
    def buscar(*candidatos):
        for cand in candidatos:
            for norm, original in normalizados.items():
                if cand in norm:
                    return original
        return None

    return {
        "provincia": buscar("cpro", "codigo_provincia", "cod_provincia", "provincia"),
        "municipio": buscar("cmun", "codigo_municipio", "cod_municipio"),
        "nombre": buscar("nombre", "denominacion", "municipio"),
    }


def leer(ruta: Path) -> list:
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        muestra = f.read(4096)
        f.seek(0)
        try:
            dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t")
        except csv.Error:
            dialecto = csv.excel
        lector = csv.DictReader(f, dialect=dialecto)
        cols = detectar_columnas(lector.fieldnames or [])
        if not all(cols.values()):
            raise SystemExit(
                f"No se han localizado las columnas necesarias en {ruta.name}.\n"
                f"Detectadas: {cols}\nCabeceras del fichero: {lector.fieldnames}"
            )
        filas = []
        for fila in lector:
            cpro = str(fila[cols["provincia"]]).strip().zfill(2)
            cmun = str(fila[cols["municipio"]]).strip().zfill(3)
            nombre = str(fila[cols["nombre"]]).strip()
            if not cpro.isdigit() or not cmun.isdigit() or not nombre:
                continue
            filas.append((cpro + cmun, nombre, cpro))
    return sorted(set(filas))


def escribir(municipios: list, version: int = 2) -> None:
    with io.open(DESTINO, "w", encoding="utf-8", newline="\n") as f:
        f.write(CABECERA.format(version=version))
        for codigo, nombre, provincia in municipios:
            seguro = nombre.replace('"', "'")
            f.write(f'  - {{ codigo: "{codigo}", nombre: "{seguro}", provincia: "{provincia}" }}\n')


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv", type=Path, help="CSV oficial del INE con códigos de municipio")
    p.add_argument("--dry-run", action="store_true", help="no escribe, solo informa")
    args = p.parse_args()

    if not args.csv.exists():
        raise SystemExit(f"No existe {args.csv}")

    municipios = leer(args.csv)
    print(f"Leídos {len(municipios)} municipios de {args.csv.name}")

    provincias = {m[2] for m in municipios}
    print(f"Provincias distintas: {len(provincias)}")
    if len(municipios) < 8000:
        print(
            f"\nAVISO: {len(municipios)} municipios es menos de los ~8.131 esperados. "
            "Comprueba que el fichero es la relación completa y no un extracto."
        )

    if args.dry_run:
        print("\n--dry-run: no se ha escrito nada.")
        return 0

    escribir(municipios)
    print(f"Escrito {DESTINO.relative_to(RAIZ)}")
    print(
        "\nPENDIENTE A MANO en normativa/geografia/es/_registro.yaml:\n"
        "  - municipios.estado: completo\n"
        "  - municipios.verificado: true\n"
        "  - municipios.n_cargados: %d\n"
        "  - borrar 'pendiente' y 'aviso'\n"
        "\nY revisar el diff en git antes de commitear." % len(municipios)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
