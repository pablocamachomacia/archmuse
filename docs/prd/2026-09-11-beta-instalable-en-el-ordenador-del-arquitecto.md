# PRD — Beta instalable en el ordenador del arquitecto

**Estado:** APROBADO · **Fecha:** 2026-09-11 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, 2026-09-11

> **Qué es esto.** La deuda «NO SE IMPLEMENTA AHORA» del PRD del 2026-09-10
> (*Un instalador único / Que el servidor arranque solo / Cómo se actualiza*)
> promovida a documento propio, porque ha dejado de ser deuda: hay un usuario
> con nombre, una máquina que no es ésta y una fecha.
>
> **Lo que Pablo ya ha decidido y este PRD no discute:** todo en local, el
> servidor se ejecuta en el ordenador del arquitecto, sus planos no salen de su
> máquina. Este documento decide **cómo**, no **si**.
>
> **Lo que este PRD tiene que decidir de verdad** son dos cosas, las que pueden
> salir mal en casa de otro: **D-1, cómo arranca el servidor** (§4.1) y **D-2,
> cómo se actualiza** (§4.2). El resto es ejecución.

---

## 1. Problema que resuelve

Hoy ArchMuse por la vía AutoCAD funciona **en esta máquina y con quien la ha
construido delante**. Para ejecutarlo hacen falta tres cosas que un arquitecto
no tiene por qué saber hacer: un Python con su entorno virtual, un servidor
levantado a mano en una consola (`python app.py`), y un `APPLOAD` del `.lsp` en
cada sesión de AutoCAD. Cualquiera de las tres que falle produce el mismo
síntoma —«no responde en localhost:5000»— y ninguna tiene arreglo que él pueda
aplicar solo.

El problema no es técnico, es de validación: **mientras no se instale en otra
máquina, no sabemos nada.** Todo lo aprendido en los últimos días —el flag de
cerrada mal puesto en 2 de 10 polilíneas, el contorno agrupador, los escapes
`\U+xxxx`, el desplazamiento de las polilíneas de área en `plantasimple.dxf`—
salió de mirar **cinco DXF** que se exportaron a propósito para esto. El corpus
real de un arquitecto son **70 DWG** (`_barrido/BARRIDO.md`), y ninguno ha
pasado nunca por el programa.

**Petición directa de Pablo (2026-09-11):** una beta que un arquitecto en
ejercicio —con AutoCAD, no técnico— pueda instalar y usar en su ordenador, con
sus proyectos, sin nadie delante.

## 2. Usuario afectado

**El primer usuario real que no es el autor.** Arquitecto en ejercicio, AutoCAD
completo (no LT), Windows, sin conocimientos de Python, de puertos ni de
servicios. No va a leer un README de 40 líneas ni va a abrir una consola.

Es también el primer usuario que **no puede preguntar por el pasillo**: si algo
falla, la única información que llegará es lo que él sepa contar por WhatsApp.
De ahí el punto 4 del encargo, que no es un extra sino la instrumentación del
experimento.

## 3. Objetivo de negocio

1. **Convertir 5 DXF de laboratorio en 70 DWG de trabajo real.** Es la única
   forma de saber qué convenciones de dibujo existen ahí fuera y cuáles rompen
   el parser. Cada fallo que aparezca en esa máquina vale más que una semana de
   tests sintéticos aquí.
2. **Probar la promesa comercial completa, no media.** «Se instala, mide tu
   plano y no sale nada de tu ordenador» es la frase con la que ArchMuse se
   vende (`MOAT_ANALYSIS.md`, y §0.0 del PRD del 2026-09-10: *la vía AutoCAD es
   el producto*). Hoy esa frase está verificada por el lado del cálculo pero no
   por el de la instalación.
3. **Aceptar el precio que ya se decidió pagar:** con el servidor en local **no
   hay telemetría**. No sabremos cuántos planos mide, cuáles fallan ni qué
   rótulos aparecen que el vocabulario no reconoce, salvo que él lo mande a
   propósito. Por eso `ARCHMUSE-INFORME` (§4.4) **es** el canal de datos de esta
   beta: sin él, la beta es ciega y el objetivo 1 no se cumple.

## 4. Objetivo técnico

Una vez instalado, esto debe ser cierto **en una máquina que nunca ha tenido
Python**:

- Un solo ejecutable deja el producto entero instalado, sin pedir permisos de
  administrador y sin pedirle que instale nada más.
- Al abrir AutoCAD, `ARCHMUSE` existe sin que él haya hecho nada.
- Al teclearlo, el servidor responde: o porque ya estaba levantado, o porque el
  propio comando lo levanta y espera.
- Ninguna petición sale de `127.0.0.1`. **Verificado hoy**, no supuesto: se
  ejecutó `/api/medicion-geometria` con `ANTHROPIC_API_KEY` vacía y con todo
  socket a destino distinto de loopback bloqueado a nivel de `socket.connect`
  → **HTTP 200**, `capacidades: ['medicion', 'reparto_de_cuadro']`. El camino
  del comando no necesita ni clave de IA ni internet.
- Cuando algo falla, queda escrito en un fichero con fecha, y un comando lo
  empaqueta para mandarlo.
- Una versión nueva se instala copiando **un fichero de unos pocos MB**, no
  reinstalando los 100 MB de dependencias.

### 4.1 · D-1 — Cómo arranca el servidor  ← **decisión**

**Tres opciones reales, y por qué se descartan dos.**

| | Arranca antes del login | Admin para instalar | Coste de actualizar | Qué ve él si se rompe |
|---|---|---|---|---|
| **A · Servicio de Windows** | sí | **sí** | alto (parar servicio, reemplazar, arrancar) | nada |
| **B · Tarea al iniciar sesión** | no (da igual) | no | bajo (reemplazar y reiniciar tarea) | nada, pero es un proceso suyo |
| **C · Lo lanza el `.lsp` al no encontrarlo** | no | no | ninguno | el propio comando se lo dice |

**DECISIÓN: B como forma normal, C como red de seguridad. No A.**

**Por qué no un servicio de Windows (A).** Tres motivos, en orden de peso:

1. **Pide administrador.** Un instalador que pide elevación en la máquina de
   otro es exactamente el momento en el que una beta no se instala. Y si su
   usuario de Windows no es administrador, no hay instalación posible.
2. **Un servicio no tiene su perfil.** Corre como `LocalSystem` o como una
   cuenta de servicio: `%LOCALAPPDATA%` es otro, el temporal es otro, y el
   directorio donde la Skill de medición escribe su PDF es otro. Todo el
   almacenamiento del producto habría que reconducirlo a rutas absolutas
   pensadas para eso.
3. **Actualizar un servicio es un procedimiento, no una copia de ficheros** — y
   D-2 (§4.2) dice justo lo contrario: que actualizar sea copiar.

Lo que se pierde eligiendo B: que el servidor esté levantado antes de que él
inicie sesión. **No se pierde nada**, porque AutoCAD tampoco arranca antes de
que él inicie sesión.

**Cómo es B, en concreto.**

- El instalador registra una **tarea programada por usuario** (`schtasks`,
  disparador *al iniciar sesión*, sin privilegios elevados) que ejecuta
  `ArchMuse-Servidor.exe` — un lanzador **sin consola** (subsistema GUI, estilo
  `pythonw`), para que no exista la ventana negra que él pueda cerrar sin
  querer.
- El servidor escucha **sólo en `127.0.0.1`**, nunca en `0.0.0.0`. Esto no es
  higiene, es producto: **un bind a loopback no dispara el diálogo del
  cortafuegos de Windows.** Un «¿Permitir que ArchMuse acceda a la red?» en la
  primera ejecución contradice de frente la promesa que le acabamos de vender.
- **Una sola instancia:** mutex con nombre + fichero de estado. Si ya hay un
  servidor vivo, el segundo se retira en silencio.
- **El puerto no se da por hecho.** Prueba 5000, 5001, 5002… y escribe el
  elegido en `%LOCALAPPDATA%\ArchMuse\servidor.json`
  (`{puerto, version, pid, arrancado}`). El `.lsp` lee ese fichero antes del
  POST, en vez de llevar `localhost:5000` escrito a mano como hoy
  (`*am:url*`, `autocad/archmuse.lsp:70`).

**Cómo es C, y por qué se queda aunque B funcione.**

`am:post` **ya distingue** «no responde» de «respondió mal» (rama
`vl-catch-all-error-p`): el sitio donde poner «y si no está, lo levanto» ya
existe y está probado. En esa rama, y sólo ahí:

1. lanzar `ArchMuse-Servidor.exe` con `startapp`,
2. reintentar `GET /api/salud` cada segundo hasta 20 s,
3. si responde, seguir como si nada y **anotarlo en el log**,
4. si no, decirle literalmente qué hacer (reiniciar el ordenador, y si sigue,
   `ARCHMUSE-INFORME`).

C cubre los tres casos que B no cubre y que en una beta van a pasar: que acabe
de instalar y no haya reiniciado, que haya matado el proceso desde el
Administrador de tareas, y que la tarea programada no se haya creado (lo más
probable de los tres, y lo que menos podemos comprobar desde aquí — §12.3).

**Riesgo abierto de D-1:** el arranque en frío. `import app` carga `shapely`,
`reportlab` y el registro de capacidades; un arranque completo está en el orden
de varios segundos. Con B eso ocurre al iniciar sesión y no lo nota; con C lo
paga el primer `ARCHMUSE`. Por eso C avisa («levantando ArchMuse, unos
segundos…») en vez de quedarse mudo.

### 4.2 · D-2 — Cómo se le pasa una versión nueva  ← **decisión**

**El problema, dicho sin adornos:** con el servidor en su casa, cada corrección
hay que llevarla a su máquina, y durante un rato habrá dos ArchMuse midiendo la
misma planta con criterios distintos. Ya estaba anotado como el punto que más
iba a doler (PRD 2026-09-10, deuda 3).

**DECISIÓN: instalación en dos capas, y la actualización toca sólo la de
arriba.**

```
%LOCALAPPDATA%\ArchMuse\
├─ runtime\              CAPA A — Python embebido + dependencias. ~100 MB.
│                        Cambia cada muchas semanas. La pone el instalador.
├─ app\
│   ├─ 0.3.1\            CAPA B — analyzer\, app.py, archmuse.lsp, version.json
│   ├─ 0.3.2\                     Unos pocos MB. Cambia a diario.
│   └─ actual  ─────────> apunta a 0.3.2   (junction o fichero puntero)
├─ registro\             el log (§4.4)
└─ servidor.json         puerto, versión y pid del servidor vivo
```

- **Actualizar = un fichero `ArchMuse-0.3.2.archmuse`** (un ZIP con extensión
  propia, asociada al actualizador por el instalador). Doble clic: para el
  servidor, descomprime en `app\0.3.2\`, mueve el puntero `actual`, vuelve a
  arrancar, y enseña una ventana de una línea: «ArchMuse 0.3.2 instalado».
  Se lo puedo mandar por WhatsApp.
- **La versión anterior no se borra.** Volver atrás es mover el puntero; el
  actualizador deja un acceso directo `ArchMuse — volver a la anterior`. En una
  beta que va a fallar, el rollback en un clic vale más que el ahorro de disco.
- **El `.lsp` viaja en la capa B**, porque cambia tanto como el servidor. Por
  eso el bundle de AutoCAD (§4.3) carga
  `%LOCALAPPDATA%\ArchMuse\app\actual\archmuse.lsp` —ruta fija que el puntero
  redirige— y nunca una ruta con número de versión dentro.
- **Sin auto-actualización y sin llamar a casa.** Ni comprobación periódica de
  versiones ni descarga automática: sería la única conexión saliente de todo el
  producto, y la promesa que se le vende es que no hay ninguna. Además, un
  ejecutable que se descarga y se ejecuta solo en la máquina de otro es
  precisamente lo que un antivirus está entrenado para parar (§9).

**Y la mitad que suele olvidarse: que se sepa qué versión está midiendo.**

- `version.json` en la capa B; el servidor lo devuelve junto a `capacidades` en
  cada respuesta de `/api/medicion-geometria`.
- `ARCHMUSE` imprime **las dos** versiones antes de medir: la del `.lsp` y la
  del servidor.
- Si no coinciden en la parte mayor, **avisa y no escribe**: dos capas
  desparejadas es el escenario que produce cifras que nadie puede reproducir
  después. Es el mismo criterio que ya se aplicó con `capacidades` el
  2026-09-11 para distinguir «no ha podido» de «es una versión anterior».
- Cada línea del log lleva las dos versiones. Sin eso, un informe suyo de dentro
  de tres semanas no es interpretable.

### 4.3 · Que el comando se cargue solo

**DECISIÓN: paquete `ApplicationPlugins` de Autodesk, no `acaddoc.lsp`.**

El instalador escribe `%APPDATA%\Autodesk\ApplicationPlugins\ArchMuse.bundle\`
con su `PackageContents.xml` y, dentro, un cargador que hace `load` del `.lsp`
de `app\actual\`.

Por qué no `acaddoc.lsp`: **es un fichero único y compartido**. Si él ya tiene
uno —y un arquitecto con años de AutoCAD suele tenerlo— lo pisamos y le rompemos
sus rutinas; y si lo ponemos en otra carpeta de la ruta de soporte, gana el
primero que AutoCAD encuentre, que no controlamos. El bundle es el mecanismo
oficial por usuario, no pide administrador, no colisiona con nada suyo, y
**desinstalar es borrar la carpeta**.

Lo que hay que comprobar en su máquina y no en ésta: que su versión de AutoCAD
trate `ApplicationPlugins` como ruta de confianza (`TRUSTEDPATHS`, `SECURELOAD`)
sin preguntar nada. Va a §12.3.

### 4.4 · Cuando falla: el log y `ARCHMUSE-INFORME`

**Dónde vive el log.** `%LOCALAPPDATA%\ArchMuse\registro\archmuse-AAAA-MM.log`.
**No** en `Documentos` ni en el `Escritorio`: los dos suelen estar sincronizados
con OneDrive, y un log que se sube a la nube contradice la única frase que le
hemos prometido. Él no navega hasta ahí nunca: el informe se le deja en el
escritorio y se le abre la carpeta.

**Qué se escribe, por línea:** fecha y hora · versión del `.lsp` · versión del
servidor · versión de AutoCAD · **nombre del dibujo, sin su ruta** · capa
elegida y si la eligió él o el heurístico · cuántas polilíneas se enviaron y
cuántas descartó el servidor · cuántas celdas se escribieron · y el error con su
traza si lo hubo.

**Qué NO se escribe, y es deliberado:** ni un vértice, ni un rótulo, ni el
contenido de una celda del cuadro, ni la ruta del fichero. Los nombres de las
estancias y los textos de su cuadro **son el proyecto de su cliente**, y la ruta
suele llevar el nombre del cliente dentro. Si más adelante hace falta relacionar
dos entradas del mismo plano, se hace con un hash del nombre, no con el nombre.

**`ARCHMUSE-INFORME`:**

1. Recoge los últimos 30 días de log y un `entorno.txt` (versiones de todo,
   puerto, si el servidor estaba vivo). **Nada más.**
2. **Antes de comprimir, enseña en la línea de comandos la lista exacta de lo
   que va a meter**, con su tamaño. Que la promesa de «sin planos dentro» sea
   verificable por él, no una afirmación nuestra.
3. Escribe `archmuse-informe-AAAA-MM-DD-HHMM.zip` **en su Escritorio** y abre la
   carpeta en el Explorador con el fichero seleccionado. De ahí lo arrastra a
   WhatsApp.
4. Si el plano hace falta, es **otro comando** — `ARCHMUSE-INFORME PLANO` — que
   dice con todas las letras «esto incluye una copia de tu dibujo» y exige un
   `Si` explícito. Nunca por omisión, nunca dentro del informe normal.

### 4.5 · El folio

Una hoja, impresa o en PDF, en su idioma. Cuatro bloques: **qué instalar**
(ejecuta esto, doble clic, listo), **qué escribir** (abre tu plano, teclea
`ARCHMUSE`), **qué esperar** (te enseña lo que va a escribir y te pregunta; un
`UNDO` lo deshace todo; queda una marca de borrador que puedes apagar pero no
borrar) y —el importante— **qué no funciona todavía**:

- Una vivienda por plano. Un plano con varias, todavía no.
- No dibuja cuadros: rellena el que ya tengas. Si no hay tabla, te lo dice.
- El cuadro tiene que ser una **tabla de AutoCAD**, no líneas y textos sueltos.
- AutoCAD completo. En **AutoCAD LT no funciona** y no tiene arreglo.
- Las estancias tienen que ser **polilíneas cerradas en una misma capa**, y
  **cada una con su rótulo dentro**. Si los rótulos de tu plano están separados
  de las polilíneas de área, ArchMuse medirá bien y no sabrá cómo se llama nada.
  *(No es hipotético: pasa en `plantasimple.dxf`, donde las polilíneas de
  «00 areas» están 50,00 unidades por encima del plano que describen —152 de 152
  encajan al desplazarlas— y por eso ningún recinto recibe nombre.)*
- Si tu plano tiene varias capas que podrían ser la de áreas, te va a preguntar
  cuál es. No es un fallo: es que no quiere adivinarlo.

Y una línea que separa las dos cosas que él necesita distinguir: **«si sale un
mensaje que te explica qué pasa, es un límite conocido. Si se queda colgado, si
AutoCAD da un error raro, o si escribe una cifra que sabes que está mal, eso es
un fallo: teclea `ARCHMUSE-INFORME` y mándamelo.»**

## 5. Casos de uso

1. **Instalación.** Doble clic en `ArchMuse-Beta-0.3.1.exe`, instala sin pedir
   administrador, «Listo. Abre AutoCAD y teclea ARCHMUSE», y arranca el servidor
   ya, sin esperar al siguiente inicio de sesión.
2. **Uso normal.** Abre su DWG, teclea `ARCHMUSE`, ve las dos versiones, elige
   capa si se lo pregunta, revisa las celdas que va a escribir, dice `Si`.
3. **El servidor no está.** El comando lo levanta, avisa de la espera, sigue.
4. **Falla algo.** Ve un mensaje, teclea `ARCHMUSE-INFORME`, arrastra el ZIP del
   escritorio a WhatsApp.
5. **Versión nueva.** Recibe `ArchMuse-0.3.2.archmuse`, doble clic, ventana de
   una línea, sigue trabajando.
6. **Se arrepiente.** `ArchMuse — volver a la anterior`, en el menú Inicio.

## 6. Casos límite

- **Puerto 5000 ocupado** por otra cosa suya → escalera de puertos y
  `servidor.json` (§4.1).
- **Dos AutoCAD abiertos** → un solo servidor; `waitress` ya atiende en hilos.
- **Actualiza con AutoCAD abierto** → el `.lsp` viejo sigue en memoria contra un
  servidor nuevo; lo detecta el cotejo de versiones de §4.2 y pide reiniciar
  AutoCAD en vez de medir.
- **Se instala sobre una instalación viva** → parar, reemplazar, arrancar; si el
  servidor no se deja parar, abortar sin tocar `actual`.
- **Sin permisos en `%LOCALAPPDATA%`** (perfil corporativo con políticas) → el
  instalador lo comprueba **antes** de copiar nada y lo dice.
- **`Documentos` o `Escritorio` redirigidos a OneDrive** → el log no está ahí
  (§4.4); el ZIP del informe sí, y es intencionado: lo va a mandar igualmente.
- **Antivirus pone el `.exe` en cuarentena** → §9, y es el caso que menos
  podemos anticipar desde aquí.
- **AutoCAD LT** → ya cubierto: `am:post` lo detecta y lo explica.

## 7. Flujo del usuario

Descargar → doble clic → «Listo» → abrir AutoCAD → `ARCHMUSE` → (capa si hace
falta) → revisar → `Si` → cifras en su cuadro y marca de borrador → un `UNDO` si
no le gusta. Cuando algo falle: `ARCHMUSE-INFORME` → ZIP en el escritorio →
WhatsApp.

## 8. Criterios de aceptación

1. En una máquina Windows **sin Python**, un solo ejecutable y sin administrador
   deja el producto instalado.
2. Tras iniciar sesión, `GET http://127.0.0.1:<puerto>/api/salud` responde sin
   que nadie haya abierto nada.
3. Al abrir AutoCAD, `ARCHMUSE` existe sin `APPLOAD`.
4. Matando el servidor a mano, `ARCHMUSE` lo vuelve a levantar y completa la
   medición.
5. Ninguna conexión sale de loopback en una sesión completa (comprobable con
   `netstat` o el Monitor de recursos).
6. Un fallo provocado a propósito deja línea en el log con fecha, nombre de
   dibujo y mensaje.
7. `ARCHMUSE-INFORME` produce un ZIP **sin ningún `.dwg`, `.dxf`, vértice ni
   rótulo dentro** — comprobado abriéndolo.
8. Un `.archmuse` de versión nueva actualiza en menos de 30 s **sin volver a
   copiar las dependencias**, y el comando declara la versión nueva.
9. El rollback devuelve la versión anterior y el comando lo declara.
10. El folio cabe en una cara y nombra los seis límites de §4.5.

## 9. Riesgos

- **SmartScreen y antivirus.** Un `.exe` sin firmar, descargado, que instala un
  intérprete y abre un puerto: es el retrato robot de lo que Defender marca.
  «Windows protegió tu PC» en la primera pantalla mata la beta. Mitigaciones por
  orden de coste: instrucciones con captura de «Más información → Ejecutar de
  todas formas» en el folio (gratis, feo); firmar con certificado (cientos de
  euros al año, y ni siquiera un EV acumula reputación de golpe).
  **Propuesta: empezar sin firmar y medir cuánto molesta en una sola máquina
  antes de gastar.**
- **Tamaño.** `site-packages` ocupa hoy **317 MB**, y `ifcopenshell` son **93 MB**
  de ellos — que el camino del comando no usa. Recortar el perfil de la beta a
  `ezdxf + shapely + numpy + flask + waitress + reportlab + pyyaml + jsonschema +
  python-dotenv` deja del orden de 100 MB antes de comprimir. **Pero `app.py`
  importa hoy en la cabecera mucho más de lo que el endpoint necesita**: hay que
  medirlo (§11, T2) antes de prometer la cifra, y hacer perezosos los imports
  pesados es trabajo con riesgo de romper otras rutas.
- **Ceguera.** Sin telemetría, si no usa `ARCHMUSE-INFORME` no nos enteramos de
  nada. El riesgo real no es que falle: es que falle y no lo cuente.
- **Es el plano de trabajo de alguien.** Escribe en dibujos reales. Lo que
  protege hoy —vista previa, `Si` explícito, un solo grupo de deshacer, y la
  retirada automática de lo escrito si la marca de borrador no se puede poner—
  **no se toca en este PRD**.
- **Compite con el trabajo en curso.** Esto no mide mejor ni un plano. Compite
  directamente con el orden fijado para `plantasimple.dxf` (dar la capa desde el
  comando, y CU-2 con 25 cuadros reales). Ver §14.

## 10. Impacto sobre módulos existentes

- `autocad/archmuse.lsp` — lee el puerto de `servidor.json` en vez de
  `*am:url*`; rama de arranque del servidor; cotejo de versiones; escritura al
  log; comandos `ARCHMUSE-INFORME` y `ARCHMUSE-INFORME PLANO`.
- `app.py` — `GET /api/salud`; `version` en la respuesta del endpoint de
  geometría, junto a `capacidades`; posible aplazamiento de imports pesados.
- **Nuevo `empaquetado/`** — script de construcción, `.iss` de Inno Setup,
  lanzador sin consola, actualizador del `.archmuse`, plantilla del bundle.
- **Nuevo `docs/beta/INSTRUCCIONES.md`** — el folio, y su PDF.
- `analyzer/` — **sin cambios**. Que el motor no se toque es condición: lo que se
  empaqueta es lo que ya se verificó en AutoCAD 2027 el 2026-09-11.

## 11. Plan de implementación

| | Tarea | ≤2 h |
|---|---|---|
| T1 | `GET /api/salud` + `version` en la respuesta del endpoint, con test | sí |
| T2 | **Medir** qué importa `app.py` de verdad en el camino del comando y qué pesa cada cosa. Decidir el perfil de dependencias con números, no con estimación | sí |
| T3 | Lanzador sin consola + `servidor.json` (puerto, versión, pid) + instancia única | sí |
| T4 | `.lsp`: leer puerto del fichero, cotejar versiones, negarse a escribir si no casan | sí |
| T5 | `.lsp`: levantar el servidor y esperar cuando no responde (rama C de §4.1) | sí |
| T6 | Log: formato de línea, rotación mensual, y el filtro de lo que NO entra | sí |
| T7 | `ARCHMUSE-INFORME`: listado previo, ZIP al escritorio, abrir carpeta | sí |
| T8 | `ARCHMUSE-INFORME PLANO`, separado y con confirmación explícita | sí |
| T9 | Árbol de dos capas + puntero `actual` + actualizador del `.archmuse` + rollback | sí |
| T10 | Instalador Inno Setup: por usuario, sin admin, tarea programada, bundle, desinstalador | no (~4 h) |
| T11 | El folio | sí |
| T12 | Prueba en máquina limpia (§12.3) | — |

**Orden:** T1 y T2 primero, porque T2 puede cambiar el tamaño de todo lo demás.
T10 al final, cuando ya haya algo que empaquetar.

## 12. Plan de pruebas

**12.1 · Automatizable aquí.** Test de que `/api/salud` responde y declara
versión. Test de que el ZIP del informe no contiene ningún `.dwg` ni `.dxf`
(criterio 7, y es el que más importa: es una promesa, no una función). Test de
que el `.lsp` y `version.json` declaran la misma versión —mismo patrón que
`tests/test_marca_borrador.py`, que ya compara una constante entre Python y
LISP—. Test del actualizador sobre un árbol de mentira: instala, mueve puntero,
revierte.

**12.2 · Manual en esta máquina.** El ciclo entero con AutoCAD 2027 sobre
`v1plantas.dxf`, que es el único plano verificado de punta a punta.

**12.3 · Lo que NO se puede probar sin otro ordenador distinto a éste**

1. **Que el instalador funcione sin Python.** Ésta invalida todas las demás:
   aquí hay Python en el `PATH`, un `venv`, compiladores y las DLL que las
   ruedas ya usaron. Un `.exe` puede funcionar aquí por accidente. **Y no se
   puede simular con Windows Sandbox: esta máquina es Windows 11 Home, y tanto
   Sandbox como Hyper-V son de Pro/Enterprise.** La única vía desde aquí es una
   **máquina virtual con VirtualBox y una imagen de evaluación de Windows**, y
   hay que montarla antes de T10 o T10 no es verificable.
2. **SmartScreen y su antivirus.** Lo que Defender hace con un `.exe` **recién
   descargado** (con marca de la web) no se reproduce con uno que acabas de
   compilar en tu disco. Y si él tiene otro antivirus, no hay forma de saberlo
   desde aquí.
3. **La autocarga en SU AutoCAD.** Versión, idioma, perfil y
   `TRUSTEDPATHS`/`SECURELOAD` cambian entre versiones. Aquí sólo hay AutoCAD
   2027.
4. **La tarea al iniciar sesión bajo su cuenta.** Cuenta Microsoft contra cuenta
   local, PIN o Hello, inicio de sesión automático, políticas de empresa: todo
   eso cambia si el disparador «al iniciar sesión» llega a dispararse.
5. **Si el puerto 5000 está libre en su máquina.** Sólo se sabe allí. Por eso la
   escalera de puertos no es opcional.
6. **Si sus carpetas están redirigidas a OneDrive**, que decide dónde acaba de
   verdad el ZIP del informe.
7. **Si su usuario es administrador**, y si su empresa tiene políticas que
   prohíban tareas programadas o escritura en `%LOCALAPPDATA%`.
8. **Sus 70 DWG.** Esto no es una limitación del método: **es el objetivo del
   experimento**. Ninguno se puede probar aquí porque ninguno está aquí.
9. **Desinstalar y reinstalar limpio.** Aquí siempre quedan restos.

**Consecuencia práctica:** de los diez criterios de aceptación de §8, **1, 2 y 3
no se pueden dar por buenos en esta máquina**. O se monta la VM, o la primera
instalación en casa del primer usuario de la beta es también la primera prueba — y entonces hay
que estar al teléfono, que es justo lo que el encargo dice que no.

## 13. Métricas para medir el éxito

Lo que hay que poder responder a las cuatro semanas:

- ¿Se instaló solo, o hizo falta una llamada? (sí/no, y cuántos minutos)
- ¿Cuántos planos suyos ha medido? (lo dice el log)
- ¿Cuántas veces tuvo que levantar el servidor la rama C? Si es alta, D-1 está
  mal elegida.
- ¿Cuántos `ARCHMUSE-INFORME` ha mandado, y cuántos fallos distintos traían?
- ¿Cuántas actualizaciones instaló sin ayuda?
- Y la única que decide si esto valió la pena: **¿ha usado alguna cifra de
  ArchMuse en un proyecto que haya entregado?**

## 14. Posibles motivos para NO implementar la idea

**14.1 · El argumento honesto en contra: es prematuro por una semana.**

El producto todavía no mide bien el único proyecto completo del lote. Hoy mismo,
sobre `plantasimple.dxf`:

- el heurístico de capa **no decide** (`00 areas` 0,4854; `00 TEXTO` 0,4640;
  `00-INST` 0,4350; umbral 0,50), y **el comando no permite todavía dársela**
  más que escribiendo el nombre a ciegas;
- y aunque se le dé, **ningún recinto recibe rótulo**, porque las polilíneas de
  área están 50,00 unidades por encima del plano.

Un cuadro que sale entero en blanco en el primer plano real de ese arquitecto no se
lee como «límite conocido»: se lee como que no funciona. **Y la primera
impresión con un usuario que no es técnico se gasta una sola vez.**

**Recomendación de CTO:** aprobar este PRD y **no ejecutarlo todavía**. El orden
ya fijado —dar la capa desde el comando, y CU-2 contra los 25 cuadros reales— se
termina primero, porque es lo que decide si lo que se empaqueta vale la pena
empaquetarlo. Empaquetar algo que falla sólo consigue que falle en dos sitios.

**14.2 · Lo que sí conviene adelantar aunque 14.1 se acepte.** T1, T2 y T6 (el
log) no dependen del estado de la medición, y el log es lo que hará
interpretable todo lo demás. Y la **VM de máquina limpia** (§12.3) hay que
montarla ya: es plazo, no trabajo, y sin ella T10 no se puede verificar.

**14.3 · La alternativa que se descarta.** Instalarlo yendo a su casa con un
pendrive. Es más rápido hoy y no resuelve nada: la segunda versión y la tercera
seguirían necesitando el viaje, y la beta existe precisamente para probar que el
producto llega a una máquina sin nosotros. Instalarlo a mano es no hacer el
experimento.

---

**Decisión:** **APROBADO por Pablo el 2026-09-11**, con la recomendación de §14.1
aceptada: **no se ejecuta todavía**. Primero `plantasimple.dxf`. De este PRD se
adelantan sólo T1, T2 y T6 (§14.2), y la VM de §12.3.

Pablo destaca como lo de más valor del documento: **el bind a loopback** (que un
diálogo de cortafuegos contradice la promesa que se le vende) y **el cotejo de
versiones `.lsp`↔servidor que se niega a escribir si no casan**. Las dos quedan
como condiciones de la aprobación, no como detalles de implementación.

---

## Ejecución · 2026-09-13

**Orden de Pablo del 2026-09-13:** tras la suite, el instalador. La
recomendación de §14.1 («primero `plantasimple.dxf`») queda cumplida por lo
hecho el 11 y el 12 (el plano se mide y publica superficies); `D-7` lo mide
Pablo en AutoCAD en paralelo.

**Hecho:** T3 (`empaquetado/capa_b/lanzador.pyw`), T4 y T5 (`.lsp` 3.1.0), T9
(`actualizador.pyw` + `archmuse_local.py`), T10 (`empaquetado/ArchMuse-Beta.iss`
y `empaquetado/construir.py`), T11 en borrador (`docs/beta/INSTRUCCIONES.md`,
con dos límites marcados `[CONFIRMAR]`). T1, T2 y T6-T8 ya estaban.
**Sin hacer:** T12, la máquina limpia. VirtualBox está instalado en esta
máquina, pero la VM no está montada.

### Cuatro desviaciones, todas medidas, ninguna silenciosa

1. **D-1: acceso directo en la carpeta Inicio, no tarea programada.**
   `schtasks /Create /SC ONLOGON … /RL LIMITED` desde una cuenta sin elevar
   devuelve **«Acceso denegado»** (medido el 2026-09-13). La tarea programada
   pide administrador, y «sin administrador» es criterio de aceptación 1. El
   acceso directo en `{userstartup}` conserva lo que D-1 buscaba: por usuario,
   al iniciar sesión, sin privilegios, y desinstalar lo quita.
2. **D-2: el cotejo es de la versión exacta del `.lsp`, no de «la parte
   mayor».** Servidor (`0.3.1`) y comando (`3.0.0`) numeran por separado: la
   parte mayor de uno no casa nunca con la del otro, y el cotejo tal como
   estaba escrito habría bloqueado siempre. El servidor declara ahora con qué
   `.lsp` se empaquetó (`lsp` en `/api/salud` y en cada medición, desde
   `version.json` o, en el repositorio, desde el propio fichero) y el comando
   **se niega a escribir si no es exactamente el suyo**. Es más estricto que lo
   aprobado, no menos: también caza el 2.3→2.4 que `PROGRESS` del 12-sep dejó
   anotado como invisible para la parte mayor.
3. **§4.3: el `.lsp` se copia dentro del bundle al activar una versión**, en vez
   de un cargador que haga `load` de `app\actual\archmuse.lsp`. Un `load` a
   `%LOCALAPPDATA%` fuera de `TRUSTEDPATHS` enseña el aviso de `SECURELOAD`; lo
   que está dentro de `ApplicationPlugins` no. La fuente sigue siendo una sola
   (`app\<version>\archmuse.lsp`). **Hipótesis sin medir**: que su AutoCAD
   confíe en `ApplicationPlugins` sin preguntar (§12.3.3 sigue abierto).
4. **`ArchMuse-Servidor.exe` es `runtime\pythonw.exe`.** Mismo subsistema sin
   consola; un ejecutable propio compilado sería un binario más, sin firmar,
   que el antivirus no conoce.

### Cifras de la construcción (2026-09-13, `construir.py`, 96 s)

| | |
|---|---:|
| Runtime (Python 3.12.10 embebido + perfil ligero) | 154,0 MB |
| Capa B | 2,6 MB |
| **Una actualización (`.archmuse`)** | **0,9 MB** |
| **Instalador** | **37,1 MB** |
| Prueba de humo con el runtime embebido | salud 200 · medición 200 · **0 módulos cargados de fuera de las dos capas** · import 2,75 s |

### Lo que NO está probado, dicho igual que en §12.3

- **Nada del instalador se ha ejecutado**: ni en esta máquina (instalaría el
  bundle en el AutoCAD de trabajo de Pablo) ni en una limpia. Criterios 1, 2,
  3, 8 y 9 de §8: sin verificar.
- **La rama C y el cotejo no se han ejecutado en AutoCAD**: `_.DELAY` dentro
  del comando y `WScript.Shell` lanzando `pythonw.exe` están escritos y
  anotados como no verificados en el propio `.lsp`.
- Lo que sí está probado aquí, con el lanzador de verdad en un proceso aparte:
  instancia única, escalera de puertos, `servidor.json`, parar sin matar un PID
  reciclado, instalar/reinstalar/volver sobre un árbol de mentira con uniones
  reales, y que un `.archmuse` con un plano dentro no se instala
  (`tests/test_empaquetado.py`, `tests/test_beta_lsp.py`).
