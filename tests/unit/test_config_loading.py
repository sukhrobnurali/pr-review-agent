from __future__ import annotations

from pathlib import Path

import pytest

from pr_review_agent.config import Settings, load_settings
from pr_review_agent.findings import Severity


def test_defaults_when_no_path() -> None:
    s = load_settings(None)
    assert s.provider == "openai"
    assert s.model == "gpt-4o-mini"
    assert set(s.agents.enabled) == {"quality", "tests", "performance", "security"}
    assert s.severity_threshold == Severity.LOW
    assert s.cost_cap_usd == pytest.approx(0.50)


def test_missing_path_returns_defaults(tmp_path: Path) -> None:
    s = load_settings(tmp_path / "nope.yml")
    assert s == Settings()


def test_partial_yaml_merges_with_defaults(tmp_path: Path) -> None:
    cfg = tmp_path / ".pr-review.yml"
    cfg.write_text("provider: anthropic\nmodel: claude-sonnet-4\n", encoding="utf-8")
    s = load_settings(cfg)
    assert s.provider == "anthropic"
    assert s.model == "claude-sonnet-4"
    assert set(s.agents.enabled) == {"quality", "tests", "performance", "security"}
    assert s.severity_threshold == Severity.LOW


def test_full_yaml_round_trip(tmp_path: Path) -> None:
    cfg = tmp_path / ".pr-review.yml"
    cfg.write_text(
        """
provider: anthropic
model: claude-sonnet-4
agents:
  enabled: [security, quality]
  models:
    security: claude-opus-4
    quality: claude-haiku-4
severity_threshold: high
include_paths: ["src/**"]
exclude_paths: ["**/vendor/**"]
max_diff_size: 5000
cost_cap_usd: 1.25
""".strip(),
        encoding="utf-8",
    )
    s = load_settings(cfg)
    assert s.provider == "anthropic"
    assert set(s.agents.enabled) == {"security", "quality"}
    assert s.agents.models == {"security": "claude-opus-4", "quality": "claude-haiku-4"}
    assert s.severity_threshold == Severity.HIGH
    assert s.exclude_paths == ["**/vendor/**"]
    assert s.max_diff_size == 5000
    assert s.cost_cap_usd == pytest.approx(1.25)


def test_invalid_provider_rejected(tmp_path: Path) -> None:
    cfg = tmp_path / ".pr-review.yml"
    cfg.write_text("provider: bedrock\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_settings(cfg)


def test_per_agent_model_lookup_falls_back_to_default() -> None:
    s = Settings.model_validate(
        {"model": "gpt-4o-mini", "agents": {"models": {"security": "gpt-4o"}}}
    )
    assert s.model_for("security") == "gpt-4o"
    assert s.model_for("quality") == "gpt-4o-mini"


def test_severity_threshold_filters_low_findings() -> None:
    s = Settings.model_validate({"severity_threshold": "medium"})
    assert s.is_above_threshold(Severity.HIGH) is True
    assert s.is_above_threshold(Severity.MEDIUM) is True
    assert s.is_above_threshold(Severity.LOW) is False
    assert s.is_above_threshold(Severity.INFO) is False


def test_path_glob_filters_apply(tmp_path: Path) -> None:
    s = Settings.model_validate({"exclude_paths": ["**/vendor/**", "**/*.lock"]})
    assert s.path_included("src/auth.py") is True
    assert s.path_included("vendor/lib/foo.py") is False
    assert s.path_included("uv.lock") is False
