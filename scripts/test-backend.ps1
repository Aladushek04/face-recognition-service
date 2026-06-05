$env:HOST="127.0.0.1"
$env:PORT="54321"
$env:DESKTOP_MODE="true"
$env:PYTHONIOENCODING="utf-8"
$env:BASE_DIR="D:\FaceService"
$env:ACTORS_DIR="D:\FaceService\actors"
$env:FAISS_INDEX_DIR="D:\FaceService\data\faiss_index"
$env:VIDEOS_DIR="D:\Videos"
$env:CORS_ORIGINS='["https://app.face.local","http://127.0.0.1:3000","http://localhost:3000"]'

$ExePath = "F:\SillyTavern\face-recognition-service\backend\dist\FaceBackend\FaceBackend.exe"
$LogPath = "F:\SillyTavern\face-recognition-service\scripts\test.log"
$ErrLogPath = "F:\SillyTavern\face-recognition-service\scripts\test-err.log"
if (Test-Path $LogPath) { Remove-Item $LogPath }
if (Test-Path $ErrLogPath) { Remove-Item $ErrLogPath }

Write-Host "Starting $ExePath..."
$process = Start-Process -FilePath $ExePath -RedirectStandardOutput $LogPath -RedirectStandardError $ErrLogPath -NoNewWindow -PassThru

Write-Host "Waiting for backend to start..."
Start-Sleep -Seconds 30

Write-Host "Testing health endpoint..."
try {
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:54321/api/health" -Method Get
    $response | ConvertTo-Json
} catch {
    Write-Host "Health check failed: $_"
}

Write-Host "Wait 2 seconds before killing to ensure logs flush..."
Start-Sleep -Seconds 2

Write-Host "Killing backend..."
Stop-Process -Id $process.Id -Force

Write-Host "Checking for GPU Execution Provider logs..."
$logContent = ""
if (Test-Path $LogPath) { $logContent += Get-Content $LogPath -Raw }
if (Test-Path $ErrLogPath) { $logContent += Get-Content $ErrLogPath -Raw }

if ($logContent -match "CUDAExecutionProvider") {
    Write-Host "[PASS] CUDAExecutionProvider found in logs."
} else {
    Write-Host "[FAIL] CUDAExecutionProvider NOT found in logs."
}

if ($logContent -match "Using ONNX providers: \['CPUExecutionProvider'\]") {
    Write-Host "[FAIL] Fallback to CPUExecutionProvider found."
} else {
    Write-Host "[PASS] No pure CPU fallback detected."
}

Write-Host "Done."
