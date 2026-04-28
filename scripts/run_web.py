"""Launch the Django web interface.

Usage:
    python scripts/run_web.py
    python scripts/run_web.py 127.0.0.1:8001
"""

import subprocess
import sys
from pathlib import Path

_manage_py = Path(__file__).parent.parent / "web" / "manage.py"
_args = sys.argv[1:] or ["127.0.0.1:8000"]

sys.exit(subprocess.call([sys.executable, str(_manage_py), "runserver", *_args]))
