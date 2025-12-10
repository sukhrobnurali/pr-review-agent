from __future__ import annotations

from pathlib import Path

import pytest

from pr_review_agent.agents.base import AgentResult
from pr_review_agent.cache import FileCache, cache_key
from pr_review_agent.findings import FileLocation, Finding, Severity


def _result(cost: float = 0.01) -> AgentResult:
    return AgentResult(
        findings=[
            Finding(
                severity=Severity.HIGH,
                location=FileLocation(path="a.py", line=1),
                agent="security",
                title="t",
                explanation="e",
            )
        ],
        cost_usd=cost,
        prompt_tokens=120,
        completion_tokens=80,
    )


def test_cache_miss_then_hit_round_trip(tmp_path: Path) -> None:
    cache = FileCache(tmp_path)
    key = cache_key(
        repo_id="acme/widgets",
        blob_sha="deadbeef",
        agent="quality",
        model="gpt-4o-mini",
        prompt_version="v1",
    )
    assert cache.get(key) is None

    cache.put(key, _result(cost=0.42))

    hit = cache.get(key)
    assert hit is not None
    assert hit.cost_usd == 0.42
    assert hit.findings[0].title == "t"


def test_key_differs_per_dimension() -> None:
    base = {
        "repo_id": "o/r",
        "blob_sha": "abc",
        "agent": "quality",
        "model": "m",
        "prompt_version": "v1",
    }
    base_key = cache_key(**base)  # type: ignore[arg-type]
    for field, alt in {
        "repo_id": "o/r2",
        "blob_sha": "def",
        "agent": "security",
        "model": "m2",
        "prompt_version": "v2",
    }.items():
        differing = base | {field: alt}
        assert cache_key(**differing) != base_key, field  # type: ignore[arg-type]


def test_corrupt_entry_is_a_miss(tmp_path: Path) -> None:
    cache = FileCache(tmp_path)
    key = "x" * 64
    path = tmp_path / key[:2] / f"{key}.json"
    path.parent.mkdir(parents=True)
    path.write_text("not json", encoding="utf-8")
    assert cache.get(key) is None


def test_clear_removes_all_entries(tmp_path: Path) -> None:
    cache = FileCache(tmp_path)
    cache.put("a" * 64, _result())
    cache.put("b" * 64, _result())
    cache.clear()
    assert cache.get("a" * 64) is None
    assert cache.get("b" * 64) is None


def test_default_cache_dir_respects_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PR_REVIEW_CACHE_DIR", str(tmp_path / "custom"))
    from pr_review_agent.cache.filecache import default_cache_dir

    assert default_cache_dir() == tmp_path / "custom"
