[Setup]
AppName=Face Recognition Service
AppVersion=1.0.0
DefaultDirName={localappdata}\Programs\Face Recognition Service
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir=..\releases
OutputBaseFilename=FaceRecognitionService-Setup-v1.0.0
Compression=lzma2
SolidCompression=yes
SetupIconFile=..\desktop\electron\assets\app-icon.ico
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\FaceRecognition.Desktop.exe

[Files]
; Copy all publish output, excluding config.json, logs, and data/jobs
Source: "..\desktop\wpf\FaceRecognition.Desktop\bin\Release\net10.0-windows\publish\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "config.json,logs\*,data\jobs\*"

[Icons]
Name: "{autoprograms}\Face Recognition Service"; Filename: "{app}\FaceRecognition.Desktop.exe"
Name: "{autodesktop}\Face Recognition Service"; Filename: "{app}\FaceRecognition.Desktop.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Code]
var
  DotNetMissing: Boolean;
  WV2Missing: Boolean;

function InitializeSetup(): Boolean;
var
  DotNetPath: String;
  WV2PathHKLM: String;
  WV2PathHKCU: String;
  FindRec: TFindRec;
  ErrorCode: Integer;
begin
  Result := True;
  
  // 1. Detect .NET 10 Desktop Runtime (x64)
  DotNetMissing := True;
  DotNetPath := ExpandConstant('{pf}\dotnet\shared\Microsoft.WindowsDesktop.App');
  if DirExists(DotNetPath) then
  begin
    if FindFirst(DotNetPath + '\10.*', FindRec) then
    begin
      DotNetMissing := False;
      FindClose(FindRec);
    end;
  end;
  
  // 2. Detect WebView2 Runtime
  WV2Missing := True;
  if RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', WV2PathHKLM) then
    WV2Missing := False;
  if RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', WV2PathHKCU) then
    WV2Missing := False;
    
  if DotNetMissing or WV2Missing then
  begin
    if DotNetMissing and WV2Missing then
    begin
      if MsgBox('This application requires the Microsoft .NET 10 Desktop Runtime (x64) and the Microsoft Edge WebView2 Runtime.' + #13#10#13#10 + 'Would you like to open the official download pages now?', mbCriticalError, MB_YESNO) = IDYES then
      begin
        ShellExec('open', 'https://dotnet.microsoft.com/download/dotnet/10.0', '', '', SW_SHOW, ewNoWait, ErrorCode);
        ShellExec('open', 'https://developer.microsoft.com/en-us/microsoft-edge/webview2/', '', '', SW_SHOW, ewNoWait, ErrorCode);
      end;
    end
    else if DotNetMissing then
    begin
      if MsgBox('This application requires the Microsoft .NET 10 Desktop Runtime (x64).' + #13#10#13#10 + 'Would you like to open the official download page now?', mbCriticalError, MB_YESNO) = IDYES then
        ShellExec('open', 'https://dotnet.microsoft.com/download/dotnet/10.0', '', '', SW_SHOW, ewNoWait, ErrorCode);
    end
    else if WV2Missing then
    begin
      if MsgBox('This application requires the Microsoft Edge WebView2 Runtime.' + #13#10#13#10 + 'Would you like to open the official download page now?', mbCriticalError, MB_YESNO) = IDYES then
        ShellExec('open', 'https://developer.microsoft.com/en-us/microsoft-edge/webview2/', '', '', SW_SHOW, ewNoWait, ErrorCode);
    end;
    
    // We let them continue if they want, or they can cancel the installer themselves.
  end;
end;
