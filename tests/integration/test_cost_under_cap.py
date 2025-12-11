"""§12 cost/latency gate.

A 500-line synthetic PR fanned out across all four specialists must come in
under $0.50 and 90 seconds end-to-end, parametrized over the three providers
the project supports (OpenAI, Anthropic, Ollama / OpenAI-compatible).

Provider semantics are simulated via stub LLMs that return realistic token
counts and per-call latencies. The cost arithmetic uses the project's real
pricing table (`pr_review_agent.models.pricing`) — only the LLM call itself
is faked.

Latency is the part most easily faked, so the simulated per-call latency
is set high enough that a serial pipeline would blow the cap. Four agents
at SIMULATED_LATENCY_S each, run serially, would take ~4× that. Run in
parallel, total wall-clock should stay close to one call's worth — the
cap test is what proves fan-out actually fans out.
"""

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

COST_CAP_USD = 0.50
LATENCY_CAP_S = 90.0
LINES = 500
INPUT_TOKENS_PER_LINE = 6
OUTPUT_TOKENS_FIXED = 250

# Simulated per-call delay. Big enough that a serial pipeline (4 agents
# × SIMULATED_LATENCY_S = 4s) would breach the parallel-only cap below;
# small enough that the test is still fast.
SIMULATED_LATENCY_S = 1.0
# Tighter than LATENCY_CAP_S so this test actually proves parallel fan-out
# bounds wall-clock to ~one call's worth, not four.
PARALLEL_WALL_CLOCK_CAP_S = 2.5


def _synthetic_diff(lines: int = LINES) -> str:
    # Body intentionally hits supervisor hints so all four specialists run —
    # otherwise the cap test only exercises the always-on pair (quality + tests)
    # and parallel-fan-out evidence becomes weak. See agents/supervisor.py.
    body_lines = [f"+    line_{i} = {i}" for i in range(lines - 4)]
    body_lines.extend(
        [
            "+    api_key = config['SECRET_KEY']     # triggers security",
            "+    for row in db.query.all():          # triggers performance",
            "+        cache.set(row.id, row.value)",
            "+    await session.commit()",
        ]
    )
    body = "\n".join(body_lines)
    return (
        "diff --git a/src/api/feature.py b/src/api/feature.py\n"
        "--- a/src/api/feature.py\n"
        "+++ b/src/api/feature.py\n"
        f"@@ -1,1 +1,{lines + 1} @@\n"
        " existing\n"
        f"{body}\n"
    )


def _stub_llm(
    *,
    input_tokens: int,
    output_tokens: int = OUTPUT_TOKENS_FIXED,
    latency_s: float = SIMULATED_LATENCY_S,
) -> Any:
    class _StubLLM:
        async def ainvoke(self, messages: object, **_: object) -> AIMessage:
            await asyncio.sleep(latency_s)
            return AIMessage(
                content='{"findings": []}',
                usage_metadata={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
            )

    return _StubLLM()


def _build_agents(model_id: str, input_tokens: int) -> dict[str, Any]:
    llm = _stub_llm(input_tokens=input_tokens)
    return {
        "quality": build_quality_agent(llm, model_id),
        "tests": build_tests_agent(llm, model_id),
        "performance": build_performance_agent(llm, model_id),
        "security": build_security_agent(llm, model_id),
    }


@pytest.mark.parametrize(
    "provider, model_id",
    [
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-haiku-4"),
        ("ollama", "ollama-local"),
    ],
)
async def test_500_line_pr_under_cost_and_latency_cap(
    provider: str, model_id: str
) -> None:
    diff = _synthetic_diff()
    agents = _build_agents(model_id, input_tokens=LINES * INPUT_TOKENS_PER_LINE)
    graph = build_graph(agents)
    pr = PRMetadata(
        owner="bench",
        repo="cost-cap",
        number=1,
        title="500-line synthetic change",
        head_sha="0" * 40,
        base_sha="1" * 40,
    )
    state: ReviewState = {
        "pr_metadata": pr,
        "diff": diff,
        "files_changed": [],
    }

    start = time.perf_counter()
    out = await graph.ainvoke(state)
    elapsed = time.perf_counter() - start

    cost = out.get("cost_usd", 0.0)
    selected = out.get("selected_agents", [])
    n_agents = len(selected)

    assert selected, f"{provider}: supervisor selected no agents"
    assert cost < COST_CAP_USD, (
        f"{provider}/{model_id}: 500-line PR cost ${cost:.4f} >= ${COST_CAP_USD:.2f}"
    )

    # Hard cap from §12 — never breach this regardless of pipeline shape.
    assert elapsed < LATENCY_CAP_S, (
        f"{provider}/{model_id}: wall-clock {elapsed:.2f}s >= {LATENCY_CAP_S}s"
    )

    # Tight cap proving parallel fan-out: a serial pipeline of n_agents calls
    # at SIMULATED_LATENCY_S each would take n_agents * SIMULATED_LATENCY_S,
    # which exceeds PARALLEL_WALL_CLOCK_CAP_S. Pass = fan-out is real.
    serial_estimate = n_agents * SIMULATED_LATENCY_S
    assert elapsed < PARALLEL_WALL_CLOCK_CAP_S < serial_estimate, (
        f"{provider}/{model_id}: wall-clock {elapsed:.2f}s suggests serial execution; "
        f"{n_agents} agents at {SIMULATED_LATENCY_S}s each would take {serial_estimate:.1f}s "
        f"serially, parallel cap is {PARALLEL_WALL_CLOCK_CAP_S}s"
    )
