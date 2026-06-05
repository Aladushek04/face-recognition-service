[CmdletBinding()]
Param(
    [switch]$IncludeBackend
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Safely resolve repo root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CurrentDir = $ScriptDir
$RepoRoot = $null

while ($CurrentDir -ne $null -and $CurrentDir -ne "") {
    if ((Test-Path (Join-Path $CurrentDir "backend\main.py")) -and (Test-Path (Join-Path $CurrentDir "frontend\package.json"))) {
        $RepoRoot = $CurrentDir
        break
    }
    $CurrentDir = Split-Path $CurrentDir -Parent
}

if ($null -eq $RepoRoot) {
    Write-Error "Could not resolve RepoRoot. Script must be run from within the FaceRecognition project."
}

Write-Host "RepoRoot found at: $RepoRoot"

$FrontendDir = Join-Path $RepoRoot "frontend"
$WpfDir = Join-Path $RepoRoot "desktop\wpf\FaceRecognition.Desktop"

# Frontend build
Write-Host "Checking frontend dependencies..."
$NodeModulesDir = Join-Path $FrontendDir "node_modules"
if (-not (Test-Path $NodeModulesDir)) {
    Write-Host "node_modules not found. Installing dependencies..."
    Push-Location $FrontendDir
    if (Test-Path "package-lock.json") {
        npm ci
    } else {
        npm install
    }
    Pop-Location
} else {
    Write-Host "Frontend dependencies found. Skipping install."
}

Write-Host "Building frontend..."
Push-Location $FrontendDir
npm run build
Pop-Location

# WPF Publish
Write-Host "Publishing WPF Desktop Shell..."
Push-Location $WpfDir
dotnet publish -c Release
Pop-Location

# Assemble Publish Output
$CsprojPath = Join-Path $WpfDir "FaceRecognition.Desktop.csproj"
$TargetFramework = ([xml](Get-Content $CsprojPath)).Project.PropertyGroup.TargetFramework
if (-not $TargetFramework) {
    $TargetFramework = "net10.0-windows"
}
$PublishOutputDir = Join-Path $WpfDir "bin\Release\$TargetFramework\publish"
Write-Host "Publish output directory: $PublishOutputDir"

# Copy frontend/dist
$TargetFrontendDist = Join-Path $PublishOutputDir "frontend\dist"
if (Test-Path $TargetFrontendDist) {
    Write-Host "Cleaning old frontend/dist from publish folder..."
    Remove-Item -Recurse -Force $TargetFrontendDist
}

$SourceFrontendDist = Join-Path $FrontendDir "dist"
if (-not (Test-Path $SourceFrontendDist)) {
    Write-Error "Frontend build failed or dist folder missing."
}

Write-Host "Copying frontend/dist to publish folder..."
New-Item -ItemType Directory -Force -Path (Split-Path $TargetFrontendDist -Parent) | Out-Null
Copy-Item -Path $SourceFrontendDist -Destination (Split-Path $TargetFrontendDist -Parent) -Recurse -Force

# Copy config.example.json
Write-Host "Copying config.example.json..."
$SourceConfigExample = Join-Path $RepoRoot "config.example.json"
$TargetConfigExample = Join-Path $PublishOutputDir "config.example.json"
if (Test-Path $SourceConfigExample) {
    Copy-Item -Path $SourceConfigExample -Destination $TargetConfigExample -Force
    
    # Create config.json only if missing
    $TargetConfig = Join-Path $PublishOutputDir "config.json"
    if (-not (Test-Path $TargetConfig)) {
        Write-Host "config.json missing in publish folder, copying from example..."
        Copy-Item -Path $SourceConfigExample -Destination $TargetConfig -Force
    }
} else {
    Write-Warning "config.example.json not found in repository root."
}

# Create logs directory
Write-Host "Ensuring logs directory exists..."
$LogsDir = Join-Path $PublishOutputDir "logs"
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
}

# Copy backend if requested
if ($IncludeBackend) {
    Write-Host "IncludeBackend flag detected. Copying packaged backend..."
    $SourceBackendDir = Join-Path $RepoRoot "backend\dist\FaceBackend"
    $TargetBackendDir = Join-Path $PublishOutputDir "backend"
    
    if (-not (Test-Path $SourceBackendDir)) {
        Write-Error "Packaged backend not found at $SourceBackendDir. Please build it first."
    }

    if (Test-Path $TargetBackendDir) {
        Write-Host "Cleaning old backend from publish folder..."
        Remove-Item -Recurse -Force $TargetBackendDir
    }

    Write-Host "Copying backend/dist/FaceBackend to publish folder..."
    Copy-Item -Path $SourceBackendDir -Destination $TargetBackendDir -Recurse -Force
}

# Create README.txt
$ReadmePath = Join-Path $PublishOutputDir "README.txt"
if ($IncludeBackend) {
    $ReadmeContent = @"
Face Recognition Service - Phase 2B Publish

This folder contains the published WPF Desktop Shell, React Frontend, and packaged Python Backend.

To launch:
Run FaceRecognition.Desktop.exe
"@
} else {
    $ReadmeContent = @"
Face Recognition Service - Phase 2A Publish

This folder contains the published WPF Desktop Shell and React Frontend.

NOTE: 
This is a Phase 2A intermediate build.
The Python backend (FaceBackend.exe) is not yet packaged.
When running FaceRecognition.Desktop.exe from this folder, it will automatically fallback to running python backend/main.py from the repository root.
Do not distribute this folder to end users without the repository.

To launch:
Run FaceRecognition.Desktop.exe
"@
}
Set-Content -Path $ReadmePath -Value $ReadmeContent -Force

Write-Host "Desktop publish completed successfully." -ForegroundColor Green
Write-Host "Output is located at: $PublishOutputDir"
