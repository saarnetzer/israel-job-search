"""AllJobs (alljobs.co.il) - public guest search pages.

URL: https://www.alljobs.co.il/SearchResultsGuest.aspx?page=N&position=&type=&freetxt=<q>&city=&region=
Card: div.job-box > div#job-box<ID>, with .job-content-top-title(-ltr) h2 / .T14 a (company),
.job-content-top-location(-ltr) a[href*=city=], .job-content-top-type, .job-content-top-desc,
.job-content-top-date ("לפני 21 שעות", "2 ימים").
"""

from __future__ import annotations

import re
from typing import Iterator
from urllib.parse import urljoin

from ..models import Job, SearchCriteria
from ..textutil import parse_date
from .base import Source, first_attr, first_text, parse_jsonld_jobs, soup

BASE = "https://www.alljobs.co.il"
JOB_ID_RE = re.compile(r"JobID=(\d+)", re.I)
LABEL_RE = re.compile(r"^\s*(מיקום המשרה|סוג משרה)\s*:?\s*")
NOT_A_TYPE = re.compile(r"^(מתאים גם|לדוברי)")


def _job_type(box) -> str:
    el = box.select_one("[class*=job-content-top-type]")
    if not el:
        return ""
    items = [d.get_text(" ", strip=True) for d in el.select(".job-types-content > div")]
    if items:  # "מספר סוגים" dropdown: keep scopes, drop "suitable also for ..." tags
        return ", ".join(i for i in items if i and not NOT_A_TYPE.match(i))
    return re.sub(r"\s+", " ", LABEL_RE.sub("", el.get_text(" ", strip=True)))

TITLE = "[class*=job-content-top-title]"
LOCATION = "[class*=job-content-top-location]"


def parse_results(html: str) -> list[Job]:
    jobs: list[Job] = []
    for box in soup(html).select("div.job-box"):
        href = first_attr(box, "href", "a[href*='UploadSingle.aspx?JobID=']", "a[href*='JobID=']")
        title = first_text(box, f"{TITLE} h2", "a[href*='JobID='] h2")
        m = JOB_ID_RE.search(href or "")
        if not title or not m:
            continue
        title_el = box.select_one(TITLE)
        if title_el and "closed-job" in (title_el.get("class") or []):
            continue  # AllJobs still lists some closed postings
        loc_el = box.select_one(LOCATION)
        cities: list[str] = []
        if loc_el:
            for a in loc_el.select("a[href*='city=']"):
                c = a.get_text(" ", strip=True)
                if c and c not in cities:
                    cities.append(c)
            if not cities:
                cities = [LABEL_RE.sub("", loc_el.get_text(" ", strip=True))]
        desc_el = box.select_one(".job-content-top-desc")
        desc = desc_el.get_text("\n", strip=True) if desc_el else ""
        jobs.append(Job(
            source="alljobs",
            title=title,
            url=urljoin(BASE, href),
            company=first_text(box, f"{TITLE} .T14 a", f"{TITLE} .T14"),
            location=", ".join(c for c in cities if c),
            description=desc[:4000],
            job_type=_job_type(box),
            posted_at=parse_date(first_text(box, ".job-content-top-date")),
            external_id=m.group(1),
        ))
    return jobs


class AllJobsSource(Source):
    name = "alljobs"
    display_name = "AllJobs"
    homepage = BASE

    def search(self, criteria: SearchCriteria) -> Iterator[Job]:
        seen: set[str] = set()
        for page in range(1, criteria.max_pages + 1):
            html = self.http.get_text(
                f"{BASE}/SearchResultsGuest.aspx",
                params={"page": page, "position": "", "type": "", "freetxt": criteria.query, "city": "", "region": ""},
            )
            jobs = [j for j in (parse_results(html) or parse_jsonld_jobs(html, self.name, BASE)) if j.uid not in seen]
            if not jobs:  # past the last page AllJobs repeats results
                return
            seen.update(j.uid for j in jobs)
            yield from jobs
