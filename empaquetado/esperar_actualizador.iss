// Ejecutar el actualizador SIN esperar a ciegas (2026-09-14).
//
// En la VM de Windows 11 limpia el instalador se quedó 14 minutos en «Poniendo
// en marcha ArchMuse»: esperaba con ewWaitUntilTerminated, sin límite, a un
// actualizador que a su vez esperaba a que alguien cerrara una ventana de
// mensaje que nadie veía. Aquí: el actualizador se lanza sin esperar, con
// --silencioso (ninguna ventana) y --resultado (deja OK/ERROR y el mensaje en un
// fichero); se lee ese fichero, y hay un límite.
//
// Lo incluyen ArchMuse-Beta.iss y, tal cual, la prueba de Inno del mismo día:
// lo que se probó es lo que se instala.

const
  ACTUALIZADOR_OK = 0;
  ACTUALIZADOR_ERROR = 1;
  ACTUALIZADOR_SIN_RESPUESTA = 2;
  ACTUALIZADOR_NO_SE_LANZA = 3;

// El Pascal de Inno Setup no trae un reloj: el de Windows, directamente.
function GetTickCount: DWORD;
  external 'GetTickCount@kernel32.dll stdcall';

function LeerResultadoDelActualizador(Fichero: String; var Correcto: Boolean; var Mensaje: String): Boolean;
var
  Lineas: TArrayOfString;
  Primera: String;
  I: Integer;
begin
  Result := False;
  if not FileExists(Fichero) then
    Exit;
  if not LoadStringsFromFile(Fichero, Lineas) then
    Exit;
  if GetArrayLength(Lineas) = 0 then
    Exit;
  Primera := Trim(Lineas[0]);
  // Por si la marca de UTF-8 llega como carácter en vez de quitarse al leer.
  if (Length(Primera) > 0) and (Ord(Primera[1]) = $FEFF) then
    Delete(Primera, 1, 1);
  Correcto := (Primera = 'OK');
  Mensaje := '';
  for I := 1 to GetArrayLength(Lineas) - 1 do
    if Trim(Lineas[I]) <> '' then
    begin
      if Mensaje <> '' then
        Mensaje := Mensaje + #13#10;
      Mensaje := Mensaje + Lineas[I];
    end;
  Result := True;
end;

function EjecutarActualizador(Pythonw, Actualizador, Argumentos: String; LimiteS: Integer;
                              Pagina: TOutputProgressWizardPage; var Mensaje: String): Integer;
var
  Fichero: String;
  Codigo: Integer;
  Inicio, Transcurridos: DWORD;
  Correcto: Boolean;
begin
  Fichero := AddBackslash(GetTempDir) + 'ArchMuse-resultado-' + IntToStr(GetTickCount) + '.txt';
  DeleteFile(Fichero);
  Mensaje := '';
  if not Exec(Pythonw, '"' + Actualizador + '" ' + Argumentos + ' --silencioso --resultado "' + Fichero + '"',
              ExtractFileDir(Pythonw), SW_HIDE, ewNoWait, Codigo) then
  begin
    Mensaje := 'No se ha podido ejecutar ' + Pythonw + ': ' + SysErrorMessage(Codigo);
    Result := ACTUALIZADOR_NO_SE_LANZA;
    Exit;
  end;
  Inicio := GetTickCount;
  Transcurridos := 0;
  while Transcurridos < LimiteS do
  begin
    if LeerResultadoDelActualizador(Fichero, Correcto, Mensaje) then
    begin
      DeleteFile(Fichero);
      if Correcto then
        Result := ACTUALIZADOR_OK
      else
        Result := ACTUALIZADOR_ERROR;
      Exit;
    end;
    if Pagina <> nil then
    begin
      Pagina.SetText('Poniendo en marcha ArchMuse. La primera vez puede tardar un par de minutos.',
                     IntToStr(Transcurridos) + ' s');
      Pagina.SetProgress(Transcurridos, LimiteS);
    end;
    Sleep(250);
    Transcurridos := (GetTickCount - Inicio) div 1000;
  end;
  Mensaje := 'ArchMuse no ha contestado en ' + IntToStr(LimiteS) + ' s. Lo que haya pasado está ' +
             'escrito en ' + ExpandConstant('{localappdata}\ArchMuse\registro') +
             '. Mándanos esa carpeta.';
  Result := ACTUALIZADOR_SIN_RESPUESTA;
end;

// La pantalla final cuando la activación no ha ido bien: el mensaje del
// actualizador entero, no uno genérico. La etiqueta se alarga hasta el final de
// la página: con la página previa se midió que, si no, corta el texto.
procedure EnsenarQueNoHaQuedadoListo(Mensaje: String);
begin
  WizardForm.FinishedHeadingLabel.Caption := 'ArchMuse no ha quedado listo';
  // Ninguna línea puede empezar por # (el preprocesador la tomaría por directiva).
  WizardForm.FinishedLabel.Caption :=
    'Los ficheros están copiados, pero ArchMuse no ha terminado de ponerse en marcha.' + #13#10#13#10 + Mensaje;
  WizardForm.FinishedLabel.Height := WizardForm.FinishedPage.ClientHeight - WizardForm.FinishedLabel.Top;
end;
