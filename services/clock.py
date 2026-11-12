"""The current time, in one place.

Pages ask clock.now() rather than datetime.now(), so tests can fix the
time ("a Thursday at 16:45") and check figures like "today so far"
exactly.
"""

from datetime import datetime


def now() -> datetime:
    return datetime.now().replace(microsecond=0)
