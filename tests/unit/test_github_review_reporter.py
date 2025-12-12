from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from pr_review_agent.reporting.github_review import MARKER, post_or_update_review


class _FakeClient:
    def __init__(self, existing_id: int | None = None) -> None:
        self.find_existing_review = AsyncMock(return_value=existing_id)
        self.post_review = AsyncMock(return_value=999)
        self.update_review = AsyncMock(return_value=None)


@pytest.mark.asyncio
async def test_marker_is_appended_when_missing() -> None:
    client = _FakeClient(existing_id=None)
    cid = await post_or_update_review(client, owner="o", repo="r", number=1, body="hello")
    assert cid == 999
    posted_body = client.post_review.call_args.kwargs["body"]
    assert MARKER in posted_body
    assert posted_body.startswith("hello")


@pytest.mark.asyncio
async def test_marker_not_duplicated() -> None:
    client = _FakeClient(existing_id=None)
    body = f"hello\n\n{MARKER}"
    await post_or_update_review(client, owner="o", repo="r", number=1, body=body)
    posted_body = client.post_review.call_args.kwargs["body"]
    assert posted_body.count(MARKER) == 1


@pytest.mark.asyncio
async def test_existing_comment_is_updated_not_recreated() -> None:
    client = _FakeClient(existing_id=42)
    cid = await post_or_update_review(client, owner="o", repo="r", number=1, body="hello")
    assert cid == 42
    client.post_review.assert_not_called()
    client.update_review.assert_called_once()
    args = client.update_review.call_args
    assert args.args[2] == 42
    assert MARKER in args.kwargs["body"]


@pytest.mark.asyncio
async def test_lookup_uses_marker() -> None:
    client = _FakeClient(existing_id=None)
    await post_or_update_review(client, owner="o", repo="r", number=1, body="hi")
    client.find_existing_review.assert_awaited_once()
    assert MARKER in client.find_existing_review.call_args.kwargs.values()


@pytest.mark.asyncio
async def test_dry_run_returns_none_and_does_not_call_client() -> None:
    client: Any = _FakeClient(existing_id=None)
    cid = await post_or_update_review(
        client, owner="o", repo="r", number=1, body="hi", dry_run=True
    )
    assert cid is None
    client.post_review.assert_not_called()
    client.update_review.assert_not_called()
    client.find_existing_review.assert_not_called()
