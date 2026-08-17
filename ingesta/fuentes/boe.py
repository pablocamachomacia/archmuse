"""Conector contra la API de datos abiertos real del BOE.

Verificado contra el servicio en vivo el 2026-08-06 (ver
`docs/design/2026-08-06-ingesta-normativa.md` §3.1), no contra documentación
leída de memoria:

- Sumario diario: ``GET /datosabiertos/api/boe/sumario/{AAAAMMDD}`` (JSON).
- Documento individual: ``GET /diario_boe/xml.php?id={identificador}`` (XML).

La trampa real de esta fuente, encontrada inspeccionando una respuesta real:
es JSON generado desde XML por PHP, así que un campo que podría repetirse
sale como objeto cuando hay uno solo y como lista cuando hay varios — en
CINCO niveles distintos del mismo sumario (`diario`, `seccion`,
`departamento`, `epigrafe`, `item`). Además, `epigrafe` cuelga unas veces de
`departamento.texto.epigrafe` y otras directamente de `departamento.epigrafe`,
según la sección — comparado en un mismo sumario real entre "I. Disposiciones
generales" y "II.A Nombramientos". Los tests de este módulo corren contra un
sumario real grabado que conserva ambas formas, no una construida a mano.
"""
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import date
from typing import List, Optional

from .. import red
from ..errores import DocumentoIlegible
from ..modelo import DocumentoOficial, ItemSumario, como_lista
from .base import FuenteOficial

BASE = "https://www.boe.es/datosabiertos/api"
URL_DOCUMENTO = "https://www.boe.es/diario_boe/xml.php?id={id}"


class FuenteBOE(FuenteOficial):
    id = "boe"

    def listar_sumario(self, fecha: date) -> List[ItemSumario]:
        url = f"{BASE}/boe/sumario/{fecha.strftime('%Y%m%d')}"
        crudo = red.obtener(url, accept="application/json")
        return self._items_desde_json(crudo, fecha)

    def descargar_documento(self, item: ItemSumario) -> DocumentoOficial:
        if not item.url_xml:
            raise DocumentoIlegible(item.identificador, "el item del sumario no trae url_xml")
        return self.descargar_por_id(item.identificador, item.url_xml)

    def descargar_por_id(self, identificador: str, url_xml: Optional[str] = None) -> DocumentoOficial:
        """Descarga directa por identificador conocido, sin pasar por el
        sumario de ningún día. Es lo que permite traer un documento concreto
        —el propio CTE, por ejemplo— sin recorrer el calendario hasta
        encontrar en qué fecha se publicó. No forma parte del contrato
        `FuenteOficial` (es específico de cómo el BOE nombra sus recursos),
        pero es la vía natural de extensión: cualquier fuente que también
        tenga URLs deterministas por id puede exponer lo mismo."""
        url = url_xml or URL_DOCUMENTO.format(id=identificador)
        crudo = red.obtener(url, accept="application/xml")
        return self._documento_desde_xml(identificador, url, crudo)

    # --- Parseo del sumario --------------------------------------------

    def _items_desde_json(self, crudo: bytes, fecha: date) -> List[ItemSumario]:
        try:
            doc = json.loads(crudo)
        except json.JSONDecodeError as exc:
            raise DocumentoIlegible(f"sumario {fecha.isoformat()}", f"JSON inválido: {exc}") from exc

        estado = (doc.get("status") or {}).get("code")
        if estado != "200":
            # No hay boletín ese día (festivo, fin de semana) — hecho normal
            # del calendario, no un error. Ver `FuenteOficial.listar_sumario`.
            return []

        items: List[ItemSumario] = []
        sumario = ((doc.get("data") or {}).get("sumario") or {})
        fecha_pub = ((sumario.get("metadatos") or {}).get("fecha_publicacion")) or fecha.strftime("%Y%m%d")

        for diario in como_lista(sumario.get("diario")):
            for seccion in como_lista(diario.get("seccion")):
                for departamento in como_lista(seccion.get("departamento")):
                    items.extend(
                        self._items_de_departamento(departamento, seccion, fecha_pub)
                    )
        return items

    def _items_de_departamento(self, departamento: dict, seccion: dict, fecha_pub: str) -> List[ItemSumario]:
        # `epigrafe` cuelga de `departamento.texto.epigrafe` en algunas
        # secciones y directamente de `departamento.epigrafe` en otras.
        # Probar ambas, en ese orden, es lo que evita perder items en
        # silencio — ver el docstring del módulo.
        contenedor = (departamento.get("texto") or departamento)
        epigrafes = como_lista(contenedor.get("epigrafe"))

        salida: List[ItemSumario] = []
        for epigrafe in epigrafes:
            nombre_epigrafe = epigrafe.get("nombre")
            for item in como_lista(epigrafe.get("item")):
                salida.append(
                    self._item_sumario(item, seccion, departamento, nombre_epigrafe, fecha_pub)
                )
        # Algunos departamentos publican un item suelto sin epígrafe.
        for item in como_lista(contenedor.get("item")):
            salida.append(self._item_sumario(item, seccion, departamento, None, fecha_pub))
        return salida

    @staticmethod
    def _item_sumario(item: dict, seccion: dict, departamento: dict, epigrafe: Optional[str], fecha_pub: str) -> ItemSumario:
        url_pdf = item.get("url_pdf")
        url_pdf_texto = url_pdf.get("texto") if isinstance(url_pdf, dict) else url_pdf
        return ItemSumario(
            identificador=item.get("identificador", ""),
            titulo=item.get("titulo", ""),
            fuente="boe",
            fecha_publicacion=fecha_pub,
            seccion_codigo=seccion.get("codigo", ""),
            seccion_nombre=seccion.get("nombre", ""),
            departamento_codigo=departamento.get("codigo", ""),
            departamento_nombre=departamento.get("nombre", ""),
            epigrafe=epigrafe,
            url_html=item.get("url_html"),
            url_pdf=url_pdf_texto,
            url_xml=item.get("url_xml"),
        )

    # --- Parseo del documento individual --------------------------------

    def _documento_desde_xml(self, identificador: str, url: str, crudo: bytes) -> DocumentoOficial:
        try:
            raiz = ET.fromstring(crudo)
        except ET.ParseError as exc:
            raise DocumentoIlegible(identificador, f"XML inválido: {exc}") from exc

        metadatos = raiz.find("metadatos")
        if metadatos is None:
            raise DocumentoIlegible(identificador, "el XML no trae <metadatos>")

        def texto(etiqueta: str) -> Optional[str]:
            nodo = metadatos.find(etiqueta)
            if nodo is None or nodo.text is None or not nodo.text.strip():
                return None
            return nodo.text.strip()

        def atributo(etiqueta: str, atributo_nombre: str) -> Optional[str]:
            nodo = metadatos.find(etiqueta)
            return nodo.get(atributo_nombre) if nodo is not None else None

        departamento_nodo = metadatos.find("departamento")
        rango_nodo = metadatos.find("rango")
        url_eli = texto("url_eli")

        return DocumentoOficial(
            identificador=texto("identificador") or identificador,
            fuente="boe",
            titulo=texto("titulo") or "",
            organismo=(departamento_nodo.text.strip() if departamento_nodo is not None and departamento_nodo.text else ""),
            rango_codigo=atributo("rango", "codigo"),
            rango_nombre=(rango_nodo.text.strip() if rango_nodo is not None and rango_nodo.text else None),
            numero_oficial=texto("numero_oficial"),
            fecha_publicacion=texto("fecha_publicacion"),
            fecha_disposicion=texto("fecha_disposicion"),
            fecha_actualizacion=raiz.get("fecha_actualizacion"),
            url_oficial=url_eli or url,
            url_xml=url,
            texto_crudo=crudo.decode("utf-8"),
            hash_texto=hashlib.sha256(crudo).hexdigest(),
        )
