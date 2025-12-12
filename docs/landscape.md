# Landscape (as of Dec 2025)

Snapshot of what the AI-PR-review space looks like at the time `pr-review-agent`
was designed. Re-survey before any major release; this category moves quickly.

## Closed SaaS

| Tool | Stance | Notes |
|---|---|---|
| **CodeRabbit** | Polished SaaS | Most-cited reference. Strong UX, codebase-aware, posts inline + summary comments. Closed model selection, code leaves the network. |
| **Greptile** | SaaS | Codebase-graph driven, claims fewer false positives. Closed, opinionated, no self-host. |
| **Bito** | SaaS | Generalist AI dev assistant; PR review is one surface. Closed. |
| **Qodo** (formerly Codium PR-Agent) | Hybrid | Has an open-source core (PR-Agent on GitHub) plus a closed SaaS layer; the OSS piece is single-agent oriented. |
| **GitHub Copilot Code Review** | First-party SaaS | Microsoft-hosted, opinionated, can't be steered or self-hosted. Free for some plans, which raises the floor for "good enough" reviews. |

The closed-SaaS group is the obvious commercial market. None of them are an
option for orgs that can't ship code to a third party.

## Open-source / self-hostable

| Tool | Architecture | Gap relative to `pr-review-agent` |
|---|---|---|
| **Codium PR-Agent** | Single-agent, prompt-engineered, multi-command | Not multi-agent; one prompt asked to handle every concern. Strong CLI ergonomics; prompts are not the focal artifact. |
| **`reviewdog`** | Linter aggregator | Orthogonal: posts deterministic linter output, not LLM judgement. Pairs with this project rather than competing. |
| **GitHub Action: "GPT review my PR"** (~dozens) | Single-call wrappers | Send-diff-to-GPT-and-paste-comment. Output reads as filler. The category is the cautionary tale this project is reacting to. |
| **AutoCodeRover / SWE-agent** | Research/agentic | Aimed at autonomous bug-fix benchmarks (SWE-bench), not PR review as a workflow. Different problem. |

## Editor-side, not async

| Tool | Why excluded |
|---|---|
| **Claude Code, Cursor, Aider** | Interactive, run in the developer's editor. Don't post on PR open/sync without bespoke glue. Different surface. |

## Where this project fits

The hole in the matrix: **open-source, self-hostable, multi-agent, model-agnostic.**

- Self-hosted defaults; no SaaS, no telemetry.
- Four parallel specialists (quality / tests / performance / security) instead of one generalist prompt - the architectural bet is that specialization beats prompt-stuffing on signal-to-noise.
- Prompts are first-class `.md` files; iterating doesn't require touching code.
- Runs against any OpenAI / Anthropic / OpenAI-compatible endpoint, including local models for air-gapped use.

## What to re-check before each release

- Has CodeRabbit shipped a self-host tier? (Closes the closest gap.)
- Has GitHub Copilot Code Review opened up steering / config? (Raises the floor.)
- Has Codium PR-Agent moved to a multi-agent design? (Direct overlap.)
- New entrants on the GitHub Marketplace - search "pr review", "code review ai".
- LangChain / LangGraph blog: are they featuring a different reference reviewer?

If a new entrant matches three of the four bullets above (open, self-host,
multi-agent, model-agnostic), the differentiation thesis needs a rewrite, not
just a README tweak.
