"""One-command bring-up for the whole Meika stack.

Starts Postgres, waits for it to accept connections, applies migrations,
seeds demo data, and launches the API — so a fresh clone goes from nothing
to a working system with one command:

    python scripts/dev_up.py

Add --no-serve to prepare everything but not hold the terminal with the API
(useful in CI, or when you want to run uvicorn yourself with --reload).

The Flutter client is deliberately NOT started here: `flutter run` wants to
own a terminal and pick its own device. Once this script reports the API is
up, run the command it prints.
"""

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
API_HOST = "127.0.0.1"
API_PORT = 8000
HEALTH_URL = f"http://{API_HOST}:{API_PORT}/api/v1/health"


def _python() -> str:
    """The backend's venv interpreter when it exists, else the current one."""
    for candidate in (
        BACKEND / ".venv" / "Scripts" / "python.exe",  # Windows
        BACKEND / ".venv" / "bin" / "python",  # POSIX
    ):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def run(cmd: list[str], *, cwd: pathlib.Path = BACKEND, check: bool = True) -> int:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd))
    if check and result.returncode != 0:
        raise SystemExit(f"command failed ({result.returncode}): {' '.join(cmd)}")
    return result.returncode


def step(label: str) -> None:
    print(f"\n\033[1m==> {label}\033[0m")


def ensure_env_file() -> None:
    step("Checking .env")
    env, example = ROOT / ".env", ROOT / ".env.example"
    if env.exists():
        print("  .env present")
        return
    if not example.exists():
        raise SystemExit("  neither .env nor .env.example found")
    shutil.copyfile(example, env)
    print("  .env was missing — copied from .env.example")
    print("  (optional: set GEMINI_API_KEY / SERPAPI_API_KEY for LLM replies and live price search)")


def start_postgres() -> None:
    step("Starting Postgres (docker compose)")
    if shutil.which("docker") is None:
        raise SystemExit("  docker not found on PATH — install Docker Desktop, or point DATABASE_URL at your own Postgres")
    run(["docker", "compose", "up", "-d", "postgres"], cwd=ROOT)

    print("  waiting for Postgres to accept connections...")
    for attempt in range(60):
        probe = subprocess.run(
            ["docker", "compose", "exec", "-T", "postgres", "pg_isready", "-U", os.environ.get("POSTGRES_USER", "meika")],
            cwd=str(ROOT),
            capture_output=True,
        )
        if probe.returncode == 0:
            print(f"  ready after {attempt * 2}s")
            return
        time.sleep(2)
    raise SystemExit("  Postgres did not become ready in 120s")


def migrate() -> None:
    step("Applying database migrations")
    run([_python(), "-m", "alembic", "upgrade", "head"])


def seed() -> None:
    step("Seeding demo data")
    run([_python(), "-m", "scripts.seed_dev_user"])
    run([_python(), "-m", "scripts.seed_catalog"])


def api_already_up() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def serve() -> None:
    step("Starting the API")
    if api_already_up():
        print(f"  something is already serving {HEALTH_URL} — leaving it alone")
        print_next_steps()
        return

    print(f"  http://{API_HOST}:{API_PORT}      docs: http://{API_HOST}:{API_PORT}/docs")
    print_next_steps()
    print("\n  (Ctrl+C to stop)\n")
    run([_python(), "-m", "uvicorn", "app.main:app", "--host", API_HOST, "--port", str(API_PORT)], check=False)


def print_next_steps() -> None:
    print("\n  Next, in a second terminal, start the Flutter client:")
    print("    cd frontend")
    print("    flutter run -d chrome --web-port=8080 \\")
    print(f"      --dart-define=MEIKA_API_BASE_URL=http://localhost:{API_PORT}/api/v1 \\")
    print(f"      --dart-define=MEIKA_WS_BASE_URL=ws://localhost:{API_PORT}/ws")
    print("\n  Port 8080 matters: it is the origin allowed by CORS_ORIGINS in .env.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bring up the full Meika stack.")
    parser.add_argument("--no-serve", action="store_true", help="prepare everything but do not start the API")
    parser.add_argument("--skip-seed", action="store_true", help="do not (re-)seed demo data")
    args = parser.parse_args()

    print("\033[1mMeika — full stack bring-up\033[0m")
    ensure_env_file()
    start_postgres()
    migrate()
    if not args.skip_seed:
        seed()

    if args.no_serve:
        step("Ready")
        print("  database migrated and seeded; API not started (--no-serve)")
        print_next_steps()
        return

    serve()


if __name__ == "__main__":
    main()
