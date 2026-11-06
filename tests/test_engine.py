from jobsearch_il.engine import JobSearchEngine
from jobsearch_il.models import Job, SearchCriteria
from jobsearch_il.sources.base import Source
from jobsearch_il.storage import JobStore


class FakeSource(Source):
    name = "fake"
    display_name = "Fake"
    calls: list = []

    def search(self, criteria):
        FakeSource.calls.append(criteria.query)
        yield Job(source="fake", title="Python Developer", url="https://f/1", company="A", location="Haifa")
        yield Job(source="fake", title="Java Developer", url="https://f/2", company="B", location="Tel Aviv")


class BrokenSource(Source):
    name = "broken"

    def search(self, criteria):
        raise RuntimeError("site down")
        yield


def make(tmp_path):
    return JobSearchEngine({}, store=JobStore(tmp_path / "t.db"), sources={"fake": FakeSource, "broken": BrokenSource})


def test_search_filters_stores_and_reports_errors(tmp_path):
    eng = make(tmp_path)
    res = eng.search(SearchCriteria(keywords=["python"], locations=["צפון"]))
    assert [j.title for j in res.jobs] == ["Python Developer"]
    assert len(res.new_jobs) == 1
    assert "broken" in res.errors
    # second run: nothing new
    res2 = eng.search(SearchCriteria(keywords=["python"]))
    assert res2.new_jobs == []
    # offline search over the DB
    assert len(eng.search_stored(SearchCriteria(keywords=["java"]))) == 1


def test_or_keywords_query_each(tmp_path):
    FakeSource.calls.clear()
    make(tmp_path).search(SearchCriteria(keywords=["python", "java"], sources=["fake"]))
    assert sorted(FakeSource.calls) == ["java", "python"]


def test_status(tmp_path):
    eng = make(tmp_path)
    res = eng.search(SearchCriteria(sources=["fake"]))
    uid = res.jobs[0].uid
    assert eng.store.set_status(uid, "hidden")
    assert uid not in {j.uid for j in eng.search_stored(SearchCriteria())}


def test_web(tmp_path):
    from fastapi.testclient import TestClient

    from jobsearch_il.web.app import create_app

    client = TestClient(create_app(engine=make(tmp_path)))
    r = client.get("/api/search", params={"live": True, "q": "python", "source": "fake"})
    assert r.status_code == 200 and r.json()["count"] == 1
    assert r.json()["jobs"][0]["is_new"] is True
    html = client.get("/").text
    assert 'dir="rtl"' in html and '"fake"' in html
    stored = client.get("/api/search", params={"q": "java"}).json()
    assert [j["title"] for j in stored["jobs"]] == ["Java Developer"]
    uid = r.json()["jobs"][0]["uid"]
    assert client.post(f"/api/jobs/{uid}/status/saved").json() == {"ok": True}
    saved = client.get("/api/search", params={"status": "saved"}).json()
    assert [j["uid"] for j in saved["jobs"]] == [uid]
    check = client.get("/api/check").json()
    assert check["fake"]["ok"] is True and check["broken"]["ok"] is False


class SnippetSource(Source):
    """Like JobMaster/LinkedIn: the site matched the keyword, but we only get a title."""
    name = "snippet"
    full_description = False

    def search(self, criteria):
        yield Job(source="snippet", title="Data Analyst", url="https://s/1", company="C", location="Tel Aviv")


def test_trusts_site_match_when_no_full_description(tmp_path):
    eng = JobSearchEngine({}, store=JobStore(tmp_path / "s.db"), sources={"snippet": SnippetSource})
    assert len(eng.search(SearchCriteria(keywords=["python"])).jobs) == 1
    assert eng.search(SearchCriteria(keywords=["python"], title_only=True)).jobs == []
    assert eng.search(SearchCriteria(keywords=["python"], exclude_keywords=["analyst"])).jobs == []
