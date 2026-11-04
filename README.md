# 🔎 jobsearch-il: מנוע חיפוש עבודה בישראל

חיפוש אחד שסורק את אתרי הדרושים בישראל, מאחד את התוצאות, מסיר כפילויות (גם משרה שפורסמה בכמה אתרים)
ומסנן לפי קריטריונים מדויקים. יש CLI, ממשק ווב בעברית ו-API.

## אתרים נתמכים

| מקור | שם | איך |
|---|---|---|
| דרושים IL | `drushim` | ה-JSON שעומד מאחורי דף החיפוש |
| AllJobs | `alljobs` | סריקת HTML |
| JobMaster | `jobmaster` | סריקת HTML |
| LinkedIn | `linkedin` | חיפוש ציבורי (guest), מוגבל לישראל |
| Comeet | `comeet` | API של מערכת הגיוס שרוב הסטארטאפים בישראל משתמשים בה |
| Greenhouse | `greenhouse` | API ציבורי של לוחות משרות של חברות |
| Lever | `lever` | API ציבורי של לוחות משרות של חברות |
| דפי קריירה | `careers` | כל דף עם schema.org `JobPosting` (JSON-LD) |

Comeet, Greenhouse, Lever ודפי קריירה עובדים לפי רשימת חברות שמגדירים ב-`config.yaml`, ומחזירים רק משרות בישראל או מהבית.
כשסורק HTML לא מוצא כלום (למשל כי האתר שינה מבנה), הוא מנסה אוטומטית לחלץ JSON-LD מהדף.

## התקנה

```bash
git clone <repo-url> && cd israel-job-search
python -m venv .venv && source .venv/bin/activate
pip install -e '.[web]'
cp config.example.yaml config.yaml   # אופציונלי
```

## שימוש

```bash
# פייתון או backend, באזור המרכז, מהשבוע האחרון, עד 3 שנות ניסיון, בלי senior
jobsearch-il search -k python -k backend -l מרכז --days 7 --max-exp 3 -x senior

# משרות חלקיות למנהלות חשבונות בחיפה או מהבית, שמירה ל-Excel (CSV)
jobsearch-il search -k "מנהלת חשבונות" -l חיפה -l remote -t חלקית -f csv -o jobs.csv

# כל המילים חייבות להופיע, רק בכותרת, רק מ-LinkedIn ו-AllJobs
jobsearch-il search -k devops -k aws --all --title-only -s linkedin,alljobs

# רק משרות שלא ראיתם בהרצות קודמות
jobsearch-il search -k "data analyst" --new-only

# חיפוש במשרות שכבר נשמרו, בלי לגשת לאתרים
jobsearch-il db -k אנליסט -l "תל אביב"

# החיפושים השמורים מ-config.yaml (מתאים ל-cron, כדי לקבל רק משרות חדשות כל בוקר)
jobsearch-il saved

# ממשק ווב: http://127.0.0.1:8000
jobsearch-il serve
```

### כל הקריטריונים

| פרמטר | משמעות |
|---|---|
| `-k/--keyword` | מילת חיפוש (אפשר כמה). מזהה תחיליות בעברית (*ל*מפתח, *ה*מפתח) ומילים נרדפות (python↔פייתון, developer↔מפתח/מתכנת) |
| `--all` | כל המילים חייבות להופיע (ברירת המחדל: לפחות אחת) |
| `--title-only` | חיפוש בכותרת בלבד |
| `-x/--exclude` | פסילת משרות שמכילות מילה |
| `-l/--location` | עיר או אזור בעברית או באנגלית: `מרכז`, `שרון`, `גוש דן`, `צפון`, `דרום`, `ירושלים והסביבה`, `שפלה`, `Haifa`, `remote` |
| `--remote` | רק עבודה מהבית או היברידית |
| `-t/--type` | `מלאה` / `חלקית` / `סטודנט` / `משמרות` / `פרילנס` / `התמחות` |
| `-c/--company`, `--exclude-company` | סינון חברות (למשל פסילת חברות השמה) |
| `-d/--days` | פורסם ב-X הימים האחרונים |
| `--min-salary` | שכר חודשי מינימלי. שכר לשעה מומר להערכה חודשית. משרות בלי שכר מפורסם לא נפסלות |
| `--max-exp` | מקסימום שנות ניסיון נדרשות (מחולץ מהטקסט: "3+ years", "4 שנות ניסיון", "ניסיון של שנתיים") |
| `-s/--source` | הגבלה לאתרים מסוימים |
| `--pages` | כמה עמודי תוצאות לסרוק בכל אתר |
| `-f/--format` | `table` / `json` / `csv` |

### API

- `GET /api/search?q=python,backend&location=מרכז&days=7&live=true` (`live=false` מחפש במאגר המקומי)
- `POST /api/jobs/{uid}/status/{saved|applied|hidden}`
- `GET /api/sources`

## הוספת אתר חדש

יוצרים מחלקה שיורשת מ-`Source` ב-`jobsearch_il/sources/`, מממשים `search(criteria)` שמחזירה אובייקטי `Job`,
ורושמים אותה ב-`SOURCES` ב-`jobsearch_il/sources/__init__.py`. כדאי לשים את הפענוח בפונקציה נפרדת ולבדוק אותה מול fixture ב-`tests/`.

## הערות חשובות

- **אתרים משנים מבנה.** הסלקטורים של AllJobs ו-JobMaster וה-endpoint של דרושים מבוססים על המבנה המוכר של האתרים
  ונבדקים מול fixtures. אם אתר מחזיר 0 תוצאות, מריצים עם `-v` ומעדכנים את הסלקטורים בקובץ של אותו מקור.
  ה-API-ים של Comeet, Greenhouse ו-Lever יציבים בהרבה.
- **הגנות בוטים.** חלק מהאתרים (בעיקר LinkedIn) מגבילים קצב או חוסמים סריקה. הכלי שומר על השהייה בין בקשות
  (`http.min_delay`), ואפשר להפעיל `respect_robots: true`.
- **תנאי שימוש.** הכלי מיועד לשימוש אישי. האחריות לעמוד בתנאי השימוש של כל אתר היא על המשתמש.

## פיתוח

```bash
pip install -e '.[dev,web]'
pytest
```
