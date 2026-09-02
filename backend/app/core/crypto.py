"""
Symmetric encryption for sensitive values stored at rest — currently
used for user-provided database connection strings (see
app.db.models.DatabaseConnection).

Uses Fernet (from the `cryptography` package): authenticated
symmetric encryption, single key, no infrastructure required beyond
one secret in .env. Appropriate for a single-key, single-app setup
like this; a real multi-tenant deployment would typically move to a
managed secrets service (e.g. AWS KMS, Vault) instead of a static key
in an env var — noted here rather than silently assumed away.
"""
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _get_fernet() -> Fernet:
    settings = get_settings()
    return Fernet(settings.encryption_key.encode())


def encrypt(plaintext: str) -> str:
    """Encrypts a string for storage. Returns a URL-safe base64 token."""
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """
    Decrypts a token produced by encrypt(). Raises ValueError if the
    token is invalid or was encrypted with a different key — this
    surfaces as a clear error rather than silently returning garbage.
    """
    fernet = _get_fernet()
    try:
        return fernet.decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise ValueError("Failed to decrypt value — invalid token or wrong encryption key.") from e