"""Cache-aware decorator around `SpecialistAgent`.

Wraps an agent so that `run()` consults the on-disk cache before invoking the
LLM. Hits return the stored `AgentResult` verbatim (cost = 0 for that call;
the original cost was already paid). Misses fall through and write back.
"""

from __future__ import annotations

import structlog

from pr_review_agent.agents.base import AgentResult, SpecialistAgent
from pr_review_agent.agents.prompts import prompt_version
from pr_review_agent.cache.filecache import FileCache, cache_key
from pr_review_agent.state import FileChange, PRMetadata

_log = structlog.get_logger(__name__)


class CachingAgent:
    """Has the same surface as `SpecialistAgent` for graph-node compatibility."""

    def __init__(self, inner: SpecialistAgent, cache: FileCache) -> None:
        self._inner = inner
        self._cache = cache
        self.agent_name = inner.agent_name
        self.prompt_name = inner.prompt_name
        self.model_id = inner.model_id

    async def run(
        self,
        pr: PRMetadata,
        files_changed: list[FileChange],
        diff: str,
    ) -> AgentResult:
        key = cache_key(
            repo_id=f"{pr.owner}/{pr.repo}",
            blob_sha=pr.head_sha,
            agent=self.agent_name,
            model=self.model_id,
            prompt_version=prompt_version(self.prompt_name),
        )
        hit = self._cache.get(key)
        if hit is not None:
            _log.info("cache_hit", agent=self.agent_name, key=key[:12])
            # Cost is zeroed because the run-level total only sums what the
            # *current* invocation paid. The cache_hit flag preserves the
            # signal that this finding came from a prior call.
            return AgentResult(
                findings=list(hit.findings),
                cost_usd=0.0,
                prompt_tokens=0,
                completion_tokens=0,
                cache_hit=True,
            )
        result = await self._inner.run(pr=pr, files_changed=files_changed, diff=diff)
        self._cache.put(key, result)
        _log.info("cache_miss", agent=self.agent_name, key=key[:12])
        return result
