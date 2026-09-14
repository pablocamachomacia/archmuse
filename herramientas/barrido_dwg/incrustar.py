"""Convierte una sonda AutoLISP en un script `.scr` de AutoCAD Core Console.

Uso: python incrustar.py <sonda.lsp> <funcion> <salida.tsv> <script.scr>

Por qué no un `(load …)`: Core Console aplica SECURELOAD y cancela la carga de
un fichero fuera de las rutas de confianza. Así que la sonda va dentro del
script, una forma por línea. Sin líneas en blanco: en un `.scr` una línea vacía
repite el último comando. Ver `LEEME.md`.
"""
import pathlib
import sys


def formas_de(texto: str) -> list:
    formas, actual, profundidad = [], [], 0
    for linea in texto.splitlines():
        if linea.lstrip().startswith(";"):
            continue
        if ";" in linea:
            raise ValueError("';' dentro de código: el conversor no sabe separarlo "
                             "de un comentario. Línea: %s" % linea)
        if not linea.strip():
            continue
        actual.append(linea.strip())
        profundidad += linea.count("(") - linea.count(")")
        if profundidad == 0:
            formas.append(" ".join(actual))
            actual = []
    if profundidad or actual:
        raise ValueError("paréntesis desparejados")
    return formas


def main(argv: list) -> None:
    lsp, funcion, salida, scr = argv[1:5]
    formas = formas_de(pathlib.Path(lsp).read_text(encoding="utf-8"))
    formas.append('(%s "%s")' % (funcion, pathlib.Path(salida).resolve().as_posix()))
    pathlib.Path(scr).write_text("\r\n".join(formas + ["_.QUIT", "_Y", ""]), encoding="ascii")
    print(len(formas), "formas")


if __name__ == "__main__":
    main(sys.argv)
