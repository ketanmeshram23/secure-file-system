import io
import os
import uuid
import sqlite3
import bcrypt
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, session, send_file, current_app
from utils.encryption import decrypt_file

share_bp = Blueprint("share", __name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(current_app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def get_current_user():
    return session.get("user_id")


# ─── Create Share Link ────────────────────────────────────────────────────────
@share_bp.route("/create", methods=["POST"])
def create_share():
    user_id = get_current_user()
    if not user_id:
        return jsonify({"error": "Not authenticated."}), 401

    data         = request.get_json(force=True) or {}
    file_id      = data.get("file_id")
    password     = data.get("password", "")
    expiry_hours = data.get("expiry_hours", 24)

    if not file_id:
        return jsonify({"error": "file_id is required."}), 400
    if not password:
        return jsonify({"error": "A share password is required."}), 400
    if len(password) < 4:
        return jsonify({"error": "Share password must be at least 4 characters."}), 400

    db     = get_db()
    record = db.execute(
        "SELECT * FROM files WHERE id = ? AND user_id = ?", (file_id, user_id)
    ).fetchone()

    if not record:
        db.close()
        return jsonify({"error": "File not found or access denied."}), 404

    try:
        expiry_hours = max(1, int(expiry_hours))
    except (ValueError, TypeError):
        expiry_hours = 24

    share_token   = str(uuid.uuid4())
    pw_hash       = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    expiry_time   = (datetime.utcnow() + timedelta(hours=expiry_hours)).isoformat()

    db.execute(
        "INSERT INTO shares (file_id, share_token, password_hash, expiry_time) VALUES (?, ?, ?, ?)",
        (file_id, share_token, pw_hash, expiry_time),
    )
    db.commit()
    db.close()

    share_url = f"/share/{share_token}"
    return jsonify({
        "message":   "Share link created.",
        "share_url": share_url,
        "token":     share_token,
        "expires":   expiry_time,
    }), 201


# ─── Get Share Info (no password needed) ─────────────────────────────────────
@share_bp.route("/<token>", methods=["GET"])
def get_share_info(token):
    db    = get_db()
    share = db.execute(
        """SELECT s.expiry_time, f.original_name, f.size, f.expiry_time AS file_expiry
           FROM shares s
           JOIN files  f ON s.file_id = f.id
           WHERE s.share_token = ?""",
        (token,),
    ).fetchone()
    db.close()

    if not share:
        return jsonify({"error": "Share link not found."}), 404

    now = datetime.utcnow()

    if share["expiry_time"]:
        if datetime.fromisoformat(share["expiry_time"]) < now:
            return jsonify({"error": "This share link has expired."}), 410

    if share["file_expiry"]:
        if datetime.fromisoformat(share["file_expiry"]) < now:
            return jsonify({"error": "The file attached to this link has expired."}), 410

    return jsonify({
        "filename":    share["original_name"],
        "size":        share["size"],
        "expiry_time": share["expiry_time"],
    }), 200


# ─── Download via Share (password required) ───────────────────────────────────
@share_bp.route("/<token>/download", methods=["POST"])
def download_shared(token):
    data     = request.get_json(force=True) or {}
    password = data.get("password", "")

    if not password:
        return jsonify({"error": "Password is required."}), 400

    db    = get_db()
    share = db.execute(
        """SELECT s.password_hash, s.expiry_time,
                  f.stored_name, f.original_name, f.mime_type, f.expiry_time AS file_expiry
           FROM shares s
           JOIN files  f ON s.file_id = f.id
           WHERE s.share_token = ?""",
        (token,),
    ).fetchone()
    db.close()

    if not share:
        return jsonify({"error": "Share link not found."}), 404

    now = datetime.utcnow()

    if share["expiry_time"]:
        if datetime.fromisoformat(share["expiry_time"]) < now:
            return jsonify({"error": "This share link has expired."}), 410

    if share["file_expiry"]:
        if datetime.fromisoformat(share["file_expiry"]) < now:
            return jsonify({"error": "The file has expired."}), 410

    if not bcrypt.checkpw(password.encode(), share["password_hash"].encode()):
        return jsonify({"error": "Incorrect password."}), 401

    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], share["stored_name"])
    if not os.path.exists(file_path):
        return jsonify({"error": "File data is missing from server."}), 404

    with open(file_path, "rb") as fh:
        encrypted = fh.read()

    decrypted = decrypt_file(encrypted)

    return send_file(
        io.BytesIO(decrypted),
        download_name=share["original_name"],
        as_attachment=True,
        mimetype=share["mime_type"] or "application/octet-stream",
    )
