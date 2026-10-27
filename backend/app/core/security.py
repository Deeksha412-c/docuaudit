"""Password hashing and login tokens. Plain functions with no settings imports, so they are easy to test."""
import datetime

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ALGORITHM = "HS256"
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_token(user_id: str, secret: str, minutes: int = 480) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {"sub": user_id, "iat": now, "exp": now + datetime.timedelta(minutes=minutes)}
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str, secret: str):
    """The user id inside the token, or None if the token is invalid, tampered with or expired."""
    try:
        return jwt.decode(token, secret, algorithms=[ALGORITHM])["sub"]
    except (jwt.PyJWTError, KeyError):
        return None
