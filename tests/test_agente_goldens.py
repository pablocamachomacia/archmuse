# -*- coding: utf-8 -*-
"""TL-4 — ninguna capacidad determinista entra sin su golden.

Ejecutar:  pytest tests/test_agente_goldens.py
Recapturar: python tests/test_agente_goldens.py --recapturar   (y explicar por qué)

**Qué garantiza esto y por qué es barato.** Una capacidad `determinista` promete
que la misma entrada da la misma salida siempre. Esa promesa es lo que permite
guardar un plan y reproducirlo dentro de dos años, y lo que hace seguro relanzar
un trabajo interrumpido. Una promesa que nadie comprueba dura hasta el primer
martes con prisa, así que aquí se comprueba de dos formas:

1. **Cada capacidad determinista del registro tiene un caso congelado** en
   `tests/fixtures/golden/G11_capacidades.json`. Añadir una capacidad sin
   golden pone la suite en rojo. El test recorre el registro, no una lista
   escrita a mano: cubre también las capacidades que aún no existen.
2. **El resultado congelado se compara entero**, no por campos elegidos. Un
   campo nuevo que aparece sin que nadie lo haya querido es exactamente el tipo
   de cambio que un golden existe para enseñar.

**Lo que se excluye de la comparación, y por qué.** Sólo lo que depende de
*dónde* está el fichero o de *cuándo* se generó —rutas temporales, GUIDs de
IFC—, nunca lo que depende de qué dice. La lista va por caso, declarada y con
motivo: un `volatiles` que crece sin justificación es un golden que deja de
comprobar cosas sin avisar.

**Recapturar no es un trámite.** Si este fichero cambia, alguien ha cambiado el
criterio de un cálculo. La orden `--recapturar` existe para no reescribir JSON a
mano, no para pasar de rojo a verde sin mirar el diff.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente.manifiesto import invocar  # noqa: E402
from agente.registro import registro  # noqa: E402

GOLDEN = RAIZ / "tests" / "fixtures" / "golden" / "G11_capacidades.json"

CID_EVACUACION = "es.rd_314_2006.seguridad_incendio.longitud_recorrido_evacuacion"

#: Un piso mínimo con superficies redondas: 20, 9, 12 y 4 m². Si el golden
#: cambia, la diferencia se lee a simple vista.
PIEZAS = (
    ("Salón", (0.0, 0.0), (5.0, 4.0)),
    ("Cocina", (5.0, 0.0), (8.0, 3.0)),
    ("Dormitorio 1", (0.0, 4.0), (4.0, 7.0)),
    ("Baño", (5.0, 3.0), (7.0, 5.0)),
)


def construir_dxf(destino: Path) -> str:
    """El mismo piso siempre, en la capa heredada y declarando metros."""
    import ezdxf

    from analyzer import parser

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6                    # metros
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()
    for etiqueta, (x0, y0), (x1, y1) in PIEZAS:
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                           dxfattribs={"layer": parser.AREA_LAYER})
        msp.add_mtext(etiqueta, dxfattribs={"layer": parser.AREA_LAYER}).set_location(
            ((x0 + x1) / 2.0, (y0 + y1) / 2.0))
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.AREA_LAYER}).set_location((-3.0, 2.0))
    ruta = destino / "piso.dxf"
    doc.saveas(str(ruta))
    return str(ruta)


def construir_ifc(destino: Path) -> str:
    """Un IFC escrito por el propio repositorio.

    Contra un fichero fabricado a mano el golden diría que el lector entiende
    lo que yo creo que dice un IFC; contra lo que ArchMuse exporta, dice que
    las dos mitades de la frontera se entienden entre sí.
    """
    from analyzer.ifc_export import exportar_espacios_ifc

    modelo = exportar_espacios_ifc(
        [{"nombre": n, "poligono": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
          "area_m2": round((x1 - x0) * (y1 - y0), 2)}
         for n, (x0, y0), (x1, y1) in PIEZAS],
        nombre_planta="Planta baja",
    )
    ruta = destino / "piso.ifc"
    modelo.write(str(ruta))
    return str(ruta)


#: id de capacidad -> cómo invocarla y qué no se compara.
#:
#: `argumentos` puede ser un dict, o una función que recibe el directorio
#: temporal y devuelve el dict — para los casos que necesitan un fichero.
CASOS = {
    "territorial.resolver_ambito": {
        "argumentos": {"municipio": "Madrid"},
    },
    "normativa.reglas_aplicables": {
        "argumentos": {"codigo_municipio": "28079", "uso": "residencial.vivienda_libre",
                       "tipologia": "plurifamiliar", "fecha_devengo": "2026-01-01"},
    },
    "normativa.umbral_de_regla": {
        "argumentos": {"concept_id": CID_EVACUACION, "ambito_id": "es",
                       "ejes": {"numero_salidas": "una", "condicion": "general"}},
    },
    "bim.inventario_de_ifc": {
        "argumentos": lambda d: {"ruta": construir_ifc(d)},
        # El GUID de un IfcSpace se genera nuevo en cada exportación: es
        # identidad de fichero, no contenido del modelo.
        "volatiles": ("identificador",),
    },
    "plano.leer_dxf": {
        "argumentos": lambda d: {"ruta": construir_dxf(d)},
        "volatiles": ("ruta",),
    },
    "plano.superficie_util": {
        "argumentos": lambda d: {"ruta": construir_dxf(d)},
        "volatiles": ("ruta",),
    },
    "plano.cuadro_de_superficies": {
        # Un `ACAD_TABLE` no se sintetiza de forma realista, así que el caso
        # congelado es el de un DXF sin cuadro: la negativa, con su motivo.
        # El camino bueno lo cubre `tests/test_agente_plano.py` contra el
        # v2s.dxf real cuando `ARCHMUSE_DXF_V2S` está definida. Anotarlo aquí
        # es la única forma honesta de decir hasta dónde llega este golden.
        "argumentos": lambda d: {"ruta": construir_dxf(d)},
        "volatiles": ("ruta", "detalle", "pregunta"),
    },
}


def _limpiar(valor, volatiles):
    """Quita recursivamente las claves volátiles declaradas."""
    if isinstance(valor, dict):
        return {k: _limpiar(v, volatiles) for k, v in valor.items() if k not in volatiles}
    if isinstance(valor, list):
        return [_limpiar(v, volatiles) for v in valor]
    return valor


def ejecutar_caso(identificador: str, directorio: Path) -> dict:
    caso = CASOS[identificador]
    argumentos = caso["argumentos"]
    if callable(argumentos):
        argumentos = argumentos(directorio)
    resultado = invocar(registro().buscar(identificador), **argumentos)
    return _limpiar(json.loads(json.dumps(resultado, ensure_ascii=False, default=str)),
                    set(caso.get("volatiles", ())))


def _golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8")) if GOLDEN.exists() else {}


# --- La política -----------------------------------------------------------

def test_toda_capacidad_determinista_tiene_su_golden():
    """LA TAREA `TL-4` EN UNA LÍNEA.

    Recorre el registro. Si mañana alguien añade una capacidad determinista y
    no congela su salida, esto se pone rojo — sin que nadie tenga que acordarse
    de venir a este fichero a apuntarla.
    """
    deterministas = {c.id for c in registro(recargar=True) if c.naturaleza == "determinista"}
    sin_caso = sorted(deterministas - set(CASOS))
    assert sin_caso == [], (
        "capacidades deterministas sin caso golden: %s. Una capacidad determinista "
        "promete que la misma entrada da la misma salida siempre; sin golden, esa "
        "promesa no la comprueba nadie." % sin_caso
    )
    sin_congelar = sorted(set(CASOS) - set(_golden()))
    assert sin_congelar == [], (
        "casos declarados y no congelados en %s: %s" % (GOLDEN.name, sin_congelar))


def test_no_hay_casos_de_capacidades_que_ya_no_existen():
    """El reverso: un golden de algo que se ha borrado da falsa sensación de
    cobertura y esconde que una capacidad desapareció."""
    ids = set(registro(recargar=True).ids())
    assert sorted(set(CASOS) - ids) == []


@pytest.mark.parametrize("identificador", sorted(CASOS))
def test_el_resultado_congelado_no_ha_cambiado(identificador, tmp_path):
    esperado = _golden().get(identificador)
    assert esperado is not None, "falta %s en %s" % (identificador, GOLDEN.name)
    assert ejecutar_caso(identificador, tmp_path) == esperado


@pytest.mark.parametrize("identificador", sorted(CASOS))
def test_dos_ejecuciones_seguidas_coinciden(identificador, tmp_path):
    """El golden dice que hoy coincide con otro día; esto dice que coincide
    consigo mismo. Sin las dos, un no-determinismo intermitente pasa."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    assert (ejecutar_caso(identificador, tmp_path / "a")
            == ejecutar_caso(identificador, tmp_path / "b"))


def _recapturar() -> None:
    golden = {
        "_nota": ("G11 — salida congelada de cada capacidad determinista (TL-4). "
                  "Generado por `python tests/test_agente_goldens.py --recapturar`. "
                  "Si cambia, alguien ha cambiado el criterio de un cálculo: hay que "
                  "decir quién y por qué en el mismo cambio, no recapturar y seguir."),
    }
    for identificador in sorted(CASOS):
        with tempfile.TemporaryDirectory() as directorio:
            golden[identificador] = ejecutar_caso(identificador, Path(directorio))
    GOLDEN.write_text(json.dumps(golden, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Recapturado %s con %d casos." % (GOLDEN.name, len(CASOS)))


if __name__ == "__main__":
    if "--recapturar" in sys.argv:
        _recapturar()
    else:
        print(__doc__)
