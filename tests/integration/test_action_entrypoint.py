from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from pr_review_agent._runner import ReviewOutcome
from pr_review_agent.main import (
    extract_pr_coords,
    main_async,
    parse_event,
    run_from_environment,
)
from pr_review_agent.state import PRMetadata


def _event_dict(number: int = 42) -> dict[str, Any]:
    return {
        "action": "opened",
        "pull_request": {
            "number": number,
            "title": "Add raw SQL login",
            "head": {"sha": "a" * 40},
            "base": {"sha": "b" * 40},
            "user": {"login": "octocat"},
        },
        "repository": {
            "owner": {"login": "acme"},
            "name": "widgets",
            "full_name": "acme/widgets",
        },
    }


def _write_event(tmp_path: Path, payload: dict[str, Any]) -> Path:
    p = tmp_path / "event.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_parse_event_reads_pr_payload(tmp_path: Path) -> None:
    p = _write_event(tmp_path, _event_dict(number=99))
    parsed = parse_event(p)
    assert parsed["pull_request"]["number"] == 99


def test_extract_pr_coords_from_event() -> None:
    owner, repo, number = extract_pr_coords(_event_dict(number=7))
    assert (owner, repo, number) == ("acme", "widgets", 7)


def test_extract_pr_coords_rejects_non_pr_event() -> None:
    with pytest.raises(ValueError):
        extract_pr_coords({"action": "opened", "repository": {"name": "x"}})


@pytest.fixture
def fake_pr() -> PRMetadata:
    return PRMetadata(
        owner="acme",
        repo="widgets",
        number=42,
        title="Add raw SQL login",
        head_sha="a" * 40,
        base_sha="b" * 40,
        author="octocat",
    )


@pytest.fixture
def fake_outcome() -> ReviewOutcome:
    return ReviewOutcome(
        final_comment="### TL;DR\n- found one\n",
        cost_usd=0.0011,
        selected_agents=["security", "quality"],
        findings_count=1,
        errors=[],
    )


@pytest.mark.asyncio
async def test_main_async_posts_via_marker(
    tmp_path: Path,
    fake_pr: PRMetadata,
    fake_outcome: ReviewOutcome,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_path = _write_event(tmp_path, _event_dict(number=42))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("INPUT_GITHUB_TOKEN", "ghs_xxx")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    fake_client = AsyncMock()
    fake_client.fetch_pr = AsyncMock(return_value=fake_pr)
    fake_client.fetch_diff = AsyncMock(return_value="diff --git a/x b/x\n+y\n")
    poster = AsyncMock(return_value=12345)

    with (
        patch("pr_review_agent.main.GitHubClient.from_token", return_value=fake_client),
        patch("pr_review_agent.main.run_review", new=AsyncMock(return_value=fake_outcome)),
        patch("pr_review_agent.main.post_or_update_review", new=poster),
    ):
        rc = await main_async()

    assert rc == 0
    poster.assert_awaited_once()
    call = poster.call_args
    assert call.kwargs["owner"] == "acme"
    assert call.kwargs["repo"] == "widgets"
    assert call.kwargs["number"] == 42
    assert "TL;DR" in call.kwargs["body"]
    assert call.kwargs.get("dry_run") is False


@pytest.mark.asyncio
async def test_main_async_dry_run_does_not_post(
    tmp_path: Path,
    fake_pr: PRMetadata,
    fake_outcome: ReviewOutcome,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_path = _write_event(tmp_path, _event_dict())
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("INPUT_GITHUB_TOKEN", "ghs_xxx")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("INPUT_DRY_RUN", "true")

    fake_client = AsyncMock()
    fake_client.fetch_pr = AsyncMock(return_value=fake_pr)
    fake_client.fetch_diff = AsyncMock(return_value="diff --git a/x b/x\n+y\n")
    poster = AsyncMock(return_value=None)

    with (
        patch("pr_review_agent.main.GitHubClient.from_token", return_value=fake_client),
        patch("pr_review_agent.main.run_review", new=AsyncMock(return_value=fake_outcome)),
        patch("pr_review_agent.main.post_or_update_review", new=poster),
    ):
        rc = await main_async()

    assert rc == 0
    assert poster.call_args.kwargs.get("dry_run") is True


@pytest.mark.asyncio
async def test_main_async_missing_event_path_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    rc = await main_async()
    assert rc != 0


@pytest.mark.asyncio
async def test_main_async_picks_up_input_overrides(
    tmp_path: Path,
    fake_pr: PRMetadata,
    fake_outcome: ReviewOutcome,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_path = _write_event(tmp_path, _event_dict())
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("INPUT_GITHUB_TOKEN", "ghs_xxx")
    monkeypatch.setenv("INPUT_PROVIDER", "anthropic")
    monkeypatch.setenv("INPUT_MODEL", "claude-haiku-4")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ak-test")

    captured: dict[str, Any] = {}

    async def fake_run_review(**kwargs: Any) -> ReviewOutcome:
        captured["provider"] = kwargs["settings"].provider
        captured["model"] = kwargs["settings"].model
        return fake_outcome

    fake_client = AsyncMock()
    fake_client.fetch_pr = AsyncMock(return_value=fake_pr)
    fake_client.fetch_diff = AsyncMock(return_value="diff --git a/x b/x\n+y\n")

    with (
        patch("pr_review_agent.main.GitHubClient.from_token", return_value=fake_client),
        patch("pr_review_agent.main.run_review", new=fake_run_review),
        patch(
            "pr_review_agent.main.post_or_update_review",
            new=AsyncMock(return_value=1),
        ),
    ):
        rc = await main_async()

    assert rc == 0
    assert captured == {"provider": "anthropic", "model": "claude-haiku-4"}


def test_run_from_environment_returns_int(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    rc = run_from_environment()
    assert isinstance(rc, int)
    assert rc != 0
