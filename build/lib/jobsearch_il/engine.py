"""Search engine: run all sources in parallel, merge, dedupe, filter, store."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

from .filters import dedupe, filter_jobs, sort_jobs
from .http import HttpClient
from .models import Job, SearchCriteria
from .sources import SOURCES, Source
from .storage import LOCAL_USER, JobStore

log = logging.getLogger(__name__)


@dataclass
class SearchResult:
    jobs: list[Job]
    new_jobs: list[Job] = field(default_factory=list)
    scraped: int = 0
    per_source: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


class JobSearchEngine:
    def __init__(self, config: dict[str, Any] | None = None, store: JobStore | None = None,
                 http: HttpClient | None = None, sources: dict[str, type[Source]] | None = None):
        self.config = config or {}
        http_cfg = self.config.get("http", {})
        self.http = http or HttpClient(
            min_delay=http_cfg.get("min_delay", 1.0),
            retries=http_cfg.get("retries", 3),
            timeout=http_cfg.get("timeout", 20),
            respect_robots=http_cfg.get("respect_robots", False),
            proxy=http_cfg.get("proxy"),
        )
        self.store = store
        self.registry = sources or SOURCES

    def enabled_sources(self, names: list[str] | None = None) -> list[Source]:
        src_cfg = self.config.get("sources", {})
        out = []
        for name, cls in self.registry.items():
            cfg = src_cfg.get(name, {}) or {}
            if names and name not in names:
                continue
            if not names and cfg.get("enabled") is False:
                continue
            src = cls(self.http, cfg)
            if src.is_configured():
                out.append(src)
            elif names:
                log.warning("source %s requested but not configured (see config.example.yaml)", name)
        return out

    def _run_source(self, src: Source, criteria: SearchCriteria) -> list[Job]:
        jobs: list[Job] = []
        # Most boards handle one free-text query best; with OR semantics query each keyword.
        queries = [criteria.keywords] if criteria.match_all or len(criteria.keywords) <= 1 else [[k] for k in criteria.keywords]
        for kws in queries:
            sub = SearchCriteria(**{**criteria.__dict__, "keywords": kws})
            for j in src.search(sub):
                if not src.full_description and kws:
                    # the site matched these keywords against text we don't have (full description)
                    j.extra.setdefault("site_matched", []).extend(kws)
                jobs.append(j)
        return jobs

    def search(self, criteria: SearchCriteria, workers: int = 8) -> SearchResult:
        result = SearchResult(jobs=[])
        raw: list[Job] = []
        sources = self.enabled_sources(criteria.sources or None)
        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(sources) or 1))) as pool:
            futures = {pool.submit(self._run_source, s, criteria): s for s in sources}
            for fut in as_completed(futures):
                src = futures[fut]
                try:
                    jobs = fut.result()
                    result.per_source[src.name] = len({j.uid for j in jobs})
                    raw.extend(jobs)
                except Exception as e:  # report and continue with other sites
                    log.warning("source %s failed: %s", src.name, e)
                    result.errors[src.name] = f"{type(e).__name__}: {e}"
        result.scraped = len(raw)
        unique = dedupe(raw)
        if self.store is not None:
            new_uids = {j.uid for j in self.store.upsert(unique)}
        else:
            new_uids = {j.uid for j in unique}
        matched = sort_jobs(filter_jobs(unique, criteria))
        if criteria.limit:
            matched = matched[: criteria.limit]
        result.jobs = matched
        result.new_jobs = [j for j in matched if j.uid in new_uids]
        return result

    def search_stored(self, criteria: SearchCriteria, status: str | None = None,
                      user_id: int = LOCAL_USER) -> list[Job]:
        """Search the local database without hitting the network."""
        if self.store is None:
            return []
        jobs = self.store.all(criteria.sources or None, status=status, user_id=user_id)
        jobs = sort_jobs(filter_jobs(jobs, criteria))
        return jobs[: criteria.limit] if criteria.limit else jobs

    def check(self, query: str = "developer") -> dict[str, dict[str, Any]]:
        """Try every enabled source once and report whether it is reachable and parses results."""
        report: dict[str, dict[str, Any]] = {}
        crit = SearchCriteria(keywords=[query], max_pages=1)

        def one(src: Source) -> tuple[str, dict[str, Any]]:
            try:
                jobs = list(src.search(crit))
                sample = jobs[0].to_dict() if jobs else None
                return src.name, {"ok": bool(jobs), "count": len(jobs), "sample": sample,
                                  "error": None if jobs else "0 results - the site may have changed its structure"}
            except Exception as e:
                return src.name, {"ok": False, "count": 0, "sample": None, "error": f"{type(e).__name__}: {e}"}

        sources = self.enabled_sources()
        with ThreadPoolExecutor(max_workers=max(1, len(sources))) as pool:
            for name, r in pool.map(one, sources):
                report[name] = r
        return report

    def close(self) -> None:
        self.http.close()
        if self.store is not None:
            self.store.close()
