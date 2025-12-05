from __future__ import annotations

from collections.abc import Iterable

from pr_review_agent.findings.schema import Finding


def rank(findings: Iterable[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda f: (-f.severity.rank, f.location.path, f.location.line),
    )
