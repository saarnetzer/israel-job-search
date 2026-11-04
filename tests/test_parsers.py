import json
from pathlib import Path

from jobsearch_il.sources.alljobs import parse_results as parse_alljobs
from jobsearch_il.sources.ats import parse_comeet, parse_greenhouse, parse_lever
from jobsearch_il.sources.base import parse_jsonld_jobs
from jobsearch_il.sources.drushim import parse_api
from jobsearch_il.sources.jobmaster import parse_results as parse_jobmaster
from jobsearch_il.sources.linkedin import parse_results as parse_linkedin

F = Path(__file__).parent / "fixtures"


def test_alljobs():
    jobs = parse_alljobs((F / "alljobs.html").read_text(encoding="utf-8"))
    assert len(jobs) == 2
    j = jobs[0]
    assert j.title == "מפתח/ת Python לצוות Backend"
    assert j.company == 'טכנולוגיות בע"מ'
    assert j.location == "תל אביב"
    assert j.external_id == "8123456"
    assert j.url.startswith("https://www.alljobs.co.il/Search/UploadSingle.aspx?JobID=8123456")
    assert j.posted_at is not None
    assert jobs[1].posted_at.day == 12


def test_jobmaster():
    jobs = parse_jobmaster((F / "jobmaster.html").read_text(encoding="utf-8"))
    assert [j.title for j in jobs] == ["DevOps Engineer", "נציג/ת שירות לקוחות - עבודה מהבית"]
    assert jobs[0].company == "CloudCo"
    assert jobs[0].location == "פתח תקווה"
    assert jobs[0].external_id == "1234567"


def test_linkedin():
    [j] = parse_linkedin((F / "linkedin.html").read_text(encoding="utf-8"))
    assert j.title == "Backend Engineer"
    assert j.company == "Acme Israel"
    assert j.external_id == "4012345678"
    assert "?" not in j.url
    assert j.posted_at.year == 2026


def test_drushim():
    [j] = parse_api(json.loads((F / "drushim.json").read_text(encoding="utf-8")))
    assert j.title == "אנליסט/ית נתונים"
    assert j.company == "בנק הדוגמה"
    assert j.location == "רמת גן"
    assert j.url == "https://www.drushim.co.il/job/55501/abc/"
    assert "SQL" in j.description and "<p>" not in j.description


def test_jsonld():
    [j] = parse_jsonld_jobs((F / "careers_jsonld.html").read_text(encoding="utf-8"), "careers", "https://startupx.com/jobs")
    assert j.title == "Frontend Developer (React)"
    assert j.company == "StartupX"
    assert "Herzliya" in j.location
    assert j.url == "https://startupx.com/careers/frontend"


def test_ats_parsers():
    gh = parse_greenhouse({"jobs": [{"id": 1, "title": "SRE", "absolute_url": "https://x/1",
                                     "location": {"name": "Tel Aviv, Israel"}, "content": "&lt;p&gt;k8s&lt;/p&gt;",
                                     "first_published": "2026-11-01T00:00:00Z"}]}, "acme")
    assert gh[0].description == "k8s" and gh[0].company == "acme"
    lv = parse_lever([{"id": "a", "text": "QA", "hostedUrl": "https://l/a", "createdAt": 1793000000000,
                       "categories": {"location": "Haifa", "commitment": "Full-time"}}], "beta")
    assert lv[0].location == "Haifa" and lv[0].posted_at is not None
    cm = parse_comeet([{"uid": "1A", "name": "PM", "url_active_page": "https://c/1A",
                        "location": {"city": "Tel Aviv", "country": "IL"}, "details": [{"value": "<b>Lead</b>"}]}], "Gamma")
    assert cm[0].location == "Tel Aviv, IL" and cm[0].description == "Lead"
