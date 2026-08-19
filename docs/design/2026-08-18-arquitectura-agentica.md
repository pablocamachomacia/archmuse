# Arquitectura agéntica de ArchMuse — capas y reglas de dependencia

**Fecha:** 2026-08-18 · **Actualizado:** 2026-08-19 (dos veces: mañana y noche) · **Estado:** implementada en `agente/`, salvo lo marcado como pendiente · **PRD:** `docs/prd/2026-08-18-sistema-de-skills-y-agente-profesional.md`

---

## 1. Las capas, y qué hay hoy en cada una

```
┌─ UI ───────────── Next.js (App Router). PENDIENTE. Sin lógica de negocio.
│                   Hoy: SPA en `static/index.html`, que se congela.
├─ API ──────────── FastAPI para lo nuevo. PENDIENTE.
│                   Hoy: Flask (`app.py`), que sigue sirviendo lo de siempre.
├─ AGENTE ───────── `agente/nucleo.py` + `agente/copiloto.py`      ✅
│                   intención → contexto → Skills/Tools → verificación → acta
│                   `agente/planificador.py`: una llamada -> un DAG validado,
│                   enseñable antes de ejecutarlo, y `revisar()` que rechaza
│                   sin gastar y devuelve la pregunta que desbloquea  ✅
├─ SKILLS ───────── `agente/skill.py` + `agente/skills/*.py`        ✅
│                   procedimiento profesional declarado y versionado
├─ TOOLS ───────── `agente/capacidad.py` + `agente/herramientas/*`  ✅
│                   saber hacer una cosa, con manifiesto ejecutable
│                   `agente/manifiesto.py`: de UN manifiesto salen los tres
│                   consumidores (Anthropic, OpenAPI, firma programática) ✅
│                   `agente/invocar.py`: la cuarta puerta, sin transporte  ✅
│                   `agente/contexto.py`: lo que ve el planificador, acotado ✅
├─ DOMINIO ─────── `modelo/`, `normativa/`, `analyzer/`             ✅ (ya existía)
│                   el grafo, el motor normativo, la geometría
├─ FRONTERAS ───── `bim/` (IFC, solo lectura)                       ✅ parcial
│                   IFC es intercambio, nunca el modelo interno
├─ ALMACENAMIENTO  `agente/memoria.py`, `agente/ejecucion.py`       ✅ en ficheros
│                   memoria de proyecto y bitácora. Postgres: PENDIENTE (D-6)
└─ INTEGRACIONES ─ Catastro, BOE, IFC, DXF, LLM                     ✅ parcial
                    detrás de capacidades; nunca invocadas desde una Skill
```

## 2. Las reglas de dependencia, y cuál las vigila

Una regla que no vigila un test es una intención. Estas cuatro las vigila CI:

| Regla | Por qué | Quién la vigila |
|---|---|---|
| Nada de `agente/` importa transporte (`flask`, `fastapi`, `werkzeug`, `django`) | Una capacidad tiene que poder invocarse desde la web, desde Revit, desde MCP o desde un `python -c` sin reescribirla. Es la prueba del plugin del ADR | `test_agente_nucleo.py::test_ninguna_capacidad_sabe_de_transporte` y `test_agente_skills.py::test_ninguna_skill_sabe_de_transporte` |
| Una Skill solo invoca las capacidades que declara | Si no, el manifiesto deja de decir la verdad sin que nada falle | `Contexto.invocar`, con test |
| Una Skill que no declara `escribe_memoria` no puede escribir en la memoria | Lo mismo, para el efecto más silencioso de todos | `_MemoriaSoloLectura`, con test |
| ArchMuse no instala Skills por su cuenta | Un sistema que se amplía a sí mismo pierde la propiedad de que alguien pueda decir qué sabe hacer y con qué criterio | `test_el_agente_no_tiene_ninguna_via_para_escribir_una_skill` |
| `bim/` no importa `agente/` ni `analyzer/` | La frontera traduce; no orquesta. Invertir la dependencia haría que el día de Revit hubiera que reescribir el dominio | estructura del paquete; `bim/__init__.py` lo declara |
| Los tres consumidores de un manifiesto dicen lo mismo, y lo mismo que la función Python real | Un esquema que declara `municipio` sobre una función que espera `nombre_municipio` revienta con `TypeError` delante de un cliente, y hasta `TL-3` nada lo detectaba | `test_agente_manifiesto.py::test_TODAS_las_capacidades_del_registro_son_coherentes` (recorre el registro, así que cubre lo que aún no existe) |
| Toda capacidad `determinista` tiene su salida congelada | Sin golden, la promesa de reproducibilidad no la comprueba nadie — y de ella dependen el sello, la reanudación y poder defender un análisis dos años después | `test_agente_goldens.py::test_toda_capacidad_determinista_tiene_su_golden` |
| Todo PDF sale marcado como borrador para revisión colegiada | C3. Delimita que ArchMuse asesora y no firma. Sin interruptor: un `con_marca=False` se usa el primer martes con prisa | `test_marca_borrador.py` (recorre `analyzer/`, y comprueba por AST que no exista el interruptor) |
| Ninguna llamada del producto va a Nominatim | Su instancia pública prohíbe el uso comercial, y el modo de fallo es un bloqueo por IP sin aviso | `test_geocodificacion_y_overpass.py::test_ningun_fichero_de_producto_llama_a_nominatim` |
| Una capacidad con efectos no se ejecuta sin autorización, **por ninguna puerta** | El portero vivía sólo en el ejecutor de Skills; el CLI, MCP o un plugin escribían sin permiso. Ahora está en `Capacidad.invocar` | `test_agente_escritura.py::test_toda_capacidad_con_efectos_se_niega_sin_autorizacion` |
| Una Skill declara los efectos de las capacidades que usa | Si no, el efecto ocurre bajo una autorización concedida para otra cosa, y la pantalla enseñó una lista incompleta | `Skill.comprobar_registro`, al **descubrir** |
| El fichero de origen conserva su sha256, también cuando la escritura falla | Un fallo a mitad es justo donde podría tocarse un original | `test_agente_escritura.py`, y `_con_sello_intacto` convierte un cambio en fallo grave |
| El planificador no ejecuta, no observa y no importa ningún framework | Un planificador que empieza a hacer eso *es* un framework de agentes escrito a plazos | `test_agente_planificador.py::test_el_planificador_no_ejecuta_nada` (por AST) |

Y una que **no** hace falta vigilar porque la impide la estructura: el dominio (`modelo/`, `normativa/`, `analyzer/`) no importa `agente/`. La dependencia va del agente al dominio y nunca al revés — que es lo que permite que el camino viejo (`/api/analizar`) siga funcionando sin enterarse de que existe un agente.

## 3. El recorrido de una petición, con el fichero de cada tramo

| Tramo | Dónde | Qué garantiza |
|---|---|---|
| **intención** | `nucleo.ejecutar` | El modelo decide; el ejecutor ejecuta. Nunca al revés |
| **contexto** | `memoria.MemoriaDeProyecto` | Append-only, con procedencia y conflictos declarados |
| **planificación** | `ejecucion.Plan` | DAG tipado, validado **antes** de ejecutar nada. Hoy lo construye el bucle paso a paso; el planificador de una llamada es V1-10 |
| **Skills** | `skill.Skill` | Requisitos, capacidades, `produce`, efectos y verificaciones declarados |
| **Tools** | `capacidad.Capacidad` | Manifiesto ejecutable; resultado estructurado con `ok` |
| **ejecución** | `ejecucion.Ejecutor` | Fallo aislado, reanudación por checkpoint, portero de efectos |
| **observación** | `ejecucion.Bitacora` | Append-only; es lo que hace posible reanudar |
| **verificación** | `verificacion.dictaminar` | Determinista, puede fallar, y sin comprobaciones no hay «verificado» |
| **resultado** | `acta.levantar` | Procedencia por dato y «no comprobado» derivado. Siempre borrador |

## 4. Lo que falta para que esto sea un producto, en orden

1. **Corpus normativo.** Con una regla transcrita, las Skills normativas citan una regla. Es el cuello de botella real y no lo arregla ninguna arquitectura.
2. **Postgres + almacenamiento de objetos + identidad.** V1-1 a V1-3 del plan de migración. Sin esto no hay estudio ajeno usándolo.
3. ~~El planificador tipado (`AG-1`)~~ **HECHO el 2026-08-19**, con `AG-2` (el validador determinista). Falta **la pantalla** (`INF-7`).

   Lo que sigue vigente del párrafo original: El ejecutor ya espera el `Plan`; falta quien lo produzca de una sola llamada y quien lo enseñe. Las dos dependencias del planificador están cerradas desde el 2026-08-19: `TL-3` (un manifiesto, tres consumidores) y `ME-5` (`agente/contexto.py`, el resumen acotado que va en el prompt). El PRD está escrito: `docs/prd/2026-08-19-planificador-tipado.md`, pendiente de aprobación.
4. ~~La escritura del DXF del cliente (`TL-2`)~~ **HECHA el 2026-08-19**, con `SK-1` (el procedimiento), `DOC-2` (el PDF que lo explica) y `DOC-3` (la marca de borrador, ya también en el DXF). El vertical entero se ejecuta con `python scripts/cuadro_de_superficies.py`. **Lo que falta es probarlo contra un plano real**: el camino completo sólo está probado contra fixtures, y los tests que usan el `v2s.dxf` de cliente se saltan si no está `ARCHMUSE_DXF_V2S`.
5. **Escritura de IFC dentro de `bim/`.** La lectura ya está (`bim/lector_ifc.py`, con la ida y la vuelta probada contra lo que exporta el propio repositorio); la escritura sigue en `analyzer/ifc_export.py` y se moverá cuando el vertical lo pida — mover hoy 300 líneas probadas no gana nada.
