from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from pr_review_agent.agents.base import AgentResult, SpecialistAgent
from pr_review_agent.cache import CachingAgent, FileCache
from pr_review_agent.findings import FileLocation, Finding, Severity
from pr_review_agent.state import PRMetadata


def _pr(head: str = "abc123") -> PRMetadata:
    return PRMetadata(
        owner="acme",
        repo="widgets",
        number=7,
        title="t",
        head_sha=head,
        base_sha="0" * 40,
    )


def _result() -> AgentResult:
    return AgentResult(
        findings=[
            Finding(
                severity=Severity.LOW,
                location=FileLocation(path="x.py", line=1),
                agent="quality",
                title="t",
                explanation="e",
            )
        ],
        cost_usd=0.05,
        prompt_tokens=100,
        completion_tokens=50,
    )


def _stub_agent(model_id: str = "gpt-4o-mini") -> SpecialistAgent:
    inner = SpecialistAgent.__new__(SpecialistAgent)
    inner.agent_name = "quality"
    inner.prompt_name = "quality"
    inner.model_id = model_id
    inner.run = AsyncMock(return_value=_result())  # type: ignore[method-assign]
    return inner


@pytest.mark.asyncio
async def test_cache_miss_calls_inner_and_writes(tmp_path: Path) -> None:
    cache = FileCache(tmp_path)
    inner = _stub_agent()
    wrapped = CachingAgent(inner, cache)
    out = await wrapped.run(pr=_pr(), files_changed=[], diff="")
    assert out.cost_usd == 0.05
    inner.run.assert_awaited_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_cache_hit_skips_inner_and_zeroes_cost(tmp_path: Path) -> None:
    cache = FileCache(tmp_path)
    inner = _stub_agent()
    wrapped = CachingAgent(inner, cache)
    pr = _pr()
    await wrapped.run(pr=pr, files_changed=[], diff="")
    inner.run.reset_mock()  # type: ignore[attr-defined]

    out = await wrapped.run(pr=pr, files_changed=[], diff="")
    inner.run.assert_not_awaited()  # type: ignore[attr-defined]
    assert out.cost_usd == 0.0
    assert len(out.findings) == 1


@pytest.mark.asyncio
async def test_different_head_sha_misses_cache(tmp_path: Path) -> None:
    cache = FileCache(tmp_path)
    inner = _stub_agent()
    wrapped = CachingAgent(inner, cache)
    await wrapped.run(pr=_pr(head="aaa"), files_changed=[], diff="")
    await wrapped.run(pr=_pr(head="bbb"), files_changed=[], diff="")
    assert inner.run.await_count == 2  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_different_model_misses_cache(tmp_path: Path) -> None:
    cache = FileCache(tmp_path)
    a = CachingAgent(_stub_agent(model_id="gpt-4o-mini"), cache)
    b = CachingAgent(_stub_agent(model_id="gpt-4o"), cache)
    pr = _pr()
    await a.run(pr=pr, files_changed=[], diff="")
    await b.run(pr=pr, files_changed=[], diff="")
    a._inner.run.assert_awaited_once()  # type: ignore[attr-defined]
    b._inner.run.assert_awaited_once()  # type: ignore[attr-defined]
