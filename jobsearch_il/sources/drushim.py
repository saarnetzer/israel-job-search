"""Drushim (drushim.co.il) - uses the JSON endpoint behind the site's search page."""

from __future__ import annotations

from typing import Any, Iterator

from ..models import Job, SearchCriteria
from ..textutil import clean_html_text, parse_date
from .base import Source, parse_jsonld_jobs

BASE = "https://www.drushim.co.il"


def _get(d: Any, *path: str, default: Any = "") -> Any:
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d if d is not None else default


def parse_api(data: dict) -> list[Job]:
    jobs = []
    for item in data.get("ResultList") or data.get("resultList") or []:
        content = item.get("JobContent") or {}
        title = content.get("Name") or content.get("FullName") or ""
        if not title:
            continue
        desc = " ".join(clean_html_text(content.get(k) or "") for k in ("Description", "Requirements"))
        addresses = content.get("Addresses") or []
        location = ", ".join(
            a.get("City") or a.get("CityEnglish") or "" for a in addresses if isinstance(a, dict)
        ) or _get(content, "Region")
        scopes = content.get("Scopes") or []
        job_type = ", ".join(s.get("Name", "") for s in scopes if isinstance(s, dict)) if isinstance(scopes, list) else ""
        company = (_get(item, "Company", "CompanyDisplayName") or _get(item, "Company", "NameInHebrew")
                   or _get(item, "Company", "NameInEnglish"))
        link = _get(item, "JobInfo", "Link")
        code = str(item.get("Code") or item.get("JobCode") or "")
        url = link if str(link).startswith("http") else (BASE + link if link else f"{BASE}/job/{code}/")
        jobs.append(Job(
            source="drushim",
            title=title.strip(),
            url=url,
            company=str(company).strip(),
            location=str(location).strip(),
            description=desc.strip()[:4000],
            posted_at=parse_date(str(_get(item, "JobInfo", "Date") or _get(item, "JobInfo", "DateView") or "")),
            job_type=job_type,
            external_id=code,
        ))
    return jobs


class DrushimSource(Source):
    name = "drushim"
    display_name = "דרושים IL"
    homepage = BASE

    def search(self, criteria: SearchCriteria) -> Iterator[Job]:
        for page in range(criteria.max_pages):
            try:
                data = self.http.get_json(
                    f"{BASE}/api/jobs/search",
                    params={"searchterm": criteria.query, "ssaen": 1, "page": page, "isAA": "true"},
                    headers={"Accept": "application/json", "Referer": f"{BASE}/jobs/search/{criteria.query}/"},
                )
            except ValueError:  # not JSON (site changed) -> fall back to HTML JSON-LD
                html = self.http.get_text(f"{BASE}/jobs/search/{criteria.query}/")
                yield from parse_jsonld_jobs(html, self.name, BASE)
                return
            jobs = parse_api(data)
            yield from jobs
            total_pages = data.get("TotalPagesNumber") or data.get("totalPagesNumber")
            if not jobs or (total_pages is not None and page + 1 >= int(total_pages)):
                return
