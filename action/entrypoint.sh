#!/usr/bin/env bash
set -euo pipefail

cd "${GITHUB_WORKSPACE:-/github/workspace}"
exec python -m pr_review_agent.main
