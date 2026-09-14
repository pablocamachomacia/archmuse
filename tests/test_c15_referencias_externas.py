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
    """La carpeta de un proyecto suele llevar el nombre del cliente."""
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


def test_el_mensaje_dice_donde_estan_y_no_culpa_a_la_capa():
    cuerpo = LSP[LSP.index("(defun am:recintos-en-xref-p "):]
    cuerpo = cuerpo[:cuerpo.find("\n(defun ", 1)]
    assert "Este dibujo referencia «" in cuerpo
    assert "y el cuadro de superficies" in cuerpo
    assert "Abre " in cuerpo and "teclea ARCHMUSE allí" in cuerpo
    assert "No te ofrezco medir otra capa" in cuerpo
    # Recintos aquí y en la xref: medir sólo los de aquí es una cifra de menos.
    assert "cifra de menos" in cuerpo


def test_el_registro_de_c15_no_lleva_nombres_de_fichero():
    """Lo que se registra es un suceso escrito por el comando, no un dato del
    plano: ni el fichero referenciado ni su capa."""
    comando = _defun("c:ARCHMUSE")
    llamadas = re.findall(r"\(am:log[^\n]*C-15[^\n]*", comando)
    assert len(llamadas) == 3, llamadas
    for llamada in llamadas:
        assert re.fullmatch(r'\(am:log "C-15:[^"]*"\)\)*', llamada.strip()), llamada


def test_la_xref_sin_cargar_avisa_pero_no_para():
    """De una xref sin cargar no se puede saber qué tiene: no hay detección, y
    `C-15` sólo firma pararse cuando la hay. Si se decide parar también aquí,
    este test tiene que cambiar a propósito, no por accidente."""
    assert "(exit)" not in _defun("am:avisar-xrefs-sin-cargar")
    comando = _defun("c:ARCHMUSE")
    aviso = comando.index("(am:avisar-xrefs-sin-cargar)")
    assert "(exit)" not in comando[aviso:comando.index("(am:buscar-cuadros)")]
