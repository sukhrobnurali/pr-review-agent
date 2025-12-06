from __future__ import annotations

from pr_review_agent.agents.base import parse_findings_from_text
from pr_review_agent.findings import Severity


def test_parse_fenced_json() -> None:
    content = """Some preamble.

```json
{"findings": [
  {"severity": "high", "file": "src/x.py", "line": 10, "title": "issue", "explanation": "bad"}
]}
```

Trailing text."""
    out = parse_findings_from_text(content, "quality")
    assert len(out) == 1
    assert out[0].agent == "quality"
    assert out[0].severity is Severity.HIGH


def test_parse_bare_json() -> None:
    content = '{"findings": [{"severity": "low", "file": "a.py", "line": 1, "title": "t", "explanation": "e"}]}'
    out = parse_findings_from_text(content, "tests")
    assert len(out) == 1
    assert out[0].agent == "tests"


def test_parse_invalid_json_returns_empty() -> None:
    assert parse_findings_from_text("not json at all", "security") == []
    assert parse_findings_from_text("```\n{not json}\n```", "security") == []


def test_parse_no_findings_key() -> None:
    out = parse_findings_from_text('{"other": []}', "performance")
    assert out == []


def test_parse_skips_invalid_entries() -> None:
    content = """```json
{"findings": [
  {"severity": "high", "file": "x.py", "line": 10, "title": "ok", "explanation": "ok"},
  {"severity": "high", "file": "x.py", "line": 0, "title": "bad-line", "explanation": "x"},
  {"severity": "INVALID", "file": "x.py", "line": 1, "title": "bad-sev", "explanation": "x"}
]}
```"""
    out = parse_findings_from_text(content, "quality")
    assert len(out) == 1
    assert out[0].title == "ok"


def test_parse_with_end_line() -> None:
    content = '{"findings":[{"severity":"medium","file":"x.py","line":10,"end_line":20,"title":"t","explanation":"e"}]}'
    out = parse_findings_from_text(content, "performance")
    assert out[0].location.end_line == 20


def test_parse_with_suggestion() -> None:
    content = '{"findings":[{"severity":"low","file":"x.py","line":1,"title":"t","explanation":"e","suggestion":"do this"}]}'
    out = parse_findings_from_text(content, "quality")
    assert out[0].suggestion == "do this"


def test_parse_empty_findings() -> None:
    out = parse_findings_from_text('{"findings": []}', "quality")
    assert out == []
