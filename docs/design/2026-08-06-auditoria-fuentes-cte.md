# Auditoría de fuentes oficiales del CTE — diseño de consolidación y actualización

Solo diseño y justificación, sin código — es lo que Pablo pidió explícitamente
al parar la ingesta masiva que esta misma sesión había empezado. Todo lo
verificado aquí es contra servicios reales (BOE, `codigotecnico.org`), no
de memoria; donde no se verificó algo se dice explícitamente.

## 0. El problema real, en una frase

**Ningún Documento Básico es un texto único y estático.** Cada uno es el
resultado acumulado de su versión de 2006 (Real Decreto 314/2006, Parte II)
más una cadena de modificaciones posteriores, publicadas en instrumentos
BOE distintos y espaciados en el tiempo — a veces un Real Decreto modifica
varios DB a la vez, a veces uno solo. El propio BOE **no ofrece un
"texto consolidado" de la Parte II** a través de su API de legislación
consolidada (verificado en la Fase 2 de esta misma sesión: se pidió el
texto consolidado de BOE-A-2006-5515 y no trae los DB). Cualquier estrategia
de ingesta tiene que decidir, para cada DB, **quién hace el trabajo de
consolidar texto + modificaciones en un único documento legible**, porque
ArchMuse no debería ser quien lo hace por primera vez.

## 1. Evidencia real recogida esta sesión

Tres hechos verificados, no supuestos, que fundamentan la recomendación de
§2:

1. **El "código electrónico" del BOE es un único PDF de 1316 páginas** que
   mezcla el CTE con ~100 normas no relacionadas (prevención de riesgos
   laborales, etc.) — descargado y comprobado entero. Sirve como
   compilación de referencia, no como fuente estructurada por DB.

2. **`codigotecnico.org` republica cada DB entero cada vez que se modifica,
   con el texto ya fusionado** — no dos documentos (original + parche), uno
   solo. Evidencia directa: el PDF de DB-HR en `codigotecnico.org` trae
   literalmente en su portada *"MINISTERIO DE TRANSPORTES, MOVILIDAD Y
   AGENDA URBANA — 20 diciembre 2019"*, que es la fecha exacta del Real
   Decreto 732/2019 — el instrumento que lo modificó por última vez. El
   Ministerio no deja el trabajo de fusión a quien lo consulta.

3. **Cada DB tiene su propia cadena de modificaciones, de longitud y fechas
   distintas** — no es un evento único ni sincronizado entre DB. Confirmado
   con al menos dos casos concretos:
   - DB-SI: RD 314/2006 (original) → RD 732/2019 → **RD 164/2025** (más
     reciente, en vigor desde el 10/05/2025 — coordina DB-SI con el nuevo
     Reglamento de seguridad contra incendios en establecimientos
     industriales).
   - DB-HR: RD 314/2006 (original) → RD 732/2019.
   - El propio Real Decreto 314/2006 (Parte I, la que sí trae la API de
     legislación consolidada del BOE) acumula al menos 8 modificaciones
     documentadas entre 2007 y 2022 — evidencia indirecta de que la Parte
     II (los DB) tiene un ritmo de cambio comparable, no son estáticos.

No se verificó exhaustivamente la cadena completa de modificaciones de
DB-SUA, DB-HS, DB-HE ni DB-SE instrumento por instrumento — no hacía falta
para la decisión de diseño (§2), y habría alargado esta auditoría sin
cambiar la recomendación. Si se necesita esa cadena completa algún día (por
ejemplo, para justificar ante un colegiado por qué una regla concreta tiene
la redacción que tiene), es un dato que se puede recuperar del propio BOE
bajo demanda, no algo que ArchMuse necesite mantener por adelantado.

**Cuarto hallazgo, corrige una suposición del propio `codigotecnico.py`
construido antes de esta pausa**: cada PDF trae en su portada una fecha
real, coherente con un instrumento BOE real — verificado en los 4 DB
restantes: DB-SE "20 diciembre 2019" (mismo día que el RD 732/2019 de
DB-HR: confirma que fue una modificación conjunta de varios DB a la vez,
no aislada) y DB-HS "14 junio 2022" (coincide con el RD 450/2022 encontrado
en el histórico de modificaciones de la Parte I). **La cabecera HTTP
`Last-Modified` del servidor, en cambio, NO sirve para esto**: los 4 PDF
comprobados devolvieron la misma fecha-hora (a 3 segundos de diferencia
entre sí) del día en que se hizo esta auditoría — es la huella de un
redespliegue del sitio, no de una actualización legal del documento. La
señal de cambio real para §3.1 tiene que ser el **hash del contenido**
(ya construido) o, como metadato humano-legible, la **fecha impresa en la
portada del propio PDF** (extraíble por texto, no por cabecera HTTP) —
nunca `Last-Modified`.

## 2. Fuente canónica recomendada, por DB

**El Ministerio, no ArchMuse, debe seguir siendo quien consolida.**
Reconstruir el texto vigente de un DB fusionando manualmente sus
modificaciones sería: (a) un motor nuevo — justo lo que Pablo dijo que no
quiere; (b) un riesgo real de introducir un error en exactamente el tipo de
detalle (un umbral numérico, una excepción) que más importa acertar; (c)
trabajo duplicado, porque el propio Ministerio ya lo hace correctamente y
lo publica gratis. La fuente canónica de **contenido** para los 6 DB es:

| DB | Fuente canónica de contenido | Fuente de proveniencia legal |
|---|---|---|
| DB-SE (+ AE/C/A/F/M) | `codigotecnico.org/pdf/Documentos/SE/DBSE*.pdf` | BOE (RD 314/2006 + modificaciones, no trazadas exhaustivamente) |
| DB-SI | `codigotecnico.org/pdf/Documentos/SI/DBSI.pdf` | BOE: RD 314/2006, RD 732/2019, **RD 164/2025** |
| DB-SUA | `codigotecnico.org/pdf/Documentos/SUA/DBSUA.pdf` | BOE (RD 314/2006 + modificaciones, no trazadas exhaustivamente) |
| DB-HS | `codigotecnico.org/pdf/Documentos/HS/DBHS.pdf` | BOE (RD 314/2006 + modificaciones, no trazadas exhaustivamente) |
| DB-HE | `codigotecnico.org/pdf/Documentos/HE/DBHE.pdf` | BOE (RD 314/2006 + modificaciones, no trazadas exhaustivamente) |
| DB-HR | `codigotecnico.org/pdf/Documentos/HR/DBHR.pdf` | BOE: RD 314/2006, **RD 732/2019** |

**Diseño de dos fuentes, nunca fusionadas por ArchMuse**: el *contenido*
(el texto que se segmenta e interpreta) viene siempre de
`codigotecnico.org`. La *proveniencia legal* (qué instrumento(s) BOE
constituyen la versión vigente, para poder citarlo con propiedad ante un
colegiado) es metadato aparte, capturado cuando se conozca, nunca inferido
ni reconstruido por ArchMuse. Si algún día `ReglaCandidata` necesita citar
"según el RD 164/2025", ese dato se añade a mano o se busca puntualmente en
el BOE — no se deriva del texto de `codigotecnico.org`, que no lo declara
explícitamente instrumento por instrumento.

## 3. Estrategia de actualización automática

Dos señales independientes, ninguna nueva en el sentido de "motor nuevo" —
ambas reutilizan mecanismos que la Fase 1/Fase 2 ya construyeron:

### 3.1 Señal primaria: hash del PDF de `codigotecnico.org` (ya construida)

`ingesta/almacen.py` (Fase 1) ya compara el hash de cada descarga contra la
última conocida y clasifica `nuevo` / `sin_cambios` / `modificado` — es
literalmente el mecanismo de detección de cambios que hace falta, sin
escribir nada nuevo. Lo único que falta es **cuándo** volver a preguntar:
una comprobación periódica y de baja frecuencia (p. ej. semanal) de los 11
PDF del catálogo es proporcional, porque estos documentos cambian con
frecuencia de años, no de días — verificado en §1 (RD 164/2025 es la
primera modificación de DB-SI desde 2019).

Cuando el hash cambia: dispara re-segmentación + re-extracción de ESE DB
únicamente (el pipeline ya versiona por hash — `extraccion/almacen.py`,
construido en esta sesión, nunca sobrescribe una corrida anterior), nunca
un barrido de los 6 documentos completos solo porque uno cambió.

### 3.2 Señal secundaria: vigilancia del sumario diario del BOE (ya construida, reutilizada)

`ingesta/pipeline.ingerir_fecha` (Fase 1) ya recorre el sumario diario del
BOE filtrando por sección "I. Disposiciones generales". Añadir un filtro de
texto sobre el título de cada item (¿menciona "Código Técnico de la
Edificación"?) — no un módulo nuevo, un parámetro más al filtro que ya
existe — da una alerta temprana de que **algo** en el CTE cambió, con el
identificador BOE-A exacto del instrumento, normalmente días o semanas
antes de que `codigotecnico.org` termine de republicar el PDF consolidado.
Esta señal no dispara re-extracción por sí sola (el contenido fusionado
todavía no está en `codigotecnico.org`) — alimenta la columna de
"proveniencia legal" de §2 y sirve de recordatorio de que hay que volver a
comprobar el hash de §3.1 pronto, no dentro de una semana entera.

### 3.3 Lo que decae si esto se automatiza sin supervisión

Ninguna candidata se promueve nunca automáticamente (ya es una invariante
de `extraccion/`, no cambia). Un DB que cambia de contenido invalida las
candidatas ya guardadas de su versión anterior — no se borran (el ledger es
append-only, mismo principio que `ingesta/almacen.py`), pero deberían
marcarse como correspondientes a una versión superada, para que quien
revise la cola no confunda una candidata de una redacción ya derogada con
la vigente. Esto es diseño para una fase futura de "cola de revisión" (la
que Pablo ya dijo dos veces que sí necesita el PRD completo), no algo a
resolver aquí.

## 4. Lo que NO se recomienda

- **No** construir un reconstructor de texto consolidado a partir de las
  modificaciones del BOE. Es trabajo real, es fácil de acertar mal en el
  detalle que más importa, y el Ministerio ya lo hace correctamente y
  gratis — construirlo sería la definición exacta de "motor nuevo".
- **No** tratar `codigotecnico.org` como si trajera metadatos legales
  fiables por instrumento — no los declara de forma estructurada. Para
  proveniencia legal, la fuente sigue siendo el BOE, consultado puntualmente.
- **No** escanear el histórico completo del BOE desde 2006 para catalogar
  por adelantado la cadena de modificaciones de los 6 DB. Es investigación
  legal de valor real pero acotado, mejor bajo demanda (cuando una
  candidata concreta necesite esa cita) que como inventario previo — mismo
  principio que ya rige `ingerir_rango` en Fase 1 ("los últimos N días
  desde la última ejecución", no un barrido histórico completo).

## 5. Siguiente paso, si Pablo aprueba este diseño

Nada de código nuevo hace falta para §2/§3.1: `ingesta/fuentes/codigotecnico.py`
y `ingesta/almacen.py` (ya construidos esta sesión) son exactamente el
mecanismo que describe §3.1. Lo único no construido es el filtro de texto
de §3.2 sobre el sumario del BOE — un cambio pequeño y acotado a
`ingesta/pipeline.py`, no un módulo nuevo. Se deja sin implementar hasta
que Pablo confirme que este diseño es el correcto.

## 6. Aprobado por Pablo (2026-08-06), con una condición: doble fuente siempre

Pablo aprobó el diseño con una condición explícita: **nunca depender de una
única fuente**. Cada documento debe guardar, junto al contenido: la URL de
`codigotecnico.org`, el/los BOE que lo modifican, el hash del PDF, la fecha
de publicación y la fecha de última comprobación — así, si mañana cambia o
desaparece la web del Ministerio, ArchMuse sigue siendo verificable.

**Implementado, no solo diseñado** (extensión aditiva de lo ya construido,
sin motor nuevo):
- `ingesta/modelo.py`: `DocumentoOficial` gana `referencias_boe` (vacío
  para BOE mismo — un documento del BOE no se cita a sí mismo); `EstadoDescarga`
  (lo que se escribe en el ledger) gana `url_oficial`, `fecha_publicacion`,
  `referencias_boe`. `fecha_descarga` (ya existía) hace de "fecha de última
  comprobación".
- `ingesta/fuentes/codigotecnico.py`: `_CATALOGO` pasa a llevar, por cada
  DB, la fecha impresa en su propia portada (verificada por regex contra el
  PDF real, no inventada) y los identificadores BOE-A de los instrumentos
  que lo constituyen — curados a mano tras investigar cada uno contra el
  BOE real (ver tabla abajo), nunca reconstruidos en tiempo de ejecución.
  Se dejó de usar la cabecera HTTP `Last-Modified` para nada con
  significado (ver el hallazgo de §1 de esta misma sesión: es la huella de
  un redespliegue del sitio, no de una actualización legal).

### Registro de proveniencia por DB (verificado contra el BOE real)

| DB | Fecha de portada | Instrumentos BOE | Confianza |
|---|---|---|---|
| DB-SE | 2019-12-20 | BOE-A-2006-5515, BOE-A-2009-6743, BOE-A-2019-18528 | Alta en RD 314/2006 y RD 732/2019 (fecha de portada coincide); Orden VIV/984/2009 sin confirmar si tocó específicamente SE |
| DB-SE-AE | 2006-03-17 | BOE-A-2006-5515 | Alta — excluido explícitamente del alcance de RD 732/2019 |
| DB-SE-C | 2019-12-20 | BOE-A-2006-5515, BOE-A-2009-6743, BOE-A-2019-18528 | Igual que DB-SE, sin diferenciar |
| DB-SE-A | 2006-03-17 | BOE-A-2006-5515 | Alta — excluido explícitamente del alcance de RD 732/2019 |
| DB-SE-F | 2019-12-20 | BOE-A-2006-5515, BOE-A-2009-6743, BOE-A-2019-18528 | Igual que DB-SE, sin diferenciar |
| DB-SE-M | 2019-12-20 | BOE-A-2006-5515, BOE-A-2009-6743, BOE-A-2019-18528 | Igual que DB-SE, sin diferenciar |
| DB-SI | 2025-03-04 | BOE-A-2006-5515, BOE-A-2019-18528, BOE-A-2025-7190 | Alta — fecha de portada es literalmente la del RD 164/2025 ("de 4 de marzo") |
| DB-SUA | 2022-06-14 | BOE-A-2006-5515, BOE-A-2009-6743, BOE-A-2019-18528, BOE-A-2022-9848 | Alta en RD 314/2006/732/2019/450/2022 (fecha de portada coincide); Orden VIV/984/2009 sin confirmar |
| DB-HS | 2022-06-14 | BOE-A-2006-5515, BOE-A-2019-18528, BOE-A-2022-9848 | Alta — fecha de portada coincide con RD 450/2022 |
| DB-HE | 2022-06-14 | BOE-A-2006-5515, BOE-A-2019-18528, BOE-A-2022-9848 | Alta — fecha de portada coincide con RD 450/2022 (que añade HE6) |
| DB-HR | 2019-12-20 | BOE-A-2007-18400, BOE-A-2019-18528 | Alta — DB-HR no viene en el RD 314/2006 original, se aprobó en 2007 |

Confianza declarada explícitamente en el propio código (`_CATALOGO`), no
solo aquí — si una futura sesión encuentra evidencia de que la Orden
VIV/984/2009 no tocó realmente SE/SUA, o de que SE-C/F/M tienen su propia
cadena distinta a SE, corregir el dato en `codigotecnico.py`, no en este
documento (el código es la fuente de verdad operativa; este documento es
el porqué).
