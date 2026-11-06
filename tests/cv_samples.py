"""Builds sample CV files for tests (PDF via reportlab, DOCX via python-docx)."""

import io

EN_CV = """Dana Levi
Senior Backend Developer
Tel Aviv | dana@example.com

Summary
Backend developer with 6 years of experience building scalable services in Python and Go.

Experience
2021 - Present  Backend Developer, Fintech Co.
- Designed microservices with Python, FastAPI and PostgreSQL on AWS
- Kafka event pipelines, Docker and Kubernetes, CI/CD with GitHub Actions
2018 - 2021  Software Engineer, StartupX
- Django REST APIs, Redis, Celery, React dashboards

Skills: Python, Django, FastAPI, PostgreSQL, Redis, Kafka, AWS, Docker, Kubernetes, Terraform, Git, Linux
Education: B.Sc. Computer Science, Tel Aviv University (2014 - 2018)
"""

HE_CV = """רונית כהן
מנהלת חשבונות סוג 3
חיפה | 050-0000000

ניסיון תעסוקתי
2019 - היום: מנהלת חשבונות, משרד רואי חשבון לוי ושות'
הנהלת חשבונות מלאה עד מאזן, התאמות בנקים, דוחות כספיים, הכנת שכר וגבייה
2016 - 2019: מזכירה ואדמיניסטרציה, חברת בנייה

כישורים
חשבשבת, פריוריטי, אקסל ברמה גבוהה, אנגלית
"""


def pdf_bytes(text: str, visual_order: bool = False) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    pdfmetrics.registerFont(TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("DejaVu", 10)
    y = 800
    for line in text.splitlines():
        # visual order = how some Hebrew PDF writers store RTL text (characters reversed)
        c.drawString(40, y, line[::-1] if visual_order else line)
        y -= 14
    c.save()
    return buf.getvalue()


def docx_bytes(text: str) -> bytes:
    import docx

    d = docx.Document()
    for line in text.splitlines():
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()

CUSTOM_CV = """נועה ברק
רכזת פרט ותגמול
רמת גן | noa@example.com

ניסיון תעסוקתי
2021 - היום: רכזת פרט ותגמול, חברת ביטוח
2018 - 2021: Scrum Master, StartupY
2016 - 2018: מזכירה, משרד הנדסה

כישורים: אקסל, חילן, מירב
"""
