"""Launch the Streamlit web interface.

Usage:
    python scripts/run_web.py
    python scripts/run_web.py --server.port 8502
"""

import subprocess
import sys
from pathlib import Path

_app = Path(__file__).parent.parent / "src" / "interfaces" / "web" / "streamlit_app.py"

sys.exit(
    subprocess.call(
        [sys.executable, "-m", "streamlit", "run", str(_app)] + sys.argv[1:]
    )
)
