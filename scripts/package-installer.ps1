[CmdletBinding()]
param (
    [ValidateSet("cpu", "gpu")]
    [string]$Runtime = "cpu",
    [string]$Version = "v1.0.2",
    [switch]$NoBuild = $false,
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
$ReleasesDir = "$RepoRoot\releases"
$PublishOutputDir = "$RepoRoot\desktop\wpf\FaceRecognition.Desktop\bin\Release\net10.0-windows\publish"
$BuildBackendScript = "$PSScriptRoot\build-backend.ps1"
$PublishDesktopScript = "$RepoRoot\desktop\wpf\FaceRecognition.Desktop\scripts\publish-desktop.ps1"
$IssScript = "$PSScriptRoot\FaceRecognitionService.iss"

$VersionLabel = $Version.Trim()
if ([string]::IsNullOrWhiteSpace($VersionLabel)) {
    Write-Error "Version must not be empty."
}
if ($VersionLabel.StartsWith("v", [System.StringComparison]::OrdinalIgnoreCase)) {
    $AppVersion = $VersionLabel.Substring(1)
} else {
    $AppVersion = $VersionLabel
    $VersionLabel = "v$VersionLabel"
}

$OutputBaseFilename = "FaceRecognitionService-Setup-$VersionLabel-$Runtime"
$ExpectedInstallerPath = Join-Path $ReleasesDir "$OutputBaseFilename.exe"
$InnoDefineArgs = @(
    "/DAppVersion=$AppVersion",
    "/DOutputBaseFilename=$OutputBaseFilename",
    "/DPackageRuntime=$Runtime"
)

Write-Host "--- Packaging Installer ---"
Write-Host "RepoRoot: $RepoRoot"
Write-Host "Runtime: $Runtime"
Write-Host "Version: $VersionLabel"
Write-Host "AppVersion: $AppVersion"
Write-Host "OutputBaseFilename: $OutputBaseFilename"
Write-Host "Expected installer: $ExpectedInstallerPath"

if ($DryRun) {
    Write-Host "--- Dry Run: no files will be created and no build commands will run ---"
    if ($NoBuild) {
        Write-Host "Backend build: skipped because -NoBuild was supplied."
        Write-Host "Desktop publish: skipped because -NoBuild was supplied."
    } else {
        Write-Host "Backend build: powershell -ExecutionPolicy Bypass -File `"$BuildBackendScript`" -Runtime $Runtime"
        Write-Host "Desktop publish: powershell -ExecutionPolicy Bypass -File `"$PublishDesktopScript`" -IncludeBackend"
    }
    Write-Host "Inno compile: ISCC $($InnoDefineArgs -join ' ') `"$IssScript`""
    exit 0
}

# Ensure releases directory exists
if (-not (Test-Path $ReleasesDir)) {
    New-Item -ItemType Directory -Path $ReleasesDir | Out-Null
}

# 1. Build Backend
if (-not $NoBuild) {
    Write-Host "Running build-backend.ps1 to package the Python backend for '$Runtime' runtime..."
    & $BuildBackendScript -Runtime $Runtime
    if ($LASTEXITCODE -ne 0) {
        Write-Error "build-backend.ps1 failed."
        exit $LASTEXITCODE
    }
}

# 2. Build Desktop publish output if not skipped
if (-not $NoBuild) {
    Write-Host "Running publish-desktop.ps1 to prepare the files..."
    & $PublishDesktopScript -IncludeBackend
    if ($LASTEXITCODE -ne 0) {
        Write-Error "publish-desktop.ps1 failed."
        exit $LASTEXITCODE
    }
}

# 2. Check if Inno Setup Compiler is installed
$InnoPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $InnoPath)) {
    $InnoPath = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path $InnoPath)) {
    Write-Error "Inno Setup 6 compiler not found. Please install Inno Setup 6."
    exit 1
}

# 3. Compile the Inno Setup Script
Write-Host "Compiling Inno Setup Script: $IssScript"
& $InnoPath @InnoDefineArgs $IssScript

if ($LASTEXITCODE -ne 0) {
    Write-Error "Inno Setup compilation failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

Write-Host "--- Packaging Complete ---"
Write-Host "Installer successfully built at: $ExpectedInstallerPath"
