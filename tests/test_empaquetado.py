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
