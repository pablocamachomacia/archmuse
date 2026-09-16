# Incidente · FILEDIA a 0 en el AutoCAD de Pablo (15 y 16-sep)

**Estado: causa reproducida, arreglada y vigilada** (2026-09-16).

## Qué pasó

Dos veces, al pulsar «Abrir» en AutoCAD, salió «Indique el nombre del dibujo que
desea abrir» en vez del explorador: FILEDIA estaba en 0. Las dos veces fue justo
después de instalar una versión de ArchMuse y reiniciar AutoCAD: el 15-sep y el
16-sep, tras ARCHMUSE-ACTUALIZAR. Pablo lo puso a 1 a mano las dos veces.

## Por qué lo descartamos mal el 15-sep

El 15-sep se anotó «ArchMuse descartado; causa desconocida», y en el guardián,
«Core Console arranca siempre con FILEDIA en 0 y no lo guarda en el perfil». Las
dos frases estaban medidas, pero las dos medían **lo que no era**:

- **Sólo se miró el comando.** El `.lsp` no toca FILEDIA, y es verdad. Pero
  nadie vigilaba lo que pasa alrededor: la instalación, el reinicio de AutoCAD, y
  las herramientas de desarrollo que lanzan AutoCAD Core Console en el mismo
  ordenador.
- **Se midió Core Console saliendo limpio.** Arranca con FILEDIA a 0, y al salir
  limpio el perfil queda como estaba: eso es lo que se vio. No se miró el
  registro **mientras** corría, ni qué pasa si no sale limpio.
- **Se descartaron los scripts de la víspera leyendo que ponían FILEDIA a 0**, sin
  preguntar qué más les había pasado: esa noche hubo que matar Core Console
  colgados.

Es el patrón de `CLAUDE.md`: una explicación medida a medias que sonaba bien, con
una etiqueta de certeza («descartado midiendo») que protegió el error un día más.

## La causa, reproducida el 2026-09-16

Medido en el ordenador de Pablo, con su AutoCAD abierto, haciendo foto del
registro antes, durante y después:

| Prueba | `FileDialog` en el registro |
|---|---|
| Core Console abre un DXF y sale limpio | 1 → 1 |
| Core Console con `(setvar "FILEDIA" 0)`, con y sin dibujo | 1 → 1 |
| Core Console con `DXFOUT` o `SAVEAS` | 1 → 1 |
| **Core Console a mitad de ejecución** | **1 → 0** |
| **Core Console matado a mitad** | **1 → 0, y se queda** |
| Core Console con `/isolate`, a mitad y matado | 1 → 1 |
| Reinstalar con el actualizador (lo mismo que ARCHMUSE-ACTUALIZAR) | 1 → 1, la clave ni se escribe |

**AutoCAD Core Console escribe `FileDialog = 0` en
`FixedProfile\General Configuration` del perfil del usuario al arrancar, y sólo
lo devuelve si sale limpio.** Matado, colgado hasta un plazo, o con un script que
no llega a su `QUIT`, el 0 se queda. Y un AutoCAD que se abra mientras corre lo lee.

**La cronología**, con lo medido y lo que no:

- **14-sep por la noche:** se mataron varios Core Console colgados del barrido de
  referencias externas (`C-15`). *Medido hoy que eso deja el 0; el valor del
  registro esa noche no se midió.*
- **15-sep, mañana:** instalación de la 0.3.7 y reinicio de AutoCAD; a las 12:33
  Pablo avisa de FILEDIA a 0 y lo pone a 1. A las 12:37 el registro tenía 1.
- **15-sep, 19:08:33:** la clave se escribió por última vez, tres segundos después
  de arrancar una sonda de tiempos en Core Console. Su salida se corta antes de su
  última línea: no salió limpia. *Medido: la hora de escritura de la clave y la
  salida de la sonda.*
- **15-sep 22:03 y 16-sep 02:13:** dos instalaciones, cada una con su reinicio de
  AutoCAD. El registro seguía en 0, y AutoCAD lo leyó al arrancar. *Medido: el 16
  a las 12:44 la clave estaba en 0 y no se había escrito desde el 15 a las 19:08.*

**«Siempre después de instalar» era «siempre después de reiniciar AutoCAD»**, que
es lo que pide cada instalación. La instalación no tocó nada: medido.

*Sin medir:* por qué el 1 que Pablo puso a mano el 16-sep no llegó al registro
(AutoCAD seguía abierto; lo más probable es que lo guarde al cerrar).

## El arreglo

- **Una sola puerta a Core Console, `herramientas/core_console.py`:** siempre con
  `/isolate` y, por si acaso, devolviendo al terminar lo que haya cambiado en
  `FixedProfile\General Configuration`, también si hay que matarlo. El banco de
  compatibilidad, el barrido de DWG y la prueba del guardián pasan por ella.
- `C-16` (propuesto) se amplía a la instalación, la actualización, el arranque y
  las herramientas del repositorio que lanzan AutoCAD.
- En el ordenador de Pablo, `FileDialog` está otra vez en 1 en el registro.

**Pablo no tiene que hacer nada más.** Si lo viera otra vez, lo que hay que mirar
primero es si en ese ordenador se ha ejecutado Core Console fuera de la puerta.

## Qué lo vigila ahora

| Qué | Cómo |
|---|---|
| Nadie lanza Core Console fuera de la puerta | `tests/test_core_console_no_toca_autocad.py`: busca el nombre en todo el código |
| La puerta aísla y devuelve, también matada | el mismo, con una consola falsa que pone el 0 y se cuelga; y uno opcional con Core Console de verdad (`ARCHMUSE_PROBAR_CORE_CONSOLE=1`) |
| Instalar, activar y volver atrás sólo tocan `TRUSTEDPATHS` | `tests/test_guardian_instalacion_y_arranque.py`, con el actualizador de verdad sobre un perfil de prueba; y `guardian_registro.py foto/comparar` en una máquina real |
| El arranque y ARCHMUSE-ACTUALIZAR no cambian variables | el mismo, leyendo el `.lsp` |
| Comparar a través de un reinicio | `guardian.lsp` guarda la foto de antes en un fichero; `probar_en_core_console.ps1` lo prueba entre dos sesiones |

Cada guardián se rompió a propósito (nueve roturas) y todos saltaron. La prueba
del guardián en Core Console, con las cuatro pruebas, pasó sin cambiar el
registro de Pablo.
