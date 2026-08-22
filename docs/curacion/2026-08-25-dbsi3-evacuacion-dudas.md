# Lista de dudas de transcripción — paquete DB-SI 3 evacuación (Residencial Vivienda)

**Fecha de transcripción:** 2026-08-22 · **Sesión de validación:** lunes 2026-08-25
**PRD:** `docs/prd/2026-08-22-corpus-firmado-dbsi3-evacuacion.md` · **Ficha:** `docs/design/2026-08-18-ficha-de-transcripcion-normativa.md`

La ficha lo dice: ante la duda, no se transcribe. Esta lista es un entregable
tan válido como las reglas — alimenta lo que ArchMuse declara como «no
comprobado» y es el orden del día de la parte deliberativa de la sesión.

## Dudas que la sesión debería dictaminar

1. **«Ocupantes que duermen» y el uso Residencial Vivienda** (heredada de la
   piloto del 18-08). La fila «35 m con más de una salida» de la tabla 3.1
   aplica a «zonas en las que se prevea la presencia de ocupantes que
   duermen». ¿Un edificio de viviendas entra SIEMPRE en esa fila, o el término
   apunta a usos con ocupantes ajenos al edificio (hotelero, hospitalario,
   residencias)? La transcripción NO lo asume: la fila existe como excepción y
   el motor no la aplica de oficio a residencial. **Es la duda con más
   impacto práctico del paquete** (50 m vs 35 m con varias salidas).

2. **Recorrido único inicial con varias salidas** (tabla 3.1, fila «La
   longitud de los recorridos de evacuación desde su origen hasta llegar a
   algún punto desde el cual existan al menos dos recorridos alternativos no
   excede de […] la longitud máxima admisible cuando se dispone de una sola
   salida, en el resto de los casos»). Es autorreferencial (remite al límite
   de salida única, con sus propias excepciones): transcribirla exige decidir
   si se materializa como valor (25 m para residencial) o como remisión.
   **No transcrita.**

3. **Ocupación nula de la tabla 2.1.** «Ocupación nula» no es una densidad en
   m²/persona: transcribirla como `valor: 0` diría otra cosa (medido y da
   cero). ¿Se modela como fila propia con convención declarada, o queda fuera
   del parámetro y solo en el literal? **Hoy: solo en el literal.**

4. **Fórmulas de capacidad de la tabla 4.1** (A ≥ P/200, A ≥ P/160,
   A ≥ P/(160-10h), E ≤ 3S+160·AS, P ≤ 3S+200·A). No encajan en ninguno de
   los 5 patrones del catálogo (comparan contra una expresión, no contra un
   valor). Transcribir solo los mínimos geométricos (hecho) deja fuera el
   dimensionado por ocupación. ¿Se abre expediente de gobernanza para un
   patrón de fórmula, o el dimensionado por ocupación queda declarado como
   «no comprobado»? **Hoy: mínimos geométricos transcritos; fórmulas fuera.**

5. **Tabla 4.2 (capacidad de escaleras por anchura).** Es la tabulación de
   las fórmulas de la 4.1 para escaleras de doble tramo. Transcribirla son
   ~75 valores con condición de configuración (nota 1). ¿Merece entrar en un
   paquete posterior, o basta la 4.1 cuando haya patrón de fórmula?
   **No transcrita.**

6. **«Salida de planta», casos 2 y siguientes del Anejo A** (paso a sector
   alternativo con condiciones de superficie 0,5 m²/persona, etc.). Se ha
   transcrito el caso 1 (escaleras protegidas); los demás son composiciones
   con condiciones propias. **Transcripción parcial, declarada en la propia
   definición.**

7. **Apartado 6, condiciones cualitativas de puertas** (dispositivos UNE-EN
   179/1125, puertas automáticas, giratorias). Son `exigencia_cualitativa` o
   `remision`: no evaluables por el motor geométrico. ¿Se transcriben como
   no-evaluables (aplica_no_evaluable, se informa) en un paquete posterior?
   **No transcritas.**

8. **Excepciones de otros usos dentro de filas transcritas.** Varias filas
   traen excepciones de usos ajenos al paquete (Aparcamiento, Hospitalario,
   Docente, Residencial Público). El literal las conserva íntegras; el
   parámetro las incluye solo cuando la fila es la misma (tabla 3.1 de
   recorridos, heredado de la piloto) y las excluye cuando son fila propia de
   otro uso (nota al pie de cada regla). ¿Conforme con el criterio?

9. **Señalización (apartado 7) y control de humo (apartado 8).** Contienen
   exigencias de presencia evaluables (señal «SALIDA» exenta en Residencial
   Vivienda; control de humo por ocupación >1000, atrios >500). Fuera del
   paquete por acotar el alcance a lo que la skill de recorridos y las
   futuras skills de evacuación geométrica pueden consumir. ¿Siguiente
   paquete?

10. **Evacuación de personas con discapacidad (apartado 9).** Umbral claro
    para Residencial Vivienda (altura de evacuación > 28 m → zona de refugio
    o sector alternativo). Evaluable y de alto valor, pero exige la
    definición de itinerario accesible (DB-SUA) y plazas por ocupación.
    ¿Siguiente paquete, junto con DB-SUA 9?

## Definiciones que el paquete consume del glosario sin firma

`normativa/terminologia/dbsi_anejo_a.yaml` aporta «Origen de evacuación»,
«Altura de evacuación», «Superficie útil» y los usos — extraídos de forma
determinista y con `verificada_por_humano: false`. La sesión puede cotejarlos
sobre el anexo de literales de la hoja, pero su mecanismo de firma no es el
del corpus de reglas y queda fuera de este PRD.
