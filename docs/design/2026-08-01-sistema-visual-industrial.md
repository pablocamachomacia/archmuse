# Sistema visual "software industrial" — reconciliación y especificación

**Estado:** Propuesta · **Fecha:** 2026-08-01 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

Quinto documento de la serie. Tu petición es una especificación cerrada y muy concreta (paleta exacta, tipografía, iconografía, fondo, animaciones) — no la reabro punto por punto. Lo que hace este documento es lo que un CTO debe hacer antes de tocar código: **decirte dónde esta petición choca con lo que ya está sobre la mesa sin decidir**, y fijar el resto como especificación cerrada.

No repito nada de `2026-08-01-rediseno-total-propuesta.md` que siga vigente.

---

## 1. Tres conflictos reales con lo ya escrito

### 1.1 El acento azul revierte tu propia decisión de §3.3, no la completa

`rediseno-total-propuesta.md` §3.3 te ofrecía tres salidas para "solo grises", y mi recomendación (opción 1) era: **colapsar `--accent*` al gris de selección**, sin color de marca en botones. Esa decisión sigue "pendiente de revisión" — nunca la confirmaste.

Esta petición no elige ninguna de las tres opciones que planteé: introduce una **cuarta**, no ofrecida antes — un azul real (`#2E86DE`) para botones principales, estados activos, foco y enlaces, reservando rojo/verde solo para error/éxito. Es una opción legítima (es literalmente como resuelven esto VS Code y Figma) pero es la contraria a lo que yo había recomendado, así que la trato como tu respuesta definitiva a §3.3, versión ampliada:

- `#2E86DE` sustituye a `--accent` / `--accent-hover` / `--accent-soft` / `--accent-border` (hoy neutros, `#1a1a1a`) en toda la Shell: botones primarios, item activo del árbol y del menú, borde de foco, enlaces.
- **No dices qué pasa con `--color-warning` (ámbar, severidad IMPORTANTE).** Tu regla dice "nunca más colores salvo error o éxito" — leído literalmente, el ámbar de advertencia sobra. Pero eliminarlo colapsaría dos severidades distintas (CRITICO y IMPORTANTE) en el mismo rojo, perdiendo la distinción que hoy existe en `--color-critical` / `--color-important` y en el semáforo de vivienda (verde/amarillo/rojo). **Recomiendo conservar el ámbar como tercer estado semántico** (no es "un color más" en el sentido decorativo que prohíbes, es el mismo tipo de excepción que ya concedes a error/éxito) — confírmalo o dime que lo colapse a rojo.
- El modo **Espacio** del plano (color por uso de habitación: salón/dormitorio/baño/terraza/tendedero) sigue sin ser ni acento ni estado — es contenido, no interfaz. Se mantiene la resolución que ya te propuse en §3.3-opción 1: grises + tu único acento en toda la Shell; el color por uso sobrevive **solo dentro del modo Espacio**, en el plano. Si no dices lo contrario, implemento con esta lectura.

### 1.2 Retirar el tema es más que una paleta — es borrar una función

Hoy `static/index.html` tiene un sistema de dos temas completo (claro por defecto, oscuro opcional), con toggle en el menú Ventana, persistencia en `localStorage("archmuse-theme")` y un script anti-parpadeo en el `<head>` que lee esa clave antes del primer render. Tu petición no es "cambia la paleta oscura" — es **eliminar el tema claro entero y la función de cambiarlo**. Lo trato como tal: no es un ajuste de tokens, es una eliminación de código (ver Paso 3 más abajo), y evita que quien retoque esto en el futuro reintroduzca "modo claro" como si fuera solo una preferencia estética a añadir de nuevo.

### 1.3 El fondo geométrico técnico no tiene todavía una regla de "dónde sí / dónde no"

Tu petición pide un fondo con geometría CAD al 2-4% de opacidad, pero no dice sobre qué superficie. La regla ya aprobada en `arquitectura-de-producto.md` §4 — **"el plano manda"** — significa que ninguna textura decorativa puede competir con la lectura del plano real de la vivienda. Decisión que tomo y dejo explícita para que la confirmes o la corrijas:

- El fondo geométrico vive en las superficies de chrome vacío: pantalla de Inicio/Analizar detrás del dropzone, fondos de panel sin contenido, pantallas de Configuración/Acerca de.
- **Nunca** detrás del lienzo del plano (ni en Workspace ni en ningún modo de vista), donde el fondo debe seguir siendo el papel neutro (`--plan-room`) que ya define la iteración 3 — superponer una retícula ahí compite visualmente con los propios muros del plano.

---

## 2. Alcance: esto es solo ArchMuse

Nombras `ArchLicencia`, `ArchSurface`, `ArchMemoria`, `ArchPliego`, `ArchPresupuesto` como módulos que deben compartir el sistema. Esos cinco nombres no son módulos de ArchMuse — son los cinco módulos de **ArchSuite**, un producto distinto (`Escritorio/Pablo/Arch/archportal`, FastAPI + Jinja2 + Tailwind CSS, desplegado en Railway), con una base de código y un stack de frontend completamente diferentes a este (Flask + un único archivo HTML/CSS/JS).

Este documento y la implementación que autorice solo cubren **ArchMuse**. Aplicar la misma paleta/tipografía/componentes a ArchSuite es un trabajo real y separado — Tailwind config, plantillas Jinja2, otro repositorio — no una consecuencia automática de esto. Si quieres un sistema visual único entre los dos productos, dímelo explícitamente y lo trato como una segunda pieza de trabajo (posiblemente un PRD propio en el repo de ArchSuite), no como parte de esta tarea.

---

## 3. Especificación cerrada (esto sí queda fijado tal cual lo pides)

### 3.1 Paleta — sustituye íntegramente al bloque `[data-theme="dark"]` actual; el bloque `:root` claro se elimina

| Token | Valor |
|---|---|
| `--bg-primary` (fondo principal) | `#2B2B2B` |
| `--bg-secondary` (paneles) | `#333333` |
| `--bg-sidebar` (sidebar) | `#252525` |
| `--bg-toolbar` (barra superior) | `#2E2E2E` |
| `--border` (separadores) | `#444444` |
| `--overlay-hover` (hover) | `#3B3B3B` |
| `--overlay-active` (activo) | `#505050` |
| `--text-primary` | `#F2F2F2` |
| `--text-secondary` | `#B5B5B5` |
| `--text-tertiary` (deshabilitado) | `#808080` |
| `--accent` / `--accent-hover` | `#2E86DE` (foco, botón primario, activo, enlaces — nunca decorativo) |
| `--color-critical` | se mantiene (`#dc2626` o el rojo que ya define el semáforo) |
| `--color-important` (ámbar) | pendiente de tu confirmación, ver §1.1 |
| `--color-success` | se mantiene (verde del semáforo) |

Los tokens heredados que hoy alían nombres antiguos a los nuevos (`--bg`, `--panel-bg`, `--raised`, `--text`) se conservan como alias — evita tocar ~200 reglas que ya los consumen, mismo criterio que ya se aplicó en la iteración de Shell.

### 3.2 Tipografía

Solo Inter. Se retira la carga de `DM Sans` (`static/index.html` línea 23 — hoy se importa y no se usa en ningún selector, confirmado por grep). Pesos permitidos: 500, 600, 700 — se retira `400` y `800` de la URL de Google Fonts y de cualquier regla que los use explícitamente.

### 3.3 Iconografía — Lucide, vendorizado, no por CDN

Hoy no hay ninguna librería de iconos: todo son SVG inline escritos a mano (7 decorativos ya marcados para eliminar en `rediseno-total-propuesta.md` §5.1, más los funcionales del plano — brújula, escala — y de la Shell). Migrar a Lucide implica:

- Inventariar cada SVG inline funcional que sobrevive a la poda de §5.1 y mapearlo a su equivalente Lucide.
- Vendorizar los `.svg` de Lucide necesarios localmente (mismo criterio que la tarea 20 de `REFACTOR_MASTERPLAN.md` sobre `three.js`: nada de dependencia de CDN en tiempo de ejecución para una pieza visual central de la app) — no cargar `lucide.js` completo desde un CDN.
- Mismo grosor de trazo y tamaño en todos los usos (24px viewBox, `stroke-width` uniforme).

### 3.4 Botones, tablas, formularios, tarjetas, animaciones

Tal como los describes: radio 6px, alturas bajas, hover sutil (`--overlay-hover`), foco azul (`--accent`), separadores finos en tablas con cabecera fija, tarjetas planas separadas por espacio y no por sombra, transiciones ≤150ms sin rebote. Esto no choca con nada ya aprobado — la escala de espaciado de 4px y el radio de 6-8px ya existen en los tokens actuales (`--space-*`, `--radius-md: 6px`), así que es aplicar lo que ya está definido, no inventar una escala nueva.

---

## 4. Riesgos y por qué no lo empezaría hoy mismo tal cual

Siendo honesto, no solo ejecutor:

1. **Hay trabajo sin commitear desde el 2026-07-31** (`chain_effects.py`, `circulation.py`, `scoring.py`, `spatial_quality.py` y cambios pendientes en `api_serializer.py`, `evaluator.py`, `plan_svg.py`, `app.py`, `static/index.html` — confirmado de nuevo hoy con `git status`, sigue sin resolverse). Es la tarea #1, ROI más alto, de `REFACTOR_MASTERPLAN.md`. Empezar un rediseño visual grande sobre un árbol de trabajo ya sucio multiplica el riesgo de perder algo si algo sale mal a mitad de camino.
2. **Ya hay una propuesta de rediseño sin cerrar, de hoy mismo**, con tres preguntas abiertas (`rediseno-total-propuesta.md` §3.1 nombres de menú, §3.2 ramas del árbol, §5 lista de eliminación). Retematizar ahora y aplicar la poda de §5 después significa tocar las mismas clases CSS dos veces. El orden correcto es podar primero, retemar después (ver plan, Paso 2 antes que Paso 4).
3. **`MOAT_ANALYSIS.md` es explícito**: "Un panel visual con colores de severidad y una lista de problemas — maquetación, no ingeniería de dominio" no es foso defendible. Eso no significa que no importe — el propio documento nombra la "confianza institucional" como lo que de verdad retiene al arquitecto, y una interfaz que no parezca una demo ayuda a esa confianza — pero si el objetivo es "parecer un software de 15.000€/año", una interfaz impecable sobre un motor de reglas con un bug crítico conocido sin corregir (`zona_cte`/tipología, tarea 5 de `REFACTOR_MASTERPLAN.md`) es la combinación exacta que un arquitecto de 20 años de oficio detecta rápido y no perdona.

Ninguno de los tres es motivo para no hacerlo — son motivo para no hacerlo **antes** de lo demás. Alternativa más barata que ya cubre la mayor parte de la percepción de "profesional": Pasos 1-5 del plan (paleta + tipografía + retirar el toggle + retirar la eliminación ya aprobada) sin el fondo geométrico ni la migración completa a Lucide, que son los dos de mayor esfuerzo y menor impacto relativo — se pueden dejar para una segunda entrega.

---

## 5. Plan de implementación (pasos pequeños, orden importa)

1. **Confirmar las respuestas pendientes** — las tres de `rediseno-total-propuesta.md` §6 más las dos nuevas de aquí (ámbar sí/no en §1.1, alcance ArchSuite en §2). Sin esto no empiezo ningún paso siguiente.
2. **Commitear el trabajo pendiente** (tarea 1 de `REFACTOR_MASTERPLAN.md`) antes de tocar una sola línea de CSS.
3. **Aplicar la poda ya aprobada** en `rediseno-total-propuesta.md` §5 (marcado + CSS) — antes de retematizar, para no perder tiempo retematizando clases que van a desaparecer.
4. **Retirar el tema claro y el toggle**: borrar el bloque `:root` claro y el script anti-parpadeo del `<head>`, dejar un único juego de tokens (el de §3.1 de este documento), quitar la entrada del menú Ventana y la lectura de `localStorage("archmuse-theme")`.
5. **Sustituir los valores de los tokens** por la paleta fija de §3.1.
6. **Tipografía**: quitar `DM Sans` de la hoja de Google Fonts, dejar solo los pesos 500/600/700 de Inter.
7. **Fondo geométrico técnico**: crear el asset (SVG o CSS puro, opacidad 2-4%) y aplicarlo únicamente en las superficies acordadas en §1.3 — nunca detrás del plano.
8. **Migrar iconografía a Lucide** vendorizado localmente, según el inventario de §3.3.
9. **Componentes**: aplicar radio/altura/hover/foco/animación de §3.4 a botones, inputs, tabs, tablas, modales, toasts ya existentes — sin crear componentes nuevos que hoy no existan en la app.
10. **Verificación visual manual** de cada pantalla (Inicio, Workspace en sus 6 modos, Generar proyecto, Configuración, modales/toasts) contra la lista de eliminación de `rediseno-total-propuesta.md` §5 y contra este documento.
11. **Fuera de este documento**: si confirmas alcance ArchSuite en §2, un documento de diseño equivalente en el repo de ArchSuite — no antes de que esto esté cerrado en ArchMuse.

## 6. Criterios de aceptación

- Cero referencias a tema claro/oscuro en el DOM, CSS o JS de `static/index.html` — ni toggle, ni `localStorage`, ni bloque `:root` claro.
- Cero valores de color hexadecimales fuera de la tabla de §3.1 en todo `static/index.html` (auditable por grep una vez terminado).
- Cero emojis y cero SVG decorativos que no comuniquen estado o acción.
- Cero fuentes cargadas salvo Inter en los tres pesos indicados.
- El plano (en cualquier modo) nunca se dibuja sobre el fondo geométrico técnico.

## 7. Métricas de éxito

No hay una métrica de producto limpia para "parece profesional" — es percepción, no conversión. La forma honesta de medirlo: enseñar la app resultante al arquitecto real que ya prueba ArchSuite (mismo probador que dio el feedback recogido en memoria del proyecto) y preguntar directamente si la usaría delante de un cliente, sin guiar la respuesta. Eso es una señal real; un recuento de "clases CSS eliminadas" no lo es.

---

**Decisión:** aprobado y aplicado por Pablo el 2026-08-01, con las cuatro respuestas de §6 de este documento resueltas en el propio mensaje de aprobación (acento §1, alcance solo ArchMuse §2, fondo solo en chrome vacío §3, §3.1/§3.2/§5 de `rediseno-total-propuesta.md` sin tocar por ahora). Implementado sobre `static/index.html`, seguido de una auditoría UX/UI completa de consistencia (colores fuera de paleta, radios, sombras, alturas de control, focus rings ausentes, tipografía sin tokenizar, CSS/variables muertas) — ver el commit correspondiente para el detalle.
