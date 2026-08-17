# -*- coding: utf-8 -*-
"""G8 — golden de FORMA: qué garantiza que los otros siete sirvan de algo.

Ejecutar:  python tests/test_golden_determinismo.py

Los siete goldens anteriores comparan contenido. Éste comprueba el continente:
que los fixtures están en forma canónica, que ningún número lleva más
decimales de los que la máquina puede reproducir, y que ninguno ha cambiado
sin que nadie lo mirara.

Cuatro propiedades, todas sobre los fixtures ya escritos en disco:

1. **Forma canónica.** Cada fichero es byte a byte igual a `canonico(cargar(f))`:
   claves ordenadas, sangría de 2, UTF-8, salto de línea final, y **LF**. Sin
   la última condición, un `git config core.autocrlf` distinto rompería los
   ocho goldens a la vez en Windows sin que nada hubiera cambiado.
2. **Redondeo a 3 decimales.** Ningún float con más precisión de la que el
   contrato admite (C7.1). Un solo número con 17 decimales convierte un golden
   en una lotería entre máquinas.
3. **Manifiesto sellado.** Se congela el `sha256` de los otros siete. Si
   alguien recaptura G1 sin querer, G8 falla y lo dice. Es deliberado: obliga
   a que toda recaptura sea consciente, que es la única disciplina que
   mantiene vivo un golden master.
4. **Inventario de campos con nombre de formato.** El principio P6 del
   documento de diseño dice que el modelo común no puede tener campos llamados
   `capa`, `layer`, `block` o `guid` fuera de la procedencia. Hoy los hay, en
   el lector y en la API. Este inventario los enumera para que E1 sepa
   exactamente cuáles no debe arrastrar — y para que ninguno nuevo aparezca
   sin que se note.

**Este golden es insensible a las mutaciones K1–K4 a propósito**, y eso no es
un hueco de la red: no vigila el comportamiento del pipeline (para eso están
G1–G7), sino la integridad de los ficheros con que se vigila. Las mutaciones
del canario ocurren en memoria y nunca tocan el disco.
"""
import hashlib
import json
import os
import re

import golden

OTROS = tuple(n for n in golden.NOMBRES if n != "G8_determinismo")

# `capa`/`layer` son nombres de formato (una capa es un concepto de DXF, no de
# arquitectura). `procedencia` es el único sitio donde el contrato C7.6 los
# admite — y en E0 ese objeto todavía no existe, así que hoy todos son deuda.
_CAMPOS_DE_FORMATO = re.compile(r"^(capa|capa_elegida|layer|block|bloque|handle|guid)$")

_DECIMALES = re.compile(r"^-?\d+\.(\d+)$")


def _rutas(dato, ruta=""):
    if isinstance(dato, dict):
        for clave, valor in sorted(dato.items()):
            yield "%s.%s" % (ruta, clave), clave, valor
            yield from _rutas(valor, "%s.%s" % (ruta, clave))
    elif isinstance(dato, list):
        for i, valor in enumerate(dato):
            yield from _rutas(valor, "%s[%d]" % (ruta, i))


def _floats_con_exceso(texto):
    """Números del JSON con más de 3 decimales, leídos del TEXTO y no del
    objeto: `json.loads` ya normaliza, y aquí lo que se vigila es lo escrito."""
    excesos = []
    for bruto in re.findall(r"-?\d+\.\d+", texto):
        m = _DECIMALES.match(bruto)
        if m and len(m.group(1)) > golden.DECIMALES:
            excesos.append(bruto)
    return sorted(set(excesos))


def construir():
    manifiesto = []
    excesos_totales = []
    campos_formato = []
    campos_formato_admitidos = []
    no_canonicos = []

    for nombre in OTROS:
        ruta = golden.ruta_fixture(nombre)
        if not os.path.exists(ruta):
            manifiesto.append({"nombre": nombre, "estado": "FALTA"})
            continue
        with open(ruta, "rb") as fh:
            crudo = fh.read()
        texto = crudo.decode("utf-8")
        dato = json.loads(texto)

        # 1. forma canónica + LF + salto final
        if golden.canonico(dato) != texto:
            no_canonicos.append(nombre)
        # 2. redondeo
        for bruto in _floats_con_exceso(texto):
            excesos_totales.append("%s: %s" % (nombre, bruto))
        # 4. inventario de campos con nombre de formato, separando los que el
        #    contrato C7.6 SÍ admite (dentro de `procedencia`) de la deuda.
        for ruta_json, clave, _valor in _rutas(dato):
            if not _CAMPOS_DE_FORMATO.match(str(clave)):
                continue
            entrada = "%s%s" % (nombre, ruta_json)
            if ruta_json.endswith(".procedencia.%s" % clave):
                campos_formato_admitidos.append(entrada)
            else:
                campos_formato.append(entrada)

        manifiesto.append({
            "nombre": nombre,
            "sha256": hashlib.sha256(crudo).hexdigest(),
            "bytes": len(crudo),
            "lineas": texto.count("\n"),
            "crlf": b"\r\n" in crudo,
        })

    return {
        "n_fixtures": len(OTROS),
        "manifiesto": manifiesto,
        "fixtures_no_canonicos": sorted(no_canonicos),
        "floats_con_mas_de_3_decimales": sorted(excesos_totales),
        # Deuda del principio P6, enumerada. Los de G1 y G6 son del lector y
        # del contrato público de hoy y se quedan; lo que importa es que la
        # lista no crezca, y sobre todo que el modelo (G9) no aporte ninguno.
        "campos_con_nombre_de_formato": sorted(set(campos_formato)),
        # Los que el contrato C7.6 sí admite: dentro de `procedencia`, que es
        # el único sitio del modelo donde puede vivir un nombre de formato.
        "n_campos_de_formato_en_procedencia": len(set(campos_formato_admitidos)),
        "modelo_sin_deuda_de_formato": not any(
            e.startswith("G9_modelo") for e in campos_formato),
    }


def ejecutar_golden() -> int:
    return golden.ejecutar("G8_determinismo", construir,
                           "forma canonica, redondeo y manifiesto sellado")


if __name__ == "__main__":
    raise SystemExit(ejecutar_golden())
