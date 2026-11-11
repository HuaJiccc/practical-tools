; ============================================================
;  实用工具 安装脚本（Inno Setup 6.7 及以上）
;
;  编译：ISCC.exe installer\app.iss
;  产物：dist-installer\实用工具-1.0.0-安装程序.exe
;
;  设计要点：
;    · 按当前用户安装，默认不弹 UAC；装到 Program Files 时才需要管理员
;    · 用户数据固定放 %LOCALAPPDATA%\实用工具\data，卸载时保留
;    · 安装时写 data-dir.txt（单行 UTF-8），程序启动即按它定位数据
; ============================================================

#define AppName "实用工具"
#define AppVersion "1.0.2"
#define AppExe "实用工具.exe"
#define AppAuthor "H.J."
#define AppId "{{7C4A1F52-9E3B-4F0A-9D21-2B77C5E8A641}"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppAuthor}
AppCopyright=© 2026 {#AppAuthor}
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile=许可协议.txt
OutputDir=..\dist-installer
OutputBaseFilename={#AppName}-{#AppVersion}-安装程序
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
AllowNoIcons=yes
MinVersion=10.0
DisableWelcomePage=no

[Languages]
Name: "chs"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: unchecked

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\使用说明.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "许可协议.txt"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
; 改名前的可执行文件，留着只会占 13 MB 且容易误点
Type: files; Name: "{app}\个人工具.exe"

[UninstallDelete]
; 运行时生成的路径配置，卸载后不需要留；用户数据在 %LOCALAPPDATA% 不动
Type: files; Name: "{app}\data-dir.txt"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "翻译、记事、待办、图片处理等 13 项工具"
Name: "{autoprograms}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; 普通安装：完成页给个勾选框由用户决定
Filename: "{app}\{#AppExe}"; Description: "立即启动 {#AppName}"; Flags: nowait postinstall skipifsilent
; 静默安装（程序内「立即更新」走这条路）：装完直接重开，否则用户只看到窗口一闪，
; 分不清是装好了还是崩了。skipifnotsilent 让两条互斥，不会开两个。
Filename: "{app}\{#AppExe}"; Flags: nowait skipifnotsilent

[Code]
{ ---------- WebView2：程序用它渲染界面，Win10/11 一般已预装 ---------- }
function WebView2Version: String;
var
  Value: String;
begin
  Result := '';
  if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'Software\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Value) then
    Result := Value
  else if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Value) then
    Result := Value
  else if RegQueryStringValue(HKEY_CURRENT_USER, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Value) then
    Result := Value;
end;

function InitializeSetup: Boolean;
var
  ErrorCode: Integer;
begin
  Result := True;
  if WebView2Version = '' then
  begin
    if MsgBox('这台电脑上没有检测到 Microsoft Edge WebView2 运行时。' + #13#10#13#10 +
      '程序用它来显示界面。Windows 11 和较新的 Windows 10 都已经自带；' + #13#10 +
      '如果继续安装，程序可能无法启动。' + #13#10#13#10 +
      '是否现在打开微软的下载页面？安装完成后回到这里继续即可。',
      mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://go.microsoft.com/fwlink/p/?LinkId=2124703', '', '',
        SW_SHOWNORMAL, ewNoWait, ErrorCode);
  end;
end;

{ ---------- 装完写 data-dir.txt，把数据放到用户目录 ---------- }
procedure CurStepChanged(CurStep: TSetupStep);
var
  Marker, DataPath: String;
  Lines: TArrayOfString;
begin
  if CurStep = ssPostInstall then
  begin
    Marker := ExpandConstant('{app}\data-dir.txt');
    { 用户自己改过就尊重原设置，升级安装不覆盖 }
    if not FileExists(Marker) then
    begin
      DataPath := ExpandConstant('{localappdata}\{#AppName}\data');
      ForceDirectories(DataPath);
      { 只能写一行：多写注释会让程序认不出路径。
        必须 UTF-8 带 BOM：程序按 utf-8-sig 读，默认 ANSI 会把中文路径写坏。 }
      SetArrayLength(Lines, 1);
      Lines[0] := DataPath;
      SaveStringsToUTF8File(Marker, Lines, True);
    end;
  end;
end;
