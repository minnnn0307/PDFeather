#define AppVersion GetEnv('APP_VERSION')
#if AppVersion == ''
  #define AppVersion '1.2.0'
#endif
[Setup]
AppId={{D1E19B3A-782F-4B6F-92EE-57D873E15EDB}
AppName=PDFeather
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\PDFeather
DefaultGroupName=PDFeather
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=PDFeather-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\assets\PDFeather-1.2.0.ico
UninstallDisplayIcon={app}\PDFeather.exe
[Files]
Source: "..\dist\PDFeather\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\PDFeather-1.2.0.ico"; DestDir: "{app}\icons"; Flags: ignoreversion
[Icons]
Name: "{group}\PDFeather"; Filename: "{app}\PDFeather.exe"; IconFilename: "{app}\icons\PDFeather-1.2.0.ico"
Name: "{autodesktop}\PDFeather"; Filename: "{app}\PDFeather.exe"; IconFilename: "{app}\icons\PDFeather-1.2.0.ico"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\PDFeather.exe"; Description: "Launch PDFeather"; Flags: nowait postinstall skipifsilent

[Code]
procedure SHChangeNotify(wEventId: Integer; uFlags: Cardinal; dwItem1, dwItem2: Integer);
  external 'SHChangeNotify@shell32.dll stdcall';
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    SHChangeNotify($08000000, 0, 0, 0);
end;
