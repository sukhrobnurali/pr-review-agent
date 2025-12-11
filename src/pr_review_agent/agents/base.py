from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError

from pr_review_agent.findings import AgentName, FileLocation, Finding, Severity
from pr_review_agent.models.pricing import compute_cost_usd
from pr_review_agent.state import FileChange, PRMetadata

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


class _RawFinding(BaseModel):
    severity: Severity
    file: str
    line: int
    end_line: int | None = None
    title: str
    explanation: str
    suggestion: str | None = None


class _RawFindings(BaseModel):
    findings: list[_RawFinding] = []


class AgentResult(BaseModel):
    findings: list[Finding]
    cost_usd: float
    prompt_tokens: int
    completion_tokens: int
    cache_hit: bool = False


@runtime_checkable
class AgentRunnable(Protocol):
    """Anything the graph can dispatch as a specialist node.

    Implemented directly by `SpecialistAgent` and by the cache wrapper.
    """

    agent_name: AgentName

    async def run(
        self,
        pr: PRMetadata,
        files_changed: list[FileChange],
        diff: str,
    ) -> AgentResult: ...


class SpecialistAgent:
    agent_name: AgentName
    prompt_name: str
    model_id: str

    def __init__(
        self,
        agent_name: AgentName,
        llm: BaseChatModel,
        prompt_name: str,
        model_id: str,
    ) -> None:
        self.agent_name = agent_name
        self.prompt_name = prompt_name
        self.model_id = model_id
        self._llm = llm

    async def run(
        self,
        pr: PRMetadata,
        files_changed: list[FileChange],
        diff: str,
    ) -> AgentResult:
        from pr_review_agent.agents.prompts import render_prompt

        prompt = render_prompt(
            self.prompt_name,
            variables={
                "pr_title": pr.title,
                "pr_author": pr.author or "unknown",
                "diff": diff,
                "files_changed": [f.path for f in files_changed],
            },
        )
        response = await self._llm.ainvoke([HumanMessage(content=prompt)])
        usage = _extract_usage(response)
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
        cost = compute_cost_usd(self.model_id, prompt_tokens, completion_tokens)
        findings = self._parse(_message_text(response))
        return AgentResult(
            findings=findings,
            cost_usd=cost,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def _parse(self, content: str) -> list[Finding]:
        return parse_findings_from_text(content, self.agent_name)


_FENCED_JSON = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(content: str) -> str | None:
    match = _FENCED_JSON.search(content)
    if match:
        return match.group(1)
    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    return None


def _message_text(response: Any) -> str:
    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(str(part["text"]))
        return "".join(parts)
    return str(content)


def _extract_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage_metadata", None)
    if isinstance(usage, dict):
        return {k: int(v) for k, v in usage.items() if isinstance(v, int)}
    legacy = getattr(response, "response_metadata", None)
    if isinstance(legacy, dict):
        token_usage = legacy.get("token_usage") or legacy.get("usage") or {}
        result: dict[str, int] = {}
        if isinstance(token_usage, dict):
            if "prompt_tokens" in token_usage:
                result["input_tokens"] = int(token_usage["prompt_tokens"])
            if "completion_tokens" in token_usage:
                result["output_tokens"] = int(token_usage["completion_tokens"])
        if result:
            return result
    return {}


def parse_findings_from_text(content: str, agent: AgentName) -> list[Finding]:
    json_text = _extract_json(content)
    if json_text is None:
        return []
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    raw_findings = payload.get("findings", [])
    if not isinstance(raw_findings, list):
        return []
    out: list[Finding] = []
    for entry in raw_findings:
        if not isinstance(entry, dict):
            continue
        try:
            r = _RawFinding.model_validate(entry)
            out.append(
                Finding(
                    severity=r.severity,
                    location=FileLocation(path=r.file, line=r.line, end_line=r.end_line),
                    agent=agent,
                    title=r.title,
                    explanation=r.explanation,
                    suggestion=r.suggestion,
                )
            )
        except ValidationError:
            continue
    return out
