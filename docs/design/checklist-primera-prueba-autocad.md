# Checklist — primer día de trial de AutoCAD

**Fecha:** 2026-09-08 · **PRD:** `docs/prd/2026-09-08-integracion-autocad-autolisp.md`
(**Borrador, sin aprobar** — si el PRD cambia de salida técnica, los pasos 5-9 de
este documento cambian con él).

**Para qué existe:** el trial es un reloj corriendo. Este documento es el orden
del día para no improvisar. **Se lee entero antes de instalar nada.**

**Regla de oro de este documento:** cada prueba dice, si falla, **de quién es la
culpa** — del *flujo* (la idea no sirve) o del *lenguaje* (AutoLISP es incómodo).
Es la única forma de que un prototipo fallido siga siendo informativo (`R-1` del
PRD).

---

## Paso 0 · Antes de activar el trial (hazlo hoy, no el día 1)

- [ ] **El trial es de AutoCAD completo, NO de AutoCAD LT.** `vlax-create-object`
      no existe en LT: devuelve `nil` siempre, y sin él no hay HTTP. Un trial de
      LT hace inejecutable el prototipo entero, y no se puede deshacer.
- [ ] Windows: el objeto COM `WinHTTP.WinHTTPRequest.5.1` es del sistema, no de
      AutoCAD. Se puede comprobar **sin AutoCAD**, desde PowerShell:
      `New-Object -ComObject WinHttp.WinHttpRequest.5.1`. Si eso falla, el
      problema no es AutoCAD y se arregla antes de gastar un día de licencia.
- [ ] Servidor ArchMuse levantado y contestando: `curl http://127.0.0.1:5000/medir`
      devuelve 200.
- [ ] Ten a mano `_material/ejemplo.dxf`. Es el plano con el que están medidas
      todas las cifras esperadas de este documento.

## Paso 1 · El fichero carga sin error de sintaxis

- [ ] `APPLOAD` → `autocad/archmuse.lsp` → **no aparece ninguna ventana de error**.
- [ ] En la línea de comandos aparece la línea de bienvenida con la versión.

**Si falla:** es del **lenguaje**. Un paréntesis. El error de AutoCAD dice el
número de línea; anótalo, no lo depures a ojo.

> Nota honesta: la sintaxis de `archmuse.lsp` se ha revisado contra la
> documentación oficial de Autodesk, pero **nunca se ha ejecutado**. Este paso
> es el que más probabilidad tiene de fallar el primer día, y fallar aquí **no
> dice nada** sobre si el flujo sirve.

## Paso 2 · El comando existe

- [ ] Teclea `ARCHMUSE` → responde algo. No «Comando desconocido».

**Si falla:** el `defun` no lleva el prefijo `c:`, o el fichero cargó a medias.
Del **lenguaje**.

## Paso 3 · Selección correcta de polilíneas

Con `ejemplo.dxf` abierto:

- [ ] El script anuncia la capa que ha detectado. Sobre este plano debe ser
      **`00 areas`**.
- [ ] Anuncia **cuántas polilíneas cerradas** ha cogido. Sobre `ejemplo.dxf` la
      medición por la web da **40 piezas** repartidas en 6 viviendas: si el
      número que anuncia el script es muy distinto, párate aquí.
- [ ] Prueba a dar una capa a mano cuando pregunte, y comprueba que la respeta.

**Si el recuento no cuadra**, mira primero estos tres, que son diferencias
**conocidas y esperadas** frente a la web, no fallos:

1. **Polilíneas con el flag de «cerrada» mal puesto.** Es la causa más probable
   y está medida: `ssget` sólo filtra por el bit del código 70, y el lector de
   Python además recupera las que cierran geométricamente. En los planos reales
   son **3 de 22 en `V5.dxf`, 2 de 10 en `v2s.dxf` y 9 de 53 en `ejemplo.dxf`**
   — hasta un 17%. **El propio comando te dice cuántas deja fuera antes de
   enviar**: si ese número explica la diferencia, no hay nada que depurar.
2. **Bloques anidados.** `ssget` no entra en bloques; el lector Python sí. Si el
   plano dibuja recintos dentro de bloques, el script verá menos.
3. **Polilíneas con arco (*bulge*).** El script las declara aparte y no las
   mide.

Cualquier otra diferencia es del **flujo** y hay que anotarla: significa que lo
que AutoCAD llama «los recintos» y lo que ArchMuse llama «los recintos» no es lo
mismo, que es un hallazgo mayor que el prototipo.

## Paso 4 · El POST llega

- [ ] Mira la consola del servidor: tiene que aparecer la línea de acceso a
      `/api/medicion-geometria`.
- [ ] AutoCAD no se queda colgado para siempre: **avisa** de que va a tardar
      (~10 s sobre 6 viviendas) y vuelve.

**Si no llega nada al servidor**, en este orden:

1. `localhost` contra `127.0.0.1` — prueba el segundo.
2. Antivirus o cortafuegos bloqueando el COM de AutoCAD.
3. El objeto COM no se creó (comprobado en el paso 0).

Los tres son del **lenguaje/entorno**. Ninguno dice nada del flujo.

## Paso 5 · La respuesta se lee

- [ ] El script imprime en la línea de comandos el total de la primera vivienda
      **antes** de dibujar nada.
- [ ] **Contrástalo contra la cifra conocida.** Sobre `ejemplo.dxf`:

  | Vivienda | interior | exterior | total |
  |---|---|---|---|
  | VT1/3 | 58,78 | 7,54 | **66,32** |
  | VT2/2 | 50,97 | 7,47 | **58,44** |
  | VT3/3 | 59,11 | 7,45 | **66,56** |
  | VT4/2 | 50,91 | 7,56 | **58,47** |
  | VT5/1 | 41,05 | 4,27 | **45,32** |
  | VT6/2 | 46,23 | 28,14 | **sin total** (solape de 8,47 m²) |

  Total de planta: **ninguno** — falta VT6/2. Y aviso: el rótulo `VT22/1` no
  tiene ningún recinto.

- [ ] **Acentos.** Comprueba que un motivo con tildes y comillas angulares se lee
      bien y no sale como `Â«VT6/2Â»`. Es el fallo más probable después de la
      sintaxis, y es de **codificación** (UTF-8 del servidor contra ANSI de
      AutoCAD), no del flujo.

**Si los números no coinciden con la tabla**, es del **flujo** y es grave: el
modo de entrada nuevo estaría midiendo por su cuenta. Para y avisa.

## Paso 6 · La tabla se inserta

- [ ] Pide punto de inserción y respeta el que pulsas.
- [ ] Es una **entidad TABLE nativa** — pínchala: se selecciona como tabla, no
      como un montón de texto. `LIST` dice `ACAD_TABLE`.
- [ ] La tabla es editable como cualquier otra tabla de AutoCAD.

**Si sale como MTEXT o como líneas sueltas:** del **lenguaje** (`vla-AddTable`
mal invocado).

## Paso 7 · La tabla dice la verdad

Esto es lo que de verdad se viene a probar. Es más importante que los seis
pasos anteriores.

- [ ] **VT6/2 NO trae número de total.** Trae el motivo: los 8,47 m² dibujados
      dos veces, con las dos cifras (74,37 suma de piezas / 65,89 superficie
      real).
- [ ] **No hay total de planta**, y la tabla dice qué vivienda lo bloquea.
- [ ] **La marca de borrador está** («Borrador para revisión de un colegiado»,
      `C3`) y **no hay forma de quitarla** desde el comando.
- [ ] Ninguna celda trae un número que no venga del servidor. Ninguna celda
      vacía sin motivo escrito.

**Si aparece un número inventado o una omisión silenciosa, el prototipo ha
fallado en lo único que no era negociable.** Anótalo y para.

## Paso 8 · Formato legible

- [ ] Se lee a la escala del plano, sin hacer zoom.
- [ ] Los motivos largos no se salen de la celda ni se cortan a mitad de palabra.
- [ ] La tabla no tapa el dibujo.

Del **lenguaje**, y es lo último que hay que arreglar. Un formato feo con las
cifras bien es un prototipo que ha funcionado.

## Paso 9 · La pregunta que hay que hacerle al arquitecto

Con la tabla ya en su plano, delante de él:

1. ¿Esto te ahorra el copiado a mano, o te lo cambia por revisar lo que ha
   escrito el programa?
2. ¿Querrías que escribiera **dentro de tu cuadro existente** en vez de insertar
   una tabla nueva?
3. ¿La marca de borrador te estorba para entregar, o te tranquiliza?

Sus respuestas valen más que los pasos 1-8. Si la respuesta a la 2 es «sí», el
camino bueno no era este prototipo: era `superficies.cuadro_de_vivienda`, que ya
existe (§14.3 del PRD).

---

## Lo que este checklist NO puede comprobar

Escrito aquí para que nadie lo dé por probado:

- **Rendimiento con un plano grande de verdad.** 12 s son los de `ejemplo.dxf`.
  Un plano de estudio con 40 capas y bloques anidados no se ha medido nunca por
  esta vía.
- **Que `ssget` coja lo mismo que el lector Python** en un plano cualquiera.
  Sólo se ha razonado sobre los dos planos reales que hay.
- **Versiones de AutoCAD distintas de la del trial.** `vla-AddTable` existe desde
  hace muchas versiones, pero eso es documentación, no una comprobación.
- **Nada en Mac.** El COM de Windows no existe allí. La integración con AutoCAD
  para Mac es un problema entero sin empezar.
