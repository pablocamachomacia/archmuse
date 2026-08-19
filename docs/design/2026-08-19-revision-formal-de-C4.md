# Revisión formal de `C4` — el tope del catálogo de capacidades

**Fecha:** 2026-08-19 · **Tipo:** revisión para decisión · **Decide:** Pablo
**Es el paso 3 de `D-12`**, autorizado por Pablo el 2026-08-19 después de aprobar
la retirada de `bim.inventario_de_ifc` (pasos 1 y 2).

> **Aviso que va primero a propósito.** La recomendación de este documento
> coincide con lo que yo intenté hacer por mi cuenta el 2026-08-19 y hubo que
> revertir: subir el número. **Eso es un motivo para desconfiar de este
> documento, no para creerlo.** Va escrito como documento y no aplicado como
> cambio precisamente por eso. La diferencia con aquel día no es el argumento —
> es que ahora hay una medición, se ha retirado una capacidad de verdad, y quien
> decide eres tú. El test sigue en rojo mientras lees esto.

---

## 1. Qué dice `C4` exactamente

De `docs/design/2026-08-18-alineacion-estrategica-paso0.md` §3, aprobado por
Pablo el 2026-08-18, literal:

> **C4 — Cobertura antes que catálogo.** Se deroga el objetivo de "cientos de
> capacidades". El MVP se construye con entre 8 y 12, elegidas por fiabilidad
> auditable. Añadir capacidades mientras el corpus normativo siga vacío
> amplifica el riesgo de alucinación normativa, no el valor.

Y su propia prueba de cumplimiento, del §7 del mismo documento:

> **Prueba del catálogo.** Contar las capacidades registradas frente a las
> auditadas. Si la primera cifra crece más rápido que la segunda, `C4` se ha
> incumplido.

**Las dos frases no dicen lo mismo, y esa es la raíz de todo este documento.**
La primera fija un número absoluto (8–12). La segunda fija una **razón** entre
dos cifras. Se pueden cumplir y romper independientemente, y hoy el repositorio
está exactamente en ese hueco: **rompe la primera y cumple la segunda de
sobra.**

---

## 2. El estado medido, hoy

13 capacidades registradas tras retirar `bim.inventario_de_ifc`. La tabla sale de
recorrer el registro, los manifiestos de las Skills y los ficheros congelados;
no de leer código a ojo.

| Capacidad | Efecto | Salida congelada | Skill que la invoca |
|---|---|---|---|
| `normativa.reglas_aplicables` | — | sí | `revision.recorridos_de_evacuacion`, `territorial.ficha_normativa_de_parcela` |
| `normativa.umbral_de_regla` | — | sí | `revision.recorridos_de_evacuacion` |
| `plano.coherencia` | — | sí | `revision.coherencia_del_plano` |
| `plano.cuadro_de_superficies` | — | sí | `superficies.cuadro_de_vivienda` |
| `plano.cuadro_en_pdf` | `escribe_fichero` | no ¹ | `superficies.cuadro_de_vivienda` |
| `plano.escribir_cuadro` | `escribe_fichero` | no ¹ | `superficies.cuadro_de_vivienda` |
| `plano.informe_de_coherencia` | `escribe_fichero` | no ¹ | `revision.coherencia_del_plano` |
| `plano.leer_dxf` | — | sí | `superficies.cuadro_de_vivienda` |
| `plano.medicion_de_la_planta` | — | sí | `superficies.medicion_de_planta` |
| `plano.medicion_en_pdf` | `escribe_fichero` | no ¹ | `superficies.medicion_de_planta` |
| `plano.superficie_util` | — | sí | `superficies.cuadro_de_vivienda` |
| `proyecto.ajustar_programa` | — | sí | **ninguna** ² |
| `territorial.resolver_ambito` | — | sí | `revision.recorridos_de_evacuacion`, `territorial.ficha_normativa_de_parcela` |

¹ Las cuatro que escriben no llevan golden **por diseño**: lo que congelaría un
golden de una capacidad de escritura es un fichero binario, no un cálculo. Están
cubiertas por sus propios tests de escritura, que es lo que hay que comprobar en
ellas — destino seguro, sello del original intacto, negativa sin autorización.

² La única sin Skill. Está en el copiloto (`/api/copiloto`, pieza ⑤ del MVP) y su
ausencia de Skill es deliberada: el copiloto es una conversación, no un
procedimiento de pasos fijos. Ver la auditoría del 2026-08-19 §2.2. **Lo que sí
le falta de verdad es levantar acta**, y eso no lo arregla el tope de `C4`.

**Las cifras que pide la prueba del §7:**

- **Registradas: 13.**
- **Auditadas: 13.** Las trece tienen contrato congelado, caso de invocación que
  comprueba el contrato de salida también en el camino de fallo, y o bien salida
  congelada o bien tests de escritura propios. Nueve están probadas además contra
  los planos reales del cliente.
- **Con Skill que las invoca y entregable que las consume: 12 de 13.**

La razón que `C4` vigila es **1,0**. No hay ni una capacidad registrada sin
auditar. La cifra que se pasa es la otra: **13 > 12, por una.**

---

## 3. Lo que `C4` estaba protegiendo, y si sigue protegido

El motivo declarado es literal: *«añadir capacidades mientras el corpus normativo
siga vacío amplifica el riesgo de alucinación normativa, no el valor»*.

Ese riesgo tiene una forma concreta: **una capacidad que afirma algo sobre
normativa sin una cita recuperada detrás.** Comprobado sobre las trece:

- **Dos tocan normativa** — `normativa.reglas_aplicables` y
  `normativa.umbral_de_regla`. Las dos leen del corpus y **devuelven nada cuando
  el corpus no cubre el caso**; no rellenan el hueco. Son las mismas dos desde
  antes de que `C4` se aprobara: el catálogo ha crecido en 5 desde entonces y
  **ninguna de las 5 consulta una norma**.
- **Las once restantes miden geometría o transforman un diccionario.** Su modo
  de equivocarse es dar mal una superficie, que es grave y es otro riesgo — uno
  que se ataca con planos reales y goldens, no con un tope de catálogo.

**Conclusión honesta de este apartado:** el riesgo que `C4` nombra por escrito no
ha subido con las cinco capacidades nuevas. Lo que sí ha subido es otra cosa que
`C4` también protegía sin decirlo con tanta claridad: **la superficie que hay que
mantener**, y con ella el número de herramientas que el planificador tiene que
saber elegir. Eso es real y no se puede descartar apelando al corpus.

---

## 4. Las tres salidas

### Opción A — Mantener el 12 y retirar una capacidad más

Bajar de 13 a 12 retirando una. **Problema: no hay candidata.** Después de sacar
`bim.inventario_de_ifc`, las trece que quedan tienen Skill que las invoca o
entregable que las consume. Retirar una más sería elegir una por el número, no
por el criterio — que es justo lo que `C4` quiere evitar en la dirección
contraria.

La única fusión posible, `medicion` + `medicion_en_pdf`, **está desaconsejada con
motivo** en la auditoría §3: obligaría a pedir autorización de escritura para
mirar, y un arquitecto al que se le piden autorizaciones que no hacen falta
aprende a concederlas sin leerlas.

- **A favor:** el tope aprobado se respeta al pie de la letra, sin discusión.
- **En contra:** se pierde una capacidad útil por aritmética. Y el mensaje que
  deja es peor que el número: que el catálogo se recorta por el contador.

### Opción B — Subir el tope a 13 y dejarlo ahí

- **A favor:** un cambio, verde, y refleja lo que hay.
- **En contra, y pesa:** es exactamente lo que se hizo mal el 2026-08-19. Un tope
  que se sube hasta donde llegue el registro cada vez que el registro lo pasa no
  es un tope. Y no arregla el problema de fondo: la próxima capacidad vuelve a
  ponerlo rojo y volvemos a esta conversación.

### Opción C — Reformular `C4` en lo que su propia prueba ya dice (recomendada)

Sustituir el tope absoluto por las dos condiciones que `C4` persigue de verdad, y
que hoy sí se pueden comprobar mecánicamente:

1. **Ninguna capacidad registrada sin auditar.** Contrato congelado + caso de
   invocación + salida congelada (o tests de escritura si escribe). Ya hay test.
2. **Ninguna capacidad registrada sin Skill que la invoque o entregable que la
   consuma**, declarado por escrito en el mismo cambio que la registra. Es el
   criterio con el que se retiró `bim.inventario_de_ifc`; convertirlo en test lo
   hace irreversible por descuido. La excepción de `proyecto.ajustar_programa`
   se declara nombrada, no en general.
3. **Un tope, pero de los que se pasan de verdad: 20.** No para permitir 20, sino
   para que dispararlo signifique algo. Entre 13 y 20 caben todas las capacidades
   que el primer vertical necesita; llegar a 20 con el corpus vacío sí sería la
   deriva que `C4` nombra.

- **A favor:** convierte `C4` en lo que su §7 ya decía que era, y añade el
  criterio del entregable, que es el que de verdad frenó el catálogo esta vez —
  el que retiró una capacidad, no el que puso un test en rojo.
- **En contra, y hay que decirlo:** reformular un guardián justo después de que
  salte es el patrón con el que se desactivan todos los guardianes del mundo. La
  única defensa es que la reformulación sea **más exigente en algo**, no sólo más
  cómoda: aquí lo es en el punto 2, que hoy no existe como test y que es el que
  habría impedido que `bim.inventario_de_ifc` estuviera registrada un año.

---

## 5. Recomendación

**Opción C**, y con la condición de que el punto 2 entre como test **en el mismo
cambio** que suba el tope. Sin eso es la opción B con mejor prosa.

Si la respuesta es «no me fío, y menos viniendo de ti después de lo del tope»,
la alternativa defendible es **mantener el 12 y dejar el test rojo como deuda
visible** hasta que el corpus tenga contenido. Un test rojo permanente es un
coste real —se aprende a ignorarlo, y ese es su propio riesgo— pero es un coste
honesto y no requiere fiarse de mi criterio en esto.

**Lo que NO va a pasar por iniciativa mía:** que el número suba sin que lo digas
tú. El test seguirá rojo hasta entonces, y ahora además está protegido por
`tests/test_guardianes_de_decision.py`, que hace que cambiarlo exija tocar dos
ficheros y nombrar la decisión.

---

**Decisión:** _pendiente de Pablo_
