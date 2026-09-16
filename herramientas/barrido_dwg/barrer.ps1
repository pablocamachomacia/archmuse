# Barrido de solo lectura de DWG con AutoCAD Core Console. Ver LEEME.md.
#
# Core Console se lanza SOLO por herramientas/core_console.py (2026-09-16): escribe
# FileDialog = 0 en el perfil de AutoCAD del usuario al arrancar y sólo lo devuelve
# si sale limpio. Un barrido que mata una consola colgada por el plazo dejaba
# FILEDIA a 0. La puerta la aísla (/isolate) y devuelve lo que cambie.
param(
  [Parameter(Mandatory = $true)] [string]$Copias,
  [Parameter(Mandatory = $true)] [string]$Sonda,
  [Parameter(Mandatory = $true)] [string]$Funcion,
  [Parameter(Mandatory = $true)] [string]$Salida,
  [switch]$UnoPorHuella,
  [int]$PlazoS = 240,
  [string]$Consola = ""
)

# La salida lleva rutas de planos de clientes y el repositorio es público.
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path.TrimEnd('\')
$salidaAbs = [System.IO.Path]::GetFullPath($Salida)
if ($salidaAbs.StartsWith($repo + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
  Write-Error "La salida tiene que quedar FUERA del repositorio ($repo): lleva rutas de planos de clientes."
  exit 1
}
$python = Join-Path $repo "venv\Scripts\python.exe"

$scr = Join-Path $env:TEMP "archmuse-sonda.scr"
& $python (Join-Path $PSScriptRoot "incrustar.py") $Sonda $Funcion $salidaAbs $scr
if (-not $?) { exit 1 }

$huellas = "$salidaAbs.huellas.tsv"
Remove-Item $salidaAbs, $huellas -ErrorAction SilentlyContinue
$vistos = @{}
$ficheros = Get-ChildItem $Copias -Recurse -Filter *.dwg -File | Sort-Object FullName
$n = 0
foreach ($f in $ficheros) {
  $n++
  $hash = (Get-FileHash -LiteralPath $f.FullName -Algorithm MD5).Hash
  if ($UnoPorHuella -and $vistos.ContainsKey($hash)) {
    Add-Content $huellas "$($f.FullName)`t$hash`tCOPIA" -Encoding utf8
    continue
  }
  $vistos[$hash] = $true
  $antes = if (Test-Path $salidaAbs) { (Get-Content $salidaAbs).Count } else { 0 }
  $opciones = @("-m", "herramientas.core_console", "--script", $scr, "--dibujo", $f.FullName,
                "--solo-lectura", "--plazo", $PlazoS, "--carpeta", $env:TEMP,
                "--salida", (Join-Path $env:TEMP "archmuse-sonda.log"))
  if ($Consola) { $opciones += @("--consola", $Consola) }
  Push-Location $repo
  try { $aviso = & $python @opciones; $codigo = $LASTEXITCODE } finally { Pop-Location }
  $aviso | Where-Object { $_ -match 'DEVUELTO' } | ForEach-Object { Write-Warning $_ }
  $estado = switch ($codigo) { 0 { "ok" } 2 { "TIMEOUT" } default { "ERROR" } }
  $despues = if (Test-Path $salidaAbs) { (Get-Content $salidaAbs).Count } else { 0 }
  if ($estado -eq "ok" -and $despues -eq $antes) { $estado = "SIN_LINEA" }
  Add-Content $huellas "$($f.FullName)`t$hash`t$estado" -Encoding utf8
  Write-Output "$n/$($ficheros.Count) $estado $($f.Name)"
}
Write-Output "FIN"
