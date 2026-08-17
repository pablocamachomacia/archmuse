# Corpus normativo real del CTE — fuente, cobertura y limitaciones (2026-08-06)

Documento de sesión (no un PRD de 14 secciones): Pablo pidió explícitamente
"no más infraestructura, no más motores, no refactorizaciones — quiero
empezar a construir el corpus normativo REAL del CTE", reutilizando el
pipeline ya existente (`ingesta/` Fase 1 + `extraccion/` Fase 2). Mismo
patrón que las dos fases anteriores: se trató la instrucción explícita de
Pablo como autorización para esta corrida concreta, sin volver a preguntar,
mientras el paquete nuevo/las extensiones se acotaban al mínimo necesario y
se documentaban aquí. Ningún cambio toca `evaluator.py`, `normativa/`
(salvo lectura de su vocabulario cerrado, ya autorizada desde la Fase 2), ni
el motor normativo.

**Actualización (misma sesión)**: Pablo aprobó la elección de fuente de
este documento con una condición — nunca depender de una sola fuente. Ver
`docs/design/2026-08-06-auditoria-fuentes-cte.md` §6 para el diseño de
doble fuente (BOE + `codigotecnico.org`) y el registro de proveniencia
verificado por DB, ya implementado.

## 1. Fuente oficial elegida, y por qué no la primera opción

Pablo aprobó inicialmente usar el "código electrónico" del BOE (la
compilación consolidada del CTE). Verificado contra el servicio real, no
de memoria: es **un único PDF de 1316 páginas** que mezcla el CTE con
~100 normas no relacionadas (prevención de riesgos laborales, etc.) — no
hay un documento por DB dentro de esa compilación.

`codigotecnico.org` (el portal oficial del Ministerio de Transportes,
Movilidad y Agenda Urbana para el CTE — no un tercero) sí publica cada
Documento Básico como su propio PDF, con URL estable:

| DB | URL |
|---|---|
| DB-SE | `codigotecnico.org/pdf/Documentos/SE/DBSE.pdf` (+ DBSE-AE, DBSE-C, DBSE-A, DBSE-F, DBSE-M) |
| DB-SI | `codigotecnico.org/pdf/Documentos/SI/DBSI.pdf` |
| DB-SUA | `codigotecnico.org/pdf/Documentos/SUA/DBSUA.pdf` |
| DB-HS | `codigotecnico.org/pdf/Documentos/HS/DBHS.pdf` |
| DB-HE | `codigotecnico.org/pdf/Documentos/HE/DBHE.pdf` |
| DB-HR | `codigotecnico.org/pdf/Documentos/HR/DBHR.pdf` |

Cambio de fuente frente a lo inicialmente aprobado, corregido y documentado
en la propia sesión al descubrir el problema del bundle — ver
`ingesta/fuentes/codigotecnico.py` para el detalle completo.

## 2. Qué se construyó (extensión mínima, no motor nuevo)

- `ingesta/fuentes/codigotecnico.py` — nueva `FuenteOficial` (mismo
  contrato de 2 métodos que ya usa `FuenteBOE`), catálogo cerrado de 11
  documentos, sin sumario diario real (`listar_sumario` ignora `fecha` a
  propósito: esta fuente no es un boletín).
- `ingesta/modelo.py`/`ingesta/almacen.py` — extensión aditiva y
  retrocompatible: `DocumentoOficial` gana `formato`/`bytes_crudos`
  (`None` por defecto, BOE no cambia); `almacen.py` archiva el PDF
  original real, no solo su texto extraído.
- `ingesta/red.py` — `obtener_con_cabeceras()` (además de `obtener()`, sin
  tocar su firma) para leer `Last-Modified` del PDF.
- `extraccion/segmentador_pdf.py` — mismo contrato de salida (`Segmento`)
  que `segmentador.py` (XML/BOE), pero por regex sobre texto plano,
  validado contra el Índice del propio documento (ver §4).
- `extraccion/almacen.py` — **el único módulo de `extraccion/` autorizado
  a escribir ficheros** (extensión explícita del test de frontera por AST).
  Persiste las candidatas de una corrida en `extraccion/estado/candidatas/`
  (versionado en git — a diferencia de la caché de `ingesta/`, esto no es
  barato de reconstruir), nunca escribe en el árbol del corpus definitivo,
  nunca promueve nada.
- `extraccion/pipeline.py` — un único parámetro nuevo, `segmentador`
  (inyectable, por defecto el de XML), para que `extraer()` reutilice
  interpretar→verificar→confianza con un segmentador PDF sin duplicar esa
  orquestación.
- `requirements.txt` — una dependencia nueva: `pypdf` (pura Python,
  licencia permisiva).

## 3. Hallazgo real: el "texto corrupto" no lo estaba

Primera lectura de `pypdf.extract_text()` mostró `�` en vez de acentos.
Verificado con 3 extractores independientes (`pypdf`, `pdfplumber`,
`pymupdf`) con el mismo resultado — parecía un defecto real del PDF
oficial. Al inspeccionar los *code points* reales devueltos (`0xe1`, `0xf3`,
`0xe9`...) resultó ser exactamente Latin-1/Unicode correcto — el problema
era la terminal de la sesión mostrando mal esos bytes, no el texto en sí.
Confirmado escribiendo a fichero UTF-8 y leyendo con la herramienta de
lectura normal: los acentos están todos bien. **No hay limitación de
codificación real** — se documenta aquí para que una sesión futura no
vuelva a investigar el mismo falso positivo.

## 4. Cobertura real de segmentación por DB (verificada, no estimada)

El segmentador PDF usa el propio Índice de cada documento como referencia
(número de apartado esperado + similitud de título por contención, sobre
texto normalizado) — ver el docstring de `extraccion/segmentador_pdf.py`
para el mecanismo completo. Verificado contra los 6 DB reales:

| DB | Páginas Índice detectadas | Apartados esperados (Índice) | Apartados segmentados | Anejos esperados | Anejos segmentados |
|---|---|---|---|---|---|
| DB-SI | 2 | 25 | **25** | 7 | 6 (falta C, ver §5) |
| DB-SUA | 2 | 22 | 20 | 0 | 0 |
| DB-HS | 4 | 36 | 27 | 0 | 0 |
| DB-HE | 1 | 0 (*) | 0 | 0 | 0 |
| DB-HR | 0 (*) | 0 | 0 | 0 | 0 |
| DB-SE | 0 (*) | 0 | 0 | 0 | 0 |

(*) Ver §5 — no es que estos documentos no tengan Secciones/apartados
reales, es que usan una plantilla de maquetación distinta que el detector
de página-Índice y/o de encabezado de Sección actual no reconoce todavía.

## 5. Limitaciones encontradas, explícitas

1. **DB-HE, DB-HR, DB-SE: 0 segmentos en esta pasada.** DB-HR/DB-SE
   numeran sus páginas como `HR-i`, `HR-1`... en vez de traer una página
   cuya 2ª línea sea literalmente "ÍNDICE" (la señal que usa
   `_es_pagina_indice`) — plantilla de maquetación distinta, verificado
   inspeccionando las primeras páginas reales de ambos PDF. DB-HE sí tiene
   una página "ÍNDICE" real, pero su Índice no usa el patrón "Sección HE
   N   Título" (probablemente "HE N" a secas, sin la palabra "Sección") —
   no verificado en detalle, sin tiempo en esta sesión. Extender el
   detector a estas 3 plantillas es la tarea más valiosa de una próxima
   sesión sobre este pipeline.
2. **DB-SI: falta el Anejo C.** Su encabezado real ("Anejo C Resistencia
   al fuego de las estructuras de hormigón armado") nunca aparece como
   línea propia en el cuerpo — solo en la cabecera de página repetida, a
   diferencia de los otros 6 anejos. Documentado en el docstring de
   `_RE_ANEJO_CUERPO`; una extensión futura podría usar la cabecera de
   página como señal de respaldo cuando el cuerpo no la trae.
3. **DB-SUA (20/22) y DB-HS (27/36): apartados reales sin segmentar.** No
   investigado exhaustivamente uno a uno por tiempo — mismo mecanismo que
   §5.2, probablemente algún apartado cuyo título envuelve a más de 2
   líneas (el lookahead actual cubre hasta 2) o cuyo formato de Índice
   difiere ligeramente. El propio ledger (`extraccion/estado/ledger.jsonl`)
   deja rastro exacto de cuántos segmentos se interpretaron por corrida.
4. **Front-matter no segmentado.** Todo lo anterior a la última página de
   Índice (portada, disposiciones generales, introducción) queda fuera de
   esta primera pasada — es contenido real del DB, pero no numerado por
   Sección/apartado, así que no encaja en el mismo mecanismo de validación
   contra el Índice. Decisión de alcance explícita, no un olvido.
5. **Anejos no se dividen en sus propios puntos internos** (p.ej. Anejo B
   tiene B.1/B.2/B.3) — se tratan como un único segmento por anejo, mismo
   alcance que ya aceptaba `segmentador.py` (XML/BOE) para los anejos del
   propio Real Decreto 314/2006. No se interpretaron con IA en la corrida
   real de esta sesión (ver §6) por ser bloques muy largos (p.ej. Anejo A
   de DB-SI: ~34.000 caracteres) — una sola `ReglaCandidata` por anejo
   entero no tiene sentido semántico; quedan para una fase futura que los
   trate como lo que son (glosarios/tablas técnicas), no como una exigencia
   normativa única.

## 6. Corrida real: candidatas generadas — completada

Pablo paró la primera corrida a medias para pedir la auditoría de fuentes
de `docs/design/2026-08-06-auditoria-fuentes-cte.md` (§0-§5 de este
documento reflejan justo esa pausa). Una vez aprobado ese diseño (con la
condición de doble fuente, ver §6 de la auditoría) se completó la ingesta
dual real (6 instrumentos BOE + 11 documentos de `codigotecnico.org`,
todos versionados en `ingesta/estado/`) y se relanzó la extracción
completa sobre los 3 DB con segmentación suficiente:

| DB | Apartados interpretados | Candidatas | Alta | Baja | Pendientes de revisión |
|---|---|---|---|---|---|
| DB-SI | 25 | 25 | 1 | 24 | 24 |
| DB-SUA | 20 | 20 | 1 | 19 | 19 |
| DB-HS | 27 | 27 | 4 | 23 | 23 |
| **Total** | **72** | **72** | **6** | **66** | **66** |

0 avisos de interpretación en las 3 corridas (ningún segmento falló al
interpretarse). **66 de 72 (92%) quedaron marcadas para revisión humana**
— esperado y correcto, no un fallo: los apartados normativos reales suelen
remitir a tablas, tener excepciones anidadas o citar cifras que el
mecanismo de verificación no puede confirmar carácter por carácter contra
el texto — el sistema está diseñado para admitirlo en vez de fingir
confianza que no tiene (mismo patrón que ya había confirmado la Fase 2 en
su propia sesión de diseño). Ejemplo real inspeccionado (DB-HS 3.4,
dimensionado de conductos de ventilación): la IA extrajo 9 parámetros
numéricos con fórmulas reales, y la verificación mecánica detectó que una
cifra citada no aparece literal en el texto del segmento — Baja confianza,
pendiente de revisión, motivo declarado.

**Ninguna candidata se promovió** — siguen las 72 en
`extraccion/estado/candidatas/*.jsonl`, pendientes de que un colegiado las
revise. Nada de esto tocó `normativa/es/`.

**Bug real encontrado y corregido durante esta misma corrida**: la primera
vez que se guardó DB-SI, ya existía un fichero de una prueba anterior (2
candidatas) — `extraccion/almacen.py` correctamente no lo reescribió, pero
el ledger registró igualmente "25 candidatas" tomando las cifras de la
corrida en memoria en vez de leer el fichero real. Corregido: el ledger
ahora siempre refleja lo que hay de verdad en disco cuando no reescribe
(test de regresión en `test_extraccion_almacen.py`). Se verificó a mano
que las cifras de la tabla de arriba coinciden línea por línea con los 3
ficheros `.jsonl` reales (25/20/27), no solo con lo que dice el ledger.

**Pendiente para una sesión futura**: DB-HE, DB-HR, DB-SE (0 segmentos —
ver §5.1) y los apartados de DB-SUA/DB-HS que el segmentador aún no
reconoce (2 y 9 respectivamente — ver §5.3). Los anejos (§5.5) siguen sin
interpretarse con IA en ningún DB, por diseño de esta primera pasada.
