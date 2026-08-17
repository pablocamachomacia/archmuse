"""Registro geográfico: nombres escritos por un humano -> cadena de ámbitos.

Carga `normativa/geografia/es/*.yaml` y resuelve lo que el arquitecto escribe.
Es la pieza que hace cierta la promesa "añadir un municipio no toca código":
el registro es dato, y `resolver_ambito` no contiene ningún nombre de
municipio.

Regla que gobierna todo el módulo: **nunca un repliegue silencioso.** Un
municipio desconocido levanta `AmbitoDesconocido`; un nombre ambiguo levanta
`AmbitoAmbiguo` con los candidatos. Ninguno de los dos elige por el usuario.
"""
from __future__ import annotations

import functools
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .ambito import Ambito, AmbitoSectorial, CadenaAmbitos, Procedencia
from .errores import AmbitoAmbiguo, AmbitoDesconocido, RegistroIncompleto

RAIZ = Path(__file__).resolve().parent
GEOGRAFIA = RAIZ / "geografia"

# Sectoriales que el sistema sabe que existen. Que estén aquí no significa que
# apliquen: significa que hay que PREGUNTAR por ellos. Sin declarar quedan
# como `desconocido`, nunca como "no aplica".
SECTORIALES_CONOCIDOS = (
    ("patrimonio", "Protección del patrimonio histórico"),
    ("inundabilidad", "Zona inundable o de policía de cauce"),
    ("aeroportuario", "Servidumbre aeronáutica"),
    ("costas", "Servidumbre de costas"),
)


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni puntuación, espacios colapsados.

    Solo cubre lo deducible mecánicamente. Las variantes que ninguna
    normalización puede deducir (cooficiales, formas castellanas, artículos)
    van en `alias.yaml`.
    """
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = "".join(c if c.isalnum() or c.isspace() else " " for c in texto)
    return " ".join(texto.lower().split())


def _leer(ruta: Path) -> dict:
    try:
        with ruta.open(encoding="utf-8") as f:
            datos = yaml.safe_load(f)
    except FileNotFoundError as exc:
        raise RegistroIncompleto(f"Falta {ruta}") from exc
    except yaml.YAMLError as exc:
        raise RegistroIncompleto(f"{ruta} no es YAML válido: {exc}") from exc
    if not isinstance(datos, dict):
        raise RegistroIncompleto(f"{ruta} no contiene un mapa en su raíz")
    return datos


class RegistroGeografico:
    """Registro de un país. Inmutable una vez cargado."""

    def __init__(self, pais: str = "es", base: Optional[Path] = None):
        self.pais = pais
        base = base or (GEOGRAFIA / pais)
        self.base = base

        meta = _leer(base / "_registro.yaml")
        self.nombre_pais: str = meta.get("nombre", pais.upper())
        self._meta = meta

        self.comunidades: Dict[str, dict] = {
            c["codigo"]: c for c in _leer(base / "comunidades.yaml")["comunidades"]
        }
        self.provincias: Dict[str, dict] = {
            p["codigo"]: p for p in _leer(base / "provincias.yaml")["provincias"]
        }
        self.municipios: Dict[str, dict] = {
            m["codigo"]: m for m in _leer(base / "municipios.yaml")["municipios"]
        }
        self.alias: Dict[str, str] = _leer(base / "alias.yaml").get("alias") or {}

        self._indice_municipios = self._construir_indice(self.municipios)
        self._indice_comunidades = self._construir_indice(self.comunidades)
        self._indice_provincias = self._construir_indice(self.provincias)
        for forma, codigo in self.alias.items():
            self._indice_municipios.setdefault(normalizar(forma), []).append(codigo)

        self._validar()

    # -- construcción -------------------------------------------------------

    @staticmethod
    def _construir_indice(registros: Dict[str, dict]) -> Dict[str, List[str]]:
        """Índice nombre normalizado -> códigos. Una entrada por cada forma
        de un nombre con barra ("Elx/Elche" indexa por "elx", por "elche" y
        por la forma completa), porque las denominaciones cooficiales se
        escriben indistintamente de las tres maneras."""
        indice: Dict[str, List[str]] = {}
        for codigo, r in registros.items():
            formas = {r["nombre"]}
            if "/" in r["nombre"]:
                formas.update(p.strip() for p in r["nombre"].split("/"))
            for forma in formas:
                indice.setdefault(normalizar(forma), []).append(codigo)
        return indice

    def _validar(self) -> None:
        """El registro se valida a sí mismo al cargar: una referencia rota
        aquí envenena toda resolución posterior."""
        fallos = []
        for cod, p in self.provincias.items():
            if p["comunidad"] not in self.comunidades:
                fallos.append(f"provincia {cod} apunta a comunidad inexistente {p['comunidad']}")
        for cod, m in self.municipios.items():
            if m["provincia"] not in self.provincias:
                fallos.append(f"municipio {cod} apunta a provincia inexistente {m['provincia']}")
            if not cod.startswith(m["provincia"]):
                fallos.append(f"municipio {cod} no empieza por su provincia {m['provincia']}")
        for forma, cod in self.alias.items():
            if cod not in self.municipios:
                fallos.append(f"alias «{forma}» apunta a municipio inexistente {cod}")
        if fallos:
            raise RegistroIncompleto("Registro geográfico incoherente:\n  - " + "\n  - ".join(fallos))

    # -- procedencia --------------------------------------------------------

    @property
    def procedencia(self) -> Procedencia:
        n = self._meta.get("niveles", {}).get("municipios", {})
        return Procedencia(
            origen=n.get("origen", "desconocido"),
            verificado=bool(n.get("verificado", False)),
            aviso=n.get("aviso"),
        )

    # -- consulta -----------------------------------------------------------

    def buscar_municipio(self, texto: str, provincia: Optional[str] = None) -> List[str]:
        """Códigos que casan con `texto`, filtrados por provincia si se da."""
        codigos = list(dict.fromkeys(self._indice_municipios.get(normalizar(texto), [])))
        if provincia:
            cod_prov = self.codigo_provincia(provincia)
            codigos = [c for c in codigos if self.municipios[c]["provincia"] == cod_prov]
        return codigos

    def codigo_comunidad(self, texto: str) -> Optional[str]:
        if texto in self.comunidades:
            return texto
        cands = self._indice_comunidades.get(normalizar(texto), [])
        return cands[0] if len(cands) == 1 else None

    def codigo_provincia(self, texto: str) -> Optional[str]:
        if texto in self.provincias:
            return texto
        cands = self._indice_provincias.get(normalizar(texto), [])
        return cands[0] if len(cands) == 1 else None

    # -- resolución ---------------------------------------------------------

    def cadena_de_municipio(self, codigo: str) -> CadenaAmbitos:
        """Cadena completa desde el país hasta el municipio `codigo`."""
        m = self.municipios[codigo]
        prov = self.provincias[m["provincia"]]
        com = self.comunidades[prov["comunidad"]]
        return CadenaAmbitos(
            ambitos=(
                Ambito(self.pais, "estatal", self.pais, self.nombre_pais),
                Ambito(f"{self.pais}.{com['codigo']}", "autonomico", com["codigo"], com["nombre"]),
                Ambito(
                    f"{self.pais}.{com['codigo']}.{prov['codigo']}",
                    "provincial",
                    prov["codigo"],
                    prov["nombre"],
                ),
                Ambito(
                    f"{self.pais}.{com['codigo']}.{prov['codigo']}.{codigo}",
                    "municipal",
                    codigo,
                    m["nombre"],
                ),
            ),
            procedencia=self.procedencia,
        )


@functools.lru_cache(maxsize=4)
def _registro_cacheado(pais: str) -> RegistroGeografico:
    return RegistroGeografico(pais)


def registro(pais: str = "es") -> RegistroGeografico:
    """Registro cacheado por país. La carga es única por proceso.

    El argumento por defecto se resuelve AQUÍ y no en la función cacheada a
    propósito: `lru_cache` indexa por la tupla de argumentos recibida, así que
    `registro()` y `registro("es")` serían dos claves distintas y construirían
    dos registros independientes. Además de duplicar carga y memoria, dos
    instancias divergen en cuanto una se toca, que es como se detectó.
    """
    return _registro_cacheado(pais)


def resolver_ambito(
    pais: str = "es",
    comunidad: Optional[str] = None,
    provincia: Optional[str] = None,
    municipio: Optional[str] = None,
    sectoriales: Optional[Dict[str, Optional[bool]]] = None,
) -> CadenaAmbitos:
    """Resuelve lo que el usuario declara en una `CadenaAmbitos`.

    Acepta códigos o nombres (con o sin tildes, cooficiales, alias). Se puede
    declarar solo el municipio: comunidad y provincia se derivan de su código,
    que es lo que permite un formulario de dos campos en vez de cuatro.

    Levanta `AmbitoDesconocido` si no existe y `AmbitoAmbiguo` si el nombre
    corresponde a varios municipios. **Nunca elige por el usuario.**
    """
    reg = registro(_codigo_pais(pais))

    if municipio:
        codigos = reg.buscar_municipio(municipio, provincia)
        if not codigos:
            raise AmbitoDesconocido(municipio, "municipio")
        if len(codigos) > 1:
            raise AmbitoAmbiguo(
                municipio,
                [
                    {
                        "codigo": c,
                        "nombre": reg.municipios[c]["nombre"],
                        "provincia": reg.provincias[reg.municipios[c]["provincia"]]["nombre"],
                    }
                    for c in codigos
                ],
            )
        cadena = reg.cadena_de_municipio(codigos[0])
    else:
        cadena = _cadena_sin_municipio(reg, comunidad, provincia)

    return _con_sectoriales(cadena, sectoriales)


def _codigo_pais(pais: str) -> str:
    p = normalizar(pais)
    if p in ("es", "espana", "spain"):
        return "es"
    raise AmbitoDesconocido(pais, "país")


def _cadena_sin_municipio(
    reg: RegistroGeografico, comunidad: Optional[str], provincia: Optional[str]
) -> CadenaAmbitos:
    """Cadena parcial: solo país, o país + comunidad (+ provincia).

    Es legítima — analizar contra CTE + normativa autonómica sin fijar
    municipio es un caso real — y lo que produce es, simplemente, ausencia de
    capa municipal, no un municipio inventado.
    """
    ambitos = [Ambito(reg.pais, "estatal", reg.pais, reg.nombre_pais)]

    cod_com = None
    if provincia:
        cod_prov = reg.codigo_provincia(provincia)
        if not cod_prov:
            raise AmbitoDesconocido(provincia, "provincia")
        cod_com = reg.provincias[cod_prov]["comunidad"]
    if comunidad:
        c = reg.codigo_comunidad(comunidad)
        if not c:
            raise AmbitoDesconocido(comunidad, "comunidad autónoma")
        if cod_com and c != cod_com:
            raise AmbitoDesconocido(
                f"{provincia} no pertenece a {comunidad}", "combinación provincia/comunidad"
            )
        cod_com = c

    if cod_com:
        com = reg.comunidades[cod_com]
        ambitos.append(Ambito(f"{reg.pais}.{cod_com}", "autonomico", cod_com, com["nombre"]))
        if provincia:
            cod_prov = reg.codigo_provincia(provincia)
            prov = reg.provincias[cod_prov]
            ambitos.append(
                Ambito(
                    f"{reg.pais}.{cod_com}.{cod_prov}", "provincial", cod_prov, prov["nombre"]
                )
            )

    return CadenaAmbitos(ambitos=tuple(ambitos), procedencia=reg.procedencia)


def _con_sectoriales(
    cadena: CadenaAmbitos, declarados: Optional[Dict[str, Optional[bool]]]
) -> CadenaAmbitos:
    """Añade los sectoriales conocidos. Los no declarados quedan como
    `desconocido` — que es una pregunta pendiente, no un "no aplica"."""
    declarados = declarados or {}
    sect = tuple(
        AmbitoSectorial(id=sid, nombre=nombre, declarado=declarados.get(sid))
        for sid, nombre in SECTORIALES_CONOCIDOS
    )
    return CadenaAmbitos(
        ambitos=cadena.ambitos, sectoriales=sect, procedencia=cadena.procedencia
    )
