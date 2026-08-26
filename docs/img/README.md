# Capturas de la interfaz

El README **no enlaza todavía** ninguna imagen, a propósito: un enlace a un fichero
que no existe pinta un icono roto en GitHub, que es peor que no tener captura. Las
líneas que hay que pegar están al final de este documento, y se pegan **cuando los
ficheros ya estén aquí**.

## Cómo levantar la aplicación

```bash
cp .env.example .env      # rellena ANTHROPIC_API_KEY y MAPBOX_TOKEN
venv\Scripts\activate     # bash/zsh: source venv/bin/activate
python app.py
```

Sin `ANTHROPIC_API_KEY` no hay diagnóstico y sin `MAPBOX_TOKEN` no hay visor 3D:
las dos capturas que más enseñan necesitan las dos claves.

## Qué capturar

Tres imágenes, y ninguna de adorno: cada una demuestra una de las tres cosas que el
README afirma que ya funcionan de punta a punta.

| Fichero | Con qué plano | Qué debe verse |
|---|---|---|
| `superficies.png` | `tests/fixtures/dxf_plausibles/01_control_estancias.dxf` | El cuadro de superficies relleno desde el DXF, con los nombres de estancia leídos del plano —no "Polilínea 7"— y las unidades declaradas por el fichero |
| `revision.png` | `tests/fixtures/dxf_tortura/06_etiquetas_duplicadas_y_huerfanas.dxf` | La revisión de coherencia **encontrando los problemas de ese plano**: etiquetas duplicadas y rótulos huérfanos. Es la captura más importante: enseña la herramienta cazando algo, no rellenando una tabla |
| `trazabilidad.png` | cualquiera de las dos anteriores | Una cifra concreta con su origen a la vista: de qué entidad del DXF sale. Es el argumento del proyecto —"nunca inventa un número"— y es lo único que lo distingue de un extractor de áreas cualquiera |

Si el visor 3D/IFC queda presentable con `MAPBOX_TOKEN` puesto, añade `visor.png`
como cuarta. Va la última porque es la más vistosa y la menos argumental: enseña
que el proyecto es bonito, no que sea fiable.

## Consejos

- **Ventana de ~1400 px de ancho.** Más estrecho y las tablas hacen scroll horizontal.
- **Página completa** si el navegador lo permite (Chrome: F12 → Ctrl+Shift+P →
  «Capture full size screenshot»). Si no cabe, es preferible recortar por una
  frontera limpia entre secciones que dejar una tabla cortada por la mitad.
- **Nada de planos reales.** Usa solo los DXF de `tests/fixtures/`, que son
  sintéticos. Un plano de cliente en una captura es la misma fuga de datos que un
  plano de cliente commiteado, y el historial tampoco la olvida.
- **Revisa la captura antes de guardarla.** Si sale un panel a medio cargar o una
  sección vacía, no la subas: una interfaz a medio llenar comunica peor que ninguna
  interfaz.

## Líneas para el README

Cuando los ficheros existan, pegar en `README.md` bajo la sección que corresponda:

```markdown
![Cuadro de superficies](docs/img/superficies.png)
![Revisión de coherencia](docs/img/revision.png)
![Trazabilidad de una cifra](docs/img/trazabilidad.png)
```
