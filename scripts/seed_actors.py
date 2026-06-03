"""Seed script to add demo actors to the database.

Usage:
    python scripts/seed_actors.py

This script adds a small set of well-known actors for demonstration.
You'll need to add reference images manually to the data/actors/ directory.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import actor_db
from config import settings


# Demo actors - add reference images to data/actors/<name>/
DEMO_ACTORS = [
    {
        "name": "Tom Hanks",
        "birth_year": 1956,
        "gender": "male",
        "bio": "American actor and filmmaker, known for both comedic and dramatic roles.",
        "filmography": "Forrest Gump, Saving Private Ryan, Cast Away, Toy Story series",
        "tags": ["actor", "hollywood", "drama", "comedy"],
    },
    {
        "name": "Meryl Streep",
        "birth_year": 1949,
        "gender": "female",
        "bio": "American actress, often described as the 'greatest actress of her generation'.",
        "filmography": "The Devil Wears Prada, Sophie's Choice, Mamma Mia!",
        "tags": ["actress", "hollywood", "drama"],
    },
    {
        "name": "Leonardo DiCaprio",
        "birth_year": 1974,
        "gender": "male",
        "bio": "American actor and film producer known for his roles in blockbuster and serious films.",
        "filmography": "Titanic, Inception, The Revenant, The Wolf of Wall Street",
        "tags": ["actor", "hollywood", "drama"],
    },
    {
        "name": "Scarlett Johansson",
        "birth_year": 1984,
        "gender": "female",
        "bio": "American actress, one of the world's highest-paid and most successful actresses.",
        "filmography": "Lost in Translation, Marvel Cinematic Universe, Marriage Story",
        "tags": ["actress", "hollywood", "action"],
    },
    {
        "name": "Denzel Washington",
        "birth_year": 1954,
        "gender": "male",
        "bio": "American actor, director, and producer known for his powerful performances.",
        "filmography": "Training Day, Malcolm X, Glorious, Flight",
        "tags": ["actor", "hollywood", "drama"],
    },
]


def seed_actors():
    """Add demo actors to the database."""
    print("Seeding actors database...")
    print("-" * 40)

    for actor_data in DEMO_ACTORS:
        existing = actor_db.get_actor_by_name(actor_data["name"])
        if existing:
            print(f"  ✓ {actor_data['name']} already exists (ID: {existing['id']})")
            continue

        actor_id = actor_db.add_actor(**actor_data)

        # Create actor directory
        actor_dir = settings.actors_dir / actor_data["name"].replace(" ", "_")
        actor_dir.mkdir(parents=True, exist_ok=True)

        print(f"  + Added {actor_data['name']} (ID: {actor_id})")
        print(f"    Directory: {actor_dir}")
        print(f"    Add reference images to this directory")

    print("-" * 40)
    print(f"Total actors in database: {actor_db.get_actors_count()}")
    print("\nNext steps:")
    print("1. Add reference photos for each actor to data/actors/<name>/")
    print("2. Run: python scripts/build_index.py")
    print("3. Start the service: python backend/main.py")


if __name__ == "__main__":
    seed_actors()
