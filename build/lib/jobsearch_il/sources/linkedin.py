"""LinkedIn public (guest) job search, restricted to Israel."""

from __future__ import annotations

import re
from typing import Iterator

from ..models import Job, SearchCriteria
from ..textutil import parse_date
from .base import Source, first_attr, first_text, soup

BASE = "https://www.linkedin.com"
PAGE_SIZE = 25


def parse_results(html: str) -> list[Job]:
    jobs: list[Job] = []
    for card in soup(html).select("div.base-card, div.job-search-card, li > div.base-search-card"):
        title = first_text(card, ".base-search-card__title", "h3")
        url = first_attr(card, "href", "a.base-card__full-link", "a.base-search-card__full-link", "a")
        if not title or not url:
            continue
        urn = card.get("data-entity-urn", "")
        m = re.search(r"(\d{6,})", urn) or re.search(r"-(\d{6,})\b", url)
        posted = first_attr(card, "datetime", "time") or first_text(card, "time")
        jobs.append(Job(
            source="linkedin",
            title=title,
            url=url.split("?")[0],
            company=first_text(card, ".base-search-card__subtitle", "h4"),
            location=first_text(card, ".job-search-card__location"),
            salary=first_text(card, ".job-search-card__salary-info"),
            posted_at=parse_date(posted),
            external_id=m.group(1) if m else "",
        ))
    return jobs


class LinkedInSource(Source):
    full_description = False
    name = "linkedin"
    display_name = "LinkedIn"
    homepage = BASE

    def search(self, criteria: SearchCriteria) -> Iterator[Job]:
        params: dict = {"keywords": criteria.query, "location": self.config.get("location", "Israel")}
        if criteria.posted_within_days:
            params["f_TPR"] = f"r{criteria.posted_within_days * 86400}"
        if criteria.remote_only:
            params["f_WT"] = "2"
        for page in range(criteria.max_pages):
            params["start"] = page * PAGE_SIZE
            html = self.http.get_text(f"{BASE}/jobs-guest/jobs/api/seeMoreJobPostings/search", params=params)
            jobs = parse_results(html)
            yield from jobs
            if len(jobs) < PAGE_SIZE:
                return
