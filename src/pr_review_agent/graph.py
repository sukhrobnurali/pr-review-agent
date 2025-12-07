from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from langgraph.graph import END, StateGraph

from pr_review_agent.agents.supervisor import select_specialists
from pr_review_agent.findings import AgentName, Finding, compose_markdown, deduplicate, rank
from pr_review_agent.state import AgentError, ReviewState

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pr_review_agent.agents.base import SpecialistAgent

_log = structlog.get_logger(__name__)


def build_graph(agents: dict[AgentName, SpecialistAgent]) -> Any:
    async def select_node(state: ReviewState) -> dict[str, Any]:
        selected = select_specialists(
            state.get("files_changed", []),
            state.get("diff", ""),
            available=list(agents.keys()),
        )
        _log.info("select", selected=selected)
        return {"selected_agents": selected}

    def make_agent_node(
        name: AgentName, agent: SpecialistAgent
    ) -> Callable[[ReviewState], Awaitable[dict[str, Any]]]:
        async def node(state: ReviewState) -> dict[str, Any]:
            if name not in state.get("selected_agents", []):
                return {}
            try:
                result = await agent.run(
                    pr=state["pr_metadata"],
                    files_changed=state.get("files_changed", []),
                    diff=state.get("diff", ""),
                )
                return {
                    "findings": {name: result.findings},
                    "cost_usd": result.cost_usd,
                }
            except Exception as exc:
                _log.warning("agent_failure", agent=name, error=str(exc))
                return {"errors": [AgentError(agent=name, message=str(exc))]}

        node.__name__ = f"{name}_node"
        return node

    async def aggregate_node(state: ReviewState) -> dict[str, Any]:
        all_findings: list[Finding] = []
        for findings_list in state.get("findings", {}).values():
            all_findings.extend(findings_list)
        deduped = deduplicate(all_findings)
        ranked = rank(deduped)
        _log.info("aggregate", input=len(all_findings), output=len(ranked))
        return {"aggregated": ranked}

    async def compose_node(state: ReviewState) -> dict[str, Any]:
        comment = compose_markdown(
            state.get("aggregated", []),
            cost_usd=state.get("cost_usd", 0.0),
        )
        return {"final_comment": comment}

    builder = StateGraph(ReviewState)
    builder.add_node("select", select_node)
    for name, agent in agents.items():
        builder.add_node(name, make_agent_node(name, agent))
    builder.add_node("aggregate", aggregate_node)
    builder.add_node("compose", compose_node)

    builder.set_entry_point("select")
    for name in agents:
        builder.add_edge("select", name)
        builder.add_edge(name, "aggregate")
    builder.add_edge("aggregate", "compose")
    builder.add_edge("compose", END)

    return builder.compile()
