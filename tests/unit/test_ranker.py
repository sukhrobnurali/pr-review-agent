from __future__ import annotations

from pr_review_agent.findings import FileLocation, Finding, Severity
from pr_review_agent.findings.ranker import rank


def _make(
    path: str = "x.py",
    line: int = 1,
    severity: Severity = Severity.MEDIUM,
    title: str = "t",
) -> Finding:
    return Finding(
        severity=severity,
        location=FileLocation(path=path, line=line),
        agent="quality",
        title=title,
        explanation="e",
    )


def test_empty() -> None:
    assert rank([]) == []


def test_severity_descending() -> None:
    findings = [
        _make(severity=Severity.LOW),
        _make(severity=Severity.CRITICAL),
        _make(severity=Severity.MEDIUM),
        _make(severity=Severity.HIGH),
        _make(severity=Severity.INFO),
    ]
    out = rank(findings)
    assert [f.severity for f in out] == [
        Severity.CRITICAL,
        Severity.HIGH,
        Severity.MEDIUM,
        Severity.LOW,
        Severity.INFO,
    ]


def test_path_then_line_within_severity() -> None:
    findings = [
        _make(path="b.py", line=1, severity=Severity.HIGH),
        _make(path="a.py", line=10, severity=Severity.HIGH),
        _make(path="a.py", line=5, severity=Severity.HIGH),
    ]
    out = rank(findings)
    assert [(f.location.path, f.location.line) for f in out] == [
        ("a.py", 5),
        ("a.py", 10),
        ("b.py", 1),
    ]


def test_stable_within_same_key() -> None:
    a = _make(path="x.py", line=1, title="first")
    b = _make(path="x.py", line=1, title="second")
    out = rank([a, b])
    assert out[0].title == "first"
    assert out[1].title == "second"


def test_does_not_mutate_input() -> None:
    findings = [
        _make(severity=Severity.LOW),
        _make(severity=Severity.CRITICAL),
    ]
    original = list(findings)
    rank(findings)
    assert findings == original
