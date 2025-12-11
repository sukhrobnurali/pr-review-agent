# Configuration

`pr-review-agent` reads its config from a `.pr-review.yml` file at the repo root (path overridable via `--config` / `INPUT_CONFIG_PATH`). Anything in the file can also be overridden by CLI flags or Action inputs.

## Schema

```yaml
# All fields are optional; defaults shown.

provider: openai                  # openai | anthropic
model: gpt-4o-mini                # default model used by every agent
                                  # unless `agents.models` overrides
api_key: null                     # else $OPENAI_API_KEY / $ANTHROPIC_API_KEY
base_url: null                    # for OpenAI-compatible endpoints (Ollama, Together, …)

agents:
  enabled: [quality, tests, performance, security]
  models:
    security: gpt-4o              # per-agent override (optional)

severity_threshold: low           # findings below this dropped before posting
                                  # (info | low | medium | high | critical)
include_paths: ["**/*"]           # globs; anything not matching is skipped
exclude_paths: []                 # globs to subtract from include_paths
max_diff_size: 8000               # truncate diff above this many lines
cost_cap_usd: 0.50                # advisory; reported in logs
```

The schema is a Pydantic model — see [`src/pr_review_agent/config.py`](../src/pr_review_agent/config.py). Unknown keys are rejected (`extra="forbid"`), so typos surface immediately.

## Path filters

`include_paths` and `exclude_paths` use a small glob:

| pattern | matches |
|---|---|
| `**/*` | every file |
| `**/*.py` | any Python file under any directory |
| `src/**` | anything inside `src/` |
| `*.md` | top-level Markdown files only |
| `?` | single character |

A file is included iff it matches at least one `include_paths` pattern AND no `exclude_paths` pattern. Useful for skipping vendored code, generated files, or the `tests/` tree.

## Provider

```yaml
provider: openai
model: gpt-4o-mini
```

```yaml
provider: anthropic
model: claude-haiku-4
```

```yaml
# Local Ollama or any OpenAI-compatible API
provider: openai
model: llama3.1:70b-instruct
base_url: http://localhost:11434/v1
api_key: ollama  # placeholder; required by the SDK but not validated by Ollama
```

## Per-agent model overrides

Run security on a smarter (more expensive) model and the others on a cheap one:

```yaml
provider: openai
model: gpt-4o-mini
agents:
  models:
    security: gpt-4o
```

The pricing table at [`src/pr_review_agent/models/pricing.py`](../src/pr_review_agent/models/pricing.py) covers common OpenAI and Anthropic models. Unknown models fall back to `(1.00, 5.00)` USD per 1M tokens — a deliberately pessimistic default so cost reporting doesn't silently under-count.

## Disabling an agent

```yaml
agents:
  enabled: [quality, tests]   # security and performance won't run
```

The supervisor only ever picks from the enabled list, so disabling is the right knob if you don't want a specialist to fire even when its hints match.

You can also disable per-invocation:

```bash
pr-review-agent review acme/widgets#42 --only quality,tests
```

## Severity threshold

```yaml
severity_threshold: medium
```

Drops `info` and `low` findings before composing the comment. `info`/`low` are typically too small to act on in a PR review, but available for callers who want full data via the library API (`outcome.aggregated` ignores the threshold).

## Caching

The cache is **off by default**. Enable per-invocation with a path:

```bash
pr-review-agent review acme/widgets#42 --cache-dir .pr-cache
```

```yaml
# .github/workflows/pr-review.yml
- uses: sukhrobnurali/pr-review-agent@v0.1.0
  with:
    cache_dir: ${{ runner.temp }}/pr-cache
```

In CI, pair with `actions/cache` keyed on something stable (e.g. a hash of `prompts/`):

```yaml
- uses: actions/cache@v4
  with:
    path: ${{ runner.temp }}/pr-cache
    key: pr-review-${{ hashFiles('prompts/*.md') }}
- uses: sukhrobnurali/pr-review-agent@v0.1.0
  with:
    cache_dir: ${{ runner.temp }}/pr-cache
```

See [architecture.md → Caching](architecture.md#caching) for what's cached and how invalidation works.

## Resolving precedence

When a setting can be specified in multiple places, the order is:

1. CLI flag / Action input (highest priority)
2. `.pr-review.yml`
3. Built-in default

So a `--model gpt-4o` flag overrides the YAML's `model:` line, which overrides the default `gpt-4o-mini`.
