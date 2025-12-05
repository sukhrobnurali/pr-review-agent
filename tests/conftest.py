from __future__ import annotations

import pytest

from pr_review_agent.findings import FileLocation, Finding, Severity


@pytest.fixture
def sample_finding() -> Finding:
    return Finding(
        severity=Severity.HIGH,
        location=FileLocation(path="src/auth.py", line=42),
        agent="security",
        title="hardcoded api key",
        explanation="API key is hardcoded in source. Move to env var.",
        suggestion="api_key = os.environ['API_KEY']",
    )


@pytest.fixture
def sample_findings() -> list[Finding]:
    return [
        Finding(
            severity=Severity.CRITICAL,
            location=FileLocation(path="src/db.py", line=12),
            agent="security",
            title="sql injection",
            explanation="raw string interpolation in query",
            suggestion="use parameterized query",
        ),
        Finding(
            severity=Severity.HIGH,
            location=FileLocation(path="src/api.py", line=88),
            agent="performance",
            title="n+1 query",
            explanation="loop fetches per row",
        ),
        Finding(
            severity=Severity.MEDIUM,
            location=FileLocation(path="src/utils.py", line=5),
            agent="quality",
            title="unused import",
            explanation="json imported but never used",
        ),
        Finding(
            severity=Severity.LOW,
            location=FileLocation(path="tests/test_api.py", line=200),
            agent="tests",
            title="missing edge case",
            explanation="no test for empty input",
        ),
    ]
