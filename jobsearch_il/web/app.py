"""Small FastAPI web UI (Hebrew, RTL) + JSON API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..engine import JobSearchEngine
from ..locations import REGIONS
from ..models import SearchCriteria
from ..sources import SOURCES
from ..storage import JobStore

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _split(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def _criteria(q: str, exclude: str, location: str, remote: bool, job_type: str, days: int | None,
              min_salary: int | None, max_exp: int | None, sources: list[str], match_all: bool,
              title_only: bool, exclude_company: str, pages: int, limit: int) -> SearchCriteria:
    return SearchCriteria(
        keywords=_split(q), match_all=match_all, title_only=title_only, exclude_keywords=_split(exclude),
        locations=_split(location), remote_only=remote, job_types=_split(job_type),
        exclude_companies=_split(exclude_company), posted_within_days=days, min_salary=min_salary,
        max_experience_years=max_exp, sources=sources, max_pages=pages, limit=limit,
    )


def create_app(config: dict[str, Any] | None = None, db_path: str = "jobs.db",
               engine: JobSearchEngine | None = None) -> FastAPI:
    engine = engine or JobSearchEngine(config or {}, store=JobStore(db_path))
    app = FastAPI(title="חיפוש עבודה בישראל")

    def run(live: bool, c: SearchCriteria) -> dict[str, Any]:
        if live:
            res = engine.search(c)
            return {"jobs": res.jobs, "new": {j.uid for j in res.new_jobs}, "per_source": res.per_source,
                    "errors": res.errors, "scraped": res.scraped}
        return {"jobs": engine.search_stored(c), "new": set(), "per_source": {}, "errors": {}, "scraped": None}

    common = dict(
        q=Query(""), exclude=Query(""), location=Query(""), remote=Query(False), job_type=Query(""),
        days=Query(None), min_salary=Query(None), max_exp=Query(None), source=Query([]),
        match_all=Query(False), title_only=Query(False), exclude_company=Query(""), pages=Query(2), limit=Query(200),
    )

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, live: bool = Query(False), q: str = common["q"], exclude: str = common["exclude"],
              location: str = common["location"], remote: bool = common["remote"], job_type: str = common["job_type"],
              days: int | None = common["days"], min_salary: int | None = common["min_salary"],
              max_exp: int | None = common["max_exp"], source: list[str] = common["source"],
              match_all: bool = common["match_all"], title_only: bool = common["title_only"],
              exclude_company: str = common["exclude_company"], pages: int = common["pages"],
              limit: int = common["limit"], submitted: bool = Query(False)):
        result = None
        if submitted:
            result = run(live, _criteria(q, exclude, location, remote, job_type, days, min_salary, max_exp, source,
                                         match_all, title_only, exclude_company, pages, limit))
        active = [s.name for s in engine.enabled_sources()]
        return TEMPLATES.TemplateResponse(request, "index.html", {
            "result": result, "sources": SOURCES, "active": active, "regions": list(REGIONS),
            "f": dict(q=q, exclude=exclude, location=location, remote=remote, job_type=job_type, days=days,
                      min_salary=min_salary, max_exp=max_exp, source=source, match_all=match_all,
                      title_only=title_only, exclude_company=exclude_company, pages=pages, live=live),
            "stats": engine.store.stats() if engine.store else {},
        })

    @app.get("/api/search")
    def api_search(live: bool = Query(False), q: str = common["q"], exclude: str = common["exclude"],
                   location: str = common["location"], remote: bool = common["remote"],
                   job_type: str = common["job_type"], days: int | None = common["days"],
                   min_salary: int | None = common["min_salary"], max_exp: int | None = common["max_exp"],
                   source: list[str] = common["source"], match_all: bool = common["match_all"],
                   title_only: bool = common["title_only"], exclude_company: str = common["exclude_company"],
                   pages: int = common["pages"], limit: int = common["limit"]):
        r = run(live, _criteria(q, exclude, location, remote, job_type, days, min_salary, max_exp, source,
                                match_all, title_only, exclude_company, pages, limit))
        return {"count": len(r["jobs"]), "scraped": r["scraped"], "per_source": r["per_source"],
                "errors": r["errors"], "jobs": [{**j.to_dict(), "is_new": j.uid in r["new"]} for j in r["jobs"]]}

    @app.post("/api/jobs/{uid}/status/{status}")
    def set_status(uid: str, status: str):
        if engine.store is None:
            raise HTTPException(400, "no database")
        try:
            ok = engine.store.set_status(uid, status)
        except ValueError as e:
            raise HTTPException(400, str(e))
        if not ok:
            raise HTTPException(404, "job not found")
        return {"ok": True}

    @app.get("/api/sources")
    def api_sources():
        active = {s.name for s in engine.enabled_sources()}
        return [{"name": n, "display_name": c.display_name, "active": n in active} for n, c in SOURCES.items()]

    return app
