"""Command line interface.

Examples:
    jobsearch-il search -k python -k backend -l מרכז --days 7
    jobsearch-il search -k "מנהלת חשבונות" -l חיפה --type "חלקית" --format csv -o jobs.csv
    jobsearch-il saved            # run the saved searches from config.yaml, print only new jobs
    jobsearch-il db -k devops     # search the local database offline
    jobsearch-il serve            # web UI on http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__
from .config import criteria_from_dict, load_config
from .engine import JobSearchEngine
from .models import SearchCriteria
from .output import render
from .sources import SOURCES
from .storage import JobStore


def _split(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for v in values or []:
        out.extend(x.strip() for x in v.split(",") if x.strip())
    return out


def add_criteria_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("קריטריונים לחיפוש / search criteria")
    g.add_argument("-k", "--keyword", action="append", help="מילת חיפוש (אפשר כמה פעמים)")
    g.add_argument("--all", dest="match_all", action="store_true", help="כל המילים חייבות להופיע (ברירת מחדל: אחת מהן)")
    g.add_argument("--title-only", action="store_true", help="חיפוש מילים בכותרת המשרה בלבד")
    g.add_argument("-x", "--exclude", action="append", help="מילים לפסילה, למשל senior")
    g.add_argument("-l", "--location", action="append", help="עיר או אזור: 'תל אביב', 'מרכז', 'צפון', 'Haifa'")
    g.add_argument("--remote", action="store_true", help="רק עבודה מהבית / היברידי")
    g.add_argument("-t", "--type", dest="job_types", action="append", help="היקף: מלאה / חלקית / סטודנט / משמרות / פרילנס")
    g.add_argument("-c", "--company", action="append", help="רק חברות מסוימות")
    g.add_argument("--exclude-company", action="append", help="פסילת חברות (למשל חברות השמה)")
    g.add_argument("-d", "--days", type=int, help="פורסם ב-X הימים האחרונים")
    g.add_argument("--min-salary", type=int, help="שכר חודשי מינימלי בש\"ח (משרות בלי שכר מפורסם נשארות)")
    g.add_argument("--max-exp", type=int, help="מקסימום שנות ניסיון נדרשות")
    g.add_argument("-s", "--source", action="append", help=f"אתרים: {', '.join(SOURCES)}")
    g.add_argument("--pages", type=int, default=2, help="עמודים לסרוק בכל אתר (ברירת מחדל 2)")
    g.add_argument("-n", "--limit", type=int, help="מקסימום תוצאות")


def criteria_from_args(a: argparse.Namespace) -> SearchCriteria:
    return SearchCriteria(
        keywords=_split(a.keyword), match_all=a.match_all, title_only=a.title_only,
        exclude_keywords=_split(a.exclude), locations=_split(a.location), remote_only=a.remote,
        job_types=_split(a.job_types), companies=_split(a.company), exclude_companies=_split(a.exclude_company),
        posted_within_days=a.days, min_salary=a.min_salary, max_experience_years=a.max_exp,
        sources=_split(a.source), max_pages=a.pages, limit=a.limit,
    )


def _output(text: str, path: str | None) -> None:
    if path:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        print(f"נשמר ל-{path}", file=sys.stderr)
    else:
        print(text)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jobsearch-il", description="מנוע חיפוש עבודה לאתרי הדרושים בישראל")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--config", help="קובץ הגדרות (ברירת מחדל: config.yaml)")
    p.add_argument("--db", default=None, help="קובץ מסד נתונים (ברירת מחדל: jobs.db)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="סריקת האתרים בזמן אמת")
    add_criteria_args(s)
    s.add_argument("--new-only", action="store_true", help="הצג רק משרות שלא נראו בהרצות קודמות")
    s.add_argument("-f", "--format", choices=["table", "json", "csv"], default="table")
    s.add_argument("-o", "--out", help="שמירה לקובץ")

    d = sub.add_parser("db", help="חיפוש במשרות שכבר נשמרו (בלי אינטרנט)")
    add_criteria_args(d)
    d.add_argument("-f", "--format", choices=["table", "json", "csv"], default="table")
    d.add_argument("-o", "--out")

    sv = sub.add_parser("saved", help="הרצת החיפושים השמורים מ-config.yaml (רק משרות חדשות)")
    sv.add_argument("name", nargs="?", help="שם חיפוש ספציפי")
    sv.add_argument("--all-results", action="store_true", help="הצג גם משרות שכבר נראו")

    st = sub.add_parser("status", help="סימון משרה: saved / applied / hidden")
    st.add_argument("uid")
    st.add_argument("status", choices=["new", "saved", "applied", "hidden"])

    sub.add_parser("sources", help="רשימת האתרים הנתמכים")

    ck = sub.add_parser("check", help="בדיקת חיבור לכל אתר (מחפש פעם אחת ומדווח)")
    ck.add_argument("-q", "--query", default="developer")

    w = sub.add_parser("serve", help="ממשק ווב")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--port", type=int, default=8000)
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    config = load_config(a.config)
    db_path = a.db or config.get("database", "jobs.db")

    if a.cmd == "sources":
        engine = JobSearchEngine(config)
        active = {s.name for s in engine.enabled_sources()}
        for name, cls in SOURCES.items():
            state = "פעיל" if name in active else ("דורש הגדרה ב-config.yaml" if cls.needs_config else "כבוי")
            print(f"{name:<11} {cls.display_name:<22} {state}")
        return 0

    if a.cmd == "check":
        engine = JobSearchEngine(config)
        try:
            for name, r in engine.check(a.query).items():
                if r["ok"]:
                    smp = r["sample"]
                    print(f"✅ {name:<11} {r['count']} משרות. לדוגמה: {smp['title']} | {smp['company']} | {smp['location']}")
                else:
                    print(f"❌ {name:<11} {r['error']}")
        finally:
            engine.close()
        return 0

    if a.cmd == "serve":
        try:
            import uvicorn

            from .web.app import create_app
        except ImportError:
            print("Install web extras: pip install 'jobsearch-il[web]'", file=sys.stderr)
            return 1
        uvicorn.run(create_app(config, db_url=db_path, secure_cookies=False), host=a.host, port=a.port)
        return 0

    store = JobStore(db_path)
    engine = JobSearchEngine(config, store=store)
    try:
        if a.cmd == "status":
            ok = store.set_status(a.uid, a.status)
            print("עודכן" if ok else "משרה לא נמצאה")
            return 0 if ok else 1

        if a.cmd == "db":
            _output(render(engine.search_stored(criteria_from_args(a)), a.format), a.out)
            return 0

        if a.cmd == "search":
            res = engine.search(criteria_from_args(a))
            jobs = res.new_jobs if a.new_only else res.jobs
            _output(render(jobs, a.format), a.out)
            summary = ", ".join(f"{k}: {v}" for k, v in sorted(res.per_source.items()))
            print(f"\nנסרקו {res.scraped} משרות ({summary}); הותאמו {len(res.jobs)}, מתוכן חדשות {len(res.new_jobs)}",
                  file=sys.stderr)
            for name, err in res.errors.items():
                print(f"שגיאה ב-{name}: {err}", file=sys.stderr)
            return 0

        if a.cmd == "saved":
            searches = config.get("saved_searches") or {}
            if not searches:
                print("אין חיפושים שמורים ב-config.yaml (saved_searches)", file=sys.stderr)
                return 1
            for name, spec in searches.items():
                if a.name and name != a.name:
                    continue
                res = engine.search(criteria_from_dict(spec))
                jobs = res.jobs if a.all_results else res.new_jobs
                print(f"\n=== {name}: {len(jobs)} {'משרות' if a.all_results else 'משרות חדשות'} ===")
                if jobs:
                    print(render(jobs, "table"))
                for src, err in res.errors.items():
                    print(f"שגיאה ב-{src}: {err}", file=sys.stderr)
            return 0
    finally:
        engine.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
