import os

import pytest


@pytest.fixture(params=["sqlite"] + (["postgres"] if os.environ.get("TEST_DATABASE_URL") else []))
def db_url(request, tmp_path):
    """Run DB tests on SQLite, and also on Postgres when TEST_DATABASE_URL is set."""
    if request.param == "sqlite":
        return str(tmp_path / "t.db")
    import sqlalchemy as sa

    from jobsearch_il import db

    url = os.environ["TEST_DATABASE_URL"]
    eng = db.make_engine(url)
    with eng.begin() as conn:
        for t in reversed(db.metadata.sorted_tables):
            conn.execute(t.delete())
    eng.dispose()
    return url
