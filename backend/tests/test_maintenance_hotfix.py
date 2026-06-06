from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
