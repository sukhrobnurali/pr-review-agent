"""Public Python API.

The 10-line library example from the README:

    from pr_review_agent import review_pr
    out = await review_pr("acme/widgets#42", api_key="sk-...", github_token="ghp-...")
    print(out.final_comment)

For local diffs without GitHub access:

    from pr_review_agent import review_diff
    out = await review_diff(diff=Path("local.diff").read_text(), title="my change")
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from pr_review_agent._runner import ReviewOutcome, run_review
from pr_review_agent.config import Settings
from pr_review_agent.state import PRMetadata
from pr_review_agent.tools.github import GitHubClient

if TYPE_CHECKING:
    from pr_review_agent.cache import FileCache


__all__ = [
    "PRMetadata",
    "ReviewOutcome",
    "Settings",
    "parse_pr_ref",
    "review_diff",
    "review_pr",
]


_PR_SHORT = re.compile(r"^([^/\s]+)/([^/#\s]+)#(\d+)$")
_PR_URL = re.compile(r"^https?://github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)(?:[/?#].*)?$")


def parse_pr_ref(ref: str) -> tuple[str, str, int]:
    """Accept `owner/repo#N` or a full GitHub PR URL; return (owner, repo, number)."""
    for pat in (_PR_SHORT, _PR_URL):
        m = pat.match(ref.strip())
        if m:
            return m.group(1), m.group(2), int(m.group(3))
    raise ValueError(f"expected 'owner/repo#NUMBER' or PR URL, got: {ref!r}")


def _resolve_api_key(provider: str, override: str | None) -> str | None:
    if override:
        return override
    env_var = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
    return os.environ.get(env_var)


async def review_pr(
    pr_ref: str,
    *,
    settings: Settings | None = None,
    api_key: str | None = None,
    github_token: str | None = None,
    cache: FileCache | None = None,
) -> ReviewOutcome:
    """Fetch a PR from GitHub and run the review pipeline.

    Does not post a comment — caller decides what to do with `outcome.final_comment`.
    """
    settings = settings or Settings()
    resolved_key = _resolve_api_key(settings.provider, api_key)
    if resolved_key is None:
        env_var = "OPENAI_API_KEY" if settings.provider == "openai" else "ANTHROPIC_API_KEY"
        raise RuntimeError(f"no API key for {settings.provider}; pass api_key= or set {env_var}")

    owner, repo, number = parse_pr_ref(pr_ref)
    token = github_token or os.environ.get("GITHUB_TOKEN") or ""
    client = GitHubClient.from_token(token)
    pr = await client.fetch_pr(owner, repo, number)
    diff = await client.fetch_diff(owner, repo, number)
    return await run_review(
        settings=settings,
        pr=pr,
        diff=diff,
        api_key=resolved_key,
        cache=cache,
    )


async def review_diff(
    diff: str,
    *,
    title: str = "local diff",
    settings: Settings | None = None,
    api_key: str | None = None,
    pr: PRMetadata | None = None,
    cache: FileCache | None = None,
) -> ReviewOutcome:
    """Run the review pipeline against a local unified diff (no GitHub call)."""
    settings = settings or Settings()
    resolved_key = _resolve_api_key(settings.provider, api_key)
    if resolved_key is None:
        env_var = "OPENAI_API_KEY" if settings.provider == "openai" else "ANTHROPIC_API_KEY"
        raise RuntimeError(f"no API key for {settings.provider}; pass api_key= or set {env_var}")

    pr = pr or PRMetadata(
        owner="local",
        repo="local",
        number=1,
        title=title,
        head_sha="0" * 40,
        base_sha="0" * 40,
    )
    return await run_review(
        settings=settings,
        pr=pr,
        diff=diff,
        api_key=resolved_key,
        cache=cache,
    )
