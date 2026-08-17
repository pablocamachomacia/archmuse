# Auditoría de proyecto — ArchMuse

**Fecha de auditoría:** 2026-07-31
**Alcance:** análisis estático completo del repositorio `arquitecto-ai` (backend Python + SPA). No se ha modificado ningún archivo de código.

---

## 1. Resumen ejecutivo

**ArchMuse es un motor de control de calidad normativo y de diseño para viviendas residenciales españolas.** Recibe o genera un plano de vivienda(s) y devuelve un diagnóstico estructurado: qué normativa incumple (CTE, LOE, decretos autonómicos de habitabilidad), qué decisiones de diseño son mediocres aunque sean legales, y qué consecuencias en cadena tiene cada problema (coste, urgencia, impacto en otras disciplinas).

Tiene dos modos de entrada que convergen en el mismo motor de reglas y en la misma interfaz:

1. **Analizar un plano existente** — el arquitecto sube un DXF, la app extrae las habitaciones y evalúa ~40 reglas normativas y de diseño.
2. **Generar un proyecto desde cero** — el arquitecto introduce parámetros de solar, edificio y mix de viviendas; Claude genera la distribución completa y se evalúa igual que un DXF real.

**El problema que resuelve:** hoy ese control de calidad lo hace un arquitecto senior revisando planos a ojo, o no se hace hasta que un visado o una ITE lo detecta tarde y caro. ArchMuse comprime ese chequeo a segundos y lo hace exhaustivo (más de 40 comprobaciones simultáneas, algo que ningún humano repite de forma consistente proyecto tras proyecto).

**Cliente ideal:** estudios de arquitectura pequeños/medianos y arquitectos autónomos en España que producen vivienda plurifamiliar o unifamiliar y necesitan autochequear cumplimiento CTE/LOE antes de visado, más promotoras que quieren auditar la calidad de un proyecto antes de comprarlo o financiarlo.

**Estado real del producto:** es un prototipo **técnicamente muy avanzado y funcionalmente rico**, construido en apenas unos días de desarrollo intensivo (57 commits, primer commit visible "v0.2"). El motor de reglas (`evaluator.py`, ~3.000 líneas) es el activo más valioso del proyecto — es difícil de replicar rápido y es la base de un foso competitivo real. Pero el envoltorio alrededor de ese motor (persistencia, seguridad, despliegue, control de versiones del propio código, pruebas) está a nivel de prototipo de un solo usuario en un portátil, no de producto vendible.

**El hallazgo más urgente no es de producto, es de higiene de proyecto:** cuatro módulos completos y sofisticados (`chain_effects.py`, `circulation.py`, `scoring.py`, `spatial_quality.py` — más de 1.700 líneas de lógica, una parte importante del valor diferencial actual) **nunca se han confirmado en git**. Existen solo en el disco de este ordenador. Ver sección de Riesgos.

---

## 2. Arquitectura

```
Navegador (SPA, static/index.html — 5.313 líneas, JS vanilla, sin build)
        │  fetch JSON
        ▼
Flask (app.py) — API REST pura, 3 endpoints, sin plantillas server-side
        │
        ├── POST /api/analizar   (sube un DXF)
        ├── POST /api/generar    (genera un proyecto desde parámetros)
        └── POST /api/informe-pdf (exporta PDF del análisis ya calculado)
        │
        ▼
analyzer/  (paquete Python, ~7.700 líneas, sin dependencias externas de framework)
        │
        ├── parser.py           DXF → objetos Room (ezdxf + shapely)
        ├── ai_generator.py     parámetros → proyecto completo (llamada a Claude)
        ├── evaluator.py        motor de ~40 reglas CTE/LOE/habitabilidad (núcleo)
        ├── circulation.py      grafo de adyacencia entre habitaciones, recorridos
        ├── spatial_quality.py  heurísticas de calidad de diseño (no normativas)
        ├── chain_effects.py    efectos en cadena / coste-urgencia por problema
        ├── scoring.py          puntuación ponderada por categoría + percentil
        ├── ai_analyst.py       diagnóstico narrativo con Claude sobre el análisis
        ├── api_serializer.py   une todo lo anterior en un único JSON de respuesta
        ├── plan_svg.py         renderizado del plano en SVG con overlays de problemas
        ├── pdf_report.py       exportación a PDF (reportlab)
        └── cte_zonas.py        ciudad → zona climática CTE + densidad urbana
```

Hay además una **segunda vía, independiente y cada vez más obsoleta**: `main.py` + `reporter.py`, un flujo de línea de comandos anterior a la SPA que escribe un `informe.html` junto al DXF. Sigue funcionando pero **no usa** `circulation.py`, `spatial_quality.py`, `chain_effects.py` ni `scoring.py` — solo llama al núcleo de `evaluator.py`. Es decir: hoy existen dos productos con features distintas compartiendo el mismo motor de reglas, y la CLI se ha quedado atrás en cada iteración reciente.

### Tecnologías

| Capa | Tecnología |
|---|---|
| Backend | Python 3, Flask 3.x (servidor de desarrollo, `debug=True`) |
| Parsing CAD | `ezdxf` (lectura DXF) + `shapely` (geometría de polígonos) |
| IA | API de Anthropic (`anthropic` SDK), modelo `claude-sonnet-4-6`, dos usos: diagnóstico narrativo y generación de proyectos |
| PDF | `reportlab` |
| Frontend | JavaScript vanilla en un único HTML de 5.313 líneas, sin framework, sin bundler, sin `package.json` |
| 3D | `three.js` r160, cargado en tiempo de ejecución desde `unpkg.com` vía import map (no está vendorizado ni empaquetado) |
| Persistencia | **Ninguna.** Sin base de datos, sin sesiones, sin usuarios. Cada análisis vive solo en memoria del navegador mientras la pestaña está abierta |

### Dependencias declaradas (`requirements.txt`)

```
ezdxf>=1.3.0
shapely>=2.0.0
anthropic>=0.40.0
flask>=3.0.0
reportlab>=5.0.0
```

Las cinco son de bajo riesgo de licencia y ampliamente usadas. El problema no es *cuáles* son, sino *cómo* están fijadas: todas usan `>=` sin límite superior, así que una instalación nueva de `pip install -r requirements.txt` dentro de seis meses puede traer versiones que rompan algo (especialmente el SDK de `anthropic`, que cambia con frecuencia) sin ningún archivo de lock que reproduzca el entorno actual.

---

## 3. Flujo del usuario

**Flujo A — Analizar un plano real:**
1. El arquitecto arranca `python app.py` en su máquina y abre `http://127.0.0.1:5000`.
2. Arrastra un archivo DXF, indica el norte (azimut), tipología (plurifamiliar / unifamiliar / rehabilitación) y ciudad.
3. El backend extrae las habitaciones de la capa `"00 areas"` del DXF, ejecuta las ~40 reglas de `evaluator.py` más los módulos de circulación, calidad espacial y efectos en cadena, y opcionalmente llama a Claude para un diagnóstico narrativo (si no hay `ANTHROPIC_API_KEY`, la app sigue funcionando sin esa sección — degradación correcta).
4. La SPA muestra: semáforo verde/amarillo/rojo por vivienda, panel de problemas filtrable por severidad y disciplina, plano SVG con overlays de problemas, diagramas de recorridos de circulación, desglose de puntuación por categoría, comparación de percentil frente a un benchmark, exportación a CSV y a PDF.

**Flujo B — Generar un proyecto desde cero:**
1. El arquitecto rellena un formulario: superficie y forma del solar, número de plantas, altura libre, mix de viviendas por dormitorios, límites urbanísticos (ocupación, edificabilidad, retranqueos).
2. Claude genera la distribución completa de habitaciones y viviendas ajustándose a esos parámetros.
3. Se evalúa exactamente con el mismo motor que el Flujo A, y además se activa un **visor 3D navegable** del edificio generado (paseo virtual, vistas de cámara, panel de plantas).

Ambos flujos convergen en `api_serializer.serialize_analysis()`, que produce una única forma de JSON consumida por la misma SPA — buena decisión de diseño, evita duplicar la capa de presentación.

---

## 4. Estado de cada módulo

| Módulo | Líneas | Estado | Notas |
|---|---:|---|---|
| `parser.py` | 220 | **Sólido** | Bug real de polígonos contenedores ya corregido y validado contra el DXF de ejemplo. Depende de una convención de capas/colores concreta (`"00 areas"`, ACI 10/150) — no verificado contra DXFs de otras fuentes. |
| `evaluator.py` | 2.966 | **Núcleo maduro, es el activo principal** | ~40 funciones de regla cubriendo CTE DB-SI, DB-SUA, DB-HS, DB-HE, DB-HR, LOE y decretos de habitabilidad. Expone honestamente sus propias limitaciones (`get_missing_data_warnings`: altura libre, escaleras, aislamiento acústico entre viviendas y compartimentación contra incendios **nunca son evaluables** porque el modelo de datos no captura esa información) — esto es una señal de madurez de producto poco común, evita sobreprometer cumplimiento. Tiene al menos una regla conocida como probablemente inerte en datos reales (ver Problemas). |
| `circulation.py` | 517 | **Funcional, sin confirmar en git** | Grafo de adyacencia entre habitaciones; 3 de sus 5 comprobaciones no se han visto disparar sobre el único DXF real disponible (`ejemplo.dxf`), solo se validaron con datos sintéticos. |
| `spatial_quality.py` | 517 | **Funcional, sin confirmar en git** | Heurísticas de diseño explícitamente no normativas (proporción, luz natural, escala humana, espacios muertos). Correctamente separado del motor CTE para no mezclar "ilegal" con "de mal gusto". |
| `chain_effects.py` | 344 | **Funcional, sin confirmar en git** | Capa de interpretación de negocio genuinamente diferenciadora: traduce un hallazgo técnico en coste estimado y urgencia. Es la pieza más "vendible" del producto y la menos probada. |
| `scoring.py` | 194 | **Funcional, sin confirmar en git** | Puntuación ponderada por categoría y percentil comparativo. **La tabla de benchmarks (`TIPOLOGIA_BENCHMARKS`) está inventada**, no proviene de datos reales de otros proyectos — el propio código lo documenta, pero de cara al usuario se presenta como un percentil objetivo. |
| `ai_analyst.py` | 192 | **Sólido** | Manejo de errores defensivo y completo (sin API key, SDK no instalado, error de red, respuesta no-JSON, rechazo por filtros de seguridad) — nunca rompe el análisis principal. |
| `ai_generator.py` | 518 | **Funcional** | Pieza más ambiciosa del producto (diseño generativo completo). Depende por completo de la calidad y consistencia geométrica de lo que devuelva el modelo — sin validación de que el layout generado sea físicamente coherente antes de evaluarlo. |
| `api_serializer.py` | 315 | **Sólido** | Buen punto único de unión de todos los módulos de análisis. |
| `plan_svg.py` | 624 | **Funcional** | Reutilizado correctamente por tres consumidores distintos (plano base, overlays de calidad espacial, diagramas de circulación). |
| `pdf_report.py` | 248 | **Funcional** | No verificado si se mantiene sincronizado con cada campo nuevo del JSON (p. ej. desglose de puntuación, efectos en cadena) a medida que se añaden. |
| `cte_zonas.py` | 108 | **Cobertura parcial, sin aviso al usuario** | Solo ~30 ciudades españolas mapeadas a zona climática. Cualquier otra ciudad recibe silenciosamente la zona por defecto ("C") sin que el usuario sepa que el dato es una suposición, no la zona real de su municipio. |
| `reporter.py` + `main.py` (CLI) | 589 | **Obsoleto / en desuso progresivo** | Segundo frontend que ya no recibe las funcionalidades nuevas. Mantiene una ruta de DXF hardcodeada al escritorio personal de Pablo como valor por defecto — es una herramienta de desarrollo, no algo que pueda entregarse a un cliente. |
| `static/index.html` (SPA) | 5.313 | **Funcional pero insostenible como archivo único** | JS vanilla, sin framework, sin build, sin tests. Incluye un visor 3D con three.js cargado desde una CDN externa en tiempo de ejecución (sin conexión a internet, esa parte del producto deja de funcionar). |

---

## 5. Problemas encontrados

### Críticos (riesgo de pérdida de trabajo o de confianza del cliente)

1. **Cuatro módulos activos no están versionados en git.** `chain_effects.py`, `circulation.py`, `scoring.py` y `spatial_quality.py` — más de 1.700 líneas, buena parte de lo que hoy diferencia a ArchMuse de un simple checklist CTE — aparecen como "Untracked" en `git status`. Si el portátil falla, se borra el directorio por error, o se necesita volver a un commit anterior, ese trabajo desaparece sin posibilidad de recuperación. Además hay 5 archivos más con cambios sin confirmar (`api_serializer.py`, `evaluator.py`, `plan_svg.py`, `app.py`, `static/index.html`). En la práctica, el estado real y funcionando del producto **no coincide con ningún commit existente**.

2. **La tabla de percentiles/benchmarks (`scoring.py`) es inventada, no datos reales**, y se presenta al usuario como una comparación objetiva contra "otros proyectos de su tipología". Esto es aceptable como placeholder de desarrollo, pero venderlo así a un cliente de pago sin dejarlo clarísimo en la interfaz es un riesgo reputacional/legal si un arquitecto toma una decisión basándose en un percentil ficticio.

### Importantes

3. **Servidor Flask en modo `debug=True` (`app.py:310`)** — expone el depurador interactivo de Werkzeug, que permite ejecución remota de código si el puerto queda accesible desde fuera de `localhost`. Aceptable para desarrollo local, inaceptable si esto se despliega tal cual.

4. **Sin autenticación, sin usuarios, sin persistencia.** Cualquiera con acceso a la URL puede subir un DXF o generar un proyecto y gastar cuota de la API de Anthropic. No hay forma de guardar un análisis, compararlo con uno anterior, ni de tener varios arquitectos usando la misma instancia con datos separados.

5. **Regla de adyacencia acústica probablemente nunca se dispara en datos reales** (`evaluator._is_adjacent`, Bloque 16) — usa intersección literal de polígonos, pero en los DXF reales de Pablo las habitaciones dejan un hueco de hasta 0,38 m (grosor de muro) entre sí, así que la comprobación nunca encuentra adyacencia. `circulation.py` ya resolvió el mismo problema con una distancia de tolerancia, pero esa corrección deliberadamente no se aplicó de vuelta a `evaluator.py`. Resultado: un aviso normativo (ruido dormitorio-baño) que probablemente lleva semanas sin aparecer nunca en un análisis real, sin que se note porque no hay tests que lo detecten.

6. **Sin pruebas automatizadas de ningún tipo.** Cero archivos de test en todo el repositorio. Con un motor de ~40 reglas normativas donde un cambio de umbral en un bloque puede alterar silenciosamente el resultado de otro (como ya ocurrió deliberadamente entre los Bloques 15 y 19 sobre huecos de ventana), la ausencia de tests de regresión es el mayor riesgo para poder iterar rápido sin romper cumplimiento normativo ya validado.

7. **Cobertura geográfica silenciosamente incompleta** (`cte_zonas.py`): solo ~30 municipios tienen zona climática real; cualquier otro recibe la zona "C" por defecto sin aviso visible al usuario de que el dato es una suposición.

8. **Dependencias sin fijar** (`requirements.txt` solo con límites inferiores `>=`) — no hay forma de reproducir exactamente el entorno que funciona hoy dentro de unos meses.

9. **`three.js` se carga desde una CDN externa en tiempo de ejecución**, no está empaquetado con la app — sin conexión a internet (o si unpkg cae), el visor 3D deja de funcionar por completo.

### Menores / cosméticos

10. Sin `README.md`: nadie que no sea Pablo puede arrancar el proyecto sin adivinar `python app.py`, la variable `ANTHROPIC_API_KEY` o la convención de capas del DXF.
11. Sin licencia declarada, sin `.env.example`.
12. La CLI (`main.py`) tiene una ruta de DXF hardcodeada al escritorio personal como valor por defecto — inofensivo hoy, pero es una pista de que ese camino de código ya es solo una herramienta interna de depuración, no parte del producto.

---

## 6. Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Pérdida de los 4 módulos no versionados por fallo de disco/borrado accidental | Media | **Muy alto** — semanas de trabajo diferencial | `git add` + commit inmediato, hoy, antes de tocar nada más |
| Un arquitecto confía en el percentil comparativo inventado para tomar una decisión de negocio | Baja-media (si se vende tal cual) | Alto (reputacional/legal) | Etiquetar visiblemente en la UI como "estimación orientativa, no datos de mercado" o retirarlo hasta tener datos reales |
| Ejecución remota de código vía el depurador de Flask si se expone la instancia fuera de `localhost` | Baja mientras sea solo local | Crítico si se despliega así | `debug=False` + servidor WSGI de producción antes de cualquier despliegue |
| Regresión silenciosa de una regla normativa al tocar el evaluador (sin tests) | Alta a medida que crece el motor | Alto — un falso "verde" en un chequeo CTE es peor que no tener la herramienta | Suite de tests de regresión sobre `ejemplo.dxf` y casos sintéticos, empezando por los bloques ya identificados como frágiles |
| El regulador de adyacencia acústica lleva tiempo sin disparar en producción sin que nadie lo note | Ya está ocurriendo | Medio (falsa sensación de cumplimiento en un chequeo concreto) | Portar la tolerancia de distancia de `circulation.py` a `evaluator._is_adjacent` |
| Dependencia total y sin fallback de la API de Anthropic para las dos funciones más "IA" del producto (diagnóstico narrativo y generación de proyectos) | Media | Medio-alto si hay caída de servicio o cambios de precio | Ya hay degradación correcta para el diagnóstico narrativo; falta para la generación de proyectos, que sí es bloqueante |

---

## 7. Prioridad de mejoras

**Ahora (esta semana, antes de tocar nada más):**
1. Confirmar en git los 4 módulos sin versionar y los 5 archivos modificados. Es una acción de 5 minutos que elimina el riesgo más grave del proyecto.
2. Etiquetar en la interfaz que el percentil/benchmark de `scoring.py` es una estimación orientativa, no un dato de mercado real.

**Antes de cualquier despliegue fuera del portátil de Pablo:**
3. `debug=False` + servidor de producción (gunicorn/waitress) en vez del servidor de desarrollo de Flask.
4. Fijar versiones exactas de dependencias (lockfile) y vendorizar o servir `three.js` localmente en vez de depender de una CDN en tiempo real.
5. Añadir autenticación mínima y, aunque sea ligera, persistencia de análisis (aunque solo sea guardar el JSON del último análisis por usuario) — sin esto no hay negocio SaaS posible, solo una demo.

**Antes de vender a un segundo cliente (no solo Pablo):**
6. Suite de tests de regresión sobre el motor de reglas — es la garantía de que "verde" siga significando lo mismo dentro de seis meses.
7. Corregir la regla de adyacencia acústica inerte.
8. Ampliar o generalizar la tabla de zonas climáticas CTE (o avisar visiblemente cuando se use el valor por defecto).
9. Decidir explícitamente el futuro de la CLI (`main.py`/`reporter.py`): o se retira, o se sincroniza con los módulos nuevos — hoy es deuda muerta que confunde sobre cuál es "el producto".

**A medio plazo (crecimiento):**
10. Migrar la SPA de un único HTML de 5.300 líneas a algo modular con build step — no es urgente mientras solo la mantenga una persona, pero se vuelve insostenible en cuanto entre un segundo desarrollador.
11. README y documentación de arranque para poder incorporar colaboradores o pasar el proyecto a un equipo técnico.

---

## 8. Ideas de alto impacto

- **`chain_effects.py` es, con diferencia, la pieza con más potencial comercial del producto.** Ningún competidor de "checker CTE" que conozca traduce un hallazgo normativo en coste estimado y urgencia de intervención. Eso es lo que convierte una herramienta de cumplimiento en una herramienta de toma de decisiones para un promotor, no solo para el técnico que redacta el proyecto. Vale la pena invertir en robustecerlo, con tests, antes que en añadir más reglas normativas.

- **El motor de ~40 reglas normativas (`evaluator.py`) es un foso real.** Reproducir esa cobertura (CTE DB-SI/SUA/HS/HE/HR + LOE + decretos autonómicos, con umbrales que varían por tipología y zona climática) costaría a un competidor meses, no días. Es el activo a proteger y a seguir ampliando con disciplina (con tests, para no degradarlo sin darse cuenta).

- **La honestidad sobre limitaciones (`get_missing_data_warnings`) es un diferencial de confianza, no solo un detalle técnico.** Pocas herramientas de "compliance automático" admiten explícitamente qué no pueden verificar. Convertir eso en un mensaje de marketing explícito ("te decimos lo que SÍ hemos comprobado y lo que NO, para que tú decidas") puede ser más persuasivo ante arquitectos escépticos de la IA que prometer cumplimiento total.

- **El flujo de generación de proyectos con visor 3D (Flujo B) es el gancho de demo más fuerte**, pero hoy depende enteramente de que Claude devuelva una geometría coherente sin validación previa. Añadir una capa de sanity-check geométrico antes de mostrar el resultado (o antes de evaluarlo) evitaría que una demo en vivo falle de forma vistosa delante de un cliente.

- **Convertir el índice de puntuación (`scoring.py`) en un dato real**, en cuanto haya un puñado de proyectos reales analizados por distintos estudios, sustituyendo la tabla inventada por percentiles agregados de uso real — eso sí sería un diferencial defendible ("comparado con 200 proyectos analizados en la plataforma") en vez de un número orientativo.

---

## Resumen para el fundador

ArchMuse no es una idea en fase de validación: **es un motor de reglas normativas y de diseño ya construido y funcionando**, con una cobertura de cumplimiento CTE que costaría meses replicar a un competidor, más una capa de generación de proyectos con IA que va más allá de lo que hace un checker típico. El activo tiene valor real hoy.

Lo que falta no es más funcionalidad — hoy hay más funcionalidad de la que está protegida. Los tres pasos que importan de verdad esta semana son: (1) guardar en git el trabajo que hoy solo existe en el disco de un portátil, porque una parte significativa del diferencial del producto no está respaldada en ningún sitio; (2) dejar de mostrar como dato real un número que hoy está inventado (el percentil comparativo); y (3) decidir, antes de enseñar esto a un segundo cliente, si el camino hacia "vendible" pasa por añadir autenticación y persistencia mínima, porque sin eso lo que existe es una demo potente, no un SaaS.
