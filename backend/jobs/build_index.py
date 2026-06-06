"""Build the FAISS index from actor reference images.

Usage:
    python scripts/build_index.py
    python scripts/build_index.py --refresh-cache
    python scripts/build_index.py --min-images 4

The script caches extracted embeddings in data/embeddings. Re-running it will
reuse valid cached embeddings and only run face detection for new or changed
images.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from jobs.runtime import configure_job_io  # noqa: E402

configure_job_io()

from config import settings  # noqa: E402
from database import actor_db  # noqa: E402
from models.face_detector import FaceDetector  # noqa: E402
from models.vector_store import VectorStore  # noqa: E402


DEFAULT_PAGE_SIZE = 1000
DEFAULT_MIN_IMAGES = 4


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the face-recognition FAISS index.")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="Actor DB page size.")
    parser.add_argument(
        "--min-images",
        type=int,
        default=DEFAULT_MIN_IMAGES,
        help="Skip actors with fewer reference image rows than this. Use 1 to index every actor with photos.",
    )
    parser.add_argument(
        "--verbose-skips",
        action="store_true",
        help="Print every actor skipped for missing/few images. Default prints only processing failures and summary.",
    )
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
    return parser.parse_args(argv)


def load_actor_image_groups(page_size: int) -> tuple[dict[int, dict], int, int]:
    """Load all image rows once and group them by actor to avoid per-actor DB queries."""
    groups: dict[int, dict] = {}
    page = 1
    total_images = 0

    while True:
        images, total = actor_db.list_actor_images(page=page, page_size=page_size)
        total_images = total
        if not images:
            break

        for image in images:
            actor_id = image["actor_id"]
            group = groups.setdefault(
                actor_id,
                {
                    "actor_id": actor_id,
                    "actor_name": image.get("actor_name") or str(actor_id),
                    "images": [],
                },
            )
            group["images"].append(image)

        if page * page_size >= total:
            break
        page += 1

    total_actors = actor_db.get_actors_count()
    return groups, total_actors, total_images


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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    page_size = max(args.page_size, 1)
    min_images = max(args.min_images, 1)
    cache_dir = args.cache_dir

    print("Building face recognition index...")
    print("-" * 50)
    print(f"Embedding cache: {cache_dir}")
    print(f"Minimum reference images per actor: {min_images}")
    if args.refresh_cache:
        print("Refresh cache enabled: all images will be reprocessed.")

    detector = FaceDetector()
    if not detector.model_loaded:
        print("ERROR: Face detection model not loaded!")
        print("Please install insightface and onnxruntime/onnxruntime-gpu.")
        return 1

    vector_store = VectorStore()
    vector_store.create_index()

    total_actors = 0
    indexed_actors = 0
    skipped_no_images = 0
    skipped_few_images = 0
    missing_image_files = 0
    total_vectors = 0

    actor_groups, actor_count, total_image_rows = load_actor_image_groups(page_size)
    total_actors = actor_count
    skipped_no_images = max(actor_count - len(actor_groups), 0)
    print(f"Found {actor_count} actors and {total_image_rows} reference image rows in database")
    print(f"Actors with image rows: {len(actor_groups)}")
    print("-" * 50)

    for group in sorted(actor_groups.values(), key=lambda item: item["actor_name"].lower()):
        actor_id = group["actor_id"]
        actor_name = group["actor_name"]
        images = group["images"]
        existing_images = [image for image in images if Path(image["file_path"]).exists()]
        missing_count = len(images) - len(existing_images)
        missing_image_files += missing_count

        if len(existing_images) < min_images:
            skipped_few_images += 1
            if args.verbose_skips:
                print(
                    f"  ! {actor_name}: only {len(existing_images)} existing reference images, "
                    f"need {min_images}"
                )
            continue

        actor_embeddings: list[np.ndarray] = []
        for image_info in existing_images:
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
        return 1

    vector_store.save_index()

    print("-" * 50)
    print("Index built successfully!")
    print(f"  Total actors scanned: {total_actors}")
    print(f"  Actors indexed: {indexed_actors}")
    print(f"  Actors skipped with no image rows: {skipped_no_images}")
    print(f"  Actors skipped with too few images: {skipped_few_images}")
    print(f"  Missing image files ignored: {missing_image_files}")
    print(f"  Total vectors: {total_vectors}")
    print(f"  Index saved to: {settings.faiss_index_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nIndex build interrupted by user.")
        raise SystemExit(130)
