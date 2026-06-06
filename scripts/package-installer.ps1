param (
    [switch]$NoBuild = $false
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
$ReleasesDir = "$RepoRoot\releases"
$PublishOutputDir = "$RepoRoot\desktop\wpf\FaceRecognition.Desktop\bin\Release\net10.0-windows\publish"

# Ensure releases directory exists
if (-not (Test-Path $ReleasesDir)) {
    New-Item -ItemType Directory -Path $ReleasesDir | Out-Null
}

# 1. Build Backend
if (-not $NoBuild) {
    Write-Host "Running build-backend.ps1 to package the Python backend..."
    & "$PSScriptRoot\build-backend.ps1"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "build-backend.ps1 failed."
        exit $LASTEXITCODE
    }
}

# 2. Build Desktop publish output if not skipped
if (-not $NoBuild) {
    Write-Host "Running publish-desktop.ps1 to prepare the files..."
    & "$RepoRoot\desktop\wpf\FaceRecognition.Desktop\scripts\publish-desktop.ps1" -IncludeBackend
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
$IssScript = "$PSScriptRoot\FaceRecognitionService.iss"
Write-Host "Compiling Inno Setup Script: $IssScript"
& $InnoPath $IssScript

if ($LASTEXITCODE -ne 0) {
    Write-Error "Inno Setup compilation failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

Write-Host "--- Packaging Complete ---"
Write-Host "Installer successfully built at: $ReleasesDir\FaceRecognitionService-Setup-v1.0.1.exe"
