"""
Background scheduler — deletes expired files and share links every minute.
Uses APScheduler's BackgroundScheduler so it runs in a daemon thread
alongside the Flask development server.
"""

import os
import sqlite3
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR


# ─── Job ──────────────────────────────────────────────────────────────────────
def _delete_expired(app):
    """Called every minute inside an app-context to reap stale data."""
    with app.app_context():
        db_path       = app.config["DATABASE"]
        upload_folder = app.config["UPLOAD_FOLDER"]
        now_iso       = datetime.utcnow().isoformat()

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # 1. Expired files ---------------------------------------------------
        expired_files = conn.execute(
            "SELECT * FROM files WHERE expiry_time IS NOT NULL AND expiry_time < ?",
            (now_iso,),
        ).fetchall()

        for rec in expired_files:
            path = os.path.join(upload_folder, rec["stored_name"])
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as exc:
                    print(f"[Scheduler] Could not delete {path}: {exc}")

            conn.execute("DELETE FROM shares WHERE file_id = ?", (rec["id"],))
            conn.execute("DELETE FROM files  WHERE id = ?",      (rec["id"],))

            print(f"[Scheduler] ⏱  Expired file removed: '{rec['original_name']}'")

        # 2. Expired share links (keep the file, just kill the link) ---------
        deleted_shares = conn.execute(
            "DELETE FROM shares WHERE expiry_time IS NOT NULL AND expiry_time < ?",
            (now_iso,),
        ).rowcount

        if deleted_shares:
            print(f"[Scheduler] ⏱  Removed {deleted_shares} expired share link(s).")

        conn.commit()
        conn.close()


# ─── Error listener ───────────────────────────────────────────────────────────
def _on_job_error(event):
    if event.exception:
        print(f"[Scheduler] Job error: {event.exception}")


# ─── Public API ───────────────────────────────────────────────────────────────
def start_scheduler(app) -> BackgroundScheduler:
    """
    Initialise and start the background scheduler.
    Returns the scheduler instance (useful for testing / shutdown).
    """
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    scheduler.add_job(
        func=_delete_expired,
        args=[app],
        trigger="interval",
        minutes=1,
        id="delete_expired_files",
        replace_existing=True,
    )

    scheduler.start()
    print("[Scheduler] Started — checking for expired files every 60 s.")
    return scheduler
