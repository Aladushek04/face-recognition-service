"""Clean actor DB rows and folders that do not match local metadata filters.

Dry-run is the default. Use --apply to delete.

Examples:
    python scripts/cleanup_actors.py --breast-type augmented --min-scenes 10 --min-birth-year 1960 --require-image
    python scripts/cleanup_actors.py --breast-type augmented --min-scenes 10 --min-birth-year 1960 --require-image --apply
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

from config import settings  # noqa: E402
from database import actor_db  # noqa: E402
from jobs.country_filters import (  # noqa: E402
    COUNTRY_REGION_FILTERS,
    allowed_countries_for_region,
    normalize_country,
    parse_country_list,
)


BREAST_TYPES = {
    "augmented": "FAKE",
    "fake": "FAKE",
    "natural": "NATURAL",
    "na": "NA",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete actors/folders that fail metadata filters.")
    parser.add_argument("--gender", choices=["female", "male", "other"], help="Required local gender.")
    parser.add_argument("--breast-type", choices=sorted(BREAST_TYPES), help="Required breast type.")
    parser.add_argument("--min-scenes", type=int, help="Minimum scene_count.")
    parser.add_argument("--min-birth-year", type=int, help="Minimum birth year.")
    parser.add_argument("--max-birth-year", type=int, help="Maximum birth year.")
    parser.add_argument("--birthdate", help="Required exact birthdate, YYYY-MM-DD.")
    parser.add_argument("--birthdate-from", help="Minimum birthdate, YYYY-MM-DD.")
    parser.add_argument("--birthdate-to", help="Maximum birthdate, YYYY-MM-DD.")
    parser.add_argument("--active-from", type=int, help="Required career overlap start year.")
    parser.add_argument("--active-to", type=int, help="Required career overlap end year.")
    parser.add_argument(
        "--country-region",
        choices=sorted(COUNTRY_REGION_FILTERS),
        help="Keep only actors from a predefined country region; delete actors outside it.",
    )
    parser.add_argument(
        "--include-countries",
        help="Comma-separated extra allowed country names. Example: USA,Canada,Germany,Russia,Brazil.",
    )
    parser.add_argument(
        "--exclude-countries",
        help="Comma-separated country names to delete. Applied after region/include filters.",
    )
    parser.add_argument(
        "--allow-unknown-country",
        action="store_true",
        help="Keep actors with an empty country when a country filter is enabled.",
    )
    parser.add_argument("--require-image", action="store_true", help="Require image_url and at least one DB image.")
    parser.add_argument(
        "--include-unknown",
        action="store_true",
        help="Also delete rows with missing metadata. Without this, unknown metadata is kept.",
    )
    parser.add_argument("--apply", action="store_true", help="Actually delete rows/folders. Default is dry-run.")
    parser.add_argument("--page-size", type=int, default=1000)
    return parser.parse_args(argv)


def iter_actors(page_size: int):
    page = 1
    while True:
        actors, total = actor_db.list_actors(page=page, page_size=page_size)
        if not actors:
            break
        for actor in actors:
            yield actor
        if page * page_size >= total:
            break
        page += 1


def actor_dir(name: str) -> Path:
    return settings.actors_dir / name.replace(" ", "_")


def fail_reason(actor: dict[str, Any], args: argparse.Namespace) -> str | None:
    if args.gender and actor.get("gender") != args.gender:
        return f"gender={actor.get('gender')}"

    if args.breast_type:
        expected = BREAST_TYPES[args.breast_type]
        actual = actor.get("breast_type")
        if actual is None and not args.include_unknown:
            return None
        if actual != expected:
            return f"breast_type={actual}"

    if args.min_scenes is not None:
        scenes = actor.get("scene_count")
        if scenes is None and not args.include_unknown:
            return None
        if scenes is None or scenes < args.min_scenes:
            return f"scene_count={scenes}"

    if args.min_birth_year is not None:
        birth_year = actor.get("birth_year")
        if birth_year is None and not args.include_unknown:
            return None
        if birth_year is None or birth_year < args.min_birth_year:
            return f"birth_year={birth_year}"

    if args.max_birth_year is not None:
        birth_year = actor.get("birth_year")
        if birth_year is None and not args.include_unknown:
            return None
        if birth_year is None or birth_year > args.max_birth_year:
            return f"birth_year={birth_year}"

    if args.birthdate:
        birthdate = actor.get("birthdate")
        if birthdate is None and not args.include_unknown:
            return None
        if birthdate != args.birthdate:
            return f"birthdate={birthdate}"

    if args.birthdate_from:
        birthdate = actor.get("birthdate")
        if birthdate is None and not args.include_unknown:
            return None
        if birthdate is None or birthdate < args.birthdate_from:
            return f"birthdate={birthdate}"

    if args.birthdate_to:
        birthdate = actor.get("birthdate")
        if birthdate is None and not args.include_unknown:
            return None
        if birthdate is None or birthdate > args.birthdate_to:
            return f"birthdate={birthdate}"

    if args.active_from is not None or args.active_to is not None:
        career_start = actor.get("career_start_year")
        career_end = actor.get("career_end_year")
        if career_start is None and not args.include_unknown:
            return None
        if career_start is None:
            return f"career={career_start}-{career_end}"
        interval_start = args.active_from if args.active_from is not None else -9999
        interval_end = args.active_to if args.active_to is not None else 9999
        actor_end = career_end if career_end is not None else 9999
        if career_start > interval_end or actor_end < interval_start:
            return f"career={career_start}-{career_end or ''}"

    country_filter_enabled = bool(args.allowed_countries or args.excluded_countries)
    if country_filter_enabled:
        country = normalize_country(actor.get("country"))
        if country is None:
            if not args.allow_unknown_country:
                return "country is empty"
        else:
            if args.allowed_countries and country not in args.allowed_countries:
                return f"country={actor.get('country')}"
            if country in args.excluded_countries:
                return f"country={actor.get('country')}"

    if args.require_image:
        images = actor_db.get_actor_images(actor["id"])
        image_url = actor.get("image_url")
        if (image_url is None or not images) and not args.include_unknown:
            return None
        if not image_url or not images:
            return f"image_url={image_url}, db_images={len(images)}"

    return None


def delete_actor_folder(path: Path) -> None:
    if path.exists() and path.is_dir():
        shutil.rmtree(path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.allowed_countries = allowed_countries_for_region(args.country_region) | parse_country_list(args.include_countries)
    args.excluded_countries = parse_country_list(args.exclude_countries)
    candidates: list[tuple[dict[str, Any], str]] = []
    kept = 0

    if args.country_region:
        print(f"Country region filter: {COUNTRY_REGION_FILTERS[args.country_region]}")
    if args.include_countries:
        print(f"Country allow-list additions: {', '.join(sorted(parse_country_list(args.include_countries)))}")
    if args.exclude_countries:
        print(f"Country block-list: {', '.join(sorted(args.excluded_countries))}")
    if args.allowed_countries or args.excluded_countries:
        unknown_text = "kept" if args.allow_unknown_country else "deleted"
        print(f"Unknown/empty country: {unknown_text}")

    for actor in iter_actors(max(args.page_size, 1)):
        reason = fail_reason(actor, args)
        if reason:
            candidates.append((actor, reason))
        else:
            kept += 1

    print(f"Actors kept: {kept}")
    print(f"Actors matching delete filters: {len(candidates)}")
    print("Mode:", "APPLY" if args.apply else "DRY-RUN")

    for actor, reason in candidates[:100]:
        print(f"  - {actor['name']} (ID {actor['id']}): {reason}")
    if len(candidates) > 100:
        print(f"  ... {len(candidates) - 100} more")

    if not args.apply:
        print("No changes made. Re-run with --apply to delete.")
        return 0

    for actor, _reason in candidates:
        delete_actor_folder(actor_dir(actor["name"]))
        actor_db.delete_actor(actor["id"])

    print(f"Deleted {len(candidates)} actors and matching folders.")
    print("Rebuild the FAISS index after cleanup: python scripts/build_index.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
