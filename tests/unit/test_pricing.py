from __future__ import annotations

from pr_review_agent.models.pricing import compute_cost_usd


def test_known_model_gpt_4o_mini() -> None:
    cost = compute_cost_usd("gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=0)
    assert cost == 0.15


def test_known_model_gpt_4o_input_and_output() -> None:
    cost = compute_cost_usd("gpt-4o", prompt_tokens=500_000, completion_tokens=100_000)
    assert cost == (0.5 * 2.50) + (0.1 * 10.00)


def test_known_model_claude_sonnet() -> None:
    cost = compute_cost_usd("claude-sonnet-4", prompt_tokens=2_000_000, completion_tokens=500_000)
    assert cost == (2 * 3.00) + (0.5 * 15.00)


def test_zero_tokens() -> None:
    assert compute_cost_usd("gpt-4o", 0, 0) == 0.0


def test_unknown_model_falls_back() -> None:
    unknown = compute_cost_usd("unknown-model-x", prompt_tokens=1_000_000, completion_tokens=0)
    fallback = compute_cost_usd("not-here-either", prompt_tokens=1_000_000, completion_tokens=0)
    assert unknown == fallback
    assert unknown == 1.00
