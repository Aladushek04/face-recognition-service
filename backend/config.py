"""Application configuration."""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Paths
    base_dir: Path = Path(__file__).parent.parent.parent
    actors_dir: Path = base_dir / "data" / "actors"
    faiss_index_dir: Path = base_dir / "data" / "faiss_index"
    faiss_index_path: Path = faiss_index_dir / "face_index.faiss"
    faiss_id_map_path: Path = faiss_index_dir / "face_index_ids.pkl"

    # Face recognition
    face_detection_threshold: float = 0.5
    face_recognition_threshold: float = 0.65
    max_faces_per_image: int = 10
    embedding_dim: int = 512
    face_execution_providers: list[str] = ["CPUExecutionProvider"]
    video_frame_step: float = 1.0
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
