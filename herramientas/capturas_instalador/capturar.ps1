# Captura las tres pantallas del instalador de captura a una escala concreta. Ver generar_iss_captura.py.
#
#   .\capturar.ps1 -SoloLeer                           # dice la escala de cada monitor, no cambia nada
#   .\capturar.ps1 -Setup x.exe -Salida carpeta -Escala 150 -Monitor \\.\DISPLAY2
#
# Si la escala pedida no es la actual, la cambia SOLO en ese monitor, captura y la
# deja como estaba (también si algo falla por el camino).
param(
  [switch]$SoloLeer,
  [string]$Setup,
  [string]$Salida,
  [int]$Escala = 100,
  [string]$Monitor = "\\.\DISPLAY2",
  [string]$Titulo = "Instalar - ArchMuse"
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing, System.Windows.Forms
Add-Type -Path (Join-Path $PSScriptRoot "Pantalla.cs") -ReferencedAssemblies System.Drawing
[Pantalla]::SetProcessDpiAwarenessContext([IntPtr](-4)) | Out-Null   # per-monitor v2: píxeles físicos

function Porcentaje-De($gdi) {
  $pantalla = [System.Windows.Forms.Screen]::AllScreens | Where-Object { $_.DeviceName -eq $gdi }
  if (-not $pantalla) { throw "No existe el monitor $gdi" }
  Add-Type -Namespace W -Name M -MemberDefinition '[DllImport("user32.dll")] public static extern IntPtr MonitorFromPoint(System.Drawing.Point p, uint f); [DllImport("shcore.dll")] public static extern int GetDpiForMonitor(IntPtr h, int t, out uint x, out uint y);' -ReferencedAssemblies System.Drawing -ErrorAction SilentlyContinue
  $centro = New-Object System.Drawing.Point(($pantalla.Bounds.Left + $pantalla.Bounds.Width / 2), ($pantalla.Bounds.Top + $pantalla.Bounds.Height / 2))
  $x = 0; $y = 0
  [W.M]::GetDpiForMonitor([W.M]::MonitorFromPoint($centro, 2), 0, [ref]$x, [ref]$y) | Out-Null
  return [pscustomobject]@{ Porcentaje = [int][math]::Round($x / 0.96); Limites = $pantalla.Bounds }
}

if ($SoloLeer) {
  foreach ($p in [System.Windows.Forms.Screen]::AllScreens) {
    $m = Porcentaje-De $p.DeviceName
    $rel = [Pantalla]::LeerRelativa($p.DeviceName)
    "{0}: {1}%  (relativa a la recomendada: actual {2}, de {3} a {4})" -f $p.DeviceName, $m.Porcentaje, $rel[1], $rel[0], $rel[2]
  }
  exit 0
}

New-Item -ItemType Directory -Force $Salida | Out-Null
$antes = (Porcentaje-De $Monitor).Porcentaje
$proceso = $null
try {
  if ($antes -ne $Escala) {
    [Pantalla]::PonerEscala($Monitor, $antes, $Escala)
    Start-Sleep -Seconds 3
    $ahora = (Porcentaje-De $Monitor).Porcentaje
    if ($ahora -ne $Escala) { throw "Pedí $Escala % en $Monitor y está a $ahora %" }
  }
  $limites = (Porcentaje-De $Monitor).Limites
  [Pantalla]::SetCursorPos($limites.Left + $limites.Width / 2, $limites.Top + $limites.Height / 2) | Out-Null
  $proceso = Start-Process -FilePath $Setup -PassThru

  $v = [IntPtr]::Zero
  for ($i = 0; $i -lt 60 -and $v -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 500; $v = [Pantalla]::VentanaQueEmpieza($Titulo) }
  if ($v -eq [IntPtr]::Zero) { throw "No aparece la ventana del instalador" }

  # En el monitor pedido: si Windows la abre en otro, se mueve, y se comprueba que
  # el instalador se ha redibujado a la escala de ese monitor.
  $esperado = [int]($Escala * 0.96)
  if ([Pantalla]::GetDpiForWindow($v) -ne $esperado) {
    [Pantalla]::SetWindowPos($v, [IntPtr]::Zero, $limites.Left + 40, $limites.Top + 40, 0, 0, 0x0001 -bor 0x0004) | Out-Null
    Start-Sleep -Seconds 2
  }
  $dpi = [Pantalla]::GetDpiForWindow($v)
  if ($dpi -ne $esperado) { throw "La ventana está a $dpi dpi y debería estar a $esperado" }
  $marco = [Pantalla]::Marco($v)
  "ventana: {0}x{1} px a {2} dpi" -f ($marco.r - $marco.l), ($marco.b - $marco.t), $dpi

  # 1. Rutas de confianza
  Start-Sleep -Seconds 1
  [Pantalla]::Capturar($v, (Join-Path $Salida "1-rutas-de-confianza-$Escala.png"))
  $boton = [Pantalla]::Hijo($v, "&Instalar")
  if ($boton -eq [IntPtr]::Zero) { throw "No encuentro el botón Instalar. Textos: " + ([Pantalla]::Textos($v) -join " | ") }
  [Pantalla]::Pulsar($boton)

  # 2. Poniendo en marcha. Se espera a lo que llegue antes: esta pantalla o la
  # final. Antes se daba un plazo fijo y se fallaba: en la VM (2026-09-15) copiar
  # los ficheros tardó más que el plazo, o la activación pasó entre dos miradas.
  # Ahora se mira cada 100 ms y se captura en cuanto aparece; si la activación
  # termina antes de verla, se dice y se sigue con la final.
  $h = [IntPtr]::Zero; $fin = [IntPtr]::Zero
  $limite = (Get-Date).AddMinutes(10)   # copiar + activar; el instalador se rinde a los 270 s
  while ((Get-Date) -lt $limite -and $h -eq [IntPtr]::Zero -and $fin -eq [IntPtr]::Zero) {
    Start-Sleep -Milliseconds 100
    $h = [Pantalla]::Hijo($v, "Poniendo en marcha")
    if ($h -eq [IntPtr]::Zero) { $fin = [Pantalla]::Hijo($v, "&Finalizar") }
  }
  if ($h -ne [IntPtr]::Zero) {
    [Pantalla]::Capturar($v, (Join-Path $Salida "2-poniendo-en-marcha-$Escala.png"))
    "capturada «Poniendo en marcha»"
  } elseif ($fin -ne [IntPtr]::Zero) {
    "AVISO: la activación terminó antes de poder ver «Poniendo en marcha»; no hay captura de esa pantalla a $Escala %"
  } else {
    throw "En 10 minutos no aparece ni «Poniendo en marcha» ni la pantalla final. Textos: " + ([Pantalla]::Textos($v) -join " | ")
  }

  # 3. Final
  while ((Get-Date) -lt $limite -and $fin -eq [IntPtr]::Zero) { Start-Sleep -Milliseconds 250; $fin = [Pantalla]::Hijo($v, "&Finalizar") }
  if ($fin -eq [IntPtr]::Zero) { throw "No aparece la pantalla final. Textos: " + ([Pantalla]::Textos($v) -join " | ") }
  Start-Sleep -Seconds 1
  [Pantalla]::Capturar($v, (Join-Path $Salida "3-instalado-$Escala.png"))
  [Pantalla]::Pulsar($fin)
  "capturas en $Salida"
}
finally {
  if ($proceso -and -not $proceso.HasExited) { Start-Sleep -Seconds 2; if (-not $proceso.HasExited) { $proceso | Stop-Process -Force } }
  if ((Porcentaje-De $Monitor).Porcentaje -ne $antes) {
    [Pantalla]::PonerEscala($Monitor, (Porcentaje-De $Monitor).Porcentaje, $antes)
    Start-Sleep -Seconds 2
    "escala de $Monitor devuelta a $((Porcentaje-De $Monitor).Porcentaje) %"
  }
}
