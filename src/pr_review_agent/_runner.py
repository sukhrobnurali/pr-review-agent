"""Internal orchestration shared by CLI and Action entrypoints.

Public surface stabilizes as `pr_review_agent.api` on Day 6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pr_review_agent.agents import (
    build_performance_agent,
    build_quality_agent,
    build_security_agent,
    build_tests_agent,
)
from pr_review_agent.findings import AgentName
from pr_review_agent.graph import build_graph
from pr_review_agent.models import ModelConfig, build_llm
from pr_review_agent.state import AgentError, PRMetadata, ReviewState
from pr_review_agent.tools.git import parse_diff

if TYPE_CHECKING:
    from collections.abc import Callable

    from langchain_core.language_models import BaseChatModel

    from pr_review_agent.agents.base import SpecialistAgent
    from pr_review_agent.config import Settings


@dataclass(frozen=True)
class ReviewOutcome:
    final_comment: str
    cost_usd: float
    selected_agents: list[AgentName]
    findings_count: int
    errors: list[AgentError] = field(default_factory=list)


_BUILDERS: dict[AgentName, Callable[[BaseChatModel, str], SpecialistAgent]] = {
    "quality": build_quality_agent,
    "tests": build_tests_agent,
    "performance": build_performance_agent,
    "security": build_security_agent,
}


def build_agents_from_settings(
    settings: Settings, *, api_key: str | None
) -> dict[AgentName, SpecialistAgent]:
    out: dict[AgentName, SpecialistAgent] = {}
    for name in settings.agents.enabled:
        model_id = settings.model_for(name)
        cfg = ModelConfig(
            provider=settings.provider,
            model=model_id,
            api_key=api_key,
            base_url=settings.base_url,
        )
        llm = build_llm(cfg)
        out[name] = _BUILDERS[name](llm, model_id)
    return out


async def run_review(
    *,
    settings: Settings,
    pr: PRMetadata,
    diff: str,
    api_key: str | None = None,
    agents: dict[AgentName, SpecialistAgent] | None = None,
) -> ReviewOutcome:
    files = [f for f in parse_diff(diff) if settings.path_included(f.path)]
    if agents is None:
        agents = build_agents_from_settings(settings, api_key=api_key)
    graph = build_graph(agents)
    state: ReviewState = {
        "pr_metadata": pr,
        "diff": diff,
        "files_changed": files,
    }
    out = await graph.ainvoke(state)
    return ReviewOutcome(
        final_comment=out.get("final_comment", ""),
        cost_usd=out.get("cost_usd", 0.0),
        selected_agents=list(out.get("selected_agents", [])),
        findings_count=len(out.get("aggregated", [])),
        errors=list(out.get("errors", [])),
    )
