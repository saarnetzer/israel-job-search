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
    everything = c.get("/api/search", params={"cv": True, "min_match": 0}).json()
    scores = {j["title"]: j["match"]["score"] for j in everything["jobs"]}
    assert scores["Senior Backend Developer"] > scores["Python Developer"] > 0
    # a bookkeeping job asks for a title this CV doesn't have
    assert [(h["title"], h["why"]) for h in everything["hidden"]] == [("מנהלת חשבונות", "title")]

    assert "📄" in c.get("/").text and "קורות חיים" in c.get("/settings").text
    assert c.delete("/api/cv").json() == {"ok": True}
    assert c.get("/api/cv").json() == {"cv": None}


@pytest.mark.parametrize("text,hit", [
    ("דרוש /ה חשב /ת שכר למשרד", True), ("דרושה חשבת שכר", True), ("דרוש חשב שכר", True),
    ("עבודה מול חשבת השכר", True), ("מנהלת חשבונות סוג 3", False), ("משרה עם שכר גבוה", False),
])
def test_exclude_phrase_catches_gender_forms(text, hit):
    from jobsearch_il.cv import excluded_by

    p = CVProfile(exclude=["חשבת שכר"])
    assert (excluded_by(Job(source="t", title="x", url="u", description=text), p) == "חשבת שכר") is hit


def test_include_tags_search_and_score():
    from jobsearch_il.cv import content_words, include_in

    assert content_words("ניסיון עם כספים") == ["כספים"]
    assert include_in("מחלקת הכספים", "ניסיון עם כספים")
    assert not include_in("Finance team", "ניסיון עם כספים")
    p = CVProfile(roles=["Bookkeeper / Accountant"], terms={"Bookkeeper / Accountant": "מנהלת חשבונות"},
                  skills=["חשבשבת"], include=["ניסיון עם כספים"])
    assert search_queries(p) == ["מנהלת חשבונות", "כספים", "חשבשבת"]
    with_wish = Job(source="t", title="מנהלת חשבונות למחלקת כספים", url="u1", description="חשבשבת")
    without = Job(source="t", title="מנהלת חשבונות", url="u2", description="חשבשבת")
    (s1, m1), (s2, _) = score_job(with_wish, p), score_job(without, p)
    assert s1 > s2 and "ניסיון עם כספים" in m1


def test_cv_include_exclude_web(db_url):
    class Src(Source):
        name = "fake"

        def search(self, criteria):
            yield Job(source="fake", title="מנהלת חשבונות למחלקת כספים", url="https://f/1", location="תל אביב",
                      description="חשבשבת, פריוריטי")
            yield Job(source="fake", title="חשב /ת שכר ומנהל /ת חשבונות", url="https://f/2", location="תל אביב",
                      description="חשבשבת")
            yield Job(source="fake", title="מנהלת חשבונות", url="https://f/3", location="תל אביב",
                      description="חשבשבת")

    c = TestClient(create_app(engine=JobSearchEngine({}, store=JobStore(db_url), sources={"fake": Src})))
    c.post("/register", data={"email": "r@example.com", "password": "password123", "password2": "password123"})
    c.post("/api/cv", files={"file": ("ronit.docx", docx_bytes(HE_CV), "application/octet-stream")})
    cv = c.put("/api/cv", json={"include": ["ניסיון עם כספים"], "exclude": ["חשבת שכר"]}).json()["cv"]
    assert cv["profile"]["include"] == ["ניסיון עם כספים"] and cv["profile"]["exclude"] == ["חשבת שכר"]
    assert cv["profile"]["roles"]  # untouched fields are kept
    assert "כספים" in cv["queries"]

    c.get("/api/search", params={"live": True, "q": ", ".join(cv["queries"])})
    r = c.get("/api/search", params={"cv": True}).json()
    assert r["excluded"] == 1
    titles = [j["title"] for j in r["jobs"]]
    assert titles == ["מנהלת חשבונות למחלקת כספים", "מנהלת חשבונות"]  # wish tag ranks first, payroll hidden
    assert "ניסיון עם כספים" in r["jobs"][0]["match"]["matched"]


@pytest.mark.parametrize("title,desc,want", [
    ("עורך/ת דין למחלקה מסחרית", "", "עורך דין"),
    ("משרה במחלקה המשפטית", 'דרישות: עו"ד בעל/ת רישיון', "עורך דין"),
    ("משרה במחלקה המשפטית", 'עו"ד - יתרון', None),
    ('מזכירה למשרד עו"ד', "ניסיון במשרד עורכי דין", None),          # workplace, not the role
    ("מזכירה", 'עבודה מול משרד עו"ד חיצוני, חובה אנגלית', None),
    ("מזכירה משפטית", "", None),
    ("QA Automation Engineer", "", "qa automation"),                # a role the CV doesn't have
    ("נהג/ת חלוקה", "", "נהג"),
    ("עבודה כללית במחסן", "", "מחסן"),
    ("משרה מעניינת", "", None),                                      # no recognizable title: keep
])
def test_missing_title_law_knowledge_cv(title, desc, want):
    from jobsearch_il.cv import missing_title, title_context

    ctx = title_context("מזכירה משפטית\\nידע במשפטים, עבודה במשרד עורכי דין", CVProfile(roles=["Office / Administration"]))
    assert ctx.credentials == set()
    assert missing_title(Job(source="t", title=title, url="u", description=desc), ctx) == want


def test_missing_title_related_roles_and_credentials():
    from jobsearch_il.cv import missing_title, title_context

    dev = title_context("Backend Developer, Python, AWS", CVProfile(roles=["Backend Developer"]))
    for ok in ("Full Stack Engineer", "Senior Software Engineer", "Team Lead Backend", "Python Developer"):
        assert missing_title(Job(source="t", title=ok, url="u"), dev) is None, ok
    for bad in ("QA Automation Engineer", "DevOps Engineer", "Data Analyst"):
        assert missing_title(Job(source="t", title=bad, url="u"), dev), bad
    lawyer = title_context('עו"ד, חברה בלשכת עורכי הדין', CVProfile())
    assert "עורך דין" in lawyer.credentials
    assert missing_title(Job(source="t", title="עורך/ת דין", url="u"), lawyer) is None


def test_cv_hides_other_titles_web(db_url):
    class Src(Source):
        name = "fake"

        def search(self, criteria):
            yield Job(source="fake", title="מזכירה משפטית למשרד עו\"ד", url="https://f/1", description="אופיס")
            yield Job(source="fake", title="עורך/ת דין לליטיגציה", url="https://f/2", description="ידע במשפטים")
            yield Job(source="fake", title="משרה משפטית", url="https://f/3", description="דרישות: עו\"ד בעל/ת רישיון, אופיס")

    c = TestClient(create_app(engine=JobSearchEngine({}, store=JobStore(db_url), sources={"fake": Src})))
    c.post("/register", data={"email": "l@example.com", "password": "password123", "password2": "password123"})
    cv_text = "מיכל לוי\nמזכירה משפטית\nידע במשפטים, אופיס, הכנת מסמכים משפטיים\n2019 - היום"
    c.post("/api/cv", files={"file": ("cv.txt", cv_text.encode(), "text/plain")})
    c.get("/api/search", params={"live": True, "q": "מזכירה"})
    r = c.get("/api/search", params={"cv": True, "min_match": 0}).json()
    assert [j["title"] for j in r["jobs"]] == ['מזכירה משפטית למשרד עו"ד']
    assert sorted((h["why"], h["term"]) for h in r["hidden"]) == [("title", "עורך דין"), ("title", "עורך דין")]
    # can be switched off
    c.put("/api/cv", json={"hide_other_titles": False})
    r = c.get("/api/search", params={"cv": True, "min_match": 0}).json()
    assert len(r["jobs"]) == 3 and r["hidden"] == []


@pytest.mark.parametrize("title", ["פקיד/ת בק אופיס למחלקת שיווק", "בק אופיס למחלקת מכירות", "פקיד /ה בק אופיס למחסן",
                                   "עובד/ת שירות לקוחות וניהול משרד", "מזכיר /ה למשרד עו\"ד"])
def test_office_jobs_kept_for_secretary(title):
    from jobsearch_il.cv import missing_title, title_context

    ctx = title_context("מזכירה משפטית\nאדמיניסטרציה", CVProfile(roles=["Office / Administration"]))
    assert missing_title(Job(source="t", title=title, url="u"), ctx) is None



@pytest.mark.parametrize("title,desc", [
    ("מנהל /ת חשבונות מקצועי /ת", "ניסיון מוכח של שנה לפחות בעבודה בתוך משרד רואי חשבון (cpa) - חובה."),
    ("מנהלת חשבונות במשרד יועץ מס מוביל", 'דרישות: ניסיון במשרד רו"ח / יועץ מס של שלוש שנים לפחות.'),
    ("מנהלת חשבונות לקוחות וספקים", 'הכנת דו"חות כספיים שנתיים לביקורת רו"ח. משרה מלאה דרישות: תעודת הנה"ח'),
])
def test_bookkeeper_jobs_mentioning_cpa_are_kept(title, desc):
    from jobsearch_il.cv import missing_title, title_context

    ctx = title_context("מנהלת חשבונות סוג 3", CVProfile(roles=["Bookkeeper / Accountant"]))
    assert missing_title(Job(source="t", title=title, url="u", description=desc), ctx) is None
    # ...but a CPA job is still hidden for this CV
    assert missing_title(Job(source="t", title='רו"ח למשרד מוביל', url="u"), ctx) == "רואה חשבון"


def test_dot_and_parenthesis_gender_forms():
    from jobsearch_il.cv import _title_roles, phrase_in

    assert "Project Manager" in _title_roles("קבוצת אשטרום מגייסת מנהל.ת פרויקטים")
    assert phrase_in("דרוש.ה חשב.ת שכר", "חשבת שכר")
    assert phrase_in("מנהל(ת) חשבונות", "מנהל חשבונות")


# ------------------------------------------------------------------ titles straight from the CV
def test_titles_from_cv_structure():
    from cv_samples import CUSTOM_CV
    from jobsearch_il.cv import extract_cv_titles

    assert extract_cv_titles(EN_CV) == ["Senior Backend Developer", "Backend Developer", "Software Engineer"]
    assert extract_cv_titles(HE_CV) == ["מנהלת חשבונות סוג 3", "מנהלת חשבונות", "מזכירה ואדמיניסטרציה"]
    assert extract_cv_titles(CUSTOM_CV) == ["רכזת פרט ותגמול", "Scrum Master", "מזכירה"]


def test_unknown_titles_become_roles_and_searches():
    from cv_samples import CUSTOM_CV

    p = extract_profile(CUSTOM_CV)
    assert p.roles[:2] == ["רכזת פרט ותגמול", "Scrum Master"]  # not in the dictionary, found anyway
    q = search_queries(p)
    assert q[:2] == ["רכזת פרט ותגמול", "Scrum Master"] and "Scrum" not in q
    # titles that are just known roles don't add duplicate tags
    assert extract_profile(EN_CV).roles == ["Backend Developer", "Software Engineer"]
    assert extract_profile(HE_CV).roles == ["Bookkeeper / Accountant", "Office / Administration"]


def test_jobs_with_own_title_always_show_and_score():
    from cv_samples import CUSTOM_CV
    from jobsearch_il.cv import missing_title, title_context

    p = extract_profile(CUSTOM_CV)
    ctx = title_context(CUSTOM_CV, p)
    assert missing_title(Job(source="t", title="רכז/ת פרט ותגמול לחברה מובילה", url="u"), ctx) is None
    assert missing_title(Job(source="t", title="Scrum Master - Fintech", url="u"), ctx) is None
    assert missing_title(Job(source="t", title="נהג/ת חלוקה", url="u"), ctx) == "נהג"
    score, matched = score_job(Job(source="t", title="רכז/ת פרט ותגמול", url="u", description="חילן, אקסל"), p)
    assert score >= 70 and "רכזת פרט ותגמול" in matched  # 1 of 2 skills (no Scrum in this job)


def test_valid_learned_role():
    from jobsearch_il.cv import valid_learned_role

    assert valid_learned_role("מתאם/ת פגישות") == "מתאם פגישות"
    assert valid_learned_role("מתאמת פגישות") == "מתאם פגישות"
    assert valid_learned_role("רכזת פרט ותגמול") == "רכז פרט ותגמול"
    assert valid_learned_role("Scrum Master") == "Scrum Master"
    for bad in ("מנהל", "Senior Manager", "Office / Administration", "<script>", "a", "x " * 10):
        assert valid_learned_role(bad) is None, bad


def test_user_added_roles_grow_the_shared_dictionary(db_url):
    class Src(Source):
        name = "fake"

        def search(self, criteria):
            yield Job(source="fake", title="מתאם/ת פגישות למוקד", url="https://f/1", description="אקסל")
            yield Job(source="fake", title="מנהלת חשבונות", url="https://f/2", description="חשבשבת")

    app = create_app(engine=JobSearchEngine({}, store=JobStore(db_url), sources={"fake": Src}))

    def user(email, cv_text):
        c = TestClient(app)
        c.post("/register", data={"email": email, "password": "password123", "password2": "password123"})
        c.post("/api/cv", files={"file": ("cv.txt", cv_text.encode(), "text/plain")})
        return c

    bookkeeper = user("bk@example.com", "רונית\nמנהלת חשבונות\n2019 - היום: מנהלת חשבונות, משרד\nחשבשבת, אקסל")
    bookkeeper.get("/api/search", params={"live": True, "q": "x"})

    def hidden_titles():
        r = bookkeeper.get("/api/search", params={"cv": True, "min_match": 0}).json()
        return [h["title"] for h in r["hidden"]]

    assert hidden_titles() == []  # nobody taught "מתאם פגישות" yet: unknown role, kept

    a = user("a@example.com", "דנה\nמזכירה\n2019 - היום: מזכירה, מוקד\nאקסל")
    cv = a.get("/api/cv").json()["cv"]
    a.put("/api/cv", json={"roles": cv["profile"]["roles"] + ["מתאמת פגישות"]})
    # a third user whose CV mentions it gets it detected automatically
    c = user("c@example.com", "יעל\nמוקדנית\nניסיון כמתאמת פגישות במוקד רפואי\nאקסל")
    prof = c.get("/api/cv").json()["cv"]["profile"]
    assert "מתאם פגישות" in prof["roles"] and prof["terms"]["מתאם פגישות"] == "מתאמת פגישות"
    assert hidden_titles() == []  # one user is not enough to hide jobs for others

    b = user("b@example.com", "גל לוי\nמוקדן\n2020 - היום: מוקדן, מוקד שירות\nאקסל")
    cv = b.get("/api/cv").json()["cv"]
    b.put("/api/cv", json={"roles": cv["profile"]["roles"] + ["מתאם/ת פגישות"]})  # same role, other gender
    assert hidden_titles() == ["מתאם/ת פגישות למוקד"]  # confirmed by 2 users: now a known role

    generic = user("g@example.com", "עמית כהן\nמחסנאי\n2020 - היום: מחסנאי, רשת אופנה\nאקסל")
    cv = generic.get("/api/cv").json()["cv"]
    generic.put("/api/cv", json={"roles": cv["profile"]["roles"] + ["מנהל"]})
    from jobsearch_il.auth import UserStore

    learned = UserStore(JobStore(db_url).engine).learned_roles()
    assert learned == {"מתאם פגישות": 2}  # one key for both genders; the generic "מנהל" was not learned
