import sqlite3
import cv2
import json
import threading
import numpy as np
from pathlib import Path
from collections import defaultdict
from models.face_detector import FaceDetector
from models.vector_store import VectorStore
from config import settings

class VideoProcessor:
    _lock = threading.Lock()
    
    def __init__(self):
        self.detector = FaceDetector()
        self.vector_store = VectorStore()
        if not self.vector_store.is_loaded:
            self.vector_store.load_index()

    def process(self, video_id: int, filepath: str, db_path: str):
        """Processes a video file to detect faces and match them with actors."""
        cap = cv2.VideoCapture(filepath)
        if not cap.isOpened():
            self._update_status(db_path, video_id, "failed", "Could not open video file.")
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if fps <= 0 or total_frames <= 0:
            cap.release()
            self._update_status(db_path, video_id, "failed", "Invalid video metadata (FPS or frame count).")
            return

        duration = total_frames / fps
        size_bytes = Path(filepath).stat().st_size
        
        # Update video metadata, set status to processing, and reset progress
        self._update_metadata(db_path, video_id, duration, size_bytes)
        self._update_status(db_path, video_id, "processing")
        self._update_progress(db_path, video_id, 0)

        # Generate thumbnail
        self._generate_thumbnail(cap, video_id, total_frames, fps)

        candidate_detections = []
        
        try:
            candidate_detections.extend(
                self._scan_video_faces(
                    cap=cap,
                    video_id=video_id,
                    db_path=db_path,
                    fps=fps,
                    total_frames=total_frames,
                    frame_step_seconds=settings.video_frame_step,
                    threshold=settings.video_face_recognition_threshold,
                    progress_start=0,
                    progress_end=85,
                )
            )

            detections = self._confirm_video_detections(
                candidate_detections,
                min_actor_hits=settings.video_min_actor_hits,
            )

            if self._should_run_fallback(detections):
                print(f"[VideoProcessor] Running fallback pass for video {video_id}")
                fallback_candidates = self._scan_video_faces(
                    cap=cap,
                    video_id=video_id,
                    db_path=db_path,
                    fps=fps,
                    total_frames=total_frames,
                    frame_step_seconds=settings.video_fallback_frame_step,
                    threshold=settings.video_fallback_face_recognition_threshold,
                    progress_start=85,
                    progress_end=99,
                )
                candidate_detections.extend(fallback_candidates)
                detections = self._confirm_video_detections(
                    candidate_detections,
                    min_actor_hits=settings.video_fallback_min_actor_hits,
                )

            cap.release()

            # Save detections to database
            self._save_detections(db_path, detections)
            self._update_status(db_path, video_id, "completed")

        except Exception as e:
            cap.release()
            self._update_status(db_path, video_id, "failed", str(e))

    def _scan_video_faces(
        self,
        *,
        cap,
        video_id: int,
        db_path: str,
        fps: float,
        total_frames: int,
        frame_step_seconds: float,
        threshold: float,
        progress_start: int,
        progress_end: int,
    ) -> list[dict]:
        frame_step = max(int(fps * max(frame_step_seconds, 0.1)), 1)
        frame_idx = 0
        last_progress_update = progress_start - 5
        candidate_detections: list[dict] = []

        while True:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break

            timestamp = frame_idx / fps
            ratio = min(max(frame_idx / total_frames, 0.0), 1.0)
            progress = min(int(progress_start + ratio * (progress_end - progress_start)), progress_end)
            if progress >= last_progress_update + 5:
                self._update_progress(db_path, video_id, progress)
                last_progress_update = progress

            # Protect FaceDetector and VectorStore with lock to avoid concurrent model access.
            with self._lock:
                faces = self.detector.detect_faces(frame)

                for face in faces:
                    embedding = face["embedding"].astype(np.float32)
                    # Search several actor candidates. Video frames are often
                    # blurrier/profile-heavy, so top-1 alone can miss a real
                    # actor when a similar reference vector ranks first.
                    results = self.vector_store.search(
                        embedding,
                        k=max(settings.video_face_search_k, 1),
                        threshold=threshold,
                    )

                    for actor_id, confidence in results:
                        bbox = face["bbox"]  # [x1, y1, x2, y2]
                        candidate_detections.append({
                            "video_id": video_id,
                            "actor_id": actor_id,
                            "timestamp": round(timestamp, 2),
                            "bbox": json.dumps([int(b) for b in bbox]),
                            "confidence": float(confidence),
                        })

            frame_idx += frame_step
            if frame_idx >= total_frames:
                break

        return candidate_detections

    def _should_run_fallback(self, detections: list[dict]) -> bool:
        if not settings.video_fallback_enabled:
            return False
        actor_ids = {int(item["actor_id"]) for item in detections}
        return len(actor_ids) < max(settings.video_fallback_trigger_min_actors, 0)

    def _generate_thumbnail(self, cap, video_id: int, total_frames: int, fps: float):
        try:
            thumbnails_dir = Path(settings.base_dir) / "thumbnails"
            thumbnails_dir.mkdir(parents=True, exist_ok=True)
            thumb_path = thumbnails_dir / f"{video_id}.jpg"
            
            # Skip if thumbnail already exists
            if thumb_path.exists():
                return
                
            # Seek to 5th second or 10% of total frames
            target_frame = min(int(fps * 5.0), total_frames - 1) if fps > 0 else 0
            target_frame = max(target_frame, 0)
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = cap.read()
            if ret:
                h, w = frame.shape[:2]
                target_h = 360
                target_w = int((w / h) * target_h)
                resized = cv2.resize(frame, (target_w, target_h))
                cv2.imwrite(str(thumb_path), resized)
        except Exception as e:
            print(f"Failed to generate thumbnail for video {video_id}: {e}")

    def _update_status(self, db_path: str, video_id: int, status: str, error_message: str = None):
        with sqlite3.connect(db_path) as conn:
            if status == "completed":
                conn.execute(
                    "UPDATE videos SET status = ?, progress = 100, error_message = ?, updated_at = datetime('now') WHERE id = ?",
                    (status, error_message, video_id)
                )
            else:
                conn.execute(
                    "UPDATE videos SET status = ?, error_message = ?, updated_at = datetime('now') WHERE id = ?",
                    (status, error_message, video_id)
                )
            conn.commit()

    def _update_progress(self, db_path: str, video_id: int, progress: int):
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE videos SET progress = ?, updated_at = datetime('now') WHERE id = ?",
                (progress, video_id)
            )
            conn.commit()

    def _update_metadata(self, db_path: str, video_id: int, duration: float, size_bytes: int):
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE videos SET duration = ?, size_bytes = ? WHERE id = ?",
                (duration, size_bytes, video_id)
            )
            conn.commit()

    def _save_detections(self, db_path: str, detections: list):
        if not detections:
            return
        with sqlite3.connect(db_path) as conn:
            conn.executemany(
                """INSERT INTO video_detections (video_id, actor_id, timestamp, bbox, confidence)
                   VALUES (:video_id, :actor_id, :timestamp, :bbox, :confidence)""",
                detections
            )
            conn.commit()

    def _confirm_video_detections(self, candidates: list[dict], min_actor_hits: int) -> list[dict]:
        """Keep actor hits that are repeated or individually strong.

        Photo matching can safely use a stricter single-frame threshold. Video
        matching needs aggregation because many frames are soft, angled, or
        motion-blurred. We keep all timestamps for actors that either appear
        more than once or have a high-confidence match.
        """
        if not candidates:
            return []

        grouped: dict[int, list[dict]] = defaultdict(list)
        for item in candidates:
            grouped[int(item["actor_id"])].append(item)

        confirmed: list[dict] = []
        for hits in grouped.values():
            max_confidence = max(float(hit["confidence"]) for hit in hits)
            if (
                len(hits) >= max(min_actor_hits, 1)
                or max_confidence >= settings.video_face_strong_match_threshold
            ):
                confirmed.extend(hits)

        # Avoid writing duplicate timestamps for the same actor when several
        # faces/candidates collapse onto the same second.
        best_by_actor_time: dict[tuple[int, float], dict] = {}
        for item in confirmed:
            key = (int(item["actor_id"]), float(item["timestamp"]))
            current = best_by_actor_time.get(key)
            if current is None or float(item["confidence"]) > float(current["confidence"]):
                best_by_actor_time[key] = item

        return sorted(
            best_by_actor_time.values(),
            key=lambda item: (float(item["timestamp"]), int(item["actor_id"])),
        )
