from __future__ import annotations

from pathlib import Path

import pytest

from pr_review_agent.tools.filesystem import PathTraversalError, safe_read_text


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text("hello\n", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("OUTSIDE\n", encoding="utf-8")
    return tmp_path / "src"


def test_reads_file_within_root(repo: Path) -> None:
    assert safe_read_text(repo, "ok.py") == "hello\n"


def test_blocks_dotdot_escape(repo: Path) -> None:
    with pytest.raises(PathTraversalError):
        safe_read_text(repo, "../outside.txt")


def test_blocks_absolute_path(repo: Path) -> None:
    with pytest.raises(PathTraversalError):
        safe_read_text(repo, str(Path("/etc/passwd")))


def test_blocks_windows_absolute_path(repo: Path) -> None:
    with pytest.raises(PathTraversalError):
        safe_read_text(repo, "C:\\Windows\\System32\\drivers\\etc\\hosts")


def test_blocks_complex_traversal(repo: Path) -> None:
    with pytest.raises(PathTraversalError):
        safe_read_text(repo, "subdir/../../outside.txt")


def test_raises_on_missing_file(repo: Path) -> None:
    with pytest.raises(FileNotFoundError):
        safe_read_text(repo, "missing.py")


def test_raises_on_directory(repo: Path, tmp_path: Path) -> None:
    (tmp_path / "src" / "subdir").mkdir()
    with pytest.raises(IsADirectoryError):
        safe_read_text(repo, "subdir")


def test_root_as_string_works(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("ok", encoding="utf-8")
    assert safe_read_text(str(tmp_path), "x.txt") == "ok"
