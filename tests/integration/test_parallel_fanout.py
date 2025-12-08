from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from pr_review_agent.agents.performance import build_performance_agent
from pr_review_agent.agents.quality import build_quality_agent
from pr_review_agent.agents.security import build_security_agent
from pr_review_agent.agents.tests import build_tests_agent
from pr_review_agent.graph import build_graph
from pr_review_agent.state import PRMetadata, ReviewState

_PER_AGENT_LATENCY_S = 0.1
_NUM_AGENTS = 4


def _slow_llm(latency_s: float = _PER_AGENT_LATENCY_S) -> Any:
    class _SlowLLM:
        async def ainvoke(self, messages: object, **_: object) -> AIMessage:
            await asyncio.sleep(latency_s)
            return AIMessage(
                content='{"findings": []}',
                usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
            )

    return _SlowLLM()


@pytest.fixture
def pr_metadata() -> PRMetadata:
    return PRMetadata(
        owner="acme",
        repo="demo",
        number=1,
        title="Touch auth and db",
        head_sha="a" * 40,
        base_sha="b" * 40,
    )


async def test_four_agents_run_concurrently(pr_metadata: PRMetadata) -> None:
    agents = {
        "quality": build_quality_agent(_slow_llm(), "gpt-4o-mini"),
        "tests": build_tests_agent(_slow_llm(), "gpt-4o-mini"),
        "performance": build_performance_agent(_slow_llm(), "gpt-4o-mini"),
        "security": build_security_agent(_slow_llm(), "gpt-4o-mini"),
    }
    graph = build_graph(agents)
    initial: ReviewState = {
        "pr_metadata": pr_metadata,
        "diff": "diff --git a/src/auth/db.py b/src/auth/db.py\n+for u in users:\n+    query(u)\n",
        "files_changed": [],
    }
    sequential_estimate = _PER_AGENT_LATENCY_S * _NUM_AGENTS
    parallel_estimate = _PER_AGENT_LATENCY_S
    midpoint = (sequential_estimate + parallel_estimate) / 2

    start = time.perf_counter()
    out = await graph.ainvoke(initial)
    elapsed = time.perf_counter() - start

    assert len(out["selected_agents"]) == _NUM_AGENTS
    assert elapsed < midpoint, (
        f"wall-clock {elapsed:.3f}s suggests sequential execution; "
        f"expected closer to {parallel_estimate}s, got past midpoint {midpoint}s"
    )
