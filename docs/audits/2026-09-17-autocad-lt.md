# ¿Funcionaría el comando en AutoCAD LT 2024 o posterior? (informe, 2026-09-17)

Encargo de Pablo: averiguarlo **sin instalar nada**; sólo informe. Nada de esto se
ha ejecutado en un AutoCAD LT.

## Respuesta corta

**No, tal como está.** Las dos cosas sin las que el comando no mide usan objetos COM
externos, y AutoCAD LT no los permite:

1. **Hablar con el servidor local.** `am:peticion` crea `WinHttp.WinHttpRequest.5.1`
   con `vlax-create-object`.
2. **Arrancar el servidor y esperar a procesos.** `am:lanzar-sin-ventana` y
   `am:ejecutar-y-esperar` crean `WScript.Shell` con `vlax-create-object`.

Lo demás —leer el dibujo, dibujar la tabla, deshacer, el arrastre— usa AutoLISP y el
ActiveX interno de AutoCAD, que la documentación dice que LT sí admite en su mayoría.

## Lo que dice la documentación pública (no medido aquí)

Desde AutoCAD LT 2024 (Windows) se cargan y ejecutan `.lsp`, `.fas`, `.vlx` y `.dcl`.
Límites publicados que tocan a ArchMuse:

- **No hay objetos ActiveX externos:** ni `vlax-create-object`, ni `vlax-get-object`,
  ni `vlax-get-or-create-object`, ni `vlax-import-type-library`, ni
  `vla-GetInterfaceObject`.
- La mayoría de las funciones `vl-`, `vla-`, `vlax-` y `vlr-` sí están.
- Ni Express Tools (`acet-`), ni VBA/ARX/.NET, ni editor VLIDE.
- La carga automática usa `ACADLTDOC.LSP`, no `ACADDOC.LSP`.
- En Mac, LT no tiene LISP.

Fuentes: [CAD Forum, límites de LISP en AutoCAD LT](https://www.cadforum.cz/en/limitations-of-the-lisp-language-autolisp-visuallisp-autocad-lt-tip13683);
[referencia de AutoLISP de AutoCAD LT 2024 (Autodesk)](https://help.autodesk.com/cloudhelp/2024/DEU/AutoCAD-LT-AutoLISP-Reference/files/GUID-7AFF597F-D630-4489-8349-94EF67CCE1F0.htm);
[novedades de AutoLISP en 2024 (Autodesk)](https://help.autodesk.com/view/ACD/2024/ENU/?guid=GUID-037BF4D4-755E-4A5C-8136-80E85CCEDF3E).

## Lo que usa el `.lsp` (contado en el código, 3.9.8)

| Familia | Veces | Para qué | ¿En LT? (según la documentación) |
|---|---|---|---|
| `vlax-create-object` | 3 | HTTP al servidor; lanzar procesos | **No** |
| `vla-*` / `vlax-*` internos | ~70 / ~29 | leer tablas, dibujar la `ACAD_TABLE`, estilos, cajas, deshacer | Sí, en su mayoría (sin medir uno a uno) |
| `startapp` | 1 | empaquetar `ARCHMUSE-INFORME` con PowerShell | Hipótesis: sí (es AutoLISP básico) |
| `(command ...)` | `_.DELAY`, `_.MOVE`, `_.U` | esperar, arrastrar, deshacer | Hipótesis: sí |
| `vl-file-*`, `open`/`read-line` | varias | registro, `servidor.json`, `actualizacion.json` | Hipótesis: sí |
| `vlr-*`, `vl-registry-*`, `acet-*`, DOSLib | 0 | — | — |

## Qué lo impediría además (hipótesis, sin medir)

- **La carga.** ArchMuse se instala como *bundle* en `ApplicationPlugins`. No se sabe
  si LT carga los bundles de terceros; el comentario de `PackageContents.xml` («En
  AutoCAD LT no carga LISP») es anterior a LT 2024 y no se ha medido.
- **`vla-AddTable` y los estilos de tabla** (`AcDbTableStyle` por diccionario): son
  ActiveX interno y deberían estar, pero la documentación no los lista uno a uno.

## Qué haría falta para que funcionara (sólo propuesta)

Sustituir los dos usos de COM externo:
- **Arrancar el servidor:** `startapp` en vez de `WScript.Shell` (no espera, pero
  el comando ya sondea el puerto).
- **HTTP:** AutoLISP no tiene HTTP propio. Una salida sería intercambiar ficheros:
  el comando escribe la petición en un fichero y un pequeño cliente la manda y deja
  la respuesta. Es un cambio de arquitectura del lado del comando: pediría PRD.

## Mensajes que tocan esto

`am:peticion` dice «Si esto es AutoCAD LT, no hay solución: LT no permite crear
objetos COM». Coincide con la documentación publicada para LT 2024, pero **no se ha
medido en un LT**. El folio dice «No funciona en AutoCAD LT», que es lo que se
espera por lo anterior.
