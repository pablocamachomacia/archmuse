# -*- coding: utf-8 -*-
"""`C-15`: si los recintos están en una referencia externa, se dice dónde y no se mide.

**El caso, 2026-09-15.** Pablo abrió un plano de otro proyecto del estudio y, al
pinchar una habitación, AutoCAD cambió a la pestaña «Referencia externa». Medido
con AutoCAD Core Console sobre copias de los 70 DWG del estudio: `ssget "_X"` no
ve nada de lo que hay dentro de una xref, y 19 de 58 dibujos distintos tienen sus
recintos sólo ahí. En esas hojas el comando no encontraba la capa, **culpaba a su
nombre** y ofrecía elegir otra: elegir mal ahí acaba en una cifra falsa.

**Firmado por Pablo:** que el comando diga «este dibujo referencia plantas
base.dwg; los recintos y el cuadro están ahí, abre ese fichero», y que **no
ofrezca elegir otra capa** cuando ha detectado que los recintos están en una xref.

Estos tests guardan el fuente, porque el `.lsp` no se ejecuta en CI. Las
funciones de detección sí se ejecutaron en Core Console sobre DWG reales; las
cifras están en `docs/PROGRESS.md`, 2026-09-15.

**Alcance:** medido en UN estudio. Otro que ponga el cuadro en la hoja y los
recintos en la xref cae en este caso cada vez.
"""
from __future__ import annotations

import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LSP = open(os.path.join(RAIZ, "autocad", "archmuse.lsp"), encoding="utf-8").read()


def _sin_comentarios(texto):
    return "\n".join(linea.split(";;")[0] for linea in texto.splitlines())


def _defun(nombre):
    ini = LSP.index("(defun %s " % nombre)
    fin = LSP.find("\n(defun ", ini + 1)
    return _sin_comentarios(LSP[ini:fin if fin > 0 else len(LSP)])


# --- 1. La detección ---------------------------------------------------------

def test_una_xref_se_reconoce_por_el_bit_4_y_si_esta_cargada_por_el_32():
    cuerpo = _defun("am:xrefs")
    assert '(tblnext "BLOCK" T)' in cuerpo
    assert "(logand 4 fl)" in cuerpo
    assert "(logand 32 fl)" in cuerpo


def test_lo_que_hay_dentro_se_lee_de_la_definicion_de_su_bloque():
    """`ssget "_X"` no lo ve; la definición del bloque sí (medido)."""
    cuerpo = _defun("am:contenido-de-xref")
    assert '(tblobjname "BLOCK" bloque)' in cuerpo
    assert "(entnext e)" in cuerpo
    assert "ssget" not in cuerpo


def test_la_capa_de_una_xref_se_compara_sin_su_prefijo():
    """Dentro de la xref la capa llega como «plantas base|00 areas»."""
    assert "(am:capa-sin-xref (cdr (assoc 8 datos)))" in _defun("am:contenido-de-xref")
    assert '(vl-string-search "|" nombre)' in _defun("am:capa-sin-xref")


def test_el_cuadro_dentro_de_la_xref_se_reconoce_por_su_titulo():
    cuerpo = _defun("am:contenido-de-xref")
    assert '"ACAD_TABLE"' in cuerpo
    assert "*am:titulo-del-cuadro*" in cuerpo


def test_del_fichero_referenciado_solo_se_ensena_el_nombre_nunca_la_carpeta():
    """La carpeta de un proyecto suele llevar el nombre del cliente. **Salvo** cuando
    no se encuentra el fichero (Pablo, 2026-09-17): entonces se enseña la ruta en
    pantalla, nunca en el registro (`test_el_detalle_tecnico_va_al_registro_y_sin_nombres`)."""
    cuerpo = _defun("am:fichero-de-xref")
    assert "vl-filename-base" in cuerpo
    assert "DWGPREFIX" not in cuerpo


# --- 2. El comando se para, y no ofrece otra capa ----------------------------

def test_se_comprueba_antes_de_buscar_el_cuadro_y_antes_de_ofrecer_capa():
    """Antes del cuadro, porque en una hoja el cuadro TAMBIÉN está en la xref y
    «este plano no tiene ningún cuadro» sería otra causa falsa. Antes de la
    lista de capas, porque ofrecerla es lo que acaba en una cifra falsa."""
    comando = _defun("c:ARCHMUSE")
    comprobacion = comando.index("(am:recintos-en-xref-p *am:capa-por-defecto*)")
    assert comprobacion < comando.index("(am:buscar-cuadros)")
    assert comprobacion < comando.index("(am:elegir-capa)")
    rama = comando[comprobacion:comando.index("(am:avisar-xrefs-sin-cargar)")]
    assert "(exit)" in rama


def test_con_la_capa_que_el_elija_se_vuelve_a_comprobar_antes_de_recoger():
    comando = _defun("c:ARCHMUSE")
    elegir = comando.index("(am:elegir-capa)")
    otra = comando.index("(am:recintos-en-xref-p capa)")
    assert elegir < otra < comando.index("(am:recolectar capa cuadros)")
    rama = comando[otra:comando.index("(am:pedir-punto)")]
    assert "(exit)" in rama


def _mensajes(cuerpo):
    return re.findall(r'\(princ\s+(?:\(strcat\s+)?"([^"]*)"', cuerpo) + \
        re.findall(r'\(getkword\s+(?:\(strcat\s+)?"([^"]*)"', cuerpo)


def test_el_mensaje_habla_como_un_arquitecto_y_ofrece_abrir_el_dibujo():
    """Pablo, 2026-09-17: «referencia externa», «677 polilínea(s)» y «No te ofrezco
    medir otra capa» no los entiende un arquitecto. Ahora:

        ArchMuse no puede medir este plano: las habitaciones están dibujadas
        en «maestro.dwg».
        ¿Abro «maestro.dwg»? [Si/No] <Si>:
    """
    cuerpo = " ".join(_defun("am:recintos-en-xref-p").split())
    assert '"\\nArchMuse no puede medir este plano: las habitaciones están dibujadas en «"' in cuerpo
    assert '(initget "Si No")' in cuerpo
    assert '"\\n¿Abro «" fichero "»? [Si/No] <Si>: "' in cuerpo
    # Enter es Sí; No termina sin dibujar; Esc llega a *error* («Cancelado con Esc»).
    assert '(/= respuesta "No")' in cuerpo
    assert '"\\nDe acuerdo: no dibujo nada."' in cuerpo
    for tecnico in ("referencia externa", "polilínea", "No te ofrezco", "capa", "NO MIDO"):
        assert not any(tecnico in m for m in _mensajes(cuerpo)), tecnico


def test_si_abre_el_dibujo_lo_abre_sin_cerrar_el_actual_y_lo_dice():
    abrir = " ".join(_defun("am:abrir-dibujo").split())
    assert "(vla-Open (vla-get-Documents (vlax-get-acad-object)) ruta :vlax-false)" in abrir
    assert "vla-Close" not in abrir and "_.OPEN" not in abrir
    assert '"\\nAbierto. Escribe ARCHMUSE allí."' in abrir


def test_si_el_fichero_no_se_encuentra_lo_dice_con_su_ruta_completa():
    """Aquí sí la ruta: Pablo lo pide para poder ir a buscarlo. Sólo en pantalla."""
    cuerpo = " ".join(_defun("am:recintos-en-xref-p").split())
    assert "(am:ruta-de-xref (nth 3 x))" in cuerpo or "(am:ruta-de-xref ruta)" in cuerpo
    assert '"\\nNo encuentro «" fichero "». Debería estar en: "' in cuerpo
    ruta = " ".join(_defun("am:ruta-de-xref").split())
    assert "findfile" in ruta and '(getvar "DWGPREFIX")' in ruta
    # 3.9.9 en forzada.dwg: `(or (findfile ...))` devuelve T, no la ruta, y abrir
    # acababa en «stringp T». La ruta encontrada tiene que ser la cadena.
    assert "(or (findfile" not in ruta
    assert "(cond ((findfile ruta))" in ruta


def test_con_varias_referencias_con_habitaciones_las_nombra_y_no_ofrece_abrir():
    cuerpo = " ".join(_defun("am:recintos-en-xref-p").split())
    varias = cuerpo[cuerpo.index("(> (length en-xref) 1)"):]
    varias = varias[:varias.index("(am:abrir-dibujo")] if "(am:abrir-dibujo" in varias else varias
    assert '"\\nArchMuse no puede medir este plano: las habitaciones están dibujadas en varios dibujos:"' in varias
    assert "(getkword" not in varias.split("(progn", 2)[1] if "(progn" in varias else True


def test_el_detalle_tecnico_va_al_registro_y_sin_nombres():
    cuerpo = _defun("am:recintos-en-xref-p")
    logs = re.findall(r"\(am:log[^\n]*", cuerpo)
    assert logs, "el detalle técnico no va al registro"
    for linea in logs:
        assert "fichero" not in linea and "ruta" not in linea and "capa" not in linea.split('"')[0], linea
    assert "polilineas" in " ".join(logs)


def test_el_registro_de_c15_no_lleva_nombres_de_fichero():
    """Lo que se registra es un suceso escrito por el comando, no un dato del
    plano: ni el fichero referenciado ni su capa."""
    comando = _defun("c:ARCHMUSE")
    llamadas = re.findall(r"\(am:log[^\n]*C-15[^\n]*", comando)
    assert len(llamadas) == 3, llamadas
    for llamada in llamadas:
        assert re.fullmatch(r'\(am:log "C-15:[^"]*"\)\)*', llamada.strip()), llamada


def test_si_no_encuentra_un_dibujo_referenciado_lo_dice_con_su_ruta_completa():
    """Medido en Core Console (2026-09-17): si el fichero no está, AutoCAD no carga la
    referencia y no se puede ver si las habitaciones están ahí. Es este aviso, no el
    de arriba, el que tiene que decir «no lo encuentro» y dónde debería estar."""
    aviso = " ".join(_defun("am:avisar-xrefs-sin-cargar").split())
    assert '"\\n\\nAVISO — No encuentro estos dibujos que usa el plano:"' in aviso
    assert "(cadr (am:ruta-de-xref" in aviso
    for tecnico in ("referencia", "cargar", "capa"):
        assert not any(tecnico in m for m in _mensajes(aviso)), tecnico


def test_la_xref_sin_cargar_avisa_pero_no_para():
    """De una xref sin cargar no se puede saber qué tiene: no hay detección.
    Pablo, 2026-09-15: «por ahora deja el aviso y que se pueda elegir capa».

    **Riesgo abierto:** si elige una capa cualquiera, puede salir una cifra falsa
    igual. Si se decide parar también aquí, este test tiene que cambiar a
    propósito, no por accidente."""
    assert "(exit)" not in _defun("am:avisar-xrefs-sin-cargar")
    comando = _defun("c:ARCHMUSE")
    aviso = comando.index("(am:avisar-xrefs-sin-cargar)")
    assert "(exit)" not in comando[aviso:comando.index("(am:buscar-cuadros)")]
