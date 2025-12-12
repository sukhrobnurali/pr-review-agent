"""Local driver to run pr-review-agent against a real PR.

Usage:
    uv run python scripts/dev/run_review.py owner/repo#NUMBER
    uv run python scripts/dev/run_review.py owner/repo#NUMBER --model gpt-4o
    uv run python scripts/dev/run_review.py owner/repo#NUMBER --only quality,tests

Reads OPENAI_API_KEY from environment or from a .env file at the project root.
GITHUB_TOKEN is optional (needed for private repos or to avoid rate limits).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

from pr_review_agent.agents import (
    build_performance_agent,
    build_quality_agent,
    build_security_agent,
    build_tests_agent,
)
from pr_review_agent.graph import build_graph
from pr_review_agent.models import ModelConfig, build_llm
from pr_review_agent.state import ReviewState
from pr_review_agent.tools.git import parse_diff
from pr_review_agent.tools.github import GitHubClient

PR_REF = re.compile(r"^([^/]+)/([^#]+)#(\d+)$")


def parse_pr_ref(ref: str) -> tuple[str, str, int]:
    m = PR_REF.match(ref)
    if not m:
        raise SystemExit(f"expected 'owner/repo#NUMBER', got: {ref}")
    return m.group(1), m.group(2), int(m.group(3))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run pr-review-agent against a PR or local diff")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--ref", help="owner/repo#NUMBER (real GitHub PR)")
    src.add_argument("--diff-file", help="path to a local unified diff (skips GitHub fetch)")
    p.add_argument("--model", default="gpt-4o-mini", help="OpenAI model id")
    p.add_argument(
        "--only",
        default="",
        help="comma-separated subset of agents (quality,tests,performance,security)",
    )
    p.add_argument("--title", default="local diff", help="PR title (used with --diff-file)")
    return p.parse_args()


async def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    if not os.environ.get("OPENAI_API_KEY"):
        print("error: OPENAI_API_KEY not set; put it in .env or export it", file=sys.stderr)
        return 2

    if args.diff_file:
        diff = Path(args.diff_file).read_text(encoding="utf-8")
        from pr_review_agent.state import PRMetadata

        pr = PRMetadata(
            owner="local",
            repo="local",
            number=1,
            title=args.title,
            head_sha="0" * 40,
            base_sha="0" * 40,
            author="local",
        )
        files = parse_diff(diff)
        print(f"-> reading local diff: {args.diff_file}")
        print(f"   {len(files)} files, {len(diff.splitlines())} diff lines")
    else:
        owner, repo, number = parse_pr_ref(args.ref)

        from githubkit import GitHub

        gh_token = os.environ.get("GITHUB_TOKEN", "")
        gh = GitHub(gh_token) if gh_token else GitHub()
        client = GitHubClient(gh)

        print(f"-> fetching {owner}/{repo}#{number}", flush=True)
        pr = await client.fetch_pr(owner, repo, number)
        diff = await client.fetch_diff(owner, repo, number)
        files = parse_diff(diff)
        print(f"   pr: {pr.title}")
        print(f"   author: {pr.author or 'unknown'}")
        print(f"   {len(files)} files, {len(diff.splitlines())} diff lines")

    cfg = ModelConfig(provider="openai", model=args.model)
    llm = build_llm(cfg)

    all_agents = {
        "quality": build_quality_agent(llm, args.model),
        "tests": build_tests_agent(llm, args.model),
        "performance": build_performance_agent(llm, args.model),
        "security": build_security_agent(llm, args.model),
    }
    if args.only:
        wanted = {a.strip() for a in args.only.split(",") if a.strip()}
        agents = {k: v for k, v in all_agents.items() if k in wanted}
        if not agents:
            print(f"error: --only={args.only!r} matched no agents", file=sys.stderr)
            return 2
    else:
        agents = all_agents

    graph = build_graph(agents)
    state: ReviewState = {
        "pr_metadata": pr,
        "diff": diff,
        "files_changed": files,
    }

    print(f"-> running review with {list(agents.keys())} on {args.model}", flush=True)
    out = await graph.ainvoke(state)

    final = out.get("final_comment", "(no comment generated)")
    output_path = Path(__file__).parent / "last_review.md"
    output_path.write_text(final, encoding="utf-8")
    print(f"-> wrote review to {output_path}")

    print()
    print("=" * 70)
    print(final)
    print("=" * 70)

    print()
    print(f"selected agents: {out.get('selected_agents', [])}")
    print(f"findings (after dedup): {len(out.get('aggregated', []))}")
    print(f"cost: ${out.get('cost_usd', 0.0):.4f}")
    if errs := out.get("errors"):
        print(f"errors: {len(errs)}")
        for e in errs:
            print(f"  - {e.agent}: {e.message}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
