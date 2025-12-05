from __future__ import annotations

import re

from pr_review_agent.findings import FileLocation, Finding, Severity
from pr_review_agent.findings.composer import REVIEW_MARKER, compose_markdown


def test_empty_findings_short_circuits() -> None:
    out = compose_markdown([], cost_usd=0.0)
    assert "No issues found." in out
    assert REVIEW_MARKER in out


def test_review_marker_always_present(sample_findings: list[Finding]) -> None:
    out = compose_markdown(sample_findings, cost_usd=0.05)
    assert out.startswith(REVIEW_MARKER)


def test_cost_footer_format() -> None:
    out = compose_markdown([], cost_usd=0.0234)
    assert re.search(r"\$0\.0234", out)


def test_tldr_only_critical_and_high(sample_findings: list[Finding]) -> None:
    out = compose_markdown(sample_findings, cost_usd=0.01)
    tldr_section = out.split("### TL;DR")[1].split("###")[0]
    assert "sql injection" in tldr_section
    assert "n+1 query" in tldr_section
    assert "unused import" not in tldr_section
    assert "missing edge case" not in tldr_section


def test_groups_by_severity(sample_findings: list[Finding]) -> None:
    out = compose_markdown(sample_findings, cost_usd=0.01)
    assert "### Critical" in out
    assert "### High" in out
    assert "### Medium" in out
    assert "### Low" in out
    crit_pos = out.index("### Critical")
    high_pos = out.index("### High")
    med_pos = out.index("### Medium")
    low_pos = out.index("### Low")
    assert crit_pos < high_pos < med_pos < low_pos


def test_severity_section_omitted_when_empty() -> None:
    findings = [
        Finding(
            severity=Severity.LOW,
            location=FileLocation(path="x.py", line=1),
            agent="quality",
            title="t",
            explanation="e",
        )
    ]
    out = compose_markdown(findings)
    assert "### Critical" not in out
    assert "### Low" in out


def test_finding_includes_file_line(sample_findings: list[Finding]) -> None:
    out = compose_markdown(sample_findings)
    assert "`src/db.py:12`" in out
    assert "`src/api.py:88`" in out


def test_suggestion_rendered_in_code_block() -> None:
    findings = [
        Finding(
            severity=Severity.HIGH,
            location=FileLocation(path="a.py", line=10),
            agent="security",
            title="hardcoded secret",
            explanation="api key in source",
            suggestion="key = os.environ['KEY']",
        )
    ]
    out = compose_markdown(findings)
    assert "key = os.environ['KEY']" in out
    assert "Suggested fix:" in out


def test_no_suggestion_no_section() -> None:
    findings = [
        Finding(
            severity=Severity.LOW,
            location=FileLocation(path="x.py", line=1),
            agent="quality",
            title="t",
            explanation="e",
        )
    ]
    out = compose_markdown(findings)
    assert "Suggested fix:" not in out


def test_count_pluralization() -> None:
    one = [
        Finding(
            severity=Severity.LOW,
            location=FileLocation(path="x.py", line=1),
            agent="quality",
            title="t",
            explanation="e",
        )
    ]
    out_one = compose_markdown(one)
    assert "1 finding " in out_one
    assert "1 findings" not in out_one


def test_no_high_or_critical_no_tldr() -> None:
    findings = [
        Finding(
            severity=Severity.LOW,
            location=FileLocation(path="x.py", line=1),
            agent="quality",
            title="t",
            explanation="e",
        )
    ]
    out = compose_markdown(findings)
    assert "### TL;DR" not in out
    assert "nothing critical or high" in out


def test_line_range_rendered() -> None:
    findings = [
        Finding(
            severity=Severity.HIGH,
            location=FileLocation(path="a.py", line=10, end_line=20),
            agent="performance",
            title="big function",
            explanation="too long",
        )
    ]
    out = compose_markdown(findings)
    assert "`a.py:10-20`" in out
