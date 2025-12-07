from __future__ import annotations

from pr_review_agent.agents.supervisor import select_specialists
from pr_review_agent.state import FileChange


def _change(path: str) -> FileChange:
    return FileChange(path=path)


def test_quality_and_tests_always_selected() -> None:
    out = select_specialists([_change("docs/usage.md")], diff="")
    assert "quality" in out
    assert "tests" in out


def test_docs_pr_skips_security_and_performance() -> None:
    out = select_specialists([_change("docs/intro.md")], diff="add a paragraph")
    assert "security" not in out
    assert "performance" not in out


def test_security_run_when_auth_path_touched() -> None:
    out = select_specialists([_change("src/auth/login.py")], diff="")
    assert "security" in out


def test_security_run_when_diff_contains_password() -> None:
    out = select_specialists([_change("src/users.py")], diff="+ user.password = 'admin'\n")
    assert "security" in out


def test_security_run_when_diff_contains_subprocess() -> None:
    out = select_specialists([_change("src/runner.py")], diff="+ subprocess.run(cmd, shell=True)")
    assert "security" in out


def test_performance_run_when_db_path_touched() -> None:
    out = select_specialists([_change("src/db/queries.py")], diff="")
    assert "performance" in out


def test_performance_run_when_loop_in_diff() -> None:
    out = select_specialists(
        [_change("src/handler.py")], diff="+ for item in items:\n+     fetch(item)"
    )
    assert "performance" in out


def test_available_filter_restricts_selection() -> None:
    out = select_specialists(
        [_change("src/auth/login.py")],
        diff="",
        available=["quality"],
    )
    assert out == ["quality"]


def test_no_duplicates() -> None:
    out = select_specialists([_change("src/auth/db.py")], diff="for u in users: query(u)")
    assert len(out) == len(set(out))


def test_empty_inputs() -> None:
    out = select_specialists([], diff="")
    assert "quality" in out
    assert "tests" in out
    assert "security" not in out
    assert "performance" not in out
