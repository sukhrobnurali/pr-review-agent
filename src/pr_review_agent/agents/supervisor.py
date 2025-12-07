from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from pr_review_agent.findings import AgentName

if TYPE_CHECKING:
    from pr_review_agent.state import FileChange


_SECURITY_HINTS: frozenset[str] = frozenset(
    {
        "password",
        "secret",
        "api_key",
        "apikey",
        "token",
        "crypto",
        "hashlib",
        "encrypt",
        "decrypt",
        "auth",
        "login",
        "session",
        "jwt",
        "sql",
        "pickle.loads",
        "eval(",
        "exec(",
        "subprocess.run",
        "os.system",
        "shell=true",
        ".env",
    }
)

_SECURITY_PATH_HINTS: frozenset[str] = frozenset(
    {"auth", "security", "crypto", "login", "password", "secrets"}
)

_PERFORMANCE_HINTS: frozenset[str] = frozenset(
    {
        "select(",
        ".filter(",
        ".all()",
        ".count()",
        ".first(",
        "join(",
        "for ",
        "while ",
        "async ",
        "await ",
        "cache",
        "redis",
        "celery",
        "n+1",
        "lru_cache",
    }
)

_PERFORMANCE_PATH_HINTS: frozenset[str] = frozenset(
    {"models", "db", "database", "api", "queries", "cache"}
)


def select_specialists(
    files_changed: Iterable[FileChange],
    diff: str,
    *,
    available: Iterable[AgentName] | None = None,
) -> list[AgentName]:
    available_set: set[AgentName] = (
        set(available) if available is not None else {"quality", "tests", "performance", "security"}
    )

    selected: list[AgentName] = []
    if "quality" in available_set:
        selected.append("quality")
    if "tests" in available_set:
        selected.append("tests")

    paths = [f.path.lower() for f in files_changed]
    diff_lower = diff.lower()

    if "security" in available_set and _matches(
        paths, diff_lower, _SECURITY_PATH_HINTS, _SECURITY_HINTS
    ):
        selected.append("security")
    if "performance" in available_set and _matches(
        paths, diff_lower, _PERFORMANCE_PATH_HINTS, _PERFORMANCE_HINTS
    ):
        selected.append("performance")
    return selected


def _matches(
    paths: list[str],
    diff_lower: str,
    path_hints: frozenset[str],
    keyword_hints: frozenset[str],
) -> bool:
    for p in paths:
        if any(hint in p for hint in path_hints):
            return True
    return any(hint in diff_lower for hint in keyword_hints)
