# Experimento: validar la arquitectura del grafo antes de migrar nada

Código desechable. No lo importa ningún módulo de producción, y nada de
`analyzer/` ha sido tocado. Sirve para responder una sola pregunta: **¿una
regla escrita solo contra una Graph API da el mismo resultado y queda más
simple que la de hoy?**

```
python -m experimentos.imprimir_grafo                 # el grafo de ejemplo.dxf
python -m experimentos.imprimir_grafo --estricto      # con el criterio de adyacencia de §4
python -m experimentos.comparar_regla                 # A/B contra circulation.py
```

## Resultado (ejemplo.dxf, 2026-08-05)

**Equivalencia: 12 de 12 salidas idénticas**, en las dos reglas portadas
(recorrido dormitorio→baño y baño sin antesala), incluidos los 3 problemas
reales que hoy detecta producción. Mismo mensaje, mismo camino, mismo veredicto.

**Simplicidad:** 30→24 y 14→13 líneas, y sobre todo 25 líneas de grafo privado
(`_build_adjacency_graph` + `_bfs_path`) que dejan de vivir dentro del módulo de
reglas. Dependencias del módulo de reglas: de 9 a 5, ninguna de ellas el parser,
shapely ni el evaluador. Desaparecen las regex, `_normalize` y el `id()` como
identidad de habitación.

## Los dos hallazgos que no se buscaban

1. **Un falso positivo en producción.** En VT6/2, el "Baño: acceso directo desde
   Salón/cocina, sin antesala" que ArchMuse enseña hoy se apoya en un contacto
   de **0,000 m de tramo enfrentado** — las dos habitaciones se tocan en una
   esquina. Con la segunda condición de §4 ese hallazgo desaparece.
2. **Y el umbral de §4 no está justificado.** En VT3/3, Dormitorio 1 y Baño
   tienen un tramo enfrentado de **0,570 m**, tres centímetros por debajo del
   0,60 m que propuse. Con el criterio estricto esa puerta desaparece, el
   recorrido se desvía por el salón y aparece un problema nuevo. El resultado
   de la regla depende de un umbral que me inventé.

Conclusión: el API se valida; el criterio de adyacencia, no. Elegirlo con datos
es trabajo aparte, y hace falta más de un plano.
