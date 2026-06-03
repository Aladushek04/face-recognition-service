"""Upload and face assignment route handlers."""

import uuid
import time
import numpy as np
import sqlite3
import shutil
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Body
from fastapi.responses import JSONResponse, FileResponse
import filetype

from models.face_detector import FaceDetector
from models.vector_store import VectorStore
from database import actor_db
from models import UploadResponse, FaceMatch, BatchUploadResponse
from config import settings

router = APIRouter(prefix="/api", tags=["upload"])
_vector_store: VectorStore | None = None


def get_face_detector() -> FaceDetector:
    """Get the singleton face detector."""
    return FaceDetector()


def get_vector_store() -> VectorStore:
    """Get the singleton vector store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    if not _vector_store.is_loaded:
        _vector_store.load_index()
    return _vector_store


def make_face_match(actor_id: int, confidence: float, bbox: list[int]) -> FaceMatch | None:
    actor = actor_db.get_actor(actor_id)
    if not actor:
        return None
    actor_image_url = get_actor_preview_url(actor_id)
    return FaceMatch(
        actor_id=actor_id,
        actor_name=actor["name"],
        confidence=confidence,
        face_bbox=bbox,
        actor_image_url=actor_image_url,
    )


def get_actor_preview_url(actor_id: int) -> str | None:
    """Return the newest local reference image URL for an actor."""
    for image in actor_db.get_actor_images(actor_id):
        if Path(image["file_path"]).exists():
            return f"/api/actors/{actor_id}/images/{image['id']}"
    return None


def dedupe_matches(matches: list[FaceMatch], limit: int = 5) -> list[FaceMatch]:
    best_by_actor: dict[int, FaceMatch] = {}
    for match in matches:
        current = best_by_actor.get(match.actor_id)
        if current is None or match.confidence > current.confidence:
            best_by_actor[match.actor_id] = match
    return sorted(best_by_actor.values(), key=lambda item: item.confidence, reverse=True)[:limit]


def validate_image(file: UploadFile) -> bool:
    """Validate that the uploaded file is an image."""
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        return False

    # Also check file magic
    try:
        kind = filetype.guess_bytes(file.file.read(4096))
        file.file.seek(0)
        if kind is None or kind.mime.split("/")[0] != "image":
            return False
    except Exception:
        pass

    return True


@router.post("/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """Upload a single image and get face recognition results."""
    start_time = time.time()

    # Validate file
    if not file.filename or not file.filename.strip():
        raise HTTPException(status_code=400, detail="No filename provided")

    # Validate image type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Only images are allowed.",
        )

    # Read file content
    content = await file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB",
        )

    # Save to uploads directory
    image_id = uuid.uuid4().hex
    temp_dir = settings.base_dir / "data" / "uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    file_ext = Path(file.filename).suffix or ".jpg"
    temp_path = temp_dir / f"{image_id}{file_ext}"

    with open(temp_path, "wb") as f:
        f.write(content)

    keep_file = False
    try:
        # Detect faces
        detector = get_face_detector()
        if not detector.model_loaded:
            raise HTTPException(
                status_code=503,
                detail="Face detection model not loaded. Please check logs.",
            )

        faces = detector.detect_faces_from_path(temp_path)
        if not faces:
            return UploadResponse(
                image_id=image_id,
                filename=file.filename,
                faces_detected=0,
                matches=[],
                closest_matches=[],
                processing_time_ms=(time.time() - start_time) * 1000,
            )

        # We found faces, so keep the uploaded photo so the user can reassign faces if needed
        keep_file = True

        # Search against database
        vector_store = get_vector_store()
        all_matches: list[FaceMatch] = []
        closest_matches: list[FaceMatch] = []

        for face in faces:
            embedding = np.array(face["embedding"], dtype=np.float32)
            closest_results = vector_store.search(
                embedding,
                k=5,
                threshold=0.0,
            )
            for actor_id, confidence in closest_results:
                match = make_face_match(actor_id, confidence, face["bbox"])
                if not match:
                    continue
                if confidence >= settings.face_recognition_threshold:
                    all_matches.append(match)
                else:
                    closest_matches.append(match)

        # Sort by confidence
        all_matches = dedupe_matches(all_matches)
        closest_matches = dedupe_matches(closest_matches)

        return UploadResponse(
            image_id=image_id,
            filename=file.filename,
            faces_detected=len(faces),
            matches=all_matches,
            closest_matches=closest_matches,
            all_faces=[face["bbox"] for face in faces] if faces else [],
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")
    finally:
        # Clean up temp file only if we don't need to keep it
        if not keep_file and temp_path.exists():
            temp_path.unlink()


@router.post("/upload/batch", response_model=BatchUploadResponse)
async def upload_batch(files: list[UploadFile] = File(...)):
    """Upload multiple images and get face recognition results for each."""
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per batch")

    results = []
    for file in files:
        start_time = time.time()

        if not file.filename or not file.filename.strip():
            continue

        if not file.content_type or not file.content_type.startswith("image/"):
            continue

        content = await file.read()
        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            continue

        image_id = uuid.uuid4().hex
        temp_dir = settings.base_dir / "data" / "uploads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        file_ext = Path(file.filename).suffix or ".jpg"
        temp_path = temp_dir / f"{image_id}{file_ext}"

        with open(temp_path, "wb") as f:
            f.write(content)

        keep_file = False
        try:
            detector = get_face_detector()
            if not detector.model_loaded:
                raise HTTPException(
                    status_code=503,
                    detail="Face detection model not loaded.",
                )

            faces = detector.detect_faces_from_path(temp_path)
            if not faces:
                results.append(UploadResponse(
                    image_id=image_id,
                    filename=file.filename,
                    faces_detected=0,
                    matches=[],
                    closest_matches=[],
                    processing_time_ms=(time.time() - start_time) * 1000,
                ))
                continue

            # We found faces, so keep the uploaded photo
            keep_file = True

            vector_store = get_vector_store()
            all_matches: list[FaceMatch] = []
            closest_matches: list[FaceMatch] = []

            for face in faces:
                embedding = np.array(face["embedding"], dtype=np.float32)
                closest_results = vector_store.search(
                    embedding,
                    k=5,
                    threshold=0.0,
                )
                for actor_id, confidence in closest_results:
                    match = make_face_match(actor_id, confidence, face["bbox"])
                    if not match:
                        continue
                    if confidence >= settings.face_recognition_threshold:
                        all_matches.append(match)
                    else:
                        closest_matches.append(match)

            all_matches = dedupe_matches(all_matches)
            closest_matches = dedupe_matches(closest_matches)

            results.append(UploadResponse(
                image_id=image_id,
                filename=file.filename,
                faces_detected=len(faces),
                matches=all_matches,
                closest_matches=closest_matches,
                all_faces=[face["bbox"] for face in faces] if faces else [],
                processing_time_ms=(time.time() - start_time) * 1000,
            ))

        except Exception as e:
            results.append(UploadResponse(
                image_id=image_id,
                filename=file.filename,
                faces_detected=0,
                matches=[],
                closest_matches=[],
                processing_time_ms=(time.time() - start_time) * 1000,
            ))
        finally:
            if not keep_file and temp_path.exists():
                temp_path.unlink()

    return BatchUploadResponse(results=results)


@router.get("/uploads/{image_id}")
def get_uploaded_image(image_id: str):
    """Retrieve a persistently cached uploaded image by ID."""
    temp_dir = settings.base_dir / "data" / "uploads"
    for path in temp_dir.glob(f"{image_id}.*"):
        if path.exists():
            return FileResponse(path)
    raise HTTPException(status_code=404, detail="Uploaded image not found")


@router.post("/uploads/{image_id}/assign")
async def assign_uploaded_face(
    image_id: str,
    actor_id: Optional[int] = Body(None),
    face_bbox: list[int] = Body(...),
    new_actor_name: Optional[str] = Body(None),
    new_actor_gender: Optional[str] = Body(None),
    new_actor_birth_year: Optional[int] = Body(None),
):
    """Assign a face bbox from an uploaded photo to a new or existing actor."""
    temp_dir = settings.base_dir / "data" / "uploads"
    file_path = None
    for path in temp_dir.glob(f"{image_id}.*"):
        if path.exists():
            file_path = path
            break

    if not file_path:
        raise HTTPException(status_code=404, detail="Uploaded image not found")

    # 1. Resolve or create actor
    if actor_id is None:
        if not new_actor_name or not new_actor_name.strip():
            raise HTTPException(status_code=400, detail="Name is required for new actor")
        
        # Create actor
        try:
            actor_id = actor_db.add_actor(
                name=new_actor_name.strip(),
                gender=new_actor_gender,
                birth_year=new_actor_birth_year,
                tags=["assigned"]
            )
            # Create actor directory
            actor_dir = settings.actors_dir / new_actor_name.strip().replace(" ", "_")
            actor_dir.mkdir(parents=True, exist_ok=True)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Actor already exists")
    
    actor = actor_db.get_actor(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")

    # 2. Copy photo to actor directory
    actor_dir = settings.actors_dir / actor["name"].replace(" ", "_")
    actor_dir.mkdir(parents=True, exist_ok=True)
    
    file_ext = file_path.suffix or ".jpg"
    new_filename = f"assigned_{uuid.uuid4().hex}{file_ext}"
    new_path = actor_dir / new_filename
    
    try:
        shutil.copy2(file_path, new_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to copy image: {str(e)}")

    # 3. Save to SQLite actor_images
    new_image_id = actor_db.add_actor_image(
        actor_id=actor_id,
        filename=new_filename,
        file_path=str(new_path),
    )

    # 4. Extract face embedding for this specific bbox
    import cv2
    detector = get_face_detector()
    faces_detected = 0
    
    try:
        # Load image with opencv
        image_bytes = np.fromfile(str(new_path), dtype=np.uint8)
        img = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to read image")
            
        faces = detector.detect_faces(img)
        if faces:
            # Find the face closest to the provided face_bbox
            best_face = None
            best_iou = 0.0
            
            def calculate_iou(boxA, boxB):
                xA = max(boxA[0], boxB[0])
                yA = max(boxA[1], boxB[1])
                xB = min(boxA[2], boxB[2])
                yB = min(boxA[3], boxB[3])
                interArea = max(0, xB - xA) * max(0, yB - yA)
                boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
                boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
                unionArea = boxAArea + boxBArea - interArea
                return interArea / max(unionArea, 1e-6)

            for face in faces:
                score = calculate_iou(face["bbox"], face_bbox)
                if score > best_iou:
                    best_iou = score
                    best_face = face
            
            # Fallback to first face if IOU is very low or no best face matched
            if not best_face and len(faces) == 1:
                best_face = faces[0]
            elif not best_face:
                # Find face with minimum center-point distance
                min_dist = float('inf')
                center_ref = [(face_bbox[0] + face_bbox[2])/2, (face_bbox[1] + face_bbox[3])/2]
                for face in faces:
                    f_box = face["bbox"]
                    center_f = [(f_box[0] + f_box[2])/2, (f_box[1] + f_box[3])/2]
                    dist = ((center_ref[0] - center_f[0])**2 + (center_ref[1] - center_f[1])**2)**0.5
                    if dist < min_dist:
                        min_dist = dist
                        best_face = face
            
            if best_face:
                embedding = best_face["embedding"].astype(np.float32)
                
                # Cache embedding (.npy)
                cache_dir = settings.base_dir / "data" / "embeddings"
                cache_dir.mkdir(parents=True, exist_ok=True)
                cache_path = cache_dir / f"actor_image_{new_image_id}.npy"
                np.save(cache_path, np.array([embedding], dtype=np.float32))
                
                # Update DB
                actor_db.update_actor_image_embedding(new_image_id, str(cache_path))
                
                # Update FAISS index
                from routes.actors import get_vector_store as get_actors_vector_store
                vector_store = get_actors_vector_store()
                vector_store.add_vectors([embedding], actor_id)
                vector_store.save_index()
                faces_detected = 1
                
    except Exception as e:
        print(f"Failed to extract/index face embedding: {e}")

    # Optionally clean up source upload file if all faces from it are processed.
    # We will keep it for now so they can assign multiple faces from the same photo.

    return {
        "status": "assigned",
        "actor_id": actor_id,
        "actor_name": actor["name"],
        "faces_indexed": faces_detected
    }
