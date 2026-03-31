import os
import sqlite3

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load .env (EMAIL_USER, EMAIL_PASS, VIRUSTOTAL_API_KEY, etc.)
load_dotenv()

# ─── App Setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "S3cur3F!leM@nag3r_CH@NGE_IN_PROD")

CORS(app, supports_credentials=True, origins=["http://localhost:5000", "http://127.0.0.1:5000"])

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DATABASE      = os.path.join(BASE_DIR, "database.db")
FRONTEND_DIR  = os.path.join(os.path.dirname(BASE_DIR), "frontend")

app.config["UPLOAD_FOLDER"]      = UPLOAD_FOLDER
app.config["DATABASE"]           = DATABASE
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024   # 100 MB hard limit

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ─── Database Initialisation ──────────────────────────────────────────────────
def _add_column_if_missing(cur, table: str, column: str, definition: str) -> None:
    """Safely add a column to an existing table; ignore if already present."""
    try:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"[DB] Added column '{column}' to '{table}'.")
    except sqlite3.OperationalError:
        pass  # column already exists


def init_db():
    conn = sqlite3.connect(DATABASE)
    cur  = conn.cursor()

    # ── Users table ──────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT UNIQUE NOT NULL,
            email           TEXT UNIQUE NOT NULL,
            password_hash   TEXT NOT NULL,
            otp_secret      TEXT NOT NULL,
            risk_score      INTEGER NOT NULL DEFAULT 0,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            lock_until      DATETIME,
            last_failed_at  DATETIME,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migrate existing databases that predate any of these columns
    _add_column_if_missing(cur, "users", "risk_score",      "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(cur, "users", "failed_attempts", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(cur, "users", "lock_until",      "DATETIME")
    _add_column_if_missing(cur, "users", "last_failed_at",  "DATETIME")

    # ── Files table ──────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            stored_name   TEXT    NOT NULL,
            original_name TEXT    NOT NULL,
            size          INTEGER NOT NULL,
            mime_type     TEXT,
            expiry_time   TEXT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ── Shares table ─────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shares (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id       INTEGER NOT NULL,
            share_token   TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            expiry_time   TEXT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES files(id)
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Tables initialised.")


init_db()


# ─── Blueprints ───────────────────────────────────────────────────────────────
from routes.auth  import auth_bp
from routes.files import files_bp
from routes.share import share_bp

app.register_blueprint(auth_bp,  url_prefix="/api/auth")
app.register_blueprint(files_bp, url_prefix="/api/files")
app.register_blueprint(share_bp, url_prefix="/api/share")


# ─── Frontend Static Routes ───────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/dashboard")
def dashboard():
    return send_from_directory(FRONTEND_DIR, "dashboard.html")


@app.route("/share/<token>")
def share_page(token):
    return send_from_directory(FRONTEND_DIR, "share.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)


# ─── Error Handlers ───────────────────────────────────────────────────────────
@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "File too large. Maximum size is 100 MB."}), 413


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Resource not found."}), 404


# ─── Scheduler ────────────────────────────────────────────────────────────────
from utils.scheduler import start_scheduler
start_scheduler(app)


# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  Secure File Management System  —  http://localhost:5000")
    print("=" * 55 + "\n")
    app.run(debug=True, port=5000, use_reloader=False)
