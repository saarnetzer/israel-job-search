"""FastAPI web app (Hebrew, RTL): accounts, live search across job sites, settings, JSON API."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..auth import AuthError, RateLimiter, UserStore
from ..cv import CVError, CVProfile, extract_profile, extract_text, score_job, search_queries
from ..engine import JobSearchEngine
from ..locations import REGIONS
from ..models import SearchCriteria
from ..storage import STATUSES, JobStore

HERE = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(HERE / "templates"))
COOKIE = "jsil_session"

# fields a user may keep as default search settings
DEFAULT_FIELDS = {"q", "location", "job_type", "days", "max_exp", "min_salary", "exclude", "exclude_company",
                  "remote", "match_all", "title_only", "pages", "source", "mode"}


def _split(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def criteria_params(
    q: str = "", exclude: str = "", location: str = "", remote: bool = False, job_type: str = "",
    days: int | None = None, min_salary: int | None = None, max_exp: int | None = None,
    source: list[str] = Query([]), match_all: bool = False, title_only: bool = False,
    exclude_company: str = "", company: str = "", pages: int = Query(2, ge=1, le=5),
    limit: int = Query(300, ge=1, le=2000),
) -> SearchCriteria:
    return SearchCriteria(
        keywords=_split(q), match_all=match_all, title_only=title_only, exclude_keywords=_split(exclude),
        locations=_split(location), remote_only=remote, job_types=_split(job_type), companies=_split(company),
        exclude_companies=_split(exclude_company), posted_within_days=days, min_salary=min_salary,
        max_experience_years=max_exp, sources=[s for x in source for s in _split(x)], max_pages=pages, limit=limit,
    )


class LoginRequired(Exception):
    pass


def create_app(config: dict[str, Any] | None = None, db_url: str = "jobs.db",
               engine: JobSearchEngine | None = None, invite_code: str | None = None,
               secure_cookies: bool = False, registration_open: bool = True) -> FastAPI:
    engine = engine or JobSearchEngine(config or {}, store=JobStore(db_url))
    if engine.store is None:
        raise ValueError("the web app needs a database")
    users = UserStore(engine.store.engine)
    limiter = RateLimiter()
    app = FastAPI(title="חיפוש עבודה בישראל", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

    # ------------------------------------------------------------------ helpers
    @app.middleware("http")
    async def same_origin_only(request: Request, call_next):
        """Block cross-site state changes (CSRF): non-GET requests must come from this site."""
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin") or request.headers.get("referer")
            if origin and urlsplit(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "cross-site request blocked"}, status_code=403)
        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    @app.exception_handler(LoginRequired)
    async def _login_redirect(request: Request, exc: LoginRequired):
        return RedirectResponse("/login", status_code=303)

    def page_user(request: Request) -> dict[str, Any]:
        uid = users.user_for_session(request.cookies.get(COOKIE))
        user = users.get(uid) if uid else None
        if user is None:
            raise LoginRequired()
        return user

    def api_user(request: Request) -> dict[str, Any]:
        uid = users.user_for_session(request.cookies.get(COOKIE))
        user = users.get(uid) if uid else None
        if user is None:
            raise HTTPException(401, "יש להתחבר")
        return user

    def set_session(resp: Response, user_id: int) -> Response:
        resp.set_cookie(COOKIE, users.create_session(user_id), max_age=30 * 86400, httponly=True,
                        secure=secure_cookies, samesite="lax", path="/")
        return resp

    def sources_info() -> list[dict[str, Any]]:
        active = {s.name for s in engine.enabled_sources()}
        return [{"name": n, "display_name": c.display_name, "active": n in active, "needs_config": c.needs_config}
                for n, c in engine.registry.items()]

    def cv_info(user_id: int) -> dict[str, Any] | None:
        cv = users.get_cv(user_id)
        if cv is None:
            return None
        profile = CVProfile.from_dict(cv["profile"])
        return {"filename": cv["filename"], "uploaded_at": cv["uploaded_at"].isoformat(timespec="seconds"),
                "profile": profile.to_dict(), "queries": search_queries(profile), "chars": len(cv["text"])}

    def client_ip(request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for", "")
        return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")

    def auth_page(request: Request, mode: str, error: str = "", email: str = "", status: int = 200):
        return TEMPLATES.TemplateResponse(request, "auth.html", {
            "mode": mode, "error": error, "email": email, "need_invite": bool(invite_code),
            "registration_open": registration_open}, status_code=status)

    # ------------------------------------------------------------------ auth pages
    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request):
        if users.user_for_session(request.cookies.get(COOKIE)):
            return RedirectResponse("/", status_code=303)
        return auth_page(request, "login")

    @app.post("/login")
    def login(request: Request, email: str = Form(""), password: str = Form("")):
        keys = [f"ip:{client_ip(request)}", f"email:{email.strip().lower()}"]
        if any(limiter.blocked(k) for k in keys):
            return auth_page(request, "login", "יותר מדי ניסיונות. נסו שוב בעוד כמה דקות.", email, 429)
        uid = users.authenticate(email, password)
        if uid is None:
            for k in keys:
                limiter.fail(k)
            return auth_page(request, "login", "אימייל או סיסמה שגויים", email, 401)
        for k in keys:
            limiter.reset(k)
        return set_session(RedirectResponse("/", status_code=303), uid)

    @app.get("/register", response_class=HTMLResponse)
    def register_page(request: Request):
        return auth_page(request, "register")

    @app.post("/register")
    def register(request: Request, email: str = Form(""), password: str = Form(""),
                 password2: str = Form(""), invite: str = Form("")):
        if not registration_open:
            return auth_page(request, "register", "ההרשמה סגורה כרגע", email, 403)
        ip_key = f"reg:{client_ip(request)}"
        if limiter.blocked(ip_key):
            return auth_page(request, "register", "יותר מדי ניסיונות. נסו שוב מאוחר יותר.", email, 429)
        if invite_code and invite.strip() != invite_code:
            limiter.fail(ip_key)
            return auth_page(request, "register", "קוד ההזמנה שגוי", email, 403)
        if password != password2:
            return auth_page(request, "register", "הסיסמאות לא תואמות", email, 400)
        try:
            uid = users.register(email, password)
        except AuthError as e:
            return auth_page(request, "register", str(e), email, 400)
        return set_session(RedirectResponse("/", status_code=303), uid)

    @app.post("/logout")
    def logout(request: Request):
        users.end_session(request.cookies.get(COOKIE))
        resp = RedirectResponse("/login", status_code=303)
        resp.delete_cookie(COOKIE, path="/")
        return resp

    # ------------------------------------------------------------------ app pages
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, user: dict = Depends(page_user)):
        boot = {"sources": sources_info(), "regions": list(REGIONS), "stats": engine.store.stats(),
                "user": {"email": user["email"], "settings": user["settings"]},
                "searches": users.list_searches(user["id"]), "cv": cv_info(user["id"])}
        return TEMPLATES.TemplateResponse(request, "index.html", {"boot": json.dumps(boot, ensure_ascii=False),
                                                                  "user": user})

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request, user: dict = Depends(page_user)):
        boot = {"sources": sources_info(), "regions": list(REGIONS), "settings": user["settings"],
                "searches": users.list_searches(user["id"]), "cv": cv_info(user["id"])}
        return TEMPLATES.TemplateResponse(request, "settings.html", {"boot": json.dumps(boot, ensure_ascii=False),
                                                                     "user": user})

    # ------------------------------------------------------------------ API
    @app.get("/api/me")
    def me(user: dict = Depends(api_user)):
        return {"email": user["email"], "settings": user["settings"],
                "created_at": user["created_at"].isoformat(timespec="seconds")}

    @app.put("/api/settings")
    def put_settings(data: dict = Body(...), user: dict = Depends(api_user)):
        defaults = {k: v for k, v in (data.get("defaults") or {}).items() if k in DEFAULT_FIELDS}
        settings = {**user["settings"], "defaults": defaults}
        users.update_settings(user["id"], settings)
        return {"ok": True, "settings": settings}

    @app.post("/api/settings/password")
    def change_password(request: Request, data: dict = Body(...), user: dict = Depends(api_user)):
        try:
            users.change_password(user["id"], str(data.get("current", "")), str(data.get("new", "")))
        except AuthError as e:
            raise HTTPException(400, str(e))
        users.end_all_sessions(user["id"], keep=request.cookies.get(COOKIE))  # sign out other devices
        return {"ok": True}

    @app.delete("/api/account")
    def delete_account(data: dict = Body(...), user: dict = Depends(api_user)):
        if users.authenticate(user["email"], str(data.get("password", ""))) != user["id"]:
            raise HTTPException(400, "הסיסמה שגויה")
        users.delete(user["id"])
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE, path="/")
        return resp

    @app.get("/api/searches")
    def list_searches(user: dict = Depends(api_user)):
        return users.list_searches(user["id"])

    @app.post("/api/searches")
    def save_search(data: dict = Body(...), user: dict = Depends(api_user)):
        params = {k: v for k, v in (data.get("params") or {}).items() if k in DEFAULT_FIELDS}
        try:
            sid = users.save_search(user["id"], str(data.get("name", "")), params)
        except AuthError as e:
            raise HTTPException(400, str(e))
        return {"id": sid, "searches": users.list_searches(user["id"])}

    @app.delete("/api/searches/{search_id}")
    def delete_search(search_id: int, user: dict = Depends(api_user)):
        if not users.delete_search(user["id"], search_id):
            raise HTTPException(404, "not found")
        return {"ok": True}

    @app.get("/api/cv")
    def get_cv(user: dict = Depends(api_user)):
        return {"cv": cv_info(user["id"])}

    @app.post("/api/cv")
    async def upload_cv(file: UploadFile = File(...), user: dict = Depends(api_user)):
        data = await file.read(5 * 1024 * 1024 + 1)
        try:
            text = extract_text(file.filename or "", data)
        except CVError as e:
            raise HTTPException(400, str(e))
        profile = extract_profile(text)
        users.save_cv(user["id"], file.filename or "cv", text, profile.to_dict())
        return {"cv": cv_info(user["id"])}

    @app.put("/api/cv")
    def update_cv(data: dict = Body(...), user: dict = Depends(api_user)):
        clean = lambda xs: [str(x).strip()[:60] for x in (xs or []) if str(x).strip()][:30]  # noqa: E731
        cv = users.get_cv(user["id"])
        if cv is None:
            raise HTTPException(404, "לא הועלו קורות חיים")
        profile = {**cv["profile"], "roles": clean(data.get("roles")), "skills": clean(data.get("skills"))}
        users.update_cv_profile(user["id"], profile)
        return {"cv": cv_info(user["id"])}

    @app.delete("/api/cv")
    def delete_cv(user: dict = Depends(api_user)):
        users.delete_cv(user["id"])
        return {"ok": True}

    @app.get("/api/search/since")
    def search_since(user: dict = Depends(api_user)):
        """When this user's previous search finished: jobs first seen after it get a "new" badge."""
        prev = user["last_search_at"]
        return {"since": prev.isoformat(timespec="seconds") if prev else None}

    @app.get("/api/search")
    def api_search(c: SearchCriteria = Depends(criteria_params), live: bool = False, status: str | None = None,
                   since: str | None = None, mark: bool = False, cv: bool = False,
                   min_match: int = Query(25, ge=0, le=100), user: dict = Depends(api_user)):
        if live:
            res = engine.search(c)
            return {"count": len(res.jobs), "scraped": res.scraped, "per_source": res.per_source,
                    "errors": res.errors}
        if status and status not in STATUSES:
            raise HTTPException(400, f"status must be one of {STATUSES}")
        cutoff = None
        if since:
            try:
                cutoff = datetime.fromisoformat(since)
            except ValueError:
                raise HTTPException(400, "bad since")
        profile = None
        if cv:
            saved = users.get_cv(user["id"])
            if saved is None:
                raise HTTPException(400, "לא הועלו קורות חיים")
            profile = CVProfile.from_dict(saved["profile"])
            limit, c.limit = c.limit, None
            c.keywords = []  # the CV decides relevance, in title and description
        jobs = engine.search_stored(c, status=status, user_id=user["id"])
        matches: dict[str, dict[str, Any]] = {}
        if profile is not None:
            scored = []
            for j in jobs:
                score, matched = score_job(j, profile)
                if score >= min_match:
                    matches[j.uid] = {"score": score, "matched": matched}
                    scored.append(j)
            jobs = sorted(scored, key=lambda j: (matches[j.uid]["score"], j.posted_at or datetime.min), reverse=True)
            jobs = jobs[:limit] if limit else jobs
        if mark:
            users.mark_searched(user["id"])

        def is_new(j) -> bool:  # no cutoff = first search ever: nothing is "new" yet
            return cutoff is not None and j.extra.get("first_seen", "") > cutoff.isoformat(timespec="seconds")

        return {"count": len(jobs),
                "jobs": [{**j.to_dict(), "is_new": is_new(j), "match": matches.get(j.uid)} for j in jobs]}

    @app.post("/api/jobs/{uid}/status/{status}")
    def set_status(uid: str, status: str, user: dict = Depends(api_user)):
        try:
            ok = engine.store.set_status(uid, status, user_id=user["id"])
        except ValueError as e:
            raise HTTPException(400, str(e))
        if not ok:
            raise HTTPException(404, "job not found")
        return {"ok": True}

    @app.get("/api/sources")
    def api_sources(user: dict = Depends(api_user)):
        return sources_info()

    @app.get("/api/check")
    def api_check(q: str = "developer", user: dict = Depends(api_user)):
        return engine.check(q)

    return app
