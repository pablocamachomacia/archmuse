"""Genera un instalador DE CAPTURA: las mismas tres pantallas que el de verdad, sin ningún efecto.

    python generar_iss_captura.py <version> <captura.iss> <carpeta-de-salida>

**Para qué.** Las pantallas del instalador se miden con capturas (el texto de la
página de rutas de confianza está ajustado a 11 pt para que quepa). Pero el
instalador de verdad para AutoCAD, termina procesos, escribe en el registro y
activa ArchMuse: ejecutarlo para hacer una foto en el ordenador de trabajo
estropea la instalación que hay.

**Lo que se copia TAL CUAL de `empaquetado/ArchMuse-Beta.iss`**, leído cada vez,
para que la captura no pueda enseñar un texto que ya no es el que se instala:
`[Setup]` (icono, imágenes, estilo, tamaño), `[Languages]`, `[Messages]`, el
procedimiento `InitializeWizard` entero (la página de rutas de confianza) y los
argumentos de `CreateOutputProgressPage`; de `esperar_actualizador.iss`, el texto
que enseña mientras espera y el límite de `LIMITE_ACTIVAR_S`.

**Lo que se cambia**, para que no toque nada: otro `AppId`, otra carpeta, sin
desinstalador ni entrada en «Aplicaciones instaladas», sin `[Files]`, `[Icons]`,
`[Registry]` ni ninguna parada de procesos. La pantalla «Poniendo en marcha» se
enseña unos segundos contando como la de verdad.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
EMPAQUETADO = RAIZ / "empaquetado"
ISS = EMPAQUETADO / "ArchMuse-Beta.iss"
ESPERA = EMPAQUETADO / "esperar_actualizador.iss"

#: Directivas de [Setup] que la captura no hereda: la identidad y todo lo que
#: deja rastro en la máquina.
NO_SE_HEREDAN = {"AppId", "DefaultDirName", "OutputDir", "OutputBaseFilename",
                 "ChangesAssociations", "SetupLogging", "UninstallDisplayIcon",
                 "UninstallDisplayName", "CloseApplications"}

#: Cuántos segundos se queda en «Poniendo en marcha».
SEGUNDOS_EN_MARCHA = 15


def _secciones(texto: str) -> dict:
    return dict(re.findall(r"^\[(\w+)\][ \t]*$(.*?)(?=^\[\w+\][ \t]*$|\Z)", texto, re.M | re.S))


def _uno(patron: str, texto: str, que: str, flags: int = re.S) -> re.Match:
    m = re.search(patron, texto, flags)
    if not m:
        raise SystemExit("No encuentro %s en el .iss: el generador de capturas se ha quedado atrás." % que)
    return m


def generar(version: str, destino: Path, salida: Path, imagenes: Path | None = None,
            nombre: str | None = None) -> Path:
    """`imagenes`: una carpeta con `cabecera-*.png` y `lateral-*.png` que sustituyen
    a las del instalador, para probar variantes en el asistente de verdad."""
    real = ISS.read_text(encoding="utf-8-sig")
    secciones = _secciones(real)
    codigo = secciones["Code"]
    espera = ESPERA.read_text(encoding="utf-8")

    def heredada(linea: str) -> bool:
        directiva = re.match(r"(\w+)=", linea)
        if imagenes and directiva and directiva.group(1) in ("WizardImageFile", "WizardSmallImageFile"):
            return False
        return not (directiva and directiva.group(1) in NO_SE_HEREDAN)

    setup = [l for l in secciones["Setup"].strip().splitlines() if heredada(l)]
    if imagenes:
        for directiva, patron in (("WizardSmallImageFile", "cabecera-*.png"), ("WizardImageFile", "lateral-*.png")):
            ficheros = sorted(imagenes.glob(patron), key=lambda f: int(f.stem.rsplit("-", 1)[1]))
            if not ficheros:
                raise SystemExit("No hay %s en %s" % (patron, imagenes))
            setup.append("%s=%s" % (directiva, ",".join(str(f) for f in ficheros)))
    setup += [
        "; --- Sólo en la captura ---",
        "AppId=ArchMuse-captura-de-pantallas",
        r"DefaultDirName={localappdata}\ArchMuse-captura-de-pantallas",
        "Uninstallable=no",
        "CreateUninstallRegKey=no",
        "SourceDir=%s" % EMPAQUETADO,
        "OutputDir=%s" % salida,
        "OutputBaseFilename=%s" % (nombre or "ArchMuse-captura-%s" % version),
    ]

    inicializar = _uno(r"^procedure InitializeWizard\(\);.*?^end;", codigo,
                       "procedure InitializeWizard", re.M | re.S).group(0)
    progreso = _uno(r"CreateOutputProgressPage\((.*?)\);", codigo, "CreateOutputProgressPage").group(1)
    limite = _uno(r"LIMITE_ACTIVAR_S = (\d+);", codigo, "LIMITE_ACTIVAR_S").group(1)
    texto_espera = _uno(r"Pagina\.SetText\((.*?)\);", espera, "Pagina.SetText en esperar_actualizador").group(1)

    captura = """; GENERADO por herramientas/capturas_instalador/generar_iss_captura.py. No editar.
; Instalador de CAPTURA: mismas pantallas que ArchMuse-Beta.iss, ningún efecto.
#define Version "{version}"

[Setup]
{setup}

[Languages]
{languages}

[Messages]
{messages}

[Code]
const
  LIMITE_ACTIVAR_S = {limite};

var
  ConfianzaPagina: TOutputMsgWizardPage;

{inicializar}

procedure CurStepChanged(CurStep: TSetupStep);
var
  Pagina: TOutputProgressWizardPage;
  Transcurridos, Vueltas: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    Pagina := CreateOutputProgressPage({progreso});
    Pagina.Show;
    try
      for Vueltas := 0 to {vueltas} do
      begin
        Transcurridos := Vueltas div 4;
        Pagina.SetText({texto_espera});
        Pagina.SetProgress(Transcurridos, LIMITE_ACTIVAR_S);
        Sleep(250);
      end;
    finally
      Pagina.Hide;
    end;
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = ConfianzaPagina.ID then
    WizardForm.NextButton.Caption := SetupMessage(msgButtonInstall);
end;
""".format(version=version, setup="\n".join(setup), languages=secciones["Languages"].strip(),
           messages=secciones["Messages"].strip(), limite=limite, inicializar=inicializar,
           progreso=progreso, vueltas=SEGUNDOS_EN_MARCHA * 4, texto_espera=texto_espera)
    destino.write_text(captura, encoding="utf-8-sig")
    return destino


if __name__ == "__main__":
    version, destino, salida = sys.argv[1:4]
    print(generar(version, Path(destino), Path(salida)))
