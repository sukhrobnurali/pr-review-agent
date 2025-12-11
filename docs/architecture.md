# Architecture

`pr-review-agent` is built around four ideas:

1. A small, frozen `Finding` model that everything downstream depends on.
2. Independent specialist agents that produce findings in parallel.
3. A LangGraph state graph that fans out, aggregates, and composes the comment.
4. A reporter that posts (or updates) a single PR comment marked with an HTML sentinel.

```
┌────────────────────────────────────────────────────────────────────┐
│                          GitHubClient.fetch_*                      │
│   PRMetadata + diff text                                           │
└───────────────────────────┬────────────────────────────────────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │  parse_diff (git.py) │
                 │  → list[FileChange] │
                 └──────────┬──────────┘
                            │
                            ▼
                ┌─────────────────────────┐
                │   supervisor.select_…   │   table-driven over the
                │   (heuristic + paths)   │   *enabled* registry
                └──────────┬──────────────┘
                           │ selected_agents
                           ▼
        ┌──────────────────┴──────────────────┐
        │                  fan-out (parallel)  │
        ▼              ▼                ▼          ▼
  ┌──────────┐   ┌──────────┐   ┌────────────┐  ┌──────────┐
  │ Quality  │   │  Tests   │   │Performance │  │ Security │
  │  agent   │   │  agent   │   │  agent     │  │  agent   │
  └────┬─────┘   └────┬─────┘   └─────┬──────┘  └────┬─────┘
       │              │               │              │
       └──────────────┴───────────────┴──────────────┘
                            │ findings + cost
                            ▼
                ┌──────────────────────┐
                │  aggregate (dedup +  │
                │  rank by severity)   │
                └──────────┬───────────┘
                           │ aggregated
                           ▼
                ┌──────────────────────┐
                │  compose_markdown    │
                │  → final_comment     │
                └──────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────────┐
              │  post_or_update_review     │
              │  (idempotent via marker)   │
              └────────────────────────────┘
```

## State

[`src/pr_review_agent/state.py`](../src/pr_review_agent/state.py) defines a `TypedDict` `ReviewState` that flows through the graph. Two reducers make parallel fan-out safe:

- `merge_findings` — merges per-agent finding lists by agent name; the graph's parallel branches each emit `{"findings": {agent: [...]}}` and the reducer joins them.
- `add_floats` — sums `cost_usd` contributions across branches.

Without these, two branches updating the same key would race on commit; with them, LangGraph applies them atomically per super-step.

## Agents

Every specialist implements [`AgentRunnable`](../src/pr_review_agent/agents/base.py):

```python
class AgentRunnable(Protocol):
    agent_name: AgentName
    async def run(self, pr, files_changed, diff) -> AgentResult: ...
```

`SpecialistAgent` is the LLM-backed implementation. It renders a prompt template with PR context, calls the model, parses the JSON response, and computes cost from the model's usage metadata. `CachingAgent` (in `cache/wrapper.py`) wraps any `AgentRunnable` with on-disk caching keyed per [ADR-0008](decisions/0001-multi-agent-architecture.md#cache).

The Protocol is the integration point — recorded fixtures, stubs, and the cache wrapper all satisfy it without inheritance.

## Supervisor

[`agents/supervisor.py`](../src/pr_review_agent/agents/supervisor.py) is a pure function over file paths and diff content. It returns a list of `AgentName`s. Two design choices:

- **Quality and Tests are always selected.** They're cheap and apply to almost every PR.
- **Security and Performance are heuristic.** Path patterns (`auth/`, `db/`) and keyword hints (`pickle`, `eval(`, `for `, `await`) drive selection. The lists are explicit and easy to extend.

The `available=` filter respects `settings.agents.enabled` so users can disable an agent globally without touching supervisor code.

## Graph

[`graph.py`](../src/pr_review_agent/graph.py) wires entry → select → (fan-out) → aggregate → compose → END. Failure isolation: if an agent's `run()` raises, the node returns `{"errors": [AgentError(...)]}` instead of propagating; other agents proceed and the final comment renders without the failing one.

## Caching

[`cache/`](../src/pr_review_agent/cache/) is opt-in. When enabled:

- Key per agent: `sha256(repo_id | head_sha | agent | model | prompt_version)`.
- `prompt_version` is a hash of the prompt template — editing a prompt invalidates entries that used the old one.
- Storage is content-addressed JSON under a sharded directory (`<root>/<2-char prefix>/<key>.json`).
- Cache hits return `cost_usd=0.0` (the cost was paid on the original call).

The cache is wired through CLI (`--cache-dir`), Action (`cache_dir` input), and library (`cache=` arg). It's never on by default — the user opts in with a path.

## Reporting

[`reporting/github_review.py`](../src/pr_review_agent/reporting/github_review.py) keeps the PR conversation clean by appending `<!-- pr-review-agent:run -->` to every comment and looking for that marker before posting. If found, it edits the existing comment in place; otherwise it posts a new one. Re-running on the same PR overwrites, not duplicates.

## Cost & latency

Per-agent cost is computed inline in `SpecialistAgent.run` from the LLM's `usage_metadata` and the project's pricing table ([`models/pricing.py`](../src/pr_review_agent/models/pricing.py)). The graph's `add_floats` reducer sums those into the state's `cost_usd`. The composer renders the total in the comment footer.

Latency stays bounded by parallel fan-out: four agents run concurrently, so the wall-clock floor is roughly the slowest single call, not the sum. [`tests/integration/test_cost_under_cap.py`](../tests/integration/test_cost_under_cap.py) gates this at <$0.50 and <90s for a 500-line synthetic PR across all three supported providers.
