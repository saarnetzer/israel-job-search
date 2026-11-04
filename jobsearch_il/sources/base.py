"""Base class for job sources + shared parsing helpers."""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from ..http import HttpClient
from ..models import Job, SearchCriteria
from ..textutil import clean_html_text, parse_date

log = logging.getLogger(__name__)


class Source(ABC):
    name: str = ""
    display_name: str = ""
    homepage: str = ""
    needs_config: bool = False
    """True for sources that only work after configuring company lists etc."""

    def __init__(self, http: HttpClient, config: dict[str, Any] | None = None):
        self.http = http
        self.config = config or {}

    def is_configured(self) -> bool:
        return True

    @abstractmethod
    def search(self, criteria: SearchCriteria) -> Iterator[Job]:
        ...


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def first_text(node: Tag, *selectors: str) -> str:
    for sel in selectors:
        el = node.select_one(sel)
        if el and el.get_text(strip=True):
            return re.sub(r"\s+", " ", el.get_text(" ", strip=True))
    return ""


def first_attr(node: Tag, attr: str, *selectors: str) -> str:
    for sel in selectors:
        el = node.select_one(sel)
        if el and el.get(attr):
            return str(el.get(attr))
    return ""


# ------------------------------------------------------------------ JSON-LD
def _iter_ld(obj: Any) -> Iterator[dict]:
    if isinstance(obj, list):
        for x in obj:
            yield from _iter_ld(x)
    elif isinstance(obj, dict):
        t = obj.get("@type")
        if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
            yield obj
        for key in ("@graph", "itemListElement", "item"):
            if key in obj:
                yield from _iter_ld(obj[key])


def _ld_location(loc: Any) -> str:
    if isinstance(loc, list):
        return " / ".join(filter(None, (_ld_location(x) for x in loc)))
    if isinstance(loc, dict):
        addr = loc.get("address", loc)
        if isinstance(addr, str):
            return addr
        if isinstance(addr, dict):
            parts = [addr.get("addressLocality"), addr.get("addressRegion")]
            country = addr.get("addressCountry")
            if isinstance(country, dict):
                country = country.get("name")
            parts.append(country)
            return ", ".join(str(p) for p in parts if p)
    return str(loc) if isinstance(loc, str) else ""


def parse_jsonld_jobs(html: str, source: str, base_url: str = "") -> list[Job]:
    """Extract schema.org JobPosting objects - works on most career pages and many job boards."""
    jobs: list[Job] = []
    for script in soup(html).find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for p in _iter_ld(data):
            org = p.get("hiringOrganization") or {}
            salary = p.get("baseSalary") or {}
            sal_text = ""
            if isinstance(salary, dict):
                v = salary.get("value", {})
                if isinstance(v, dict):
                    lo, hi = v.get("minValue"), v.get("maxValue") or v.get("value")
                    sal_text = " - ".join(str(x) for x in (lo, hi) if x)
                    if sal_text:
                        sal_text += f" {salary.get('currency', '')}".rstrip()
            url = p.get("url") or base_url
            emp_type = p.get("employmentType") or ""
            jobs.append(Job(
                source=source,
                title=clean_html_text(str(p.get("title", ""))),
                url=urljoin(base_url, url) if base_url else url,
                company=org.get("name", "") if isinstance(org, dict) else str(org),
                location=_ld_location(p.get("jobLocation")),
                description=clean_html_text(str(p.get("description", "")))[:4000],
                posted_at=parse_date(p.get("datePosted")),
                salary=sal_text,
                job_type=", ".join(emp_type) if isinstance(emp_type, list) else str(emp_type),
                remote=True if p.get("jobLocationType") == "TELECOMMUTE" else None,
                external_id=str((p.get("identifier") or {}).get("value", "")) if isinstance(p.get("identifier"), dict) else "",
            ))
    return [j for j in jobs if j.title]
