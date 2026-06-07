param (
    [ValidateSet("cpu", "gpu")]
    [string]$Runtime = "gpu",
    [switch]$DebugBuild
)
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $RepoRoot "backend"
$RuntimeRequirements = Join-Path $BackendDir "requirements-$Runtime.txt"
$BuildRequirements = Join-Path $BackendDir "requirements-build.txt"

if (-not (Test-Path $RuntimeRequirements)) {
    Write-Error "Runtime requirements file not found: $RuntimeRequirements"
}

if (-not (Test-Path $BuildRequirements)) {
    Write-Error "Build requirements file not found: $BuildRequirements"
}

if ($DebugBuild -and $Runtime -ne "gpu") {
    Write-Error "DebugBuild currently uses FaceBackend.debug.spec and only supports the gpu runtime."
}

Push-Location $BackendDir
$previousRuntime = $env:FACE_BACKEND_RUNTIME
try {
    Write-Host "Preparing backend dependencies for '$Runtime' runtime..."
    python -m pip uninstall -y onnxruntime onnxruntime-gpu
    python -m pip install -r $RuntimeRequirements -r $BuildRequirements

    $env:FACE_BACKEND_RUNTIME = $Runtime

    if ($DebugBuild) {
        Write-Host "Building Backend in DEBUG mode (with console) for '$Runtime' runtime..."
        pyinstaller FaceBackend.debug.spec --clean -y
    } else {
        Write-Host "Building Backend in RELEASE mode (hidden console) for '$Runtime' runtime..."
        pyinstaller FaceBackend.spec --clean -y
    }
} finally {
    if ($null -eq $previousRuntime) {
        Remove-Item Env:\FACE_BACKEND_RUNTIME -ErrorAction SilentlyContinue
    } else {
        $env:FACE_BACKEND_RUNTIME = $previousRuntime
    }

    Pop-Location
}
Write-Host "Build complete for '$Runtime' runtime. Output in backend/dist/"
