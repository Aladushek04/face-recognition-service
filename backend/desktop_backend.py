"""Frozen backend entrypoint for desktop packaging."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

_log_handle = None


def _backend_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


backend_dir = _backend_dir()
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def _log_path() -> Path:
    return backend_dir / "backend-startup.log"


def _write_startup_error(exc: BaseException) -> None:
    _log_path().write_text(
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        encoding="utf-8",
    )


def _ensure_standard_streams() -> None:
    global _log_handle
    if sys.stdout is not None and sys.stderr is not None:
        return
    _log_handle = _log_path().open("a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = _log_handle
    if sys.stderr is None:
        sys.stderr = _log_handle


def main() -> int:
    try:
        _ensure_standard_streams()
        from config import settings
        from main import app
        import uvicorn

        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            reload=False,
        )
        return 0
    except BaseException as exc:
        _write_startup_error(exc)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
