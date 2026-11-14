"""Arabic interface: language choice, translated pages and messages, Arabic place names."""

import re

import pytest
from fastapi.testclient import TestClient

from jobsearch_il import auth
from jobsearch_il.engine import JobSearchEngine
from jobsearch_il.locations import location_matches
from jobsearch_il.models import Job, SearchCriteria
from jobsearch_il.sources.base import Source
from jobsearch_il.storage import JobStore
from jobsearch_il.web import i18n
from jobsearch_il.web.app import create_app

HEB = re.compile(r"[א-ת]")
ARAB = re.compile(r"[؀-ۿ]")


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    monkeypatch.setattr(auth, "_N", 2 ** 10)


class Src(Source):
    name = "fake"
    display_name = "Fake"

    def search(self, criteria):
        yield Job(source="fake", title="מנהלת חשבונות", url="https://f/1", location="נצרת", description="חשבשבת")
        yield Job(source="fake", title="מנהלת חשבונות", url="https://f/2", location="באר שבע", description="חשבשבת",
                  company="אחרת")


def client(db_url, **headers):
    return TestClient(create_app(engine=JobSearchEngine({}, store=JobStore(db_url), sources={"fake": Src})),
                      headers=headers)


def register(c):
    return c.post("/register", data={"email": "a@example.com", "password": "password123", "password2": "password123"})


def test_every_string_has_both_languages():
    for key, (he, ar) in i18n.STRINGS.items():
        assert he or key == "content_note", key
        assert ar, key
        # Arabic strings may quote Hebrew examples (job ads are in Hebrew), but must be written in Arabic
        if key not in ("exclude_words_ph", "include_ph", "exclude_ph"):
            assert ARAB.search(ar) or not re.search(r"[A-Za-zא-ת]{3}", ar), key
        assert set(re.findall(r"\{(\w+)\}", he)) == set(re.findall(r"\{(\w+)\}", ar)), key


def test_language_choice_order(db_url):
    c = client(db_url)
    assert 'lang="he"' in c.get("/login").text  # default
    ar_browser = client(db_url, **{"Accept-Language": "ar-IL,ar;q=0.9,he;q=0.8"})
    page = ar_browser.get("/login").text
    assert 'lang="ar"' in page and 'dir="rtl"' in page and "تسجيل الدخول" in page and "Noto+Sans+Arabic" in page
    # explicit switch wins and is remembered
    r = c.get("/lang/ar", params={"next": "/register"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/register" and r.cookies.get("lang") == "ar"
    assert "إنشاء حساب" in c.get("/register").text
    c.get("/lang/he")
    assert "יצירת חשבון" in c.get("/register").text
    # ?lang= in a link also works and is remembered
    assert "تسجيل الدخول" in c.get("/login", params={"lang": "ar"}).text
    assert "تسجيل الدخول" in c.get("/login").text
    # unsafe redirect targets are ignored
    assert c.get("/lang/ar", params={"next": "//evil.example"}, follow_redirects=False).headers["location"] == "/"
    assert c.get("/lang/xx").status_code == 404


def test_arabic_pages_have_no_hebrew_ui_text(db_url):
    c = client(db_url)
    c.get("/lang/ar")
    register(c)
    for path in ("/", "/settings"):
        html = c.get(path).text
        assert 'lang="ar"' in html
        visible = re.sub(r"<script>.*?</script>", "", html, flags=re.S)       # page script holds data, not UI text
        visible = re.sub(r'value="[^"]*"', "", visible)                         # option values the search understands
        visible = re.sub(r'placeholder="[^"]*"', "", visible)                   # Hebrew example words (ads are in Hebrew)
        visible = re.sub(r'<a class="langswitch"[^>]*>[^<]*</a>', "", visible)  # "עברית" is written in Hebrew
        assert not HEB.search(visible), [l for l in visible.splitlines() if HEB.search(l)][:5]
    boot = re.search(r"const BOOT = (\{.*?\});\n", c.get("/").text).group(1)
    assert '"lang": "ar"' in boot and '"البحث عن عمل في إسرائيل"' in boot and '"المركز"' in boot


def test_server_messages_are_translated(db_url):
    c = client(db_url)
    c.get("/lang/ar")
    assert "البريد الإلكتروني أو كلمة المرور غير صحيحة" in c.post("/login", data={"email": "x@y.co", "password": "x"}).text
    r = c.post("/register", data={"email": "a@example.com", "password": "short", "password2": "short"})
    assert "يجب أن تحتوي كلمة المرور على 8 أحرف على الأقل" in r.text
    assert c.get("/api/me").json()["detail"] == "يجب تسجيل الدخول"
    register(c)
    r = c.post("/api/cv", files={"file": ("cv.png", b"123", "image/png")})
    assert r.json()["detail"].startswith("نوع الملف غير مدعوم")
    c.get("/lang/he")
    r = c.post("/api/cv", files={"file": ("cv.png", b"123", "image/png")})
    assert r.json()["detail"].startswith("סוג קובץ לא נתמך")


def test_search_with_arabic_place_names(db_url):
    c = client(db_url)
    c.get("/lang/ar")
    register(c)
    c.get("/api/search", params={"live": True, "q": "מנהלת חשבונות"})
    for loc in ("الناصرة", "الشمال", "المركز، الشمال"):
        jobs = c.get("/api/search", params={"location": loc}).json()["jobs"]
        assert [j["location"] for j in jobs] == ["נצרת"], loc
    assert len(c.get("/api/search", params={"location": "الجنوب"}).json()["jobs"]) == 1


def test_arabic_place_names_and_arab_towns():
    assert location_matches("תל אביב יפו", ["تل ابيب"])          # spelling without hamza
    assert location_matches("סכנין", ["الشمال"])                   # Arab town inside its region
    assert location_matches("רהט", ["الجنوب"]) and location_matches("טייבה", ["الشارون"])
    assert location_matches("אום אל-פחם", ["أم الفحم"])
    assert not location_matches("באר שבע", ["المركز"])
    from jobsearch_il.filters import matches
    remote = Job(source="t", title="נציג שירות", url="u", location="באר שבע", description="עבודה מהבית")
    assert matches(remote, SearchCriteria(locations=["من البيت"]))
