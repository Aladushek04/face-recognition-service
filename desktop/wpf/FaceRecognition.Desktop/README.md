# Face Recognition Desktop Shell

WPF .NET 10 LTS Desktop Shell for Face Recognition Service.

## Dev Mode
1. Run Vite dev server in `/frontend` (if `frontend/dist` is missing):
   ```bash
   npm run dev
   ```
2. Run WPF shell:
   ```bash
   cd desktop/wpf/FaceRecognition.Desktop
   dotnet run
   ```

Backend starts automatically (hidden). No manual backend launch needed.

## Phase 1 Hardcoded Paths
Currently runtime paths are hardcoded for validation:
- `BASE_DIR=D:\FaceService`
- `ACTORS_DIR=D:\FaceService\actors`
- `FAISS_INDEX_DIR=D:\FaceService\data\faiss_index`
- `VIDEOS_DIR=D:\Videos`

## Troubleshooting
- **"Failed to fetch" / "Model Unready"**: Check CORS origins, backend port, or `logs/backend.log`.
- **DevTools**: Open with `F12` in Debug build, or set `FACE_DESKTOP_DEVTOOLS=true`.

## Runtime Requirements
If using framework-dependent publish, .NET 10 Desktop Runtime is required.
If using self-contained publish later, .NET runtime is bundled.

