import sqlite3
import json
import re
import requests
import cv2
import threading
import filetype
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Body
from fastapi.responses import FileResponse
from database.schema import get_db_path
from models.video_processor import VideoProcessor
from config import settings

router = APIRouter(prefix="/api/videos", tags=["videos"])
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v", ".wmv", ".ts"}


def _decode_json_list(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _video_thumbnail_url(video_id: int) -> str | None:
    thumb_path = Path(settings.base_dir) / "thumbnails" / f"{video_id}.jpg"
    if not thumb_path.exists():
        return None
    return f"/api/thumbnails/{video_id}.jpg"


def _infer_video_suffix(path: Path) -> str:
    """Infer a video suffix for files that were previously renamed without one."""
    suffix = path.suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return suffix

    try:
        kind = filetype.guess(str(path))
    except Exception:
        kind = None

    if kind and kind.extension:
        inferred = f".{kind.extension.lower()}"
        if inferred in VIDEO_EXTENSIONS:
            return inferred

    return ""


def _resolve_rename_target(old_path: Path, requested_name: str) -> Path:
    old_suffix = _infer_video_suffix(old_path)
    requested_path = Path(requested_name)
    requested_suffix = requested_path.suffix.lower()

    if requested_suffix in VIDEO_EXTENSIONS:
        if old_suffix and requested_suffix != old_suffix:
            raise HTTPException(
                status_code=400,
                detail=f"Changing video extension is not supported. Keep {old_suffix}.",
            )
        return old_path.parent / requested_name

    # Scene titles often contain dots, e.g. "Anal. Deep balls". Treat unknown
    # suffixes as title punctuation and append the real container extension.
    if old_suffix:
        return old_path.parent / f"{requested_name}{old_suffix}"

    return old_path.parent / requested_name


@router.get("")
def list_videos(
    search: Optional[str] = None,
    status: Optional[str] = None,
    actor_id: Optional[int] = None
):
    """List scanned videos with optional search and filters."""
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        
        query = "SELECT v.* FROM videos v"
        params = []
        conditions = []
        
        if actor_id is not None:
            query += " JOIN video_detections vd ON vd.video_id = v.id"
            conditions.append("vd.actor_id = ?")
            params.append(actor_id)
            
        if search:
            conditions.append("v.filename LIKE ?")
            params.append(f"%{search}%")
            
        if status:
            conditions.append("v.status = ?")
            params.append(status)
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        if actor_id is not None:
            query += " GROUP BY v.id"
            
        query += " ORDER BY v.created_at DESC"
        
        videos = conn.execute(query, params).fetchall()
        
        result_list = []
        for video in videos:
            v_dict = dict(video)
            v_dict["stashdb_performers"] = _decode_json_list(v_dict.get("stashdb_performers"))
            v_dict["thumbnail_url"] = _video_thumbnail_url(v_dict["id"])
            
            # Fetch distinct actors detected in this video
            actors = conn.execute(
                """SELECT DISTINCT a.id, a.name 
                   FROM video_detections vd 
                   JOIN actors a ON vd.actor_id = a.id 
                   WHERE vd.video_id = ?""",
                (v_dict["id"],)
            ).fetchall()
            v_dict["actors"] = [dict(act) for act in actors]
            result_list.append(v_dict)
            
        return result_list

@router.get("/{video_id}")
def get_video(video_id: int):
    """Get video details and timeline of detections."""
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        video = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
            
        # Get detections
        detections = conn.execute(
            """SELECT vd.id, vd.actor_id, a.name as actor_name, vd.timestamp, vd.bbox, vd.confidence
               FROM video_detections vd
               JOIN actors a ON vd.actor_id = a.id
               WHERE vd.video_id = ?
               ORDER BY vd.timestamp ASC""",
            (video_id,)
        ).fetchall()
        
        formatted_detections = []
        for det in detections:
            det_dict = dict(det)
            try:
                det_dict["bbox"] = json.loads(det_dict["bbox"])
            except Exception:
                det_dict["bbox"] = []
            formatted_detections.append(det_dict)
            
        video_dict = dict(video)
        video_dict["stashdb_performers"] = _decode_json_list(video_dict.get("stashdb_performers"))
        video_dict["thumbnail_url"] = _video_thumbnail_url(video_dict["id"])
        video_dict["detections"] = formatted_detections
        
        # Extract unique actors found in detections
        distinct_actors = []
        seen = set()
        for det in formatted_detections:
            if det["actor_id"] not in seen:
                seen.add(det["actor_id"])
                distinct_actors.append({
                    "id": det["actor_id"],
                    "name": det["actor_name"]
                })
        video_dict["actors"] = distinct_actors
        
        return video_dict

def generate_missing_thumbnails():
    db_path = get_db_path()
    thumbnails_dir = Path(settings.base_dir) / "thumbnails"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        completed_videos = conn.execute(
            "SELECT id, filepath FROM videos WHERE status = 'completed'"
        ).fetchall()
        
    for video in completed_videos:
        video_id = video["id"]
        filepath = video["filepath"]
        thumb_path = thumbnails_dir / f"{video_id}.jpg"
        
        if not thumb_path.exists():
            print(f"Generating missing thumbnail for video {video_id}...")
            try:
                cap = cv2.VideoCapture(filepath)
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    target_frame = min(int(fps * 5.0), total_frames - 1) if fps > 0 else 0
                    target_frame = max(target_frame, 0)
                    
                    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                    ret, frame = cap.read()
                    if ret:
                        h, w = frame.shape[:2]
                        target_h = 360
                        target_w = int((w / h) * target_h)
                        resized = cv2.resize(frame, (target_w, target_h))
                        cv2.imwrite(str(thumb_path), resized)
                    cap.release()
            except Exception as e:
                print(f"Failed to generate thumbnail for video {video_id}: {e}")

@router.post("/scan")
def scan_videos():
    """Scan the configured VIDEOS_DIR and add new videos as unprocessed."""
    videos_dir = settings.videos_dir
    videos_dir_path = str(videos_dir)
    
    if not videos_dir.exists():
        raise HTTPException(
            status_code=404, 
            detail=f"Videos directory {videos_dir_path} does not exist. Please create it or configure VIDEOS_DIR in .env."
        )
        
    db_path = get_db_path()
    
    scanned_count = 0
    added_count = 0
    
    with sqlite3.connect(db_path) as conn:
        for file in videos_dir.rglob("*"):
            if file.is_file() and file.suffix.lower() in VIDEO_EXTENSIONS:
                scanned_count += 1
                filepath = str(file.resolve())
                filename = file.name
                
                # Check if already present
                exists = conn.execute("SELECT 1 FROM videos WHERE filepath = ?", (filepath,)).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO videos (filepath, filename) VALUES (?, ?)",
                        (filepath, filename)
                    )
                    added_count += 1
        conn.commit()
        
    # Generate missing thumbnails for completed videos in background
    threading.Thread(target=generate_missing_thumbnails, daemon=True).start()
        
    return {
        "status": "success",
        "scanned": scanned_count,
        "added": added_count,
        "directory": videos_dir_path
    }

@router.post("/{video_id}/process")
def process_video(video_id: int, background_tasks: BackgroundTasks):
    """Start background face detection/recognition processing for a video."""
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        video = conn.execute("SELECT filepath, status FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
            
        if video["status"] == "processing":
            return {"status": "already_processing", "video_id": video_id}
            
        # Update status and clear any existing detections
        conn.execute("UPDATE videos SET status = 'processing', error_message = NULL, progress = 0 WHERE id = ?", (video_id,))
        conn.execute("DELETE FROM video_detections WHERE video_id = ?", (video_id,))
        conn.commit()
        
    processor = VideoProcessor()
    background_tasks.add_task(processor.process, video_id, video["filepath"], str(db_path))
    
    return {"status": "started", "video_id": video_id}

@router.get("/{video_id}/stream")
def stream_video(video_id: int):
    """Streams a video file with support for range queries (for seeking)."""
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        video = conn.execute("SELECT filepath FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        filepath = Path(video["filepath"])
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="Video file does not exist on disk")
            
        return FileResponse(str(filepath))

@router.delete("/{video_id}", status_code=204)
def delete_video(video_id: int):
    """Removes a video file record from the database (detections deleted via cascade)."""
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Video not found")
    return None

QUERY_SEARCH_SCENES = """
query QueryScenes($input: SceneQueryInput!) {
  queryScenes(input: $input) {
    count
    scenes {
      id
      title
      date
      studio {
        id
        name
      }
      images {
        url
      }
      performers {
        performer {
          id
          name
        }
      }
    }
  }
}
"""

QUERY_FIND_SCENE = """
query FindScene($id: ID!) {
  findScene(id: $id) {
    id
    title
    date
    studio {
      id
      name
    }
    images {
      url
    }
    performers {
      performer {
        id
        name
      }
    }
  }
}
"""

def batch_process_unprocessed(db_path_str: str):
    db_path = Path(db_path_str)
    processor = VideoProcessor()

    while True:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            video = conn.execute(
                "SELECT id, filepath FROM videos WHERE status IN ('unprocessed', 'failed') LIMIT 1"
            ).fetchone()
            
        if not video:
            break

        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE videos SET status = 'processing', error_message = NULL, progress = 0 WHERE id = ?", (video["id"],))
            conn.commit()

        try:
            processor.process(video["id"], video["filepath"], str(db_path))
        except Exception as e:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "UPDATE videos SET status = 'failed', error_message = ?, updated_at = datetime('now') WHERE id = ?",
                    (str(e), video["id"])
                )
                conn.commit()


def reset_stale_processing_videos(db_path: Path, stale_after_minutes: int = 30) -> int:
    """Move abandoned processing rows back to failed so they can be queued again."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """UPDATE videos
               SET status = 'failed',
                   error_message = 'Processing was interrupted or abandoned.',
                   updated_at = datetime('now')
               WHERE status = 'processing'
                 AND updated_at < datetime('now', ?)""",
            (f"-{stale_after_minutes} minutes",)
        )
        conn.commit()
        return cursor.rowcount


def reset_interrupted_processing_videos(db_path: Path) -> int:
    """Recover processing rows left behind by a previous backend process."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """UPDATE videos
               SET status = 'failed',
                   error_message = 'Processing was interrupted by a service restart.',
                   updated_at = datetime('now')
               WHERE status = 'processing'"""
        )
        conn.commit()
        return cursor.rowcount

@router.post("/process-unprocessed")
def process_unprocessed_videos(background_tasks: BackgroundTasks):
    """Start background sequential processing for all unprocessed/failed videos."""
    db_path = get_db_path()
    reset_count = reset_stale_processing_videos(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        unprocessed = conn.execute(
            "SELECT id FROM videos WHERE status IN ('unprocessed', 'failed')"
        ).fetchall()
        
    if not unprocessed:
        return {"status": "no_videos_to_process", "count": 0, "reset_stale": reset_count}
        
    background_tasks.add_task(batch_process_unprocessed, str(db_path))
    return {"status": "started", "count": len(unprocessed), "reset_stale": reset_count}

@router.post("/{video_id}/rename")
def rename_video(video_id: int, new_filename: str = Body(..., embed=True)):
    """Renames the video file on disk and updates the database record."""
    requested_name = new_filename.strip()
    if not requested_name:
        raise HTTPException(status_code=400, detail="New filename cannot be empty")
    if Path(requested_name).name != requested_name:
        raise HTTPException(status_code=400, detail="New filename must not include a path")

    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        video = conn.execute("SELECT filepath FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
            
        old_path = Path(video["filepath"])
        if not old_path.exists():
            raise HTTPException(status_code=404, detail="Original video file not found on disk")
            
        new_path = _resolve_rename_target(old_path, requested_name)
        new_path = new_path.resolve()
        parent_dir = old_path.parent.resolve()
        if new_path.parent != parent_dir:
            raise HTTPException(status_code=400, detail="New filename must stay in the original directory")
            
        if new_path.exists():
            raise HTTPException(status_code=400, detail="A file with that name already exists")
            
        try:
            old_path.rename(new_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to rename file on disk: {str(e)}")
            
        conn.execute(
            "UPDATE videos SET filepath = ?, filename = ?, updated_at = datetime('now') WHERE id = ?",
            (str(new_path.resolve()), new_path.name, video_id)
        )
        conn.commit()
        
    return {"status": "success", "new_filepath": str(new_path.resolve()), "new_filename": new_path.name}

@router.post("/{video_id}/match-stashdb")
def match_stashdb_scene(video_id: int):
    """Smart auto-match: runs multi-strategy search and picks the best candidate."""
    if not settings.stashdb_api_key:
        raise HTTPException(
            status_code=400,
            detail="StashDB API Key is not set. Please add STASHDB_API_KEY to your .env file."
        )

    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        video = conn.execute("SELECT filename FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        filename = video["filename"]

        actors = conn.execute(
            """SELECT DISTINCT a.name FROM video_detections vd 
               JOIN actors a ON vd.actor_id = a.id 
               WHERE vd.video_id = ?""",
            (video_id,)
        ).fetchall()
        detected_actors = [r["name"] for r in actors]

        all_actors = conn.execute("SELECT name FROM actors").fetchall()
        all_db_actors = [r["name"] for r in all_actors]

    # Use the smart search pipeline
    queries = _build_search_queries(filename, detected_actors, all_db_actors)
    print(f"[SmartMatch] Video '{filename}' -> {len(queries)} queries: {queries}")

    seen_ids: set[str] = set()
    all_scenes: list[dict] = []

    for query in queries:
        scenes = _query_stashdb_scenes(query, per_page=5)
        for scene in scenes:
            sid = scene["id"]
            if sid not in seen_ids:
                seen_ids.add(sid)
                all_scenes.append(scene)
        if len(all_scenes) >= 15:
            break

    if not all_scenes:
        queries_str = ", ".join(f"'{q}'" for q in queries)
        raise HTTPException(
            status_code=404,
            detail=f"No matching scene found on StashDB. Tried queries: {queries_str}"
        )

    # Score all candidates and pick the best
    best_scene = None
    best_score = -1
    for scene in all_scenes:
        title = scene.get("title") or ""
        studio_name = scene.get("studio", {}).get("name") if scene.get("studio") else None
        performers = [p["performer"]["name"] for p in scene.get("performers") or []]
        scene_date = scene.get("date")
        score = calculate_match_score(filename, title, studio_name or "", scene_date, detected_actors, performers)
        if score > best_score:
            best_score = score
            best_scene = scene

    scene = best_scene
    scene_id = scene["id"]
    title = scene.get("title")
    studio_name = scene.get("studio", {}).get("name") if scene.get("studio") else None

    images = scene.get("images") or []
    cover_downloaded = False
    if images:
        cover_url = images[0].get("url")
        if cover_url:
            if not cover_url.startswith("http"):
                cover_url = f"https:{cover_url}"

            thumbnails_dir = Path(settings.base_dir) / "thumbnails"
            thumbnails_dir.mkdir(parents=True, exist_ok=True)
            thumb_path = thumbnails_dir / f"{video_id}.jpg"

            try:
                img_res = requests.get(cover_url, stream=True, timeout=15)
                img_res.raise_for_status()
                with open(thumb_path, "wb") as f:
                    for chunk in img_res.iter_content(1024 * 64):
                        f.write(chunk)
                cover_downloaded = True
            except Exception as e:
                print(f"Failed to download StashDB cover image: {e}")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE videos SET stashdb_scene_id = ?, stashdb_performers = ?, updated_at = datetime('now') WHERE id = ?",
            (
                scene_id,
                json.dumps([p["performer"]["name"] for p in scene.get("performers") or []]),
                video_id,
            )
        )
        conn.commit()

    return {
        "status": "success",
        "scene_id": scene_id,
        "title": title,
        "studio": studio_name,
        "cover_downloaded": cover_downloaded,
        "performers": [p["performer"]["name"] for p in scene.get("performers") or []],
        "match_score": best_score,
        "queries_tried": len(queries),
    }

# ── Smart StashDB Scene Search Engine ────────────────────────────────────────

# Noise tokens that should be stripped from filenames before searching.
# Includes codecs, resolutions, quality markers, scene numbering, common site tags.
_NOISE_TOKENS = {
    # resolutions & quality
    "1080p", "720p", "480p", "2160p", "4k", "8k", "uhd", "hd", "sd", "fhd",
    "high", "low", "hq", "lq",
    # codecs & containers
    "x264", "x265", "h264", "h265", "hevc", "avc", "vp9", "av1",
    "mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v", "ts",
    "aac", "ac3", "dts", "flac", "opus",
    # release / rip tags
    "bluray", "bdrip", "brrip", "dvdrip", "webrip", "web", "webdl",
    "hdtv", "hdrip", "remux", "repack", "proper", "real",
    "kcd", "rarbg", "yts", "yify", "eztv", "sparks", "geckos",
    "fgt", "ntb", "megusta", "amzn", "nf", "dsnp",
    # misc noise
    "xxx", "18", "19", "com", "www", "org", "net",
    "scene", "sample", "trailer", "teaser",
}

# Common studio / site names – these get stripped so the title keywords survive.
_KNOWN_STUDIOS = {
    "brazzers", "realitykings", "bangbros", "naughtyamerica", "mofos",
    "digitalplayground", "fakehub", "faketaxi", "fakehospital",
    "tushy", "tushyraw", "vixen", "blacked", "blackedraw", "deeper",
    "slayed", "milfy", "analonly",
    "babes", "twistys", "teamskeet", "sislovesme",
    "sexart", "x-art", "xart", "metart", "metartx",
    "evil angel", "evilangel", "julesjordan", "manuelferrara",
    "kink", "boundgangbangs",
    "wicked", "sweetsinner", "newsensations",
    "dorcelclub", "dorcel", "private",
    "legalporno", "analvids", "gonzo",
    "spizoo", "nfbusty", "nubilefilms", "nubiles",
    "passion-hd", "passionhd", "fantasyhd", "puremature",
    "rkprime", "bignaturals", "bigtitcreampie",
    "propertysex", "castingcouch", "woodmancastingx", "czechcasting",
    "bang", "mofos", "stranded teens", "strandedteens",
    "letsdoeit", "doeprojects",
}


def _normalize(text: str) -> str:
    """Lowercase, strip non-alphanumeric except spaces, collapse whitespace."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return ' '.join(text.split())


def _clean_name(name: str) -> str:
    """Reduce an actor name to comparable lowercase alpha form."""
    return re.sub(r'[^a-z]', '', name.lower())


_STOPWORDS = {"the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "with"}


def _name_token_set(names: list[str]) -> set[str]:
    """Return normalized word tokens from performer names."""
    tokens: set[str] = set()
    for name in names:
        tokens.update(_normalize(name).split())
    return tokens


def _add_unique_query(queries: list[str], query: str) -> None:
    """Append a cleaned search query if it is meaningful and not already present."""
    normalized = ' '.join(query.split())
    if len(normalized) < 3:
        return
    if normalized.lower() not in {q.lower() for q in queries}:
        queries.append(normalized)


def _parse_filename(filename: str) -> dict:
    """
    Parse a video filename into structured parts:
      - raw_stem: the filename without extension
      - tokens: list of cleaned tokens (noise removed)
      - date_hint: extracted date string if present (e.g. '2023-01-15' or '23.01.15')
      - cleaned: the cleaned search string
    """
    stem = Path(filename).stem

    # Try to extract a date (YYYY-MM-DD, YYYY.MM.DD, YY.MM.DD)
    date_hint = None
    date_match = re.search(r'(\d{4})[.\-](\d{2})[.\-](\d{2})', stem)
    if not date_match:
        date_match = re.search(r'(\d{2})[.\-](\d{2})[.\-](\d{2})', stem)
    if date_match:
        date_hint = date_match.group(0)
        stem = stem[:date_match.start()] + stem[date_match.end():]

    # Replace separators with spaces and normalize punctuation before tokenizing.
    cleaned = re.sub(r'[_.\-\[\](){}]', ' ', stem)
    cleaned = _normalize(cleaned)

    # Remove part/scene numbering: pt1, part2, s01e02, ep3, scene4, etc.
    cleaned = re.sub(r'\b(?:pt|part|ep|episode|s\d+e)\s*\d+\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b(?:scene)\s*\d+\b', '', cleaned, flags=re.IGNORECASE)

    # Remove standalone short numbers (likely scene/part numbers, not years)
    cleaned = re.sub(r'\b\d{1,3}\b', '', cleaned)

    # Tokenize
    tokens_raw = cleaned.lower().split()

    # Remove noise tokens and known studios
    tokens = []
    for t in tokens_raw:
        if t in _NOISE_TOKENS:
            continue
        if t in _KNOWN_STUDIOS:
            continue
        if len(t) < 2:
            continue
        tokens.append(t)

    return {
        "raw_stem": Path(filename).stem,
        "tokens": tokens,
        "date_hint": date_hint,
        "cleaned": ' '.join(tokens),
    }


def _find_actor_tokens(tokens: list[str], known_actor_names: list[str]) -> tuple[list[str], list[str]]:
    """
    Given filename tokens and known actor names, split into (actor_parts, remaining_parts).
    Tries to match consecutive tokens against known multi-word actor names.
    """
    if not known_actor_names:
        return [], tokens

    # Build a set of normalised actor name token sequences
    actor_patterns = []
    for name in known_actor_names:
        parts = _normalize(name).split()
        if parts:
            actor_patterns.append(parts)

    matched_indices = set()
    for pattern in actor_patterns:
        plen = len(pattern)
        for i in range(len(tokens) - plen + 1):
            window = tokens[i:i + plen]
            if all(_clean_name(w) == _clean_name(p) for w, p in zip(window, pattern)):
                for j in range(i, i + plen):
                    matched_indices.add(j)

    actor_parts = [tokens[i] for i in sorted(matched_indices)]
    remaining = [tokens[i] for i in range(len(tokens)) if i not in matched_indices]

    return actor_parts, remaining


def _filename_exact_queries(filename: str) -> list[str]:
    """Build exact StashDB text-search phrases before actor/studio token stripping."""
    stem = Path(filename).stem
    stem = re.sub(r'[_]+', ' ', stem)
    stem = ' '.join(stem.split())

    queries: list[str] = []
    _add_unique_query(queries, stem)

    # Also try the title without a leading "[Studio]" prefix while preserving
    # performer names. StashDB exact search often likes "Actor - Title" style
    # strings, but bracketed site tags can be inconsistent.
    without_bracket_prefix = re.sub(r'^\s*\[[^\]]+\]\s*', '', stem).strip()
    if without_bracket_prefix != stem:
        _add_unique_query(queries, without_bracket_prefix)

    return queries


def calculate_match_score(
    filename: str,
    scene_title: str,
    scene_studio: str,
    scene_date: str | None,
    detected_actors: list[str],
    scene_performers: list[str],
) -> int:
    """
    Calculate a match score (0-100) between a local video file and a StashDB scene.
    Uses multiple signals: title overlap, performer match, studio match, date match.
    """
    parsed = _parse_filename(filename)
    actor_tokens = _name_token_set(detected_actors + scene_performers)
    fn_tokens = set(parsed["tokens"]) - actor_tokens

    # ── Title overlap (Jaccard on meaningful tokens) ──
    title_norm = _normalize(scene_title or "")
    title_tokens = set(title_norm.split()) - _STOPWORDS - actor_tokens
    
    text_score = 0.0
    if fn_tokens and title_tokens:
        intersection = fn_tokens.intersection(title_tokens)
        # Use title-weighted Jaccard: how much of the *title* is covered by filename tokens
        title_recall = len(intersection) / len(title_tokens) if title_tokens else 0.0
        # Also consider standard Jaccard for balance
        union = fn_tokens.union(title_tokens)
        jaccard = len(intersection) / len(union) if union else 0.0
        text_score = (title_recall * 0.7 + jaccard * 0.3)
        if title_recall == 1.0:
            text_score = max(text_score, 0.95)

    # ── Studio match ──
    studio_score = 0.0
    if scene_studio:
        studio_norm = _normalize(scene_studio)
        studio_tokens = set(studio_norm.split())
        raw_fn = _normalize(Path(filename).stem)
        raw_fn_tokens = set(raw_fn.split())
        if studio_tokens and studio_tokens.issubset(raw_fn_tokens):
            studio_score = 1.0
        elif studio_tokens:
            overlap = studio_tokens.intersection(raw_fn_tokens)
            studio_score = len(overlap) / len(studio_tokens)

    # ── Performer / Actor match ──
    actor_score = 0.0
    if detected_actors and scene_performers:
        det_set = {_clean_name(a) for a in detected_actors}
        perf_set = {_clean_name(p) for p in scene_performers}
        if det_set and perf_set:
            matched = det_set.intersection(perf_set)
            # Recall: how many of our detected actors appear in the scene
            actor_recall = len(matched) / len(det_set)
            # Precision: how many of the scene's performers we detected
            actor_precision = len(matched) / len(perf_set)
            actor_score = (actor_recall * 0.6 + actor_precision * 0.4)
    elif not detected_actors and scene_performers:
        # No detected actors: check if performer names appear in the filename
        raw_fn = _normalize(Path(filename).stem)
        name_hits = 0
        for p in scene_performers:
            p_clean = _clean_name(p)
            if p_clean and p_clean in raw_fn.replace(' ', ''):
                name_hits += 1
        if scene_performers:
            actor_score = name_hits / len(scene_performers) * 0.5  # Lower weight

    # ── Date match ──
    date_score = 0.0
    if parsed["date_hint"] and scene_date:
        # Simple: if the scene date appears somewhere in the filename date hint
        scene_date_clean = scene_date.replace('-', '')
        date_hint_clean = re.sub(r'[^0-9]', '', parsed["date_hint"])
        if scene_date_clean in date_hint_clean or date_hint_clean in scene_date_clean:
            date_score = 1.0

    # ── Weighted combination ──
    # Different weights depending on what signals are available
    if detected_actors:
        # With face recognition data: actors matter most
        combined = (
            text_score * 0.30
            + actor_score * 0.45
            + studio_score * 0.15
            + date_score * 0.10
        )
    else:
        # Without actors: rely more on text + studio
        combined = (
            text_score * 0.55
            + studio_score * 0.25
            + actor_score * 0.10  # name-in-filename heuristic
            + date_score * 0.10
        )

    return min(100, max(0, int(combined * 100)))


def _query_stashdb_scenes(search_text: str, per_page: int = 10) -> list[dict]:
    """Execute a single StashDB scene search and return raw scene dicts."""
    headers = {
        "ApiKey": settings.stashdb_api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    variables = {
        "input": {
            "text": search_text,
            "page": 1,
            "per_page": per_page,
        }
    }
    try:
        resp = requests.post(
            settings.stashdb_api_url,
            json={"query": QUERY_SEARCH_SCENES, "variables": variables},
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("errors"):
            print(f"[SmartSearch] StashDB error for query '{search_text}': {payload['errors']}")
            return []
        data = payload.get("data") or {}
        return (data.get("queryScenes") or {}).get("scenes") or []
    except requests.RequestException as e:
        print(f"[SmartSearch] StashDB request failed for query '{search_text}': {e}")
        return []


def _extract_stashdb_scene_id(scene_url: str) -> str:
    """Extract a StashDB scene UUID from a pasted URL or raw ID."""
    match = re.search(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        scene_url.strip(),
    )
    if not match:
        raise HTTPException(status_code=400, detail="Could not find a StashDB scene ID in the pasted URL")
    return match.group(0)


def _fetch_stashdb_scene(scene_id: str) -> dict:
    """Fetch a StashDB scene by ID."""
    headers = {
        "ApiKey": settings.stashdb_api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        resp = requests.post(
            settings.stashdb_api_url,
            json={"query": QUERY_FIND_SCENE, "variables": {"id": scene_id}},
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to communicate with StashDB: {str(e)}")

    if payload.get("errors"):
        raise HTTPException(status_code=502, detail=f"StashDB GraphQL errors: {payload['errors']}")

    scene = (payload.get("data") or {}).get("findScene")
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found on StashDB")
    return scene


def _download_stashdb_cover(video_id: int, cover_url: Optional[str]) -> bool:
    """Download a StashDB cover image into the local thumbnails directory."""
    if not cover_url:
        return False
    if not cover_url.startswith("http"):
        cover_url = f"https:{cover_url}"

    thumbnails_dir = Path(settings.base_dir) / "thumbnails"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumbnails_dir / f"{video_id}.jpg"

    try:
        img_res = requests.get(cover_url, stream=True, timeout=15)
        img_res.raise_for_status()
        with open(thumb_path, "wb") as f:
            for chunk in img_res.iter_content(1024 * 64):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"Failed to download StashDB cover image: {e}")
        return False


def _scene_response(scene: dict, cover_downloaded: bool) -> dict:
    studio_name = scene.get("studio", {}).get("name") if scene.get("studio") else None
    performers = [p["performer"]["name"] for p in scene.get("performers") or []]
    images = scene.get("images") or []
    cover_url = images[0].get("url") if images else None
    return {
        "status": "success",
        "scene_id": scene["id"],
        "title": scene.get("title"),
        "studio": studio_name,
        "date": scene.get("date"),
        "cover_url": cover_url,
        "cover_downloaded": cover_downloaded,
        "performers": performers,
    }


def _build_search_queries(filename: str, detected_actors: list[str], all_db_actors: list[str]) -> list[str]:
    """
    Generate a list of search queries to try, ordered from most specific to broadest.
    Each query targets a different combination of filename tokens and actor names.
    """
    parsed = _parse_filename(filename)
    tokens = parsed["tokens"]
    queries: list[str] = []
    known_actor_names = detected_actors + all_db_actors

    for query in _filename_exact_queries(filename):
        _add_unique_query(queries, query)

    _, title_tokens = _find_actor_tokens(tokens, known_actor_names)
    title_tokens_no_stop = [token for token in title_tokens if token not in _STOPWORDS]

    # StashDB scene text search behaves much better with title-only queries than
    # with "performer + title" in one string. Score performers locally instead.
    if title_tokens:
        _add_unique_query(queries, ' '.join(title_tokens))
    if title_tokens_no_stop and title_tokens_no_stop != title_tokens:
        _add_unique_query(queries, ' '.join(title_tokens_no_stop))

    # Full cleaned filename remains useful when it does not mix a recognized
    # performer name with the title. StashDB text search often fails on that mix.
    if tokens and title_tokens == tokens:
        _add_unique_query(queries, ' '.join(tokens))

    # If we have detected actors, keep a narrow title fallback and actor-only fallback.
    if detected_actors:
        actor_str = ' '.join(detected_actors)
        if title_tokens_no_stop:
            _add_unique_query(queries, ' '.join(title_tokens_no_stop[:4]))
        _add_unique_query(queries, actor_str)

    # Try extracting likely "proper names" from tokens (capitalised bigrams in original stem).
    stem_parts = re.sub(r'[_.\-\[\](){}]', ' ', Path(filename).stem).split()
    name_candidates = []
    i = 0
    while i < len(stem_parts):
        # Look for sequences of capitalised words (likely actor names)
        if stem_parts[i] and stem_parts[i][0].isupper() and stem_parts[i].lower() not in _NOISE_TOKENS and stem_parts[i].lower() not in _KNOWN_STUDIOS:
            name_parts = [stem_parts[i]]
            j = i + 1
            while j < len(stem_parts) and stem_parts[j] and stem_parts[j][0].isupper() and stem_parts[j].lower() not in _NOISE_TOKENS:
                name_parts.append(stem_parts[j])
                j += 1
            if len(name_parts) >= 2:
                name_candidates.append(' '.join(name_parts))
            i = j
        else:
            i += 1

    if name_candidates and not detected_actors and not title_tokens_no_stop:
        name_query = ' '.join(name_candidates)
        _add_unique_query(queries, name_query)

    # Shorter keyword combos are broad fallbacks.
    fallback_tokens = title_tokens_no_stop or tokens
    if len(fallback_tokens) > 3:
        _add_unique_query(queries, ' '.join(fallback_tokens[:3]))

    # If date was found, try date + title tokens.
    if parsed["date_hint"]:
        date_clean = parsed["date_hint"].replace('.', '-')
        _add_unique_query(queries, f"{date_clean} {' '.join(fallback_tokens[:2])}")

    return queries


@router.post("/{video_id}/search-stashdb")
def search_stashdb_candidates(video_id: int):
    """
    Smart multi-strategy StashDB scene search.
    
    Generates multiple search queries from the filename and detected actors,
    runs them against StashDB, deduplicates results, and scores each candidate.
    Returns candidates sorted by match score with debug info about which queries matched.
    """
    if not settings.stashdb_api_key:
        raise HTTPException(
            status_code=400,
            detail="StashDB API Key is not set. Please add STASHDB_API_KEY to your .env file."
        )

    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        video = conn.execute("SELECT filename FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        filename = video["filename"]

        # Get detected actors for this video
        actors = conn.execute(
            """SELECT DISTINCT a.name FROM video_detections vd 
               JOIN actors a ON vd.actor_id = a.id 
               WHERE vd.video_id = ?""",
            (video_id,)
        ).fetchall()
        detected_actors = [r["name"] for r in actors]

        # Get all known actor names from DB for name-matching in filename
        all_actors = conn.execute("SELECT name FROM actors").fetchall()
        all_db_actors = [r["name"] for r in all_actors]

    # Generate search queries
    queries = _build_search_queries(filename, detected_actors, all_db_actors)
    print(f"[SmartSearch] Video '{filename}' -> {len(queries)} queries: {queries}")

    # Run searches and collect unique results
    seen_ids: set[str] = set()
    all_scenes: list[dict] = []
    query_log: list[dict] = []

    for i, query in enumerate(queries):
        scenes = _query_stashdb_scenes(query, per_page=10)
        new_count = 0
        for scene in scenes:
            sid = scene["id"]
            if sid not in seen_ids:
                seen_ids.add(sid)
                all_scenes.append(scene)
                new_count += 1
        query_log.append({"query": query, "results": len(scenes), "new": new_count})
        
        # Stop early if we have enough candidates
        if len(all_scenes) >= 20:
            break

    print(f"[SmartSearch] Query results: {query_log}")

    # Score and format candidates
    candidates = []
    for scene in all_scenes:
        scene_id = scene["id"]
        title = scene.get("title") or ""
        studio_name = scene.get("studio", {}).get("name") if scene.get("studio") else None
        performers = [p["performer"]["name"] for p in scene.get("performers") or []]
        scene_date = scene.get("date")

        images = scene.get("images") or []
        cover_url = images[0].get("url") if images else None

        score = calculate_match_score(
            filename, title, studio_name or "", scene_date,
            detected_actors, performers
        )

        candidates.append({
            "scene_id": scene_id,
            "title": title,
            "studio": studio_name,
            "date": scene_date,
            "cover_url": cover_url,
            "performers": performers,
            "score": score,
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Return top 15 candidates max
    return {
        "candidates": candidates[:15],
        "search_info": {
            "filename": filename,
            "detected_actors": detected_actors,
            "queries_used": query_log,
            "total_unique_results": len(all_scenes),
        }
    }

@router.post("/{video_id}/link-stashdb")
def link_stashdb(
    video_id: int,
    scene_id: str = Body(..., embed=True),
    title: str = Body(..., embed=True),
    studio: Optional[str] = Body(None, embed=True),
    cover_url: Optional[str] = Body(None, embed=True),
    performers: Optional[list[str]] = Body(None, embed=True),
):
    """Links a video to a specific StashDB scene, downloading the cover image if available."""
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        exists = conn.execute("SELECT 1 FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Video not found")

    cover_downloaded = _download_stashdb_cover(video_id, cover_url)
            
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE videos SET stashdb_scene_id = ?, stashdb_performers = ?, updated_at = datetime('now') WHERE id = ?",
            (scene_id, json.dumps(performers or []), video_id)
        )
        conn.commit()
        
    return {
        "status": "success",
        "scene_id": scene_id,
        "cover_downloaded": cover_downloaded
    }


@router.post("/{video_id}/link-stashdb-url")
def link_stashdb_url(
    video_id: int,
    scene_url: str = Body(..., embed=True),
):
    """Fetch a StashDB scene from a pasted URL/ID, link it, and download its cover."""
    if not settings.stashdb_api_key:
        raise HTTPException(
            status_code=400,
            detail="StashDB API Key is not set. Please add STASHDB_API_KEY to your .env file."
        )

    scene_id = _extract_stashdb_scene_id(scene_url)
    scene = _fetch_stashdb_scene(scene_id)
    images = scene.get("images") or []
    cover_url = images[0].get("url") if images else None
    cover_downloaded = _download_stashdb_cover(video_id, cover_url)
    scene_data = _scene_response(scene, cover_downloaded)

    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        exists = conn.execute("SELECT 1 FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Video not found")
        conn.execute(
            "UPDATE videos SET stashdb_scene_id = ?, stashdb_performers = ?, updated_at = datetime('now') WHERE id = ?",
            (scene_id, json.dumps(scene_data["performers"]), video_id)
        )
        conn.commit()

    return scene_data

@router.post("/{video_id}/actors/{actor_id}", status_code=201)
def add_actor_to_video(video_id: int, actor_id: int):
    """Manually links an actor to a video by creating a presence detection record."""
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        # Verify actor exists
        actor = conn.execute("SELECT 1 FROM actors WHERE id = ?", (actor_id,)).fetchone()
        if not actor:
            raise HTTPException(status_code=404, detail="Actor not found")
        # Verify video exists
        video = conn.execute("SELECT 1 FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
            
        # Check if already exists
        exists = conn.execute(
            "SELECT 1 FROM video_detections WHERE video_id = ? AND actor_id = ? LIMIT 1",
            (video_id, actor_id)
        ).fetchone()
        if not exists:
            conn.execute(
                """INSERT INTO video_detections (video_id, actor_id, timestamp, bbox, confidence) 
                   VALUES (?, ?, 0.0, '[]', 1.0)""",
                (video_id, actor_id)
            )
            conn.commit()
    return {"status": "success"}

@router.delete("/{video_id}/actors/{actor_id}", status_code=204)
def remove_actor_from_video(video_id: int, actor_id: int):
    """Manually removes an actor from a video by deleting all their detection records."""
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "DELETE FROM video_detections WHERE video_id = ? AND actor_id = ?",
            (video_id, actor_id)
        )
        conn.commit()
    return None
