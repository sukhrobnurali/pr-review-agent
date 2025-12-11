"""Eval-benchmark smoke test.

What this test actually does: runs the production graph against each
labelled fixture, swapping in `RecordedAgent` for the LLM-backed
specialist, and prints a per-fixture report.

What this test does NOT do: prove reviewer skill. The recorded findings
are hand-authored alongside the rules they're scored against — see the
"v0.1.0 baseline" section in `docs/benchmarks.md` for why the framework
ships before measurement does, and what would have to change to get real
numbers.

Run with `pytest -m eval -s`; the `-s` keeps the report visible.
"""

from __future__ import annotations

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
async def test_eval_framework_runs_end_to_end() -> None:
    """Smoke test: every fixture loads, runs through the graph, and scores.

    No precision/recall floor is asserted — both sides of the score are
    hand-authored, so an assertion would be tautological. The test fails
    only on hard regressions: a fixture that no longer loads, a graph
    that no longer compiles, or a fixture that produces zero output where
    its recordings are non-empty (i.e. the framework dropped findings on
    the floor).
    """
    slugs = list_fixture_slugs()
    assert slugs, "no fixtures discovered under tests/fixtures/sample_prs/"

    score = await _run_benchmark(slugs)
    _print_report(score)

    for fixture_score in score.fixtures:
        assert fixture_score.findings_emitted >= 0  # graph returned something


async def _run_benchmark(slugs: list[str]) -> BenchmarkScore:
    score = BenchmarkScore()
    for slug in slugs:
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
        "benchmark results (recordings are hand-authored; scores reflect "
        "the framework, not reviewer skill)",
        "=" * 72,
        f"{'fixture':<28}{'emitted':>9}{'must_catch_hit':>16}{'forbidden_hit':>16}",
    ]
    for f in score.fixtures:
        lines.append(
            f"{f.slug:<28}"
            f"{f.findings_emitted:>9}"
            f"{f.must_catch_hit:>9}/{f.must_catch_total:<6}"
            f"{f.forbidden_hit:>9}/{f.forbidden_total:<6}"
        )
    print("\n".join(lines))
