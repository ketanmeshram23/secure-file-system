"""
TOTP-based one-time password helpers using pyotp.

Task 4: OTP is now delivered via Gmail SMTP.
- Set EMAIL_USER and EMAIL_PASS as environment variables (or in a .env file).
- If env vars are missing the OTP falls back to console print so development
  still works without an email account configured.
"""

import os
import smtplib
import pyotp
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# ─── TOTP Helpers ─────────────────────────────────────────────────────────────

def generate_otp_secret() -> str:
    """Return a fresh, random base-32 TOTP secret for a new user."""
    return pyotp.random_base32()


def get_current_otp(secret: str) -> str:
    """Return the current 6-digit TOTP code for the given secret."""
    return pyotp.TOTP(secret).now()


def verify_otp_code(secret: str, code: str) -> bool:
    """
    Verify a user-supplied OTP code with a ±30-second tolerance window.
    """
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def get_provisioning_uri(secret: str, username: str, issuer: str = "SecureVault") -> str:
    """Return an otpauth:// URI for QR-code generation."""
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


# ─── Email Delivery ────────────────────────────────────────────────────────────

def send_otp_email(to_email: str, username: str, otp_code: str) -> bool:
    """
    Send the OTP to the user's registered email via Gmail SMTP.

    Requires:
        EMAIL_USER  — Gmail address used to send (e.g. yourapp@gmail.com)
        EMAIL_PASS  — Gmail App Password (not your account password)

    Returns True if email was sent, False if it fell back to console.
    """
    email_user = os.environ.get("EMAIL_USER", "").strip()
    email_pass = os.environ.get("EMAIL_PASS", "").strip()

    if not email_user or not email_pass:
        # ── Fallback: print to console ────────────────────────────────────────
        print(f"\n{'─' * 55}")
        print(f"  [OTP FALLBACK]  Email not configured.")
        print(f"  OTP for '{username}' → {otp_code}")
        print(f"{'─' * 55}\n")
        return False

    subject = "SecureVault OTP"
    body    = (
        f"Hello {username},\n\n"
        f"Your SecureVault one-time password is:\n\n"
        f"    {otp_code}\n\n"
        f"This code is valid for 30 seconds.\n"
        f"If you did not request this, please ignore this email.\n\n"
        f"— SecureVault Security"
    )

    msg               = MIMEMultipart("alternative")
    msg["From"]       = f"SecureVault <{email_user}>"
    msg["To"]         = to_email
    msg["Subject"]    = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(email_user, email_pass)
            server.send_message(msg)
        print(f"[OTP] Email sent to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("[OTP] Gmail authentication failed. Check EMAIL_USER / EMAIL_PASS.")
    except smtplib.SMTPException as exc:
        print(f"[OTP] SMTP error: {exc}")
    except Exception as exc:
        print(f"[OTP] Unexpected email error: {exc}")

    # Final fallback on any email error — never leave user stuck
    print(f"\n{'─' * 55}")
    print(f"  [OTP FALLBACK]  Email delivery failed.")
    print(f"  OTP for '{username}' → {otp_code}")
    print(f"{'─' * 55}\n")
    return False
