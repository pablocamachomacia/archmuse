# -*- coding: utf-8 -*-
"""C7 — Serialización determinista.

Un único formato, JSON, que es a la vez el artefacto de los goldens y el
futuro formato de persistencia de E2. Siete reglas duras, todas comprobables:

1. Todo float redondeado a 3 decimales (el milímetro). Sin excepción.
2. Toda lista ordenada por `id` antes de serializar. Ningún conjunto.
3. `sort_keys=True`, `ensure_ascii=False`, separadores fijos, salto final.
4. Round-trip sin pérdida: `cargar(volcar(m))` reconstruye el mismo modelo, y
   `volcar(cargar(j))` devuelve los mismos bytes.
5. `sellado` = sha256 del cuerpo sin el propio campo. Es la comprobación
   mecánica del invariante I8.
6. Cero campos con nombre de formato fuera de `procedencia` (principio P6).
7. Cero campos evaluativos (`nodos.LISTA_NEGRA`).

**Por qué el sellado se calcula aquí y no en `grafo.py`.** El hash es una
propiedad de la forma serializada, no de los objetos en memoria: dos grafos
con los mismos datos y distinto orden de inserción deben sellar igual. Ponerlo
en el grafo obligaría a que el grafo conociera su propio formato de volcado, y
entonces cambiar el formato cambiaría la identidad de versiones ya emitidas.

---

**DESVIACIÓN respecto del contrato C7, documentada (E1).**

- *Decisión original:* el ejemplo de JSON del PRD incluía un bloque
  `derivados` (área, perímetro, centroide, envolvente…) dentro de cada
  espacio.
- *Problema encontrado:* rompe la regla 4 (round-trip sin pérdida). Los
  derivados se calculan de la geometría exacta al volcar, pero al cargar la
  geometría vuelve redondeada al milímetro, así que el segundo volcado
  produce `area_m2: 12.724` donde el primero decía `12.725`. Medido: 357
  líneas de diferencia sobre `ejemplo.dxf`, **todas** en `derivados`; ni un
  nodo, arista, identidad o atributo cambiaba.
- *Solución aplicada:* `derivados` sale del formato. El JSON persiste
  **fuentes** —los puntos del contorno— y quien necesite área o perímetro los
  pide al API (`Grafo.derivados`), que los calcula. G9 sí los congela, porque
  eso es trabajo del golden y no del formato.
- *Impacto:* el JSON es algo menos legible de un vistazo; a cambio el
  round-trip es exacto y el sellado es estable. Ningún consumidor pierde nada:
  no había ninguno.
- *Por qué sigue siendo compatible con la arquitectura:* es literalmente el
  principio P7 del documento de diseño —«si un dato puede derivarse del
  modelo, no se persiste como dato»—. El `cargar()` de más abajo ya lo decía
  en su docstring antes de que esto se midiera; el formato no lo cumplía.

**Límite conocido de la persistencia, que E2 tendrá que tener presente.** Un
modelo cargado desde JSON tiene geometría con precisión de milímetro; uno
construido desde el DXF conserva la del origen. Recalcular la topología sobre
el modelo cargado podría, en teoría, mover una arista cuya separación cayera a
menos de 1 mm del umbral. Sobre `ejemplo.dxf` no ocurre: la separación más
próxima al umbral de 0,5 m está a 0,38 m, es decir a 120 mm.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .aristas import Arista, Criterio
from .atributo import Atributo, Motivo
from .geometria import AlmacenGeometria, DECIMALES
from .grafo import Grafo
from .nodos import Edificio, Espacio, Planta, Procedencia, Proyecto, Unidad

CONTRATO = "1.0"


def _redondear(dato: Any) -> Any:
    if isinstance(dato, float):
        valor = round(dato, DECIMALES)
        return 0.0 if valor == 0.0 else valor
    if isinstance(dato, dict):
        return {clave: _redondear(valor) for clave, valor in dato.items()}
    if isinstance(dato, (list, tuple)):
        return [_redondear(valor) for valor in dato]
    if isinstance(dato, (set, frozenset)):
        raise TypeError(
            "no se serializa un conjunto: su orden no es estable. "
            "Conviertelo en lista ordenada por una clave explicita.")
    return dato


def _cuerpo(grafo: Grafo) -> dict:
    """El modelo entero como dato plano, sin el campo `sellado`."""
    espacios = sorted(grafo.get_spaces(), key=lambda e: e.id)
    return {
        "contrato": CONTRATO,
        "criterio": grafo.criterio.a_dict(),
        "proyecto": {
            "id": grafo.proyecto.id,
            "concepto": grafo.proyecto.concepto,
            "escala": grafo.proyecto.escala.a_dict(),
            "norte_grados": grafo.proyecto.norte_grados.a_dict(),
            "tipologia": grafo.proyecto.tipologia.a_dict(),
            "ciudad": grafo.proyecto.ciudad.a_dict(),
            "procedencia": grafo.proyecto.procedencia.a_dict(),
            "presencia": dict(grafo.proyecto.presencia),
            "edificios": list(grafo.proyecto.edificios),
        },
        "edificios": [
            {"id": e.id, "concepto": e.concepto, "plantas": list(e.plantas)}
            for e in sorted(grafo.edificios(), key=lambda e: e.id)
        ],
        "plantas": [
            {"id": p.id, "concepto": p.concepto, "edificio_id": p.edificio_id,
             "numero": p.numero.a_dict(), "cota_base_m": p.cota_base_m.a_dict(),
             "altura_libre_m": p.altura_libre_m.a_dict(),
             "unidades": list(p.unidades)}
            for p in sorted(grafo.plantas(), key=lambda p: p.id)
        ],
        "unidades": [
            {"id": u.id, "concepto": u.concepto, "planta_id": u.planta_id,
             "etiqueta": u.etiqueta.a_dict(), "uso": u.uso.a_dict(),
             "espacios": list(u.espacios)}
            for u in sorted(grafo.unidades(), key=lambda u: u.id)
        ],
        "espacios": [
            {"id": e.id, "concepto": e.concepto, "unidad_id": e.unidad_id,
             "planta_id": e.planta_id, "rotulo": e.rotulo,
             "tipo": e.tipo.a_dict(), "tipos_ambiguos": list(e.tipos_ambiguos),
             "geometrias": dict(e.geometrias),
             # Sin `derivados`: son función pura de `geometrias` y persistirlos
             # junto a su fuente rompe el round-trip (ver cabecera).
             "procedencia": e.procedencia.a_dict()}
            for e in espacios
        ],
        "aristas": [
            a.a_dict() for a in sorted(
                grafo.aristas(), key=lambda a: (a.tipo, a.a, a.b))
        ],
        "geometrias": grafo.almacen.a_dict(),
    }


def canonico(dato: Any) -> str:
    return json.dumps(_redondear(dato), sort_keys=True, ensure_ascii=False,
                      indent=2, separators=(",", ": ")) + "\n"


def sellado_de(grafo: Grafo) -> str:
    """sha256 del cuerpo canónico. La identidad de esta versión."""
    return hashlib.sha256(canonico(_cuerpo(grafo)).encode("utf-8")).hexdigest()


def a_dict(grafo: Grafo) -> dict:
    cuerpo = _cuerpo(grafo)
    cuerpo["sellado"] = grafo.sellado or sellado_de(grafo)
    return _redondear(cuerpo)


def volcar(grafo: Grafo) -> str:
    return canonico(a_dict(grafo))


# --- Reconstrucción ---------------------------------------------------------


def _atributo(datos: dict) -> Atributo:
    return Atributo(
        valor=datos.get("valor"),
        estado=datos["estado"],
        origen=datos.get("origen"),
        confianza=datos.get("confianza"),
        motivos=tuple(Motivo(m["codigo"], m["detalle"])
                      for m in datos.get("motivos") or ()),
        fuente=datos.get("fuente") or "",
    )


def _procedencia(datos: dict) -> Procedencia:
    return Procedencia(
        formato=datos.get("formato") or "",
        fichero=datos.get("fichero") or "",
        capa=datos.get("capa"),
        id_nativo=datos.get("id_nativo"),
    )


def cargar(texto: str) -> Grafo:
    """Reconstruye un grafo desde su JSON. Cierra el round-trip de C7.4.

    Los `derivados` no se leen: se recalculan de la geometría. Un derivado
    persistido que no coincidiera con su geometría sería un dato podrido
    imposible de detectar, y el principio P7 dice que lo derivable no se
    guarda como dato — aquí viaja sólo para que el JSON sea legible y
    comparable.
    """
    datos = json.loads(texto)
    almacen = AlmacenGeometria.desde_dict(datos["geometrias"])

    proyecto = Proyecto(
        id=datos["proyecto"]["id"],
        concepto=datos["proyecto"]["concepto"],
        escala=_atributo(datos["proyecto"]["escala"]),
        norte_grados=_atributo(datos["proyecto"]["norte_grados"]),
        tipologia=_atributo(datos["proyecto"]["tipologia"]),
        ciudad=_atributo(datos["proyecto"]["ciudad"]),
        procedencia=_procedencia(datos["proyecto"]["procedencia"]),
        presencia=dict(datos["proyecto"]["presencia"]),
        edificios=tuple(datos["proyecto"]["edificios"]),
    )
    edificios = [Edificio(id=e["id"], concepto=e["concepto"],
                          plantas=tuple(e["plantas"]))
                 for e in datos["edificios"]]
    plantas = [Planta(id=p["id"], concepto=p["concepto"],
                      edificio_id=p["edificio_id"], numero=_atributo(p["numero"]),
                      cota_base_m=_atributo(p["cota_base_m"]),
                      altura_libre_m=_atributo(p["altura_libre_m"]),
                      unidades=tuple(p["unidades"]))
               for p in datos["plantas"]]
    unidades = [Unidad(id=u["id"], concepto=u["concepto"], planta_id=u["planta_id"],
                       etiqueta=_atributo(u["etiqueta"]), uso=_atributo(u["uso"]),
                       espacios=tuple(u["espacios"]))
                for u in datos["unidades"]]
    espacios = [Espacio(id=e["id"], concepto=e["concepto"], unidad_id=e["unidad_id"],
                        planta_id=e["planta_id"], rotulo=e["rotulo"],
                        tipo=_atributo(e["tipo"]),
                        geometrias=dict(e["geometrias"]),
                        procedencia=_procedencia(e["procedencia"]),
                        tipos_ambiguos=tuple(e["tipos_ambiguos"]))
                for e in datos["espacios"]]
    aristas = [Arista(tipo=a["tipo"], a=a["a"], b=a["b"], origen=a["origen"],
                      separacion_m=a["separacion_m"], tramo_m=a["tramo_m"],
                      distancia_m=a["distancia_m"])
               for a in datos["aristas"]]
    criterio = Criterio(**datos["criterio"])

    grafo = Grafo(proyecto=proyecto, edificios=edificios, plantas=plantas,
                  unidades=unidades, espacios=espacios, aristas=aristas,
                  almacen=almacen, criterio=criterio)
    return grafo.sellar(datos["sellado"])


def verificar_sellado(grafo: Grafo) -> bool:
    """I8: el hash guardado sigue describiendo el contenido actual."""
    return grafo.sellado is not None and grafo.sellado == sellado_de(grafo)
