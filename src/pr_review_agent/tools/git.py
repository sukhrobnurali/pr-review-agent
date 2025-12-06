from __future__ import annotations

import re
from collections.abc import Iterable

from pr_review_agent.state import FileChange, Hunk

_DIFF_GIT = re.compile(r"^diff --git a/(?P<old>.+?) b/(?P<new>.+?)$")
_HUNK = re.compile(
    r"^@@ -(?P<o_start>\d+)(?:,(?P<o_len>\d+))? \+(?P<n_start>\d+)(?:,(?P<n_len>\d+))? @@"
)
_RENAME_FROM = re.compile(r"^rename from (?P<path>.+)$")
_RENAME_TO = re.compile(r"^rename to (?P<path>.+)$")
_NEW_FILE = re.compile(r"^new file mode")
_DELETED = re.compile(r"^deleted file mode")


def parse_diff(diff_text: str) -> list[FileChange]:
    if not diff_text.strip():
        return []

    changes: list[FileChange] = []
    for block in _split_into_file_blocks(diff_text):
        change = _parse_file_block(block)
        if change is not None:
            changes.append(change)
    return changes


def _split_into_file_blocks(diff_text: str) -> Iterable[list[str]]:
    block: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            if block:
                yield block
            block = [line]
        elif block:
            block.append(line)
    if block:
        yield block


def _parse_file_block(lines: list[str]) -> FileChange | None:
    header = _DIFF_GIT.match(lines[0])
    if not header:
        return None
    old_path = header.group("old")
    new_path = header.group("new")
    status = "modified"
    body_lines: list[str] = []
    for line in lines[1:]:
        if _NEW_FILE.match(line):
            status = "added"
        elif _DELETED.match(line):
            status = "deleted"
        elif _RENAME_FROM.match(line):
            status = "renamed"
        elif _RENAME_TO.match(line):
            pass
        else:
            body_lines.append(line)

    hunks = tuple(_parse_hunks(body_lines))
    return FileChange(
        path=new_path,
        old_path=old_path if old_path != new_path else None,
        status=status,
        hunks=hunks,
    )


def _parse_hunks(lines: list[str]) -> Iterable[Hunk]:
    current_header: re.Match[str] | None = None
    current_body: list[str] = []
    for line in lines:
        match = _HUNK.match(line)
        if match:
            if current_header is not None:
                yield _build_hunk(current_header, current_body)
            current_header = match
            current_body = [line]
        elif current_header is not None:
            current_body.append(line)
    if current_header is not None:
        yield _build_hunk(current_header, current_body)


def _build_hunk(header: re.Match[str], body: list[str]) -> Hunk:
    o_start = int(header.group("o_start"))
    o_len = int(header.group("o_len") or 1)
    n_start = int(header.group("n_start"))
    n_len = int(header.group("n_len") or 1)
    return Hunk(
        old_start=max(o_start, 0),
        old_end=o_start + max(o_len - 1, 0),
        new_start=max(n_start, 1),
        new_end=max(n_start + max(n_len - 1, 0), 1),
        body="\n".join(body),
    )
