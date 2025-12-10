from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined

_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


@lru_cache(maxsize=8)
def _read_template(name: str, prompts_dir: str) -> str:
    path = Path(prompts_dir) / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def render_prompt(
    name: str,
    variables: dict[str, Any],
    prompts_dir: Path | None = None,
) -> str:
    base = prompts_dir if prompts_dir is not None else _DEFAULT_PROMPTS_DIR
    template_text = _read_template(name, str(base))
    env = Environment(undefined=StrictUndefined, autoescape=False)
    return env.from_string(template_text).render(**variables)


def prompt_version(name: str, prompts_dir: Path | None = None) -> str:
    """Stable short hash of a prompt template; cache key invalidates on edit."""
    base = prompts_dir if prompts_dir is not None else _DEFAULT_PROMPTS_DIR
    text = _read_template(name, str(base))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
