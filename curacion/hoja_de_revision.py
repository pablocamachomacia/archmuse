# -*- coding: utf-8 -*-
"""La hoja de revisión de un paquete de curación: el artefacto que se firma.

    python -m curacion.hoja_de_revision [prefijo] [ruta_salida.html]

PRD: `docs/prd/2026-08-22-corpus-firmado-dbsi3-evacuacion.md` §3.2. NO es
YAML: es un documento imprimible en A4 donde el validador marca conforme
(F/L/M, los tres criterios humanos de la ficha §4), corrige al margen o tacha
— y firma de su puño y letra. Dos partes:

1. **La página de decisiones** — una tabla, una fila por regla, con su huella
   de contenido (10 hex). Es la ÚNICA página que se firma.
2. **El anexo de literales** — solo lectura, para cotejar cada fila contra el
   texto oficial. Lleva la huella del paquete al pie, que lo ata a la página
   de decisiones.

La huella impresa por fila es `normativa/firma.py::hash_de_contenido_firmado`
sobre el borrador: `volcar_acta.py firmar` la recomputa y se niega a firmar si
el borrador cambió después de imprimir — el papel manda.
"""
from __future__ import annotations

import html
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from curacion.paquete import (  # noqa: E402
    PREFIJO_POR_DEFECTO, cargar_paquete, exigencia_resumida,
    huella_del_paquete, localizacion,
)

_CSS = """
@page { size: A4; margin: 14mm 12mm 16mm 16mm; }
* { box-sizing: border-box; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 8.2pt; color: #111;
       margin: 0; }
h1 { font-size: 13pt; margin: 0 0 2mm 0; }
h2 { font-size: 10pt; margin: 6mm 0 2mm 0; }
.cajetin { width: 100%; border: 1.2px solid #111; border-collapse: collapse;
           margin-bottom: 3mm; }
.cajetin td { border: 0.4px solid #999; padding: 1.2mm 2mm; vertical-align: middle; }
.cajetin .etiqueta { font-size: 6.2pt; font-weight: bold; color: #555;
                     width: 30mm; text-transform: uppercase; }
.borrador { color: #8A2A2A; border: 1.2px solid #8A2A2A; font-weight: bold;
            padding: 1mm 3mm; float: right; font-size: 8.5pt; }
table.decisiones { width: 100%; border-collapse: collapse; }
table.decisiones th { background: #E9E9E9; border: 0.5px solid #888;
                      padding: 1.2mm 1.5mm; font-size: 6.8pt; text-align: left; }
table.decisiones td { border: 0.5px solid #888; padding: 1.2mm 1.5mm;
                      vertical-align: top; }
table.decisiones tr:nth-child(even) td { background: #F6F6F6; }
.num { white-space: nowrap; font-weight: bold; }
.loc { width: 26mm; font-size: 7pt; }
.exi { font-size: 7.4pt; }
.flm { white-space: nowrap; font-size: 8.5pt; width: 17mm; }
.hue { font-family: "Courier New", monospace; font-size: 6.6pt; width: 15mm; }
.margen { width: 30mm; }
.convenciones { font-size: 7pt; color: #333; margin-top: 3mm; }
.firmas { width: 100%; margin-top: 5mm; border-collapse: collapse; }
.firmas td { border: 0.8px solid #111; height: 24mm; width: 50%;
             vertical-align: top; padding: 1.5mm 2mm; font-size: 7pt; }
.pie { font-size: 6.4pt; color: #555; margin-top: 3mm; }
.salto { page-break-before: always; }
pre.literal { font-family: Helvetica, Arial, sans-serif; font-size: 7.6pt;
              white-space: pre-wrap; border: 0.5px solid #bbb; padding: 2mm;
              background: #FAFAFA; }
.checkbox { display: inline-block; width: 3.2mm; height: 3.2mm;
            border: 0.7px solid #111; margin: 0 0.8mm -0.6mm 1.5mm; }
"""


def _c(texto: str) -> str:
    return html.escape(texto, quote=False)


def generar_hoja(prefijo: str = PREFIJO_POR_DEFECTO,
                 fecha_sesion: str = "2026-08-25") -> str:
    filas = cargar_paquete(prefijo)
    if not filas:
        raise SystemExit("No hay borradores «%s*» que imprimir." % prefijo)
    huella_paquete = huella_del_paquete(filas)
    norma = filas[0].norma
    fuente = norma.get("fuente") or {}
    doc_sha = (fuente.get("documento_sha256") or "")[:12]

    cuerpo = []
    cuerpo.append('<div class="borrador">BORRADOR — PENDIENTE DE VALIDACIÓN</div>')
    cuerpo.append("<h1>Hoja de revisión del corpus normativo</h1>")
    cuerpo.append('<table class="cajetin">')
    for etiqueta, valor in (
        ("Paquete", "DB-SI 3 · Evacuación · uso Residencial Vivienda (%s*)" % prefijo),
        ("Sesión de validación", fecha_sesion),
        ("Fuente", "%s · %s — PDF oficial %s… (%d regla(s))"
         % (fuente.get("identificador_oficial", "—"),
            fuente.get("boletin", "—"), doc_sha, len(filas))),
        ("Huella del paquete", huella_paquete),
    ):
        cuerpo.append('<tr><td class="etiqueta">%s</td><td>%s</td></tr>'
                      % (_c(etiqueta), _c(str(valor))))
    cuerpo.append("</table>")

    cuerpo.append('<table class="decisiones"><tr>'
                  "<th>Nº</th><th>Localización</th><th>Exigencia transcrita</th>"
                  "<th>F · L · M</th><th>Huella</th><th>Corrección al margen</th></tr>")
    for fila in filas:
        cuerpo.append(
            '<tr><td class="num">%s</td><td class="loc">%s</td>'
            '<td class="exi">%s</td>'
            '<td class="flm">F<span class="checkbox"></span> '
            'L<span class="checkbox"></span> M<span class="checkbox"></span></td>'
            '<td class="hue">%s</td><td class="margen"></td></tr>'
            % (fila.numero, _c(localizacion(fila)),
               _c(exigencia_resumida(fila)), fila.huella_corta))
    cuerpo.append("</table>")

    cuerpo.append(
        '<p class="convenciones"><b>Convención de marcado.</b> Conforme = las tres '
        "casillas marcadas (F fidelidad al literal · L localización exacta · M mensaje "
        "útil). Corrección = texto al margen con la inicial del validador: la regla se "
        "firmará con el valor corregido y el registro conservará ambos. Fila tachada = "
        "excluida: vuelve a borrador y no se firma. Lo que genere discusión va a la "
        "lista de dudas, no se marca a medias.</p>")
    cuerpo.append(
        '<p class="convenciones"><b>Declaración.</b> «He cotejado cada fila marcada '
        "conforme contra el texto oficial del DB-SI referido en la cabecera, sobre el "
        "anexo de literales que acompaña a esta hoja.»</p>")
    cuerpo.append('<table class="firmas"><tr>'
                  "<td>Nombre y colegiatura / cargo:<br/><br/>Fecha:<br/><br/>Firma:</td>"
                  "<td>Nombre y colegiatura / cargo:<br/><br/>Fecha:<br/><br/>Firma:</td>"
                  "</tr></table>")
    cuerpo.append('<p class="pie">Esta página de decisiones es la única que se firma. '
                  "El volcado al corpus exige que la huella de cada fila coincida con la "
                  "del borrador en el momento de firmar digitalmente "
                  "(curacion/volcar_acta.py): si el borrador cambia después de imprimir, "
                  "el volcado se niega. Huella del paquete: %s.</p>" % huella_paquete)

    # ----- anexo de literales, solo lectura -----
    cuerpo.append('<div class="salto"></div>')
    cuerpo.append("<h1>Anexo de literales — solo lectura</h1>")
    cuerpo.append('<p class="convenciones">El texto oficial, tal como está transcrito '
                  "en el corpus, para cotejar cada fila. No se firma: la página de "
                  "decisiones manda.</p>")
    vistos = set()
    for fila in filas:
        clave = str(fila.fichero)
        if clave in vistos:
            continue
        vistos.add(clave)
        numeros = ", ".join(f.numero for f in filas if f.fichero == fila.fichero)
        cuerpo.append("<h2>%s (%s) — filas %s</h2>"
                      % (_c(localizacion(fila)), _c(fila.fichero.name), numeros))
        cuerpo.append('<pre class="literal">%s</pre>'
                      % _c(fila.norma.get("literal") or "(sin literal)"))
    cuerpo.append('<p class="pie">Anexo del paquete con huella %s — emitido el %s.</p>'
                  % (huella_paquete, date.today().strftime("%d/%m/%Y")))

    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Hoja de revisión — DB-SI 3 evacuación</title>"
            "<style>%s</style></head><body>%s</body></html>"
            % (_CSS, "\n".join(cuerpo)))


def main(argv: list) -> int:
    prefijo = argv[1] if len(argv) > 1 else PREFIJO_POR_DEFECTO
    destino = Path(argv[2]) if len(argv) > 2 else (
        RAIZ / "docs" / "curacion" / "2026-08-25-dbsi3-evacuacion-p1.html")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(generar_hoja(prefijo), encoding="utf-8")
    print("Hoja escrita en %s" % destino)
    print("Imprimir a A4 desde el navegador (la página de decisiones es la primera).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
