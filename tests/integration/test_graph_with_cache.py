"""End-to-end cache check through the production graph.

The unit tests in `test_caching_agent.py` confirm the wrapper itself
caches correctly. This test confirms the wiring: a `CachingAgent` slotted
into `build_graph` actually short-circuits the LLM call on the second run
of an identical PR (same head SHA), and that `cost_usd` drops to 0.0
when every selected agent reports a cache hit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from pr_review_agent.agents.performance import build_performance_agent
from pr_review_agent.agents.quality import build_quality_agent
from pr_review_agent.agents.security import build_security_agent
from pr_review_agent.agents.tests import build_tests_agent
from pr_review_agent.cache import CachingAgent, FileCache
from pr_review_agent.findings import AgentName
from pr_review_agent.graph import build_graph
from pr_review_agent.state import PRMetadata, ReviewState


class _CountingLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, messages: object, **_: object) -> AIMessage:
        self.calls += 1
        return AIMessage(
            content='{"findings": []}',
            usage_metadata={"input_tokens": 50, "output_tokens": 10, "total_tokens": 60},
        )


def _wrap_agents(llm: Any, cache: FileCache) -> dict[AgentName, CachingAgent]:
    inner = {
        "quality": build_quality_agent(llm, "gpt-4o-mini"),
        "tests": build_tests_agent(llm, "gpt-4o-mini"),
        "performance": build_performance_agent(llm, "gpt-4o-mini"),
        "security": build_security_agent(llm, "gpt-4o-mini"),
    }
    return {name: CachingAgent(agent, cache) for name, agent in inner.items()}


def _state() -> ReviewState:
    pr = PRMetadata(
        owner="acme",
        repo="widgets",
        number=99,
        title="touch auth.py and db.py",
        head_sha="cafef00d" + "0" * 32,
        base_sha="0" * 40,
    )
    diff = (
        "diff --git a/src/auth/login.py b/src/auth/login.py\n"
        "--- a/src/auth/login.py\n"
        "+++ b/src/auth/login.py\n"
        "@@ -1,1 +1,2 @@\n"
        " a\n"
        "+password = config['SECRET']\n"
    )
    return {
        "pr_metadata": pr,
        "diff": diff,
        "files_changed": [],
    }


@pytest.mark.asyncio
async def test_second_run_against_same_head_sha_hits_cache(tmp_path: Path) -> None:
    cache = FileCache(tmp_path)
    llm = _CountingLLM()
    graph = build_graph(_wrap_agents(llm, cache))  # type: ignore[arg-type]

    out_first = await graph.ainvoke(_state())
    selected = list(out_first["selected_agents"])
    assert selected, "supervisor should select at least quality + tests"
    first_call_count = llm.calls
    assert first_call_count == len(selected), (
        f"first run should call LLM once per selected agent; "
        f"got {first_call_count} calls for {selected}"
    )
    assert out_first["cost_usd"] > 0.0

    # Second run, same PR head SHA, same prompts, same models → all hit.
    out_second = await graph.ainvoke(_state())
    assert llm.calls == first_call_count, (
        f"second run should not call LLM at all; "
        f"call count went from {first_call_count} → {llm.calls}"
    )
    assert out_second["cost_usd"] == 0.0


@pytest.mark.asyncio
async def test_changed_head_sha_misses_cache(tmp_path: Path) -> None:
    cache = FileCache(tmp_path)
    llm = _CountingLLM()
    graph = build_graph(_wrap_agents(llm, cache))  # type: ignore[arg-type]

    state_a = _state()
    await graph.ainvoke(state_a)
    after_first = llm.calls

    state_b = _state()
    state_b["pr_metadata"] = state_a["pr_metadata"].model_copy(
        update={"head_sha": "deadbeef" + "0" * 32}
    )
    await graph.ainvoke(state_b)

    assert llm.calls > after_first, "different head_sha must miss cache"
