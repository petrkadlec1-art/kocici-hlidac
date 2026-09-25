; Instalátor Windows verze (Inno Setup 6). Sestavuje ho CI:
;   iscc /DAppVersion=0.1.0 installer\kocici-hlidac.iss
; Čeká dist\kocici-hlidac.exe a kocka.ico v kořeni repa.
; Instaluje jen pro aktuálního uživatele: bez admin práv a bez UAC,
; stejně jako spouštění po přihlášení (HKCU\...\Run).

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

[Setup]
AppId={{A7BA4D6D-3E1F-4250-847D-3F5DF11D9309}
AppName=Kočičí hlídač
AppVersion={#AppVersion}
AppPublisher=Petr Kadlec
AppPublisherURL=https://github.com/petrkadlec1-art/kocici-hlidac
DefaultDirName={localappdata}\Programs\kocici-hlidac
DefaultGroupName=Kočičí hlídač
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=kocici-hlidac-setup
SetupIconFile=..\kocka.ico
UninstallDisplayIcon={app}\kocici-hlidac.exe
UninstallDisplayName=Kočičí hlídač
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "cs"; MessagesFile: "compiler:Languages\Czech.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
cs.Autostart=Spouštět po přihlášení
en.Autostart=Start at login
cs.Launch=Spustit Kočičí hlídač
en.Launch=Start Kočičí hlídač

[Tasks]
Name: "autostart"; Description: "{cm:Autostart}"

[Files]
Source: "..\dist\kocici-hlidac.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Kočičí hlídač"; Filename: "{app}\kocici-hlidac.exe"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "KociciHlidac"; ValueData: """{app}\kocici-hlidac.exe"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\kocici-hlidac.exe"; Description: "{cm:Launch}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Autostart mohl uživatel zapnout i z menu ikony, uklidí ho sama aplikace.
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM kocici-hlidac.exe"; Flags: runhidden; RunOnceId: "Ukoncit"
Filename: "{app}\kocici-hlidac.exe"; Parameters: "--no-autostart"; Flags: runhidden waituntilterminated; RunOnceId: "BezAutostartu"

[Code]
// Běžící hlídač drží exe, při aktualizaci by ho nešlo přepsat.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Kod: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM kocici-hlidac.exe', '', SW_HIDE,
       ewWaitUntilTerminated, Kod);
  Result := '';
end;

// Bez zaškrtnutého autostartu smazat i hodnotu z dřívější instalace.
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and not WizardIsTaskSelected('autostart') then
    RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'KociciHlidac');
end;
