# -*- coding: utf-8 -*-
"""El volcado del acta de papel al corpus: `transcribir` y `firmar`.

    python -m curacion.volcar_acta transcribir --acta docs/curacion/actas/....pdf
    python -m curacion.volcar_acta firmar --curador "Pablo Camacho"

PRD: `docs/prd/2026-08-22-corpus-firmado-dbsi3-evacuacion.md` §3.3. Dos actos
separados, nunca fusionados en una tecla — mismo contrato que
`scripts/curar_corpus.py` (congelado cuando esto se escribió):

- **`transcribir`** pasa la hoja firmada, fila a fila, al ledger append-only
  `extraccion/estado/curacion/actas_papel.jsonl`. NUNCA escribe en
  `normativa/es/`. Reanudable: una fila ya registrada para el mismo acta no se
  pregunta dos veces.
- **`firmar`** es la ÚNICA acción de este paquete que escribe en
  `normativa/es/estatal/`: para cada fila conforme (o corregida al margen)
  recomputa la huella del borrador y **exige que coincida con la del ledger**
  — si el borrador cambió después de imprimir, se niega: el papel manda.
  Escribe `dbsi3_evacuacion_<slug>.yaml` con `estado: FIRMADA`, el bloque
  `firma` completo (curador, fecha, hash_contenido, validado_por) y SIN
  prefijo `_`: visible para el loader. **Una regla firmada es inmutable**: si
  el destino existe, se registra el conflicto y se sigue, nunca se
  sobrescribe. Correcciones al margen: la regla se firma con el valor
  corregido y el ledger conserva ambos (decisión de Pablo, 2026-08-22).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import yaml  # noqa: E402

from normativa import loader, validacion  # noqa: E402
from normativa.firma import hash_de_contenido_firmado  # noqa: E402

from curacion.paquete import (  # noqa: E402
    CARPETA_CORPUS, PREFIJO_POR_DEFECTO, cargar_paquete, exigencia_resumida,
)

LEDGER_POR_DEFECTO = RAIZ / "extraccion" / "estado" / "curacion" / "actas_papel.jsonl"

DECISIONES = ("conforme", "corregida", "excluida")


# ---------------------------------------------------------------------------
# Ledger append-only
# ---------------------------------------------------------------------------

def _leer_ledger(ruta: Path) -> List[Dict[str, Any]]:
    if not ruta.is_file():
        return []
    lineas = []
    for cruda in ruta.read_text(encoding="utf-8").splitlines():
        if cruda.strip():
            lineas.append(json.loads(cruda))
    return lineas


def _apuntar(ruta: Path, entrada: Dict[str, Any]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    entrada = dict(entrada)
    entrada["timestamp"] = datetime.now(timezone.utc).isoformat()
    with ruta.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entrada, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Correcciones al margen: aplicar «parametro.valores[0].valor = 30» a la regla
# ---------------------------------------------------------------------------

def _aplicar_correccion(regla: Dict[str, Any], campo: str, despues: Any) -> Any:
    """Aplica una corrección por ruta («parametro.valores[0].valor») y devuelve
    el valor anterior. Falla con KeyError/IndexError si la ruta no existe: una
    corrección sobre un campo inexistente es un error de transcripción del
    acta, no algo que inventar."""
    partes: List[Any] = []
    for trozo in campo.split("."):
        while "[" in trozo:
            trozo, resto = trozo.split("[", 1)
            indice, trozo_siguiente = resto.split("]", 1)
            if trozo:
                partes.append(trozo)
            partes.append(int(indice))
            trozo = trozo_siguiente.lstrip(".")
        if trozo:
            partes.append(trozo)
    objetivo: Any = regla
    for parte in partes[:-1]:
        objetivo = objetivo[parte]
    antes = objetivo[partes[-1]]
    objetivo[partes[-1]] = despues
    return antes


# ---------------------------------------------------------------------------
# transcribir — interactivo, ledger, nunca escribe en normativa/es/
# ---------------------------------------------------------------------------

def _preguntar_validadores(acta: str) -> List[Dict[str, Any]]:
    validadores = []
    print("Validadores del acta (línea vacía en el nombre para terminar):")
    while True:
        nombre = input("  Nombre: ").strip()
        if not nombre:
            break
        rol = ""
        while rol not in ("arquitecto_colegiado", "experto_normativo", "curador_interno"):
            rol = input("  Rol [arquitecto_colegiado/experto_normativo/curador_interno]: ").strip()
        colegiatura = input("  Colegiatura (vacío si no aplica): ").strip()
        fecha = input("  Fecha de la sesión (AAAA-MM-DD): ").strip()
        entrada = {"nombre": nombre, "rol": rol, "fecha": fecha, "acta": acta}
        if colegiatura:
            entrada["colegiatura"] = colegiatura
        validadores.append(entrada)
    if not validadores:
        raise SystemExit("Un acta sin validadores no se transcribe.")
    return validadores


def transcribir(acta: str, prefijo: str = PREFIJO_POR_DEFECTO,
                ledger: Path = LEDGER_POR_DEFECTO) -> int:
    if not (RAIZ / acta).is_file():
        raise SystemExit("El acta escaneada «%s» no existe. Escanéala y comítela antes "
                         "de transcribir: el ledger apunta a ella." % acta)
    filas = cargar_paquete(prefijo)
    ya = {(e.get("acta"), e.get("concept_id")) for e in _leer_ledger(ledger)
          if e.get("tipo") == "decision"}
    validadores = _preguntar_validadores(acta)

    for fila in filas:
        if (acta, fila.concept_id) in ya:
            print("%s ya transcrita para este acta — se salta." % fila.numero)
            continue
        print("\n%s  [%s]  huella %s" % (fila.numero, fila.concept_id, fila.huella_corta))
        print("   %s" % exigencia_resumida(fila))
        decision = ""
        while decision not in ("c", "x", "e", "s"):
            decision = input("   [c]onforme / [x] corregida / [e]xcluida / [s]altar: ").strip().lower()
        if decision == "s":
            continue
        correcciones = []
        if decision == "x":
            print("   Correcciones del margen (campo vacío para terminar).")
            while True:
                campo = input("   Campo (p. ej. parametro.valores[0].valor): ").strip()
                if not campo:
                    break
                despues = yaml.safe_load(input("   Valor corregido: "))
                correcciones.append({"campo": campo, "despues": despues})
            if not correcciones:
                print("   Corregida sin correcciones no tiene sentido: vuelve a la fila.")
                continue
        _apuntar(ledger, {
            "tipo": "decision",
            "acta": acta,
            "paquete": prefijo,
            "regla_id": fila.numero,
            "concept_id": fila.concept_id,
            "fichero": fila.fichero.name,
            "huella_fila": fila.huella,
            "decision": {"c": "conforme", "x": "corregida", "e": "excluida"}[decision],
            "correcciones": correcciones,
            "validadores": validadores,
        })
    print("\nLedger: %s" % ledger)
    return 0


# ---------------------------------------------------------------------------
# firmar — la única acción que escribe en normativa/es/
# ---------------------------------------------------------------------------

def firmar_desde_ledger(curador: str,
                        prefijo: str = PREFIJO_POR_DEFECTO,
                        ledger: Path = LEDGER_POR_DEFECTO,
                        carpeta: Path = CARPETA_CORPUS,
                        fecha: Optional[str] = None) -> Dict[str, List[str]]:
    """El núcleo de `firmar`, sin interacción — lo que prueban los tests.

    Devuelve {"firmadas": [...], "conflictos": [...], "rechazadas": [...],
    "derivadas": [...]}: qué se escribió, qué destino ya existía (inmutable),
    qué no pasó las validaciones y qué borrador había cambiado tras imprimir.
    """
    if not curador or not curador.strip():
        raise SystemExit("--curador es obligatorio: una firma sin firmante no es una firma.")
    fecha = fecha or date.today().isoformat()
    decisiones = [e for e in _leer_ledger(ledger)
                  if e.get("tipo") == "decision" and e.get("paquete") == prefijo
                  and e.get("decision") in ("conforme", "corregida")]
    if not decisiones:
        raise SystemExit("El ledger no tiene ninguna decisión firmable para «%s»." % prefijo)

    filas = {f.concept_id: f for f in cargar_paquete(prefijo, carpeta)}
    resultado: Dict[str, List[str]] = {
        "firmadas": [], "conflictos": [], "rechazadas": [], "derivadas": []}

    # Agrupar por fichero de origen: un fichero firmado por NormaFuente,
    # igual que los borradores.
    por_fichero: Dict[str, List[Dict[str, Any]]] = {}
    for decision in decisiones:
        por_fichero.setdefault(decision["fichero"], []).append(decision)

    for nombre_fichero, grupo in sorted(por_fichero.items()):
        slug = Path(nombre_fichero).stem
        for sobrante in ("_paquete_dbsi3_", "_paquete_"):
            if slug.startswith(sobrante):
                slug = slug[len(sobrante):]
                break
        destino = carpeta / ("dbsi3_evacuacion_%s.yaml" % slug)
        if destino.exists():
            resultado["conflictos"].append(
                "%s: el destino %s ya existe — una regla firmada es inmutable; una "
                "corrección exige un concept_id/instancia nueva, no reescribir"
                % (nombre_fichero, destino.name))
            continue

        reglas_firmadas: List[Dict[str, Any]] = []
        norma: Optional[Dict[str, Any]] = None
        for decision in grupo:
            fila = filas.get(decision["concept_id"])
            if fila is None:
                resultado["derivadas"].append(
                    "%s: la regla ya no está en el borrador" % decision["concept_id"])
                continue
            if fila.huella != decision["huella_fila"]:
                resultado["derivadas"].append(
                    "%s: el borrador cambió después de imprimir la hoja (huella %s ≠ "
                    "ledger %s) — el papel manda: reimprime y revalida"
                    % (fila.concept_id, fila.huella_corta,
                       decision["huella_fila"][:10]))
                continue
            norma = dict(fila.norma)
            regla = json.loads(json.dumps(fila.regla, ensure_ascii=False))
            for correccion in decision.get("correcciones") or []:
                antes = _aplicar_correccion(regla, correccion["campo"],
                                            correccion["despues"])
                _apuntar(ledger, {
                    "tipo": "correccion_aplicada", "concept_id": fila.concept_id,
                    "campo": correccion["campo"], "antes": antes,
                    "despues": correccion["despues"], "acta": decision.get("acta")})
            regla["estado"] = "FIRMADA"
            regla["tags"] = [t for t in (regla.get("tags") or [])
                             if t != validacion.TAG_SIN_FIRMAR]
            regla["firma"] = {
                "curador": curador,
                "fecha": fecha,
                "hash_contenido": hash_de_contenido_firmado(fila.norma, regla),
                "validado_por": decision.get("validadores") or [],
            }
            reglas_firmadas.append(regla)

        if not reglas_firmadas or norma is None:
            continue
        doc_final = {"version": 1, "norma": norma, "reglas": reglas_firmadas}
        fallos = validacion.validar_fichero(loader.normalizar_fechas(doc_final))
        if fallos:
            resultado["rechazadas"].append("%s: %s" % (nombre_fichero, "; ".join(fallos)))
            continue
        destino.write_text(
            "# Reglas FIRMADAS del paquete de curación (acta en papel).\n"
            "# Generado por curacion/volcar_acta.py — NO editar a mano: una regla\n"
            "# firmada es inmutable y la validación 20 rechaza cualquier edición.\n"
            + yaml.safe_dump(doc_final, allow_unicode=True, sort_keys=False,
                             width=88),
            encoding="utf-8")
        _apuntar(ledger, {
            "tipo": "firma", "fichero_destino": destino.name, "curador": curador,
            "fecha": fecha,
            "concept_ids": [r["concept_id"] for r in reglas_firmadas]})
        resultado["firmadas"].append(destino.name)

    return resultado


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="curacion.volcar_acta", description=__doc__)
    sub = parser.add_subparsers(dest="orden", required=True)
    p_transcribir = sub.add_parser("transcribir")
    p_transcribir.add_argument("--acta", required=True,
                               help="Ruta (relativa a la raíz) del acta escaneada")
    p_transcribir.add_argument("--paquete", default=PREFIJO_POR_DEFECTO)
    p_firmar = sub.add_parser("firmar")
    p_firmar.add_argument("--curador", required=True)
    p_firmar.add_argument("--paquete", default=PREFIJO_POR_DEFECTO)
    args = parser.parse_args(argv[1:])

    if args.orden == "transcribir":
        return transcribir(args.acta, args.paquete)

    resultado = firmar_desde_ledger(args.curador, args.paquete)
    for clave in ("firmadas", "conflictos", "rechazadas", "derivadas"):
        for linea in resultado[clave]:
            print("%s: %s" % (clave.upper(), linea))
    print("\nRecuerda el orden del manifiesto: primero las reglas (ya sin tag), "
          "después promover la materia — o la validación 18 lo rechaza.")
    return 0 if resultado["firmadas"] and not resultado["rechazadas"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
