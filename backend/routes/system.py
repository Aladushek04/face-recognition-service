"""System diagnostics routes for browser and desktop shells."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from config import settings
from database import actor_db


router = APIRouter(prefix="/api/system", tags=["system"])


def _path_status(path: Path, *, should_exist: bool = True) -> dict[str, Any]:
    exists = path.exists()
    stat = path.stat() if exists else None
    return {
        "path": str(path),
        "exists": exists,
        "is_dir": path.is_dir() if exists else False,
        "is_file": path.is_file() if exists else False,
        "size_bytes": stat.st_size if stat and path.is_file() else None,
        "updated_at": stat.st_mtime if stat else None,
        "required": should_exist,
        "ok": exists if should_exist else True,
    }


def _count_files(path: Path, patterns: tuple[str, ...]) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    total = 0
    for pattern in patterns:
        total += sum(1 for item in path.rglob(pattern) if item.is_file())
    return total


@router.get("/status")
def system_status() -> dict[str, Any]:
    """Return desktop-readiness diagnostics without mutating runtime state."""
    from models.face_detector import FaceDetector
    from models.vector_store import VectorStore

    detector = FaceDetector()
    vector_store = VectorStore()
    if not vector_store.is_loaded:
        vector_store.load_index()

    models_dir = settings.base_dir / "models"
    jobs_dir = settings.base_dir / "data" / "jobs"
    uploads_dir = settings.base_dir / "data" / "uploads"
    thumbnails_dir = settings.base_dir / "thumbnails"
    embeddings_dir = settings.base_dir / "data" / "embeddings"
    db_dir = settings.base_dir / "data" / "db"

    paths = {
        "base_dir": _path_status(settings.base_dir),
        "models_dir": _path_status(models_dir),
        "actors_dir": _path_status(settings.actors_dir),
        "videos_dir": _path_status(settings.videos_dir),
        "faiss_index_dir": _path_status(settings.faiss_index_dir),
        "faiss_index": _path_status(settings.faiss_index_path),
        "faiss_id_map": _path_status(settings.faiss_id_map_path),
        "jobs_dir": _path_status(jobs_dir, should_exist=False),
        "uploads_dir": _path_status(uploads_dir, should_exist=False),
        "thumbnails_dir": _path_status(thumbnails_dir, should_exist=False),
        "embeddings_dir": _path_status(embeddings_dir, should_exist=False),
        "db_dir": _path_status(db_dir, should_exist=False),
    }

    checks = [
        {
            "id": "backend",
            "label": "Backend API",
            "status": "ok",
            "message": f"FastAPI is running on {settings.host}:{settings.port}.",
        },
        {
            "id": "model",
            "label": "Face model",
            "status": "ok" if detector.model_loaded else "error",
            "message": "InsightFace model is loaded." if detector.model_loaded else "InsightFace model is not loaded.",
        },
        {
            "id": "faiss",
            "label": "FAISS index",
            "status": "ok" if paths["faiss_index"]["exists"] and vector_store.index_size > 0 else "warning",
            "message": (
                f"Index contains {vector_store.index_size} vectors."
                if paths["faiss_index"]["exists"]
                else "Index file is missing. Build the FAISS index before recognition."
            ),
        },
        {
            "id": "actors",
            "label": "Actor database",
            "status": "ok" if actor_db.get_actors_count() > 0 else "warning",
            "message": f"{actor_db.get_actors_count()} actors are available.",
        },
        {
            "id": "videos",
            "label": "Video library",
            "status": "ok" if paths["videos_dir"]["exists"] else "warning",
            "message": (
                "Video directory is available."
                if paths["videos_dir"]["exists"]
                else "Video directory is missing or not configured."
            ),
        },
        {
            "id": "stashdb",
            "label": "StashDB API key",
            "status": "ok" if bool(settings.stashdb_api_key) else "warning",
            "message": "StashDB API key is configured." if settings.stashdb_api_key else "STASHDB_API_KEY is not configured.",
        },
    ]

    overall = "ok"
    if any(check["status"] == "error" for check in checks):
        overall = "error"
    elif any(check["status"] == "warning" for check in checks):
        overall = "warning"

    return {
        "status": overall,
        "service": {
            "name": "Face Recognition Service",
            "version": "1.0.0",
            "python": sys.version.split()[0],
            "pid": os.getpid(),
        },
        "server": {
            "host": settings.host,
            "port": settings.port,
            "debug": settings.debug,
            "cors_origins": settings.cors_origins,
        },
        "features": {
            "stashdb_configured": bool(settings.stashdb_api_key),
            "model_loaded": detector.model_loaded,
            "faiss_available": True,
            "browser_mode_supported": True,
            "desktop_mode_supported": True,
        },
        "counts": {
            "actors": actor_db.get_actors_count(),
            "actor_images": actor_db.get_actor_images_count(),
            "faiss_vectors": vector_store.index_size,
            "model_files": _count_files(models_dir, ("*.onnx", "*.param", "*.bin")),
        },
        "paths": paths,
        "checks": checks,
    }
