import io
import os
import uuid
import sqlite3
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, session, send_file, current_app
from utils.encryption import encrypt_file, decrypt_file
from utils.virustotal import scan_with_virustotal

files_bp = Blueprint("files", __name__)

BLOCKED_EXTENSIONS = {"exe", "bat", "sh", "cmd", "msi", "vbs", "ps1", "scr", "pif", "com"}
MAX_UPLOAD_BYTES   = 100 * 1024 * 1024   # 100 MB
RISK_BLOCK_THRESHOLD = 3


# ─── Helpers ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(current_app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def get_current_user():
    return session.get("user_id")


def is_safe_filename(filename: str) -> bool:
    if not filename or "." not in filename:
        return True
    return filename.rsplit(".", 1)[-1].lower() not in BLOCKED_EXTENSIONS


# ─── Risk Score Helpers (Task 3) ──────────────────────────────────────────────
def get_user_risk_score(db, user_id: int) -> int:
    row = db.execute("SELECT risk_score FROM users WHERE id = ?", (user_id,)).fetchone()
    return int(row["risk_score"]) if row and row["risk_score"] is not None else 0


def increment_risk_score(db, user_id: int) -> int:
    db.execute(
        "UPDATE users SET risk_score = COALESCE(risk_score, 0) + 1 WHERE id = ?",
        (user_id,),
    )
    db.commit()
    return get_user_risk_score(db, user_id)


# ─── Upload ───────────────────────────────────────────────────────────────────
@files_bp.route("/upload", methods=["POST"])
def upload_file():
    user_id = get_current_user()
    if not user_id:
        return jsonify({"error": "Not authenticated."}), 401

    if "file" not in request.files:
        return jsonify({"error": "No file part in request."}), 400

    f              = request.files["file"]
    expiry_minutes = request.form.get("expiry_minutes", "").strip()

    if f.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not is_safe_filename(f.filename):
        return jsonify({"error": "File type is not allowed (.exe, .bat, .sh, etc.)."}), 400

    # ── Task 3: block high-risk users ─────────────────────────────────────
    db   = get_db()
    risk = get_user_risk_score(db, user_id)
    if risk >= RISK_BLOCK_THRESHOLD:
        db.close()
        return jsonify({
            "status": "restricted",
            "error":  "You are temporarily restricted due to suspicious activity.",
        }), 403

    raw_data  = f.read()
    file_size = len(raw_data)

    if file_size == 0:
        db.close()
        return jsonify({"error": "Cannot upload an empty file."}), 400

    if file_size > MAX_UPLOAD_BYTES:
        db.close()
        return jsonify({"error": "File exceeds the 100 MB limit."}), 400

    # ── Task 1 & 8: VirusTotal malware scan ───────────────────────────────
    # NEVER save file before scan completes
    is_clean, threat_name = scan_with_virustotal(raw_data)

    if is_clean is False and threat_name is None:
        # Scan failed / API error — block upload, surface failure message
        db.close()
        return jsonify({
            "status":  "blocked",
            "message": "Security scan failed",
        }), 400

    if not is_clean:
        # Malware detected — increment risk score, never save file
        new_score = increment_risk_score(db, user_id)
        db.close()
        print(
            f"[Security] Malware BLOCKED user_id={user_id} | "
            f"threat={threat_name} | risk_score={new_score}"
        )
        return jsonify({
            "status":      "blocked",
            "message":     "Security threat detected",
            "threat_type": threat_name or "Malicious File",
        }), 400

    # ── Encrypt and save (only after clean scan) ───────────────────────────
    encrypted   = encrypt_file(raw_data)
    stored_name = uuid.uuid4().hex + ".enc"
    file_path   = os.path.join(current_app.config["UPLOAD_FOLDER"], stored_name)
    with open(file_path, "wb") as out:
        out.write(encrypted)

    expiry_time = None
    if expiry_minutes:
        try:
            mins = int(expiry_minutes)
            if mins > 0:
                expiry_time = (datetime.utcnow() + timedelta(minutes=mins)).isoformat()
        except ValueError:
            pass

    db.execute(
        "INSERT INTO files (user_id, stored_name, original_name, size, mime_type, expiry_time) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, stored_name, f.filename, file_size, f.content_type, expiry_time),
    )
    db.commit()
    db.close()

    return jsonify({"message": f"'{f.filename}' uploaded and encrypted successfully."}), 201


# ─── List ─────────────────────────────────────────────────────────────────────
@files_bp.route("/list", methods=["GET"])
def list_files():
    user_id = get_current_user()
    if not user_id:
        return jsonify({"error": "Not authenticated."}), 401

    db   = get_db()
    rows = db.execute(
        "SELECT id, original_name, size, mime_type, expiry_time, created_at "
        "FROM files WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    db.close()

    now   = datetime.utcnow()
    files = []
    for r in rows:
        expired = False
        if r["expiry_time"]:
            try:
                expired = datetime.fromisoformat(r["expiry_time"]) < now
            except Exception:
                pass
        files.append({
            "id":          r["id"],
            "name":        r["original_name"],
            "size":        r["size"],
            "mime_type":   r["mime_type"],
            "expiry_time": r["expiry_time"],
            "created_at":  r["created_at"],
            "expired":     expired,
        })

    return jsonify({"files": files}), 200


# ─── Download ─────────────────────────────────────────────────────────────────
@files_bp.route("/download/<int:file_id>", methods=["GET"])
def download_file(file_id):
    user_id = get_current_user()
    if not user_id:
        return jsonify({"error": "Not authenticated."}), 401

    db     = get_db()
    record = db.execute(
        "SELECT * FROM files WHERE id = ? AND user_id = ?", (file_id, user_id)
    ).fetchone()
    db.close()

    if not record:
        return jsonify({"error": "File not found."}), 404

    if record["expiry_time"]:
        if datetime.fromisoformat(record["expiry_time"]) < datetime.utcnow():
            return jsonify({"error": "This file has expired."}), 410

    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], record["stored_name"])
    if not os.path.exists(file_path):
        return jsonify({"error": "File data missing from server."}), 404

    with open(file_path, "rb") as fh:
        encrypted = fh.read()

    decrypted = decrypt_file(encrypted)

    return send_file(
        io.BytesIO(decrypted),
        download_name=record["original_name"],
        as_attachment=True,
        mimetype=record["mime_type"] or "application/octet-stream",
    )


# ─── Delete ───────────────────────────────────────────────────────────────────
@files_bp.route("/delete/<int:file_id>", methods=["DELETE"])
def delete_file(file_id):
    user_id = get_current_user()
    if not user_id:
        return jsonify({"error": "Not authenticated."}), 401

    db     = get_db()
    record = db.execute(
        "SELECT * FROM files WHERE id = ? AND user_id = ?", (file_id, user_id)
    ).fetchone()

    if not record:
        db.close()
        return jsonify({"error": "File not found."}), 404

    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], record["stored_name"])
    if os.path.exists(file_path):
        os.remove(file_path)

    db.execute("DELETE FROM shares WHERE file_id = ?", (file_id,))
    db.execute("DELETE FROM files  WHERE id = ?",      (file_id,))
    db.commit()
    db.close()

    return jsonify({"message": "File deleted successfully."}), 200
