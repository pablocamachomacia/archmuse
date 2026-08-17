"""Las 17 validaciones de carga (`NORMATIVE_RESOLUTION.md` §9).

Ninguna regla entra en producción sin pasarlas. Se ejecutan al cargar y en CI.

Las 1-8 vienen de `NORMATIVE_ENGINE.md` §11.1. Las 9-17 son las que la capa
de resolución territorial hace posibles por primera vez; de ellas, dos son el
corazón de este subsistema:

- **La 11** rechaza que una regla declare una materia que no es competencia de
  su nivel territorial. Es la que impide reincidir en el hallazgo M1 de
  `docs/audits/NORMATIVE_AUDIT.md`: la superficie mínima de vivienda es
  competencia autonómica, así que una regla estatal o municipal que la fije
  no se carga.
- **La 12** comprueba que el Documento Básico citado regula la materia
  declarada. Es la que habría impedido las 5 discrepancias M1-M5: hoy nada
  impide emitir `CTE-DB-HE` (ahorro de energía) para una regla de superficie.

Devuelven una lista de fallos (vacía = válido). No lanzan: quien decide qué
hacer con los fallos es el loader, que es fail-closed.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Set

from jsonschema import Draft202012Validator

from . import catalogos
from .registro import registro

# ---------------------------------------------------------------------------
# 1-8 · Estructura, cita y forma (NORMATIVE_ENGINE.md §11.1)
# ---------------------------------------------------------------------------


def validar_esquema(doc: dict) -> List[str]:
    """1. Forma del fichero contra el JSON Schema."""
    validador = Draft202012Validator(catalogos.esquema_regla())
    fallos = []
    for err in sorted(validador.iter_errors(doc), key=lambda e: list(e.path)):
        ruta = "/".join(str(p) for p in err.path) or "(raíz)"
        fallos.append(f"[1] esquema: {ruta}: {err.message}")
    return fallos


def validar_cita(doc: dict) -> List[str]:
    """1b. Toda norma tiene boletín e identificador oficial.

    Redundante con el esquema por diseño: es la invariante que impide que una
    etiqueta de agrupación se presente como código normativo, y merece
    comprobarse aunque el esquema cambie.
    """
    fallos = []
    fuente = (doc.get("norma") or {}).get("fuente") or {}
    if not fuente.get("boletin"):
        fallos.append("[1b] la norma no declara boletín: no es citable")
    if not fuente.get("identificador_oficial"):
        fallos.append("[1b] la norma no declara identificador oficial")
    return fallos


def validar_evaluabilidad(doc: dict) -> List[str]:
    """3. Tipo evaluable ⟹ tiene patrón. No evaluable ⟹ no lo tiene.

    Un tipo `definicion` con patrón de umbral significa que alguien intentó
    evaluar algo que solo se referencia.
    """
    from .modelo import TIPOS_REGLA

    fallos = []
    for r in doc.get("reglas") or []:
        evaluable = TIPOS_REGLA.get(r.get("tipo"), False)
        tiene_patron = bool(r.get("patron"))
        if evaluable and not tiene_patron:
            fallos.append(f"[3] {r.get('concept_id')}: tipo «{r['tipo']}» es evaluable pero no declara patrón")
        if not evaluable and tiene_patron:
            fallos.append(
                f"[3] {r.get('concept_id')}: tipo «{r['tipo']}» no es evaluable pero declara "
                f"patrón «{r['patron']}» — se expone, no se evalúa"
            )
    return fallos


def validar_vigencia(doc: dict) -> List[str]:
    """4. Fechas reales y coherencia temporal: no se puede derogar antes de
    entrar en vigor.

    El formato se comprueba aquí y no en el esquema porque `jsonschema` no
    valida `format: date` por defecto: un "2000-13-45" pasaría el esquema
    como cadena y luego rompería la comparación de vigencias en silencio.
    """
    fallos = []
    registros = [("norma", doc.get("norma") or {})] + [
        (r.get("concept_id", "?"), r) for r in (doc.get("reglas") or [])
    ]
    for nombre, reg in registros:
        v = reg.get("vigencia") or {}
        for campo in ("vigencia_desde", "vigencia_hasta", "registro_desde", "registro_hasta"):
            valor = v.get(campo)
            if valor is None:
                continue
            try:
                date.fromisoformat(str(valor))
            except ValueError:
                fallos.append(f"[4] {nombre}: {campo} «{valor}» no es una fecha ISO (AAAA-MM-DD)")
        desde, hasta = v.get("vigencia_desde"), v.get("vigencia_hasta")
        if desde and hasta and str(hasta) <= str(desde):
            fallos.append(f"[4] {nombre}: vigencia_hasta ({hasta}) no es posterior a vigencia_desde ({desde})")
    return fallos


def validar_parametros(doc: dict) -> List[str]:
    """7. Ningún parámetro es un escalar desnudo: siempre tabla con cadena de
    repliegue declarada.

    Un repliegue sin declarar es el Bug #1 esperando a repetirse en la capa
    normativa.
    """
    fallos = []
    for r in doc.get("reglas") or []:
        p = r.get("parametro")
        if p is None:
            continue
        if not p.get("repliegue"):
            fallos.append(f"[7] {r.get('concept_id')}: parámetro sin cadena de repliegue declarada")
        if not p.get("valores"):
            fallos.append(f"[7] {r.get('concept_id')}: parámetro sin valores")
    return fallos


def validar_hash(doc: dict) -> List[str]:
    """8. Si se declara `hash_texto`, coincide con el literal transcrito.

    Detecta deriva silenciosa entre lo que decimos que dice la norma y lo que
    tenemos guardado.
    """
    import hashlib

    fallos = []
    norma = doc.get("norma") or {}
    declarado = (norma.get("fuente") or {}).get("hash_texto")
    if not declarado:
        return fallos
    real = hashlib.sha256((norma.get("literal") or "").encode("utf-8")).hexdigest()
    if declarado != real:
        fallos.append(f"[8] hash_texto no coincide con el literal (declarado {declarado[:12]}…, real {real[:12]}…)")
    return fallos


# ---------------------------------------------------------------------------
# 9-17 · Territorio, competencia y cobertura (nuevas)
# ---------------------------------------------------------------------------


def validar_ambito_existe(doc: dict) -> List[str]:
    """9. El ámbito declarado existe en el registro geográfico.

    Un código INE mal escrito produce una regla que nunca aplicará a nadie y
    que no da ningún error visible: se queda muda para siempre.
    """
    fallos = []
    reg = registro()
    ambitos = [(doc.get("norma") or {}).get("ambito")] + [
        (r.get("aplicabilidad") or {}).get("ambito") for r in (doc.get("reglas") or [])
    ]
    for a in ambitos:
        if not a:
            continue
        partes = a.split(".")
        if partes[0] != reg.pais:
            fallos.append(f"[9] ámbito «{a}»: país desconocido «{partes[0]}»")
            continue
        if len(partes) >= 2 and partes[1] not in reg.comunidades:
            fallos.append(f"[9] ámbito «{a}»: comunidad «{partes[1]}» no existe")
        if len(partes) >= 3 and partes[2] not in reg.provincias:
            fallos.append(f"[9] ámbito «{a}»: provincia «{partes[2]}» no existe")
        if len(partes) >= 4 and partes[3] not in reg.municipios:
            fallos.append(
                f"[9] ámbito «{a}»: municipio «{partes[3]}» no está en el registro "
                f"(registro incompleto: ver normativa/geografia/es/_registro.yaml)"
            )
    return fallos


def validar_materia(doc: dict) -> List[str]:
    """10. La materia pertenece al catálogo cerrado.

    Si la materia fuera texto libre, la competencia dejaría de ser computable
    y toda la jerarquía territorial se vendría abajo.
    """
    catalogo = catalogos.materias()
    return [
        f"[10] {r.get('concept_id')}: materia «{r.get('materia')}» no está en el catálogo cerrado"
        for r in (doc.get("reglas") or [])
        if r.get("materia") not in catalogo
    ]


def validar_competencia(doc: dict) -> List[str]:
    """11. LA VALIDACIÓN CENTRAL: la materia es competencia del nivel que la
    declara.

    Impide reincidir en el hallazgo M1: la superficie mínima de vivienda es
    competencia autonómica exclusiva, así que una regla estatal o municipal
    que la fije no entra al corpus. Un modelo de "gana la más restrictiva"
    nunca habría detectado esto, porque presupone que ambas capas regulan lo
    mismo.
    """
    comps = catalogos.competencias()
    fallos = []
    for r in doc.get("reglas") or []:
        materia = r.get("materia")
        comp = comps.get(materia)
        if not comp:
            continue  # la 10 ya lo reporta
        nivel = catalogos.nivel_de_ambito((r.get("aplicabilidad") or {}).get("ambito", "es"))
        if comp["modo"] == "exclusivo" and nivel != comp["competencia"]:
            fallos.append(
                f"[11] {r.get('concept_id')}: «{materia}» es competencia {comp['competencia']} "
                f"exclusiva, pero la regla se declara en nivel {nivel}. "
                f"No es una cita mal escrita: ese nivel no regula esta materia."
            )
        if comp["modo"] == "suelo" and nivel != comp["competencia"]:
            permitidos = comp.get("permite_endurecer") or []
            if nivel not in permitidos:
                fallos.append(
                    f"[11] {r.get('concept_id')}: «{materia}» tiene suelo {comp['competencia']} "
                    f"y el nivel {nivel} no está autorizado a endurecerla"
                )
    return fallos


def validar_db_coherente(doc: dict) -> List[str]:
    """12. El Documento Básico citado regula la materia declarada.

    El validador que habría impedido las 5 discrepancias M1-M5. Hoy nada
    impide emitir `CTE-DB-HE` para una regla de superficie mínima de vivienda,
    materia que el CTE no regula en absoluto.
    """
    cat = catalogos.materias()
    db = ((doc.get("norma") or {}).get("articulo") or {}).get("documento_basico")
    if not db:
        return []
    fallos = []
    for r in doc.get("reglas") or []:
        m = cat.get(r.get("materia"))
        if not m:
            continue
        permitidos = m.get("documentos_basicos") or []
        if not permitidos:
            fallos.append(
                f"[12] {r.get('concept_id')}: cita «{db}» pero la materia «{r['materia']}» "
                f"no la regula ningún Documento Básico del CTE"
            )
        elif db not in permitidos:
            fallos.append(
                f"[12] {r.get('concept_id')}: cita «{db}» pero «{r['materia']}» se regula "
                f"en {permitidos}"
            )
    return fallos


def validar_perfil(doc: dict) -> List[str]:
    """13. Los usos, tipologías y tipos de intervención declarados existen.

    Un uso escrito a mano que no está en el árbol no filtra nada: la regla
    aplicaría a todo o a nada sin que nadie se entere.
    """
    tabla_usos, tipos, tipos_int = catalogos.usos(), catalogos.tipologias(), catalogos.tipos_de_intervencion()
    fallos = []
    for r in doc.get("reglas") or []:
        ap = r.get("aplicabilidad") or {}
        for u in ap.get("usos") or []:
            if u not in tabla_usos:
                fallos.append(f"[13] {r.get('concept_id')}: uso «{u}» no existe en el árbol de usos")
        for t in ap.get("tipologias") or []:
            if t not in tipos:
                fallos.append(f"[13] {r.get('concept_id')}: tipología «{t}» no existe")
        for t in ap.get("tipos_de_intervencion") or []:
            if t not in tipos_int:
                fallos.append(f"[13] {r.get('concept_id')}: tipo de intervención «{t}» no existe")
    return fallos


def validar_sin_contradiccion(docs: List[dict]) -> List[str]:
    """14. No hay dos reglas de igual materia, ámbito y perfil compitiendo.

    Si dos reglas del mismo nivel y materia se solapan, el resolver tendría
    que desempatar — y cualquier desempate no declarado (orden de carga,
    alfabético por id) es un criterio oculto disfrazado de determinismo, el
    riesgo que `CONFLICT_ENGINE.md` §2 nombra como el más probable bajo
    presión de entrega. Se prohíbe en carga en vez de resolverse en ejecución.
    """
    vistos: Dict[tuple, str] = {}
    fallos = []
    for doc in docs:
        for r in doc.get("reglas") or []:
            ap = r.get("aplicabilidad") or {}
            clave = (
                r.get("materia"),
                ap.get("ambito"),
                tuple(sorted(ap.get("usos") or [])),
                tuple(sorted(ap.get("tipologias") or [])),
                tuple(sorted(ap.get("tipos_de_intervencion") or [])),
                r.get("patron"),
            )
            if clave in vistos and vistos[clave] != r.get("concept_id"):
                fallos.append(
                    f"[14] {r.get('concept_id')} y {vistos[clave]} compiten por la misma "
                    f"materia, ámbito y perfil: el resolver tendría que desempatar en silencio"
                )
            vistos[clave] = r.get("concept_id")
    return fallos


def validar_aristas(docs: List[dict]) -> List[str]:
    """15. Toda arista apunta a un concept_id existente, y el grafo de
    derogaciones es acíclico.

    Un ciclo de derogaciones no es una situación legal: es un error de
    transcripción, y debe fallar la carga.
    """
    conocidos: Set[str] = set()
    for doc in docs:
        norma = doc.get("norma") or {}
        if norma.get("concept_id"):
            conocidos.add(norma["concept_id"])
        for r in doc.get("reglas") or []:
            conocidos.add(r.get("concept_id"))

    fallos = []
    derogaciones: Dict[str, List[str]] = {}
    for doc in docs:
        for r in doc.get("reglas") or []:
            for a in r.get("aristas") or []:
                if a["destino"] not in conocidos:
                    fallos.append(
                        f"[15] {r.get('concept_id')}: arista «{a['tipo']}» apunta a "
                        f"«{a['destino']}», que no existe en el corpus"
                    )
                if a["tipo"] == "deroga":
                    derogaciones.setdefault(r["concept_id"], []).append(a["destino"])

    # Detección de ciclos por DFS con marcado tricolor.
    BLANCO, GRIS, NEGRO = 0, 1, 2
    color: Dict[str, int] = {}

    def visitar(n: str, camino: List[str]) -> None:
        color[n] = GRIS
        for m in derogaciones.get(n, []):
            if color.get(m, BLANCO) == GRIS:
                fallos.append(f"[15] ciclo de derogaciones: {' -> '.join(camino + [n, m])}")
            elif color.get(m, BLANCO) == BLANCO:
                visitar(m, camino + [n])
        color[n] = NEGRO

    for n in list(derogaciones):
        if color.get(n, BLANCO) == BLANCO:
            visitar(n, [])
    return fallos


def validar_nivel_conocimiento(doc: dict) -> List[str]:
    """16. Toda regla evaluable declara su nivel de conocimiento (1-4).

    Sin él, `EVIDENCE_MODEL.md` §3 no puede calcular la fuerza del tramo y
    toda la cadena de confianza se queda sin su primer eslabón.
    """
    from .modelo import NIVELES_CONOCIMIENTO

    return [
        f"[16] {r.get('concept_id')}: nivel_de_conocimiento «{r.get('nivel_de_conocimiento')}» inválido"
        for r in (doc.get("reglas") or [])
        if r.get("nivel_de_conocimiento") not in NIVELES_CONOCIMIENTO
    ]


def validar_cobertura(manifiesto: dict, ambitos_en_disco: Dict[str, Set[str]]) -> List[str]:
    """17. El manifiesto de cobertura coincide con lo que hay en disco.

    Corta los dos errores opuestos: declarar cobertura que no existe (peligroso
    — el informe afirma más de lo que sabe) y tener cobertura sin declararla
    (desperdicia trabajo hecho y deja al usuario creyendo que no la hay).
    """
    fallos = []
    for entrada in manifiesto.get("cobertura") or []:
        ambito = entrada["ambito"]
        declaradas = entrada.get("materias") or {}
        reales = ambitos_en_disco.get(ambito, set())
        for materia, estado in declaradas.items():
            e = estado.get("estado") if isinstance(estado, dict) else estado
            if e in ("completo", "parcial") and materia not in reales:
                fallos.append(
                    f"[17] {ambito}: declara «{materia}» como {e} pero no hay ninguna "
                    f"regla de esa materia en disco"
                )
        for materia in reales:
            if materia not in declaradas:
                fallos.append(
                    f"[17] {ambito}: hay reglas de «{materia}» en disco pero el manifiesto "
                    f"no declara su cobertura"
                )
    return fallos


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

VALIDACIONES_POR_FICHERO = (
    validar_esquema,
    validar_cita,
    validar_evaluabilidad,
    validar_vigencia,
    validar_parametros,
    validar_hash,
    validar_ambito_existe,
    validar_materia,
    validar_competencia,
    validar_db_coherente,
    validar_perfil,
    validar_nivel_conocimiento,
)

VALIDACIONES_GLOBALES = (validar_sin_contradiccion, validar_aristas)


def validar_fichero(doc: dict) -> List[str]:
    """Todas las validaciones que se pueden decidir mirando un solo fichero."""
    fallos: List[str] = []
    for v in VALIDACIONES_POR_FICHERO:
        fallos.extend(v(doc))
    return fallos


def validar_corpus(docs: List[dict]) -> List[str]:
    """Las que necesitan ver el corpus entero (aristas, contradicciones)."""
    fallos: List[str] = []
    for v in VALIDACIONES_GLOBALES:
        fallos.extend(v(docs))
    return fallos
