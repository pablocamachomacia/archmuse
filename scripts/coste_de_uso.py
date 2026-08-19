# -*- coding: utf-8 -*-
"""Cuánto ha costado lo que ArchMuse ya ha ejecutado, y en qué se ha ido.

    python scripts/coste_de_uso.py [ruta_al_jsonl]

Lee el registro que escribe `ia/uso.py` en cada llamada a un modelo y lo
agrega **por punto de llamada y por modelo**. Es la respuesta con datos a la
pregunta que hasta la tarea SEG-4 no la tenía: cuánto cuesta un análisis
completo. Sin ella no hay precio defendible (`INF-9`) ni forma de decidir el
modelo de cada perfil midiendo en vez de por intuición (`AG-3`).

Da euros sólo si `ARCHMUSE_EUR_POR_USD` declara un tipo de cambio; si no, da
dólares, que es la moneda de la tarifa. Convertir con un cambio inventado
produce una cifra que parece contable y no lo es.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from ia import uso  # noqa: E402


def main(argv: list) -> int:
    ruta = argv[1] if len(argv) > 1 else uso.ruta_registro()
    d = uso.desglose_de_registro(ruta)
    print("Registro: %s" % ruta)
    if not d["llamadas"]:
        print("Sin llamadas registradas. ¿Se ha ejecutado algo que use un modelo?")
        return 0
    print(uso.a_texto(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
