"""Application configuration and .env loading."""

import os
from pathlib import Path


def load_env_file() -> None:
    """Load simple KEY=VALUE entries from the project .env file."""
    module_dir = Path(__file__).resolve().parent
    env_paths = (module_dir / ".env", module_dir.parent / ".env")
    env_path = next((path for path in env_paths if path.exists()), env_paths[0])
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            os.environ.setdefault(key, value)


def required_env(name: str) -> str:
    """Return a required environment variable or raise a useful error."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
