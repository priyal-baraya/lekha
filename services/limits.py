"""Limits on how often something can be tried, to slow down guessing.

Each account already locks after 5 wrong passwords (services/accounts.py).
These limits add a second layer that works across accounts:

  * sign-in failures from one network address, so someone can't try a
    common password against many usernames;
  * new accounts from one network address, so the accounts database
    can't be flooded;
  * wrong invite codes from one person.

They are kept in memory: restarting Lekha clears them, which is fine,
because the account lockout (stored in the database) is the one that
must survive a restart.
"""

import threading
import time
from collections import defaultdict, deque


class AttemptLimiter:
    """At most `limit` attempts per `window_seconds` for each key."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._attempts: dict[str, deque] = defaultdict(deque)
        # Streamlit runs each visitor's page on its own thread.
        self._lock = threading.Lock()

    def _forget_old(self, key: str, now: float) -> deque:
        attempts = self._attempts[key]
        while attempts and attempts[0] <= now - self.window:
            attempts.popleft()
        return attempts

    def blocked(self, key: str, now: float | None = None) -> bool:
        """True when this key has used up its attempts for now."""
        now = time.monotonic() if now is None else now
        with self._lock:
            return len(self._forget_old(key, now)) >= self.limit

    def record(self, key: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            self._forget_old(key, now).append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


WINDOW_MINUTES = 15
SIGN_IN_FAILURES = AttemptLimiter(limit=20, window_seconds=WINDOW_MINUTES * 60)
NEW_ACCOUNTS = AttemptLimiter(limit=10, window_seconds=60 * 60)
INVITE_FAILURES = AttemptLimiter(limit=10, window_seconds=WINDOW_MINUTES * 60)
