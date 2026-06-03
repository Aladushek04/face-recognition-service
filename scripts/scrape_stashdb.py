"""Import StashDB performer metadata into the local actor database.

Usage:
    set STASHDB_API_KEY=<your token>
    python scripts/scrape_stashdb.py --limit 50

Optional:
    python scripts/scrape_stashdb.py --query "Jane" --limit 20 --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Add the project root to the path so we can import backend modules.
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from config import settings  # noqa: E402
from database import actor_db  # noqa: E402


API_URL = os.getenv("STASHDB_API_URL", "https://stashdb.org/graphql")
API_KEY = os.getenv("STASHDB_API_KEY", "")
REQUEST_DELAY = 2.0
DEFAULT_LIMIT = 50
DEFAULT_PAGE_SIZE = 50
GENDER_FILTERS = {
    "unknown": "UNKNOWN",
    "male": "MALE",
    "female": "FEMALE",
    "transgender_male": "TRANSGENDER_MALE",
    "trans_male": "TRANSGENDER_MALE",
    "transgender_female": "TRANSGENDER_FEMALE",
    "trans_female": "TRANSGENDER_FEMALE",
    "intersex": "INTERSEX",
    "non_binary": "NON_BINARY",
}
BREAST_TYPE_FILTERS = {
    "natural": "NATURAL",
    "augmented": "FAKE",
    "fake": "FAKE",
    "na": "NA",
}


QUERY_PERFORMERS = """
query QueryPerformers($input: PerformerQueryInput!) {
  queryPerformers(input: $input) {
    count
    performers {
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
}
"""


class StashDBError(RuntimeError):
    """Raised when StashDB returns an HTTP or GraphQL error."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import performers from StashDB into data/db/actors.db.",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum new performers to import.")
    parser.add_argument("--max-seen", type=int, help="Stop after scanning this many performers, even if limit is not met.")
    parser.add_argument("--all", action="store_true", help="Import every page returned by StashDB.")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="StashDB page size.")
    parser.add_argument("--start-page", type=int, default=1, help="First StashDB page to read.")
    parser.add_argument("--resume-page", type=int, help="Alias for --start-page when resuming after an interruption.")
    parser.add_argument("--retries", type=int, default=5, help="GraphQL request retry count for network/5xx errors.")
    parser.add_argument("--retry-delay", type=float, default=5.0, help="Initial retry delay in seconds.")
    parser.add_argument("--query", default=None, help="Optional performer search string.")
    parser.add_argument(
        "--gender",
        choices=sorted(GENDER_FILTERS),
        help="Optional gender filter, for example: female, male, transgender_female.",
    )
    parser.add_argument(
        "--breast-type",
        choices=sorted(BREAST_TYPE_FILTERS),
        help="Optional breast type filter: natural, augmented, fake, na.",
    )
    parser.add_argument("--min-scenes", type=int, help="Skip performers with fewer scenes than this.")
    parser.add_argument("--min-birth-year", type=int, help="Only include performers born in or after this year.")
    parser.add_argument("--max-birth-year", type=int, help="Only include performers born in or before this year.")
    parser.add_argument("--birthdate", help="Only include performers with this exact birthdate, YYYY-MM-DD.")
    parser.add_argument("--birthdate-from", help="Only include performers born on or after this date, YYYY-MM-DD.")
    parser.add_argument("--birthdate-to", help="Only include performers born on or before this date, YYYY-MM-DD.")
    parser.add_argument("--active-from", type=int, help="Only include performers active during or after this year.")
    parser.add_argument("--active-to", type=int, help="Only include performers active during or before this year.")
    parser.add_argument(
        "--sort",
        default="NAME",
        choices=[
            "NAME",
            "BIRTHDATE",
            "DEATHDATE",
            "SCENE_COUNT",
            "CAREER_START_YEAR",
            "DEBUT",
            "LAST_SCENE",
            "CREATED_AT",
            "UPDATED_AT",
        ],
        help="StashDB performer sort field.",
    )
    parser.add_argument("--direction", default="ASC", choices=["ASC", "DESC"], help="Sort direction.")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY, help="Delay between performers in seconds.")
    parser.add_argument("--require-image", action="store_true", help="Skip performers without a profile image URL.")
    parser.add_argument("--no-images", action="store_true", help="Import metadata without downloading images.")
    parser.add_argument(
        "--image-count",
        type=int,
        default=1,
        help="How many performer images to download. Use 0 to download all available images.",
    )
    parser.add_argument(
        "--image-order",
        choices=["largest", "first", "last"],
        default="largest",
        help="Which images to prefer: largest resolution, API order from start, or API order from end.",
    )
    parser.add_argument(
        "--validate-image-faces",
        action="store_true",
        help="Only keep downloaded reference images where the face detector finds a usable face.",
    )
    parser.add_argument(
        "--min-face-area-ratio",
        type=float,
        default=0.01,
        help="Minimum detected face bbox area relative to image area when --validate-image-faces is enabled.",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update StashDB metadata for existing performers instead of only skipping them.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print candidates without writing DB/files.")
    return parser.parse_args()


def headers() -> dict[str, str]:
    if not API_KEY:
        raise StashDBError(
            "STASHDB_API_KEY is not set. Put it in .env or set it in the shell before running."
        )

    return {
        "ApiKey": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def post_graphql(
    query: str,
    variables: dict[str, Any],
    *,
    retries: int,
    retry_delay: float,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(max(retries, 0) + 1):
        try:
            response = requests.post(
                API_URL,
                json={"query": query, "variables": variables},
                headers=headers(),
                timeout=45,
            )
        except requests.RequestException as exc:
            last_error = exc
            if attempt < retries:
                delay = retry_delay * (2 ** attempt)
                print(f"Request failed ({exc}). Retrying in {delay:.1f}s... [{attempt + 1}/{retries}]")
                time.sleep(delay)
                continue
            raise StashDBError(f"Request failed before StashDB responded: {exc}") from exc

        if response.status_code in {429, 500, 502, 503, 504} and attempt < retries:
            delay = retry_delay * (2 ** attempt)
            print(
                f"StashDB HTTP {response.status_code}. Retrying in {delay:.1f}s... "
                f"[{attempt + 1}/{retries}]"
            )
            time.sleep(delay)
            continue
        break
    else:
        raise StashDBError(f"Request failed after retries: {last_error}")

    try:
        payload = response.json()
    except ValueError as exc:
        body = response.text[:500].replace("\n", " ")
        raise StashDBError(f"StashDB returned non-JSON HTTP {response.status_code}: {body}") from exc

    if response.status_code >= 400:
        errors = payload.get("errors") or payload
        raise StashDBError(f"StashDB HTTP {response.status_code}: {errors}")

    if payload.get("errors"):
        raise StashDBError(f"StashDB GraphQL errors: {payload['errors']}")

    return payload.get("data") or {}


def fetch_performer_page(
    *,
    page: int,
    page_size: int,
    query_text: str | None,
    gender: str | None,
    breast_type: str | None,
    min_birth_year: int | None,
    max_birth_year: int | None,
    sort: str,
    direction: str,
    retries: int,
    retry_delay: float,
) -> dict[str, Any]:
    input_filter: dict[str, Any] = {
        "page": page,
        "per_page": page_size,
        "sort": sort,
        "direction": direction,
    }
    if query_text:
        input_filter["names"] = query_text
    if gender:
        input_filter["gender"] = GENDER_FILTERS[gender]
    if breast_type:
        input_filter["breast_type"] = {
            "value": BREAST_TYPE_FILTERS[breast_type],
            "modifier": "EQUALS",
        }
    if min_birth_year is not None:
        input_filter["birth_year"] = {
            "value": min_birth_year - 1,
            "modifier": "GREATER_THAN",
        }
    if max_birth_year is not None:
        if "birth_year" in input_filter:
            # StashDB accepts one IntCriterionInput per field, so stricter ranges
            # that need both ends are finished locally after fetching.
            pass
        else:
            input_filter["birth_year"] = {
                "value": max_birth_year + 1,
                "modifier": "LESS_THAN",
            }

    data = post_graphql(
        QUERY_PERFORMERS,
        {"input": input_filter},
        retries=retries,
        retry_delay=retry_delay,
    )
    result = data.get("queryPerformers")
    if not result:
        raise StashDBError(f"Unexpected StashDB response shape: {data}")
    return result


def safe_actor_dir_name(name: str) -> str:
    cleaned = re.sub(r"[^\w .'-]+", "", name, flags=re.UNICODE).strip()
    return cleaned.replace(" ", "_") or "Unknown"


def birth_year_from_birthdate(birthdate: dict[str, Any] | str | None) -> int | None:
    if not birthdate:
        return None
    if isinstance(birthdate, dict):
        year = birthdate.get("year")
        if isinstance(year, int):
            return year
        birthdate = birthdate.get("date")
        if not birthdate:
            return None
    match = re.match(r"^(\d{4})", birthdate)
    return int(match.group(1)) if match else None


def performer_birthdate(performer: dict[str, Any]) -> dict[str, Any] | str | None:
    """Return the birth date value from old or current StashDB field names."""
    return performer.get("birth_date") or performer.get("birthdate")


def birthdate_value(birthdate: dict[str, Any] | str | None) -> str | None:
    if not birthdate:
        return None
    if isinstance(birthdate, dict):
        value = birthdate.get("date")
        if value:
            return value
        year = birthdate.get("year")
        month = birthdate.get("month")
        day = birthdate.get("day")
        if isinstance(year, int) and isinstance(month, int) and isinstance(day, int):
            return f"{year:04d}-{month:02d}-{day:02d}"
        return None
    return birthdate


def normalize_gender(value: str | None) -> str:
    gender = (value or "").lower()
    if gender in {"female", "male"}:
        return gender
    return "other"


def normalize_enum(value: str | None) -> str | None:
    """Convert StashDB enum values into compact display text."""
    if not value:
        return None
    return value.replace("_", " ").title()


def build_measurements(performer: dict[str, Any]) -> str | None:
    cup_size = performer.get("cup_size")
    band_size = performer.get("band_size")
    waist_size = performer.get("waist_size")
    hip_size = performer.get("hip_size")
    if not any([cup_size, band_size, waist_size, hip_size]):
        return None

    bust = f"{band_size or ''}{cup_size or ''}".strip()
    parts = [bust or None, waist_size, hip_size]
    return "-".join(str(part) for part in parts if part not in {None, ""}) or None


def body_modifications(items: list[dict[str, Any]] | None) -> list[str]:
    values: list[str] = []
    for item in items or []:
        location = item.get("location")
        description = item.get("description")
        if location and description:
            values.append(f"{location}: {description}")
        elif location:
            values.append(location)
        elif description:
            values.append(description)
    return values


def build_bio(performer: dict[str, Any]) -> str:
    parts: list[str] = []
    if performer.get("disambiguation"):
        parts.append(f"Disambiguation: {performer['disambiguation']}")

    urls = [entry.get("url") for entry in performer.get("urls", []) if entry.get("url")]
    if urls:
        parts.append(f"URLs: {', '.join(urls[:5])}")

    return ". ".join(parts)[:1000]


def build_filmography(performer: dict[str, Any]) -> str | None:
    start = performer.get("career_start_year")
    end = performer.get("career_end_year")
    if start and end:
        return f"Career: {start}-{end}"
    if start:
        return f"Career start: {start}"
    if end:
        return f"Career end: {end}"
    return None


def normalize_image_url(url: str) -> str:
    return url if url.startswith("http") else f"https:{url}"


def image_candidates(performer: dict[str, Any], *, order: str = "largest") -> list[str]:
    images = performer.get("images") or []
    if order == "largest":
        images = sorted(
            images,
            key=lambda item: (item.get("width") or 0) * (item.get("height") or 0),
            reverse=True,
        )
    elif order == "last":
        images = list(reversed(images))

    urls: list[str] = []
    seen: set[str] = set()
    for item in images:
        url = item.get("url")
        if not url:
            continue
        normalized = normalize_image_url(url)
        if normalized not in seen:
            urls.append(normalized)
            seen.add(normalized)
    return urls


def stashdb_urls(performer: dict[str, Any]) -> list[str]:
    """Return external URLs attached to the StashDB performer."""
    return [entry["url"] for entry in performer.get("urls", []) if entry.get("url")]


def performer_metadata(performer: dict[str, Any], image_urls: list[str]) -> dict[str, Any]:
    """Build actor_db metadata kwargs from a StashDB performer."""
    gender = normalize_gender(performer.get("gender"))
    return {
        "stashdb_id": performer.get("id"),
        "birth_year": birth_year_from_birthdate(performer_birthdate(performer)),
        "birthdate": birthdate_value(performer_birthdate(performer)),
        "gender": gender,
        "aliases": performer.get("aliases") or [],
        "scene_count": performer.get("scene_count"),
        "breast_type": performer.get("breast_type"),
        "height_cm": performer.get("height"),
        "measurements": build_measurements(performer),
        "cup_size": performer.get("cup_size"),
        "band_size": performer.get("band_size"),
        "waist_size": performer.get("waist_size"),
        "hip_size": performer.get("hip_size"),
        "country": performer.get("country"),
        "ethnicity": normalize_enum(performer.get("ethnicity")),
        "eye_color": normalize_enum(performer.get("eye_color")),
        "hair_color": normalize_enum(performer.get("hair_color")),
        "tattoos": body_modifications(performer.get("tattoos")),
        "piercings": body_modifications(performer.get("piercings")),
        "career_start_year": performer.get("career_start_year"),
        "career_end_year": performer.get("career_end_year"),
        "image_url": image_urls[0] if image_urls else None,
        "stashdb_urls": stashdb_urls(performer),
        "bio": build_bio(performer),
        "filmography": build_filmography(performer),
        "tags": ["stashdb", "adult", gender],
    }


def passes_local_filters(
    performer: dict[str, Any],
    *,
    breast_type: str | None,
    min_scenes: int | None,
    min_birth_year: int | None,
    max_birth_year: int | None,
    birthdate: str | None,
    birthdate_from: str | None,
    birthdate_to: str | None,
    active_from: int | None,
    active_to: int | None,
    require_image: bool,
) -> tuple[bool, str | None]:
    if require_image and not image_candidates(performer):
        return False, "no profile image"

    scene_count = performer.get("scene_count")
    if min_scenes is not None and (not isinstance(scene_count, int) or scene_count < min_scenes):
        return False, f"scene_count={scene_count}"

    if breast_type is not None:
        expected_breast_type = BREAST_TYPE_FILTERS[breast_type]
        actual_breast_type = performer.get("breast_type")
        if actual_breast_type != expected_breast_type:
            return False, f"breast_type={actual_breast_type}"

    birth_year = birth_year_from_birthdate(performer_birthdate(performer))
    if min_birth_year is not None and (birth_year is None or birth_year < min_birth_year):
        return False, f"birth_year={birth_year}"
    if max_birth_year is not None and (birth_year is None or birth_year > max_birth_year):
        return False, f"birth_year={birth_year}"

    actual_birthdate = birthdate_value(performer_birthdate(performer))
    if birthdate is not None and actual_birthdate != birthdate:
        return False, f"birthdate={actual_birthdate}"
    if birthdate_from is not None and (actual_birthdate is None or actual_birthdate < birthdate_from):
        return False, f"birthdate={actual_birthdate}"
    if birthdate_to is not None and (actual_birthdate is None or actual_birthdate > birthdate_to):
        return False, f"birthdate={actual_birthdate}"

    if active_from is not None or active_to is not None:
        career_start = performer.get("career_start_year")
        career_end = performer.get("career_end_year")
        if not isinstance(career_start, int):
            return False, f"career={career_start}-{career_end}"
        interval_start = active_from if active_from is not None else -9999
        interval_end = active_to if active_to is not None else 9999
        performer_end = career_end if isinstance(career_end, int) else 9999
        if career_start > interval_end or performer_end < interval_start:
            return False, f"career={career_start}-{career_end or ''}"

    return True, None


def download_image(url: str, save_path: Path) -> bool:
    try:
        response = requests.get(url, stream=True, timeout=20)
        response.raise_for_status()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as file:
            for chunk in response.iter_content(1024 * 64):
                if chunk:
                    file.write(chunk)
        return True
    except requests.RequestException as exc:
        print(f"   -> Image failed: {exc}")
        return False


def image_has_usable_face(image_path: Path, min_face_area_ratio: float) -> bool:
    from models.face_detector import FaceDetector  # noqa: PLC0415
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    image_bytes = np.fromfile(str(image_path), dtype=np.uint8)
    image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
    if image is None:
        return False
    height, width = image.shape[:2]
    image_area = max(width * height, 1)

    detector = FaceDetector()
    if not detector.model_loaded:
        print("   -> Face validation skipped: detector model is not loaded.")
        return True

    try:
        faces = detector.detect_faces(image)
    except Exception as exc:
        print(f"   -> Face validation failed: {exc}")
        return False

    for face in faces:
        x1, y1, x2, y2 = face["bbox"]
        face_area = max(x2 - x1, 0) * max(y2 - y1, 0)
        if face_area / image_area >= min_face_area_ratio:
            return True
    return False


def download_performer_images(
    *,
    actor_id: int,
    actor_name: str,
    image_urls: list[str],
    image_count: int,
    validate_faces: bool,
    min_face_area_ratio: float,
) -> None:
    if not image_urls:
        print("   -> No profile image found.")
        return

    selected_urls = image_urls if image_count == 0 else image_urls[: max(image_count, 1)]
    actor_dir = settings.actors_dir / safe_actor_dir_name(actor_name)
    existing_filenames = {image["filename"] for image in actor_db.get_actor_images(actor_id)}
    saved = 0
    for index, image_url in enumerate(selected_urls, start=1):
        image_path = actor_dir / f"profile_{index:02d}.jpg"
        if image_path.name in existing_filenames or image_path.exists():
            print(f"   -> Image {index} already exists. Skipping.")
            continue
        if not download_image(image_url, image_path):
            continue

        if validate_faces and not image_has_usable_face(image_path, min_face_area_ratio):
            image_path.unlink(missing_ok=True)
            print(f"   -> Image {index} rejected: no usable face detected.")
            continue

        actor_db.add_actor_image(actor_id, image_path.name, str(image_path))
        saved += 1
        print(f"   -> Image {index} downloaded.")

    if saved == 0:
        print("   -> No usable reference images saved.")


def update_existing_actor(actor: dict, performer: dict[str, Any], *, dry_run: bool) -> None:
    """Update StashDB metadata columns for an existing actor."""
    image_urls = image_candidates(performer)
    if dry_run:
        print(f"   -> Dry run: would update metadata for existing ID {actor['id']}.")
        return

    actor_db.update_actor(actor_id=actor["id"], **performer_metadata(performer, image_urls))
    print(f"   -> Updated metadata for existing ID {actor['id']}.")


def import_performer(
    performer: dict[str, Any],
    *,
    download_images: bool,
    image_count: int,
    image_order: str,
    validate_image_faces: bool,
    min_face_area_ratio: float,
    dry_run: bool,
    update_existing: bool,
) -> bool:
    name = performer.get("name") or "Unknown"
    stashdb_id = performer.get("id")
    image_urls = image_candidates(performer, order=image_order)

    if stashdb_id:
        existing = actor_db.get_actor_by_stashdb_id(stashdb_id)
        if existing:
            if update_existing:
                update_existing_actor(existing, performer, dry_run=dry_run)
                if download_images and not dry_run:
                    download_performer_images(
                        actor_id=existing["id"],
                        actor_name=existing["name"],
                        image_urls=image_urls,
                        image_count=image_count,
                        validate_faces=validate_image_faces,
                        min_face_area_ratio=min_face_area_ratio,
                    )
            else:
                print(f"   -> Exists by StashDB ID (ID: {existing['id']}). Skipping.")
            return False

    existing = actor_db.get_actor_by_name(name)
    if existing:
        if update_existing:
            update_existing_actor(existing, performer, dry_run=dry_run)
            if download_images and not dry_run:
                download_performer_images(
                    actor_id=existing["id"],
                    actor_name=existing["name"],
                    image_urls=image_urls,
                    image_count=image_count,
                    validate_faces=validate_image_faces,
                    min_face_area_ratio=min_face_area_ratio,
                )
        else:
            print(f"   -> Exists by name (ID: {existing['id']}). Skipping.")
        return False

    metadata = performer_metadata(performer, image_urls)

    if dry_run:
        print(f"   -> Dry run: would add gender={metadata['gender']}, birth_year={metadata['birth_year']}")
        return True

    try:
        actor_id = actor_db.add_actor(
            name=name,
            **metadata,
        )
    except sqlite3.IntegrityError:
        print("   -> Duplicate name hit SQLite UNIQUE constraint. Skipping.")
        return False
    print(f"   -> Added to DB as ID: {actor_id}")

    if download_images:
        download_performer_images(
            actor_id=actor_id,
            actor_name=name,
            image_urls=image_urls,
            image_count=image_count,
            validate_faces=validate_image_faces,
            min_face_area_ratio=min_face_area_ratio,
        )

    return True


def main() -> int:
    args = parse_args()
    limit = None if args.all else max(args.limit, 1)
    page_size = min(max(args.page_size, 1), 100)
    imported = 0
    skipped = 0
    seen = 0
    page = max(args.resume_page or args.start_page, 1)

    target = "all available performers" if limit is None else f"{limit} new performers"
    print(f"Starting StashDB ingestion... (targeting {target})")
    print(f"Endpoint: {API_URL}")
    if args.query:
        print(f"Search query: {args.query}")
    if args.gender:
        print(f"Gender filter: {args.gender}")
    if args.breast_type:
        print(f"Breast type filter: {args.breast_type}")
    if args.min_scenes is not None:
        print(f"Minimum scenes: {args.min_scenes}")
    if args.min_birth_year is not None or args.max_birth_year is not None:
        print(f"Birth year range: {args.min_birth_year or '*'}-{args.max_birth_year or '*'}")
    if args.birthdate:
        print(f"Exact birthdate: {args.birthdate}")
    if args.birthdate_from or args.birthdate_to:
        print(f"Birthdate range: {args.birthdate_from or '*'}-{args.birthdate_to or '*'}")
    if args.active_from is not None or args.active_to is not None:
        print(f"Career active range: {args.active_from or '*'}-{args.active_to or '*'}")
    if args.require_image:
        print("Profile image required.")
    if not args.no_images:
        image_count_text = "all available" if args.image_count == 0 else str(max(args.image_count, 1))
        print(f"Image downloads: {image_count_text} per performer, order={args.image_order}")
        if args.validate_image_faces:
            print(f"Downloaded image face validation enabled (min area ratio: {args.min_face_area_ratio})")
    if args.dry_run:
        print("Dry run enabled: DB and files will not be changed.")
    if page > 1:
        print(f"Resuming from page: {page}")

    try:
        total_count = None
        while limit is None or imported < limit:
            if args.max_seen is not None and seen >= args.max_seen:
                break
            result = fetch_performer_page(
                page=page,
                page_size=page_size,
                query_text=args.query,
                gender=args.gender,
                breast_type=args.breast_type,
                min_birth_year=args.min_birth_year,
                max_birth_year=args.max_birth_year,
                sort=args.sort,
                direction=args.direction,
                retries=args.retries,
                retry_delay=args.retry_delay,
            )
            performers = result.get("performers") or []
            total_count = result.get("count", 0)
            if not performers:
                print("No performers returned by StashDB.")
                break

            print(f"Page {page}: fetched {len(performers)} performers (total available: {total_count})")
            for performer in performers:
                if limit is not None and imported >= limit:
                    break
                if args.max_seen is not None and seen >= args.max_seen:
                    break

                seen += 1
                name = performer.get("name") or "Unknown"
                print(f"Processing {seen}: {name}")
                passes, reason = passes_local_filters(
                    performer,
                    breast_type=args.breast_type,
                    min_scenes=args.min_scenes,
                    min_birth_year=args.min_birth_year,
                    max_birth_year=args.max_birth_year,
                    birthdate=args.birthdate,
                    birthdate_from=args.birthdate_from,
                    birthdate_to=args.birthdate_to,
                    active_from=args.active_from,
                    active_to=args.active_to,
                    require_image=args.require_image,
                )
                if not passes:
                    skipped += 1
                    print(f"   -> Filtered out: {reason}.")
                    continue

                if import_performer(
                    performer,
                    download_images=not args.no_images,
                    image_count=args.image_count,
                    image_order=args.image_order,
                    validate_image_faces=args.validate_image_faces,
                    min_face_area_ratio=args.min_face_area_ratio,
                    dry_run=args.dry_run,
                    update_existing=args.update_existing,
                ):
                    imported += 1
                else:
                    skipped += 1
                time.sleep(max(args.delay, 0.0))

            page += 1
            if total_count is not None and seen >= total_count:
                break

    except StashDBError as exc:
        print(f"ERROR: {exc}")
        print(f"Resume with: --resume-page {page}")
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        print(f"Progress before interruption: Seen: {seen}. Imported candidates: {imported}. Skipped: {skipped}.")
        print(f"Resume with: --resume-page {page}")
        return 130

    print(f"Ingestion complete. Seen: {seen}. Imported candidates: {imported}. Skipped: {skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
