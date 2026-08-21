#!/usr/bin/env python3
"""Resolución manual de discrepancias — Prompt 2,
docs/prd/2026-08-21-verificacion-doble-del-corpus.md §5.5.

Uso:
    python scripts/revisar_pendientes.py <pendientes.jsonl>

Presenta cada pendiente de `extraccion/estado/pendientes/*.verificacion_doble.jsonl`
uno a uno, con las dos lecturas (o la única) y el motivo por el que no se
promovió sola. Pablo elige:

    a  — usar la lectura A (ruta pypdf + IA)
    b  — usar la lectura B (ruta pdfminer.six + extractor determinista)
    m  — corregir a mano (teclear valor y unidad)
    d  — descartar (sigue pendiente, sin generar regla)
    s  — saltar por ahora (no se registra resolución; vuelve a salir la
         próxima vez que se ejecute el script)

Toda resolución que NO sea «saltar» se registra en
`extraccion/estado/resoluciones.jsonl` (append-only, nunca se reescribe una
línea ya escrita) con fecha y quién resolvió. Si no es «descartar», además
se genera la regla `VERIFICADA_AUTOMATICA` correspondiente, con
`tags: ["resuelto_manualmente:AAAA-MM-DD"]` — la firma de Pablo sustituye
a la segunda ruta cuando las dos rutas no bastaron por sí solas.

**Reanudable.** Una discrepancia ya resuelta (por `candidata_padre` +
`parametro_nombre`, en `resoluciones.jsonl`) no se vuelve a preguntar —
correr el script dos veces sobre el mismo `pendientes.jsonl` no repite
trabajo ya hecho.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Callable, Optional

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extraccion.confianza import calcular_confianza  # noqa: E402
from normativa.validacion import validar_fichero  # noqa: E402
from scripts.generar_borrador_corpus import _construir_documento, _señales_desde_dict  # noqa: E402

RESOLUCIONES = RAIZ / "extraccion" / "estado" / "resoluciones.jsonl"


def _clave(pendiente: dict) -> str:
    return f"{pendiente['candidata_padre']}::{pendiente['parametro_nombre']}"


def _ya_resueltas(ruta: Path = RESOLUCIONES) -> set:
    if not ruta.exists():
        return set()
    resueltas = set()
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        r = json.loads(linea)
        resueltas.add(f"{r['candidata_padre']}::{r['parametro_nombre']}")
    return resueltas


def _formatear_lectura(etiqueta: str, lectura: Optional[dict]) -> str:
    if lectura is None:
        return f"  {etiqueta}: (sin lectura de esta ruta)"
    return f"  {etiqueta}: {lectura['valor']} {lectura['unidad']} — «{lectura.get('contexto_citado', '')}»"


def presentar(pendiente: dict, salida: Callable[[str], None] = print) -> None:
    salida("")
    salida(f"=== {pendiente['candidata_padre']} — {pendiente['parametro_nombre']} ===")
    salida(f"Motivo: {pendiente['motivo']}")
    salida(_formatear_lectura("A (pypdf + IA)", pendiente.get("lectura_a")))
    salida(_formatear_lectura("B (pdfminer.six + patrón)", pendiente.get("lectura_b")))


def _opciones_disponibles(pendiente: dict) -> list:
    opciones = []
    if pendiente.get("lectura_a"):
        opciones.append("a")
    if pendiente.get("lectura_b"):
        opciones.append("b")
    opciones += ["m", "d", "s"]
    return opciones


def resolver_uno(
    pendiente: dict,
    entrada: Callable[[str], str] = input,
    salida: Callable[[str], None] = print,
) -> Optional[dict]:
    """Presenta un pendiente y devuelve su resolución como dict, o `None`
    si se salta (no se registra nada). `entrada`/`salida` son inyectables
    para poder probar la lógica sin una terminal real."""
    presentar(pendiente, salida)
    opciones = _opciones_disponibles(pendiente)
    salida(f"Elige [{'/'.join(opciones)}] (a=usar A, b=usar B, m=a mano, d=descartar, s=saltar): ")
    respuesta = entrada("> ").strip().lower()

    if respuesta == "s" or respuesta not in opciones:
        return None

    hoy = date.today().isoformat()
    base = {
        "candidata_padre": pendiente["candidata_padre"],
        "parametro_nombre": pendiente["parametro_nombre"],
        "lectura_a": pendiente.get("lectura_a"),
        "lectura_b": pendiente.get("lectura_b"),
        "resuelto_por": "Pablo",
        "fecha": hoy,
    }

    if respuesta == "d":
        return {**base, "resolucion": "descartada", "valor_final": None, "unidad_final": None}
    if respuesta == "a":
        lectura = pendiente["lectura_a"]
        return {**base, "resolucion": "A", "valor_final": lectura["valor"], "unidad_final": lectura["unidad"]}
    if respuesta == "b":
        lectura = pendiente["lectura_b"]
        return {**base, "resolucion": "B", "valor_final": lectura["valor"], "unidad_final": lectura["unidad"]}
    # "m": a mano
    valor_txt = entrada("  Valor (número): ").strip()
    unidad_txt = entrada("  Unidad: ").strip()
    try:
        valor = float(valor_txt.replace(",", "."))
    except ValueError:
        salida(f"  «{valor_txt}» no es un número — se descarta esta resolución, vuelve a intentarlo.")
        return None
    return {**base, "resolucion": "manual", "valor_final": valor, "unidad_final": unidad_txt}


def _registrar(resolucion: dict, ruta: Path = RESOLUCIONES) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a", encoding="utf-8") as f:
        f.write(json.dumps(resolucion, ensure_ascii=False) + "\n")


def _generar_regla(resolucion: dict, cand_padre: dict, salida_dir: Path, sha256_pdf: str, salida: Callable[[str], None] = print) -> Optional[Path]:
    """Construye y escribe la regla VERIFICADA_AUTOMATICA de una
    resolución manual. `cand_padre` es la candidata de la ruta A que dio
    origen al pendiente (para heredar tipo/patrón/materia/texto_original)."""
    parametro_nombre = resolucion["parametro_nombre"]
    unidad_cand = dict(cand_padre)
    unidad_cand["parametros"] = [{
        "nombre": parametro_nombre,
        "valor_citado": f"{resolucion['valor_final']} {resolucion['unidad_final']}".strip(),
        "unidad": resolucion["unidad_final"],
        "comparador": ">=",
        "contexto_citado": (resolucion.get("lectura_a") or resolucion.get("lectura_b") or {}).get("contexto_citado", ""),
    }]

    señales = _señales_desde_dict(cand_padre["señales"])
    nivel_confianza, _revisar, _motivos = calcular_confianza(señales)
    doc = _construir_documento(unidad_cand, nivel_confianza, estado="VERIFICADA_AUTOMATICA", documento_sha256=sha256_pdf)
    doc["reglas"][0]["tags"].append(f"resuelto_manualmente:{resolucion['fecha']}")

    fallos = validar_fichero(doc)
    if fallos:
        salida(f"  No se ha podido generar la regla: {'; '.join(fallos)}")
        return None

    concept_id = doc["reglas"][0]["concept_id"]
    destino = salida_dir / f"_verificada_manual_{concept_id.split('.')[-1]}.yaml"
    with destino.open("w", encoding="utf-8") as f:
        f.write(
            "# Generado automáticamente por scripts/revisar_pendientes.py — NO EDITAR A MANO.\n"
            f"# Resolución manual de Pablo, {resolucion['fecha']} — ver extraccion/estado/resoluciones.jsonl\n\n"
        )
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return destino


def procesar(
    pendientes_ruta: Path,
    candidatas_por_padre: dict,
    salida_dir: Path,
    sha256_pdf: str,
    entrada: Callable[[str], str] = input,
    salida: Callable[[str], None] = print,
    resoluciones_ruta: Path = RESOLUCIONES,
) -> dict:
    """`resoluciones_ruta` es un parámetro explícito, no un valor por
    defecto que dependa de parchear el módulo: un `Path` por defecto se
    fija al DEFINIR la función, así que `monkeypatch` sobre `RESOLUCIONES`
    después de importar no lo cambiaría — pasarlo aquí es lo que hace esto
    probable sin tocar el fichero real del proyecto."""
    pendientes = [json.loads(linea) for linea in pendientes_ruta.read_text(encoding="utf-8").splitlines()]
    resueltas = _ya_resueltas(resoluciones_ruta)

    resueltos_ahora = 0
    generadas = []
    for p in pendientes:
        if _clave(p) in resueltas:
            continue
        resolucion = resolver_uno(p, entrada, salida)
        if resolucion is None:
            continue
        _registrar(resolucion, resoluciones_ruta)
        resueltos_ahora += 1
        if resolucion["resolucion"] != "descartada":
            cand_padre = candidatas_por_padre.get(p["candidata_padre"])
            if cand_padre is not None:
                destino = _generar_regla(resolucion, cand_padre, salida_dir, sha256_pdf, salida)
                if destino:
                    generadas.append(destino)

    return {"resueltos_ahora": resueltos_ahora, "generadas": generadas, "total_pendientes": len(pendientes)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pendientes", type=Path)
    parser.add_argument("candidatas_a", type=Path, help="El .jsonl de candidatas de la ruta A, para reconstruir la regla")
    parser.add_argument("--sha256-pdf", required=True)
    parser.add_argument("--salida", type=Path, default=RAIZ / "normativa" / "es" / "estatal")
    args = parser.parse_args()

    from extraccion import almacen

    candidatas = almacen.leer(args.candidatas_a if args.candidatas_a.is_absolute() else RAIZ / args.candidatas_a)
    por_padre = {c["articulo"]: c for c in candidatas}

    resultado = procesar(
        args.pendientes if args.pendientes.is_absolute() else RAIZ / args.pendientes,
        por_padre, args.salida, args.sha256_pdf,
    )
    print(f"\nResueltas en esta sesión: {resultado['resueltos_ahora']} / {resultado['total_pendientes']} pendientes")
    if resultado["generadas"]:
        print("Reglas generadas:")
        for p in resultado["generadas"]:
            print(f"  - {p.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
