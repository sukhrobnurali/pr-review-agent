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

The test asserts a hard floor (precision ≥ 0.5, recall ≥ 0.5) and warns at a soft floor (< 0.85) — it never silently passes through a regression, but a single fixture authoring mistake doesn't break CI.

## v0.1.0 baseline

```
fixture                       emitted    recall     noise
01-pickle-cve                       3      1.00      0.00
02-n-plus-one                       4      1.00      0.00
03-untested-feature                 2      1.00      0.00
04-quality-smell                    5      1.00      0.00
05-clean-control                    0      1.00      0.00

overall precision=1.000 recall=1.000 noise=0.000
```

These numbers come from running `pytest -m eval -s` against the v0.1.0 fixtures. Both `must_catch` and `must_not_catch` are tight enough to break if recordings drift.

The numbers are clean by construction — they reflect the framework working against curated recordings, not a generalised "reviewer skill" claim. Two extensions that bring them closer to that claim:

1. **Replay against a real model.** Drop the `RecordedAgent`, point the eval at a real provider with cassettes, and re-record. The framework is unchanged; only the recording source moves. This is the work that backs ADR-0001 (`docs/decisions/0001-multi-agent-architecture.md`).
2. **Adversarial fixtures.** Add diffs that *look* like they should trip an agent but shouldn't, plus diffs that the agent has historically missed. `must_not_catch` is where most of the signal lives — that's the noise floor.

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
