"""Public tracked-link redirect with first-party click recording."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.api.dependencies import DbSession
from app.services.campaign import record_click

router = APIRouter(tags=["links"])


@router.get("/r/{tracking_id}")
async def follow_tracked_link(
    tracking_id: str, request: Request, db_session: DbSession
) -> RedirectResponse:
    if not tracking_id.isalnum() or len(tracking_id) > 64:
        raise HTTPException(status_code=404, detail="Tracked link not found")
    destination = await record_click(
        db_session, tracking_id, referrer=request.headers.get("referer")
    )
    if destination is None:
        raise HTTPException(status_code=404, detail="Tracked link not found")
    await db_session.commit()
    return RedirectResponse(
        url=destination,
        status_code=302,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )
