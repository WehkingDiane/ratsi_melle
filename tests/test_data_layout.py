from __future__ import annotations

from pathlib import Path

from src import data_layout


def test_migrate_legacy_database_layout_moves_sqlite_and_sidecars(tmp_path: Path, monkeypatch) -> None:
    processed_dir = tmp_path / "processed"
    db_dir = tmp_path / "db"
    processed_dir.mkdir(parents=True, exist_ok=True)

    legacy_db = processed_dir / "local_index.sqlite"
    legacy_db.write_text("db")
    legacy_wal = processed_dir / "local_index.sqlite-wal"
    legacy_wal.write_text("wal")
    legacy_shm = processed_dir / "local_index.sqlite-shm"
    legacy_shm.write_text("shm")

    monkeypatch.setattr(data_layout, "PROCESSED_DATA_DIR", processed_dir)
    monkeypatch.setattr(data_layout, "DB_DIR", db_dir)
    monkeypatch.setattr(data_layout, "LOCAL_INDEX_DB", db_dir / "local_index.sqlite")
    monkeypatch.setattr(data_layout, "ONLINE_INDEX_DB", db_dir / "online_session_index.sqlite")

    moved = data_layout.migrate_legacy_database_layout()

    assert moved == [(legacy_db, db_dir / "local_index.sqlite")]
    assert not legacy_db.exists()
    assert not legacy_wal.exists()
    assert not legacy_shm.exists()
    assert (db_dir / "local_index.sqlite").exists()
    assert (db_dir / "local_index.sqlite-wal").exists()
    assert (db_dir / "local_index.sqlite-shm").exists()
