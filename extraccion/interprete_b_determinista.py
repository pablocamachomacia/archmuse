"""Extractor determinista de umbrales normativos — ruta B sin LLM.

Decisión de Pablo, 2026-08-21, sobre la tarea 8 del Prompt 2
(`docs/prd/2026-08-21-verificacion-doble-del-corpus.md`): la ruta B deja de
llamar a la API (bloqueada por saldo insuficiente de la cuenta) y pasa a
reconocer, por patrón, el lenguaje de umbral propio del articulado del CTE
sobre el texto ya des-guionizado de `segmentador_pdf_b.py`.

**Por qué esto es una verificación MÁS fuerte, no un sustituto más débil,
de la independencia LLM↔LLM que proponía el Prompt 2 original.** Dos
lecturas de IA pueden compartir el mismo sesgo de lectura —el mismo tipo
de error, dos veces, porque ambas son el mismo tipo de sistema—. Un
extractor determinista y una IA no pueden fallar igual: uno reconoce por
patrón léxico fijo, la otra por comprensión del lenguaje. Que coincidan es
una señal más fuerte que dos modelos de lenguaje de acuerdo entre sí. Y
deja el pipeline entero ejecutable OFFLINE y a coste cero, coherente con
la política de scripts offline del repositorio (`scripts/validar_corpus.py`
y el resto de `scripts/generar_borrador_corpus.py` ya lo son).

**Catálogo cerrado de patrones, a propósito — no un intento de cubrir
"todo el lenguaje normativo posible".** Patrón reconocido → dato. Patrón
no reconocido → `ClausulaNoReconocida`, con el texto íntegro de la
cláusula, nunca un valor adivinado. Ampliar el catálogo es un acto
deliberado (añadir un patrón, con su propio test), igual que el catálogo
de 5 patrones de `CONSTRAINT_MODEL.md` — nunca una reacción silenciosa a
una cláusula que no encaja hoy.

Una misma cláusula puede producir MÁS de un `ValorExtraido` — es
exactamente lo que exige DB-SUA 7.3 («capacidad mayor que 200 vehículos O
con superficie mayor que 5000 m2»): las dos cifras de una disyunción
tienen que salir las dos, nunca una sola eligiéndose en silencio.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

# --- Cláusulas ---------------------------------------------------------
#
# Mismo criterio grueso que `scripts/generar_borrador_corpus.py::
# _limites_clausula` (agrupar de más, nunca partir una condición
# entrelazada), reimplementado aquí a propósito: `extraccion/` no depende
# de `scripts/` —esa dependencia iría en el sentido contrario del resto
# del árbol— y esto es una utilidad de texto pequeña y estable, no un
# guardián de seguridad que arriesgue divergir en silencio.

_RE_LIMITE_FIN_CLAUSULA = re.compile(r"[.:;]\s+")
_RE_LIMITE_ENUMERACION = re.compile(r"(?:(?<=\s)|^)[a-z]\)\s")


def _normalizar_espacios(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def _limites_clausula(texto: str) -> List[int]:
    posiciones = {0, len(texto)}
    for m in _RE_LIMITE_FIN_CLAUSULA.finditer(texto):
        posiciones.add(m.end())
    for m in _RE_LIMITE_ENUMERACION.finditer(texto):
        posiciones.add(m.start())
    return sorted(posiciones)


def _clausulas(texto: str) -> List[str]:
    norm = _normalizar_espacios(texto)
    limites = _limite_clausula_valida(norm)
    return [c for c in (norm[limites[i]:limites[i + 1]].strip() for i in range(len(limites) - 1)) if c]


def _limite_clausula_valida(texto: str) -> List[int]:
    return _limites_clausula(texto)


# --- Resultados ----------------------------------------------------------

@dataclass(frozen=True)
class ValorExtraido:
    nombre: str
    valor_citado: str
    unidad: str
    comparador: str
    contexto_citado: str


@dataclass(frozen=True)
class ClausulaNoReconocida:
    texto: str
    motivo: str = "patron_no_reconocido_ruta_b"


# --- Catálogo cerrado de patrones ------------------------------------------
#
# Unidades vistas en el corpus real de DB-SUA — no una lista genérica
# inventada por adelantado.
_UNIDAD = r"(m²|m2|km/h|cm|mm|m|%|N|lux|º|veh[íi]culos|espectadores(?:\s+de\s+pie)?|personas|plazas)"
_NUM = r"(\d+(?:[.,]\d+)?)"

#: (regex, comparador, invertir) — `invertir=True` es para los patrones
#: «NÚMERO <comparador> VARIABLE» de una fila de tabla («0,95 < E»): el
#: comparador que ve el regex describe la relación NÚMERO-VARIABLE, así
#: que el comparador real sobre la VARIABLE (lo que se cita) es el
#: opuesto — «0,95 < E» significa E > 0,95, no E < 0,95.
_PATRONES: Tuple[Tuple["re.Pattern[str]", str, bool], ...] = (
    (re.compile(rf"no\s+(?:será|serán)\s+inferior(?:es)?\s+a\s+{_NUM}\s*{_UNIDAD}?", re.IGNORECASE), ">=", False),
    (re.compile(rf"no\s+exced(?:a|erá|an|en)?\s+(?:de|del)?\s*{_NUM}\s*{_UNIDAD}?", re.IGNORECASE), "<=", False),
    (re.compile(rf"al\s+menos\s+{_NUM}\s*{_UNIDAD}?", re.IGNORECASE), ">=", False),
    (re.compile(rf"(?:mayor|superior)\s+que\s+{_NUM}\s*{_UNIDAD}?", re.IGNORECASE), ">", False),
    (re.compile(rf"(?:menor|inferior)\s+que\s+{_NUM}\s*{_UNIDAD}?", re.IGNORECASE), "<", False),
    # «más de N», «menos de N» — encontrado como hueco real al comparar
    # contra la ruta A (DB-SUA 1.2 «resalto... más de 4 mm», DB-SUA 5.1
    # «más de 3000 espectadores de pie»): equivalente a "mayor/menor que"
    # pero con una preposición distinta, muy frecuente en el CTE.
    (re.compile(rf"m[aá]s\s+de\s+{_NUM}\s*{_UNIDAD}?", re.IGNORECASE), ">", False),
    (re.compile(rf"menos\s+de\s+{_NUM}\s*{_UNIDAD}?", re.IGNORECASE), "<", False),
    (re.compile(rf"{_NUM}\s*{_UNIDAD}?\s*,?\s*como\s+m[ií]nimo", re.IGNORECASE), ">=", False),
    (re.compile(rf"como\s+m[ií]nimo,?\s+(?:de\s+)?{_NUM}\s*{_UNIDAD}?", re.IGNORECASE), ">=", False),
    (re.compile(rf"{_NUM}\s*{_UNIDAD}?\s*,?\s*como\s+m[aá]ximo", re.IGNORECASE), "<=", False),
    (re.compile(rf"como\s+m[aá]ximo,?\s+(?:de\s+)?{_NUM}\s*{_UNIDAD}?", re.IGNORECASE), "<=", False),
    # Filas de tabla, símbolo directo: «E > 0,98», «Rd ≤ 15».
    (re.compile(rf"[A-Za-zÀ-ÿ]{{1,3}}\s*>\s*{_NUM}\s*{_UNIDAD}?"), ">", False),
    (re.compile(rf"[A-Za-zÀ-ÿ]{{1,3}}\s*<\s*{_NUM}\s*{_UNIDAD}?"), "<", False),
    (re.compile(rf"[A-Za-zÀ-ÿ]{{1,3}}\s*(?:≥|>=)\s*{_NUM}\s*{_UNIDAD}?"), ">=", False),
    (re.compile(rf"[A-Za-zÀ-ÿ]{{1,3}}\s*(?:≤|<=)\s*{_NUM}\s*{_UNIDAD}?"), "<=", False),
    # Filas de tabla, símbolo invertido: «0,95 < E», «15 ≤ Rd». El
    # comparador de la tupla es el símbolo LITERAL del regex («<» tal como
    # aparece en «0,95 < E»); `invertir=True` es lo que lo convierte en el
    # comparador real sobre la variable citada (E > 0,95, no E < 0,95).
    # Guardar aquí ya la versión invertida sería una doble inversión — el
    # bug real de la primera versión de este módulo, encontrado por
    # `tests/test_interprete_b_determinista.py::test_fila_de_tabla_con_dos_cotas`.
    (re.compile(rf"{_NUM}\s*{_UNIDAD}?\s*<\s*[A-Za-zÀ-ÿ]{{1,3}}"), "<", True),
    (re.compile(rf"{_NUM}\s*{_UNIDAD}?\s*>\s*[A-Za-zÀ-ÿ]{{1,3}}"), ">", True),
    (re.compile(rf"{_NUM}\s*{_UNIDAD}?\s*(?:≤|<=)\s*[A-Za-zÀ-ÿ]{{1,3}}"), "<=", True),
    (re.compile(rf"{_NUM}\s*{_UNIDAD}?\s*(?:≥|>=)\s*[A-Za-zÀ-ÿ]{{1,3}}"), ">=", True),
)

_INVERSA = {">": "<", "<": ">", ">=": "<=", "<=": ">="}


def _slug(texto: str) -> str:
    s = texto.lower()
    s = (s.replace("á", "a").replace("é", "e").replace("í", "i")
         .replace("ó", "o").replace("ú", "u").replace("ñ", "n"))
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "valor"


def _nombre_de(clausula: str, valor: str, posicion: int) -> str:
    palabras = re.findall(r"[A-Za-zÀ-ÿ]+", clausula)[:4]
    return _slug("_".join(palabras) + f"_{valor}_{posicion}")


def extraer(texto: str) -> Tuple[List[ValorExtraido], List[ClausulaNoReconocida]]:
    """Recorre cada cláusula de `texto` y aplica el catálogo cerrado de
    patrones. Una cláusula con patrón reconocido puede producir varios
    `ValorExtraido` (nunca se descarta ninguno para quedarse con "el
    primero"). Una cláusula que cita una cifra pero no encaja en ningún
    patrón vuelve como `ClausulaNoReconocida`, con su texto íntegro — no
    se aproxima ni se adivina."""
    valores: List[ValorExtraido] = []
    no_reconocidas: List[ClausulaNoReconocida] = []

    for clausula in _clausulas(texto):
        encontrados = []
        for patron, comparador, invertir in _PATRONES:
            for m in patron.finditer(clausula):
                numero = m.group(1)
                unidad = (m.group(2) or "").strip() or "adimensional"
                comparador_real = _INVERSA[comparador] if invertir else comparador
                encontrados.append(ValorExtraido(
                    nombre=_nombre_de(clausula, numero, len(encontrados)),
                    valor_citado=f"{numero} {unidad}".strip(),
                    unidad=unidad,
                    comparador=comparador_real,
                    contexto_citado=clausula,
                ))
        if encontrados:
            # Sin duplicar el mismo (valor, comparador) si dos patrones
            # coinciden sobre el mismo número (p.ej. "no excederá de" y un
            # patrón de tabla se solapan en un caso límite).
            vistos = set()
            for v in encontrados:
                clave = (v.valor_citado, v.comparador)
                if clave in vistos:
                    continue
                vistos.add(clave)
                valores.append(v)
        elif re.search(r"\d", clausula):
            no_reconocidas.append(ClausulaNoReconocida(texto=clausula))

    return valores, no_reconocidas
