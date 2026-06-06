param(
    [switch]$Detached
)

Write-Host "=== Starting Docker Backend ===" -ForegroundColor Cyan
Write-Host "Health check URL: http://127.0.0.1:8000/api/health" -ForegroundColor Yellow
Write-Host "To stop the backend, run: docker compose down --remove-orphans" -ForegroundColor Yellow
Write-Host ""

if ($Detached) {
    docker compose up -d backend
} else {
    docker compose up backend
}
