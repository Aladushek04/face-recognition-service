from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock


class MaintenanceHotfixTests(unittest.TestCase):
    def test_repair_defaults_do_not_delete_or_rebuild(self) -> None:
        source = Path("backend/jobs/repair_empty_actor_photos.py").read_text(encoding="utf-8")

        self.assertIn('"--delete-after-failed-repair"', source)
        self.assertIn("default=False", source)
        self.assertIn('"--rebuild-index"', source)
        self.assertNotIn('sys.executable, str(PROJECT_ROOT / "scripts" / "build_index.py")', source)

    def test_cleanup_processing_errors_are_not_delete_candidates(self) -> None:
        source = Path("backend/jobs/cleanup_images.py").read_text(encoding="utf-8")

        self.assertIn("processing_errors += 1", source)
        self.assertIn("skipped_due_to_errors += 1", source)
        self.assertNotIn('candidates.append((image, f"processing error: {exc}"))', source)

    def test_scrape_stashdb_command_uses_dry_run_not_apply(self) -> None:
        old_base_dir = os.environ.get("BASE_DIR")
        old_jobs_dir = os.environ.get("JOBS_DIR")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["BASE_DIR"] = temp_dir
            os.environ["JOBS_DIR"] = str(Path(temp_dir) / "jobs")
            sys.path.insert(0, str(Path("backend").resolve()))
            try:
                job_manager_module = importlib.import_module("services.job_manager")
                manager = job_manager_module.JobManager()
                definition = job_manager_module.JOB_DEFINITIONS["scrape_stashdb"]

                dry_command = manager._build_command(definition, False, ["--limit", "2"])
                apply_command = manager._build_command(definition, True, ["--limit", "2"])
            finally:
                if sys.path[0] == str(Path("backend").resolve()):
                    sys.path.pop(0)
                if old_base_dir is None:
                    os.environ.pop("BASE_DIR", None)
                else:
                    os.environ["BASE_DIR"] = old_base_dir
                if old_jobs_dir is None:
                    os.environ.pop("JOBS_DIR", None)
                else:
                    os.environ["JOBS_DIR"] = old_jobs_dir

        self.assertIn("--dry-run", dry_command)
        self.assertNotIn("--apply", dry_command)
        self.assertNotIn("--dry-run", apply_command)
        self.assertNotIn("--apply", apply_command)

    def test_stash_jobs_use_settings_env_source(self) -> None:
        for path in [
            Path("backend/jobs/scrape_stashdb.py"),
            Path("backend/jobs/repair_empty_actor_photos.py"),
        ]:
            source = path.read_text(encoding="utf-8")
            self.assertIn("settings.stashdb_api_key", source)
            self.assertNotIn('load_dotenv(PROJECT_ROOT / ".env")', source)

    def test_job_io_utf8_helper_is_used(self) -> None:
        for path in [
            Path("backend/jobs/build_index.py"),
            Path("backend/jobs/cleanup_images.py"),
            Path("backend/jobs/scrape_stashdb.py"),
            Path("backend/jobs/repair_empty_actor_photos.py"),
        ]:
            source = path.read_text(encoding="utf-8")
            self.assertIn("configure_job_io()", source)

    def test_build_index_refuses_empty_index_by_default(self) -> None:
        sys.path.insert(0, str(Path("backend").resolve()))
        try:
            build_index = importlib.import_module("jobs.build_index")
            saved: list[bool] = []

            class FakeDetector:
                model_loaded = True

            class FakeVectorStore:
                def create_index(self) -> None:
                    pass

                def save_index(self) -> bool:
                    saved.append(True)
                    return True

            with mock.patch.object(build_index, "FaceDetector", FakeDetector), \
                 mock.patch.object(build_index, "VectorStore", FakeVectorStore), \
                 mock.patch.object(build_index, "load_actor_image_groups", return_value=({}, 3, 0)):
                rc = build_index.main([])

            self.assertEqual(rc, 1)
            self.assertEqual(saved, [])
        finally:
            if sys.path and sys.path[0] == str(Path("backend").resolve()):
                sys.path.pop(0)

    def test_build_index_force_empty_index_allows_save(self) -> None:
        sys.path.insert(0, str(Path("backend").resolve()))
        try:
            build_index = importlib.import_module("jobs.build_index")
            saved: list[bool] = []

            class FakeDetector:
                model_loaded = True

            class FakeVectorStore:
                def create_index(self) -> None:
                    pass

                def save_index(self) -> bool:
                    saved.append(True)
                    return True

            with mock.patch.object(build_index, "FaceDetector", FakeDetector), \
                 mock.patch.object(build_index, "VectorStore", FakeVectorStore), \
                 mock.patch.object(build_index, "load_actor_image_groups", return_value=({}, 3, 0)):
                rc = build_index.main(["--force-empty-index"])

            self.assertEqual(rc, 0)
            self.assertEqual(saved, [True])
        finally:
            if sys.path and sys.path[0] == str(Path("backend").resolve()):
                sys.path.pop(0)

    def test_cleanup_detector_unavailable_aborts_without_deletes(self) -> None:
        sys.path.insert(0, str(Path("backend").resolve()))
        try:
            cleanup = importlib.import_module("jobs.cleanup_images")
            face_detector = importlib.import_module("models.face_detector")
            deleted: list[int] = []
            rows = [
                (
                    {
                        "id": 1,
                        "actor_id": 1,
                        "actor_name": "DetectorFail",
                        "filename": "face.jpg",
                        "file_path": __file__,
                    },
                    1,
                )
            ]

            class FakeDetector:
                is_available = True

            fake_db = Namespace(delete_actor_image=lambda image_id: deleted.append(image_id) or True)
            with mock.patch.object(cleanup, "FaceDetector", FakeDetector), \
                 mock.patch.object(cleanup, "iter_images", return_value=iter(rows)), \
                 mock.patch.object(
                     cleanup,
                     "has_usable_face",
                     side_effect=face_detector.FaceDetectorUnavailableError("synthetic unavailable"),
                 ), \
                 mock.patch.object(cleanup, "actor_db", fake_db):
                rc = cleanup.main(["--apply"])

            self.assertEqual(rc, 1)
            self.assertEqual(deleted, [])
        finally:
            if sys.path and sys.path[0] == str(Path("backend").resolve()):
                sys.path.pop(0)

    def test_cleanup_large_delete_requires_confirmation(self) -> None:
        sys.path.insert(0, str(Path("backend").resolve()))
        try:
            cleanup = importlib.import_module("jobs.cleanup_images")
            deleted: list[int] = []
            rows = [
                (
                    {
                        "id": index,
                        "actor_id": index,
                        "actor_name": f"Missing {index}",
                        "filename": f"{index}.jpg",
                        "file_path": str(Path(tempfile.gettempdir()) / f"missing-{index}.jpg"),
                    },
                    1000,
                )
                for index in range(501)
            ]

            class FakeDetector:
                is_available = True

            fake_db = Namespace(delete_actor_image=lambda image_id: deleted.append(image_id) or True)
            with mock.patch.object(cleanup, "FaceDetector", FakeDetector), \
                 mock.patch.object(cleanup, "iter_images", return_value=iter(rows)), \
                 mock.patch.object(cleanup, "actor_db", fake_db):
                rc = cleanup.main(["--apply", "--delete-missing"])

            self.assertEqual(rc, 1)
            self.assertEqual(deleted, [])
        finally:
            if sys.path and sys.path[0] == str(Path("backend").resolve()):
                sys.path.pop(0)

    def test_cleanup_large_delete_can_be_confirmed(self) -> None:
        sys.path.insert(0, str(Path("backend").resolve()))
        try:
            cleanup = importlib.import_module("jobs.cleanup_images")
            deleted: list[int] = []
            rows = [
                (
                    {
                        "id": index,
                        "actor_id": index,
                        "actor_name": f"Missing {index}",
                        "filename": f"{index}.jpg",
                        "file_path": str(Path(tempfile.gettempdir()) / f"missing-confirm-{index}.jpg"),
                    },
                    1000,
                )
                for index in range(501)
            ]

            class FakeDetector:
                is_available = True

            fake_db = Namespace(delete_actor_image=lambda image_id: deleted.append(image_id) or True)
            with mock.patch.object(cleanup, "FaceDetector", FakeDetector), \
                 mock.patch.object(cleanup, "iter_images", return_value=iter(rows)), \
                 mock.patch.object(cleanup, "actor_db", fake_db):
                rc = cleanup.main(["--apply", "--delete-missing", "--confirm-large-delete"])

            self.assertEqual(rc, 0)
            self.assertEqual(len(deleted), 501)
        finally:
            if sys.path and sys.path[0] == str(Path("backend").resolve()):
                sys.path.pop(0)

    def test_cleanup_limit_caps_scanned_rows(self) -> None:
        sys.path.insert(0, str(Path("backend").resolve()))
        try:
            cleanup = importlib.import_module("jobs.cleanup_images")
            checked: list[int] = []
            rows = [
                (
                    {
                        "id": index,
                        "actor_id": index,
                        "actor_name": f"Missing {index}",
                        "filename": f"{index}.jpg",
                        "file_path": str(Path(tempfile.gettempdir()) / f"limit-missing-{index}.jpg"),
                    },
                    10,
                )
                for index in range(10)
            ]

            class FakeDetector:
                is_available = True

            with mock.patch.object(cleanup, "FaceDetector", FakeDetector), \
                 mock.patch.object(cleanup, "iter_images", return_value=iter(rows)), \
                 mock.patch.object(cleanup, "has_usable_face", side_effect=lambda *_: checked.append(1) or True):
                rc = cleanup.main(["--limit", "3"])

            self.assertEqual(rc, 0)
            self.assertEqual(len(checked), 0)
        finally:
            if sys.path and sys.path[0] == str(Path("backend").resolve()):
                sys.path.pop(0)

    def test_repair_validation_unavailable_prevents_save(self) -> None:
        sys.path.insert(0, str(Path("backend").resolve()))
        try:
            repair = importlib.import_module("jobs.repair_empty_actor_photos")
            added: list[int] = []
            actor = {"id": 7, "name": "No Save", "stashdb_id": "stash-7"}
            performer = {
                "id": "stash-7",
                "images": [{"url": "https://example.test/image.jpg", "width": 100, "height": 100}],
            }
            args = Namespace(
                image_order="largest",
                image_count=1,
                apply=True,
                validate_faces=True,
                min_face_area_ratio=0.01,
                allow_unvalidated_images=False,
            )

            with tempfile.TemporaryDirectory() as temp_dir:
                with mock.patch.object(repair.settings, "actors_dir", Path(temp_dir)), \
                     mock.patch.object(repair, "find_stashdb_performer", return_value=performer), \
                     mock.patch.object(
                         repair,
                         "download_image",
                         side_effect=lambda _url, path: path.parent.mkdir(parents=True, exist_ok=True)
                         or path.write_bytes(b"jpg")
                         or True,
                     ), \
                     mock.patch.object(repair, "image_has_usable_face", return_value=False), \
                     mock.patch.object(repair, "delete_stale_image_rows"), \
                     mock.patch.object(repair.actor_db, "update_actor"), \
                     mock.patch.object(repair.actor_db, "add_actor_image", side_effect=lambda *args: added.append(args[0])):
                    saved = repair.repair_actor_photos(actor, args)

            self.assertEqual(saved, 0)
            self.assertEqual(added, [])
        finally:
            if sys.path and sys.path[0] == str(Path("backend").resolve()):
                sys.path.pop(0)

    def test_ui_defaults_do_not_include_advanced_unsafe_flags(self) -> None:
        source = Path("frontend/src/components/MaintenancePanel.tsx").read_text(encoding="utf-8")
        self.assertNotIn("--force-empty-index", source)
        self.assertNotIn("--confirm-large-delete", source)
        self.assertNotIn("--allow-unvalidated-images", source)
        self.assertIn(
            "Face Recognition Service v1.0.1",
            Path("frontend/src/lib/uiPreferences.tsx").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
