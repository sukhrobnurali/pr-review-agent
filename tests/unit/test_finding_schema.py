from __future__ import annotations

import pytest
from pydantic import ValidationError

from pr_review_agent.findings import FileLocation, Finding, Severity


class TestSeverity:
    def test_ordering(self) -> None:
        assert Severity.CRITICAL > Severity.HIGH
        assert Severity.HIGH > Severity.MEDIUM
        assert Severity.MEDIUM > Severity.LOW
        assert Severity.LOW > Severity.INFO

    def test_sort(self) -> None:
        ascending = sorted([Severity.HIGH, Severity.LOW, Severity.CRITICAL, Severity.INFO])
        assert ascending == [Severity.INFO, Severity.LOW, Severity.HIGH, Severity.CRITICAL]

    def test_rank(self) -> None:
        assert Severity.CRITICAL.rank == 4
        assert Severity.INFO.rank == 0


class TestFileLocation:
    def test_basic(self) -> None:
        loc = FileLocation(path="a/b.py", line=10)
        assert loc.path == "a/b.py"
        assert loc.line == 10
        assert loc.end_line is None

    def test_line_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            FileLocation(path="a.py", line=0)

    def test_end_line_after_line(self) -> None:
        with pytest.raises(ValidationError):
            FileLocation(path="a.py", line=10, end_line=5)

    def test_end_line_equal_ok(self) -> None:
        loc = FileLocation(path="a.py", line=10, end_line=10)
        assert loc.end_line == 10

    def test_empty_path_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FileLocation(path="", line=1)

    def test_frozen(self) -> None:
        loc = FileLocation(path="a.py", line=1)
        with pytest.raises(ValidationError):
            loc.line = 2  # type: ignore[misc]


class TestFinding:
    def test_minimum_fields(self) -> None:
        f = Finding(
            severity=Severity.LOW,
            location=FileLocation(path="x.py", line=1),
            agent="quality",
            title="t",
            explanation="e",
        )
        assert f.suggestion is None

    def test_missing_required_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Finding(  # type: ignore[call-arg]
                severity=Severity.LOW,
                location=FileLocation(path="x.py", line=1),
                agent="quality",
                title="t",
            )

    def test_invalid_agent_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Finding(
                severity=Severity.LOW,
                location=FileLocation(path="x.py", line=1),
                agent="docs",  # type: ignore[arg-type]
                title="t",
                explanation="e",
            )

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Finding(
                severity=Severity.LOW,
                location=FileLocation(path="x.py", line=1),
                agent="quality",
                title="",
                explanation="e",
            )

    def test_frozen(self, sample_finding: Finding) -> None:
        with pytest.raises(ValidationError):
            sample_finding.title = "new"  # type: ignore[misc]
