from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from pr_review_agent.agents.quality import build_quality_agent
from pr_review_agent.findings import Severity
from pr_review_agent.state import PRMetadata


@pytest.fixture
def sample_pr() -> PRMetadata:
    return PRMetadata(
        owner="acme",
        repo="demo",
        number=1,
        title="Add user dashboard widget",
        head_sha="a" * 40,
        base_sha="b" * 40,
        author="octocat",
    )


@pytest.fixture
def sample_diff() -> str:
    return """diff --git a/src/dashboard.py b/src/dashboard.py
--- a/src/dashboard.py
+++ b/src/dashboard.py
@@ -1,5 +1,30 @@
+import json
+import os, sys, time, datetime  # noqa: F401
+
+def d(u, t, ctx=None, x=None, y=None, z=None):
+    if u is None:
+        if t is None:
+            if ctx is None:
+                return None
+            else:
+                return ctx
+        else:
+            return t
+    else:
+        return u
+
+UNUSED_CONST = 42
+
+def render():
+    pass
+
 class Dashboard:
     pass
"""


def _fake_llm_with_content(content: str, usage: dict[str, int] | None = None) -> Any:
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(
        return_value=AIMessage(
            content=content,
            usage_metadata={
                "input_tokens": usage["input_tokens"] if usage else 800,
                "output_tokens": usage["output_tokens"] if usage else 220,
                "total_tokens": (usage["input_tokens"] + usage["output_tokens"]) if usage else 1020,
            },
        )
    )
    return llm


async def test_quality_agent_parses_findings(sample_pr: PRMetadata, sample_diff: str) -> None:
    response = """```json
{"findings": [
  {
    "severity": "high",
    "file": "src/dashboard.py",
    "line": 4,
    "title": "single-letter parameter names",
    "explanation": "Function `d` takes `u`, `t`, `ctx`, `x`, `y`, `z` \\u2014 the names give no indication of meaning.",
    "suggestion": "Rename `d`, `u`, `t` to descriptive names; remove unused `x`, `y`, `z`."
  },
  {
    "severity": "medium",
    "file": "src/dashboard.py",
    "line": 14,
    "title": "deeply nested conditional",
    "explanation": "Five levels of nesting where a flat early-return would read better.",
    "suggestion": null
  }
]}
```"""
    llm = _fake_llm_with_content(response)
    agent = build_quality_agent(llm, "gpt-4o-mini")
    result = await agent.run(pr=sample_pr, files_changed=[], diff=sample_diff)
    assert len(result.findings) == 2
    assert all(f.agent == "quality" for f in result.findings)
    assert result.findings[0].severity is Severity.HIGH
    assert result.cost_usd > 0
    assert result.prompt_tokens == 800
    assert result.completion_tokens == 220


async def test_quality_agent_clean_diff_returns_empty(
    sample_pr: PRMetadata, sample_diff: str
) -> None:
    llm = _fake_llm_with_content('{"findings": []}')
    agent = build_quality_agent(llm, "gpt-4o-mini")
    result = await agent.run(pr=sample_pr, files_changed=[], diff=sample_diff)
    assert result.findings == []
    assert result.cost_usd > 0


async def test_quality_agent_handles_garbage_response(
    sample_pr: PRMetadata, sample_diff: str
) -> None:
    llm = _fake_llm_with_content("Sure, here's my analysis: it looks fine.")
    agent = build_quality_agent(llm, "gpt-4o-mini")
    result = await agent.run(pr=sample_pr, files_changed=[], diff=sample_diff)
    assert result.findings == []


async def test_quality_agent_renders_prompt_with_pr_context(
    sample_pr: PRMetadata, sample_diff: str
) -> None:
    llm = _fake_llm_with_content('{"findings": []}')
    agent = build_quality_agent(llm, "gpt-4o-mini")
    await agent.run(pr=sample_pr, files_changed=[], diff=sample_diff)
    prompt_arg = llm.ainvoke.await_args.args[0][0].content
    assert "Add user dashboard widget" in prompt_arg
    assert "octocat" in prompt_arg
    assert "src/dashboard.py" in prompt_arg
