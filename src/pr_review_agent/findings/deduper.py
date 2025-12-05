from __future__ import annotations

from collections.abc import Iterable

from pr_review_agent.findings.schema import FileLocation, Finding

_TITLE_OVERLAP_THRESHOLD = 0.5


def deduplicate(findings: Iterable[Finding]) -> list[Finding]:
    items = list(findings)
    if len(items) <= 1:
        return items

    groups: list[list[Finding]] = []
    for f in items:
        bucket = next((g for g in groups if any(_is_duplicate(f, x) for x in g)), None)
        if bucket is None:
            groups.append([f])
        else:
            bucket.append(f)
    return [_representative(g) for g in groups]


def _is_duplicate(a: Finding, b: Finding) -> bool:
    return (
        a.location.path == b.location.path
        and _lines_overlap(a.location, b.location)
        and _title_jaccard(a.title, b.title) >= _TITLE_OVERLAP_THRESHOLD
    )


def _lines_overlap(a: FileLocation, b: FileLocation) -> bool:
    a_end = a.end_line if a.end_line is not None else a.line
    b_end = b.end_line if b.end_line is not None else b.line
    return not (a_end < b.line or b_end < a.line)


def _title_jaccard(a: str, b: str) -> float:
    a_tokens = {t for t in a.lower().split() if t}
    b_tokens = {t for t in b.lower().split() if t}
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def _representative(group: list[Finding]) -> Finding:
    return max(group, key=lambda f: f.severity.rank)
