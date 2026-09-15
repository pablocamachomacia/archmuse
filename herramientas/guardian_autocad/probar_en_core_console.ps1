# Comprueba el propio guardián en AutoCAD Core Console, sin AutoCAD con ventanas.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File herramientas\guardian_autocad\probar_en_core_console.ps1
#
# Dos pruebas, y hacen falta las dos:
#   1. Cambia FILEDIA entre las dos fotos: el guardián TIENE que decir que AutoCAD
#      no está como estaba, y nombrar FILEDIA. Si no lo dice, no vigila nada.
#   2. Nada entre las dos fotos: TIENE que decir que está exactamente como estaba.
#      Si no, da falsos avisos y nadie le hará caso.
#
# Core Console arranca siempre con FILEDIA en 0 y no lo guarda en el perfil
# (medido el 2026-09-15), así que la prueba 1 no cambia el AutoCAD del usuario.
# El registro no se prueba aquí: Core Console no tiene vlax-product-key.
#
# El guardián va incrustado en el .scr, no con (load): Core Console aplica
# SECURELOAD. La carpeta de trabajo es %TEMP%, nunca el repositorio: si algo sale
# mal, un QUIT desordenado puede acabar guardando un dibujo donde esté la consola.
param(
  [string]$Consola = "C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe",
  [int]$PlazoS = 300
)

$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$raiz = (Resolve-Path (Join-Path $aqui "..\..")).Path
$python = Join-Path $raiz "venv\Scripts\python.exe"
$trabajo = Join-Path $env:TEMP ("archmuse-guardian-prueba-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $trabajo | Out-Null
$scr = Join-Path $trabajo "prueba.scr"
$salida = Join-Path $trabajo "consola.txt"

$conversor = @'
import pathlib, sys
fuente = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
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
formas += ['(princ "\\n=== PRUEBA 1 ===")',
           "(c:ARCHMUSE-GUARDIAN)", '(setvar "FILEDIA" 1)', "(c:ARCHMUSE-GUARDIAN)",
           '(princ "\\n=== PRUEBA 2 ===")',
           "(c:ARCHMUSE-GUARDIAN)", "(c:ARCHMUSE-GUARDIAN)",
           '(princ "\\n=== FIN ===")', "_.QUIT", "_Y"]
pathlib.Path(sys.argv[2]).write_text("\r\n".join(formas) + "\r\n", encoding="cp1252")
'@
$conversor | & $python - (Join-Path $aqui "guardian.lsp") $scr
if (-not (Test-Path $scr)) { Write-Error "no se ha podido preparar el .scr"; exit 2 }

$p = Start-Process -FilePath $Consola -ArgumentList "/s `"$scr`"" -WorkingDirectory $trabajo `
                   -NoNewWindow -PassThru -RedirectStandardOutput $salida
if (-not $p.WaitForExit($PlazoS * 1000)) { $p.Kill(); Write-Error "Core Console no ha terminado en $PlazoS s"; exit 2 }

$bytes = [IO.File]::ReadAllBytes($salida)
$texto = [Text.Encoding]::Unicode.GetString($bytes) -replace "`0", ""
$lineas = $texto -split "`n" | ForEach-Object { $_.TrimEnd("`r") }

function Tramo($desde, $hasta) {
  $i = [Array]::IndexOf($lineas, ($lineas | Where-Object { $_ -like "*=== $desde ===*" } | Select-Object -First 1))
  $j = [Array]::IndexOf($lineas, ($lineas | Where-Object { $_ -like "*=== $hasta ===*" } | Select-Object -First 1))
  if ($i -lt 0 -or $j -lt 0) { return @() }
  return $lineas[$i..$j]
}

$uno = Tramo "PRUEBA 1" "PRUEBA 2"
$dos = Tramo "PRUEBA 2" "FIN"
$errores = @($lineas | Where-Object { $_ -match '; error' })

# Patrones SOLO en ASCII: PowerShell 5.1 lee un .ps1 sin BOM como ANSI, y un
# «está» escrito aquí no casaba con el «está» de la consola (medido).
$ok1 = [bool]($uno | Where-Object { $_ -match 'RESULTADO: AutoCAD NO ' }) -and
       [bool]($uno | Where-Object { $_ -match '^\s+FILEDIA: 0 -> 1' })
$ok2 = [bool]($dos | Where-Object { $_ -match 'RESULTADO: AutoCAD ' -and $_ -match 'exactamente como estaba' })

"--- prueba 1, FILEDIA cambiado:"
$uno | Where-Object { $_ -match 'RESULTADO|^\s+\w+: .* -> |Ignoradas' }
"--- prueba 2, sin cambios:"
$dos | Where-Object { $_ -match 'RESULTADO|^\s+\w+: .* -> |Ignoradas' }
if ($errores) { "--- errores de AutoLISP:"; $errores }
"--- salida completa: $salida"

if ($ok1 -and $ok2 -and -not $errores) { "GUARDIAN OK: caza el cambio y no da falsos avisos"; exit 0 }
"GUARDIAN FALLA: prueba 1 = $ok1, prueba 2 = $ok2, errores = $($errores.Count)"
exit 1
