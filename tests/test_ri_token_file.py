"""Token-file validation must neither use keyrings nor disclose file contents."""

import pytest

from src.config import ri_proton as module

TOKEN = "pst_synthetic::synthetic-key"


@pytest.fixture
def token_file(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    folder = tmp_path / ".env"
    folder.mkdir()
    return folder / "ri_token.txt"


@pytest.mark.parametrize("suffix", ["", "\n", "\r\n"])
@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_token_read_independent_of_cwd_and_accepts_windows_line_ending(token_file, monkeypatch, tmp_path, suffix, encoding):
    token_file.write_bytes((TOKEN + suffix).encode(encoding))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert module.read_token() == TOKEN


@pytest.mark.parametrize("value", ["", "not-a-token", "pst_::key", "pst_id::", "pst_id::one::two", '"' + TOKEN + '"', TOKEN + "\nsecond-line", TOKEN + " ", "pst_id::" + "a" * 16000])
def test_invalid_token_is_not_disclosed(token_file, value):
    token_file.write_text(value, encoding="utf-8")
    with pytest.raises(module.RiAccessError) as error:
        module.read_token()
    assert "ri_token.txt" in str(error.value)
    if value:
        assert value not in str(error.value)


def test_missing_file_has_actionable_error(token_file):
    with pytest.raises(module.RiAccessError, match="Token-Datei fehlt"):
        module.read_token()


def test_unreadable_or_invalid_encoding_has_safe_error(token_file):
    token_file.write_bytes(b"private-secret\xff")
    with pytest.raises(module.RiAccessError) as error:
        module.read_token()
    assert "private-secret" not in str(error.value)
    assert "UTF-8" in str(error.value)


def test_official_windows_install_found_without_path(monkeypatch, tmp_path):
    monkeypatch.setattr(module.sys, "platform", "win32")
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    cli = tmp_path / "Programs/ProtonPass/pass-cli.exe"
    cli.parent.mkdir(parents=True)
    cli.touch()
    assert module.find_cli() == str(cli)
