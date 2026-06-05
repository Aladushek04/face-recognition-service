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
waits for `/api/health`, and exits automatically.

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
