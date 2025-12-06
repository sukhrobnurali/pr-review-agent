from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import UndefinedError

from pr_review_agent.agents.prompts import render_prompt


@pytest.fixture
def tmp_prompts(tmp_path: Path) -> Path:
    (tmp_path / "test_agent.md").write_text(
        "Hello {{ name }}, your PR is {{ pr_title }}.\n", encoding="utf-8"
    )
    return tmp_path


def test_render_basic(tmp_prompts: Path) -> None:
    out = render_prompt(
        "test_agent",
        {"name": "Alex", "pr_title": "Fix bug"},
        prompts_dir=tmp_prompts,
    )
    assert "Hello Alex, your PR is Fix bug." in out


def test_missing_template_raises(tmp_prompts: Path) -> None:
    with pytest.raises(FileNotFoundError):
        render_prompt("nonexistent", {}, prompts_dir=tmp_prompts)


def test_missing_variable_raises(tmp_prompts: Path) -> None:
    with pytest.raises(UndefinedError):
        render_prompt("test_agent", {"name": "Alex"}, prompts_dir=tmp_prompts)
