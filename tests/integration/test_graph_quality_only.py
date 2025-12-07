from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from pr_review_agent.agents.quality import build_quality_agent
from pr_review_agent.graph import build_graph
from pr_review_agent.state import PRMetadata, ReviewState


@pytest.fixture
def pr_metadata() -> PRMetadata:
    return PRMetadata(
        owner="acme",
        repo="demo",
        number=1,
        title="Add widget",
        head_sha="a" * 40,
        base_sha="b" * 40,
    )


def _llm_with(content: str, in_toks: int = 500, out_toks: int = 100) -> Any:
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


async def test_graph_quality_only_produces_comment(pr_metadata: PRMetadata) -> None:
    response = """```json
{"findings": [
  {"severity": "medium", "file": "x.py", "line": 5, "title": "naming", "explanation": "single-letter var"}
]}
```"""
    llm = _llm_with(response)
    agents = {"quality": build_quality_agent(llm, "gpt-4o-mini")}
    graph = build_graph(agents)
    initial: ReviewState = {
        "pr_metadata": pr_metadata,
        "diff": "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-x = 1\n+y = 2\n",
        "files_changed": [],
    }
    out = await graph.ainvoke(initial)
    assert "selected_agents" in out
    assert "quality" in out["selected_agents"]
    assert out["findings"]["quality"][0].title == "naming"
    assert len(out["aggregated"]) == 1
    assert "naming" in out["final_comment"]
    assert out["cost_usd"] > 0


async def test_graph_handles_agent_failure(pr_metadata: PRMetadata) -> None:
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
    agents = {"quality": build_quality_agent(llm, "gpt-4o-mini")}
    graph = build_graph(agents)
    initial: ReviewState = {
        "pr_metadata": pr_metadata,
        "diff": "diff --git a/x.py b/x.py\n@@ -1 +1 @@\n-a\n+b\n",
        "files_changed": [],
    }
    out = await graph.ainvoke(initial)
    assert "errors" in out
    assert out["errors"][0].agent == "quality"
    assert "unavailable" in out["errors"][0].message.lower()
    assert out["aggregated"] == []
    assert "No issues found" in out["final_comment"]


async def test_graph_skips_unselected_agents(pr_metadata: PRMetadata) -> None:
    quality_llm = _llm_with('{"findings": []}')
    security_llm = _llm_with('{"findings": []}')
    agents = {
        "quality": build_quality_agent(quality_llm, "gpt-4o-mini"),
        "security": build_quality_agent(security_llm, "gpt-4o-mini"),
    }
    graph = build_graph(agents)
    initial: ReviewState = {
        "pr_metadata": pr_metadata,
        "diff": "diff --git a/docs/intro.md b/docs/intro.md\n@@ -1 +1 @@\n-a\n+b\n",
        "files_changed": [],
    }
    out = await graph.ainvoke(initial)
    assert "security" not in out["selected_agents"]
    assert security_llm.ainvoke.await_count == 0
    assert quality_llm.ainvoke.await_count == 1
