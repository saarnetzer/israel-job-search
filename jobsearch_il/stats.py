"""Usage statistics for the admin page.

Events record only when something happened, its kind, the search mode and the UI language,
never what was searched or the contents of a CV.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import sqlalchemy as sa

from . import db

log = logging.getLogger(__name__)
KINDS = ("signup", "login", "search", "cv_upload")


def record_event(engine: sa.Engine, kind: str, user_id: int | None = None, mode: str | None = None,
                 lang: str | None = None) -> None:
    """Never let statistics break the action being counted."""
    try:
        with engine.begin() as conn:
            conn.execute(db.events.insert().values(ts=datetime.now(), user_id=user_id, kind=kind, mode=mode,
                                                   lang=lang))
    except Exception as e:  # pragma: no cover - defensive
        log.warning("could not record %s event: %s", kind, e)


def _day(v: Any) -> str:
    return v.isoformat() if isinstance(v, (date, datetime)) else str(v)[:10]


def admin_stats(engine: sa.Engine, days: int = 30, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    d7, d30, since = now - timedelta(days=7), now - timedelta(days=30), now - timedelta(days=days)
    u, e, s = db.users, db.events, db.sessions
    count = lambda q: conn.execute(q).scalar() or 0  # noqa: E731

    with engine.connect() as conn:
        def active_since(t: datetime) -> int:
            """Users who searched since t: from the event log, or (for searches before it existed) last_search_at."""
            from_events = sa.select(e.c.user_id).where(e.c.kind == "search", e.c.ts >= t, e.c.user_id.is_not(None))
            from_users = sa.select(u.c.id).where(u.c.last_search_at >= t)
            return count(sa.select(sa.func.count()).select_from(sa.union(from_events, from_users).subquery()))

        totals = {
            "registered": count(sa.select(sa.func.count()).select_from(u)),
            "new_7d": count(sa.select(sa.func.count()).select_from(u).where(u.c.created_at >= d7)),
            "new_30d": count(sa.select(sa.func.count()).select_from(u).where(u.c.created_at >= d30)),
            "active_7d": active_since(d7),
            "active_30d": active_since(d30),
            "logged_in": count(sa.select(sa.func.count(sa.distinct(s.c.user_id))).where(s.c.expires_at > now)),
            "cvs": count(sa.select(sa.func.count()).select_from(db.cvs)),
            "saved_searches": count(sa.select(sa.func.count()).select_from(db.saved_searches)),
            "searches_7d": count(sa.select(sa.func.count()).select_from(e).where(e.c.kind == "search", e.c.ts >= d7)),
            "searches_30d": count(sa.select(sa.func.count()).select_from(e).where(e.c.kind == "search", e.c.ts >= d30)),
            "jobs_in_db": count(sa.select(sa.func.count()).select_from(db.jobs)),
            "learned_roles": count(sa.select(sa.func.count()).select_from(db.learned_roles)),
        }

        # per day: sign-ups (from users, so it covers people who joined before the log existed) and activity
        daily: dict[str, dict[str, int]] = {}
        for d in range(days):
            key = (now - timedelta(days=d)).date().isoformat()
            daily[key] = {"signups": 0, "searches": 0, "searchers": 0, "logins": 0, "cv_uploads": 0}
        q = (sa.select(sa.func.date(u.c.created_at), sa.func.count()).where(u.c.created_at >= since)
             .group_by(sa.func.date(u.c.created_at)))
        for day, n in conn.execute(q):
            if _day(day) in daily:
                daily[_day(day)]["signups"] = n
        q = (sa.select(sa.func.date(e.c.ts), e.c.kind, sa.func.count(), sa.func.count(sa.distinct(e.c.user_id)))
             .where(e.c.ts >= since).group_by(sa.func.date(e.c.ts), e.c.kind))
        for day, kind, n, people in conn.execute(q):
            row = daily.get(_day(day))
            if row is None:
                continue
            if kind == "search":
                row["searches"], row["searchers"] = n, people
            elif kind == "login":
                row["logins"] = n
            elif kind == "cv_upload":
                row["cv_uploads"] = n

        def split(column) -> dict[str, int]:
            q = (sa.select(column, sa.func.count()).where(e.c.kind == "search", e.c.ts >= d30).group_by(column))
            return {str(k or "?"): n for k, n in conn.execute(q)}

        by_lang_users = {str(k or "?"): n for k, n in conn.execute(
            sa.select(e.c.lang, sa.func.count(sa.distinct(e.c.user_id)))
            .where(e.c.ts >= d30, e.c.user_id.is_not(None)).group_by(e.c.lang))}

        # people: newest first
        searches = (sa.select(e.c.user_id, sa.func.count().label("n")).where(e.c.kind == "search")
                    .group_by(e.c.user_id).subquery())
        saved = (sa.select(db.saved_searches.c.user_id, sa.func.count().label("n"))
                 .group_by(db.saved_searches.c.user_id).subquery())
        q = (sa.select(u.c.id, u.c.email, u.c.first_name, u.c.last_name, u.c.created_at, u.c.last_search_at, searches.c.n.label("searches"),
                       saved.c.n.label("saved"), db.cvs.c.user_id.label("has_cv"))
             .select_from(u.outerjoin(searches, searches.c.user_id == u.c.id)
                          .outerjoin(saved, saved.c.user_id == u.c.id)
                          .outerjoin(db.cvs, db.cvs.c.user_id == u.c.id))
             .order_by(u.c.created_at.desc()).limit(500))
        people = [{"id": r.id, "email": r.email, "first_name": r.first_name or "", "last_name": r.last_name or "",
                   "created_at": r.created_at.isoformat(timespec="minutes"),
                   "last_search_at": r.last_search_at.isoformat(timespec="minutes") if r.last_search_at else None,
                   "searches": r.searches or 0, "saved_searches": r.saved or 0, "has_cv": r.has_cv is not None}
                  for r in conn.execute(q)]

        log_started = conn.execute(sa.select(sa.func.min(e.c.ts))).scalar()
        by_mode, by_lang = split(e.c.mode), split(e.c.lang)

    return {
        "generated_at": now.isoformat(timespec="minutes"),
        "log_started": log_started.isoformat(timespec="minutes") if log_started else None,
        "totals": totals,
        "daily": [{"day": k, **v} for k, v in sorted(daily.items(), reverse=True)],
        "searches_by_mode": by_mode,
        "searches_by_lang": by_lang,
        "users_by_lang": by_lang_users,
        "users": people,
    }
