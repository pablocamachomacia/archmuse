# -*- coding: utf-8 -*-
"""Carga del `.env` local (REFACTOR_MASTERPLAN tarea 3).

`.env` lleva claves reales y no se versiona; `.env.example` sí, y documenta
qué variables existen. Este módulo es el único sitio del proyecto donde se lee
el primero.

**No sobrescribe nada.** Una variable ya presente en el entorno del proceso
gana siempre sobre el `.env` (`override=False`). Así, un despliegue que exporta
sus secretos de verdad no puede quedar pisado por un archivo olvidado en el
directorio, y `ANTHROPIC_API_KEY=... pytest ...` sigue funcionando como
siempre.

**Quién lo llama:** `app.py` (el producto), `main.py` (la CLI de depuración) y
`conftest.py` (la suite). Los tres, para que `.env` signifique lo mismo en todo
el proyecto: la alternativa —que funcionara al arrancar la app pero no bajo
pytest— convierte cada entrada del bloque de tests de `.env.example` en una
trampa silenciosa.

Como `conftest.py` lo carga en `os.environ`, los 72 scripts de `tests/` que
`test_scripts_legacy.py` lanza en subprocesos también lo heredan (copian el
entorno del padre). La contrapartida, y está avisada en `.env.example` junto a
las variables afectadas: un `.env` con `ARCHMUSE_TEST_RED=1` o
`ARCHMUSE_TEST_IA=1` activa los tests que golpean boe.es, el Catastro y la API
real de Anthropic. Son las dos únicas variables con las que un `.env` puede
cambiar lo que la suite hace.
"""
from __future__ import annotations

from pathlib import Path

#: `.env` vive en la raíz del repositorio, junto a `.env.example`.
RUTA_ENV = Path(__file__).resolve().parents[1] / ".env"


def cargar_dotenv() -> bool:
    """Carga `.env` si existe. Devuelve True si se leyó el archivo.

    Si falta `python-dotenv`, avisa solo cuando hay un `.env` que leer: quien
    exporta sus variables a mano no necesita la dependencia, y no merece el
    ruido. Al revés sí importa —un `.env` presente y silenciosamente ignorado
    se diagnostica como "mi clave no funciona"—, así que ese caso sí habla.
    """
    if not RUTA_ENV.is_file():
        return False
    try:
        from dotenv import load_dotenv
    except ImportError:
        print(
            "Aviso: existe %s pero `python-dotenv` no está instalado, así que "
            "no se ha leído.\n"
            "  Instálalo con `pip install -r requirements.txt`, o exporta las "
            "variables a mano." % RUTA_ENV
        )
        return False
    return load_dotenv(RUTA_ENV, override=False)
