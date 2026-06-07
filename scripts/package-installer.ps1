[CmdletBinding()]
param (
    [ValidateSet("cpu", "gpu")]
    [string]$Runtime = "cpu",
    [string]$Version = "v1.0.3",
    [string]$OutputDir = "",
    [switch]$NoBuild = $false,
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$DefaultOutputDir = Join-Path $RepoRoot "releases"
$PublishOutputDir = "$RepoRoot\desktop\wpf\FaceRecognition.Desktop\bin\Release\net10.0-windows\publish"
$BuildBackendScript = "$PSScriptRoot\build-backend.ps1"
$PublishDesktopScript = "$RepoRoot\desktop\wpf\FaceRecognition.Desktop\scripts\publish-desktop.ps1"
$IssScript = "$PSScriptRoot\FaceRecognitionService.iss"
$CustomOutputDir = -not [string]::IsNullOrWhiteSpace($OutputDir)

if ($CustomOutputDir) {
    $ResolvedOutputDir = [System.IO.Path]::GetFullPath($OutputDir)
} else {
    $ResolvedOutputDir = $DefaultOutputDir
}

$ForbiddenInstallerDir = [System.IO.Path]::GetFullPath("F:\VMShare\FaceRecognitionInstaller")
if ($ResolvedOutputDir.Equals($ForbiddenInstallerDir, [System.StringComparison]::OrdinalIgnoreCase) -or
    $ResolvedOutputDir.StartsWith("$ForbiddenInstallerDir\", [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Error "Refusing to write packaging output to protected release directory: $ForbiddenInstallerDir"
}

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
$ExpectedInstallerPath = Join-Path $ResolvedOutputDir "$OutputBaseFilename.exe"
$InnoDefineArgs = @(
    "/DAppVersion=$AppVersion",
    "/DOutputBaseFilename=$OutputBaseFilename",
    "/DPackageRuntime=$Runtime"
)
$InnoCompileArgs = @()
if ($CustomOutputDir) {
    $InnoCompileArgs += "/O$ResolvedOutputDir"
}
$InnoCompileArgs += $InnoDefineArgs

Write-Host "--- Packaging Installer ---"
Write-Host "RepoRoot: $RepoRoot"
Write-Host "Runtime: $Runtime"
Write-Host "Version: $VersionLabel"
Write-Host "AppVersion: $AppVersion"
Write-Host "OutputDir: $ResolvedOutputDir"
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
    Write-Host "Inno compile: ISCC $($InnoCompileArgs -join ' ') `"$IssScript`""
    exit 0
}

if ($CustomOutputDir -and (Test-Path $ExpectedInstallerPath)) {
    Write-Error "Installer output already exists. Refusing to overwrite: $ExpectedInstallerPath"
}

# Ensure output directory exists
if (-not (Test-Path $ResolvedOutputDir)) {
    New-Item -ItemType Directory -Path $ResolvedOutputDir | Out-Null
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
& $InnoPath @InnoCompileArgs $IssScript

if ($LASTEXITCODE -ne 0) {
    Write-Error "Inno Setup compilation failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

Write-Host "--- Packaging Complete ---"
Write-Host "Installer successfully built at: $ExpectedInstallerPath"
