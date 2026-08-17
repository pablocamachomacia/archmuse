# Prueba con proyectos reales — 2026-08-12

Protocolo de uso directo, no documentación teórica. Se rellena a mano, sobre
este mismo fichero, durante la sesión de mañana.

---

## 0. PRE-VUELO (antes de abrir el primer DXF)

- [ ] `ANTHROPIC_API_KEY` configurada en el entorno donde corre `app.py`.
      **Importante:** `analyzer/ai_analyst.py` no lanza excepción si falta —
      el "análisis experto IA" se salta en silencio y el resto de la pantalla
      se ve normal. Sin esto, la prueba de mañana no está probando la pieza
      de IA, solo el motor de reglas. Confirmar con una prueba de humo antes
      de empezar (subir un DXF y comprobar que aparece el diagnóstico
      narrativo, no solo los números).
- [ ] `python app.py` arrancado, `http://127.0.0.1:5000` responde.
- [ ] 5–10 DXF reales localizados y accesibles (no `ejemplo.dxf` — ese ya
      está cubierto por el canario y los goldens).
- [ ] Este fichero abierto en un editor para ir rellenando en vivo — no
      confiar en la memoria para reconstruir la sesión después.

---

## 1. OBJETIVO

Determinar si ArchMuse interpreta correctamente planos reales (no el DXF de
ejemplo, ya cubierto por tests) y si una persona sin conocimientos avanzados
de arquitectura puede entender y utilizar el diagnóstico sin ayuda.

Dos preguntas separadas, no una: el motor puede acertar y el producto puede
seguir siendo incomprensible, o al revés. No mezclar los dos juicios en una
sola conclusión — por eso las secciones 3 y 4 van separadas.

---

## 2. MATRIZ DE PRUEBA

Una fila por proyecto. Rellenar mientras se prueba, no después de memoria.

| # | Nombre | Tamaño DXF | Nº viviendas (aprox.) | Tipología | Plantas | Complejidad geométrica | Resultado del análisis | Tiempo de análisis | Errores técnicos |
|---|--------|-----------|------------------------|-----------|---------|--------------------------|--------------------------|----------------------|-------------------|
| 1 |        |           |                        |           |         | baja / media / alta      |                          |                      |                   |
| 2 |        |           |                        |           |         | baja / media / alta      |                          |                      |                   |
| 3 |        |           |                        |           |         | baja / media / alta      |                          |                      |                   |
| 4 |        |           |                        |           |         | baja / media / alta      |                          |                      |                   |
| 5 |        |           |                        |           |         | baja / media / alta      |                          |                      |                   |
| 6 |        |           |                        |           |         | baja / media / alta      |                          |                      |                   |
| 7 |        |           |                        |           |         | baja / media / alta      |                          |                      |                   |
| 8 |        |           |                        |           |         | baja / media / alta      |                          |                      |                   |
| 9 |        |           |                        |           |         | baja / media / alta      |                          |                      |                   |
| 10|        |           |                        |           |         | baja / media / alta      |                          |                      |                   |

"Tiempo de análisis" = desde que se pulsa "Analizar plano" hasta que se
renderiza el resultado (cronómetro real, no estimado).

Para cada proyecto, además de la fila de arriba, rellenar en prosa corta
(2-4 líneas cada uno, en la sección de notas al final del bloque del
proyecto en la sección 5):

- Incidencias detectadas (lista, aunque sea larga — no resumir todavía).
- Incidencias que parecen falsas (falsos positivos sospechados).
- Cosas que ArchMuse no detectó y debería haber detectado (falsos negativos
  sospechados — lo que tú, mirando el plano, ves que está mal y el informe
  no menciona).
- Información que faltó para poder decidir (dato que el informe no da y que
  hacía falta para juzgar si el problema es real o cuánto importa).
- Dificultad de uso para un usuario no arquitecto: baja / media / alta, con
  el motivo concreto (no solo la etiqueta).

---

## 3. VALIDACIÓN DEL MOTOR

**No asumir que un resultado es correcto solo porque el software lo
produjo.** Para cada categoría, contrastar contra el plano real (medir a
ojo o con el propio DXF en un visor CAD si hace falta), no contra lo que
ArchMuse dice de sí mismo.

Códigos: `OK` = coincide con la realidad del plano · `✗` = no coincide ·
`?` = dudoso / no se pudo verificar con la info disponible.

| Categoría | Qué verificar contra el plano real | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | P10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A. Importación/geometría | ¿Se leyeron todas las habitaciones? ¿Alguna duplicada, fusionada o perdida? ¿Los polígonos de agrupación/contenedor se descartaron bien? | | | | | | | | | | |
| B. Identificación de espacios | ¿La etiqueta de cada pieza (Dormitorio, Baño, Salón...) es la correcta? ¿Alguna mal clasificada? | | | | | | | | | | |
| C. Superficies | ¿Los m² de cada pieza y el total útil/construido coinciden con el plano? | | | | | | | | | | |
| D. Ocupación | ¿La ocupación de parcela/edificabilidad calculada tiene sentido para este solar? (Es un proxy geométrico, no dato catastral real — anotar si eso importó aquí) | | | | | | | | | | |
| E. Plantas | ¿El modelo de plantas (número, reparto de viviendas por planta) es el real? | | | | | | | | | | |
| F. Altura de evacuación | ¿La altura de evacuación calculada es plausible para el edificio? | | | | | | | | | | |
| G. Evacuación/circulación | ¿Los recorridos de evacuación y las rutas de circulación detectadas son físicamente los que existen en el plano? | | | | | | | | | | |
| H. Normativa | ¿La zona climática, tipología y umbrales aplicados son los correctos para la ciudad/uso reales de este proyecto? | | | | | | | | | | |
| I. Severidad | ¿El nivel (CRÍTICO/IMPORTANTE/RECOMENDACIÓN) de cada incidencia es proporcional al problema real, o hay algo crítico marcado como menor (o al revés)? | | | | | | | | | | |
| J. Puntuación | ¿La puntuación final refleja el estado real del proyecto? **Nota conocida:** el percentil comparativo de `scoring.py` (`TIPOLOGIA_BENCHMARKS`) es una tabla fabricada, no un dataset real de mercado — no tratarlo como un dato objetivo al juzgar esta fila. Anotar también si el sistema de puntuación "de reglas" y el de "calidad espacial" (`docs/design/2026-08-02-dos-sistemas-de-puntuacion.md`) discrepan de forma llamativa para este proyecto. | | | | | | | | | | |

Para cada `✗` o `?`, añadir una línea en el registro de hallazgos (sección
5) con evidencia concreta (qué pieza, qué número, qué se esperaba).

---

## 4. VALIDACIÓN DEL PRODUCTO

Responder como si fueras un usuario real viendo el resultado por primera
vez, no como quien conoce el motor por dentro. Sí / No / Parcial.

| Pregunta | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | P10 |
|---|---|---|---|---|---|---|---|---|---|---|
| ¿Entiendo inmediatamente qué debo hacer? | | | | | | | | | | |
| ¿Sé qué significa el resultado? | | | | | | | | | | |
| ¿Sé cuál es el problema más importante? | | | | | | | | | | |
| ¿Sé qué debería cambiar en el proyecto? | | | | | | | | | | |
| ¿Entiendo por qué ArchMuse dice que existe ese problema? | | | | | | | | | | |
| ¿Sé qué información es segura y cuál es estimada? | | | | | | | | | | |
| ¿Podría utilizarlo alguien sin conocimientos de arquitectura? | | | | | | | | | | |

Cualquier "No" o "Parcial" va también al registro de hallazgos (sección 5)
como hallazgo de producto/UX, con la frase o pantalla concreta que generó
la confusión — no basta con marcar la casilla.

---

## 5. REGISTRO DE HALLAZGOS

**Regla fundamental: no intentar arreglar cada problema durante la prueba.
Primero recopilar evidencia.** Si algo tienta a "solo un cambio rápido",
anotarlo aquí y seguir con el siguiente proyecto — el arreglo es una sesión
aparte, con su propio PRD si corresponde.

Clasificación de severidad:

- **P0** — bloquea el uso o puede producir una conclusión peligrosamente
  incorrecta (p. ej. un problema real de seguridad que ArchMuse no detecta,
  o un falso "todo correcto").
- **P1** — afecta significativamente a la utilidad (falso positivo/negativo
  claro, dato mal calculado, mensaje que induce a un error de decisión).
- **P2** — mejora de UX/producto (se entiende con esfuerzo, pero cuesta).
- **P3** — detalle menor (cosmético, no cambia ninguna decisión).

| ID | Proyecto (#) | Categoría (A-J motor / UX producto) | Severidad | Descripción breve | Evidencia (captura, m², nombre de pieza...) |
|----|---------------|--------------------------------------|-----------|--------------------|-----------------------------------------------|
| H1 | | | | | |
| H2 | | | | | |
| H3 | | | | | |
| H4 | | | | | |
| H5 | | | | | |
| H6 | | | | | |
| H7 | | | | | |
| H8 | | | | | |
| H9 | | | | | |
| H10 | | | | | |
| H11 | | | | | |
| H12 | | | | | |
| H13 | | | | | |
| H14 | | | | | |
| H15 | | | | | |
| H16 | | | | | |
| H17 | | | | | |
| H18 | | | | | |
| H19 | | | | | |
| H20 | | | | | |

(Añadir más filas si hacen falta — no parar de registrar por quedarse sin
filas.)

### Conclusión por proyecto

Obligatoria para cada proyecto probado, una de estas cuatro, con la
justificación en una frase (qué la sostiene, no una opinión general):

| # | Conclusión (correcto / parcialmente correcto / incorrecto / no evaluable por falta de información) | Justificación (1 frase) |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |
| 8 | | |
| 9 | | |
| 10 | | |

---

## 6. REGLA FUNDAMENTAL (recordatorio)

No se arregla nada hoy. El valor de esta sesión es tener, al final, un
registro de hallazgos completo y honesto (secciones 5 y 7), no un ArchMuse
con parches de última hora sin decidir cuáles merecían la pena. Si aparece
algo que no puede esperar (P0 real, con datos en riesgo), pararlo y decidir
explícitamente romper la regla — no romperla por inercia.

---

## 7. RESUMEN FINAL

Rellenar solo al terminar los 5-10 proyectos, con las secciones 2-5 ya
completas — no antes.

### Tabla comparativa

| # | Proyecto | Conclusión | Nº hallazgos P0 | Nº hallazgos P1 | Nº hallazgos P2 | Nº hallazgos P3 | Usable por no-arquitecto |
|---|----------|------------|-------------------|-------------------|-------------------|-------------------|-----------------------------|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |
| 6 | | | | | | | |
| 7 | | | | | | | |
| 8 | | | | | | | |
| 9 | | | | | | | |
| 10 | | | | | | | |

### Problemas repetidos
(aparecen en 2+ proyectos — candidatos a bug del motor, no ruido de un plano concreto)

-

### Problemas específicos
(un solo proyecto — puede ser peculiaridad de ese DXF, no generalizar sin más evidencia)

-

### Falsos positivos
(ArchMuse marcó un problema que, al revisar el plano, no lo es)

-

### Falsos negativos
(ArchMuse no marcó algo que sí es un problema real)

-

### Partes del motor que funcionan bien
(categorías A-J con más aciertos que fallos across los proyectos probados)

-

### Partes del motor que necesitan trabajo
(categorías A-J con fallos repetidos o graves)

-

### Problemas principales de UX
(de la sección 4 — patrones de "No"/"Parcial" repetidos)

-

### Las 5 mejoras con mayor impacto

Ordenadas por impacto real observado hoy, no por facilidad de implementar.
Cada una debe señalar a hallazgos concretos de la sección 5 (IDs), no ser
una idea nueva sin evidencia detrás.

1.
2.
3.
4.
5.
