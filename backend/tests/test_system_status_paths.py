from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class SystemStatusPathTests(unittest.TestCase):
    def test_status_reports_canonical_job_and_log_paths(self) -> None:
        sys.path.insert(0, str(Path("backend").resolve()))
        try:
            from routes import system

            with TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                external_base = root / "external" / "FaceService"
                local_app = root / "local" / "Face Recognition Service"
                jobs_dir = local_app / "data" / "jobs"
                logs_dir = local_app / "logs"

                for path in [
                    external_base,
                    external_base / "actors",
                    external_base / "models",
                    external_base / "data" / "faiss_index",
                    root / "videos",
                    jobs_dir,
                    logs_dir,
                ]:
                    path.mkdir(parents=True, exist_ok=True)

                original_settings = system.settings
                original_actor_db = system.actor_db
                original_models = {
                    name: sys.modules.get(name)
                    for name in ["models", "models.face_detector", "models.vector_store"]
                }

                fake_settings = types.SimpleNamespace(
                    base_dir=external_base,
                    actors_dir=external_base / "actors",
                    videos_dir=root / "videos",
                    faiss_index_dir=external_base / "data" / "faiss_index",
                    faiss_index_path=external_base / "data" / "faiss_index" / "face_index.faiss",
                    faiss_id_map_path=external_base / "data" / "faiss_index" / "face_index_ids.pkl",
                    jobs_dir=jobs_dir,
                    logs_dir=logs_dir,
                    host="127.0.0.1",
                    port=12345,
                    debug=False,
                    cors_origins=[],
                    stashdb_api_key="",
                )
                fake_actor_db = types.SimpleNamespace(
                    get_actors_count=lambda: 0,
                    get_actor_images_count=lambda: 0,
                )

                fake_models = types.ModuleType("models")
                fake_face_detector = types.ModuleType("models.face_detector")
                fake_vector_store = types.ModuleType("models.vector_store")

                class FakeFaceDetector:
                    model_loaded = False

                class FakeVectorStore:
                    is_loaded = False
                    index_size = 0

                    def load_index(self) -> None:
                        self.is_loaded = False

                fake_face_detector.FaceDetector = FakeFaceDetector
                fake_vector_store.VectorStore = FakeVectorStore

                system.settings = fake_settings
                system.actor_db = fake_actor_db
                sys.modules["models"] = fake_models
                sys.modules["models.face_detector"] = fake_face_detector
                sys.modules["models.vector_store"] = fake_vector_store
                try:
                    payload = system.system_status()
                finally:
                    system.settings = original_settings
                    system.actor_db = original_actor_db
                    for name, module in original_models.items():
                        if module is None:
                            sys.modules.pop(name, None)
                        else:
                            sys.modules[name] = module

                paths = payload["paths"]
                self.assertEqual(paths["jobs_dir"]["path"], str(jobs_dir))
                self.assertEqual(paths["logs_dir"]["path"], str(logs_dir))
                self.assertNotEqual(paths["jobs_dir"]["path"], str(external_base / "data" / "jobs"))
                self.assertNotEqual(paths["logs_dir"]["path"], str(external_base / "logs"))
                self.assertEqual(payload["service"]["version"], "1.0.3")
        finally:
            if sys.path and sys.path[0] == str(Path("backend").resolve()):
                sys.path.pop(0)


if __name__ == "__main__":
    unittest.main()
