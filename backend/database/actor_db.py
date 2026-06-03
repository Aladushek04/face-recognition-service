"""Actor database operations."""

import sqlite3
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from contextlib import contextmanager
from database.schema import get_db_path, init_db
from config import settings


@contextmanager
def get_db():
    """Get a database connection with auto-cleanup."""
    conn = init_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_actor(
    name: str,
    stashdb_id: Optional[str] = None,
    birth_year: Optional[int] = None,
    birthdate: Optional[str] = None,
    gender: Optional[str] = None,
    aliases: Optional[list[str]] = None,
    scene_count: Optional[int] = None,
    breast_type: Optional[str] = None,
    height_cm: Optional[int] = None,
    measurements: Optional[str] = None,
    cup_size: Optional[str] = None,
    band_size: Optional[int] = None,
    waist_size: Optional[int] = None,
    hip_size: Optional[int] = None,
    country: Optional[str] = None,
    ethnicity: Optional[str] = None,
    eye_color: Optional[str] = None,
    hair_color: Optional[str] = None,
    tattoos: Optional[list[str]] = None,
    piercings: Optional[list[str]] = None,
    career_start_year: Optional[int] = None,
    career_end_year: Optional[int] = None,
    image_url: Optional[str] = None,
    stashdb_urls: Optional[list[str]] = None,
    bio: Optional[str] = None,
    filmography: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> int:
    """Add a new actor to the database. Returns the actor ID."""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO actors (
                   name, stashdb_id, birth_year, birthdate, gender, aliases,
                   scene_count, breast_type, height_cm, measurements, cup_size, band_size,
                   waist_size, hip_size, country, ethnicity, eye_color, hair_color,
                   tattoos, piercings,
                   career_start_year, career_end_year, image_url, stashdb_urls, bio, filmography, tags
               )
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                stashdb_id,
                birth_year,
                birthdate,
                gender,
                json.dumps(aliases or []),
                scene_count,
                breast_type,
                height_cm,
                measurements,
                cup_size,
                band_size,
                waist_size,
                hip_size,
                country,
                ethnicity,
                eye_color,
                hair_color,
                json.dumps(tattoos or []),
                json.dumps(piercings or []),
                career_start_year,
                career_end_year,
                image_url,
                json.dumps(stashdb_urls or []),
                bio,
                filmography,
                json.dumps(tags or []),
            ),
        )
        return cursor.lastrowid


def get_actor(actor_id: int) -> Optional[dict]:
    """Get actor details by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM actors WHERE id = ?", (actor_id,)
        ).fetchone()
        if row:
            return dict(row)
        return None


def get_actor_by_name(name: str) -> Optional[dict]:
    """Get actor by name (case-insensitive)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM actors WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        if row:
            return dict(row)
        return None


def get_actor_by_stashdb_id(stashdb_id: str) -> Optional[dict]:
    """Get actor by StashDB performer ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM actors WHERE stashdb_id = ?", (stashdb_id,)
        ).fetchone()
        if row:
            return dict(row)
        return None


def update_actor(
    actor_id: int,
    name: Optional[str] = None,
    stashdb_id: Optional[str] = None,
    birth_year: Optional[int] = None,
    birthdate: Optional[str] = None,
    gender: Optional[str] = None,
    aliases: Optional[list[str]] = None,
    scene_count: Optional[int] = None,
    breast_type: Optional[str] = None,
    height_cm: Optional[int] = None,
    measurements: Optional[str] = None,
    cup_size: Optional[str] = None,
    band_size: Optional[int] = None,
    waist_size: Optional[int] = None,
    hip_size: Optional[int] = None,
    country: Optional[str] = None,
    ethnicity: Optional[str] = None,
    eye_color: Optional[str] = None,
    hair_color: Optional[str] = None,
    tattoos: Optional[list[str]] = None,
    piercings: Optional[list[str]] = None,
    career_start_year: Optional[int] = None,
    career_end_year: Optional[int] = None,
    image_url: Optional[str] = None,
    stashdb_urls: Optional[list[str]] = None,
    bio: Optional[str] = None,
    filmography: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> bool:
    """Update an actor's information."""
    updates = []
    params = []

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if stashdb_id is not None:
        updates.append("stashdb_id = ?")
        params.append(stashdb_id)
    if birth_year is not None:
        updates.append("birth_year = ?")
        params.append(birth_year)
    if birthdate is not None:
        updates.append("birthdate = ?")
        params.append(birthdate)
    if gender is not None:
        updates.append("gender = ?")
        params.append(gender)
    if aliases is not None:
        updates.append("aliases = ?")
        params.append(json.dumps(aliases))
    if scene_count is not None:
        updates.append("scene_count = ?")
        params.append(scene_count)
    if breast_type is not None:
        updates.append("breast_type = ?")
        params.append(breast_type)
    if height_cm is not None:
        updates.append("height_cm = ?")
        params.append(height_cm)
    if measurements is not None:
        updates.append("measurements = ?")
        params.append(measurements)
    if cup_size is not None:
        updates.append("cup_size = ?")
        params.append(cup_size)
    if band_size is not None:
        updates.append("band_size = ?")
        params.append(band_size)
    if waist_size is not None:
        updates.append("waist_size = ?")
        params.append(waist_size)
    if hip_size is not None:
        updates.append("hip_size = ?")
        params.append(hip_size)
    if country is not None:
        updates.append("country = ?")
        params.append(country)
    if ethnicity is not None:
        updates.append("ethnicity = ?")
        params.append(ethnicity)
    if eye_color is not None:
        updates.append("eye_color = ?")
        params.append(eye_color)
    if hair_color is not None:
        updates.append("hair_color = ?")
        params.append(hair_color)
    if tattoos is not None:
        updates.append("tattoos = ?")
        params.append(json.dumps(tattoos))
    if piercings is not None:
        updates.append("piercings = ?")
        params.append(json.dumps(piercings))
    if career_start_year is not None:
        updates.append("career_start_year = ?")
        params.append(career_start_year)
    if career_end_year is not None:
        updates.append("career_end_year = ?")
        params.append(career_end_year)
    if image_url is not None:
        updates.append("image_url = ?")
        params.append(image_url)
    if stashdb_urls is not None:
        updates.append("stashdb_urls = ?")
        params.append(json.dumps(stashdb_urls))
    if bio is not None:
        updates.append("bio = ?")
        params.append(bio)
    if filmography is not None:
        updates.append("filmography = ?")
        params.append(filmography)
    if tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(tags))

    if not updates:
        return False

    updates.append("updated_at = datetime('now')")
    params.append(actor_id)

    with get_db() as conn:
        conn.execute(
            f"UPDATE actors SET {', '.join(updates)} WHERE id = ?", params
        )
        return True


def delete_actor(actor_id: int) -> bool:
    """Delete an actor and all their reference images."""
    with get_db() as conn:
        # Get image paths before deleting
        images = conn.execute(
            "SELECT file_path FROM actor_images WHERE actor_id = ?", (actor_id,)
        ).fetchall()

        # Delete actor (cascade deletes images)
        cursor = conn.execute("DELETE FROM actors WHERE id = ?", (actor_id,))
        if cursor.rowcount == 0:
            return False

        # Clean up image files
        for img in images:
            path = Path(img["file_path"])
            if path.exists():
                path.unlink()

        return True


def list_actors(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    breast_type: Optional[str] = None,
    min_scenes: Optional[int] = None,
    has_photo: Optional[bool] = None,
) -> tuple[list[dict], int]:
    """List actors with pagination, optional search, and database-level filters."""
    with get_db() as conn:
        where_clauses = []
        params: list[object] = []

        if search:
            where_clauses.append("LOWER(actors.name) LIKE LOWER(?)")
            params.append(f"%{search}%")

        if breast_type:
            if breast_type == "FAKE":
                where_clauses.append(
                    "UPPER(COALESCE(actors.breast_type, '')) IN ('FAKE', 'AUGMENTED')"
                )
            elif breast_type == "NATURAL":
                where_clauses.append("UPPER(COALESCE(actors.breast_type, '')) = 'NATURAL'")
            elif breast_type == "NA":
                where_clauses.append("UPPER(COALESCE(actors.breast_type, '')) IN ('NA', 'N/A')")

        if min_scenes is not None:
            where_clauses.append("COALESCE(actors.scene_count, 0) >= ?")
            params.append(min_scenes)

        if has_photo is True:
            where_clauses.append(
                "EXISTS (SELECT 1 FROM actor_images ai WHERE ai.actor_id = actors.id)"
            )
        elif has_photo is False:
            where_clauses.append(
                "NOT EXISTS (SELECT 1 FROM actor_images ai WHERE ai.actor_id = actors.id)"
            )

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_row = conn.execute(
            f"SELECT COUNT(*) as cnt FROM actors {where_sql}",
            params,
        ).fetchone()
        total = count_row["cnt"]

        rows = conn.execute(
            f"""SELECT actors.*, (SELECT COUNT(*) FROM actor_images ai WHERE ai.actor_id = actors.id) as reference_image_count
                FROM actors
                {where_sql}
                ORDER BY name ASC
                LIMIT ? OFFSET ?""",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()

        actors = [dict(r) for r in rows]
        return actors, total


def add_actor_image(
    actor_id: int,
    filename: str,
    file_path: str,
    embedding_path: Optional[str] = None,
) -> int:
    """Add a reference image for an actor."""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO actor_images (actor_id, filename, file_path, embedding_path)
               VALUES (?, ?, ?, ?)""",
            (actor_id, filename, file_path, embedding_path),
        )
        return cursor.lastrowid


def get_actor_images(actor_id: int) -> list[dict]:
    """Get all reference images for an actor."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM actor_images WHERE actor_id = ? ORDER BY created_at DESC",
            (actor_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_actor_images(page: int = 1, page_size: int = 1000) -> tuple[list[dict], int]:
    """List actor images with their actor names."""
    with get_db() as conn:
        count_row = conn.execute("SELECT COUNT(*) as cnt FROM actor_images").fetchone()
        total = count_row["cnt"]
        rows = conn.execute(
            """SELECT actor_images.*, actors.name as actor_name
               FROM actor_images
               JOIN actors ON actors.id = actor_images.actor_id
               ORDER BY actors.name ASC, actor_images.filename ASC
               LIMIT ? OFFSET ?""",
            (page_size, (page - 1) * page_size),
        ).fetchall()
        return [dict(r) for r in rows], total


def delete_actor_image(image_id: int) -> Optional[dict]:
    """Delete an actor image row and file. Returns deleted image info when found."""
    with get_db() as conn:
        image = conn.execute(
            "SELECT * FROM actor_images WHERE id = ?", (image_id,)
        ).fetchone()
        if not image:
            return None

        image_dict = dict(image)
        conn.execute("DELETE FROM actor_images WHERE id = ?", (image_id,))

        path = Path(image_dict["file_path"])
        if path.exists():
            path.unlink()

        embedding_path = image_dict.get("embedding_path")
        if embedding_path:
            cache_path = Path(embedding_path)
            if cache_path.exists():
                cache_path.unlink()

        return image_dict


def update_actor_image_embedding(image_id: int, embedding_path: str) -> bool:
    """Store the cached embedding path for a reference image."""
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE actor_images SET embedding_path = ? WHERE id = ?",
            (embedding_path, image_id),
        )
        return cursor.rowcount > 0


def get_actor_images_count() -> int:
    """Get total number of reference images."""
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM actor_images").fetchone()
        return row["cnt"]


def get_actors_count() -> int:
    """Get total number of actors."""
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM actors").fetchone()
        return row["cnt"]
