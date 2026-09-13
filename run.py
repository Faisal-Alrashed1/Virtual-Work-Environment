"""Run the API and web app locally without Docker: python3 run.py"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API_DIR = ROOT / "apps" / "api"
WEB_DIR = ROOT / "apps" / "web"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"


def start_processes() -> list[subprocess.Popen]:
    if not VENV_PYTHON.is_file():
        raise RuntimeError("Run first: python3 -m venv .venv")
    if not (WEB_DIR / "node_modules").exists():
        raise RuntimeError("Run first: cd apps/web && npm install")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(API_DIR)
    api = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
        cwd=API_DIR,
        env=environment,
    )
    web = subprocess.Popen(["npm", "run", "dev"], cwd=WEB_DIR, env=environment)
    return [api, web]


def stop_processes(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> int:
    processes: list[subprocess.Popen] = []
    try:
        processes = start_processes()
        print("\nVenv: http://localhost:3000")
        print("API docs: http://localhost:8000/docs")
        print("Press Control+C to stop.\n")
        return max(process.wait() for process in processes)
    except RuntimeError as error:
        print(f"Setup error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        stop_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
