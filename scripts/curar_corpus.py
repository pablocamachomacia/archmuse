#!/usr/bin/env python3
"""Curación y firma humana del corpus DB-SUA —
docs/prd/2026-08-21-curacion-y-firma-del-corpus-db-sua.md.

Extiende `scripts/revisar_pendientes.py` (Prompt 2 §5.5), pero separa en DOS
ACTOS explícitos lo que aquella herramienta fundía en una sola tecla:

    python scripts/curar_corpus.py resolver <verificacion_doble.jsonl>
    python scripts/curar_corpus.py firmar --curador NOMBRE --sha256-pdf HASH <candidatas_a.jsonl>

**resolver** — recorre cada entrada de `verificacion_doble.jsonl` (Prompt 2:
101 sobre DB-SUA, ninguna de ellas un caso de "coinciden" — ver el docstring
de §1 del PRD, todas exigen decisión humana campo a campo) y pide:

    a  — aprobar (si hay una única lectura, esa; si hay dos, elige cuál)
    r  — rechazar CON MOTIVO (obligatorio; sin motivo no se registra nada)
    e  — editar valor/unidad a mano y aprobar lo corregido
    s  — saltar (no se registra nada; vuelve a salir la próxima vez)

Cada decisión (aprobar/rechazar/editar) queda en
`extraccion/estado/curacion/resoluciones.jsonl` — append-only, con
timestamp, nunca sobreescrito. **`resolver` NUNCA escribe en `normativa/es/`.**
Una candidata aprobada no es todavía una regla del corpus.

**firmar** — la ÚNICA acción que escribe en `normativa/es/`. Toma las
resoluciones «aprobada» que `resolver` dejó en el ledger y, para cada una
que aún no tenga firma, genera su regla `estado: FIRMADA` con:
`documento_sha256` del PDF fuente, versión/fecha del documento (heredadas de
la candidata origen), el bloque `firma: {curador, fecha}` (curador viene de
`--curador`, obligatorio — sin él el comando falla antes de procesar nada),
y el texto `literal` copiado tal cual del PDF. Cada firma queda también en
`extraccion/estado/curacion/firmas.jsonl` — append-only.

**Una regla firmada es inmutable.** Si el fichero que le correspondería ya
existe, `firmar` no lo toca — lo registra como conflicto y sigue con las
demás. Corregir una regla firmada es escribir una nueva versión con su
propio `concept_id`, nunca editar el YAML existente. Esto es a propósito,
no una limitación: `docs/prd/2026-08-21-curacion-y-firma-del-corpus-db-sua.md`
§4 lo pide explícitamente.

--- Sobre la colisión de aplicabilidad genérica (limitación conocida) --------

`_construir_documento` (heredada de `scripts/generar_borrador_corpus.py`) no
deriva `usos`/`tipologias` por regla — todas las reglas de una misma
`materia` quedan con `aplicabilidad: {ambito: es}` genérica. Firmar UNA
regla de una materia dada carga limpio (es el caso que prueba este PRD).
Firmar VARIAS reglas de la MISMA materia+patrón sin usos/tipologías propios
choca con la validación 14 (`normativa/validacion.py::validar_sin_contradiccion`)
y tumba la carga del corpus completo — el mismo límite ya documentado para
`VERIFICADA_AUTOMATICA` en
`docs/design/2026-08-21-limite-aplicabilidad-generica-verificada-automatica.md`.
No se resuelve aquí: es una tarea de especificidad de `aplicabilidad` por
regla, no de esta herramienta de curación. Antes de una sesión de firma real
sobre las 101 entradas, hay que resolverlo o firmar solo una regla por
materia hasta entonces.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extraccion import almacen  # noqa: E402
from extraccion.confianza import calcular_confianza  # noqa: E402
from normativa.validacion import validar_fichero  # noqa: E402
from scripts.generar_borrador_corpus import _construir_documento, _descomponer, _señales_desde_dict  # noqa: E402

ESTADO_CURACION = RAIZ / "extraccion" / "estado" / "curacion"
RESOLUCIONES = ESTADO_CURACION / "resoluciones.jsonl"
FIRMAS = ESTADO_CURACION / "firmas.jsonl"

OPCIONES = ("a", "r", "e", "s")


# --- Utilidades compartidas de ledger ---------------------------------------

def _clave(entrada: dict) -> str:
    return f"{entrada['candidata_padre']}::{entrada['parametro_nombre']}"


def _claves_registradas(ruta: Path) -> set:
    """Claves (`candidata_padre::parametro_nombre`) que ya tienen una línea
    en `ruta` — usado tanto para el ledger de resoluciones como el de
    firmas, mismo criterio de reanudabilidad en los dos actos."""
    if not ruta.exists():
        return set()
    claves = set()
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        r = json.loads(linea)
        claves.add(f"{r['candidata_padre']}::{r['parametro_nombre']}")
    return claves


def _registrar(registro: dict, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ruta_legible(ruta: Path) -> str:
    """Para informes y ledger: relativa a RAIZ cuando es posible (el caso
    real, producción), absoluta si no (tests contra un `tmp_path` fuera del
    árbol del proyecto) — nunca una excepción por `relative_to`."""
    try:
        return str(ruta.relative_to(RAIZ))
    except ValueError:
        return str(ruta)


# =============================================================================
# ACTO 1 — RESOLVER: decisión campo a campo, nunca escribe en normativa/es/.
# =============================================================================

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
    no_reconocidas = pendiente.get("no_reconocidas_b_del_articulo")
    if no_reconocidas:
        salida("  Cláusulas del artículo que la ruta B no reconoció:")
        for c in no_reconocidas:
            salida(f"    - «{c.get('texto', '')}» ({c.get('motivo', '')})")


def resolver_uno(
    pendiente: dict,
    entrada: Callable[[str], str] = input,
    salida: Callable[[str], None] = print,
) -> Optional[dict]:
    """Presenta un pendiente y devuelve la resolución como dict, o `None` si
    no se registra nada (saltar, o una respuesta inválida/incompleta —
    tratada como saltar, nunca como excepción: la sesión sigue con la
    siguiente entrada). `entrada`/`salida` inyectables para probar sin
    terminal real."""
    presentar(pendiente, salida)
    salida(f"Elige [{'/'.join(OPCIONES)}] (a=aprobar, r=rechazar con motivo, e=editar y aprobar, s=saltar): ")
    respuesta = entrada("> ").strip().lower()

    if respuesta not in OPCIONES or respuesta == "s":
        return None

    base = {
        "candidata_padre": pendiente["candidata_padre"],
        "parametro_nombre": pendiente["parametro_nombre"],
        "timestamp": _timestamp(),
    }

    if respuesta == "r":
        motivo = entrada("  Motivo del rechazo (obligatorio): ").strip()
        if not motivo:
            salida("  El motivo es obligatorio — no se registra nada.")
            return None
        return {**base, "decision": "rechazada", "motivo": motivo}

    if respuesta == "a":
        tiene_a = pendiente.get("lectura_a") is not None
        tiene_b = pendiente.get("lectura_b") is not None
        if tiene_a and tiene_b:
            salida("  Hay dos lecturas — ¿cuál apruebas? [a/b]: ")
            cual = entrada("  > ").strip().lower()
            if cual not in ("a", "b"):
                salida(f"  «{cual}» no es una opción válida — no se registra nada.")
                return None
            lectura, fuente = (pendiente["lectura_a"], "A") if cual == "a" else (pendiente["lectura_b"], "B")
        elif tiene_a:
            lectura, fuente = pendiente["lectura_a"], "A"
        elif tiene_b:
            lectura, fuente = pendiente["lectura_b"], "B"
        else:
            salida("  No hay ninguna lectura que aprobar — no se registra nada.")
            return None
        return {
            **base, "decision": "aprobada", "fuente": fuente,
            "valor_final": lectura["valor"], "unidad_final": lectura["unidad"],
            "contexto_citado": lectura.get("contexto_citado", ""),
        }

    # "e": editar campos y aprobar. Alcance deliberadamente acotado a
    # valor/unidad (los únicos campos donde las dos rutas pueden discrepar) —
    # editar el texto citado no tiene sentido: la cita literal sale siempre
    # del PDF, nunca de lo que el curador teclee (PRD §6).
    valor_txt = entrada("  Valor (número): ").strip()
    unidad_txt = entrada("  Unidad: ").strip()
    try:
        valor = float(valor_txt.replace(",", "."))
    except ValueError:
        salida(f"  «{valor_txt}» no es un número — no se registra nada.")
        return None
    if not unidad_txt:
        salida("  La unidad no puede estar vacía — no se registra nada.")
        return None
    contexto = (pendiente.get("lectura_a") or pendiente.get("lectura_b") or {}).get("contexto_citado", "")
    return {
        **base, "decision": "aprobada", "fuente": "editado",
        "valor_final": valor, "unidad_final": unidad_txt, "contexto_citado": contexto,
    }


def procesar_resolver(
    pendientes_ruta: Path,
    entrada: Callable[[str], str] = input,
    salida: Callable[[str], None] = print,
    resoluciones_ruta: Path = RESOLUCIONES,
) -> dict:
    pendientes = [json.loads(linea) for linea in pendientes_ruta.read_text(encoding="utf-8").splitlines() if linea.strip()]
    ya_resueltas = _claves_registradas(resoluciones_ruta)

    resueltas_ahora = 0
    aprobadas = 0
    rechazadas = 0
    for p in pendientes:
        if _clave(p) in ya_resueltas:
            continue
        resolucion = resolver_uno(p, entrada, salida)
        if resolucion is None:
            continue
        _registrar(resolucion, resoluciones_ruta)
        resueltas_ahora += 1
        if resolucion["decision"] == "aprobada":
            aprobadas += 1
        else:
            rechazadas += 1

    return {
        "total_pendientes": len(pendientes),
        "resueltas_ahora": resueltas_ahora,
        "aprobadas": aprobadas,
        "rechazadas": rechazadas,
    }


# =============================================================================
# ACTO 2 — FIRMAR: única acción que escribe en normativa/es/. Inmutable.
# =============================================================================

def _generar_regla_firmada(
    resolucion: dict, cand_padre: dict, salida_dir: Path, sha256_pdf: str, curador: str,
    salida: Callable[[str], None] = print,
) -> Optional[tuple]:
    """Devuelve `(destino, concept_id)`, o `None` si no se pudo firmar
    (esquema inválido o el fichero de destino ya existe — inmutabilidad)."""
    """Construye y escribe la regla `FIRMADA` de una resolución aprobada.
    `cand_padre` es la candidata de la ruta A que originó el pendiente (para
    heredar tipo/patrón/materia/texto_original/vigencia).

    Dos correcciones sobre lo que un primer borrador de esta función hacía
    (encontradas auditando la colisión de validación 14, no en el diseño
    original — ver `docs/design/2026-08-21-limite-aplicabilidad-generica-
    verificada-automatica.md`):

    1. **`patron` de la cláusula, no del artículo padre.** Un artículo
       compuesto (p. ej. `COMBINACION_LOGICA`) puede tener sub-candidatas
       atómicas cuyo patrón real es `UMBRAL_SIMPLE`
       (`_descomponer`/`patron_override`, igual que ya hace
       `scripts/verificar_doble_ruta.py::comparar_padre`). Heredar el patrón
       del padre sin más habría firmado la regla con un patrón que no
       corresponde a su propia exigencia.
    2. **`sufijo_desambiguador` siempre presente**, no solo "si hay más de
       una". Un artículo con muchas sub-candidatas (DB-SUA 1.4 tiene ~40)
       produciría, sin esto, el MISMO `concept_id` para todas —
       `nombre_corto` sale del título del artículo, no del parámetro
       concreto. Siempre incluir `parametro_nombre` es más simple y más
       seguro que intentar saber de antemano cuántas se acabarán firmando.
    """
    parametro_nombre = resolucion["parametro_nombre"]
    unidad_cand = dict(cand_padre)
    unidad_cand["parametros"] = [{
        "nombre": parametro_nombre,
        "valor_citado": f"{resolucion['valor_final']} {resolucion['unidad_final']}".strip(),
        "unidad": resolucion["unidad_final"],
        "comparador": ">=",
        "contexto_citado": resolucion.get("contexto_citado", ""),
    }]
    grupo = next(
        (g for g in _descomponer(cand_padre) if any(p.get("nombre") == parametro_nombre for p in g.parametros)),
        None,
    )
    if grupo and grupo.patron_override:
        unidad_cand["patron"] = grupo.patron_override

    señales = _señales_desde_dict(cand_padre["señales"])
    nivel_confianza, _revisar, _motivos = calcular_confianza(señales)
    fecha_firma = date.today().isoformat()
    doc = _construir_documento(
        unidad_cand, nivel_confianza, sufijo_desambiguador=parametro_nombre,
        estado="FIRMADA", documento_sha256=sha256_pdf,
        firma={"curador": curador, "fecha": fecha_firma},
    )
    doc["reglas"][0]["tags"].append(f"firmado_por:{curador}:{fecha_firma}")

    fallos = validar_fichero(doc)
    if fallos:
        salida(f"  No se ha podido firmar la regla: {'; '.join(fallos)}")
        return None

    concept_id = doc["reglas"][0]["concept_id"]
    # Sin «_»: a diferencia de BORRADOR/VERIFICADA_AUTOMATICA, una regla
    # FIRMADA debe ser descubrible por el loader — es el punto entero de
    # firmarla (ver limitación de aplicabilidad genérica en el docstring
    # del módulo).
    destino = salida_dir / f"firmada_db_sua_{concept_id.split('.')[-1]}.yaml"
    if destino.exists():
        salida(f"  {destino} ya existe — una regla firmada es inmutable, no se sobreescribe. "
               f"Para corregirla, crea una nueva versión con otro concept_id.")
        return None

    with destino.open("w", encoding="utf-8") as f:
        f.write(
            "# Generado automáticamente por scripts/curar_corpus.py (firmar) — NO EDITAR A MANO.\n"
            f"# Regla FIRMADA por {curador}, {fecha_firma} — ver extraccion/estado/curacion/firmas.jsonl\n"
            "# Inmutable: una regla firmada no se edita in situ, se supersede con una versión nueva.\n\n"
        )
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return destino, concept_id


def procesar_firmar(
    resoluciones_ruta: Path,
    candidatas_por_padre: dict,
    salida_dir: Path,
    sha256_pdf: str,
    curador: str,
    salida: Callable[[str], None] = print,
    firmas_ruta: Path = FIRMAS,
) -> dict:
    if not curador:
        raise SystemExit("--curador es obligatorio: ninguna regla se firma sin identificar quién firma.")

    resoluciones = [json.loads(linea) for linea in resoluciones_ruta.read_text(encoding="utf-8").splitlines() if linea.strip()]
    ya_firmadas = _claves_registradas(firmas_ruta)

    firmadas_ahora = []
    sin_candidata_padre = []
    conflictos = []

    for r in resoluciones:
        if r.get("decision") != "aprobada":
            continue
        clave = _clave(r)
        if clave in ya_firmadas:
            continue
        cand_padre = candidatas_por_padre.get(r["candidata_padre"])
        if cand_padre is None:
            sin_candidata_padre.append(clave)
            continue

        generado = _generar_regla_firmada(r, cand_padre, salida_dir, sha256_pdf, curador, salida)
        if generado is None:
            conflictos.append(clave)
            continue
        destino, concept_id = generado

        _registrar({
            "candidata_padre": r["candidata_padre"],
            "parametro_nombre": r["parametro_nombre"],
            "concept_id": concept_id,
            "fichero": _ruta_legible(destino),
            "curador": curador,
            "fecha": date.today().isoformat(),
            "timestamp": _timestamp(),
        }, firmas_ruta)
        firmadas_ahora.append(destino)

    return {
        "total_aprobadas": sum(1 for r in resoluciones if r.get("decision") == "aprobada"),
        "firmadas_ahora": firmadas_ahora,
        "sin_candidata_padre": sin_candidata_padre,
        "conflictos": conflictos,
    }


# --- CLI ---------------------------------------------------------------------

def _informe_resolver(resultado: dict) -> str:
    return (
        f"Pendientes totales:     {resultado['total_pendientes']}\n"
        f"Resueltas esta sesión:  {resultado['resueltas_ahora']} "
        f"({resultado['aprobadas']} aprobadas, {resultado['rechazadas']} rechazadas)"
    )


def _informe_firmar(resultado: dict) -> str:
    lineas = [
        f"Aprobadas en el ledger:  {resultado['total_aprobadas']}",
        f"Firmadas en esta sesión: {len(resultado['firmadas_ahora'])}",
    ]
    if resultado["firmadas_ahora"]:
        lineas.append("Ficheros generados:")
        lineas.extend(f"  - {_ruta_legible(p)}" for p in resultado["firmadas_ahora"])
    if resultado["sin_candidata_padre"]:
        lineas.append(f"Sin candidata de origen (no se pudo firmar): {len(resultado['sin_candidata_padre'])}")
        lineas.extend(f"  - {c}" for c in resultado["sin_candidata_padre"])
    if resultado["conflictos"]:
        lineas.append(f"Conflictos (no firmadas, ver detalle arriba): {len(resultado['conflictos'])}")
    return "\n".join(lineas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="accion", required=True)

    p_resolver = sub.add_parser("resolver", help="Decide campo a campo, sin tocar normativa/es/.")
    p_resolver.add_argument("pendientes", type=Path)
    p_resolver.add_argument("--resoluciones", type=Path, default=RESOLUCIONES)

    p_firmar = sub.add_parser("firmar", help="La única acción que escribe en normativa/es/.")
    p_firmar.add_argument("candidatas_a", type=Path, help="El .jsonl de candidatas de la ruta A, para reconstruir la regla")
    p_firmar.add_argument("--curador", required=True, help="Identificador de quien firma. Obligatorio.")
    p_firmar.add_argument("--sha256-pdf", required=True, dest="sha256_pdf")
    p_firmar.add_argument("--resoluciones", type=Path, default=RESOLUCIONES)
    p_firmar.add_argument("--firmas", type=Path, default=FIRMAS)
    p_firmar.add_argument("--salida", type=Path, default=RAIZ / "normativa" / "es" / "estatal")

    args = parser.parse_args()

    if args.accion == "resolver":
        ruta = args.pendientes if args.pendientes.is_absolute() else RAIZ / args.pendientes
        resultado = procesar_resolver(ruta, resoluciones_ruta=args.resoluciones)
        print(_informe_resolver(resultado))
        return

    # accion == "firmar"
    ruta_candidatas = args.candidatas_a if args.candidatas_a.is_absolute() else RAIZ / args.candidatas_a
    candidatas = almacen.leer(ruta_candidatas)
    por_padre = {c["articulo"]: c for c in candidatas}
    resultado = procesar_firmar(
        args.resoluciones, por_padre, args.salida, args.sha256_pdf, args.curador,
        firmas_ruta=args.firmas,
    )
    print(_informe_firmar(resultado))


if __name__ == "__main__":
    main()
