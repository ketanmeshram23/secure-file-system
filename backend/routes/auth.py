import sqlite3
import bcrypt
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, session, current_app
from utils.otp import generate_otp_secret, get_current_otp, verify_otp_code, send_otp_email

auth_bp = Blueprint("auth", __name__)

# ── Lock thresholds (Task 10) ─────────────────────────────────────────────────
_LOCK_SCHEDULE = {
    3: timedelta(minutes=15),
    4: timedelta(minutes=30),
}
_LOCK_DEFAULT  = timedelta(hours=1)    # failed_attempts >= 5
_AUTO_RESET_H  = timedelta(hours=6)    # auto-reset window


# ─── DB Helper ────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(current_app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


# ─── Lock helpers (Task 10) ───────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _parse_dt(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return None


def _is_locked(user) -> bool:
    """Return True if the account is currently locked."""
    lock_until = _parse_dt(user["lock_until"])
    return lock_until is not None and lock_until > datetime.utcnow()


def _lock_duration(failed: int) -> timedelta | None:
    """Return the lock duration for the given failed-attempt count, or None."""
    if failed >= 5:
        return _LOCK_DEFAULT
    return _LOCK_SCHEDULE.get(failed)


def _handle_failed_login(db, user_id: int, current_attempts: int) -> None:
    """Increment failed_attempts and apply lock if threshold is crossed."""
    new_attempts  = current_attempts + 1
    now           = datetime.utcnow()
    lock_duration = _lock_duration(new_attempts)
    lock_until    = (now + lock_duration).isoformat() if lock_duration else None

    db.execute(
        """UPDATE users
           SET failed_attempts = ?,
               last_failed_at  = ?,
               lock_until      = COALESCE(?, lock_until)
           WHERE id = ?""",
        (new_attempts, now.isoformat(), lock_until, user_id),
    )
    db.commit()


def _handle_successful_login(db, user_id: int) -> None:
    """Reset all brute-force counters on successful password verification."""
    db.execute(
        """UPDATE users
           SET failed_attempts = 0,
               lock_until      = NULL,
               last_failed_at  = NULL
           WHERE id = ?""",
        (user_id,),
    )
    db.commit()


def _maybe_auto_reset(db, user) -> bool:
    """
    If the last failed attempt was >= 6 hours ago and the account is not
    currently locked, reset the counter.  Returns True if a reset occurred.
    """
    last_failed = _parse_dt(user["last_failed_at"])
    if last_failed is None:
        return False
    if datetime.utcnow() - last_failed >= _AUTO_RESET_H and not _is_locked(user):
        db.execute(
            """UPDATE users
               SET failed_attempts = 0,
                   lock_until      = NULL,
                   last_failed_at  = NULL
               WHERE id = ?""",
            (user["id"],),
        )
        db.commit()
        return True
    return False


# ─── Register ─────────────────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    data     = request.get_json(force=True) or {}
    username = data.get("username", "").strip()
    email    = data.get("email",    "").strip()
    password = data.get("password", "")

    if not username or not email or not password:
        return jsonify({"error": "All fields are required."}), 400

    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters."}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    if "@" not in email:
        return jsonify({"error": "Invalid email address."}), 400

    pw_hash    = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    otp_secret = generate_otp_secret()

    try:
        db = get_db()
        db.execute(
            "INSERT INTO users (username, email, password_hash, otp_secret) "
            "VALUES (?, ?, ?, ?)",
            (username, email, pw_hash, otp_secret),
        )
        db.commit()
        db.close()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username or email already exists."}), 409
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"message": "Registration successful. Please log in."}), 201


# ─── Login — Step 1: password check + lock enforcement ────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    data     = request.get_json(force=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    # ── Unknown user — return generic error (don't reveal existence) ──────
    if not user:
        db.close()
        return jsonify({"error": "Invalid credentials."}), 401

    # ── Task 10: auto-reset stale failed attempts ─────────────────────────
    _maybe_auto_reset(db, user)
    # Reload after potential reset
    user = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()

    # ── Task 10: check if account is locked ───────────────────────────────
    if _is_locked(user):
        lock_until = _parse_dt(user["lock_until"])
        remaining  = max(0, int((lock_until - datetime.utcnow()).total_seconds() // 60))
        db.close()
        return jsonify({
            "status":  "locked",
            "message": "Too many attempts. Try again later",
            "retry_in_minutes": remaining,
        }), 429

    # ── Password verification ─────────────────────────────────────────────
    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        failed_now = (user["failed_attempts"] or 0)
        _handle_failed_login(db, user["id"], failed_now)
        db.close()
        return jsonify({"error": "Invalid credentials."}), 401

    # ── Success: reset counters ───────────────────────────────────────────
    _handle_successful_login(db, user["id"])
    db.close()

    # ── Task 4: send OTP via email ────────────────────────────────────────
    current_otp = get_current_otp(user["otp_secret"])
    send_otp_email(
        to_email=user["email"],
        username=user["username"],
        otp_code=current_otp,
    )

    session["pending_user_id"]  = user["id"]
    session["pending_username"] = user["username"]

    return jsonify({
        "message":      "OTP sent to your registered email address.",
        "otp_required": True,
    }), 200


# ─── OTP Verification — Step 2 ────────────────────────────────────────────────
@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp_route():
    data = request.get_json(force=True) or {}
    otp  = data.get("otp", "").strip()

    pending_id = session.get("pending_user_id")
    if not pending_id:
        return jsonify({"error": "No pending login session."}), 400

    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (pending_id,)).fetchone()
    db.close()

    if not user:
        session.clear()
        return jsonify({"error": "User not found."}), 404

    if not verify_otp_code(user["otp_secret"], otp):
        return jsonify({"error": "Invalid or expired OTP. Try logging in again."}), 401

    session.pop("pending_user_id",  None)
    session.pop("pending_username", None)
    session["user_id"]  = user["id"]
    session["username"] = user["username"]

    return jsonify({"message": "Login successful.", "username": user["username"]}), 200


# ─── Logout ───────────────────────────────────────────────────────────────────
@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out."}), 200


# ─── Who Am I ─────────────────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["GET"])
def me():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated."}), 401
    return jsonify({"user_id": session["user_id"], "username": session["username"]}), 200
