"""Find or delete actor reference images that do not contain usable faces.

Dry-run is the default. Use --apply to delete files and DB rows.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from jobs.runtime import configure_job_io  # noqa: E402

configure_job_io()

from database import actor_db  # noqa: E402
from models.face_detector import FaceDetector  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete actor reference images without usable faces.")
    parser.add_argument("--apply", action="store_true", help="Actually delete files and DB rows. Default is dry-run.")
    parser.add_argument("--page-size", type=int, default=500, help="DB page size.")
    parser.add_argument("--limit", type=int, help="Stop after checking this many image rows.")
    parser.add_argument(
        "--delete-missing",
        action="store_true",
        help="Also delete DB rows whose image file is missing.",
    )
    parser.add_argument(
        "--min-face-area-ratio",
        type=float,
        default=0.01,
        help="Minimum detected face bbox area relative to image area.",
    )
    return parser.parse_args(argv)


def iter_images(page_size: int):
    page = 1
    while True:
        images, total = actor_db.list_actor_images(page=page, page_size=page_size)
        if not images:
            break
        for image in images:
            yield image, total
        if page * page_size >= total:
            break
        page += 1


def has_usable_face(detector: FaceDetector, image_path: Path, min_face_area_ratio: float) -> bool:
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    image_bytes = np.fromfile(str(image_path), dtype=np.uint8)
    image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
    if image is None:
        return False

    height, width = image.shape[:2]
    image_area = max(width * height, 1)
    faces = detector.detect_faces(image)

    for face in faces:
        x1, y1, x2, y2 = face["bbox"]
        face_area = max(x2 - x1, 0) * max(y2 - y1, 0)
        if face_area / image_area >= min_face_area_ratio:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    checked = 0
    kept = 0
    candidates: list[tuple[dict, str]] = []
    missing = 0
    no_usable_face = 0
    processing_errors = 0
    skipped_due_to_errors = 0

    detector = FaceDetector()
    if not detector.model_loaded:
        print("ERROR: Face detector model is not loaded.")
        return 1

    for image, total in iter_images(max(args.page_size, 1)):
        if args.limit is not None and checked >= args.limit:
            break
        checked += 1

        image_path = Path(image["file_path"])
        label = f"{image.get('actor_name') or image['actor_id']} / {image['filename']}"
        if checked == 1:
            print(f"Found {total} reference image rows.")

        if not image_path.exists():
            missing += 1
            if args.delete_missing:
                candidates.append((image, "missing file"))
                print(f"  ! {label}: missing file")
            else:
                kept += 1
            continue

        try:
            usable = has_usable_face(detector, image_path, args.min_face_area_ratio)
        except Exception as exc:
            processing_errors += 1
            skipped_due_to_errors += 1
            print(f"  ! {label}: processing error: {exc}")
            continue

        if usable:
            kept += 1
            continue

        no_usable_face += 1
        candidates.append((image, "no usable face"))
        print(f"  ! {label}: no usable face")

    print("-" * 50)
    print(f"Images checked: {checked}")
    print(f"Images kept: {kept}")
    print(f"Missing files: {missing}")
    print(f"No usable face: {no_usable_face}")
    print(f"Processing errors: {processing_errors}")
    print(f"Skipped due to errors: {skipped_due_to_errors}")
    print(f"Images matching delete criteria: {len(candidates)}")
    print("Mode:", "APPLY" if args.apply else "DRY-RUN")

    if not args.apply:
        print("No changes made. Re-run with --apply to delete.")
        return 0

    deleted = 0
    for image, reason in candidates:
        if reason.startswith("processing error"):
            continue
        if actor_db.delete_actor_image(image["id"]):
            deleted += 1

    print(f"Deleted {deleted} image rows/files.")
    print("Rebuild the FAISS index after cleanup: python scripts/build_index.py")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nImage cleanup interrupted by user.")
        raise SystemExit(130)
