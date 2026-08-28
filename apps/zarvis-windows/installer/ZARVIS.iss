#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\artifacts\publish"
#endif
#ifndef OutputDir
  #define OutputDir "..\artifacts"
#endif

[Setup]
AppId={{9E60CE95-6C99-49FC-9E85-6DFF88E4EB94}
AppName=Z.A.R.V.I.S.
AppVersion={#MyAppVersion}
AppPublisher=ZEAZDEV COMPANY LIMITED
DefaultDirName={localappdata}\Programs\ZARVIS
DefaultGroupName=Z.A.R.V.I.S.
OutputDir={#OutputDir}
OutputBaseFilename=ZARVIS-Setup-{#MyAppVersion}-win-x64
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayIcon={app}\ZARVIS.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Files]
Source: "{#SourceDir}\ZARVIS.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Z.A.R.V.I.S."; Filename: "{app}\ZARVIS.exe"
Name: "{autodesktop}\Z.A.R.V.I.S."; Filename: "{app}\ZARVIS.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\ZARVIS.exe"; Description: "Launch Z.A.R.V.I.S."; Flags: nowait postinstall skipifsilent
