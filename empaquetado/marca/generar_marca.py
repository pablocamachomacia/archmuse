"""Genera el símbolo de ArchMuse para el instalador: icono y las dos imágenes del asistente.

    venv\\Scripts\\python.exe empaquetado\\marca\\generar_marca.py

Escribe en esta carpeta:
  archmuse.ico            16, 24, 32, 48 y 256 px, cada tamaño dibujado por separado
  cabecera-<lado>.png     WizardSmallImageFile, las siete escalas de Inno Setup
  lateral-<ancho>.png     WizardImageFile, las siete escalas de Inno Setup

**El símbolo es la dirección «B1 · Paredes desplazadas»**, elegida por Pablo el
2026-09-15 entre tres direcciones y tres variantes: una planta de vivienda con
recintos de tamaños distintos y el recinto medido en azul. Paleta de la web
(`static/style.css`): negro #0a0a0c, blanco, acento #4A90D9.

**Por qué se dibuja cada tamaño y no se reduce el grande.** La planta vive en una
rejilla de 16. En cada tamaño las líneas de la rejilla caen en píxeles enteros y
el grueso de pared es entero; reducir el de 256 a 24 px pondría las paredes en
1,5 px, borrosas. Es el ajuste que se haría a mano píxel a píxel, hecho por cálculo.

Las medidas de las imágenes son las de la documentación de Inno Setup 6.7
(`topic_setup_wizardsmallimagefile`, `topic_setup_wizardimagefile`), consultadas
el 2026-09-14: la cabecera es cuadrada y la lateral guarda la proporción 164:314.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
FUENTE = RAIZ / "static" / "vendor" / "fuentes" / "v20-UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7.woff2"

NEGRO = (10, 10, 12, 255)      # #0a0a0c
BLANCO = (255, 255, 255, 255)
AZUL = (74, 144, 217, 255)     # #4A90D9
CLARO = (243, 243, 243, 255)   # gris muy suave, el de la barra de botones del asistente

TAMANOS_ICO = (16, 24, 32, 48, 256)
#: WizardSmallImageFile: 100 %, 125 %, 150 %, 175 %, 200 %, 225 % y 250 %.
CABECERA = (58, 77, 97, 116, 124, 143, 159)
#: WizardImageFile, mismas escalas.
LATERAL = ((202, 386), (269, 515), (336, 643), (403, 772), (430, 824), (498, 953), (534, 1022))

#: Estilos de la imagen lateral en prueba (2026-09-15, Pablo: el negro contra el
#: blanco del asistente es demasiado duro). `planta`, `texto` y `hueco` son
#: fracciones del ancho. `ESTILO_LATERAL` es el que va al instalador.
ESTILOS_LATERAL = {
    "oscuro": {"fondo": NEGRO, "tinta": BLANCO, "planta": 0.52, "texto": 0.135, "hueco": 0.12},
    "oscuro-aire": {"fondo": NEGRO, "tinta": BLANCO, "planta": 0.40, "texto": 0.105, "hueco": 0.10},
    "claro": {"fondo": CLARO, "tinta": NEGRO, "planta": 0.40, "texto": 0.105, "hueco": 0.10},
}
ESTILO_LATERAL = "oscuro"
#: La cabecera: el icono con su placa negra, o la planta sola sobre el blanco.
ESTILO_CABECERA = "placa"


def H(y, x1, x2):
    """Pared horizontal en la línea `y` de la rejilla, de la línea `x1` a la `x2`."""
    return ("H", y, x1, x2)


def V(x, y1, y2):
    return ("V", x, y1, y2)


def AZ(x1, y1, x2, y2):
    """El recinto medido, entre las paredes `x1`..`x2` e `y1`..`y2`."""
    return ("AZ", x1, y1, x2, y2)


#: B1 · Paredes desplazadas. Marco de 2 a 13; arriba un recinto grande y uno
#: estrecho, abajo uno pequeño y el salón (azul). Las paredes interiores no se
#: alinean: 9 arriba, 6 abajo.
PLANTA = [
    H(2, 2, 13), H(13, 2, 13), V(2, 2, 13), V(13, 2, 13),
    V(9, 2, 8), H(8, 2, 13), V(6, 8, 13),
    AZ(6, 8, 13, 13),
]


def _dibujar_planta(d, origen_x, origen_y, unidad, grueso, escala, pared=BLANCO):
    """Pinta la planta sobre `d`. `unidad` son los píxeles por línea de rejilla
    del tamaño final; `escala` es el supermuestreo del lienzo; `pared`, el color
    de las paredes (blanco sobre negro, negro sobre claro)."""

    def px(c):
        return int(c * unidad + 0.5)

    def caja(x0, y0, x1, y1, color):
        d.rectangle([(origen_x + x0) * escala, (origen_y + y0) * escala,
                     (origen_x + x1) * escala - 1, (origen_y + y1) * escala - 1], fill=color)

    for p in PLANTA:
        if p[0] == "AZ":
            _, x1, y1, x2, y2 = p
            caja(px(x1) + grueso, px(y1) + grueso, px(x2), px(y2), AZUL)
    for p in PLANTA:
        if p[0] == "H":
            _, y, x1, x2 = p
            caja(px(x1), px(y), px(x2) + grueso, px(y) + grueso, pared)
        elif p[0] == "V":
            _, x, y1, y2 = p
            caja(px(x), px(y1), px(x) + grueso, px(y2) + grueso, pared)


def icono(lado: int, supermuestreo: int = 8) -> Image.Image:
    """El símbolo con su placa negra de esquinas redondeadas, a `lado` px."""
    s = supermuestreo
    lienzo = Image.new("RGBA", (lado * s, lado * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(lienzo)
    d.rounded_rectangle([0, 0, lado * s - 1, lado * s - 1], radius=3 * lado * s / 16, fill=NEGRO)
    _dibujar_planta(d, 0, 0, lado / 16, max(1, lado // 16), s)
    return lienzo.resize((lado, lado), Image.BOX)


def planta_sola(lado: int, pared=NEGRO, supermuestreo: int = 8) -> Image.Image:
    """La planta sin placa, llenando el cuadro y con fondo transparente: para la
    cabecera blanca del asistente, donde la placa negra puede sobrar."""
    s = supermuestreo
    grueso = max(1, round(lado / 20))
    unidad = (lado - grueso) / 11            # de la pared 2 a la 13, más su grueso
    desplazamiento = -int(2 * unidad + 0.5)
    lienzo = Image.new("RGBA", (lado * s, lado * s), (0, 0, 0, 0))
    _dibujar_planta(ImageDraw.Draw(lienzo), desplazamiento, desplazamiento, unidad, grueso, s, pared=pared)
    return lienzo.resize((lado, lado), Image.BOX)


def cabecera(lado: int, estilo: str = ESTILO_CABECERA) -> Image.Image:
    return icono(lado) if estilo == "placa" else planta_sola(lado)


def lateral(ancho: int, alto: int, estilo: str = ESTILO_LATERAL, supermuestreo: int = 4) -> Image.Image:
    """La imagen lateral: la planta y el nombre, centrados en los dos ejes.

    **El centrado se hace sobre lo que se pinta**, no sobre la geometría: se
    dibuja el bloque, se recorta por su caja de tinta y se pega en el centro. Así
    el nombre, más ancho que la planta, no descoloca el conjunto."""
    e = ESTILOS_LATERAL[estilo]
    s = supermuestreo
    capa = Image.new("RGBA", (ancho * s, alto * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)

    unidad = ancho * e["planta"] / 12
    grueso = max(1, round(unidad))
    borde_izquierdo = int(2 * unidad + 0.5)
    borde_derecho = int(13 * unidad + 0.5) + grueso
    origen_x = (ancho - (borde_izquierdo + borde_derecho)) // 2
    origen_y = alto // 5
    _dibujar_planta(d, origen_x, origen_y, unidad, grueso, s, pared=e["tinta"])

    fuente = ImageFont.truetype(str(FUENTE), int(ancho * e["texto"] * s))
    fuente.set_variation_by_axes([600])
    texto = "ArchMuse"
    caja = d.textbbox((0, 0), texto, font=fuente)
    tx = ancho * s / 2 - (caja[0] + caja[2]) / 2
    ty = (origen_y + borde_derecho + ancho * e["hueco"]) * s - caja[1]
    d.text((tx, ty), texto, font=fuente, fill=e["tinta"])

    bloque = capa.crop(capa.getbbox())
    fondo = Image.new("RGBA", capa.size, e["fondo"])
    fondo.alpha_composite(bloque, ((capa.width - bloque.width) // 2, (capa.height - bloque.height) // 2))
    return fondo.convert("RGB").resize((ancho, alto), Image.LANCZOS)


def generar(destino: Path = AQUI, estilo_lateral: str = ESTILO_LATERAL,
            estilo_cabecera: str = ESTILO_CABECERA, icono_tambien: bool = True) -> list[Path]:
    escritos = []
    if icono_tambien:
        marcos = [icono(lado) for lado in TAMANOS_ICO]
        ico = destino / "archmuse.ico"
        # `append_images`: cada tamaño es su dibujo, no una reducción del de 256.
        marcos[-1].save(ico, format="ICO", sizes=[(l, l) for l in TAMANOS_ICO], append_images=marcos[:-1])
        escritos.append(ico)
    for lado in CABECERA:
        ruta = destino / f"cabecera-{lado}.png"
        cabecera(lado, estilo_cabecera).save(ruta, optimize=True)
        escritos.append(ruta)
    for ancho, alto in LATERAL:
        ruta = destino / f"lateral-{ancho}.png"
        lateral(ancho, alto, estilo_lateral).save(ruta, optimize=True)
        escritos.append(ruta)
    return escritos


if __name__ == "__main__":
    for ruta in generar():
        print(ruta.name, ruta.stat().st_size, "bytes")
