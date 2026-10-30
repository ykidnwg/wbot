from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.session import Session
from app.models.user import User
from app.services.auth import get_current_session

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def current_session(request: Request, db_session: DbSession) -> Session:
    return await get_current_session(request, db_session)


async def current_user(session_record: Annotated[Session, Depends(current_session)]) -> User:
    user = session_record.user
    if not isinstance(user, User):
        raise RuntimeError("Authenticated session has no user")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
