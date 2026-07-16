"""
reports.routers — HTTP surface for ground reports. Thin: validate, delegate.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

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
def create_report(payload: ReportCreate):
    """Publish a ground report. It stays visible for 24 hours, then expires."""
    try:
        created = repo.create(
            district=payload.district.strip(),
            location=payload.location,
            title=payload.title,
            body=payload.body,
        )
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    if created is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Unknown district '{payload.district}'.",
        )
    return created
