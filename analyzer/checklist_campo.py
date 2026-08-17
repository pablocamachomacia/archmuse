# Checklist de inspección en campo (2026-08-16,
# docs/prd/2026-08-16-checklist-inspeccion-campo.md): guía de comprobación para cuando el arquitecto
# visita la parcela física, NO una verificación automática nueva. Ninguna de las 4 categorías del
# encargo original (pendientes reales, viento dominante, impacto acústico real, vegetación protegida)
# tiene hoy una fuente de datos en ArchMuse -- cada ítem es un recordatorio de "esto lo compruebas
# tú en el terreno", y solo lleva una `nota` cuando existe un dato REAL disponible (Catastro/Overpass,
# ya recogido por `analyzer.sitio` para este proyecto) -- nunca un valor inventado. Mismo criterio de
# honestidad que `evaluator.get_missing_data_warnings`.
#
# Función pura, sin I/O: `datos_parcela` ya viene resuelto por quien llama (`app.py`, que junta
# `proyecto` + `sitio.datos` -- ver docstring de `generar_checklist_campo`). Esto la hace trivial de
# testear con distintas combinaciones de datos disponibles/ausentes.

from typing import Any, Dict, List, Optional


def _lista_nombres(items: List[dict], max_items: int = 3) -> str:
    """"3, 4 y 2 más" -- mismo criterio de recorte que el resto de ArchMuse usa para listas largas de
    Overpass (nunca vuelca 40 nombres en una nota que se supone breve)."""
    nombres = [it.get("nombre") for it in items if it.get("nombre")]
    if not nombres:
        return ""
    mostrados = nombres[:max_items]
    resto = len(nombres) - len(mostrados)
    texto = ", ".join(mostrados)
    if resto > 0:
        texto += " y %d más" % resto
    return texto


def _nota_superficie(datos: Dict[str, Any]) -> Optional[str]:
    superficie = datos.get("superficie_m2")
    if not superficie:
        return None
    return "Superficie según Catastro: %.0f m² — confirma que coincide con la medición en campo." % superficie


def _nota_colindantes(datos: Dict[str, Any]) -> Optional[str]:
    colindantes = datos.get("colindantes") or []
    if not colindantes:
        return None
    return "%d edificio(s) colindante(s) registrado(s) en Overpass (radio 80 m)." % len(colindantes)


def _nota_alturas_colindantes(datos: Dict[str, Any]) -> Optional[str]:
    colindantes = datos.get("colindantes") or []
    alturas = [c.get("altura_plantas") for c in colindantes if c.get("altura_plantas")]
    if not alturas:
        return None
    return "Alturas conocidas de colindantes (plantas): %s — el resto no tiene dato de altura en OSM." % (
        ", ".join(str(a) for a in alturas)
    )


def _nota_viales(datos: Dict[str, Any]) -> Optional[str]:
    viales = datos.get("viales") or []
    if not viales:
        return None
    nombres = _lista_nombres(viales)
    return "%d vía(s) registrada(s) cerca de la parcela%s." % (len(viales), (": " + nombres) if nombres else "")


def _nota_orientacion(datos: Dict[str, Any]) -> Optional[str]:
    norte = datos.get("norte_grados")
    if norte is None:
        return None
    return "Orientación declarada en el proyecto: %s° respecto al norte." % norte


def _nota_densidad(datos: Dict[str, Any]) -> Optional[str]:
    densidad = datos.get("densidad_urbana")
    if not densidad:
        return None
    return "Densidad urbana clasificada como '%s' según la ubicación del proyecto." % densidad


def _nota_zona_cte(datos: Dict[str, Any]) -> Optional[str]:
    zona = datos.get("zona_cte")
    if not zona:
        return None
    return "Zona climática CTE: %s." % zona


def _nota_zonas_verdes(datos: Dict[str, Any]) -> Optional[str]:
    zonas = datos.get("zonas_verdes") or []
    if not zonas:
        return None
    nombres = _lista_nombres(zonas)
    return "%d zona(s) verde(s)/espacio(s) registrados cerca%s." % (len(zonas), (": " + nombres) if nombres else "")


def _nota_referencia_catastral(datos: Dict[str, Any]) -> Optional[str]:
    ref = datos.get("referencia_catastral")
    if not ref:
        return None
    return "Referencia catastral registrada: %s." % ref


def _item(item_id: str, texto: str, nota: Optional[str] = None) -> dict:
    return {"id": item_id, "texto": texto, "nota": nota}


def generar_checklist_campo(datos_parcela: Dict[str, Any]) -> List[dict]:
    """4 bloques de comprobación para la visita física a la parcela. `datos_parcela` (dict, todas las
    claves opcionales -- un proyecto sin sitio real enlazado puede pasar un dict vacío o parcial, ver
    `app.py:checklist_campo`): `ciudad`, `tipologia`, `zona_cte`, `densidad_urbana`, `norte_grados`
    (del `proyecto` guardado), `superficie_m2`, `referencia_catastral`, `colindantes`, `viales`,
    `zonas_verdes` (de `sitio.datos`, si hay sitio real enlazado).

    Nunca lanza, nunca devuelve un bloque vacío: si falta un dato, el ítem correspondiente se queda
    sin `nota` (recordatorio genérico), nunca con un valor inventado en su lugar."""
    datos = datos_parcela or {}

    topografia_suelo = {
        "id": "topografia_suelo",
        "titulo": "Topografía y suelo",
        "items": [
            _item("pendiente_terreno", "Comprueba la pendiente real del terreno y compárala con la que asume el proyecto."),
            _item(
                "limites_fisicos_catastro",
                "Verifica que los linderos físicos (vallas, muros, setos) coinciden con el polígono catastral.",
                _nota_superficie(datos),
            ),
            _item("muros_contencion", "Localiza muros de contención existentes y valora su estado."),
            _item("tipo_suelo", "Anota el tipo de suelo aparente y cualquier indicio de humedad o nivel freático alto."),
            _item(
                "acceso_maquinaria",
                "Evalúa el acceso para maquinaria de obra (anchura de calle, pendiente de acceso, giro).",
                _nota_viales(datos),
            ),
        ],
    }

    suministros_servidumbres = {
        "id": "suministros_servidumbres",
        "titulo": "Suministros y servidumbres",
        "items": [
            _item("acometidas", "Localiza las acometidas existentes (agua, electricidad, gas, saneamiento)."),
            _item("arquetas_registros", "Fotografía arquetas y registros visibles en el entorno de la parcela."),
            _item("tendidos_aereos", "Comprueba si hay tendidos eléctricos/telefónicos aéreos que puedan condicionar la altura del proyecto."),
            _item(
                "servidumbres_paso",
                "Identifica posibles servidumbres de paso o de luces/vistas con parcelas colindantes.",
                _nota_colindantes(datos),
            ),
            _item("vegetacion_protegida", "Comprueba si hay arbolado o vegetación protegida a conservar."),
        ],
    }

    bioclimatica_entorno = {
        "id": "bioclimatica_entorno",
        "titulo": "Bioclimática y entorno real",
        "items": [
            _item(
                "sombras_colindantes",
                "Valora la sombra real que proyectan los edificios colindantes, especialmente en invierno.",
                _nota_alturas_colindantes(datos),
            ),
            _item("viento_dominante", "Observa el viento dominante en la parcela (dirección e intensidad aproximada)."),
            _item(
                "impacto_acustico",
                "Evalúa el ruido de tráfico u otras fuentes cercanas en distintos momentos del día.",
                _nota_viales(datos),
            ),
            _item("vistas_privacidad", "Comprueba vistas reales y privacidad hacia/desde las parcelas colindantes."),
            _item(
                "orientacion_real",
                "Confirma la orientación real de la parcela con brújula o GPS en el propio terreno.",
                _nota_orientacion(datos),
            ),
        ],
    }

    potencial_valor_cultural = {
        "id": "potencial_valor_cultural",
        "titulo": "Potencial del proyecto y valor cultural",
        "items": [
            _item(
                "integracion_urbana",
                "Valora la integración del proyecto con la escala y el carácter real del entorno urbano.",
                _nota_densidad(datos),
            ),
            _item(
                "autosuficiencia_solar",
                "Valora el potencial de autosuficiencia solar según la orientación y las sombras reales del entorno.",
                _nota_zona_cte(datos),
            ),
            _item(
                "zonas_verdes_cercanas",
                "Identifica zonas verdes o espacios públicos cercanos que aporten valor al proyecto.",
                _nota_zonas_verdes(datos),
            ),
            _item("valor_patrimonial", "Valora si el entorno tiene valor patrimonial o cultural relevante (catalogación, BIC, entorno histórico)."),
            _item(
                "referencia_catastral_confirmar",
                "Confirma en campo la referencia catastral (placa o mojón, si existe).",
                _nota_referencia_catastral(datos),
            ),
        ],
    }

    return [topografia_suelo, suministros_servidumbres, bioclimatica_entorno, potencial_valor_cultural]
