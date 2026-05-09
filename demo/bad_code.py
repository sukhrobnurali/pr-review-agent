"""Deliberately-bad code added on a demo branch so the self-review
workflow has something meaty to review. Not imported anywhere.

Issues hidden in this file - on purpose - to exercise every specialist:

  * security: SQL injection, command injection, weak crypto, hardcoded creds
  * performance: N+1 query, O(n^2) duplicate scan
  * tests: zero tests for any of these functions
  * quality: deeply nested branches, weak names, unused constants
"""

from __future__ import annotations

import hashlib
import subprocess
from typing import Any

# pretend this came from env in real code
STRIPE_API_KEY = "<<<FIXTURE_KEY_REDACTED>>>"

# defined and never referenced
UNUSED_HELPER_CONSTANT = "deprecated"


def authenticate(u, p, ctx=None, x=None, y=None, z=None):  # type: ignore[no-untyped-def]
    if u is None:
        if p is None:
            if ctx is None:
                return False
            else:
                if x is None:
                    return False
                else:
                    return False
        else:
            return False
    else:
        # SQL injection: u and p concatenated straight into the query
        query = f"SELECT * FROM users WHERE name = '{u}' AND password = '{p}'"
        row = _db_one(query)
        return row is not None


def charge_users(user_ids: list[int], amount: int) -> int:
    n = 0
    for uid in user_ids:
        # SQL injection AND classic N+1 - one round-trip per id
        user = _db_one(f"SELECT * FROM users WHERE id = {uid}")
        if user is not None:
            _db_exec(f"UPDATE users SET balance = balance - {amount} WHERE id = {uid}")
            n += 1
    return n


def find_duplicates(items: list[Any]) -> list[Any]:
    out: list[Any] = []
    for i, item in enumerate(items):
        # O(n^2): list.index re-scans from 0 every iteration
        if items.index(item) != i and item not in out:
            out.append(item)
    return out


def hash_password(password: str) -> str:
    # MD5 for password hashing - broken
    return hashlib.md5(password.encode()).hexdigest()


def run_admin_command(cmd: str) -> str:
    # command injection: shell=True with a string from the caller
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout


def _db_one(_query: str) -> Any:
    raise NotImplementedError


def _db_exec(_query: str) -> None:
    raise NotImplementedError
