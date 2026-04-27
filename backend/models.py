from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime


class IngestUrlRequest(BaseModel):
    url: HttpUrl


class IngestResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # queued | running | done | failed
    message: Optional[str] = None
    result: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class OverviewResponse(BaseModel):
    html: str
    updated: Optional[str] = None


class LogResponse(BaseModel):
    html: str
    total_entries: int
    page: int
    pages: int


class RecentJob(BaseModel):
    job_id: str
    status: str
    title: Optional[str] = None
    source: Optional[str] = None
    date: datetime


class RecentResponse(BaseModel):
    jobs: List[RecentJob]


class WikiPageInfo(BaseModel):
    path: str
    title: str
    folder: str


class WikiPagesResponse(BaseModel):
    pages: List[WikiPageInfo]


class WikiPageResponse(BaseModel):
    html: str
    title: str
    path: str


class SearchResult(BaseModel):
    path: str
    title: str
    snippet: str


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
