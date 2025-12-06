from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from pr_review_agent.tools.github import GitHubClient


@pytest.fixture
def fake_gh() -> MagicMock:
    gh = MagicMock()
    gh.rest = MagicMock()
    gh.rest.pulls = MagicMock()
    gh.rest.issues = MagicMock()
    gh.rest.pulls.async_get = AsyncMock()
    gh.rest.issues.async_list_comments = AsyncMock()
    gh.rest.issues.async_create_comment = AsyncMock()
    gh.rest.issues.async_update_comment = AsyncMock()
    gh.arequest = AsyncMock()
    return gh


def _pull_response(
    title: str = "Add feature X",
    head_sha: str = "abc123",
    base_sha: str = "def456",
    user_login: str | None = "octocat",
) -> SimpleNamespace:
    user = SimpleNamespace(login=user_login) if user_login else None
    parsed = SimpleNamespace(
        title=title,
        head=SimpleNamespace(sha=head_sha),
        base=SimpleNamespace(sha=base_sha),
        user=user,
    )
    return SimpleNamespace(parsed_data=parsed)


async def test_fetch_pr(fake_gh: MagicMock) -> None:
    fake_gh.rest.pulls.async_get.return_value = _pull_response()
    client = GitHubClient(fake_gh)
    pr = await client.fetch_pr("acme", "demo", 42)
    assert pr.owner == "acme"
    assert pr.repo == "demo"
    assert pr.number == 42
    assert pr.title == "Add feature X"
    assert pr.head_sha == "abc123"
    assert pr.author == "octocat"
    fake_gh.rest.pulls.async_get.assert_awaited_once_with("acme", "demo", 42)


async def test_fetch_pr_no_author(fake_gh: MagicMock) -> None:
    fake_gh.rest.pulls.async_get.return_value = _pull_response(user_login=None)
    client = GitHubClient(fake_gh)
    pr = await client.fetch_pr("a", "b", 1)
    assert pr.author is None


async def test_fetch_diff_uses_diff_accept_header(fake_gh: MagicMock) -> None:
    fake_gh.arequest.return_value = SimpleNamespace(text="diff --git a/x b/x\n")
    client = GitHubClient(fake_gh)
    diff = await client.fetch_diff("acme", "demo", 7)
    assert diff.startswith("diff --git")
    fake_gh.arequest.assert_awaited_once()
    _, kwargs = fake_gh.arequest.await_args
    assert kwargs["headers"]["Accept"] == "application/vnd.github.v3.diff"


async def test_find_existing_review_matches_marker(fake_gh: MagicMock) -> None:
    fake_gh.rest.issues.async_list_comments.return_value = SimpleNamespace(
        parsed_data=[
            SimpleNamespace(id=1, body="some comment"),
            SimpleNamespace(id=2, body="<!-- pr-review-agent:run -->\nbody"),
            SimpleNamespace(id=3, body="another"),
        ]
    )
    client = GitHubClient(fake_gh)
    found = await client.find_existing_review("a", "b", 1, "<!-- pr-review-agent:run -->")
    assert found == 2


async def test_find_existing_review_none(fake_gh: MagicMock) -> None:
    fake_gh.rest.issues.async_list_comments.return_value = SimpleNamespace(
        parsed_data=[
            SimpleNamespace(id=1, body="hello"),
            SimpleNamespace(id=2, body=None),
        ]
    )
    client = GitHubClient(fake_gh)
    found = await client.find_existing_review("a", "b", 1, "<!-- marker -->")
    assert found is None


async def test_post_review(fake_gh: MagicMock) -> None:
    fake_gh.rest.issues.async_create_comment.return_value = SimpleNamespace(
        parsed_data=SimpleNamespace(id=99)
    )
    client = GitHubClient(fake_gh)
    new_id = await client.post_review("a", "b", 1, "body")
    assert new_id == 99


async def test_update_review(fake_gh: MagicMock) -> None:
    client = GitHubClient(fake_gh)
    await client.update_review("a", "b", 99, "new body")
    fake_gh.rest.issues.async_update_comment.assert_awaited_once_with("a", "b", 99, body="new body")
