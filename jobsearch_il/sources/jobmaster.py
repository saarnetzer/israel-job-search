"""JobMaster (jobmaster.co.il) - public search results.

URL: https://www.jobmaster.co.il/jobs/?q=<q>
Card: <article id="misra<ID>"> with a.CardHeader (title), a.CompanyNameLink span (company),
li.jobLocation a, li.jobType a, div.jobShortDescription, span.Gray ("פורסם לפני ...").
Only the first results page (~10 jobs) is available without logging in.
"""

from __future__ import annotations

import re
from typing import Iterator

from ..models import Job, SearchCriteria
from ..textutil import parse_date
from .base import Source, first_text, parse_jsonld_jobs, soup

BASE = "https://www.jobmaster.co.il"


def parse_results(html: str) -> list[Job]:
    jobs: list[Job] = []
    for card in soup(html).select("article[id^=misra]"):
        m = re.match(r"misra(\d+)", card.get("id", ""))
        title = first_text(card, "a.CardHeader")
        if not m or not title:
            continue
        posted = ""
        for span in card.select("span.Gray"):
            t = span.get_text(" ", strip=True)
            if t.startswith("פורסם"):
                posted = t
                break
        jobs.append(Job(
            source="jobmaster",
            title=title,
            url=f"{BASE}/jobs/checknum.asp?key={m.group(1)}",
            company=first_text(card, "a.CompanyNameLink span", "a.CompanyNameLink"),
            location=first_text(card, "li.jobLocation a", "li.jobLocation"),
            job_type=first_text(card, "li.jobType a", "li.jobType"),
            description=first_text(card, "div.jobShortDescription")[:4000],
            posted_at=parse_date(posted),
            external_id=m.group(1),
        ))
    return jobs


class JobMasterSource(Source):
    name = "jobmaster"
    display_name = "JobMaster"
    homepage = BASE

    def search(self, criteria: SearchCriteria) -> Iterator[Job]:
        html = self.http.get_text(f"{BASE}/jobs/", params={"q": criteria.query})
        yield from parse_results(html) or parse_jsonld_jobs(html, self.name, BASE)
