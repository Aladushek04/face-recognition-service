import unittest
import tempfile
import sys
from pathlib import Path
from unittest import mock
from argparse import Namespace

# Add backend to path if needed to ensure absolute imports work
if str(Path("backend").resolve()) not in sys.path:
    sys.path.insert(0, str(Path("backend").resolve()))

from config import settings
import database.actor_db as actor_db
from database.schema import init_db
import jobs.repair_empty_actor_photos as repair_job
import jobs.cleanup_images as cleanup_job
import jobs.build_index as build_index_job
import jobs.scrape_stashdb as scrape_job

class DockerMaintenanceSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self.temp_dir_obj.name)
        
        # Create necessary directories
        (self.temp_dir / "db").mkdir(parents=True)
        (self.temp_dir / "actors").mkdir(parents=True)
        (self.temp_dir / "faiss_index").mkdir(parents=True)
        
        # Patch settings globally
        self.settings_patchers = [
            mock.patch.object(settings, "base_dir", self.temp_dir),
            mock.patch.object(settings, "actors_dir", self.temp_dir / "actors"),
            mock.patch.object(settings, "faiss_index_dir", self.temp_dir / "faiss_index"),
        ]
        for p in self.settings_patchers:
            p.start()
            
        # Initialize the fresh synthetic DB
        init_db()

    def tearDown(self) -> None:
        for p in self.settings_patchers:
            p.stop()
        self.temp_dir_obj.cleanup()

    def test_repair_empty_actor_photos_failure_leaves_actor(self) -> None:
        """A. repair_empty_actor_photos must fail gracefully and leave actor untouched if photo is bad."""
        actor_id = actor_db.add_actor("SmokeActor", "stash-smoke-1")
        actor = {"id": actor_id, "name": "SmokeActor", "stashdb_id": "stash-smoke-1"}
        
        performer = {
            "id": "stash-smoke-1",
            "images": [{"url": "https://example.test/fake.jpg", "width": 100, "height": 100}],
        }
        args = Namespace(
            image_order="largest",
            image_count=1,
            apply=True,
            validate_faces=True,
            min_face_area_ratio=0.01,
            allow_unvalidated_images=False,
        )
        
        with mock.patch.object(repair_job, "find_stashdb_performer", return_value=performer), \
             mock.patch.object(repair_job, "download_image", return_value=True), \
             mock.patch.object(repair_job, "image_has_usable_face", return_value=False):
            
            saved = repair_job.repair_actor_photos(actor, args)
            
        self.assertEqual(saved, 0)
        
        # Verify actor is still in DB and has 0 images
        actors = actor_db.list_actors()
        self.assertEqual(len(actors[0]), 1)
        self.assertEqual(actors[0][0]["name"], "SmokeActor")
        images, count = actor_db.list_actor_images()
        self.assertEqual(count, 0)

    def test_cleanup_images_handles_missing_file_and_processing_error(self) -> None:
        """B. cleanup_images handles missing files safely."""
        actor_id = actor_db.add_actor("CleanupActor", "stash-cleanup-1")
        # Add an image that points to a non-existent file
        actor_db.add_actor_image(actor_id, "missing.jpg", str(self.temp_dir / "missing.jpg"))
        
        class FakeDetector:
            is_available = True

        with mock.patch.object(cleanup_job, "FaceDetector", FakeDetector):
            # Apply but DO NOT pass --delete-missing, should leave row intact
            rc = cleanup_job.main(["--apply"])
            
        self.assertEqual(rc, 0)
        images, count = actor_db.list_actor_images()
        self.assertEqual(count, 1)

    def test_build_index_preserves_existing_on_zero_vectors(self) -> None:
        """C. build_index 0-vector build must not overwrite existing index unless forced."""
        dummy_faiss = settings.faiss_index_path
        dummy_faiss.parent.mkdir(parents=True, exist_ok=True)
        dummy_faiss.write_bytes(b"DUMMY_FAISS_DATA")
        
        # We have 0 actors with photos, so it will generate 0 vectors
        class FakeDetector:
            model_loaded = True

        with mock.patch.object(build_index_job, "FaceDetector", FakeDetector):
            # Should fail (return 1) and preserve file
            rc = build_index_job.main([])
            
        self.assertEqual(rc, 1)
        self.assertTrue(dummy_faiss.exists())
        self.assertEqual(dummy_faiss.read_bytes(), b"DUMMY_FAISS_DATA")

    def test_scrape_stashdb_dry_run_flag(self) -> None:
        """D. scrape_stashdb uses dry run properly."""
        args_no_flag = scrape_job.parse_args([])
        self.assertFalse(args_no_flag.dry_run)
        
        args_flag = scrape_job.parse_args(["--dry-run"])
        self.assertTrue(args_flag.dry_run)
