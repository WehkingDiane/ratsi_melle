from __future__ import annotations

from datetime import date
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - test safety
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching.models import SessionReference
from src.fetching.sessionnet_client import SessionNetClient


def test_build_paths_use_month_subdirectory(tmp_path: Path) -> None:
    client = SessionNetClient(storage_root=tmp_path / "data" / "raw")
    reference = SessionReference(
        committee="Rat",
        meeting_name="Ratssitzung",
        session_id="7001",
        date=date(2026, 3, 10),
        start_time="19:00 Uhr",
        detail_url="https://example.org/si0057.asp?__ksinr=7001",
    )

    overview = client._build_month_filename(2026, 3)
    session_dir = client._build_session_directory(reference)

    assert overview.as_posix().endswith("data/raw/2026/03/2026-03_overview.html")
    assert session_dir.as_posix().endswith("data/raw/2026/03/2026-03-10-Rat-7001")


def test_legacy_storage_layout_is_migrated_once(tmp_path: Path) -> None:
    data_root = tmp_path / "data" / "raw"
    year_dir = data_root / "2026"
    year_dir.mkdir(parents=True, exist_ok=True)

    legacy_overview = year_dir / "2026-03_overview.html"
    legacy_overview.write_text("<html></html>", encoding="utf-8")

    legacy_session_dir = year_dir / "2026-03-10_Rat_7001"
    legacy_session_dir.mkdir()
    (legacy_session_dir / "manifest.json").write_text("{}", encoding="utf-8")

    SessionNetClient(storage_root=data_root)

    assert not legacy_overview.exists()
    assert not legacy_session_dir.exists()
    assert (data_root / "2026" / "03" / "2026-03_overview.html").exists()
    assert (data_root / "2026" / "03" / "2026-03-10_Rat_7001" / "manifest.json").exists()
