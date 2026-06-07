[CmdletBinding()]
Param(
    [ValidateSet("cpu", "gpu")]
    [string]$Runtime = "cpu",
    [string]$Version = "v1.0.2",
    [string]$ReleaseName = "",
    [string]$OutputDir = "",
    [string]$OutputRoot = "",
    [switch]$Force = $false,
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

$Version = $Version.Trim()
if ([string]::IsNullOrWhiteSpace($Version)) {
    Write-Error "Version must not be empty."
}
if (-not $Version.StartsWith("v", [System.StringComparison]::OrdinalIgnoreCase)) {
    $Version = "v$Version"
}

if ([string]::IsNullOrWhiteSpace($ReleaseName)) {
    $ReleaseName = "FaceRecognitionService-Portable-$Version-$Runtime"
} elseif ($ReleaseName -match '-(cpu|gpu)$') {
    $ReleaseNameRuntime = $Matches[1]
    if ($ReleaseNameRuntime -ne $Runtime) {
        Write-Error "ReleaseName runtime suffix '$ReleaseNameRuntime' does not match selected runtime '$Runtime'."
    }
} else {
    $ReleaseName = "$ReleaseName-$Runtime"
}
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = $OutputDir
} elseif (-not [string]::IsNullOrWhiteSpace($OutputDir) -and
          -not $OutputRoot.Equals($OutputDir, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Error "Use either -OutputDir or -OutputRoot, not both with different values."
}
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $ResolvedOutputDir = Join-Path $RepoRoot "releases"
} else {
    $ResolvedOutputDir = [System.IO.Path]::GetFullPath($OutputRoot)
}

$ForbiddenInstallerDir = [System.IO.Path]::GetFullPath("F:\VMShare\FaceRecognitionInstaller")
if ($ResolvedOutputDir.Equals($ForbiddenInstallerDir, [System.StringComparison]::OrdinalIgnoreCase) -or
    $ResolvedOutputDir.StartsWith("$ForbiddenInstallerDir\", [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Error "Refusing to write packaging output to protected release directory: $ForbiddenInstallerDir"
}

Write-Host "--- Packaging Portable Release ---"
Write-Host "RepoRoot: $RepoRoot"
Write-Host "Runtime: $Runtime"
Write-Host "Version: $Version"
Write-Host "ReleaseName: $ReleaseName"
Write-Host "OutputDir: $ResolvedOutputDir"

# 1. Build packaged backend
$BuildBackendScript = Join-Path $RepoRoot "scripts\build-backend.ps1"
if (-not (Test-Path $BuildBackendScript)) {
    Write-Error "Backend build script not found: $BuildBackendScript"
}

# 2. Run publish script
$PublishScript = Join-Path $RepoRoot "desktop\wpf\FaceRecognition.Desktop\scripts\publish-desktop.ps1"
if (-not (Test-Path $PublishScript)) {
    Write-Error "Publish script not found: $PublishScript"
}

# 3. Determine publish output directory
$WpfDir = Join-Path $RepoRoot "desktop\wpf\FaceRecognition.Desktop"
$CsprojPath = Join-Path $WpfDir "FaceRecognition.Desktop.csproj"
$TargetFramework = ([xml](Get-Content $CsprojPath)).Project.PropertyGroup.TargetFramework
if (-not $TargetFramework) { $TargetFramework = "net10.0-windows" }
$PublishOutputDir = Join-Path $WpfDir "bin\Release\$TargetFramework\publish"

# 4. Create output directory
$ReleasesDir = $ResolvedOutputDir
$ReleaseTargetDir = Join-Path $ReleasesDir $ReleaseName
$ZipPath = Join-Path $ReleasesDir "$ReleaseName.zip"
$ChecksumPath = "$ZipPath.sha256"

if ($DryRun) {
    Write-Host "--- Dry Run: no files will be created and no build commands will run ---"
    Write-Host "Backend build: powershell -ExecutionPolicy Bypass -File `"$BuildBackendScript`" -Runtime $Runtime"
    Write-Host "Desktop publish: powershell -ExecutionPolicy Bypass -File `"$PublishScript`" -IncludeBackend"
    Write-Host "Publish output: $PublishOutputDir"
    Write-Host "Release directory: $ReleaseTargetDir"
    Write-Host "ZIP archive: $ZipPath"
    Write-Host "Checksum file: $ChecksumPath"
    exit 0
}

Write-Host "Running build-backend.ps1 for '$Runtime' runtime..."
& $BuildBackendScript -Runtime $Runtime
if ($LASTEXITCODE -ne 0) {
    Write-Error "build-backend.ps1 failed."
    exit $LASTEXITCODE
}

Write-Host "Running publish-desktop.ps1 -IncludeBackend..."
& $PublishScript -IncludeBackend
if ($LASTEXITCODE -ne 0) {
    Write-Error "publish-desktop.ps1 failed."
    exit $LASTEXITCODE
}

if (-not (Test-Path $PublishOutputDir)) {
    Write-Error "Publish output directory not found: $PublishOutputDir"
}

if (-not (Test-Path $ReleasesDir)) {
    New-Item -ItemType Directory -Force -Path $ReleasesDir | Out-Null
}

if ((Test-Path $ReleaseTargetDir) -or (Test-Path $ZipPath) -or (Test-Path $ChecksumPath)) {
    if (-not $Force) {
        Write-Error "Portable output already exists. Re-run with -Force to replace exact targets: $ReleaseTargetDir, $ZipPath, $ChecksumPath"
    }

    Write-Host "Force enabled. Removing exact portable targets only..."
    if (Test-Path $ReleaseTargetDir) {
        Remove-Item -LiteralPath $ReleaseTargetDir -Recurse -Force
    }
    if (Test-Path $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    if (Test-Path $ChecksumPath) {
        Remove-Item -LiteralPath $ChecksumPath -Force
    }
}

New-Item -ItemType Directory -Force -Path $ReleaseTargetDir | Out-Null

# 5. Copy required files
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
Face Recognition Service - Portable Release ($Version)
Runtime channel: $Runtime

== How to Run ==
1. Extract the folder to your preferred location.
2. Double click "FaceRecognition.Desktop.exe".
3. The app will launch the React frontend and automatically start the hidden Python AI backend.

== First-Run Configuration ==
On your first launch, the app will generate a "config.json" file from "config.example.json" in this folder.
You must go to the "Settings" page in the UI to point the app to your external data directories.

== Data Requirements ==
This portable release does NOT bundle user data or models. You must provide:
- <your-face-service-data-folder> for the main service data folder.
- <your-actors-folder> for actor reference photos.
- <your-models-folder> for ONNX face models.
- <your-faiss-index-folder> for FAISS index files.
- <your-videos-folder> for video files.

== System Requirements ==
1. .NET 10 Desktop Runtime: This release is Framework-Dependent. You MUST install the Microsoft .NET 10 Desktop Runtime (x64) to launch the shell.
2. WebView2 Runtime: Required to render the UI. (Pre-installed on Windows 11).
3. Runtime channel:
   - CPU package: Default recommended package for most users. No NVIDIA GPU is required.
   - GPU package: NVIDIA-accelerated package for CUDAExecutionProvider. Install current NVIDIA drivers. If no compatible GPU/CUDA driver is found, the backend falls back to CPUExecutionProvider.

== Logs & Diagnostics ==
Application logs are stored in the "logs/" folder next to the executable.

== Security & Antivirus Warning ==
This folder contains an unsigned PyInstaller packaged Python executable (backend/FaceBackend.exe).
If Windows Security quarantines FaceBackend.exe, only restore or exclude the folder if you trust the source of this build. Verify the SHA256 checksum before running the package.
"@
Set-Content -Path $ReadmePath -Value $ReadmeContent -Encoding ASCII -Force

Write-Host "Files copied."

# 6. Create ZIP
Write-Host "Compressing to $ZipPath..."
Compress-Archive -Path $ReleaseTargetDir -DestinationPath $ZipPath -CompressionLevel Optimal

# 7. Generate SHA256 Checksum
Write-Host "Generating SHA256 Checksums..."
$ZipHash = (Get-FileHash -Path $ZipPath -Algorithm SHA256).Hash
"$ZipHash  $ReleaseName.zip" | Out-File -FilePath $ChecksumPath -Encoding ASCII

Write-Host "--- Portable Release Package Created Successfully! ---" -ForegroundColor Green
Write-Host "Release Directory: $ReleaseTargetDir"
Write-Host "ZIP Archive: $ZipPath"
Write-Host "Checksum File: $ChecksumPath"
