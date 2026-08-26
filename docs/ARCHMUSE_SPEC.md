# ARCHMUSE — Especificación de construcción

> Documento de trabajo para un agente de código (Claude Code).
> Lee este fichero **completo** antes de escribir una sola línea.
> Idioma del código y comentarios: inglés. Idioma de la UI y los informes: español.

> **Nota (2026-08-19).** El §3 (stack y estructura de directorios) y el §14
> (orden de trabajo) **se han eliminado de este documento: quedaron sin efecto**.
> M0 y ese orden de trabajo describían arrancar de cero, y cuando se redactó
> esta especificación el repositorio ya tenía ~950 tests y una arquitectura
> propia (`agente/`, `analyzer/`, `normativa/`, `modelo/`). Ver `PROGRESS.md`.


---

## 0. Cómo usar este documento

Este fichero define **qué construir, en qué orden, y con qué criterios de aceptación**.

Reglas de trabajo obligatorias:

1. **No saltes hitos.** El orden M0 → M1 → M2 → M3 → M4 es una cadena de dependencias, no una lista de deseos.
2. **No implementes nada marcado como `NO CONSTRUIR`.** Si crees que hace falta, pregunta antes; no lo añadas por iniciativa propia.
3. **Cada hito termina con sus tests en verde y su criterio de aceptación demostrado.** No avances con tests rojos.
4. **Cuando dudes entre "hacerlo bien" y "hacerlo completo", elige hacerlo bien y más pequeño.**
5. Al terminar cada hito, escribe en `PROGRESS.md` qué se hizo, qué se dejó fuera y qué decisiones se tomaron.

---

## 1. Qué es ArchMuse

ArchMuse es el **cerebro agéntico de un arquitecto**. No es un chatbot de arquitectura y no compite con Revit ni AutoCAD.

El LLM **interpreta, planifica y razona**. No calcula, no inventa normativa y no genera números. Todo dato numérico o normativo que llegue al usuario debe proceder de una **Tool determinista** y llevar su procedencia adjunta.

**Regla de oro, sin excepciones:**

> Si un número aparece en una respuesta o en un informe sin un registro de procedencia que diga qué tool lo produjo, con qué inputs y con qué versión, es un bug de severidad crítica.

### Por qué alguien paga por esto

Un estudio de arquitectura paga porque le ahorra horas caras y evita errores caros. El valor concreto de la V1 es:

> Detectar que el cuadro de superficies de la memoria no cuadra con los planos **antes** de visar, decir exactamente dónde y por cuánto, y generar el informe.

Todo lo que no sirva a eso es secundario en la V1.

---

## 2. Vocabulario (usa estos términos en el código)

| Término | Definición |
|---|---|
| **Project Model** | Representación canónica del proyecto en memoria/BD. Fuente única de verdad. |
| **Tool** | Función determinista, tipada e idempotente. Mismos inputs → mismos outputs. Sin LLM dentro. |
| **Skill** | Procedimiento de alto nivel que orquesta Tools para resolver una tarea profesional. Puede usar LLM para interpretar, nunca para calcular. |
| **Orchestrator** | Núcleo agéntico: intención → plan → ejecución de tools → verificación → respuesta. |
| **Provenance** | Registro inmutable de cómo se obtuvo un dato. |
| **Finding** | Hallazgo detectado por una comprobación: incoherencia, incumplimiento o aviso. |
| **Evidence** | Referencia concreta a la fuente de un dato (documento, página, elemento IFC, capa DXF). |

---

## 4. Project Model — el cimiento

**Esto es lo primero que se construye y lo que más importa.** Si el Project Model está mal, todo lo demás hereda el error.

Entidades mínimas de V1:

```python
Project          # id, nombre, ubicación, fase, referencia catastral
Parcel           # superficie, linderos, clasificación, parámetros urbanísticos
Building         # id, uso principal, plantas
Level            # nombre, cota, altura libre
Space            # ← LA ENTIDAD CENTRAL
Element          # muros, huecos, forjados (mínimo en V1)
Document         # fichero fuente: pdf, ifc, dxf, docx
SourceRef        # documento + página/hoja/GUID + bbox opcional
AreaFigure       # una cifra de superficie con tipo, valor, unidad y origen
Finding          # hallazgo con severidad, evidencia y sugerencia
```

### Reglas duras del modelo

1. **Identidad estable.** Un `Space` que aparece en el IFC, en el PDF y en la memoria es **un único `Space`** con varias `SourceRef`. La reconciliación es un problema explícito, no un accidente.
2. **Nunca un `float` desnudo.** Toda magnitud es `Quantity(value, unit)`. Las unidades se validan; mezclar m² y m se detecta en tiempo de ejecución.
3. **Superficies tipadas.** `AreaKind` es un enum cerrado: `USEFUL`, `BUILT`, `COMPUTABLE`, `OCCUPIED`, `PLOT`. Prohibido un campo genérico `area`.
4. **Toda `AreaFigure` lleva `provenance_id` obligatorio.** El modelo no permite crear una sin él.
5. **Conflictos, no sobrescrituras.** Si dos fuentes dan valores distintos para el mismo dato, se guardan **ambos** y se genera un `Finding`. Nunca elijas una fuente en silencio.

---

## 5. Contratos de Tools

Toda Tool cumple esta forma:

```python
class ToolResult(BaseModel, Generic[T]):
    value: T
    provenance: Provenance
    confidence: Literal["high", "medium", "low"]
    warnings: list[str] = []

class Provenance(BaseModel):
    tool_name: str
    tool_version: str
    inputs_hash: str
    sources: list[SourceRef]
    computed_at: datetime
    method: str          # descripción legible del método aplicado
```

Requisitos:

- **Determinismo.** Sin `random`, sin `datetime.now()` dentro del cálculo, sin llamadas al LLM.
- **Idempotencia.** Ejecutarla dos veces con los mismos inputs da el mismo `inputs_hash` y el mismo resultado.
- **Fallo explícito.** Si no puede calcular, devuelve un error tipado. **Nunca un valor aproximado sin marcar.**
- **Registro declarativo.** Cada tool se registra en `core/registry.py` con su schema de entrada y salida, para que el orquestador pueda razonar sobre ellas sin conocerlas.

---

## 6. HITOS DE LA V1

### M0 — Esqueleto vertical (objetivo: demoable en 1 día)

**No es la V1.** Es un corte fino que atraviesa toda la arquitectura para validar que las piezas encajan.

Alcance:
- `Project`, `Level`, `Space`, `AreaFigure`, `Provenance`, `SourceRef` en Pydantic.
- Persistencia SQLite mínima (crear proyecto, guardar, cargar).
- **Una** tool real: `ingest_ifc_spaces` — lee un IFC y extrae `IfcSpace` con nombre, planta y superficie.
- **Una** tool real: `compute_useful_area_by_level` — agrega superficie útil por planta.
- Orquestador mínimo: recibe una frase, elige entre 2 tools, ejecuta, devuelve resultado con procedencia.
- CLI: `archmuse ingest <fichero.ifc>` y `archmuse ask "¿cuánta superficie útil hay por planta?"`

**Criterio de aceptación M0:**
Con un IFC de ejemplo, el comando `archmuse ask` devuelve una tabla de superficie útil por planta donde **cada cifra muestra el GUID del `IfcSpace` del que procede**. Test end-to-end en verde.

**NO CONSTRUIR en M0:** PDF, DXF, normativa, informes, memoria, API HTTP.

---

### M1 — Ingesta multiformato y reconciliación

- `ingest_dxf`: capas, polilíneas cerradas, textos de rotulación de recintos.
- `ingest_pdf_tables`: extracción de tablas de cuadros de superficies.
- `ingest_docx`: memoria descriptiva, extracción de cifras declaradas.
- **Motor de reconciliación**: casar entidades entre fuentes por nombre normalizado, planta y proximidad de superficie. Debe producir un informe explícito de qué casó, qué no, y con qué confianza.

**Criterio de aceptación M1:**
Dado un proyecto con IFC + PDF del cuadro de superficies + memoria en Word, el sistema produce una lista única de `Space` con las tres fuentes vinculadas y un listado de los no reconciliados.

**Nota crítica:** la reconciliación *nunca* se resuelve adivinando. Lo que no case queda marcado como no reconciliado y se le presenta al usuario. Un falso emparejamiento es peor que un hueco.

---

### M2 — Motor de superficies y coherencia (el corazón económico)

Tools:
- `compute_areas`: útil, construida, computable, ocupación, edificabilidad. Reglas de cómputo **parametrizables por ordenanza**, en ficheros de configuración, no hardcodeadas.
- `check_area_coherence`: compara superficies entre todas las fuentes, con tolerancia configurable.
- `check_level_consistency`: suma de recintos vs. superficie de planta declarada.
- `check_document_consistency`: cifras de la memoria vs. cifras calculadas.

Cada comprobación devuelve `Finding` con: severidad (`error` / `warning` / `info`), delta cuantificado, evidencia en ambas fuentes y sugerencia de resolución.

**Criterio de aceptación M2:**
Se introduce deliberadamente una discrepancia de superficie en un proyecto de prueba y el sistema la detecta, la localiza en la planta y el recinto correctos, y cuantifica la diferencia con el signo correcto.

---

### M3 — Normativa con cita obligatoria

- Corpus estructurado en `corpus/`. Empieza **pequeño y bien**: DB-SUA 1 y DB-SI 3 completos, en JSON estructurado por artículo, con texto literal y metadatos (documento, sección, artículo, versión, fecha de vigencia).
- `query_regulation`: recuperación sobre el corpus. **Devuelve siempre texto literal + referencia de artículo, o devuelve nada.**
- Skill `regulation_query`: el LLM interpreta la pregunta y redacta la explicación, pero **el texto normativo citado sale íntegro de la tool**, nunca del modelo.
- Carga de ordenanza municipal por el usuario, como PDF, con extracción asistida y **validación humana obligatoria** de los parámetros extraídos antes de usarlos.

**Criterio de aceptación M3:**
Ante una pregunta normativa, la respuesta incluye la cita literal con su referencia. Ante una pregunta fuera del corpus cargado, el sistema dice explícitamente que no dispone de esa normativa. **Nunca improvisa.**

**Prohibición absoluta:** el LLM no parafrasea normativa como si fuera texto normativo, no infiere artículos que no ha recuperado, y no responde "según el CTE..." sin una cita recuperada.

---

### M4 — Informes y Skills

- `generate_report`: informe docx/xlsx con hallazgos, cuadro de superficies, y **anexo de procedencia** de cada cifra.
- Skill `area_audit`: auditoría de superficies de principio a fin.
- Skill `project_review`: revisión de coherencia de todo el proyecto.
- Memoria de proyecto: hechos estructurados persistentes, separados de las preferencias de conversación.

**Criterio de aceptación M4 (y de la V1):**
Un arquitecto sube IFC + PDF + memoria, escribe *"revisa la coherencia de este proyecto"*, y en menos de 5 minutos recibe un informe Word con los hallazgos ordenados por severidad, cada uno con su evidencia y la trazabilidad completa de cada cifra.

---

## 7. Núcleo agéntico — cómo debe comportarse

El orquestador ejecuta este ciclo:

1. **Interpretar** la intención del usuario.
2. **Planificar**: producir un plan explícito de llamadas a tools. El plan es un objeto, no texto libre.
3. **Mostrar el plan** al usuario si implica más de 3 tools o cualquier escritura.
4. **Ejecutar** las tools por el registro.
5. **Verificar**: comprobar unidades, rangos plausibles, y que cada resultado tenga procedencia.
6. **Responder** citando la procedencia.
7. **Registrar** en la traza del proyecto.

Comportamientos obligatorios:

- **Si no puede comprobar algo, lo dice.** La cobertura declarada es una función del producto: al final de toda revisión, el sistema enumera qué comprobó y **qué no comprobó**.
- **Nunca afirma cumplimiento normativo global.** Como mucho: "esta comprobación concreta pasa/no pasa".
- **Nada que produzca un documento con valor profesional se cierra sin confirmación humana.**
- Ante datos contradictorios, expone el conflicto. No lo resuelve por su cuenta.

---

## 8. NO CONSTRUIR EN V1

Esta lista es vinculante. Si algo de aquí aparece en el código, es un error de alcance.

- Escritura en Revit o en cualquier BIM.
- Generación o modificación de geometría.
- Cálculo estructural, de instalaciones o certificación energética.
- Mediciones y presupuesto.
- **Generación de alternativas: permitida** cuando la geometría se deriva de
  parámetros comprobables — envolvente y volumen edificable a partir de
  retranqueos, ocupación, edificabilidad y alturas. Cada alternativa lleva la
  procedencia de los parámetros que la producen.
- **Sigue fuera: la distribución interior libre.** Repartir estancias dentro de
  una planta según criterio propio no se deriva de nada comprobable.
- Renders, presentaciones o material gráfico.
- Integración de correo electrónico.
- Búsqueda de referencias arquitectónicas.
- Colaboración multiusuario, permisos, roles.
- **Frontend web: permitido.** La vista de tres zonas y la SPA se mantienen.
- **Creación automática de Skills por el propio agente.** Ver §11.
- Verificación normativa "completa" o automática de todo el proyecto.

---

## 9. V2 — contexto, no implementar todavía

Sirve para que las decisiones de la V1 no cierren puertas. **No escribas código de V2.**

1. Plugin Revit de lectura rica (parámetros, tablas, vistas).
2. Escritura BIM acotada y reversible: parámetros, tablas de planificación, anotaciones, cotas. **Nunca geometría libre.** Toda escritura con vista previa, aprobación y deshacer.
3. Normativa versionada por vigencia temporal: qué norma aplicaba en la fecha del proyecto.
4. Mediciones y presupuesto con salida BC3/FIEBDC.
5. Diff entre versiones de proyecto: qué cambió y qué se rompió al cambiar.
6. Memoria de estudio: criterios propios, plantillas, decisiones recurrentes.
7. SDK de Skills con tests obligatorios para terceros.

**Consecuencias para el diseño de la V1:** el Project Model debe soportar versiones desde el principio (aunque la V1 solo use una), y toda tool debe declarar si es de lectura o escritura aunque en V1 todas sean de lectura.

---

## 10. V3 — contexto, no implementar todavía

1. Coordinación del ciclo de proyecto con checkpoints humanos en cada transición de fase.
2. BIM bidireccional con resolución de conflictos.
3. Aprendizaje del criterio del estudio.
4. Creación controlada de Skills: sandbox + suite de evaluaciones + revisión y firma humana antes de activar.
5. Planificación y coste integrados con el modelo.

**El momento wow de V3:** el arquitecto dice *"sube una planta y cambia el uso de la planta baja a comercial"* y ArchMuse devuelve el mapa completo de consecuencias, separando lo que puede resolver solo de lo que necesita decisión humana.

---

## 11. Sobre la auto-creación de Skills

La visión del producto contempla que ArchMuse detecte carencias y desarrolle nuevas Skills. Esto se implementa **en su versión segura y solo en esa**:

- **V1 y V2:** ArchMuse puede **detectar la carencia y redactar una especificación de Skill** — qué haría, qué tools necesitaría, qué tests la validarían. Un humano la implementa. El agente **no genera ni ejecuta código propio**.
- **V3:** generación de Skill en sandbox, con suite de evaluaciones obligatoria y firma humana antes de activarse en producción.

Razón: de este sistema dependen documentos que un técnico firma bajo su responsabilidad civil. El riesgo de código autogenerado sin revisión no compensa el atractivo de la función.

---

## 12. Definition of Done — por hito

Un hito no está terminado hasta que:

- [ ] `mypy --strict` pasa en `core/` y `tools/`.
- [ ] `pytest` en verde, cobertura ≥80% en `tools/`.
- [ ] Existe un test end-to-end que demuestra el criterio de aceptación del hito.
- [ ] Toda tool nueva está registrada con su schema en `core/registry.py`.
- [ ] Ninguna cifra del output carece de procedencia — hay un test que lo verifica automáticamente.
- [ ] `PROGRESS.md` actualizado con decisiones y descartes.
- [ ] No se ha implementado nada de la lista §8.

---

## 13. Test que nunca puede fallar

Escribe este test en M0 y mantenlo vivo en todos los hitos:

```python
def test_no_orphan_numbers():
    """Ninguna magnitud del resultado puede existir sin procedencia."""
    result = run_full_review(sample_project)
    for figure in walk_all_quantities(result):
        assert figure.provenance_id is not None
        assert store.get_provenance(figure.provenance_id) is not None
```

Si este test se pone en rojo, el producto ha dejado de ser vendible. Es el test más importante del repositorio.

---

