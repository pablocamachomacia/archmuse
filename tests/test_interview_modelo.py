# -*- coding: utf-8 -*-
"""Fase A del entrevistador — modelo de estado y persistencia.

Ejecutar:  python tests/test_interview_modelo.py

Mismo estilo que `tests/test_storage.py` / `tests/test_e2_persistencia.py`:
script sin dependencias, `check()` acumula fallos, sale con código 1 si algo
falla. Cubre exactamente el criterio de aceptación de A8 del plan
(`docs/design/2026-08-12-plan-implementacion-entrevistador.md`): los 4 tipos
de dato (`naturaleza` de `RespuestaInterpretada`: Hecho/Inferencia/
Hipótesis/Preferencia) y las 2 tablas/columnas nuevas (`entrevistas`,
`proyectos.traza_generacion`).

Siete bloques:

1. Serialización — round-trip de cada dataclass, incluidos los 4 valores de
   `naturaleza` y las 5 categorías de `DirectivaCualitativa`.
2. `especificacion_id` estable entre serializaciones sucesivas (A2).
3. Catálogos cerrados — construir con un valor fuera de catálogo lanza
   `ValueError` explícito (A3: `DirectivaCualitativa.categoria`, y el resto
   de enumeraciones cerradas del módulo).
4. Persistencia de `EstadoEntrevista` / `EspecificacionArquitectonica`
   (tabla `entrevistas`) — guardar, "reiniciar proceso", recuperar.
5. Persistencia de `TrazaDeGeneracion` (columna `proyectos.traza_generacion`).
6. Compatibilidad hacia atrás — fila de antes de la Fase A, migración
   idempotente, nada de lo existente se rompe.
7. Resiliencia — ids hostiles y filas corruptas nunca lanzan una excepción.
"""
import json
import os
import sqlite3
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

TMP = tempfile.mkdtemp(prefix="archmuse_test_interview_")
os.environ["ARCHMUSE_DATA_DIR"] = TMP

from analyzer import storage  # noqa: E402
from analyzer.interview import modelo as m  # noqa: E402

fallos = []
comprobaciones = 0


def check(nombre, cond, detalle=""):
    global comprobaciones
    comprobaciones += 1
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


def _payload_minimo(nombre="proyecto-generado.dxf"):
    return {"archivo": nombre, "puntuacion_global": 70, "valoracion_global": "Correcto",
            "viviendas": [{"nombre": "VT1/1", "svg": "<svg></svg>"}],
            "proyecto": {"ciudad": "Sevilla", "tipologia": "plurifamiliar"}}


print("=" * 70)
print("1. SERIALIZACION — round-trip de cada dataclass")
print("=" * 70)
storage.init_db()

turno = m.Turno(
    turno_id=m.nuevo_id(),
    preguntas_ids=["p1", "p4", "p5"],
    respuesta_cruda={"p1": "Quiero una vivienda en Sevilla", "p4": "no sé", "p5": "moderno"},
)
turno_2 = m.Turno.desde_dict(turno.a_dict())
check("Turno round-trip", turno.a_dict() == turno_2.a_dict())

for naturaleza in m.NATURALEZAS_RESPUESTA:
    confianza = "Baja" if naturaleza in ("Inferencia", "Hipótesis") else None
    r = m.RespuestaInterpretada(
        respuesta_id=m.nuevo_id(), turno_id=turno.turno_id,
        especificacion_id="solar.superficie_m2", respuesta_cruda="800 m2",
        naturaleza=naturaleza, valor=800, confianza=confianza,
        motivo="ejemplo" if confianza else None,
    )
    r2 = m.RespuestaInterpretada.desde_dict(r.a_dict())
    check("RespuestaInterpretada round-trip (naturaleza=%s)" % naturaleza, r.a_dict() == r2.a_dict())

contradiccion = m.Contradiccion(
    contradiccion_id=m.nuevo_id(), especificacion_id="solar.superficie_m2",
    valores_en_conflicto=[
        m.ValorEnConflicto(turno_id="t1", valor=800),
        m.ValorEnConflicto(turno_id="t3", valor=650),
    ],
)
contradiccion_2 = m.Contradiccion.desde_dict(contradiccion.a_dict())
check("Contradiccion round-trip", contradiccion.a_dict() == contradiccion_2.a_dict())

campo = m.CampoEspecificacion(
    especificacion_id="solar.superficie_m2", categoria="parcela", etiqueta="Superficie del solar",
    tipo_dato="información_usuario", valor=800, origen=[turno.turno_id],
    destino_generador="usado_directo",
)
campo_2 = m.CampoEspecificacion.desde_dict(campo.a_dict())
check("CampoEspecificacion round-trip", campo.a_dict() == campo_2.a_dict())

for categoria in m.CATEGORIAS_DIRECTIVA:
    directiva = m.DirectivaCualitativa(
        especificacion_id="accesibilidad.requerida", categoria=categoria, fuerza="dura",
        texto_origen="necesito acceso para silla de ruedas",
        texto_prompt="DEBES: garantizar accesibilidad para silla de ruedas",
        verificable_geometricamente=(categoria == "accesibilidad"),
    )
    directiva_2 = m.DirectivaCualitativa.desde_dict(directiva.a_dict())
    check("DirectivaCualitativa round-trip (categoria=%s)" % categoria, directiva.a_dict() == directiva_2.a_dict())

contexto = m.ContextoCualitativo(directivas=[directiva], texto_prompt="DEBES CUMPLIR:\n- ...")
contexto_2 = m.ContextoCualitativo.desde_dict(contexto.a_dict())
check("ContextoCualitativo round-trip", contexto.a_dict() == contexto_2.a_dict())

especificacion = m.EspecificacionArquitectonica(
    especificacion_id=m.nuevo_id(), sesion_entrevista_id="sesion-1", campos=[campo],
    contexto_cualitativo=contexto, decisiones_pendientes=["presupuesto.cifra"],
)
especificacion_2 = m.EspecificacionArquitectonica.desde_dict(especificacion.a_dict())
check("EspecificacionArquitectonica round-trip", especificacion.a_dict() == especificacion_2.a_dict())

estado = m.EstadoEntrevista(
    sesion_id=m.nuevo_id(), historial_turnos=[turno],
    respuestas_interpretadas=[r], contradicciones=[contradiccion],
    no_negociables=["dormitorios lejos de la puerta principal"],
    llamadas_ia_consumidas=1, turnos_totales=1,
)
estado_2 = m.EstadoEntrevista.desde_dict(estado.a_dict())
check("EstadoEntrevista round-trip", estado.a_dict() == estado_2.a_dict())

verificacion = m.VerificacionDeterminista(
    especificacion_id="accesibilidad.requerida", metodo="evaluate_bathroom_accessibility",
    resultado="cumple",
)
verificacion_2 = m.VerificacionDeterminista.desde_dict(verificacion.a_dict())
check("VerificacionDeterminista round-trip", verificacion.a_dict() == verificacion_2.a_dict())

respuesta_ia = m.RespuestaIAResumen(justificacion="...", referencias_especificacion=["accesibilidad.requerida"])
respuesta_ia_2 = m.RespuestaIAResumen.desde_dict(respuesta_ia.a_dict())
check("RespuestaIAResumen round-trip", respuesta_ia.a_dict() == respuesta_ia_2.a_dict())

traza = m.TrazaDeGeneracion(
    traza_id=m.nuevo_id(), especificacion_id=especificacion.especificacion_id,
    proyecto_id=None, directivas_enviadas=[directiva], respuesta_ia=respuesta_ia,
    verificaciones_deterministas=[verificacion],
)
traza_2 = m.TrazaDeGeneracion.desde_dict(traza.a_dict())
check("TrazaDeGeneracion round-trip", traza.a_dict() == traza_2.a_dict())

print()
print("=" * 70)
print("2. especificacion_id ESTABLE entre serializaciones sucesivas")
print("=" * 70)

texto_1 = m.volcar_especificacion(especificacion)
recargada = m.cargar_especificacion(texto_1)
texto_2 = m.volcar_especificacion(recargada)
check("volcar->cargar->volcar produce el mismo texto", texto_1 == texto_2)
check("especificacion_id no cambia al recargar", recargada.especificacion_id == especificacion.especificacion_id)
check("especificacion_id de cada campo no cambia al recargar",
      [c.especificacion_id for c in recargada.campos] == [c.especificacion_id for c in especificacion.campos])

print()
print("=" * 70)
print("3. CATALOGOS CERRADOS — un valor fuera de catalogo lanza ValueError")
print("=" * 70)


def _rechaza(nombre, constructor):
    try:
        constructor()
        check(nombre, False, "no lanzó ValueError")
    except ValueError:
        check(nombre, True)
    except Exception as exc:  # noqa: BLE001 - queremos ver exactamente qué lanzó si no es ValueError
        check(nombre, False, "lanzó %s en vez de ValueError: %s" % (type(exc).__name__, exc))


_rechaza(
    "DirectivaCualitativa.categoria fuera de catálogo [Decisión Pablo #3]",
    lambda: m.DirectivaCualitativa(
        especificacion_id="x", categoria="categoria_inventada", fuerza="dura",
        texto_origen="x", texto_prompt="x",
    ),
)
_rechaza(
    "DirectivaCualitativa.fuerza fuera de catálogo",
    lambda: m.DirectivaCualitativa(
        especificacion_id="x", categoria="accesibilidad", fuerza="media",
        texto_origen="x", texto_prompt="x",
    ),
)
_rechaza(
    "CampoEspecificacion.categoria fuera de catálogo (15 categorías)",
    lambda: m.CampoEspecificacion(
        especificacion_id="x", categoria="categoria_inventada", etiqueta="x",
        tipo_dato="información_usuario",
    ),
)
_rechaza(
    "CampoEspecificacion.tipo_dato fuera de catálogo",
    lambda: m.CampoEspecificacion(
        especificacion_id="x", categoria="parcela", etiqueta="x", tipo_dato="opinion",
    ),
)
_rechaza(
    "CampoEspecificacion.destino_generador fuera de catálogo",
    lambda: m.CampoEspecificacion(
        especificacion_id="x", categoria="parcela", etiqueta="x",
        tipo_dato="información_usuario", destino_generador="usado_a_veces",
    ),
)
_rechaza(
    "CampoEspecificacion.decision_contrato fuera de catálogo",
    lambda: m.CampoEspecificacion(
        especificacion_id="x", categoria="parcela", etiqueta="x",
        tipo_dato="información_usuario", decision_contrato="D",
    ),
)
_rechaza(
    "RespuestaInterpretada.naturaleza fuera de catálogo",
    lambda: m.RespuestaInterpretada(
        respuesta_id="x", turno_id="x", especificacion_id="x", respuesta_cruda="x",
        naturaleza="Recomendación",
    ),
)
_rechaza(
    "RespuestaInterpretada.confianza fuera de catálogo",
    lambda: m.RespuestaInterpretada(
        respuesta_id="x", turno_id="x", especificacion_id="x", respuesta_cruda="x",
        naturaleza="Inferencia", confianza="Altísima",
    ),
)
_rechaza(
    "EstadoEntrevista.estado (ciclo de vida) fuera de catálogo",
    lambda: m.EstadoEntrevista(sesion_id="x", estado="pausada"),
)
_rechaza(
    "EstadoEntrevista.modo fuera de catálogo",
    lambda: m.EstadoEntrevista(sesion_id="x", modo="hibrido"),
)
_rechaza(
    "EstadoEntrevista.llamadas_ia_consumidas negativo",
    lambda: m.EstadoEntrevista(sesion_id="x", llamadas_ia_consumidas=-1),
)
_rechaza(
    "EspecificacionArquitectonica.modo_origen fuera de catálogo",
    lambda: m.EspecificacionArquitectonica(especificacion_id="x", modo_origen="automatico"),
)
_rechaza(
    "VerificacionDeterminista.resultado fuera de catálogo",
    lambda: m.VerificacionDeterminista(especificacion_id="x", metodo="x", resultado="parcial"),
)

# Los 5 valores válidos del catálogo de directivas SÍ deben aceptarse (no solo
# rechazar el inválido: comprobar también que el catálogo no está vacío por error).
for categoria_valida in m.CATEGORIAS_DIRECTIVA:
    try:
        m.DirectivaCualitativa(
            especificacion_id="x", categoria=categoria_valida, fuerza="blanda",
            texto_origen="x", texto_prompt="x",
        )
        check("categoria válida aceptada: %s" % categoria_valida, True)
    except ValueError as exc:
        check("categoria válida aceptada: %s" % categoria_valida, False, str(exc))

print()
print("=" * 70)
print("4. PERSISTENCIA — tabla `entrevistas`")
print("=" * 70)

sesion_id = m.nuevo_id()
estado_real = m.EstadoEntrevista(
    sesion_id=sesion_id, modo="entrevista_guiada", modo_entrada="entrevista_guiada",
    historial_turnos=[turno], respuestas_interpretadas=[r], no_negociables=["luz natural en cocina"],
    llamadas_ia_consumidas=1, turnos_totales=1,
)
meta = storage.guardar_entrevista(estado_real)
check("guardar_entrevista devuelve el mismo sesion_id", meta["sesion_id"] == sesion_id)

recuperado = storage.obtener_entrevista(sesion_id)
check("obtener_entrevista devuelve algo", recuperado is not None)
check("estado recuperado idéntico byte a byte",
      recuperado is not None and m.volcar_estado(recuperado["estado"]) == m.volcar_estado(estado_real))
check("especificacion es None (todavía no se ha guardado ninguna)",
      recuperado is not None and recuperado["especificacion"] is None)

# Segundo turno: actualiza la MISMA sesión (upsert), ahora con especificación.
estado_real.turnos_totales = 2
estado_real.llamadas_ia_consumidas = 2
meta_2 = storage.guardar_entrevista(estado_real, especificacion=especificacion)
check("segundo guardado conserva creado_en", meta_2["creado_en"] == meta["creado_en"])
check("segundo guardado actualiza modificado_en", meta_2["modificado_en"] >= meta["modificado_en"])

recuperado_2 = storage.obtener_entrevista(sesion_id)
check("turnos_totales actualizado tras el upsert",
      recuperado_2 is not None and recuperado_2["estado"].turnos_totales == 2)
check("especificacion ahora presente y correcta",
      recuperado_2 is not None and recuperado_2["especificacion"] is not None
      and recuperado_2["especificacion"].especificacion_id == especificacion.especificacion_id)

try:
    storage.guardar_entrevista(m.EstadoEntrevista(sesion_id="id-mal-formado"))
    check("guardar_entrevista con sesion_id inválido lanza ValueError", False)
except ValueError:
    check("guardar_entrevista con sesion_id inválido lanza ValueError", True)

print()
print("--- 'reinicio del proceso' (reimport del módulo) ---")
del sys.modules["analyzer.storage"]
from analyzer import storage as storage2  # noqa: E402

recuperado_3 = storage2.obtener_entrevista(sesion_id)
check("otra 'instancia' de storage recupera la misma entrevista",
      recuperado_3 is not None and recuperado_3["estado"].turnos_totales == 2)

print()
print("=" * 70)
print("5. PERSISTENCIA — columna `proyectos.traza_generacion`")
print("=" * 70)

meta_proyecto = storage2.guardar_proyecto(_payload_minimo(), origen="generado")
proyecto_id = meta_proyecto["id"]

check("proyecto recién creado no tiene traza todavía",
      storage2.obtener_traza_generacion(proyecto_id) is None)

traza_real = m.TrazaDeGeneracion(
    traza_id=m.nuevo_id(), especificacion_id=especificacion.especificacion_id,
    proyecto_id=proyecto_id, directivas_enviadas=[directiva], respuesta_ia=respuesta_ia,
    verificaciones_deterministas=[verificacion],
)
ok = storage2.guardar_traza_generacion(traza_real)
check("guardar_traza_generacion devuelve True (el proyecto existía)", ok is True)

traza_recuperada = storage2.obtener_traza_generacion(proyecto_id)
check("traza recuperada idéntica byte a byte",
      traza_recuperada is not None and m.volcar_traza(traza_recuperada) == m.volcar_traza(traza_real))

check("guardar_traza_generacion sobre proyecto inexistente devuelve False",
      storage2.guardar_traza_generacion(
          m.TrazaDeGeneracion(traza_id=m.nuevo_id(), especificacion_id="x", proyecto_id="0" * 12)
      ) is False)
meta_proyecto_sin_traza = storage2.guardar_proyecto(_payload_minimo("sin-traza.dxf"), origen="dxf")
check("proyecto distinto sin traza -> None, no la traza de otro proyecto",
      storage2.obtener_traza_generacion(meta_proyecto_sin_traza["id"]) is None)
check("el proyecto con traza no se ve afectado por el guardado del otro",
      storage2.obtener_traza_generacion(proyecto_id) is not None)

print()
print("=" * 70)
print("6. COMPATIBILIDAD HACIA ATRAS — fila de antes de la Fase A")
print("=" * 70)

TMP_VIEJO = tempfile.mkdtemp(prefix="archmuse_test_interview_viejo_")
os.environ["ARCHMUSE_DATA_DIR"] = TMP_VIEJO
con = sqlite3.connect(storage2.db_path())
con.execute(
    """
    CREATE TABLE proyectos (
        id TEXT PRIMARY KEY, nombre TEXT NOT NULL, origen TEXT NOT NULL,
        creado_en TEXT NOT NULL, modificado_en TEXT NOT NULL,
        puntuacion INTEGER, valoracion TEXT, num_viviendas INTEGER,
        ciudad TEXT, tipologia TEXT, miniatura TEXT, payload TEXT NOT NULL,
        modelo TEXT
    )
    """
)
payload_viejo = _payload_minimo("proyecto-antes-de-fase-a.dxf")
con.execute(
    "INSERT INTO proyectos (id, nombre, origen, creado_en, modificado_en, "
    "puntuacion, valoracion, num_viviendas, ciudad, tipologia, miniatura, payload, modelo) "
    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
    ("def456def456", "proyecto-antes-de-fase-a.dxf", "dxf", "2026-08-11T00:00:00+00:00",
     "2026-08-11T00:00:00+00:00", 70, "Correcto", 1, "Sevilla", "plurifamiliar", None,
     json.dumps(payload_viejo, ensure_ascii=False), None),
)
con.commit()
con.close()

columnas_antes = {f[1] for f in sqlite3.connect(storage2.db_path())
                  .execute("PRAGMA table_info(proyectos)").fetchall()}
tablas_antes = {f[0] for f in sqlite3.connect(storage2.db_path())
                .execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
check("la base vieja NO tiene columna traza_generacion (montaje del test)",
      "traza_generacion" not in columnas_antes)
check("la base vieja NO tiene tabla entrevistas (montaje del test)", "entrevistas" not in tablas_antes)

storage2.init_db()  # aquí migra

columnas_despues = {f[1] for f in sqlite3.connect(storage2.db_path())
                    .execute("PRAGMA table_info(proyectos)").fetchall()}
tablas_despues = {f[0] for f in sqlite3.connect(storage2.db_path())
                  .execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
check("init_db() añade la columna traza_generacion", "traza_generacion" in columnas_despues)
check("init_db() añade la tabla entrevistas", "entrevistas" in tablas_despues)
check("la fila vieja sigue ahí", len(storage2.listar_proyectos()) == 1)

recuperado_viejo = storage2.obtener_proyecto("def456def456")
check("obtener_proyecto de la fila vieja funciona igual que siempre",
      recuperado_viejo is not None and recuperado_viejo.get("proyecto_id") is None)
check("obtener_traza_generacion de la fila vieja -> None (columna NULL tras migrar)",
      storage2.obtener_traza_generacion("def456def456") is None)
check("init_db() otra vez es idempotente (no rompe la fila ni la tabla)",
      (storage2.init_db(), len(storage2.listar_proyectos()) == 1)[1])

# La fila vieja SÍ puede recibir una traza nueva a partir de ahora (E2 no la
# migra retroactivamente, pero tampoco impide que se genere una desde hoy).
traza_para_vieja = m.TrazaDeGeneracion(
    traza_id=m.nuevo_id(), especificacion_id="x", proyecto_id="def456def456",
)
check("una fila migrada SÍ puede recibir una traza nueva",
      storage2.guardar_traza_generacion(traza_para_vieja) is True)

os.environ["ARCHMUSE_DATA_DIR"] = TMP  # vuelve a la base principal de este test

print()
print("=" * 70)
print("7. RESILIENCIA — ids hostiles y filas corruptas")
print("=" * 70)

for malo in ["../../etc/passwd", "'; DROP TABLE entrevistas; --", "", None, "ABCDEF123456", sesion_id + "x"]:
    check("obtener_entrevista rechaza %r" % (malo,), storage.obtener_entrevista(malo) is None)
    check("obtener_traza_generacion rechaza %r" % (malo,), storage.obtener_traza_generacion(malo) is None)

check("la tabla entrevistas sigue viva tras los intentos hostiles",
      storage.obtener_entrevista(sesion_id) is not None)

con = sqlite3.connect(storage.db_path())
con.execute(
    "INSERT INTO entrevistas (id, estado, especificacion, creado_en, modificado_en) VALUES (?,?,?,?,?)",
    ("111111111111", "{esto no es json", None, "2026-08-12T00:00:00+00:00", "2026-08-12T00:00:00+00:00"),
)
con.commit()
con.close()
check("estado ilegible -> None, no excepción", storage.obtener_entrevista("111111111111") is None)

con = sqlite3.connect(storage.db_path())
con.execute("UPDATE proyectos SET traza_generacion = ? WHERE id = ?", ("{esto no es json", proyecto_id))
con.commit()
con.close()
check("traza_generacion ilegible -> None, no excepción", storage.obtener_traza_generacion(proyecto_id) is None)
check("pero el proyecto sigue en la lista", proyecto_id in [p["id"] for p in storage.listar_proyectos()])

import shutil  # noqa: E402
shutil.rmtree(TMP, ignore_errors=True)
shutil.rmtree(TMP_VIEJO, ignore_errors=True)

print()
print("=" * 70)
print("%d comprobaciones" % comprobaciones)
if fallos:
    print("FALLOS (%d): %s" % (len(fallos), ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK")
