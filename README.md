# 🔎 jobsearch-il: מנוע חיפוש עבודה בישראל

חיפוש אחד שסורק את אתרי הדרושים בישראל, מאחד את התוצאות, מסיר כפילויות (גם משרה שפורסמה בכמה אתרים)
ומסנן לפי קריטריונים מדויקים. יש CLI, ממשק ווב בעברית ו-API.

## אתרים נתמכים

| מקור | שם | דרך החיבור |
|---|---|---|
| דרושים IL | `drushim` | ה-API של האתר (JSON): `webapi.drushim.co.il/api/jobs/search?SearchTerm=…&ssaen=1&isAA=true`, כולל תיאור מלא ודילוג על משרות שפגו |
| AllJobs | `alljobs` | דפי חיפוש לאורחים: `SearchResultsGuest.aspx?freetxt=…&page=N`, כרטיסי `div.job-box`, כולל מודעות באנגלית (`-ltr`) ומשרות בכמה ערים |
| JobMaster | `jobmaster` | דף החיפוש `/jobs/?q=…`, כרטיסי `article#misra<ID>`. בלי התחברות מוצג רק עמוד ראשון (כ-10 משרות) |
| LinkedIn | `linkedin` | חיפוש ציבורי לאורחים `/jobs-guest/…/seeMoreJobPostings/search`, מוגבל לישראל. LinkedIn חוסם לעתים קרובות כתובות IP של שרתים בענן |
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

# בדיקת חיבור לכל אתר: מחפש פעם אחת ומדווח כמה משרות התקבלו או מה השגיאה
jobsearch-il check

# ממשק ווב: http://127.0.0.1:8000
jobsearch-il serve
```

### ממשק הווב

- שורת חיפוש אחת למילים ולמיקום, וכפתורי אזור מהירים (מרכז, שרון, צפון, דרום, ירושלים, שפלה, מהבית)
- סריקה של כל האתרים במקביל, עם סטטוס חי לכל אתר: כמה משרות נסרקו, כמה התאימו, או מה השגיאה
- סינון מתקדם: היקף משרה, תאריך פרסום, שנות ניסיון, שכר, מילים וחברות לפסילה
- תוצאות מאוחדות בלי כפילויות, עם תג "חדש" למשרות שלא הופיעו בחיפוש קודם
- מיון וסינון מהיר בתוך התוצאות
- שמירה, סימון "הגשתי" והסתרה של משרות, ולשוניות "שמורות" ו"הגשתי"
- הדפדפן זוכר את החיפוש האחרון. מותאם לנייד ולמצב כהה

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
- `GET /api/search?status=saved` משרות ששמרתם (או `applied`)
- `GET /api/check` בדיקת חיבור לכל אתר
- `GET /api/sources`

## הוספת אתר חדש

יוצרים מחלקה שיורשת מ-`Source` ב-`jobsearch_il/sources/`, מממשים `search(criteria)` שמחזירה אובייקטי `Job`,
ורושמים אותה ב-`SOURCES` ב-`jobsearch_il/sources/__init__.py`. כדאי לשים את הפענוח בפונקציה נפרדת ולבדוק אותה מול fixture ב-`tests/`.

## הערות חשובות

- **אתרים משנים מבנה.** המבנה של כל אתר מתועד בראש הקובץ שלו ב-`jobsearch_il/sources/` ונבדק מול fixtures
  שנבנו מדפים אמיתיים. אם `jobsearch-il check` מראה 0 תוצאות לאתר, מעדכנים את הסלקטורים באותו קובץ.
  ה-API-ים של Comeet, Greenhouse ו-Lever יציבים בהרבה.
- **הגנות בוטים.** חלק מהאתרים (בעיקר LinkedIn) מגבילים קצב או חוסמים סריקה. הכלי שומר על השהייה בין בקשות
  (`http.min_delay`), ואפשר להפעיל `respect_robots: true`.
- **תנאי שימוש.** הכלי מיועד לשימוש אישי. האחריות לעמוד בתנאי השימוש של כל אתר היא על המשתמש.

## פיתוח

```bash
pip install -e '.[dev,web]'
pytest
```
