# Comprueba el propio guardián en AutoCAD Core Console, sin AutoCAD con ventanas.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File herramientas\guardian_autocad\probar_en_core_console.ps1
#
# Cuatro pruebas, y hacen falta todas:
#   1. Cambia FILEDIA entre las dos fotos, en la misma sesión: el guardián TIENE que
#      decir que AutoCAD no está como estaba, y nombrar FILEDIA.
#   2. Nada entre las dos fotos: TIENE que decir que está exactamente como estaba.
#   3. Foto en una sesión de Core Console, FILEDIA cambiado en OTRA (como cerrar y
#      abrir AutoCAD, o instalar con ARCHMUSE-ACTUALIZAR): tiene que compararlo con la
#      foto guardada y nombrar FILEDIA.
#   4. Foto en una sesión y nada en la siguiente: exactamente como estaba.
# Las pruebas 1 y 3 rompen a propósito lo que vigila; si no saltan, no vigila nada.
#
# **Core Console se lanza SOLO por herramientas/core_console.py** (2026-09-16):
# escribe FileDialog = 0 en el perfil de AutoCAD del usuario al arrancar y sólo lo
# devuelve si sale limpio. Lanzado a mano y matado, dejó FILEDIA a 0. La puerta lo
# aísla (/isolate) y devuelve lo que cambie.
#
# El registro no se prueba aquí: Core Console no tiene vlax-product-key. El guardián
# va incrustado en el .scr, no con (load): Core Console aplica SECURELOAD. TEMP
# apunta a la carpeta de trabajo, para no pisar la foto guardada de una pasada de
# verdad en %TEMP%.
param(
  [string]$Consola = "",
  [int]$PlazoS = 300
)

$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$raiz = (Resolve-Path (Join-Path $aqui "..\..")).Path
$python = Join-Path $raiz "venv\Scripts\python.exe"
$trabajo = Join-Path $env:TEMP ("archmuse-guardian-prueba-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $trabajo | Out-Null

$conversor = @'
import pathlib, sys
fuente = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
destino = pathlib.Path(sys.argv[2])
formas, actual, prof = [], [], 0
for linea in fuente.splitlines():
    s = linea.strip()
    if s.startswith(";") or not s:
        if actual and not s:
            raise SystemExit("línea en blanco dentro de una forma")
        continue
    if ";" in linea:
        raise SystemExit("punto y coma dentro de código: " + linea)
    actual.append(s)
    prof += linea.count("(") - linea.count(")")
    if prof == 0:
        formas.append(" ".join(actual))
        actual = []
if prof or actual:
    raise SystemExit("paréntesis desparejados")
formas = [f for f in formas if f != "(vl-load-com)"]
fin = ["_.QUIT", "_Y"]
guiones = {
    "misma_sesion.scr": formas + ['(princ "\\n=== PRUEBA 1 ===")',
                                  "(c:ARCHMUSE-GUARDIAN)", '(setvar "FILEDIA" 1)', "(c:ARCHMUSE-GUARDIAN)",
                                  '(princ "\\n=== PRUEBA 2 ===")',
                                  "(c:ARCHMUSE-GUARDIAN)", "(c:ARCHMUSE-GUARDIAN)",
                                  '(princ "\\n=== FIN ===")'] + fin,
    "foto.scr": formas + ['(princ "\\n=== FOTO ===")', "(c:ARCHMUSE-GUARDIAN)", '(princ "\\n=== FIN ===")'] + fin,
    "otra_sesion_cambio.scr": formas + ['(princ "\\n=== PRUEBA 3 ===")', '(setvar "FILEDIA" 1)',
                                        "(c:ARCHMUSE-GUARDIAN)", '(princ "\\n=== FIN ===")'] + fin,
    "otra_sesion_igual.scr": formas + ['(princ "\\n=== PRUEBA 4 ===")',
                                       "(c:ARCHMUSE-GUARDIAN)", '(princ "\\n=== FIN ===")'] + fin,
}
for nombre, lineas in guiones.items():
    (destino / nombre).write_text("\r\n".join(lineas) + "\r\n", encoding="cp1252")
'@
$conversor | & $python - (Join-Path $aqui "guardian.lsp") $trabajo
if (-not (Test-Path (Join-Path $trabajo "foto.scr"))) { Write-Error "no se han podido preparar los .scr"; exit 2 }

# El guardián de Core Console escribe su foto en TEMP: la de la prueba va aquí.
$env:TEMP = $trabajo
$env:TMP = $trabajo

function Consola($guion) {
  $salida = Join-Path $trabajo ($guion + ".txt")
  # La misma carpeta aislada en todas las sesiones: con una nueva cada vez, las rutas
  # de AutoCAD (TEMPPREFIX, SAVEFILEPATH...) cambiarían y la prueba 4 daría falsos avisos.
  $opciones = @("-m", "herramientas.core_console", "--script", (Join-Path $trabajo $guion),
                "--salida", $salida, "--plazo", $PlazoS, "--carpeta", $trabajo,
                "--aislada", (Join-Path $trabajo "aislada"))
  if ($Consola) { $opciones += @("--consola", $Consola) }
  Push-Location $raiz
  try { $aviso = & $python @opciones } finally { Pop-Location }
  if ($LASTEXITCODE -ne 0) { Write-Error "Core Console: $aviso"; exit 2 }
  if ($aviso) { $aviso }
  $texto = [Text.Encoding]::Unicode.GetString([IO.File]::ReadAllBytes($salida)) -replace "`0", ""
  return ,($texto -split "`n" | ForEach-Object { $_.TrimEnd("`r") })
}

function Tramo($lineas, $desde, $hasta) {
  $i = [Array]::IndexOf($lineas, ($lineas | Where-Object { $_ -like "*=== $desde ===*" } | Select-Object -First 1))
  $j = [Array]::IndexOf($lineas, ($lineas | Where-Object { $_ -like "*=== $hasta ===*" } | Select-Object -First 1))
  if ($i -lt 0 -or $j -lt 0) { return @() }
  return $lineas[$i..$j]
}

$misma = Consola "misma_sesion.scr"
$null = Consola "foto.scr"
$tres = Tramo (Consola "otra_sesion_cambio.scr") "PRUEBA 3" "FIN"
$null = Consola "foto.scr"
$cuatro = Tramo (Consola "otra_sesion_igual.scr") "PRUEBA 4" "FIN"
$uno = Tramo $misma "PRUEBA 1" "PRUEBA 2"
$dos = Tramo $misma "PRUEBA 2" "FIN"
$errores = @(@($misma) + @($tres) + @($cuatro) | Where-Object { $_ -match '; error' })

# Patrones SOLO en ASCII: PowerShell 5.1 lee un .ps1 sin BOM como ANSI, y un
# «está» escrito aquí no casaba con el «está» de la consola (medido).
function Caza($tramo) {
  [bool]($tramo | Where-Object { $_ -match 'RESULTADO: AutoCAD NO ' }) -and
  [bool]($tramo | Where-Object { $_ -match '^\s+FILEDIA: 0 -> 1' })
}
function Limpio($tramo) {
  [bool]($tramo | Where-Object { $_ -match 'RESULTADO: AutoCAD ' -and $_ -match 'exactamente como estaba' })
}
$ok1 = Caza $uno
$ok2 = Limpio $dos
$ok3 = (Caza $tres) -and [bool]($tres | Where-Object { $_ -match 'foto guardada' })
$ok4 = (Limpio $cuatro) -and [bool]($cuatro | Where-Object { $_ -match 'foto guardada' })

foreach ($p in @(@("prueba 1, FILEDIA cambiado en la misma sesion", $uno), @("prueba 2, sin cambios", $dos),
                 @("prueba 3, FILEDIA cambiado en otra sesion", $tres), @("prueba 4, otra sesion sin cambios", $cuatro))) {
  "--- $($p[0]):"
  $p[1] | Where-Object { $_ -match 'RESULTADO|foto guardada|^\s+\w+: .* -> |Ignoradas' }
}
if ($errores) { "--- errores de AutoLISP:"; $errores }
"--- salidas completas: $trabajo"

if ($ok1 -and $ok2 -and $ok3 -and $ok4 -and -not $errores) {
  "GUARDIAN OK: caza el cambio en la sesion y entre sesiones, y no da falsos avisos"; exit 0
}
"GUARDIAN FALLA: prueba 1 = $ok1, prueba 2 = $ok2, prueba 3 = $ok3, prueba 4 = $ok4, errores = $($errores.Count)"
exit 1
