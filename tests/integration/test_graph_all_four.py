from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from pr_review_agent.agents.performance import build_performance_agent
from pr_review_agent.agents.quality import build_quality_agent
from pr_review_agent.agents.security import build_security_agent
from pr_review_agent.agents.tests import build_tests_agent
from pr_review_agent.graph import build_graph
from pr_review_agent.state import PRMetadata, ReviewState


@pytest.fixture
def pr_metadata() -> PRMetadata:
    return PRMetadata(
        owner="acme",
        repo="demo",
        number=99,
        title="Add login with raw SQL",
        head_sha="a" * 40,
        base_sha="b" * 40,
    )


def _llm_with(content: str) -> Any:
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(
        return_value=AIMessage(
            content=content,
            usage_metadata={"input_tokens": 700, "output_tokens": 250, "total_tokens": 950},
        )
    )
    return llm


_DIFF_AUTH_SQL = """diff --git a/src/auth/login.py b/src/auth/login.py
--- a/src/auth/login.py
+++ b/src/auth/login.py
@@ -10,5 +10,12 @@
 def authenticate(username: str, password: str):
-    user = User.get(username=username)
+    query = f"SELECT * FROM users WHERE username='{username}'"
+    user = db.execute(query).first()
+    for u in extra_users:
+        if u.name == username:
+            user = u
+    if password == user.password:
+        return user
+    return None
"""


async def test_all_four_agents_fan_out_through_graph(pr_metadata: PRMetadata) -> None:
    quality_resp = '{"findings":[{"severity":"medium","file":"src/auth/login.py","line":12,"title":"f-string in query","explanation":"q"}]}'
    tests_resp = '{"findings":[{"severity":"high","file":"src/auth/login.py","line":11,"title":"no test for auth","explanation":"e"}]}'
    perf_resp = '{"findings":[{"severity":"medium","file":"src/auth/login.py","line":14,"title":"linear scan over extra_users","explanation":"e"}]}'
    sec_resp = '{"findings":[{"severity":"critical","file":"src/auth/login.py","line":12,"title":"sql injection in login","explanation":"unparameterized query"},{"severity":"high","file":"src/auth/login.py","line":17,"title":"plaintext password compare","explanation":"e"}]}'

    agents = {
        "quality": build_quality_agent(_llm_with(quality_resp), "gpt-4o-mini"),
        "tests": build_tests_agent(_llm_with(tests_resp), "gpt-4o-mini"),
        "performance": build_performance_agent(_llm_with(perf_resp), "gpt-4o-mini"),
        "security": build_security_agent(_llm_with(sec_resp), "gpt-4o-mini"),
    }
    graph = build_graph(agents)
    initial: ReviewState = {
        "pr_metadata": pr_metadata,
        "diff": _DIFF_AUTH_SQL,
        "files_changed": [],
    }
    out = await graph.ainvoke(initial)
    assert set(out["selected_agents"]) == {"quality", "tests", "performance", "security"}
    assert set(out["findings"].keys()) == {"quality", "tests", "performance", "security"}
    assert len(out["aggregated"]) >= 1
    assert out["aggregated"][0].severity.value == "critical"
    assert "sql injection" in out["final_comment"].lower()
    assert out["cost_usd"] > 0


async def test_dedup_collapses_cross_agent_overlap(pr_metadata: PRMetadata) -> None:
    same_title = "hardcoded api key"
    quality_resp = (
        '{"findings":[{"severity":"low","file":"src/x.py","line":10,"title":'
        f'"{same_title}","explanation":"e"}}]}}'
    )
    sec_resp = (
        '{"findings":[{"severity":"high","file":"src/x.py","line":10,"title":'
        f'"{same_title}","explanation":"e"}}]}}'
    )
    agents = {
        "quality": build_quality_agent(_llm_with(quality_resp), "gpt-4o-mini"),
        "security": build_security_agent(_llm_with(sec_resp), "gpt-4o-mini"),
    }
    graph = build_graph(agents)
    initial: ReviewState = {
        "pr_metadata": pr_metadata,
        "diff": "diff --git a/src/x.py b/src/x.py\n+API_KEY = 'sk-real'\n",
        "files_changed": [],
    }
    out = await graph.ainvoke(initial)
    assert len(out["aggregated"]) == 1
    assert out["aggregated"][0].agent == "security"
    assert out["aggregated"][0].severity.value == "high"
