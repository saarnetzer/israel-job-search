"""SQLite storage: keeps every job seen, so you can search offline and get only *new* jobs."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import Job

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    uid TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    description TEXT,
    url TEXT NOT NULL,
    posted_at TEXT,
    salary TEXT,
    job_type TEXT,
    remote INTEGER,
    external_id TEXT,
    extra TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    status TEXT DEFAULT 'new'  -- new / saved / applied / hidden
);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
"""

STATUSES = ("new", "saved", "applied", "hidden")


class JobStore:
    def __init__(self, path: str | Path = "jobs.db"):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def upsert(self, jobs: Iterable[Job]) -> list[Job]:
        """Store jobs; returns the ones never seen before."""
        now = datetime.now().isoformat(timespec="seconds")
        new: list[Job] = []
        with self.conn:
            for j in jobs:
                cur = self.conn.execute("UPDATE jobs SET last_seen=? WHERE uid=?", (now, j.uid))
                if cur.rowcount:
                    continue
                self.conn.execute(
                    "INSERT INTO jobs (uid, source, title, company, location, description, url, posted_at, salary,"
                    " job_type, remote, external_id, extra, first_seen, last_seen)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (j.uid, j.source, j.title, j.company, j.location, j.description, j.url,
                     j.posted_at.isoformat() if j.posted_at else None, j.salary, j.job_type,
                     None if j.remote is None else int(j.remote), j.external_id,
                     json.dumps(j.extra, ensure_ascii=False), now, now),
                )
                new.append(j)
        return new

    def all(self, sources: list[str] | None = None, include_hidden: bool = False,
            status: str | None = None) -> list[Job]:
        sql, args = "SELECT * FROM jobs WHERE 1=1", []
        if sources:
            sql += f" AND source IN ({','.join('?' * len(sources))})"
            args += sources
        if status:
            sql += " AND status = ?"
            args.append(status)
        elif not include_hidden:
            sql += " AND status != 'hidden'"
        sql += " ORDER BY COALESCE(posted_at, first_seen) DESC"
        return [self._row_to_job(r) for r in self.conn.execute(sql, args)]

    def set_status(self, uid: str, status: str) -> bool:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        with self.conn:
            return self.conn.execute("UPDATE jobs SET status=? WHERE uid=?", (status, uid)).rowcount > 0

    def stats(self) -> dict[str, int]:
        rows = self.conn.execute("SELECT source, COUNT(*) c FROM jobs GROUP BY source").fetchall()
        return {r["source"]: r["c"] for r in rows}

    @staticmethod
    def _row_to_job(r: sqlite3.Row) -> Job:
        extra = json.loads(r["extra"] or "{}")
        extra.update(status=r["status"], first_seen=r["first_seen"])
        return Job(
            source=r["source"], title=r["title"], url=r["url"], company=r["company"] or "",
            location=r["location"] or "", description=r["description"] or "",
            posted_at=datetime.fromisoformat(r["posted_at"]) if r["posted_at"] else None,
            salary=r["salary"] or "", job_type=r["job_type"] or "",
            remote=None if r["remote"] is None else bool(r["remote"]),
            external_id=r["external_id"] or "", extra=extra,
        )

    def close(self) -> None:
        self.conn.close()
