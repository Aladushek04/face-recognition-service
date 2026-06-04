# Desktop Migration Plan

This document is the working plan for moving the project from a local browser
app to a stable desktop application. It is intentionally staged: reliability
comes before packaging, and packaging comes before replacing the desktop shell.

## Current Direction

Target architecture:

```text
React frontend
  -> universal API client
  -> local FastAPI backend
  -> scripts / SQLite / FAISS / ML / StashDB

Desktop shell
  -> starts Python backend
  -> waits for /api/health
  -> opens the React UI
  -> exposes logs, paths, and app lifecycle controls
```

Short-term shell: Electron.

Possible later shell: WebView2 with WinUI, WPF, or WinForms.

## Non-Negotiable Rules

- Keep the browser-local mode working at every stage.
- Keep all destructive operations behind dry-run/apply flows.
- Do not commit heavy runtime data: actor DB, actor photos, videos, FAISS indexes,
  embeddings, downloaded ML models, thumbnails, uploads.
- Prefer backend API/job orchestration over launching scripts directly from UI.
- Long tasks must expose status, progress, logs, exit code, and cancellation where
  practical.
- The desktop app must start and stop the backend predictably.
- The desktop shell is replaceable; React and FastAPI must not depend on Electron.

## Phase 0 - Stabilize The Existing App

Goal: make the current browser-based app dependable enough to wrap.

Tasks:

- Finish critical video workflows: scan, analyze, reanalyze, StashDB link,
  rename, thumbnail fallback, actor confirmation.
- Keep maintenance scripts safe and repeatable.
- Ensure `.env.example`, README, and `.gitignore` reflect local HDD paths and
  ignored heavy runtime data.
- Keep `npm run build` and `python -m compileall backend scripts` passing.

Acceptance criteria:

- The service runs via `start_service`.
- Browser UI works at `http://127.0.0.1:3000`.
- Backend health works at `http://127.0.0.1:8000/api/health`.
- Rebuild index, repair empty actors, cleanup, and video reanalysis are usable
  from scripts.

## Phase 1 - Maintenance Job API

Goal: move script orchestration behind stable FastAPI endpoints.

Backend deliverables:

- Job model with fields:
  - `id`
  - `type`
  - `status`
  - `created_at`
  - `started_at`
  - `finished_at`
  - `progress`
  - `exit_code`
  - `command`
  - `dry_run`
  - `log_path`
  - `error`
- Endpoints:
  - `GET /api/tools/jobs`
  - `GET /api/tools/jobs/{job_id}`
  - `GET /api/tools/jobs/{job_id}/logs`
  - `POST /api/tools/jobs/{job_type}`
  - `POST /api/tools/jobs/{job_id}/cancel`
- Supported job types:
  - `build_index`
  - `repair_empty_actor_photos`
  - `cleanup_actors`
  - `cleanup_empty_actor_dirs`
  - `cleanup_images`
  - `scrape_stashdb`

Implementation notes:

- Use subprocesses first; do not rewrite all script logic immediately.
- Persist job metadata under runtime data, not repo data:
  `BASE_DIR/data/jobs`.
- Capture stdout/stderr to log files.
- Run one heavy ML/index job at a time unless explicitly configured otherwise.

Acceptance criteria:

- Every supported job can run as dry-run from API.
- Apply jobs require explicit `apply=true`.
- Logs are readable while the job is still running.
- A failed script surfaces a non-zero exit code and useful error text.

## Phase 2 - Maintenance UI In React

Goal: expose the job API in the existing frontend before desktop packaging.

Views:

- Tools dashboard
- Job detail drawer/modal
- Live log viewer
- Dry-run preview
- Apply confirmation
- Index status panel
- Runtime paths panel

UI principles:

- Material Design 3 structure.
- Liquid glass only as a restrained surface treatment, not visual noise.
- Stable card sizes, predictable controls, clear danger states.
- Long logs should be readable and scrollable.
- Destructive actions must be visually distinct and require confirmation.

Acceptance criteria:

- A user can repair empty actor photos from UI.
- A user can rebuild the FAISS index from UI.
- A user can run cleanup dry-run, inspect logs, then apply.
- UI remains usable while a job runs.
- Browser mode still works without Electron.

## Phase 3 - Electron Shell Prototype

Goal: create the first desktop wrapper without changing core app logic.

Deliverables:

- `desktop/electron` workspace.
- Main process that:
  - finds a free backend port;
  - starts Python backend;
  - waits for `/api/health`;
  - opens the React UI;
  - forwards backend URL to the renderer;
  - stops backend on exit.
- Development mode:
  - use Vite dev server.
- Production mode:
  - use built frontend files.

Acceptance criteria:

- `npm run desktop:dev` opens the app window and starts backend.
- Closing the app stops the backend process.
- Backend startup failure shows a readable desktop error screen.
- Browser mode is unaffected.

## Phase 4 - Desktop Packaging

Goal: build a distributable Windows app.

Packaging direction:

- Start with a portable folder distribution, not a fragile single-file exe.
- Package Electron shell and frontend.
- Decide separately how Python is provided:
  - installed Python;
  - bundled embedded Python;
  - PyInstaller backend bundle.

Recommended first package:

```text
FaceService/
  FaceService.exe
  resources/
  backend/
  frontend/
  scripts/
  runtime/
```

Acceptance criteria:

- App launches on a clean test Windows machine with documented prerequisites.
- Runtime paths can be configured.
- No actor DB, models, videos, FAISS indexes, or thumbnails are packaged.
- Logs are available from the UI and from disk.

## Phase 5 - WebView2 Shell Evaluation

Goal: decide whether replacing Electron is worth it.

WebView2 constraints:

- Use Evergreen WebView2 Runtime for most users.
- Installer must detect/install WebView2 Runtime if missing.
- Shell must implement the same contract as Electron:
  - start backend;
  - wait for health;
  - show React UI;
  - manage logs and lifecycle.

Acceptance criteria:

- A WebView2 prototype can open the same built React UI.
- Backend lifecycle behavior matches Electron.
- Installer/runtime story is simpler or lighter enough to justify migration.

## Phase 6 - Hardening

Goal: make the desktop app boringly reliable.

Tasks:

- Port conflict handling.
- Backend crash recovery.
- Job cancellation and stale job cleanup.
- Log rotation.
- Runtime path validation.
- Health diagnostics screen.
- Update README and troubleshooting docs.
- Smoke test script for browser and desktop modes.

Acceptance criteria:

- User can diagnose missing models, missing StashDB key, missing WebView2,
  missing Python/backend, broken FAISS index, and unavailable video paths from UI.
- App can recover from interrupted index/video jobs.
- Packaging and startup steps are documented.

## Working Order

Default order for future work:

1. Keep browser app passing checks.
2. Add backend job API.
3. Add React maintenance UI.
4. Add Electron shell.
5. Package portable app.
6. Evaluate WebView2 replacement.

