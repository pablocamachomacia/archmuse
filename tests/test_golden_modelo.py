# -*- coding: utf-8 -*-
"""G9 — golden del MODELO: `modelo.constructor.construir(ejemplo.dxf)`.

Ejecutar:  python tests/test_golden_modelo.py

Congela el modelo entero serializado —nodos, identidades, atributos, aristas,
geometría y sellado— más dos cosas que el formato deliberadamente no persiste:

1. **Los derivados por espacio.** Salieron del JSON porque son función pura de
   la geometría y persistirlos junto a su fuente rompía el round-trip (ver la
   cabecera de `modelo/serializacion.py`). Congelarlos **aquí** sí procede: es
   trabajo del golden, no del formato, y sin ellos un cambio de geometría de
   un milímetro pasaría desapercibido.

2. **La equivalencia con G3.** Las aristas `conecta_con` del modelo deben ser
   exactamente los 45 pares que `analyzer/adyacencia.py` produce hoy, con las
   mismas separaciones y las mismas distancias entre centroides. Es la prueba
   operativa de que E1 es neutro: si el modelo viera la topología de otra
   manera, `circulation.py` daría otros recorridos en cuanto se migrara.

**Semilla fija.** `concept_id` es opaco, y sin semilla sería un `uuid4`
distinto en cada ejecución. Con `semilla="golden-e1"` es un `uuid5` sobre
`(semilla, instance_id)`: sigue siendo opaco —no se lee de él ni el área ni el
rótulo— y es reproducible, que es lo que permite congelarlo. En producción,
sin semilla, cada proyecto nace una vez y `uuid4` es lo correcto.
"""
import golden

from modelo import constructor, serializacion
from modelo.aristas import CONECTA_CON
from modelo.geometria import HUELLA_2D

SEMILLA = "golden-e1"


def _equivalencia_con_g3(modelo):
    """Compara las aristas del modelo con el fixture de G3, par a par.

    G3 identifica los recintos por su índice en el orden de lectura del
    parser; el modelo, por `instance_id`. El puente es el orden: el
    constructor crea un espacio por `Room` en el orden en que
    `group_rooms_by_unit_label` devuelve las viviendas, que es el mismo orden
    en que G3 recorre las unidades.
    """
    g3 = golden.cargar("G3_adyacencia")
    esperadas = []
    for unidad in g3["unidades"]:
        for arista in unidad["aristas"]:
            esperadas.append((
                unidad["nombre"], arista["rotulo_i"], arista["rotulo_j"],
                round(arista["separacion_m"], 3), round(arista["distancia_m"], 3),
            ))

    obtenidas = []
    for unidad in modelo.unidades():
        nombre = str(unidad.etiqueta.valor)
        propios = set(unidad.espacios)
        for arista in modelo.aristas(CONECTA_CON):
            if arista.a not in propios:
                continue
            obtenidas.append((
                nombre,
                modelo.get_space(arista.a).rotulo,
                modelo.get_space(arista.b).rotulo,
                round(arista.separacion_m, 3), round(arista.distancia_m, 3),
            ))

    faltan = sorted(set(esperadas) - set(obtenidas))
    sobran = sorted(set(obtenidas) - set(esperadas))
    return {
        "n_en_G3": len(esperadas),
        "n_en_el_modelo": len(obtenidas),
        "coinciden": not faltan and not sobran and len(esperadas) == len(obtenidas),
        "solo_en_G3": ["%s: %s-%s" % (u, a, b) for u, a, b, _s, _d in faltan],
        "solo_en_el_modelo": ["%s: %s-%s" % (u, a, b) for u, a, b, _s, _d in sobran],
    }


def construir():
    plano = golden.plano()
    modelo = constructor.construir(plano, semilla=SEMILLA, fichero="ejemplo.dxf")

    texto = serializacion.volcar(modelo)
    recargado = serializacion.cargar(texto)

    return {
        "semilla": SEMILLA,
        "round_trip_exacto": serializacion.volcar(recargado) == texto,
        "sellado_verificado": serializacion.verificar_sellado(modelo),
        "modelo": serializacion.a_dict(modelo),
        # Fuera del formato a propósito; congelados aquí (ver docstring).
        "derivados": [
            dict(id=e.id, **modelo.almacen.derivados(e.geometrias[HUELLA_2D]))
            for e in sorted(modelo.get_spaces(), key=lambda e: e.id)
        ],
        "equivalencia_G3": _equivalencia_con_g3(modelo),
        "desconocidos": sorted(modelo.desconocidos()),
    }


def ejecutar_golden() -> int:
    return golden.ejecutar("G9_modelo", construir,
                           "modelo comun serializado + equivalencia con G3")


if __name__ == "__main__":
    raise SystemExit(ejecutar_golden())
