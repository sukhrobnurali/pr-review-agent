from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from pr_review_agent.findings import AgentName, Severity

Provider = Literal["openai", "anthropic"]

_ALL_AGENTS: tuple[AgentName, ...] = ("quality", "tests", "performance", "security")


class AgentSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: list[AgentName] = Field(default_factory=lambda: list(_ALL_AGENTS))
    models: dict[AgentName, str] = Field(default_factory=dict)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Provider = "openai"
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str | None = None
    agents: AgentSettings = Field(default_factory=AgentSettings)
    severity_threshold: Severity = Severity.LOW
    include_paths: list[str] = Field(default_factory=lambda: ["**/*"])
    exclude_paths: list[str] = Field(default_factory=list)
    max_diff_size: int = Field(default=8000, gt=0)
    cost_cap_usd: float = Field(default=0.50, gt=0)

    @field_validator("severity_threshold", mode="before")
    @classmethod
    def _parse_severity(cls, v: object) -> object:
        if isinstance(v, str):
            return Severity(v.lower())
        return v

    def model_for(self, agent: AgentName) -> str:
        return self.agents.models.get(agent, self.model)

    def is_above_threshold(self, severity: Severity) -> bool:
        return severity >= self.severity_threshold

    def path_included(self, path: str) -> bool:
        if any(_glob_match(path, pat) for pat in self.exclude_paths):
            return False
        if not self.include_paths:
            return True
        return any(_glob_match(path, pat) for pat in self.include_paths)


@lru_cache(maxsize=256)
def _compile_glob(pattern: str) -> re.Pattern[str]:
    pat = pattern.replace("\\", "/")
    parts: list[str] = []
    i = 0
    n = len(pat)
    while i < n:
        if pat[i : i + 3] == "**/":
            parts.append(r"(?:[^/]+/)*")
            i += 3
        elif pat[i : i + 2] == "**":
            parts.append(r".*")
            i += 2
        elif pat[i] == "*":
            parts.append(r"[^/]*")
            i += 1
        elif pat[i] == "?":
            parts.append(r"[^/]")
            i += 1
        else:
            parts.append(re.escape(pat[i]))
            i += 1
    return re.compile("^" + "".join(parts) + "$")


def _glob_match(path: str, pattern: str) -> bool:
    return _compile_glob(pattern).fullmatch(path.replace("\\", "/")) is not None


def load_settings(path: str | Path | None) -> Settings:
    if path is None:
        return Settings()
    p = Path(path)
    if not p.exists():
        return Settings()
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{p}: top-level YAML must be a mapping, got {type(raw).__name__}")
    try:
        return Settings.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"{p}: {exc}") from exc
