; Instalador de la beta de ArchMuse (PRD 2026-09-11, T10).
;
; Lo compila empaquetado\construir.py, que antes deja listo empaquetado\salida\.
; A mano:  ISCC.exe /DVersion=0.3.8 /DSalida=..\_empaquetado\salida empaquetado\ArchMuse-Beta.iss
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
; Datos del editor: salen en Propiedades del .exe y en «Aplicaciones instaladas».
; Sin nombre personal ni email, porque el instalador se reparte (Pablo, 2026-09-15).
AppPublisherURL=https://github.com/pablocamachomacia/archmuse
AppSupportURL=https://github.com/pablocamachomacia/archmuse/issues
AppCopyright=© 2026 ArchMuse
VersionInfoVersion={#Version}
VersionInfoProductVersion={#Version}
VersionInfoCompany=ArchMuse
VersionInfoProductName=ArchMuse Beta
VersionInfoDescription=Instalador de ArchMuse Beta
VersionInfoCopyright=© 2026 ArchMuse
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
; El símbolo de ArchMuse (empaquetado\marca, lo genera generar_marca.py). El icono
; lo llevan el .exe, el desinstalador y «Aplicaciones instaladas». Las imágenes van
; en las siete escalas de Inno Setup (100 % a 250 %): elige la que mejor encaja.
SetupIconFile=marca\archmuse.ico
UninstallDisplayIcon={app}\archmuse.ico
WizardSmallImageFile=marca\cabecera-58.png,marca\cabecera-77.png,marca\cabecera-97.png,marca\cabecera-116.png,marca\cabecera-124.png,marca\cabecera-143.png,marca\cabecera-159.png
WizardImageFile=marca\lateral-202.png,marca\lateral-269.png,marca\lateral-336.png,marca\lateral-403.png,marca\lateral-430.png,marca\lateral-498.png,marca\lateral-534.png
SetupLogging=yes
; RedirectionGuard se queda activado (Inno Setup lo activa por defecto desde la
; 6.7.0): prohíbe atravesar uniones creadas sin administrador, también a los
; procesos que lanza el instalador. ArchMuse ya no usa ninguna: desde el
; 2026-09-14 la versión activa es app\actual.txt y todo entra por lanzar.pyw.

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
; El punto de entrada fijo: lee app\actual.txt y ejecuta la versión activa. Del
; repositorio y no de la capa B: tiene que valer con cualquier versión.
Source: "lanzar.pyw"; DestDir: "{app}"; Flags: ignoreversion
; El símbolo, para los accesos directos y los .archmuse. En {app} y no en la capa
; B: tiene que seguir ahí aunque se cambie de versión.
Source: "marca\archmuse.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; D-1: el servidor arranca al iniciar sesión. Con un acceso directo en la
; carpeta Inicio del usuario y NO con una tarea programada: `schtasks /SC
; ONLOGON` sin elevar devuelve «Acceso denegado» (medido el 2026-09-13), y el
; PRD no admite pedir administrador. La semántica es la misma: por usuario, al
; iniciar sesión, sin privilegios.
; IconFilename en los que apuntan a pythonw.exe: sin él salían con el icono de Python.
Name: "{userstartup}\ArchMuse (servidor)"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\lanzar.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\archmuse.ico"
Name: "{userprograms}\ArchMuse\ArchMuse - volver a la versión anterior"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\lanzar.pyw"" actualizador --volver"; WorkingDir: "{app}"; IconFilename: "{app}\archmuse.ico"
Name: "{userprograms}\ArchMuse\Desinstalar ArchMuse"; Filename: "{uninstallexe}"

[Registry]
; Doble clic en un .archmuse = instalar esa versión (D-2).
Root: HKCU; Subkey: "Software\Classes\.archmuse"; ValueType: string; ValueName: ""; ValueData: "ArchMuse.Actualizacion"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\ArchMuse.Actualizacion"; ValueType: string; ValueName: ""; ValueData: "Actualización de ArchMuse"; Flags: uninsdeletekey
; Sin DefaultIcon, Windows enseñaba los .archmuse como una hoja en blanco. Se
; borra con la clave de arriba (uninsdeletekey).
Root: HKCU; Subkey: "Software\Classes\ArchMuse.Actualizacion\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\archmuse.ico,0"
Root: HKCU; Subkey: "Software\Classes\ArchMuse.Actualizacion\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\runtime\pythonw.exe"" ""{app}\lanzar.pyw"" actualizador --instalar ""%1"""

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
#include "esperar_actualizador.iss"

// Cuánto espera el instalador a cada orden del actualizador: algo más que el
// tope duro del propio actualizador (`LIMITES_S` en actualizador.pyw; un test
// compara las cifras). Pasado esto, se rinde y lo dice.
const
  LIMITE_ACTIVAR_S = 270;
  LIMITE_BREVE_S = 90;

var
  ActivacionFallida: Boolean;
  MensajeActivacion: String;
  ConfianzaPagina: TOutputMsgWizardPage;

// TRUSTEDPATHS no se escribe nunca con AutoCAD abierto (enmienda del PRD): puede
// reescribir sus variables al cerrarse. Instalar y desinstalar esperan a que se
// cierre. SuppressibleMsgBox con Cancelar por defecto: en modo silencioso no se
// queda dando vueltas, se cancela.
function AutoCADAbierto(): Boolean;
var
  Localizador, Servicio, Procesos: Variant;
begin
  Localizador := CreateOleObject('WbemScripting.SWbemLocator');
  Servicio := Localizador.ConnectServer('.', 'root\CIMV2');
  Procesos := Servicio.ExecQuery('SELECT ProcessId FROM Win32_Process WHERE Name = ''acad.exe''');
  Result := Procesos.Count > 0;
end;

function EsperarAutoCADCerrado(): Boolean;
begin
  Result := True;
  try
    while AutoCADAbierto() do
      if SuppressibleMsgBox('AutoCAD está abierto. Guarda tu trabajo, cierra AutoCAD y pulsa Reintentar.',
                            mbError, MB_RETRYCANCEL, IDCANCEL) = IDCANCEL then
      begin
        Result := False;
        Exit;
      end;
  except
    // Sin WMI no se sabe si está abierto: se pregunta, no se supone.
    Result := SuppressibleMsgBox('No he podido comprobar si AutoCAD está abierto. ' +
                                 'Asegúrate de que está cerrado y pulsa Sí para seguir.',
                                 mbConfirmation, MB_YESNO, IDNO) = IDYES;
  end;
end;

// Parar ArchMuse desde aquí, sin depender de Python ni de servidor.json (VM
// limpia, 2026-09-14: el instalador creía haber parado el servidor y la copia
// chocó con su libcrypto-3.dll). Todo proceso cuyo ejecutable esté en
// {app}\runtime\ es de ArchMuse: es nuestro Python y no lo usa nadie más.
const
  LIMITE_PARADA_S = 20;

// Una línea en registro\servidor-AAAA-MM.log, con el formato de las que escribe
// Python («AAAA-MM-DD HH:MM:SS | texto») y en UTF-8 sin marca, como ellas. Nunca
// interrumpe la instalación. Existe desde el 2026-09-14: la parada del
// instalador no dejaba rastro, y cuando falle en el ordenador de un arquitecto
// esta línea será lo único que haya.
procedure RegistrarEnArchMuse(Texto: String);
var
  Carpeta: String;
  Linea: TArrayOfString;
begin
  try
    Carpeta := ExpandConstant('{app}\registro');
    ForceDirectories(Carpeta);
    SetArrayLength(Linea, 1);
    Linea[0] := GetDateTimeString('yyyy/mm/dd hh:nn:ss', '-', ':') + ' | instalador: ' + Texto;
    SaveStringsToUTF8FileWithoutBOM(Carpeta + '\servidor-' + GetDateTimeString('yyyy/mm', '-', ':') + '.log', Linea, True);
  except
  end;
end;

function ProcesosDelRuntime(Terminar: Boolean; var Descripcion: String): Integer;
var
  Localizador, Servicio, Procesos, Proceso: Variant;
  Runtime, Ruta: String;
  I, Codigo: Integer;
begin
  Result := 0;
  Descripcion := '';
  Runtime := Lowercase(AddBackslash(ExpandConstant('{app}\runtime')));
  Localizador := CreateOleObject('WbemScripting.SWbemLocator');
  Servicio := Localizador.ConnectServer('.', 'root\CIMV2');
  Procesos := Servicio.ExecQuery('SELECT ProcessId, ExecutablePath FROM Win32_Process ' +
                                 'WHERE Name = ''python.exe'' OR Name = ''pythonw.exe''');
  for I := 0 to Procesos.Count - 1 do
  begin
    Proceso := Procesos.ItemIndex(I);
    if not VarIsNull(Proceso.ExecutablePath) then
    begin
      Ruta := Proceso.ExecutablePath;
      if Pos(Runtime, Lowercase(Ruta)) = 1 then
      begin
        Result := Result + 1;
        Descripcion := Descripcion + #13#10 + '  pid ' + IntToStr(Proceso.ProcessId) + ': ' + Ruta;
        if Terminar then
        begin
          // Win32_Process.Terminate contesta 0 si lo ha terminado; 2, acceso
          // denegado; 3, privilegios insuficientes; 8, error desconocido.
          Codigo := Proceso.Terminate();
          RegistrarEnArchMuse('terminado el pid ' + IntToStr(Proceso.ProcessId) + ' (' + Ruta +
                              '): Windows contesta ' + IntToStr(Codigo));
        end;
      end;
    end;
  end;
end;

function PararArchMuse(var Mensaje: String): Boolean;
var
  Inicio, Transcurridos: DWORD;
  Descripcion, EnUnaLinea: String;
begin
  Mensaje := '';
  Result := False;
  try
    repeat
      if ProcesosDelRuntime(True, Descripcion) = 0 then
      begin
        Result := True;
        Exit;
      end;
      Inicio := GetTickCount;
      Transcurridos := 0;
      while (Transcurridos < LIMITE_PARADA_S) and (ProcesosDelRuntime(False, Descripcion) > 0) do
      begin
        Sleep(500);
        Transcurridos := (GetTickCount - Inicio) div 1000;
      end;
      if ProcesosDelRuntime(False, Descripcion) = 0 then
      begin
        RegistrarEnArchMuse('parada: no queda nada de ArchMuse en marcha');
        Result := True;
        Exit;
      end;
      EnUnaLinea := Descripcion;
      StringChangeEx(EnUnaLinea, #13#10, ';', True);
      RegistrarEnArchMuse('parada: tras ' + IntToStr(LIMITE_PARADA_S) + ' s sigue en marcha' + EnUnaLinea);
    until SuppressibleMsgBox('ArchMuse está en marcha y no se deja parar:' + Descripcion + #13#10#13#10 +
                             'Pulsa Reintentar. Si sigue igual, cierra la sesión de Windows, vuelve a entrar y ' +
                             'ejecuta otra vez el instalador.', mbError, MB_RETRYCANCEL, IDCANCEL) = IDCANCEL;
    RegistrarEnArchMuse('parada: cancelada con ArchMuse todavía en marcha');
    Mensaje := 'ArchMuse está en marcha y no se deja parar:' + Descripcion;
  except
    RegistrarEnArchMuse('parada: no se han podido consultar los procesos: ' + GetExceptionMessage);
    Result := SuppressibleMsgBox('No he podido comprobar si ArchMuse está en marcha. Si lo está, ' +
                                 'la copia de ficheros puede fallar. ¿Seguir?',
                                 mbConfirmation, MB_YESNO, IDNO) = IDYES;
    if not Result then
      Mensaje := 'No se ha podido comprobar si ArchMuse está en marcha.';
  end;
end;

// El actualizador de una versión instalada, SIN pasar por uniones: primero el de
// app\actual.txt; si no lo hay (instalación anterior al 2026-09-14, con la unión
// app\actual), el de cualquier carpeta de versión real. Todos saben desinstalar.
function ActualizadorInstalado(): String;
var
  Leido: AnsiString;
  Version: String;
  Busqueda: TFindRec;
begin
  Result := '';
  if LoadStringFromFile(ExpandConstant('{app}\app\actual.txt'), Leido) then
  begin
    Version := Trim(String(Leido));
    if FileExists(ExpandConstant('{app}\app\') + Version + '\actualizador.pyw') then
    begin
      Result := ExpandConstant('{app}\app\') + Version + '\actualizador.pyw';
      Exit;
    end;
  end;
  if FindFirst(ExpandConstant('{app}\app\*'), Busqueda) then
  try
    repeat
      // $10: carpeta; $400: punto de reparación (la unión antigua), que no se toca.
      if ((Busqueda.Attributes and $10) <> 0) and ((Busqueda.Attributes and $400) = 0) and
         (Busqueda.Name <> '.') and (Busqueda.Name <> '..') and
         FileExists(ExpandConstant('{app}\app\') + Busqueda.Name + '\actualizador.pyw') then
        Result := ExpandConstant('{app}\app\') + Busqueda.Name + '\actualizador.pyw';
    until not FindNext(Busqueda);
  finally
    FindClose(Busqueda);
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := EsperarAutoCADCerrado();
end;

// Condición 1 de Pablo (enmienda del PRD, 2026-09-14): ANTES de instalar, y no
// en letra pequeña, que ArchMuse añade su carpeta a las rutas de confianza de
// AutoCAD, qué significa y que se deshace al desinstalar. Página propia, y el
// botón que la cierra es el que instala.
procedure InitializeWizard();
begin
  // Medido el 2026-09-14 con capturas del asistente, dos fallos distintos: la
  // ruta entera en una línea salía cortada por la derecha (por eso va partida),
  // y con la letra a 11 pt el texto se cortaba por abajo (ver MsgLabel.Height,
  // más abajo). Si este texto crece, hay que volver a mirarlo en pantalla.
  ConfianzaPagina := CreateOutputMsgPage(wpWelcome,
    'Antes de instalar: un cambio en tu AutoCAD',
    'Léelo antes de seguir. Es un ajuste de seguridad de AutoCAD.',
    'Para que ARCHMUSE funcione sin que AutoCAD pregunte cada vez, ArchMuse añade ' +
    'su carpeta a las RUTAS DE CONFIANZA de AutoCAD.' + #13#10#13#10 +
    'Qué significa: AutoCAD cargará sin preguntar lo que haya en esa carpeta, y sólo en esa:' + #13#10 +
    ExpandConstant('{userappdata}\Autodesk\') + #13#10 +
    'ApplicationPlugins\ArchMuse.bundle\Contents' + #13#10#13#10 +
    'Tus otras rutas de confianza no se tocan. Se deshace al desinstalar ArchMuse.' + #13#10#13#10 +
    'AutoCAD tiene que estar cerrado para instalar y para desinstalar.' + #13#10#13#10 +
    'Si creas otro perfil de AutoCAD, ArchMuse le añade la carpeta al iniciar sesión. ' +
    'Si la quitas a mano, volverá a ponerla: para quitarla, desinstala ArchMuse.');
  ConfianzaPagina.MsgLabel.Font.Size := 11;
  // Sin esto el texto se corta a media página: la altura de la etiqueta se
  // calcula al crearla, con la letra por defecto, y no crece al subir la letra
  // (medido con captura el 2026-09-14: cortado en seco con media página libre).
  ConfianzaPagina.MsgLabel.Height := ConfianzaPagina.SurfaceHeight;
end;

// La activación (rutas de confianza, puntero, comando en AutoCAD, servidor) va
// aquí y NO en [Run], que no mira el resultado. Y desde el 2026-09-14 sin
// esperar a ciegas: en la VM limpia la espera sin límite dejó el instalador
// 14 minutos en «Poniendo en marcha». `EjecutarActualizador` lee el resultado
// que deja el actualizador, enseña los segundos y se rinde a LIMITE_ACTIVAR_S.
procedure CurStepChanged(CurStep: TSetupStep);
var
  Pagina: TOutputProgressWizardPage;
  Resultado: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    Pagina := CreateOutputProgressPage('Poniendo en marcha ArchMuse',
      'No cierres esta ventana. La primera vez puede tardar un par de minutos.');
    Pagina.Show;
    try
      Resultado := EjecutarActualizador(ExpandConstant('{app}\runtime\pythonw.exe'),
                                        ExpandConstant('{app}\app\{#Version}\actualizador.pyw'),
                                        '--activar {#Version}', LIMITE_ACTIVAR_S, Pagina,
                                        MensajeActivacion);
    finally
      Pagina.Hide;
    end;
    ActivacionFallida := (Resultado <> ACTUALIZADOR_OK);
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = ConfianzaPagina.ID then
    WizardForm.NextButton.Caption := SetupMessage(msgButtonInstall);
  if (CurPageID = wpFinished) and ActivacionFallida then
    EnsenarQueNoHaQuedadoListo(MensajeActivacion);
end;

// Desinstalar: parar el servidor y quitar NUESTRA ruta de confianza de AutoCAD
// (condición 2). Aquí y no en [UninstallRun], que tampoco mira el código de
// salida: si no se ha podido quitar, él tiene que saberlo, porque su AutoCAD
// seguiría confiando en una carpeta que ya no es de nadie.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Mensaje, Parada: String;
  Pythonw, Actualizador: String;
  Quitada: Boolean;
begin
  if CurUninstallStep = usUninstall then
  begin
    Quitada := False;
    Mensaje := '';
    Pythonw := ExpandConstant('{app}\runtime\pythonw.exe');
    Actualizador := ActualizadorInstalado();
    if FileExists(Pythonw) and (Actualizador <> '') then
      Quitada := (EjecutarActualizador(Pythonw, Actualizador, '--desinstalar', LIMITE_BREVE_S,
                                       nil, Mensaje) = ACTUALIZADOR_OK);
    if not Quitada then
      MsgBox('ArchMuse se va a desinstalar, pero NO ha podido quitar su carpeta de las ' +
             'rutas de confianza de AutoCAD. AutoCAD seguiría cargando sin preguntar lo que ' +
             'haya en ' + ExpandConstant('{userappdata}\Autodesk\ApplicationPlugins\ArchMuse.bundle\Contents') +
             '. Avísanos para quitarla.' + #13#10#13#10 + Mensaje, mbError, MB_OK);
    // Lo que siga en marcha desde runtime\ (también el actualizador que acaba de
    // terminar) tiene que haber terminado antes de que se borren sus ficheros.
    if not PararArchMuse(Parada) then
      MsgBox('ArchMuse se desinstala, pero algo suyo sigue en marcha y puede que no se borren ' +
             'todos sus ficheros.' + #13#10#13#10 + Parada, mbError, MB_OK);
  end;
end;

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
  Mensaje: String;
begin
  Result := '';
  if not EsperarAutoCADCerrado() then
  begin
    Result := 'AutoCAD sigue abierto. No se ha instalado nada.';
    Exit;
  end;
  // Antes de copiar un solo fichero, y comprobando que no queda nada. Sin Python:
  // hasta el 2026-09-14 esto lo hacía el actualizador de la versión instalada,
  // que se buscaba a través de la unión app\actual (RedirectionGuard: «no
  // existe», y se saltaba la parada sin decir nada).
  if not PararArchMuse(Mensaje) then
  begin
    // Ninguna línea puede empezar por # (el preprocesador la tomaría por directiva).
    Result := 'No se ha instalado nada.' + #13#10#13#10 + Mensaje;
    Exit;
  end;
  DeleteFile(ExpandConstant('{app}\servidor.json'));
end;
