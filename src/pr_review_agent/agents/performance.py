from __future__ import annotations

from typing import TYPE_CHECKING

from pr_review_agent.agents.base import SpecialistAgent

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


def build_performance_agent(llm: BaseChatModel, model_id: str) -> SpecialistAgent:
    return SpecialistAgent(
        agent_name="performance",
        llm=llm,
        prompt_name="performance",
        model_id=model_id,
    )
