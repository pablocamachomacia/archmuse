<!--
  El folio de la beta (T11 del PRD 2026-09-11, §4.5). Una hoja, para el
  arquitecto, sin jerga. Rehecho el 2026-09-15 para el primer usuario, con el
  contenido que pidió Pablo y contrastado contra el .lsp 3.7.0:
    - «un clic y Sí»: `getpoint` de la esquina y después «¿Te dibujo el cuadro?».
    - Ctrl+Z: todo va en un grupo de deshacer (StartUndoMark/EndUndoMark).
      Sin probar en AutoCAD.
    - NUMERO UDS vacía: `analyzer/plantilla_cuadro.py`, motivo C-8.
    - Referencias externas: C-15, el comando dice qué fichero abrir.
  Sin medir: el título exacto del aviso de Control Inteligente de Aplicaciones.
  Fuera a propósito, para que quepa en una hoja: actualizar, volver a la versión
  anterior, desinstalar y el aviso «Cargar una vez» de un perfil nuevo.
-->

# ArchMuse · beta

**Qué hace.** Mide las superficies útiles de las estancias de tu plano y dibuja
el cuadro de superficies al lado del tuyo, sin tocar nada de lo que tienes.
Todo ocurre en tu ordenador.

## 1 · Instalar

1. **Cierra AutoCAD.**
2. Doble clic en **`ArchMuse-Beta-0.3.7.exe`** y pulsa **Siguiente** hasta
   **Instalar**. La pantalla «Antes de instalar» explica el único cambio que
   hace en tu AutoCAD: léela.
3. Cuando diga **«Listo»**, ya está. No hace falta reiniciar.

## 2 · Si Windows no te deja abrirlo

Hay **dos avisos distintos**, y se resuelven distinto:

- **Ventana azul, «Windows protegió su PC».** Pulsa **«Más información»** y
  después **«Ejecutar de todas formas»**.
- **«Control Inteligente de Aplicaciones bloqueó una aplicación».** Aquí ese
  botón **no existe**:
  1. Escribe **Seguridad de Windows** en el menú Inicio y ábrelo.
  2. Entra en **Control de aplicaciones y navegador** y **apágalo**.
  3. Instala ArchMuse.
  4. **Vuelve a encenderlo.**

## 3 · Usar

1. Abre tu plano en AutoCAD y escribe **`ARCHMUSE`**.
2. **Haz clic** donde quieras el cuadro y contesta **Sí**.

Si antes te pregunta algo (qué capa, qué vivienda), contesta: prefiere
preguntar a adivinar. El cuadro sale marcado como **borrador**; puedes apagar
la capa «ARCHMUSE - BORRADOR» para imprimir.

**Ctrl+Z** justo después lo deshace todo de una vez.

## 4 · Lo que todavía no hace

- **No mide hojas con referencias externas.** Si las estancias están dibujadas
  en otro fichero, ArchMuse te dice cuál: ábrelo y escribe `ARCHMUSE` allí.
- **La casilla NUMERO UDS sale vacía.** Rellénala tú.
- **No funciona en AutoCAD LT**: hace falta AutoCAD completo.

## 5 · Si algo falla

Si sale un mensaje que explica qué pasa, es un límite conocido. Si se queda
colgado, da un error raro o escribe una cifra que sabes que está mal, escribe
**`ARCHMUSE-INFORME`**: te enseña lo que va a meter, te pregunta, y deja un ZIP
en tu **Escritorio**. **Mándamelo.**
