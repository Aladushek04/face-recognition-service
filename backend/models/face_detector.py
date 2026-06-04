"""Face detection and embedding extraction using insightface."""

import numpy as np
import cv2
import os
import site
from pathlib import Path
from insightface.app import FaceAnalysis
from config import settings

try:
    import onnxruntime as ort
except Exception:
    ort = None


class FaceDetector:
    """Handles face detection and embedding extraction."""

    _instance: "FaceDetector | None" = None
    _model_initialized: bool = False

    def __new__(cls) -> "FaceDetector":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._model_initialized:
            return
        self._providers: list[str] = self._get_execution_providers()
        self._app: FaceAnalysis | None = None
        self._model_loaded: bool = False
        self._initialize()
        self._model_initialized = True

    def _get_execution_providers(self) -> list[str]:
        """Resolve configured ONNX Runtime providers with CPU fallback."""
        configured = list(settings.face_execution_providers or ["CPUExecutionProvider"])
        if "CPUExecutionProvider" not in configured:
            configured.append("CPUExecutionProvider")

        if ort is None:
            print("[FaceDetector] ONNX Runtime is not importable; using configured providers as-is")
            return configured

        self._add_nvidia_dll_directories()

        if hasattr(ort, "preload_dlls"):
            try:
                ort.preload_dlls()
            except Exception as exc:
                print(f"[FaceDetector] Warning: Could not preload ONNX Runtime GPU DLLs: {exc}")

        available = set(ort.get_available_providers())
        selected = [provider for provider in configured if provider in available]
        if not selected:
            selected = ["CPUExecutionProvider"]

        missing = [provider for provider in configured if provider not in available]
        if missing:
            print(f"[FaceDetector] Requested providers unavailable: {missing}")
        print(f"[FaceDetector] Available ONNX providers: {sorted(available)}")
        print(f"[FaceDetector] Using ONNX providers: {selected}")
        return selected

    def _add_nvidia_dll_directories(self) -> None:
        """Add NVIDIA pip package DLL folders to Windows DLL search path."""
        if os.name != "nt" or not hasattr(os, "add_dll_directory"):
            return

        candidate_roots: list[Path] = []
        for site_dir in site.getsitepackages():
            candidate_roots.append(Path(site_dir) / "nvidia")

        for root in candidate_roots:
            if not root.exists():
                continue
            for bin_dir in root.glob("*/bin"):
                if not bin_dir.is_dir():
                    continue
                current_path = os.environ.get("PATH", "")
                bin_dir_text = str(bin_dir)
                if bin_dir_text not in current_path.split(os.pathsep):
                    os.environ["PATH"] = bin_dir_text + os.pathsep + current_path
                try:
                    os.add_dll_directory(str(bin_dir))
                except OSError as exc:
                    print(f"[FaceDetector] Warning: Could not add DLL directory {bin_dir}: {exc}")

    def _initialize(self) -> None:
        """Initialize the insightface model."""
        try:
            self._app = FaceAnalysis(
                name="antelopev2",
                root=settings.base_dir / "models",
                providers=self._providers,
            )
            self._app.prepare(
                ctx_id=0,
                det_thresh=settings.face_detection_threshold,
                det_size=(640, 640),
            )
            self._model_loaded = True
            print(f"[FaceDetector] Model loaded successfully with {self._providers}")
        except Exception as e:
            print(f"[FaceDetector] Warning: Could not load antelopev2 model: {e}")
            # Fallback to buffalo_l model
            try:
                self._app = FaceAnalysis(
                    name="buffalo_l",
                    root=settings.base_dir / "models",
                    providers=self._providers,
                )
                self._app.prepare(
                    ctx_id=0,
                    det_thresh=settings.face_detection_threshold,
                    det_size=(640, 640),
                )
                self._model_loaded = True
                print(f"[FaceDetector] Fallback model 'buffalo_l' loaded successfully")
            except Exception as fallback_err:
                print(f"[FaceDetector] Error: Could not load any face model: {fallback_err}")
                self._model_loaded = False

    @property
    def model_loaded(self) -> bool:
        return self._model_loaded

    def detect_faces(self, image: np.ndarray) -> list[dict]:
        """
        Detect faces in an image and extract embeddings.

        Args:
            image: BGR numpy array (OpenCV format)

        Returns:
            List of dicts with face info: bbox, embedding, confidence
        """
        if not self._model_loaded or self._app is None:
            raise RuntimeError("Face detection model not loaded")

        # Convert BGR to RGB for insightface
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Get faces
        faces = self._app.get(image_rgb)

        if not faces:
            return []

        results = []
        for face in faces[:settings.max_faces_per_image]:
            bbox = face.bbox.astype(int)
            embedding = face.embedding.astype(np.float32)

            results.append({
                "bbox": bbox.tolist(),  # [x_min, y_min, x_max, y_max]
                "embedding": embedding,
                "confidence": float(face.det_score),
            })

        return results

    def detect_faces_from_path(self, image_path: Path) -> list[dict]:
        """Detect faces from an image file path."""
        image_bytes = np.fromfile(str(image_path), dtype=np.uint8)
        image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Could not read image: {image_path}")
        return self.detect_faces(image)

    @staticmethod
    def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
        """L2 normalize an embedding vector."""
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
