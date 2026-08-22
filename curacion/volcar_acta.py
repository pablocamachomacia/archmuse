# -*- coding: utf-8 -*-
"""El volcado del acta de revisión al corpus: `transcribir` y `firmar`.

    python -m curacion.volcar_acta transcribir --acta docs/curacion/actas/....acta.json
    python -m curacion.volcar_acta firmar --curador "Pablo Camacho"

PRD: `docs/prd/2026-08-22-corpus-firmado-dbsi3-evacuacion.md` §3.3, adaptado
el 22-08 al cambio de medio decidido por Pablo: la revisión se hace EN
PANTALLA (`hoja_de_revision.py`) y el acta es el **JSON de revisión** que
descarga el botón «Guardar revisión» — no un escaneo. La atestación (opción A,
aprobada): declaración en pantalla + identidad en el propio JSON + reenvío del
fichero desde el correo del validador citando el código de revisión (los 12
primeros hex de `hash_revision`).

Siguen siendo dos actos separados, nunca fusionados en una tecla — mismo
contrato que `scripts/curar_corpus.py`:

- **`transcribir`** ingiere uno o varios actas JSON al ledger append-only
  `extraccion/estado/curacion/actas_papel.jsonl`. Verifica `hash_revision`
  recomputando el SHA-256 del contenido canónico (la MISMA serialización que
  calcula el JS de la hoja): un acta editada tras descargarse se rechaza.
  NUNCA escribe en `normativa/es/`. Una corrección llega como texto libre del
  validador; el curador la traduce aquí a campo=valor (queda el texto Y la
  traducción en el ledger). Reanudable: (acta, regla) ya registrada no se
  vuelve a ingerir.
- **`firmar`** es la ÚNICA acción que escribe en `normativa/es/estatal/`:
  fusiona las decisiones de todos los actas por regla (una exclusión veta;
  conforme exige serlo en todos; correcciones contradictorias bloquean la
  fila), recomputa la huella del borrador y **exige que coincida con la del
  acta** — si el borrador cambió después de generar la hoja, se niega: el
  acta manda. Escribe `dbsi3_evacuacion_<slug>.yaml` con `estado: FIRMADA`,
  el bloque `firma` completo (curador, fecha, hash_contenido, validado_por
  con todos los validadores) y SIN prefijo `_`. **Inmutable**: destino
  existente = conflicto y se sigue, nunca se sobrescribe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import yaml  # noqa: E402

from normativa import loader, validacion  # noqa: E402
from normativa.firma import hash_de_contenido_firmado  # noqa: E402

from curacion.paquete import (  # noqa: E402
    CARPETA_CORPUS, PREFIJO_POR_DEFECTO, cargar_paquete,
)

LEDGER_POR_DEFECTO = RAIZ / "extraccion" / "estado" / "curacion" / "actas_papel.jsonl"


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
# El acta JSON: serialización canónica y verificación de integridad
# ---------------------------------------------------------------------------

def serializacion_canonica_acta(carga: Dict[str, Any]) -> str:
    """La misma forma que `serializacionCanonica` en el JS de la hoja: claves
    ordenadas, sin espacios, unicode sin escapar, y SIN `hash_revision` (el
    hash no puede hashearse a sí mismo)."""
    sin_hash = {k: v for k, v in carga.items() if k != "hash_revision"}
    return json.dumps(sin_hash, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def verificar_acta(carga: Dict[str, Any], origen: str) -> str:
    """Devuelve el hash de revisión verificado (o computado si el navegador no
    pudo). Un hash declarado que no coincide es un acta editada: se rechaza."""
    if carga.get("tipo") != "revision_corpus":
        raise SystemExit("%s: no es un acta de revisión del corpus." % origen)
    real = hashlib.sha256(
        serializacion_canonica_acta(carga).encode("utf-8")).hexdigest()
    declarado = carga.get("hash_revision")
    if declarado and declarado != real:
        raise SystemExit(
            "%s: hash_revision no coincide (declarado %s…, real %s…) — el "
            "acta se ha editado después de guardarse, o la serialización "
            "canónica del JS y la de Python han divergido. No se ingiere."
            % (origen, declarado[:12], real[:12]))
    return declarado or real


# ---------------------------------------------------------------------------
# transcribir — ingiere el acta JSON al ledger; nunca escribe en normativa/es/
# ---------------------------------------------------------------------------

def _entrada_validador(carga: Dict[str, Any], acta_rel: str) -> Dict[str, Any]:
    v = carga.get("validador") or {}
    entrada = {"nombre": v.get("nombre", ""),
               "rol": v.get("rol", "arquitecto_colegiado"),
               "fecha": v.get("fecha", ""), "acta": acta_rel}
    if v.get("colegiatura"):
        entrada["colegiatura"] = v["colegiatura"]
    if not entrada["nombre"]:
        raise SystemExit("%s: acta sin nombre de validador." % acta_rel)
    return entrada


def _traducir_interactivo(concept_id: str, texto: str) -> List[Dict[str, Any]]:
    print("\nCorrección del validador en %s:\n  «%s»" % (concept_id, texto))
    print("Tradúcela a campos del YAML (campo vacío para terminar).")
    correcciones = []
    while True:
        campo = input("  Campo (p. ej. parametro.valores[0].valor): ").strip()
        if not campo:
            break
        despues = yaml.safe_load(input("  Valor corregido: "))
        correcciones.append({"campo": campo, "despues": despues})
    return correcciones


def ingerir_acta(ruta_acta: Path, prefijo: str = PREFIJO_POR_DEFECTO,
                 ledger: Path = LEDGER_POR_DEFECTO,
                 traducir: Optional[Callable[[str, str], List[dict]]] = None,
                 ) -> Dict[str, int]:
    """El núcleo de `transcribir`, sin interacción salvo `traducir` (que el
    CLI hace interactivo y los tests inyectan). Devuelve el recuento por
    decisión."""
    ruta_acta = ruta_acta if ruta_acta.is_absolute() else RAIZ / ruta_acta
    if not ruta_acta.is_file():
        raise SystemExit("El acta «%s» no existe. Guarda el JSON descargado "
                         "de la hoja (y comítelo) antes de transcribir: el "
                         "ledger apunta a él." % ruta_acta)
    carga = json.loads(ruta_acta.read_text(encoding="utf-8"))
    try:
        acta_rel = ruta_acta.relative_to(RAIZ).as_posix()
    except ValueError:
        acta_rel = ruta_acta.as_posix()
    hash_revision = verificar_acta(carga, acta_rel)

    filas_actuales = {f.concept_id: f for f in cargar_paquete(prefijo)}
    ya = {(e.get("acta"), e.get("concept_id")) for e in _leer_ledger(ledger)
          if e.get("tipo") == "decision"}
    validador = _entrada_validador(carga, acta_rel)

    recuento = {"conforme": 0, "corregida": 0, "excluida": 0,
                "sin_decision": 0, "ya_ingeridas": 0}
    for fila in carga.get("filas") or []:
        cid = fila.get("concept_id", "")
        if (acta_rel, cid) in ya:
            recuento["ya_ingeridas"] += 1
            continue
        if cid in filas_actuales and \
                filas_actuales[cid].huella != fila.get("huella_fila"):
            print("AVISO %s: el borrador actual no coincide con el que se "
                  "revisó — firmar lo bloqueará si no se resuelve." % cid)
        texto = (fila.get("correccion") or "").strip()
        if fila.get("excluida"):
            decision, correcciones = "excluida", []
        elif texto:
            decision = "corregida"
            correcciones = (traducir or (lambda _c, _t: []))(cid, texto)
            if not correcciones:
                # Sin traducción a campo=valor no se puede firmar corregida:
                # queda pendiente, visible, nunca firmada a medias.
                decision = "correccion_pendiente"
        elif fila.get("conforme"):
            decision, correcciones = "conforme", []
        else:
            decision, correcciones = "sin_decision", []
        recuento[decision] = recuento.get(decision, 0) + 1
        _apuntar(ledger, {
            "tipo": "decision", "acta": acta_rel, "paquete": prefijo,
            "regla_id": fila.get("numero"), "concept_id": cid,
            "huella_fila": fila.get("huella_fila"), "decision": decision,
            "criterios": {"f": fila.get("f"), "l": fila.get("l"),
                          "m": fila.get("m")},
            "correccion_texto": texto, "correcciones": correcciones,
            "validadores": [validador],
        })
    _apuntar(ledger, {"tipo": "revision", "acta": acta_rel,
                      "hash_revision": hash_revision,
                      "huella_paquete": carga.get("huella_paquete"),
                      "validador": validador})
    return recuento


# ---------------------------------------------------------------------------
# Correcciones: aplicar «parametro.valores[0].valor = 30» a la regla
# ---------------------------------------------------------------------------

def _aplicar_correccion(regla: Dict[str, Any], campo: str, despues: Any) -> Any:
    """Aplica una corrección por ruta y devuelve el valor anterior. Falla con
    KeyError/IndexError si la ruta no existe: una corrección sobre un campo
    inexistente es un error de traducción del acta, no algo que inventar."""
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
# firmar — fusiona decisiones por regla; la única acción que escribe
# ---------------------------------------------------------------------------

def _fusionar_por_regla(decisiones: List[Dict[str, Any]]
                        ) -> Dict[str, Dict[str, Any]]:
    """Una regla puede venir en varios actas (un validador cada uno). La
    fusión es conservadora: una exclusión veta; conforme exige que TODAS las
    revisiones lo sean (o corregida con la MISMA corrección); correcciones
    contradictorias bloquean la fila con motivo."""
    por_cid: Dict[str, Dict[str, Any]] = {}
    for d in decisiones:
        cid = d["concept_id"]
        registro = por_cid.setdefault(cid, {
            "concept_id": cid, "huellas": set(), "decisiones": [],
            "correcciones": None, "validadores": [], "bloqueo": None})
        registro["huellas"].add(d.get("huella_fila"))
        registro["decisiones"].append(d["decision"])
        for v in d.get("validadores") or []:
            if v not in registro["validadores"]:
                registro["validadores"].append(v)
        if d["decision"] == "corregida":
            correcciones = d.get("correcciones") or []
            if registro["correcciones"] is None:
                registro["correcciones"] = correcciones
            elif registro["correcciones"] != correcciones:
                registro["bloqueo"] = ("correcciones contradictorias entre "
                                       "validadores — resolver a mano")
    for registro in por_cid.values():
        decs = set(registro["decisiones"])
        if registro["bloqueo"]:
            continue
        if len(registro["huellas"]) > 1:
            registro["bloqueo"] = "los actas revisaron borradores distintos"
        elif "excluida" in decs:
            registro["bloqueo"] = "excluida por un validador"
        elif "correccion_pendiente" in decs:
            registro["bloqueo"] = ("corrección sin traducir a campo=valor — "
                                   "vuelve a transcribir y tradúcela")
        elif "sin_decision" in decs:
            registro["bloqueo"] = "sin decisión de algún validador"
        elif not decs <= {"conforme", "corregida"}:
            registro["bloqueo"] = "decisiones no firmables: %s" % sorted(decs)
    return por_cid


def firmar_desde_ledger(curador: str,
                        prefijo: str = PREFIJO_POR_DEFECTO,
                        ledger: Path = LEDGER_POR_DEFECTO,
                        carpeta: Path = CARPETA_CORPUS,
                        fecha: Optional[str] = None) -> Dict[str, List[str]]:
    """El núcleo de `firmar`, sin interacción — lo que prueban los tests.

    Devuelve {"firmadas": [...], "conflictos": [...], "rechazadas": [...],
    "derivadas": [...], "bloqueadas": [...]}.
    """
    if not curador or not curador.strip():
        raise SystemExit("--curador es obligatorio: una firma sin firmante no es una firma.")
    fecha = fecha or date.today().isoformat()
    decisiones = [e for e in _leer_ledger(ledger)
                  if e.get("tipo") == "decision" and e.get("paquete") == prefijo]
    if not decisiones:
        raise SystemExit("El ledger no tiene ninguna decisión para «%s»." % prefijo)

    filas = {f.concept_id: f for f in cargar_paquete(prefijo, carpeta)}
    fusion = _fusionar_por_regla(decisiones)
    resultado: Dict[str, List[str]] = {
        "firmadas": [], "conflictos": [], "rechazadas": [], "derivadas": [],
        "bloqueadas": []}

    # Agrupar por fichero de origen: un fichero firmado por NormaFuente,
    # igual que los borradores.
    por_fichero: Dict[str, List[Dict[str, Any]]] = {}
    for cid, registro in fusion.items():
        fila = filas.get(cid)
        if fila is None:
            resultado["derivadas"].append(
                "%s: la regla ya no está en el borrador" % cid)
            continue
        if registro["bloqueo"]:
            resultado["bloqueadas"].append("%s: %s" % (cid, registro["bloqueo"]))
            continue
        por_fichero.setdefault(fila.fichero.name, []).append(registro)

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
        for registro in sorted(grupo, key=lambda r: r["concept_id"]):
            fila = filas[registro["concept_id"]]
            (huella_acta,) = registro["huellas"]
            if fila.huella != huella_acta:
                resultado["derivadas"].append(
                    "%s: el borrador cambió después de generar la hoja "
                    "(huella %s ≠ acta %s) — el acta manda: regenera la hoja "
                    "y revalida" % (fila.concept_id, fila.huella_corta,
                                    str(huella_acta)[:10]))
                continue
            norma = dict(fila.norma)
            regla = json.loads(json.dumps(fila.regla, ensure_ascii=False))
            for correccion in registro["correcciones"] or []:
                antes = _aplicar_correccion(regla, correccion["campo"],
                                            correccion["despues"])
                _apuntar(ledger, {
                    "tipo": "correccion_aplicada",
                    "concept_id": fila.concept_id,
                    "campo": correccion["campo"], "antes": antes,
                    "despues": correccion["despues"]})
            regla["estado"] = "FIRMADA"
            regla["tags"] = [t for t in (regla.get("tags") or [])
                             if t != validacion.TAG_SIN_FIRMAR]
            regla["firma"] = {
                "curador": curador,
                "fecha": fecha,
                "hash_contenido": hash_de_contenido_firmado(fila.norma, regla),
                "validado_por": registro["validadores"],
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
            "# Reglas FIRMADAS del paquete de curación (acta JSON de revisión\n"
            "# en pantalla). Generado por curacion/volcar_acta.py — NO editar a\n"
            "# mano: una regla firmada es inmutable y la validación 20 rechaza\n"
            "# cualquier edición.\n"
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
    p_transcribir.add_argument("--acta", required=True, nargs="+",
                               help="Acta(s) JSON descargada(s) de la hoja, "
                                    "ruta relativa a la raíz")
    p_transcribir.add_argument("--paquete", default=PREFIJO_POR_DEFECTO)
    p_firmar = sub.add_parser("firmar")
    p_firmar.add_argument("--curador", required=True)
    p_firmar.add_argument("--paquete", default=PREFIJO_POR_DEFECTO)
    args = parser.parse_args(argv[1:])

    if args.orden == "transcribir":
        for ruta in args.acta:
            recuento = ingerir_acta(Path(ruta), args.paquete,
                                    traducir=_traducir_interactivo)
            print("%s: %s" % (ruta, ", ".join(
                "%s=%d" % (k, v) for k, v in recuento.items() if v)))
        print("Ledger: %s" % LEDGER_POR_DEFECTO)
        return 0

    resultado = firmar_desde_ledger(args.curador, args.paquete)
    for clave in ("firmadas", "conflictos", "rechazadas", "derivadas", "bloqueadas"):
        for linea in resultado[clave]:
            print("%s: %s" % (clave.upper(), linea))
    print("\nRecuerda el orden del manifiesto: primero las reglas (ya sin tag), "
          "después promover la materia — o la validación 18 lo rechaza.")
    return 0 if resultado["firmadas"] and not resultado["rechazadas"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
