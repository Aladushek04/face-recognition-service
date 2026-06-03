"""StashDB integration route handlers."""

import uuid
import requests
import numpy as np
from pathlib import Path
from typing import Optional, Any
import re
import sqlite3
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from database import actor_db
from config import settings
from models.face_detector import FaceDetector
from models.vector_store import VectorStore

router = APIRouter(prefix="/api/stashdb", tags=["stashdb"])

_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get the singleton vector store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    if not _vector_store.is_loaded:
        _vector_store.load_index()
    return _vector_store


# Re-use schema queries
QUERY_SEARCH_PERFORMERS = """
query QueryPerformers($input: PerformerQueryInput!) {
  queryPerformers(input: $input) {
    count
    performers {
      id
      name
      disambiguation
      gender
      birth_date
      scene_count
      breast_type
      images {
        url
        width
        height
      }
    }
  }
}
"""

QUERY_FIND_PERFORMER = """
query FindPerformer($id: ID!) {
  findPerformer(id: $id) {
    id
    name
    disambiguation
    gender
    birth_date
    aliases
    country
    ethnicity
    eye_color
    hair_color
    height
    cup_size
    band_size
    waist_size
    hip_size
    career_start_year
    career_end_year
    breast_type
    tattoos {
      location
      description
    }
    piercings {
      location
      description
    }
    scene_count
    urls {
      url
    }
    images {
      url
      width
      height
    }
  }
}
"""


def get_stashdb_headers() -> dict[str, str]:
    if not settings.stashdb_api_key:
        raise HTTPException(
            status_code=400,
            detail="StashDB API Key is not set. Please add STASHDB_API_KEY to your .env file."
        )
    return {
        "ApiKey": settings.stashdb_api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def call_stashdb_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.post(
            settings.stashdb_api_url,
            json={"query": query, "variables": variables},
            headers=get_stashdb_headers(),
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise HTTPException(status_code=502, detail=f"StashDB GraphQL errors: {payload['errors']}")
        return payload.get("data") or {}
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to communicate with StashDB: {str(e)}")


def safe_actor_dir_name(name: str) -> str:
    cleaned = re.sub(r"[^\w .'-]+", "", name, flags=re.UNICODE).strip()
    return cleaned.replace(" ", "_") or "Unknown"


def birth_year_from_birthdate(birthdate: Any) -> Optional[int]:
    if not birthdate:
        return None
    if isinstance(birthdate, dict):
        year = birthdate.get("year")
        if isinstance(year, int):
            return year
        birthdate = birthdate.get("date")
    if not birthdate:
        return None
    match = re.match(r"^(\d{4})", str(birthdate))
    return int(match.group(1)) if match else None


def birthdate_value(birthdate: Any) -> Optional[str]:
    if not birthdate:
        return None
    if isinstance(birthdate, dict):
        value = birthdate.get("date")
        if value:
            return str(value)
        year = birthdate.get("year")
        month = birthdate.get("month")
        day = birthdate.get("day")
        if isinstance(year, int) and isinstance(month, int) and isinstance(day, int):
            return f"{year:04d}-{month:02d}-{day:02d}"
        return None
    return str(birthdate)


def image_candidates(performer: dict[str, Any], order: str = "largest") -> list[str]:
    images = performer.get("images") or []
    if order == "largest":
        # Prefer largest resolution
        images = sorted(
            images,
            key=lambda item: (item.get("width") or 0) * (item.get("height") or 0),
            reverse=True,
        )
    elif order == "end":
        # Start from the end of the StashDB list
        images = list(reversed(images))
    else: # "start"
        # Start from the beginning of the StashDB list
        images = list(images)

    urls = []
    for item in images:
        url = item.get("url")
        if not url:
            continue
        if not url.startswith("http"):
            url = f"https:{url}"
        if url not in urls:
            urls.append(url)
    return urls


class PerformerImportRequest(BaseModel):
    performer_id: str
    image_count: int = 3
    image_order: str = "largest"
    check_face: bool = True
    overwrite_metadata: bool = False


@router.get("/search")
def search_stashdb(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Search performers on StashDB."""
    variables = {
        "input": {
            "names": q,
            "page": page,
            "per_page": page_size,
            "sort": "NAME",
            "direction": "ASC",
        }
    }
    data = call_stashdb_graphql(QUERY_SEARCH_PERFORMERS, variables)
    result = data.get("queryPerformers") or {"count": 0, "performers": []}
    
    # Simplify response for UI
    performers = []
    for p in result.get("performers") or []:
        urls = image_candidates(p)
        performers.append({
            "id": p["id"],
            "name": p["name"],
            "disambiguation": p.get("disambiguation"),
            "gender": (p.get("gender") or "").lower(),
            "birth_date": birthdate_value(p.get("birth_date")),
            "scene_count": p.get("scene_count") or 0,
            "breast_type": p.get("breast_type"),
            "image_url": urls[0] if urls else None,
        })
        
    return {
        "count": result.get("count", 0),
        "performers": performers,
        "page": page,
        "page_size": page_size,
    }


@router.post("/import")
def import_stashdb_performer(req: PerformerImportRequest):
    """Import a single performer from StashDB into local DB and index."""
    performer_id = req.performer_id
    image_count = req.image_count
    image_order = req.image_order
    check_face = req.check_face
    overwrite_metadata = req.overwrite_metadata

    # Check if already exists
    existing = actor_db.get_actor_by_stashdb_id(performer_id)
    if existing and not overwrite_metadata:
        return {
            "status": "exists",
            "message": "Actor already exists in database",
            "actor": existing
        }

    # Fetch performer details
    variables = {"id": performer_id}
    data = call_stashdb_graphql(QUERY_FIND_PERFORMER, variables)
    performer = data.get("findPerformer")
    if not performer:
        raise HTTPException(status_code=404, detail="Performer not found on StashDB")

    name = performer.get("name") or "Unknown"
    
    # Check by name just in case
    if not existing:
        existing_by_name = actor_db.get_actor_by_name(name)
        if existing_by_name and not overwrite_metadata:
            return {
                "status": "exists",
                "message": "Actor with this name already exists in database",
                "actor": existing_by_name
            }
        existing = existing_by_name

    urls = image_candidates(performer, image_order)
    gender = (performer.get("gender") or "other").lower()
    if gender not in {"female", "male"}:
        gender = "other"

    # Build bio and filmography
    bio_parts = []
    if performer.get("disambiguation"):
        bio_parts.append(f"Disambiguation: {performer['disambiguation']}")
    urls_list = [entry.get("url") for entry in performer.get("urls", []) if entry.get("url")]
    if urls_list:
        bio_parts.append(f"URLs: {', '.join(urls_list[:5])}")
    bio = ". ".join(bio_parts)[:1000]

    filmography = None
    start_yr = performer.get("career_start_year")
    end_yr = performer.get("career_end_year")
    if start_yr and end_yr:
        filmography = f"Career: {start_yr}-{end_yr}"
    elif start_yr:
        filmography = f"Career start: {start_yr}"
    elif end_yr:
        filmography = f"Career end: {end_yr}"

    # Build DB metadata
    metadata = {
        "stashdb_id": performer_id,
        "birth_year": birth_year_from_birthdate(performer.get("birth_date")),
        "birthdate": birthdate_value(performer.get("birth_date")),
        "gender": gender,
        "aliases": performer.get("aliases") or [],
        "scene_count": performer.get("scene_count"),
        "breast_type": performer.get("breast_type"),
        "height_cm": performer.get("height"),
        "measurements": None, # parsed dynamically if needed
        "cup_size": performer.get("cup_size"),
        "band_size": performer.get("band_size"),
        "waist_size": performer.get("waist_size"),
        "hip_size": performer.get("hip_size"),
        "country": performer.get("country"),
        "ethnicity": performer.get("ethnicity").replace("_", " ").title() if performer.get("ethnicity") else None,
        "eye_color": performer.get("eye_color").replace("_", " ").title() if performer.get("eye_color") else None,
        "hair_color": performer.get("hair_color").replace("_", " ").title() if performer.get("hair_color") else None,
        "tattoos": [f"{t.get('location') or ''}: {t.get('description') or ''}".strip(': ') for t in performer.get("tattoos") or []],
        "piercings": [f"{p.get('location') or ''}: {p.get('description') or ''}".strip(': ') for p in performer.get("piercings") or []],
        "career_start_year": start_yr,
        "career_end_year": end_yr,
        "image_url": urls[0] if urls else None,
        "stashdb_urls": urls_list,
        "bio": bio,
        "filmography": filmography,
        "tags": ["stashdb", "adult", gender],
    }

    # Calculate band, cup, waist, hip sizes for measurements string
    band = performer.get("band_size")
    cup = performer.get("cup_size")
    waist = performer.get("waist_size")
    hip = performer.get("hip_size")
    if any([band, cup, waist, hip]):
        bust = f"{band or ''}{cup or ''}".strip()
        parts = [bust or None, waist, hip]
        metadata["measurements"] = "-".join(str(part) for part in parts if part not in {None, ""})

    detector = FaceDetector()
    vector_store = get_vector_store()

    if existing:
        actor_id = existing["id"]
        # Overwrite metadata
        actor_db.update_actor(actor_id, name=name, **metadata)

        # Clear existing images and their embeddings from DB and disk
        old_images = actor_db.get_actor_images(actor_id)
        for img in old_images:
            actor_db.delete_actor_image(img["id"])

        # Remove existing vectors from FAISS
        vector_store.remove_actor(actor_id)
        vector_store.save_index()
    else:
        # Add to SQLite DB
        try:
            actor_id = actor_db.add_actor(name=name, **metadata)
        except sqlite3.IntegrityError as e:
            raise HTTPException(status_code=409, detail=f"Actor already exists: {str(e)}")

    actor_dir = settings.actors_dir / safe_actor_dir_name(name)
    actor_dir.mkdir(parents=True, exist_ok=True)

    # Download images and index them
    download_urls = urls[:image_count] if image_count > 0 else urls
    images_downloaded = 0
    faces_indexed = 0
    all_embeddings = []

    for idx, url in enumerate(download_urls, start=1):
        image_path = actor_dir / f"profile_{idx:02d}.jpg"
        try:
            res = requests.get(url, stream=True, timeout=15)
            res.raise_for_status()
            with open(image_path, "wb") as f:
                for chunk in res.iter_content(1024 * 64):
                    f.write(chunk)
            
            # Register image in SQLite
            image_id = actor_db.add_actor_image(
                actor_id=actor_id,
                filename=image_path.name,
                file_path=str(image_path)
            )
            images_downloaded += 1

            # Detect faces and cache
            faces = detector.detect_faces_from_path(image_path)
            if faces:
                embeddings = [face["embedding"].astype(np.float32) for face in faces]
                all_embeddings.extend(embeddings)
                
                cache_dir = settings.base_dir / "data" / "embeddings"
                cache_dir.mkdir(parents=True, exist_ok=True)
                cache_path = cache_dir / f"actor_image_{image_id}.npy"
                np.save(cache_path, np.array(embeddings, dtype=np.float32))
                
                actor_db.update_actor_image_embedding(image_id, str(cache_path))
                faces_indexed += len(faces)
            elif check_face:
                # No face found, delete if face checking is enabled
                image_path.unlink(missing_ok=True)
                actor_db.delete_actor_image(image_id)
                images_downloaded -= 1
            
        except Exception as e:
            # Clean up if download/processing fails
            image_path.unlink(missing_ok=True)
            print(f"Failed to import reference image {url}: {e}")

    # Add all embeddings to FAISS
    if all_embeddings:
        try:
            vector_store.add_vectors(all_embeddings, actor_id)
            vector_store.save_index()
        except Exception as e:
            print(f"Failed to update FAISS index for imported actor {name}: {e}")

    imported_actor = actor_db.get_actor(actor_id)
    
    return {
        "status": "imported",
        "actor": dict(imported_actor),
        "images_downloaded": images_downloaded,
        "faces_indexed": faces_indexed
    }
