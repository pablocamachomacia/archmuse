"""Extractor determinista de la ruta B (`extraccion/interprete_b_determinista.py`),
decisión de Pablo del 2026-08-21 sobre la tarea 8 del Prompt 2: sin API,
sin red, coste cero. Golden tests contra cláusulas REALES de DB-SUA (el
mismo `texto_original` que ya usa la ruta A —
`extraccion/estado/candidatas/codigotecnico__DB-SUA__3cfb5bbb135e.jsonl`—),
de cuatro tipos distintos: mínimo, máximo, porcentaje y tabla — más el
caso adversarial de la disyunción de 7.3, que el propio encargo exige
resolver con las DOS cifras, nunca una sola.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extraccion import interprete_b_determinista as m  # noqa: E402


def test_minimo_atrapamiento_2_2():
    """DB-SUA 2.2, `texto_original` real: «...la distancia a hasta el
    objeto fijo más próximo será 20 cm, como mínimo (véase figura 2.1).»"""
    texto = "la distancia a hasta el objeto fijo más próximo será 20 cm, como mínimo"
    valores, no_reconocidas = m.extraer(texto)
    assert len(valores) == 1
    assert valores[0].valor_citado == "20 cm"
    assert valores[0].comparador == ">="
    assert not no_reconocidas


def test_maximo_aprisionamiento_3_1():
    """DB-SUA 3.1, real: «La fuerza de apertura de las puertas de salida
    será de 140 N, como máximo»."""
    texto = "la fuerza de apertura de las puertas de salida será de 140 N, como máximo"
    valores, _ = m.extraer(texto)
    assert len(valores) == 1
    assert valores[0].valor_citado == "140 N"
    assert valores[0].comparador == "<="


def test_porcentaje_alumbrado_4_1():
    """DB-SUA 4.1, real: «El factor de uniformidad media será del 40% como
    mínimo.»"""
    texto = "El factor de uniformidad media será del 40% como mínimo"
    valores, _ = m.extraer(texto)
    assert len(valores) == 1
    assert valores[0].valor_citado == "40 %"
    assert valores[0].comparador == ">="


def test_porcentaje_maximo_caracteristicas_constructivas_7_2():
    """DB-SUA 7.2, real: «...y una pendiente del 5% como máximo.»"""
    texto = "una pendiente del 5% como máximo"
    valores, _ = m.extraer(texto)
    assert len(valores) == 1
    assert valores[0].valor_citado == "5 %"
    assert valores[0].comparador == "<="


def test_mas_de_discontinuidades_1_2():
    """Hueco real encontrado comparando contra la ruta A: DB-SUA 1.2, real:
    «No tendrá juntas que presenten un resalto de más de 4 mm.» — «más de»
    no estaba en el catálogo original de patrones."""
    texto = "No tendrá juntas que presenten un resalto de más de 4 mm."
    valores, _ = m.extraer(texto)
    assert len(valores) == 1
    assert valores[0].valor_citado == "4 mm"
    assert valores[0].comparador == ">"


def test_mas_de_ambito_graderios_5_1():
    """DB-SUA 5.1, real: «...previstos para más de 3000 espectadores de
    pie.»"""
    texto = "previstos para más de 3000 espectadores de pie"
    valores, _ = m.extraer(texto)
    assert len(valores) == 1
    assert valores[0].valor_citado == "3000 espectadores de pie"
    assert valores[0].comparador == ">"


def test_disyuncion_proteccion_recorridos_7_3_emite_las_dos_cifras():
    """El caso que más importa de todos, exigido explícitamente por el
    encargo: DB-SUA 7.3, real: «En plantas de Aparcamiento con capacidad
    mayor que 200 vehículos o con superficie mayor que 5000 m2...» — una
    disyunción real (confirmada por las propias `excepciones` de la
    candidata en el Prompt 1.5: «Si la capacidad es ≤200 vehículos Y la
    superficie es ≤5000 m², el apartado no es de aplicación»). El
    extractor tiene que devolver AMBAS cifras, nunca elegir una."""
    texto = ("En plantas de Aparcamiento con capacidad mayor que 200 vehículos "
             "o con superficie mayor que 5000 m2, los itinerarios peatonales "
             "de zonas de uso público se identificarán")
    valores, _ = m.extraer(texto)
    citados = {(v.valor_citado, v.comparador) for v in valores}
    assert ("200 vehículos", ">") in citados
    assert ("5000 m2", ">") in citados
    assert len(valores) == 2, f"se esperaban exactamente 2 valores, salieron {len(valores)}: {citados}"


def test_tabla_2_1_proteccion_contra_el_rayo_8_2_da_las_siete_cotas():
    """DB-SUA 8.2, Tabla 2.1 real (4 filas, cada una una o dos cotas de un
    rango): «E > 0,98 1 / 0,95 < E <0,98 2 / 0,80 < E <0,95 3 /
    0 < E < 0,80 (1) 4». 7 cotas en total — el bug real encontrado al
    implementar esto (doble inversión del comparador en los patrones
    «NÚMERO < VARIABLE») se quedaba en 5, con dos comparadores al revés;
    este test es el que lo habría cazado."""
    texto = ("Tabla 2.1 Componentes de la instalación Eficiencia requerida "
             "Nivel de protección E > 0,98 1 0,95 < E <0,98 2 0,80 < E <0,95 3 "
             "0 < E < 0,80 (1) 4")
    valores, _ = m.extraer(texto)
    citados = {(v.valor_citado.split()[0], v.comparador) for v in valores}
    assert citados == {
        ("0,98", ">"),   # fila 1: E > 0,98
        ("0,98", "<"),   # fila 2, cota superior: E < 0,98
        ("0,95", ">"),   # fila 2, cota inferior: 0,95 < E
        ("0,95", "<"),   # fila 3, cota superior: E < 0,95
        ("0,80", ">"),   # fila 3, cota inferior: 0,80 < E
        ("0,80", "<"),   # fila 4, cota superior: E < 0,80
        ("0", ">"),      # fila 4, cota inferior: 0 < E
    }
    assert all(v.unidad == "adimensional" for v in valores)


def test_clausula_sin_patron_reconocido_va_a_no_reconocidas_no_se_inventa():
    """DB-SUA 2.2, real: la segunda oración del artículo no cita ninguna
    cifra reconocible por el catálogo de patrones («especificaciones
    técnicas propias», sin más) — tiene que quedar fuera, no forzarse."""
    texto = ("Los elementos de apertura y cierre automáticos dispondrán de "
             "dispositivos de protección adecuados al tipo de accionamiento "
             "y cumplirán con las especificaciones técnicas propias")
    valores, no_reconocidas = m.extraer(texto)
    assert not valores
    assert not no_reconocidas  # sin cifra citada: no hay nada que declarar pendiente tampoco


def test_clausula_con_cifra_pero_sin_patron_se_declara_no_reconocida():
    texto = "El plazo de ejecución de la obra 47 no está sujeto a esta sección"
    valores, no_reconocidas = m.extraer(texto)
    assert not valores
    assert len(no_reconocidas) == 1
    assert no_reconocidas[0].motivo == "patron_no_reconocido_ruta_b"
    assert no_reconocidas[0].texto == texto


def test_nunca_pierde_una_cifra_en_silencio():
    """Invariante general: toda cláusula con al menos una cifra termina en
    `valores` o en `no_reconocidas`, nunca desaparece sin más."""
    texto = ("la distancia será 20 cm, como mínimo. El plazo de ejecución de "
             "la obra 47 no está sujeto a esta sección. capacidad mayor que "
             "200 vehículos o con superficie mayor que 5000 m2.")
    valores, no_reconocidas = m.extraer(texto)
    assert len(valores) + len(no_reconocidas) >= 3
