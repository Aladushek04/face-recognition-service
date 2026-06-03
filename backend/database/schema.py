"""SQLite database schema and initialization."""

import sqlite3
from pathlib import Path
from config import settings


def get_db_path() -> Path:
    """Get the database file path."""
    db_dir = settings.base_dir / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "actors.db"


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Add a column to an existing SQLite table when it is missing."""
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> sqlite3.Connection:
    """Initialize the database and return a connection."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Create tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS actors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stashdb_id TEXT UNIQUE,
            name TEXT NOT NULL UNIQUE,
            birth_year INTEGER,
            birthdate TEXT,
            gender TEXT,
            aliases TEXT DEFAULT '[]',
            scene_count INTEGER,
            breast_type TEXT,
            height_cm INTEGER,
            measurements TEXT,
            cup_size TEXT,
            band_size INTEGER,
            waist_size INTEGER,
            hip_size INTEGER,
            country TEXT,
            ethnicity TEXT,
            eye_color TEXT,
            hair_color TEXT,
            tattoos TEXT DEFAULT '[]',
            piercings TEXT DEFAULT '[]',
            career_start_year INTEGER,
            career_end_year INTEGER,
            image_url TEXT,
            stashdb_urls TEXT DEFAULT '[]',
            bio TEXT,
            filmography TEXT,
            tags TEXT DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS actor_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            embedding_path TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (actor_id) REFERENCES actors(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            duration REAL,
            size_bytes INTEGER,
            status TEXT DEFAULT 'unprocessed',
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS video_detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            actor_id INTEGER NOT NULL,
            timestamp REAL NOT NULL,
            bbox TEXT NOT NULL,
            confidence REAL NOT NULL,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
            FOREIGN KEY (actor_id) REFERENCES actors(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_actor_images_actor_id ON actor_images(actor_id);
        CREATE INDEX IF NOT EXISTS idx_actors_name ON actors(name);
        CREATE INDEX IF NOT EXISTS idx_video_detections_video_id ON video_detections(video_id);
        CREATE INDEX IF NOT EXISTS idx_video_detections_actor_id ON video_detections(actor_id);
    """)

    _ensure_column(conn, "actors", "stashdb_id", "TEXT")
    _ensure_column(conn, "actors", "aliases", "TEXT DEFAULT '[]'")
    _ensure_column(conn, "actors", "scene_count", "INTEGER")
    _ensure_column(conn, "actors", "breast_type", "TEXT")
    _ensure_column(conn, "actors", "height_cm", "INTEGER")
    _ensure_column(conn, "actors", "measurements", "TEXT")
    _ensure_column(conn, "actors", "cup_size", "TEXT")
    _ensure_column(conn, "actors", "band_size", "INTEGER")
    _ensure_column(conn, "actors", "waist_size", "INTEGER")
    _ensure_column(conn, "actors", "hip_size", "INTEGER")
    _ensure_column(conn, "actors", "country", "TEXT")
    _ensure_column(conn, "actors", "ethnicity", "TEXT")
    _ensure_column(conn, "actors", "eye_color", "TEXT")
    _ensure_column(conn, "actors", "hair_color", "TEXT")
    _ensure_column(conn, "actors", "tattoos", "TEXT DEFAULT '[]'")
    _ensure_column(conn, "actors", "piercings", "TEXT DEFAULT '[]'")
    _ensure_column(conn, "actors", "birthdate", "TEXT")
    _ensure_column(conn, "actors", "career_start_year", "INTEGER")
    _ensure_column(conn, "actors", "career_end_year", "INTEGER")
    _ensure_column(conn, "actors", "image_url", "TEXT")
    _ensure_column(conn, "actors", "stashdb_urls", "TEXT DEFAULT '[]'")
    _ensure_column(conn, "videos", "progress", "INTEGER DEFAULT 0")
    _ensure_column(conn, "videos", "stashdb_scene_id", "TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_actors_stashdb_id ON actors(stashdb_id)")

    conn.commit()
    return conn
