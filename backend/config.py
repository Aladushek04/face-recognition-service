"""Application configuration."""

from pydantic_settings import BaseSettings
from pydantic import model_validator
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    actors_dir: Path | None = None
    faiss_index_dir: Path | None = None
    videos_dir: Path = Path("D:/Videos")

    @model_validator(mode="after")
    def resolve_dependent_paths(self) -> "Settings":
        if self.actors_dir is None:
            self.actors_dir = self.base_dir / "data" / "actors"
        if self.faiss_index_dir is None:
            self.faiss_index_dir = self.base_dir / "data" / "faiss_index"
        return self

    @property
    def faiss_index_path(self) -> Path:
        if self.faiss_index_dir is None:
            return self.base_dir / "data" / "faiss_index" / "face_index.faiss"
        return self.faiss_index_dir / "face_index.faiss"

    @property
    def faiss_id_map_path(self) -> Path:
        if self.faiss_index_dir is None:
            return self.base_dir / "data" / "faiss_index" / "face_index_ids.pkl"
        return self.faiss_index_dir / "face_index_ids.pkl"

    # Face recognition
    face_detection_threshold: float = 0.5
    face_recognition_threshold: float = 0.65
    face_reference_vote_top_n: int = 3
    face_reference_vote_weight: float = 0.2
    face_reference_vote_bonus: float = 0.01
    faiss_candidate_multiplier: int = 20
    max_faces_per_image: int = 10
    embedding_dim: int = 512
    face_execution_providers: list[str] = ["CPUExecutionProvider"]
    video_frame_step: float = 1.0
    video_face_recognition_threshold: float = 0.55
    video_face_strong_match_threshold: float = 0.68
    video_face_search_k: int = 5
    video_min_actor_hits: int = 2
    concurrent_video_limit: int = 1

    # FAISS
    faiss_index_type: str = "HNSW32"  # HNSW for speed, IVFFlat as alternative
    faiss_m: int = 32  # HNSW M parameter
    faiss_ef_construction: int = 256  # HNSW construction parameter

    # Upload
    max_upload_size_mb: int = 50
    allowed_image_types: list[str] = ["jpg", "jpeg", "png", "webp", "bmp"]

    # StashDB ingestion
    stashdb_api_url: str = "https://stashdb.org/graphql"
    stashdb_api_key: str = ""

    class Config:
        env_file = Path(__file__).parent.parent / ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
