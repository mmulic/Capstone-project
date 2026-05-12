"""
Auth Router (BE-021)
=====================
POST /api/auth/register — Create user
POST /api/auth/login    — Get access + refresh tokens
POST /api/auth/refresh  — Refresh access token
GET  /api/auth/me       — Get current user info
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import User
from app.services.auth_service import auth_service
from app.schemas.schemas import UserCreate, UserResponse, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ── Dependency: Get current user from JWT ────────────────

async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency that extracts the current user from a Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split(" ", 1)[1]
    payload = auth_service.decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


# ── Endpoints ────────────────────────────────────────────

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account."""
    # Check if email already exists
    existing = await db.execute(select(User).where(User.email == user_data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=user_data.email,
        hashed_password=auth_service.hash_password(user_data.password),
        full_name=user_data.full_name,
    )
    db.add(user)
    await db.flush()

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: dict,
    db: AsyncSession = Depends(get_db),
):
    """Login with email + password. Returns access + refresh tokens."""
    email = credentials.get("email")
    password = credentials.get("password")

    if not email or not password:
        raise HTTPException(status_code=422, detail="Email and password required")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not auth_service.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    return TokenResponse(
        access_token=auth_service.create_access_token(str(user.id), user.email),
        refresh_token=auth_service.create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a refresh token for a new access token."""
    refresh = body.get("refresh_token")
    if not refresh:
        raise HTTPException(status_code=422, detail="refresh_token required")

    payload = auth_service.decode_token(refresh)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=auth_service.create_access_token(str(user.id), user.email),
        refresh_token=auth_service.create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return information about the currently authenticated user."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
