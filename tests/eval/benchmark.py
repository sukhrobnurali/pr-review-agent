"""Eval-benchmark scaffolding.

Each fixture under `tests/fixtures/sample_prs/<slug>/` is:

    diff.patch          — the unified diff fed into the graph
    expected.yaml       — must_catch / must_not_catch label rules
    recorded/<agent>.yaml — what the agent produced in a recorded run

The benchmark builds `RecordedAgent` instances out of the recorded YAMLs,
runs them through the production graph, then scores aggregated findings
against the labels. Numbers are stable across machines because no LLM is
called.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pr_review_agent.agents.base import AgentResult
from pr_review_agent.findings import AgentName, FileLocation, Finding, Severity

FIXTURES_ROOT = Path(__file__).parent.parent / "fixtures" / "sample_prs"
ALL_AGENTS: tuple[AgentName, ...] = ("quality", "tests", "performance", "security")


@dataclass(frozen=True)
class LabelRule:
    severity_min: Severity = Severity.INFO
    file_pattern: str = ""
    title_keywords: tuple[str, ...] = ()

    def matches(self, finding: Finding) -> bool:
        if finding.severity < self.severity_min:
            return False
        if self.file_pattern and self.file_pattern not in finding.location.path:
            return False
        if self.title_keywords:
            haystack = finding.title.lower()
            return any(kw.lower() in haystack for kw in self.title_keywords)
        return True


@dataclass(frozen=True)
class FixtureLabels:
    title: str
    must_catch: tuple[LabelRule, ...]
    must_not_catch: tuple[LabelRule, ...]


@dataclass(frozen=True)
class Fixture:
    slug: str
    diff: str
    labels: FixtureLabels
    recorded: dict[AgentName, list[Finding]]


@dataclass
class FixtureScore:
    slug: str
    must_catch_total: int
    must_catch_hit: int
    forbidden_total: int
    forbidden_hit: int
    findings_emitted: int


@dataclass
class BenchmarkScore:
    fixtures: list[FixtureScore] = field(default_factory=list)

    @property
    def precision(self) -> float:
        emitted = sum(f.findings_emitted for f in self.fixtures)
        if emitted == 0:
            return 1.0
        bad = sum(f.forbidden_hit for f in self.fixtures)
        return max(0.0, (emitted - bad) / emitted)

    @property
    def recall(self) -> float:
        total = sum(f.must_catch_total for f in self.fixtures)
        if total == 0:
            return 1.0
        return sum(f.must_catch_hit for f in self.fixtures) / total

    @property
    def noise_rate(self) -> float:
        return 1.0 - self.precision


def load_fixture(slug: str) -> Fixture:
    root = FIXTURES_ROOT / slug
    diff = (root / "diff.patch").read_text(encoding="utf-8")
    raw_labels = yaml.safe_load((root / "expected.yaml").read_text(encoding="utf-8"))
    labels = FixtureLabels(
        title=raw_labels.get("title", slug),
        must_catch=tuple(_rules(raw_labels.get("must_catch") or [])),
        must_not_catch=tuple(_rules(raw_labels.get("must_not_catch") or [])),
    )

    recorded: dict[AgentName, list[Finding]] = {}
    for agent in ALL_AGENTS:
        path = root / "recorded" / f"{agent}.yaml"
        recorded[agent] = list(_load_recorded(path, agent)) if path.exists() else []
    return Fixture(slug=slug, diff=diff, labels=labels, recorded=recorded)


def list_fixture_slugs() -> list[str]:
    return sorted(p.name for p in FIXTURES_ROOT.iterdir() if p.is_dir())


def _rules(raw: list[dict[str, object]]) -> list[LabelRule]:
    out: list[LabelRule] = []
    for entry in raw:
        sev = entry.get("severity_min", "info")
        out.append(
            LabelRule(
                severity_min=Severity(str(sev).lower()),
                file_pattern=str(entry.get("file_pattern", "")),
                title_keywords=tuple(entry.get("title_keywords") or ()),
            )
        )
    return out


def _load_recorded(path: Path, agent: AgentName) -> list[Finding]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[Finding] = []
    for entry in raw.get("findings", []) or []:
        out.append(
            Finding(
                severity=Severity(str(entry["severity"]).lower()),
                location=FileLocation(
                    path=str(entry["file"]),
                    line=int(entry["line"]),
                    end_line=entry.get("end_line"),
                ),
                agent=agent,
                title=str(entry["title"]),
                explanation=str(entry["explanation"]),
                suggestion=entry.get("suggestion"),
            )
        )
    return out


class RecordedAgent:
    """AgentRunnable substitute that returns canned recorded findings."""

    def __init__(self, agent_name: AgentName, recorded: list[Finding]) -> None:
        self.agent_name = agent_name
        self.prompt_name = agent_name
        self.model_id = "recorded"
        self._recorded = recorded

    async def run(self, pr: object, files_changed: object, diff: object) -> AgentResult:
        return AgentResult(
            findings=list(self._recorded),
            cost_usd=0.0,
            prompt_tokens=0,
            completion_tokens=0,
        )


def score_fixture(fixture: Fixture, emitted: list[Finding]) -> FixtureScore:
    must_catch_hit = sum(
        1 for rule in fixture.labels.must_catch if any(rule.matches(f) for f in emitted)
    )
    forbidden_hit = sum(
        1 for rule in fixture.labels.must_not_catch if any(rule.matches(f) for f in emitted)
    )
    return FixtureScore(
        slug=fixture.slug,
        must_catch_total=len(fixture.labels.must_catch),
        must_catch_hit=must_catch_hit,
        forbidden_total=len(fixture.labels.must_not_catch),
        forbidden_hit=forbidden_hit,
        findings_emitted=len(emitted),
    )
