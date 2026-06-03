"""Build the FAISS index from actor reference images.

Usage:
    python scripts/build_index.py
    python scripts/build_index.py --refresh-cache

The script caches extracted embeddings in data/embeddings. Re-running it will
reuse valid cached embeddings and only run face detection for new or changed
images.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

# Add parent directory to path.
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from config import settings  # noqa: E402
from database import actor_db  # noqa: E402
from models.face_detector import FaceDetector  # noqa: E402
from models.vector_store import VectorStore  # noqa: E402


DEFAULT_PAGE_SIZE = 1000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the face-recognition FAISS index.")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="Actor DB page size.")
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Ignore existing cached embeddings and reprocess every image.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=settings.base_dir / "data" / "embeddings",
        help="Directory for cached .npy embedding files.",
    )
    return parser.parse_args()


def iter_actors(page_size: int):
    page = 1
    while True:
        actors, total = actor_db.list_actors(page=page, page_size=page_size)
        if not actors:
            break

        for actor in actors:
            yield actor, total

        if page * page_size >= total:
            break
        page += 1


def embedding_cache_path(cache_dir: Path, image_id: int) -> Path:
    return cache_dir / f"actor_image_{image_id}.npy"


def load_cached_embeddings(cache_path: Path, image_path: Path, refresh_cache: bool) -> list[np.ndarray] | None:
    if refresh_cache or not cache_path.exists():
        return None
    if cache_path.stat().st_mtime < image_path.stat().st_mtime:
        return None

    cached = np.load(cache_path)
    if cached.ndim == 1:
        cached = cached.reshape(1, -1)
    if cached.ndim != 2 or cached.shape[1] != settings.embedding_dim:
        return None
    return [row.astype(np.float32) for row in cached]


def save_cached_embeddings(cache_path: Path, embeddings: list[np.ndarray]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    stacked = np.array(embeddings, dtype=np.float32)
    np.save(cache_path, stacked)


def get_image_embeddings(
    *,
    detector: FaceDetector,
    image_info: dict,
    cache_dir: Path,
    refresh_cache: bool,
) -> list[np.ndarray]:
    image_path = Path(image_info["file_path"])
    if not image_path.exists():
        print(f"    ! Missing: {image_path}")
        return []

    cache_path = Path(image_info["embedding_path"] or "") if image_info.get("embedding_path") else None
    if cache_path is None:
        cache_path = embedding_cache_path(cache_dir, image_info["id"])

    cached = load_cached_embeddings(cache_path, image_path, refresh_cache)
    if cached is not None:
        return cached

    try:
        faces = detector.detect_faces_from_path(image_path)
    except Exception as exc:
        print(f"    ! Error processing {image_path.name}: {exc}")
        return []

    if not faces:
        print(f"    ! No faces found in: {image_path.name}")
        return []

    embeddings = [face["embedding"].astype(np.float32) for face in faces]
    save_cached_embeddings(cache_path, embeddings)
    actor_db.update_actor_image_embedding(image_info["id"], str(cache_path))
    return embeddings


def build_index() -> bool:
    args = parse_args()
    page_size = max(args.page_size, 1)
    cache_dir = args.cache_dir

    print("Building face recognition index...")
    print("-" * 50)
    print(f"Embedding cache: {cache_dir}")
    if args.refresh_cache:
        print("Refresh cache enabled: all images will be reprocessed.")

    detector = FaceDetector()
    if not detector.model_loaded:
        print("ERROR: Face detection model not loaded!")
        print("Please install insightface and onnxruntime/onnxruntime-gpu.")
        return False

    vector_store = VectorStore()
    vector_store.create_index()

    first_actor = True
    total_actors = 0
    indexed_actors = 0
    total_vectors = 0

    for actor, total in iter_actors(page_size):
        if first_actor:
            print(f"Found {total} actors in database")
            print("-" * 50)
            first_actor = False

        total_actors += 1
        actor_id = actor["id"]
        actor_name = actor["name"]
        images = actor_db.get_actor_images(actor_id)

        if not images:
            print(f"  ! {actor_name}: No reference images")
            continue

        actor_embeddings: list[np.ndarray] = []
        for image_info in images:
            actor_embeddings.extend(
                get_image_embeddings(
                    detector=detector,
                    image_info=image_info,
                    cache_dir=cache_dir,
                    refresh_cache=args.refresh_cache,
                )
            )

        if actor_embeddings:
            vector_store.add_vectors(actor_embeddings, actor_id)
            indexed_actors += 1
            total_vectors += len(actor_embeddings)
            print(f"  + {actor_name}: {len(actor_embeddings)} face embeddings")

    if total_actors == 0:
        print("No actors found in database. Run seed_actors.py or scrape_stashdb.py first.")
        return False

    vector_store.save_index()

    print("-" * 50)
    print("Index built successfully!")
    print(f"  Total actors scanned: {total_actors}")
    print(f"  Actors indexed: {indexed_actors}")
    print(f"  Total vectors: {total_vectors}")
    print(f"  Index saved to: {settings.faiss_index_path}")
    return True


if __name__ == "__main__":
    try:
        raise SystemExit(0 if build_index() else 1)
    except KeyboardInterrupt:
        print("\nIndex build interrupted by user.")
        raise SystemExit(130)
