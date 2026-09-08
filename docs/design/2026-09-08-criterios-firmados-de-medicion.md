# Criterios firmados de medición

**Qué es este documento y en qué se diferencia de `decisiones-pendientes.md`.**
Aquél registra lo que **necesita a Pablo** y no se ha decidido. Éste registra lo
contrario: criterios profesionales que **ya se han dictaminado**, quién los
dictaminó y cuándo, para que dejen de vivir como comentarios sueltos dentro del
código que los aplica.

Existe porque `D-7` lleva abierta desde el 2026-08-19 diciendo que hay criterio
profesional codificado y sin firmar, y que eso «no puede quedarse sin firmar
cuando esto se cobre». Cada criterio que sale de esa lista entra en ésta.

**Regla de este documento:** un criterio no se escribe aquí hasta que alguien
con competencia para dictaminarlo lo ha dictaminado. La implementación cita el
criterio; el criterio no se deduce de la implementación.

---

## C-1 · La superficie útil interior y la exterior no se suman

**Dictaminado por:** el arquitecto, en la sesión de validación del 2026-09-07.
**Aprobado por Pablo:** 2026-09-08. **Estado:** implementado el 2026-09-08.

**El criterio.** Una vivienda tiene **dos** superficies útiles —interior y
exterior (terrazas y tendederos)— y son dos magnitudes, no un desglose de una
tercera. **No existe una «superficie útil total» que las sume.**

**Qué había antes.** Un único `total_util_m2 = interior + exterior`, con los
espacios exteriores computando al **100 %**. Sobre el plano real, la vivienda
`VT1/3` publicaba 66,32 m² de «superficie útil total», de los que 7,54 eran
terraza contando igual que un dormitorio.

**Por qué importa más de lo que parece.** El cómputo de los espacios exteriores
(al 100 %, al 50 %, fuera del útil) depende de la ordenanza y del criterio del
técnico que firma. Una cifra que lo resuelve por su cuenta no es una medición:
es una decisión profesional disfrazada de cálculo, y viaja hasta la memoria
justificativa, que alguien presenta y firma.

**Dónde está aplicado, y es en todas partes.** `total_util_m2` no existe en
ninguna capa: ni en el modelo (`analyzer/medicion.py`), ni en el acta de
procedencia (`agente/skills/medicion.py` publica `medicion.util_interior_m2` y
`medicion.util_exterior_m2` como **dos hechos**), ni en el PDF de medición, ni
en la memoria justificativa, ni en la API, ni en la pantalla `/medir`, ni en el
CLI. La celda «TOTAL S. ÚTIL» del `ACAD_TABLE` del plano sale **`N/D` con su
motivo escrito** (`MOTIVO_TOTAL_UTIL_NO_SE_SUMA`), no en blanco: en blanco se
leería como «ArchMuse no ha sabido», y lo que ha hecho es no decidir por el
arquitecto.

**El único sitio donde se suman**, y es una comprobación, no una salida:
`_todo_total_suma_todas_sus_piezas` verifica que entre las dos no se ha perdido
ninguna pieza. Está documentado ahí mismo para que nadie lo confunda con
reintroducir el total.

---

## C-2 · Un impedimento bloquea las dos superficies, no sólo su suma

**Propuesto por:** ArchMuse (CTO), al implementar `C-1` el 2026-09-08.
**Dictaminado por Pablo:** 2026-09-08 — «aprobada y bien argumentada».
**Estado:** implementado.

**El criterio.** Cuando una vivienda tiene un impedimento —piezas solapadas,
reparto entre viviendas no firme, o una pieza que no se sabe clasificar—
**ninguna de las dos superficies se publica**. Las dos salen ausentes, con el
motivo y su magnitud. Las piezas se siguen midiendo y enseñando una a una.

**Qué había antes, y por qué cambia.** Hasta el 2026-09-08 los parciales
interior y exterior se publicaban **aunque** el total estuviera bloqueado: eran
el desglose de una cifra que el lector ya veía ausente, y se leían como
información de apoyo. Al desaparecer el total, esos dos parciales **pasan a ser
ellos mismos el resultado**, y publicar un resultado con un impedimento abierto
es exactamente el «número que puede estar mal» que la regla dura del módulo
existe para no dar.

**El razonamiento, que es lo que hay que poder discutir.** Un solape puede caer
dentro de lo interior, dentro de lo exterior o a caballo entre los dos: no se
sabe a cuál de las dos cifras le sobra superficie. Una pieza sin clasificar no
se sabe de qué lado cuenta, así que a las dos les puede faltar. Un reparto
dudoso puede llevarse cualquier pieza a la vivienda de al lado. En los tres
casos, publicar **una** de las dos sería afirmar que esa está bien, y no consta.

**Es una extensión de una regla ya firmada**, no una nueva: «una cifra que puede
estar mal es peor que su ausencia — la primera se copia a la memoria del
proyecto y la segunda se pregunta».

**Comprobado sobre plano real:** `tests/fixtures/reales/vivienda_con_solapes.dxf`
(7,08 m² dibujados dos veces) no publica ninguna de las dos, y sus nueve piezas
siguen medidas.

---

## Lo que sigue sin firmar

De los tres criterios que `D-7` enumera desde el 2026-08-19, **`C-1` y `C-2`
resuelven el tercero** (qué hacer ante un solape). Siguen abiertos:

1. **El orden del procedimiento de `superficies.cuadro_de_vivienda`** —
   comprobar la unidad antes de medir, medir por un camino separado del cálculo,
   y cruzar los dos. Ese orden es criterio profesional y hoy lo eligió Claude.
2. **Qué hacer ante una ambigüedad de reparto** — dos piezas «Tendedero» para un
   hueco del cuadro, una «Terraza» para dos. Hoy: no se reparte ni se suma, y la
   celda queda bloqueada con su motivo. Defendible y conservador, pero otro
   arquitecto podría sostener que la mayor manda.

Y de las cuatro preguntas abiertas de la sesión de validación siguen sin
contestar dos: **qué vocabulario de rótulos** reconoce el motor (hoy ocho
familias, y lo que no entra bloquea la vivienda entera) y **la tasa real de
discrepancias** memoria↔plano, que es la que gobierna el PRD del 2026-08-22.
