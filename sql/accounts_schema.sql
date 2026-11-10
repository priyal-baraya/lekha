-- Lekha accounts database (data/accounts.db): people, shops, memberships,
-- invitations. Each shop's books and sales live in their own file
-- (data/shops/shop_<shop_id>.db), so one shop can never read another's.
-- Times are text 'YYYY-MM-DD HH:MM:SS' in local time, checked the same
-- way as in sql/schema.sql.

-- One row per person who can sign in.
CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER PRIMARY KEY,
    -- COLLATE NOCASE makes UNIQUE ignore upper/lower case: "Priya" and
    -- "priya" can't both exist. NULL for people who only use Google.
    username       TEXT UNIQUE COLLATE NOCASE
                   CHECK (username IS NULL
                          OR (length(username) BETWEEN 3 AND 32
                              AND username NOT GLOB '*[^A-Za-z0-9._-]*')),
    display_name   TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    -- Never the password itself: a salted scrypt hash, written as
    -- "scrypt$n$r$p$<salt in hex>$<hash in hex>". NULL for Google-only people.
    password_hash  TEXT CHECK (password_hash IS NULL OR password_hash GLOB 'scrypt$*'),
    -- Google's permanent ID for the person ("sub"), from Google sign-in.
    google_subject TEXT UNIQUE,
    email          TEXT,
    created_at     TEXT NOT NULL CHECK (strftime('%Y-%m-%d %H:%M:%S', created_at) IS created_at),
    failed_logins  INTEGER NOT NULL DEFAULT 0 CHECK (failed_logins >= 0),
    locked_until   TEXT CHECK (locked_until IS NULL
                               OR strftime('%Y-%m-%d %H:%M:%S', locked_until) IS locked_until),
    -- Every person can sign in somehow: a username with a password, or Google.
    CHECK ((username IS NOT NULL AND password_hash IS NOT NULL) OR google_subject IS NOT NULL)
) STRICT;

-- One row per shop.
CREATE TABLE IF NOT EXISTS shops (
    shop_id               INTEGER PRIMARY KEY,
    name                  TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 80),
    default_reorder_level INTEGER NOT NULL DEFAULT 2 CHECK (default_reorder_level >= 0),
    created_at            TEXT NOT NULL CHECK (strftime('%Y-%m-%d %H:%M:%S', created_at) IS created_at)
) STRICT;

-- Who belongs to which shop, and as what. A person can belong to several shops.
CREATE TABLE IF NOT EXISTS memberships (
    shop_id   INTEGER NOT NULL REFERENCES shops (shop_id) ON DELETE RESTRICT,
    user_id   INTEGER NOT NULL REFERENCES users (user_id) ON DELETE RESTRICT,
    role      TEXT NOT NULL CHECK (role IN ('owner', 'staff')),
    joined_at TEXT NOT NULL CHECK (strftime('%Y-%m-%d %H:%M:%S', joined_at) IS joined_at),
    PRIMARY KEY (shop_id, user_id)          -- nobody can join the same shop twice
) STRICT;

-- One-time invite codes. Only a SHA-256 hash of each code is stored: the
-- code itself is shown to the owner once, like a password.
CREATE TABLE IF NOT EXISTS invitations (
    invitation_id INTEGER PRIMARY KEY,
    shop_id       INTEGER NOT NULL REFERENCES shops (shop_id) ON DELETE RESTRICT,
    code_hash     TEXT NOT NULL UNIQUE CHECK (length(code_hash) = 64),
    role          TEXT NOT NULL CHECK (role IN ('owner', 'staff')),
    created_by    INTEGER NOT NULL REFERENCES users (user_id) ON DELETE RESTRICT,
    created_at    TEXT NOT NULL CHECK (strftime('%Y-%m-%d %H:%M:%S', created_at) IS created_at),
    expires_at    TEXT NOT NULL CHECK (strftime('%Y-%m-%d %H:%M:%S', expires_at) IS expires_at),
    used_by       INTEGER REFERENCES users (user_id) ON DELETE RESTRICT,
    used_at       TEXT CHECK (used_at IS NULL OR strftime('%Y-%m-%d %H:%M:%S', used_at) IS used_at),
    revoked_at    TEXT CHECK (revoked_at IS NULL OR strftime('%Y-%m-%d %H:%M:%S', revoked_at) IS revoked_at),
    CHECK ((used_by IS NULL) = (used_at IS NULL))   -- used means both who and when
) STRICT;

CREATE INDEX IF NOT EXISTS idx_memberships_user_id ON memberships (user_id);
CREATE INDEX IF NOT EXISTS idx_invitations_shop_id ON invitations (shop_id);
