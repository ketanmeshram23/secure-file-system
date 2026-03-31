"""File model helpers — thin wrappers over raw sqlite3 queries."""

import sqlite3


def get_file_by_id(db: sqlite3.Connection, file_id: int, user_id: int = None):
    """
    Return a sqlite3.Row for the file.
    If user_id is provided the query also enforces ownership.
    """
    if user_id is not None:
        return db.execute(
            "SELECT * FROM files WHERE id = ? AND user_id = ?", (file_id, user_id)
        ).fetchone()
    return db.execute(
        "SELECT * FROM files WHERE id = ?", (file_id,)
    ).fetchone()


def get_files_by_user(db: sqlite3.Connection, user_id: int):
    """Return all file rows for the given user, newest first."""
    return db.execute(
        "SELECT * FROM files WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    ).fetchall()


def get_expired_files(db: sqlite3.Connection, now_iso: str):
    """Return all files whose expiry_time has passed."""
    return db.execute(
        "SELECT * FROM files WHERE expiry_time IS NOT NULL AND expiry_time < ?",
        (now_iso,),
    ).fetchall()


def delete_file_record(db: sqlite3.Connection, file_id: int) -> None:
    """Delete a file record (caller must commit)."""
    db.execute("DELETE FROM files WHERE id = ?", (file_id,))
