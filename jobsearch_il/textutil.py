"""Hebrew-aware text helpers: normalization, keyword matching, salary/experience/date parsing."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

NIQQUD = re.compile(r"[֑-ׇ]")
HEB_PREFIXES = "והבלמשכ"  # ו ה ב ל מ ש כ - prefixes that attach to Hebrew words

# Bilingual synonyms so "פייתון" also finds "python" and vice versa.
SYNONYMS: list[set[str]] = [
    {"python", "פייתון", "פיתון"},
    {"javascript", "js", "ג'אווהסקריפט", "גאווה סקריפט"},
    {"java", "ג'אווה", "גאווה"},
    {"developer", "מפתח", "מפתחת", "מתכנת", "מתכנתת", "engineer", "מהנדס", "מהנדסת"},
    {"devops", "דבאופס", "דב אופס"},
    {"qa", "בודק", "בודקת", "בדיקות", "tester", "automation", "אוטומציה"},
    {"data scientist", "מדען נתונים", "data science"},
    {"data analyst", "אנליסט", "אנליסטית", "analyst", "מנתח נתונים"},
    {"product manager", "מנהל מוצר", "מנהלת מוצר", "pm"},
    {"student", "סטודנט", "סטודנטית", "סטודנטים"},
    {"junior", "ג'וניור", "גוניור", "ללא ניסיון", "entry level"},
    {"senior", "סניור", "בכיר", "בכירה"},
    {"full stack", "fullstack", "full-stack", "פולסטאק", "פול סטאק"},
    {"backend", "back-end", "back end", "בקאנד", "צד שרת"},
    {"frontend", "front-end", "front end", "פרונטאנד", "צד לקוח"},
    {"accountant", "רואה חשבון", "רו\"ח", "מנהלת חשבונות", "הנהלת חשבונות"},
    {"sales", "מכירות", "איש מכירות", "נציג מכירות"},
    {"customer service", "שירות לקוחות", "נציג שירות"},
    {"secretary", "מזכירה", "מזכיר", "office manager", "אדמיניסטרציה"},
    {"driver", "נהג", "נהגת"},
    {"nurse", "אח", "אחות"},
    {"teacher", "מורה"},
    {"lawyer", "עורך דין", "עו\"ד", "עורכת דין"},
    {"marketing", "שיווק"},
    {"hr", "משאבי אנוש", "גיוס"},
    {"cyber", "סייבר", "security", "אבטחת מידע"},
]


def normalize(text: str) -> str:
    text = NIQQUD.sub("", text or "")
    text = text.replace("״", '"').replace("׳", "'").replace("־", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


def expand_synonyms(term: str) -> list[str]:
    t = normalize(term)
    for group in SYNONYMS:
        if t in group:
            return sorted(group, key=len, reverse=True)
    return [t]


def _term_pattern(term: str) -> re.Pattern[str]:
    t = re.escape(normalize(term)).replace(r"\ ", r"[\s\-]*")
    if re.search(r"[֐-׿]", term):
        # Hebrew: allow up to 3 attached prefix letters (e.g. "למפתח", "ומהמפתח")
        return re.compile(rf"(?<![\w֐-׿])[{HEB_PREFIXES}]{{0,3}}{t}")
    return re.compile(rf"(?<![\w]){t}(?![a-z0-9])")


def keyword_in(text: str, keyword: str, synonyms: bool = True) -> bool:
    hay = normalize(text)
    terms = expand_synonyms(keyword) if synonyms else [normalize(keyword)]
    return any(_term_pattern(t).search(hay) for t in terms)


# ---------------------------------------------------------------- experience
_EXP_PATTERNS = [
    re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years?|yrs?)\b", re.I),
    re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?שנות\s+ניסיון"),
    re.compile(r"ניסיון\s+(?:של\s+|מוכח\s+|של\s+לפחות\s+|לפחות\s+|מעל\s+)?(\d{1,2})\s*\+?\s*שנ"),
    re.compile(r"ניסיון\s+של\s+(?:לפחות\s+)?(שנה|שנתיים)"),
    re.compile(r"(שנה|שנתיים)\s+ניסיון"),
]
_WORD_NUM = {"שנה": 1, "שנתיים": 2}


def required_experience(text: str) -> int | None:
    """Best-effort minimum years of experience mentioned in the posting."""
    found: list[int] = []
    for pat in _EXP_PATTERNS:
        for m in pat.finditer(text or ""):
            raw = m.group(1)
            n = _WORD_NUM.get(raw) if raw in _WORD_NUM else int(raw)
            if n is not None and n <= 30:
                found.append(n)
    if found:
        return min(found)
    t = normalize(text)
    if "ללא ניסיון" in t or "no experience" in t or "entry level" in t:
        return 0
    return None


# ---------------------------------------------------------------- salary
_SALARY_RE = re.compile(
    r"(?:₪\s*)?(\d{1,3}(?:[,.]\d{3})+|\d{2,6})\s*(k|K|אלף)?\s*(?:₪|ש\"ח|שח|nis|ils)?"
)


def parse_salary(text: str) -> int | None:
    """Highest monthly-ish salary figure mentioned near a currency marker."""
    if not text:
        return None
    t = text.replace("ש״ח", 'ש"ח')
    if not re.search(r"₪|ש\"ח|שח|nis|ils|שכר|salary|לשעה|per hour", t, re.I):
        return None
    values: list[int] = []
    for m in _SALARY_RE.finditer(t):
        num = int(re.sub(r"[,.]", "", m.group(1)))
        if m.group(2):
            num *= 1000
        if 30 <= num <= 200 and re.search(r"לשעה|per hour|/h", t, re.I):
            num *= 186  # approximate monthly from hourly
        if 3_000 <= num <= 150_000:
            values.append(num)
    return max(values) if values else None


# ---------------------------------------------------------------- dates
_REL_PATTERNS = [
    (re.compile(r"(\d+)\s*(?:דקות|minutes?)"), "minutes"),
    (re.compile(r"(\d+)\s*(?:שעות|hours?)"), "hours"),
    (re.compile(r"(\d+)\s*(?:ימים|days?)"), "days"),
    (re.compile(r"(\d+)\s*(?:שבועות|weeks?)"), "weeks"),
    (re.compile(r"(\d+)\s*(?:חודשים|months?)"), "months"),
]


def parse_date(value: str | None, now: datetime | None = None) -> datetime | None:
    """Parse ISO, dd/mm/yyyy, dd.mm.yy and relative Hebrew/English dates ("לפני 3 ימים")."""
    if not value:
        return None
    now = now or datetime.now()
    v = value.strip()
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except ValueError:
        pass
    m = re.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})", v)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        y = y + 2000 if y < 100 else y
        try:
            return datetime(y, mo, d)
        except ValueError:
            return None
    m = re.search(r"/Date\((\d+)", v)  # .NET JSON date
    if m:
        return datetime.fromtimestamp(int(m.group(1)) / 1000)
    lv = normalize(v)
    if "היום" in lv or "today" in lv or "just now" in lv or "עכשיו" in lv:
        return now
    if "אתמול" in lv or "yesterday" in lv:
        return now - timedelta(days=1)
    if "שלשום" in lv:
        return now - timedelta(days=2)
    if "שבוע" in lv and not re.search(r"\d", lv) or lv in ("a week ago", "1 week ago"):
        return now - timedelta(weeks=1)
    if "חודש" in lv and not re.search(r"\d", lv):
        return now - timedelta(days=30)
    for pat, unit in _REL_PATTERNS:
        m = pat.search(lv)
        if m:
            n = int(m.group(1))
            if unit == "months":
                return now - timedelta(days=30 * n)
            return now - timedelta(**{unit: n})
    return None


def clean_html_text(html: str) -> str:
    from bs4 import BeautifulSoup

    return re.sub(r"\s+", " ", BeautifulSoup(html or "", "lxml").get_text(" ")).strip()
