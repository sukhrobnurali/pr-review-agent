# pr-review-agent

Multi-agent pull request reviewer built on LangGraph.

Specialist agents (security / performance / tests / quality) review a PR in
parallel; a supervisor synthesizes a structured, severity-ranked review
comment. Ships as a GitHub Action, a CLI, and a Python library.
Model-agnostic (OpenAI, Anthropic, OpenAI-compatible).

Status: WIP, pre-release.
