from __future__ import annotations

from pr_review_agent.findings import FileLocation, Finding, Severity
from pr_review_agent.findings.deduper import deduplicate


def _make(
    path: str = "x.py",
    line: int = 1,
    end_line: int | None = None,
    severity: Severity = Severity.MEDIUM,
    agent: str = "quality",
    title: str = "issue",
) -> Finding:
    return Finding(
        severity=severity,
        location=FileLocation(path=path, line=line, end_line=end_line),
        agent=agent,  # type: ignore[arg-type]
        title=title,
        explanation="x",
    )


def test_empty() -> None:
    assert deduplicate([]) == []


def test_singleton_passthrough() -> None:
    f = _make()
    assert deduplicate([f]) == [f]


def test_merges_same_file_same_line_same_title() -> None:
    a = _make(severity=Severity.MEDIUM, agent="quality", title="hardcoded api key")
    b = _make(severity=Severity.HIGH, agent="security", title="hardcoded api key")
    out = deduplicate([a, b])
    assert len(out) == 1
    assert out[0].severity is Severity.HIGH
    assert out[0].agent == "security"


def test_keeps_distinct_titles_same_line() -> None:
    a = _make(title="hardcoded api key")
    b = _make(title="missing docstring")
    out = deduplicate([a, b])
    assert len(out) == 2


def test_keeps_different_files() -> None:
    a = _make(path="a.py", title="dup")
    b = _make(path="b.py", title="dup")
    out = deduplicate([a, b])
    assert len(out) == 2


def test_overlapping_line_ranges_merged() -> None:
    a = _make(line=10, end_line=20, title="big function")
    b = _make(line=15, title="big function")
    out = deduplicate([a, b])
    assert len(out) == 1


def test_non_overlapping_lines_kept() -> None:
    a = _make(line=10, title="dup")
    b = _make(line=50, title="dup")
    out = deduplicate([a, b])
    assert len(out) == 2


def test_picks_highest_severity_in_group() -> None:
    findings = [
        _make(severity=Severity.LOW, agent="quality", title="sql injection"),
        _make(severity=Severity.CRITICAL, agent="security", title="sql injection"),
        _make(severity=Severity.MEDIUM, agent="performance", title="sql injection"),
    ]
    out = deduplicate(findings)
    assert len(out) == 1
    assert out[0].severity is Severity.CRITICAL
    assert out[0].agent == "security"


def test_partial_token_overlap_below_threshold_kept() -> None:
    a = _make(title="missing test for foo")
    b = _make(title="hardcoded api key")
    out = deduplicate([a, b])
    assert len(out) == 2
