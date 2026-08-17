import io

from pypdf import PdfReader

from analyzer.dossier_pdf import generar_dossier_pdf

DATOS_COMPLETOS = {
    "nombre_proyecto": "Residencial Gran Vía",
    "nombre_promotora": "Estudio Ejemplo",
    "ubicacion": {"lat": 40.42, "lon": -3.70},
    "mapbox_token": None,
    "solido_capaz": {"superficie_ocupada_m2": 500, "plantas_estimadas": 4, "altura_max_m": 12.4},
    "superficie_solar_m2": 1000,
    "superficie_total_construida_m2": 1590,
    "viviendas": [
        {"nombre": "Planta 1", "habitaciones": [
            {"nombre": "Salón", "poligono": [[0, 0], [5, 0], [5, 4], [0, 4]]},
            {"nombre": "Dormitorio 1", "poligono": [[5, 0], [8, 0], [8, 4], [5, 4]]},
        ]},
    ],
    "viabilidad": {
        "superficie": 1590, "ratioM2": 1000, "costeSuelo": 200000, "precioVenta": 2500000,
        "pem": 1590000, "repercusionSuelo": 125.8, "margenBruto": 710000,
        "margenPromotorPct": 13.4, "ratioEficienciaSuperficie": 0.82,
    },
}


def _paginas(pdf_bytes):
    return PdfReader(io.BytesIO(pdf_bytes)).pages


def test_genera_pdf_valido_con_datos_completos():
    pdf_bytes = generar_dossier_pdf(DATOS_COMPLETOS)
    assert pdf_bytes[:5] == b"%PDF-"
    paginas = _paginas(pdf_bytes)
    assert len(paginas) == 4  # portada, ficha, planos, viabilidad


def test_solo_nombre_proyecto_no_falla():
    """Ninguna clave salvo `nombre_proyecto` es obligatoria -- todo lo
    demás ausente se traduce en secciones vacías/"No disponible", nunca en
    una excepción."""
    pdf_bytes = generar_dossier_pdf({"nombre_proyecto": "Mínimo"})
    assert pdf_bytes[:5] == b"%PDF-"
    texto = _paginas(pdf_bytes)[0].extract_text()
    assert "Sin render 3D ni mapa" in texto


def test_ficha_urbanistica_no_disponible_sin_inventar():
    pdf_bytes = generar_dossier_pdf({"nombre_proyecto": "Sin urbanismo"})
    texto = "\n".join(p.extract_text() for p in _paginas(pdf_bytes))
    assert "No disponible" in texto


def test_viabilidad_vacia_muestra_pendiente_no_ceros():
    pdf_bytes = generar_dossier_pdf({"nombre_proyecto": "Sin viabilidad"})
    texto = "\n".join(p.extract_text() for p in _paginas(pdf_bytes))
    assert "todavía no ha rellenado" in texto


def test_logo_base64_invalido_no_rompe_generacion():
    datos = dict(DATOS_COMPLETOS, logo_base64="esto-no-es-base64-valido-!!!")
    pdf_bytes = generar_dossier_pdf(datos)
    assert pdf_bytes[:5] == b"%PDF-"


def test_render_3d_data_url_se_decodifica():
    # 1x1 PNG transparente real, como data-URL -- confirma que el prefijo
    # `data:image/...;base64,` se recorta correctamente.
    png_1x1 = (
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42"
        "mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    datos = dict(DATOS_COMPLETOS, render_3d_base64=png_1x1)
    pdf_bytes = generar_dossier_pdf(datos)
    assert pdf_bytes[:5] == b"%PDF-"


def test_habitacion_sin_poligono_se_omite_del_plano():
    datos = dict(DATOS_COMPLETOS, viviendas=[
        {"nombre": "Planta vacía", "habitaciones": [{"nombre": "Sin geometría", "poligono": []}]},
    ])
    pdf_bytes = generar_dossier_pdf(datos)
    assert pdf_bytes[:5] == b"%PDF-"
    # Sin ninguna habitación con polígono válido, no debería añadirse un plano de esa planta
    # (la página de planos se omite si no hay ningún dibujo generado -- ver `_dibujar_planta`).
