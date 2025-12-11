# pr-review-agent

> Multi-agent pull-request reviewer built on LangGraph. Specialist agents (security, performance, tests, quality) review a PR in parallel; a supervisor synthesizes a structured, severity-ranked review comment.

Ships as a **GitHub Action**, a **CLI**, and a **Python library**. Model-agnostic — runs against OpenAI, Anthropic, or any OpenAI-compatible endpoint (Ollama, vLLM, internal gateway). Open-source, self-hostable, no data egress.

[![CI](https://github.com/sukhrobnurali/pr-review-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/sukhrobnurali/pr-review-agent/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python: 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)

## How it works

```
            diff + PR metadata
                    │
                    ▼
          ┌───────────────────┐
          │     supervisor    │  picks specialists from
          │  (path + keyword  │  enabled registry; quality
          │     heuristics)   │  + tests always run
          └────────┬──────────┘
                   │ selected
                   ▼
       ┌───────────┴───────────┐
       │   parallel fan-out    │
       ▼     ▼     ▼     ▼
   Quality Tests Perf Security    each returns findings + cost
       └─────┴─────┴─────┘
                   │
                   ▼
          ┌───────────────────┐
          │  dedup + rank by  │
          │     severity      │
          └────────┬──────────┘
                   │
                   ▼
          ┌───────────────────┐
          │  compose markdown │
          │  + post (or       │  idempotent via
          │  update) comment  │  <!-- pr-review-agent:run --> marker
          └───────────────────┘
```

Specialist scoping is enforced in the prompt — the security agent doesn't comment on naming, the quality agent doesn't comment on N+1 queries. Parallel fan-out keeps the wall-clock floor at one slow call, not four.

## Quick start

### Drop into a repo as a GitHub Action

```yaml
# .github/workflows/pr-review.yml
name: PR Review
on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: sukhrobnurali/pr-review-agent@v0.1.0
        with:
          provider: openai
          model: gpt-4o-mini
          api_key: ${{ secrets.OPENAI_API_KEY }}
```

That's it — the bot reviews every PR open / sync, posts a single comment, updates it on subsequent pushes.

### CLI

```bash
pip install pr-review-agent
export OPENAI_API_KEY=sk-...
export GITHUB_TOKEN=ghp-...

pr-review-agent review acme/widgets#42                # post the review
pr-review-agent review acme/widgets#42 --dry-run      # print, don't post
pr-review-agent review --diff-file change.patch       # local, no GitHub call
```

More recipes in [`examples/cli-usage.md`](examples/cli-usage.md).

### Library

```python
import asyncio
from pr_review_agent import review_pr

async def main():
    out = await review_pr("acme/widgets#42")
    print(out.final_comment)
    print(f"cost: ${out.cost_usd:.4f}")

asyncio.run(main())
```

Full example: [`examples/library-usage.py`](examples/library-usage.py).

## Why another PR reviewer

| | |
|---|---|
| **CodeRabbit / Greptile / Bito / Qodo** | Closed SaaS. Code leaves your network. Most enterprises can't ship to a third party. |
| **Generic "GPT review" Actions** | Single-prompt, one specialist's worth of attention spread across every concern. Output reads as filler. |
| **GitHub Copilot review** | Microsoft-hosted, opinionated, can't be steered. |
| **Claude Code / Cursor** | Interactive, editor-side. Don't run unattended on PRs. |
| **`pr-review-agent`** | Open-source, self-hosted, multi-agent, model-agnostic. Works with local models for air-gapped use. |

The architecture is the differentiator. Four specialists in parallel produce far better signal than one prompt asked to do everything — and the prompts are flat Markdown files you can iterate on without touching code.

## Cost & latency

Per-review cost depends on the diff size and which models the supervisor selects. The hard ceiling is enforced in CI: a 500-line synthetic PR fanned out across all four specialists must come in under **$0.50** and **90 seconds**, parametrized over OpenAI / Anthropic / Ollama — see [`tests/integration/test_cost_under_cap.py`](tests/integration/test_cost_under_cap.py).

In practice the cost is dominated by input tokens (the diff itself), so a small PR on `gpt-4o-mini` is typically a fraction of a cent. The composer renders the actual cost in the comment footer of every review, so the number is never hidden.

Wall-clock latency is bounded by the slowest single specialist call rather than the sum, because the four agents fan out in parallel — see [architecture.md → graph](docs/architecture.md#graph) and [`tests/integration/test_parallel_fanout.py`](tests/integration/test_parallel_fanout.py).

## Configuration

Drop a `.pr-review.yml` at your repo root:

```yaml
provider: openai
model: gpt-4o-mini

agents:
  enabled: [quality, tests, performance, security]
  models:
    security: gpt-4o   # use a smarter model where false positives hurt most

severity_threshold: medium
include_paths: ["**/*"]
exclude_paths: ["vendor/**", "**/*.generated.*"]
```

Full schema: [`docs/configuration.md`](docs/configuration.md).

## Documentation

| | |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | how the graph, supervisor, agents, cache, and reporter fit together |
| [`docs/agents.md`](docs/agents.md) | per-specialist scope, severity calibration, supervisor selection rules |
| [`docs/configuration.md`](docs/configuration.md) | full `.pr-review.yml` reference, provider switching, path filters |
| [`docs/prompts.md`](docs/prompts.md) | prompt format, output schema, iteration recipe |
| [`docs/benchmarks.md`](docs/benchmarks.md) | eval methodology and v0.1.0 baseline numbers |
| [`docs/decisions/`](docs/decisions/) | architectural decision records |

## Hacking

```bash
git clone https://github.com/sukhrobnurali/pr-review-agent
cd pr-review-agent
uv sync --extra dev

uv run pytest                  # full suite (incl. eval benchmark)
uv run pytest -m "not eval"    # fast loop
uv run pytest -m eval -s       # benchmark with per-fixture report
uv run ruff check
uv run mypy src/
```

Adding a new specialist takes ~6 lines of Python plus a prompt — see [`docs/agents.md` → Adding a specialist](docs/agents.md#adding-a-specialist).

## License

[Apache 2.0](LICENSE). Patent grant matters for code-touching tools.
