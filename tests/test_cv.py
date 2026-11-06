import pytest
from fastapi.testclient import TestClient

from cv_samples import EN_CV, HE_CV, docx_bytes, pdf_bytes
from jobsearch_il import auth
from jobsearch_il.cv import (CVError, CVProfile, extract_profile, extract_text, fix_hebrew_order, score_job,
                             search_queries)
from jobsearch_il.engine import JobSearchEngine
from jobsearch_il.models import Job
from jobsearch_il.sources.base import Source
from jobsearch_il.storage import JobStore
from jobsearch_il.web.app import create_app


def test_english_pdf_profile():
    p = extract_profile(extract_text("cv.pdf", pdf_bytes(EN_CV)))
    assert p.roles[0] == "Backend Developer"
    for s in ("Python", "Go", "Git", "Django", "AWS", "Kubernetes", "Kafka"):
        assert s in p.skills, s
    assert "Golang" not in p.skills and "R" not in p.skills
    assert p.years == 6
    assert search_queries(p)[:2] == ["backend developer", "software engineer"]


@pytest.mark.parametrize("make", [lambda: ("cv.docx", docx_bytes(HE_CV)),
                                  lambda: ("cv.pdf", pdf_bytes(HE_CV, visual_order=True))])
def test_hebrew_profile_uses_hebrew_search_terms(make):
    p = extract_profile(extract_text(*make()))
    assert p.roles[0] == "Bookkeeper / Accountant"
    assert p.terms["Bookkeeper / Accountant"] == "מנהלת חשבונות"
    assert {"חשבשבת", "פריוריטי", "התאמות בנקים", "הכנת שכר"} <= set(p.skills)
    assert "שכר" not in p.skills  # bare "שכר" also means "salary" in job ads
    assert search_queries(p)[0] == "מנהלת חשבונות"
    assert p.years == 10  # 2016 - today


def test_fix_reversed_hebrew_line():
    good = "מנהלת חשבונות במשרד רואי חשבון ותיק"  # detection relies on final letters (ן)
    assert fix_hebrew_order(good[::-1]) == good
    assert fix_hebrew_order(good) == good
    assert fix_hebrew_order("ניסיון 9102 - היום") == "ניסיון 2019 - היום"


def test_bad_files():
    with pytest.raises(CVError, match="סוג קובץ"):
        extract_text("cv.png", b"\x89PNG....")
    with pytest.raises(CVError, match="‎.docx‎"):
        extract_text("cv.doc", b"xx")
    with pytest.raises(CVError, match="לא נמצא טקסט"):
        extract_text("cv.txt", b"hi")
    with pytest.raises(CVError, match="גדול"):
        extract_text("cv.txt", b"x" * (6 * 1024 * 1024))
    with pytest.raises(CVError, match="לא הצלחתי"):
        extract_text("cv.pdf", b"%PDF-broken")


def test_score_title_beats_description():
    p = CVProfile(roles=["Backend Developer"], skills=["Python", "AWS", "Kafka"])
    in_title = Job(source="t", title="Backend Developer (Python)", url="u1", description="AWS")
    in_desc = Job(source="t", title="Engineer", url="u2", description="backend developer, python")
    unrelated = Job(source="t", title="נהג חלוקה", url="u3", description="רישיון C")
    s1, m1 = score_job(in_title, p)
    s2, _ = score_job(in_desc, p)
    s3, m3 = score_job(unrelated, p)
    assert s1 > s2 > s3 == 0
    assert m1 == ["Backend Developer", "Python", "AWS"] and m3 == []


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    monkeypatch.setattr(auth, "_N", 2 ** 10)


class FakeSource(Source):
    name = "fake"
    display_name = "Fake"
    queries: list = []

    def search(self, criteria):
        FakeSource.queries.append(criteria.query)
        yield Job(source="fake", title="Senior Backend Developer", url="https://f/1", company="A", location="תל אביב",
                  description="Python, Django, PostgreSQL, AWS, Docker")
        yield Job(source="fake", title="Python Developer", url="https://f/2", company="B", location="חיפה",
                  description="Python scripts")
        yield Job(source="fake", title="מנהלת חשבונות", url="https://f/3", company="C", location="תל אביב",
                  description="חשבשבת")


def test_cv_web_flow(db_url):
    c = TestClient(create_app(engine=JobSearchEngine({}, store=JobStore(db_url), sources={"fake": FakeSource})))
    c.post("/register", data={"email": "a@example.com", "password": "password123", "password2": "password123"})
    assert c.get("/api/cv").json() == {"cv": None}
    assert c.get("/api/search", params={"cv": True}).status_code == 400

    r = c.post("/api/cv", files={"file": ("dana.pdf", pdf_bytes(EN_CV), "application/pdf")})
    cv = r.json()["cv"]
    assert cv["filename"] == "dana.pdf" and cv["profile"]["roles"][0] == "Backend Developer"
    assert cv["queries"][0] == "backend developer"
    assert c.post("/api/cv", files={"file": ("x.png", b"123", "image/png")}).status_code == 400

    # edit tags: remove a skill, add one
    skills = [s for s in cv["profile"]["skills"] if s != "Kafka"] + ["Celery"]
    cv = c.put("/api/cv", json={"roles": cv["profile"]["roles"], "skills": skills}).json()["cv"]
    assert "Kafka" not in cv["profile"]["skills"] and "Celery" in cv["profile"]["skills"]

    c.get("/api/search", params={"live": True, "q": ", ".join(cv["queries"])})
    jobs = c.get("/api/search", params={"cv": True, "location": "מרכז"}).json()["jobs"]
    assert [j["title"] for j in jobs] == ["Senior Backend Developer"]  # Haifa filtered, bookkeeping not a match
    assert jobs[0]["match"]["score"] >= 80 and "Backend Developer" in jobs[0]["match"]["matched"]
    everything = c.get("/api/search", params={"cv": True, "min_match": 0}).json()["jobs"]
    scores = {j["title"]: j["match"]["score"] for j in everything}
    assert scores["Senior Backend Developer"] > scores["Python Developer"] > scores["מנהלת חשבונות"] == 0

    assert "📄" in c.get("/").text and "קורות חיים" in c.get("/settings").text
    assert c.delete("/api/cv").json() == {"ok": True}
    assert c.get("/api/cv").json() == {"cv": None}
