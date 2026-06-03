"""Actor management route handlers."""

import uuid
import sqlite3
import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Query
from fastapi.responses import FileResponse

import numpy as np
from models.vector_store import VectorStore
from database import actor_db
from models import ActorResponse, ActorListResponse
from config import settings

router = APIRouter(prefix="/api/actors", tags=["actors"])

_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get the singleton vector store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    if not _vector_store.is_loaded:
        _vector_store.load_index()
    return _vector_store



def split_form_list(value: Optional[str]) -> list[str]:
    """Parse a comma-separated form field into a clean list."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def get_actor_image_items(actor_id: int) -> list[dict]:
    """Return existing local image metadata for an actor."""
    image_items = []
    for image in actor_db.get_actor_images(actor_id):
        if not Path(image["file_path"]).exists():
            continue
        image_items.append(
            {
                "id": image["id"],
                "filename": image["filename"],
                "url": f"/api/actors/{actor_id}/images/{image['id']}",
                "created_at": image.get("created_at"),
            }
        )
    return image_items


def serialize_actor(actor: dict, include_images: bool = False) -> ActorResponse:
    """Convert a DB actor row into the API response shape."""
    actor_dict = dict(actor)
    for json_field in ("tags", "stashdb_urls", "aliases", "tattoos", "piercings"):
        actor_dict[json_field] = actor_dict.get(json_field) or "[]"
        if isinstance(actor_dict[json_field], str):
            try:
                actor_dict[json_field] = json.loads(actor_dict[json_field])
            except (json.JSONDecodeError, TypeError):
                actor_dict[json_field] = []
    image_items = get_actor_image_items(actor_dict["id"])
    actor_dict["preview_image_url"] = image_items[0]["url"] if image_items else None
    actor_dict["reference_images"] = image_items if include_images else []
    actor_dict["reference_image_count"] = len(image_items)
    return ActorResponse(**actor_dict)


@router.get("", response_model=ActorListResponse)
def list_actors(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    breast_type: Optional[str] = Query(None, pattern="^(FAKE|NATURAL|NA)$"),
    min_scenes: Optional[int] = Query(None, ge=0),
    has_photo: Optional[bool] = None,
):
    """List all actors with pagination and optional filters."""
    actors, total = actor_db.list_actors(
        page=page,
        page_size=page_size,
        search=search,
        breast_type=breast_type,
        min_scenes=min_scenes,
        has_photo=has_photo,
    )

    actor_list = [serialize_actor(actor) for actor in actors]

    return ActorListResponse(
        actors=actor_list,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{actor_id}", response_model=ActorResponse)
def get_actor(actor_id: int):
    """Get actor details by ID."""
    actor = actor_db.get_actor(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")

    return serialize_actor(actor, include_images=True)


@router.post("", response_model=ActorResponse, status_code=201)
def create_actor(
    name: str = Form(...),
    stashdb_id: Optional[str] = Form(None),
    birth_year: Optional[int] = Form(None),
    birthdate: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    aliases: Optional[str] = Form(None),
    scene_count: Optional[int] = Form(None),
    breast_type: Optional[str] = Form(None),
    height_cm: Optional[int] = Form(None),
    measurements: Optional[str] = Form(None),
    cup_size: Optional[str] = Form(None),
    band_size: Optional[int] = Form(None),
    waist_size: Optional[int] = Form(None),
    hip_size: Optional[int] = Form(None),
    country: Optional[str] = Form(None),
    ethnicity: Optional[str] = Form(None),
    eye_color: Optional[str] = Form(None),
    hair_color: Optional[str] = Form(None),
    tattoos: Optional[str] = Form(None),
    piercings: Optional[str] = Form(None),
    career_start_year: Optional[int] = Form(None),
    career_end_year: Optional[int] = Form(None),
    image_url: Optional[str] = Form(None),
    stashdb_urls: Optional[str] = Form(None),
    bio: Optional[str] = Form(None),
    filmography: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
):
    """Create a new actor entry."""
    try:
        actor_id = actor_db.add_actor(
            name=name,
            stashdb_id=stashdb_id,
            birth_year=birth_year,
            birthdate=birthdate,
            gender=gender,
            aliases=split_form_list(aliases),
            scene_count=scene_count,
            breast_type=breast_type,
            height_cm=height_cm,
            measurements=measurements,
            cup_size=cup_size,
            band_size=band_size,
            waist_size=waist_size,
            hip_size=hip_size,
            country=country,
            ethnicity=ethnicity,
            eye_color=eye_color,
            hair_color=hair_color,
            tattoos=split_form_list(tattoos),
            piercings=split_form_list(piercings),
            career_start_year=career_start_year,
            career_end_year=career_end_year,
            image_url=image_url,
            stashdb_urls=stashdb_urls.split(",") if stashdb_urls else [],
            bio=bio,
            filmography=filmography,
            tags=tags.split(",") if tags else [],
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Actor already exists")

    # Create actor directory
    actor_dir = settings.actors_dir / name.replace(" ", "_")
    actor_dir.mkdir(parents=True, exist_ok=True)

    actor = actor_db.get_actor(actor_id)
    return serialize_actor(actor, include_images=True)


@router.put("/{actor_id}", response_model=ActorResponse)
def update_actor(
    actor_id: int,
    name: Optional[str] = Form(None),
    stashdb_id: Optional[str] = Form(None),
    birth_year: Optional[int] = Form(None),
    birthdate: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    aliases: Optional[str] = Form(None),
    scene_count: Optional[int] = Form(None),
    breast_type: Optional[str] = Form(None),
    height_cm: Optional[int] = Form(None),
    measurements: Optional[str] = Form(None),
    cup_size: Optional[str] = Form(None),
    band_size: Optional[int] = Form(None),
    waist_size: Optional[int] = Form(None),
    hip_size: Optional[int] = Form(None),
    country: Optional[str] = Form(None),
    ethnicity: Optional[str] = Form(None),
    eye_color: Optional[str] = Form(None),
    hair_color: Optional[str] = Form(None),
    tattoos: Optional[str] = Form(None),
    piercings: Optional[str] = Form(None),
    career_start_year: Optional[int] = Form(None),
    career_end_year: Optional[int] = Form(None),
    image_url: Optional[str] = Form(None),
    stashdb_urls: Optional[str] = Form(None),
    bio: Optional[str] = Form(None),
    filmography: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
):
    """Update an actor's information."""
    existing = actor_db.get_actor(actor_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Actor not found")

    actor_db.update_actor(
        actor_id=actor_id,
        name=name,
        stashdb_id=stashdb_id,
        birth_year=birth_year,
        birthdate=birthdate,
        gender=gender,
        aliases=split_form_list(aliases) if aliases is not None else None,
        scene_count=scene_count,
        breast_type=breast_type,
        height_cm=height_cm,
        measurements=measurements,
        cup_size=cup_size,
        band_size=band_size,
        waist_size=waist_size,
        hip_size=hip_size,
        country=country,
        ethnicity=ethnicity,
        eye_color=eye_color,
        hair_color=hair_color,
        tattoos=split_form_list(tattoos) if tattoos is not None else None,
        piercings=split_form_list(piercings) if piercings is not None else None,
        career_start_year=career_start_year,
        career_end_year=career_end_year,
        image_url=image_url,
        stashdb_urls=stashdb_urls.split(",") if stashdb_urls else None,
        bio=bio,
        filmography=filmography,
        tags=tags.split(",") if tags else None,
    )

    actor = actor_db.get_actor(actor_id)
    return serialize_actor(actor, include_images=True)


@router.delete("/{actor_id}", status_code=204)
def delete_actor(actor_id: int):
    """Delete an actor and their reference images."""
    if not actor_db.delete_actor(actor_id):
        raise HTTPException(status_code=404, detail="Actor not found")
    
    # Dynamics index: remove actor from FAISS index and save
    try:
        vector_store = get_vector_store()
        vector_store.remove_actor(actor_id)
        vector_store.save_index()
    except Exception as e:
        print(f"Error removing actor from vector store: {e}")
        
    return None


@router.post("/{actor_id}/images", status_code=201)
async def add_actor_image(
    actor_id: int,
    file: UploadFile = File(...),
):
    """Add a reference image for an actor and extract/index its face embeddings."""
    actor = actor_db.get_actor(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")

    # Validate image
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    content = await file.read()

    # Save to actor directory
    actor_dir = settings.actors_dir / actor["name"].replace(" ", "_")
    actor_dir.mkdir(parents=True, exist_ok=True)

    file_ext = Path(file.filename).suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = actor_dir / filename

    with open(file_path, "wb") as f:
        f.write(content)

    image_id = actor_db.add_actor_image(
        actor_id=actor_id,
        filename=filename,
        file_path=str(file_path),
    )

    # Dynamic index: extract faces and add to index
    from models.face_detector import FaceDetector
    detector = FaceDetector()
    
    faces_detected = 0
    message = "Image added successfully"
    
    try:
        faces = detector.detect_faces_from_path(file_path)
        if faces:
            faces_detected = len(faces)
            embeddings = [face["embedding"].astype(np.float32) for face in faces]
            
            # Cache embeddings (.npy)
            cache_dir = settings.base_dir / "data" / "embeddings"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = cache_dir / f"actor_image_{image_id}.npy"
            np.save(cache_path, np.array(embeddings, dtype=np.float32))
            
            # Update DB with embedding path
            actor_db.update_actor_image_embedding(image_id, str(cache_path))
            
            # Add to FAISS index
            vector_store = get_vector_store()
            vector_store.add_vectors(embeddings, actor_id)
            vector_store.save_index()
            message = f"Image added and {faces_detected} faces indexed successfully"
        else:
            message = "Image added successfully, but no faces were detected for indexing"
    except Exception as e:
        message = f"Image added, but indexing failed: {str(e)}"

    return {"message": message, "actor_id": actor_id, "faces_detected": faces_detected}


@router.get("/{actor_id}/images/{image_id}")
def get_actor_image(actor_id: int, image_id: str):
    """Get a specific actor reference image."""
    images = actor_db.get_actor_images(actor_id)
    for img in images:
        matches_id = image_id.isdigit() and img["id"] == int(image_id)
        if matches_id or img["filename"] == image_id:
            if Path(img["file_path"]).exists():
                return FileResponse(img["file_path"])

    raise HTTPException(status_code=404, detail="Image not found")


@router.delete("/{actor_id}/images/{image_id}", status_code=204)
def delete_actor_image(actor_id: int, image_id: int):
    """Delete a reference image for an actor and update the FAISS index."""
    images = actor_db.get_actor_images(actor_id)
    image = None
    for img in images:
        if img["id"] == image_id:
            image = img
            break

    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    img_path = Path(image["file_path"])
    if img_path.exists():
        img_path.unlink()

    # Clean up embedding cache
    embedding_path = image.get("embedding_path")
    if embedding_path:
        cache_path = Path(embedding_path)
        if cache_path.exists():
            cache_path.unlink()

    with actor_db.get_db() as conn:
        conn.execute(
            "DELETE FROM actor_images WHERE id = ?", (image_id,)
        )

    # Rebuild actor vectors in the FAISS index
    try:
        vector_store = get_vector_store()
        # 1. Remove all vectors for this actor
        vector_store.remove_actor(actor_id)
        
        # 2. Extract vectors from all remaining images
        remaining_embeddings = []
        remaining_images = actor_db.get_actor_images(actor_id)
        for r_img in remaining_images:
            r_emb_path = r_img.get("embedding_path")
            if r_emb_path and Path(r_emb_path).exists():
                try:
                    cached = np.load(r_emb_path)
                    if cached.ndim == 1:
                        cached = cached.reshape(1, -1)
                    for row in cached:
                        remaining_embeddings.append(row.astype(np.float32))
                except Exception as load_err:
                    print(f"Error loading cached embedding {r_emb_path}: {load_err}")
        
        if remaining_embeddings:
            vector_store.add_vectors(remaining_embeddings, actor_id)
            
        vector_store.save_index()
    except Exception as e:
        print(f"Error rebuilding actor vectors in vector store: {e}")

    return None
