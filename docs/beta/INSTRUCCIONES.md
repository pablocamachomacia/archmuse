<!--
  El folio de la beta (T11 del PRD 2026-09-11, §4.5). Una cara, para el
  arquitecto, en su idioma.

  ANTES DE IMPRIMIRLO, Pablo tiene que confirmar el apartado 4 contra el .lsp
  que se entregue. El §4.5 del PRD se escribió el 2026-09-11 y dos de sus
  límites han cambiado desde entonces: desde el 2026-09-12 ArchMuse SÍ dibuja
  un cuadro (el suyo, al lado del tuyo), y lee más de un cuadro por plano. Lo
  que queda abajo es sólo lo que sigue siendo cierto con lo medido; lo dudoso
  está marcado [CONFIRMAR] y no debe llegar impreso.
-->

# ArchMuse · beta

## 1 · Instalar

1. Doble clic en **`ArchMuse-Beta-0.3.1.exe`**. No pide contraseña de administrador.
2. Si sale **«Windows protegió su PC»**: pulsa **«Más información»** y después
   **«Ejecutar de todas formas»**. Sale porque el programa es nuevo y aún no
   está firmado.
3. Cuando diga **«Listo»**, ya está. No hace falta reiniciar.

## 2 · Usar

Abre AutoCAD, abre tu plano y teclea **`ARCHMUSE`**.

Si tu plano tiene varias capas que podrían ser la de las estancias, te
pregunta cuál. No es un fallo: es que no quiere adivinarlo.

## 3 · Qué esperar

- Antes de escribir nada, te enseña lo que va a hacer y te pregunta.
- **Tu cuadro no se toca.** ArchMuse dibuja el suyo al lado, con sus mediciones.
- Un **`UNDO`** lo deshace todo de una vez.
- Queda una marca de borrador en la capa **`ARCHMUSE - BORRADOR`**. Puedes
  apagarla; no está pensada para borrarse.
- **Tus planos no salen de tu ordenador.** ArchMuse no se conecta a internet.

## 4 · Lo que todavía no funciona

- **AutoCAD LT no sirve**, y no tiene arreglo: hace falta AutoCAD completo.
- Las estancias tienen que ser **polilíneas cerradas, todas en la misma capa**,
  y **cada una con su nombre escrito dentro**. Si los nombres están separados
  de las polilíneas, medirá bien pero no sabrá cómo se llama nada.
- [CONFIRMAR] Una vivienda por plano / varias.
- [CONFIRMAR] Que el cuadro tenga que ser una tabla de AutoCAD y no líneas y textos sueltos.

## 5 · Si algo falla

> **Si sale un mensaje que te explica qué pasa, es un límite conocido. Si se
> queda colgado, si AutoCAD da un error raro, o si escribe una cifra que sabes
> que está mal, eso es un fallo: teclea `ARCHMUSE-INFORME` y mándamelo.**

`ARCHMUSE-INFORME` te enseña la lista exacta de lo que va a meter (ni planos ni
nombres de estancias), te pregunta, y deja un ZIP en tu **Escritorio**.
Arrástralo a WhatsApp.

## 6 · Versiones nuevas

- Te mandaré un fichero **`ArchMuse-0.3.2.archmuse`**. Doble clic, espera al
  mensaje, y **cierra y vuelve a abrir AutoCAD**. Si no lo cierras, ArchMuse
  te avisará y no escribirá nada hasta que lo hagas.
- Si la versión nueva va peor: menú **Inicio → ArchMuse → «volver a la versión
  anterior»**.
