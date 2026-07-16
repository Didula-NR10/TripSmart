"""
reports.repositories — ground_reports persistence.

Every read and write first purges anything older than 24 hours, so expiry
needs no scheduler: the table cleans itself on use, and the database is never
serving stale reports.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import or_

from core.database import db_available, get_session
from core.models import District, GroundReport

log = logging.getLogger("trip_smart.reports.repo")

REPORT_TTL_HOURS = 24


class ReportRepository:

    def _purge_expired(self, session) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=REPORT_TTL_HOURS)
        session.query(GroundReport).filter(GroundReport.created_at < cutoff).delete(
            synchronize_session=False
        )

    def _district_by_name(self, session, name: str) -> Optional[District]:
        return session.query(District).filter(District.name == name).first()

    def create(self, district: str, location: str, title: str, body: str) -> Optional[dict]:
        """Returns the stored report, or None when the district is unknown."""
        if not db_available():
            raise RuntimeError("Database is not configured.")
        with get_session() as session:
            self._purge_expired(session)
            d = self._district_by_name(session, district)
            if d is None:
                return None
            report = GroundReport(
                district_id=d.id, location=location, title=title, body=body
            )
            session.add(report)
            session.flush()          # server defaults (id, created_at) come back
            session.refresh(report)
            return self._to_dict(report, d.name)

    def list(self, district: Optional[str] = None, search: Optional[str] = None) -> List[dict]:
        """Live reports, newest first. `district` narrows to one district;
        `search` matches title, body or location, case-insensitively. Both
        combine: filter by Colombo + search 'rain' = rain reports in Colombo."""
        if not db_available():
            raise RuntimeError("Database is not configured.")
        with get_session() as session:
            self._purge_expired(session)

            query = (
                session.query(GroundReport, District.name)
                .join(District, District.id == GroundReport.district_id)
            )
            if district:
                query = query.filter(District.name == district)
            if search:
                needle = f"%{search.strip()}%"
                query = query.filter(
                    or_(
                        GroundReport.title.ilike(needle),
                        GroundReport.body.ilike(needle),
                        GroundReport.location.ilike(needle),
                    )
                )
            rows = query.order_by(GroundReport.created_at.desc()).limit(100).all()
            return [self._to_dict(r, name) for r, name in rows]

    @staticmethod
    def _to_dict(r: GroundReport, district_name: str) -> dict:
        return {
            "id": str(r.id),
            "district": district_name,
            "location": r.location,
            "title": r.title,
            "body": r.body or "",
            "created_at": r.created_at.isoformat(),
        }
