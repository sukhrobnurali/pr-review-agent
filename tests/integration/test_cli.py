from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from pr_review_agent._runner import ReviewOutcome
from pr_review_agent.cli import app, parse_pr_ref

runner = CliRunner()


def test_parse_pr_ref_short_form() -> None:
    assert parse_pr_ref("acme/widgets#42") == ("acme", "widgets", 42)


def test_parse_pr_ref_https_url() -> None:
    assert parse_pr_ref("https://github.com/acme/widgets/pull/42") == ("acme", "widgets", 42)


def test_parse_pr_ref_with_trailing_slash_or_query() -> None:
    assert parse_pr_ref("https://github.com/acme/widgets/pull/42/files") == (
        "acme",
        "widgets",
        42,
    )


def test_parse_pr_ref_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_pr_ref("not-a-ref")


@pytest.fixture
def fake_outcome() -> ReviewOutcome:
    return ReviewOutcome(
        final_comment="### TL;DR\n- one finding\n",
        cost_usd=0.0123,
        selected_agents=["quality", "tests"],
        findings_count=1,
        errors=[],
    )


def _diff_file(tmp_path: Path) -> Path:
    p = tmp_path / "sample.diff"
    p.write_text(
        "diff --git a/src/x.py b/src/x.py\n"
        "--- a/src/x.py\n"
        "+++ b/src/x.py\n"
        "@@ -1,1 +1,2 @@\n"
        " a\n"
        "+b\n",
        encoding="utf-8",
    )
    return p


def test_review_dry_run_with_diff_file_prints_comment(
    tmp_path: Path, fake_outcome: ReviewOutcome, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    diff = _diff_file(tmp_path)
    with patch("pr_review_agent.cli.run_review", new=AsyncMock(return_value=fake_outcome)):
        result = runner.invoke(
            app,
            ["review", "--diff-file", str(diff), "--dry-run", "--title", "local test"],
        )
    assert result.exit_code == 0, result.output
    assert "### TL;DR" in result.output
    assert "one finding" in result.output
    assert "0.0123" in result.output


def test_review_dry_run_does_not_post(
    tmp_path: Path, fake_outcome: ReviewOutcome, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    diff = _diff_file(tmp_path)
    posted: dict[str, Any] = {"called": False}

    async def fake_post(*args: Any, **kwargs: Any) -> int:
        posted["called"] = True
        return 1

    with (
        patch("pr_review_agent.cli.run_review", new=AsyncMock(return_value=fake_outcome)),
        patch("pr_review_agent.cli.post_or_update_review", new=AsyncMock(side_effect=fake_post)),
    ):
        result = runner.invoke(app, ["review", "--diff-file", str(diff), "--dry-run"])
    assert result.exit_code == 0
    assert posted["called"] is False


def test_review_with_only_filters_agents(
    tmp_path: Path, fake_outcome: ReviewOutcome, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    diff = _diff_file(tmp_path)
    captured: dict[str, Any] = {}

    async def fake_run(**kwargs: Any) -> ReviewOutcome:
        captured["enabled"] = list(kwargs["settings"].agents.enabled)
        return fake_outcome

    with patch("pr_review_agent.cli.run_review", new=fake_run):
        result = runner.invoke(
            app,
            ["review", "--diff-file", str(diff), "--dry-run", "--only", "quality,tests"],
        )
    assert result.exit_code == 0
    assert captured["enabled"] == ["quality", "tests"]


def test_review_missing_api_key_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    diff = _diff_file(tmp_path)
    result = runner.invoke(app, ["review", "--diff-file", str(diff), "--dry-run"])
    assert result.exit_code != 0
    assert "api key" in result.output.lower()


def test_review_uses_config_file(
    tmp_path: Path, fake_outcome: ReviewOutcome, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    diff = _diff_file(tmp_path)
    cfg = tmp_path / "cfg.yml"
    cfg.write_text("provider: anthropic\nmodel: claude-haiku-4\n", encoding="utf-8")
    captured: dict[str, Any] = {}

    async def fake_run(**kwargs: Any) -> ReviewOutcome:
        captured["provider"] = kwargs["settings"].provider
        captured["model"] = kwargs["settings"].model
        return fake_outcome

    with patch("pr_review_agent.cli.run_review", new=fake_run):
        result = runner.invoke(
            app,
            ["review", "--diff-file", str(diff), "--dry-run", "--config", str(cfg)],
        )
    assert result.exit_code == 0, result.output
    assert captured == {"provider": "anthropic", "model": "claude-haiku-4"}
