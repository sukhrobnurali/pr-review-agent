from __future__ import annotations

from pathlib import Path


class PathTraversalError(ValueError):
    pass


def safe_read_text(repo_root: Path | str, relative_path: str) -> str:
    """Read a text file under `repo_root`, rejecting paths that escape it.

    Rejects:
    - Absolute paths (`/etc/passwd`, `C:\\Windows\\...`)
    - Paths containing `..` segments after resolution that escape repo_root
    - Symlinks pointing outside repo_root
    - Anything that isn't a regular file
    """
    root = Path(repo_root).resolve(strict=False)
    rel = Path(relative_path)
    if rel.is_absolute():
        raise PathTraversalError(f"absolute paths rejected: {relative_path}")

    candidate = (root / rel).resolve(strict=False)
    if not _is_within(candidate, root):
        raise PathTraversalError(f"path escapes repo root: {relative_path}")
    if not candidate.exists():
        raise FileNotFoundError(f"not found: {relative_path}")
    if not candidate.is_file():
        raise IsADirectoryError(f"not a regular file: {relative_path}")
    return candidate.read_text(encoding="utf-8")


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True
