"""
reports.routers — HTTP surface for ground reports. Thin: validate, delegate.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth.deps import get_current_user
from core.models import User
from reports.repositories import ReportRepository
from reports.schemas import ReportCreate, ReportList, ReportOut

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
def create_report(payload: ReportCreate, user: User = Depends(get_current_user)):
    """Publish a ground report — login required. Visible for 24 hours, then expires."""
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
    return created


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
