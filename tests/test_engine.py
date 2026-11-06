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
    return JobSearchEngine({}, store=JobStore(str(tmp_path / "t.db")), sources={"fake": FakeSource, "broken": BrokenSource})


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


class SnippetSource(Source):
    """Like JobMaster/LinkedIn: the site matched the keyword, but we only get a title."""
    name = "snippet"
    full_description = False

    def search(self, criteria):
        yield Job(source="snippet", title="Data Analyst", url="https://s/1", company="C", location="Tel Aviv")


def test_trusts_site_match_when_no_full_description(tmp_path):
    eng = JobSearchEngine({}, store=JobStore(str(tmp_path / "s.db")), sources={"snippet": SnippetSource})
    assert len(eng.search(SearchCriteria(keywords=["python"])).jobs) == 1
    assert eng.search(SearchCriteria(keywords=["python"], title_only=True)).jobs == []
    assert eng.search(SearchCriteria(keywords=["python"], exclude_keywords=["analyst"])).jobs == []


def test_stored_search_scoped_to_this_scan(tmp_path):
    import time as _time
    from datetime import datetime, timedelta

    eng = make(tmp_path)
    eng.search(SearchCriteria(sources=["fake"]))  # an earlier scan: 2 jobs stored
    eng.store.upsert([Job(source="fake", title="Old Python job", url="https://f/old", company="Z")])
    _time.sleep(1.1)
    start = datetime.now() - timedelta(seconds=0.5)
    eng.search(SearchCriteria(sources=["fake"]))  # this scan touches only the 2 fake jobs
    everything = eng.search_stored(SearchCriteria(keywords=["python"]))
    scoped = eng.search_stored(SearchCriteria(keywords=["python"]), seen_after=start)
    assert {j.title for j in everything} == {"Python Developer", "Old Python job"}
    assert [j.title for j in scoped] == ["Python Developer"]


def test_time_budget_and_partial_failures(tmp_path):
    import time as _time

    calls = []

    class Slow(Source):
        name = "slow"

        def search(self, criteria):
            calls.append(criteria.query)
            if criteria.query == "bad":
                raise RuntimeError("blocked")
            _time.sleep(0.3)
            yield Job(source="slow", title=f"{criteria.query} job", url=f"https://s/{criteria.query}")

    eng = JobSearchEngine({}, store=JobStore(str(tmp_path / "b.db")), sources={"slow": Slow})
    # one failing query doesn't lose the others
    res = eng.search(SearchCriteria(keywords=["a", "bad", "b"]))
    assert {j.title for j in res.jobs} == {"a job", "b job"} and res.errors == {}
    # after the budget no more queries start
    calls.clear()
    res = eng.search(SearchCriteria(keywords=["q1", "q2", "q3", "q4", "q5"]), budget_s=0.5)
    assert 1 <= len(calls) < 5 and res.jobs
    # all queries failing is reported as an error
    res = eng.search(SearchCriteria(keywords=["bad"]))
    assert "slow" in res.errors
