"""Shared runtime guards for maintenance jobs."""

from __future__ import annotations

import sys


def configure_job_io() -> None:
    """Use UTF-8 job output in packaged Windows log capture."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
