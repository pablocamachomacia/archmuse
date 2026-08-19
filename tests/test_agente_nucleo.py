# -*- coding: utf-8 -*-
"""El bucle del agente, de punta a punta y sin tocar la red.

**Qué se prueba aquí.** Que el recorrido completo funciona —usuario → agente →
herramienta → resultado → agente → respuesta— y, sobre todo, que las cuatro
defensas contra la invención hacen lo que dicen. Un agente que encadena
herramientas es fácil; uno del que se puede demostrar que no se inventa un
resultado es lo que este repositorio necesita, porque es lo único que un
arquitecto no perdona dos veces.

**Por qué un cliente guionizado y no la API real.** Tres motivos, y ninguno es
la comodidad:

1. Un test que llama a la API cuesta dinero cada vez que corre y da un
   resultado distinto cada vez. La suite se ejecuta en CI en cada empujón.
2. Lo que hay que fijar es el comportamiento del **bucle**, no el del modelo.
   Guionizar la respuesta del modelo es la única forma de comprobar qué hace el
   bucle cuando el modelo pide una capacidad que no existe, o cuando no para
   nunca de pedir herramientas.
3. El doble se escribe contra la misma superficie que usa producción
   (`cliente.messages.create`), así que si esa superficie cambiara, estos tests
   se enterarían.

Las herramientas, en cambio, son las **de verdad**: se ejecuta `normativa/` y
su corpus real. Guionizar también las herramientas dejaría el test probándose a
sí mismo.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from agente.capacidad import Capacidad  # noqa: E402
from agente.nucleo import ejecutar  # noqa: E402
from agente.registro import Registro, descubrir, registro  # noqa: E402

CID_EVACUACION = "es.rd_314_2006.seguridad_incendio.longitud_recorrido_evacuacion"


# --- Dobles del cliente -----------------------------------------------------

class BloqueTexto:
    type = "text"

    def __init__(self, texto: str) -> None:
        self.text = texto


class BloqueHerramienta:
    type = "tool_use"

    def __init__(self, nombre: str, entrada: dict, ident: str = "tu_1") -> None:
        self.id = ident
        self.name = nombre
        self.input = entrada


class RespuestaFalsa:
    def __init__(self, *bloques) -> None:
        self.content = list(bloques)
        self.stop_reason = (
            "tool_use" if any(b.type == "tool_use" for b in bloques) else "end_turn"
        )
        self.usage = None


class ClienteGuionizado:
    """Devuelve las respuestas del guion, en orden, y guarda lo que recibió.

    Si el guion tiene una sola entrada la repite: es lo que permite probar el
    límite de iteraciones sin escribir seis veces lo mismo.
    """

    def __init__(self, *guion) -> None:
        self._guion = list(guion)
        self.llamadas = []
        self.messages = self

    def create(self, **kwargs):
        # Copia profunda del historial: el bucle reutiliza y amplía la misma
        # lista de mensajes, así que guardar la referencia dejaría las N
        # llamadas apuntando al estado final. La API serializa en el momento de
        # la llamada; el doble tiene que hacer lo mismo para ser fiel.
        self.llamadas.append({**kwargs, "messages": copy.deepcopy(kwargs["messages"])})
        if len(self._guion) == 1:
            return self._guion[0]
        if not self._guion:
            raise AssertionError("el bucle pidió más turnos de los guionizados")
        return self._guion.pop(0)


def _resultados_devueltos(cliente) -> list:
    """Los `tool_result` que el bucle metió en el historial, ya deserializados.

    Se mira la última llamada porque el historial es acumulativo: recorrer
    todas contaría cada resultado tantas veces como turnos vinieran después.
    """
    fuera = []
    for mensaje in cliente.llamadas[-1]["messages"]:
        if mensaje["role"] != "user" or not isinstance(mensaje["content"], list):
            continue
        for bloque in mensaje["content"]:
            if bloque.get("type") == "tool_result":
                fuera.append(json.loads(bloque["content"]))
    return fuera


# --- El recorrido mínimo ----------------------------------------------------

def test_sin_herramientas_responde_directo():
    """Si no hace falta una herramienta, no se ejecuta ninguna."""
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueTexto("Hola.")))
    r = ejecutar("Hola", cliente)

    assert r.texto == "Hola."
    assert r.pasos == ()
    assert r.iteraciones == 1
    assert r.parada == "fin"


def test_una_herramienta_y_respuesta_final():
    """El recorrido completo con una sola herramienta real."""
    cliente = ClienteGuionizado(
        RespuestaFalsa(BloqueHerramienta("territorial__resolver_ambito", {"municipio": "Madrid"})),
        RespuestaFalsa(BloqueTexto("El municipio es Madrid, código INE 28079.")),
    )
    r = ejecutar("¿Qué ámbitos rigen un proyecto en Madrid?", cliente)

    assert r.parada == "fin"
    assert r.iteraciones == 2
    assert len(r.pasos) == 1

    paso = r.pasos[0]
    assert paso.capacidad == "territorial.resolver_ambito"
    assert paso.version == "1.0.0"
    assert paso.ok is True
    assert paso.resultado["codigo_municipio"] == "28079"
    # Cuatro niveles: estatal, autonómico, provincial, municipal.
    assert [a["nivel"] for a in paso.resultado["cadena"]] == [
        "estatal", "autonomico", "provincial", "municipal",
    ]
    assert r.fundamentada, r.cifras_sin_respaldo


def test_encadena_tres_herramientas_y_el_numero_final_es_real():
    """La cadena completa del producto, con las tres capacidades reales.

    Municipio → código INE → normativa aplicable → umbral de la tabla 3.1. El
    25 del final sale del PDF oficial vía el corpus, no de la memoria de nadie.
    """
    cliente = ClienteGuionizado(
        RespuestaFalsa(
            BloqueHerramienta("territorial__resolver_ambito", {"municipio": "Madrid"}, "t1")
        ),
        RespuestaFalsa(
            BloqueHerramienta(
                "normativa__reglas_aplicables",
                {
                    "codigo_municipio": "28079",
                    "uso": "residencial.vivienda_libre",
                    "tipologia": "plurifamiliar",
                    "fecha_devengo": "2026-01-01",
                },
                "t2",
            )
        ),
        RespuestaFalsa(
            BloqueHerramienta(
                "normativa__umbral_de_regla",
                {
                    "concept_id": CID_EVACUACION,
                    "ambito_id": "es",
                    "ejes": {"numero_salidas": "una", "condicion": "general"},
                },
                "t3",
            )
        ),
        RespuestaFalsa(
            BloqueTexto(
                "El recorrido no puede exceder de 25 m (RD 314/2006, DB-SI, SI 3, "
                "apartado 3, tabla 3.1). Las materias listadas como sin cobertura "
                "no se han comprobado."
            )
        ),
    )
    r = ejecutar("Planta con una única salida en Madrid: ¿qué recorrido admite?", cliente)

    assert [p.capacidad for p in r.pasos] == [
        "territorial.resolver_ambito",
        "normativa.reglas_aplicables",
        "normativa.umbral_de_regla",
    ]
    assert all(p.ok for p in r.pasos)

    # El eslabón: el código con el que se llamó a la segunda es exactamente el
    # que devolvió la primera.
    assert r.pasos[1].argumentos["codigo_municipio"] == r.pasos[0].resultado["codigo_municipio"]
    # Y el concept_id de la tercera, el que devolvió la segunda.
    assert r.pasos[2].argumentos["concept_id"] == r.pasos[1].resultado["normas"][0]["concept_id"]

    assert r.pasos[2].resultado["valor"] == 25
    assert r.pasos[2].resultado["unidad"] == "m"
    assert r.pasos[2].resultado["pendiente_de_firma_colegiada"] is True
    assert r.fundamentada, r.cifras_sin_respaldo

    # Lo que no se ha comprobado se deriva de las capacidades ejecutadas.
    assert any("no evalúa el proyecto" in l for l in r.limitaciones)
    assert any("pendiente_de_firma_colegiada" in l for l in r.limitaciones)


# --- Las cuatro defensas contra la invención --------------------------------

def test_el_resultado_lo_produce_el_ejecutor_y_no_el_modelo():
    """Aunque el modelo afirme otro código, lo que vuelve es lo que midió la herramienta."""
    cliente = ClienteGuionizado(
        RespuestaFalsa(
            BloqueTexto("Madrid es el 08019, lo recuerdo."),
            BloqueHerramienta("territorial__resolver_ambito", {"municipio": "Madrid"}),
        ),
        RespuestaFalsa(BloqueTexto("Corrijo: el código es 28079.")),
    )
    r = ejecutar("Código INE de Madrid", cliente)

    devueltos = _resultados_devueltos(cliente)
    assert len(devueltos) == 1
    assert devueltos[0]["codigo_municipio"] == "28079"
    assert "08019" not in json.dumps(devueltos[0])
    assert r.pasos[0].resultado["codigo_municipio"] == "28079"


def test_capacidad_desconocida_se_rechaza_sin_inventar_un_valor():
    cliente = ClienteGuionizado(
        RespuestaFalsa(BloqueHerramienta("normativa__calcular_lo_que_sea", {"x": 1})),
        RespuestaFalsa(BloqueTexto("No tengo esa herramienta.")),
    )
    r = ejecutar("Haz algo raro", cliente)

    paso = r.pasos[0]
    assert paso.ok is False
    assert paso.resultado["error"] == "capacidad_desconocida"
    assert set(paso.resultado) == {"ok", "error", "detalle"}      # ni un valor de más
    assert _resultados_devueltos(cliente)[0]["ok"] is False


def test_argumento_no_declarado_se_rechaza_antes_de_ejecutar():
    cliente = ClienteGuionizado(
        RespuestaFalsa(
            BloqueHerramienta(
                "territorial__resolver_ambito", {"municipio": "Madrid", "pais": "Francia"}
            )
        ),
        RespuestaFalsa(BloqueTexto("Reformulo.")),
    )
    r = ejecutar("Ámbito de Madrid en Francia", cliente)

    assert r.pasos[0].ok is False
    assert r.pasos[0].resultado["error"] == "argumentos_invalidos"
    assert "pais" in r.pasos[0].resultado["detalle"]


def test_argumento_obligatorio_ausente_se_rechaza():
    cliente = ClienteGuionizado(
        RespuestaFalsa(BloqueHerramienta("territorial__resolver_ambito", {})),
        RespuestaFalsa(BloqueTexto("¿De qué municipio?")),
    )
    r = ejecutar("Dime los ámbitos", cliente)

    assert r.pasos[0].ok is False
    assert r.pasos[0].resultado["error"] == "argumentos_invalidos"
    assert "municipio" in r.pasos[0].resultado["detalle"]


def test_una_capacidad_que_revienta_no_tumba_el_bucle():
    """Un fallo se convierte en un resultado con motivo, nunca en un valor."""

    def _explota() -> dict:
        raise RuntimeError("el disco no está")

    reg = Registro((
        Capacidad(
            id="prueba.explota",
            version="1.0.0",
            dominio="prueba",
            naturaleza="determinista",
            descripcion="Revienta siempre.",
            parametros={"type": "object", "properties": {}, "additionalProperties": False},
            funcion=_explota,
        ),
    ))
    cliente = ClienteGuionizado(
        RespuestaFalsa(BloqueHerramienta("prueba__explota", {})),
        RespuestaFalsa(BloqueTexto("La herramienta ha fallado.")),
    )
    r = ejecutar("Prueba", cliente, reg=reg)

    assert r.parada == "fin"
    assert r.pasos[0].ok is False
    assert r.pasos[0].resultado["error"] == "fallo_de_capacidad"
    assert "RuntimeError" in r.pasos[0].resultado["detalle"]


def test_una_cifra_que_no_sale_de_ninguna_herramienta_se_detecta():
    """La cuarta defensa: la red de seguridad sobre la prosa final."""
    cliente = ClienteGuionizado(
        RespuestaFalsa(BloqueHerramienta("territorial__resolver_ambito", {"municipio": "Madrid"})),
        RespuestaFalsa(BloqueTexto("El recorrido máximo admisible es de 30 m.")),
    )
    r = ejecutar("¿Qué recorrido admite una planta en Madrid?", cliente)

    assert r.fundamentada is False
    assert "30" in r.cifras_sin_respaldo


def test_una_cifra_que_dijo_el_usuario_no_cuenta_como_inventada():
    """El respaldo incluye lo que escribió el usuario: repetírselo no es inventar."""
    cliente = ClienteGuionizado(RespuestaFalsa(BloqueTexto("Anotado: 42 viviendas.")))
    r = ejecutar("El edificio tiene 42 viviendas", cliente)

    assert r.fundamentada, r.cifras_sin_respaldo


# --- El control del bucle ---------------------------------------------------

def test_el_limite_de_iteraciones_para_el_bucle():
    """Un modelo que no para nunca de pedir herramientas no cuelga el proceso."""
    cliente = ClienteGuionizado(
        RespuestaFalsa(BloqueHerramienta("territorial__resolver_ambito", {"municipio": "Madrid"}))
    )
    r = ejecutar("Bucle", cliente, max_iteraciones=3)

    assert r.parada == "limite_de_iteraciones"
    assert r.iteraciones == 3
    assert len(cliente.llamadas) == 3
    assert len(r.pasos) == 3


def test_dos_herramientas_en_un_mismo_turno_se_ejecutan_las_dos():
    cliente = ClienteGuionizado(
        RespuestaFalsa(
            BloqueHerramienta("territorial__resolver_ambito", {"municipio": "Madrid"}, "a"),
            BloqueHerramienta("territorial__resolver_ambito", {"municipio": "Barcelona"}, "b"),
        ),
        RespuestaFalsa(BloqueTexto("Madrid es 28079 y Barcelona 08019.")),
    )
    r = ejecutar("Códigos de Madrid y Barcelona", cliente)

    assert len(r.pasos) == 2
    assert {p.resultado["codigo_municipio"] for p in r.pasos} == {"28079", "08019"}
    assert r.fundamentada, r.cifras_sin_respaldo


def test_cada_tool_use_se_cierra_con_su_tool_result():
    """La API rechaza un historial con un `tool_use` sin respuesta. Se comprueba
    aquí porque el fallo real llegaría como un 400 en producción, no en la suite."""
    cliente = ClienteGuionizado(
        RespuestaFalsa(
            BloqueHerramienta("territorial__resolver_ambito", {"municipio": "Madrid"}, "a"),
            BloqueHerramienta("normativa__no_existe", {}, "b"),
        ),
        RespuestaFalsa(BloqueTexto("Listo.")),
    )
    ejecutar("Dos cosas", cliente)

    ultimo = cliente.llamadas[-1]["messages"]
    pedidos = [
        b["id"]
        for m in ultimo
        if m["role"] == "assistant"
        for b in m["content"]
        if b.get("type") == "tool_use"
    ]
    respondidos = [
        b["tool_use_id"]
        for m in ultimo
        if m["role"] == "user" and isinstance(m["content"], list)
        for b in m["content"]
        if b.get("type") == "tool_result"
    ]
    assert pedidos == ["a", "b"] == respondidos


# --- El registro ------------------------------------------------------------

def test_el_registro_se_puebla_por_descubrimiento():
    reg = registro(recargar=True)
    assert set(reg.ids()) == {
        "bim.inventario_de_ifc",
        "territorial.resolver_ambito",
        "normativa.reglas_aplicables",
        "normativa.umbral_de_regla",
        # Las tres de lectura del primer vertical (tarea TL-1, 2026-08-19)...
        "plano.leer_dxf",
        "plano.cuadro_de_superficies",
        "plano.superficie_util",
        # ...y las dos que escriben: el DXF relleno (TL-2) y el PDF que lo
        # explica (DOC-2). Son las únicas `io` del registro, las únicas que
        # exigen autorización explícita del efecto.
        "plano.escribir_cuadro",
        "plano.cuadro_en_pdf",
        # La revisión de coherencia del plano (tarea CO-4, 2026-08-19), con la
        # misma separación por efecto: una lee y no pide autorización, la otra
        # escribe el informe y sí la pide.
        "plano.coherencia",
        "plano.informe_de_coherencia",
    }
    # C4 — cobertura antes que catálogo: entre 8 y 12 capacidades auditadas al
    # cerrar el MVP, no cientos. Esta lista es larga a propósito: obliga a que
    # añadir una capacidad sea una decisión visible, no una deriva.
    assert len(reg) <= 12, "C4: el catálogo no crece sin decidirlo"
    # Orden estable: los manifiestos viajan en el prefijo cacheado del prompt.
    assert list(reg.ids()) == sorted(reg.ids())


def test_una_capacidad_nueva_aparece_sin_tocar_ningun_init():
    """La promesa del registro por descubrimiento, comprobada en el árbol real.

    Es el mismo test que `tests/test_normativa_municipio_nuevo.py` hace con el
    corpus, y por el mismo motivo: si alguien mete un `if` "solo para este
    caso", a partir de ahí cada capacidad nueva cuesta una release.
    """
    destino = RAIZ / "agente" / "herramientas" / "zzz_prueba_descubrimiento.py"
    destino.write_text(
        "# -*- coding: utf-8 -*-\n"
        "from agente.capacidad import Capacidad\n"
        "CAPACIDADES = (Capacidad(id='prueba.descubierta', version='0.1.0',\n"
        "    dominio='prueba', naturaleza='determinista', descripcion='De prueba.',\n"
        "    parametros={'type': 'object', 'properties': {}},\n"
        "    funcion=lambda: {'ok': True}),)\n",
        encoding="utf-8",
    )
    try:
        assert "prueba.descubierta" in [c.id for c in descubrir()]
    finally:
        destino.unlink()
        registro(recargar=True)

    assert "prueba.descubierta" not in registro(recargar=True).ids()


def test_ninguna_capacidad_sabe_de_transporte():
    """La prueba del plugin, mecanizada: una capacidad se invoca igual desde la
    web, desde Revit o desde un `python -c`. Si importa Flask, no."""
    prohibido = re.compile(r"^\s*(from|import)\s+(flask|fastapi|django|werkzeug)\b", re.M)
    culpables = [
        f.name
        for f in sorted((RAIZ / "agente").rglob("*.py"))
        if prohibido.search(f.read_text(encoding="utf-8"))
    ]
    assert culpables == [], f"el agente no puede depender del transporte: {culpables}"


def test_los_esquemas_valen_para_la_api():
    """Nombre admisible, esquema de objeto y descripción con sus limitaciones."""
    admisible = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
    for esquema in registro().esquemas():
        assert admisible.match(esquema["name"]), esquema["name"]
        assert esquema["input_schema"]["type"] == "object"
        assert esquema["description"].strip()
    # Las limitaciones declaradas llegan al modelo, no se quedan en el registro.
    por_nombre = {e["name"]: e for e in registro().esquemas()}
    assert "NO comprueba:" in por_nombre["normativa__umbral_de_regla"]["description"]


def test_una_capacidad_mal_declarada_no_llega_al_registro():
    with pytest.raises(ValueError, match="semver"):
        Capacidad(
            id="mala.version", version="1.0", dominio="p", naturaleza="determinista",
            descripcion="x", parametros={"type": "object"}, funcion=lambda: {"ok": True},
        )
    with pytest.raises(ValueError, match="naturaleza"):
        Capacidad(
            id="mala.naturaleza", version="1.0.0", dominio="p", naturaleza="magia",
            descripcion="x", parametros={"type": "object"}, funcion=lambda: {"ok": True},
        )


def test_una_capacidad_que_no_devuelve_un_dict_estructurado_se_rechaza():
    """El contrato de salida se hace cumplir en el punto de invocación."""
    capacidad = Capacidad(
        id="prueba.prosa", version="1.0.0", dominio="prueba", naturaleza="determinista",
        descripcion="Devuelve texto libre.", parametros={"type": "object", "properties": {}},
        funcion=lambda: "25 metros",
    )
    cliente = ClienteGuionizado(
        RespuestaFalsa(BloqueHerramienta("prueba__prosa", {})),
        RespuestaFalsa(BloqueTexto("No he podido usarla.")),
    )
    r = ejecutar("Prueba", cliente, reg=Registro((capacidad,)))

    assert r.pasos[0].ok is False
    assert r.pasos[0].resultado["error"] == "resultado_invalido"
    assert "25" not in json.dumps(r.pasos[0].resultado)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
