Write-Host "=== Building Backend Container ===" -ForegroundColor Cyan
docker compose build backend
if ($LASTEXITCODE -ne 0) { Write-Error "Build failed"; exit $LASTEXITCODE }

Write-Host "`n=== Compiling Backend Scripts ===" -ForegroundColor Cyan
docker compose run --rm backend python -m compileall backend scripts
if ($LASTEXITCODE -ne 0) { Write-Error "Compilation failed"; exit $LASTEXITCODE }

Write-Host "`n=== Running Unit Tests (Hotfix & Paths) ===" -ForegroundColor Cyan
docker compose run --rm backend python -m unittest backend.tests.test_maintenance_hotfix backend.tests.test_system_status_paths -v
if ($LASTEXITCODE -ne 0) { Write-Error "Unit tests failed"; exit $LASTEXITCODE }

Write-Host "`n=== Running Docker Maintenance Smoke Tests ===" -ForegroundColor Cyan
docker compose run --rm backend python -m unittest backend.tests.test_docker_maintenance_smoke -v
if ($LASTEXITCODE -ne 0) { Write-Error "Smoke tests failed"; exit $LASTEXITCODE }

Write-Host "`n=== All tests passed successfully! ===" -ForegroundColor Green
