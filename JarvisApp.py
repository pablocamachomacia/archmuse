"""JarvisApp.py — asistente de escritorio para ArchMuse.

Flujo: el usuario dicta o escribe una orden informal -> Gemini la convierte
en un prompt técnico estructurado -> ese prompt se ejecuta automáticamente
en Claude Code (`claude -p "<prompt>"`) -> Jarvis avisa por voz y con una
alerta visual cuando termina.

Es una herramienta de escritorio independiente del backend Flask de
ArchMuse (app.py): no lo importa ni depende de él, solo lo tiene como
contexto en la instrucción que se le da a Gemini. Se lanza aparte, con
`python JarvisApp.py` o con el launcher "Iniciar Jarvis.bat".

Dependencias (no están en requirements.txt de ArchMuse a propósito, ver
requirements-jarvis.txt): google-generativeai, SpeechRecognition, pyaudio,
pyttsx3. Todas se importan de forma defensiva -- si falta alguna, Jarvis
arranca igual y solo desactiva la función que la necesita, con un aviso
claro en el momento de usarla en vez de un traceback de import al abrir.
"""

import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

# Reconfigura la salida estándar del propio proceso a UTF-8 (2026-08-16, corrección de "Â¡Hola!" y
# símbolos similares): en Windows, `sys.stdout`/`sys.stderr` suelen abrirse con la codificación de
# consola heredada (cp1252/cp850, no UTF-8) salvo que se fuerce explícitamente. Jarvis es una app de
# escritorio (todo su texto real va al Registro de la UI, no a la consola), así que esto rara vez se
# nota -- pero cualquier traceback no capturado o print de depuración que sí llegue a la terminal
# saldría con la codificación equivocada sin este ajuste. `reconfigure` no existe en streams ya
# redirigidos a algo sin ese método (p.ej. bajo `pythonw`, sin consola) -- de ahí el try/except.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import google.generativeai as genai
    # `google-api-core` viene siempre instalado junto a `google-generativeai` (es una dependencia
    # transitiva suya, confirmado en requirements-jarvis.txt) -- se importa aquí, en el mismo bloque
    # defensivo, para poder distinguir "este modelo no existe" (404, `NotFound`) de cualquier otro
    # fallo (API key inválida, cuota, red) al decidir si tiene sentido reintentar con otro modelo.
    from google.api_core.exceptions import NotFound as GeminiModeloNoEncontrado
except ImportError:
    genai = None
    GeminiModeloNoEncontrado = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None


# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------

# Contrato de dos modos (2026-08-16, separación conversación/comando): antes, CUALQUIER orden --
# incluido un simple "hola" -- se convertía en un prompt técnico y se ejecutaba en Claude Code, lo
# cual es caro (llamada real a la CLI) y una experiencia rara para algo que no era una orden de
# código. Ahora Gemini decide primero en qué modo responder, y lo marca con una etiqueta al
# principio de su respuesta que `_parsear_respuesta_gemini` sabe leer -- así la clasificación la
# hace el propio LLM (que entiende intención en lenguaje natural mucho mejor que cualquier regla de
# palabras clave que pudiéramos escribir a mano aquí), no un `if` frágil en Python.
SYSTEM_INSTRUCTION = (
    "Eres Jarvis, el asistente de escritorio de ArchMuse. El usuario te habla de forma informal, "
    "por voz o por texto. Tienes EXACTAMENTE dos modos de respuesta, y debes elegir uno:\n\n"
    "1. CONVERSACIÓN: si el usuario solo saluda, hace una pregunta general, da las gracias, "
    "pregunta quién eres, o no da ninguna instrucción explícita de crear, modificar o corregir "
    "código, archivos o funcionalidad -- respóndele con una frase corta y natural, como hablaría un "
    "asistente por voz: MÁXIMO 1-2 frases breves, nunca una explicación larga, nunca una lista, "
    "nunca detalles técnicos de ArchMuse que nadie pidió. Ejemplo: si dice 'hola', responde algo "
    "como '¡Hola! Dime en qué te ayudo' -- no expliques qué es ArchMuse ni des una introducción. Tu "
    "respuesta debe empezar EXACTAMENTE con la etiqueta 'CONVERSACION:' seguida de tu respuesta "
    "breve.\n\n"
    "2. COMANDO: si el usuario pide explícitamente crear, modificar, corregir o generar código, "
    "archivos o funcionalidad de ArchMuse -- convierte su idea informal en un prompt estructurado "
    "de alta precisión técnica para Claude Code, especificando objetivos, requisitos de "
    "frontend/backend y reglas de salida. Tu respuesta debe empezar EXACTAMENTE con la etiqueta "
    "'COMANDO:' seguida del prompt técnico.\n\n"
    "No mezcles los dos modos en una misma respuesta. No añadas ninguna otra etiqueta ni texto "
    "antes de la etiqueta elegida."
)

# Configurable sin tocar código: `set GEMINI_MODEL_NAME=gemini-...` antes de
# lanzar Jarvis si el nombre de modelo por defecto queda obsoleto.
# Bajado de "gemini-2.5-pro" a "gemini-2.5-flash" (2026-08-16, corrección de error 404 "modelo no
# disponible"): flash es la variante que Google AI Studio sirve más ampliamente nada más generar la
# API key, y es más que suficiente para esta tarea (convertir una orden informal en un prompt
# estructurado, no razonamiento complejo).
GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.5-flash")

# Si el modelo configurado (el de arriba, o el que venga en GEMINI_MODEL_NAME) devuelve 404 --
# típico cuando un nombre de modelo queda obsoleto o todavía no está habilitado en la cuenta/región
# del usuario-- se prueba, en orden, con estos antes de rendirse. "gemini-1.5-flash" como último
# recurso: familia más antigua, pero todavía servida ampliamente, así que es la apuesta más segura
# si hasta "gemini-2.5-flash" fallara.
GEMINI_MODELOS_RESPALDO = ("gemini-2.5-flash", "gemini-1.5-flash")

# timeout=None (petición explícita, 2026-08-16, "REFACTORIZACIÓN DEFINITIVA"): antes había un
# límite de segundos para que el usuario EMPEZARA a hablar (TIMEOUT_ESCUCHA_S=12); ahora
# `recognizer.listen` espera indefinidamente a que arranque la frase -- nunca corta al usuario por
# tardar en reaccionar tras pulsar el botón. `sr.WaitTimeoutError` ya no puede producirse en la
# práctica con esto, pero se conserva su manejo en `_hilo_dictado` por si una versión futura de
# SpeechRecognition volviera a pasar un timeout por defecto.
TIMEOUT_ESCUCHA_S = None
# 10s (petición explícita, 2026-08-16): límite de duración de UNA frase ya empezada, para no
# grabar indefinidamente si el usuario se queda con el micrófono abierto sin cortar.
TIMEOUT_FRASE_S = 10
TIMEOUT_CLAUDE_S = 900  # Claude Code puede tardar en tareas grandes

COLOR_BG = "#0a0b0d"
COLOR_CARD = "#16191f"
COLOR_BORDE = "#262a33"
COLOR_TEXTO = "#f8fafc"
COLOR_MUTED = "#8b93a1"
COLOR_ACCENT = "#3b82f6"
COLOR_ACCENT_HOVER = "#60a5fa"

ESTADOS = {
    "esperando": ("Esperando", COLOR_MUTED),
    "escuchando": ("Escuchando…", COLOR_ACCENT),
    "optimizando": ("Gemini optimizando…", "#f59e0b"),
    "ejecutando": ("Claude ejecutando…", "#a78bfa"),
    "completado": ("Completado", "#22c55e"),
    "respondido": ("Respondido", "#22c55e"),
    "sin_voz": ("No se detectó voz. Vuelve a intentarlo.", COLOR_MUTED),
    "error": ("Error", "#ef4444"),
}


# --------------------------------------------------------------------------
# Integraciones (funciones puras, sin tocar la UI -- se llaman desde hilos
# de fondo para no bloquear el mainloop de Tkinter)
# --------------------------------------------------------------------------

# Modelo que ya se confirmó funcionando en esta ejecución de Jarvis (ver `optimizar_prompt_con_
# gemini`) -- una vez resuelto dinámicamente con `genai.list_models()`, se recuerda para el resto de
# la sesión: así solo se paga el coste de listar modelos la primera vez que hace falta, no en cada
# orden que dicta el usuario.
_modelo_gemini_resuelto = None


def _normalizar_nombre_modelo(nombre):
    """`genai.list_models()` devuelve nombres con el prefijo "models/" (p.ej.
    "models/gemini-1.5-flash-latest"); GEMINI_MODEL_NAME/GEMINI_MODELOS_RESPALDO no lo llevan. Se
    normaliza solo para poder comparar y no reintentar el mismo modelo subyacente dos veces bajo dos
    formas de nombre distintas -- el nombre real que se usa para la llamada es siempre el original.
    """
    return nombre[len("models/"):] if nombre.startswith("models/") else nombre


def _es_modelo_no_encontrado(exc):
    """True si `exc` es "este modelo no existe/no está disponible" (404) y no otra cosa (API key
    inválida, cuota, red) -- solo en ese caso merece la pena seguir probando otro nombre de modelo.
    Se comprueba tanto la excepción específica del SDK como el texto del error, por si una versión
    distinta de la librería lo envuelve en otra clase.
    """
    return (
        (GeminiModeloNoEncontrado is not None and isinstance(exc, GeminiModeloNoEncontrado))
        or "404" in str(exc)
        or "not found" in str(exc).lower()
    )


def _generar_con_modelo(nombre_modelo, texto_usuario):
    modelo = genai.GenerativeModel(model_name=nombre_modelo, system_instruction=SYSTEM_INSTRUCTION)
    respuesta = modelo.generate_content(texto_usuario)
    texto = (getattr(respuesta, "text", "") or "").strip()
    if not texto:
        raise RuntimeError("Gemini devolvió una respuesta vacía.")
    return texto


def _listar_modelos_gemini_con_generate_content(log=None):
    """Pregunta a la API, en vivo, qué modelos admiten `generateContent` para la API key
    configurada -- en vez de seguir adivinando nombres fijos que pueden quedar obsoletos (la causa
    real del 404 que motivó este cambio). Devuelve [] si la llamada falla (sin red, key inválida):
    es un mecanismo de último recurso, nunca debe lanzar ni tumbar el flujo si tampoco funciona.
    """
    def _log(mensaje):
        if log is not None:
            log(mensaje)
    try:
        disponibles = []
        for modelo in genai.list_models():
            metodos = getattr(modelo, "supported_generation_methods", ()) or ()
            if "generateContent" in metodos:
                disponibles.append(modelo.name)
        return disponibles
    except Exception as exc:
        _log("[INFO] No se pudo listar modelos de Gemini ({}).".format(exc))
        return []


def optimizar_prompt_con_gemini(texto_usuario, log=None):
    """Envía la orden informal a Gemini y devuelve el prompt técnico.

    `log`, si se pasa, es una función de un argumento para el Registro de la UI (mismo patrón que
    `escuchar_microfono`) -- aquí se usa para trazar qué modelo de Gemini acabó respondiendo.
    """
    global _modelo_gemini_resuelto

    def _log(mensaje):
        if log is not None:
            log(mensaje)

    if genai is None:
        raise RuntimeError(
            "Falta 'google-generativeai'. Instálalo con: pip install google-generativeai"
        )
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("No se encontró la variable de entorno GEMINI_API_KEY.")

    genai.configure(api_key=api_key)

    # Orden de intento: 1) el modelo ya confirmado en esta sesión (si lo hay), 2) el configurado
    # (GEMINI_MODEL_NAME), 3) los de respaldo fijos -- sin repetir el mismo modelo subyacente dos
    # veces (ver `_normalizar_nombre_modelo`).
    candidatos = ([_modelo_gemini_resuelto] if _modelo_gemini_resuelto else [])
    candidatos += [GEMINI_MODEL_NAME] + list(GEMINI_MODELOS_RESPALDO)
    modelos_a_probar, vistos = [], set()
    for nombre in candidatos:
        clave = _normalizar_nombre_modelo(nombre)
        if clave not in vistos:
            vistos.add(clave)
            modelos_a_probar.append(nombre)

    ultimo_error = None
    hubo_404 = False
    for nombre_modelo in modelos_a_probar:
        try:
            texto = _generar_con_modelo(nombre_modelo, texto_usuario)
            _modelo_gemini_resuelto = nombre_modelo
            _log("[INFO] Modelo Gemini activo: {}".format(nombre_modelo))
            return texto
        except Exception as exc:
            ultimo_error = exc
            if not _es_modelo_no_encontrado(exc):
                raise  # fallo real (API key/cuota/red): no tiene sentido probar otro nombre
            hubo_404 = True

    if not hubo_404:
        raise RuntimeError("Ningún modelo de Gemini disponible. Último error: {}".format(ultimo_error))

    # Ningún nombre fijo funcionó -- en vez de seguir adivinando, se pregunta a la API qué modelos
    # admite de verdad esta clave ahora mismo (encargo explícito, 2026-08-16).
    _log("[INFO] Ningún modelo fijo disponible; consultando genai.list_models()...")
    for nombre_modelo in _listar_modelos_gemini_con_generate_content(log=_log):
        clave = _normalizar_nombre_modelo(nombre_modelo)
        if clave in vistos:
            continue
        vistos.add(clave)
        try:
            texto = _generar_con_modelo(nombre_modelo, texto_usuario)
            _modelo_gemini_resuelto = nombre_modelo
            _log("[INFO] Modelo Gemini activo: {}".format(nombre_modelo))
            return texto
        except Exception as exc:
            ultimo_error = exc
            continue

    raise RuntimeError("Ningún modelo de Gemini disponible. Último error: {}".format(ultimo_error))


def _parsear_respuesta_gemini(texto_crudo):
    """Separa la respuesta de Gemini en (modo, contenido) según la etiqueta de SYSTEM_INSTRUCTION
    ("CONVERSACION:"/"COMANDO:"). Si Gemini no sigue el formato (los LLM no son 100% deterministas,
    puede pasar), se trata como conversación por defecto: es la opción segura -- invocar Claude Code
    sobre algo que no era realmente una orden de código es mucho más disruptivo que responder en
    texto algo que sí lo era.
    """
    texto = (texto_crudo or "").strip()
    mayus = texto.upper()
    if mayus.startswith("COMANDO:"):
        return "comando", texto[len("COMANDO:"):].strip()
    if mayus.startswith("CONVERSACION:"):
        return "conversacion", texto[len("CONVERSACION:"):].strip()
    if mayus.startswith("CONVERSACIÓN:"):
        return "conversacion", texto[len("CONVERSACIÓN:"):].strip()
    return "conversacion", texto


def resolver_modelo_gemini_al_inicio(log=None):
    """Resuelve y cachea (`_modelo_gemini_resuelto`) qué modelo de Gemini usar, en segundo plano,
    justo al arrancar Jarvis -- para que la primera orden real del usuario no pague el coste de
    `genai.list_models()` si el modelo configurado por defecto ya está obsoleto (encargo explícito,
    2026-08-16). Solo consulta disponibilidad, nunca llama a `generate_content`: arrancar la app no
    debe gastar cuota de generación. Si algo falla (sin API key todavía, sin red), no hace nada --
    `optimizar_prompt_con_gemini` ya resuelve el modelo por su cuenta, más despacio, en la primera
    orden real si esto no llegó a completarse.
    """
    global _modelo_gemini_resuelto

    def _log(mensaje):
        if log is not None:
            log(mensaje)

    if genai is None:
        return
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return
    try:
        genai.configure(api_key=api_key)
    except Exception:
        return

    candidatos_fijos = [GEMINI_MODEL_NAME] + list(GEMINI_MODELOS_RESPALDO)
    disponibles = _listar_modelos_gemini_con_generate_content(log=_log)
    if not disponibles:
        return  # sin red o key inválida -- se deja para que optimizar_prompt_con_gemini lo intente

    disponibles_normalizados = {_normalizar_nombre_modelo(n) for n in disponibles}
    for candidato in candidatos_fijos:
        if _normalizar_nombre_modelo(candidato) in disponibles_normalizados:
            _modelo_gemini_resuelto = candidato
            _log("[INFO] Modelo Gemini activo: {}".format(candidato))
            return

    # Ninguno de los nombres fijos aparece en lo que la API dice que existe -- se usa el primero
    # disponible de verdad en vez de seguir confiando en nombres que podrían dar 404.
    _modelo_gemini_resuelto = disponibles[0]
    _log("[INFO] Modelo Gemini activo: {}".format(disponibles[0]))


# Palabras que delatan un micrófono real (nombres típicos de driver/marca
# en Windows). Comparación en minúsculas, sin acentos exigidos -- se listan
# ambas formas de "micrófono" para no depender de que Windows reporte el
# nombre con o sin tilde según el idioma del sistema.
PALABRAS_CLAVE_MIC_REAL = ("microphone", "micrófono", "microfono", "realtek", "headset", "array")

# Dispositivos de captura virtuales/de bucle -- válidos para grabar lo que
# suena en el PC, pero mudos si el usuario está hablando delante del
# micrófono físico. En muchos equipos Windows uno de estos aparece en el
# índice 0, que es justo el que PyAudio abre "por defecto" -- causa
# confirmada del "Timeout: no se detectó voz" con el usuario hablando.
PALABRAS_CLAVE_VIRTUAL = (
    "stereo mix", "mezcla estéreo", "mezcla estereo", "virtual", "mapper",
    "asignador de sonido",  # "Sound Mapper" en Windows en español -- es
    # justo el dispositivo que ocupa el índice 0 en máquinas con varias
    # tarjetas de sonido (confirmado en pruebas): sin este descarte
    # explícito, la lógica solo lo evitaba por casualidad al no matchear
    # ninguna palabra clave de micrófono real, no por exclusión activa.
)


def listar_microfonos():
    """Devuelve [(índice, nombre), ...] de los micrófonos que ve PyAudio, o
    [] si SpeechRecognition/pyaudio no están instalados o fallan al listar.
    """
    if sr is None:
        return []
    try:
        return list(enumerate(sr.Microphone.list_microphone_names()))
    except Exception:
        return []


def _es_dispositivo_virtual(nombre):
    nombre_normalizado = (nombre or "").lower()
    return any(palabra in nombre_normalizado for palabra in PALABRAS_CLAVE_VIRTUAL)


def _indice_microfono_preferido(microfonos=None):
    """Elige automáticamente el índice de micrófono a usar.

    Orden de prioridad:
    1. El primer dispositivo cuyo nombre contenga una palabra clave de
       micrófono real (Microphone/Micrófono/Realtek/Headset/Array) y que no
       sea, a la vez, un dispositivo virtual (Stereo Mix/Virtual/Mapper).
    2. Si ninguno matchea por nombre, el dispositivo de entrada por defecto
       que reporta PyAudio -- pero solo si tampoco es un virtual conocido.
    3. El primer dispositivo no vacío y no virtual de la lista.
    4. None, para que decida PyAudio como último recurso (nunca debe
       impedir el arranque ni el intento de escucha).
    """
    if microfonos is None:
        microfonos = listar_microfonos()

    for indice, nombre in microfonos:
        if not nombre or _es_dispositivo_virtual(nombre):
            continue
        nombre_normalizado = nombre.lower()
        if any(palabra in nombre_normalizado for palabra in PALABRAS_CLAVE_MIC_REAL):
            return indice

    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        try:
            indice_defecto = pa.get_default_input_device_info()["index"]
            nombre_defecto = dict(microfonos).get(indice_defecto, "")
            if not _es_dispositivo_virtual(nombre_defecto):
                return indice_defecto
        finally:
            pa.terminate()
    except Exception:
        pass

    for indice, nombre in microfonos:
        if nombre and not _es_dispositivo_virtual(nombre):
            return indice

    return None


def _resolver_microfono(device_index_forzado=None):
    """Devuelve (índice, nombre) del micrófono a usar. Si se pasa un índice
    ya elegido a mano (desde el desplegable de la UI), lo respeta tal cual;
    si no, aplica la selección automática de `_indice_microfono_preferido`.
    """
    microfonos = listar_microfonos()
    nombres_por_indice = dict(microfonos)

    if device_index_forzado is not None:
        return device_index_forzado, nombres_por_indice.get(device_index_forzado, "desconocido")

    indice = _indice_microfono_preferido(microfonos)
    nombre = nombres_por_indice.get(indice, "predeterminado del sistema")
    return indice, nombre


def escuchar_microfono(log=None, device_index=None):
    """Graba del micrófono y devuelve la transcripción (es-ES).

    `log`, si se pasa, es una función de un argumento a la que se le
    reportan mensajes de progreso ([INFO]/[OK]) para el Registro de la UI.
    Se pasa como parámetro en vez de importar Tkinter aquí -- esta función
    sigue siendo utilizable sola, sin GUI, desde el hilo de fondo que la
    llama.

    `device_index`, si se pasa (por ejemplo desde el desplegable manual de
    la UI), fuerza ese micrófono concreto; si es None, se elige solo con
    `_resolver_microfono` (ver ahí el orden de prioridad).
    """
    def _log(mensaje):
        if log is not None:
            log(mensaje)

    if sr is None:
        raise RuntimeError(
            "Falta 'SpeechRecognition'/'pyaudio'. Instálalos con: "
            "pip install SpeechRecognition pyaudio"
        )
    reconocedor = sr.Recognizer()
    # 175 como umbral de partida (bajo, a propósito, para no perder voces
    # suaves) -- adjust_for_ambient_noise lo recalcula igualmente en cuanto
    # mide el ruido real de la sala. dynamic_energy_threshold=True hace que
    # siga ajustándose después, frase a frase, en vez de quedarse fijo si
    # cambia el ruido ambiente a mitad de sesión.
    reconocedor.energy_threshold = 175
    reconocedor.dynamic_energy_threshold = True

    indice_mic, nombre_mic = _resolver_microfono(device_index)
    _log("[INFO] Usando micrófono: {}".format(nombre_mic))
    _log("[INFO] Abriendo micrófono...")
    with sr.Microphone(device_index=indice_mic) as fuente:
        # Subido de 0.2s a 0.8s (petición explícita, 2026-08-16, "captura robusta"): un ajuste más
        # largo de ruido ambiente calibra mejor `energy_threshold` antes de cada frase -- se prioriza
        # una detección de voz más fiable sobre el pequeño retraso extra que supone.
        _log("[INFO] Calibrando ruido ambiente...")
        reconocedor.adjust_for_ambient_noise(fuente, duration=0.8)
        _log("[INFO] Escuchando (sin límite de espera hasta que empieces a hablar)...")
        audio = reconocedor.listen(
            fuente, timeout=TIMEOUT_ESCUCHA_S, phrase_time_limit=TIMEOUT_FRASE_S
        )
    _log("[INFO] Audio capturado, procesando reconocimiento...")
    texto = reconocedor.recognize_google(audio, language="es-ES")
    _log("[OK] Orden capturada: '{}'".format(texto))
    return texto


def ejecutar_claude(prompt_optimizado):
    """Ejecuta `claude -p <prompt>` y devuelve el CompletedProcess.

    En Windows, `claude` suele ser un shim npm (.cmd), que CreateProcess no
    puede lanzar directamente sin shell=True. Se intenta primero sin shell
    (más seguro, sin interpretación de metacaracteres) y solo se cae a
    shell=True si el ejecutable no aparece así -- list2cmdline conserva el
    escapado correcto del prompt como un único argumento.
    """
    # `encoding="utf-8", errors="replace"` explícito (2026-08-16, corrección de "Â¡Hola!" y símbolos
    # descuadrados): sin esto, `text=True` decodifica la salida de `claude` con
    # `locale.getpreferredencoding()`, que en Windows suele ser cp1252/cp850, no UTF-8 -- y `claude`
    # escribe en UTF-8. `errors="replace"` evita que un byte realmente inválido tumbe la ejecución
    # con un `UnicodeDecodeError` a mitad de una tarea larga; en el peor caso se pierde un carácter
    # como `�`, nunca la salida completa.
    args = ["claude", "-p", prompt_optimizado]
    try:
        return subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=TIMEOUT_CLAUDE_S,
        )
    except (FileNotFoundError, OSError):
        comando = subprocess.list2cmdline(args)
        return subprocess.run(
            comando,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_CLAUDE_S,
        )


# Palabras que delatan una voz en español instalada en el sistema (nombres típicos de las voces de
# Microsoft en Windows: "Microsoft Helena Desktop - Spanish (Spain)", "Microsoft Sabina Desktop -
# Spanish (Mexico)"; y los códigos de locale "es-ES"/"es_ES" que suelen aparecer en el `id` interno
# de la voz aunque no en su nombre visible). Se busca por nombre/id porque `voice.languages` de
# SAPI5 (el backend de pyttsx3 en Windows) casi nunca viene relleno de forma fiable -- coincidir por
# texto es lo que de verdad funciona en la práctica.
PALABRAS_CLAVE_VOZ_ESPANOLA = (
    "spanish", "español", "espanol", "helena", "sabina", "es-es", "es_es",
)

# Velocidad de habla (palabras/min aprox.) -- 165 (encargo explícito, 2026-08-16): el valor por
# defecto de pyttsx3/SAPI5 suena acelerado y algo metálico para una voz que debe sonar natural en
# una conversación, no para leer texto lo más rápido posible.
VELOCIDAD_VOZ = 165


def _configurar_voz_espanola(motor):
    """Selecciona una voz en español con tono natural en `motor` si el sistema tiene alguna
    instalada, y fija la velocidad de habla a `VELOCIDAD_VOZ`. Sin la selección de voz, pyttsx3 usa
    la voz por defecto del sistema -- en Windows suele ser una voz en inglés, que pronuncia el
    español mal. Si no encuentra ninguna coincidencia, deja la voz por defecto tal cual (nunca
    lanza, ni bloquea el aviso por voz por esto)."""
    try:
        motor.setProperty("rate", VELOCIDAD_VOZ)
    except Exception:
        pass
    try:
        voces = motor.getProperty("voices") or []
    except Exception:
        return
    for voz in voces:
        nombre = (getattr(voz, "name", "") or "").lower()
        identificador = (getattr(voz, "id", "") or "").lower()
        idioma = " ".join(str(item) for item in (getattr(voz, "languages", None) or [])).lower()
        texto_voz = nombre + " " + identificador + " " + idioma
        if any(palabra in texto_voz for palabra in PALABRAS_CLAVE_VOZ_ESPANOLA):
            try:
                motor.setProperty("voice", voz.id)
            except Exception:
                pass
            return


# Patrones de limpieza para TTS (petición explícita, 2026-08-16, "REFACTORIZACIÓN DEFINITIVA"): la
# salida real de Claude Code o del propio Registro puede traer bloques de código Markdown, marcas de
# formato o etiquetas de log ("[INFO]", "[OK]") -- todo eso suena fatal leído en voz alta letra a
# letra por pyttsx3 ("almohadilla almohadilla", "corchete INFO corchete"...). Ninguno de estos
# patrones toca el Registro de la UI, que sigue mostrando el texto completo sin tocar -- solo se
# aplican a la copia que se lee en voz alta.
_RE_BLOQUE_CODIGO = re.compile(r"```.*?```", re.S)  # ```...``` (con o sin lenguaje tras las comillas)
_RE_CODIGO_INLINE = re.compile(r"`([^`]*)`")  # `algo` -> algo (se lee el contenido, no las comillas)
_RE_ETIQUETA_LOG = re.compile(r"\[(?:INFO|OK|ERROR|WARN|DEBUG)\]\s*", re.I)
_RE_MARCAS_MARKDOWN = re.compile(r"[*_#>~]+")  # negrita/cursiva/encabezados/citas/tachado
_RE_ESPACIOS = re.compile(r"\s+")


def _limpiar_texto_para_voz(texto):
    """Quita de `texto` todo lo que no tiene sentido leído en voz alta: bloques de código Markdown
    completos (se descartan, no se leen), formato inline (negrita/cursiva/código suelto -- se
    conserva el contenido, se quitan solo los símbolos) y etiquetas de log. Nunca lanza: si algo
    falla, se devuelve el texto original tal cual antes que dejar a Jarvis sin voz."""
    try:
        limpio = _RE_BLOQUE_CODIGO.sub(" ", texto or "")
        limpio = _RE_CODIGO_INLINE.sub(r"\1", limpio)
        limpio = _RE_ETIQUETA_LOG.sub("", limpio)
        limpio = _RE_MARCAS_MARKDOWN.sub("", limpio)
        return _RE_ESPACIOS.sub(" ", limpio).strip()
    except Exception:
        return texto or ""


def _resumen_para_voz(texto, max_caracteres=220):
    """Limpia `texto` de formato no apto para voz (`_limpiar_texto_para_voz`) y lo recorta a un
    tamaño razonable para leerlo en voz alta -- la salida real de Claude Code puede ser un volcado
    larguísimo (diffs, rutas de archivo, etc.); leerlo entero en voz alta sería peor experiencia que
    un resumen corto. Corta por palabra completa, no a mitad, para que no suene truncado a media
    sílaba. El Registro de la UI (`self._log`) sigue mostrando siempre el texto original completo --
    esta versión corta y limpia es solo para `notificar_voz`."""
    texto = _limpiar_texto_para_voz(texto)
    if not texto:
        return ""
    if len(texto) <= max_caracteres:
        return texto
    return texto[:max_caracteres].rsplit(" ", 1)[0] + "…"


def notificar_voz(texto):
    """Lee `texto` en voz alta en un hilo aparte (no bloquea la UI)."""
    if pyttsx3 is None:
        return

    def _hablar():
        try:
            motor = pyttsx3.init()
            _configurar_voz_espanola(motor)
            motor.say(texto)
            motor.runAndWait()
        except Exception:
            pass  # la voz es un "extra"; un fallo aquí no debe tumbar Jarvis

    threading.Thread(target=_hablar, daemon=True).start()


# --------------------------------------------------------------------------
# Interfaz gráfica
# --------------------------------------------------------------------------

class JarvisApp:
    def __init__(self, root):
        self.root = root
        self.cola = queue.Queue()
        self.procesando = False
        self.device_index_seleccionado = None  # None = selección automática
        # Escucha continua (encargo explícito, 2026-08-16): mientras esté a True, cada ciclo
        # completo (escuchar -> Gemini -> [Claude Code] -> respuesta) relanza otro automáticamente
        # en vez de volver a "Esperando" -- ver `_continuar_o_esperar`. Solo el propio botón lo pone
        # a False; un ciclo ya en curso cuando se pulsa "Detener" termina solo (no se puede
        # interrumpir a mitad un `recognizer.listen()` ya bloqueado sin arriesgar el estado del
        # micrófono), simplemente no se relanza otro después.
        self.escucha_continua = False

        self.root.title("Jarvis · ArchMuse")
        self.root.configure(bg=COLOR_BG)
        self.root.geometry("460x420")
        self.root.minsize(420, 380)
        self.root.attributes("-topmost", True)

        self._avisos_dependencias_pendientes()
        self._construir_ui()
        self.root.after(120, self._drenar_cola)

        # Resuelve el modelo de Gemini al arrancar, en segundo plano (encargo explícito,
        # 2026-08-16), para que la primera orden real del usuario no pague el coste de
        # `genai.list_models()` si el modelo por defecto ya está obsoleto.
        threading.Thread(
            target=lambda: resolver_modelo_gemini_al_inicio(log=lambda m: self.cola.put(("log", m))),
            daemon=True,
        ).start()

    # -- construcción --------------------------------------------------

    def _avisos_dependencias_pendientes(self):
        faltantes = []
        if genai is None:
            faltantes.append("google-generativeai (optimización con Gemini)")
        if sr is None:
            faltantes.append("SpeechRecognition/pyaudio (dictado por voz)")
        if pyttsx3 is None:
            faltantes.append("pyttsx3 (aviso por voz)")
        self._faltantes = faltantes

    def _construir_ui(self):
        contenedor = tk.Frame(self.root, bg=COLOR_BG, padx=18, pady=16)
        contenedor.pack(fill="both", expand=True)

        # -- cabecera --
        cabecera = tk.Frame(contenedor, bg=COLOR_BG)
        cabecera.pack(fill="x")
        tk.Label(
            cabecera, text="JARVIS", fg=COLOR_TEXTO, bg=COLOR_BG,
            font=("Segoe UI Semibold", 15),
        ).pack(side="left")
        tk.Label(
            cabecera, text="para ArchMuse", fg=COLOR_MUTED, bg=COLOR_BG,
            font=("Segoe UI", 10),
        ).pack(side="left", padx=(6, 0))

        # -- indicador de estado --
        fila_estado = tk.Frame(contenedor, bg=COLOR_BG)
        fila_estado.pack(fill="x", pady=(10, 14))
        self.punto_estado = tk.Canvas(
            fila_estado, width=12, height=12, bg=COLOR_BG, highlightthickness=0
        )
        self.punto_estado.pack(side="left")
        self._dibujo_punto = self.punto_estado.create_oval(1, 1, 11, 11, fill=COLOR_MUTED, outline="")
        self.label_estado = tk.Label(
            fila_estado, text=ESTADOS["esperando"][0], fg=COLOR_MUTED, bg=COLOR_BG,
            font=("Segoe UI", 11, "bold"),
        )
        self.label_estado.pack(side="left", padx=(8, 0))

        # -- botón de micrófono --
        self.boton_mic = tk.Button(
            contenedor, text="🎙  Hablar con Jarvis", command=self._al_pulsar_microfono,
            bg=COLOR_ACCENT, fg="white", activebackground=COLOR_ACCENT_HOVER,
            activeforeground="white", font=("Segoe UI", 12, "bold"),
            relief="flat", bd=0, padx=14, pady=12, cursor="hand2",
        )
        self.boton_mic.pack(fill="x")

        # -- selector de micrófono --
        fila_mic = tk.Frame(contenedor, bg=COLOR_BG)
        fila_mic.pack(fill="x", pady=(8, 0))
        tk.Label(
            fila_mic, text="Micrófono:", fg=COLOR_MUTED, bg=COLOR_BG,
            font=("Segoe UI", 9),
        ).pack(side="left")
        # Nota: en Windows el tema ttk nativo ("vista"/"xpnative") ignora
        # parte de estos colores en el Combobox pese a configurarlos -- es
        # una limitación conocida de ttk, no un fallo de esta app.
        estilo_combo = ttk.Style()
        estilo_combo.configure(
            "Jarvis.TCombobox", fieldbackground=COLOR_CARD, background=COLOR_CARD,
            foreground=COLOR_TEXTO, arrowcolor=COLOR_TEXTO,
        )
        self._opciones_mic = [(None, "Automático (recomendado)")] + listar_microfonos()
        self.combo_mic = ttk.Combobox(
            fila_mic, style="Jarvis.TCombobox", state="readonly",
            font=("Segoe UI", 9),
            values=[nombre for _, nombre in self._opciones_mic],
        )
        self.combo_mic.current(0)
        self.combo_mic.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.combo_mic.bind("<<ComboboxSelected>>", self._al_cambiar_microfono)
        if not self._opciones_mic[1:]:
            self.combo_mic.configure(state="disabled")

        # -- texto rápido opcional --
        tk.Label(
            contenedor, text="o escribe la orden (opcional):", fg=COLOR_MUTED, bg=COLOR_BG,
            font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x", pady=(14, 4))
        fila_texto = tk.Frame(contenedor, bg=COLOR_BG)
        fila_texto.pack(fill="x")
        self.entrada_texto = tk.Entry(
            fila_texto, bg=COLOR_CARD, fg=COLOR_TEXTO, insertbackground=COLOR_TEXTO,
            relief="flat", font=("Segoe UI", 10), highlightthickness=1,
            highlightbackground=COLOR_BORDE, highlightcolor=COLOR_ACCENT,
        )
        self.entrada_texto.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self.entrada_texto.bind("<Return>", lambda ev: self._al_enviar_texto())
        tk.Button(
            fila_texto, text="Enviar", command=self._al_enviar_texto,
            bg=COLOR_CARD, fg=COLOR_TEXTO, activebackground=COLOR_BORDE,
            activeforeground=COLOR_TEXTO, relief="flat", bd=0, padx=12,
            font=("Segoe UI", 10), cursor="hand2",
        ).pack(side="left")

        # -- registro --
        tk.Label(
            contenedor, text="Registro:", fg=COLOR_MUTED, bg=COLOR_BG,
            font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x", pady=(14, 4))
        self.registro = scrolledtext.ScrolledText(
            contenedor, bg=COLOR_CARD, fg=COLOR_TEXTO, insertbackground=COLOR_TEXTO,
            relief="flat", font=("Consolas", 9), wrap="word", height=8, state="disabled",
        )
        self.registro.pack(fill="both", expand=True)

        if self._faltantes:
            self._log(
                "⚠ Dependencias no instaladas: " + "; ".join(self._faltantes)
            )

    # -- estado / registro ----------------------------------------------

    def _set_estado(self, clave):
        texto, color = ESTADOS[clave]
        self.label_estado.configure(text=texto, fg=color)
        self.punto_estado.itemconfig(self._dibujo_punto, fill=color)

    def _log(self, texto):
        self.registro.configure(state="normal")
        self.registro.insert("end", texto.rstrip() + "\n\n")
        self.registro.see("end")
        self.registro.configure(state="disabled")

    # -- disparadores de UI ----------------------------------------------

    def _al_cambiar_microfono(self, _evento):
        indice, _nombre = self._opciones_mic[self.combo_mic.current()]
        self.device_index_seleccionado = indice

    def _al_pulsar_microfono(self):
        if self.escucha_continua:
            # "Detener escucha": corta el bucle. El ciclo en curso (si lo hay) termina solo -- ver
            # el comentario de `self.escucha_continua` en __init__.
            self.escucha_continua = False
            self.boton_mic.configure(text="🎙  Hablar con Jarvis")
            return
        if self.procesando:
            return
        if sr is None:
            # Cero pop-ups (petición explícita, 2026-08-16): también para esto, que antes sí abría
            # un messagebox modal. El aviso ya vive en el Registro desde el arranque
            # (`_avisos_dependencias_pendientes`); aquí solo se refuerza en el estado visible.
            self._log(
                "⚠ Falta 'SpeechRecognition'/'pyaudio' para dictar por voz. Instálalos con: "
                "pip install SpeechRecognition pyaudio"
            )
            self._set_estado("error")
            return
        self.escucha_continua = True
        self.boton_mic.configure(text="🛑  Detener escucha")
        self.procesando = True
        threading.Thread(target=self._hilo_dictado, daemon=True).start()

    def _continuar_o_esperar(self, demora_ms=2500):
        """Al terminar un ciclo (respuesta, comando completado, timeout sin voz o error): si la
        escucha continua sigue activa, relanza otra escucha automáticamente tras `demora_ms` (para
        no encadenar sin pausa, se deja un respiro); si no, vuelve a "Esperando"."""
        if self.escucha_continua:
            self.root.after(demora_ms, self._relanzar_escucha)
        else:
            self.root.after(demora_ms, lambda: self._set_estado("esperando"))

    def _relanzar_escucha(self):
        if not self.escucha_continua or self.procesando:
            return
        # El propio `_hilo_dictado` pone el estado a "escuchando" como primer paso (vía la cola,
        # igual que cualquier otro ciclo) -- no hace falta duplicarlo aquí.
        self.procesando = True
        threading.Thread(target=self._hilo_dictado, daemon=True).start()

    def _hilo_dictado(self):
        self.cola.put(("estado", "escuchando"))
        try:
            texto = escuchar_microfono(
                log=lambda m: self.cola.put(("log", m)),
                device_index=self.device_index_seleccionado,
            )
        except sr.WaitTimeoutError:
            # Se conserva por si una versión futura de SpeechRecognition volviera a pasar un timeout
            # por defecto (con TIMEOUT_ESCUCHA_S=None esto ya no debería producirse en la práctica).
            # No es un error real: cero pop-ups, solo estado + registro, y se reintenta solo.
            self.cola.put(("log", "[INFO] Timeout: no se detectó voz a tiempo."))
            self.cola.put(("sin_voz", None))
            return
        except sr.UnknownValueError:
            # Se capturó audio pero no se entendió nada (silencio, ruido de fondo, voz demasiado
            # baja) -- exactamente el caso que pide la "REFACTORIZACIÓN DEFINITIVA": nunca un
            # pop-up ni un aviso de error por voz, solo el estado en la interfaz y otro intento
            # transparente, como si nada hubiera pasado.
            self.cola.put(("log", "[INFO] No se entendió el audio (silencio o ruido de fondo)."))
            self.cola.put(("sin_voz", None))
            return
        except sr.RequestError as exc:
            # Este sí es un fallo real (el servicio de reconocimiento de Google no respondió: sin
            # red, caído, cuota) -- pero sigue sin pop-up, igual que cualquier otro error de este
            # refactor: se refleja en estado + registro y el ciclo se reintenta igual.
            self.cola.put(("log", "[ERROR] Servicio de reconocimiento no disponible: {}".format(exc)))
            self.cola.put(("error", "No se pudo contactar con el servicio de voz: {}".format(exc)))
            return
        except Exception as exc:
            self.cola.put(("log", "[ERROR] {}".format(exc)))
            self.cola.put(("error", "No se pudo escuchar: {}".format(exc)))
            return
        self._procesar_orden(texto)

    def _al_enviar_texto(self):
        if self.procesando:
            return
        texto = self.entrada_texto.get().strip()
        if not texto:
            return
        self.entrada_texto.delete(0, "end")
        self.procesando = True
        threading.Thread(target=self._procesar_orden, args=(texto,), daemon=True).start()

    # -- pipeline (se ejecuta en hilo de fondo) --------------------------

    def _procesar_orden(self, texto_usuario):
        self.cola.put(("log", "Orden: {}".format(texto_usuario)))
        self.cola.put(("estado", "optimizando"))
        try:
            respuesta_cruda = optimizar_prompt_con_gemini(
                texto_usuario, log=lambda m: self.cola.put(("log", m))
            )
        except Exception as exc:
            self.cola.put(("error", "Gemini falló: {}".format(exc)))
            return

        # Separación conversación/comando (encargo explícito, 2026-08-16): un saludo o pregunta
        # general no debe invocar la CLI de Claude Code -- eso es una llamada real, cara, y una
        # experiencia rara para algo que no era una orden de código. Gemini ya decidió el modo (ver
        # SYSTEM_INSTRUCTION); aquí solo se lee su etiqueta.
        modo, contenido = _parsear_respuesta_gemini(respuesta_cruda)
        if modo == "conversacion":
            self.cola.put(("log", "Jarvis: {}".format(contenido)))
            self.cola.put(("conversacion", contenido))
            return

        prompt_optimizado = contenido
        self.cola.put(("log", "Prompt optimizado:\n{}".format(prompt_optimizado)))
        self.cola.put(("estado", "ejecutando"))
        try:
            resultado = ejecutar_claude(prompt_optimizado)
        except subprocess.TimeoutExpired:
            self.cola.put(("error", "Claude Code superó el tiempo máximo de espera."))
            return
        except Exception as exc:
            self.cola.put(("error", "No se pudo ejecutar Claude Code: {}".format(exc)))
            return

        salida = (resultado.stdout or "").strip()
        salida_error = (resultado.stderr or "").strip()
        if resultado.returncode != 0:
            detalle = salida_error or salida or "sin salida"
            self.cola.put(("log", "Claude Code devolvió código {}:\n{}".format(
                resultado.returncode, detalle
            )))
            self.cola.put(("error", "Claude Code terminó con error. Revisa el registro."))
            return

        if salida:
            self.cola.put(("log", "Salida de Claude Code:\n{}".format(salida)))
        self.cola.put(("completado", salida))

    # -- bombeo de la cola (hilo principal, seguro para Tkinter) --------

    def _drenar_cola(self):
        try:
            while True:
                tipo, valor = self.cola.get_nowait()
                if tipo == "estado":
                    self._set_estado(valor)
                elif tipo == "log":
                    self._log(valor)
                elif tipo == "sin_voz":
                    self._set_estado("sin_voz")
                    self.procesando = False
                    # En escucha continua, un timeout sin voz simplemente relanza otra escucha --
                    # es justo el caso de uso de "no hace falta pulsar el botón cada vez".
                    self._continuar_o_esperar(2000)
                elif tipo == "error":
                    # Cero pop-ups (petición explícita, 2026-08-16, "REFACTORIZACIÓN DEFINITIVA"):
                    # antes esto también abría un messagebox modal que había que cerrar a mano. El
                    # registro completo (`valor` sin limpiar) sigue viéndose entero en la interfaz;
                    # solo la versión hablada pasa por `_resumen_para_voz` para sonar natural.
                    self._set_estado("error")
                    self._log("⚠ " + valor)
                    self.procesando = False
                    notificar_voz("Ha ocurrido un error. " + _resumen_para_voz(valor))
                    self._continuar_o_esperar(500)
                elif tipo == "conversacion":
                    # Respuesta conversacional de Gemini (sin pasar por Claude Code): se lee en voz
                    # alta y el estado se refleja solo en la interfaz -- sin messagebox, es una
                    # respuesta, no un evento que requiera confirmación del usuario.
                    self._set_estado("respondido")
                    self.procesando = False
                    if valor:
                        notificar_voz(_resumen_para_voz(valor))
                    # Escucha continua (encargo explícito, 2026-08-16): tras responder, vuelve a
                    # escuchar sola -- no hay que pulsar el botón de nuevo hasta decir "Detener".
                    self._continuar_o_esperar(2500)
                elif tipo == "completado":
                    self._set_estado("completado")
                    self.procesando = False
                    # Lee el mensaje principal de la respuesta (la salida real de Claude Code,
                    # recortada -- ver `_resumen_para_voz`), no solo un "listo" genérico; si no hubo
                    # salida de texto (tarea silenciosa, solo archivos tocados), cae al mensaje fijo.
                    resumen = _resumen_para_voz(valor)
                    notificar_voz("Listo. " + (resumen or "Claude Code ha terminado de ejecutar la orden."))
                    # Sin messagebox (encargo explícito, 2026-08-16): el estado "Completado" en la
                    # propia interfaz (punto verde + etiqueta) ya lo comunica, sin interrumpir con un
                    # pop-up modal de Windows que hay que cerrar a mano.
                    self._continuar_o_esperar(2500)
        except queue.Empty:
            pass
        self.root.after(120, self._drenar_cola)


def main():
    root = tk.Tk()
    JarvisApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
