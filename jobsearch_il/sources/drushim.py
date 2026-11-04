"""Drushim (drushim.co.il) - the site's own JSON search API.

Endpoint: https://webapi.drushim.co.il/api/jobs/search?SearchTerm=<q>&ssaen=1&isAA=true[&page=N]
Response: {ResultList: [...], TotalPagesNumber, NextPageNumber, TotalSearchResultCount}
Each item: Code, Company{CompanyDisplayName, NameInHebrew}, JobContent{Name, Description,
Requirements, Scopes[{NameInHebrew}], Addresses[{City, CityEnglish}]}, JobInfo{Link, Date, IsExpired}.
"""

from __future__ import annotations

from typing import Any, Iterator

from ..models import Job, SearchCriteria
from ..textutil import clean_html_text, parse_date
from .base import Source

API = "https://webapi.drushim.co.il/api/jobs/search"
SITE = "https://www.drushim.co.il"


def _get(d: Any, *path: str, default: Any = "") -> Any:
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d if d is not None else default


def parse_api(data: dict) -> list[Job]:
    jobs = []
    for item in data.get("ResultList") or []:
        if _get(item, "JobInfo", "IsExpired", default=False):
            continue
        content = item.get("JobContent") or {}
        title = (content.get("Name") or content.get("FullName") or "").strip()
        if not title:
            continue
        desc = "\n".join(clean_html_text(content.get(k) or "") for k in ("Description", "Requirements")).strip()
        cities = []
        for a in content.get("Addresses") or []:
            city = (a.get("City") or a.get("CityEnglish") or "").strip() if isinstance(a, dict) else ""
            if city and city not in cities:
                cities.append(city)
        scopes = content.get("Scopes") or []
        job_type = ", ".join(s.get("NameInHebrew") or s.get("Name") or "" for s in scopes if isinstance(s, dict))
        company = _get(item, "Company", "CompanyDisplayName") or _get(item, "Company", "NameInHebrew")
        link = _get(item, "JobInfo", "Link")
        code = str(item.get("Code") or "")
        url = link if str(link).startswith("http") else (SITE + link if link else f"{SITE}/job/{code}/")
        jobs.append(Job(
            source="drushim",
            title=title,
            url=url,
            company=str(company).strip(),
            location=", ".join(cities),
            description=desc[:4000],
            posted_at=parse_date(str(_get(item, "JobInfo", "Date") or "")),
            job_type=job_type,
            external_id=code,
        ))
    return jobs


class DrushimSource(Source):
    name = "drushim"
    display_name = "דרושים IL"
    homepage = SITE

    def search(self, criteria: SearchCriteria) -> Iterator[Job]:
        params: dict[str, Any] = {"SearchTerm": criteria.query, "ssaen": 1, "isAA": "true"}
        for page in range(criteria.max_pages):
            if page:
                params["page"] = page
            data = self.http.get_json(API, params=params, headers={"Accept": "application/json", "Referer": SITE + "/"})
            jobs = parse_api(data)
            yield from jobs
            total = data.get("TotalPagesNumber")
            if not data.get("ResultList") or (total is not None and page + 1 >= int(total)):
                return
