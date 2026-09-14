# -*- coding: utf-8 -*-
"""La beta instalable: lo que se puede probar en esta máquina.

PRD `docs/prd/2026-09-11-beta-instalable-en-el-ordenador-del-arquitecto.md`,
§12.1. Lo que NO se puede probar aquí (Python ausente, SmartScreen, la
autocarga en otro AutoCAD, el inicio de sesión de otra cuenta) está en §12.3 y
no se finge con ningún test.

Todo corre sobre un árbol de mentira (`ARCHMUSE_BASE`) y en puertos altos
(`ARCHMUSE_PUERTOS`): nada de esto toca `%LOCALAPPDATA%\\ArchMuse`, el paquete
de AutoCAD de verdad ni el servidor de desarrollo del puerto 5000.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
EMPAQUETADO = RAIZ / "empaquetado"
CAPA_B = EMPAQUETADO / "capa_b"

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="la beta es de Windows: uniones, mutex, netstat")


def _cargar(nombre: str, ruta: Path):
    cargador = importlib.machinery.SourceFileLoader(nombre, str(ruta))
    spec = importlib.util.spec_from_loader(nombre, cargador)
    modulo = importlib.util.module_from_spec(spec)
    cargador.exec_module(modulo)
    return modulo


def _puertos_libres(n: int = 4) -> list[int]:
    for inicio in range(15100, 16000, 10):
        abiertos = []
        try:
            for p in range(inicio, inicio + n):
                s = socket.socket()
                s.bind(("127.0.0.1", p))
                abiertos.append(s)
        except OSError:
            continue
        finally:
            for s in abiertos:
                s.close()
        if len(abiertos) == n:
            return list(range(inicio, inicio + n))
    pytest.skip("no hay cuatro puertos altos libres seguidos")


@pytest.fixture()
def arbol(tmp_path, monkeypatch):
    puertos = _puertos_libres()
    (tmp_path / "bundle").mkdir()
    monkeypatch.setenv("ARCHMUSE_BASE", str(tmp_path / "base"))
    monkeypatch.setenv("ARCHMUSE_BUNDLE", str(tmp_path / "bundle"))
    monkeypatch.setenv("ARCHMUSE_PUERTOS", "%d-%d" % (puertos[0], puertos[-1]))
    monkeypatch.setenv("ARCHMUSE_SIN_VENTANAS", "1")
    # Que ningún test llegue al AutoCAD de verdad: sin esto, `activar` leería y
    # escribiría TRUSTEDPATHS en el perfil real de quien ejecuta los tests.
    monkeypatch.setenv("ARCHMUSE_RAIZ_AUTOCAD", r"Software\ArchMuse-tests\ninguno")
    sys.path.insert(0, str(CAPA_B))
    try:
        local = _cargar("archmuse_local", CAPA_B / "archmuse_local.py")
        sys.modules["archmuse_local"] = local
        actualizador = _cargar("actualizador_beta", CAPA_B / "actualizador.pyw")
        yield local, actualizador, puertos, tmp_path
    finally:
        sys.path.remove(str(CAPA_B))
        sys.modules.pop("archmuse_local", None)


def _capa_falsa(local, version: str) -> Path:
    carpeta = Path(local.carpeta_app()) / version
    carpeta.mkdir(parents=True)
    (carpeta / "version.json").write_text(json.dumps({"version": version}), encoding="utf-8")
    (carpeta / "archmuse.lsp").write_text(";; lsp de la %s\n" % version, encoding="utf-8")
    return carpeta


def _paquete_falso(ruta: Path, version: str, extra: dict | None = None) -> Path:
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("version.json", json.dumps({"version": version}))
        for nombre in ("app.py", "lanzador.pyw", "actualizador.pyw", "archmuse_local.py"):
            z.writestr(nombre, "# %s\n" % nombre)
        z.writestr("archmuse.lsp", ";; lsp de la %s\n" % version)
        for nombre, contenido in (extra or {}).items():
            z.writestr(nombre, contenido)
    return ruta


# ── D-1: puertos, servidor.json, instancia única ───────────────────────────

def test_la_escalera_salta_el_puerto_ocupado_y_solo_escucha_en_loopback(arbol):
    local, _, puertos, _ = arbol
    ocupante = socket.socket()
    ocupante.bind(("127.0.0.1", puertos[0]))
    ocupante.listen(1)
    try:
        sock, puerto = local.elegir_socket()
        try:
            assert puerto == puertos[1]
            assert sock.getsockname() == ("127.0.0.1", puertos[1])
        finally:
            sock.close()
    finally:
        ocupante.close()


def test_sin_ningun_puerto_libre_se_dice_en_vez_de_arrancar_en_otro(arbol):
    local, _, puertos, _ = arbol
    ocupantes = []
    for p in puertos:
        s = socket.socket()
        s.bind(("127.0.0.1", p))
        ocupantes.append(s)
    try:
        with pytest.raises(RuntimeError, match="ningún puerto libre"):
            local.elegir_socket()
    finally:
        for s in ocupantes:
            s.close()


def test_un_servidor_json_ilegible_es_como_no_tenerlo(arbol):
    local, _, _, _ = arbol
    os.makedirs(local.base())
    Path(local.fichero_estado()).write_text("{a medias", encoding="utf-8")
    assert local.leer_estado() is None
    local.escribir_estado({"puerto": 5001, "version": "0.3.1", "pid": 42})
    assert local.leer_estado()["puerto"] == 5001


def test_un_servidor_json_obsoleto_no_mata_el_proceso_que_hereda_su_pid(arbol):
    """**El test que protege su AutoCAD.** Tras un apagón, `servidor.json` sigue
    ahí con un PID que Windows puede haber dado a otro programa. Parar ArchMuse
    no puede consistir en matar ese PID a ciegas."""
    local, _, puertos, _ = arbol
    inocente = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        local.escribir_estado({"puerto": puertos[0], "version": "0.3.1", "pid": inocente.pid})
        assert local.parar_servidor() is False
        time.sleep(0.5)
        assert inocente.poll() is None, "ha matado un proceso que no era ArchMuse"
        assert local.leer_estado() is None
    finally:
        inocente.kill()


def test_el_registro_del_servidor_no_entra_en_archmuse_informe(arbol):
    local, _, _, _ = arbol
    local.registrar("una línea")
    assert [p.name for p in Path(local.carpeta_registro()).iterdir()] == [
        "servidor-%s.log" % time.strftime("%Y-%m")]
    lsp = (RAIZ / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")
    assert "registro\\\\archmuse-*.log" in lsp
    assert "servidor-*.log" not in lsp


# ── D-2: dos capas, puntero, actualizar y volver ────────────────────────────

def test_apuntar_actual_y_volver_a_la_anterior_sin_borrar_nada(arbol):
    local, actualizador, _, tmp = arbol
    _capa_falsa(local, "0.3.1")
    _capa_falsa(local, "0.3.2")

    assert local.apuntar_actual("0.3.1") is None
    assert os.path.isjunction(local.carpeta_actual())
    assert local.apuntar_actual("0.3.2") == "0.3.1"
    assert local.version_activa() == "0.3.2"
    assert local.version_anterior() == "0.3.1"

    assert actualizador.volver(arrancar=False) == ("0.3.1", "0.3.2")
    assert local.version_activa() == "0.3.1"
    assert (tmp / "bundle" / "Contents" / "archmuse.lsp").read_text(encoding="utf-8") \
        == ";; lsp de la 0.3.1\n"
    assert actualizador.volver(arrancar=False) == ("0.3.2", "0.3.1")
    assert sorted(local.versiones_instaladas()) == ["0.3.1", "0.3.2"]


def test_apuntar_a_una_version_que_no_esta_no_toca_el_puntero(arbol):
    local, _, _, _ = arbol
    _capa_falsa(local, "0.3.1")
    local.apuntar_actual("0.3.1")
    with pytest.raises(ValueError):
        local.apuntar_actual("9.9.9")
    assert local.version_activa() == "0.3.1"


def test_volver_sin_version_anterior_lo_dice(arbol):
    local, actualizador, _, _ = arbol
    _capa_falsa(local, "0.3.1")
    local.apuntar_actual("0.3.1")
    with pytest.raises(RuntimeError, match="ninguna versión anterior"):
        actualizador.volver(arrancar=False)


def test_instalar_un_archmuse_y_reinstalar_la_misma_version(arbol):
    local, actualizador, _, tmp = arbol
    _capa_falsa(local, "0.3.1")
    local.apuntar_actual("0.3.1")

    paquete = _paquete_falso(tmp / "ArchMuse-0.3.2.archmuse", "0.3.2")
    assert actualizador.instalar(str(paquete), arrancar=False) == "0.3.2"
    assert local.version_activa() == "0.3.2"
    assert local.version_anterior() == "0.3.1"
    assert (Path(local.carpeta_app()) / "0.3.1" / "version.json").exists()
    assert (tmp / "bundle" / "Contents" / "archmuse.lsp").read_text(encoding="utf-8") \
        == ";; lsp de la 0.3.2\n"

    actualizador.instalar(str(paquete), arrancar=False)
    assert local.version_activa() == "0.3.2"
    assert not [n for n in os.listdir(local.carpeta_app()) if n.endswith(".instalando")]


@pytest.mark.parametrize("extra, motivo", [
    ({"planos/cliente.dxf": "0\nEOF"}, "plano dentro"),
    ({"otro/CLIENTE.DWG": "x"}, "plano dentro"),
    ({"../fuera.txt": "x"}, "ruta no permitida"),
])
def test_un_paquete_con_un_plano_o_una_ruta_fuera_no_se_instala(arbol, extra, motivo):
    local, actualizador, _, tmp = arbol
    paquete = _paquete_falso(tmp / "malo.archmuse", "0.3.2", extra)
    with pytest.raises(ValueError, match=motivo):
        actualizador.instalar(str(paquete), arrancar=False)
    assert not os.path.exists(local.carpeta_app())


def test_un_zip_que_no_es_de_archmuse_no_se_instala(arbol):
    _, actualizador, _, tmp = arbol
    with zipfile.ZipFile(tmp / "fotos.archmuse", "w") as z:
        z.writestr("foto.jpg", "x")
    with pytest.raises(ValueError, match="no es un paquete de ArchMuse"):
        actualizador.validar_paquete(str(tmp / "fotos.archmuse"))


def test_sin_paquete_de_autocad_activar_lo_dice_en_vez_de_callarse(arbol):
    """Hasta el 2026-09-14 `copiar_lsp_al_bundle` devolvía `False` y nadie lo
    miraba: el usuario se enteraba al teclear ARCHMUSE y leer «comando
    desconocido». Un fallo que no se dice no es un fallo menor, es invisible."""
    local, actualizador, _, tmp = arbol
    _capa_falsa(local, "0.3.1")
    (tmp / "bundle").rmdir()
    with pytest.raises(RuntimeError, match="comando ARCHMUSE"):
        actualizador.activar("0.3.1", arrancar=False)
    assert actualizador.main(["--activar", "0.3.1", "--sin-arrancar", "--silencioso"]) == 1
    log = Path(local.carpeta_registro()) / ("servidor-%s.log" % time.strftime("%Y-%m"))
    assert "comando ARCHMUSE" in log.read_text(encoding="utf-8")


def test_si_la_copia_del_lsp_falla_tambien_se_dice(arbol):
    local, actualizador, _, _ = arbol
    (_capa_falsa(local, "0.3.1") / "archmuse.lsp").unlink()
    with pytest.raises(RuntimeError, match="no se ha podido copiar el comando"):
        actualizador.activar("0.3.1", arrancar=False)


# ── la confianza de AutoCAD (enmienda del 2026-09-14, vía B) ────────────────

NUESTRA = r"C:\Users\x\AppData\Roaming\Autodesk\ApplicationPlugins\ArchMuse.bundle\Contents"

#: Lo que un arquitecto puede tener ya en TRUSTEDPATHS. Las parecidas a la
#: nuestra están a propósito: son las que un «quitar» descuidado se llevaría.
AJENAS = [
    r"C:\suyo",
    "",                                                  # un `;;` que ya tenía
    r"D:\rutinas\...",
    NUESTRA + r"\...",                                   # la nuestra CON subcarpetas: no es la nuestra
    NUESTRA.replace("ArchMuse.bundle", "Otro.bundle"),   # el paquete de al lado
    r'"C:\con comillas"',
]


def test_anadir_nuestra_ruta_no_duplica_ni_reordena(arbol):
    local, _, _, _ = arbol
    assert local.con_nuestra_ruta("", NUESTRA) == NUESTRA
    assert local.con_nuestra_ruta(r"C:\suyo", NUESTRA) == r"C:\suyo;" + NUESTRA
    assert local.con_nuestra_ruta("C:\\suyo;", NUESTRA) == r"C:\suyo;" + NUESTRA
    ya = r"C:\suyo;" + NUESTRA.upper() + "\\"
    assert local.con_nuestra_ruta(ya, NUESTRA) == ya


def test_guardian_quitar_solo_se_lleva_nuestra_ruta(arbol):
    """**Condición 2 de Pablo.** El desinstalador quita nuestra ruta y ninguna
    otra: las del arquitecto salen idénticas, carácter a carácter, esté la
    nuestra delante, en medio o detrás, y aunque haya rutas que se le parecen."""
    local, _, _, _ = arbol
    ajenas = ";".join(AJENAS)
    assert local.sin_nuestra_ruta(ajenas, NUESTRA) == ajenas
    for i in range(len(AJENAS) + 1):
        con_la_nuestra = ";".join(AJENAS[:i] + [NUESTRA] + AJENAS[i:])
        assert local.sin_nuestra_ruta(con_la_nuestra, NUESTRA) == ajenas, i
    assert local.sin_nuestra_ruta(local.con_nuestra_ruta(ajenas, NUESTRA), NUESTRA) == ajenas
    assert local.sin_nuestra_ruta(NUESTRA, NUESTRA) == ""


def _borrar_clave(raiz, clave: str) -> None:
    import winreg
    try:
        with winreg.OpenKey(raiz, clave) as k:
            hijas = []
            while True:
                try:
                    hijas.append(winreg.EnumKey(k, len(hijas)))
                except OSError:
                    break
    except FileNotFoundError:
        return
    for hija in hijas:
        _borrar_clave(raiz, clave + "\\" + hija)
    winreg.DeleteKey(raiz, clave)


@pytest.fixture()
def autocad_falso(arbol, monkeypatch):
    """Un `HKCU\\Software\\Autodesk\\AutoCAD` de mentira: nunca el de verdad."""
    import uuid
    import winreg
    contenedor = r"Software\ArchMuse-tests\%s" % uuid.uuid4().hex
    raiz = contenedor + r"\AutoCAD"
    monkeypatch.setenv("ARCHMUSE_RAIZ_AUTOCAD", raiz)
    monkeypatch.setattr(arbol[0], "autocad_abierto", lambda: False)

    def perfil(version, producto, nombre, valor):
        clave = r"%s\%s\%s\Profiles\%s\Variables" % (raiz, version, producto, nombre)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, clave) as k:
            if valor is not None:
                winreg.SetValueEx(k, "TRUSTEDPATHS", 0, winreg.REG_SZ, valor)
        return clave

    try:
        yield arbol, perfil
    finally:
        _borrar_clave(winreg.HKEY_CURRENT_USER, contenedor)
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\ArchMuse-tests")
        except OSError:
            pass


def _tp(clave: str):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave) as k:
        return winreg.QueryValueEx(k, "TRUSTEDPATHS")[0]


def test_anadir_y_quitar_en_cada_perfil_desde_r24_y_en_ninguno_mas(autocad_falso):
    (local, _, _, _), perfil = autocad_falso
    nuestra = local.ruta_de_confianza()
    anterior = perfil("R23.1", "ACAD-3001:40A", "<<Perfil sin nombre>>", r"C:\suyo")
    estudio = perfil("R24.0", "ACAD-4101:409", "Estudio", r"C:\suyo;D:\rutinas\...")
    vacio = perfil("R26.0", "ACAD-A101:40A", "<<Perfil sin nombre>>", "")
    sin_valor = perfil("R26.0", "ACAD-A101:40A", "Planos", None)
    assert local.perfiles_de_autocad() == sorted([estudio, vacio, sin_valor])

    local.anadir_confianza()
    assert [escrito for _, escrito in local.anadir_confianza()] == [False, False, False]
    assert _tp(estudio) == r"C:\suyo;D:\rutinas\...;" + nuestra
    assert _tp(vacio) == nuestra and _tp(sin_valor) == nuestra
    assert _tp(anterior) == r"C:\suyo", "AutoCAD 2020 no carga el bundle: no se toca"

    local.quitar_confianza()
    assert _tp(estudio) == r"C:\suyo;D:\rutinas\..."
    assert _tp(vacio) == "" and _tp(sin_valor) == ""
    assert _tp(anterior) == r"C:\suyo"


def test_desinstalar_quita_nuestra_ruta_y_deja_las_suyas(autocad_falso):
    (local, actualizador, _, _), perfil = autocad_falso
    suyas = ";".join(AJENAS)
    clave = perfil("R26.0", "ACAD-A101:40A", "<<Perfil sin nombre>>", suyas)
    local.anadir_confianza()
    assert _tp(clave) != suyas
    assert actualizador.main(["--desinstalar", "--silencioso"]) == 0
    assert _tp(clave) == suyas


def test_activar_anade_nuestra_ruta_de_confianza(autocad_falso):
    (local, actualizador, _, _), perfil = autocad_falso
    clave = perfil("R26.0", "ACAD-A101:40A", "<<Perfil sin nombre>>", r"C:\suyo")
    _capa_falsa(local, "0.3.1")
    actualizador.activar("0.3.1", arrancar=False)
    assert _tp(clave) == r"C:\suyo;" + local.ruta_de_confianza()


def test_con_autocad_abierto_no_se_escribe_la_confianza_y_se_dice(autocad_falso, monkeypatch):
    """Condición 3a: nunca se escribe TRUSTEDPATHS con AutoCAD abierto, porque
    puede pisarlo al cerrarse. Ni al activar ni al desinstalar; y si no hay
    nada que escribir, una actualización con AutoCAD abierto sí sigue."""
    (local, actualizador, _, _), perfil = autocad_falso
    clave = perfil("R26.0", "ACAD-A101:40A", "<<Perfil sin nombre>>", r"C:\suyo")
    _capa_falsa(local, "0.3.1")
    monkeypatch.setattr(local, "autocad_abierto", lambda: True)
    with pytest.raises(RuntimeError, match="AutoCAD está abierto"):
        actualizador.activar("0.3.1", arrancar=False)
    assert _tp(clave) == r"C:\suyo"
    assert local.version_activa() is None, "ha movido el puntero antes de fallar"

    local.anadir_confianza()
    actualizador.activar("0.3.1", arrancar=False)
    assert local.version_activa() == "0.3.1"

    with pytest.raises(RuntimeError, match="AutoCAD está abierto"):
        actualizador.desinstalar()
    assert _tp(clave) == r"C:\suyo;" + local.ruta_de_confianza()


def test_reponer_al_iniciar_sesion_solo_con_autocad_cerrado_y_sin_lanzar(autocad_falso, monkeypatch):
    (local, _, _, _), perfil = autocad_falso
    nuevo = perfil("R26.0", "ACAD-A101:40A", "Perfil nuevo", "")
    monkeypatch.setattr(local, "autocad_abierto", lambda: True)
    local.reponer_confianza()
    assert _tp(nuevo) == ""
    monkeypatch.setattr(local, "autocad_abierto", lambda: False)
    local.reponer_confianza()
    assert _tp(nuevo) == local.ruta_de_confianza()
    log = Path(local.carpeta_registro()) / ("servidor-%s.log" % time.strftime("%Y-%m"))
    texto = log.read_text(encoding="utf-8")
    assert "sin reponer: AutoCAD está abierto" in texto
    assert "repuesta en 1 perfil" in texto


def test_el_lanzador_repone_la_confianza_despues_de_quedarse_con_el_mutex():
    fuente = (CAPA_B / "lanzador.pyw").read_text(encoding="utf-8")
    assert fuente.index("local.mutex_unico(") < fuente.index("local.reponer_confianza()") \
        < fuente.index("local.elegir_socket()")


def test_instalar_y_desinstalar_esperan_a_que_autocad_este_cerrado():
    codigo = _secciones_iss()["Code"]
    preparar = codigo[codigo.index("function PrepareToInstall"):]
    assert preparar.index("EsperarAutoCADCerrado()") < preparar.index("--parar")
    assert re.search(r"function InitializeUninstall\(\): Boolean;\s*begin\s*"
                     r"Result := EsperarAutoCADCerrado\(\);", codigo)
    esperar = codigo[codigo.index("function EsperarAutoCADCerrado"):codigo.index("function InitializeUninstall")]
    assert "IDCANCEL) = IDCANCEL" in esperar, "en silencioso tiene que cancelar, no dar vueltas"
    assert "except" in esperar


def test_el_desinstalador_se_entera_si_no_puede_quitar_la_ruta():
    secciones = _secciones_iss()
    assert "--desinstalar" not in secciones.get("UninstallRun", "")
    codigo = secciones["Code"]
    inicio = codigo.index("procedure CurUninstallStepChanged")
    cuerpo = codigo[inicio:codigo.index("\nend;", inicio)]
    assert "--desinstalar" in cuerpo and "Quitada := (Codigo = 0)" in cuerpo
    assert "if not Quitada then" in cuerpo and "rutas de confianza" in cuerpo


def test_sin_ningun_autocad_no_hay_perfiles_ni_error(autocad_falso):
    (local, _, _, _), _ = autocad_falso
    assert local.perfiles_de_autocad() == []
    assert local.anadir_confianza() == []


# ── lo que se construye ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def construido(tmp_path_factory):
    construir = _cargar("construir_beta", EMPAQUETADO / "construir.py")
    destino = tmp_path_factory.mktemp("salida")
    carpeta = construir.capa_b(destino / "app")
    return construir, carpeta, construir.paquete_archmuse(carpeta)


def test_la_capa_b_declara_las_dos_versiones_que_trae(construido):
    _, carpeta, _ = construido
    from analyzer.version import VERSION_DEL_REPOSITORIO
    lsp = (RAIZ / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")
    datos = json.loads((carpeta / "version.json").read_text(encoding="utf-8"))
    assert datos["version"] == VERSION_DEL_REPOSITORIO == carpeta.name
    assert datos["lsp"] == re.search(r'\*am:version-corta\* "([^"]+)"', lsp).group(1)
    assert (carpeta / "archmuse.lsp").read_bytes() == (RAIZ / "autocad" / "archmuse.lsp").read_bytes()


def test_el_archmuse_no_lleva_planos_ni_cache_y_se_deja_instalar(construido, arbol):
    _, carpeta, paquete = construido
    _, actualizador, _, _ = arbol
    nombres = zipfile.ZipFile(paquete).namelist()
    assert not [n for n in nombres if n.lower().endswith((".dxf", ".dwg"))]
    assert not [n for n in nombres if "__pycache__" in n]
    assert actualizador.validar_paquete(str(paquete)) == carpeta.name
    assert paquete.stat().st_size < 5e6, "la actualización tenía que ser de unos pocos MB"


def test_el_bundle_carga_el_lsp_que_deja_el_actualizador():
    raiz = ET.parse(EMPAQUETADO / "bundle" / "PackageContents.xml").getroot()
    entradas = raiz.findall("./Components/ComponentEntry")
    assert [e.get("ModuleName") for e in entradas] == ["./Contents/archmuse.lsp"]


def test_el_instalador_no_pide_administrador_ni_crea_tareas_programadas():
    iss = (EMPAQUETADO / "ArchMuse-Beta.iss").read_text(encoding="utf-8-sig")
    assert "PrivilegesRequired=lowest" in iss
    assert "HKLM" not in iss
    # `schtasks /SC ONLOGON` sin elevar da «Acceso denegado» (2026-09-13): el
    # arranque al iniciar sesión es un acceso directo en Inicio.
    assert not re.search(r"^(Filename|Parameters):.*schtasks", iss, re.M | re.I)
    assert "{userstartup}" in iss


def _secciones_iss() -> dict:
    iss = (EMPAQUETADO / "ArchMuse-Beta.iss").read_text(encoding="utf-8-sig")
    return dict(re.findall(r"^\[(\w+)\][ \t]*$(.*?)(?=^\[\w+\][ \t]*$|\Z)", iss, re.M | re.S))


def test_el_instalador_se_entera_si_la_activacion_falla():
    """`[Run]` de Inno Setup no mira el código de salida: con `--activar` allí,
    una activación fallida terminaba en la pantalla de «Listo»."""
    secciones = _secciones_iss()
    assert "--activar" not in secciones.get("Run", "")
    codigo = secciones["Code"]
    assert "--activar" in codigo and "Codigo <> 0" in codigo
    assert "wpFinished" in codigo and "no ha quedado listo" in codigo


def test_el_instalador_avisa_de_la_ruta_de_confianza_antes_de_instalar():
    """**Condición 1 de Pablo:** antes de instalar y no en letra pequeña, que se
    añade la carpeta a las rutas de confianza, qué significa y que se deshace
    al desinstalar. Una página propia delante de todo, y su botón es «Instalar»."""
    codigo = _secciones_iss()["Code"]
    inicio = codigo.index("CreateOutputMsgPage(wpWelcome")
    pagina = codigo[inicio:codigo.index("end;", inicio)]
    texto = re.sub(r"'\s*\+\s*'", "", pagina)             # une las cadenas partidas
    assert "RUTAS DE CONFIANZA" in texto
    assert "cargará sin preguntar" in texto                # qué significa
    assert "ArchMuse.bundle\\Contents" in texto            # qué carpeta, exacta
    assert "otras rutas de confianza no se tocan" in texto
    assert "Se deshace al desinstalar" in texto
    assert "AutoCAD tiene que estar cerrado" in texto
    assert "volverá a ponerla" in texto                    # la reposición al iniciar sesión, dicha
    assert "MsgLabel.Font.Size" in pagina
    # Que se VEA, no sólo que esté escrito. El 2026-09-14 las capturas del
    # asistente enseñaron dos fallos que este test no veía: la etiqueta no crece
    # al subir la letra (texto cortado con media página libre) y, con ~1.000
    # caracteres, la ruta cortada. El límite es el texto que la captura enseñó
    # entero (677) con poco margen; para superarlo, hay que volver a mirarlo.
    assert "MsgLabel.Height := ConfianzaPagina.SurfaceHeight" in pagina
    visibles = sum(len(c) for c in re.findall(r"'([^']*)'", texto))
    assert visibles <= 700, "%d caracteres: mira la página en pantalla antes de subir el límite" % visibles
    assert re.search(r"ConfianzaPagina\.ID then\s+WizardForm\.NextButton\.Caption := "
                     r"SetupMessage\(msgButtonInstall\)", codigo)


# ── el lanzador de verdad, en un proceso aparte ─────────────────────────────

def test_el_lanzador_arranca_una_sola_vez_declara_su_puerto_y_se_deja_parar(construido, arbol):
    construir, _, _ = construido
    local, _, puertos, _ = arbol
    carpeta = construir.capa_b(Path(local.carpeta_app()))
    local.apuntar_actual(carpeta.name)
    try:
        local.arrancar_lanzador()
        vivo = local.esperar_servidor(carpeta.name, segundos=90)
        assert vivo is not None, (Path(local.carpeta_registro()).glob("*.log"), "no arranca")
        assert vivo["puerto"] in puertos
        assert local.pid_escuchando(vivo["puerto"]) == vivo["pid"]

        local.arrancar_lanzador()          # el segundo tiene que retirarse
        time.sleep(6)
        assert local.leer_estado()["pid"] == vivo["pid"]
        assert local.salud(vivo["puerto"]) is not None

        assert local.parar_servidor() is True
        assert local.leer_estado() is None
        assert local.salud(vivo["puerto"], timeout=0.5) is None
    finally:
        estado = local.leer_estado()
        if estado:
            local.matar_arbol(estado["pid"])
