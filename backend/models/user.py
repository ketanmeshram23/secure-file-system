"""User model helpers — thin wrappers over raw sqlite3 queries."""

import sqlite3


def get_user_by_username(db: sqlite3.Connection, username: str):
    """Return a sqlite3.Row for the given username, or None."""
    return db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()


def get_user_by_id(db: sqlite3.Connection, user_id: int):
    """Return a sqlite3.Row for the given id, or None."""
    return db.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()


def get_user_by_email(db: sqlite3.Connection, email: str):
    """Return a sqlite3.Row for the given email, or None."""
    return db.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()


def create_user(
    db: sqlite3.Connection,
    username: str,
    email: str,
    password_hash: str,
    otp_secret: str,
) -> int:
    """Insert a new user and return its rowid."""
    cur = db.execute(
        "INSERT INTO users (username, email, password_hash, otp_secret) VALUES (?, ?, ?, ?)",
        (username, email, password_hash, otp_secret),
    )
    db.commit()
    return cur.lastrowid
