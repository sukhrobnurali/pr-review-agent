from __future__ import annotations

from pr_review_agent.findings import FileLocation, Finding, Severity
from pr_review_agent.state import add_floats, merge_findings


def _f(agent: str, title: str = "t") -> Finding:
    return Finding(
        severity=Severity.LOW,
        location=FileLocation(path="x.py", line=1),
        agent=agent,  # type: ignore[arg-type]
        title=title,
        explanation="e",
    )


def test_merge_findings_combines_keys() -> None:
    left = {"quality": [_f("quality")]}
    right = {"tests": [_f("tests")]}
    out = merge_findings(left, right)
    assert set(out.keys()) == {"quality", "tests"}


def test_merge_findings_right_overwrites_same_key() -> None:
    left = {"quality": [_f("quality", title="a")]}
    right = {"quality": [_f("quality", title="b")]}
    out = merge_findings(left, right)
    assert len(out["quality"]) == 1
    assert out["quality"][0].title == "b"


def test_merge_findings_handles_none() -> None:
    assert merge_findings(None, {"quality": [_f("quality")]}) == {"quality": [_f("quality")]}
    assert merge_findings({"quality": []}, None) == {"quality": []}
    assert merge_findings(None, None) == {}


def test_add_floats() -> None:
    assert add_floats(0.5, 0.25) == 0.75
    assert add_floats(None, 0.1) == 0.1
    assert add_floats(0.1, None) == 0.1
    assert add_floats(None, None) == 0.0
