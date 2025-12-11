# Agents

Four specialists, each scoped to a narrow concern. Scoping is enforced in the prompt — every agent's "you do not comment on" section explicitly hands off the other three concerns. This is what makes parallel fan-out tractable: agents don't double-flag the same issue from different angles, so deduplication is mostly a same-line / same-title check.

| agent | concern | default model |
|---|---|---|
| Quality | naming, readability, dead code, leaky abstractions | `gpt-4o-mini` (fast tier) |
| Tests | missing coverage on new behaviour, brittle assertions, untested branches | `gpt-4o-mini` (reasoning helps but cheap is OK) |
| Performance | per-row queries, allocations in hot loops, missing indexes | `gpt-4o-mini` (fast tier) |
| Security | input validation, deserialization, secret handling, authz boundaries | `gpt-4o` (precision matters; FP cost is high) |

Override defaults in `.pr-review.yml`:

```yaml
provider: openai
agents:
  enabled: [quality, tests, performance, security]
  models:
    security: gpt-4o
    quality: gpt-4o-mini
    tests: gpt-4o-mini
    performance: gpt-4o-mini
```

## Quality

[`prompts/quality.md`](../prompts/quality.md). Looks for:

- naming that misleads or obscures intent
- readability problems: dense, deeply nested, hard-to-follow blocks
- functions / classes that have grown past comprehension
- dead code: unreachable branches, unused imports/variables/functions
- non-idiomatic patterns for the language
- leaky abstractions: implementation details bleeding across module boundaries

Skips: anything a linter catches, subjective style, "consider a comment" filler.

The prompt explicitly says to drop borderline findings — quality noise trains reviewers to ignore the bot.

## Tests

[`prompts/tests.md`](../prompts/tests.md). Looks for:

- new behaviour added without a test
- changed behaviour without an updated test
- assertions that pass trivially (e.g., asserting a mock's return value)
- branches in production code that have no test path

Skips: test naming, test organization, suggesting more tests "for safety". The threshold is "is this *behaviour change* untested?".

## Performance

[`prompts/performance.md`](../prompts/performance.md). Looks for:

- N+1 query patterns (per-row `.get()` / `.fetch()`)
- O(n²) where O(n) reads obviously fine
- allocations in hot loops
- blocking I/O in async paths
- missing pagination on unbounded queries

Skips: micro-optimizations, premature concerns about not-yet-measured code.

## Security

[`prompts/security.md`](../prompts/security.md). Looks for:

- insecure deserialization (`pickle`, `yaml.load` without `SafeLoader`, `eval(...)`)
- SQL/command injection from string-built queries
- hardcoded secrets, tokens, credentials in changed lines
- weak crypto (MD5, plain `random` for tokens)
- authz / tenancy boundary violations
- subprocess invocations with `shell=True` over user input

Skips: speculative threats not present in the diff, OWASP top-10 topics that don't actually appear, "use HTTPS" filler. Highest false-positive risk among the four — the prompt is the most conservative.

## Supervisor selection

The supervisor in [`agents/supervisor.py`](../src/pr_review_agent/agents/supervisor.py) decides which specialists run on a given diff:

| agent | always? | trigger |
|---|---|---|
| Quality | yes | every PR |
| Tests | yes | every PR |
| Performance | no | path matches `models/`, `db/`, `database/`, `api/`, `queries/`, `cache/`, **or** diff contains loop / DB / async hints |
| Security | no | path matches `auth/`, `security/`, `crypto/`, `login/`, `password/`, `secrets/`, **or** diff contains hint keywords (`pickle.loads`, `eval(`, `subprocess.run`, `shell=true`, `password`, `api_key`, …) |

The hint lists are intentionally explicit — easier to extend, easier to audit. `select_specialists()` is unit-tested in [`tests/unit/test_supervisor_selection.py`](../tests/unit/test_supervisor_selection.py).

## Adding a specialist

1. Write the prompt at `prompts/<name>.md` following the existing convention (PR section, output schema, severity guidance).
2. Add the `AgentName` literal in [`findings/schema.py`](../src/pr_review_agent/findings/schema.py).
3. Implement `build_<name>_agent(llm, model_id) -> SpecialistAgent` in `agents/<name>.py` (mirror the existing four — they're 5 lines each).
4. Re-export from [`agents/__init__.py`](../src/pr_review_agent/agents/__init__.py).
5. Wire into the `_BUILDERS` table in [`_runner.py`](../src/pr_review_agent/_runner.py).
6. If the agent is heuristic (not always-on), add path/keyword hints to the supervisor.

The graph picks up new entries from the registry; you don't need to edit `graph.py` or LangGraph wiring.
