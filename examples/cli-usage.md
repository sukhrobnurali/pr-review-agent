# CLI examples

`pr-review-agent` is a single command (`review`) with a few flags. Below are the recipes you'll actually use.

## Install

```bash
pip install pr-review-agent
# or, with uv:
uv pip install pr-review-agent
```

## Review a real PR

```bash
export OPENAI_API_KEY=sk-...
export GITHUB_TOKEN=ghp-...

pr-review-agent review acme/widgets#42
```

This fetches the PR via the GitHub API, runs the review, and posts (or updates) the review comment. It also accepts a full URL:

```bash
pr-review-agent review https://github.com/acme/widgets/pull/42
```

## Dry run — print, don't post

```bash
pr-review-agent review acme/widgets#42 --dry-run
```

The Markdown comment goes to stdout; nothing is posted to the PR. Useful for trying prompt changes locally before they're visible to anyone else.

## Local diff (no GitHub call)

```bash
git diff main > /tmp/change.patch
pr-review-agent review --diff-file /tmp/change.patch --title "my change" --dry-run
```

`--diff-file` skips GitHub entirely. Pair with `--dry-run` so the runner doesn't try to post against the synthetic `local/local#1` PR coordinates.

## Switch providers

```bash
export ANTHROPIC_API_KEY=...
pr-review-agent review acme/widgets#42 \
  --provider anthropic --model claude-haiku-4
```

Or via `.pr-review.yml`:

```yaml
provider: anthropic
model: claude-haiku-4
```

For Ollama / OpenAI-compatible endpoints, set `base_url` in the YAML — see [docs/configuration.md](../docs/configuration.md).

## Run a subset of agents

```bash
pr-review-agent review acme/widgets#42 --only security,quality
```

Useful when you want to sanity-check a security-sensitive change without paying for the full fan-out. Agents not in `--only` don't fire even if the supervisor would have selected them.

## Enable on-disk cache

```bash
pr-review-agent review acme/widgets#42 --cache-dir ~/.cache/pr-review
```

Re-running on the same PR head SHA reuses the cached agent results — useful when iterating on the comment composer or aggregator without re-paying for LLM calls. See [docs/architecture.md → Caching](../docs/architecture.md#caching) for invalidation rules.

## Override config file path

```bash
pr-review-agent review acme/widgets#42 --config ./configs/strict.yml
```

By default the CLI looks for `./.pr-review.yml`. With `--config`, point at any path (relative or absolute).

## Override individual settings on the command line

CLI flags trump `.pr-review.yml`:

```bash
pr-review-agent review acme/widgets#42 \
  --provider openai \
  --model gpt-4o \
  --only security \
  --dry-run
```

## Environment variables

| variable | purpose |
|---|---|
| `OPENAI_API_KEY` | LLM key when `provider: openai` |
| `ANTHROPIC_API_KEY` | LLM key when `provider: anthropic` |
| `GITHUB_TOKEN` | API access for fetch + post (use `${{ github.token }}` in CI) |
| `PR_REVIEW_CACHE_DIR` | default cache root if `--cache-dir` not passed and `FileCache(None)` is used |

## Exit codes

| code | meaning |
|---|---|
| 0 | review completed (with or without findings) |
| 2 | bad inputs — missing API key, malformed PR ref, unknown agent in `--only` |
| 1 | runtime error — propagated as a Python exception |

The agent failing on a single specialist (e.g. one of four agents raises) does **not** make the CLI exit non-zero — the other three still produce findings, and the failure is reported in the structlog output and at the bottom of the printed comment.
