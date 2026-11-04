"""Apply SearchCriteria to scraped jobs."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from .locations import location_matches, looks_remote
from .models import Job, SearchCriteria
from .textutil import keyword_in, normalize, parse_salary, required_experience

JOB_TYPE_ALIASES: dict[str, list[str]] = {
    "full-time": ["full-time", "full time", "משרה מלאה", "מלאה"],
    "part-time": ["part-time", "part time", "משרה חלקית", "חלקית"],
    "student": ["student", "סטודנט", "סטודנטים", "משרת סטודנט"],
    "shifts": ["shifts", "משמרות"],
    "freelance": ["freelance", "פרילנס", "פרילנסר", "עצמאי"],
    "temporary": ["temporary", "זמנית", "משרה זמנית"],
    "internship": ["internship", "intern", "התמחות", "סטאז'"],
}


def _job_type_terms(t: str) -> list[str]:
    nt = normalize(t)
    for terms in JOB_TYPE_ALIASES.values():
        if nt in terms:
            return terms
    return [nt]


def matches(job: Job, c: SearchCriteria, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    searchable = job.title if c.title_only else f"{job.title} {job.description}"

    if c.keywords:
        hits = [keyword_in(searchable, k) for k in c.keywords]
        if not (all(hits) if c.match_all else any(hits)):
            return False
    if c.exclude_keywords and any(keyword_in(f"{job.title} {job.description}", k, synonyms=False) for k in c.exclude_keywords):
        return False

    if c.locations:
        remote_ok = c.remote_only or any(normalize(l) in ("remote", "מהבית", "מרחוק") for l in c.locations)
        locs = [l for l in c.locations if normalize(l) not in ("remote", "מהבית", "מרחוק")]
        if locs and not location_matches(job.location, locs) and not (remote_ok and _is_remote(job)):
            return False

    if c.remote_only and not _is_remote(job):
        return False

    if c.job_types:
        hay = normalize(f"{job.job_type} {job.title} {job.description}")
        if not any(term in hay for t in c.job_types for term in _job_type_terms(t)):
            return False

    company = normalize(job.company)
    if c.companies and not any(normalize(x) in company for x in c.companies):
        return False
    if c.exclude_companies and any(normalize(x) in company for x in c.exclude_companies if x):
        return False

    if c.posted_within_days is not None and job.posted_at is not None:
        if job.posted_at < now - timedelta(days=c.posted_within_days):
            return False

    if c.min_salary:
        sal = parse_salary(f"{job.salary} {job.description}")
        # unknown salary is kept (most Israeli postings don't publish salary)
        if sal is not None and sal < c.min_salary:
            return False

    if c.max_experience_years is not None:
        exp = required_experience(f"{job.title} {job.description}")
        if exp is not None and exp > c.max_experience_years:
            return False

    return True


def _is_remote(job: Job) -> bool:
    if job.remote is not None:
        return job.remote
    return looks_remote(f"{job.title} {job.location} {job.job_type} {job.description}")


def filter_jobs(jobs: Iterable[Job], c: SearchCriteria) -> list[Job]:
    return [j for j in jobs if matches(j, c)]


def dedupe(jobs: Iterable[Job]) -> list[Job]:
    """Remove exact duplicates and the same job cross-posted on several sites."""
    seen_uid: set[str] = set()
    by_fp: dict[str, Job] = {}
    out: list[Job] = []
    for j in jobs:
        if j.uid in seen_uid:
            continue
        seen_uid.add(j.uid)
        fp = j.fingerprint
        if j.company and fp in by_fp:
            first = by_fp[fp]
            first.extra.setdefault("also_on", []).append({"source": j.source, "url": j.url})
            continue
        by_fp[fp] = j
        out.append(j)
    return out


def sort_jobs(jobs: list[Job]) -> list[Job]:
    return sorted(jobs, key=lambda j: j.posted_at or datetime.min, reverse=True)
