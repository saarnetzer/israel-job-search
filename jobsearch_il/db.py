"""Database schema (SQLAlchemy Core). SQLite locally, PostgreSQL in production (DATABASE_URL)."""

from __future__ import annotations

import sqlalchemy as sa

metadata = sa.MetaData()

jobs = sa.Table(
    "jobs", metadata,
    sa.Column("uid", sa.String(16), primary_key=True),
    sa.Column("source", sa.String(32), nullable=False, index=True),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("company", sa.Text, default=""),
    sa.Column("location", sa.Text, default=""),
    sa.Column("description", sa.Text, default=""),
    sa.Column("url", sa.Text, nullable=False),
    sa.Column("posted_at", sa.DateTime, nullable=True),
    sa.Column("salary", sa.Text, default=""),
    sa.Column("job_type", sa.Text, default=""),
    sa.Column("remote", sa.Boolean, nullable=True),
    sa.Column("external_id", sa.String(64), default=""),
    sa.Column("extra", sa.Text, default="{}"),
    sa.Column("first_seen", sa.DateTime, nullable=False, index=True),
    sa.Column("last_seen", sa.DateTime, nullable=False),
)

users = sa.Table(
    "users", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("email", sa.String(254), nullable=False, unique=True),
    sa.Column("password_hash", sa.Text, nullable=False),
    sa.Column("settings", sa.Text, nullable=False, default="{}"),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Column("last_search_at", sa.DateTime, nullable=True),
)

sessions = sa.Table(
    "sessions", metadata,
    sa.Column("token_hash", sa.String(64), primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Column("expires_at", sa.DateTime, nullable=False),
)

user_jobs = sa.Table(
    "user_jobs", metadata,
    sa.Column("user_id", sa.Integer, primary_key=True),
    sa.Column("job_uid", sa.String(16), primary_key=True),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("updated_at", sa.DateTime, nullable=False),
)

saved_searches = sa.Table(
    "saved_searches", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("name", sa.String(100), nullable=False),
    sa.Column("params", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.UniqueConstraint("user_id", "name"),
)

cvs = sa.Table(
    "cvs", metadata,
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("filename", sa.String(255), nullable=False),
    sa.Column("text", sa.Text, nullable=False),
    sa.Column("profile", sa.Text, nullable=False),
    sa.Column("uploaded_at", sa.DateTime, nullable=False),
)

# roles users added by hand, shared by everyone so the role dictionary grows
learned_roles = sa.Table(
    "learned_roles", metadata,
    sa.Column("term", sa.String(80), primary_key=True),
    sa.Column("created_at", sa.DateTime, nullable=False),
)

learned_role_users = sa.Table(
    "learned_role_users", metadata,
    sa.Column("term", sa.String(80), primary_key=True),
    sa.Column("user_id", sa.Integer, primary_key=True),
    sa.Column("created_at", sa.DateTime, nullable=False),
)


def make_engine(url: str) -> sa.Engine:
    """Accept a file path, sqlite:// URL, or postgres(ql):// URL (Neon/Render style)."""
    if "://" not in url:
        url = f"sqlite:///{url}"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    kw: dict = {"future": True}
    if url.startswith("sqlite"):
        kw["connect_args"] = {"check_same_thread": False}
    else:
        kw.update(pool_pre_ping=True, pool_recycle=300)  # Neon suspends idle connections
    engine = sa.create_engine(url, **kw)
    if url.startswith("sqlite"):
        @sa.event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # pragma: no cover - trivial
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    metadata.create_all(engine)
    return engine
