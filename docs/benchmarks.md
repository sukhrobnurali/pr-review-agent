# Benchmarks

How `pr-review-agent` measures itself, and the v0.1.0 baseline numbers.

## Methodology

Each labelled fixture under [`tests/fixtures/sample_prs/`](../tests/fixtures/sample_prs/) has:

- `diff.patch` — the unified diff fed into the graph
- `expected.yaml` — `must_catch` rules (the agent should produce findings matching these) and `must_not_catch` rules (the agent should not)
- `recorded/<agent>.yaml` — the findings each specialist produced in a recorded run

The benchmark wires up `RecordedAgent` instances from those YAMLs, runs them through the production graph (same `select → dispatch → aggregate → compose` pipeline used at runtime), and scores aggregated findings against the rules.

This means numbers are **reproducible across machines, across runs, with no LLM calls** — the recorded YAMLs are the LLM stand-in. New fixtures land with a fresh recording captured against whichever model the project ships against.

Three metrics are tracked:

| metric | definition |
|---|---|
| **recall** | fraction of `must_catch` rules satisfied across all fixtures |
| **precision** | (emitted − forbidden_hit) / emitted |
| **noise rate** | `1 − precision` — how often the agent flagged something it shouldn't |

## How to run

```bash
pytest -m eval -s
```

The `-s` keeps the per-fixture report visible. The benchmark is also part of the default suite, so `pytest` runs it too.

The test asserts a smoke-level invariant — every fixture loads, runs through the graph, and produces output. It does **not** assert precision/recall floors, because in v0.1.0 the recorded findings are hand-authored alongside the rules they score against, so a floor would be tautological.

## v0.1.0 status: framework, not measurement

What ships today:

- 5 labelled fixtures covering the four specialist concerns plus a clean control.
- `RecordedAgent` and the rule-matching machinery, so adding a fixture is a YAML drop with no Python changes.
- A graph integration that swaps in `RecordedAgent` without touching production code.

What does **not** ship today: a real measurement of reviewer skill. The recordings under `recorded/<agent>.yaml` were written by the same hand that wrote the `expected.yaml` rules, so any score they produce reflects authoring consistency rather than agent quality.

Two paths bring real numbers in v0.2:

1. **Replay against a real model.** Drop `RecordedAgent`, run the production agents against the fixtures with cassettes, and commit the captured findings. The framework is unchanged; only the recording source moves. This is the work that backs ADR-0001.
2. **Adversarial fixtures.** Add diffs that *look* like they should trip an agent but shouldn't, plus diffs the agent has historically missed. `must_not_catch` is where most of the real signal lives — that's the noise floor.

## Fixture catalogue

| slug | scenario | primary specialist exercised |
|---|---|---|
| `01-pickle-cve` | session restore endpoint deserializes user-supplied pickle | security |
| `02-n-plus-one` | order summary regresses to per-row Item.query.get | performance |
| `03-untested-feature` | new billing module ships with no tests | tests |
| `04-quality-smell` | report builder rewritten with cryptic names + dead code | quality |
| `05-clean-control` | small clean addition with tests; nothing to flag | (control) |

## Adding a fixture

```
tests/fixtures/sample_prs/<NN-slug>/
├── diff.patch
├── expected.yaml          # must_catch / must_not_catch rules
└── recorded/
    ├── quality.yaml
    ├── tests.yaml
    ├── performance.yaml
    └── security.yaml
```

Each `recorded/<agent>.yaml` is `findings: []` for agents the supervisor doesn't select on this diff. `expected.yaml` rules support three filters:

```yaml
must_catch:
  - severity_min: high            # findings below this severity ignored
    file_pattern: "sessions.py"   # substring match against location.path
    title_keywords: ["pickle"]    # any keyword (case-insensitive) in title
```

A `must_catch` rule "matches" if **any** emitted finding satisfies all three filters.
