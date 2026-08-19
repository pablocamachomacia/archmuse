# -*- coding: utf-8 -*-
"""TL-2 — escribir en el fichero del cliente sin poder estropearlo.

Ejecutar:  pytest tests/test_agente_escritura.py

PRD aprobado por Pablo el 2026-08-19
(`docs/prd/2026-08-19-escritura-protegida-del-dxf-del-cliente.md`), con tres
condiciones textuales. Este fichero existe para que las tres sean comprobables
y no promesas:

1. **El original siempre intacto y verificado por SHA-256.** Se comprueba en el
   camino feliz y —sobre todo— en el que falla a mitad, que es donde de verdad
   podría tocarse algo.
2. **El efecto explícitamente autorizado.** Sin autorización no se ejecuta y
   **no se crea ningún fichero**, verificado listando el directorio antes y
   después. El portero vive en la capacidad, no sólo en el ejecutor de Skills:
   así cubre también el CLI, MCP y un futuro plugin de Revit.
3. **`N/D` nunca convertido en número.** Una celda que ArchMuse no ha podido
   calcular sale como `N/D` y vuelve listada con su motivo.

Y una política, que es lo que hace que esto siga siendo cierto con la capacidad
de escritura número dos: el test que recorre el registro (`§5`).

El caso completo necesita el `v2s.dxf` real —un `ACAD_TABLE` no se sintetiza de
forma realista— y se salta con motivo si no está `ARCHMUSE_DXF_V2S`, mismo
criterio que el resto de la suite.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente import manifiesto  # noqa: E402
from agente.efectos import (ESCRIBE_FICHERO, Autorizaciones,  # noqa: E402
                            EfectoNoAutorizado)
from agente.herramientas import plano  # noqa: E402
from agente.registro import registro  # noqa: E402
from tests.test_agente_goldens import construir_dxf  # noqa: E402

DXF_V2S = os.environ.get("ARCHMUSE_DXF_V2S", "")

PERMISO = Autorizaciones.de([ESCRIBE_FICHERO], por="test")


def sha256(ruta) -> str:
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


@pytest.fixture
def origen(tmp_path) -> str:
    return construir_dxf(tmp_path)


# --- 1. El original, intacto y verificado ---------------------------------

def test_el_original_conserva_su_sha256_aunque_la_escritura_falle(origen, tmp_path):
    """EL CASO QUE MÁS IMPORTA, y el que se comprueba peor por costumbre.

    El DXF sintético no trae `ACAD_TABLE`, así que la escritura falla. Un fallo
    a mitad es justo el momento en el que un original podría haberse tocado —
    comprobar el sello sólo en el camino feliz sería comprobarlo donde no hace
    falta.
    """
    antes = sha256(origen)
    resultado = plano.escribir_cuadro(origen, str(tmp_path / "copia.dxf"))

    assert resultado["ok"] is False
    assert resultado["origen_intacto"] is True
    assert resultado["sello_origen_sha256"] == antes
    assert sha256(origen) == antes


def test_el_resultado_publica_el_sello_para_que_el_arquitecto_lo_vea(origen, tmp_path):
    """«Tu plano no se toca» sólo vale como argumento si se puede comprobar."""
    resultado = plano.escribir_cuadro(origen, str(tmp_path / "copia.dxf"))
    assert resultado["sello_origen_sha256"] == sha256(origen)


# --- 2. El destino, nunca el origen ---------------------------------------

def test_el_destino_no_puede_ser_el_origen(origen):
    resultado = plano.escribir_cuadro(origen, origen)
    assert resultado["ok"] is False
    assert resultado["error"] == "destino_es_el_origen"
    assert resultado["pregunta"]


def test_el_destino_no_puede_ser_el_origen_con_otra_capitalizacion(origen):
    """En Windows `Plano.dxf` y `plano.dxf` son el mismo fichero, y comparar
    cadenas no lo detecta."""
    resultado = plano.escribir_cuadro(origen, str(origen).upper())
    assert resultado["ok"] is False
    assert resultado["error"] == "destino_es_el_origen"


def test_el_destino_no_puede_ser_el_origen_por_una_ruta_con_rodeo(origen, tmp_path):
    """`.../carpeta/../carpeta/piso.dxf` es el mismo fichero."""
    con_rodeo = str(tmp_path / "sub" / ".." / Path(origen).name)
    resultado = plano.escribir_cuadro(origen, con_rodeo)
    assert resultado["ok"] is False
    assert resultado["error"] == "destino_es_el_origen"


def test_no_se_sobrescribe_un_fichero_que_ya_existe(origen, tmp_path):
    """Podría ser un entregable anterior que el arquitecto ya ha revisado."""
    ocupado = tmp_path / "copia.dxf"
    ocupado.write_bytes(b"entregable de ayer")
    resultado = plano.escribir_cuadro(origen, str(ocupado))
    assert resultado["ok"] is False
    assert resultado["error"] == "destino_ya_existe"
    assert ocupado.read_bytes() == b"entregable de ayer"


def test_sin_destino_se_pregunta_en_vez_de_inventar_uno(origen):
    resultado = plano.escribir_cuadro(origen, "")
    assert resultado["ok"] is False and resultado["error"] == "destino_no_indicado"


def test_el_rechazo_del_destino_ocurre_antes_de_abrir_nada(origen, tmp_path, monkeypatch):
    """No es lo mismo rechazar tarde que rechazar pronto: si la exportación
    llega a ejecutarse, el original ya se ha abierto."""
    def no_debe_llamarse(*_a, **_k):
        raise AssertionError("no se puede llegar a exportar con un destino inseguro")

    monkeypatch.setattr("analyzer.cuadro_superficies_export.exportar_cuadro_relleno",
                        no_debe_llamarse)
    assert plano.escribir_cuadro(origen, origen)["ok"] is False


# --- 3. La autorización ----------------------------------------------------

def test_sin_autorizacion_no_se_ejecuta_y_no_se_crea_ningun_fichero(origen, tmp_path):
    """Criterio 6 del PRD, comprobado como pide: listando el directorio."""
    cap = registro(recargar=True).buscar("plano.escribir_cuadro")
    destino = tmp_path / "copia.dxf"
    antes = sorted(os.listdir(tmp_path))

    with pytest.raises(EfectoNoAutorizado):
        manifiesto.invocar(cap, origen, str(destino))

    assert sorted(os.listdir(tmp_path)) == antes
    assert not destino.exists()


def test_con_autorizacion_se_ejecuta(origen, tmp_path):
    cap = registro(recargar=True).buscar("plano.escribir_cuadro")
    resultado = manifiesto.invocar(cap, origen, str(tmp_path / "copia.dxf"),
                                   autorizaciones=PERMISO)
    # Este DXF no tiene cuadro: lo que importa aquí es que el portero dejó pasar.
    assert resultado["error"] == "cuadro_no_escribible"


def test_el_portero_esta_en_la_capacidad_y_no_solo_en_el_ejecutor():
    """Si viviera sólo en el ejecutor de Skills, el CLI de `CAD-1`, un servidor
    MCP o un plugin escribirían sin que nadie lo hubiera permitido."""
    cap = registro(recargar=True).buscar("plano.escribir_cuadro")
    with pytest.raises(EfectoNoAutorizado):
        cap.invocar({"ruta_origen": "x", "ruta_destino": "y"})


def test_el_portero_salta_antes_incluso_de_validar_los_argumentos():
    """Un rechazo por permisos no puede depender de que los argumentos estén
    bien: si no, un argumento malo enseñaría un error distinto y confuso."""
    cap = registro(recargar=True).buscar("plano.escribir_cuadro")
    with pytest.raises(EfectoNoAutorizado):
        cap.invocar({})


def test_la_autorizacion_de_otro_efecto_no_vale():
    from agente.efectos import GASTA_TOKENS

    cap = registro(recargar=True).buscar("plano.escribir_cuadro")
    with pytest.raises(EfectoNoAutorizado):
        cap.invocar({"ruta_origen": "x", "ruta_destino": "y"},
                    Autorizaciones.de([GASTA_TOKENS], por="test"))


# --- 4. La capacidad, declarada como es -----------------------------------

def test_la_capacidad_esta_declarada_como_io_con_su_efecto():
    cap = registro(recargar=True).buscar("plano.escribir_cuadro")
    assert cap.naturaleza == "io"
    assert cap.efectos == (ESCRIBE_FICHERO,)
    assert "N/D" in cap.descripcion          # lo que hace con lo que no sabe, dicho


def test_las_limitaciones_dicen_que_escribe_una_copia():
    cap = registro(recargar=True).buscar("plano.escribir_cuadro")
    assert any("copia" in l and "original" in l for l in cap.limitaciones)


# --- 5. La política: que valga también para la escritura número dos -------

def test_toda_capacidad_con_efectos_se_niega_sin_autorizacion():
    """LA POLÍTICA, no la costumbre de un módulo.

    Recorre el registro. La capacidad de escritura número dos la escribirá
    alguien que no ha leído este fichero, y tiene que comportarse igual.
    """
    culpables = []
    for cap in registro(recargar=True):
        if not cap.efectos:
            continue
        try:
            cap.invocar({})
        except EfectoNoAutorizado:
            continue
        except Exception:                      # noqa: BLE001
            culpables.append(cap.id)           # falló por otra cosa: llegó a ejecutar
        else:
            culpables.append(cap.id)
    assert culpables == [], (
        "estas capacidades con efectos no se niegan sin autorización: %s" % culpables)


def test_toda_capacidad_que_escribe_ficheros_es_de_naturaleza_io():
    for cap in registro(recargar=True):
        if ESCRIBE_FICHERO in cap.efectos:
            assert cap.naturaleza == "io", cap.id


def test_toda_capacidad_que_escribe_ficheros_pasa_por_el_patron_de_proteccion():
    """Comprobación de código, no de comportamiento: la protección tiene que
    estar en el camino, no reimplementada «parecida» en cada módulo nuevo."""
    modulos = {
        cap.funcion.__module__
        for cap in registro(recargar=True) if ESCRIBE_FICHERO in cap.efectos
    }
    assert modulos, "no hay ninguna capacidad de escritura: ¿se ha borrado?"
    for nombre in sorted(modulos):
        fuente = Path(sys.modules[nombre].__file__).read_text(encoding="utf-8")
        for guardia in ("_destino_seguro", "_con_sello_intacto"):
            assert guardia in fuente, "%s no usa %s" % (nombre, guardia)


def test_una_skill_no_puede_usar_una_capacidad_cuyo_efecto_no_declara():
    """El manifiesto de una Skill no puede mentir por omisión: la pantalla de
    autorización le enseñaría al arquitecto una lista incompleta."""
    from agente.skill import Skill, SkillInvalida

    muda = Skill(
        id="prueba.muda", version="1.0.0", dominio="prueba",
        objetivo="Escribir sin decirlo",
        cuando_usarla="Nunca: existe para que este test la rechace.",
        procedimiento=("Invocar una capacidad que escribe, sin declarar el efecto.",),
        requiere=(), capacidades=("plano.escribir_cuadro",),
        produce=("nada.util",), funcion=lambda ctx: None, efectos=(),
    )
    with pytest.raises(SkillInvalida, match="efecto"):
        muda.comprobar_registro(registro(recargar=True))


# --- 6. El caso completo, con el DXF real --------------------------------

@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S para el caso completo")
def test_el_dxf_real_sale_relleno_y_el_original_no_se_toca(tmp_path):
    antes = sha256(DXF_V2S)
    destino = tmp_path / "v2s_relleno.dxf"

    resultado = plano.escribir_cuadro(DXF_V2S, str(destino))

    assert resultado["ok"] is True
    assert resultado["celdas_escritas"], "no se ha escrito ninguna celda"
    assert resultado["copia_reabierta_sin_errores"] is True
    assert destino.exists() and resultado["sello_destino_sha256"] == sha256(destino)
    # La condición nº1 de la aprobación, byte a byte.
    assert sha256(DXF_V2S) == antes and resultado["origen_intacto"] is True
    # Y no se ha escrito nada más que el destino.
    assert resultado["ficheros_nuevos_en_la_carpeta"] == [destino.name]


@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S para el caso completo")
def test_lo_que_no_se_sabe_sale_como_ND_con_su_motivo_y_nunca_como_numero(tmp_path):
    """La condición nº3 de la aprobación."""
    resultado = plano.escribir_cuadro(DXF_V2S, str(tmp_path / "v2s.dxf"))
    assert resultado["celdas_sin_resolver"], "v2s.dxf tiene celdas que no se pueden calcular"
    for celda in resultado["celdas_sin_resolver"]:
        assert celda["motivo"], celda
    escritas = {c["campo"]: c["texto"] for c in resultado["celdas_escritas"]}
    for celda in resultado["celdas_sin_resolver"]:
        if celda["campo"] in escritas:
            assert escritas[celda["campo"]] == "N/D", celda


@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S para el caso completo")
def test_lo_que_declara_el_arquitecto_se_escribe_y_deja_de_estar_sin_resolver(tmp_path):
    sin_respuestas = plano.escribir_cuadro(DXF_V2S, str(tmp_path / "a.dxf"))
    campo = sin_respuestas["celdas_sin_resolver"][0]["campo"]

    con_respuestas = plano.escribir_cuadro(
        DXF_V2S, str(tmp_path / "b.dxf"),
        respuestas=[{"tipo": "numerico", "campo": campo, "valor": 65.4}])

    pendientes = {c["campo"] for c in con_respuestas["celdas_sin_resolver"]}
    if campo not in pendientes:                # si la respuesta aplicaba a ese campo
        escritas = {c["campo"]: c["texto"] for c in con_respuestas["celdas_escritas"]}
        assert escritas.get(campo) != "N/D"
