from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.models.session import Session
from app.models.user import User

settings = get_settings()
_dummy_password_hash = hash_password("not-a-valid-user-password")


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Session"},
    )


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    normalized_email = email.casefold()
    user = await session.scalar(select(User).where(User.email == normalized_email))
    if user is None or not user.is_active:
        verify_password(password, _dummy_password_hash)
        raise unauthorized()
    if not verify_password(password, user.password_hash):
        raise unauthorized()
    return user


async def create_session(session: AsyncSession, user: User) -> tuple[Session, str]:
    now = datetime.now(UTC)
    raw_token = generate_session_token()
    record = Session(
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        expires_at=now + timedelta(hours=settings.session_ttl_hours),
        last_seen_at=now,
    )
    session.add(record)
    await session.commit()
    return record, raw_token


async def get_current_session(request: Request, db_session: AsyncSession) -> Session:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token is None:
        raise unauthorized()
    session_record = await db_session.scalar(
        select(Session)
        .options(selectinload(Session.user))
        .where(Session.token_hash == hash_session_token(raw_token))
    )
    now = datetime.now(UTC)
    expires_at = None
    if session_record is not None:
        expires_at = session_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
    if (
        session_record is None
        or session_record.revoked_at is not None
        or expires_at is None
        or expires_at <= now
        or not session_record.user.is_active
    ):
        raise unauthorized()
    session_record.last_seen_at = now
    await db_session.commit()
    return session_record


async def revoke_session(request: Request, db_session: AsyncSession) -> None:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token is None:
        return
    session_record = await db_session.scalar(
        select(Session).where(Session.token_hash == hash_session_token(raw_token))
    )
    if session_record is not None and session_record.revoked_at is None:
        session_record.revoked_at = datetime.now(UTC)
        await db_session.commit()


async def create_initial_admin(db_session: AsyncSession) -> None:
    if not settings.initial_admin_email or not settings.initial_admin_password:
        return
    email = settings.initial_admin_email.casefold()
    existing_user = await db_session.scalar(select(User).where(User.email == email))
    if existing_user is None:
        db_session.add(
            User(
                email=email,
                password_hash=hash_password(settings.initial_admin_password),
                is_active=True,
            )
        )
        await db_session.commit()
