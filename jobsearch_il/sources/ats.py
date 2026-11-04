"""Company career systems (ATS) used by many Israeli companies.

These have stable public JSON APIs, so they're the most reliable sources. Each needs a
list of companies in config.yaml. Only jobs located in Israel (or remote) are returned.
"""

from __future__ import annotations

import html
import logging
from datetime import datetime
from typing import Iterator

from ..locations import is_israel_location, looks_remote
from ..models import Job, SearchCriteria
from ..textutil import clean_html_text, keyword_in, parse_date
from .base import Source, parse_jsonld_jobs

log = logging.getLogger(__name__)


def _israel_or_remote(job: Job, include_remote: bool) -> bool:
    return is_israel_location(job.location) or (include_remote and looks_remote(job.location))


def _query_match(job: Job, criteria: SearchCriteria) -> bool:
    # ATS APIs have no search param: pre-filter here so we don't keep every job of every company
    if not criteria.keywords:
        return True
    return any(keyword_in(f"{job.title} {job.description}", k) for k in criteria.keywords)


class _CompanyListSource(Source):
    needs_config = True
    config_key = "companies"

    def companies(self) -> list:
        return self.config.get(self.config_key) or []

    def is_configured(self) -> bool:
        return bool(self.companies())

    def fetch_company(self, company) -> list[Job]:  # pragma: no cover - abstract
        raise NotImplementedError

    def search(self, criteria: SearchCriteria) -> Iterator[Job]:
        include_remote = self.config.get("include_remote", True)
        for company in self.companies():
            try:
                jobs = self.fetch_company(company)
            except Exception as e:  # one broken company must not kill the whole source
                log.warning("%s: company %s failed: %s", self.name, company, e)
                continue
            for j in jobs:
                if _israel_or_remote(j, include_remote) and _query_match(j, criteria):
                    yield j


def parse_greenhouse(data: dict, board: str) -> list[Job]:
    jobs = []
    for p in data.get("jobs", []):
        jobs.append(Job(
            source="greenhouse",
            title=p.get("title", ""),
            url=p.get("absolute_url", ""),
            company=p.get("company_name") or board,
            location=(p.get("location") or {}).get("name", ""),
            description=clean_html_text(html.unescape(p.get("content", "")))[:4000],
            posted_at=parse_date(p.get("first_published") or p.get("updated_at")),
            external_id=str(p.get("id", "")),
        ))
    return jobs


class GreenhouseSource(_CompanyListSource):
    name = "greenhouse"
    display_name = "Greenhouse (חברות)"
    homepage = "https://boards.greenhouse.io"

    def fetch_company(self, board: str) -> list[Job]:
        data = self.http.get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", params={"content": "true"})
        return parse_greenhouse(data, board)


def parse_lever(data: list, company: str) -> list[Job]:
    jobs = []
    for p in data:
        cats = p.get("categories") or {}
        locs = cats.get("allLocations") or [cats.get("location", "")]
        created = p.get("createdAt")
        jobs.append(Job(
            source="lever",
            title=p.get("text", ""),
            url=p.get("hostedUrl", ""),
            company=company,
            location=" / ".join(l for l in locs if l),
            description=(p.get("descriptionPlain") or "")[:4000],
            job_type=cats.get("commitment", ""),
            posted_at=datetime.fromtimestamp(created / 1000) if created else None,
            remote=True if p.get("workplaceType") == "remote" else None,
            external_id=p.get("id", ""),
        ))
    return jobs


class LeverSource(_CompanyListSource):
    name = "lever"
    display_name = "Lever (חברות)"
    homepage = "https://jobs.lever.co"

    def fetch_company(self, company: str) -> list[Job]:
        data = self.http.get_json(f"https://api.lever.co/v0/postings/{company}", params={"mode": "json"})
        return parse_lever(data, company)


def parse_comeet(data: list, company_name: str) -> list[Job]:
    jobs = []
    for p in data:
        loc = p.get("location") or {}
        location = ", ".join(x for x in (loc.get("city"), loc.get("country")) if x) or loc.get("name", "")
        details = " ".join(clean_html_text(d.get("value", "")) for d in p.get("details") or [] if isinstance(d, dict))
        jobs.append(Job(
            source="comeet",
            title=p.get("name", ""),
            url=p.get("url_active_page") or p.get("url_comeet_hosted_page") or "",
            company=p.get("company_name") or company_name,
            location=location,
            description=details[:4000],
            job_type=p.get("employment_type") or "",
            posted_at=parse_date(p.get("time_updated")),
            remote=True if (p.get("workplace_type") or "").lower() == "remote" or loc.get("is_remote") else None,
            external_id=p.get("uid", ""),
        ))
    return jobs


class ComeetSource(_CompanyListSource):
    """Comeet is very common among Israeli startups.

    Each company entry needs the `uid` and `token` that appear in the company's careers page
    source (look for `comeet.co/careers-api/2.0/company/<uid>/positions?token=<token>`).
    """

    name = "comeet"
    display_name = "Comeet (חברות)"
    homepage = "https://www.comeet.com"

    def fetch_company(self, company: dict) -> list[Job]:
        data = self.http.get_json(
            f"https://www.comeet.co/careers-api/2.0/company/{company['uid']}/positions",
            params={"token": company["token"], "details": "true"},
        )
        return parse_comeet(data, company.get("name", ""))


class CareerPagesSource(_CompanyListSource):
    """Any careers page that embeds schema.org JobPosting JSON-LD (very common)."""

    name = "careers"
    display_name = "דפי קריירה (JSON-LD)"
    config_key = "urls"

    def fetch_company(self, url: str) -> list[Job]:
        return parse_jsonld_jobs(self.http.get_text(url), self.name, url)

    def search(self, criteria: SearchCriteria) -> Iterator[Job]:
        for url in self.companies():
            try:
                jobs = self.fetch_company(url)
            except Exception as e:
                log.warning("careers: %s failed: %s", url, e)
                continue
            yield from (j for j in jobs if _query_match(j, criteria))
