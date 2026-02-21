"""
Fernet-based symmetric encryption for sensitive data (eBay OAuth tokens).

Uses the ENCRYPTION_KEY from app settings. The key must be a valid
Fernet key (base64-encoded 32 bytes), generated with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazily initialize the Fernet cipher from settings."""
    global _fernet
    if _fernet is None:
        settings = get_settings()
        _fernet = Fernet(settings.encryption_key.encode())
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return the base64-encoded ciphertext."""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext and return the plaintext string."""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        # If token can't be decrypted (e.g., stored before encryption was enabled),
        # return the raw value as a fallback so existing unencrypted tokens still work.
        return ciphertext
