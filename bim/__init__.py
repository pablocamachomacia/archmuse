# -*- coding: utf-8 -*-
"""La frontera BIM: IFC entra y sale, pero nunca es el modelo interno.

**La decisión que este paquete existe para hacer cumplir** está razonada en
`docs/design/2026-08-18-revision-stack-2026.md` §4: IFC es un **formato de
intercambio**, no la representación interna del proyecto. La lógica de dominio
se escribe contra el grafo de `modelo/`; aquí vive la traducción, en los dos
sentidos.

**Por qué importa antes de que exista Revit.** Revit no habla IFC nativo, habla
su API .NET. Un `RevitDocument` y un `IfcFile` solo tienen en común lo que el
grafo ya sabe representar. Si la lógica de dominio se escribiera contra
`ifcopenshell`, el día que entre Revit habría que reescribirla; escrita contra
el grafo, Revit es un adaptador más al lado de este.

**Reglas del paquete, y son las mismas que las de `normativa/`:**

- No importa `agente/` ni `analyzer/`: la dependencia va del agente a la
  frontera, nunca al revés.
- No importa transporte. Se invoca igual desde la web que desde un complemento.
- **No juzga.** Lee lo que el fichero dice y declara lo que no dice. Un modelo
  IFC sin superficies declaradas produce superficies `None` con motivo, no
  superficies calculadas en silencio: son dos afirmaciones distintas y
  confundirlas es exactamente lo que un arquitecto no perdona.

Estado: **solo lectura**. La escritura de IFC ya existe en
`analyzer/ifc_export.py` y se moverá aquí cuando el vertical lo pida; hacerlo
hoy movería 300 líneas probadas sin ganar nada.
"""
from .lector_ifc import InventarioIFC, IFCIlegible, inventariar

__all__ = ["IFCIlegible", "InventarioIFC", "inventariar"]
