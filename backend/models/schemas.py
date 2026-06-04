"""Pydantic models for request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FaceMatch(BaseModel):
    """A single face match result."""
    actor_id: int
    actor_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    face_bbox: list[int] = Field(description="[x_min, y_min, x_max, y_max]")
    actor_image_url: Optional[str] = None
    face_embedding: Optional[list[float]] = None


class UploadResponse(BaseModel):
    """Response for image upload."""
    image_id: str
    filename: str
    faces_detected: int
    matches: list[FaceMatch]
    closest_matches: list[FaceMatch] = Field(default_factory=list)
    all_faces: list[list[int]] = Field(default_factory=list, description="All detected face bounding boxes")
    processing_time_ms: float


class BatchUploadResponse(BaseModel):
    """Response for batch upload."""
    results: list[UploadResponse]


class ActorCreate(BaseModel):
    """Schema for creating a new actor."""
    name: str = Field(..., min_length=1, max_length=255)
    stashdb_id: Optional[str] = None
    birth_year: Optional[int] = None
    birthdate: Optional[str] = None
    gender: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    scene_count: Optional[int] = None
    breast_type: Optional[str] = None
    height_cm: Optional[int] = None
    measurements: Optional[str] = None
    cup_size: Optional[str] = None
    band_size: Optional[int] = None
    waist_size: Optional[int] = None
    hip_size: Optional[int] = None
    country: Optional[str] = None
    ethnicity: Optional[str] = None
    eye_color: Optional[str] = None
    hair_color: Optional[str] = None
    tattoos: list[str] = Field(default_factory=list)
    piercings: list[str] = Field(default_factory=list)
    career_start_year: Optional[int] = None
    career_end_year: Optional[int] = None
    image_url: Optional[str] = None
    stashdb_urls: list[str] = Field(default_factory=list)
    bio: Optional[str] = None
    filmography: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class ActorUpdate(BaseModel):
    """Schema for updating an actor."""
    name: Optional[str] = None
    stashdb_id: Optional[str] = None
    birth_year: Optional[int] = None
    birthdate: Optional[str] = None
    gender: Optional[str] = None
    aliases: Optional[list[str]] = None
    scene_count: Optional[int] = None
    breast_type: Optional[str] = None
    height_cm: Optional[int] = None
    measurements: Optional[str] = None
    cup_size: Optional[str] = None
    band_size: Optional[int] = None
    waist_size: Optional[int] = None
    hip_size: Optional[int] = None
    country: Optional[str] = None
    ethnicity: Optional[str] = None
    eye_color: Optional[str] = None
    hair_color: Optional[str] = None
    tattoos: Optional[list[str]] = None
    piercings: Optional[list[str]] = None
    career_start_year: Optional[int] = None
    career_end_year: Optional[int] = None
    image_url: Optional[str] = None
    stashdb_urls: Optional[list[str]] = None
    bio: Optional[str] = None
    filmography: Optional[str] = None
    tags: Optional[list[str]] = None


class ActorResponse(BaseModel):
    """Schema for actor response."""
    id: int
    stashdb_id: Optional[str] = None
    name: str
    birth_year: Optional[int] = None
    birthdate: Optional[str] = None
    gender: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    scene_count: Optional[int] = None
    breast_type: Optional[str] = None
    height_cm: Optional[int] = None
    measurements: Optional[str] = None
    cup_size: Optional[str] = None
    band_size: Optional[int] = None
    waist_size: Optional[int] = None
    hip_size: Optional[int] = None
    country: Optional[str] = None
    ethnicity: Optional[str] = None
    eye_color: Optional[str] = None
    hair_color: Optional[str] = None
    tattoos: list[str] = Field(default_factory=list)
    piercings: list[str] = Field(default_factory=list)
    career_start_year: Optional[int] = None
    career_end_year: Optional[int] = None
    image_url: Optional[str] = None
    stashdb_urls: list[str] = Field(default_factory=list)
    bio: Optional[str] = None
    filmography: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    reference_image_count: int = 0
    preview_image_url: Optional[str] = None
    reference_images: list["ActorImageResponse"] = Field(default_factory=list)
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ActorImageResponse(BaseModel):
    """Schema for actor reference image metadata."""
    id: int
    filename: str
    url: str
    created_at: Optional[str] = None


class ActorListResponse(BaseModel):
    """Paginated actor list response."""
    actors: list[ActorResponse]
    total: int
    page: int
    page_size: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    actors_count: int
    index_size: int
    faiss_available: bool
    model_loaded: bool
