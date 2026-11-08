"""Lekha's business rules.

Pages in views/ call these functions instead of writing SQL themselves,
so the rules can be tested without a browser and reused across pages.
"""


class ValidationError(Exception):
    """Raised when input breaks one or more rules.

    `errors` holds every problem found, so the page can show them all at
    once instead of making the user fix them one at a time.
    """

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors
