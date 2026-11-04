"""AllJobs (alljobs.co.il) - HTML search results for guests."""

from __future__ import annotations

import re
from typing import Iterator
from urllib.parse import urljoin

from ..models import Job, SearchCriteria
from ..textutil import parse_date
from .base import Source, first_attr, first_text, parse_jsonld_jobs, soup

BASE = "https://www.alljobs.co.il"
JOB_ID_RE = re.compile(r"JobID=(\d+)", re.I)


def parse_results(html: str) -> list[Job]:
    doc = soup(html)
    jobs: list[Job] = []
    boxes = doc.select("div.open-board, div.job-box, div[id^=job-box-container]")
    for box in boxes:
        title = first_text(box, ".job-content-top-title h2", ".job-content-top-title a", "h2 a", "h2", "h3")
        href = first_attr(box, "href", ".job-content-top-title a", "a[href*='JobID']", "h2 a")
        if not title or not href:
            continue
        m = JOB_ID_RE.search(href) or JOB_ID_RE.search(box.get("id", "")) or re.search(r"(\d{5,})", box.get("id", ""))
        job_id = m.group(1) if m else ""
        company = first_text(box, ".job-content-top-acord .T14 a", ".T14 a", ".job-company-details a", "a[href*='Employer']")
        location = first_text(box, ".job-content-top-location a", ".job-content-top-location", ".job-region")
        location = re.sub(r"^(מיקום המשרה|מיקום)\s*:?\s*", "", location)
        desc = first_text(box, ".job-content-top-desc", ".PT15", ".job-description")
        job_type = first_text(box, ".job-content-top-type", ".job-type")
        date_text = first_text(box, ".job-content-top-date", ".job-date", "time")
        jobs.append(Job(
            source="alljobs",
            title=title,
            url=urljoin(BASE, href),
            company=company,
            location=location,
            description=desc[:4000],
            posted_at=parse_date(date_text),
            job_type=re.sub(r"^סוג משרה\s*:?\s*", "", job_type),
            external_id=job_id,
        ))
    return jobs


class AllJobsSource(Source):
    name = "alljobs"
    display_name = "AllJobs"
    homepage = BASE

    def search(self, criteria: SearchCriteria) -> Iterator[Job]:
        for page in range(1, criteria.max_pages + 1):
            html = self.http.get_text(
                f"{BASE}/SearchResultsGuest.aspx",
                params={"page": page, "position": "", "type": "", "freetxt": criteria.query, "city": "", "region": ""},
            )
            jobs = parse_results(html) or parse_jsonld_jobs(html, self.name, BASE)
            yield from jobs
            if not jobs:
                return
