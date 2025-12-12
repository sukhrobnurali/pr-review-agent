# Changelog

## v0.1.0 - 2025-12-12

First release.

### Added

- Four specialist agents (quality, tests, performance, security) returning
  structured `Finding[]` lists.
- LangGraph supervisor + parallel fan-out + aggregator + composer pipeline.
- Severity-ranked Markdown comment with cost / token footer.
- Three integration modes: GitHub Action (Docker), CLI (`pr-review-agent review`),
  Python library (`from pr_review_agent import review_pr`).
- Model-agnostic provider layer (OpenAI, Anthropic, any OpenAI-compatible
  endpoint via `base_url`).
- File-backed agent-result cache, keyed on `sha256(repo + file_blob_sha + agent
  + model + prompt_version)`.
- Idempotent PR comment via `<!-- pr-review-agent:run -->` HTML marker - first
  run posts, later runs update.
- `.pr-review.yml` config with path filters, per-agent model overrides, severity
  threshold, agent enable list.
- Path-traversal guard on the `read_file` tool.
- Eval benchmark scaffold under `tests/eval/` with five hand-labelled fixtures.
- 500-line synthetic-PR cost+latency cap test parametrised over OpenAI,
  Anthropic, Ollama (under $0.50, under 90s).
- Self-review workflow at `.github/workflows/self-review.yml` - the agent
  reviews this repo's own PRs.
- Docs: architecture, agents, configuration, prompts, benchmarks, landscape.

### Known limitations

- Agents only consume the diff plus on-demand `read_file`; no full repo
  embedding / graph context.
- Severity calibration is prompt-driven and noisier on the security agent than
  the others; per-agent threshold knobs land in 0.2.
- Eval set is five fixtures - representative, not exhaustive. Will grow with
  contributed PRs.
- No inline review comments yet; one summary comment per PR.
