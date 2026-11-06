"""CV (קורות חיים) support: extract text from PDF/DOCX/TXT, detect roles and skills, score jobs.

Matching is dictionary based (no external AI service): the detected terms are shown to the
user as editable tags, so anything we miss can be added by hand.
"""

from __future__ import annotations

import io
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .models import Job
from .textutil import keyword_in, normalize

MAX_CV_BYTES = 5 * 1024 * 1024
MAX_CV_CHARS = 30_000

# ---------------------------------------------------------------------------- lexicon
# Job titles. The first item of each group is the display name; the rest are aliases.
ROLES: list[list[str]] = [
    ["Full Stack Developer", "full stack", "fullstack", "full-stack", "פולסטאק", "מפתח פול סטאק", "מפתחת פול סטאק"],
    ["Backend Developer", "backend developer", "backend engineer", "back-end developer", "server side", "מפתח backend",
     "מפתחת backend", "מפתח צד שרת"],
    ["Frontend Developer", "frontend developer", "frontend engineer", "front-end developer", "מפתח frontend",
     "מפתחת frontend", "מפתח צד לקוח"],
    ["Software Engineer", "software engineer", "software developer", "מהנדס תוכנה", "מהנדסת תוכנה", "מפתח תוכנה",
     "מפתחת תוכנה", "מתכנת", "מתכנתת"],
    ["Mobile Developer", "mobile developer", "android developer", "ios developer", "מפתח מובייל", "מפתחת מובייל"],
    ["DevOps Engineer", "devops", "site reliability", "sre", "platform engineer", "מהנדס devops", "דבאופס"],
    ["QA Engineer", "qa engineer", "qa automation", "automation engineer", "software tester", "בודק תוכנה",
     "בודקת תוכנה", "בודק תוכנה ואוטומציה", "מהנדס בדיקות", "אוטומציה"],
    ["Data Analyst", "data analyst", "bi analyst", "business analyst", "אנליסט נתונים", "אנליסטית נתונים",
     "אנליסט bi", "מנתח נתונים", "אנליסט", "אנליסטית"],
    ["Data Scientist", "data scientist", "machine learning engineer", "ml engineer", "מדען נתונים", "מדענית נתונים"],
    ["Data Engineer", "data engineer", "etl developer", "מהנדס נתונים", "מהנדסת נתונים"],
    ["Product Manager", "product manager", "product owner", "מנהל מוצר", "מנהלת מוצר"],
    ["Project Manager", "project manager", "program manager", "מנהל פרויקטים", "מנהלת פרויקטים", "מנהל פרויקט",
     "מנהלת פרויקט"],
    ["UX/UI Designer", "ux designer", "ui designer", "product designer", "graphic designer", "מעצב", "מעצבת",
     "מעצב גרפי", "מעצבת גרפית"],
    ["Security Engineer", "security engineer", "cyber security", "penetration tester", "חוקר סייבר", "אבטחת מידע",
     "סייבר"],
    ["Embedded Engineer", "embedded", "firmware", "מהנדס embedded", "תוכנה משובצת"],
    ["Hardware Engineer", "hardware engineer", "electrical engineer", "מהנדס חשמל", "מהנדסת חשמל",
     "מהנדס אלקטרוניקה", "הנדסאי אלקטרוניקה"],
    ["IT / System Administrator", "system administrator", "sysadmin", "it support", "help desk", "helpdesk",
     "מנהל רשת", "מנהל מערכות", "תמיכה טכנית", "טכנאי מחשבים"],
    ["Team Lead", "team lead", "team leader", "tech lead", "ראש צוות"],
    ["Bookkeeper / Accountant", "bookkeeper", "accountant", "cpa", "מנהלת חשבונות", "מנהל חשבונות", "הנהלת חשבונות",
     "רואה חשבון", "רואת חשבון", "חשב", "חשבת", "כספים"],
    ["Customer Service", "customer service", "customer support", "customer success", "שירות לקוחות",
     "נציג שירות", "נציגת שירות", "מוקדן", "מוקדנית"],
    ["Sales", "sales representative", "account manager", "business development", "מכירות", "איש מכירות",
     "אשת מכירות", "נציג מכירות", "נציגת מכירות", "מנהל לקוחות"],
    ["Marketing", "marketing manager", "digital marketing", "performance marketing", "content writer", "seo",
     "שיווק", "מנהל שיווק", "מנהלת שיווק", "שיווק דיגיטלי", "קופירייטר", "קופירייטרית"],
    ["HR / Recruitment", "human resources", "hr manager", "recruiter", "talent acquisition", "משאבי אנוש",
     "גיוס", "רכזת גיוס", "רכז גיוס"],
    ["Office / Administration", "office manager", "administrative assistant", "secretary", "back office",
     "backoffice", "מזכירה", "מזכיר", "מזכירה משפטית", "מזכירה רפואית", "אדמיניסטרציה", "אדמיניסטרטיבי",
     "אדמיניסטרטיבית", "מנהלת משרד", "רכזת", "רכז", "בק אופיס", "בק-אופיס", "פקיד", "פקידה", "פקידת", "עובד משרד",
     "עובדת משרד", "ניהול משרד", "רפרנט", "רפרנטית", "תפעול"],
    ["Logistics / Warehouse", "logistics", "warehouse", "supply chain", "procurement", "לוגיסטיקה", "מחסן",
     "מחסנאי", "רכש", "שרשרת אספקה"],
    ["Driver", "driver", "נהג", "נהגת", "שליח"],
    ["Technician", "technician", "טכנאי", "טכנאית", "חשמלאי", "אחזקה"],
    ["Teacher", "teacher", "tutor", "מורה", "מדריך", "מדריכה", "גננת"],
    ["Nurse / Healthcare", "nurse", "caregiver", "אח", "אחות", "מטפל", "מטפלת", "רוקח", "רוקחת"],
    ["Lawyer", "lawyer", "attorney", "legal counsel", "עורך דין", "עורכת דין", "עו\"ד", "משפטן", "משפטנית"],
    ["Civil Engineer / Architect", "civil engineer", "architect", "מהנדס אזרחי", "מהנדסת אזרחית", "אדריכל",
     "אדריכלית", "מהנדס בניין"],
]

SKILLS: list[str] = [
    # languages & frameworks
    "Python", "Java", "JavaScript", "TypeScript", "C#", "C++", "Go", "Golang", "Rust", "Kotlin", "Swift", "PHP",
    "Ruby", "Scala", "R", "MATLAB", "Bash", "PowerShell", "React", "Angular", "Vue", "Next.js", "Node.js",
    "Express", "Django", "Flask", "FastAPI", "Spring", "Spring Boot", ".NET", "ASP.NET", "Laravel", "Rails",
    "HTML", "CSS", "Tailwind", "Redux", "GraphQL", "REST", "gRPC", "Microservices", "Android", "iOS", "Flutter",
    "React Native",
    # data
    "SQL", "PostgreSQL", "MySQL", "SQL Server", "Oracle", "MongoDB", "Redis", "Elasticsearch", "Cassandra",
    "Snowflake", "BigQuery", "Redshift", "Databricks", "Kafka", "RabbitMQ", "Spark", "Airflow", "Hadoop", "ETL",
    "dbt", "Pandas", "NumPy", "scikit-learn", "TensorFlow", "PyTorch", "Machine Learning", "Deep Learning", "NLP",
    "LLM", "Computer Vision", "Statistics", "Tableau", "Power BI", "Looker", "Qlik", "Excel",
    # cloud & ops
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins", "GitHub Actions", "GitLab",
    "CI/CD", "Linux", "Git", "Prometheus", "Grafana", "Networking", "Active Directory", "VMware",
    # testing
    "Selenium", "Cypress", "Playwright", "Appium", "JMeter", "Postman", "Manual Testing", "Automation",
    # embedded / hw
    "Embedded C", "RTOS", "FPGA", "Verilog", "VHDL", "PCB", "Altium", "AutoCAD", "SolidWorks", "Revit",
    # product, design, business
    "Figma", "Photoshop", "Illustrator", "InDesign", "UX", "UI", "Jira", "Confluence", "Agile", "Scrum",
    "Salesforce", "HubSpot", "SAP", "Priority", "Monday", "Google Ads", "Facebook Ads", "SEO", "SEM",
    "Google Analytics", "CRM", "ERP",
    # Hebrew business skills
    "חשבשבת", "פריוריטי", "הנהלת חשבונות סוג 3", "הנהלת חשבונות סוג 2", "דוחות כספיים", "התאמות בנקים",
    "חשבות שכר", "הכנת שכר", "Payroll", "גבייה", "תקציב", "אופיס", "אקסל", "שירות לקוחות", "מכירות טלפוניות", "ניהול צוות", "רישיון נהיגה",
    "רישיון B", "רישיון C", "מלגזה", "אנגלית ברמה גבוהה", "אנגלית", "ערבית", "רוסית",
]

# short or ambiguous English skills that must appear exactly (case-sensitive) to count
CASE_SENSITIVE = {"Go", "R", "UI", "UX", "REST", "SAP", "ETL", "CRM", "ERP", "SEO", "SEM", "PCB", "NLP", "LLM",
                  "Monday", "Priority", "Spring", "Express", "Rails", "Swift"}


@dataclass
class CVProfile:
    roles: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    years: int | None = None
    terms: dict[str, str] = field(default_factory=dict)
    """role -> the wording the CV itself uses (searched in that language, e.g. "מנהלת חשבונות")."""
    include: list[str] = field(default_factory=list)
    """Extra things the user wants ("ניסיון עם כספים"): searched for and counted in the match score."""
    exclude: list[str] = field(default_factory=list)
    """Jobs mentioning these ("חשבת שכר") are hidden."""
    hide_other_titles: bool = True
    """Hide jobs whose title (or a required credential) doesn't appear in the CV."""

    def to_dict(self) -> dict[str, Any]:
        return {"roles": self.roles, "skills": self.skills, "years": self.years, "terms": self.terms,
                "include": self.include, "exclude": self.exclude, "hide_other_titles": self.hide_other_titles}

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "CVProfile":
        d = d or {}
        return cls(roles=list(d.get("roles") or []), skills=list(d.get("skills") or []), years=d.get("years"),
                   terms=dict(d.get("terms") or {}), include=list(d.get("include") or []),
                   exclude=list(d.get("exclude") or []), hide_other_titles=d.get("hide_other_titles", True) is not False)


# ---------------------------------------------------------------------------- text extraction
class CVError(Exception):
    """User-facing error (Hebrew)."""


_HEB = re.compile(r"[֐-׿]")
_FINALS = "ךםןףץ"


def _fix_reversed_years(line: str) -> str:
    """In Hebrew lines of some PDFs, numbers come out reversed ("9102" for 2019)."""
    if not _HEB.search(line):
        return line

    def fix(m: re.Match) -> str:
        n = m.group(0)
        return n[::-1] if not re.fullmatch(r"19\d\d|20\d\d", n) and re.fullmatch(r"19\d\d|20\d\d", n[::-1]) else n

    return re.sub(r"(?<!\d)\d{4}(?!\d)", fix, line)


def fix_hebrew_order(text: str) -> str:
    """Some PDFs store Hebrew in visual order, so extracted lines come out reversed.

    Hebrew final letters (ך ם ן ף ץ) only appear at the end of words; when most Hebrew words in a
    line *start* with one, the line is reversed - flip it and restore the Latin/digit runs.
    """
    out = []
    for line in (_fix_reversed_years(x) for x in text.splitlines()):
        words = re.findall(r"[א-ת]{2,}", line)
        starts = sum(1 for w in words if w[0] in _FINALS)
        ends = sum(1 for w in words if w[-1] in _FINALS)
        if words and starts > ends:
            rev = line[::-1]
            rev = re.sub(r"[A-Za-z0-9][A-Za-z0-9.+#@/_\-]*[A-Za-z0-9+#]|[A-Za-z0-9]", lambda m: m.group(0)[::-1], rev)
            rev = rev.translate(str.maketrans("()[]{}<>", ")(][}{><"))
            out.append(rev)
        else:
            out.append(line)
    return "\n".join(out)


def extract_text(filename: str, data: bytes) -> str:
    if len(data) > MAX_CV_BYTES:
        raise CVError("הקובץ גדול מדי (עד 5MB)")
    name = (filename or "").lower()
    try:
        if name.endswith(".pdf") or data[:5] == b"%PDF-":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:10])
            text = fix_hebrew_order(text)
        elif name.endswith(".docx"):
            import docx

            d = docx.Document(io.BytesIO(data))
            parts = [p.text for p in d.paragraphs]
            for table in d.tables:
                for row in table.rows:
                    parts.append(" | ".join(c.text for c in row.cells))
            text = "\n".join(parts)
        elif name.endswith((".txt", ".md")):
            text = data.decode("utf-8", errors="replace")
        elif name.endswith(".doc"):
            raise CVError("קבצי ‎.doc‎ ישנים לא נתמכים. שמרו את הקובץ כ-‎.docx‎ או PDF")
        else:
            raise CVError("סוג קובץ לא נתמך. אפשר להעלות PDF, Word (‎.docx‎) או טקסט")
    except CVError:
        raise
    except Exception as e:  # corrupt / encrypted file
        raise CVError(f"לא הצלחתי לקרוא את הקובץ ({type(e).__name__})") from e
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 30:
        raise CVError("לא נמצא טקסט בקובץ. אם זה PDF סרוק (תמונה), העלו גרסה עם טקסט או קובץ Word")
    return text[:MAX_CV_CHARS]


# ---------------------------------------------------------------------------- profile
def _skill_in(text: str, skill: str) -> bool:
    if skill in CASE_SENSITIVE:
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(skill)}(?![A-Za-z0-9])", text) is not None
    if re.fullmatch(r"[A-Za-z0-9.+#/ \-]+", skill):
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(skill.lower())}(?![A-Za-z0-9+#])", text.lower()) is not None
    return keyword_in(text, skill, synonyms=False)


def _years_of_experience(text: str) -> int | None:
    stated = [int(m.group(1)) for m in re.finditer(r"(\d{1,2})\+?\s*(?:years? of experience|שנות ניסיון|שנות נסיון)", text, re.I)]
    if stated:
        return max(n for n in stated if n <= 45) if any(n <= 45 for n in stated) else None
    years = [int(y) for y in re.findall(r"\b(19[89]\d|20[0-4]\d)\b", text)]
    if re.search(r"\b(present|current|today|היום|כיום|עד היום|הווה)\b", text, re.I):
        from datetime import date

        years.append(date.today().year)
    if len(years) >= 2:
        span = max(years) - min(years)
        return span if 0 < span <= 45 else None
    return None


def _alias_pattern(alias: str) -> re.Pattern[str]:
    """Whole-word match; Hebrew may carry attached prefixes (ו/ה/ב/ל/מ/ש/כ)."""
    t = re.escape(normalize(alias)).replace(r"\ ", r"[\s\-]*")
    pre = r"[והבלמשכ]{0,3}" if _HEB.search(alias) else ""
    return re.compile(rf"(?<![\w\u0590-\u05FF]){pre}{t}(?![\w\u0590-\u05FF])")


def extract_profile(text: str) -> CVProfile:
    """Detect roles (ranked: earlier + more frequent first) and skills mentioned in the CV."""
    norm = normalize(text)
    n = max(len(norm), 1)
    role_scores: dict[str, float] = {}
    terms: dict[str, str] = {}
    for group in ROLES:
        score, best, best_score = 0.0, None, 0.0
        for alias in group[1:]:
            alias_score = 0.0
            for m in _alias_pattern(alias).finditer(norm):
                alias_score += 1.0 + 2.0 * (1 - m.start() / n)  # headline / recent jobs weigh more
            score += alias_score
            # the most prominent wording (headline, frequency); a longer one wins a near-tie
            if alias_score and (best is None or alias_score > best_score * 1.2
                                or (alias_score >= best_score * 0.8 and len(alias) > len(best))):
                best, best_score = alias, alias_score
        if score:
            role_scores[group[0]] = score
            terms[group[0]] = best
    roles = [r for r, _ in sorted(role_scores.items(), key=lambda kv: -kv[1])][:5]

    counts: Counter[str] = Counter()
    for skill in SKILLS:
        if _skill_in(text, skill):
            counts[skill] = len(re.findall(re.escape(skill.lower()), text.lower())) or 1
    # drop sub-skills already covered by a longer one (e.g. "אנגלית" when "אנגלית ברמה גבוהה" matched)
    skills = [s for s, _ in counts.most_common()]

    def covered(s: str, by: str) -> bool:  # "אנגלית" is covered by "אנגלית ברמה גבוהה", "Go" is not by "Django"
        return by != s and re.search(rf"(?<![\w]){re.escape(s.lower())}(?![\w])", by.lower()) is not None

    skills = [s for s in skills if not any(covered(s, o) for o in skills)]
    if "Golang" in skills and "Go" in skills:
        skills.remove("Go")
    return CVProfile(roles=roles, skills=skills[:25], years=_years_of_experience(text),
                     terms={r: terms[r] for r in roles})


# filler words in free-text tags like "ניסיון עם כספים" / "experience with finance"
STOPWORDS = {"ניסיון", "נסיון", "עם", "של", "את", "על", "או", "גם", "ידע", "יכולת", "עבודה", "בתחום", "תחום",
             "experience", "with", "in", "of", "and", "or", "the", "a", "an", "knowledge", "working", "work"}


def content_words(term: str) -> list[str]:
    """Meaningful words of a tag; Hebrew prefixes are stripped from stopwords too ("בתחום" -> skipped)."""
    words = re.findall(r"[\w\u0590-\u05FF+#.\-]+", term)
    out = [w for w in words if w.lower() not in STOPWORDS and w.lstrip("והבלמשכ") not in STOPWORDS]
    return out or words


def _gender_variants(term: str) -> list[str]:
    """"חשבת שכר" should also find "חשב/ת שכר" and "חשב שכר" (job ads write both genders)."""
    variants = [term]
    words = term.split()
    for i, w in enumerate(words):
        if _HEB.search(w) and len(w) >= 4:
            for suffix in ("ית", "ת", "ה"):
                if w.endswith(suffix) and len(w) - len(suffix) >= 3:
                    variants.append(" ".join(words[:i] + [w[: -len(suffix)]] + words[i + 1:]))
                    break
    return variants


_GENDER_SLASH = re.compile(r"\s*/\s*(?:ית|ה|ת|ים|ות|יות)(?![\u0590-\u05FF])")


def _ungender(text: str) -> str:
    """"חשב /ת שכר" -> "חשב שכר"."""
    return _GENDER_SLASH.sub("", text or "")


def _phrase_pattern(term: str) -> re.Pattern[str]:
    """Whole-word phrase; every Hebrew word may carry attached prefixes ("לחשבת השכר")."""
    parts = []
    for w in normalize(term).split():
        pre = r"[והבלמשכ]{0,3}" if _HEB.search(w) else ""
        parts.append(pre + re.escape(w))
    return re.compile(r"(?<![\w\u0590-\u05FF])" + r"[\s\-]+".join(parts) + r"(?![\w\u0590-\u05FF])")


def phrase_in(text: str, term: str) -> bool:
    """Exact phrase (with gender variants), Hebrew-prefix aware on every word."""
    clean = normalize(_ungender(text))
    return any(_phrase_pattern(v).search(clean) for v in _gender_variants(term) if v.strip())


def include_in(text: str, term: str) -> bool:
    """A wish tag matches when the phrase appears, or all its meaningful words do."""
    if phrase_in(text, term):
        return True
    words = content_words(term)
    return bool(words) and all(phrase_in(text, w) for w in words)


def excluded_by(job: Job, profile: CVProfile) -> str | None:
    """The exclude tag this job hits (in its title or description), if any."""
    text = f"{job.title} {job.description}"
    return next((t for t in profile.exclude if phrase_in(text, t)), None)


def search_queries(profile: CVProfile, max_queries: int = 6) -> list[str]:
    """What to type into the job sites: top roles, the user's wish tags, then the strongest skills."""
    role_terms = []
    for r in profile.roles[:3]:
        group = next((g for g in ROLES if g[0] == r), None)
        # the CV's own wording, else the first alias, else what the user typed
        role_terms.append(profile.terms.get(r) or (group[1] if group else r))
    wishes = [" ".join(content_words(t)) for t in profile.include[:3]]
    room = max(0, max_queries - len(role_terms) - len(wishes))
    skills = [s for s in profile.skills if s not in CASE_SENSITIVE or len(s) > 2][:room]
    seen, out = set(), []
    for q in role_terms + wishes + skills:
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out[:max_queries]


# ---------------------------------------------------------------------------- scoring
def _role_aliases(role: str) -> list[str]:
    group = next((g for g in ROLES if g[0] == role), None)
    return group[1:] if group else [role]


def score_job(job: Job, profile: CVProfile) -> tuple[int, list[str]]:
    """0-100 match score between a job and the CV, plus the CV terms that matched.

    Half the score is the role (job title match counts fully, description match partially),
    half is the skills: a job that asks for ~6 of your top skills is a full skills match.
    Matches in the job title count more than matches in the description.
    """
    title, desc = job.title or "", job.description or ""
    matched: list[str] = []

    role_part = 0.0
    for role in profile.roles[:3]:
        aliases = _role_aliases(role)
        if any(keyword_in(title, a, synonyms=False) for a in aliases):
            role_part = 1.0
            matched.append(role)
        elif any(keyword_in(desc, a, synonyms=False) for a in aliases):
            role_part = max(role_part, 0.4)
            matched.append(role)

    skill_points = 0.0
    # wish tags ("ניסיון עם כספים") first: the user asked for them explicitly
    for wish in profile.include:
        if include_in(title, wish):
            skill_points += 3
            matched.append(wish)
        elif include_in(desc, wish):
            skill_points += 1.5
            matched.append(wish)
    top_skills = profile.skills[:15]
    for skill in top_skills:
        if _skill_in(title, skill):
            skill_points += 3
            matched.append(skill)
        elif _skill_in(desc, skill):
            skill_points += 1
            matched.append(skill)
    # the site matched our query but gave us no description (JobMaster/LinkedIn): don't punish that
    if not desc and job.extra.get("site_matched"):
        skill_points += 1
    n_terms = len(top_skills) + len(profile.include)
    skill_part = min(1.0, skill_points / min(6, n_terms)) if n_terms else 0.0

    if profile.roles and n_terms:
        score = 50 * role_part + 50 * skill_part
    elif profile.roles:
        score = 100 * role_part
    else:
        score = 100 * skill_part
    return round(score), matched


# ---------------------------------------------------------------------------- titles the CV doesn't have
# Roles in the same family count as the same title (a backend developer may take a full stack job).
ROLE_FAMILY: dict[str, str | None] = {
    "Full Stack Developer": "dev", "Backend Developer": "dev", "Frontend Developer": "dev",
    "Software Engineer": "dev", "Mobile Developer": "dev",
    "Team Lead": None,  # a seniority word, not a profession
}

# Licensed / protected titles: the CV must have the title itself, related knowledge isn't enough
# ("ידע במשפטים" is not "עורך דין").
CREDENTIALS: list[list[str]] = [
    ["עורך דין", "עורך דין", "עורכת דין", "עו\"ד", "עוה\"ד", "עריכת דין", "lawyer", "attorney", "advocate"],
    ["רואה חשבון", "רואה חשבון", "רואת חשבון", "רו\"ח", "cpa", "certified public accountant"],
    ["רופא", "רופא", "רופאה", "רופא משפחה", "physician", "medical doctor"],
    ["רופא שיניים", "רופא שיניים", "רופאת שיניים", "dentist"],
    ["אחות מוסמכת", "אח מוסמך", "אחות מוסמכת", "registered nurse"],
    ["פסיכולוג", "פסיכולוג", "פסיכולוגית", "psychologist"],
    ["רוקח", "רוקח", "רוקחת", "pharmacist"],
    ["עובד סוציאלי", "עובד סוציאלי", "עובדת סוציאלית", "עו\"ס", "social worker"],
    ["פיזיותרפיסט", "פיזיותרפיסט", "פיזיותרפיסטית", "physiotherapist"],
    ["שמאי", "שמאי", "שמאית", "appraiser"],
    ["יועץ מס", "יועץ מס", "יועצת מס", "tax advisor"],
    ["חשמלאי מוסמך", "חשמלאי מוסמך", "חשמלאי ראשי", "חשמלאי בכיר", "רישיון חשמלאי"],
    ["אדריכל", "אדריכל", "אדריכלית"],
    ["מהנדס בניין", "מהנדס בניין", "מהנדסת בניין", "מהנדס אזרחי", "מהנדסת אזרחית", "civil engineer"],
]

# words that make a credential in the job description a requirement, not just context
_REQUIRE = re.compile(r"דרוש|דרושה|דרושים|דרישות|חובה|רישיון|רשיון|מוסמך|מוסמכת|בעל|בעלת|לפחות|תואר|הסמכה|"
                      r"required|requirements|must|licen[cs]e|licensed|certified|qualified", re.I)


def _has_alias(text: str, aliases: list[str]) -> str | None:
    clean = normalize(_ungender(text))
    return next((a for a in aliases if _alias_pattern(a).search(clean)), None)


@dataclass
class TitleContext:
    """What titles a CV has, computed once per search."""
    families: set[str]
    credentials: set[str]


def title_context(cv_text: str, profile: CVProfile) -> TitleContext:
    own = "\n".join([cv_text, *profile.roles, *profile.include, *profile.terms.values()])
    families, creds = set(), set()
    for group in ROLES:
        fam = ROLE_FAMILY.get(group[0], group[0])
        if fam and (group[0] in profile.roles or _has_alias(own, group[1:])):
            families.add(fam)
    for cred in CREDENTIALS:
        if _has_alias(own, cred[1:]):
            creds.add(cred[0])
    return TitleContext(families, creds)


# "משרד עו"ד", "חברת רו"ח", "law office": the title describes the workplace, not the job
_WORKPLACE = re.compile(r"(?:^|[\s(])[והבלמשכ]{0,3}(?:משרד|משרדי|חברת|פירמת|פירמה|קבוצת|office|firm|of)(?:\s|$)[^.;\n]{0,20}$", re.I)


# "בק אופיס למחלקת מכירות": a department, not the job's role
_DEPARTMENT = re.compile(r"(?:^|[\s(])[והבלמשכ]{0,3}(?:מחלקת|מחלקה|חטיבת|אגף|צוות|יחידת|department|team|dept\.?)\s*$", re.I)


def _credential_hits(text: str, aliases: list[str]):
    clean = normalize(_ungender(text))
    for alias in aliases:
        for m in _alias_pattern(alias).finditer(clean):
            if not _WORKPLACE.search(clean[max(0, m.start() - 20): m.start()]):
                yield clean, m


def _required_in(clean: str, m: re.Match) -> bool:
    """Is this credential mention phrased as a requirement? Same sentence, close by, not "an advantage"."""
    before = re.split(r"[.;\n•]", clean[max(0, m.start() - 35): m.start()])[-1]
    after = re.split(r"[.;\n•]", clean[m.end(): m.end() + 35])[0]
    window = f"{before} {after}"
    return bool(_REQUIRE.search(window)) and not re.search(r"יתרון|advantage|nice to have|plus", window, re.I)


def missing_title(job: Job, ctx: TitleContext) -> str | None:
    """The title this job asks for that the CV doesn't have (None = the job is fine)."""
    title, desc = job.title or "", job.description or ""
    title_fits = _title_families(title) & ctx.families
    for cred in CREDENTIALS:
        if cred[0] in ctx.credentials:
            continue
        if any(True for _ in _credential_hits(title, cred[1:])):
            return cred[0]
        # in the description only when the job isn't already one of the CV's roles: a bookkeeper ad that
        # mentions "work with the CPA" or "experience at a CPA office" is still a bookkeeper job
        if not title_fits and any(_required_in(clean, m) for clean, m in _credential_hits(desc, cred[1:])):
            return cred[0]
    job_families = _title_roles(title)
    if job_families and not (set(job_families) & ctx.families):
        return next(iter(job_families.values()))
    return None


def _title_roles(title: str) -> dict[str, str]:
    """Role families named in a job title -> the wording found (departments are skipped)."""
    out: dict[str, str] = {}
    clean_title = normalize(_ungender(title))
    for group in ROLES:
        fam = ROLE_FAMILY.get(group[0], group[0])
        if fam is None:
            continue
        for alias in group[1:]:
            hits = [m for m in _alias_pattern(alias).finditer(clean_title)
                    if not _DEPARTMENT.search(clean_title[max(0, m.start() - 25): m.start()])]
            if hits:
                out.setdefault(fam, alias)
                break
    return out


def _title_families(title: str) -> set[str]:
    return set(_title_roles(title))
