# -*- coding: utf-8 -*-
"""La hoja de revisión de un paquete de curación — EN PANTALLA.

    python -m curacion.hoja_de_revision [prefijo] [ruta_salida.html]

PRD: `docs/prd/2026-08-22-corpus-firmado-dbsi3-evacuacion.md` §3.2 y adéndum.
Tercera iteración de presentación (22-08, feedback directo de Pablo): la
página la revisa un colegiado que no conoce ArchMuse, así que manda la
claridad:

- **Una sola pregunta por regla**, sin siglas: «Correcta» / «Necesita
  corrección» (con su campo de texto) / «Excluir». Los tres criterios de la
  ficha (fidelidad, localización, mensaje) no desaparecen: quedan resumidos
  en la guía y colapsan en «Correcta» — marcarla es afirmarlos.
- **Comprobación a un clic**: el texto oficial va VISIBLE bajo cada regla, y
  cada regla enlaza al PDF oficial de codigotecnico.org abierto en su página
  (`#page=N`). El PDF en línea es byte a byte el mismo que el transcrito —
  lo garantiza `documento_sha256` — así que la página no puede desviar.
- **Nada se pierde**: el estado se guarda solo en el navegador
  (localStorage) con cada marca; cerrar y volver no borra nada. «Guardar
  revisión» además descarga el acta JSON.
- Guía de tres pasos arriba, «Regla N de 6» y contador de progreso junto al
  botón, que no se habilita hasta responder las 6 y firmar la declaración.

La trazabilidad no cambia (opción A aprobada): el acta JSON lleva marcas,
correcciones, identidad, la huella de contenido de cada fila (en los datos,
no en la vista) y `hash_revision` (SHA-256 del contenido canónico, calculado
en el navegador con la MISMA serialización que replica `volcar_acta.py`).
Tras guardar, la página muestra el código de revisión que el validador cita
al reenviar el fichero desde su correo.

La redacción es la curada de la iteración anterior: `CONTENIDO` no cambia, y
cada cifra sale de `parametro.valores` del YAML — un caso que no casa
revienta la generación. Prohibido volcar claves del YAML; hay un test.
"""
from __future__ import annotations

import html
import json
import sys
from datetime import date
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

#: El PDF oficial del DB-SI en codigotecnico.org — el MISMO fichero del que se
#: transcribió (documento_sha256 del corpus == sha256 de esta descarga,
#: verificado el 2026-08-22). `#page=N` lo abre en la página de cada regla.
PDF_OFICIAL = "https://www.codigotecnico.org/pdf/Documentos/SI/DBSI.pdf"

#: Cómo se lee cada unidad del corpus en la hoja. Cerrado: una unidad que no
#: esté aquí hace fallar la generación — mejor que imprimir «por_ciento».
_UNIDADES = {"m": "m", "personas": "personas", "por_ciento": "%",
             "m2_por_persona": "m²/persona"}

#: Redacción curada por regla: frase de entrada, etiqueta humana de cada caso
#: (el VALOR se busca en `parametro.valores` del borrador, nunca se escribe
#: aquí), fragmentos exactos del literal para la cita visible, y la página del
#: PDF oficial donde comprobarlo.
CONTENIDO: Dict[str, Dict[str, Any]] = {
    _CID + "longitud_recorrido_evacuacion": {
        "intro": ("Longitud máxima de los recorridos de evacuación hasta una "
                  "salida de planta, según el número de salidas de la planta o "
                  "recinto y el caso que concurra."),
        "pagina_pdf": 25,
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
        "pagina_pdf": 25,
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
        "pagina_pdf": 24,
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
        "pagina_pdf": 25,
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
        "pagina_pdf": 26,
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
        "pagina_pdf": 26,
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
* { box-sizing: border-box; }
body { font-family: Georgia, "Times New Roman", serif; background: #fff;
       color: #1a1a1a; margin: 0; font-size: 17px; line-height: 1.55; }
.envoltura { max-width: 840px; margin: 0 auto; padding: 36px 26px 90px; }
header h1 { font-family: Helvetica, Arial, sans-serif; font-size: 25px;
            margin: 0 0 6px; }
.chip { display: inline-block; color: #8A2A2A; border: 1.5px solid #8A2A2A;
        font-family: Helvetica, Arial, sans-serif; font-weight: bold;
        font-size: 12.5px; padding: 3px 10px; border-radius: 3px;
        margin-bottom: 12px; }
.resumen { color: #444; font-size: 15px; margin: 0; }
.fuentes { font-family: Helvetica, Arial, sans-serif; font-size: 14.5px;
           margin: 10px 0 0; }
.fuentes a { color: #0B57D0; }
.guia { background: #F3F6FB; border-radius: 10px; padding: 16px 20px;
        font-size: 15.5px; margin: 24px 0 8px; }
.guia ol { margin: 6px 0 0; padding-left: 22px; }
.guia li { margin: 4px 0; }
section.regla { border: 1px solid #e2e2e2; border-radius: 12px;
                padding: 20px 22px; margin: 22px 0; }
.regla-cabecera { font-family: Helvetica, Arial, sans-serif;
                  display: flex; justify-content: space-between;
                  align-items: baseline; gap: 12px; flex-wrap: wrap;
                  margin-bottom: 6px; }
.regla-cabecera .numero { font-weight: bold; font-size: 14px; color: #0B57D0; }
.regla-cabecera .donde { font-size: 13.5px; color: #666; }
p.intro { margin: 8px 0 10px; font-weight: bold; font-size: 17px; }
.caso { display: flex; justify-content: space-between; gap: 16px;
        padding: 5px 2px; border-bottom: 1px dotted #ddd; font-size: 15.5px; }
.caso:last-of-type { border-bottom: none; }
.caso .v { font-family: Helvetica, Arial, sans-serif; font-weight: bold;
           white-space: nowrap; }
.oficial { margin-top: 14px; }
.oficial .titulo-oficial { font-family: Helvetica, Arial, sans-serif;
                           font-size: 13.5px; color: #555; font-weight: bold;
                           text-transform: uppercase; letter-spacing: 0.4px; }
blockquote.literal { border-left: 3px solid #C9A227; background: #FBF8EF;
                     margin: 6px 0; padding: 8px 14px; font-size: 15px; }
.comprobar { font-family: Helvetica, Arial, sans-serif; font-size: 14.5px; }
.comprobar a { color: #0B57D0; font-weight: bold; }
.decision { margin-top: 14px; font-family: Helvetica, Arial, sans-serif;
            font-size: 15.5px; display: flex; flex-wrap: wrap;
            gap: 10px 22px; }
.decision label { cursor: pointer; padding: 7px 12px; border: 1px solid #ccc;
                  border-radius: 8px; }
.decision input { margin-right: 6px; }
.decision label:has(input:checked) { border-color: #1B5E20;
                                     background: #EDF6EE; }
.decision label.excluir:has(input:checked) { border-color: #8A2A2A;
                                             background: #FBEFEF; }
textarea.correccion { display: none; width: 100%; margin-top: 10px;
                      min-height: 56px; font: inherit; font-size: 15.5px;
                      padding: 8px 10px; border: 1px solid #C9A227;
                      border-radius: 8px; background: #FFFDF5; }
section.regla.con-correccion textarea.correccion { display: block; }
#panel { border: 1px solid #e2e2e2; border-radius: 12px; padding: 20px 22px;
         margin-top: 30px; font-family: Helvetica, Arial, sans-serif; }
#panel h2 { font-size: 19px; margin: 0 0 4px; }
#progreso { font-size: 15px; color: #555; margin: 0 0 14px; }
.campos { display: flex; flex-wrap: wrap; gap: 12px 18px; margin: 0 0 14px; }
.campos label { display: flex; flex-direction: column; font-size: 13.5px;
                color: #555; gap: 4px; }
.campos input, .campos select { font-size: 15.5px; padding: 7px 9px;
                                border: 1px solid #ccc; border-radius: 6px;
                                min-width: 200px; }
.declaracion { font-size: 15px; margin: 6px 0 18px; }
#guardar { font-size: 16.5px; font-weight: bold; padding: 12px 26px;
           border-radius: 8px; border: none; background: #1B5E20; color: #fff;
           cursor: pointer; }
#guardar:disabled { background: #bbb; cursor: not-allowed; }
#autoguardado { font-size: 13px; color: #777; margin-left: 12px; }
#resultado { display: none; background: #EDF6EE; border: 1px solid #1B5E20;
             border-radius: 8px; padding: 14px 18px; margin-top: 18px;
             font-size: 15.5px; }
#resultado code { font-size: 17px; font-weight: bold; }
footer { color: #888; font-size: 13px; margin-top: 34px;
         font-family: Helvetica, Arial, sans-serif; }
"""

_JS = """
'use strict';
const DATOS = JSON.parse(document.getElementById('datos-paquete').textContent);
const HUELLAS = Object.fromEntries(
  DATOS.filas.map(f => [f.concept_id, f.huella_fila]));
const CLAVE_LOCAL = 'archmuse-revision-' + DATOS.paquete;

function serializacionCanonica(v) {
  // La MISMA forma que json.dumps(sort_keys=True, separators=(',',':'),
  // ensure_ascii=False) en volcar_acta.py. Si divergen, el volcado rechaza
  // el acta — mejor un rechazo ruidoso que un acta inverificable.
  if (v === null || typeof v === 'number' || typeof v === 'boolean')
    return JSON.stringify(v);
  if (typeof v === 'string') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(serializacionCanonica).join(',') + ']';
  const claves = Object.keys(v).sort();
  return '{' + claves.map(k =>
    JSON.stringify(k) + ':' + serializacionCanonica(v[k])).join(',') + '}';
}

async function sha256Hex(texto) {
  if (!(window.crypto && crypto.subtle)) return null;
  const datos = new TextEncoder().encode(texto);
  const hash = await crypto.subtle.digest('SHA-256', datos);
  return Array.from(new Uint8Array(hash))
    .map(b => b.toString(16).padStart(2, '0')).join('');
}

function decisionDe(sec) {
  const elegido = sec.querySelector('input[type=radio]:checked');
  return elegido ? elegido.value : 'sin_responder';
}

function estadoDeFila(sec) {
  const decision = decisionDe(sec);
  const texto = sec.querySelector('textarea').value.trim();
  return {
    numero: sec.dataset.numero,
    concept_id: sec.dataset.concept,
    huella_fila: HUELLAS[sec.dataset.concept],
    decision: decision,
    conforme: decision === 'correcta',
    correccion: decision === 'corregir' ? texto : '',
    excluida: decision === 'excluir',
  };
}

// --- Guardado automático en este navegador: nada se pierde al cerrar. ------
function guardarLocal() {
  try {
    const estado = {campos: {}, filas: {}};
    for (const id of ['v-nombre', 'v-colegiatura', 'v-rol', 'v-fecha'])
      estado.campos[id] = document.getElementById(id).value;
    estado.campos['v-declaracion'] =
      document.getElementById('v-declaracion').checked;
    document.querySelectorAll('section.regla').forEach(sec => {
      estado.filas[sec.dataset.concept] = {
        decision: decisionDe(sec),
        correccion: sec.querySelector('textarea').value,
      };
    });
    localStorage.setItem(CLAVE_LOCAL, JSON.stringify(estado));
    document.getElementById('autoguardado').textContent =
      'Cambios guardados en este navegador.';
  } catch (e) { /* sin almacenamiento local: la descarga sigue funcionando */ }
}

function restaurarLocal() {
  try {
    const crudo = localStorage.getItem(CLAVE_LOCAL);
    if (!crudo) return;
    const estado = JSON.parse(crudo);
    for (const [id, valor] of Object.entries(estado.campos || {})) {
      const campo = document.getElementById(id);
      if (!campo) continue;
      if (campo.type === 'checkbox') campo.checked = !!valor;
      else if (valor) campo.value = valor;
    }
    document.querySelectorAll('section.regla').forEach(sec => {
      const fila = (estado.filas || {})[sec.dataset.concept];
      if (!fila) return;
      if (fila.decision && fila.decision !== 'sin_responder') {
        const radio = sec.querySelector(
          'input[type=radio][value=' + fila.decision + ']');
        if (radio) radio.checked = true;
      }
      sec.querySelector('textarea').value = fila.correccion || '';
    });
  } catch (e) { /* nada que restaurar */ }
}

function refrescar() {
  document.querySelectorAll('section.regla').forEach(sec => {
    sec.classList.toggle('con-correccion', decisionDe(sec) === 'corregir');
  });
  const filas = Array.from(document.querySelectorAll('section.regla'));
  const listas = filas.filter(sec => {
    const d = decisionDe(sec);
    if (d === 'sin_responder') return false;
    if (d === 'corregir')
      return sec.querySelector('textarea').value.trim() !== '';
    return true;
  }).length;
  document.getElementById('progreso').textContent =
    'Revisadas ' + listas + ' de ' + filas.length + ' reglas.' +
    (listas < filas.length
      ? ' El botón se activa al responderlas todas.' : '');
  const nombre = document.getElementById('v-nombre').value.trim();
  const coleg = document.getElementById('v-colegiatura').value.trim();
  const decl = document.getElementById('v-declaracion').checked;
  document.getElementById('guardar').disabled =
    !(listas === filas.length && nombre && coleg && decl);
}

document.addEventListener('input', () => { refrescar(); guardarLocal(); });
document.addEventListener('change', () => { refrescar(); guardarLocal(); });

document.getElementById('guardar').addEventListener('click', async () => {
  const filas = Array.from(document.querySelectorAll('section.regla'))
    .map(estadoDeFila);
  const carga = {
    tipo: 'revision_corpus',
    paquete: DATOS.paquete,
    generada: DATOS.generada,
    documento_sha256: DATOS.documento_sha256,
    huella_paquete: DATOS.huella_paquete,
    validador: {
      nombre: document.getElementById('v-nombre').value.trim(),
      colegiatura: document.getElementById('v-colegiatura').value.trim(),
      rol: document.getElementById('v-rol').value,
      fecha: document.getElementById('v-fecha').value,
    },
    declaracion_aceptada: true,
    filas: filas,
  };
  const hash = await sha256Hex(serializacionCanonica(carga));
  carga.hash_revision = hash;

  const nombreFichero = DATOS.paquete + '.' +
    carga.validador.nombre.toLowerCase().normalize('NFD')
      .replace(/[^a-z ]/g, '').trim().split(/ +/).slice(-1)[0] + '.acta.json';
  const blob = new Blob([JSON.stringify(carga, null, 2)],
                        {type: 'application/json'});
  const enlace = document.createElement('a');
  enlace.href = URL.createObjectURL(blob);
  enlace.download = nombreFichero;
  enlace.click();
  guardarLocal();

  const res = document.getElementById('resultado');
  res.style.display = 'block';
  const conformes = filas.filter(f => f.conforme).length;
  res.innerHTML =
    'Revisión guardada y descargada como <b>' + nombreFichero + '</b> — ' +
    conformes + ' de ' + filas.length + ' reglas correctas.<br/>' +
    (hash
      ? 'Código de revisión: <code>' + hash.slice(0, 12) + '</code>. ' +
        'Envíe el fichero descargado desde su propio correo citando este ' +
        'código: es lo que ata su identidad al contenido exacto.'
      : 'Este navegador no permite calcular el código de revisión; envíe ' +
        'igualmente el fichero desde su correo y el código se calculará al ' +
        'incorporarlo.');
});

if (!document.getElementById('v-fecha').value)
  document.getElementById('v-fecha').value = DATOS.hoy;
restaurarLocal();
refrescar();
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


def _cuerpo_exigencia(fila: Fila) -> str:
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
    for etiqueta, filtro in contenido["casos"]:
        piezas.append('<div class="caso"><span>%s</span><span class="v">%s'
                      "</span></div>"
                      % (_c(etiqueta), _c(_valor_de_caso(fila, filtro))))
    return "".join(piezas)


def _fragmentos(fila: Fila) -> List[str]:
    """Los fragmentos del literal que se muestran como texto oficial,
    verificados como subcadena del literal transcrito (espacios
    normalizados)."""
    contenido = CONTENIDO.get(fila.concept_id)
    literal = _normalizar(fila.norma.get("literal") or "")
    if contenido is None:
        return [fila.norma.get("literal") or "(sin literal)"]
    for fragmento in contenido["fragmentos"]:
        if _normalizar(fragmento) not in literal:
            raise AssertionError(
                "%s: el fragmento no está en el literal transcrito — no se "
                "muestra una cita que no lo sea: %r"
                % (fila.concept_id, fragmento[:80]))
    return list(contenido["fragmentos"])


def generar_hoja(prefijo: str = PREFIJO_POR_DEFECTO,
                 seleccion=None,
                 fecha_sesion: str = "2026-08-25") -> str:
    filas = seleccionar(cargar_paquete(prefijo), seleccion)
    if not filas:
        raise SystemExit("No hay borradores «%s*» que revisar." % prefijo)
    huella_paquete = huella_del_paquete(filas)
    fuente = filas[0].norma.get("fuente") or {}
    url_boe = fuente.get("url_oficial") or "https://www.boe.es"

    # Los datos que la vista no enseña pero el acta necesita.
    datos = {
        "paquete": "dbsi3_evacuacion_p1",
        "generada": date.today().isoformat(),
        "hoy": date.today().isoformat(),
        "documento_sha256": fuente.get("documento_sha256"),
        "huella_paquete": huella_paquete,
        "filas": [{"numero": f.numero, "concept_id": f.concept_id,
                   "huella_fila": f.huella} for f in filas],
    }

    cuerpo = []
    cuerpo.append('<div class="envoltura">')
    cuerpo.append("<header>")
    cuerpo.append('<div class="chip">BORRADOR — PENDIENTE DE VALIDACIÓN</div>')
    cuerpo.append("<h1>Revisión de normativa — evacuación (DB-SI 3)</h1>")
    cuerpo.append('<p class="resumen">ArchMuse ha transcrito %d reglas de '
                  "evacuación del Código Técnico para edificios de viviendas. "
                  "Antes de usarlas necesita que un profesional confirme que "
                  "dicen exactamente lo que dice la norma. Sesión del %s.</p>"
                  % (len(filas), fecha_sesion))
    cuerpo.append('<p class="fuentes">Fuente oficial para comprobar: '
                  '<a href="%s" target="_blank" rel="noopener">PDF del '
                  "Documento Básico SI (codigotecnico.org)</a> · "
                  '<a href="%s" target="_blank" rel="noopener">Real Decreto '
                  "314/2006 en el BOE</a></p>"
                  % (PDF_OFICIAL, _c(url_boe)))
    cuerpo.append("</header>")
    cuerpo.append(
        '<div class="guia"><b>Cómo se revisa (20 minutos):</b><ol>'
        "<li>Lea cada regla. Debajo tiene, en amarillo, <b>lo que dice el "
        "texto oficial</b>, y un enlace que abre el PDF oficial por la página "
        "exacta para comprobarlo.</li>"
        "<li>Marque <b>«Correcta»</b> si la regla dice lo mismo que la norma "
        "(los valores, los casos y la referencia son exactos y se entiende). "
        "Si algo está mal, marque <b>«Necesita corrección»</b> y escriba qué "
        "corregir. Si una regla no debería estar, <b>«Excluir»</b>.</li>"
        "<li>Al final, escriba su nombre y colegiatura y pulse <b>«Guardar "
        "revisión»</b>. Sus marcas se van guardando solas en este navegador: "
        "puede cerrar y seguir más tarde.</li></ol></div>")

    for i, fila in enumerate(filas, start=1):
        contenido = CONTENIDO.get(fila.concept_id) or {}
        pagina = contenido.get("pagina_pdf")
        enlace = ('<p class="comprobar"><a href="%s#page=%d" target="_blank" '
                  'rel="noopener">Comprobar en el PDF oficial (se abre por la '
                  "página %d)</a></p>" % (PDF_OFICIAL, pagina, pagina)
                  if pagina else "")
        citas = "".join('<blockquote class="literal">%s</blockquote>'
                        % _c(_normalizar(f)) for f in _fragmentos(fila))
        cuerpo.append(
            '<section class="regla" data-numero="%s" data-concept="%s">'
            '<div class="regla-cabecera"><span class="numero">Regla %d de %d'
            '</span><span class="donde">%s</span></div>'
            "%s"
            '<div class="oficial"><div class="titulo-oficial">Lo que dice el '
            "texto oficial</div>%s%s</div>"
            '<div class="decision">'
            '<label><input type="radio" name="d-%d" value="correcta"/>'
            "Correcta — dice lo mismo que la norma</label>"
            '<label><input type="radio" name="d-%d" value="corregir"/>'
            "Necesita corrección</label>"
            '<label class="excluir"><input type="radio" name="d-%d" '
            'value="excluir"/>Excluir</label></div>'
            '<textarea class="correccion" placeholder="Escriba aquí qué hay '
            'que corregir (el valor o el texto correcto)."></textarea>'
            "</section>"
            % (fila.numero, _c(fila.concept_id), i, len(filas),
               _c(localizacion(fila)), _cuerpo_exigencia(fila), citas, enlace,
               i, i, i))

    cuerpo.append('<div id="panel">')
    cuerpo.append("<h2>Cierre de la revisión</h2>")
    cuerpo.append('<p id="progreso"></p>')
    cuerpo.append(
        '<div class="campos">'
        '<label>Nombre y apellidos<input id="v-nombre" type="text"/></label>'
        '<label>Colegiatura / cargo<input id="v-colegiatura" type="text"/></label>'
        '<label>Rol<select id="v-rol">'
        '<option value="arquitecto_colegiado">Arquitecto colegiado</option>'
        '<option value="experto_normativo">Experto normativo</option>'
        "</select></label>"
        '<label>Fecha<input id="v-fecha" type="date"/></label></div>')
    cuerpo.append(
        '<p class="declaracion"><label><input type="checkbox" '
        'id="v-declaracion"/> He comprobado estas reglas contra el texto '
        "oficial del DB-SI.</label></p>")
    cuerpo.append('<button id="guardar" disabled>Guardar revisión</button>'
                  '<span id="autoguardado"></span>')
    cuerpo.append('<div id="resultado"></div>')
    cuerpo.append(
        "<footer>Al guardar se descarga un fichero con sus respuestas y su "
        "identidad; envíelo desde su correo citando el código de revisión "
        "que aparecerá arriba. Ese fichero es el acta de esta sesión: "
        "ArchMuse no incorpora nada que no esté en él. Sus marcas se guardan "
        "además automáticamente en este navegador.</footer>")
    cuerpo.append("</div></div>")

    return ("<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Revisión de normativa — DB-SI 3 evacuación</title>"
            "<style>%s</style></head><body>%s"
            "<script id='datos-paquete' type='application/json'>%s</script>"
            "<script>%s</script></body></html>"
            % (_CSS, "\n".join(cuerpo),
               json.dumps(datos, ensure_ascii=False), _JS))


def main(argv: list) -> int:
    prefijo = argv[1] if len(argv) > 1 else PREFIJO_POR_DEFECTO
    destino = Path(argv[2]) if len(argv) > 2 else (
        RAIZ / "docs" / "curacion" / "2026-08-25-dbsi3-evacuacion-p1.html")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(generar_hoja(prefijo, seleccion=SELECCION_P1),
                       encoding="utf-8")
    print("Hoja escrita en %s" % destino)
    print("Se revisa EN PANTALLA: abrir en el navegador; «Guardar revisión» "
          "descarga el acta JSON que consume curacion/volcar_acta.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
