# Evaluación: las 4 peticiones del primer lector vs. producto B (superficies)

> Documento de decisión. Sesión del 2026-08-23, pedido explícito de Pablo:
> evaluar, sin escribir código, cuál de las cuatro cosas que pidió el primer lector
> («detalles constructivos, planos de carpintería, todo desde BIM, y memoria
> justificativa») es mejor producto vendible que el producto B actual
> (cuadro de superficies + memoria desde DXF, ~70% construido).
>
> Registrado aquí para que nada de esto se redescubra como idea nueva —
> mismo patrón que `OP-13`/`OP-14` en `docs/AGENTE_BACKLOG.md`.

## 0. Contexto y dato nuevo de la sesión

La petición del primer lector **ya estaba registrada** (2026-08-19, noche 7) y produjo
el roadmap vinculante de 7 pasos
(`docs/design/2026-08-19-roadmap-bim-carpinteria-detalles-memoria.md`).
Lo nuevo el 2026-08-23 son dos cosas:

1. **Fallo de generalización confirmado por Pablo con un DXF ajeno** (plano
   latinoamericano de descarga): sus superficies estaban en capas
   `A-POLIGONO` / `A-TEXTOS AREAS`, no en la `00 areas` de los planos del
   estudio, y el motor no extrajo superficies por estancia. El motor depende
   de la convención de capas del autor.
2. La pregunta de si **carpintería** debía adelantarse o sustituir a B, por
   la intuición de que «las puertas y ventanas ya están en el DXF».

## 1. Dato medido (2026-08-23): qué hay de carpintería en los DXF reales

Escaneo directo con ezdxf de `v2s.dxf` y `V5.dxf` (los dos planos reales del
cliente, fuera del repo). Tercera medición, coherente con las dos de
`OP-13` (2026-08-19):

| Qué | v2s.dxf y V5.dxf (estructura idéntica: 55 capas, 353 bloques con nombre, 154 con nombre de carpintería) |
|---|---|
| Capas de carpintería | Solo puertas: `00 PUERTAS`, `00 PUERTA`, `00 PUERTA-S`, `__ 00 PUERTA _`. **Ninguna capa de ventanas** |
| Puertas | Bloques exportados de Revit con vivienda tipo en el nombre (`DIR04_PE-_PUERTA - PE-01-…-VT25`); ~3 de 4 con dimensión legible en el nombre (`K_Puerta de entrada - 825 x 2150 mm-…`, medición de `OP-13`) |
| Ventanas | **Sin datos.** Cuatro bloques genéricos (`ven01`, `ven2`, `ven3`, `00 SEC VENTANA`), sin dimensión, sin vivienda, dibujadas como geometría |
| Atributos (`ATTDEF`) | **Cero** en los 154 bloques de carpintería — todo el dato vive en el *nombre* del bloque |
| `INSERT` en modelspace | **0** — las referencias están anidadas en otros bloques |

Conclusión: un plano de carpintería automático desde estos DXF saldría con las
ventanas en blanco, y en un cuadro de carpintería español las ventanas son la
mitad cara (vidrio, DB-HE, presupuesto pieza a pieza).

## 2. La trampa de carpintería — son tres, no una

1. **El dato no está en el DXF.** Tres mediciones sobre dos planos reales:
   puertas a medias, ventanas nada.
2. **Donde el dato sí está (BIM), ya es casi gratis.** Revit genera tablas de
   planificación de puertas/ventanas de serie, y el plugin *id:legend / plano
   de carpinterías* (Autodesk App Store) monta el plano completo con alzado,
   planta, cotas y cantidades. Ahí no hay hueco de mercado.
3. **Es el candidato MÁS dependiente de cómo dibuje el autor, no el menos.**
   El dato de puertas vive en la nomenclatura de bloques de un export Revit
   concreto; parsear nombres de bloque generaliza peor que detectar capas.

El cierre de la trampa: **el mercado sin competencia (CAD 2D) es exactamente
el mercado sin dato; el mercado con dato (BIM) es el mercado con competencia
gratis.** Lo único cierto de la intuición: no exige firma de otro técnico.

## 3. Los cuatro candidatos, en una línea cada uno

- **Detalles constructivos** — sigue vetado (`OP-14`, «NO SE HACE»): el
  detalle se *elige* con criterio, foso nulo frente a bibliotecas de
  fabricantes, y es lo más cercano a la autoría de todo el catálogo. Ningún
  dato nuevo lo reabre.
- **Planos de carpintería** — no desde DXF (§1-§2). Camino honesto: paso 6
  del roadmap, desde IFC, donde `IfcDoor`/`IfcWindow` son objetos tipados con
  dimensiones declaradas (`bim/lector_ifc.py` ya los lee, verificado el
  2026-08-20 contra 3 IFC reales de terceros).
- **Generación desde BIM** — no es un producto, es **el canal de datos**: la
  respuesta estructural al fallo de generalización (IFC es semántico, el DXF
  es dibujo). Paso 3 del roadmap, PoC ya verificado.
- **Memoria justificativa** — la mitad ya está hecha y es parte de B
  (`docs/prd/2026-08-19-memoria-justificativa-automatica.md`, Implementado);
  la mitad normativa espera al corpus (`NOR-1`) y tiene delante a CYPE
  Memorias CTE, que ya genera la memoria del Anejo I del CTE con asistentes.
  El hueco de ArchMuse no es *redactar* la memoria: es **contrastarla contra
  el plano** — que es exactamente el producto B.

## 4. Dependencia de que el arquitecto «dibuje bien» (de menos a más)

1. Memoria normativa (texto, no dibujo) — pero bloqueada por corpus y con CYPE delante.
2. BIM/IFC — semántica estándar; el antídoto real al fallo del DXF ajeno.
3. **B (superficies DXF)** — dependencia media y **atacable**: el DXF ajeno
   SÍ tenía el dato (`A-POLIGONO`/`A-TEXTOS AREAS`); el motor no supo dónde mirar.
4. Carpintería DXF — dependencia máxima (nombres de bloque de un export concreto).
5. Detalles — no depende del dibujo; depende de criterio profesional, que es peor.

## 5. Puntuación (marco de 6 criterios, 1–5)

| Criterio | B (superficies + memoria) | Carpintería DXF | Carpintería IFC (paso 6) | Detalles | Memoria normativa |
|---|---|---|---|---|---|
| Frecuencia | **5** (cada proyecto y cada revisión) | 3 | 3 | 3 | 3 |
| Horas que quita | 3–4 | **1** (solo puertas al 75%) | 4 | 2 (no fiable) | 3 (CYPE ya las comprimió) |
| Aprovecha el motor | **5** (~70% hecho) | 1 (el dato no existe) | 3 (PoC verificado) | 0 | 4 hecha / 1 normativa |
| Competencia (5 = poca) | **4** (nadie contrasta memoria↔plano) | 2 | 2 (Revit + plugins) | 1 (fabricantes gratis) | 1 (CYPE Memorias CTE) |
| Vendibilidad | **4** | 1 | 3 | 1 | 2 |
| Ticket defendible | 3–4 | 1 | 3 | — | 2 (CYPE ancla el precio) |
| **Total orientativo** | **24–25** | **9** | **18** | **7** | **13** |

## 6. Decisión

1. **Se sigue con B.** Nada de lo pedido lo supera hoy, y la memoria
   justificativa (petición nº 4 del primer lector) ya es un entregable de B.
2. **Carpintería ni sustituye a B ni se adelanta.** Va donde el roadmap
   aprobado ya la puso: paso 6, desde BIM (paso 3). Adelantarla desde DXF
   violaría la regla dura del roadmap y entregaría un cuadro con las ventanas
   en blanco.
3. **Detalles constructivos: sigue vetado** (`OP-14`).
4. **La inversión que el dato nuevo sí justifica: atacar la generalización de
   B** — detección asistida de convenciones de capas (proponer capas
   candidatas por heurística de contenido, confirmación del usuario, sin
   adivinar). Si Pablo lo aprueba, el primer entregable es su PRD
   (`docs/prd/2026-08-23-deteccion-asistida-de-convenciones-de-capas.md`),
   por la regla PRD-antes-de-código de `CLAUDE.md`.

## Referencias

- `docs/design/2026-08-19-roadmap-bim-carpinteria-detalles-memoria.md` — orden vinculante de 7 pasos.
- `docs/AGENTE_BACKLOG.md` §`OP-13` (carpintería, medida dos veces el 19-08) y §`OP-14` (detalles, vetado).
- `docs/prd/2026-08-19-memoria-justificativa-automatica.md` — Implementado.
- `docs/design/2026-08-20-resumen-de-cierre.md` §4 — la apuesta: capa de verificación antes de visado.
- Competencia verificada (2026-08-23): CYPE Memorias CTE (memoria del Anejo I
  del CTE con asistentes, https://info.cype.com/es/tema/memoria-del-proyecto-segun-el-cte/)
  y *id:legend / plano de carpinterías* para Revit (Autodesk App Store,
  https://apps.autodesk.com/RVT/es/Detail/Index?id=3280528001367031810).
