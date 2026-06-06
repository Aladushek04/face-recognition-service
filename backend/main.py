"""FastAPI application entry point."""

import sys
from pathlib import Path
import subprocess
import threading
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

ALLOWED_JOBS = {
    "cleanup_actors": "jobs.cleanup_actors",
    "cleanup_empty_actor_dirs": "jobs.cleanup_empty_actor_dirs",
    "cleanup_images": "jobs.cleanup_images",
    "repair_empty_actor_photos": "jobs.repair_empty_actor_photos",
    "scrape_stashdb": "jobs.scrape_stashdb",
    "build_index": "jobs.build_index",
}


def _run_job_from_args() -> None:
    job_name = sys.argv[2]
    job_args = sys.argv[3:]

    if job_name not in ALLOWED_JOBS:
        print(f"ERROR: Unknown or unauthorized job '{job_name}'", file=sys.stderr)
        sys.exit(1)

    import importlib
    try:
        module = importlib.import_module(ALLOWED_JOBS[job_name])
        exit_code = module.main(job_args)
        sys.exit(exit_code)
    except Exception as e:
        print(f"ERROR: Failed to run job '{job_name}': {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__" and len(sys.argv) >= 3 and sys.argv[1] == "--run-job":
    _run_job_from_args()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from config import settings
from routes import upload, actors, stashdb, videos, tools, system, desktop
from database.schema import init_db

_index_rebuild_state = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "exit_code": None,
    "message": None,
}
_index_rebuild_lock = threading.Lock()

# Create the FastAPI app
app = FastAPI(
    title="Face Recognition Service",
    description="Local self-hosted face recognition for actor/actress identification",
    version="1.0.1",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router)
app.include_router(actors.router)
app.include_router(stashdb.router)
app.include_router(videos.router)
app.include_router(tools.router)
app.include_router(system.router)
app.include_router(desktop.router)

# Mount static files for icons
icons_dir = Path(__file__).parent.parent / "data" / "icons"
if icons_dir.exists():
    app.mount("/api/icons", StaticFiles(directory=str(icons_dir)), name="icons")

# Mount static files for thumbnails
try:
    thumbnails_dir = Path(settings.base_dir) / "thumbnails"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/api/thumbnails", StaticFiles(directory=str(thumbnails_dir)), name="thumbnails")
except Exception as e:
    print(f"[Startup Warning] Could not create or mount thumbnails directory: {e}")



@app.on_event("startup")
async def startup_event():
    """Initialize database and models on startup."""
    try:
        # Initialize database
        init_db()
        from database.schema import get_db_path
        reset_count = videos.reset_interrupted_processing_videos(get_db_path())
        if reset_count:
            print(f"[Startup] Reset {reset_count} interrupted video processing jobs")
    except Exception as e:
        print(f"[Startup Warning] Could not initialize database: {e}")

    # Check missing data
    is_missing_data = False
    try:
        if not settings.base_dir.exists():
            is_missing_data = True
        else:
            settings.actors_dir.mkdir(parents=True, exist_ok=True)
            settings.faiss_index_dir.mkdir(parents=True, exist_ok=True)
            (settings.base_dir / "data" / "uploads").mkdir(parents=True, exist_ok=True)
            (settings.base_dir / "models").mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[Startup Warning] Could not create external directories: {e}")
        is_missing_data = True

    if not settings.faiss_index_path.exists():
        is_missing_data = True

    if not is_missing_data:
        # Generate missing thumbnails in background thread
        import threading
        from routes.videos import generate_missing_thumbnails
        threading.Thread(target=generate_missing_thumbnails, daemon=True).start()

        # Preload ML models
        print("Preloading face detection and recognition models...")
        try:
            from models.face_detector import FaceDetector
            FaceDetector()
        except Exception as e:
            print(f"[Startup Warning] Could not preload models: {e}")
    else:
        print("[Startup Warning] Missing required external data. Skipping model preload.")

    print("=" * 60)
    print("Face Recognition Service starting...")
    print(f"  Actors directory: {settings.actors_dir}")
    print(f"  FAISS index: {settings.faiss_index_path}")
    print(f"  Server: {settings.host}:{settings.port}")
    print("=" * 60)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    from models.face_detector import FaceDetector
    from models.vector_store import VectorStore
    from database import actor_db

    errors = []
    
    # Check basic paths
    if not settings.base_dir.exists():
        errors.append(f"baseDir missing: {settings.base_dir}")
    if not settings.actors_dir.exists():
        errors.append(f"actorsDir missing: {settings.actors_dir}")
    if not settings.faiss_index_dir.exists():
        errors.append(f"faissIndexDir missing: {settings.faiss_index_dir}")
    if not settings.faiss_index_path.exists():
        errors.append(f"FAISS index file missing: {settings.faiss_index_path}")
    
    warnings = []
    if not settings.videos_dir or not settings.videos_dir.exists():
        warnings.append(f"Videos directory not found: {settings.videos_dir}")

    # Attempt DB read safely
    actors_count = 0
    if not errors:
        try:
            actors_count = actor_db.get_actors_count()
        except Exception as e:
            errors.append(f"Database unavailable: {e}")

    model_loaded = False
    faiss_available = False
    index_size = 0

    if not errors:
        try:
            detector = FaceDetector()
            model_loaded = detector.model_loaded
        except Exception as e:
            errors.append(f"Models unavailable: {e}")

        try:
            vector_store = VectorStore()
            if not vector_store.is_loaded:
                vector_store.load_index()
            faiss_available = vector_store.is_loaded
            index_size = vector_store.index_size
        except Exception as e:
            errors.append(f"VectorStore error: {e}")

    if errors or actors_count == 0 or not faiss_available:
        return JSONResponse(
            status_code=200,
            content={
                "status": "config_required",
                "actors_count": actors_count,
                "index_size": index_size,
                "faiss_available": faiss_available,
                "model_loaded": model_loaded,
                "errors": errors,
                "warnings": warnings
            }
        )
    else:
        status = "healthy"

    return {
        "status": status,
        "actors_count": actors_count,
        "index_size": index_size,
        "faiss_available": faiss_available,
        "model_loaded": model_loaded,
        "errors": errors,
        "warnings": warnings
    }


@app.get("/api/index/status")
async def index_status():
    """Return index and image-cache status without starting a rebuild."""
    from database import actor_db

    index_path = settings.faiss_index_path
    id_map_path = settings.faiss_id_map_path
    embedding_cache_dir = settings.base_dir / "data" / "embeddings"

    def file_info(path: Path) -> dict:
        if not path.exists():
            return {"exists": False, "size_bytes": 0, "updated_at": None}
        stat = path.stat()
        return {
            "exists": True,
            "size_bytes": stat.st_size,
            "updated_at": stat.st_mtime,
        }

    cached_embeddings = 0
    if embedding_cache_dir.exists():
        cached_embeddings = sum(1 for _ in embedding_cache_dir.glob("*.npy"))

    return {
        "actors_count": actor_db.get_actors_count(),
        "actor_images_count": actor_db.get_actor_images_count(),
        "cached_embedding_files": cached_embeddings,
        "faiss_index": file_info(index_path),
        "faiss_id_map": file_info(id_map_path),
        "rebuild": dict(_index_rebuild_state),
    }


def _run_index_rebuild(refresh_cache: bool) -> None:
    script_path = settings.base_dir / "face-recognition-service" / "scripts" / "build_index.py"
    if not script_path.exists():
        script_path = Path(__file__).parent.parent / "scripts" / "build_index.py"

    command = [sys.executable, str(script_path)]
    if refresh_cache:
        command.append("--refresh-cache")

    try:
        import os
        kwargs = {}
        if os.name == "nt":
            create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            kwargs["creationflags"] = create_no_window
        result = subprocess.run(command, cwd=str(script_path.parent.parent), check=False, **kwargs)
        message = "completed" if result.returncode == 0 else f"failed with exit code {result.returncode}"
        exit_code = result.returncode
    except Exception as exc:
        message = str(exc)
        exit_code = -1

    with _index_rebuild_lock:
        _index_rebuild_state.update({
            "running": False,
            "finished_at": time.time(),
            "exit_code": exit_code,
            "message": message,
        })


@app.post("/api/index/rebuild")
async def rebuild_index(refresh_cache: bool = False):
    """Start a background FAISS index rebuild."""
    with _index_rebuild_lock:
        if _index_rebuild_state["running"]:
            return {"status": "already_running", "rebuild": dict(_index_rebuild_state)}

        _index_rebuild_state.update({
            "running": True,
            "started_at": time.time(),
            "finished_at": None,
            "exit_code": None,
            "message": "started",
        })

    thread = threading.Thread(target=_run_index_rebuild, args=(refresh_cache,), daemon=True)
    thread.start()
    return {"status": "started", "rebuild": dict(_index_rebuild_state)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
