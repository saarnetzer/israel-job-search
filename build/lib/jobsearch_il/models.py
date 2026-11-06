"""Core data models: a job posting and the search criteria."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Job:
    source: str
    title: str
    url: str
    company: str = ""
    location: str = ""
    description: str = ""
    posted_at: datetime | None = None
    salary: str = ""
    job_type: str = ""
    remote: bool | None = None
    external_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def uid(self) -> str:
        """Stable identifier, used to dedupe and to detect new jobs between runs."""
        key = f"{self.source}:{self.external_id}" if self.external_id else self.url.split("#")[0]
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]

    @property
    def fingerprint(self) -> str:
        """Cross-site fingerprint: the same job is often posted on several sites."""
        norm = lambda s: re.sub(r"[\W_]+", "", (s or "").lower())  # noqa: E731
        return f"{norm(self.title)}|{norm(self.company)}"

    @property
    def text(self) -> str:
        return " ".join(p for p in (self.title, self.company, self.location, self.job_type, self.description) if p)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["posted_at"] = self.posted_at.isoformat() if self.posted_at else None
        d["uid"] = self.uid
        return d


@dataclass
class SearchCriteria:
    keywords: list[str] = field(default_factory=list)
    """Free-text terms. Matched against title + description (Hebrew-prefix aware)."""
    match_all: bool = False
    """True: every keyword must appear. False: at least one."""
    title_only: bool = False
    exclude_keywords: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    """Cities or regions (Hebrew or English), e.g. 'תל אביב', 'מרכז', 'Haifa'."""
    remote_only: bool = False
    job_types: list[str] = field(default_factory=list)
    """e.g. 'משרה מלאה', 'חלקית', 'full-time', 'student', 'סטודנט'."""
    companies: list[str] = field(default_factory=list)
    exclude_companies: list[str] = field(default_factory=list)
    posted_within_days: int | None = None
    min_salary: int | None = None
    max_experience_years: int | None = None
    sources: list[str] = field(default_factory=list)
    """Empty = all enabled sources."""
    max_pages: int = 2
    limit: int | None = None

    @property
    def query(self) -> str:
        return " ".join(self.keywords)
