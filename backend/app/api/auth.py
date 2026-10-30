from fastapi import APIRouter, Request, Response, status

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import get_settings
from app.schemas.auth import CurrentUserResponse, LoginRequest
from app.services.auth import authenticate_user, create_session, revoke_session

router = APIRouter(prefix="/auth", tags=["authentication"])
settings = get_settings()


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
async def login(credentials: LoginRequest, response: Response, db_session: DbSession) -> None:
    user = await authenticate_user(db_session, str(credentials.email), credentials.password)
    _, raw_token = await create_session(db_session, user)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_ttl_hours * 60 * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(current_user: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse(id=current_user.id, email=current_user.email)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, db_session: DbSession, request: Request) -> None:
    await revoke_session(request, db_session)
    response.delete_cookie(key=settings.session_cookie_name, path="/")
