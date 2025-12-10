"""On-disk cache for agent results.

Key per ADR-0008 (q8 in the brief): sha256(repo_id | blob_sha | agent | model |
prompt_version). `blob_sha` is the PR head SHA — stable across rebases of the
same diff, fresh on push. `prompt_version` is a hash of the prompt template
text so editing a prompt invalidates entries that used the old one.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pr_review_agent.agents.base import AgentResult
    from pr_review_agent.findings import AgentName


def default_cache_dir() -> Path:
    if env := os.environ.get("PR_REVIEW_CACHE_DIR"):
        return Path(env)
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "pr-review-agent" / "cache"
        return Path.home() / "AppData" / "Local" / "pr-review-agent" / "cache"
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "pr-review-agent"


def cache_key(
    *,
    repo_id: str,
    blob_sha: str,
    agent: AgentName,
    model: str,
    prompt_version: str,
) -> str:
    parts = "|".join([repo_id, blob_sha, agent, model, prompt_version])
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()


class FileCache:
    """Tiny content-addressed JSON cache. Best-effort — corrupt entries miss."""

    def __init__(self, root: Path | str | None = None) -> None:
        self._root = Path(root) if root is not None else default_cache_dir()

    @property
    def root(self) -> Path:
        return self._root

    def get(self, key: str) -> AgentResult | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        from pr_review_agent.agents.base import AgentResult

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return AgentResult.model_validate(data)
        except (OSError, json.JSONDecodeError, ValueError):
            return None

    def put(self, key: str, result: AgentResult) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(result.model_dump_json(), encoding="utf-8")
        tmp.replace(path)

    def clear(self) -> None:
        if not self._root.exists():
            return
        for entry in self._root.rglob("*.json"):
            entry.unlink()

    def _path_for(self, key: str) -> Path:
        return self._root / key[:2] / f"{key}.json"
