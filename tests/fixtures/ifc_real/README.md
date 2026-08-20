# IFC reales de terceros, para probar `bim/lector_ifc.py` contra software real

Tres ficheros descargados de [`buildingSMART/Sample-Test-Files`](https://github.com/buildingSMART/Sample-Test-Files)
(repositorio oficial de buildingSMART, licencia CC BY 4.0, publicado
explícitamente para pruebas de interoperabilidad IFC — uso exactamente para
esto). Añadidos el 2026-08-20, paso 3 del roadmap ("avanzar la lectura de
modelo BIM real"), para que `tests/test_bim_lector.py` deje de probar
*solo* el round-trip sintético de `analyzer/ifc_export.py` y compruebe
también que el lector aguanta ficheros que ArchMuse no ha escrito.

- **`Building-Architecture.ifc`** — exportado por SketchUp (IFC-manager for
  SketchUp 5.3.3). `IFC 4.0.2.1 (IFC 4)/PCERT-Sample-Scene/`. Una planta,
  2 `IfcSpace`, 4 `IfcWall`, 3 `IfcSlab`. Sin puertas/ventanas como objetos
  propios.
- **`Building-Structural.ifc`** — mismo escenario, disciplina estructural,
  software distinto. `IfcBeam`(6), `IfcWall`(4), `IfcBuildingElementProxy`(3),
  `IfcFooting`(1), `IfcRoof`(1), `IfcChimney`(1), `IfcDiscreteAccessory`(2) —
  ninguna de estas clases (salvo Wall/Beam) estaba en la lista fija que el
  lector usaba antes de esta ampliación; motivó el cambio a un inventario de
  clases completo (`_conteo_por_clase`), no una lista predefinida.
- **`wall-with-opening-and-window.ifc`** — fichero de referencia de la ISO
  Spec (`IFC 4.0.2.1 (IFC 4)/ISO Spec - ReferenceView_V1.2/`), pequeño (12KB),
  con un `IfcWindow` real con `OverallWidth`/`OverallHeight` declarados
  (1000mm × 1000mm) — el caso de prueba más directo para la lectura de
  aberturas añadida en esta misma ampliación.

Los tres declaran la longitud del proyecto en **milímetros** (`LENGTHUNIT`,
escala 0.001) pero área y volumen en unidades SI **ya en metros/m³**
(`AREAUNIT`/`VOLUMEUNIT`, escala 1) — confirmó que ese patrón mixto no es una
rareza de un fichero, es el uso estándar de `IfcUnitAssignment`, y es
exactamente el bug que motivó la corrección de unidades del mismo cambio
(ver el docstring de `bim/lector_ifc.py`).
