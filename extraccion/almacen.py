"""Persistencia de las candidatas extraídas — la pieza que le faltaba a la
Fase 2 para que una corrida real deje algo detrás. `extraccion/pipeline.py`
sigue sin escribir nada (lo sigue verificando `test_extraccion_fronteras.py`
por AST) — este módulo nuevo es lo que un llamante externo usa DESPUÉS de
`extraer()`, igual que `ingesta/almacen.py` es lo que usa después de
descargar un documento. Mismo patrón de versionado por hash, aplicado una
vez más — no un motor nuevo.

**Asimetría deliberada con `ingesta/estado/cache/` (gitignored)**: aquí SÍ
se versiona en git lo que este módulo guarda. La caché de `ingesta/` es
barata de reconstruir (el BOE/`codigotecnico.org` siguen ahí, se puede
volver a descargar). Una candidata no: cuesta una llamada real a la IA por
segmento, y es exactamente el contenido que alguien tiene que poder abrir,
leer y revisar — igual que el corpus definitivo (el árbol "normativa / es"
del paquete `normativa/`) es texto versionado y diffable, no una caché.
Perderlo en un `.gitignore` por copiar el patrón de `ingesta/` sin
pensarlo sería el error real aquí.

**Nunca escribe en el árbol del corpus definitivo ni lo importa** — mismo
test de frontera por AST que ya protege a `extraccion/`
(`test_extraccion_fronteras.py`), ampliado para cubrir también este
módulo. Guardar una candidata pendiente de revisión no es promoverla;
`ReglaCandidata.lista_para_promocion` sigue siendo una etiqueta que nadie
en este paquete actúa sobre.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from ingesta.modelo import DocumentoOficial

from .modelo import ReglaCandidata
from .pipeline import ResultadoExtraccion

RAIZ = Path(__file__).resolve().parent / "estado"


def _rutas(raiz: Optional[Path]) -> tuple[Path, Path]:
    base = raiz or RAIZ
    return base / "ledger.jsonl", base / "candidatas"


def _candidata_a_dict(c: ReglaCandidata) -> dict:
    datos = asdict(c)
    datos["lista_para_promocion"] = c.lista_para_promocion  # property, asdict() no la incluye sola
    return datos


def guardar(
    resultado: ResultadoExtraccion, documento: DocumentoOficial, raiz: Optional[Path] = None
) -> Path:
    """Todas las candidatas de una corrida sobre `documento`, a un único
    `.jsonl` (una línea por candidata — igual de fácil de revisar en un
    diff que el corpus YAML de `normativa/`). Idempotente por
    `(fuente, identificador, hash_texto)`: reintentar sobre la misma
    versión exacta del documento no vuelve a escribir — evita que una
    segunda corrida accidental sobre el mismo texto duplique candidatas o
    pise silenciosamente una revisión ya en curso sobre el fichero anterior.

    **Bug real encontrado y corregido en esta misma sesión**: el ledger
    registraba las cifras de `resultado` (lo que ACABABA de calcular esta
    llamada) incluso cuando el fichero ya existía y por tanto NO se
    reescribía — una corrida de prueba pequeña seguida de la corrida real
    completa dejaba el `.jsonl` con solo las candidatas de la prueba, pero
    el ledger afirmaba que se habían guardado todas las de la corrida real.
    Ahora, si el fichero ya existía, las cifras del ledger se leen del
    fichero tal cual está en disco — el ledger nunca puede afirmar algo
    distinto de lo que hay realmente guardado."""
    ledger, carpeta = _rutas(raiz)
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = f"{documento.fuente}__{documento.identificador}__{documento.hash_texto[:12]}.jsonl"
    destino = carpeta / nombre

    ya_existia = destino.exists()
    if not ya_existia:
        with destino.open("w", encoding="utf-8") as f:
            for candidata in resultado.candidatas:
                f.write(json.dumps(_candidata_a_dict(candidata), ensure_ascii=False) + "\n")
        candidatas_en_disco = [_candidata_a_dict(c) for c in resultado.candidatas]
    else:
        candidatas_en_disco = leer(destino)

    conteo_por_confianza: Dict[str, int] = {}
    for c in candidatas_en_disco:
        conteo_por_confianza[c["nivel_confianza"]] = conteo_por_confianza.get(c["nivel_confianza"], 0) + 1

    registro = {
        "documento_identificador": documento.identificador,
        "fuente": documento.fuente,
        "version": documento.hash_texto,
        "segmentos_totales": resultado.segmentos_totales,
        "candidatas_generadas": len(candidatas_en_disco),
        "por_confianza": conteo_por_confianza,
        "pendientes_revision": sum(1 for c in candidatas_en_disco if c["revisar_manualmente"]),
        "avisos": len(resultado.avisos),
        "ya_existia": ya_existia,
        "ruta": f"candidatas/{nombre}",
    }
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    return destino


def leer(ruta: Path) -> List[dict]:
    """Las candidatas guardadas en un fichero, como dicts — no reconstruye
    `ReglaCandidata` (perdería la distinción "dict crudo leído" vs "objeto
    recién verificado" que `extraccion/modelo.py` existe para mantener;
    quien necesite reinterpretarlas como objetos lo hace explícitamente,
    no de vuelta por este módulo)."""
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as f:
        return [json.loads(linea) for linea in f if linea.strip()]


def listar(raiz: Optional[Path] = None) -> List[Path]:
    _, carpeta = _rutas(raiz)
    if not carpeta.exists():
        return []
    return sorted(carpeta.glob("*.jsonl"))
