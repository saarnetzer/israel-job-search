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
     "מגייס", "מגייסת", "גיוס"],
    ["Office / Administration", "office manager", "administrative assistant", "secretary", "מזכירה", "מזכיר",
     "אדמיניסטרציה", "מנהלת משרד", "רכזת", "רכז"],
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

    def to_dict(self) -> dict[str, Any]:
        return {"roles": self.roles, "skills": self.skills, "years": self.years, "terms": self.terms}

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "CVProfile":
        d = d or {}
        return cls(roles=list(d.get("roles") or []), skills=list(d.get("skills") or []), years=d.get("years"),
                   terms=dict(d.get("terms") or {}))


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
            # prefer the longest wording the CV uses: "מנהלת חשבונות" over "כספים"
            if alias_score and (best is None or len(alias) > len(best) or alias_score > 2 * best_score):
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


def search_queries(profile: CVProfile, max_queries: int = 5) -> list[str]:
    """What to type into the job sites: the top roles plus the strongest skills."""
    role_terms = []
    for r in profile.roles[:3]:
        group = next((g for g in ROLES if g[0] == r), None)
        # the CV's own wording, else the first alias, else what the user typed
        role_terms.append(profile.terms.get(r) or (group[1] if group else r))
    skills = [s for s in profile.skills if s not in CASE_SENSITIVE or len(s) > 2][: max(0, max_queries - len(role_terms))]
    seen, out = set(), []
    for q in role_terms + skills:
        if q.lower() not in seen:
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
    skill_part = min(1.0, skill_points / min(6, len(top_skills))) if top_skills else 0.0

    if profile.roles and top_skills:
        score = 50 * role_part + 50 * skill_part
    elif profile.roles:
        score = 100 * role_part
    else:
        score = 100 * skill_part
    return round(score), matched
