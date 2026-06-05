[CmdletBinding()]
Param(
    [Parameter(Mandatory=$true)]
    [string]$OutputDir,

    [switch]$NoZip,

    [switch]$ReuseBackend,
    
    [switch]$ForceBackend,

    [switch]$CleanRuntime
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

Write-Host "--- Deploying to Sandbox ---"
Write-Host "OutputDir: $OutputDir"

# 1. Clean Runtime if requested
if ($CleanRuntime) {
    Write-Host "Cleaning runtime files in $OutputDir..."
    if (Test-Path (Join-Path $OutputDir "config.json")) { Remove-Item (Join-Path $OutputDir "config.json") -Force }
    if (Test-Path (Join-Path $OutputDir "logs")) { Remove-Item (Join-Path $OutputDir "logs") -Recurse -Force }
    if (Test-Path (Join-Path $OutputDir "data\jobs")) { Remove-Item (Join-Path $OutputDir "data\jobs") -Recurse -Force }
}

# 2. Check Backend
$BackendAlreadyExists = (Test-Path (Join-Path $OutputDir "backend\FaceBackend.exe")) -and (Test-Path (Join-Path $OutputDir "backend\_internal"))

if ($ForceBackend) {
    $CopyBackendToTarget = $true
} elseif ($ReuseBackend -and $BackendAlreadyExists) {
    Write-Host "Backend already exists in OutputDir. Reusing it."
    $CopyBackendToTarget = $false
} else {
    $CopyBackendToTarget = $true
}

# 3. Run publish script
$PublishScript = Join-Path $RepoRoot "desktop\wpf\FaceRecognition.Desktop\scripts\publish-desktop.ps1"

Write-Host "Running publish-desktop.ps1..."
if ($CopyBackendToTarget) {
    & $PublishScript -IncludeBackend
} else {
    & $PublishScript
}

# 4. Determine publish output directory
$WpfDir = Join-Path $RepoRoot "desktop\wpf\FaceRecognition.Desktop"
$CsprojPath = Join-Path $WpfDir "FaceRecognition.Desktop.csproj"
$TargetFramework = ([xml](Get-Content $CsprojPath)).Project.PropertyGroup.TargetFramework
if (-not $TargetFramework) { $TargetFramework = "net10.0-windows" }
$PublishOutputDir = Join-Path $WpfDir "bin\Release\$TargetFramework\publish"

# 5. Copy required files to OutputDir
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
}

Write-Host "Copying files to $OutputDir..."

# Copy WPF Executables, DLLs, and Runtimes
Get-ChildItem -Path $PublishOutputDir | Where-Object { $_.Name -notin @("config.json", "frontend", "backend") } | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $OutputDir -Recurse -Force
}

# Copy Frontend
$TargetFrontend = Join-Path $OutputDir "frontend"
if (-not (Test-Path $TargetFrontend)) { New-Item -ItemType Directory -Force -Path $TargetFrontend | Out-Null }
Copy-Item -Path (Join-Path $PublishOutputDir "frontend\dist") -Destination $TargetFrontend -Recurse -Force

if ($CopyBackendToTarget) {
    Write-Host "Copying backend..."
    $TargetBackend = Join-Path $OutputDir "backend"
    if (-not (Test-Path $TargetBackend)) { New-Item -ItemType Directory -Force -Path $TargetBackend | Out-Null }
    Copy-Item -Path (Join-Path $PublishOutputDir "backend\FaceBackend.exe") -Destination $TargetBackend -Force
    Copy-Item -Path (Join-Path $PublishOutputDir "backend\_internal") -Destination $TargetBackend -Recurse -Force
}

# Make sure logs dir exists
$TargetLogs = Join-Path $OutputDir "logs"
if (-not (Test-Path $TargetLogs)) { New-Item -ItemType Directory -Force -Path $TargetLogs | Out-Null }

Write-Host "--- Deployment Complete ---"
