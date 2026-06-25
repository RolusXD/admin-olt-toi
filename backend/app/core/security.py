import base64
import hashlib
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

password_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.crypto_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")


def create_access_token(subject: str, minutes: int = 720) -> str:
    expires = datetime.now(UTC) + timedelta(minutes=minutes)
    return jwt.encode({"sub": subject, "exp": expires}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_password(plain: str, hashed: str) -> bool:
    return password_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return password_context.hash(plain)


def decode_access_token(token: str) -> str:
    """Decode a JWT access token and return its subject (username).

    The function is intentionally HTTP-framework agnostic: it raises
    ``ValueError`` when the token is invalid, expired or does not contain a
    non-empty ``sub`` claim. Callers (e.g. FastAPI dependencies) are
    responsible for translating those errors into HTTP responses.
    """

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:  # pragma: no cover - exercised indirectly in API deps
        raise ValueError("Invalid access token") from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("Invalid access token payload: missing subject")
    return subject
