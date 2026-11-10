"""Tests for services/accounts.py, services/permissions.py and the
separation between shops."""

import threading
from datetime import datetime, timedelta

import pytest

import database
from database import connect, connect_accounts, ensure_shop_database, shop_path, use_database
from services import ValidationError
from services import accounts
from services.accounts import SignInError
from services.books import BookInput, add_book, count_books
from services.inventory import correct_stock, recent_adjustments
from services.sales import SaleLine, cancel_sale, get_sale, list_sales, record_sale
from services.permissions import can

NOW = datetime(2026, 11, 10, 10, 0, 0)
GOOD_PASSWORD = "correct horse battery"


@pytest.fixture
def acc(tmp_path):
    with connect_accounts(tmp_path / "accounts.db") as conn:
        yield conn


def new_user(acc, username="priya", name="Priya", password=GOOD_PASSWORD):
    return accounts.create_user(acc, username, name, password, now=NOW)


# ---------- Passwords ----------

def test_password_is_never_stored_in_plain_text(acc):
    user_id = new_user(acc)
    stored = acc.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,)).fetchone()[0]
    assert GOOD_PASSWORD not in stored
    assert stored.startswith("scrypt$16384$8$1$")


def test_same_password_gives_different_hashes():
    assert accounts.hash_password("same password") != accounts.hash_password("same password")


def test_verify_password():
    stored = accounts.hash_password(GOOD_PASSWORD)
    assert accounts.verify_password(GOOD_PASSWORD, stored)
    assert not accounts.verify_password("wrong password!", stored)
    assert not accounts.verify_password(GOOD_PASSWORD, "not a hash")


# ---------- Creating accounts ----------

@pytest.mark.parametrize(
    "username, name, password, message",
    [
        ("ab", "A", GOOD_PASSWORD, "A username is 3 to 32 letters, digits, dots, dashes or underscores."),
        ("has space", "A", GOOD_PASSWORD, "A username is 3 to 32 letters, digits, dots, dashes or underscores."),
        ("priya", " ", GOOD_PASSWORD, "Your name is required."),
        ("priya", "Priya", "short", "Use a password of at least 10 characters."),
        ("priya.baraya", "Priya", "Priya.Baraya", "The password can't be the same as the username."),
    ],
)
def test_bad_sign_up_is_refused(acc, username, name, password, message):
    with pytest.raises(ValidationError) as caught:
        accounts.create_user(acc, username, name, password, now=NOW)
    assert message in caught.value.errors


def test_usernames_are_unique_ignoring_case(acc):
    new_user(acc, "Priya")
    with pytest.raises(ValidationError) as caught:
        new_user(acc, "priya")
    assert caught.value.errors == ["That username is taken. Choose another."]


# ---------- Signing in ----------

def test_correct_password_signs_in(acc):
    user_id = new_user(acc)
    assert accounts.authenticate(acc, "PRIYA", GOOD_PASSWORD, now=NOW) == user_id


def test_wrong_password_and_unknown_user_give_the_same_message(acc):
    new_user(acc)
    with pytest.raises(SignInError) as wrong_password:
        accounts.authenticate(acc, "priya", "not the password", now=NOW)
    with pytest.raises(SignInError) as unknown_user:
        accounts.authenticate(acc, "nobody", "not the password", now=NOW)
    assert str(wrong_password.value) == str(unknown_user.value) == "The username or password is incorrect."


def test_five_wrong_passwords_lock_the_account(acc):
    new_user(acc)
    for _ in range(4):
        with pytest.raises(SignInError, match="incorrect"):
            accounts.authenticate(acc, "priya", "wrong password", now=NOW)
    with pytest.raises(SignInError, match="Try again after 10:15"):
        accounts.authenticate(acc, "priya", "wrong password", now=NOW)
    # Locked: even the right password is refused for 15 minutes...
    with pytest.raises(SignInError, match="Too many wrong passwords"):
        accounts.authenticate(acc, "priya", GOOD_PASSWORD, now=NOW + timedelta(minutes=14))
    # ...and works afterwards.
    assert accounts.authenticate(acc, "priya", GOOD_PASSWORD, now=NOW + timedelta(minutes=15, seconds=1))


def test_successful_sign_in_resets_the_count(acc):
    new_user(acc)
    for _ in range(4):
        with pytest.raises(SignInError):
            accounts.authenticate(acc, "priya", "wrong password", now=NOW)
    accounts.authenticate(acc, "priya", GOOD_PASSWORD, now=NOW)
    with pytest.raises(SignInError, match="incorrect"):     # counting starts again: not locked
        accounts.authenticate(acc, "priya", "wrong password", now=NOW)


def test_google_sign_in_creates_one_account_per_google_id(acc):
    first = accounts.google_sign_in(acc, "google-sub-123", "a@example.com", "Asha", now=NOW)
    again = accounts.google_sign_in(acc, "google-sub-123", "asha@example.com", "Asha", now=NOW)
    assert first == again
    assert accounts.get_user(acc, first)["email"] == "asha@example.com"   # email may change; the ID doesn't
    assert accounts.google_sign_in(acc, "google-sub-456", None, "Ben", now=NOW) != first


def test_google_user_has_no_password_to_sign_in_with(acc):
    accounts.google_sign_in(acc, "google-sub-123", "a@example.com", "Asha", now=NOW)
    with pytest.raises(SignInError):
        accounts.authenticate(acc, "a@example.com", "anything at all", now=NOW)


def test_change_password(acc):
    user_id = new_user(acc)
    with pytest.raises(ValidationError) as caught:
        accounts.change_password(acc, user_id, "wrong current", "a brand new password")
    assert caught.value.errors == ["Your current password is incorrect."]
    accounts.change_password(acc, user_id, GOOD_PASSWORD, "a brand new password")
    assert accounts.authenticate(acc, "priya", "a brand new password", now=NOW)


# ---------- Shops and roles ----------

def test_creating_a_shop_makes_you_its_owner(acc):
    user_id = new_user(acc)
    shop_id = accounts.create_shop(acc, user_id, "  Kitaab   Corner ", now=NOW)
    assert accounts.memberships(acc, user_id) == [accounts.Membership(shop_id, "Kitaab Corner", "owner")]


@pytest.mark.parametrize(
    "role, allowed, refused",
    [
        ("owner", ["sell", "add_books", "edit_books", "correct_stock", "view_profit", "manage_team"], []),
        ("staff", ["sell", "add_books", "view_stock", "view_insights"],
         ["edit_books", "correct_stock", "view_profit", "manage_settings", "manage_team"]),
        (None, [], ["sell", "view_stock"]),
    ],
)
def test_permissions(role, allowed, refused):
    assert all(can(role, action) for action in allowed)
    assert not any(can(role, action) for action in refused)


def test_unknown_action_is_a_programming_error():
    with pytest.raises(ValueError):
        can("owner", "launch_rockets")


# ---------- Invitations ----------

def shop_with_owner(acc):
    owner = new_user(acc, "owner", "Owner")
    return owner, accounts.create_shop(acc, owner, "Kitaab Corner", now=NOW)


def test_invite_code_is_shown_once_and_stored_hashed(acc):
    owner, shop = shop_with_owner(acc)
    code = accounts.create_invitation(acc, owner, shop, "staff", now=NOW)
    assert len(code) == 11 and code[5] == "-"
    stored = acc.execute("SELECT code_hash FROM invitations").fetchone()[0]
    assert code.replace("-", "") not in stored and len(stored) == 64


def test_staff_joins_with_a_code(acc):
    owner, shop = shop_with_owner(acc)
    code = accounts.create_invitation(acc, owner, shop, "staff", now=NOW)
    staff = new_user(acc, "assistant", "Assistant")
    assert accounts.redeem_invitation(acc, staff, code.lower().replace("-", " "), now=NOW) == shop  # forgiving typing
    assert accounts.role_in(acc, staff, shop) == "staff"


@pytest.mark.parametrize("problem", ["used", "expired", "revoked", "wrong", "member"])
def test_bad_invite_codes_are_refused(acc, problem):
    owner, shop = shop_with_owner(acc)
    code = accounts.create_invitation(acc, owner, shop, "staff", now=NOW)
    person = new_user(acc, "someone", "Someone")
    when = NOW
    if problem == "used":
        accounts.redeem_invitation(acc, new_user(acc, "first", "First"), code, now=NOW)
    elif problem == "expired":
        when = NOW + timedelta(days=7, seconds=1)
    elif problem == "revoked":
        invitation_id = acc.execute("SELECT invitation_id FROM invitations").fetchone()[0]
        accounts.revoke_invitation(acc, owner, shop, invitation_id, now=NOW)
    elif problem == "wrong":
        code = "AAAAA-AAAAA"
    elif problem == "member":
        person = owner
    with pytest.raises(ValidationError):
        accounts.redeem_invitation(acc, person, code, now=when)
    if problem != "member":
        assert accounts.role_in(acc, person, shop) is None


def test_staff_cannot_do_owner_things(acc):
    owner, shop = shop_with_owner(acc)
    staff = new_user(acc, "assistant", "Assistant")
    accounts.redeem_invitation(acc, staff, accounts.create_invitation(acc, owner, shop, now=NOW), now=NOW)
    for action in (
        lambda: accounts.create_invitation(acc, staff, shop, now=NOW),
        lambda: accounts.change_role(acc, staff, shop, staff, "owner"),
        lambda: accounts.remove_member(acc, staff, shop, owner),
        lambda: accounts.update_shop_settings(acc, staff, shop, "Taken over", 1),
        lambda: accounts.team(acc, staff, shop, now=NOW),
    ):
        with pytest.raises(PermissionError):
            action()
    assert accounts.role_in(acc, staff, shop) == "staff"
    assert accounts.get_shop(acc, shop)["name"] == "Kitaab Corner"


def test_someone_outside_the_shop_can_do_nothing(acc):
    owner, shop = shop_with_owner(acc)
    stranger = new_user(acc, "stranger", "Stranger")
    with pytest.raises(PermissionError):
        accounts.create_invitation(acc, stranger, shop, now=NOW)


def test_a_shop_always_keeps_an_owner(acc):
    owner, shop = shop_with_owner(acc)
    last_owner = ["A shop needs at least one owner. Make someone else an owner first."]
    with pytest.raises(ValidationError) as caught:
        accounts.change_role(acc, owner, shop, owner, "staff")
    assert caught.value.errors == last_owner
    with pytest.raises(ValidationError) as caught:
        accounts.remove_member(acc, owner, shop, owner)
    assert caught.value.errors == last_owner
    # With a second owner, the first can step down.
    second = new_user(acc, "second", "Second")
    accounts.redeem_invitation(acc, second, accounts.create_invitation(acc, owner, shop, "owner", now=NOW), now=NOW)
    accounts.change_role(acc, owner, shop, owner, "staff")
    assert accounts.role_in(acc, owner, shop) == "staff"


def test_owner_changes_settings(acc):
    owner, shop = shop_with_owner(acc)
    accounts.update_shop_settings(acc, owner, shop, "Kitaab Corner, Kochi", 3)
    saved = accounts.get_shop(acc, shop)
    assert (saved["name"], saved["default_reorder_level"]) == ("Kitaab Corner, Kochi", 3)


def test_one_person_can_belong_to_several_shops(acc):
    owner_a, shop_a = shop_with_owner(acc)
    person = new_user(acc, "both", "Both")
    accounts.create_shop(acc, person, "Own Shop", now=NOW)
    accounts.redeem_invitation(acc, person, accounts.create_invitation(acc, owner_a, shop_a, now=NOW), now=NOW)
    assert {(m.shop_name, m.role) for m in accounts.memberships(acc, person)} == {
        ("Own Shop", "owner"), ("Kitaab Corner", "staff")}


# ---------- Keeping shops apart ----------

def test_each_shop_has_its_own_books(tmp_path, monkeypatch):
    monkeypatch.setenv("LEKHA_DATA_DIR", str(tmp_path))
    first, second = ensure_shop_database(1), ensure_shop_database(2)
    assert first != second and first == shop_path(1)
    with connect(first) as conn:
        add_book(conn, BookInput(title="Only in shop one", author="A", genre="Fiction", selling_price=100))
    with connect(first) as conn:
        assert count_books(conn) == 1
    with connect(second) as conn:
        assert count_books(conn) == 0


def test_shop_choice_doesnt_leak_between_visitors(tmp_path, monkeypatch):
    """Two visitors' page runs at the same moment each see only their own shop."""
    monkeypatch.delenv("LEKHA_DB_PATH", raising=False)
    seen = {}
    ready = threading.Barrier(2)

    def visit(name, path):
        use_database(path)
        ready.wait()                       # both have set their shop before either reads
        seen[name] = database.database_path()

    threads = [threading.Thread(target=visit, args=("a", tmp_path / "a.db")),
               threading.Thread(target=visit, args=("b", tmp_path / "b.db"))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert seen == {"a": tmp_path / "a.db", "b": tmp_path / "b.db"}
    assert database.database_path() == database.DEFAULT_DB_PATH   # this test's own run was never changed


def test_reset_deletes_accounts_and_shops_only(tmp_path):
    with connect_accounts(tmp_path / "accounts.db") as conn:
        new_user(conn)
    (tmp_path / "shops").mkdir()
    (tmp_path / "shops" / "shop_1.db").write_bytes(b"")
    (tmp_path / "keep_me.txt").write_text("not Lekha's")
    database.reset_everything(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keep_me.txt"]


# ---------- Who did what ----------

def test_sales_cancellations_and_corrections_record_who(sample_db):
    sale_id = record_sale(sample_db, [SaleLine(1, 1, 39900)], now=NOW, recorded_by=7)
    assert get_sale(sample_db, sale_id)["recorded_by"] == 7
    assert list_sales(sample_db)[0]["recorded_by"] == 7
    cancel_sale(sample_db, sale_id, "Entered by mistake", now=NOW, cancelled_by=8)
    assert get_sale(sample_db, sale_id)["cancelled_by"] == 8
    correct_stock(sample_db, 3, 6, 5, "damaged_or_lost", now=NOW, recorded_by=9)
    assert recent_adjustments(sample_db)[0]["recorded_by"] == 9


def test_older_records_have_no_recorder(sample_db):
    assert get_sale(sample_db, 1)["recorded_by"] is None     # made before accounts existed


def test_display_names_for_recorded_by(acc):
    first = new_user(acc, "first", "Asha")
    second = new_user(acc, "second", "Ben")
    assert accounts.display_names(acc, [first, second, None, first]) == {first: "Asha", second: "Ben"}
    assert accounts.display_names(acc, []) == {}
