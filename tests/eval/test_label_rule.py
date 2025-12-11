from __future__ import annotations

import pytest

from pr_review_agent.findings import FileLocation, Finding, Severity
from tests.eval.benchmark import LabelRule


def _f(severity: Severity = Severity.HIGH, path: str = "src/x.py", title: str = "t") -> Finding:
    return Finding(
        severity=severity,
        location=FileLocation(path=path, line=1),
        agent="security",
        title=title,
        explanation="e",
    )


def test_rule_must_have_at_least_one_filter() -> None:
    with pytest.raises(ValueError, match="needs at least one filter"):
        LabelRule()


def test_severity_floor_alone_is_a_valid_filter() -> None:
    rule = LabelRule(severity_min=Severity.MEDIUM)
    assert rule.matches(_f(severity=Severity.HIGH))
    assert not rule.matches(_f(severity=Severity.LOW))


def test_file_pattern_substring_match() -> None:
    rule = LabelRule(file_pattern="auth", severity_min=Severity.LOW)
    assert rule.matches(_f(path="src/auth/login.py"))
    assert not rule.matches(_f(path="src/api/users.py"))


def test_keyword_match_is_case_insensitive() -> None:
    rule = LabelRule(title_keywords=("Pickle",), severity_min=Severity.LOW)
    assert rule.matches(_f(title="pickle.loads on input"))
    assert not rule.matches(_f(title="json deserialization"))
