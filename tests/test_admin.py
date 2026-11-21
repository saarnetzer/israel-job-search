"""Admin page: who can see it, and that the numbers add up."""

import pytest
from fastapi.testclient import TestClient

from jobsearch_il import auth, db
from jobsearch_il.engine import JobSearchEngine
from jobsearch_il.models import Job
from jobsearch_il.sources.base import Source
from jobsearch_il.storage import JobStore
from jobsearch_il.web.app import create_app


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    monkeypatch.setattr(auth, "_N", 2 ** 10)


class Src(Source):
    name = "fake"

    def search(self, criteria):
        yield Job(source="fake", title="Python Developer", url="https://f/1", location="תל אביב")


def make(db_url, **kw):
    app = create_app(engine=JobSearchEngine({}, store=JobStore(db_url), sources={"fake": Src}), **kw)
    return lambda: TestClient(app)


def user(new_client, email, lang=None):
    c = new_client()
    if lang:
        c.get(f"/lang/{lang}")
    c.post("/register", data={"email": email, "password": "password123", "password2": "password123", "first_name": "Test", "last_name": "User"})
    return c


def search(c, cv=False):
    c.get("/api/search", params={"live": True, "q": "python"})
    return c.get("/api/search", params={"mark": True, **({"cv": True, "min_match": 0} if cv else {"q": "python"})})


def test_only_admins_see_it(db_url):
    new = make(db_url)
    owner = user(new, "owner@example.com")           # no ADMIN_EMAILS: the first user is the admin
    other = user(new, "other@example.com")
    assert owner.get("/admin").status_code == 200 and "📊" in owner.get("/").text
    r = other.get("/admin", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert "/admin" not in other.get("/").text
    assert other.get("/api/admin/stats").status_code == 403
    assert new().get("/admin", follow_redirects=False).headers["location"] == "/login"

    new2 = make(db_url, admin_emails=["Other@Example.com"])  # explicit list wins (case-insensitive)
    c = new2(); c.post("/login", data={"email": "other@example.com", "password": "password123"})
    assert c.get("/api/admin/stats").status_code == 200
    c = new2(); c.post("/login", data={"email": "owner@example.com", "password": "password123"})
    assert c.get("/api/admin/stats").status_code == 403


def test_numbers(db_url):
    new = make(db_url)
    owner = user(new, "owner@example.com")
    a = user(new, "a@example.com", lang="ar")
    user(new, "idle@example.com")
    search(owner)
    search(a); search(a)
    a.post("/api/cv", files={"file": ("cv.txt", b"Dana\nBackend Developer\n2020 - 2024: Backend Developer, X\nPython",
                                       "text/plain")})
    search(a, cv=True)
    a.post("/api/searches", json={"name": "x", "params": {"q": "python"}})
    s = owner.get("/api/admin/stats").json()
    t = s["totals"]
    assert t["registered"] == 3 and t["new_7d"] == 3
    assert t["active_7d"] == 2 and t["active_30d"] == 2          # "idle" never searched
    assert t["searches_7d"] == 4 and t["cvs"] == 1 and t["saved_searches"] == 1
    assert t["logged_in"] == 3 and t["jobs_in_db"] == 1
    assert s["searches_by_mode"] == {"words": 3, "cv": 1}
    assert s["searches_by_lang"] == {"he": 1, "ar": 3}
    assert s["users_by_lang"]["ar"] == 1
    today = s["daily"][0]
    assert (today["signups"], today["searches"], today["searchers"], today["cv_uploads"]) == (3, 4, 2, 1)
    assert len(s["daily"]) == 30
    by_email = {u["email"]: u for u in s["users"]}
    assert by_email["a@example.com"]["searches"] == 3 and by_email["a@example.com"]["has_cv"]
    assert by_email["idle@example.com"]["searches"] == 0 and by_email["idle@example.com"]["last_search_at"] is None
    # the admin page renders, in Arabic too
    assert "משתמשים רשומים" in owner.get("/admin").text
    owner.get("/lang/ar")
    assert "مستخدمون مسجّلون" in owner.get("/admin").text


def test_events_store_no_search_content_and_survive_account_deletion(db_url):
    new = make(db_url)
    owner = user(new, "owner@example.com")
    a = user(new, "a@example.com")
    search(a)
    store = JobStore(db_url)
    with store.engine.connect() as conn:
        cols = [c.name for c in db.events.columns]
        rows = conn.execute(db.events.select()).mappings().all()
    assert cols == ["id", "ts", "user_id", "kind", "mode", "lang"]  # no query text, no CV content
    assert sorted(r["kind"] for r in rows) == ["search", "signup", "signup"]
    a.request("DELETE", "/api/account", json={"password": "password123"})
    t = owner.get("/api/admin/stats").json()["totals"]
    assert t["registered"] == 1 and t["searches_7d"] == 1       # the search still counts, anonymously
    with store.engine.connect() as conn:
        assert conn.execute(db.events.select().where(db.events.c.kind == "search")).mappings().one()["user_id"] is None


def test_admin_shows_names(db_url):
    new = make(db_url)
    owner = user(new, "owner@example.com")
    people = owner.get("/api/admin/stats").json()["users"]
    assert (people[0]["first_name"], people[0]["last_name"]) == ("Test", "User")
    assert '"adm_name": "שם"' in owner.get("/admin").text  # the column title reaches the page
