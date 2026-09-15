# Dentro de la máquina virtual: captura las tres pantallas de CADA instalador de la carpeta compartida,
# al 100 % y al 150 %.
#
#   powershell -ExecutionPolicy Bypass -File \\VBOXSVR\capturas\capturar_en_vm.ps1
#
# Copia la carpeta compartida a C:\capturas (un .exe lanzado desde la red pide
# confirmación y para la captura), captura cada instalador y cada escala en un
# PowerShell aparte (Add-Type no deja cargar dos veces la misma clase) y devuelve
# las capturas a la carpeta compartida, una subcarpeta por instalador, aunque
# algo falle por el camino. La escala de la VM queda como estaba.
param([string]$Compartida = "\\VBOXSVR\capturas")
$ErrorActionPreference = "Stop"
$local = "C:\capturas"
if (Test-Path $local) { Remove-Item $local -Recurse -Force }
Copy-Item $Compartida $local -Recurse
if (Test-Path "$local\pantallas-vm") { Remove-Item "$local\pantallas-vm" -Recurse -Force }
$instaladores = Get-ChildItem $local -Filter "*.exe" | Sort-Object Name
if (-not $instaladores) { throw "No hay ningún instalador (.exe) en $Compartida" }

$fallos = @()
try {
  foreach ($setup in $instaladores) {
    foreach ($escala in 100, 150) {
      "--- $($setup.BaseName) al $escala %"
      & powershell -NoProfile -ExecutionPolicy Bypass -File "$local\capturar.ps1" -Setup $setup.FullName `
          -Salida "$local\pantallas\$($setup.BaseName)" -Escala $escala -Monitor "\\.\DISPLAY1"
      if ($LASTEXITCODE -ne 0) { $fallos += "$($setup.BaseName) al $escala %" }
    }
  }
}
finally {
  # Lo que se haya capturado vuelve aunque algo falle: una captura parcial también sirve.
  if (Test-Path "$local\pantallas") { Copy-Item "$local\pantallas" "$Compartida\pantallas-vm" -Recurse -Force }
}
if ($fallos) { "Han fallado: $($fallos -join ', '). Lo capturado está en $Compartida\pantallas-vm" ; exit 1 }
"Listo: capturas en $Compartida\pantallas-vm"
