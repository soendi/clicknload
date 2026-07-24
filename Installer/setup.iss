#define MyAppName "ClickNLoad Bridge"
#define MyAppVersion "1.0.17.0"
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
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=ClickNLoadBridge_Setup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\ClickNLoadBridge.exe
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
UninstallDisplayName=ClickNLoad Bridge
CloseApplications=force
RestartApplications=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktopverknüpfung"; GroupDescription: "Zusätzliche Symbole:"; Flags: checkedonce
Name: "autostart"; Description: "Mit Windows starten"; GroupDescription: "Autostart:"
Name: "systray"; Description: "Direkt in den Systray starten"; GroupDescription: "Autostart:"; Flags: unchecked

[Files]
Source: "..\dist\ClickNLoadBridge.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\ClickNLoad Bridge"; Filename: "{app}\{#MyAppExeName}"; Parameters: "/start"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,ClickNLoad Bridge}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\ClickNLoad Bridge"; Filename: "{app}\{#MyAppExeName}"; Parameters: "/start"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "/start"; Description: "ClickNLoad Bridge starten"; Flags: nowait postinstall skipifnotsilent
Filename: "{app}\{#MyAppExeName}"; Parameters: "/start"; Description: ""; Flags: nowait postinstall skipifsilent

[Registry]
; Uninstall-Eintrag (wird bei Deinstallation automatisch entfernt)
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\ClickNLoadBridge"; Flags: uninsdeletekey
; App-Einstellungen in HKCU (wird bei Deinstallation entfernt, bei Update beibehalten)
Root: HKCU; Subkey: "Software\ClickNLoadBridge"; Flags: uninsdeletekey

[UninstallRun]
Filename: "{app}\{#MyAppExeName}"; Parameters: "/uninstall"; Flags: runhidden
