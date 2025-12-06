from __future__ import annotations

from typing import Any, cast

from githubkit import GitHub

from pr_review_agent.state import PRMetadata


class GitHubClient:
    def __init__(self, gh: Any) -> None:
        self._gh = gh

    @classmethod
    def from_token(cls, token: str) -> GitHubClient:
        return cls(GitHub(token))

    async def fetch_pr(self, owner: str, repo: str, number: int) -> PRMetadata:
        resp = await self._gh.rest.pulls.async_get(owner, repo, number)
        pr = resp.parsed_data
        author = pr.user.login if pr.user is not None else None
        return PRMetadata(
            owner=owner,
            repo=repo,
            number=number,
            title=pr.title or "",
            head_sha=pr.head.sha,
            base_sha=pr.base.sha,
            author=author,
        )

    async def fetch_diff(self, owner: str, repo: str, number: int) -> str:
        resp = await self._gh.arequest(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        return cast(str, resp.text)

    async def find_existing_review(
        self, owner: str, repo: str, number: int, marker: str
    ) -> int | None:
        resp = await self._gh.rest.issues.async_list_comments(owner, repo, number)
        for comment in resp.parsed_data:
            body = getattr(comment, "body", None)
            if isinstance(body, str) and marker in body:
                return cast(int, comment.id)
        return None

    async def post_review(self, owner: str, repo: str, number: int, body: str) -> int:
        resp = await self._gh.rest.issues.async_create_comment(owner, repo, number, body=body)
        return cast(int, resp.parsed_data.id)

    async def update_review(self, owner: str, repo: str, comment_id: int, body: str) -> None:
        await self._gh.rest.issues.async_update_comment(owner, repo, comment_id, body=body)
