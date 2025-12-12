from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from pr_review_agent import api
from pr_review_agent._runner import ReviewOutcome
from pr_review_agent.config import Settings
from pr_review_agent.state import PRMetadata


@pytest.mark.parametrize(
    "ref, expected",
    [
        ("acme/widgets#42", ("acme", "widgets", 42)),
        ("https://github.com/acme/widgets/pull/42", ("acme", "widgets", 42)),
        ("https://github.com/acme/widgets/pull/42/files", ("acme", "widgets", 42)),
        ("  acme/widgets#7  ", ("acme", "widgets", 7)),
    ],
)
def test_parse_pr_ref_accepts_short_and_url(ref: str, expected: tuple[str, str, int]) -> None:
    assert api.parse_pr_ref(ref) == expected


@pytest.mark.parametrize("ref", ["nope", "acme/widgets", "acme#42", ""])
def test_parse_pr_ref_rejects_garbage(ref: str) -> None:
    with pytest.raises(ValueError):
        api.parse_pr_ref(ref)


@pytest.mark.asyncio
async def test_review_diff_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="no API key"):
        await api.review_diff(diff="--- a\n+++ b\n")


@pytest.mark.asyncio
async def test_review_pr_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    s = Settings(provider="openai")
    with pytest.raises(RuntimeError, match="no API key"):
        await api.review_pr("acme/widgets#1", settings=s)


@pytest.mark.asyncio
async def test_review_diff_passes_diff_through_to_runner() -> None:
    captured: dict[str, Any] = {}

    async def fake_run(**kwargs: Any) -> ReviewOutcome:
        captured.update(kwargs)
        return ReviewOutcome(final_comment="ok", cost_usd=0.0, selected_agents=[], findings_count=0)

    with patch("pr_review_agent.api.run_review", side_effect=fake_run):
        out = await api.review_diff(diff="some diff", title="my change", api_key="k")

    assert out.final_comment == "ok"
    assert captured["diff"] == "some diff"
    assert captured["api_key"] == "k"
    assert captured["pr"].title == "my change"


@pytest.mark.asyncio
async def test_review_pr_fetches_then_runs() -> None:
    fake_client = type("C", (), {})()
    fake_client.fetch_pr = AsyncMock(  # type: ignore[attr-defined]
        return_value=PRMetadata(
            owner="o", repo="r", number=1, title="t", head_sha="h", base_sha="b"
        )
    )
    fake_client.fetch_diff = AsyncMock(return_value="DIFF")  # type: ignore[attr-defined]

    captured: dict[str, Any] = {}

    async def fake_run(**kwargs: Any) -> ReviewOutcome:
        captured.update(kwargs)
        return ReviewOutcome(final_comment="x", cost_usd=0.0, selected_agents=[], findings_count=0)

    with (
        patch.object(api.GitHubClient, "from_token", return_value=fake_client),
        patch("pr_review_agent.api.run_review", side_effect=fake_run),
    ):
        out = await api.review_pr("o/r#1", api_key="k", github_token="ghp")

    assert out.final_comment == "x"
    assert captured["diff"] == "DIFF"
    assert captured["pr"].owner == "o"
    fake_client.fetch_pr.assert_awaited_once()  # type: ignore[attr-defined]
    fake_client.fetch_diff.assert_awaited_once()  # type: ignore[attr-defined]
