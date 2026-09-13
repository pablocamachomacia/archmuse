; Instalador de la beta de ArchMuse (PRD 2026-09-11, T10).
;
; Lo compila empaquetado\construir.py, que antes deja listo empaquetado\salida\.
; A mano:  ISCC.exe /DVersion=0.3.1 empaquetado\ArchMuse-Beta.iss
;
; Condiciones del PRD que este fichero cumple y conviene no romper:
;   - por usuario y SIN administrador (PrivilegesRequired=lowest, todo en HKCU
;     y en carpetas del perfil);
;   - dos capas: runtime\ (A) y app\<version>\ (B), con app\actual como puntero;
;   - el servidor arranca al terminar la instalación, sin esperar a reiniciar.

#ifndef Version
  #error Falta /DVersion. Compílalo con empaquetado\construir.py
#endif
; La salida de construir.py vive FUERA del repositorio (..\_empaquetado\salida).
#ifndef Salida
  #error Falta /DSalida. Compílalo con empaquetado\construir.py
#endif

[Setup]
AppId={{6F3B2C1A-8D4E-4B7A-9C21-5E0F7A3D9B64}
AppName=ArchMuse Beta
AppVersion={#Version}
AppPublisher=ArchMuse
DefaultDirName={localappdata}\ArchMuse
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#Salida}
OutputBaseFilename=ArchMuse-Beta-{#Version}
Compression=lzma2/ultra64
SolidCompression=yes
ChangesAssociations=yes
CloseApplications=no
UninstallDisplayName=ArchMuse Beta
WizardStyle=modern
SetupLogging=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Messages]
es.FinishedHeadingLabel=ArchMuse está instalado
es.FinishedLabel=Listo. Abre AutoCAD, abre tu plano y teclea ARCHMUSE.
es.FinishedLabelNoIcons=Listo. Abre AutoCAD, abre tu plano y teclea ARCHMUSE.

[InstallDelete]
; Reinstalar la misma versión no deja restos de la copia anterior.
Type: filesandordirs; Name: "{app}\app\{#Version}"

[Files]
Source: "{#Salida}\runtime\*"; DestDir: "{app}\runtime"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#Salida}\app\{#Version}\*"; DestDir: "{app}\app\{#Version}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#Salida}\bundle\PackageContents.xml"; DestDir: "{userappdata}\Autodesk\ApplicationPlugins\ArchMuse.bundle"; Flags: ignoreversion

[Icons]
; D-1: el servidor arranca al iniciar sesión. Con un acceso directo en la
; carpeta Inicio del usuario y NO con una tarea programada: `schtasks /SC
; ONLOGON` sin elevar devuelve «Acceso denegado» (medido el 2026-09-13), y el
; PRD no admite pedir administrador. La semántica es la misma: por usuario, al
; iniciar sesión, sin privilegios.
Name: "{userstartup}\ArchMuse (servidor)"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\actual\lanzador.pyw"""; WorkingDir: "{app}\app\actual"
Name: "{userprograms}\ArchMuse\ArchMuse - volver a la versión anterior"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\actual\actualizador.pyw"" --volver"; WorkingDir: "{app}"
Name: "{userprograms}\ArchMuse\Desinstalar ArchMuse"; Filename: "{uninstallexe}"

[Registry]
; Doble clic en un .archmuse = instalar esa versión (D-2).
Root: HKCU; Subkey: "Software\Classes\.archmuse"; ValueType: string; ValueName: ""; ValueData: "ArchMuse.Actualizacion"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\ArchMuse.Actualizacion"; ValueType: string; ValueName: ""; ValueData: "Actualización de ArchMuse"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\ArchMuse.Actualizacion\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\runtime\pythonw.exe"" ""{app}\app\actual\actualizador.pyw"" --instalar ""%1"""

[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\{#Version}\actualizador.pyw"" --activar {#Version} --silencioso"; WorkingDir: "{app}"; StatusMsg: "Poniendo en marcha ArchMuse (unos segundos)..."; Flags: waituntilterminated

[UninstallRun]
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\actual\actualizador.pyw"" --desinstalar"; WorkingDir: "{app}"; Flags: waituntilterminated skipifdoesntexist; RunOnceId: "PararArchMuse"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\runtime"
Type: files; Name: "{app}\servidor.json"
Type: files; Name: "{app}\entorno.txt"
Type: files; Name: "{app}\informe.ps1"
Type: filesandordirs; Name: "{userappdata}\Autodesk\ApplicationPlugins\ArchMuse.bundle"
; registro\ se queda a propósito: es lo único que explica un fallo después de
; haber desinstalado.

[Code]
// §6: sin permisos en %LOCALAPPDATA% se dice ANTES de copiar nada.
function InitializeSetup(): Boolean;
var
  Prueba: String;
begin
  Result := True;
  Prueba := ExpandConstant('{localappdata}\ArchMuse-prueba-de-escritura.tmp');
  if not SaveStringToFile(Prueba, 'x', False) then
  begin
    MsgBox('ArchMuse no puede escribir en ' + ExpandConstant('{localappdata}') +
           '. Suele ser una política del ordenador. No se ha instalado nada.',
           mbError, MB_OK);
    Result := False;
  end
  else
    DeleteFile(Prueba);
end;

// §6: instalar sobre una instalación viva. Se para el servidor antes de copiar
// (si no, runtime\ está en uso y la copia falla a medias).
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
  Pythonw, Actualizador: String;
begin
  Result := '';
  Pythonw := ExpandConstant('{app}\runtime\pythonw.exe');
  Actualizador := ExpandConstant('{app}\app\actual\actualizador.pyw');
  if FileExists(Pythonw) and FileExists(Actualizador) then
    Exec(Pythonw, '"' + Actualizador + '" --parar', ExpandConstant('{app}'),
         SW_HIDE, ewWaitUntilTerminated, Codigo);
end;
