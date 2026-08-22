# -*- coding: utf-8 -*-
"""La hoja de revisión de un paquete de curación: el artefacto que se firma.

    python -m curacion.hoja_de_revision [prefijo] [ruta_salida.html]

PRD: `docs/prd/2026-08-22-corpus-firmado-dbsi3-evacuacion.md` §3.2, rehecha el
22-08 con los criterios de presentación de Pablo: la hoja la lee un arquitecto
que no conoce ArchMuse y la revisa en veinte minutos. Eso manda sobre todo lo
demás:

- **Solo la selección de la sesión** (`SELECCION_P1`): lo evaluable que la
  skill consume. Ni definiciones ni el resto del paquete, que sigue en
  borrador.
- **La exigencia se escribe como la escribiría un arquitecto.** La redacción
  de cada regla está curada aquí (`CONTENIDO`), pero **cada cifra sale del
  YAML del borrador, nunca de la prosa**: los casos se resuelven contra
  `parametro.valores` y un caso que no encuentre su fila hace fallar la
  generación en vez de imprimir otra cosa. Prohibido volcar claves del YAML
  («condicion:», «por_ciento», nombres de fichero) — hay un test que lo
  comprueba sobre la hoja real.
- **Casos tabulados**, no frases con puntos medios.
- **Sin huellas hexadecimales en la vista del validador**: el anclaje técnico
  (huella por fila, huella del paquete, hash del PDF) baja a una línea de
  letra pequeña al pie de la MISMA página firmada — la firma manuscrita tiene
  que cubrir el ancla, o el ancla no vale — y al anexo técnico.
- **El anexo trae solo el fragmento literal de cada regla**, no apartados
  enteros del CTE. Cada fragmento se comprueba mecánicamente como subcadena
  del literal transcrito (normalizando espacios): un fragmento que no esté en
  el literal no se imprime, revienta.

El volcado (`volcar_acta.py`) exige que la huella de cada fila coincida con la
del ledger: si el borrador cambia después de imprimir, se niega — el papel
manda.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from curacion.paquete import (  # noqa: E402
    PREFIJO_POR_DEFECTO, SELECCION_P1, Fila, cargar_paquete,
    huella_del_paquete, localizacion, seleccionar,
)

_CID = "es.rd_314_2006.seguridad_incendio."

#: Cómo se lee cada unidad del corpus en la hoja. Cerrado: una unidad que no
#: esté aquí hace fallar la generación — mejor que imprimir «por_ciento».
_UNIDADES = {"m": "m", "personas": "personas", "por_ciento": "%",
             "m2_por_persona": "m²/persona"}

#: Redacción curada por regla: la frase de entrada y la etiqueta humana de
#: cada caso (el VALOR de cada caso se busca en `parametro.valores` del
#: borrador, nunca se escribe aquí). `fragmentos` son las subcadenas exactas
#: del literal que el anexo muestra — se verifican contra el literal.
CONTENIDO: Dict[str, Dict[str, Any]] = {
    _CID + "longitud_recorrido_evacuacion": {
        "intro": ("Longitud máxima de los recorridos de evacuación hasta una "
                  "salida de planta, según el número de salidas de la planta o "
                  "recinto y el caso que concurra."),
        "casos": [
            ("Una única salida — caso general",
             {"numero_salidas": "una", "condicion": "general"}),
            ("Una única salida — uso Aparcamiento",
             {"numero_salidas": "una", "condicion": "uso_aparcamiento"}),
            ("Una única salida — salida directa a espacio exterior seguro y "
             "ocupación de 25 personas como máximo",
             {"numero_salidas": "una",
              "condicion": "salida_directa_exterior_seguro_ocupacion_max_25"}),
            ("Más de una salida — caso general",
             {"numero_salidas": "varias", "condicion": "general"}),
            ("Más de una salida — zonas con ocupantes que duermen; "
             "hospitalización o tratamiento intensivo; escuela infantil o "
             "enseñanza primaria",
             {"numero_salidas": "varias",
              "condicion": "ocupantes_que_duermen_u_hospitalario_o_escuela"}),
            ("Más de una salida — espacios al aire libre con riesgo de "
             "incendio irrelevante",
             {"numero_salidas": "varias",
              "condicion": "espacio_al_aire_libre_riesgo_irrelevante"}),
        ],
        "fragmentos": [
            "La longitud de los recorridos de evacuación hasta una salida de "
            "planta no excede de 25 m, excepto en los casos que se indican a "
            "continuación: - 35 m en uso Aparcamiento; - 50 m si se trata de "
            "una planta, incluso de uso Aparcamiento, que tiene una salida "
            "directa al espacio exterior seguro y la ocupación no excede de "
            "25 personas, o bien de un espacio al aire libre en el que el "
            "riesgo de incendio sea irrelevante, por ejemplo, una cubierta de "
            "edificio, una terraza, etc.",
            "La longitud de los recorridos de evacuación hasta alguna salida "
            "de planta no excede de 50 m, excepto en los casos que se indican "
            "a continuación: - 35 m en zonas en las que se prevea la "
            "presencia de ocupantes que duermen, o en plantas de "
            "hospitalización o de tratamiento intensivo en uso Hospitalario y "
            "en plantas de escuela infantil o de enseñanza primaria. - 75 m "
            "en espacios al aire libre en los que el riesgo de declaración de "
            "un incendio sea irrelevante, por ejemplo, una cubierta de "
            "edificio, una terraza, etc.",
        ],
    },
    _CID + "incremento_recorridos_extincion_automatica": {
        "intro_con_valor": (
            "La longitud máxima admisible de los recorridos se puede aumentar "
            "un {valor} cuando el sector de incendio está protegido con una "
            "instalación automática de extinción."),
        "casos": [],
        "fragmentos": [
            "(1) La longitud de los recorridos de evacuación que se indican "
            "se puede aumentar un 25% cuando se trate de sectores de incendio "
            "protegidos con una instalación automática de extinción.",
        ],
    },
    _CID + "ocupacion_maxima_salida_unica": {
        "intro": ("Ocupación máxima que admite una planta o recinto con una "
                  "única salida."),
        "casos": [
            ("Caso general", {"caso": "general"}),
            ("Salida de un edificio de viviendas, contando el conjunto del "
             "edificio",
             {"caso": "salida_de_edificio_de_viviendas_conjunto_del_edificio"}),
            ("Zonas cuya evacuación hasta la salida de planta salva más de "
             "2 m en sentido ascendente",
             {"caso": "evacuacion_ascendente_salva_mas_de_2_m"}),
        ],
        "fragmentos": [
            "La ocupación no excede de 100 personas, excepto en los casos que "
            "se indican a continuación: - 500 personas en el conjunto del "
            "edificio, en el caso de salida de un edificio de viviendas; - 50 "
            "personas en zonas desde las que la evacuación hasta una salida "
            "de planta deba salvar una altura mayor que 2 m en sentido "
            "ascendente;",
        ],
    },
    _CID + "altura_evacuacion_maxima_salida_unica": {
        "intro": ("Altura de evacuación máxima de la planta para poder "
                  "disponer una única salida."),
        "casos": [
            ("Evacuación descendente", {"sentido": "descendente"}),
            ("Evacuación ascendente", {"sentido": "ascendente"}),
        ],
        "fragmentos": [
            "La altura de evacuación descendente de la planta considerada no "
            "excede de 28 m, excepto en uso Residencial Público, en cuyo caso "
            "es, como máximo, la segunda planta por encima de la de salida de "
            "edificio(2), o de 10 m cuando la evacuación sea ascendente.",
        ],
    },
    _CID + "anchura_minima_elementos_evacuacion": {
        "intro": ("Anchura mínima libre de los elementos de un recorrido de "
                  "evacuación."),
        "casos": [
            ("Puertas y pasos", {"elemento": "puertas_y_pasos"}),
            ("Pasillos y rampas", {"elemento": "pasillos_y_rampas"}),
            ("Pasillos previstos para 10 personas como máximo, usuarios "
             "habituales",
             {"elemento": "pasillos_hasta_10_personas_usuarios_habituales"}),
        ],
        "fragmentos": [
            "Puertas y pasos: A ≥ P / 200(1) ≥ 0,80 m(2).",
            "Pasillos y rampas: A ≥ P / 200 ≥ 1,00 m(3)(4)(5)",
            "(5) La anchura mínima es 0,80 m en pasillos previstos para 10 "
            "personas, como máximo, y estas sean usuarios habituales.",
        ],
    },
    _CID + "anchura_hoja_puerta_evacuacion": {
        "intro": ("Anchura admisible de cada hoja de puerta en un recorrido "
                  "de evacuación."),
        "casos": [
            ("Anchura mínima de la hoja", {"limite": "minimo"}),
            ("Anchura máxima de la hoja", {"limite": "maximo"}),
        ],
        "fragmentos": [
            "La anchura de toda hoja de puerta no debe ser menor que 0,60 m, "
            "ni exceder de 1,23 m.",
        ],
    },
}

_CSS = """
@page { size: A4; margin: 13mm 12mm 14mm 16mm; }
* { box-sizing: border-box; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 8.4pt; color: #111;
       margin: 0; }
h1 { font-size: 13pt; margin: 0 0 2mm 0; }
h2 { font-size: 9.5pt; margin: 5mm 0 1.5mm 0; }
.cajetin { width: 100%; border: 1.2px solid #111; border-collapse: collapse;
           margin-bottom: 2.5mm; }
.cajetin td { border: 0.4px solid #999; padding: 1.1mm 2mm; vertical-align: middle; }
.cajetin .etiqueta { font-size: 6.2pt; font-weight: bold; color: #555;
                     width: 30mm; text-transform: uppercase; }
.borrador { color: #8A2A2A; border: 1.2px solid #8A2A2A; font-weight: bold;
            padding: 1mm 3mm; float: right; font-size: 8.5pt; }
table.decisiones { width: 100%; border-collapse: collapse; }
table.decisiones th { background: #E9E9E9; border: 0.5px solid #888;
                      padding: 1.1mm 1.5mm; font-size: 6.6pt; text-align: left;
                      vertical-align: top; }
table.decisiones > tbody > tr > td { border: 0.5px solid #888;
                      padding: 1.2mm 1.5mm; vertical-align: top; }
.num { white-space: nowrap; font-weight: bold; width: 8mm; }
.loc { width: 23mm; font-size: 7.2pt; }
.intro { font-size: 8pt; margin: 0 0 1mm 0; }
table.casos { border-collapse: collapse; margin: 0.5mm 0 0 0; width: 100%; }
table.casos td { border: 0.3px solid #bbb; padding: 0.7mm 1.5mm;
                 font-size: 7.6pt; }
table.casos td.v { text-align: right; white-space: nowrap; width: 17mm;
                   font-weight: bold; }
.flm { white-space: nowrap; font-size: 9pt; width: 21mm; text-align: center; }
.margen { width: 27mm; }
.convenciones { font-size: 6.9pt; color: #333; margin-top: 2.5mm; }
.firmas { width: 100%; margin-top: 3.5mm; border-collapse: collapse; }
.firmas td { border: 0.8px solid #111; height: 21mm; width: 50%;
             vertical-align: top; padding: 1.5mm 2mm; font-size: 7pt; }
.anclaje { font-size: 5.6pt; color: #777; margin-top: 2.5mm;
           font-family: "Courier New", monospace; }
.salto { page-break-before: always; }
blockquote.literal { font-size: 8pt; border-left: 2px solid #999;
                     margin: 1mm 0 3mm 0; padding: 1mm 3mm; background: #FAFAFA; }
.pie { font-size: 6.4pt; color: #555; margin-top: 3mm; }
.checkbox { display: inline-block; width: 3.4mm; height: 3.4mm;
            border: 0.7px solid #111; margin: 0 0.6mm -0.7mm 1.2mm; }
"""


def _c(texto: str) -> str:
    return html.escape(texto, quote=False)


def _normalizar(texto: str) -> str:
    return " ".join((texto or "").split())


def _valor_humano(valor: Any, unidad: Optional[str]) -> str:
    """«25 m», «0,80 m», «100 personas», «25%». Nunca una clave del YAML."""
    if isinstance(valor, float) and valor != int(valor):
        cifra = ("%.2f" % valor).replace(".", ",")
    else:
        cifra = "%d" % int(valor)
    legible = _UNIDADES[unidad or ""]  # KeyError a propósito si es desconocida
    return cifra + legible if legible == "%" else "%s %s" % (cifra, legible)


def _valor_de_caso(fila: Fila, filtro: Dict[str, str]) -> str:
    """El valor de la fila de `parametro.valores` que casa con el filtro. La
    cifra sale SIEMPRE del YAML; si ninguna fila casa, la generación falla."""
    parametro = fila.regla.get("parametro") or {}
    for valores in parametro.get("valores") or []:
        if all(valores.get(k) == v for k, v in filtro.items()):
            return _valor_humano(valores["valor"], parametro.get("unidad"))
    raise LookupError("%s: ningún valor del parámetro casa con %s"
                      % (fila.concept_id, filtro))


def _celda_exigencia(fila: Fila) -> str:
    contenido = CONTENIDO.get(fila.concept_id)
    if contenido is None:
        # Regla sin redacción curada (paquetes futuros): se usa la explicación
        # técnica del propio YAML, que ya es prosa de arquitecto.
        return '<p class="intro">%s</p>' % _c(
            fila.regla.get("explicacion_tecnica") or fila.regla.get("nombre") or "")
    if "intro_con_valor" in contenido:
        parametro = fila.regla.get("parametro") or {}
        valor = _valor_humano(parametro["valores"][0]["valor"],
                              parametro.get("unidad"))
        intro = contenido["intro_con_valor"].format(valor=valor)
    else:
        intro = contenido["intro"]
    piezas = ['<p class="intro">%s</p>' % _c(intro)]
    if contenido["casos"]:
        piezas.append('<table class="casos">')
        for etiqueta, filtro in contenido["casos"]:
            piezas.append('<tr><td>%s</td><td class="v">%s</td></tr>'
                          % (_c(etiqueta), _c(_valor_de_caso(fila, filtro))))
        piezas.append("</table>")
    return "".join(piezas)


def _fragmentos(fila: Fila) -> List[str]:
    """Los fragmentos del literal que el anexo muestra, verificados como
    subcadena del literal transcrito (espacios normalizados)."""
    contenido = CONTENIDO.get(fila.concept_id)
    literal = _normalizar(fila.norma.get("literal") or "")
    if contenido is None:
        return [fila.norma.get("literal") or "(sin literal)"]
    for fragmento in contenido["fragmentos"]:
        if _normalizar(fragmento) not in literal:
            raise AssertionError(
                "%s: el fragmento del anexo no está en el literal transcrito — "
                "no se imprime un anexo que no sea cita: %r"
                % (fila.concept_id, fragmento[:80]))
    return list(contenido["fragmentos"])


def generar_hoja(prefijo: str = PREFIJO_POR_DEFECTO,
                 seleccion=None,
                 fecha_sesion: str = "2026-08-25") -> str:
    filas = seleccionar(cargar_paquete(prefijo), seleccion)
    if not filas:
        raise SystemExit("No hay borradores «%s*» que imprimir." % prefijo)
    huella_paquete = huella_del_paquete(filas)
    fuente = filas[0].norma.get("fuente") or {}

    cuerpo = []
    cuerpo.append('<div class="borrador">BORRADOR — PENDIENTE DE VALIDACIÓN</div>')
    cuerpo.append("<h1>Hoja de revisión del corpus normativo</h1>")
    cuerpo.append('<table class="cajetin">')
    for etiqueta, valor in (
        ("Paquete", "DB-SI 3 · Evacuación de ocupantes · uso Residencial "
                    "Vivienda — sesión p1 (%d reglas; el resto de lo "
                    "transcrito queda en borrador)" % len(filas)),
        ("Sesión de validación", fecha_sesion),
        ("Fuente", "%s — Documento Básico SI (%s), texto oficial de "
                   "codigotecnico.org" % (fuente.get("identificador_oficial", "—"),
                                          fuente.get("boletin", "—"))),
        ("Qué se valida", "Que cada exigencia de la tabla dice lo mismo que "
                          "el fragmento oficial del anexo adjunto — ni un "
                          "número ni una condición de más o de menos."),
    ):
        cuerpo.append('<tr><td class="etiqueta">%s</td><td>%s</td></tr>'
                      % (_c(etiqueta), _c(str(valor))))
    cuerpo.append("</table>")

    cuerpo.append(
        '<table class="decisiones"><thead><tr>'
        "<th>Nº</th><th>Dónde está<br/>en el DB-SI</th>"
        "<th>Exigencia transcrita (revisar contra el fragmento del anexo)</th>"
        "<th>Conforme — marcar las tres:<br/>"
        "<b>F</b> fiel al literal oficial<br/>"
        "<b>L</b> la referencia es exacta<br/>"
        "<b>M</b> un arquitecto la entiende</th>"
        "<th>Corrección al margen<br/>(con su inicial)</th></tr></thead><tbody>")
    for fila in filas:
        cuerpo.append(
            '<tr><td class="num">%s</td><td class="loc">%s</td>'
            "<td>%s</td>"
            '<td class="flm">F<span class="checkbox"></span> '
            'L<span class="checkbox"></span> M<span class="checkbox"></span></td>'
            '<td class="margen"></td></tr>'
            % (fila.numero, _c(localizacion(fila)), _celda_exigencia(fila)))
    cuerpo.append("</tbody></table>")

    cuerpo.append(
        '<p class="convenciones"><b>Convención.</b> Conforme = las tres casillas. '
        "Corrección = el valor o el texto correcto escrito al margen con la inicial "
        "del validador: la regla se registrará con la corrección y quedará constancia "
        "de ambos valores. Fila tachada = excluida, vuelve a borrador. Lo dudoso no "
        "se marca a medias: va a la lista de dudas de la sesión. "
        "<b>Declaración:</b> «He cotejado cada fila marcada conforme contra el "
        "fragmento del texto oficial que la acompaña en el anexo.»</p>")
    cuerpo.append('<table class="firmas"><tr>'
                  "<td>Nombre y colegiatura / cargo:<br/><br/>Fecha:<br/><br/>Firma:</td>"
                  "<td>Nombre y colegiatura / cargo:<br/><br/>Fecha:<br/><br/>Firma:</td>"
                  "</tr></table>")
    cuerpo.append(
        '<p class="anclaje">Anclaje técnico del volcado (no requiere revisión): '
        "PDF fuente %s… · %s · paquete %s…</p>"
        % ((fuente.get("documento_sha256") or "")[:12],
           " · ".join("%s %s" % (f.numero, f.huella_corta) for f in filas),
           huella_paquete[:12]))

    # ----- anexo: solo el fragmento exacto de cada regla -----
    cuerpo.append('<div class="salto"></div>')
    cuerpo.append("<h1>Anexo — el texto oficial, regla a regla</h1>")
    cuerpo.append('<p class="convenciones">Para cada fila, el fragmento exacto del '
                  "DB-SI del que sale. Solo lectura: las marcas van en la página de "
                  "decisiones, que es la que se firma.</p>")
    for fila in filas:
        cuerpo.append("<h2>%s — %s</h2>" % (fila.numero, _c(localizacion(fila))))
        for fragmento in _fragmentos(fila):
            cuerpo.append('<blockquote class="literal">%s</blockquote>'
                          % _c(_normalizar(fragmento)))
    cuerpo.append('<p class="pie">Huella completa del paquete: %s · '
                  "SHA-256 del PDF fuente: %s</p>"
                  % (huella_paquete, fuente.get("documento_sha256") or "—"))

    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Hoja de revisión — DB-SI 3 evacuación</title>"
            "<style>%s</style></head><body>%s</body></html>"
            % (_CSS, "\n".join(cuerpo)))


def main(argv: list) -> int:
    prefijo = argv[1] if len(argv) > 1 else PREFIJO_POR_DEFECTO
    destino = Path(argv[2]) if len(argv) > 2 else (
        RAIZ / "docs" / "curacion" / "2026-08-25-dbsi3-evacuacion-p1.html")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(generar_hoja(prefijo, seleccion=SELECCION_P1),
                       encoding="utf-8")
    print("Hoja escrita en %s" % destino)
    print("Imprimir a A4 desde el navegador (la página de decisiones es la primera).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
