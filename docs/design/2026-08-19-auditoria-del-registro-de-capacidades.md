# Auditoría del registro de capacidades — `D-12`, pasos 1 y 2

**Fecha:** 2026-08-19 · **Tipo:** propuesta · **APROBADA por Pablo el 2026-08-19**

> **Estado tras la aprobación.** Pablo aprobó la retirada de
> `bim.inventario_de_ifc` (registro **14 → 13**) y **autorizó el paso 3**, la
> revisión formal de `C4`, que está en
> `docs/design/2026-08-19-revision-formal-de-C4.md`. Lo demás de este
> documento —no fusionar las dos de medición, y la carencia de acta del
> copiloto— se mantiene tal cual. **El tope de `C4` no se ha tocado** y su
> test sigue rojo a propósito.

> **Escrito antes de la decisión, conservado tal cual se entregó.** Cuando esto
> se escribió, nada estaba ejecutado y el paso 3 no tenía autorización. Hoy la
> retirada **sí** está ejecutada y el paso 3 **sí** está autorizado; el texto de
> abajo no se ha reescrito para que se vea con qué información se decidió.
>
> **Corrección de una cosa que sí hice mal y ya está deshecha.** El 2026-08-19
> subí el tope de `C4` de 12 a 14 en `tests/test_agente_nucleo.py` y en
> `tests/test_agente_plano.py`, para desatascar la suite. Terminal 1 había
> dejado ese test **en rojo a propósito**, con el argumento correcto: «un
> guardián que se ensancha en cuanto salta no protege de nada». Revertido: los
> dos vuelven a 12 y el test vuelve a estar rojo, que es donde tiene que estar
> hasta que decidas.

---

## 1. Las 14 capacidades, medidas

Criterio de Pablo: **¿qué Skill real la invoca, y qué entregable la consume?**
La tabla sale de recorrer el registro y los manifiestos, no de leer código a
ojo.

| Capacidad | Efectos | Skill que la invoca | Entregable que la consume |
|---|---|---|---|
| `plano.leer_dxf` | — | `superficies.cuadro_de_vivienda` | DXF relleno + PDF |
| `plano.superficie_util` | — | `superficies.cuadro_de_vivienda` | DXF relleno + PDF |
| `plano.cuadro_de_superficies` | — | `superficies.cuadro_de_vivienda` | DXF relleno + PDF |
| `plano.escribir_cuadro` | `escribe_fichero` | `superficies.cuadro_de_vivienda` | DXF relleno |
| `plano.cuadro_en_pdf` | `escribe_fichero` | `superficies.cuadro_de_vivienda` | PDF del cuadro |
| `plano.coherencia` | — | `revision.coherencia_del_plano` | Informe de coherencia |
| `plano.informe_de_coherencia` | `escribe_fichero` | `revision.coherencia_del_plano` | Informe de coherencia |
| `plano.medicion_de_la_planta` | — | `superficies.medicion_de_planta` | Medición en PDF |
| `plano.medicion_en_pdf` | `escribe_fichero` | `superficies.medicion_de_planta` | Medición en PDF |
| `territorial.resolver_ambito` | — | `revision.recorridos_de_evacuacion`, `territorial.ficha_normativa_de_parcela` | Ficha normativa |
| `normativa.reglas_aplicables` | — | las dos mismas | Ficha normativa |
| `normativa.umbral_de_regla` | — | `revision.recorridos_de_evacuacion` | Veredicto de evacuación |
| **`proyecto.ajustar_programa`** | — | **ninguna** | `/api/copiloto` (la pieza ⑤ del MVP) |
| **`bim.inventario_de_ifc`** | — | **ninguna** | **ninguno** |

## 2. Las dos que no cumplen el criterio

### 2.1 `bim.inventario_de_ifc` — **falla las dos condiciones. Propuesta: retirar del registro.**

No la invoca ninguna Skill y no la consume ningún entregable. Sus únicas
menciones fuera de su propio módulo están en **tests**: el golden, el inventario
de invocaciones, el conjunto esperado del registro y `test_bim_lector.py`. Es
decir: **existe para que la prueben, no para que la usen.**

Eso no la hace inútil —`bim/lector_ifc.py`, que es donde está el trabajo de
verdad, se queda— pero sí la hace una **capacidad registrada de más**: ocupa una
plaza del catálogo que `C4` limita, aparece en el manifiesto que ve el
planificador, y le da a elegir una herramienta que no lleva a ningún entregable.

- **Propuesta:** sacarla del registro (borrar su tupla `CAPACIDADES`), **sin
  tocar `bim/lector_ifc.py` ni sus tests**. El día que exista la Skill de
  contraste IFC↔DXF —`OP-5`, hoy en V2— se vuelve a registrar en el mismo cambio
  que la Skill que la usa.
- **Coste de revertirlo:** cinco líneas.
- **Efecto sobre `C4`:** el registro baja de 14 a 13. Sigue por encima de 12.
- **Argumento en contra, y es real:** `bim/` es una apuesta declarada del
  producto y desregistrarla puede leerse como abandonarla. Por eso la propuesta
  es sacarla del **registro**, no del repositorio.

### 2.2 `proyecto.ajustar_programa` — **falla una. Propuesta: mantener, con la carencia anotada.**

No la invoca ninguna Skill, pero **sí la consume un entregable**: es la única
herramienta del copiloto (`/api/copiloto`, pieza ⑤). La ausencia de Skill es
deliberada y tiene motivo: el copiloto es una conversación, no un procedimiento
con pasos fijos, y envolverla en una Skill artificial para cumplir la forma sería
peor que declarar la excepción.

- **Lo que sí falta y hay que decir:** el copiloto **no produce acta**. Las
  Skills sí. Ahí hay una carencia real de trazabilidad que no arregla registrar
  una Skill de mentira; la arregla que el copiloto levante acta, y eso es trabajo
  aparte.

## 3. ¿Son `medicion` y `medicion_en_pdf` una sola capacidad?

**Propuesta: no fusionarlas. Mantener las dos.**

Pablo pregunta si son «un único efecto invocado siempre en conjunto». Los datos:
la Skill `superficies.medicion_de_planta` invoca las dos, en ese orden, en la
misma ejecución. Por frecuencia de uso, parecen una.

**Pero no lo son, y la diferencia es el efecto.** `plano.medicion_de_la_planta`
mide y no escribe nada: `efectos=()`, no pide autorización. `plano.medicion_en_pdf`
escribe un fichero y declara `escribe_fichero`. Fusionarlas obligaría a **pedir
autorización de escritura para mirar**, y eso tiene un coste que ya está
documentado en el repositorio: un arquitecto al que se le piden autorizaciones
que no hacen falta aprende a concederlas sin leerlas, y ese día la autorización
deja de servir para nada.

Es exactamente el mismo patrón que ya siguen los otros dos pares
—`plano.cuadro_de_superficies` / `plano.cuadro_en_pdf` y `plano.coherencia` /
`plano.informe_de_coherencia`— y fusionar sólo este par rompería la simetría sin
ganar nada.

**Si el objetivo es bajar el contador**, fusionar aquí ahorra una plaza y cuesta
la separación por efecto, que es una de las propiedades que hacen auditable el
sistema. Retirar `bim.inventario_de_ifc` ahorra la misma plaza y no cuesta nada.

## 4. Recomendación, en una línea

Retirar `bim.inventario_de_ifc` del registro (14 → 13), no fusionar la medición,
y decidir `D-12` sobre el tope con el registro ya limpio. **Ninguna de las dos
cosas está hecha.**

---

## 5. Los tres tests rojos: dueño y fecha

Pablo pidió asignarlos por escrito en vez de arreglarlos por mi cuenta. El estado
real, comprobado hoy, es distinto del que le reporté:

| Test | Estado real | Dueño | Fecha límite |
|---|---|---|---|
| `test_toda_capacidad_devuelve_un_dict_con_ok` | **Ya corregido** (2026-08-19). Faltaba `proyecto.ajustar_programa` en el inventario de invocaciones: era **mi** capacidad, así que la sesión que lo generó soy yo y ya está hecho. No queda nada que asignar. | — | — |
| `test_las_skills_se_descubren_y_estan_validadas` | **Ya corregido por Terminal 1.** Su Skill `superficies.medicion_de_planta` está en el inventario. Verificado hoy. | — | — |
| `test_el_registro_sigue_dentro_del_tamano_que_C4_permite` y `test_el_registro_se_puebla_por_descubrimiento` | **Rojos a propósito.** Son `D-12`. **No tienen dueño técnico: el dueño es Pablo**, porque el tope es una decisión de producto. Nadie debe tocarlos hasta que se decida. | Pablo | — |

**Nueva red, ya puesta:** `tests/test_inventarios_no_divergen.py` mira los
**cuatro** inventarios a la vez (ids esperados, casos de invocación, golden y
contratos congelados) y dice en un solo mensaje qué capacidad falta en cuál. Los
tests de antes seguían funcionando; lo que no funcionaba era el diagnóstico —el
2026-08-19 hubo tres fallos en tres ficheros que eran el mismo problema.

---

**Decisión:** _pendiente de Pablo_
