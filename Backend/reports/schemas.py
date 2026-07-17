"""
reports.schemas — the API contract for crowd-sourced ground reports.
"""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ReportCreate(BaseModel):
    district: str = Field(..., description="District name, e.g. 'Colombo' or 'NuwaraEliya'")
    location: str = Field(..., description="Where exactly, in the reporter's words")
    title: str = Field(..., description="The main point, one line")
    body: str = Field(default="", description="Detail: trail state, closures, queues")

    @field_validator("location", "title")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("body")
    @classmethod
    def _trim(cls, v: str) -> str:
        return v.strip()


class ReportOut(BaseModel):
    id: str
    district: str
    location: str
    title: str
    body: str
    author: str = ""          # username of the logged-in reporter
    author_avatar: str = ""   # the reporter's profile-picture URL, if they set one
    created_at: str           # ISO-8601 UTC


class ReportList(BaseModel):
    count: int
    reports: List[ReportOut]
