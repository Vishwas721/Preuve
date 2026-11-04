"""Password hashing and opaque tokens. Raw secrets are only ever returned once, never stored."""

import contextlib
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()  # argon2id with the library's current recommended parameters

MIN_PASSWORD_CHARS = 10
# The most common passwords of 10+ characters; anything here is refused outright.
_COMMON = {
    "1234567890",
    "12345678910",
    "0123456789",
    "1q2w3e4r5t",
    "qwertyuiop",
    "1qaz2wsx3edc",
    "password12",
    "password123",
    "password1234",
    "iloveyou12",
    "qwerty1234",
    "qwerty12345",
    "abcdefghij",
    "abc1234567",
    "aaaaaaaaaa",
    "letmein123",
    "welcome123",
    "changeme123",
    "administrator",
    "preuvepreuve",
}

SESSION_PREFIX = "ses_"
API_TOKEN_PREFIX = "prv_"
INVITE_PREFIX = "inv_"


class WeakPasswordError(ValueError):
    pass


def check_password_strength(password: str, email: str = "") -> None:
    if len(password) < MIN_PASSWORD_CHARS:
        raise WeakPasswordError(f"Use at least {MIN_PASSWORD_CHARS} characters.")
    low = password.lower()
    if low in _COMMON or len(set(low)) < 4:
        raise WeakPasswordError("That password is too common. Pick something less guessable.")
    local = email.split("@")[0].lower()
    if local and len(local) >= 4 and local in low:
        raise WeakPasswordError("Don't use your email address in the password.")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-ish time either way: an absent hash still runs a verification."""
    if not password_hash:
        _dummy_verify(password)  # same work as a real check, so timing doesn't reveal accounts
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


_DUMMY_HASH = _hasher.hash("not-a-real-password-just-for-timing")


def _dummy_verify(password: str) -> None:
    with contextlib.suppress(VerifyMismatchError, VerificationError, InvalidHashError):
        _hasher.verify(_DUMMY_HASH, password)


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_token(prefix: str) -> str:
    return prefix + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()
