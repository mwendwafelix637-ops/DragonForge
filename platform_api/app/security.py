import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import pyotp
from cryptography.fernet import Fernet
from pwdlib import PasswordHash

from .config import settings

password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("NotARealDragonForgeAccount!2026")


def hash_password(password: str) -> str:
    validate_password(password)
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return password_hash.verify(password, hashed)
    except (ValueError, TypeError):
        return False


def validate_password(password: str) -> None:
    if len(password) < 12 or len(password) > 256:
        raise ValueError("Password must be between 12 and 256 characters")
    if not any(char.islower() for char in password) or not any(char.isupper() for char in password):
        raise ValueError("Password must include upper- and lowercase letters")
    if not any(char.isdigit() for char in password) or not any(not char.isalnum() for char in password):
        raise ValueError("Password must include a number and a symbol")


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def session_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours)


def _fernet() -> Fernet:
    key = settings.totp_encryption_key
    if not key:
        raise RuntimeError("DRAGONFORGE_TOTP_ENCRYPTION_KEY must be configured")
    return Fernet(key.encode())


def encrypt_totp_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_totp_secret(secret: str) -> str:
    return _fernet().decrypt(secret.encode()).decode()


def create_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def recovery_code_hash(code: str) -> str:
    pepper = settings.session_secret
    if not pepper:
        raise RuntimeError("DRAGONFORGE_SESSION_SECRET must be configured")
    return hmac.new(pepper.encode(), code.encode(), hashlib.sha256).hexdigest()


def generate_recovery_codes() -> list[str]:
    return [base64.b32encode(secrets.token_bytes(8)).decode().rstrip("=") for _ in range(10)]