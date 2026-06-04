"""Repair or delete actor rows that have no local reference photos.

Interactive flow:
    python scripts/repair_empty_actor_photos.py
    python scripts/repair_empty_actor_photos.py --apply

Option 1 deletes actors with no local image files.
Option 2 tries to re-download StashDB performer images first; actors that still
have no usable photos after the attempt can be deleted automatically.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

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
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

QUERY_FIND_PERFORMER = """
query FindPerformer($id: ID!) {
  findPerformer(id: $id) {
    id
    name
    images {
      url
      width
      height
    }
  }
}
"""

QUERY_SEARCH_PERFORMERS = """
query QueryPerformers($input: PerformerQueryInput!) {
  queryPerformers(input: $input) {
    performers {
      id
      name
      images {
        url
        width
        height
      }
    }
  }
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair/delete actors with no local reference photos.")
    parser.add_argument("--apply", action="store_true", help="Actually write files/delete actors. Default is dry-run.")
    parser.add_argument("--action", choices=["delete", "repair"], help="Skip the interactive 1/2 prompt.")
    parser.add_argument("--limit", type=int, help="Limit actors processed.")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--image-count", type=int, default=4, help="Images to download per actor. Use 0 for all.")
    parser.add_argument("--image-order", choices=["largest", "start", "end"], default="largest")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between StashDB performers.")
    parser.add_argument("--validate-faces", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--min-face-area-ratio", type=float, default=0.01)
    parser.add_argument(
        "--delete-after-failed-repair",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Delete actors that still have no photos after repair attempt.",
    )
    parser.add_argument(
        "--rebuild-index",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run scripts/build_index.py after successful downloads/deletions.",
    )
    parser.add_argument(
        "--build-index-args",
        default="",
        help='Extra build_index.py args, for example "--min-images 4".',
    )
    return parser.parse_args()


def safe_actor_dir_name(name: str) -> str:
    cleaned = re.sub(r"[^\w .'-]+", "", name, flags=re.UNICODE).strip()
    return cleaned.replace(" ", "_") or "Unknown"


def has_local_image(actor_id: int) -> bool:
    for image in actor_db.get_actor_images(actor_id):
        path = Path(image["file_path"])
        if path.exists() and path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            return True
    return False


def empty_photo_actors(page_size: int, limit: int | None) -> list[dict[str, Any]]:
    actors: list[dict[str, Any]] = []
    page = 1
    while True:
        rows, total = actor_db.list_actors(page=page, page_size=page_size)
        if not rows:
            break
        for actor in rows:
            if not has_local_image(actor["id"]):
                actors.append(actor)
                if limit is not None and len(actors) >= limit:
                    return actors
        if page * page_size >= total:
            break
        page += 1
    return actors


def call_stashdb(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    if not API_KEY:
        raise RuntimeError("STASHDB_API_KEY is empty. Add it to .env first.")
    response = requests.post(
        API_URL,
        json={"query": query, "variables": variables},
        headers={
            "ApiKey": API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(f"StashDB GraphQL errors: {payload['errors']}")
    return payload.get("data") or {}


def find_stashdb_performer(actor: dict[str, Any]) -> dict[str, Any] | None:
    stashdb_id = actor.get("stashdb_id")
    if stashdb_id:
        data = call_stashdb(QUERY_FIND_PERFORMER, {"id": stashdb_id})
        return data.get("findPerformer")

    data = call_stashdb(
        QUERY_SEARCH_PERFORMERS,
        {
            "input": {
                "names": actor["name"],
                "page": 1,
                "per_page": 10,
                "sort": "NAME",
                "direction": "ASC",
            }
        },
    )
    performers = (data.get("queryPerformers") or {}).get("performers") or []
    actor_name = actor["name"].casefold()
    for performer in performers:
        if (performer.get("name") or "").casefold() == actor_name:
            return performer
    return None


def image_candidates(performer: dict[str, Any], order: str) -> list[str]:
    images = performer.get("images") or []
    if order == "largest":
        images = sorted(
            images,
            key=lambda item: (item.get("width") or 0) * (item.get("height") or 0),
            reverse=True,
        )
    elif order == "end":
        images = list(reversed(images))

    urls: list[str] = []
    seen: set[str] = set()
    for image in images:
        url = image.get("url")
        if not url:
            continue
        url = url if url.startswith("http") else f"https:{url}"
        if url not in seen:
            urls.append(url)
            seen.add(url)
    return urls


def download_image(url: str, path: Path) -> bool:
    try:
        response = requests.get(url, stream=True, timeout=25)
        response.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as file:
            for chunk in response.iter_content(1024 * 64):
                if chunk:
                    file.write(chunk)
        return True
    except requests.RequestException as exc:
        print(f"     image failed: {exc}")
        return False


def image_has_usable_face(path: Path, min_face_area_ratio: float) -> bool:
    from models.face_detector import FaceDetector  # noqa: PLC0415
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    image_bytes = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
    if image is None:
        return False

    height, width = image.shape[:2]
    image_area = max(width * height, 1)
    detector = FaceDetector()
    if not detector.model_loaded:
        print("     face validation skipped: detector is not loaded")
        return True

    for face in detector.detect_faces(image):
        x1, y1, x2, y2 = face["bbox"]
        face_area = max(x2 - x1, 0) * max(y2 - y1, 0)
        if face_area / image_area >= min_face_area_ratio:
            return True
    return False


def delete_stale_image_rows(actor_id: int) -> None:
    for image in actor_db.get_actor_images(actor_id):
        if not Path(image["file_path"]).exists():
            actor_db.delete_actor_image(image["id"])


def repair_actor_photos(actor: dict[str, Any], args: argparse.Namespace) -> int:
    performer = find_stashdb_performer(actor)
    if not performer:
        print("   -> performer not found on StashDB")
        return 0

    urls = image_candidates(performer, args.image_order)
    if not urls:
        print("   -> no images on StashDB")
        return 0

    selected_urls = urls if args.image_count == 0 else urls[: max(args.image_count, 1)]
    actor_dir = settings.actors_dir / safe_actor_dir_name(actor["name"])
    saved = 0

    if args.apply:
        delete_stale_image_rows(actor["id"])
        actor_db.update_actor(actor_id=actor["id"], image_url=urls[0], stashdb_id=performer.get("id"))

    for index, url in enumerate(selected_urls, start=1):
        image_path = actor_dir / f"profile_{index:02d}.jpg"
        if image_path.exists():
            continue
        if not args.apply:
            print(f"   -> would download image {index}: {url}")
            saved += 1
            continue

        if not download_image(url, image_path):
            continue

        if args.validate_faces and not image_has_usable_face(image_path, args.min_face_area_ratio):
            image_path.unlink(missing_ok=True)
            print(f"     image {index} rejected: no usable face")
            continue

        actor_db.add_actor_image(actor["id"], image_path.name, str(image_path))
        saved += 1
        print(f"     image {index} saved")

    return saved


def delete_actor(actor: dict[str, Any], apply: bool) -> None:
    print(f"   -> {'deleting' if apply else 'would delete'} {actor['name']} (ID {actor['id']})")
    if not apply:
        return
    actor_dir = settings.actors_dir / safe_actor_dir_name(actor["name"])
    actor_db.delete_actor(actor["id"])
    if actor_dir.exists() and actor_dir.is_dir() and not has_local_image(actor["id"]):
        try:
            actor_dir.rmdir()
        except OSError:
            pass


def choose_action(args: argparse.Namespace) -> str:
    if args.action:
        return args.action
    print("\nWhat do you want to do?")
    print("1. Delete actors with no photos")
    print("2. Try to re-download photos from StashDB first")
    choice = input("Choice [1/2/q]: ").strip().lower()
    if choice == "1":
        return "delete"
    if choice == "2":
        return "repair"
    raise SystemExit("Cancelled.")


def rebuild_index(args: argparse.Namespace) -> int:
    command = [sys.executable, str(PROJECT_ROOT / "scripts" / "build_index.py")]
    if args.build_index_args.strip():
        command.extend(args.build_index_args.split())
    print("\nRebuilding FAISS index...")
    print(" ".join(command))
    return subprocess.run(command, cwd=PROJECT_ROOT, check=False).returncode


def main() -> int:
    args = parse_args()
    candidates = empty_photo_actors(max(args.page_size, 1), args.limit)

    print(f"Actors with no local reference photos: {len(candidates)}")
    for actor in candidates[:30]:
        print(f"  - {actor['name']} (ID {actor['id']}, stashdb_id={actor.get('stashdb_id') or '-'})")
    if len(candidates) > 30:
        print(f"  ... {len(candidates) - 30} more")
    print("Mode:", "APPLY" if args.apply else "DRY-RUN")

    if not candidates:
        return 0

    action = choose_action(args)
    changed = False
    repaired = 0
    deleted = 0
    failed: list[str] = []

    if action == "delete":
        for actor in candidates:
            delete_actor(actor, args.apply)
            deleted += 1
        changed = bool(candidates) and args.apply

    elif action == "repair":
        for index, actor in enumerate(candidates, start=1):
            print(f"\n[{index}/{len(candidates)}] {actor['name']}")
            try:
                saved = repair_actor_photos(actor, args)
            except Exception as exc:
                print(f"   -> repair failed: {exc}")
                saved = 0

            if saved > 0:
                repaired += 1
                changed = changed or args.apply
                status = "repaired" if args.apply else "would repair"
                print(f"   -> {status} with {saved} image(s)")
            else:
                failed.append(actor["name"])
                if args.delete_after_failed_repair:
                    delete_actor(actor, args.apply)
                    deleted += 1
                    changed = changed or args.apply

            if args.delay > 0 and index < len(candidates):
                time.sleep(args.delay)

    print("\nSummary")
    print(f"  {'Repaired' if args.apply else 'Would repair'} actors: {repaired}")
    print(f"  Deleted actors: {deleted if args.apply else 0}")
    print(f"  Failed repairs: {len(failed)}")
    if failed[:20]:
        print("  Failed sample:", ", ".join(failed[:20]))

    if not args.apply:
        print("\nNo changes made. Re-run with --apply to write changes.")
        return 0

    if changed and args.rebuild_index:
        return rebuild_index(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
