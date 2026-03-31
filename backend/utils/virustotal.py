"""
VirusTotal v3 API — malware scanning helper.

Usage:
    is_clean, threat_name = scan_with_virustotal(file_bytes)

Environment variable required:
    VIRUSTOTAL_API_KEY  — your VirusTotal API key

Behaviour:
  - Uploads the file bytes to /files/upload
  - Polls /analyses/{id} until status == 'completed' (max 60 s)
  - Returns (False, threat_name) if any engine flags as malicious
  - Returns (True, None) if all engines are clean
  - On any API/network error → returns (False, None) so caller can block
    the upload and surface a "scan failed" message (fail-closed)

Free-tier note:
  VirusTotal free API allows ~4 requests/minute and 500/day.
  Files are cached by SHA-256; identical files won't consume quota.
"""

import os
import time
import hashlib
import requests

_VT_BASE    = "https://www.virustotal.com/api/v3"
_POLL_SLEEP = 5      # seconds between status polls
_POLL_MAX   = 12     # maximum poll attempts (= 60 s total wait)


def _api_key() -> str:
    key = os.environ.get("VIRUSTOTAL_API_KEY", "").strip()
    return key


def _headers() -> dict:
    return {"x-apikey": _api_key(), "Accept": "application/json"}


def _extract_threat_name(stats: dict, results: dict) -> str:
    """
    Walk per-engine results and return the first meaningful malware name,
    or 'Malicious File' if none can be extracted.
    """
    for engine_result in results.values():
        category = engine_result.get("category", "")
        name     = engine_result.get("result") or ""
        if category in ("malicious", "suspicious") and name:
            return name
    return "Malicious File"


def scan_with_virustotal(file_bytes: bytes) -> tuple:
    """
    Scan file bytes with VirusTotal.

    Returns:
        (is_clean: bool, threat_name: str | None)
          is_clean=True  → file passed all engines
          is_clean=False → at least one engine flagged it
          threat_name    → malware name string, or None on scan failure
    """
    key = _api_key()
    if not key:
        print("[VirusTotal] VIRUSTOTAL_API_KEY not set. Blocking upload as precaution.")
        return False, None

    # ── Step 1: Check if file is already known by SHA-256 ─────────────────
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    try:
        resp = requests.get(
            f"{_VT_BASE}/files/{sha256}",
            headers=_headers(),
            timeout=15,
        )
        if resp.status_code == 200:
            data    = resp.json().get("data", {})
            attrs   = data.get("attributes", {})
            stats   = attrs.get("last_analysis_stats", {})
            results = attrs.get("last_analysis_results", {})
            malicious  = stats.get("malicious",  0)
            suspicious = stats.get("suspicious", 0)
            if malicious > 0 or suspicious > 0:
                threat = _extract_threat_name(stats, results)
                print(f"[VirusTotal] Known malicious file: {sha256[:16]}… | threat={threat}")
                return False, threat
            if stats.get("undetected", 0) > 0 or stats.get("harmless", 0) > 0:
                print(f"[VirusTotal] Known clean file (cached): {sha256[:16]}…")
                return True, None
            # If stats are empty/zero fall through to fresh upload
    except requests.RequestException as exc:
        print(f"[VirusTotal] Hash lookup failed ({exc}). Uploading for fresh scan.")

    # ── Step 2: Upload file for scanning ──────────────────────────────────
    try:
        upload_resp = requests.post(
            f"{_VT_BASE}/files",
            headers=_headers(),
            files={"file": ("upload", file_bytes, "application/octet-stream")},
            timeout=60,
        )
    except requests.RequestException as exc:
        print(f"[VirusTotal] Upload request failed: {exc}")
        return False, None  # fail-closed

    if upload_resp.status_code not in (200, 201):
        print(f"[VirusTotal] Upload HTTP {upload_resp.status_code}: {upload_resp.text[:200]}")
        return False, None

    analysis_id = upload_resp.json().get("data", {}).get("id")
    if not analysis_id:
        print("[VirusTotal] No analysis ID in upload response.")
        return False, None

    # ── Step 3: Poll for completion ────────────────────────────────────────
    for attempt in range(1, _POLL_MAX + 1):
        time.sleep(_POLL_SLEEP)
        try:
            poll_resp = requests.get(
                f"{_VT_BASE}/analyses/{analysis_id}",
                headers=_headers(),
                timeout=15,
            )
        except requests.RequestException as exc:
            print(f"[VirusTotal] Poll attempt {attempt} failed: {exc}")
            continue

        if poll_resp.status_code != 200:
            print(f"[VirusTotal] Poll HTTP {poll_resp.status_code}")
            continue

        poll_data = poll_resp.json().get("data", {})
        attrs     = poll_data.get("attributes", {})
        status    = attrs.get("status", "")

        if status != "completed":
            print(f"[VirusTotal] Attempt {attempt}/{_POLL_MAX}: status={status}")
            continue

        # Completed — evaluate results
        stats   = attrs.get("stats",   {})
        results = attrs.get("results", {})
        malicious  = stats.get("malicious",  0)
        suspicious = stats.get("suspicious", 0)

        if malicious > 0 or suspicious > 0:
            threat = _extract_threat_name(stats, results)
            print(
                f"[VirusTotal] MALICIOUS — malicious={malicious} "
                f"suspicious={suspicious} threat={threat}"
            )
            return False, threat

        print(
            f"[VirusTotal] Clean — malicious={malicious} "
            f"suspicious={suspicious} harmless={stats.get('harmless', 0)}"
        )
        return True, None

    # Timed out waiting for analysis
    print(f"[VirusTotal] Analysis timed out after {_POLL_MAX * _POLL_SLEEP}s.")
    return False, None  # fail-closed on timeout
