# Banco de DXF plausibles

La misma vivienda válida (4 estancias, 36 m² útiles) dibujada a la manera de 11 estudios distintos. Criterio contrario al banco de tortura: **todos deberían medirse sin preguntar nada**. Un AVISO aquí es un falso rechazo a investigar, no un rechazo controlado correcto.

| Fichero | Convención |
|---|---|
| `01_control_estancias.dxf` | Capa ESTANCIAS, rótulo dentro del recinto con área (control) |
| `02_capa_a_sup_util.dxf` | Capa «A-SUP-UTIL»: convención de capas por prefijo de disciplina (A-) |
| `03_capa_superficies.dxf` | Capa «SUPERFICIES»: nombre llano, sin prefijo ni numeración |
| `04_capa_03_recintos.dxf` | Capa «03_RECINTOS»: numeración de capas por índice de plano |
| `05_capa_areas.dxf` | Capa «AREAS»: nombre llano en plural, sin acento |
| `06_rotulo_fuera_con_directriz.dxf` | Rótulo fuera de cada recinto (~0.6 m del borde) con línea directriz hasta el contorno |
| `07_rotulo_solo_nombre.dxf` | Rótulo dentro del recinto pero solo el nombre, sin cifra de superficie |
| `08_mm_insunits_correcto.dxf` | Geometría en mm con $INSUNITS=4 declarado correctamente (sin mentir) |
| `09_capas_de_ruido.dxf` | Estancias reales + capas de ruido habituales: MOBILIARIO, COTAS, EJES, TEXTOS, CAJETIN |
| `10_muros_doble_linea.dxf` | Muros de doble línea (perímetro + particiones) en capa MUROS alrededor de las estancias |
| `11_capa_opaca_rotulos_fuera.dxf` | Capa «V-04» (sin pista de nombre) + TODOS los rótulos fuera con directriz + capas de ruido: el suelo del heurístico de detección de capa |
