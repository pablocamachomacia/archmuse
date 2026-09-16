# Barrido de DWG con AutoCAD Core Console

Sondas de **solo lectura** para medir planos DWG que `ezdxf` no lee. Se usaron
el 2026-09-15 para medir las referencias externas y los cuadros de superficies
en los 70 DWG de un estudio (ver `docs/PROGRESS.md`, entrada del 2026-09-15).

**Los resultados NO van en este repositorio.** El repositorio es público, y
cada línea de resultado lleva la ruta de un plano de cliente. `barrer.ps1` se
niega a escribir la salida dentro del repositorio. Los del 2026-09-15 están en
`Proyectos/archmuse/_barrido/2026-09-15-xref/`, junto al barrido anterior.

## Reglas

1. **Siempre sobre copias**, nunca sobre la carpeta del estudio. Copiar
   conservando la estructura de carpetas: las xref con ruta relativa sólo se
   resuelven así.
2. Core Console abre cada fichero con `/readonly`, y la sonda no guarda nada.
   **Y se lanza sólo por `herramientas/core_console.py`** (2026-09-16): Core Console
   escribe FILEDIA a 0 en el perfil de AutoCAD del usuario al arrancar y sólo lo
   devuelve si sale limpio; un barrido que mata una consola colgada lo dejaba a 0.
   La puerta la aísla con `/isolate` y devuelve lo que cambie.
3. Lanzar desde **PowerShell**. Desde Git Bash los argumentos `/i` y `/s` llegan
   rotos: la consola abre un dibujo en blanco sin script y se queda esperando.

## Por qué la sonda va incrustada en el `.scr`

Core Console aplica SECURELOAD: un `(load "…")` de un fichero fuera de las rutas
de confianza se cancela («Carga de archivos cancelada»). `incrustar.py` convierte
la sonda en un `.scr` con una forma por línea. No admite `;` dentro del código
(sólo líneas de comentario enteras) ni deja líneas en blanco: en un `.scr` una
línea vacía repite el último comando.

## Las sondas

| Fichero | Función | Una línea por dibujo con… |
|---|---|---|
| `sonda_xref.lsp` | `sonda` | xrefs (bit 4), cargadas (bit 32), inserciones, polilíneas que ve `ssget "_X"`, polilíneas en capas `*AREA*` propias y dentro de cada xref cargada |
| `sonda_areas.lsp` | `sonda2` | por capa `*AREA*`: número de polilíneas y superficie (Gauss), propias y dentro de xref |
| `sonda_cuadros.lsp` | `sonda3` | `ACAD_TABLE` que ve `ssget "_X"`, cuántas son cuadros, en qué espacio, cuadros dentro de xref, textos sueltos con «SUPERFICIE» |
| `sonda_textos.lsp` | `sonda4` | los textos con «SUPERFICIE», agrupados por espacio, capa y contenido |

**Aproximación declarada:** «recinto» es una polilínea en una capa cuyo nombre
contiene «area». No es la elección de capa del servidor.

## Uso

```powershell
.\barrer.ps1 -Copias C:\ruta\copias -Sonda .\sonda_xref.lsp -Funcion sonda `
             -Salida C:\fuera\del\repo\xref.tsv -UnoPorHuella
```

`-UnoPorHuella` abre un solo fichero por contenido idéntico (MD5). Junto a la
salida se escribe `<salida>.huellas.tsv` con la huella y el estado de cada
fichero (`ok`, `TIMEOUT`, `SIN_LINEA`). Alrededor de un minuto por DWG.
