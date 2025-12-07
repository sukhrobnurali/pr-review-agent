from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from pr_review_agent.agents.quality import build_quality_agent
from pr_review_agent.agents.tests import build_tests_agent
from pr_review_agent.graph import build_graph
from pr_review_agent.state import PRMetadata, ReviewState


@pytest.fixture
def pr_metadata() -> PRMetadata:
    return PRMetadata(
        owner="acme",
        repo="demo",
        number=42,
        title="Refactor parser",
        head_sha="a" * 40,
        base_sha="b" * 40,
    )


def _llm_with(content: str, in_toks: int = 600, out_toks: int = 200) -> Any:
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(
        return_value=AIMessage(
            content=content,
            usage_metadata={
                "input_tokens": in_toks,
                "output_tokens": out_toks,
                "total_tokens": in_toks + out_toks,
            },
        )
    )
    return llm


async def test_two_agents_run_in_parallel_and_findings_combined(
    pr_metadata: PRMetadata,
) -> None:
    quality_response = """```json
{"findings": [
  {"severity": "medium", "file": "src/parser.py", "line": 12, "title": "deeply nested",
   "explanation": "five levels of nesting"}
]}
```"""
    tests_response = """```json
{"findings": [
  {"severity": "high", "file": "src/parser.py", "line": 12, "title": "no test for new branch",
   "explanation": "new error branch added without test"}
]}
```"""
    quality_llm = _llm_with(quality_response)
    tests_llm = _llm_with(tests_response)
    agents = {
        "quality": build_quality_agent(quality_llm, "gpt-4o-mini"),
        "tests": build_tests_agent(tests_llm, "gpt-4o-mini"),
    }
    graph = build_graph(agents)
    initial: ReviewState = {
        "pr_metadata": pr_metadata,
        "diff": "diff --git a/src/parser.py b/src/parser.py\n@@ -1 +1 @@\n-x\n+y\n",
        "files_changed": [],
    }
    out = await graph.ainvoke(initial)
    assert set(out["findings"].keys()) == {"quality", "tests"}
    assert len(out["aggregated"]) == 2
    severities = {f.severity.value for f in out["aggregated"]}
    assert "high" in severities
    assert "medium" in severities
    assert out["aggregated"][0].severity.value == "high"
    assert out["cost_usd"] > 0


async def test_one_agent_failure_does_not_block_other(
    pr_metadata: PRMetadata,
) -> None:
    quality_response = '{"findings": [{"severity": "low", "file": "x.py", "line": 1, "title": "t", "explanation": "e"}]}'
    quality_llm = _llm_with(quality_response)
    tests_llm = AsyncMock()
    tests_llm.ainvoke = AsyncMock(side_effect=RuntimeError("rate limited"))
    agents = {
        "quality": build_quality_agent(quality_llm, "gpt-4o-mini"),
        "tests": build_tests_agent(tests_llm, "gpt-4o-mini"),
    }
    graph = build_graph(agents)
    initial: ReviewState = {
        "pr_metadata": pr_metadata,
        "diff": "diff --git a/x.py b/x.py\n@@ -1 +1 @@\n-a\n+b\n",
        "files_changed": [],
    }
    out = await graph.ainvoke(initial)
    assert "quality" in out["findings"]
    assert "tests" not in out.get("findings", {})
    assert any(e.agent == "tests" for e in out["errors"])
    assert len(out["aggregated"]) == 1
