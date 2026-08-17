"""Errores del subsistema normativo.

Todos comparten un principio: **nunca silencio**. Un municipio que no está en
el registro, un nombre ambiguo o un fichero de corpus inválido producen un
error explícito, jamás un repliegue callado a otro ámbito ni a un valor por
defecto. Es la traducción a excepciones del Bug #1 de `TECH_REVIEW.md`
(tipología/zona_cte replegando en silencio) llevado a la capa normativa.
"""
from __future__ import annotations

from typing import List


class ErrorNormativa(Exception):
    """Raíz de todos los errores del paquete."""


class AmbitoDesconocido(ErrorNormativa):
    """El municipio (o comunidad/provincia) no está en el registro geográfico.

    No significa "no tiene normativa": significa que no sabemos que exista.
    Las dos cosas se responden distinto y no deben confundirse.
    """

    def __init__(self, texto: str, nivel: str = "municipio"):
        self.texto = texto
        self.nivel = nivel
        super().__init__(
            f"No hay ningún {nivel} llamado «{texto}» en el registro geográfico. "
            f"El registro de municipios está incompleto (ver "
            f"normativa/geografia/es/_registro.yaml): que no aparezca no implica "
            f"que no exista."
        )


class AmbitoAmbiguo(ErrorNormativa):
    """El nombre corresponde a más de un ámbito. Se pregunta, no se elige.

    Elegir por el usuario (el más poblado, el primero alfabéticamente) sería
    un repliegue silencioso disfrazado de conveniencia.
    """

    def __init__(self, texto: str, candidatos: List[dict]):
        self.texto = texto
        self.candidatos = candidatos
        detalle = ", ".join(f"{c['nombre']} ({c['codigo']})" for c in candidatos[:8])
        super().__init__(
            f"«{texto}» corresponde a {len(candidatos)} municipios: {detalle}. "
            f"Hace falta la provincia para desambiguar."
        )


class CorpusInvalido(ErrorNormativa):
    """Un fichero del corpus no supera la validación de carga.

    El loader es fail-closed: esa materia de ese ámbito queda `sin_cobertura`.
    Nunca se carga "lo que sí funciona": un informe que afirma cumplimiento
    sobre un corpus mutilado sin que nadie lo sepa es el peor resultado
    posible.
    """

    def __init__(self, ruta: str, fallos: List[str]):
        self.ruta = ruta
        self.fallos = fallos
        super().__init__(f"{ruta}: {len(fallos)} fallo(s) de validación:\n  - " + "\n  - ".join(fallos))


class RegistroIncompleto(ErrorNormativa):
    """El registro geográfico no se puede cargar o está mal formado."""


class CoberturaInsuficiente(ErrorNormativa):
    """Falta normativa exigible a este proyecto: el motor NO continúa.

    Es el cierre fail-closed de la Fase 1, y el error que más veces se va a
    levantar mientras el corpus esté vacío. Eso es correcto: la alternativa —
    devolver las reglas que sí tenemos— produce una lista que el arquitecto
    leerá como "esto es todo lo que aplica a mi proyecto". Nadie lee una lista
    de normativa esperando que le falten materias enteras.

    El mensaje enumera cada materia que falta con su ámbito competente y su
    estado de cobertura, porque "falta normativa" sin decir cuál no es
    accionable: no se puede encargar la transcripción de algo sin nombre.
    """

    def __init__(self, cadena: str, faltantes: List[str], preguntas: List[str] = None):
        self.cadena = cadena
        self.faltantes = faltantes
        self.preguntas = preguntas or []
        detalle = "\n  - ".join(faltantes)
        mensaje = (
            f"No se puede determinar la normativa aplicable a este proyecto: faltan "
            f"{len(faltantes)} materia(s) exigible(s) sobre las que no hay cobertura "
            f"declarada.\n\nCadena territorial: {cadena}\n\nFalta:\n  - {detalle}"
        )
        if self.preguntas:
            mensaje += "\n\nAdemás, quedan sin decidir (no bloquean, pero cambian el resultado):\n  - "
            mensaje += "\n  - ".join(self.preguntas)
        mensaje += (
            "\n\nQue no tengamos una materia NO significa que el proyecto no esté sujeto "
            "a ella. Significa que no la hemos transcrito, y por eso no se emite un "
            "resultado parcial que se leería como completo."
        )
        super().__init__(mensaje)
