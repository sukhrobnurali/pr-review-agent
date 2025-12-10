"""GitHub Action entrypoint.

The action's Dockerfile invokes `python -m pr_review_agent.main`. We read the
event payload from `GITHUB_EVENT_PATH`, pull config from `INPUT_*` env vars,
run the graph, and post (or update) a review comment.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import structlog

from pr_review_agent._runner import run_review
from pr_review_agent.cache import FileCache
from pr_review_agent.config import Settings, load_settings
from pr_review_agent.findings import AgentName
from pr_review_agent.reporting import post_or_update_review
from pr_review_agent.tools.github import GitHubClient

_log = structlog.get_logger("pr_review_agent.main")

_VALID_AGENTS: tuple[AgentName, ...] = ("quality", "tests", "performance", "security")
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def parse_event(path: Path) -> dict[str, Any]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"event payload at {path} is not a JSON object")
    return payload


def extract_pr_coords(event: dict[str, Any]) -> tuple[str, str, int]:
    pr = event.get("pull_request")
    repo = event.get("repository")
    if not isinstance(pr, dict) or not isinstance(repo, dict):
        raise ValueError("event is not a pull_request payload")
    number = pr.get("number")
    owner = (repo.get("owner") or {}).get("login")
    name = repo.get("name")
    if not (isinstance(number, int) and isinstance(owner, str) and isinstance(name, str)):
        raise ValueError("event missing pull_request.number / repository.owner.login / .name")
    return owner, name, number


def _input(name: str) -> str | None:
    value = os.environ.get(f"INPUT_{name.upper()}")
    return value.strip() if value and value.strip() else None


def _bool_input(name: str) -> bool:
    val = _input(name)
    return val is not None and val.lower() in _TRUTHY


def _build_settings_from_env() -> Settings:
    config_path = _input("config_path")
    settings = load_settings(Path(config_path) if config_path else _default_config_path())
    overrides: dict[str, Any] = {}
    if (provider := _input("provider")) is not None:
        overrides["provider"] = provider
    if (model := _input("model")) is not None:
        overrides["model"] = model
    if (only := _input("only")) is not None:
        wanted = [a.strip() for a in only.split(",") if a.strip()]
        invalid = [a for a in wanted if a not in _VALID_AGENTS]
        if invalid:
            raise ValueError(f"unknown agent(s) in INPUT_ONLY: {invalid}")
        data = settings.agents.model_dump()
        data["enabled"] = wanted
        overrides["agents"] = data
    if not overrides:
        return settings
    merged = settings.model_dump()
    merged.update(overrides)
    return Settings.model_validate(merged)


def _default_config_path() -> Path | None:
    candidate = Path.cwd() / ".pr-review.yml"
    return candidate if candidate.exists() else None


def _resolve_api_key(provider: str) -> str | None:
    if (override := _input("api_key")) is not None:
        return override
    env_var = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
    return os.environ.get(env_var)


def _resolve_github_token() -> str | None:
    return _input("github_token") or os.environ.get("GITHUB_TOKEN")


async def main_async() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        _log.error("missing_event_path")
        print("error: GITHUB_EVENT_PATH not set", file=sys.stderr)
        return 2

    try:
        event = parse_event(Path(event_path))
        owner, repo, number = extract_pr_coords(event)
    except (OSError, ValueError) as exc:
        _log.error("event_parse_failed", error=str(exc))
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        settings = _build_settings_from_env()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    api_key = _resolve_api_key(settings.provider)
    if api_key is None:
        env_var = "OPENAI_API_KEY" if settings.provider == "openai" else "ANTHROPIC_API_KEY"
        print(f"error: no API key for {settings.provider}; set {env_var}", file=sys.stderr)
        return 2

    gh_token = _resolve_github_token()
    if gh_token is None:
        print("error: no GitHub token; set GITHUB_TOKEN or pass via inputs", file=sys.stderr)
        return 2

    dry_run = _bool_input("dry_run")
    cache_dir = _input("cache_dir")
    cache = FileCache(cache_dir) if cache_dir else None
    client = GitHubClient.from_token(gh_token)

    _log.info("review_start", owner=owner, repo=repo, number=number, dry_run=dry_run)
    pr = await client.fetch_pr(owner, repo, number)
    diff = await client.fetch_diff(owner, repo, number)

    outcome = await run_review(
        settings=settings, pr=pr, diff=diff, api_key=api_key, cache=cache
    )

    posted_id = await post_or_update_review(
        client,
        owner=owner,
        repo=repo,
        number=number,
        body=outcome.final_comment,
        dry_run=dry_run,
    )
    _log.info(
        "review_done",
        posted_id=posted_id,
        cost_usd=outcome.cost_usd,
        findings=outcome.findings_count,
        selected=outcome.selected_agents,
        errors=len(outcome.errors),
    )
    return 0


def run_from_environment() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(run_from_environment())
