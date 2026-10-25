#define AppVersion GetEnv('APP_VERSION')
#if AppVersion == ''
  #define AppVersion '0.1.0'
#endif
[Setup]
AppId={{D1E19B3A-782F-4B6F-92EE-57D873E15EDB}
AppName=Feather PDF
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\FeatherPDF
DefaultGroupName=Feather PDF
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=FeatherPDF-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\FeatherPDF.exe
[Files]
Source: "..\dist\FeatherPDF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Feather PDF"; Filename: "{app}\FeatherPDF.exe"
Name: "{autodesktop}\Feather PDF"; Filename: "{app}\FeatherPDF.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\FeatherPDF.exe"; Description: "Launch Feather PDF"; Flags: nowait postinstall skipifsilent
