"""
Auth Service (BE-021)
======================
JWT token generation/validation and password hashing.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Handles password hashing and JWT operations."""

    # ── Password ─────────────────────────────────────────

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    # ── JWT ──────────────────────────────────────────────

    def create_access_token(self, user_id: str, email: str) -> str:
        """Create a short-lived access token."""
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
        payload = {
            "sub": str(user_id),
            "email": email,
            "exp": expire,
            "type": "access",
        }
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        """Create a long-lived refresh token."""
        expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "type": "refresh",
        }
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    def decode_token(self, token: str) -> Optional[dict]:
        """Decode and validate a JWT. Returns payload or None if invalid."""
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            return payload
        except JWTError:
            return None


auth_service = AuthService()
