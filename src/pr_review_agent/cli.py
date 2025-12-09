"""Typer-based CLI for pr-review-agent.

Examples:
    pr-review-agent review acme/widgets#42 --dry-run
    pr-review-agent review https://github.com/acme/widgets/pull/42
    pr-review-agent review --diff-file local.diff --dry-run
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
import sys
from pathlib import Path

import typer

from pr_review_agent._runner import ReviewOutcome, run_review
from pr_review_agent.config import Settings, load_settings
from pr_review_agent.findings import AgentName
from pr_review_agent.reporting import post_or_update_review
from pr_review_agent.state import PRMetadata
from pr_review_agent.tools.github import GitHubClient

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Multi-agent PR reviewer")

_PR_SHORT = re.compile(r"^([^/\s]+)/([^/#\s]+)#(\d+)$")
_PR_URL = re.compile(r"^https?://github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)(?:[/?#].*)?$")
_VALID_AGENTS: tuple[AgentName, ...] = ("quality", "tests", "performance", "security")


def parse_pr_ref(ref: str) -> tuple[str, str, int]:
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


def _apply_overrides(
    settings: Settings,
    *,
    provider: str | None,
    model: str | None,
    only: str | None,
) -> Settings:
    data = settings.model_dump()
    if provider is not None:
        data["provider"] = provider
    if model is not None:
        data["model"] = model
    if only:
        wanted = [a.strip() for a in only.split(",") if a.strip()]
        invalid = [a for a in wanted if a not in _VALID_AGENTS]
        if invalid:
            raise typer.BadParameter(f"unknown agent(s): {invalid}")
        data["agents"]["enabled"] = wanted
    return Settings.model_validate(data)


@app.command("review")
def review(
    pr_ref: str | None = typer.Argument(
        None, help="owner/repo#N or PR URL; omit when using --diff-file"
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="path to .pr-review.yml"
    ),
    provider: str | None = typer.Option(
        None, "--provider", help="override provider (openai|anthropic)"
    ),
    model: str | None = typer.Option(None, "--model", help="override default model"),
    only: str | None = typer.Option(None, "--only", help="comma-separated subset of agents"),
    api_key: str | None = typer.Option(
        None, "--api-key", help="LLM API key (else read from env)"
    ),
    token: str | None = typer.Option(
        None, "--token", help="GitHub token (else read from GITHUB_TOKEN)"
    ),
    diff_file: Path | None = typer.Option(
        None, "--diff-file", help="local unified diff (skips GitHub fetch)"
    ),
    title: str = typer.Option("local diff", "--title", help="PR title (with --diff-file)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="print comment instead of posting"),
) -> None:
    """Review a pull request."""
    settings = load_settings(config or _default_config_path())
    settings = _apply_overrides(settings, provider=provider, model=model, only=only)

    resolved_key = _resolve_api_key(settings.provider, api_key)
    if resolved_key is None:
        typer.echo(
            f"error: no API key for {settings.provider}; pass --api-key or set "
            f"{'OPENAI_API_KEY' if settings.provider == 'openai' else 'ANTHROPIC_API_KEY'}",
            err=True,
        )
        raise typer.Exit(code=2)

    if diff_file is not None:
        outcome = asyncio.run(
            _review_local_diff(diff_file, title, settings, resolved_key)
        )
        _print_outcome(outcome, dry_run=True, posted_id=None)
        return

    if pr_ref is None:
        typer.echo("error: provide a PR reference or --diff-file", err=True)
        raise typer.Exit(code=2)

    owner, repo, number = parse_pr_ref(pr_ref)
    gh_token = token or os.environ.get("GITHUB_TOKEN")
    posted_id, outcome = asyncio.run(
        _review_real_pr(
            owner=owner,
            repo=repo,
            number=number,
            settings=settings,
            api_key=resolved_key,
            gh_token=gh_token,
            dry_run=dry_run,
        )
    )
    _print_outcome(outcome, dry_run=dry_run, posted_id=posted_id)


async def _review_local_diff(
    diff_path: Path, title: str, settings: Settings, api_key: str
) -> ReviewOutcome:
    diff = diff_path.read_text(encoding="utf-8")
    pr = PRMetadata(
        owner="local",
        repo="local",
        number=1,
        title=title,
        head_sha="0" * 40,
        base_sha="0" * 40,
    )
    return await run_review(settings=settings, pr=pr, diff=diff, api_key=api_key)


async def _review_real_pr(
    *,
    owner: str,
    repo: str,
    number: int,
    settings: Settings,
    api_key: str,
    gh_token: str | None,
    dry_run: bool,
) -> tuple[int | None, ReviewOutcome]:
    client = GitHubClient.from_token(gh_token or "")
    pr = await client.fetch_pr(owner, repo, number)
    diff = await client.fetch_diff(owner, repo, number)
    outcome = await run_review(settings=settings, pr=pr, diff=diff, api_key=api_key)
    posted_id = await post_or_update_review(
        client,
        owner=owner,
        repo=repo,
        number=number,
        body=outcome.final_comment,
        dry_run=dry_run,
    )
    return posted_id, outcome


def _default_config_path() -> Path | None:
    candidate = Path.cwd() / ".pr-review.yml"
    return candidate if candidate.exists() else None


def _print_outcome(outcome: ReviewOutcome, *, dry_run: bool, posted_id: int | None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    typer.echo(outcome.final_comment)
    typer.echo("")
    typer.echo(f"selected: {outcome.selected_agents}")
    typer.echo(f"findings: {outcome.findings_count}")
    typer.echo(f"cost_usd: {outcome.cost_usd:.4f}")
    if outcome.errors:
        typer.echo(f"errors: {len(outcome.errors)}", err=True)
        for e in outcome.errors:
            typer.echo(f"  - {e.agent}: {e.message}", err=True)
    if dry_run:
        typer.echo("(dry run; nothing posted)")
    elif posted_id is not None:
        typer.echo(f"posted comment id: {posted_id}")


if __name__ == "__main__":
    app()
