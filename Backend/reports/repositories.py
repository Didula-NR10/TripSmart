"""
reports.repositories — ground_reports persistence.

Every read and write first purges anything older than 24 hours, so expiry
needs no scheduler: the table cleans itself on use, and the database is never
serving stale reports.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
import uuid
from typing import List, Optional

from sqlalchemy import and_, or_

from core.database import db_available, get_session
from core.models import District, GroundReport, PushSubscription, User

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

    def create(
        self,
        district: str,
        location: str,
        title: str,
        body: str,
        author: str = "",
        posted_by_id: Optional[uuid.UUID] = None,
    ) -> Optional[dict]:
        """Returns the stored report, or None when the district is unknown."""
        if not db_available():
            raise RuntimeError("Database is not configured.")
        with get_session() as session:
            self._purge_expired(session)
            d = self._district_by_name(session, district)
            if d is None:
                return None
            report = GroundReport(
                district_id=d.id,
                location=location,
                title=title,
                body=body,
                author=author,
                posted_by_id=posted_by_id,
            )
            session.add(report)
            session.flush()          # server defaults (id, created_at) come back
            session.refresh(report)
            out = self._to_dict(report, d.name)
            out["_district_id"] = d.id  # internal only — ReportOut doesn't declare this field
            return out

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

            # Avatar lookup: prefer the stable posted_by_id link, which
            # survives the poster renaming their username; fall back to a
            # username-text match only for legacy rows that predate that
            # column (posted_by_id is NULL).
            user_ids = {r.posted_by_id for r, _ in rows if r.posted_by_id}
            avatars_by_id: dict = {}
            if user_ids:
                avatars_by_id = dict(
                    session.query(User.id, User.avatar_url)
                    .filter(User.id.in_(user_ids))
                    .all()
                )
            legacy_authors = {r.author for r, _ in rows if r.author and not r.posted_by_id}
            avatars_by_name: dict = {}
            if legacy_authors:
                avatars_by_name = dict(
                    session.query(User.username, User.avatar_url)
                    .filter(User.username.in_(legacy_authors))
                    .all()
                )
            return [
                self._to_dict(
                    r, name, avatars_by_id.get(r.posted_by_id) or avatars_by_name.get(r.author, "")
                )
                for r, name in rows
            ]

    def delete(self, report_id: str, user_id: uuid.UUID, author: str) -> bool:
        """Delete a report — only its own poster may remove it. Authorizes on
        the stable posted_by_id when the row has one; falls back to the
        author-name match only for legacy rows without it (posted before
        posted_by_id existed). Returns whether a row was actually deleted
        (False = not found / not yours)."""
        if not db_available():
            raise RuntimeError("Database is not configured.")
        with get_session() as session:
            self._purge_expired(session)
            deleted = (
                session.query(GroundReport)
                .filter(
                    GroundReport.id == report_id,
                    or_(
                        GroundReport.posted_by_id == user_id,
                        and_(
                            GroundReport.posted_by_id.is_(None),
                            GroundReport.author == author,
                        ),
                    ),
                )
                .delete(synchronize_session=False)
            )
            return bool(deleted)

    def subscribe(self, expo_token: str, district: str) -> bool:
        """This device now wants ground-report alerts for `district`, replacing
        whatever district it was previously subscribed to. Returns False when
        the district name is unrecognised."""
        if not db_available():
            raise RuntimeError("Database is not configured.")
        with get_session() as session:
            d = self._district_by_name(session, district)
            if d is None:
                return False
            existing = (
                session.query(PushSubscription)
                .filter(PushSubscription.expo_token == expo_token)
                .first()
            )
            if existing:
                existing.district_id = d.id
                existing.updated_at = datetime.now(timezone.utc)
            else:
                session.add(PushSubscription(expo_token=expo_token, district_id=d.id))
            return True

    def tokens_for_district(self, district_id, exclude_token: str = "") -> List[str]:
        """Every device currently subscribed to this district, minus the
        poster's own token (if supplied) so they don't get pushed their own
        report."""
        if not db_available():
            return []
        with get_session() as session:
            q = session.query(PushSubscription.expo_token).filter(
                PushSubscription.district_id == district_id
            )
            if exclude_token:
                q = q.filter(PushSubscription.expo_token != exclude_token)
            return [t for (t,) in q.all()]

    @staticmethod
    def _to_dict(r: GroundReport, district_name: str, author_avatar: str = "") -> dict:
        return {
            "id": str(r.id),
            "district": district_name,
            "location": r.location,
            "title": r.title,
            "body": r.body or "",
            "author": r.author or "",
            "author_avatar": author_avatar or "",
            "created_at": r.created_at.isoformat(),
        }
