from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from auth.deps import get_current_user
from core.database import db_available, get_session
from core.models import TravelJournal, TravelNote, User

router = APIRouter(prefix="/api/v1/journals", tags=["Travel Journal"])

MAX_PAGES_PER_BOOK = 10

def _require_db() -> None:
    if not db_available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The journal needs the database; SUPABASE_DB_URL is not configured.",
        )

class JournalCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=80)

class PageCreate(BaseModel):
    place: str = Field(..., max_length=120, description="Where you went")
    body: str = Field(..., max_length=4000, description="What you saw / did")
    photo_url: str = Field("", max_length=2000, description="Cloudinary URL, if a photo was added")

    @field_validator("place", "body")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

class PageOut(BaseModel):
    id: str
    page_number: int
    place: str
    body: str
    photo_url: str
    created_at: str

class JournalOut(BaseModel):
    id: str
    title: str
    created_at: str
    page_count: int

class JournalDetail(JournalOut):
    pages: List[PageOut]

def _page_dict(n: TravelNote) -> dict:
    return {
        "id": str(n.id),
        "page_number": n.page_number,
        "place": n.place,
        "body": n.body,
        "photo_url": n.photo_url,
        "created_at": n.created_at.isoformat(),
    }

def _book_dict(b: TravelJournal, page_count: int) -> dict:
    return {
        "id": str(b.id),
        "title": b.title,
        "created_at": b.created_at.isoformat(),
        "page_count": page_count,
    }

@router.get("", response_model=List[JournalOut])
def list_journals(user: User = Depends(get_current_user)):
    """Every book the traveller has started, newest first."""
    _require_db()
    with get_session() as session:
        books = (
            session.query(TravelJournal)
            .filter(TravelJournal.user_id == user.id)
            .order_by(TravelJournal.created_at.desc())
            .all()
        )
        counts = {
            b.id: session.query(TravelNote).filter(TravelNote.journal_id == b.id).count()
            for b in books
        }
        return [_book_dict(b, counts[b.id]) for b in books]

@router.post("", response_model=JournalOut, status_code=status.HTTP_201_CREATED)
def create_journal(payload: JournalCreate, user: User = Depends(get_current_user)):
    """Start a new book. Untitled books are auto-numbered ('Book 1', 'Book 2', ...)."""
    _require_db()
    with get_session() as session:
        existing_count = (
            session.query(TravelJournal).filter(TravelJournal.user_id == user.id).count()
        )
        title = payload.title.strip() if payload.title and payload.title.strip() else None
        book = TravelJournal(user_id=user.id, title=title or f"Book {existing_count + 1}")
        session.add(book)
        session.flush()
        session.refresh(book)
        return _book_dict(book, 0)

@router.get("/{journal_id}", response_model=JournalDetail)
def get_journal(journal_id: str, user: User = Depends(get_current_user)):
    """One book, with every page written so far, in page order."""
    _require_db()
    with get_session() as session:
        book = (
            session.query(TravelJournal)
            .filter(TravelJournal.id == journal_id, TravelJournal.user_id == user.id)
            .first()
        )
        if not book:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Book not found.")
        pages = (
            session.query(TravelNote)
            .filter(TravelNote.journal_id == book.id)
            .order_by(TravelNote.page_number.asc())
            .all()
        )
        return {**_book_dict(book, len(pages)), "pages": [_page_dict(p) for p in pages]}

@router.post("/{journal_id}/pages", response_model=PageOut, status_code=status.HTTP_201_CREATED)
def create_page(journal_id: str, payload: PageCreate, user: User = Depends(get_current_user)):
    """Write the next page: one location, its story, and an optional photo."""
    _require_db()
    with get_session() as session:
        book = (
            session.query(TravelJournal)
            .filter(TravelJournal.id == journal_id, TravelJournal.user_id == user.id)
            .first()
        )
        if not book:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Book not found.")
        existing = session.query(TravelNote).filter(TravelNote.journal_id == book.id).count()
        if existing >= MAX_PAGES_PER_BOOK:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"This book is full ({MAX_PAGES_PER_BOOK} pages) — start a new one.",
            )
        note = TravelNote(
            user_id=user.id,
            place=payload.place,
            body=payload.body,
            photo_url=payload.photo_url,
            journal_id=book.id,
            page_number=existing + 1,
        )
        session.add(note)
        session.flush()
        session.refresh(note)
        return _page_dict(note)

@router.delete("/{journal_id}/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_page(journal_id: str, page_id: str, user: User = Depends(get_current_user)):
    """Tear out one page. Later pages shift down so the book stays gapless."""
    _require_db()
    with get_session() as session:
        note = (
            session.query(TravelNote)
            .filter(
                TravelNote.id == page_id,
                TravelNote.journal_id == journal_id,
                TravelNote.user_id == user.id,
            )
            .first()
        )
        if not note:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Page not found.")
        deleted_number = note.page_number
        session.delete(note)
        session.flush()
        later_pages = (
            session.query(TravelNote)
            .filter(TravelNote.journal_id == journal_id, TravelNote.page_number > deleted_number)
            .order_by(TravelNote.page_number.asc())
            .all()
        )
        for p in later_pages:
            p.page_number -= 1

@router.delete("/{journal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journal(journal_id: str, user: User = Depends(get_current_user)):
    """Retire a whole book (and every page in it)."""
    _require_db()
    with get_session() as session:
        deleted = (
            session.query(TravelJournal)
            .filter(TravelJournal.id == journal_id, TravelJournal.user_id == user.id)
            .delete()
        )
        if not deleted:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Book not found.")
