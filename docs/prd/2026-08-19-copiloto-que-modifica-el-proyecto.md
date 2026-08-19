# PRD — Copiloto que modifica el proyecto (pieza ⑤ del MVP)

**Estado:** Borrador · **Fecha:** 2026-08-19 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente — el informe ejecutivo de Pablo del 2026-08-19 hace de requisitos_

> **Alcance.** Este PRD cubre **sólo la pieza ⑤** del MVP: el chat contextual que
> **modifica el proyecto** en vez de responder texto. Las piezas ① a ④ no
> necesitan PRD: sus capacidades y sus endpoints ya existen
> (`/api/analizar-sitio`, `/api/generar-opciones`, `/api/analizar`,
> `/api/viabilidad-financiera`) y lo que falta ahí es una vista, no una
> capacidad.

---

## 1. Problema que resuelve

Del informe ejecutivo: *«Y ArchMuse modifica el proyecto, no simplemente
responde con texto.»* Es la frase que separa este producto de un chat sobre
arquitectura, y es la única de las cinco piezas que **no existe en ninguna
forma**: no hay chat en los 800 KB de la SPA, y `OP-8` («modifica el proyecto y
recalcula lo que dependa») está aplazado a V2 en el backlog.

El dolor concreto: hoy, para probar «¿y si quito una vivienda y agrando las
demás?», el arquitecto vuelve al formulario, cambia el mix, y regenera —
perdiendo la comparación con lo anterior. Es el bucle que hace que nadie
explore alternativas de verdad.

## 2. Usuario afectado

El arquitecto de la prueba del §7 del informe: entra sin que nadie le explique
nada, tiene una parcela, y quiere el proyecto más rentable posible. No va a
leer documentación y no va a perdonar un número que no cuadre.

## 3. Objetivo de negocio

Es **el** diferenciador del MVP. ①–④ existen en otros productos; un copiloto que
entiende «haz la opción B más eficiente» y reejecuta los motores no. Y es lo que
convierte la demo de «mira qué gráficos» en «esto me ahorraría trabajo», que es
literalmente el criterio de éxito que fija el informe.

## 4. Objetivo técnico

- El copiloto **no calcula nada**. Traduce la intención del arquitecto a
  invocaciones de herramientas; los motores calculan y el copiloto narra lo que
  devolvieron. Es la regla fundamental del informe, y en ArchMuse ya está hecha
  cumplir por construcción: una capacidad `llm` no puede emitir un hecho ni un
  cálculo — no hay forma de construir el objeto.
- Tras cada modificación, el proyecto se **reevalúa entero** con los mismos
  motores que lo evaluaron la primera vez. No hay un camino de código paralelo
  para «lo modificado».
- **Nunca toca un fichero del arquitecto.** Opera sobre el proyecto generado en
  memoria/almacén. Ésta es la distinción que saca a `OP-8` de su aplazamiento:
  lo que estaba aplazado es escribir en el DXF de un cliente, y aquí no hay
  ninguno.
- Toda modificación es **reversible y trazable**: queda registrado qué se pidió,
  qué herramienta se invocó, con qué argumentos y qué cambió.
- Lo que el copiloto no puede hacer, **lo dice**. No reformula la petición hasta
  que encaje con lo que sabe hacer.

## 5. Casos de uso

Los tres del informe, más el que falta y hay que declarar:

**CU-1 · «Haz la opción B más eficiente.»** Interpreta «eficiente» como el
indicador que ya calcula el comparador (repercusión de zonas comunes), propone
el cambio de mix que lo mejora, lo aplica, regenera y reevalúa. Enseña las dos
cifras: antes y después.

**CU-2 · «Elimina una vivienda y aumenta las superficies.»** Modifica el mix
manteniendo la superficie construida objetivo. Es aritmética, no criterio.

**CU-3 · «¿Cuál tiene mejor rentabilidad?»** **No modifica nada**: lee el
comparador y contesta. Distinguir las preguntas de las órdenes es parte del
trabajo, y confundirlas —modificar el proyecto porque alguien preguntó— es el
peor fallo posible de esta pieza.

**CU-4 · «Ponme el salón orientado al sur.»** ArchMuse **no sabe hacer esto**:
el generador coloca las estancias y no admite una restricción de orientación por
pieza. La respuesta correcta es decirlo, no intentarlo.

## 6. Casos límite

| Caso | Qué tiene que pasar |
|---|---|
| Petición ambigua («hazlo mejor») | Pregunta qué eje: superficie, nº de viviendas, eficiencia o margen. No elige por el arquitecto |
| Petición fuera de lo que sabe hacer (CU-4) | Lo dice, con lo que **sí** puede hacer al lado. No lo aproxima |
| La regeneración falla | El proyecto anterior **queda intacto**; se dice que no se pudo y por qué |
| El cambio empeora la métrica que se pedía mejorar | Se entrega igual, **diciéndolo**. Ocultarlo sería el LLM decidiendo qué es un buen proyecto |
| Pregunta sobre normativa | Contesta desde lo verificable (parámetros urbanísticos) y declara que el corpus del CTE no está cubierto. No improvisa un artículo |
| Sin clave de API | El chat se desactiva con aviso explícito; ①–④ siguen funcionando enteras |
| Dos peticiones seguidas | La segunda parte del estado que dejó la primera. El copiloto tiene memoria del proyecto, no del turno |

## 7. Flujo del usuario

1. El arquitecto tiene una alternativa en pantalla (zona central) y escribe en la
   zona derecha.
2. ArchMuse enseña **qué va a hacer** antes de hacerlo: la herramienta y los
   argumentos, en castellano. Un cambio de proyecto no ocurre en silencio.
3. Ejecuta, regenera, reevalúa.
4. Contesta con **lo que cambió**, cifra anterior y nueva, y deja la vista
   actualizada.

## 8. Criterios de aceptación

1. «Elimina una vivienda y aumenta las superficies» modifica el mix, regenera y
   reevalúa, y la vista refleja el cambio.
2. «¿Cuál tiene mejor rentabilidad?» **no modifica nada** y contesta con las
   cifras del comparador. Comprobado con un test que verifica que no se invocó
   ninguna herramienta de escritura.
3. Una petición que ArchMuse no sabe atender produce una negativa explícita, no
   un intento aproximado.
4. Ninguna cifra de la respuesta del copiloto puede faltar en el respaldo de las
   herramientas ejecutadas — `agente/respaldo.py` lo comprueba.
5. Un fallo de generación deja el proyecto anterior intacto.
6. Sin `ANTHROPIC_API_KEY`, la aplicación arranca y ①–④ funcionan.
7. Toda modificación queda en el acta: petición, herramienta, argumentos,
   resultado.

## 9. Riesgos

**R-1 · El copiloto decide criterio de proyecto.** «Más eficiente» es
interpretable, y elegir por el arquitecto cruza la frontera de autoría. *Mitigación:*
las herramientas son aritméticas y estrechas; el copiloto elige **cuál** invocar,
nunca **cuánto** vale un resultado. Y enseña la traducción antes de ejecutarla.

**R-2 · Coste por turno.** Cada regeneración es una llamada al generador con
8.192 tokens de salida. Cuatro alternativas y tres modificaciones son siete
llamadas caras. *Mitigación:* el techo de gasto por proceso ya existe
(`ia/uso.py`, `ARCHMUSE_TOPE_GASTO_USD`), y regenerar sólo la alternativa
tocada, no las cuatro.

**R-3 · Latencia.** Regenerar es lento y el informe pide «pocos minutos».
*Mitigación:* enseñar el plan inmediatamente y el resultado cuando llegue; el
arquitecto ve que pasa algo.

**R-4 · Se demuestra y no se usa.** El riesgo de fondo de toda esta línea, que
`OP-11` ya señaló para el generador. *No lo mitigo con tecnología:* lo mide la
prueba del §7 del informe, y si sale que no, el producto cambia, no se le añade.

## 10. Impacto sobre módulos existentes

**Nuevo:** `agente/herramientas/proyecto.py` (las herramientas de modificación),
`static/copiloto.js` y la vista de tres zonas, un endpoint `/api/copiloto`, y sus
tests.

**Se consume sin modificar:** `agente/nucleo.py` (el bucle de tool-use ya
existe), `agente/respaldo.py`, `analyzer/ai_generator.py`,
`analyzer/comparador_opciones.py`, `analyzer/evaluator.py`, `analyzer/storage.py`.

**No se toca:** `static/app.js` (275 KB) — la vista nueva es aparte, que es lo
que pide el §4 del informe y lo que evita romper lo que ya funciona.

## 11. Plan de implementación

| # | Tarea | ~ |
|---|---|---|
| **CP-1** | `agente/herramientas/proyecto.py`: leer el proyecto, cambiar el mix, cambiar plantas, cambiar superficie objetivo, regenerar+reevaluar. Aritméticas y estrechas. | 2h |
| **CP-2** | Endpoint `/api/copiloto`: petición + proyecto_id → plan, ejecución y respuesta con acta. | 1,5h |
| **CP-3** | La vista de tres zonas: izquierda proyecto/parcela, centro plano/3D, derecha copiloto, y las 5 pestañas de arriba. | 3h |
| **CP-4** | ①② cableados: formulario de parcela y parámetros → análisis automático. | 1,5h |
| **CP-5** | ③④: los cuatro objetivos de optimización y la tabla comparativa. | 2h |
| **CP-6** | Separar «comprobado» de «estimado» en la pestaña Normativa (decisión de Pablo, 2026-08-19). | 1h |
| **CP-7** | Tests de los 7 criterios de aceptación. | 2h |

## 12. Plan de pruebas

- **Con cliente guionizado, sin red ni clave**: la mayoría. Es como ya se prueba
  `agente/nucleo.py`.
- **El test que más importa:** una pregunta (CU-3) no invoca ninguna herramienta
  de modificación. Se comprueba contando invocaciones, no leyendo la respuesta.
- **De no regresión:** la suite entera verde. La vista nueva no toca `app.js`, así
  que una regresión ahí significaría que el cableado ha roto un endpoint.

## 13. Métricas para medir el éxito

1. **Minutos hasta la primera alternativa comparable.** El informe dice «pocos».
2. **Peticiones por sesión, y cuántas ArchMuse sabe atender.** Si la segunda cifra
   es baja, el catálogo de herramientas está mal elegido.
3. **La prueba del §7**, que es la única que decide.

## 14. Posibles motivos para NO implementar la idea

**1. Revierte `OP-11`, que congelaba el generador.** El backlog lo congeló
citando que la generación «demuestra bien y no vende» y que es lo que más
tensiona la frontera de autoría. Este PRD lo pone en el centro. **Es una
reversión legítima —la decisión es de Pablo— pero es una reversión**, y si a las
24 h la prueba del §7 sale «está muy chulo pero no lo usaría», la decisión
anterior era la correcta y hay que volver a ella sin discutir.

**2. El corpus sigue vacío, y eso no cambia.** El MVP no lo necesita —el informe
excluye explícitamente resolver el CTE— pero conviene no engañarse: lo que se
demuestra mañana es el flujo, no la verificación normativa. Vender lo segundo
con lo primero es el ataque nº1 contra el producto.

**3. Es la línea contraria a la de las últimas sesiones.** DXF real,
trazabilidad y revisión de coherencia funcionan hoy sobre ficheros de clientes.
Esto es lo otro. **Las dos no pueden ser la prioridad**, y dejar los dos rumbos
vivos es como se pierden los dos.

**Mi recomendación:** hacerlo, con la reversión de `OP-11` escrita y con la
prueba del §7 como juez. Si pasa, se reordena el backlog entero detrás. Si no
pasa, se vuelve a la línea del DXF y se ha perdido un día, que es exactamente lo
que un MVP sirve para averiguar.

---

**Decisión:** _pendiente — se implementa contra el informe ejecutivo del 2026-08-19_
