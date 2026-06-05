# Desktop Prototype

Phase 3 adds an Electron shell prototype. It is not an installer yet.

## Install

```powershell
cd F:\SillyTavern\face-recognition-service
npm run desktop:install
```

## Development Run

```powershell
npm run desktop:dev
```

Development mode opens the Vite frontend at `http://127.0.0.1:3000` and starts
the Python backend on `127.0.0.1` with a free port selected by Electron.

## Production-Style Smoke Test

```powershell
npm run frontend:build
npm --prefix desktop/electron run smoke
```

Smoke mode opens the built `frontend/dist/index.html`, starts the backend,
waits for `/api/health`, verifies that React rendered into `#root`, and exits
automatically.

## Portable Build

Build a first portable Windows package:

```powershell
npm run desktop:build
```

Output:

```text
desktop/electron/dist/
  FaceRecognitionService-0.1.0-portable-x64.exe
  win-unpacked/
```

The portable build includes:

- Electron shell.
- Built React frontend from `frontend/dist`.
- Backend Python source from `backend`.
- Project scripts from `scripts`.
- Small static icons from `data/icons`.

The portable build does not bundle Python yet. The target machine still needs a
working Python environment with backend dependencies installed, or
`FACE_SERVICE_PYTHON` must point to the intended Python executable.

For portable `file://` loading the frontend is built with relative assets. If
the app window is blank, rebuild with `npm run desktop:build` and run the
portable smoke test again.

## Runtime Data

The desktop shell does not package actor databases, videos, FAISS indexes,
thumbnails, uploads, or downloaded ML models. Runtime data stays outside the app
through `.env` paths such as:

```env
BASE_DIR=D:\FaceService
ACTORS_DIR=D:\FaceService\actors
FAISS_INDEX_DIR=D:\FaceService\data\faiss_index
VIDEOS_DIR=D:\Videos
```

## Notes

- `FACE_SERVICE_PYTHON` can override the Python executable used by Electron.
- Backend startup logs are written to `logs/desktop-backend-*.log`.
- The desktop shell shows a startup screen while it prepares logs, finds a free
  backend port, checks Python, starts the backend, waits for health, and loads
  the UI.
- The app menu has shortcuts for opening the logs folder and the current backend
  log.
- If Python is missing, backend startup times out, or the backend process exits
  unexpectedly, the shell shows a readable failure screen with the log path.
- The React frontend receives the backend URL through `?apiBaseUrl=...`, so
  ordinary React components stay independent of Electron APIs.
