"""Share model helpers — thin wrappers over raw sqlite3 queries."""

import sqlite3


def get_share_by_token(db: sqlite3.Connection, token: str):
    """Return a sqlite3.Row for the share token, or None."""
    return db.execute(
        "SELECT * FROM shares WHERE share_token = ?", (token,)
    ).fetchone()


def get_shares_for_file(db: sqlite3.Connection, file_id: int):
    """Return all share rows for a specific file."""
    return db.execute(
        "SELECT * FROM shares WHERE file_id = ?", (file_id,)
    ).fetchall()


def create_share(
    db: sqlite3.Connection,
    file_id: int,
    share_token: str,
    password_hash: str,
    expiry_time: str,
) -> int:
    """Insert a share row and return its rowid."""
    cur = db.execute(
        "INSERT INTO shares (file_id, share_token, password_hash, expiry_time) VALUES (?, ?, ?, ?)",
        (file_id, share_token, password_hash, expiry_time),
    )
    db.commit()
    return cur.lastrowid


def delete_shares_for_file(db: sqlite3.Connection, file_id: int) -> None:
    """Remove all share links for a file (caller must commit)."""
    db.execute("DELETE FROM shares WHERE file_id = ?", (file_id,))


def delete_expired_shares(db: sqlite3.Connection, now_iso: str) -> int:
    """Delete shares whose expiry_time has passed. Returns deleted row count."""
    cur = db.execute(
        "DELETE FROM shares WHERE expiry_time IS NOT NULL AND expiry_time < ?",
        (now_iso,),
    )
    db.commit()
    return cur.rowcount
