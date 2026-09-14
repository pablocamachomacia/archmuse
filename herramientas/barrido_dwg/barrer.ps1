# Barrido de solo lectura de DWG con AutoCAD Core Console. Ver LEEME.md.
param(
  [Parameter(Mandatory = $true)] [string]$Copias,
  [Parameter(Mandatory = $true)] [string]$Sonda,
  [Parameter(Mandatory = $true)] [string]$Funcion,
  [Parameter(Mandatory = $true)] [string]$Salida,
  [switch]$UnoPorHuella,
  [int]$PlazoS = 240,
  [string]$Consola = "C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe"
)

# La salida lleva rutas de planos de clientes y el repositorio es público.
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path.TrimEnd('\')
$salidaAbs = [System.IO.Path]::GetFullPath($Salida)
if ($salidaAbs.StartsWith($repo + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
  Write-Error "La salida tiene que quedar FUERA del repositorio ($repo): lleva rutas de planos de clientes."
  exit 1
}

$scr = Join-Path $env:TEMP "archmuse-sonda.scr"
python (Join-Path $PSScriptRoot "incrustar.py") $Sonda $Funcion $salidaAbs $scr
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
  $p = Start-Process -FilePath $Consola -ArgumentList "/i `"$($f.FullName)`" /s `"$scr`" /readonly" `
                     -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $env:TEMP "archmuse-sonda.log")
  $estado = "ok"
  if (-not $p.WaitForExit($PlazoS * 1000)) { try { $p.Kill() } catch {}; $estado = "TIMEOUT" }
  $despues = if (Test-Path $salidaAbs) { (Get-Content $salidaAbs).Count } else { 0 }
  if ($estado -eq "ok" -and $despues -eq $antes) { $estado = "SIN_LINEA" }
  Add-Content $huellas "$($f.FullName)`t$hash`t$estado" -Encoding utf8
  Write-Output "$n/$($ficheros.Count) $estado $($f.Name)"
}
Write-Output "FIN"
