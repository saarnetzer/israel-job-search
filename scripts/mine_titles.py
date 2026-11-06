"""Collect real job titles from the Israeli job sites, to build and check the role dictionary.

Usage:  python scripts/mine_titles.py titles.json      (takes a few minutes)
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor

from jobsearch_il.http import HttpClient
from jobsearch_il.models import SearchCriteria
from jobsearch_il.sources import SOURCES

QUERIES = [
    # tech
    "מפתח", "מתכנת", "developer", "software engineer", "devops", "qa", "data", "product manager", "designer",
    "cyber", "embedded", "hardware", "IT", "תמיכה טכנית", "אנליסט",
    # engineering & industry
    "מהנדס", "הנדסאי", "מהנדס מכונות", "מהנדס חשמל", "מהנדס בניין", "מהנדס תעשייה וניהול", "ייצור", "מפעיל",
    "איכות", "טכנאי", "חשמלאי", "אחזקה", "מכונאי", "רתך", "אינסטלטור", "נגר",
    # business & office
    "מנהלת חשבונות", "חשב", "רואה חשבון", "כספים", "שכר", "גבייה", "בנק", "ביטוח", "מזכירה", "פקידה",
    "בק אופיס", "קלדנית", "מנהלת משרד", "משאבי אנוש", "גיוס", "רכש", "יבוא", "עורך דין", "משפטי",
    "שיווק", "דיגיטל", "תוכן", "מכירות", "טלמרקטינג", "שירות לקוחות", "מוקד", "נדלן",
    # field & service
    "נהג", "שליח", "מחסן", "מלגזה", "לוגיסטיקה", "קופאית", "מוכרת", "מנהל סניף", "מאבטח", "ניקיון",
    "טבח", "שף", "מלצר", "ברמן", "בריסטה", "מלון", "פועל", "בנייה", "מנהל עבודה",
    # health, education, social
    "אחות", "רופא", "מטפלת", "סייעת", "רוקחת", "פיזיותרפיסט", "פסיכולוג", "עובדת סוציאלית", "קלינאית תקשורת",
    "מורה", "גננת", "מדריך", "יועצת", "מעבדה", "כימאי", "חוקר",
    # misc
    "ספר", "קוסמטיקאית", "צלם", "עורך וידאו", "חקלאות", "וטרינר", "סטודנט", "ללא ניסיון",
]


def main(out_path: str) -> None:
    http = HttpClient(min_delay=1.0)
    sources = [SOURCES[n](http, {}) for n in ("drushim", "alljobs", "jobmaster")]
    titles: dict[str, set[str]] = {}

    def run(src):
        got = []
        for q in QUERIES:
            try:
                got += [j.title for j in src.search(SearchCriteria(keywords=[q], max_pages=2))]
            except Exception as e:  # keep going
                print(f"{src.name} {q!r}: {e}", file=sys.stderr)
        return src.name, got

    with ThreadPoolExecutor(len(sources)) as pool:
        for name, got in pool.map(run, sources):
            titles[name] = set(got)
            print(f"{name}: {len(got)} titles ({len(set(got))} unique)", file=sys.stderr)
    all_titles = sorted(set().union(*titles.values()))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_titles, f, ensure_ascii=False, indent=0)
    print(f"{len(all_titles)} unique titles -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "titles.json")
