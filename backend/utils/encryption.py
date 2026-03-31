"""
AES encryption / decryption via Fernet (AES-128-CBC + HMAC-SHA256).
The key is generated once and persisted in secret.key inside the backend folder.
"""

import os
from cryptography.fernet import Fernet, InvalidToken

_KEY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "secret.key")


def _load_or_create_key() -> bytes:
    """Load the Fernet key from disk, creating it on first run."""
    if os.path.exists(_KEY_PATH):
        with open(_KEY_PATH, "rb") as fh:
            key = fh.read().strip()
        # Basic sanity-check: Fernet keys are 44 URL-safe base64 characters
        if len(key) == 44:
            return key
        # If corrupted, regenerate
        print("[Encryption] WARNING: Existing key is invalid. Regenerating…")

    key = Fernet.generate_key()
    with open(_KEY_PATH, "wb") as fh:
        fh.write(key)
    print(f"[Encryption] New encryption key generated and saved to {_KEY_PATH}")
    return key


_KEY    = _load_or_create_key()
_fernet = Fernet(_KEY)


def encrypt_file(data: bytes) -> bytes:
    """Encrypt raw bytes and return Fernet ciphertext."""
    if not isinstance(data, bytes):
        raise TypeError("encrypt_file expects bytes input.")
    return _fernet.encrypt(data)


def decrypt_file(data: bytes) -> bytes:
    """Decrypt Fernet ciphertext and return raw bytes.

    Raises cryptography.fernet.InvalidToken if the data is corrupt / wrong key.
    """
    if not isinstance(data, bytes):
        raise TypeError("decrypt_file expects bytes input.")
    try:
        return _fernet.decrypt(data)
    except InvalidToken:
        raise ValueError("Decryption failed: invalid token or corrupted file data.")
