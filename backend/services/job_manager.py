"""Subprocess-backed maintenance job manager."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
JOBS_DIR = settings.base_dir / "data" / "jobs"


@dataclass(frozen=True)
class JobDefinition:
    script: str
    supports_apply: bool = True
    heavy: bool = True
    default_args: tuple[str, ...] = ()
    dry_run_args: tuple[str, ...] = ()
    writes_without_apply: bool = False


JOB_DEFINITIONS: dict[str, JobDefinition] = {
    "build_index": JobDefinition(
        "scripts/build_index.py",
        supports_apply=False,
        writes_without_apply=True,
    ),
    "repair_empty_actor_photos": JobDefinition(
        "scripts/repair_empty_actor_photos.py",
        default_args=("--action", "repair"),
    ),
    "cleanup_actors": JobDefinition("scripts/cleanup_actors.py"),
    "cleanup_empty_actor_dirs": JobDefinition("scripts/cleanup_empty_actor_dirs.py"),
    "cleanup_images": JobDefinition("scripts/cleanup_images.py"),
    "scrape_stashdb": JobDefinition("scripts/scrape_stashdb.py", dry_run_args=("--dry-run",)),
}


class JobManager:
    """Run maintenance scripts as tracked background jobs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: dict[str, subprocess.Popen] = {}
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        self._recover_running_jobs()

    def list_jobs(self) -> list[dict[str, Any]]:
        jobs = [self._read_job(path) for path in JOBS_DIR.glob("*.json")]
        return sorted(
            (job for job in jobs if job),
            key=lambda item: float(item.get("created_at") or 0),
            reverse=True,
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        path = self._metadata_path(job_id)
        if not path.exists():
            return None
        return self._read_job(path)

    def get_logs(self, job_id: str, tail_bytes: int | None = None) -> str | None:
        job = self.get_job(job_id)
        if not job:
            return None
        log_path = Path(job["log_path"])
        if not log_path.exists():
            return ""
        if tail_bytes is None or tail_bytes <= 0:
            return log_path.read_text(encoding="utf-8", errors="replace")
        with open(log_path, "rb") as file:
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(max(size - tail_bytes, 0), os.SEEK_SET)
            return file.read().decode("utf-8", errors="replace")

    def start_job(
        self,
        *,
        job_type: str,
        apply: bool,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        definition = JOB_DEFINITIONS.get(job_type)
        if definition is None:
            raise ValueError(f"Unknown job type: {job_type}")
        if apply and not definition.supports_apply and not definition.writes_without_apply:
            raise ValueError(f"Job type '{job_type}' does not use apply mode")

        requested_args = self._sanitize_args(args or [])
        command = self._build_command(definition, apply, requested_args)
        dry_run = not apply and not definition.writes_without_apply

        with self._lock:
            if definition.heavy and self._has_running_heavy_job():
                raise RuntimeError("Another heavy maintenance job is already running")

            job_id = uuid.uuid4().hex
            log_path = JOBS_DIR / f"{job_id}.log"
            job = {
                "id": job_id,
                "type": job_type,
                "status": "queued",
                "created_at": time.time(),
                "started_at": None,
                "finished_at": None,
                "progress": None,
                "exit_code": None,
                "command": command,
                "dry_run": dry_run,
                "log_path": str(log_path),
                "error": None,
                "heavy": definition.heavy,
            }
            self._write_job(job)

            thread = threading.Thread(
                target=self._run_job,
                args=(job_id, command, env or {}),
                daemon=True,
            )
            thread.start()
            return job

    def cancel_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            process = self._processes.get(job_id)
            job = self.get_job(job_id)
            if job is None:
                return None
            if process is None or process.poll() is not None:
                return job

            job["status"] = "cancelling"
            job["error"] = "Cancellation requested."
            self._write_job(job)

            try:
                process.terminate()
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
            return job

    def _build_command(self, definition: JobDefinition, apply: bool, args: list[str]) -> list[str]:
        script_path = PROJECT_ROOT / definition.script
        command = [sys.executable, str(script_path), *definition.default_args]
        if apply and definition.supports_apply and "--apply" not in args:
            command.append("--apply")
        if not apply:
            for item in definition.dry_run_args:
                if item not in args:
                    command.append(item)
        command.extend(args)
        return command

    def _sanitize_args(self, args: list[str]) -> list[str]:
        clean: list[str] = []
        for item in args:
            if not isinstance(item, str):
                raise ValueError("All args must be strings")
            if "\x00" in item or "\r" in item or "\n" in item:
                raise ValueError("Args must not contain control line breaks")
            clean.append(item)
        return clean

    def _run_job(self, job_id: str, command: list[str], extra_env: dict[str, str]) -> None:
        job = self.get_job(job_id)
        if job is None:
            return

        log_path = Path(job["log_path"])
        env = os.environ.copy()
        env.update(extra_env)
        env["PYTHONIOENCODING"] = "utf-8"

        process: subprocess.Popen | None = None
        try:
            job["status"] = "running"
            job["started_at"] = time.time()
            self._write_job(job)

            with open(log_path, "w", encoding="utf-8", errors="replace") as log_file:
                log_file.write(f"$ {' '.join(command)}\n\n")
                log_file.flush()
                process = subprocess.Popen(
                    command,
                    cwd=str(PROJECT_ROOT),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                )
                with self._lock:
                    self._processes[job_id] = process
                exit_code = process.wait()

            job = self.get_job(job_id) or job
            job["exit_code"] = exit_code
            job["finished_at"] = time.time()
            if job.get("status") == "cancelling":
                job["status"] = "cancelled"
                job["error"] = job.get("error") or "Cancelled."
            elif exit_code == 0:
                job["status"] = "completed"
                job["error"] = None
            else:
                job["status"] = "failed"
                job["error"] = f"Process exited with code {exit_code}."
            self._write_job(job)
        except Exception as exc:
            job = self.get_job(job_id) or job
            job["status"] = "failed"
            job["finished_at"] = time.time()
            job["exit_code"] = -1
            job["error"] = str(exc)
            self._append_log(log_path, f"\n[JobManager] {exc}\n")
            self._write_job(job)
        finally:
            with self._lock:
                self._processes.pop(job_id, None)

    def _has_running_heavy_job(self) -> bool:
        for job in self.list_jobs():
            if job.get("heavy") and job.get("status") in {"queued", "running", "cancelling"}:
                return True
        return False

    def _recover_running_jobs(self) -> None:
        for job in self.list_jobs():
            if job.get("status") in {"queued", "running", "cancelling"}:
                job["status"] = "failed"
                job["finished_at"] = time.time()
                job["exit_code"] = -1
                job["error"] = "Backend restarted while this job was running."
                self._write_job(job)

    def _metadata_path(self, job_id: str) -> Path:
        if not re_valid_job_id(job_id):
            raise ValueError("Invalid job id")
        return JOBS_DIR / f"{job_id}.json"

    def _read_job(self, path: Path) -> dict[str, Any] | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_job(self, job: dict[str, Any]) -> None:
        path = self._metadata_path(str(job["id"]))
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def _append_log(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8", errors="replace") as file:
            file.write(text)


def re_valid_job_id(job_id: str) -> bool:
    return len(job_id) == 32 and all(char in "0123456789abcdef" for char in job_id)


job_manager = JobManager()
