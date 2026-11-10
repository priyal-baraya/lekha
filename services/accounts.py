"""People, sign-in, shops, memberships and invitations.

Everything here works on the accounts database (data/accounts.db). It
never touches a shop's books or sales, which live in each shop's own file.

Security choices, each explained where it happens:
  * passwords are stored only as salted scrypt hashes;
  * password checks use a constant-time comparison;
  * passwords are 10 to 128 characters, and very common ones are refused;
  * five wrong passwords lock an account for 15 minutes, whether they
    were typed when signing in or when changing the password;
  * sign-in errors never say whether the username exists;
  * changing a password signs out the account's other open tabs;
  * invite codes are random, single-use, expire, and are stored hashed;
  * admin actions check the person is an owner of that shop;
  * security events are written to the log (never passwords or codes).
"""

import hashlib
import hmac
import logging
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from services import ValidationError
from services.permissions import ROLES, can

# Security events go to the terminal Lekha runs in, under "lekha.security".
log = logging.getLogger("lekha.security")

TIMESTAMP = "%Y-%m-%d %H:%M:%S"
MIN_PASSWORD_LENGTH = 10
# A limit keeps one enormous "password" from tying up the computer while
# it is hashed. 128 characters is far longer than any passphrase needs.
MAX_PASSWORD_LENGTH = 128
MAX_NAME_LENGTH = 60
MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15
INVITE_DAYS = 7
# scrypt settings: n=2**14, r=8, p=1 uses about 16 MB of memory and a few
# hundredths of a second per check: fine for one person signing in, slow
# and costly for someone trying millions of guesses.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1
# Letters and digits that can't be confused with each other when read out
# (no 0/O, 1/I/L).
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


class SignInError(Exception):
    """Sign-in failed. The message is safe to show as it is."""


@dataclass(frozen=True)
class Membership:
    shop_id: int
    shop_name: str
    role: str


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now()).replace(microsecond=0)


def _text(moment: datetime) -> str:
    return moment.strftime(TIMESTAMP)


# --------------------------------------------------------------- passwords

def hash_password(password: str) -> str:
    """A salted scrypt hash of the password, never the password itself.

    The salt is 16 random bytes, different for every password, so two
    people with the same password get different hashes, and precomputed
    tables of common passwords are useless.
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check a password against a stored hash.

    hmac.compare_digest takes the same time whether the first or the last
    byte differs, so timing can't reveal how close a guess was.
    """
    try:
        _, n, r, p, salt_hex, hash_hex = stored.split("$")
        digest = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                                n=int(n), r=int(r), p=int(p), dklen=len(hash_hex) // 2)
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


# Used when the username doesn't exist, so a wrong username takes as long
# as a wrong password and timing doesn't reveal which usernames exist.
_DUMMY_HASH = hash_password(secrets.token_hex(8))


# Some of the most common passwords that meet the length rule, as found in
# published lists of leaked passwords. Length alone doesn't make these safe:
# they are among the first guesses anyone tries.
COMMON_PASSWORDS = frozenset({
    "1234567890", "12345678910", "123456789a", "0987654321", "1111111111",
    "qwertyuiop", "1q2w3e4r5t", "1qaz2wsx3edc", "qwerty1234", "qwerty12345",
    "password12", "password123", "password1234", "passw0rd123", "iloveyou12",
    "abcdefghij", "abcd123456", "a1b2c3d4e5", "letmein123", "welcome123",
    "changeme123", "admin12345", "football12", "baseball12", "superman12",
    "sunshine12", "princess12", "monkey1234", "dragon1234", "asdfghjkl1",
    "zxcvbnm123", "trustno1234", "india12345", "bookshop12", "bookstore1",
})


def _check_new_password(password: str, username: str | None, errors: list[str],
                        display_name: str | None = None) -> None:
    password = password or ""
    lowered = password.lower()
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Use a password of at least {MIN_PASSWORD_LENGTH} characters.")
    elif len(password) > MAX_PASSWORD_LENGTH:
        errors.append(f"Use a password of at most {MAX_PASSWORD_LENGTH} characters.")
    elif username and username.lower() in lowered:
        errors.append("The password can't contain the username.")
    elif display_name and len(display_name) >= 4 and lowered == "".join(display_name.lower().split()):
        errors.append("The password can't be your name.")
    elif lowered in COMMON_PASSWORDS or len(set(password)) <= 2:
        errors.append("That password is too easy to guess. Try a few unrelated words together.")


def _check_display_name(display_name: str, errors: list[str]) -> None:
    if not display_name:
        errors.append("Your name is required.")
    elif len(display_name) > MAX_NAME_LENGTH:
        errors.append(f"A name is at most {MAX_NAME_LENGTH} characters.")


def _record_failure(conn: sqlite3.Connection, user_id: int, failed_logins: int, now: datetime) -> str | None:
    """Count one wrong password. Returns the lock message once the account locks."""
    failed = failed_logins + 1
    locked = _text(now + timedelta(minutes=LOCK_MINUTES)) if failed >= MAX_FAILED_LOGINS else None
    with conn:
        conn.execute("UPDATE users SET failed_logins = ?, locked_until = ? WHERE user_id = ?",
                     (0 if locked else failed, locked, user_id))
    if locked:
        log.warning("Account %s locked after %s wrong passwords", user_id, MAX_FAILED_LOGINS)
        return f"Too many wrong passwords. Try again after {now + timedelta(minutes=LOCK_MINUTES):%H:%M}."
    return None


def _locked_message(locked_until: str | None, now: datetime) -> str | None:
    if locked_until and datetime.strptime(locked_until, TIMESTAMP) > now:
        return f"Too many wrong passwords. Try again after {datetime.strptime(locked_until, TIMESTAMP):%H:%M}."
    return None


# ------------------------------------------------------------------ people

def create_user(conn: sqlite3.Connection, username: str, display_name: str, password: str,
                now: datetime | None = None) -> int:
    """Create a username-and-password account. Returns the new user_id."""
    username = (username or "").strip()
    display_name = " ".join((display_name or "").split())
    errors = []
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,32}", username):
        errors.append("A username is 3 to 32 letters, digits, dots, dashes or underscores.")
    _check_display_name(display_name, errors)
    _check_new_password(password, username, errors, display_name)
    if not errors and conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        errors.append("That username is taken. Choose another.")
    if errors:
        raise ValidationError(errors)
    with conn:
        user_id = conn.execute(
            "INSERT INTO users (username, display_name, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (username, display_name, hash_password(password), _text(_now(now))),
        ).lastrowid
    log.info("Account %s created", user_id)
    return user_id


def authenticate(conn: sqlite3.Connection, username: str, password: str, now: datetime | None = None) -> int:
    """Return the user_id for a correct username and password, or raise SignInError."""
    now = _now(now)
    password = (password or "")[:MAX_PASSWORD_LENGTH + 1]   # never hash something enormous
    user = conn.execute(
        "SELECT user_id, password_hash, failed_logins, locked_until FROM users WHERE username = ?",
        ((username or "").strip()[:64],),
    ).fetchone()
    if user is None or user["password_hash"] is None:
        verify_password(password, _DUMMY_HASH)          # same work, same time
        log.info("Failed sign-in for an unknown username")
        raise SignInError("The username or password is incorrect.")
    locked = _locked_message(user["locked_until"], now)
    if locked:
        log.info("Sign-in refused: account %s is locked", user["user_id"])
        raise SignInError(locked)
    if not verify_password(password, user["password_hash"]):
        log.info("Failed sign-in for account %s", user["user_id"])
        raise SignInError(_record_failure(conn, user["user_id"], user["failed_logins"], now)
                          or "The username or password is incorrect.")
    with conn:
        conn.execute("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE user_id = ?", (user["user_id"],))
    log.info("Account %s signed in", user["user_id"])
    return user["user_id"]


def google_sign_in(conn: sqlite3.Connection, subject: str, email: str | None, name: str | None,
                   now: datetime | None = None) -> int:
    """Find or create the account for a Google identity. Returns user_id.

    Google's "sub" (subject) is a permanent ID for the person; email
    addresses can change, so the account is matched on the subject.
    """
    if not subject or not isinstance(subject, str) or len(subject) > 255:
        raise SignInError("Google didn't send an account ID. Try signing in again.")
    email = email[:254] if isinstance(email, str) else None
    display_name = " ".join(str(name or email or "Google user").split())[:MAX_NAME_LENGTH] or "Google user"
    found = conn.execute("SELECT user_id FROM users WHERE google_subject = ?", (subject,)).fetchone()
    with conn:
        if found:
            conn.execute("UPDATE users SET email = ? WHERE user_id = ?", (email, found["user_id"]))
            user_id = found["user_id"]
        else:
            user_id = conn.execute(
                "INSERT INTO users (display_name, google_subject, email, created_at) VALUES (?, ?, ?, ?)",
                (display_name, subject, email, _text(_now(now))),
            ).lastrowid
    log.info("Account %s signed in with Google", user_id)
    return user_id


def get_user(conn: sqlite3.Connection, user_id: int) -> dict | None:
    row = conn.execute(
        "SELECT user_id, username, display_name, email, google_subject IS NOT NULL AS uses_google, "
        "password_hash IS NOT NULL AS has_password FROM users WHERE user_id = ?", (user_id,),
    ).fetchone()
    return dict(row) if row else None


def display_names(conn: sqlite3.Connection, user_ids) -> dict[int, str]:
    """user_id -> display name, for "recorded by" columns."""
    ids = sorted({int(i) for i in user_ids if i is not None})
    if not ids:
        return {}
    rows = conn.execute(
        # Reviewed for bandit: only "?" placeholders are joined into the text; the ids are passed separately.
        f"SELECT user_id, display_name FROM users WHERE user_id IN ({', '.join('?' for _ in ids)})", ids  # nosec B608
    )
    return {row["user_id"]: row["display_name"] for row in rows}


def change_password(conn: sqlite3.Connection, user_id: int, current: str, new: str,
                    now: datetime | None = None) -> None:
    """Change a password after checking the current one.

    A wrong current password counts towards the same 5-try lockout as
    signing in, so this form can't be used to guess a password either.
    """
    now = _now(now)
    user = conn.execute(
        "SELECT username, display_name, password_hash, failed_logins, locked_until FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if user is None or user["password_hash"] is None:
        raise ValidationError(["This account signs in with Google, so it has no password to change."])
    locked = _locked_message(user["locked_until"], now)
    if locked:
        raise ValidationError([locked])
    if not verify_password((current or "")[:MAX_PASSWORD_LENGTH + 1], user["password_hash"]):
        log.info("Wrong current password when changing the password of account %s", user_id)
        raise ValidationError([_record_failure(conn, user_id, user["failed_logins"], now)
                               or "Your current password is incorrect."])
    errors = []
    _check_new_password(new, user["username"], errors, user["display_name"])
    if not errors and verify_password(new, user["password_hash"]):
        errors.append("Choose a new password, different from the current one.")
    if errors:
        raise ValidationError(errors)
    with conn:
        conn.execute("UPDATE users SET password_hash = ?, failed_logins = 0, locked_until = NULL WHERE user_id = ?",
                     (hash_password(new), user_id))
    log.info("Account %s changed its password", user_id)


def credential_stamp(conn: sqlite3.Connection, user_id: int) -> str | None:
    """A short fingerprint of the account's password hash (None for
    Google-only accounts). Each signed-in tab remembers it, and app.py
    signs the tab out if it changes, so changing a password ends every
    other session that knew the old one. It reveals nothing about the
    password: it's a hash of a hash."""
    row = conn.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if row is None or row["password_hash"] is None:
        return None
    return hashlib.sha256(row["password_hash"].encode("utf-8")).hexdigest()[:16]


def change_display_name(conn: sqlite3.Connection, user_id: int, display_name: str) -> None:
    display_name = " ".join((display_name or "").split())
    errors = []
    _check_display_name(display_name, errors)
    if errors:
        raise ValidationError(errors)
    with conn:
        conn.execute("UPDATE users SET display_name = ? WHERE user_id = ?", (display_name, user_id))


# ------------------------------------------------------------------- shops

def memberships(conn: sqlite3.Connection, user_id: int) -> list[Membership]:
    rows = conn.execute(
        """
        SELECT s.shop_id, s.name, m.role FROM memberships AS m
        JOIN shops AS s ON s.shop_id = m.shop_id
        WHERE m.user_id = ? ORDER BY s.name COLLATE NOCASE
        """, (user_id,),
    )
    return [Membership(row["shop_id"], row["name"], row["role"]) for row in rows]


def role_in(conn: sqlite3.Connection, user_id: int, shop_id: int) -> str | None:
    row = conn.execute("SELECT role FROM memberships WHERE user_id = ? AND shop_id = ?", (user_id, shop_id)).fetchone()
    return row["role"] if row else None


def _require(conn, actor_id: int, shop_id: int, action: str) -> None:
    """Refuse unless the actor's role in this shop allows the action."""
    if not can(role_in(conn, actor_id, shop_id), action):
        log.warning("Account %s was refused '%s' in shop %s", actor_id, action, shop_id)
        raise PermissionError("Only the shop's owners can do that.")


def _shop_name(name: str) -> str:
    name = " ".join((name or "").split())
    if not 1 <= len(name) <= 80:
        raise ValidationError(["A shop name is 1 to 80 characters."])
    return name


def create_shop(conn: sqlite3.Connection, user_id: int, name: str, now: datetime | None = None) -> int:
    """Create a shop with this person as its owner. Returns shop_id."""
    name = _shop_name(name)
    stamp = _text(_now(now))
    with conn:   # the shop and its first owner are created together, or not at all
        shop_id = conn.execute("INSERT INTO shops (name, created_at) VALUES (?, ?)", (name, stamp)).lastrowid
        conn.execute("INSERT INTO memberships (shop_id, user_id, role, joined_at) VALUES (?, ?, 'owner', ?)",
                     (shop_id, user_id, stamp))
    log.info("Account %s created shop %s", user_id, shop_id)
    return shop_id


def get_shop(conn: sqlite3.Connection, shop_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM shops WHERE shop_id = ?", (shop_id,)).fetchone()
    return dict(row) if row else None


def update_shop_settings(conn: sqlite3.Connection, actor_id: int, shop_id: int, name: str,
                         default_reorder_level: int) -> None:
    _require(conn, actor_id, shop_id, "manage_settings")
    name = _shop_name(name)
    if isinstance(default_reorder_level, bool) or not isinstance(default_reorder_level, int) or default_reorder_level < 0:
        raise ValidationError(["The default reorder level is a whole number, 0 or more."])
    with conn:
        conn.execute("UPDATE shops SET name = ?, default_reorder_level = ? WHERE shop_id = ?",
                     (name, default_reorder_level, shop_id))
    log.info("Account %s changed the settings of shop %s", actor_id, shop_id)


# ------------------------------------------------------------- invitations

def _normalise_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (code or "").upper())


def _code_hash(code: str) -> str:
    return hashlib.sha256(_normalise_code(code).encode("ascii")).hexdigest()


def create_invitation(conn: sqlite3.Connection, actor_id: int, shop_id: int, role: str = "staff",
                      now: datetime | None = None) -> str:
    """Make a one-time invite code. Returns the code: it is shown once and
    only its hash is stored."""
    _require(conn, actor_id, shop_id, "manage_team")
    if role not in ROLES:
        raise ValidationError(["Choose owner or staff."])
    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(10))
    now = _now(now)
    with conn:
        conn.execute(
            "INSERT INTO invitations (shop_id, code_hash, role, created_by, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (shop_id, _code_hash(code), role, actor_id, _text(now), _text(now + timedelta(days=INVITE_DAYS))),
        )
    log.info("Account %s made a %s invite code for shop %s", actor_id, role, shop_id)
    return f"{code[:5]}-{code[5:]}"


def redeem_invitation(conn: sqlite3.Connection, user_id: int, code: str, now: datetime | None = None) -> int:
    """Join the shop an invite code belongs to. Returns shop_id."""
    now = _now(now)
    invite = conn.execute("SELECT * FROM invitations WHERE code_hash = ?", (_code_hash(code),)).fetchone()
    if invite is None or invite["revoked_at"]:
        raise ValidationError(["That invite code isn't valid. Check it with the shop's owner."])
    if invite["used_at"]:
        raise ValidationError(["That invite code has already been used. Ask the owner for a new one."])
    if datetime.strptime(invite["expires_at"], TIMESTAMP) <= now:
        raise ValidationError(["That invite code has expired. Ask the owner for a new one."])
    if role_in(conn, user_id, invite["shop_id"]):
        raise ValidationError(["You're already part of this shop."])
    with conn:   # mark the code used and add the member together
        used = conn.execute(
            "UPDATE invitations SET used_by = ?, used_at = ? WHERE invitation_id = ? AND used_at IS NULL",
            (user_id, _text(now), invite["invitation_id"]),
        ).rowcount
        if used == 0:   # someone else used it a moment ago
            raise ValidationError(["That invite code has already been used. Ask the owner for a new one."])
        conn.execute("INSERT INTO memberships (shop_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)",
                     (invite["shop_id"], user_id, invite["role"], _text(now)))
    log.info("Account %s joined shop %s as %s with an invite code", user_id, invite["shop_id"], invite["role"])
    return invite["shop_id"]


def revoke_invitation(conn: sqlite3.Connection, actor_id: int, shop_id: int, invitation_id: int,
                      now: datetime | None = None) -> None:
    _require(conn, actor_id, shop_id, "manage_team")
    with conn:
        conn.execute(
            "UPDATE invitations SET revoked_at = ? WHERE invitation_id = ? AND shop_id = ? AND used_at IS NULL",
            (_text(_now(now)), invitation_id, shop_id),
        )
    log.info("Account %s cancelled invite %s of shop %s", actor_id, invitation_id, shop_id)


# -------------------------------------------------------------------- team

def team(conn: sqlite3.Connection, actor_id: int, shop_id: int, now: datetime | None = None) -> dict:
    """Members and pending invitations, for the shop's owners."""
    _require(conn, actor_id, shop_id, "manage_team")
    members = conn.execute(
        """
        SELECT u.user_id, u.display_name, u.username, u.email, m.role, m.joined_at
        FROM memberships AS m JOIN users AS u ON u.user_id = m.user_id
        WHERE m.shop_id = ? ORDER BY m.role, u.display_name COLLATE NOCASE
        """, (shop_id,),
    ).fetchall()
    pending = conn.execute(
        """
        SELECT invitation_id, role, created_at, expires_at FROM invitations
        WHERE shop_id = ? AND used_at IS NULL AND revoked_at IS NULL AND expires_at > ?
        ORDER BY created_at DESC
        """, (shop_id, _text(_now(now))),
    ).fetchall()
    return {"members": [dict(row) for row in members], "invitations": [dict(row) for row in pending]}


def _owner_count(conn, shop_id: int) -> int:
    return conn.execute("SELECT COUNT(*) FROM memberships WHERE shop_id = ? AND role = 'owner'", (shop_id,)).fetchone()[0]


def change_role(conn: sqlite3.Connection, actor_id: int, shop_id: int, user_id: int, role: str) -> None:
    _require(conn, actor_id, shop_id, "manage_team")
    if role not in ROLES:
        raise ValidationError(["Choose owner or staff."])
    current = role_in(conn, user_id, shop_id)
    if current is None:
        raise ValidationError(["That person isn't part of this shop."])
    if current == "owner" and role != "owner" and _owner_count(conn, shop_id) == 1:
        raise ValidationError(["A shop needs at least one owner. Make someone else an owner first."])
    with conn:
        conn.execute("UPDATE memberships SET role = ? WHERE shop_id = ? AND user_id = ?", (role, shop_id, user_id))
    log.info("Account %s made account %s %s of shop %s", actor_id, user_id, role, shop_id)


def remove_member(conn: sqlite3.Connection, actor_id: int, shop_id: int, user_id: int) -> None:
    _require(conn, actor_id, shop_id, "manage_team")
    current = role_in(conn, user_id, shop_id)
    if current is None:
        raise ValidationError(["That person isn't part of this shop."])
    if current == "owner" and _owner_count(conn, shop_id) == 1:
        raise ValidationError(["A shop needs at least one owner. Make someone else an owner first."])
    with conn:
        conn.execute("DELETE FROM memberships WHERE shop_id = ? AND user_id = ?", (shop_id, user_id))
    log.info("Account %s removed account %s from shop %s", actor_id, user_id, shop_id)
