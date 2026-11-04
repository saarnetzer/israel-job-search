from datetime import datetime, timedelta

from jobsearch_il.filters import dedupe, matches
from jobsearch_il.locations import expand_location, is_israel_location, location_matches
from jobsearch_il.models import Job, SearchCriteria
from jobsearch_il.textutil import keyword_in, parse_date, parse_salary, required_experience

NOW = datetime(2026, 11, 4, 12, 0)


def job(**kw):
    base = dict(source="t", title="Python Developer", url="https://x/1", company="Acme", location="תל אביב",
                description="", posted_at=NOW - timedelta(days=1))
    base.update(kw)
    return Job(**base)


def test_hebrew_prefixes_and_synonyms():
    assert keyword_in("דרוש/ה למפתח בכיר", "מפתח")
    assert keyword_in("Senior Python developer", "פייתון")
    assert keyword_in("מתכנת/ת פייתון", "python")
    assert not keyword_in("javascript developer", "java")
    assert keyword_in("Full-Stack engineer", "fullstack")


def test_locations():
    assert location_matches("Tel Aviv-Yafo, Israel", ["תל אביב"])
    assert location_matches("פתח תקווה", ["מרכז"])
    assert location_matches("Haifa", ["צפון"])
    assert not location_matches("באר שבע", ["center"])
    assert "באר שבע" in expand_location("south")
    assert is_israel_location("Herzliya")
    assert not is_israel_location("London, UK")
    assert not location_matches("Yamit", ["ים"])  # short alias must be a whole word


def test_criteria_basic():
    j = job(description="3 years experience, Django")
    assert matches(j, SearchCriteria(keywords=["python"]), NOW)
    assert not matches(j, SearchCriteria(keywords=["java"]), NOW)
    assert matches(j, SearchCriteria(keywords=["python", "java"]), NOW)
    assert not matches(j, SearchCriteria(keywords=["python", "java"], match_all=True), NOW)
    assert not matches(j, SearchCriteria(exclude_keywords=["django"]), NOW)
    assert matches(j, SearchCriteria(locations=["מרכז"]), NOW)
    assert not matches(j, SearchCriteria(locations=["חיפה"]), NOW)
    assert not matches(j, SearchCriteria(max_experience_years=2), NOW)
    assert matches(j, SearchCriteria(max_experience_years=3), NOW)
    assert not matches(job(posted_at=NOW - timedelta(days=10)), SearchCriteria(posted_within_days=7), NOW)
    assert not matches(j, SearchCriteria(exclude_companies=["acme"]), NOW)


def test_remote_and_types():
    r = job(title="נציג שירות", location="באר שבע", description="עבודה מהבית", job_type="משמרות")
    assert matches(r, SearchCriteria(remote_only=True), NOW)
    assert matches(r, SearchCriteria(locations=["מרכז", "remote"]), NOW)
    assert not matches(job(), SearchCriteria(remote_only=True), NOW)
    assert matches(r, SearchCriteria(job_types=["shifts"]), NOW)
    assert not matches(r, SearchCriteria(job_types=["student"]), NOW)


def test_salary():
    assert parse_salary('שכר 12,000 ש"ח') == 12000
    assert parse_salary("45 ש\"ח לשעה") == 45 * 186
    assert parse_salary("15K NIS") == 15000
    assert parse_salary("3 years experience") is None
    assert not matches(job(description='שכר 9,000 ש"ח'), SearchCriteria(min_salary=10000), NOW)
    assert matches(job(description="no salary"), SearchCriteria(min_salary=10000), NOW)


def test_experience():
    assert required_experience("3+ years of experience") == 3
    assert required_experience("לפחות 4 שנות ניסיון") == 4
    assert required_experience("ניסיון של שנתיים") == 2
    assert required_experience("ללא ניסיון") == 0
    assert required_experience("Great team") is None


def test_dates():
    assert parse_date("לפני 3 ימים", NOW) == NOW - timedelta(days=3)
    assert parse_date("היום", NOW) == NOW
    assert parse_date("5 hours ago", NOW) == NOW - timedelta(hours=5)
    assert parse_date("04/11/2026") == datetime(2026, 11, 4)
    assert parse_date("2026-11-01T10:00:00Z") == datetime(2026, 11, 1, 10)


def test_dedupe_cross_site():
    a = job(source="alljobs", url="https://a/1")
    b = job(source="drushim", url="https://b/1", title="Python  Developer")
    out = dedupe([a, b, a])
    assert len(out) == 1
    assert out[0].extra["also_on"][0]["source"] == "drushim"
