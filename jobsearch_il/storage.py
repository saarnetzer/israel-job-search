"""Job storage: a shared cache of every job seen, plus per-user statuses (saved/applied/hidden)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import sqlalchemy as sa

from . import db
from .models import Job

STATUSES = ("new", "saved", "applied", "hidden")
LOCAL_USER = 0
"""Statuses set from the CLI belong to this pseudo-user."""


class JobStore:
    def __init__(self, url: str | Path = "jobs.db"):
        self.url = str(url)
        self.engine = db.make_engine(self.url)

    def upsert(self, jobs: Iterable[Job]) -> list[Job]:
        """Store jobs; returns the ones never seen before (by anyone)."""
        jobs = list({j.uid: j for j in jobs}.values())
        if not jobs:
            return []
        now = datetime.now()
        new: list[Job] = []
        with self.engine.begin() as conn:
            existing: set[str] = set()
            uids = [j.uid for j in jobs]
            for i in range(0, len(uids), 500):
                chunk = uids[i:i + 500]
                existing.update(r[0] for r in conn.execute(sa.select(db.jobs.c.uid).where(db.jobs.c.uid.in_(chunk))))
            if existing:
                conn.execute(db.jobs.update().where(db.jobs.c.uid.in_(existing)).values(last_seen=now))
            rows = []
            for j in jobs:
                if j.uid in existing:
                    continue
                rows.append(dict(
                    uid=j.uid, source=j.source, title=j.title, company=j.company, location=j.location,
                    description=j.description, url=j.url, posted_at=j.posted_at, salary=j.salary,
                    job_type=j.job_type, remote=j.remote, external_id=j.external_id,
                    extra=json.dumps(j.extra, ensure_ascii=False), first_seen=now, last_seen=now,
                ))
                new.append(j)
            if rows:
                conn.execute(db.jobs.insert(), rows)
        return new

    def all(self, sources: list[str] | None = None, include_hidden: bool = False,
            status: str | None = None, user_id: int = LOCAL_USER, seen_after: datetime | None = None) -> list[Job]:
        uj = db.user_jobs
        j = db.jobs
        q = (sa.select(j, uj.c.status)
             .select_from(j.outerjoin(uj, sa.and_(uj.c.job_uid == j.c.uid, uj.c.user_id == user_id))))
        if sources:
            q = q.where(j.c.source.in_(sources))
        if seen_after is not None:
            q = q.where(j.c.last_seen >= seen_after)
        if status:
            q = q.where(uj.c.status == status)
        elif not include_hidden:
            q = q.where(sa.or_(uj.c.status.is_(None), uj.c.status != "hidden"))
        q = q.order_by(sa.func.coalesce(j.c.posted_at, j.c.first_seen).desc())
        with self.engine.connect() as conn:
            return [self._row_to_job(r) for r in conn.execute(q).mappings()]

    def set_status(self, uid: str, status: str, user_id: int = LOCAL_USER) -> bool:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        with self.engine.begin() as conn:
            if not conn.execute(sa.select(db.jobs.c.uid).where(db.jobs.c.uid == uid)).first():
                return False
            conn.execute(db.user_jobs.delete().where(
                sa.and_(db.user_jobs.c.user_id == user_id, db.user_jobs.c.job_uid == uid)))
            if status != "new":
                conn.execute(db.user_jobs.insert().values(user_id=user_id, job_uid=uid, status=status,
                                                          updated_at=datetime.now()))
        return True

    def stats(self) -> dict[str, int]:
        q = sa.select(db.jobs.c.source, sa.func.count()).group_by(db.jobs.c.source)
        with self.engine.connect() as conn:
            return {s: c for s, c in conn.execute(q)}

    @staticmethod
    def _row_to_job(r) -> Job:
        extra = json.loads(r["extra"] or "{}")
        extra.update(status=r["status"] or "new", first_seen=r["first_seen"].isoformat(timespec="seconds"))
        return Job(
            source=r["source"], title=r["title"], url=r["url"], company=r["company"] or "",
            location=r["location"] or "", description=r["description"] or "", posted_at=r["posted_at"],
            salary=r["salary"] or "", job_type=r["job_type"] or "", remote=r["remote"],
            external_id=r["external_id"] or "", extra=extra,
        )

    def close(self) -> None:
        self.engine.dispose()
