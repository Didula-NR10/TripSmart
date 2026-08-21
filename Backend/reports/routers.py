"""
reports.routers — HTTP surface for ground reports. Thin: validate, delegate.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth.deps import get_current_user
from core.models import User
from reports.push import send_district_push
from reports.repositories import ReportRepository
from reports.schemas import (
    ReportCreate,
    ReportList,
    ReportOut,
    SubscribeRequest,
    SubscribeResponse,
)

router = APIRouter(prefix="/api/v1/reports", tags=["Ground Reports"])
repo = ReportRepository()


@router.get("", response_model=ReportList)
def list_reports(
    district: Optional[str] = Query(default=None, description="Filter to one district, e.g. 'Colombo'"),
    search: Optional[str] = Query(default=None, description="Match against title, detail and location"),
):
    """Live traveller reports from the last 24 hours, newest first.

    Reports older than 24 hours are deleted, not hidden — the query itself
    purges them before answering.
    """
    try:
        reports = repo.list(district=district, search=search)
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return {"count": len(reports), "reports": reports}


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
async def create_report(payload: ReportCreate, user: User = Depends(get_current_user)):
    """Publish a ground report — login required. Visible for 24 hours, then
    expires. Every other device currently subscribed to this district gets
    an Expo push about it (the poster's own device is excluded via
    exclude_token); a failed push send never blocks the response below."""
    try:
        created = repo.create(
            district=payload.district.strip(),
            location=payload.location,
            title=payload.title,
            body=payload.body,
            author=user.username,
        )
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    if created is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Unknown district '{payload.district}'.",
        )

    district_id = created.pop("_district_id", None)
    if district_id is not None:
        tokens = repo.tokens_for_district(district_id, exclude_token=payload.exclude_token)
        await send_district_push(
            tokens,
            title=f"New ground report in {created['district']}",
            body=f"{created['title']} — {created['location']}",
            data={
                "districtKey": created["district"],
                "reportId": created["id"],
                "kind": "report",
                "remote": True,
            },
        )

    return created


@router.post("/subscribe", response_model=SubscribeResponse)
def subscribe(payload: SubscribeRequest):
    """Register (or move) this device's push token to one district, so it
    gets alerted whenever someone else posts a ground report there. No login
    needed — anyone with the app open in a district can opt into its alerts."""
    try:
        ok = repo.subscribe(payload.expo_token.strip(), payload.district.strip())
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    if not ok:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Unknown district '{payload.district}'.",
        )
    return {"message": f"Subscribed to ground-report alerts for {payload.district}."}


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(report_id: str, user: User = Depends(get_current_user)):
    """Delete one of YOUR OWN reports. Login required; you cannot delete
    someone else's report — the response doesn't distinguish "not found"
    from "not yours" so it never confirms another user's report exists."""
    try:
        deleted = repo.delete(report_id, author=user.username)
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    if not deleted:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Report not found, already expired, or not yours to delete.",
        )
