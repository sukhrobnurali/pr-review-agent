from __future__ import annotations

from typing import Protocol

MARKER = "<!-- pr-review-agent:run -->"


class _Client(Protocol):
    async def find_existing_review(
        self, owner: str, repo: str, number: int, marker: str
    ) -> int | None: ...

    async def post_review(self, owner: str, repo: str, number: int, body: str) -> int: ...

    async def update_review(
        self, owner: str, repo: str, comment_id: int, body: str
    ) -> None: ...


def _ensure_marker(body: str) -> str:
    if MARKER in body:
        return body
    sep = "\n\n" if not body.endswith("\n") else "\n"
    return f"{body}{sep}{MARKER}"


async def post_or_update_review(
    client: _Client,
    *,
    owner: str,
    repo: str,
    number: int,
    body: str,
    dry_run: bool = False,
) -> int | None:
    if dry_run:
        return None
    body = _ensure_marker(body)
    existing = await client.find_existing_review(owner, repo, number, marker=MARKER)
    if existing is not None:
        await client.update_review(owner, repo, existing, body=body)
        return existing
    return await client.post_review(owner, repo, number, body=body)
