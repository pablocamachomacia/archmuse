# -*- coding: utf-8 -*-
"""Las promesas del registro local y de `ARCHMUSE-INFORME`. T6 del PRD de la beta.

**Qué prueba esto y qué no.** Igual que `test_archmuse_lsp.py`, no ejecuta
AutoLISP: lee el fichero. Pero lo que comprueba aquí no es sintaxis, son **las
tres promesas que le hacemos al arquitecto** y que, si se rompen, se rompen en
silencio y en casa de otro:

1. **El registro no sale de su máquina.** Vive en `%LOCALAPPDATA%`, que no está
   sincronizado, y no en `Documentos` ni en el `Escritorio`, que con OneDrive sí
   lo están. Un registro que se sube a la nube contradice la única frase con la
   que se le ha vendido esto.
2. **El registro no lleva su proyecto dentro.** Ni vértices, ni rótulos, ni
   celdas, ni la ruta del fichero — la ruta es donde suele estar el nombre del
   cliente. La forma de garantizarlo en un lenguaje sin tipos es estructural:
   `am:log` no se llama desde ninguna de las funciones que tocan el payload.
3. **El plano sólo viaja si él teclea otro comando.** Nunca por omisión, nunca
   dentro del informe normal.

Las tres son verificables leyendo el fichero, y ninguna la vería una revisión
por encima seis meses después — que es exactamente para lo que sirve un test.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

LSP = Path(__file__).parent.parent / "autocad" / "archmuse.lsp"


@pytest.fixture(scope="module")
def fuente() -> str:
    return LSP.read_text(encoding="utf-8")


def _sin_comentarios(fuente: str) -> str:
    """Fuera los comentarios `;`, **conservando las cadenas**.

    Los dos tests que miran `DWGPREFIX` tienen que mirar código y no prosa: el
    nombre aparece dentro de una cadena —`(getvar "DWGPREFIX")`— así que el
    limpiador de `test_archmuse_lsp.py`, que también vacía las cadenas, no sirve
    aquí. Y no quitar los comentarios tampoco: la primera versión de este test
    se puso roja por un comentario que decía «DWGPREFIX no aparece aquí», que es
    a la vez cierto y una forma tonta de fallar.
    """
    salida = []
    en_cadena = False
    en_comentario = False
    escapado = False
    for ch in fuente:
        if en_comentario:
            if ch == "\n":
                en_comentario = False
                salida.append(ch)
            continue
        if en_cadena:
            salida.append(ch)
            if escapado:
                escapado = False
            elif ch == "\\":
                escapado = True
            elif ch == '"':
                en_cadena = False
            continue
        if ch == ";":
            en_comentario = True
            continue
        if ch == '"':
            en_cadena = True
        salida.append(ch)
    return "".join(salida)


def _por_funcion(fuente: str) -> dict:
    trozos = {}
    for parte in fuente.split("\n(defun ")[1:]:
        nombre = re.match(r"([A-Za-z0-9:*>-]+)", parte)
        if nombre:
            trozos[nombre.group(1)] = parte
    return trozos


@pytest.fixture(scope="module")
def codigo(fuente) -> dict:
    """El cuerpo de cada `defun`, sin comentarios. Para lo que se afirma del
    código."""
    return _por_funcion(_sin_comentarios(fuente))


@pytest.fixture(scope="module")
def funciones(fuente) -> dict:
    """El cuerpo de cada `defun`, por nombre. Trocear por `(defun ` basta: en
    este fichero ningún `defun` está anidado dentro de otro salvo el `*error*`
    del comando, que no nos interesa aquí."""
    trozos = {}
    partes = fuente.split("\n(defun ")
    for parte in partes[1:]:
        nombre = re.match(r"([A-Za-z0-9:*>-]+)", parte)
        if nombre:
            trozos[nombre.group(1)] = parte
    return trozos


# ---------------------------------------------------------------------------
# 1. Dónde vive el registro
# ---------------------------------------------------------------------------

def test_el_registro_vive_en_localappdata(fuente):
    assert 'getenv "LOCALAPPDATA"' in fuente


def test_el_registro_no_se_escribe_en_carpetas_sincronizadas(funciones):
    """`Documentos` y `Escritorio` suelen estar en OneDrive. El ZIP del informe
    sí va al escritorio —lo va a mandar de todas formas— pero **el registro
    no**, porque se escribe solo, en cada medición, sin que él lo decida."""
    for nombre in ("am:carpeta", "am:carpeta-de-registro", "am:fichero-de-registro",
                   "am:log"):
        cuerpo = funciones[nombre]
        assert "USERPROFILE" not in cuerpo, nombre
        assert "Desktop" not in cuerpo, nombre
        assert "Documents" not in cuerpo, nombre
        assert "Escritorio" not in cuerpo, nombre


def test_el_fichero_de_registro_rota_por_meses(funciones):
    """Un solo fichero que crece sin fin acaba siendo imposible de mandar, y es
    también lo que hace innecesaria la aritmética de fechas: el recorte natural
    de «los últimos meses» es un fichero por mes."""
    assert "am:mes-actual" in funciones["am:fichero-de-registro"]


# ---------------------------------------------------------------------------
# 2. Qué NO puede entrar en el registro
# ---------------------------------------------------------------------------

#: Las funciones que tienen delante datos del proyecto del arquitecto.
#:
#: Se actualizó el 2026-09-12: `am:reparto-celdas` y `am:rellenar-cuadro` ya no
#: existen —escribían en el cuadro del arquitecto y se quitaron con el cambio de
#: diseño—, y en su lugar entran las que manejan el cuadro propio. **Que una
#: función desaparezca de esta lista no es una relajación: es que ya no hay nada
#: que vigilar ahí.** Lo que no puede pasar es que entre código nuevo con datos
#: del plano delante y nadie lo añada aquí.
#:
#: Y otra vez el 2026-09-13, con la plantilla fija: `am:notas-del-cuadro` se
#: quitó, y entran las que arman el cuerpo con las cajas y alturas de sus
#: cuadros y las que leen de la respuesta nombres de estancias y de viviendas.
TOCAN_EL_PROYECTO = ("am:recolectar", "am:json-vertices", "am:celdas-json",
                     "am:vertices-de", "am:texto-de", "am:cuadros-json",
                     "am:celdas-del-cuadro", "am:notas-colocadas",
                     "am:dibujar-cuadro", "am:con-dibujo", "am:alturas-de-cuadro",
                     "am:preguntar-ambitos", "am:viviendas-de",
                     "am:bloque-de-vivienda", "am:zona-de-repartos",
                     "am:motivos-indistinguibles", "am:estilos-de-cuadro",
                     "am:cadenas-tras", "am:textos-de-notas", "am:medir-textos",
                     "am:json-celdas", "am:maquetar")


@pytest.mark.parametrize("nombre", TOCAN_EL_PROYECTO)
def test_las_funciones_que_tocan_el_proyecto_no_registran_nada(nombre, codigo):
    """**La garantía estructural.** En un lenguaje sin tipos no se puede impedir
    que alguien pase un rótulo a `am:log`; lo que sí se puede es que las
    funciones que tienen rótulos, vértices y celdas a mano **no llamen a
    `am:log` en absoluto**. Si alguien necesita registrar algo desde ahí, este
    test se pone rojo y le obliga a pensar qué está a punto de escribir en un
    fichero que va a viajar por WhatsApp."""
    assert "(am:log" not in codigo[nombre], (
        "«%s» tiene el proyecto del arquitecto a mano y llama a am:log. Lo que "
        "se registra tiene que ser un recuento construido por el comando, no un "
        "dato del plano." % nombre
    )


def test_la_linea_de_registro_lleva_el_nombre_del_dibujo_pero_no_su_ruta(codigo):
    """`DWGNAME` es «plano.dwg». `DWGPREFIX` es la carpeta, y la carpeta de un
    proyecto lleva casi siempre el nombre del cliente."""
    contexto = codigo["am:contexto"]
    assert 'getvar "DWGNAME"' in contexto
    assert "DWGPREFIX" not in contexto


def test_dwgprefix_solo_aparece_donde_se_manda_el_plano_a_proposito(codigo):
    """La ruta completa del dibujo se construye en un solo sitio de todo el
    fichero: el que copia el DWG cuando él ha tecleado `ARCHMUSE-INFORME-PLANO`.
    Si aparece en otro, alguien está a punto de mandar una ruta sin saberlo."""
    con_ruta = [n for n, cuerpo in codigo.items() if "DWGPREFIX" in cuerpo]
    # **Excepción** (3.9.9, 2026-09-17): `am:ruta-de-xref` busca el dibujo donde están
    # las habitaciones junto a éste, para abrirlo o decir en pantalla dónde debería
    # estar (Pablo lo pide). Su resultado no puede ir al registro ni a ningún envío.
    assert sorted(con_ruta) == ["am:lanza-el-empaquetado", "am:ruta-de-xref"], con_ruta
    for nombre, cuerpo in codigo.items():
        if "(am:ruta-de-xref" in cuerpo:
            assert nombre in ("am:recintos-en-xref-p", "am:avisar-xrefs-sin-cargar"), nombre
            for linea in cuerpo.splitlines():
                if "am:log" in linea:
                    assert "ruta" not in linea and "am:ruta-de-xref" not in linea, (nombre, linea)


def test_el_entorno_no_declara_la_ruta_del_dibujo(codigo):
    entorno = codigo["am:escribe-entorno"]
    assert "DWGPREFIX" not in entorno
    assert "DWGNAME" not in entorno


# ---------------------------------------------------------------------------
# 3. El plano sólo viaja si se teclea el otro comando
# ---------------------------------------------------------------------------

def test_hay_dos_comandos_de_informe_y_uno_solo_lleva_el_plano(fuente):
    assert "(defun c:ARCHMUSE-INFORME (" in fuente
    assert "(defun c:ARCHMUSE-INFORME-PLANO (" in fuente


def test_el_informe_normal_se_pide_sin_plano(funciones):
    """`(am:informe nil)`: el informe corriente no puede llevar el dibujo ni por
    descuido, porque el parámetro va escrito en la llamada."""
    assert re.search(r"\(am:informe\s+nil\)", funciones["c:ARCHMUSE-INFORME"])


def test_el_informe_con_plano_avisa_con_todas_las_letras(funciones):
    cuerpo = funciones["am:informe"]
    assert "INCLUYE UNA COPIA DE TU DIBUJO" in cuerpo
    assert "proyecto de tu cliente" in cuerpo


def test_los_dos_informes_piden_confirmacion(funciones):
    """Ni el normal se escapa: crea un fichero en su escritorio, y eso se
    pregunta."""
    cuerpo = funciones["am:informe"]
    assert "(initget \"Si No\")" in cuerpo
    assert "getkword" in cuerpo
    assert '(/= r "Si")' in cuerpo


def test_se_ensena_lo_que_va_dentro_antes_de_comprimir(funciones):
    """La promesa de «sin planos dentro» tiene que ser comprobable por él, no
    creíble. Se le enseña la lista con el tamaño de cada fichero, y se le dice
    que puede abrir el ZIP."""
    cuerpo = funciones["am:informe"]
    assert "TODO lo que voy a meter" in cuerpo
    assert "am:legible" in cuerpo
    assert "comprobarlo antes de mandarlo" in cuerpo


def test_si_el_zip_falla_se_dice_donde_estan_los_ficheros(funciones):
    """Un comando de diagnóstico que falla en silencio es peor que no tenerlo:
    pase lo que pase con PowerShell, él acaba sabiendo en qué carpeta mirar."""
    cuerpo = funciones["am:informe"]
    assert cuerpo.count("carpeta") >= 2
    assert "los puedes" in cuerpo


# ---------------------------------------------------------------------------
# 4. Que registrar no pueda tumbar la medición
# ---------------------------------------------------------------------------

def test_escribir_el_registro_nunca_revienta_el_comando(funciones):
    """Perder una línea de registro es barato. Perder la medición por no haber
    podido escribirla, no."""
    cuerpo = funciones["am:log"]
    assert cuerpo.count("vl-catch-all-apply") >= 3


def test_sin_localappdata_el_comando_sigue_midiendo(funciones):
    """`am:carpeta` devuelve nil y todo lo de arriba se degrada a no registrar,
    en vez de a no medir."""
    assert "nil" in funciones["am:carpeta"]
    assert "(if ruta" in funciones["am:log"]


# ---------------------------------------------------------------------------
# 5. Las dos versiones
# ---------------------------------------------------------------------------

def test_la_version_larga_empieza_por_la_corta(fuente):
    """Dos números que se separan son peor que uno solo: el cotejo con el
    servidor usa la corta y lo que él lee en pantalla es la larga."""
    corta = re.search(r'\*am:version-corta\*\s+"([^"]+)"', fuente).group(1)
    larga = re.search(r'\*am:version\*\s+"([^"]+)"', fuente).group(1)
    assert larga.startswith(corta)


def test_la_linea_de_registro_lleva_las_dos_versiones(funciones):
    """Sin esto, un informe suyo de dentro de tres semanas no es interpretable:
    no se sabría qué ArchMuse produjo esas cifras."""
    contexto = funciones["am:contexto"]
    assert "*am:version-corta*" in contexto
    assert "*am:version-del-servidor*" in contexto
    assert 'getvar "ACADVER"' in contexto


def test_la_version_del_servidor_se_lee_de_la_respuesta(funciones):
    assert '(am:valor-tras respuesta "version" 0)' in funciones["c:ARCHMUSE"]
