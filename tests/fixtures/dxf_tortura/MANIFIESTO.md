# Banco de DXF de tortura

Ficheros sinteticos, libres de derechos. Cada uno ataca una suposicion del parser.
Exito = ninguno produce traceback: preguntan, descartan con motivo o se degradan.

| Fichero | Ataque |
|---|---|
| `01_limpio.dxf` | Vivienda valida en metros con capa y etiquetas claras (control) |
| `02_sin_unidades.dxf` | Sin $INSUNITS: unidad indeterminada, geometria ambigua (4x3 podria ser m o... nada) |
| `03_milimetros_mentirosos.dxf` | Geometria en mm con cabecera que declara metros: un salon de 12 millones de m2 |
| `04_polilinea_abierta.dxf` | Polilineas abiertas: una casi cerrada y otra con hueco de 80 cm |
| `05_estancias_solapadas.dxf` | Solape de 3 m2 entre SALON y COCINA: sumar areas a ciegas infla la superficie |
| `06_etiquetas_duplicadas_y_huerfanas.dxf` | Etiqueta duplicada + recinto mudo + texto huerfano flotando en el vacio |
| `07_capas_enganosas.dxf` | Capa señuelo 'HABITACIONES' vacia; estancias reales en 'A-07-SUP_UTIL' |
| `08_bloques_anidados.dxf` | Bloques anidados 2 niveles, geometria en capa 0 heredando, insert escalado x2 |
| `09_geometria_basura.dxf` | Area cero + polilinea en pajarita (autointerseccion) + vertices duplicados |
| `10_coordenadas_lejanas.dxf` | Coordenadas UTM enormes: estresa deduccion de unidad por plausibilidad y precision float |
| `11_vacio_y_ruido.dxf` | Sin estancias: solo ejes y cajetin. Debe decir 'no encuentro recintos' y que necesita |
| `12_texto_hostil.dxf` | MTEXT multilinea con formato, acentos, coma decimal y area declarada que no cuadra con la medida |
| `13_r12_antiguo.dxf` | Formato R12 de 1992: POLYLINE clasica en vez de LWPOLYLINE, cabecera minima |
