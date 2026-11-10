"""What each role in a shop may do.

Owners can do everything. Staff do the day-to-day work: record and cancel
sales, look up and add books, see stock and low-stock alerts, and see
Insights without profit. Pages call can() before showing an action, and
the admin services in services/accounts.py check again on their own.
"""

ROLES = ("owner", "staff")

ACTIONS = {
    "sell": "Record and cancel sales",
    "add_books": "Look up and add books",
    "view_stock": "See stock and low-stock alerts",
    "view_insights": "See Insights",
    "edit_books": "Edit book details and prices",
    "correct_stock": "Correct stock counts",
    "view_profit": "See estimated profit",
    "manage_settings": "Change shop settings",
    "manage_team": "Invite and manage the team",
}

STAFF_ACTIONS = frozenset({"sell", "add_books", "view_stock", "view_insights"})


def can(role: str | None, action: str) -> bool:
    """True if someone with this role may do this action."""
    if action not in ACTIONS:
        raise ValueError(f"Unknown action: {action}")
    if role == "owner":
        return True
    if role == "staff":
        return action in STAFF_ACTIONS
    return False
