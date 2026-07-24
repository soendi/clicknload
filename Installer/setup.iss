#define MyAppName "ClickNLoad Bridge"
#define MyAppVersion "1.0.7.0"
#define MyAppPublisher "Lukas Sonderegger"
#define MyAppURL "https://github.com/soendi/clicknload"
#define MyAppExeName "ClickNLoadBridge.exe"

[Setup]
AppId={{C0FFEEC0-C0FF-EEC0-FFEE-C0FFEEC0FFEE}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\ClickNLoad Bridge
DefaultGroupName=ClickNLoad Bridge
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=dist
OutputBaseFilename=ClickNLoadBridge_Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\ClickNLoadBridge.exe
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
UninstallDisplayName=ClickNLoad Bridge

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktopverkn&uuml;pfung"; GroupDescription: "Zus&auml;tzliche Symbole:"; Flags: checkedonce

[Files]
Source: "dist\ClickNLoadBridge.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\ClickNLoad Bridge"; Filename: "{app}\{#MyAppExeName}"; Parameters: "/start"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,ClickNLoad Bridge}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\ClickNLoad Bridge"; Filename: "{app}\{#MyAppExeName}"; Parameters: "/start"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "/start"; Description: "ClickNLoad Bridge starten"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\ClickNLoadBridge"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\ClickNLoadBridge"; Flags: uninsdeletekey

[UninstallRun]
Filename: "{app}\{#MyAppExeName}"; Parameters: "/uninstall"; Flags: runhidden