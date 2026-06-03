"""Start backend and frontend dev servers together on Windows."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:3000"


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def port_is_open(host: str, port: int) -> bool:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False

    for family, socktype, proto, _canonname, sockaddr in infos:
        with socket.socket(family, socktype, proto) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(sockaddr) == 0:
                return True
    return False


def service_is_open(port: int) -> bool:
    return any(port_is_open(host, port) for host in ("localhost", "127.0.0.1", "::1"))


def wait_for_port(name: str, port: int, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if service_is_open(port):
            print(f"{name} is ready.")
            return True
        time.sleep(0.5)
    print(f"{name} did not become ready within {timeout:.0f}s.")
    return False


def start_process(name: str, command: list[str], cwd: Path) -> subprocess.Popen:
    print(f"Starting {name}: {' '.join(command)}")
    return subprocess.Popen(command, cwd=str(cwd))


def main() -> int:
    if not (BACKEND_DIR / "main.py").exists():
        print(f"Backend entrypoint not found: {BACKEND_DIR / 'main.py'}")
        return 1
    if not (FRONTEND_DIR / "package.json").exists():
        print(f"Frontend package.json not found: {FRONTEND_DIR / 'package.json'}")
        return 1
    if not (FRONTEND_DIR / "node_modules").exists():
        print("frontend/node_modules is missing. Run first:")
        print(f"  cd {FRONTEND_DIR}")
        print("  npm install")
        return 1

    if service_is_open(8000):
        print(f"Backend port 8000 is already in use. Existing backend may already be running: {BACKEND_URL}")
        backend = None
    else:
        backend = start_process("backend", [sys.executable, "main.py"], BACKEND_DIR)

    if service_is_open(3000):
        print(f"Frontend port 3000 is already in use. Existing frontend may already be running: {FRONTEND_URL}")
        frontend = None
    else:
        frontend = start_process(
            "frontend",
            ["npm.cmd", "run", "dev", "--", "--host", "127.0.0.1", "--port", "3000"],
            FRONTEND_DIR,
        )

    if backend is not None:
        wait_for_port("Backend", 8000)
    if frontend is not None:
        wait_for_port("Frontend", 3000)

    print()
    print("=" * 60)
    print("Face Recognition Service is running")
    print(f"  Web UI:   {FRONTEND_URL}")
    print(f"  API:      {BACKEND_URL}")
    print(f"  API docs: {BACKEND_URL}/docs")
    print("=" * 60)
    print("Keep this window open. Press Ctrl+C to stop started servers.")

    started = [proc for proc in (backend, frontend) if proc is not None]
    if not started:
        return 0

    try:
        while True:
            for proc in started:
                code = proc.poll()
                if code is not None:
                    print(f"A server process exited with code {code}.")
                    return code
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopping servers...")
        for proc in started:
            if proc.poll() is None:
                proc.terminate()
        for proc in started:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("Stopped.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
