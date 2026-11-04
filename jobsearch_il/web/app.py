"""FastAPI web UI (Hebrew, RTL) + JSON API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..engine import JobSearchEngine
from ..locations import REGIONS
from ..models import SearchCriteria
from ..sources import SOURCES
from ..storage import STATUSES, JobStore

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _split(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def criteria_params(
    q: str = "", exclude: str = "", location: str = "", remote: bool = False, job_type: str = "",
    days: int | None = None, min_salary: int | None = None, max_exp: int | None = None,
    source: list[str] = Query([]), match_all: bool = False, title_only: bool = False,
    exclude_company: str = "", company: str = "", pages: int = Query(2, ge=1, le=10),
    limit: int = Query(300, ge=1, le=2000),
) -> SearchCriteria:
    return SearchCriteria(
        keywords=_split(q), match_all=match_all, title_only=title_only, exclude_keywords=_split(exclude),
        locations=_split(location), remote_only=remote, job_types=_split(job_type), companies=_split(company),
        exclude_companies=_split(exclude_company), posted_within_days=days, min_salary=min_salary,
        max_experience_years=max_exp, sources=[s for x in source for s in _split(x)], max_pages=pages, limit=limit,
    )


def create_app(config: dict[str, Any] | None = None, db_path: str = "jobs.db",
               engine: JobSearchEngine | None = None) -> FastAPI:
    engine = engine or JobSearchEngine(config or {}, store=JobStore(db_path))
    app = FastAPI(title="חיפוש עבודה בישראל")

    def sources_info() -> list[dict[str, Any]]:
        active = {s.name for s in engine.enabled_sources()}
        return [{"name": n, "display_name": c.display_name, "homepage": c.homepage, "active": n in active,
                 "needs_config": c.needs_config} for n, c in engine.registry.items()]

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        boot = {"sources": sources_info(), "regions": list(REGIONS),
                "stats": engine.store.stats() if engine.store else {}}
        return TEMPLATES.TemplateResponse(request, "index.html", {"boot": json.dumps(boot, ensure_ascii=False)})

    @app.get("/api/search")
    def api_search(c: SearchCriteria = Depends(criteria_params), live: bool = False, status: str | None = None):
        if live:
            res = engine.search(c)
            new = {j.uid for j in res.new_jobs}
            jobs, per_source, errors, scraped = res.jobs, res.per_source, res.errors, res.scraped
        else:
            if status and status not in STATUSES:
                raise HTTPException(400, f"status must be one of {STATUSES}")
            jobs, new, per_source, errors, scraped = engine.search_stored(c, status=status), set(), {}, {}, None
        return {"count": len(jobs), "scraped": scraped, "per_source": per_source, "errors": errors,
                "jobs": [{**j.to_dict(), "is_new": j.uid in new} for j in jobs]}

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
        return sources_info()

    @app.get("/api/check")
    def api_check(q: str = "developer"):
        return engine.check(q)

    return app
