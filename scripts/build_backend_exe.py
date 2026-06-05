"""Build the desktop backend executable with PyInstaller."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
DIST_DIR = ROOT / "desktop" / "electron" / "backend-dist"


def main() -> int:
    spec_path = BACKEND_DIR / "backend.spec"
    if not spec_path.exists():
        print(f"Missing spec: {spec_path}")
        return 1

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(ROOT / "tmp" / "pyinstaller-build"),
        str(spec_path),
    ]
    print(" ".join(command))
    return subprocess.call(command, cwd=str(BACKEND_DIR))


if __name__ == "__main__":
    raise SystemExit(main())
