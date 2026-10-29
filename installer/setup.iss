#include "version.iss"
[Setup]
AppId={{D1E19B3A-782F-4B6F-92EE-57D873E15EDB}
AppName=PDFeather
AppVerName=PDFeather
AppPublisher={cm:PublisherName}
AppPublisherURL=https://github.com/minnnn0307/PDFeather
AppUpdatesURL=https://github.com/minnnn0307/PDFeather/releases
VersionInfoDescription=PDFeather
VersionInfoProductName=PDFeather
VersionInfoCompany={#AppPublisherEnglish}
VersionInfoProductVersion={#AppVersion}
LanguageDetectionMethod=uilanguage
UsePreviousLanguage=no
ShowLanguageDialog=no
AppVersion={#AppVersion}
ChangesAssociations=yes
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
[Languages]
Name: english; MessagesFile: "compiler:Default.isl"
Name: korean; MessagesFile: "compiler:Languages\Korean.isl"
[CustomMessages]
english.PublisherName={#AppPublisherEnglish}
korean.PublisherName={#AppPublisherKorean}
english.DesktopShortcut=Create a desktop shortcut
korean.DesktopShortcut=바탕화면 바로가기 만들기
english.LaunchApp=Launch PDFeather
korean.LaunchApp=PDFeather 실행
[Files]
Source: "..\dist\PDFeather\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\PDFeather-1.2.0.ico"; DestDir: "{app}\icons"; Flags: ignoreversion
[Registry]
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "PDFeather.PDF"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\PDFeather.PDF"; ValueType: string; ValueName: ""; ValueData: "PDF"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\PDFeather.PDF\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\icons\PDFeather-1.2.0.ico"
Root: HKA; Subkey: "Software\Classes\PDFeather.PDF\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\PDFeather.exe"" ""%1"""
Root: HKA; Subkey: "Software\Classes\Applications\PDFeather.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "PDFeather"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\PDFeather.exe\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\PDFeather.exe\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\PDFeather.exe"" ""%1"""
Root: HKA; Subkey: "Software\PDFeather\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "PDFeather"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\PDFeather\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "PDFeather"
Root: HKA; Subkey: "Software\PDFeather\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "PDFeather.PDF"
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "PDFeather"; ValueData: "Software\PDFeather\Capabilities"; Flags: uninsdeletevalue
[Icons]
Name: "{group}\PDFeather"; Filename: "{app}\PDFeather.exe"; IconFilename: "{app}\icons\PDFeather-1.2.0.ico"
Name: "{autodesktop}\PDFeather"; Filename: "{app}\PDFeather.exe"; IconFilename: "{app}\icons\PDFeather-1.2.0.ico"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "{cm:DesktopShortcut}"; Flags: unchecked
[Run]
Filename: "{app}\PDFeather.exe"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

Filename: "{app}\PDFeather.exe"; Flags: nowait; Check: IsUpdateInstall

[Code]
function OpenProcess(Access: LongWord; InheritHandle: Integer; ProcessId: LongWord): THandle;
  external 'OpenProcess@kernel32.dll stdcall';
function WaitForSingleObject(Handle: THandle; Milliseconds: LongWord): LongWord;
  external 'WaitForSingleObject@kernel32.dll stdcall';
function CloseHandle(Handle: THandle): Integer;
  external 'CloseHandle@kernel32.dll stdcall';

function InitializeSetup: Boolean;
var
  ParentPid: Integer;
  ParentHandle: THandle;
  WaitResult: LongWord;
begin
  Result := True;
  ParentPid := StrToIntDef(ExpandConstant('{param:PDFEATHERWAITPID|0}'), 0);
  if ParentPid > 0 then begin
    ParentHandle := OpenProcess($00100000, 0, ParentPid);
    if ParentHandle <> 0 then begin
      WaitResult := WaitForSingleObject(ParentHandle, 60000);
      CloseHandle(ParentHandle);
      if WaitResult <> 0 then begin
        Log('The previous PDFeather process did not exit; update cancelled.');
        Result := False;
      end;
    end;
  end;
end;

function IsUpdateInstall: Boolean;
begin
  Result := ExpandConstant('{param:PDFEATHERUPDATE|0}') = '1';
end;

procedure SHChangeNotify(wEventId: Integer; uFlags: Cardinal; dwItem1, dwItem2: Integer);
  external 'SHChangeNotify@shell32.dll stdcall';
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    SHChangeNotify($08000000, 0, 0, 0);
end;
