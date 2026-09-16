# -*- coding: utf-8 -*-
"""Actualizaciones automáticas por canal, firmadas (PRD 2026-09-15).

Todo contra un **GitHub simulado** —un servidor HTTP local que imita la lista de
releases y sirve los paquetes— y un árbol de mentira (`ARCHMUSE_BASE`). Los
paquetes se firman con una clave de test; la de ArchMuse vive fuera del
repositorio.

Los casos del PRD, §8.3: versión nueva, igual y más vieja; canal equivocado;
firma mala; fichero manipulado; sin red; GitHub caído; GitHub lento. Y la vuelta
completa (§8.4): comprobar → pendiente → instalar pendiente → volver atrás.
"""
from __future__ import annotations

import http.server
import importlib.machinery
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
EMPAQUETADO = RAIZ / "empaquetado"
CAPA_B = EMPAQUETADO / "capa_b"
LSP = (RAIZ / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")
SEMILLA = bytes(range(32))
OTRA_SEMILLA = bytes(range(100, 132))


def _cargar(nombre: str, ruta: Path):
    cargador = importlib.machinery.SourceFileLoader(nombre, str(ruta))
    spec = importlib.util.spec_from_loader(nombre, cargador)
    modulo = importlib.util.module_from_spec(spec)
    cargador.exec_module(modulo)
    return modulo


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHMUSE_BASE", str(tmp_path / "base"))
    monkeypatch.setenv("ARCHMUSE_BUNDLE", str(tmp_path / "bundle"))
    monkeypatch.setenv("ARCHMUSE_SIN_VENTANAS", "1")
    monkeypatch.setenv("ARCHMUSE_SIN_ACTUALIZACIONES", "1")
    monkeypatch.setenv("ARCHMUSE_RAIZ_AUTOCAD", r"Software\ArchMuse-tests\ninguno")
    monkeypatch.setenv("ARCHMUSE_PUERTOS", "15990-15993")
    (tmp_path / "bundle").mkdir()
    guardados = {n: sys.modules.get(n) for n in ("archmuse_local", "firma", "actualizaciones")}
    sys.path.insert(0, str(CAPA_B))
    try:
        local = _cargar("archmuse_local", CAPA_B / "archmuse_local.py")
        sys.modules["archmuse_local"] = local
        firma = _cargar("firma", CAPA_B / "firma.py")
        firma.CLAVE_PUBLICA_HEX = firma.clave_publica_de(SEMILLA).hex()
        sys.modules["firma"] = firma
        act = _cargar("actualizaciones", CAPA_B / "actualizaciones.py")
        sys.modules["actualizaciones"] = act
        actualizador = _cargar("actualizador_de_tests", CAPA_B / "actualizador.pyw")
        yield local, firma, act, actualizador, tmp_path
    finally:
        sys.path.remove(str(CAPA_B))
        for nombre, modulo in guardados.items():
            if modulo is None:
                sys.modules.pop(nombre, None)
            else:
                sys.modules[nombre] = modulo


def _instalada(local, version: str) -> None:
    carpeta = Path(local.carpeta_app()) / version
    carpeta.mkdir(parents=True)
    (carpeta / "version.json").write_text(json.dumps({"version": version}), encoding="utf-8")
    (carpeta / "archmuse.lsp").write_bytes((";; lsp de la %s\n" % version).encode("utf-8"))
    local.apuntar_actual(version)


def _paquete(firma, destino: Path, version: str, semilla: bytes = SEMILLA, retocar=None) -> Path:
    with tempfile.TemporaryDirectory() as d:
        carpeta = Path(d)
        (carpeta / "version.json").write_bytes(json.dumps({"version": version}).encode("utf-8"))
        for nombre in ("app.py", "lanzador.pyw", "actualizador.pyw", "archmuse_local.py"):
            (carpeta / nombre).write_bytes(("# %s\n" % nombre).encode("utf-8"))
        (carpeta / "archmuse.lsp").write_bytes((";; lsp de la %s\n" % version).encode("utf-8"))
        firma.firmar_carpeta(str(carpeta), semilla)
        if retocar:
            retocar(carpeta)
        with zipfile.ZipFile(destino, "w") as z:
            for fichero in sorted(carpeta.iterdir()):
                z.write(fichero, fichero.name)
    return destino


class GitHubFalso:
    """La lista de releases de GitHub y sus descargas, en local."""

    def __init__(self):
        self.releases = []
        self.ficheros = {}
        self.estado = 200
        self.retraso = 0.0

    def __enter__(self):
        falso = self

        class Manejador(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                time.sleep(falso.retraso)
                ruta = self.path.split("?")[0]
                if ruta == "/repos/x/releases":
                    cuerpo = json.dumps(falso.releases).encode("utf-8")
                else:
                    cuerpo = falso.ficheros.get(ruta)
                estado = falso.estado if falso.estado != 200 else (200 if cuerpo is not None else 404)
                try:
                    self.send_response(estado)
                    self.send_header("Content-Length", str(len(cuerpo or b"")))
                    self.end_headers()
                    if estado == 200:
                        self.wfile.write(cuerpo)
                except OSError:
                    pass

        self.servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self.servidor.daemon_threads = True
        self.url = "http://127.0.0.1:%d" % self.servidor.server_address[1]
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *args):
        self.servidor.shutdown()
        self.servidor.server_close()

    def publicar(self, version: str, datos: bytes, prerelease: bool, nombre: str | None = None):
        nombre = nombre or "ArchMuse-%s.archmuse" % version
        self.ficheros["/descargas/" + nombre] = datos
        self.releases.append({"tag_name": "v" + version, "draft": False, "prerelease": prerelease,
                              "assets": [{"name": nombre,
                                          "browser_download_url": self.url + "/descargas/" + nombre}]})

    @property
    def api(self) -> str:
        return self.url + "/repos/x/releases?per_page=30"


def _registro(local) -> str:
    carpeta = Path(local.carpeta_registro())
    return "".join(f.read_text(encoding="utf-8") for f in carpeta.glob("servidor-*.log"))


# ── 1. La firma ─────────────────────────────────────────────────────────────

def test_ed25519_da_los_vectores_de_la_rfc_8032(mundo):
    _, firma, _, _, _ = mundo
    secreta = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
    assert firma.clave_publica_de(secreta).hex() == \
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c"
    assert firma.firmar(secreta, b"\x72").hex() == (
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
        "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00")


def test_ed25519_firma_igual_que_cryptography(mundo):
    ed25519 = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    _, firma, _, _, _ = mundo
    for n in range(5):
        semilla, mensaje = os.urandom(32), os.urandom(n * 91)
        clave = ed25519.Ed25519PrivateKey.from_private_bytes(semilla)
        assert clave.sign(mensaje) == firma.firmar(semilla, mensaje)


def test_un_paquete_firmado_se_verifica(mundo, tmp_path):
    _, firma, _, _, _ = mundo
    assert firma.verificar_paquete(str(_paquete(firma, tmp_path / "p.archmuse", "0.3.9"))) == "0.3.9"


def test_la_firma_de_otra_clave_no_vale(mundo, tmp_path):
    _, firma, _, _, _ = mundo
    paquete = _paquete(firma, tmp_path / "p.archmuse", "0.3.9", semilla=OTRA_SEMILLA)
    with pytest.raises(ValueError, match="no es la de ArchMuse"):
        firma.verificar_paquete(str(paquete))


@pytest.mark.parametrize("retoque, motivo", [
    (lambda c: (c / "app.py").write_bytes(b"import os  # otro codigo\n"), "modificado"),
    (lambda c: (c / "extra.py").write_bytes(b"x = 1\n"), "no es el que se firmó"),
    (lambda c: (c / "archmuse.lsp").unlink(), "no es el que se firmó"),
    (lambda c: (c / "version.json").write_bytes(b'{"version": "9.9.9"}'), "modificado"),
])
def test_un_paquete_manipulado_despues_de_firmar_no_vale(mundo, tmp_path, retoque, motivo):
    _, firma, _, _, _ = mundo
    paquete = _paquete(firma, tmp_path / "p.archmuse", "0.3.9", retocar=retoque)
    with pytest.raises(ValueError, match=motivo):
        firma.verificar_paquete(str(paquete))


def test_un_paquete_sin_firmar_no_se_instala_ni_con_doble_clic(mundo, tmp_path):
    local, firma, _, actualizador, _ = mundo
    _instalada(local, "0.3.8")
    paquete = tmp_path / "sin_firmar.archmuse"
    with zipfile.ZipFile(paquete, "w") as z:
        z.writestr("version.json", json.dumps({"version": "0.3.9"}))
        for nombre in ("app.py", "lanzador.pyw", "actualizador.pyw", "archmuse_local.py", "archmuse.lsp"):
            z.writestr(nombre, "#\n")
    with pytest.raises(ValueError, match="no está firmado"):
        actualizador.instalar(str(paquete), arrancar=False)
    assert local.version_activa() == "0.3.8"
    assert not (Path(local.carpeta_app()) / "0.3.9").exists()


# ── 2. El canal ─────────────────────────────────────────────────────────────

def test_el_canal_es_estable_si_nadie_dice_otra_cosa_y_se_cambia_con_una_orden(mundo):
    _, _, act, actualizador, _ = mundo
    assert act.canal() == "estable"
    assert actualizador.main(["--canal", "prueba", "--silencioso"]) == 0
    assert act.canal() == "prueba"
    assert actualizador.main(["--canal", "estable", "--silencioso"]) == 0
    assert act.canal() == "estable"


def test_un_canal_que_no_existe_no_se_guarda(mundo):
    _, _, act, actualizador, _ = mundo
    assert actualizador.main(["--canal", "beta", "--silencioso"]) == 1
    assert act.canal() == "estable"


# ── 3. Comprobar contra un GitHub simulado ──────────────────────────────────

@pytest.mark.parametrize("instalada, publicada, aviso", [
    ("0.3.8", "0.3.9", "0.3.9"),     # nueva
    ("0.3.9", "0.3.9", None),        # igual
    ("0.3.9", "0.3.8", None),        # más vieja
])
def test_solo_avisa_de_una_version_mas_nueva(mundo, monkeypatch, tmp_path, instalada, publicada, aviso):
    local, firma, act, _, _ = mundo
    _instalada(local, instalada)
    with GitHubFalso() as github:
        github.publicar(publicada, _paquete(firma, tmp_path / "p.archmuse", publicada).read_bytes(), False)
        monkeypatch.setenv("ARCHMUSE_URL_ACTUALIZACIONES", github.api)
        resultado = act.comprobar()
    pendiente = act.leer_pendiente()
    if aviso is None:
        assert resultado is None and pendiente is None
    else:
        assert resultado["version"] == aviso and pendiente["version"] == aviso
        assert firma.verificar_paquete(pendiente["fichero"]) == aviso


def test_el_canal_estable_no_ve_las_prereleases_y_el_de_prueba_si(mundo, monkeypatch, tmp_path):
    local, firma, act, _, _ = mundo
    _instalada(local, "0.3.8")
    with GitHubFalso() as github:
        github.publicar("0.3.9", _paquete(firma, tmp_path / "p.archmuse", "0.3.9").read_bytes(), True)
        monkeypatch.setenv("ARCHMUSE_URL_ACTUALIZACIONES", github.api)
        assert act.comprobar() is None, "el canal estable ha visto una prerelease"
        act.fijar_canal("prueba")
        assert act.comprobar()["version"] == "0.3.9"


def test_el_canal_de_prueba_ve_tambien_una_release_estable_mas_nueva(mundo, monkeypatch, tmp_path):
    local, firma, act, _, _ = mundo
    _instalada(local, "0.3.8")
    act.fijar_canal("prueba")
    with GitHubFalso() as github:
        github.publicar("0.3.9", _paquete(firma, tmp_path / "a.archmuse", "0.3.9").read_bytes(), True)
        github.publicar("0.3.10", _paquete(firma, tmp_path / "b.archmuse", "0.3.10").read_bytes(), False)
        monkeypatch.setenv("ARCHMUSE_URL_ACTUALIZACIONES", github.api)
        assert act.comprobar()["version"] == "0.3.10"


@pytest.mark.parametrize("como", ["firma_mala", "manipulado", "otra_version"])
def test_un_paquete_que_no_cuadra_no_deja_aviso_y_dice_por_que(mundo, monkeypatch, tmp_path, como):
    local, firma, act, _, _ = mundo
    _instalada(local, "0.3.8")
    if como == "firma_mala":
        datos = _paquete(firma, tmp_path / "p.archmuse", "0.3.9", semilla=OTRA_SEMILLA).read_bytes()
    elif como == "manipulado":
        datos = _paquete(firma, tmp_path / "p.archmuse", "0.3.9",
                         retocar=lambda c: (c / "app.py").write_bytes(b"malo\n")).read_bytes()
    else:
        datos = _paquete(firma, tmp_path / "p.archmuse", "0.3.10").read_bytes()
    with GitHubFalso() as github:
        github.publicar("0.3.9", datos, False)
        monkeypatch.setenv("ARCHMUSE_URL_ACTUALIZACIONES", github.api)
        assert act.comprobar() is None
    assert act.leer_pendiente() is None
    assert "se descarta" in _registro(local)
    assert not [f for f in os.listdir(act.carpeta_descargas()) if f.endswith(".parte")]


def test_sin_red_no_hay_aviso_ni_espera(mundo, monkeypatch, tmp_path):
    local, firma, act, _, _ = mundo
    _instalada(local, "0.3.8")
    # Un aviso de una sesión anterior: sin poder comprobar, tampoco se enseña.
    viejo = _paquete(firma, tmp_path / "viejo.archmuse", "0.3.9")
    Path(act.fichero_pendiente()).parent.mkdir(parents=True, exist_ok=True)
    Path(act.fichero_pendiente()).write_text(json.dumps({"version": "0.3.9", "fichero": str(viejo)}))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    monkeypatch.setenv("ARCHMUSE_URL_ACTUALIZACIONES", "http://127.0.0.1:%d/repos/x/releases" % puerto)
    t = time.monotonic()
    assert act.comprobar() is None
    assert time.monotonic() - t < act.PLAZO_S + 1
    assert act.leer_pendiente() is None
    assert "no se ha podido comprobar" in _registro(local)


def test_github_caido_no_hay_aviso(mundo, monkeypatch, tmp_path):
    local, firma, act, _, _ = mundo
    _instalada(local, "0.3.8")
    with GitHubFalso() as github:
        github.publicar("0.3.9", _paquete(firma, tmp_path / "p.archmuse", "0.3.9").read_bytes(), False)
        github.estado = 503
        monkeypatch.setenv("ARCHMUSE_URL_ACTUALIZACIONES", github.api)
        assert act.comprobar() is None
    assert act.leer_pendiente() is None
    assert "503" in _registro(local)


def test_github_lento_no_espera_mas_que_el_plazo(mundo, monkeypatch, tmp_path):
    local, firma, act, _, _ = mundo
    _instalada(local, "0.3.8")
    with GitHubFalso() as github:
        github.publicar("0.3.9", _paquete(firma, tmp_path / "p.archmuse", "0.3.9").read_bytes(), False)
        github.retraso = 3.0
        monkeypatch.setenv("ARCHMUSE_URL_ACTUALIZACIONES", github.api)
        t = time.monotonic()
        assert act.comprobar(plazo=0.5) is None
        assert time.monotonic() - t < 2.0
    assert act.leer_pendiente() is None


# ── 4. De punta a punta ─────────────────────────────────────────────────────

def test_de_punta_a_punta_comprobar_instalar_y_volver_atras(mundo, monkeypatch, tmp_path):
    local, firma, act, actualizador, _ = mundo
    _instalada(local, "0.3.8")
    act.fijar_canal("prueba")
    with GitHubFalso() as github:
        github.publicar("0.3.9", _paquete(firma, tmp_path / "p.archmuse", "0.3.9").read_bytes(), True)
        monkeypatch.setenv("ARCHMUSE_URL_ACTUALIZACIONES", github.api)
        assert actualizador.main(["--comprobar", "--silencioso"]) == 0
    assert act.leer_pendiente()["version"] == "0.3.9"

    assert actualizador.main(["--instalar-pendiente", "--sin-arrancar", "--silencioso"]) == 0
    assert local.version_activa() == "0.3.9"
    assert act.leer_pendiente() is None
    bundle = Path(os.environ["ARCHMUSE_BUNDLE"]) / "Contents" / "archmuse.lsp"
    assert bundle.read_text(encoding="utf-8") == ";; lsp de la 0.3.9\n"

    assert actualizador.volver(arrancar=False) == ("0.3.8", "0.3.9")
    assert local.version_activa() == "0.3.8"


def test_instalar_pendiente_sin_nada_descargado_lo_dice(mundo):
    local, _, _, actualizador, _ = mundo
    _instalada(local, "0.3.8")
    assert actualizador.main(["--instalar-pendiente", "--sin-arrancar", "--silencioso"]) == 1
    assert "No hay ninguna actualización" in _registro(local)


def test_si_el_fichero_cambia_entre_la_descarga_y_el_clic_no_se_instala(mundo, monkeypatch, tmp_path):
    local, firma, act, actualizador, _ = mundo
    _instalada(local, "0.3.8")
    with GitHubFalso() as github:
        github.publicar("0.3.9", _paquete(firma, tmp_path / "p.archmuse", "0.3.9").read_bytes(), False)
        monkeypatch.setenv("ARCHMUSE_URL_ACTUALIZACIONES", github.api)
        pendiente = act.comprobar()
    with zipfile.ZipFile(pendiente["fichero"], "a") as z:
        z.writestr("colado.py", "print('hola')\n")
    assert actualizador.main(["--instalar-pendiente", "--sin-arrancar", "--silencioso"]) == 1
    assert local.version_activa() == "0.3.8"


# ── 5. Al arrancar el servidor ──────────────────────────────────────────────

def test_el_lanzador_comprueba_en_un_hilo_antes_de_servir_y_sin_poder_impedirlo():
    fuente = (CAPA_B / "lanzador.pyw").read_text(encoding="utf-8")
    llamada = fuente.index("actualizaciones.comprobar_al_arrancar()")
    assert llamada < fuente.index("serve(aplicacion.app")
    bloque = fuente[fuente.rindex("try:", 0, llamada):fuente.index("from waitress", llamada)]
    assert "except Exception" in bloque, "un fallo al comprobar podría impedir servir"


def test_la_comprobacion_al_arrancar_va_en_un_hilo_que_no_retiene_el_proceso(mundo, monkeypatch):
    _, _, act, _, _ = mundo
    monkeypatch.delenv("ARCHMUSE_SIN_ACTUALIZACIONES")
    llamado = threading.Event()
    monkeypatch.setattr(act, "comprobar", lambda: llamado.set())
    hilo = act.comprobar_al_arrancar()
    assert hilo is not None and hilo.daemon
    hilo.join(5)
    assert llamado.is_set()


def test_la_comprobacion_se_puede_desactivar(mundo):
    _, _, act, _, _ = mundo
    assert act.comprobar_al_arrancar() is None


# ── 5b. Una versión publicada con el servidor ya en marcha (2026-09-15) ─────
#
# **Medido en la instalación de Pablo:** el servidor 0.3.9 arrancó a las 18:49,
# comprobó («la 0.3.9 es la más reciente del canal "prueba"») y no volvió a mirar.
# La 0.3.12 se publicó horas después; AutoCAD se abrió y cerró sin reiniciar el
# servidor, así que nadie la vio. Lanzada a mano la misma comprobación, la
# encontró, la descargó y verificó su firma.

def test_una_version_publicada_con_el_servidor_en_marcha_se_encuentra_sin_reiniciarlo(
        mundo, monkeypatch, tmp_path):
    local, firma, act, _, _ = mundo
    _instalada(local, "0.3.8")
    monkeypatch.delenv("ARCHMUSE_SIN_ACTUALIZACIONES")
    monkeypatch.setattr(act, "INTERVALO_S", 0.2)
    parar = threading.Event()
    with GitHubFalso() as github:
        monkeypatch.setenv("ARCHMUSE_URL_ACTUALIZACIONES", github.api)
        hilo = act.comprobar_al_arrancar(parar=parar)
        try:
            limite = time.monotonic() + 10
            while "más reciente" not in _registro(local) and time.monotonic() < limite:
                time.sleep(0.05)
            assert act.leer_pendiente() is None
            github.publicar("0.3.9", _paquete(firma, tmp_path / "p.archmuse", "0.3.9").read_bytes(),
                            False)
            limite = time.monotonic() + 10
            while act.leer_pendiente() is None and time.monotonic() < limite:
                time.sleep(0.05)
            assert (act.leer_pendiente() or {}).get("version") == "0.3.9", _registro(local)
        finally:
            parar.set()
            hilo.join(5)
    assert not hilo.is_alive(), "la comprobación periódica no se puede parar"


def _comprobacion(act) -> dict:
    return json.loads(Path(act.fichero_comprobacion()).read_text(encoding="utf-8"))


def test_cada_comprobacion_deja_escrito_su_resultado_para_autocad(mundo, monkeypatch, tmp_path):
    local, firma, act, _, _ = mundo
    _instalada(local, "0.3.8")
    with GitHubFalso() as github:
        monkeypatch.setenv("ARCHMUSE_URL_ACTUALIZACIONES", github.api)
        act.comprobar()
        assert {k: _comprobacion(act)[k] for k in ("resultado", "instalada", "canal")} == \
            {"resultado": "al_dia", "instalada": "0.3.8", "canal": "estable"}
        github.publicar("0.3.9", _paquete(firma, tmp_path / "p.archmuse", "0.3.9").read_bytes(), False)
        act.comprobar()
        assert (_comprobacion(act)["resultado"], _comprobacion(act)["version"]) == ("actualizacion", "0.3.9")
        github.estado = 500
        act.comprobar()
        assert _comprobacion(act)["resultado"] == "error"


def test_la_misma_version_pendiente_no_se_vuelve_a_descargar(mundo, monkeypatch, tmp_path):
    """Con una comprobación cada hora, volver a bajar el paquete cada vez sería
    un mega por hora para nada; y si GitHub falla en la descarga, se perdería
    una actualización ya verificada."""
    local, firma, act, _, _ = mundo
    _instalada(local, "0.3.8")
    with GitHubFalso() as github:
        monkeypatch.setenv("ARCHMUSE_URL_ACTUALIZACIONES", github.api)
        github.publicar("0.3.9", _paquete(firma, tmp_path / "p.archmuse", "0.3.9").read_bytes(), False)
        primera = act.comprobar()
        github.ficheros.clear()
        segunda = act.comprobar()
    assert primera and segunda and segunda["fichero"] == primera["fichero"]
    assert act.leer_pendiente()["version"] == "0.3.9"


# ── 6. Publicar y construir ─────────────────────────────────────────────────

@pytest.fixture
def publicar(mundo, monkeypatch):
    _, firma, _, _, _ = mundo
    modulo = _cargar("publicar_de_tests", EMPAQUETADO / "publicar.py")
    monkeypatch.setattr(modulo, "_firma", lambda: firma)
    return modulo, firma


def test_publicar_es_una_sola_orden_de_prerelease_con_el_paquete_firmado(publicar, tmp_path):
    modulo, firma = publicar
    _paquete(firma, tmp_path / "ArchMuse-0.3.9.archmuse", "0.3.9")
    orden = modulo.orden_publicar("0.3.9", salida=tmp_path, commit="abc123")
    assert orden[:4] == ["gh", "release", "create", "v0.3.9"]
    assert str(tmp_path / "ArchMuse-0.3.9.archmuse") in orden
    assert "--prerelease" in orden
    assert orden[orden.index("--target") + 1] == "abc123"
    assert orden[orden.index("--repo") + 1] == "pablocamachomacia/archmuse"


def test_publicar_se_niega_con_un_paquete_sin_firma_de_archmuse(publicar, tmp_path):
    modulo, firma = publicar
    _paquete(firma, tmp_path / "ArchMuse-0.3.9.archmuse", "0.3.9", semilla=OTRA_SEMILLA)
    with pytest.raises(SystemExit, match="No se publica"):
        modulo.orden_publicar("0.3.9", salida=tmp_path, commit="abc123")


def test_pasar_de_prueba_a_estable_es_una_sola_orden(publicar):
    modulo, _ = publicar
    assert modulo.orden_promover("0.3.9") == [
        "gh", "release", "edit", "v0.3.9", "--repo", "pablocamachomacia/archmuse",
        "--prerelease=false", "--latest"]


def test_mostrar_ensena_la_orden_y_no_ejecuta_nada(publicar, monkeypatch, capsys):
    modulo, _ = publicar

    def prohibido(*args, **kwargs):
        raise AssertionError("--mostrar ha ejecutado algo")

    monkeypatch.setattr(modulo.subprocess, "run", prohibido)
    assert modulo.main(["--promover", "0.3.9", "--mostrar"]) == 0
    assert "gh release edit v0.3.9" in capsys.readouterr().out


def test_la_siguiente_version_es_la_siguiente_a_la_mayor_usada():
    construir = _cargar("construir_de_tests", EMPAQUETADO / "construir.py")
    assert construir.siguiente_version(["0.3.1", "0.3.8", "0.3.4"], "0.3.5") == "0.3.9"
    assert construir.siguiente_version(["0.3.9"], "0.3.10") == "0.3.11"
    usadas = construir.versiones_usadas()
    assert "0.3.8" in usadas and "0.3.4" in usadas and "0.3.6" in usadas


def test_fijar_la_version_la_escribe_en_los_tres_sitios(tmp_path):
    construir = _cargar("construir_de_tests", EMPAQUETADO / "construir.py")
    (tmp_path / "analyzer").mkdir()
    (tmp_path / "empaquetado" / "bundle").mkdir(parents=True)
    (tmp_path / "analyzer" / "version.py").write_text(
        (RAIZ / "analyzer" / "version.py").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "empaquetado" / "bundle" / "PackageContents.xml").write_text(
        (EMPAQUETADO / "bundle" / "PackageContents.xml").read_text(encoding="utf-8"), encoding="utf-8")
    usadas = tmp_path / "usadas.txt"
    usadas.write_text("0.3.8\n", encoding="utf-8")

    construir.fijar_version("0.3.9", raiz=tmp_path, usadas=usadas)

    assert 'VERSION_DEL_REPOSITORIO = "0.3.9"' in (tmp_path / "analyzer" / "version.py").read_text(encoding="utf-8")
    assert 'AppVersion="0.3.9"' in (tmp_path / "empaquetado" / "bundle" / "PackageContents.xml").read_text(encoding="utf-8")
    assert construir.versiones_usadas(usadas) == ["0.3.8", "0.3.9"]


def test_construir_se_niega_con_una_clave_dentro_del_repositorio_o_que_no_es_la_de_archmuse(
        tmp_path, monkeypatch):
    construir = _cargar("construir_de_tests", EMPAQUETADO / "construir.py")
    dentro = tmp_path / "repo" / "k.semilla"
    dentro.parent.mkdir()
    dentro.write_text(OTRA_SEMILLA.hex())
    monkeypatch.setattr(construir, "RAIZ", tmp_path / "repo")
    with pytest.raises(SystemExit, match="DENTRO del repositorio"):
        construir.leer_clave(dentro)
    fuera = tmp_path / "fuera.semilla"
    fuera.write_text(OTRA_SEMILLA.hex())
    with pytest.raises(SystemExit, match="no es la de ArchMuse"):
        construir.leer_clave(fuera)


def test_la_capa_b_lleva_la_firma_y_las_actualizaciones():
    construir = _cargar("construir_de_tests", EMPAQUETADO / "construir.py")
    assert {"firma.py", "actualizaciones.py"} <= set(construir.FICHEROS_PROPIOS)


# ── 7. La clave privada no entra nunca ──────────────────────────────────────

def test_la_clave_publica_de_archmuse_esta_puesta():
    fuente = (CAPA_B / "firma.py").read_text(encoding="utf-8")
    m = re.search(r'^CLAVE_PUBLICA_HEX = "([0-9a-f]{64})"$', fuente, re.M)
    assert m, "firma.py no lleva una clave pública de 32 bytes"


def test_ninguna_clave_privada_esta_versionada_y_gitignore_la_cubre():
    versionados = subprocess.run(["git", "-C", str(RAIZ), "ls-files"], capture_output=True,
                                 text=True, check=True).stdout.splitlines()
    assert not [f for f in versionados if f.lower().endswith((".semilla", ".pem", ".key"))]
    for ruta in ("empaquetado/archmuse-ed25519.semilla", ".archmuse/firma/cualquier.txt"):
        r = subprocess.run(["git", "-C", str(RAIZ), "check-ignore", "-q", ruta])
        assert r.returncode == 0, "%s no está en .gitignore" % ruta
    construir = _cargar("construir_de_tests", EMPAQUETADO / "construir.py")
    assert RAIZ.resolve() not in construir.CLAVE_POR_DEFECTO.resolve().parents


# ── 8. El .lsp ──────────────────────────────────────────────────────────────

def _defun(nombre: str) -> str:
    ini = LSP.index("(defun %s " % nombre)
    return LSP[ini:LSP.index("\n(defun", ini + 10)]


# ── ARCHMUSE-ACTUALIZAR busca en ese momento (2026-09-16) ───────────────────────
#
# **Medido en la instalación de Pablo:** servidor 0.3.16, última búsqueda a las 20:57;
# la 0.3.17 se publicó a las 21:19. ARCHMUSE-ACTUALIZAR sólo leía
# `actualizacion.json` —lo que dejó una búsqueda anterior— y decía «No hay ninguna
# actualización de ArchMuse descargada»; un ARCHMUSE cancelado con Esc antes de hablar
# con el servidor tampoco lanzaba búsqueda. Ahora el comando busca y descarga en ese
# momento y dice lo que ha encontrado. Teclearlo ya es decir que sí: sin ventana.

def test_archmuse_actualizar_busca_en_ese_momento_y_espera():
    ofrecer = _defun("am:ofrecer-actualizacion")
    buscar = ofrecer.index('\\" actualizador --comprobar')
    assert "(am:ejecutar-y-esperar" in ofrecer[:buscar + 200], "no espera a que termine la búsqueda"
    # Lee lo que ha dejado ESA búsqueda, no una anterior.
    assert ofrecer.index("vl-file-delete") < buscar
    assert buscar < ofrecer.index("comprobacion.json") and buscar < ofrecer.index("am:actualizacion-pendiente-en")
    assert "(vl-file-size resultado-busqueda)" in ofrecer, "no comprueba que la búsqueda ha terminado"
    esperar = _defun("am:ejecutar-y-esperar")
    assert "'Run" in esperar and ":vlax-true" in esperar
    assert "(defun c:ARCHMUSE-ACTUALIZAR ()" in LSP


def test_archmuse_actualizar_dice_lo_que_ha_encontrado():
    ofrecer = _defun("am:ofrecer-actualizacion")
    assert '"\\nEstás al día ("' in ofrecer
    instalar = ofrecer.index('"\\nInstalando "')
    assert instalar < ofrecer.index("actualizador --instalar-pendiente")
    assert "No hay ninguna actualización de ArchMuse descargada" not in LSP
    assert "'Popup" not in ofrecer, "teclear ARCHMUSE-ACTUALIZAR ya es decir que sí"
    # Si no ha podido buscar, lo dice: ni «al día» ni «instalando» sin haberlo sabido.
    assert "No he podido comprobar si hay una versión nueva" in ofrecer


def test_comprobar_desde_el_comando_deja_el_resultado_y_la_comprobacion(mundo, monkeypatch, tmp_path):
    """Lo que lee ARCHMUSE-ACTUALIZAR: el fichero de resultado (que la búsqueda ha
    terminado) y `comprobacion.json` (qué ha encontrado)."""
    local, firma, act, actualizador, _ = mundo
    _instalada(local, "0.3.16")
    act.fijar_canal("prueba")
    resultado = tmp_path / "resultado.txt"
    with GitHubFalso() as github:
        monkeypatch.setenv("ARCHMUSE_URL_ACTUALIZACIONES", github.api)
        assert actualizador.main(["--comprobar", "--silencioso", "--resultado", str(resultado)]) == 0
        assert resultado.read_text(encoding="utf-8-sig").startswith("OK")
        assert _comprobacion(act)["resultado"] == "al_dia" and _comprobacion(act)["instalada"] == "0.3.16"
        github.publicar("0.3.17", _paquete(firma, tmp_path / "p.archmuse", "0.3.17").read_bytes(), True)
        resultado.unlink()
        assert actualizador.main(["--comprobar", "--silencioso", "--resultado", str(resultado)]) == 0
    assert resultado.exists()
    assert _comprobacion(act)["resultado"] == "actualizacion"
    assert act.leer_pendiente()["version"] == "0.3.17"


def test_el_lsp_no_sale_a_la_red_para_saber_si_hay_version_nueva():
    pendiente = _defun("am:actualizacion-pendiente-en")
    assert "actualizacion.json" in pendiente
    for funcion in (pendiente, _defun("am:ofrecer-actualizacion"),
                    _defun("am:actualizaciones-al-cargar")):
        for red in ("WinHttp", "http", "github", "am:peticion"):
            assert red not in funcion, red


# ── El aviso al cargar (corrección de Pablo, 2026-09-15) ─────────────────────
#
# «No quiero una línea en cada arranque. El aviso sale como mucho una vez al día.
# Si no hay versión nueva, no muestra nada en pantalla; solo lo deja escrito en
# el log.» Y ya no depende de `S::STARTUP`: que llegue a ejecutarse con el
# paquete cargado por el autoloader nunca se midió, y sin versión nueva no dejaba
# ni rastro. Se revisa al cargar, que es lo que imprime «ArchMuse cargado».

def test_al_cargar_se_revisa_una_vez_y_sin_poder_romper_la_carga():
    llamada = LSP.index('(am:actualizaciones-al-cargar (strcat (getenv "LOCALAPPDATA")')
    assert "(vl-catch-all-apply" in LSP[llamada - 60:llamada], "un fallo aquí rompería la carga"
    assert llamada < LSP.index('(princ "\\nArchMuse cargado.')
    assert "S::STARTUP" not in _sin_comentarios_lsp(LSP), (
        "el aviso ya no cuelga de S::STARTUP: nunca se midió que se ejecute")


def test_sin_version_nueva_no_se_ensena_nada_y_queda_en_el_registro():
    cuerpo = _defun("am:actualizaciones-al-cargar")
    princs = re.findall(r'\(princ \(strcat "([^"]*)', cuerpo)
    assert princs == ["\\nHay una actualización de ArchMuse ("], (
        "al cargar sólo se enseña el aviso de versión nueva: %s" % princs)
    assert '"al dia ("' in cuerpo and "(am:log" in cuerpo
    assert "comprobacion.json" in cuerpo


def test_el_aviso_sale_como_mucho_una_vez_al_dia():
    cuerpo = _defun("am:actualizaciones-al-cargar")
    assert "aviso-de-actualizaciones.txt" in cuerpo
    assert "(am:hoy)" in cuerpo
    # Se compara con lo que se avisó la última vez y, si ya se dijo hoy, no se repite.
    assert "(/= ultimo clave)" in cuerpo
    assert "(am:escribe-fichero fichero clave)" in cuerpo


def _sin_comentarios_lsp(texto: str) -> str:
    return "\n".join(l.split(";")[0] for l in texto.splitlines())


# ── Reiniciar AutoCAD no comprobaba (2026-09-16) ─────────────────────────────
#
# **Medido en la instalación de Pablo:** el servidor 0.3.12 arrancó a las 22:03,
# comprobó una vez y siguió vivo; la 0.3.13 se publicó a las 23:50 y Pablo
# reinició AutoCAD pasadas las 00:11. El servidor no se reinicia con AutoCAD, así
# que nadie volvió a mirar. La 0.3.12 no tenía la comprobación cada hora, pero con
# ella el hueco sigue: hasta una hora sin ver una versión publicada, reinicie lo
# que reinicie. Ahora el uso del comando cuenta: una petición al servidor lanza
# una comprobación si hace más de `MINIMO_ENTRE_COMPROBACIONES_S` que no se mira,
# en un hilo, y el comando enseña el aviso del día al terminar.

def test_una_peticion_del_comando_comprueba_si_hace_rato_que_no_se_mira(mundo, monkeypatch):
    _, _, act, _, _ = mundo
    monkeypatch.delenv("ARCHMUSE_SIN_ACTUALIZACIONES")
    veces = []
    hecho = threading.Event()
    monkeypatch.setattr(act, "comprobar", lambda: (veces.append(1), hecho.set()))
    hilo = act.comprobar_si_hace_tiempo()
    assert hilo is not None and hilo.daemon
    hilo.join(5)
    assert hecho.is_set() and len(veces) == 1
    assert act.comprobar_si_hace_tiempo() is None, "recién comprobado: no se vuelve a mirar"
    monkeypatch.setattr(act, "MINIMO_ENTRE_COMPROBACIONES_S", 0.0)
    otro = act.comprobar_si_hace_tiempo()
    assert otro is not None
    otro.join(5)
    assert len(veces) == 2


def test_la_comprobacion_periodica_cuenta_como_mirada_reciente(mundo, monkeypatch):
    """Si el hilo de cada hora acaba de mirar, una petición no repite la consulta."""
    _, _, act, _, _ = mundo
    monkeypatch.delenv("ARCHMUSE_SIN_ACTUALIZACIONES")
    monkeypatch.setattr(act, "comprobar", lambda: None)
    parar = threading.Event()
    hilo = act.comprobar_al_arrancar(parar=parar)
    try:
        limite = time.monotonic() + 5
        while act.comprobar_si_hace_tiempo() is not None and time.monotonic() < limite:
            time.sleep(0.05)
        assert act.comprobar_si_hace_tiempo() is None
    finally:
        parar.set()
        hilo.join(5)


def test_la_peticion_no_espera_a_github(mundo, monkeypatch):
    _, _, act, _, _ = mundo
    monkeypatch.delenv("ARCHMUSE_SIN_ACTUALIZACIONES")
    monkeypatch.setattr(act, "comprobar", lambda: time.sleep(2))
    inicio = time.monotonic()
    act.al_recibir_peticion()
    assert time.monotonic() - inicio < 0.5


def test_la_peticion_nunca_falla_por_las_actualizaciones(mundo, monkeypatch):
    local, _, act, _, _ = mundo
    monkeypatch.delenv("ARCHMUSE_SIN_ACTUALIZACIONES")

    def revienta():
        raise RuntimeError("roto a propósito")
    monkeypatch.setattr(act, "comprobar_si_hace_tiempo", revienta)
    assert act.al_recibir_peticion() is None
    assert "roto a propósito" in _registro(local)


def test_con_las_actualizaciones_desactivadas_una_peticion_no_comprueba(mundo, monkeypatch):
    _, _, act, _, _ = mundo
    monkeypatch.setattr(act, "comprobar", lambda: pytest.fail("no debía comprobar"))
    assert act.comprobar_si_hace_tiempo() is None


def test_el_lanzador_engancha_la_comprobacion_a_las_peticiones_sin_poder_impedir_servir():
    fuente = (CAPA_B / "lanzador.pyw").read_text(encoding="utf-8")
    enganche = fuente.index("before_request(actualizaciones.al_recibir_peticion)")
    assert enganche < fuente.index("serve(aplicacion.app")
    bloque = fuente[fuente.rindex("try:", 0, enganche):fuente.index("from waitress", enganche)]
    assert "except Exception" in bloque


def test_el_comando_ensena_el_aviso_del_dia_al_terminar():
    """La comprobación que lanza su primera petición ya ha acabado cuando el
    comando termina: si hay versión nueva, se dice ahí, sin esperar a reiniciar
    AutoCAD. Sigue siendo como mucho un aviso al día (`am:actualizaciones-al-cargar`)."""
    comando = LSP[LSP.index("(defun c:ARCHMUSE ("):LSP.index("(defun c:ARCHMUSE-ACTUALIZAR")]
    final = comando[comando.rindex("(setvar \"CMDECHO\" eco)"):]
    assert "am:actualizaciones-al-cargar" in final
    assert "vl-catch-all-apply" in final, "un fallo aquí no puede estropear un comando que ha ido bien"
