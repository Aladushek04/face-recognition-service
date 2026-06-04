"""Maintenance tooling routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from services.job_manager import JOB_DEFINITIONS, job_manager


router = APIRouter(prefix="/api/tools", tags=["tools"])


class JobStartRequest(BaseModel):
    apply: bool = False
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


@router.get("/jobs")
def list_jobs() -> dict[str, Any]:
    return {
        "job_types": {
            name: {
                "supports_apply": definition.supports_apply,
                "writes_without_apply": definition.writes_without_apply,
                "heavy": definition.heavy,
            }
            for name, definition in sorted(JOB_DEFINITIONS.items())
        },
        "jobs": job_manager.list_jobs(),
    }


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    try:
        job = job_manager.get_job(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job id")
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/logs", response_class=PlainTextResponse)
def get_job_logs(
    job_id: str,
    tail_bytes: int | None = Query(None, ge=1, le=2_000_000),
) -> str:
    try:
        logs = job_manager.get_logs(job_id, tail_bytes=tail_bytes)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job id")
    if logs is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return logs


@router.post("/jobs/{job_type}")
def start_job(
    job_type: str,
    request: JobStartRequest | None = Body(default=None),
) -> dict[str, Any]:
    request = request or JobStartRequest()
    try:
        job = job_manager.start_job(
            job_type=job_type,
            apply=request.apply,
            args=request.args,
            env=request.env,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"status": "started", "job": job}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    try:
        job = job_manager.cancel_job(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job id")
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "cancel_requested", "job": job}
