from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from pydantic import BaseModel, ConfigDict, Field

from pr_review_agent.findings import AgentName, Finding


def merge_findings(
    left: dict[AgentName, list[Finding]] | None,
    right: dict[AgentName, list[Finding]] | None,
) -> dict[AgentName, list[Finding]]:
    out: dict[AgentName, list[Finding]] = dict(left or {})
    out.update(right or {})
    return out


def add_floats(left: float | None, right: float | None) -> float:
    return (left or 0.0) + (right or 0.0)


class PRMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    owner: str
    repo: str
    number: int = Field(..., ge=1)
    title: str
    head_sha: str
    base_sha: str
    author: str | None = None


class Hunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    new_start: int = Field(..., ge=1)
    new_end: int = Field(..., ge=1)
    old_start: int = Field(..., ge=0)
    old_end: int = Field(..., ge=0)
    body: str


class FileChange(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    old_path: str | None = None
    status: str = "modified"
    hunks: tuple[Hunk, ...] = ()

    @property
    def is_renamed(self) -> bool:
        return self.old_path is not None and self.old_path != self.path

    @property
    def added_line_ranges(self) -> list[tuple[int, int]]:
        return [(h.new_start, h.new_end) for h in self.hunks]


class AgentError(BaseModel):
    agent: AgentName
    message: str


class ReviewState(TypedDict, total=False):
    pr_metadata: PRMetadata
    diff: str
    files_changed: list[FileChange]
    selected_agents: list[AgentName]
    findings: Annotated[dict[AgentName, list[Finding]], merge_findings]
    cost_usd: Annotated[float, add_floats]
    errors: Annotated[list[AgentError], add]
    aggregated: list[Finding]
    final_comment: str
