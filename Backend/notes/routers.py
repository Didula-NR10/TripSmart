"""
notes.routers — the traveller's private notebook. Login required throughout;
every query is scoped to the authenticated user, so nobody reads anyone
else's notes.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from auth.deps import get_current_user
from core.database import db_available, get_session
from core.models import TravelNote, User

router = APIRouter(prefix="/api/v1/notes", tags=["Travel Notebook"])


class NoteCreate(BaseModel):
    place: str = Field(..., max_length=120, description="Where you went")
    body: str = Field(..., max_length=4000, description="What you saw / did")

    @field_validator("place", "body")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class NoteOut(BaseModel):
    id: str
    place: str
    body: str
    created_at: str


class NoteList(BaseModel):
    count: int
    notes: List[NoteOut]


def _require_db() -> None:
    if not db_available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The notebook needs the database; SUPABASE_DB_URL is not configured.",
        )


def _to_dict(n: TravelNote) -> dict:
    return {
        "id": str(n.id),
        "place": n.place,
        "body": n.body,
        "created_at": n.created_at.isoformat(),
    }


@router.get("", response_model=NoteList)
def list_notes(user: User = Depends(get_current_user)):
    """The logged-in user's notes, newest first."""
    _require_db()
    with get_session() as session:
        rows = (
            session.query(TravelNote)
            .filter(TravelNote.user_id == user.id)
            .order_by(TravelNote.created_at.desc())
            .limit(200)
            .all()
        )
        return {"count": len(rows), "notes": [_to_dict(n) for n in rows]}


@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_note(payload: NoteCreate, user: User = Depends(get_current_user)):
    """Write a notebook entry: where you went, what you saw."""
    _require_db()
    with get_session() as session:
        note = TravelNote(user_id=user.id, place=payload.place, body=payload.body)
        session.add(note)
        session.flush()
        session.refresh(note)
        return _to_dict(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: str, user: User = Depends(get_current_user)):
    """Remove one of your own notes."""
    _require_db()
    with get_session() as session:
        deleted = (
            session.query(TravelNote)
            .filter(TravelNote.id == note_id, TravelNote.user_id == user.id)
            .delete()
        )
        if not deleted:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Note not found.")
