import pytest
from fastapi.testclient import TestClient

from jobsearch_il import auth
from jobsearch_il.engine import JobSearchEngine
from jobsearch_il.models import Job
from jobsearch_il.sources.base import Source
from jobsearch_il.storage import JobStore
from jobsearch_il.web.app import create_app


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    monkeypatch.setattr(auth, "_N", 2 ** 10)  # keep tests fast; production uses 2^17


class FakeSource(Source):
    name = "fake"
    display_name = "Fake"
    extra_jobs: list = []

    def search(self, criteria):
        yield Job(source="fake", title="Python Developer", url="https://f/1", company="A", location="Haifa")
        yield Job(source="fake", title="Java Developer", url="https://f/2", company="B", location="Tel Aviv")
        yield from FakeSource.extra_jobs


def make_client(db_url, **kw):
    eng = JobSearchEngine({}, store=JobStore(db_url), sources={"fake": FakeSource})
    return TestClient(create_app(engine=eng, **kw))


def register(c, email="a@example.com", pw="password123", **extra):
    return c.post("/register", data={"email": email, "password": pw, "password2": pw, "first_name": "Test", "last_name": "User", **extra},
                  follow_redirects=False)


def test_pages_require_login(db_url):
    c = make_client(db_url)
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert c.get("/api/search").status_code == 401
    assert c.get("/healthz").json() == {"ok": True}
    assert 'dir="rtl"' in c.get("/login").text


def test_register_login_logout(db_url):
    c = make_client(db_url)
    r = register(c, "Me@Example.com")
    assert r.status_code == 303 and "jsil_session" in r.cookies
    assert c.get("/api/me").json()["email"] == "me@example.com"
    assert "me@example.com" in c.get("/").text
    c.post("/logout")
    assert c.get("/api/me").status_code == 401
    # wrong password, then right one (email is case-insensitive)
    assert c.post("/login", data={"email": "me@example.com", "password": "nope"}).status_code == 401
    r = c.post("/login", data={"email": "ME@example.com", "password": "password123"}, follow_redirects=False)
    assert r.status_code == 303
    assert c.get("/api/me").status_code == 200


def test_register_validation(db_url):
    c = make_client(db_url)
    assert "לפחות 8" in register(c, pw="short").text
    assert "לא תקינה" in register(c, email="not-an-email").text
    r = c.post("/register", data={"email": "x@y.co", "password": "password123", "password2": "different1", "first_name": "Test", "last_name": "User"})
    assert "לא תואמות" in r.text
    assert register(c).status_code == 303
    c.cookies.clear()
    assert "כבר קיים" in register(c).text


def test_invite_code_and_closed_registration(db_url):
    c = make_client(db_url, invite_code="secret")
    assert "קוד הזמנה" in c.get("/register").text
    assert register(c, invite="wrong").status_code == 403
    assert register(c, invite="secret").status_code == 303
    closed = make_client(db_url, registration_open=False)
    assert register(closed, email="b@example.com").status_code == 403


def test_login_rate_limit(db_url):
    c = make_client(db_url)
    register(c)
    c.cookies.clear()
    codes = [c.post("/login", data={"email": "a@example.com", "password": "bad"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429
    # even the right password is blocked for now
    assert c.post("/login", data={"email": "a@example.com", "password": "password123"}).status_code == 429


def test_cross_site_post_blocked(db_url):
    c = make_client(db_url)
    register(c)
    r = c.post("/api/searches", json={"name": "x", "params": {}}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_search_statuses_are_per_user(db_url):
    a = make_client(db_url)
    register(a, "a@example.com")
    assert a.get("/api/search", params={"live": True, "q": "developer"}).json()["count"] == 2
    jobs = a.get("/api/search", params={"q": "python"}).json()["jobs"]
    uid = jobs[0]["uid"]
    assert a.post(f"/api/jobs/{uid}/status/saved").json() == {"ok": True}
    assert [j["uid"] for j in a.get("/api/search", params={"status": "saved"}).json()["jobs"]] == [uid]

    b = make_client(db_url)
    register(b, "b@example.com")
    assert b.get("/api/search", params={"status": "saved"}).json()["jobs"] == []
    b.post(f"/api/jobs/{uid}/status/hidden")
    assert b.get("/api/search", params={"q": "python"}).json()["count"] == 0
    assert a.get("/api/search", params={"q": "python"}).json()["count"] == 1


def test_new_badge_since_previous_search(db_url):
    c = make_client(db_url)
    register(c)
    assert c.get("/api/search/since").json()["since"] is None
    c.get("/api/search", params={"live": True})
    first = c.get("/api/search", params={"since": "", "mark": True}).json()["jobs"]
    assert first and not any(j["is_new"] for j in first)  # first search ever: nothing flagged

    since = c.get("/api/search/since").json()["since"]
    assert since
    FakeSource.extra_jobs = [Job(source="fake", title="Go Developer", url="https://f/3", company="C", location="Haifa")]
    try:
        import time
        time.sleep(1.1)  # timestamps have 1s resolution
        c.get("/api/search", params={"live": True})
        jobs = c.get("/api/search", params={"since": since, "mark": True}).json()["jobs"]
    finally:
        FakeSource.extra_jobs = []
    assert {j["title"] for j in jobs if j["is_new"]} == {"Go Developer"}


def test_settings_saved_searches_password_delete(db_url):
    c = make_client(db_url)
    register(c)
    r = c.put("/api/settings", json={"defaults": {"q": "python", "location": "מרכז", "evil": "x"}})
    assert r.json()["settings"]["defaults"] == {"q": "python", "location": "מרכז"}
    assert c.get("/api/me").json()["settings"]["defaults"]["q"] == "python"
    assert "הגדרות" in c.get("/settings").text

    sid = c.post("/api/searches", json={"name": "פייתון במרכז", "params": {"q": "python"}}).json()["id"]
    c.post("/api/searches", json={"name": "פייתון במרכז", "params": {"q": "python, django"}})  # same name updates
    searches = c.get("/api/searches").json()
    assert len(searches) == 1 and searches[0]["params"]["q"] == "python, django"
    assert c.post("/api/searches", json={"name": " ", "params": {}}).status_code == 400
    assert c.delete(f"/api/searches/{sid}").json() == {"ok": True}

    # other devices are signed out after a password change
    other = make_client(db_url)
    other.post("/login", data={"email": "a@example.com", "password": "password123"})
    assert other.get("/api/me").status_code == 200
    assert c.post("/api/settings/password", json={"current": "wrong", "new": "newpassword1"}).status_code == 400
    assert c.post("/api/settings/password", json={"current": "password123", "new": "newpassword1"}).json() == {"ok": True}
    assert c.get("/api/me").status_code == 200
    assert other.get("/api/me").status_code == 401

    assert c.request("DELETE", "/api/account", json={"password": "nope"}).status_code == 400
    assert c.request("DELETE", "/api/account", json={"password": "newpassword1"}).json() == {"ok": True}
    c.cookies.clear()
    assert c.post("/login", data={"email": "a@example.com", "password": "newpassword1"}).status_code == 401


def test_password_hashing():
    h = auth.hash_password("correct horse")
    assert h.startswith("scrypt$") and "correct" not in h
    assert auth.verify_password("correct horse", h)
    assert not auth.verify_password("wrong", h)
    assert not auth.verify_password("x", "garbage")


def test_since_endpoint_gives_server_clock_for_scoping(db_url):
    c = make_client(db_url)
    register(c)
    t = c.get("/api/search/since").json()
    assert t["since"] is None and t["now"]
    c.get("/api/search", params={"live": True, "q": "developer"})
    assert c.get("/api/search", params={"seen_after": t["now"]}).json()["count"] == 2
    assert c.get("/api/search", params={"seen_after": "2999-01-01T00:00:00"}).json()["count"] == 0
    assert c.get("/api/search", params={"seen_after": "nope"}).status_code == 400


def test_names_on_registration_and_settings(db_url):
    c = make_client(db_url)
    base = {"email": "n@example.com", "password": "password123", "password2": "password123"}
    r = c.post("/register", data={**base, "first_name": " ", "last_name": "כהן"})
    assert r.status_code == 400 and "יש למלא שם פרטי ושם משפחה" in r.text
    assert 'value="כהן"' in r.text  # what was typed is kept
    r = c.post("/register", data={**base, "first_name": "<b>x", "last_name": "כהן"})
    assert r.status_code == 400 and "רק אותיות" in r.text
    r = c.post("/register", data={**base, "first_name": "  נועה   מרים ", "last_name": "בן-דוד"}, follow_redirects=False)
    assert r.status_code == 303
    me = c.get("/api/me").json()
    assert (me["first_name"], me["last_name"]) == ("נועה מרים", "בן-דוד")
    assert "נועה מרים בן-דוד" in c.get("/").text  # shown in the top bar
    # Arabic and English names, apostrophes
    assert c.put("/api/profile", json={"first_name": "عبد الله", "last_name": "O'Neil"}).status_code == 200
    assert c.get("/api/me").json()["first_name"] == "عبد الله"
    assert c.put("/api/profile", json={"first_name": "", "last_name": "x"}).status_code == 400
    assert c.put("/api/profile", json={"first_name": "a" * 61, "last_name": "x"}).json()["detail"] == "השם ארוך מדי"
    assert "פרטים אישיים" in c.get("/settings").text


def test_existing_database_gets_name_columns(tmp_path):
    """A database created before names existed (like the live one on Neon) is upgraded on start."""
    import sqlalchemy as sa

    from jobsearch_il import db

    path = tmp_path / "old.db"
    eng = sa.create_engine(f"sqlite:///{path}")
    with eng.begin() as conn:
        conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(254) NOT NULL UNIQUE, "
                             "password_hash TEXT NOT NULL, settings TEXT NOT NULL, created_at DATETIME NOT NULL, "
                             "last_search_at DATETIME)"))
        conn.execute(sa.text("INSERT INTO users (email, password_hash, settings, created_at) "
                             "VALUES ('old@example.com', 'x', '{}', '2026-11-01 10:00:00')"))
    eng.dispose()
    upgraded = db.make_engine(str(path))
    cols = {c["name"] for c in sa.inspect(upgraded).get_columns("users")}
    assert {"first_name", "last_name"} <= cols
    with upgraded.connect() as conn:
        row = conn.execute(sa.text("SELECT email, first_name FROM users")).one()
    assert row == ("old@example.com", None)  # existing users are kept, without a name
    db.make_engine(str(path))  # running it again changes nothing
