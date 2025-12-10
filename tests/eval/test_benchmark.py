"""End-to-end benchmark over labelled PR fixtures.

Run with `pytest -m eval` to include this; default `pytest` skips it via
`-m "not eval"`. Asserts soft thresholds: regressions print warnings to
stderr, only catastrophic numbers fail the test (precision < 0.5 or
recall < 0.5).
"""

from __future__ import annotations

import warnings

import pytest

from pr_review_agent.findings import AgentName, Finding
from pr_review_agent.graph import build_graph
from pr_review_agent.state import PRMetadata, ReviewState
from pr_review_agent.tools.git import parse_diff
from tests.eval.benchmark import (
    ALL_AGENTS,
    BenchmarkScore,
    Fixture,
    RecordedAgent,
    list_fixture_slugs,
    load_fixture,
    score_fixture,
)


@pytest.mark.eval
@pytest.mark.asyncio
async def test_benchmark_meets_soft_thresholds(capsys: pytest.CaptureFixture[str]) -> None:
    score = await _run_benchmark()
    _print_report(score)

    # Hard floor — anything below this is a regression worth failing on.
    assert score.precision >= 0.5, (
        f"precision {score.precision:.2f} below floor; review fixtures or prompts"
    )
    assert score.recall >= 0.5, (
        f"recall {score.recall:.2f} below floor; review fixtures or prompts"
    )

    # Soft floor — warn so flake doesn't break CI but the regression is visible.
    if score.precision < 0.85:
        warnings.warn(f"precision regressed to {score.precision:.2f}", stacklevel=2)
    if score.recall < 0.85:
        warnings.warn(f"recall regressed to {score.recall:.2f}", stacklevel=2)


async def _run_benchmark() -> BenchmarkScore:
    score = BenchmarkScore()
    for slug in list_fixture_slugs():
        fixture = load_fixture(slug)
        emitted = await _run_pipeline(fixture)
        score.fixtures.append(score_fixture(fixture, emitted))
    return score


async def _run_pipeline(fixture: Fixture) -> list[Finding]:
    agents: dict[AgentName, RecordedAgent] = {
        name: RecordedAgent(name, fixture.recorded.get(name, [])) for name in ALL_AGENTS
    }
    graph = build_graph(agents)  # type: ignore[arg-type]
    pr = PRMetadata(
        owner="bench",
        repo=fixture.slug,
        number=1,
        title=fixture.labels.title,
        head_sha="0" * 40,
        base_sha="0" * 40,
    )
    state: ReviewState = {
        "pr_metadata": pr,
        "diff": fixture.diff,
        "files_changed": parse_diff(fixture.diff),
    }
    out = await graph.ainvoke(state)
    return list(out.get("aggregated", []))


def _print_report(score: BenchmarkScore) -> None:
    lines = [
        "",
        "benchmark results",
        "=================",
        f"{'fixture':<28}{'emitted':>9}{'recall':>10}{'noise':>10}",
    ]
    for f in score.fixtures:
        recall = (
            f.must_catch_hit / f.must_catch_total if f.must_catch_total else 1.0
        )
        noise = (
            f.forbidden_hit / f.forbidden_total if f.forbidden_total else 0.0
        )
        lines.append(f"{f.slug:<28}{f.findings_emitted:>9}{recall:>10.2f}{noise:>10.2f}")
    lines.append(
        f"\noverall precision={score.precision:.3f} "
        f"recall={score.recall:.3f} "
        f"noise={score.noise_rate:.3f}"
    )
    print("\n".join(lines))
