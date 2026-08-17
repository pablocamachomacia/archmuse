# -*- coding: utf-8 -*-
"""Prueba de `analyzer/pliego_extractor.py` + la persistencia de `pliegos`.

Ejecutar:  python tests/test_pliego_extractor.py

Sin dependencias, mismo runner que `tests/test_storage.py`: script que sale
con código 1 si algo falla. Todo lo de aquí es DETERMINISTA -- no hay ningún
pliego PDF real de fixture todavía (haría falta uno real de Pablo, ver §12
del PRD), así que `_convertir()` se prueba directamente con diccionarios que
imitan lo que la herramienta forzada le haría rellenar al modelo, sin llamar
a la API. `extraer_parametros_pliego()` (la llamada real) no se prueba aquí.
"""
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

TMP = tempfile.mkdtemp(prefix="archmuse_test_pliego_")
os.environ["ARCHMUSE_DATA_DIR"] = TMP

from analyzer import storage  # noqa: E402
from analyzer.hechos import UNKNOWN, hecho_a_dict  # noqa: E402
from analyzer.pliego_extractor import (  # noqa: E402
    _NOMBRES_CAMPOS,
    _convertir,
    _tool_schema,
)

fallos = []


def check(nombre, cond, detalle=""):
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


print("1. Esquema de la herramienta")
schema = _tool_schema()
props = schema["input_schema"]["properties"]
check("trae los 17 campos + no_es_pliego", set(props) == set(_NOMBRES_CAMPOS) | {"no_es_pliego"})
check("todos los 17 son required", set(schema["input_schema"]["required"]) == set(_NOMBRES_CAMPOS) | {"no_es_pliego"})
check(
    "regimen_proteccion tiene el enum cerrado pedido",
    props["regimen_proteccion"]["properties"]["valor"]["enum"] == ["VPP", "VPPA", "libre"],
)
check(
    "mix_tipologias.valor es una lista de objetos con tipo/porcentaje",
    props["mix_tipologias"]["properties"]["valor"]["items"]["required"] == ["tipo", "porcentaje"],
)

print("\n2. Conversión — pliego bien encontrado")
bruto_ok = {n: {"encontrado": False} for n in _NOMBRES_CAMPOS}
bruto_ok["no_es_pliego"] = False
bruto_ok["municipio"] = {"encontrado": True, "valor": "Alcorcón", "cita": "sito en el término de Alcorcón", "confianza": "Alta"}
bruto_ok["num_viviendas_minimo"] = {"encontrado": True, "valor": 20, "cita": "no menos de 20 viviendas", "confianza": "Alta"}
bruto_ok["mix_tipologias"] = {
    "encontrado": True,
    "valor": [{"tipo": "2 dormitorios", "porcentaje": 60, "sup_util_min": 60, "sup_util_max": 70}],
    "cita": "tabla anexa", "confianza": "Media",
}
resultado = _convertir(bruto_ok, "pliego_alcorcon.pdf")
check("es_pliego True", resultado.es_pliego is True)
check("municipio KNOWN", resultado.hechos["municipio"].estado != UNKNOWN)
check("municipio.valor correcto", resultado.hechos["municipio"].valor == "Alcorcón")
check("municipio.fuente cita el archivo", resultado.hechos["municipio"].fuente == "pliego:pliego_alcorcon.pdf")
check("num_viviendas_minimo = 20", resultado.hechos["num_viviendas_minimo"].valor == 20)
check("mix_tipologias trae la fila", len(resultado.hechos["mix_tipologias"].valor) == 1)
check("pem_maximo_euros (no citado) es UNKNOWN", resultado.hechos["pem_maximo_euros"].estado == UNKNOWN)
check("un UNKNOWN lleva motivo", bool(resultado.hechos["pem_maximo_euros"].motivos))

dict_municipio = hecho_a_dict(resultado.hechos["municipio"])
check("hecho_a_dict: no_encontrado False para municipio", dict_municipio["no_encontrado"] is False)
dict_pem = hecho_a_dict(resultado.hechos["pem_maximo_euros"])
check("hecho_a_dict: no_encontrado True para pem_maximo_euros", dict_pem["no_encontrado"] is True)
check("hecho_a_dict: motivo presente en el no encontrado", bool(dict_pem["motivo"]))

print("\n3. Conversión — documento que no es un pliego")
bruto_no_pliego = {n: {"encontrado": False} for n in _NOMBRES_CAMPOS}
bruto_no_pliego["no_es_pliego"] = True
resultado_no = _convertir(bruto_no_pliego, "otro.pdf")
check("es_pliego False", resultado_no.es_pliego is False)

print("\n4. Nunca confía en «encontrado» sin valor utilizable")
bruto_raro = {n: {"encontrado": False} for n in _NOMBRES_CAMPOS}
bruto_raro["no_es_pliego"] = False
bruto_raro["altura_maxima_plantas"] = {"encontrado": True}  # sin "valor" -- respuesta inconsistente
bruto_raro["normativa_aplicable"] = {"encontrado": True, "valor": []}  # lista vacía
resultado_raro = _convertir(bruto_raro, "raro.pdf")
check("altura_maxima_plantas degrada a UNKNOWN", resultado_raro.hechos["altura_maxima_plantas"].estado == UNKNOWN)
check("normativa_aplicable (lista vacía) degrada a UNKNOWN", resultado_raro.hechos["normativa_aplicable"].estado == UNKNOWN)

print("\n5. Confianza fuera de catálogo se descarta, no rompe")
bruto_confianza_mala = {n: {"encontrado": False} for n in _NOMBRES_CAMPOS}
bruto_confianza_mala["no_es_pliego"] = False
bruto_confianza_mala["parcela"] = {"encontrado": True, "valor": "R-3", "confianza": "muy_segura"}
resultado_cm = _convertir(bruto_confianza_mala, "x.pdf")
check("confianza inválida -> None, no excepción", resultado_cm.hechos["parcela"].confianza is None)

print("\n6. Persistencia (`storage.pliegos`)")
storage.init_db()
parametros = {n: hecho_a_dict(h) for n, h in resultado.hechos.items()}
meta = storage.guardar_pliego("pliego_alcorcon.pdf", b"%PDF-1.4 contenido falso", parametros, es_pliego=True)
check("devuelve un id de 12 hex", len(meta["id"]) == 12 and all(c in "0123456789abcdef" for c in meta["id"]))
check("proyecto_id nace NULL", meta["proyecto_id"] is None)

recuperado = storage.obtener_pliego(meta["id"])
check("se recupera", recuperado is not None)
check("nombre_archivo intacto", recuperado["nombre_archivo"] == "pliego_alcorcon.pdf")
check(
    "parametros idénticos a lo guardado",
    json.dumps(recuperado["parametros"], sort_keys=True) == json.dumps(parametros, sort_keys=True),
)
check("no incluye el PDF binario", "pdf" not in recuperado)

check("ids hostiles rechazados", storage.obtener_pliego("../../etc/passwd") is None)
check("id inexistente -> None", storage.obtener_pliego("0" * 12) is None)

print("\n7. Vincular a un proyecto")
check("vincular con proyecto_id inexistente devuelve False", storage.vincular_pliego_proyecto(meta["id"], "1" * 12) is False)
check(
    "vincular con id de pliego inválido devuelve False",
    storage.vincular_pliego_proyecto("no-es-un-id", "1" * 12) is False,
)
with open(os.path.join(RAIZ, "tests", "fixtures", "ejemplo-dxf-analisis.json"), encoding="utf-8") as fh:
    fixture_proyecto = json.load(fh)
meta_proyecto = storage.guardar_proyecto(json.loads(json.dumps(fixture_proyecto)), origen="dxf")
check(
    "vincular con proyecto real devuelve True",
    storage.vincular_pliego_proyecto(meta["id"], meta_proyecto["id"]) is True,
)
check(
    "el pliego recuperado ya lleva el proyecto_id",
    storage.obtener_pliego(meta["id"])["proyecto_id"] == meta_proyecto["id"],
)

import shutil  # noqa: E402

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 55)
if fallos:
    print("FALLOS (%d): %s" % (len(fallos), ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK")
