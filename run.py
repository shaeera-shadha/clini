"""One-command local run for ClinNote.

    python run.py           # uses LLM_MODE from backend/.env (mock if not set up)
    python run.py --mock    # force offline mock mode (replays a recorded live run)
    python run.py --planted # mock mode with hand-made planted extractor mistakes (demo)
    python run.py --setup   # install dependencies only
    python run.py --no-browser

Creates backend/.venv and installs Python dependencies, runs `npm install` for the frontend,
creates backend/.env from .env.example if missing, then starts the API (port 8000) and the web
app (port 5173) and opens the browser. Ctrl+C stops both.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import tomllib
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
WINDOWS = os.name == "nt"
VENV_PYTHON = BACKEND / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")
NPM = "npm.cmd" if WINDOWS else "npm"
APP_URL = "http://127.0.0.1:5173"
HEALTH_URL = f"{APP_URL}/api/health"


def step(message: str) -> None:
    print(f"\n> {message}", flush=True)


def check_prerequisites() -> None:
    if sys.version_info[:2] != (3, 11):
        sys.exit(f"Python 3.11 is required (this is {sys.version.split()[0]}).")
    if shutil.which(NPM) is None:
        sys.exit("Node.js 20 or newer (with npm) is required: https://nodejs.org")


def setup() -> None:
    if not VENV_PYTHON.exists():
        step("Creating backend/.venv")
        subprocess.run([sys.executable, "-m", "venv", str(BACKEND / ".venv")], check=True)
    step("Installing backend dependencies")
    # The backend runs from backend/, so only its dependencies are installed, not the package.
    project = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = [*project["dependencies"], *project["optional-dependencies"]["dev"]]
    subprocess.run(
        [str(VENV_PYTHON), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
         *requirements],
        check=True,
    )  # fmt: skip
    if not (FRONTEND / "node_modules").exists():
        step("Installing frontend dependencies")
        subprocess.run([NPM, "install", "--no-fund", "--no-audit"], cwd=FRONTEND, check=True)
    env_file = BACKEND / ".env"
    if not env_file.exists():
        step("Creating backend/.env from .env.example (mock mode)")
        shutil.copy(BACKEND / ".env.example", env_file)


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = BACKEND / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    return values


def choose_mode(force_mock: bool) -> str:
    env = read_env()
    mode = "mock" if force_mock else env.get("LLM_MODE", "mock")
    if mode == "live" and not env.get("GROQ_API_KEY"):
        print(
            "\nLLM_MODE=live but GROQ_API_KEY is empty in backend/.env, so starting in mock mode.\n"
            "Add a key with:  powershell -File backend/scripts/set-groq-key.ps1  (or edit .env)."
        )
        mode = "mock"
    return mode


def ensure_ports_free() -> None:
    for port, what in ((8000, "API"), (5173, "web app")):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                sys.exit(
                    f"Port {port} (the {what}) is already in use, probably by another ClinNote "
                    "or dev server. Stop it and run this again."
                )


def wait_for(url: str, timeout: float = 60) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except OSError:
            time.sleep(0.5)
    return False


def start(mode: str, open_browser: bool, planted: bool = False) -> None:
    ensure_ports_free()
    env = {**os.environ, "LLM_MODE": mode}
    if planted:
        env["FIXTURES_DIR"] = str(BACKEND / "tests" / "fixtures")
    if mode == "mock":
        env.setdefault("MOCK_LATENCY_MS", "300")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if WINDOWS else 0
    api = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "app.main:app", "--port", "8000"],
        cwd=BACKEND,
        env=env,
        creationflags=flags,
    )
    web = subprocess.Popen(
        [NPM, "run", "dev", "--", "--host", "127.0.0.1"],
        cwd=FRONTEND,
        creationflags=flags,
    )
    try:
        label = "mock mode with planted mistakes" if planted else f"{mode} mode"
        step(f"Starting ClinNote in {label}")
        if not wait_for(HEALTH_URL):
            sys.exit("The app did not start within 60 seconds. See the output above.")
        print(f"\nClinNote is running at {APP_URL}  (Ctrl+C to stop)\n", flush=True)
        if open_browser:
            webbrowser.open(APP_URL)
        while api.poll() is None and web.poll() is None:
            time.sleep(0.5)
        sys.exit("A server stopped unexpectedly. See the output above.")
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        for proc in (web, api):
            if proc.poll() is None:
                if WINDOWS:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        check=False,
                        capture_output=True,
                    )
                else:
                    proc.send_signal(signal.SIGINT)
                    proc.wait(timeout=10)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ClinNote locally.")
    parser.add_argument("--mock", action="store_true", help="force offline mock mode")
    parser.add_argument(
        "--planted",
        action="store_true",
        help="mock mode with hand-made fixtures containing planted extractor mistakes",
    )
    parser.add_argument("--setup", action="store_true", help="install dependencies and exit")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    args = parser.parse_args()
    check_prerequisites()
    setup()
    if args.setup:
        print("\nSetup complete. Run: python run.py")
        return
    mode = choose_mode(args.mock or args.planted)
    start(mode, open_browser=not args.no_browser, planted=args.planted)


if __name__ == "__main__":
    main()
