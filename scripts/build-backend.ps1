param (
    [switch]$DebugBuild
)
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $RepoRoot "backend"

Push-Location $BackendDir

# Ensure PyInstaller is installed
Write-Host "Ensuring PyInstaller is installed..."
python -m pip install pyinstaller

if ($DebugBuild) {
    Write-Host "Building Backend in DEBUG mode (with console)..."
    pyinstaller FaceBackend.debug.spec --clean -y
} else {
    Write-Host "Building Backend in RELEASE mode (hidden console)..."
    pyinstaller FaceBackend.spec --clean -y
}

Pop-Location
Write-Host "Build complete. Output in backend/dist/"
