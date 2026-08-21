#!/usr/bin/env python3
"""Verificación doble del corpus (Prompt 2,
docs/prd/2026-08-21-verificacion-doble-del-corpus.md).

Uso:
    python scripts/verificar_doble_ruta.py <candidatas_a.jsonl> <pdf_original>

Toma las sub-candidatas atómicas que la descomposición del Prompt 1.5
(`scripts/generar_borrador_corpus.py::_descomponer`) ya identifica sobre la
ruta A (`pypdf` + interpretación por IA), corre una segunda lectura
INDEPENDIENTE sobre el mismo PDF con la ruta B, y compara.

**La ruta B no usa la API** — decisión de Pablo, 2026-08-21, tras
encontrarse el saldo de la cuenta insuficiente para las llamadas de
interpretación: `extraccion/segmentador_pdf_b.py` (motor de texto
`pdfminer.six`, des-guionizado explícito) segmenta el documento, y
`extraccion/interprete_b_determinista.py` reconoce por patrón el lenguaje
de umbral del CTE sobre ese texto — cero llamadas a la API, cero coste,
ejecutable offline. Ver el docstring de ese módulo para por qué esto es
una verificación MÁS fuerte que dos lecturas de IA, no una más débil.

**Coincidencia = mismo valor numérico y misma unidad** (PRD §5.3), no
mismo nombre de parámetro — una IA y un extractor de patrones no tienen
por qué llamar igual al mismo hecho. Coincide → `estado:
VERIFICADA_AUTOMATICA`, con el SHA-256 del PDF oficial. No coincide, o
solo una ruta la ancla → pendientes, con las dos lecturas (o la única)
adjuntas — nunca se elige una por defecto.

`_contar_cifras_de_umbral` (el guardián que evita convertir la mitad de
una disyunción como si fuera un umbral incondicional, Prompt 1.5) sigue
aplicándose en la ruta A vía `_descomponer`; en la ruta B el mismo riesgo
lo cubre el propio extractor determinista, que declara TODAS las cifras
de una cláusula, nunca solo la primera (ver
`test_disyuncion_proteccion_recorridos_7_3_emite_las_dos_cifras`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extraccion import almacen  # noqa: E402
from extraccion import interprete_b_determinista as _det  # noqa: E402
from extraccion import segmentador_pdf_b  # noqa: E402
from extraccion.confianza import calcular_confianza  # noqa: E402
from ingesta.modelo import DocumentoOficial  # noqa: E402
from normativa.validacion import validar_fichero  # noqa: E402
from scripts.generar_borrador_corpus import (  # noqa: E402
    _construir_documento,
    _numero,
    _señales_desde_dict,
    _descomponer,
)

RUTA_B_ESTADO = RAIZ / "extraccion" / "estado" / "ruta_b"

#: Normaliza variantes de escritura de la misma unidad — cerrado a las
#: unidades ya vistas en el corpus real de DB-SUA, no una tabla genérica
#: inventada por adelantado.
_UNIDADES_EQUIVALENTES = {
    "m2": "m²", "metros cuadrados": "m²",
    "grados": "º", "°": "º",
}


def _normalizar_unidad(unidad: Optional[str]) -> str:
    u = (unidad or "").strip().lower()
    return _UNIDADES_EQUIVALENTES.get(u, u)


# --- Construcción del DocumentoOficial para la ruta B -----------------------

def _documento_desde_candidata_a(cand: dict, bytes_pdf: bytes) -> DocumentoOficial:
    """Reconstruye los metadatos del documento oficial a partir de lo que
    ya guardó la ruta A en su primera candidata — no se vuelve a preguntar
    nada que ya se sabe, solo se le da a la ruta B su propio PDF."""
    return DocumentoOficial(
        identificador=cand["documento_identificador"],
        fuente="codigotecnico",
        titulo=cand["documento"],
        organismo=cand["organismo"],
        rango_codigo=None, rango_nombre=None, numero_oficial=None,
        fecha_publicacion=cand.get("fecha"), fecha_disposicion=None, fecha_actualizacion=None,
        url_oficial=cand["url_oficial"], url_xml="",
        texto_crudo="",  # segmentador_pdf_b lo sustituye por su propia extracción
        hash_texto=cand["version"],
        formato="pdf", bytes_crudos=bytes_pdf,
    )


def ejecutar_ruta_b(candidatas_a: List[dict], ruta_pdf: Path) -> Dict[str, dict]:
    """Segmenta el PDF con el motor de texto de la ruta B y aplica el
    extractor determinista a cada segmento — sin red, sin API. Devuelve
    `{articulo: {"valores": [...], "no_reconocidas": [...], "texto": ...}}`.

    Se persiste en `RUTA_B_ESTADO` para trazabilidad y para no repetir el
    trabajo si se vuelve a invocar sobre la misma versión del documento —
    barato de recalcular al ser determinista, pero el registro en disco es
    lo que deja ver qué produjo la ruta B sin tener que volver a correrla."""
    documento = _documento_desde_candidata_a(candidatas_a[0], ruta_pdf.read_bytes())
    nombre = f"{documento.fuente}__{documento.identificador}__{documento.hash_texto[:12]}.rutab.jsonl"
    destino = RUTA_B_ESTADO / "candidatas" / nombre

    if destino.exists():
        registros = [json.loads(linea) for linea in destino.read_text(encoding="utf-8").splitlines()]
    else:
        segmentos = segmentador_pdf_b.segmentar(documento)
        registros = []
        for s in segmentos:
            valores, no_reconocidas = _det.extraer(s.texto)
            registros.append({
                "articulo": s.titulo,
                "texto": s.texto,
                "valores": [vars(v) for v in valores],
                "no_reconocidas": [vars(n) for n in no_reconocidas],
            })
        destino.parent.mkdir(parents=True, exist_ok=True)
        with destino.open("w", encoding="utf-8") as f:
            for r in registros:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return {r["articulo"]: r for r in registros}


# --- Comparación --------------------------------------------------------

def _valores_convertibles_a(cand: dict) -> List[Tuple[float, str, Any]]:
    """[(valor, unidad_normalizada, grupo)] de los grupos que la ruta A
    convertiría en solitario (mismo criterio que
    scripts/generar_borrador_corpus.py::procesar) — el guardián
    `_contar_cifras_de_umbral` ya vive dentro de `_descomponer`."""
    salida = []
    for grupo in _descomponer(cand):
        if grupo.motivo_forzado is not None or not grupo.parametros:
            continue
        p = grupo.parametros[0]
        valor = _numero(p.get("valor_citado", ""))
        if valor is None:
            continue
        salida.append((valor, _normalizar_unidad(p.get("unidad")), grupo))
    return salida


def _valores_ruta_b(registro_b: Optional[dict]) -> List[Tuple[float, str, dict]]:
    if registro_b is None:
        return []
    salida = []
    for v in registro_b["valores"]:
        valor = _numero(v["valor_citado"])
        if valor is None:
            continue
        salida.append((valor, _normalizar_unidad(v["unidad"]), v))
    return salida


def comparar_padre(cand_a: dict, registro_b: Optional[dict]) -> Dict[str, Any]:
    """Compara los valores convertibles de un mismo artículo entre las dos
    rutas. Devuelve {'promovidas': [...], 'pendientes': [...]} — cada
    entrada de `pendientes` lleva las dos lecturas (o la única, si la otra
    ruta no encontró nada para ese artículo)."""
    convertibles_a = _valores_convertibles_a(cand_a)
    convertibles_b = _valores_ruta_b(registro_b)

    promovidas: List[dict] = []
    pendientes: List[dict] = []
    usados_b: set = set()

    for valor_a, unidad_a, grupo_a in convertibles_a:
        indice_b = next(
            (i for i, (vb, ub, _) in enumerate(convertibles_b)
             if i not in usados_b and vb == valor_a and ub == unidad_a),
            None,
        )
        unidad_padre_a = dict(cand_a)
        unidad_padre_a["parametros"] = grupo_a.parametros
        if grupo_a.patron_override:
            unidad_padre_a["patron"] = grupo_a.patron_override

        if indice_b is not None:
            usados_b.add(indice_b)
            promovidas.append({
                "candidata_padre": cand_a.get("articulo"),
                "parametro_nombre": grupo_a.parametros[0]["nombre"],
                "valor": valor_a, "unidad": unidad_a,
                "unidad_a": unidad_padre_a,
            })
        else:
            if registro_b is None:
                motivo = "la ruta B no segmentó este artículo (límite conocido, ver segmentador_pdf_b.py)"
            elif not convertibles_b and registro_b["no_reconocidas"]:
                motivo = "patron_no_reconocido_ruta_b: el extractor determinista no reconoció ninguna cláusula de este artículo"
            else:
                motivo = "la ruta B no produjo el mismo valor/unidad para este artículo"
            pendientes.append({
                "candidata_padre": cand_a.get("articulo"),
                "parametro_nombre": grupo_a.parametros[0]["nombre"],
                "motivo": motivo,
                "lectura_a": {"valor": valor_a, "unidad": unidad_a,
                             "contexto_citado": grupo_a.parametros[0].get("contexto_citado")},
                "lectura_b": None,
                "no_reconocidas_b_del_articulo": registro_b["no_reconocidas"] if registro_b else None,
            })

    for i, (valor_b, unidad_b, v_b) in enumerate(convertibles_b):
        if i in usados_b:
            continue
        pendientes.append({
            "candidata_padre": cand_a.get("articulo"),
            "parametro_nombre": v_b["nombre"],
            "motivo": "solo la ruta B ancló este valor: hallazgo nuevo, no confirmado por la ruta A",
            "lectura_a": None,
            "lectura_b": {"valor": valor_b, "unidad": unidad_b,
                         "contexto_citado": v_b.get("contexto_citado")},
        })

    return {"promovidas": promovidas, "pendientes": pendientes}


# --- Orquestación -----------------------------------------------------------

def procesar(ruta_candidatas_a: Path, ruta_pdf: Path, salida_dir: Path, pendientes_ruta: Path) -> dict:
    candidatas_a = almacen.leer(ruta_candidatas_a)
    if not candidatas_a:
        raise SystemExit(f"«{ruta_candidatas_a}» no contiene candidatas")

    sha256_pdf = hashlib.sha256(ruta_pdf.read_bytes()).hexdigest()
    registros_b = ejecutar_ruta_b(candidatas_a, ruta_pdf)

    salida_dir.mkdir(parents=True, exist_ok=True)
    pendientes_ruta.parent.mkdir(parents=True, exist_ok=True)
    # `_` a propósito, aunque parezca contradecir el sentido de "promoción":
    # SIN un `aplicabilidad.usos`/`tipologias` propio, tres reglas
    # VERIFICADA_AUTOMATICA de materias distintas exigencias pero la misma
    # `materia`+`patron` genéricos COMPITEN en la validación 14
    # (`normativa/validacion.py::validar_sin_contradiccion`) y tumban la
    # carga del corpus ENTERO — lo probé sin el guión bajo y se llevó por
    # delante hasta `seguridad_incendio.yaml`. Ver
    # docs/design/2026-08-21-limite-aplicabilidad-generica-verificada-automatica.md:
    # hace falta resolver la especificidad de `aplicabilidad` por regla
    # antes de que "afirmable" (normativa/resolucion.py) sea también
    # "cargable sin chocar con sus hermanas" — tareas relacionadas, no la
    # misma. Hasta entonces, VERIFICADA_AUTOMATICA queda registrado (dos
    # rutas coincidieron, el hecho es real) pero invisible al loader, igual
    # que BORRADOR.
    prefijo_stem = "_verificada_db_sua"
    for viejo in salida_dir.glob(f"{prefijo_stem}_*.yaml"):
        viejo.unlink()

    convertidas: List[Path] = []
    pendientes_totales: List[dict] = []
    motivos: Counter = Counter()
    concept_ids_vistos: set = set()
    articulos_sin_ruta_b: List[str] = []

    for cand_a in candidatas_a:
        registro_b = registros_b.get(cand_a["articulo"])
        if registro_b is None:
            articulos_sin_ruta_b.append(cand_a["articulo"])
        resultado = comparar_padre(cand_a, registro_b)

        for p in resultado["pendientes"]:
            motivos[p["motivo"].split(":")[0]] += 1
            pendientes_totales.append(p)

        promovidas_de_este_padre = resultado["promovidas"]
        for promovida in promovidas_de_este_padre:
            unidad_padre = promovida["unidad_a"]
            señales = _señales_desde_dict(cand_a["señales"])
            nivel_confianza, _revisar, _motivos_conf = calcular_confianza(señales)
            doc = _construir_documento(
                unidad_padre, nivel_confianza,
                sufijo_desambiguador=(promovida["parametro_nombre"] if len(promovidas_de_este_padre) > 1 else None),
                estado="VERIFICADA_AUTOMATICA", documento_sha256=sha256_pdf,
            )
            regla = doc["reglas"][0]
            if regla["concept_id"] in concept_ids_vistos:
                motivos["concept_id_duplicado"] += 1
                continue
            fallos = validar_fichero(doc)
            if fallos:
                motivos["invalida_contra_esquema"] += 1
                pendientes_totales.append({**promovida, "motivo": "regla construida pero no pasa el esquema: " + "; ".join(fallos)})
                continue

            concept_ids_vistos.add(regla["concept_id"])
            nombre_fichero = f"{prefijo_stem}_{regla['concept_id'].split('.')[-1]}.yaml"
            destino = salida_dir / nombre_fichero
            cabecera = (
                "# Generado automáticamente por scripts/verificar_doble_ruta.py — NO EDITAR A MANO.\n"
                f"# Origen: {cand_a.get('documento_identificador')} — {cand_a.get('articulo')}\n"
                "#\n"
                "# ESTADO: VERIFICADA_AUTOMATICA. Dos rutas de extracción independientes\n"
                "# (ruta A: pypdf + interpretación por IA; ruta B: pdfminer.six +\n"
                "# extractor determinista de patrones, sin API) coincidieron en valor y\n"
                "# unidad para este parámetro.\n"
                "# Ver docs/prd/2026-08-21-verificacion-doble-del-corpus.md.\n"
                f"# SHA-256 del PDF oficial: {sha256_pdf}\n\n"
            )
            with destino.open("w", encoding="utf-8") as f:
                f.write(cabecera)
                yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
            convertidas.append(destino)

    with pendientes_ruta.open("w", encoding="utf-8") as f:
        for p in pendientes_totales:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    return {
        "leidas_a": len(candidatas_a),
        "segmentadas_b": len(registros_b),
        "articulos_sin_ruta_b": articulos_sin_ruta_b,
        "verificadas": convertidas,
        "pendientes_dobles": len(pendientes_totales),
        "motivos": motivos,
        "pendientes_ruta": pendientes_ruta,
        "sha256_pdf": sha256_pdf,
    }


def _informe(resultado: dict) -> str:
    lineas = [
        f"Candidatas ruta A leídas:  {resultado['leidas_a']}",
        f"Artículos segmentados por la ruta B: {resultado['segmentadas_b']}",
        f"VERIFICADA_AUTOMATICA:     {len(resultado['verificadas'])}",
        f"Pendientes (doble lectura o hallazgo nuevo): {resultado['pendientes_dobles']}",
        f"SHA-256 del PDF oficial: {resultado['sha256_pdf']}",
    ]
    if resultado["articulos_sin_ruta_b"]:
        lineas.append("\nArtículos sin segmentar por la ruta B (límite conocido, ver segmentador_pdf_b.py):")
        lineas.extend(f"  - {a}" for a in resultado["articulos_sin_ruta_b"])
    if resultado["verificadas"]:
        lineas.append("\nFicheros generados:")
        lineas.extend(f"  - {p.relative_to(RAIZ)}" for p in resultado["verificadas"])
    if resultado["motivos"]:
        lineas.append("\nMotivos de pendiente:")
        for motivo, n in sorted(resultado["motivos"].items(), key=lambda kv: -kv[1]):
            lineas.append(f"  - {motivo}: {n}")
    lineas.append(f"\nPendientes dobles: {resultado['pendientes_ruta'].relative_to(RAIZ)}")
    return "\n".join(lineas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("candidatas_a", type=Path)
    parser.add_argument("pdf_original", type=Path)
    parser.add_argument("--salida", type=Path, default=RAIZ / "normativa" / "es" / "estatal")
    parser.add_argument("--pendientes", type=Path, default=None)
    args = parser.parse_args()

    ruta_candidatas = args.candidatas_a if args.candidatas_a.is_absolute() else RAIZ / args.candidatas_a
    ruta_pdf = args.pdf_original if args.pdf_original.is_absolute() else RAIZ / args.pdf_original
    pendientes_ruta = args.pendientes or (RAIZ / "extraccion" / "estado" / "pendientes" / f"{ruta_candidatas.stem}.verificacion_doble.jsonl")

    resultado = procesar(ruta_candidatas, ruta_pdf, args.salida, pendientes_ruta)
    print(_informe(resultado))


if __name__ == "__main__":
    main()
