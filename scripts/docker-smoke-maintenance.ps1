Write-Host "=== Running Docker Maintenance Smoke Tests ===" -ForegroundColor Cyan
Write-Host "WARNING: Tests use synthetic/temp fixtures only. No real data or network is touched." -ForegroundColor Yellow

docker compose run --rm backend python -m unittest backend.tests.test_docker_maintenance_smoke -v
if ($LASTEXITCODE -ne 0) { Write-Error "Smoke tests failed"; exit $LASTEXITCODE }

Write-Host "`n=== Smoke tests passed successfully! ===" -ForegroundColor Green
