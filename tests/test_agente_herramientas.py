# -*- coding: utf-8 -*-
"""Las capacidades del núcleo, ejecutadas de verdad contra el corpus real.

`tests/test_agente_nucleo.py` prueba el bucle; esto prueba lo que el bucle
ejecuta. La separación importa: un bucle impecable sobre herramientas que
devuelven cualquier cosa no vale nada, y las dos propiedades se rompen por
motivos distintos.

**Las dos propiedades que se fijan aquí:**

1. **Deterministas.** Misma entrada, misma salida, siempre. Es lo que permite
   que estas capacidades entren algún día en el golden, y lo que hace que
   relanzar un trabajo interrumpido sea seguro (V1-13).
2. **Nunca un número por defecto.** Cuando la cadena de repliegue de una regla
   se agota, el valor es `null` **con motivo y con la pregunta concreta**. Que
   una capacidad devuelva 25 cuando no sabe es el bug nº1 de este repositorio
   reencarnado en la capa del agente.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from agente import efectos as _efectos  # noqa: E402
from agente.herramientas import reglas, territorial  # noqa: E402
from agente.registro import registro  # noqa: E402

CID_EVACUACION = "es.rd_314_2006.seguridad_incendio.longitud_recorrido_evacuacion"


def _congelar(valor) -> str:
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, default=str)


# --- Contrato común ---------------------------------------------------------

def test_toda_capacidad_devuelve_un_dict_con_ok():
    """El contrato de salida, comprobado sobre todas las del registro a la vez."""
    invocaciones = {
        "territorial.resolver_ambito": {"municipio": "Madrid"},
        "normativa.reglas_aplicables": {
            "codigo_municipio": "28079",
            "uso": "residencial.vivienda_libre",
            "tipologia": "plurifamiliar",
            "fecha_devengo": "2026-01-01",
        },
        "normativa.umbral_de_regla": {"concept_id": CID_EVACUACION, "ambito_id": "es"},
        # Mismo criterio para las tres del vertical (TL-1): aquí se comprueba
        # que el fallo respeta el contrato; el camino bueno, con un DXF de
        # verdad, lo prueban `tests/test_agente_plano.py` y el golden G11.
        "plano.leer_dxf": {"ruta": "no_existe.dxf"},
        "plano.cuadro_de_superficies": {"ruta": "no_existe.dxf"},
        "plano.superficie_util": {"ruta": "no_existe.dxf"},
        "plano.escribir_cuadro": {"ruta_origen": "no_existe.dxf",
                                  "ruta_destino": "tampoco_existe.dxf"},
        # Y la revisión de coherencia (CO-4): el contrato de salida se
        # comprueba en el camino de fallo, que es el que más fácilmente se
        # olvida. El camino bueno lo prueban
        # `tests/test_agente_skill_coherencia.py` y el golden G11.
        "plano.coherencia": {"ruta": "no_existe.dxf"},
        # El ajuste del encargo (CP-1): no toca ficheros, asi que su camino de
        # fallo es otro -- unos parametros vacios. El contrato de salida es el
        # mismo: dict con `ok`.
        "proyecto.ajustar_programa": {"parametros": {}, "operacion": "cambiar_mix"},
        # Y la medicion de una planta con varias viviendas: mismo criterio
        # otra vez. El camino bueno lo prueba
        # `tests/test_medicion_de_planta.py`, contra los DOS planos reales del
        # cliente -- el de tres viviendas y el que tiene solapes.
        "plano.medicion_de_la_planta": {"ruta": "no_existe.dxf"},
        # Cierre de C4 (Prompt 1.7, 2026-08-21): plano.cuadro_en_pdf,
        # plano.informe_de_coherencia y plano.medicion_en_pdf se fusionaron en
        # ÉSTA, despachada por «tipo» -- así que aquí se prueban los tres
        # caminos de fallo que antes eran tres entradas de esta tabla, no uno.
        "plano.entregable_en_pdf": [
            {"tipo": "medicion", "ruta": "no_existe.dxf",
             "ruta_destino": "tampoco_existe.pdf"},
            {"tipo": "cuadro", "ruta": "no_existe.dxf",
             "ruta_destino": "tampoco_existe.pdf"},
            {"tipo": "coherencia", "ruta": "no_existe.dxf",
             "ruta_destino": "tampoco_existe.pdf"},
        ],
    }
    reg = registro()
    assert set(invocaciones) == set(reg.ids()), "hay una capacidad sin probar aquí"

    for identificador, argumentos_o_lista in invocaciones.items():
        capacidad = reg.buscar(identificador)
        # Una capacidad con efectos se niega sin autorización (TL-2), así que
        # aquí se le concede lo que declara: lo que se comprueba en este test
        # es el CONTRATO DE SALIDA, no el portero — ese tiene el suyo en
        # `tests/test_agente_escritura.py`.
        permisos = (_efectos.Autorizaciones.de(capacidad.efectos, por="test")
                    if capacidad.efectos else None)
        # La mayoría declara un único juego de argumentos; entregable_en_pdf
        # declara una lista, uno por «tipo» -- ver el comentario de arriba.
        lista_de_argumentos = (argumentos_o_lista if isinstance(argumentos_o_lista, list)
                               else [argumentos_o_lista])
        for argumentos in lista_de_argumentos:
            resultado = capacidad.invocar(argumentos, permisos)
            assert isinstance(resultado, dict)
            assert isinstance(resultado["ok"], bool)
            json.dumps(resultado, ensure_ascii=False, default=str)  # serializable


def test_las_capacidades_normativas_son_deterministas():
    """Dos ejecuciones idénticas, byte a byte. Sin esto no hay golden posible."""
    llamadas = (
        (territorial.resolver_ambito, {"municipio": "Madrid"}),
        (
            reglas.reglas_aplicables,
            {
                "codigo_municipio": "28079",
                "uso": "residencial.vivienda_libre",
                "tipologia": "plurifamiliar",
                "fecha_devengo": "2026-01-01",
            },
        ),
        (
            reglas.umbral_de_regla,
            {
                "concept_id": CID_EVACUACION,
                "ambito_id": "es",
                "ejes": {"numero_salidas": "una", "condicion": "general"},
            },
        ),
    )
    for funcion, argumentos in llamadas:
        assert _congelar(funcion(**argumentos)) == _congelar(funcion(**argumentos))


# --- territorial.resolver_ambito --------------------------------------------

def test_resolver_ambito_devuelve_la_cadena_completa():
    r = territorial.resolver_ambito("Madrid")

    assert r["ok"] is True
    assert r["codigo_municipio"] == "28079"
    assert [a["id"] for a in r["cadena"]] == ["es", "es.13", "es.13.28", "es.13.28.28079"]


def test_un_municipio_que_no_esta_en_el_registro_no_se_aproxima():
    """No se elige el más parecido: se dice que no está y se pregunta."""
    r = territorial.resolver_ambito("Villafantasma del Ejemplo")

    assert r["ok"] is False
    assert r["error"] == "municipio_desconocido"
    assert "codigo_municipio" not in r
    assert r["pregunta"]


def test_un_nombre_ambiguo_se_pregunta_en_vez_de_elegirse(monkeypatch):
    """El registro de hoy es una semilla de 31 municipios y no tiene homónimos,
    así que la rama se prueba con un registro doble. Es la rama que más importa:
    elegir «el más poblado» sería un repliegue silencioso con buena cara."""

    class RegistroFalso:
        municipios = {
            "16078": {"codigo": "16078", "nombre": "Cuenca", "provincia": "16"},
            "99999": {"codigo": "99999", "nombre": "Cuenca", "provincia": "44"},
        }
        provincias = {
            "16": {"codigo": "16", "nombre": "Cuenca"},
            "44": {"codigo": "44", "nombre": "Teruel"},
        }

        def buscar_municipio(self, texto, provincia=None):
            return ["16078", "99999"]

    monkeypatch.setattr(territorial, "_registro_geografico", lambda: RegistroFalso())
    r = territorial.resolver_ambito("Cuenca")

    assert r["ok"] is False
    assert r["error"] == "municipio_ambiguo"
    assert len(r["candidatos"]) == 2
    assert "provincia" in r["pregunta"].lower()


# --- normativa.reglas_aplicables --------------------------------------------

def test_reglas_aplicables_declara_lo_que_no_cubre():
    """El corpus está en transcripción, y la respuesta lo dice en vez de callarlo."""
    r = reglas.reglas_aplicables(
        "28079", "residencial.vivienda_libre", "plurifamiliar", "2026-01-01"
    )

    assert r["ok"] is True
    assert r["completo"] is False
    assert len(r["materias_sin_cobertura"]) >= 1
    assert "seguridad_incendio" in r["materias_sin_cobertura"] or any(
        n["materia"] == "seguridad_incendio" for n in r["normas"]
    )
    assert r["aviso_de_corpus"]

    piloto = [n for n in r["normas"] if n["concept_id"] == CID_EVACUACION]
    assert len(piloto) == 1
    assert piloto[0]["cita"].startswith("Real Decreto RD 314/2006")


def test_un_codigo_que_no_es_del_registro_se_rechaza_con_motivo():
    r = reglas.reglas_aplicables("00000", "residencial.vivienda_libre", "plurifamiliar")

    assert r["ok"] is False
    assert r["error"] == "codigo_municipio_desconocido"
    assert "territorial.resolver_ambito" in r["detalle"]


def test_un_perfil_invalido_devuelve_los_valores_admitidos():
    """El rechazo trae lo que hace falta para reintentar sin adivinar."""
    r = reglas.reglas_aplicables("28079", "residencial.vivienda_libre", "chalecito")

    assert r["ok"] is False
    assert r["error"] == "perfil_invalido"
    assert "plurifamiliar" in r["tipologias_admitidas"]


# --- normativa.umbral_de_regla ----------------------------------------------

@pytest.mark.parametrize(
    "ejes, esperado",
    [
        ({"numero_salidas": "una", "condicion": "general"}, 25),
        ({"numero_salidas": "una", "condicion": "uso_aparcamiento"}, 35),
        ({"numero_salidas": "varias", "condicion": "general"}, 50),
        (
            {
                "numero_salidas": "varias",
                "condicion": "espacio_al_aire_libre_riesgo_irrelevante",
            },
            75,
        ),
    ],
)
def test_el_umbral_sale_de_la_tabla_3_1_del_db_si(ejes, esperado):
    """Las cuatro filas comprobadas contra el literal transcrito del PDF oficial."""
    r = reglas.umbral_de_regla(CID_EVACUACION, "es", ejes)

    assert r["ok"] is True
    assert r["valor"] == esperado
    assert r["unidad"] == "m"
    assert r["traza"][-1].startswith("coincidencia exacta")
    assert r["cita"].startswith(
        "RD 314/2006, DB-SI, SI 3, apartado 3, tabla 3.1 (BOE-A-2006-5515)")
    # La fecha/estado de validación va JUNTO a la cita, visible, no
    # escondida (encargo de Pablo, 2026-08-22) — y el enlace, aparte.
    assert "pendiente de validación profesional" in r["cita"]
    assert r["validacion"]["estado"] == "pendiente"
    assert r["fuente_url"] == "https://www.boe.es/eli/es/rd/2006/03/17/314/con"
    assert r["pendiente_de_firma_colegiada"] is True


def test_sin_ejes_no_hay_numero_y_si_hay_pregunta():
    """La propiedad que sostiene todo lo demás: no saber se dice, no se rellena."""
    r = reglas.umbral_de_regla(CID_EVACUACION, "es", {})

    assert r["ok"] is True          # la consulta funcionó
    assert r["valor"] is None       # y su respuesta es «no lo sé»
    assert r["motivo"]
    assert r["ejes_de_la_regla"] == ["numero_salidas", "condicion"]
    assert r["valores_admitidos_por_eje"]["numero_salidas"] == ["una", "varias"]
    assert "numero_salidas" in r["pregunta"]


def test_un_eje_a_medias_tampoco_coge_la_fila_mas_parecida():
    r = reglas.umbral_de_regla(CID_EVACUACION, "es", {"numero_salidas": "una"})

    assert r["valor"] is None
    assert "no evaluable" in r["traza"][-1]


def test_una_regla_que_no_esta_transcrita_se_dice_asi():
    r = reglas.umbral_de_regla("es.inventada.regla_que_no_existe", "es")

    assert r["ok"] is False
    assert r["error"] == "regla_no_encontrada"
    assert "valor" not in r
    assert CID_EVACUACION in r["reglas_disponibles"]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
