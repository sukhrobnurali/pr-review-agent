"""Run pr-review-agent as a Python library.

Usage:
    OPENAI_API_KEY=sk-... GITHUB_TOKEN=ghp-... python examples/library-usage.py acme/widgets#42

The whole call is 10 lines. Output is a Markdown comment string plus
metadata (cost, selected agents, finding count).
"""

from __future__ import annotations

import asyncio
import os
import sys

from pr_review_agent import Settings, review_pr


async def main(pr_ref: str) -> int:
    settings = Settings(
        provider="openai",
        model="gpt-4o-mini",
        # severity_threshold drops info/low before composing
        severity_threshold="medium",  # type: ignore[arg-type]
    )

    outcome = await review_pr(
        pr_ref,
        settings=settings,
        api_key=os.environ.get("OPENAI_API_KEY"),
        github_token=os.environ.get("GITHUB_TOKEN"),
    )

    print(outcome.final_comment)
    print()
    print(f"selected: {outcome.selected_agents}")
    print(f"findings: {outcome.findings_count}")
    print(f"cost:     ${outcome.cost_usd:.4f}")
    if outcome.errors:
        print(f"errors:   {len(outcome.errors)}", file=sys.stderr)
        for err in outcome.errors:
            print(f"  - {err.agent}: {err.message}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python examples/library-usage.py <owner>/<repo>#<number>", file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
