"""JobMaster (jobmaster.co.il) - HTML search results."""

from __future__ import annotations

import re
from typing import Iterator
from urllib.parse import urljoin

from ..models import Job, SearchCriteria
from ..textutil import parse_date
from .base import Source, first_attr, first_text, parse_jsonld_jobs, soup

BASE = "https://www.jobmaster.co.il"


def parse_results(html: str) -> list[Job]:
    doc = soup(html)
    jobs: list[Job] = []
    for card in doc.select("article.JobItem, article.CardStyle, div.JobItem"):
        title = first_text(card, "a.CardHeader", ".JobItemName", "h2 a", "h3 a", "h2", "h3")
        href = first_attr(card, "href", "a.CardHeader", "a[href*='checknum']", "h2 a", "h3 a", "a.View_Job_Details")
        raw_id = card.get("id", "")
        m = re.search(r"(\d{4,})", raw_id) or re.search(r"key=(\d+)", href or "")
        job_id = m.group(1) if m else ""
        if not href and job_id:
            href = f"/jobs/checknum.asp?key={job_id}"
        if not title or not href:
            continue
        jobs.append(Job(
            source="jobmaster",
            title=title,
            url=urljoin(BASE, href),
            company=first_text(card, "a.CompanyNameLink", ".ByTitle a", "span.ByTitle", ".CompanyName"),
            location=first_text(card, "li.jobLocation", ".jobLocation", ".Location"),
            description=first_text(card, "div.jobShortDescription", ".jobDescription", ".Description")[:4000],
            job_type=first_text(card, "li.jobType", ".jobType"),
            posted_at=parse_date(first_text(card, "span.Gray", ".jobTimePublish", ".paddingTop10px span", "time")),
            external_id=job_id,
        ))
    return jobs


class JobMasterSource(Source):
    name = "jobmaster"
    display_name = "JobMaster"
    homepage = BASE

    def search(self, criteria: SearchCriteria) -> Iterator[Job]:
        for page in range(1, criteria.max_pages + 1):
            html = self.http.get_text(f"{BASE}/jobs/", params={"q": criteria.query, "currPage": page})
            jobs = parse_results(html) or parse_jsonld_jobs(html, self.name, BASE)
            yield from jobs
            if not jobs:
                return
