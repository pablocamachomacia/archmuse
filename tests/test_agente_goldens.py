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


def construir_dxf_incoherente(destino: Path) -> str:
    """Un piso con defectos DE VERDAD, para congelar la revision de coherencia.

    El fixture limpio (`construir_dxf`) no sirve aqui: congelaria «cero
    hallazgos», que es la salida menos informativa posible y la que seguiria
    pasando aunque alguien rompiera las cuatro comprobaciones. Este trae, a
    proposito, los tres defectos que el plano real del cliente tambien tiene:

    - dos piezas que se solapan de verdad (no que compartan borde);
    - el mismo rotulo repetido, que es lo que impide el reparto automatico;
    - una polilinea con el flag `closed` mal puesto.
    """
    import ezdxf

    from analyzer import parser

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6                    # metros
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()

    def rect(x0, y0, x1, y1, etiqueta, cerrada=True):
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=cerrada,
                           dxfattribs={"layer": parser.AREA_LAYER})
        msp.add_mtext(etiqueta, dxfattribs={"layer": parser.AREA_LAYER}).set_location(
            ((x0 + x1) / 2.0, (y0 + y1) / 2.0))

    rect(0.0, 0.0, 4.0, 3.0, "Salon")
    # Se solapa 2 m2 con el salon: no comparten borde, se pisan.
    rect(3.0, 0.0, 6.0, 2.0, "Terraza")
    # Mismo rotulo dos veces: el cuadro tiene un hueco por familia.
    rect(0.0, 5.0, 2.0, 7.0, "Tendedero")
    rect(3.0, 5.0, 5.0, 7.0, "Tendedero")
    # `close=False` y los extremos NO coinciden: el parser la descarta con su
    # motivo, y ese descarte tiene que llegar al informe en vez de perderse.
    rect(7.0, 0.0, 9.0, 2.0, "Aseo", cerrada=False)
    # `close=False` pero con el primer vertice repetido al final: el parser la
    # trata como cerrada y lo avisa. Es una correccion de datos, no un hecho
    # neutro, y hoy ese aviso sale por `logging` y no lo lee nadie.
    msp.add_lwpolyline(
        [(7.0, 5.0), (9.0, 5.0), (9.0, 7.0), (7.0, 7.0), (7.0, 5.0)],
        close=False, dxfattribs={"layer": parser.AREA_LAYER})
    msp.add_mtext("Bano", dxfattribs={"layer": parser.AREA_LAYER}).set_location((8.0, 6.0))

    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.AREA_LAYER}).set_location((-3.0, 2.0))
    ruta = destino / "piso_incoherente.dxf"
    doc.saveas(str(ruta))
    return str(ruta)


def construir_dxf_de_planta(destino: Path) -> str:
    """Dos viviendas en la misma planta, cada una con su rotulo `VT`.

    El fixture limpio (`construir_dxf`) tiene UNA vivienda, y congelar la
    medicion contra el no probaria lo unico que esta capacidad existe para
    hacer: no rendirse ante la segunda. Las dos van separadas 20 m para que el
    reparto sea holgado -- lo apretado tiene su propio test en
    `tests/test_medicion_de_planta.py`, aqui interesa congelar el caso normal.
    """
    import ezdxf

    from analyzer import parser

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6                    # metros
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()

    def pieza(x0, y0, x1, y1, etiqueta):
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                           dxfattribs={"layer": parser.AREA_LAYER})
        msp.add_mtext(etiqueta, dxfattribs={"layer": parser.AREA_LAYER}).set_location(
            ((x0 + x1) / 2.0, (y0 + y1) / 2.0))

    for desplazamiento, nombre in ((0.0, "VT1/1"), (30.0, "VT2/1")):
        pieza(desplazamiento, 0.0, desplazamiento + 5.0, 4.0, "Salon/cocina")   # 20
        pieza(desplazamiento, 4.0, desplazamiento + 4.0, 7.0, "Dormitorio 1")   # 12
        pieza(desplazamiento + 5.0, 0.0, desplazamiento + 7.0, 2.0, "Bano")     # 4
        pieza(desplazamiento + 5.0, 3.0, desplazamiento + 8.0, 6.0, "Terraza")  # 9
        msp.add_mtext(nombre, dxfattribs={"layer": parser.AREA_LAYER}).set_location(
            (desplazamiento + 4.0, -3.0))

    ruta = destino / "planta.dxf"
    doc.saveas(str(ruta))
    return str(ruta)


# `construir_ifc()` vivia aqui y se ha ido con el caso golden de
# `bim.inventario_de_ifc`, retirada del registro el 2026-08-19 (D-12).
# Cuando `OP-5` vuelva a registrar esa capacidad, el helper se recupera del
# historial: `git log -p -- tests/test_agente_goldens.py`.


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
    "plano.coherencia": {
        # Contra el fixture CON defectos, no contra el limpio: congelar «cero
        # hallazgos» seguiria pasando aunque alguien rompiera las cuatro
        # comprobaciones. El `handle` de la polilinea mal cerrada lo asigna
        # ezdxf al guardar y no es contenido del hallazgo, asi que es volatil.
        "argumentos": lambda d: {"ruta": construir_dxf_incoherente(d)},
        "volatiles": ("ruta", "entidad", "handle", "descripcion"),
    },
    "plano.medicion_de_la_planta": {
        # Contra el fixture de DOS viviendas: es lo unico que esta capacidad
        # hace y las otras no, asi que congelarla contra el piso de una sola
        # dejaria sin vigilar precisamente el motivo por el que existe.
        "argumentos": lambda d: {"ruta": construir_dxf_de_planta(d)},
        "volatiles": ("ruta",),
    },
    "proyecto.ajustar_programa": {
        # Pura aritmetica sobre un diccionario: no toca ficheros ni red, asi
        # que el caso congelado es el camino BUENO y no una negativa.
        "argumentos": {
            "parametros": {
                "proyecto": {"ciudad": "Madrid", "tipologia": "plurifamiliar"},
                "solar": {"superficie_m2": 600.0},
                "edificio": {"plantas": 4, "altura_libre_m": 2.8},
                "mix_viviendas": {"dorm_1": 2, "dorm_2": 6, "dorm_3": 2,
                                  "superficie_minima_m2": 45.0},
                "normativa": {"ocupacion_maxima_pct": 70.0, "retranqueos_m": 3.0},
                "superficie_objetivo_m2": 900.0,
            },
            "operacion": "cambiar_mix",
            "argumentos": {"dorm_2": "-1"},
        },
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
