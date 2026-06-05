"""Delete empty actor folders under the configured actors directory.

Dry-run is the default. Use --apply to actually delete.

Examples:
    python scripts/cleanup_empty_actor_dirs.py
    python scripts/cleanup_empty_actor_dirs.py --apply
    python scripts/cleanup_empty_actor_dirs.py --without-images --apply
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from config import settings  # noqa: E402


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete empty actor folders from the local actors directory.",
    )
    parser.add_argument(
        "--actors-dir",
        type=Path,
        default=settings.actors_dir,
        help=f"Actors directory. Default: {settings.actors_dir}",
    )
    parser.add_argument(
        "--without-images",
        action="store_true",
        help="Delete actor folders that contain no image files, even if they contain other files.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete folders. Default is dry-run.",
    )
    return parser.parse_args(argv)


def resolve_safe_actors_dir(path: Path) -> Path:
    actors_dir = path.expanduser().resolve()
    expected_root = settings.actors_dir.expanduser().resolve()

    if actors_dir != expected_root:
        raise SystemExit(
            f"Refusing to run outside configured actors dir.\n"
            f"Requested: {actors_dir}\n"
            f"Expected:  {expected_root}"
        )

    if not actors_dir.exists() or not actors_dir.is_dir():
        raise SystemExit(f"Actors directory does not exist: {actors_dir}")

    return actors_dir


def has_image_file(path: Path) -> bool:
    return any(
        item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS
        for item in path.rglob("*")
    )


def is_empty_dir(path: Path) -> bool:
    return path.is_dir() and not any(path.iterdir())


def collect_delete_candidates(actors_dir: Path, without_images: bool) -> list[Path]:
    if without_images:
        return sorted(
            (path for path in actors_dir.iterdir() if path.is_dir() and not has_image_file(path)),
            key=lambda p: p.name.lower(),
        )

    # Walk deepest folders first so nested empty folders are handled before parents.
    return sorted(
        (path for path in actors_dir.rglob("*") if is_empty_dir(path)),
        key=lambda p: len(p.parts),
        reverse=True,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    actors_dir = resolve_safe_actors_dir(args.actors_dir)
    candidates = collect_delete_candidates(actors_dir, args.without_images)

    print(f"Actors directory: {actors_dir}")
    print("Mode:", "APPLY" if args.apply else "DRY-RUN")
    print("Rule:", "delete folders without images" if args.without_images else "delete empty folders")
    print(f"Folders matching rule: {len(candidates)}")

    for path in candidates[:200]:
        print(f"  - {path}")
    if len(candidates) > 200:
        print(f"  ... {len(candidates) - 200} more")

    if not args.apply:
        print("No changes made. Re-run with --apply to delete.")
        return 0

    deleted = 0
    for path in candidates:
        if not path.exists() or not path.is_dir():
            continue
        if args.without_images:
            shutil.rmtree(path)
            deleted += 1
        elif is_empty_dir(path):
            path.rmdir()
            deleted += 1

    print(f"Deleted folders: {deleted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
