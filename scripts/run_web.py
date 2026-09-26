"""Launch the primary Django web interface.

Usage:
    python scripts/run_web.py
    python scripts/run_web.py 127.0.0.1:8001
"""

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.observability import run_cli


def main() -> None:
    """Run Django's development server with shared diagnostics."""

    manage_py = _REPO_ROOT / "web" / "manage.py"
    arguments = sys.argv[1:] or ["127.0.0.1:8000"]
    exit_code = subprocess.call([sys.executable, str(manage_py), "runserver", *arguments])
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    run_cli(Path(__file__).stem, main)
