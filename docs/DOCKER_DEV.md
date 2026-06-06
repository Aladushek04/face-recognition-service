# Docker Dev/Test Environment

This project includes a CPU-only Docker environment for backend development and testing.

## Prerequisites

- Docker Desktop or WSL2 with Docker installed
- No GPU configuration is required for this CPU-only dev runtime

## Setup

1. (Optional) Copy `.env.docker.local.example` to `.env.docker.local` and configure your local overrides.
2. If you want to use existing models instead of downloading them, set `MODELS_DIR` in `.env.docker.local` to the absolute path of your models directory.

## Commands

### Build the backend container
```powershell
docker compose build backend
```

### Run the backend service
```powershell
docker compose up backend
```

### Run unit tests and compilation checks
```powershell
docker compose run --rm backend python -m compileall backend scripts
docker compose run --rm backend python -m unittest backend.tests.test_maintenance_hotfix backend.tests.test_system_status_paths -v
```

### Run a safe maintenance job (Dry-run)
```powershell
docker compose run --rm backend python backend/main.py --run-job scrape_stashdb --dry-run
```

## Data Isolation

The Docker environment isolates runtime data to prevent overwriting your real `D:\FaceService` directory.
All writable volumes (jobs, logs, db, faiss_index) are mapped to `./.docker_data/` which is ignored by Git.
