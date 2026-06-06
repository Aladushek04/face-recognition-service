# Docker Dev/Test Environment

This project includes a CPU-only Docker environment for backend development and testing.

## Prerequisites

- Docker Desktop or WSL2 with Docker installed
- No GPU configuration is required for this CPU-only dev runtime

## Setup

1. (Optional) Copy `.env.docker.local.example` to `.env.docker.local` and configure your local overrides.
2. If you want to use existing models instead of downloading them, set `MODELS_DIR` in `.env.docker.local` to the absolute path of your models directory.

## Developer Scripts

For convenience, we provide PowerShell scripts to run common Docker workflows safely.

### Run full Docker tests
Builds the container and runs all compilation checks and unit tests.
```powershell
powershell -ExecutionPolicy Bypass -File scripts\docker-test.ps1
```

### Run maintenance smoke only
Runs just the synthetic maintenance smoke tests.
```powershell
powershell -ExecutionPolicy Bypass -File scripts\docker-smoke-maintenance.ps1
```

### Run backend service
Starts the backend container and provides the health check URL.
```powershell
powershell -ExecutionPolicy Bypass -File scripts\docker-run-backend.ps1
# To run detached in the background:
powershell -ExecutionPolicy Bypass -File scripts\docker-run-backend.ps1 -Detached
```

### Stop backend service
```powershell
docker compose down --remove-orphans
```

## Important Reminders

- **CPU Only**: Docker dev runtime is currently CPU-only. GPU support is planned for a future phase.
- **No Real Data**: Do not mount your real `D:\FaceService` as writable.
- **Not a Production Substitute**: This Docker setup does not replace final Windows VM or Installer testing.

## Data Isolation

The Docker environment isolates runtime data to prevent overwriting your real `D:\FaceService` directory.
All writable volumes (jobs, logs, db, faiss_index) are mapped to `./.docker_data/` which is ignored by Git.
