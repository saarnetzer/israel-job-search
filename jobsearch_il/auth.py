"""User accounts: email + password registration, sessions, settings and saved searches."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from datetime import datetime, timedelta
from typing import Any

import sqlalchemy as sa

from . import db

SESSION_DAYS = 30
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8

# scrypt parameters (OWASP recommendation: N=2^17, r=8, p=1)
_N, _R, _P = 2 ** 17, 8, 1


class AuthError(Exception):
    """User-facing error (message is shown in Hebrew)."""


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, maxmem=256 * 1024 * 1024, dklen=32)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_N}${_R}${_P}${b64(salt)}${b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                             maxmem=256 * 1024 * 1024, dklen=32)
        return hmac.compare_digest(got, base64.b64decode(dk))
    except (ValueError, TypeError):
        return False


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_password(password: str) -> None:
    if len(password or "") < MIN_PASSWORD:
        raise AuthError(f"הסיסמה צריכה להכיל לפחות {MIN_PASSWORD} תווים")
    if len(password) > 256:
        raise AuthError("הסיסמה ארוכה מדי")


class RateLimiter:
    """Slows down password guessing: max `limit` failures per key per `window` seconds."""

    def __init__(self, limit: int = 5, window: int = 900):
        self.limit, self.window = limit, window
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def blocked(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            fails = [t for t in self._fails.get(key, []) if now - t < self.window]
            self._fails[key] = fails
            return len(fails) >= self.limit

    def fail(self, key: str) -> None:
        with self._lock:
            self._fails.setdefault(key, []).append(time.time())

    def reset(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)


class UserStore:
    def __init__(self, engine: sa.Engine):
        self.engine = engine

    # ------------------------------------------------------------ accounts
    def register(self, email: str, password: str) -> int:
        email = normalize_email(email)
        if not EMAIL_RE.match(email) or len(email) > 254:
            raise AuthError("כתובת אימייל לא תקינה")
        validate_password(password)
        with self.engine.begin() as conn:
            if conn.execute(sa.select(db.users.c.id).where(db.users.c.email == email)).first():
                raise AuthError("כבר קיים חשבון עם האימייל הזה")
            res = conn.execute(db.users.insert().values(
                email=email, password_hash=hash_password(password), settings="{}", created_at=datetime.now()))
            return int(res.inserted_primary_key[0])

    def authenticate(self, email: str, password: str) -> int | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(db.users.c.id, db.users.c.password_hash)
                               .where(db.users.c.email == normalize_email(email))).first()
        if row is None:
            verify_password(password, hash_password("timing-equalizer"))  # don't reveal which emails exist
            return None
        return row.id if verify_password(password, row.password_hash) else None

    def get(self, user_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(db.users).where(db.users.c.id == user_id)).mappings().first()
        if row is None:
            return None
        return {"id": row["id"], "email": row["email"], "settings": json.loads(row["settings"] or "{}"),
                "created_at": row["created_at"], "last_search_at": row["last_search_at"]}

    def change_password(self, user_id: int, current: str, new: str) -> None:
        with self.engine.connect() as conn:
            stored = conn.execute(sa.select(db.users.c.password_hash).where(db.users.c.id == user_id)).scalar()
        if not stored or not verify_password(current, stored):
            raise AuthError("הסיסמה הנוכחית שגויה")
        validate_password(new)
        with self.engine.begin() as conn:
            conn.execute(db.users.update().where(db.users.c.id == user_id).values(password_hash=hash_password(new)))

    def delete(self, user_id: int) -> None:
        with self.engine.begin() as conn:
            for t in (db.sessions, db.saved_searches, db.user_jobs, db.cvs, db.learned_role_users):
                conn.execute(t.delete().where(t.c.user_id == user_id))
            conn.execute(db.users.delete().where(db.users.c.id == user_id))

    def update_settings(self, user_id: int, settings: dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            conn.execute(db.users.update().where(db.users.c.id == user_id)
                         .values(settings=json.dumps(settings, ensure_ascii=False)))

    def mark_searched(self, user_id: int) -> datetime | None:
        """Record a live search; returns the previous search time (for per-user "new" badges)."""
        now = datetime.now()
        with self.engine.begin() as conn:
            prev = conn.execute(sa.select(db.users.c.last_search_at).where(db.users.c.id == user_id)).scalar()
            conn.execute(db.users.update().where(db.users.c.id == user_id).values(last_search_at=now))
        return prev

    # ------------------------------------------------------------ sessions
    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now()
        with self.engine.begin() as conn:
            conn.execute(db.sessions.delete().where(db.sessions.c.expires_at < now))
            conn.execute(db.sessions.insert().values(token_hash=self._hash_token(token), user_id=user_id,
                                                     created_at=now, expires_at=now + timedelta(days=SESSION_DAYS)))
        return token

    def user_for_session(self, token: str | None) -> int | None:
        if not token:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(db.sessions.c.user_id, db.sessions.c.expires_at)
                               .where(db.sessions.c.token_hash == self._hash_token(token))).first()
        if row is None or row.expires_at < datetime.now():
            return None
        return row.user_id

    def end_session(self, token: str | None) -> None:
        if token:
            with self.engine.begin() as conn:
                conn.execute(db.sessions.delete().where(db.sessions.c.token_hash == self._hash_token(token)))

    def end_all_sessions(self, user_id: int, keep: str | None = None) -> None:
        q = db.sessions.delete().where(db.sessions.c.user_id == user_id)
        if keep:
            q = q.where(db.sessions.c.token_hash != self._hash_token(keep))
        with self.engine.begin() as conn:
            conn.execute(q)

    # ------------------------------------------------------------ saved searches
    def list_searches(self, user_id: int) -> list[dict[str, Any]]:
        q = sa.select(db.saved_searches).where(db.saved_searches.c.user_id == user_id).order_by(db.saved_searches.c.name)
        with self.engine.connect() as conn:
            return [{"id": r["id"], "name": r["name"], "params": json.loads(r["params"])}
                    for r in conn.execute(q).mappings()]

    def save_search(self, user_id: int, name: str, params: dict[str, Any]) -> int:
        name = (name or "").strip()[:100]
        if not name:
            raise AuthError("צריך לתת שם לחיפוש")
        data = json.dumps(params, ensure_ascii=False)
        t = db.saved_searches
        with self.engine.begin() as conn:
            existing = conn.execute(sa.select(t.c.id).where(sa.and_(t.c.user_id == user_id, t.c.name == name))).scalar()
            if existing:
                conn.execute(t.update().where(t.c.id == existing).values(params=data))
                return int(existing)
            res = conn.execute(t.insert().values(user_id=user_id, name=name, params=data, created_at=datetime.now()))
            return int(res.inserted_primary_key[0])

    def delete_search(self, user_id: int, search_id: int) -> bool:
        t = db.saved_searches
        with self.engine.begin() as conn:
            return conn.execute(t.delete().where(sa.and_(t.c.id == search_id, t.c.user_id == user_id))).rowcount > 0

    # ------------------------------------------------------------ CV
    def get_cv(self, user_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            r = conn.execute(sa.select(db.cvs).where(db.cvs.c.user_id == user_id)).mappings().first()
        if r is None:
            return None
        return {"filename": r["filename"], "text": r["text"], "profile": json.loads(r["profile"]),
                "uploaded_at": r["uploaded_at"]}

    def save_cv(self, user_id: int, filename: str, text: str, profile: dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            conn.execute(db.cvs.delete().where(db.cvs.c.user_id == user_id))
            conn.execute(db.cvs.insert().values(user_id=user_id, filename=filename[:255], text=text,
                                                profile=json.dumps(profile, ensure_ascii=False),
                                                uploaded_at=datetime.now()))

    def update_cv_profile(self, user_id: int, profile: dict[str, Any]) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(db.cvs.update().where(db.cvs.c.user_id == user_id)
                                .values(profile=json.dumps(profile, ensure_ascii=False))).rowcount > 0

    def delete_cv(self, user_id: int) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(db.cvs.delete().where(db.cvs.c.user_id == user_id)).rowcount > 0

    # ------------------------------------------------------------ shared role dictionary
    def learn_roles(self, user_id: int, terms: list[str]) -> None:
        now = datetime.now()
        with self.engine.begin() as conn:
            for term in terms:
                key = term[:80]
                if not conn.execute(sa.select(db.learned_roles.c.term).where(db.learned_roles.c.term == key)).first():
                    conn.execute(db.learned_roles.insert().values(term=key, created_at=now))
                exists = conn.execute(sa.select(db.learned_role_users.c.term).where(sa.and_(
                    db.learned_role_users.c.term == key, db.learned_role_users.c.user_id == user_id))).first()
                if not exists:
                    conn.execute(db.learned_role_users.insert().values(term=key, user_id=user_id, created_at=now))

    def learned_roles(self) -> dict[str, int]:
        """term -> number of different users who added it."""
        q = (sa.select(db.learned_roles.c.term, sa.func.count(db.learned_role_users.c.user_id))
             .select_from(db.learned_roles.outerjoin(db.learned_role_users,
                                                     db.learned_role_users.c.term == db.learned_roles.c.term))
             .group_by(db.learned_roles.c.term))
        with self.engine.connect() as conn:
            return {t: n for t, n in conn.execute(q)}
