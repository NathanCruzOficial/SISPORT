#define AppName "SISPORT"
#define AppVersion "1.0.0"
#define AppPublisher "Nathan Cruz"
#define AppExeName "sisport.exe"
#define BuildDir "dist\\main"

[Setup]
AppId={{SISPORT-2026}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppContact=suporte@sisport.app
UninstallDisplayIcon={app}\{#AppExeName}

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

OutputDir=.\installer_output
OutputBaseFilename={#AppName}-Setup-v{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar ícone na Área de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
; Copia TODO o conteúdo do onedir gerado pelo PyInstaller
Source: ".\{#BuildDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Executar {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
var
  ShouldDeleteAppData: Boolean;

function InitializeUninstall(): Boolean;
begin
  ShouldDeleteAppData :=
    (MsgBox(
      'Deseja também remover os dados do usuário (AppData) do {#AppName}?'#13#10 +
      'Esta ação é permanente e não pode ser desfeita.',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES);
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDataPath: string;
begin
  if (CurUninstallStep = usUninstall) and ShouldDeleteAppData then
  begin
    AppDataPath := ExpandConstant('{userappdata}\{#AppName}');
    if DirExists(AppDataPath) then
    begin
      DelTree(AppDataPath, True, True, True);
    end;
  end;
end;
