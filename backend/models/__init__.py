# Models package - re-export schemas for backward compatibility
from .schemas import (
    FaceMatch,
    UploadResponse,
    BatchUploadResponse,
    ActorCreate,
    ActorUpdate,
    ActorResponse,
    ActorListResponse,
    HealthResponse,
)

__all__ = [
    "FaceMatch",
    "UploadResponse",
    "BatchUploadResponse",
    "ActorCreate",
    "ActorUpdate",
    "ActorResponse",
    "ActorListResponse",
    "HealthResponse",
]
