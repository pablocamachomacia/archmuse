# Guardián de AutoCAD (`C-16`)

Comprueba **ejecutando en un AutoCAD real** que ARCHMUSE deja AutoCAD exactamente
como lo encontró: si acaba bien, si falla a medias y si se pulsa Esc. Herramienta
de desarrollo: **no va en el instalador**.

Existe porque ningún test puede verlo desde fuera. El servidor no ve AutoCAD
(`C-7`), y `tests/test_lsp_deja_autocad_como_estaba.py` sólo lee el código.

## Uso

Con un plano abierto en AutoCAD, y el servidor de ArchMuse en marcha si se quiere
probar la pasada completa:

1. `APPLOAD` → `herramientas/guardian_autocad/guardian.lsp`.
2. `ARCHMUSE-GUARDIAN` — foto de antes.
3. `ARCHMUSE` — como se quiera probar. Una pasada por prueba:
   - hasta el final;
   - **Esc** en la pregunta de la capa;
   - **Esc** al pedir el punto;
   - **Esc** en interior/exterior, si sale;
   - con el servidor parado.
4. `ARCHMUSE-GUARDIAN` — foto de después. Dice el resultado y deja el informe en
   `%TEMP%\archmuse-guardian-<fecha>.txt`.

**Entre 2 y 4, ningún otro comando.** Cualquier comando cambia variables por su
cuenta y saldría como si fuera de ArchMuse. **Y en el mismo dibujo:** la foto vive
en el dibujo en el que se hizo. Si el paso 4 dice «foto de antes hecha» en vez
del resultado, no ha comparado: hay que repetir la pasada.

Volver a cargar el guardián ya no borra la foto (2026-09-15). Antes sí, y es la
causa probable, sin medir, de que dos pasadas de la primera prueba no dejaran
informe.

## Qué mira

- **Las variables de sistema de AutoCAD 2027**, sacadas el 2026-09-15 en Core
  Console con `(setvar "QAFLAGS" 2)` y `SETVAR ? *`. Van escritas dentro de
  `guardian.lsp`.
- **El registro**: los valores del perfil activo (`Profiles\<perfil>\Variables`)
  y de `FixedProfile\General Configuration`, que es donde vive FILEDIA
  (`FileDialog`). Una variable puede volver a su valor en la sesión y quedarse
  cambiada para la próxima vez que se abra AutoCAD.

Las diferencias salen en tres grupos:

| Grupo | Qué es | ¿Cuenta? |
|---|---|---|
| Variables cambiadas / registro cambiado | todo lo demás | **sí: AutoCAD NO está como estaba** |
| Cambios de haber dibujado | `DBMOD`, `EXTMIN`, `EXTMAX`, `HANDSEED`, `VSMIN`, `VSMAX`, `LASTPOINT` | no |
| Ignoradas por cambiar solas | la hora, `LASTPROMPT`, `CMDNAMES`, `ERRNO` | no |

Cada variable ignorada lleva su motivo escrito en `guardian.lsp`. **Añadir una
exige escribir el motivo**, no sólo el nombre.

## Comprobar el propio guardián

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File herramientas\guardian_autocad\probar_en_core_console.ps1
```

Lo ejecuta en AutoCAD Core Console, sin AutoCAD con ventanas, en dos pruebas:
cambiar FILEDIA entre las dos fotos (tiene que decir **NO está como estaba** y
nombrar FILEDIA) y no hacer nada (tiene que decir **exactamente como estaba**).
Una sirve para ver que caza y la otra para ver que no da falsos avisos. Trabaja
en `%TEMP%`, nunca en el repositorio.

**Medido el 2026-09-15:** prueba 1, `FILEDIA: 0 -> 1` y «NO está como estaba»;
prueba 2, «exactamente como estaba»; sin errores de AutoLISP. El registro no se
prueba ahí porque Core Console no tiene `vlax-product-key`. Al principio abortaba
por eso mismo: `vl-catch-all-apply` no atrapa una función sin definir, y hubo que
mirar si existe antes de llamarla.

## Qué no mira

- El contenido del dibujo: eso lo protege el grupo de deshacer (`C-3`).
- Las variables que sólo existen en el AutoCAD con ventanas y no lista Core
  Console.

## Sin medir todavía

- **Ruido del registro.** No se sabe si AutoCAD escribe en esas claves por su
  cuenta durante una sesión (posiciones de ventanas, recientes). Si la primera
  pasada limpia sale con «Registro cambiado», ese valor se añade a una lista de
  ignorados **con su motivo**, igual que las variables.

## Por qué no es automático

Se intentó el 2026-09-15 manejando un AutoCAD aparte por COM desde PowerShell, y
no es fiable en esta máquina. Lo que se midió:

- Mientras un `getpoint` espera, AutoCAD rechaza toda llamada COM
  (`RPC_E_CALL_REJECTED`).
- `SendCommand` no vuelve mientras el comando espera entrada, y se bloquea a sí
  mismo.
- La instancia oculta quedaba libre a los 5 s de abrir el DWG con otro AutoCAD
  abierto, y **nunca** después, sin un solo diálogo a la vista.
- `SetVariable("TRUSTEDPATHS")` escribe en el registro al momento, en el perfil
  que se comparte con el AutoCAD del usuario.

Por eso son dos pasos a mano: un Esc aborta toda la evaluación de AutoLISP, y un
guardián que llamase a ARCHMUSE por dentro no llegaría a comparar justo tras el Esc.
