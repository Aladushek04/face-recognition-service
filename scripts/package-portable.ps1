[CmdletBinding()]
Param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

Write-Host "--- Packaging Portable Release ---"
Write-Host "RepoRoot: $RepoRoot"

# 1. Run publish script
$PublishScript = Join-Path $RepoRoot "desktop\wpf\FaceRecognition.Desktop\scripts\publish-desktop.ps1"
if (-not (Test-Path $PublishScript)) {
    Write-Error "Publish script not found: $PublishScript"
}

Write-Host "Running publish-desktop.ps1 -IncludeBackend..."
& $PublishScript -IncludeBackend

# 2. Determine publish output directory
$WpfDir = Join-Path $RepoRoot "desktop\wpf\FaceRecognition.Desktop"
$CsprojPath = Join-Path $WpfDir "FaceRecognition.Desktop.csproj"
$TargetFramework = ([xml](Get-Content $CsprojPath)).Project.PropertyGroup.TargetFramework
if (-not $TargetFramework) { $TargetFramework = "net10.0-windows" }
$PublishOutputDir = Join-Path $WpfDir "bin\Release\$TargetFramework\publish"

if (-not (Test-Path $PublishOutputDir)) {
    Write-Error "Publish output directory not found: $PublishOutputDir"
}

# 3. Create releases directory
$Version = "v1.0.0"
$ReleaseName = "FaceRecognitionService-Portable-$Version"
$ReleasesDir = Join-Path $RepoRoot "releases"
$ReleaseTargetDir = Join-Path $ReleasesDir $ReleaseName

if (-not (Test-Path $ReleasesDir)) {
    New-Item -ItemType Directory -Force -Path $ReleasesDir | Out-Null
}

if (Test-Path $ReleaseTargetDir) {
    Write-Host "Cleaning existing release directory..."
    Remove-Item -Recurse -Force $ReleaseTargetDir
}

New-Item -ItemType Directory -Force -Path $ReleaseTargetDir | Out-Null

# 4. Copy required files
Write-Host "Copying files to $ReleaseTargetDir..."

# WPF Executables, DLLs, and Runtimes
Get-ChildItem -Path $PublishOutputDir | Where-Object { $_.Name -notin @("config.json", "frontend", "backend") } | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $ReleaseTargetDir -Recurse -Force
}

# Frontend
$TargetFrontend = Join-Path $ReleaseTargetDir "frontend"
New-Item -ItemType Directory -Force -Path $TargetFrontend | Out-Null
Copy-Item -Path (Join-Path $PublishOutputDir "frontend\dist") -Destination $TargetFrontend -Recurse -Force

# Backend
$TargetBackend = Join-Path $ReleaseTargetDir "backend"
New-Item -ItemType Directory -Force -Path $TargetBackend | Out-Null
Copy-Item -Path (Join-Path $PublishOutputDir "backend\FaceBackend.exe") -Destination $TargetBackend -Force
Copy-Item -Path (Join-Path $PublishOutputDir "backend\_internal") -Destination $TargetBackend -Recurse -Force

# Create Logs directory
$TargetLogs = Join-Path $ReleaseTargetDir "logs"
New-Item -ItemType Directory -Force -Path $TargetLogs | Out-Null

# Write README
Write-Host "Generating README.txt..."
$ReadmePath = Join-Path $ReleaseTargetDir "README.txt"
$ReadmeContent = @"
Face Recognition Service - Portable Release (v1.0.0)

== How to Run ==
1. Extract the folder to your preferred location.
2. Double click "FaceRecognition.Desktop.exe".
3. The app will launch the React frontend and automatically start the hidden Python AI backend.

== First-Run Configuration ==
On your first launch, the app will generate a "config.json" file from "config.example.json" in this folder.
You must go to the "Settings" page in the UI to point the app to your external data directories.

== Data Requirements ==
This portable release does NOT bundle user data or models. You must provide:
- D:\FaceService (or equivalent) for Faiss indices, Actor photos, and ONNX models.
- D:\Videos (or equivalent) for video files.

== System Requirements ==
1. .NET 10 Desktop Runtime: This release is Framework-Dependent. You MUST install the Microsoft .NET 10 Desktop Runtime (x64) to launch the shell.
2. WebView2 Runtime: Required to render the UI. (Pre-installed on Windows 11).
3. NVIDIA GPU (Optional but highly recommended): The backend supports CUDAExecutionProvider. Ensure you have the latest NVIDIA drivers installed.
   - CPU Fallback: If no compatible GPU/CUDA driver is found, the backend will automatically fallback to CPUExecutionProvider (which is significantly slower).

== Logs & Diagnostics ==
Application logs are stored in the "logs/" folder next to the executable.

== Security & Antivirus Warning ==
This folder contains an unsigned PyInstaller packaged Python executable (backend/FaceBackend.exe).
If Windows Security quarantines FaceBackend.exe, only restore or exclude the folder if you trust the source of this build. Verify the SHA256 checksum before running the package.
"@
Set-Content -Path $ReadmePath -Value $ReadmeContent -Encoding ASCII -Force

Write-Host "Files copied."

# 5. Create ZIP
$ZipPath = Join-Path $ReleasesDir "$ReleaseName.zip"
if (Test-Path $ZipPath) {
    Remove-Item -Force $ZipPath
}

Write-Host "Compressing to $ZipPath..."
Compress-Archive -Path $ReleaseTargetDir -DestinationPath $ZipPath -CompressionLevel Optimal

# 6. Generate SHA256 Checksum
Write-Host "Generating SHA256 Checksums..."
$ChecksumPath = Join-Path $ReleasesDir "$ReleaseName.sha256"

$ZipHash = (Get-FileHash -Path $ZipPath -Algorithm SHA256).Hash
"$ZipHash  $ReleaseName.zip" | Out-File -FilePath $ChecksumPath -Encoding ASCII

Write-Host "--- Portable Release Package Created Successfully! ---" -ForegroundColor Green
Write-Host "Release Directory: $ReleaseTargetDir"
Write-Host "ZIP Archive: $ZipPath"
Write-Host "Checksum File: $ChecksumPath"
