# -*- coding: utf-8 -*-
"""El modelo arquitectónico común de ArchMuse — capa de instancia.

Diseño de referencia: `docs/design/2026-08-11-modelo-arquitectonico-comun.md`
y `docs/brain/KNOWLEDGE_GRAPH.md`. Contrato implementado: C1–C8 de
`docs/prd/2026-08-11-e0-modelo-arquitectonico.md`.

**Qué es esta capa.** El sitio donde *un proyecto concreto* existe como grafo
de objetos con identidad, geometría referenciada y relaciones explícitas, en
vez de como la lista plana de polígonos que hoy viaja del parser al evaluador.
Es el punto de encuentro previsto para importación, normativa, editor, 2D, 3D,
generación y persistencia.

**Qué NO es.** No juzga. Ningún nodo lleva `iluminacion`, `cumple`,
`puntuacion` ni `problemas`: el modelo guarda *lo que el proyecto es*, y el
motor concluye *lo que cumple, vale o arriesga* (`KNOWLEDGE_GRAPH.md` §0.1).
La frontera la vigila `tests/test_modelo_fronteras.py`, no la buena voluntad.

**Estado real (E1).** Cinco nodos de once, dos relaciones, una representación
geométrica. `Muro`, `Hueco`, `Parcela`, `Pilar`, `Instalación` y `Zona común`
existen **sólo como entrada en el mapa de presencia**, declarados y vacíos. No
es un olvido: siete clases vacías durante meses son una invitación a
rellenarlas con valores plausibles (`KNOWLEDGE_GRAPH.md` §8.1).

Orden de dependencia interno, estricto (de abajo arriba, sin ciclos):

    identidad ─┐
    atributo  ─┼─► nodos ─► aristas ─► grafo ─► invariantes ─► serializacion
    geometria ─┘                          ▲
                                          │
                        constructor ──────┘   (único que mira el sustrato actual)
                        compat ───────────┘   (única salida hacia `evaluator.Unit`)
"""
from .aristas import CONECTA_CON, ES_CONTIGUO_A, Arista, Criterio
from .atributo import DECLARADO, DERIVADO, OBSERVADO, SUPUESTO, Atributo, desconocido
from .geometria import AlmacenGeometria, HUELLA_2D
from .grafo import Grafo, VistaUnidad
from .identidad import Identidades
from .invariantes import ModeloInvalido, comprobar_invariantes
from .nodos import Edificio, Espacio, Planta, Procedencia, Proyecto, Unidad
from .serializacion import cargar, sellado_de, volcar

__all__ = [
    "AlmacenGeometria", "Arista", "Atributo", "CONECTA_CON", "Criterio",
    "DECLARADO", "DERIVADO", "Edificio", "ES_CONTIGUO_A", "Espacio", "Grafo",
    "HUELLA_2D", "Identidades", "ModeloInvalido", "OBSERVADO", "Planta",
    "Procedencia", "Proyecto", "SUPUESTO", "Unidad", "VistaUnidad", "cargar",
    "comprobar_invariantes", "desconocido", "sellado_de", "volcar",
]
