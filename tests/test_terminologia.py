# -*- coding: utf-8 -*-
"""El corpus de terminologia se ingiere y se consulta sin deformarse.

Ejecutar:  python tests/test_terminologia.py

Rapido (<2 s): lee el PDF cacheado del DB-SI y el XML del BOE ya presentes
en el repositorio. No hay red.

Que protege (Bloque 0, docs/design/DB-SI_DECISIONS.md D5):

1. Que el Anejo SI A se siga segmentando (P5.1). El pipeline lo saltaba por
   un filtro `tipos_segmento={"apartado"}`, no porque el segmentador no
   supiera; si alguien toca el segmentador, esto lo nota.
2. Que la extraccion sea DETERMINISTA. Una definicion se copia, no se
   infiere: si algun dia esto pasa por un modelo, el literal dejaria de ser
   citable.
3. Que las definiciones NO se guarden como reglas evaluables (P5.2). Es la
   condicion explicita del encargo.
4. Que un termino ausente falle RUIDOSAMENTE. La alternativa -devolver la
   definicion del vecino- es un error que nadie ve leyendo el YAML.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from extraccion.segmentador_pdf import DocumentoOficial, segmentar  # noqa: E402
from extraccion.terminologia import (  # noqa: E402
    TerminoNoEncontrado,
    extraer_de_anejo_boe,
    extraer_de_anejo_pdf,
)
from ingesta.fuentes.codigotecnico import _texto_desde_pdf  # noqa: E402
from normativa import definiciones  # noqa: E402

PDF = os.path.join(RAIZ, "ingesta", "estado", "cache",
                   "codigotecnico__DB-SI__0a2e78cd6247.pdf")
XML = os.path.join(RAIZ, "tests", "fixtures", "boe", "BOE-A-2006-5515.xml")

fallos = []
comprobaciones = 0


def check(condicion, titulo, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s" % ("OK  " if condicion else "FALLO", titulo))
    if detalle:
        print("         %s" % detalle)
    if not condicion:
        fallos.append(titulo)


print("A. P5.1 - el segmentador ingiere el Anejo SI A")

raw = open(PDF, "rb").read()
doc = DocumentoOficial(
    identificador="DB-SI", fuente="codigotecnico", titulo="DB-SI", organismo="",
    rango_codigo=None, rango_nombre=None, numero_oficial=None,
    fecha_publicacion=None, fecha_disposicion=None, fecha_actualizacion=None,
    url_oficial="", url_xml="", texto_crudo=_texto_desde_pdf("DB-SI", raw),
    hash_texto="x", formato="pdf", bytes_crudos=raw,
)
segmentos = segmentar(doc)
anejos = [s for s in segmentos if s.tipo_segmento == "anejo"]
anejo_a = [s for s in anejos if s.id == "dbsi_anejo_a"]

check(len(segmentos) == 31, "el DB-SI da 31 segmentos", "%d" % len(segmentos))
check(len(anejos) == 6, "6 de ellos son anejos", "%d" % len(anejos))
check(bool(anejo_a), "el Anejo SI A esta entre ellos")
check(anejo_a and len(anejo_a[0].texto) > 30000,
      "y trae el cuerpo completo, no solo el titulo",
      "%d caracteres" % (len(anejo_a[0].texto) if anejo_a else 0))

print("\nB. La extraccion es determinista y literal")

TERMINOS = ["Superficie util".replace("util", "útil"),
            "Origen de evacuación", "Uso Residencial Vivienda"]
extraidas = extraer_de_anejo_pdf(anejo_a[0].texto, TERMINOS)
otra_vez = extraer_de_anejo_pdf(anejo_a[0].texto, TERMINOS)

check([d.literal for d in extraidas] == [d.literal for d in otra_vez],
      "dos extracciones seguidas dan el mismo texto")

superficie = [d for d in extraidas if d.termino.startswith("Superficie")][0]
check(superficie.literal.startswith("Superficie en planta de un recinto, sector o edificio"),
      "«Superficie util» empieza por el texto del anejo",
      superficie.literal[:70] + "...")
check("ocupable por las personas" in superficie.literal.replace("ocup able", "ocupable"),
      "y contiene el nucleo de la definicion (ocupable por las personas)")

origen = [d for d in extraidas if d.termino.startswith("Origen")][0]
check("exceptuando los del interior de las viviendas" in origen.literal,
      "«Origen de evacuacion» excluye el interior de las viviendas",
      "es la cita que invalida el ambito actual de R17")

vivienda = [d for d in extraidas if d.termino.startswith("Uso Residencial")][0]
check("unifamiliar" in vivienda.literal and "edificio de pisos" in vivienda.literal,
      "«Uso Residencial Vivienda» cubre unifamiliar y plurifamiliar")

print("\nC. Un termino ausente falla ruidosamente")

try:
    extraer_de_anejo_pdf(anejo_a[0].texto, ["Termino Que No Existe En El Anejo"])
    check(False, "un termino inexistente lanza TerminoNoEncontrado")
except TerminoNoEncontrado:
    check(True, "un termino inexistente lanza TerminoNoEncontrado",
          "no devuelve la definicion del vecino ni texto a medias")

print("\nD. El Anejo III de la Parte I del CTE (BOE) tambien")

xml = open(XML, "rb").read().decode("utf-8")
uso = extraer_de_anejo_boe(xml, ["Uso previsto"])[0]
check("se debe reflejar documentalmente" in uso.literal,
      "«Uso previsto» dice que se debe reflejar documentalmente",
      "declararlo en el formulario no es exigencia nuestra: CAP-2")

print("\nE. P5.2 - se consultan como fuente normativa, no como reglas")

d = definiciones.buscar("superficie util".replace("util", "útil"))
check(d is not None, "el corpus responde a una consulta por termino")
check(d is not None and d.documento_basico == "DB-SI" and d.anejo == "SI A",
      "y trae su localizador jerarquico",
      d.cita if d else "")
check(d is not None and d.verificada_por_humano is False,
      "la transcripcion NO se marca como verificada por humano",
      "regla de dos personas (NORMATIVE_ENGINE.md §12): una maquina no es la segunda")
check(d is not None and bool(d.anomalias_conocidas),
      "las anomalias del PDF quedan declaradas, no corregidas")

check(definiciones.buscar("SUPERFICIE UTIL") is not None,
      "la busqueda no depende de mayusculas ni acentos")
check(definiciones.buscar("termino inexistente") is None,
      "un termino no cargado devuelve None (sin_cobertura), no una excepcion")

previsto = definiciones.buscar("Uso previsto")
check(previsto is not None and previsto.documento_basico == "CTE Parte I",
      "la precedencia hacia el Anejo III del CTE funciona",
      previsto.cita if previsto else "")

check(len(definiciones.terminos()) >= 8,
      "hay al menos las 8 definiciones del Bloque A",
      "%d cargadas: %s" % (len(definiciones.terminos()), ", ".join(definiciones.terminos())))

print("\nF. La terminologia no contamina el corpus de reglas")

from normativa import loader  # noqa: E402

rutas = loader.descubrir(["es"])
check(not any("terminologia" in str(p) for p in rutas),
      "loader.descubrir() no recoge los glosarios",
      "%d ficheros de reglas descubiertos" % len(rutas))
check("terminologia" in loader.DIRECTORIOS_DE_DATOS,
      "pero el arbol si esta declarado como capa de datos",
      "asi la frontera F2 (nada de .py dentro) lo vigila")

print("\n" + "=" * 60)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
