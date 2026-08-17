@echo off
rem Lanzador de escritorio para JarvisApp.py.
rem Copia o crea un acceso directo a este .bat en el escritorio para abrir
rem Jarvis con un doble clic, sin tocar la terminal.
setlocal
cd /d "%~dp0"

rem Usa el entorno virtual dedicado (.venv-jarvis, Python 3.12) si existe --
rem ahi estan instaladas las dependencias de requirements-jarvis.txt,
rem incluida pyaudio (que no tiene wheel precompilada para Python 3.14).
if exist "%~dp0.venv-jarvis\Scripts\pythonw.exe" (
    start "" "%~dp0.venv-jarvis\Scripts\pythonw.exe" "JarvisApp.py"
    goto :fin
)

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "JarvisApp.py"
) else (
    start "" python "JarvisApp.py"
)
:fin
endlocal
