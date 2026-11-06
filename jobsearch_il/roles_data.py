"""The role dictionary: job titles in Israel, grouped into families of related roles.

Each role is [display name, alias, alias, ...]. Aliases are matched as whole words (Hebrew prefixes like
ו/ה/ב/ל are allowed) after gender marks are removed from the text ("מנהל/ת" -> "מנהל"), so list the
masculine form and the feminine form a CV would use. Roles in the same family count as the same job when
deciding whether a job's title appears in a CV (a backend developer may take a full stack job).

Built from ~6,000 real job titles collected from Drushim, AllJobs and JobMaster (scripts/mine_titles.py).
Users can teach the system more roles from the app; those live in the database, not here.
"""

from __future__ import annotations

# family -> roles. Family None = a seniority/position word, not a profession (ignored when hiding jobs).
FAMILIES: dict[str | None, list[list[str]]] = {
    # ------------------------------------------------------------------ software
    "dev": [
        ["Full Stack Developer", "full stack", "fullstack", "full-stack", "פולסטאק", "פול סטאק", "מפתח פול סטאק",
         "מפתחת פול סטאק", "מפתח full stack", "מפתחת full stack"],
        ["Backend Developer", "backend developer", "backend engineer", "back-end developer", "back end developer",
         "server side", "מפתח backend", "מפתחת backend", "מפתח צד שרת", "מפתחת צד שרת"],
        ["Frontend Developer", "frontend developer", "frontend engineer", "front-end developer", "front end developer",
         "ui developer", "מפתח frontend", "מפתחת frontend", "מפתח צד לקוח", "מפתחת צד לקוח"],
        ["Software Engineer", "software engineer", "software developer", "programmer", "developer", "מהנדס תוכנה",
         "מהנדסת תוכנה", "מפתח תוכנה", "מפתחת תוכנה", "מתכנת", "מתכנתת", "מפתח", "מפתחת", "מתכנת מערכות"],
        ["Mobile Developer", "mobile developer", "android developer", "ios developer", "מפתח מובייל",
         "מפתחת מובייל", "מפתח אנדרואיד", "מפתח ios"],
        ["Game Developer", "game developer", "unity developer", "מפתח משחקים"],
        ["Algorithm Developer", "algorithm developer", "algorithm engineer", "מפתח אלגוריתמים", "מפתחת אלגוריתמים",
         "אלגוריתמאי", "אלגוריתמאית"],
    ],
    "embedded": [
        ["Embedded Engineer", "embedded", "firmware", "מהנדס embedded", "מפתח embedded", "תוכנה משובצת",
         "מפתח קושחה"],
    ],
    "devops": [
        ["DevOps Engineer", "devops", "site reliability", "sre", "platform engineer", "מהנדס devops", "דבאופס",
         "cloud engineer", "מהנדס ענן"],
    ],
    "qa": [
        ["QA Engineer", "qa engineer", "qa automation", "automation engineer", "software tester", "qa", "בודק תוכנה",
         "בודקת תוכנה", "בודק תוכנה ואוטומציה", "מהנדס בדיקות", "מהנדסת בדיקות", "מפתח אוטומציה",
         "מפתחת אוטומציה", "בודק qa", "בודקת qa"],
    ],
    "data": [
        ["Data Analyst", "data analyst", "bi analyst", "business analyst", "אנליסט נתונים", "אנליסטית נתונים",
         "אנליסט bi", "מנתח נתונים", "מנתחת נתונים", "אנליסט", "אנליסטית", "bi developer", "מפתח bi", "מפתחת bi"],
        ["Data Scientist", "data scientist", "machine learning engineer", "ml engineer", "ai engineer",
         "מדען נתונים", "מדענית נתונים", "חוקר ai", "חוקרת ai"],
        ["Data Engineer", "data engineer", "etl developer", "מהנדס נתונים", "מהנדסת נתונים", "מהנדס דאטה",
         "מהנדסת דאטה"],
        ["Financial Analyst", "financial analyst", "אנליסט פיננסי", "אנליסטית פיננסית", "אנליסט כלכלי",
         "כלכלן", "כלכלנית", "economist"],
    ],
    "it": [
        ["IT / System Administrator", "system administrator", "sysadmin", "it support", "help desk", "helpdesk",
         "it manager", "מנהל it", "מנהלת it", "מנהל רשת", "מנהלת רשת", "מנהל מערכות", "מנהלת מערכות",
         "תמיכה טכנית", "טכנאי מחשבים", "טכנאית מחשבים", "איש it", "אשת it", "מנהל מערכות מידע",
         "מנהלת מערכות מידע", "network engineer", "it infrastructure", "it business partner", "מהנדס רשתות", "מהנדסת רשתות", "dba", "מנהל בסיסי נתונים"],
        ["Systems Analyst", "systems analyst", "system analyst", "מנתח מערכות", "מנתחת מערכות", "מיישם",
         "מיישמת", "יישום מערכות", "מיישם מערכות", "מיישמת מערכות"],
    ],
    "security": [
        ["Security Engineer", "security engineer", "cyber security", "penetration tester", "security analyst",
         "soc analyst", "חוקר סייבר", "חוקרת סייבר", "אבטחת מידע", "סייבר", "מהנדס אבטחה", "אנליסט סייבר",
         "אנליסטית סייבר", "ממונה אבטחת מידע"],
    ],
    # ------------------------------------------------------------------ product & design
    "product": [
        ["Product Manager", "product manager", "product owner", "מנהל מוצר", "מנהלת מוצר"],
    ],
    "project": [
        ["Project Manager", "project manager", "program manager", "מנהל פרויקטים", "מנהלת פרויקטים",
         "מנהל פרויקט", "מנהלת פרויקט", "מנהל תוכנית", "מנהלת תוכנית", "pmo"],
    ],
    "design": [
        ["UX/UI Designer", "ux designer", "ui designer", "ux/ui", "ui/ux", "product designer", "מעצב ux",
         "מעצבת ux", "מעצב ui", "מעצבת ui", "מעצב מוצר", "מעצבת מוצר", "מעצב חווית משתמש", "מעצבת חווית משתמש"],
        ["Graphic Designer", "graphic designer", "מעצב גרפי", "מעצבת גרפית", "גרפיקאי", "גרפיקאית", "מעצב",
         "מעצבת", "מעצב גרפי ודיגיטל"],
        ["Interior Designer", "interior designer", "מעצב פנים", "מעצבת פנים", "הנדסאי עיצוב פנים"],
    ],
    "media": [
        ["Video Editor", "video editor", "motion designer", "עורך וידאו", "עורכת וידאו", "עורך סרטים",
         "עורכת סרטים", "אנימטור", "אנימטורית"],
        ["Photographer", "photographer", "צלם", "צלמת"],
        ["Journalist / Writer", "journalist", "reporter", "content writer", "copywriter", "עיתונאי", "עיתונאית", "קופירייטר", "קופירייטרית", "כותב תוכן", "כותבת תוכן", "עורך תוכן", "עורכת תוכן",
         "יוצר תוכן", "יוצרת תוכן", "עורך לשוני", "עורכת לשונית", "מתרגם", "מתרגמת", "translator"],
    ],
    # ------------------------------------------------------------------ engineering
    "hw": [
        ["Hardware / Electronics Engineer", "hardware engineer", "hardware", "electronics engineer", "board designer",
         "rf engineer", "asic", "vlsi", "fpga engineer", "מהנדס חומרה", "מהנדסת חומרה", "מהנדס אלקטרוניקה",
         "מהנדסת אלקטרוניקה", "הנדסאי אלקטרוניקה", "הנדסאית אלקטרוניקה", "מהנדס rf", "מתכנן מעגלים"],
        ["Electrical Engineer", "electrical engineer", "מהנדס חשמל", "מהנדסת חשמל", "הנדסאי חשמל",
         "הנדסאית חשמל", "מתכנן חשמל", "מתכננת חשמל"],
    ],
    "mech": [
        ["Mechanical Engineer", "mechanical engineer", "mechanical designer", "מהנדס מכונות", "מהנדסת מכונות",
         "הנדסאי מכונות", "הנדסאית מכונות", "מתכנן מכני", "מתכננת מכנית", "מהנדס מכני", "מהנדסת מכנית"],
    ],
    "systems_eng": [
        ["Systems Engineer", "systems engineer", "system engineer", "מהנדס מערכת", "מהנדסת מערכת",
         "מהנדס מערכות", "מהנדסת מערכות"],
    ],
    "industrial_eng": [
        ["Industrial Engineer", "industrial engineer", "process engineer", "manufacturing engineer",
         "מהנדס תעשייה וניהול", "מהנדסת תעשייה וניהול", "מהנדס תו\"נ", "הנדסאי תעשייה וניהול", "מהנדס תהליך",
         "מהנדסת תהליך", "מהנדס ייצור", "מהנדסת ייצור", "מהנדס שיטות", "מהנדסת שיטות", "מהנדס תפעול",
         "מהנדסת תפעול"],
    ],
    "quality": [
        ["Quality Engineer / Inspector", "quality engineer", "quality assurance", "quality control",
         "quality inspector", "qc", "מהנדס איכות", "מהנדסת איכות", "מבקר איכות", "מבקרת איכות", "בקר איכות",
         "בקרית איכות", "בודק איכות", "בודקת איכות", "מנהל איכות", "מנהלת איכות", "ממונה איכות",
         "אבטחת איכות", "הבטחת איכות", "רכז איכות", "רכזת איכות"],
    ],
    "chem_bio": [
        ["Chemical / Biomedical Engineer", "chemical engineer", "biomedical engineer", "מהנדס כימיה",
         "מהנדסת כימיה", "מהנדס ביו רפואי", "מהנדסת ביו רפואית", "מהנדס ביוטכנולוגיה", "מהנדס חומרים"],
        ["Chemist / Lab", "chemist", "lab technician", "laboratory", "microbiologist", "biologist", "researcher",
         "scientist", "כימאי", "כימאית", "לבורנט", "לבורנטית", "עובד מעבדה", "עובדת מעבדה", "טכנאי מעבדה",
         "טכנאית מעבדה", "מיקרוביולוג", "מיקרוביולוגית", "ביולוג", "ביולוגית", "חוקר", "חוקרת", "מדען",
         "מדענית", "אנליטיקאי", "אנליטיקאית"],
        ["Regulatory Affairs", "regulatory affairs", "רגולציה", "רגולטורי", "ממונה רגולציה", "מנהל רגולציה",
         "מנהלת רגולציה"],
    ],
    "construction_eng": [
        ["Civil / Construction Engineer", "civil engineer", "structural engineer", "site engineer",
         "מהנדס בניין", "מהנדסת בניין", "מהנדס אזרחי", "מהנדסת אזרחית", "מהנדס ביצוע", "מהנדסת ביצוע",
         "הנדסאי בניין", "הנדסאית בניין", "הנדסאי ביצוע", "מהנדס קונסטרוקציה", "מהנדסת קונסטרוקציה",
         "מפקח בנייה", "מפקחת בנייה", "bim", "מתאם bim", "מתאמת bim", "מהנדס תשתיות", "מהנדסת תשתיות", "מהנדס כבישים"],
        ["Site Manager", "site manager", "construction manager", "מנהל עבודה", "מנהלת עבודה", "מנהל עבודה מוסמך",
         "מנהל אתר", "מנהלת אתר", "מנהל פרויקט בנייה", "מנהל ביצוע", "מנהלת ביצוע"],
        ["Architect / Drafter", "architect", "drafter", "draftsman", "שרטט", "שרטטת", "הנדסאי אדריכלות",
         "הנדסאית אדריכלות", "מודד", "מודדת"],
    ],
    # ------------------------------------------------------------------ production & trades
    "production": [
        ["Production Worker / Operator", "production worker", "machine operator", "operator", "cnc operator",
         "עובד ייצור", "עובדת ייצור", "פועל ייצור", "פועלת ייצור", "מפעיל מכונה", "מפעילת מכונה",
         "מפעיל מכונות", "מפעילת מכונות", "מפעיל cnc", "מפעיל", "מפעילה", "עובד קו ייצור", "אורז",
         "אורזת", "עובד אריזה", "עובדת אריזה", "מרכיב", "מרכיבה", "עובד הרכבה", "עובדת הרכבה",
         "עיבוד שבבי", "חרט", "כרסם", "עובד מפעל", "עובדת מפעל"],
        ["Production Manager", "production manager", "plant manager", "מנהל ייצור", "מנהלת ייצור",
         "מנהל מפעל", "מנהלת מפעל", "מתכנן ייצור", "מתכננת ייצור", "מנהל תפעול", "מנהלת תפעול",
         "operations manager"],
    ],
    "maintenance": [
        ["Maintenance / Technician", "maintenance technician", "technician", "טכנאי", "טכנאית", "טכנאי אחזקה",
         "טכנאית אחזקה", "עובד אחזקה", "איש אחזקה", "אחזקה", "טכנאי שירות", "טכנאית שירות", "טכנאי מיזוג",
         "טכנאי מיזוג אוויר", "טכנאי קירור", "טכנאי מתח נמוך", "טכנאי מעליות", "מנהל אחזקה", "מנהלת אחזקה",
         "טכנאי תקשורת", "מתקין", "מתקינה", "מתקינים"],
        ["Mechanic", "mechanic", "מכונאי", "מכונאית", "מכונאי רכב", "מכונאי רכב כבד", "מכונאי צמ\"ה",
         "חשמלאי רכב", "פחח", "צבע רכב", "מכונאי מטוסים"],
    ],
    "trades": [
        ["Electrician", "electrician", "חשמלאי", "חשמלאית", "עוזר חשמלאי"],
        ["Plumber", "plumber", "אינסטלטור", "שרברב"],
        ["Welder / Metalworker", "welder", "רתך", "רתכת", "מסגר", "מסגרית", "פחח תעשייתי"],
        ["Carpenter", "carpenter", "נגר", "נגרית"],
        ["Construction Worker", "construction worker", "פועל בניין", "פועלי בניין", "טייח", "רצף", "צבעי",
         "שפכטלן", "גבסן", "טפסן", "ברזלן", "איטום", "עובד בניין"],
    ],
    # ------------------------------------------------------------------ logistics & driving
    "warehouse": [
        ["Warehouse Worker", "warehouse worker", "warehouse", "picker", "מחסן", "מחסנאי", "מחסנאית",
         "עובד מחסן", "עובדת מחסן", "מלקט", "מלקטת", "ליקוט", "סדרן מחסן", "עובד לוגיסטיקה", "מנהל מחסן",
         "מנהלת מחסן", "אחראי מחסן", "אחראית מחסן"],
    ],
    "logistics": [
        ["Logistics / Supply Chain", "logistics", "supply chain", "logistics coordinator", "לוגיסטיקה",
         "מתאם לוגיסטיקה", "מתאמת לוגיסטיקה", "רכז לוגיסטיקה", "רכזת לוגיסטיקה", "מנהל לוגיסטיקה",
         "מנהלת לוגיסטיקה", "שרשרת אספקה", "מתכנן אספקה", "מתכננת אספקה", "מתכנן רכש", "מתכננת רכש"],
        ["Procurement / Purchasing", "procurement", "purchasing", "buyer", "רכש", "קניין", "קניינית",
         "איש רכש", "אשת רכש", "מנהל רכש", "מנהלת רכש", "רכזת רכש", "רכז רכש", "נציג רכש"],
        ["Import / Export", "import", "export", "יבוא", "יצוא", "שילוח", "רכז יבוא", "רכזת יבוא",
         "מנהל יבוא", "מנהלת יבוא", "תיאום יבוא", "סחר חוץ"],
        ["Dispatcher", "dispatcher", "סדרן", "סדרנית", "סדרן עבודה", "סדרנית עבודה", "סדרן הפצה",
         "מתאם הפצה", "מתאמת הפצה"],
    ],
    "driving": [
        ["Driver", "driver", "delivery driver", "נהג", "נהגת", "נהג חלוקה", "נהגת חלוקה", "נהג רכב פרטי",
         "נהג מסחרי", "נהג הסעות", "נהגת הסעות", "נהג מונית"],
        ["Courier", "courier", "שליח", "שליחה", "חלוקת עיתונים", "מחלק עיתונים", "מחלקת עיתונים", "שליח אופנוע", "שליח רכב"],
    ],
    # ------------------------------------------------------------------ business & office
    "accounting": [
        ["Bookkeeper / Accountant", "bookkeeper", "accountant", "מנהלת חשבונות", "מנהל חשבונות",
         "הנהלת חשבונות", "מנה\"ח", "מנהלת חשבונות ראשית", "מנהל חשבונות ראשי"],
        ["Controller / Finance Manager", "controller", "financial controller", "finance manager", "cfo",
         "חשב", "חשבת", "סגן חשב", "ע. חשב", "מנהל כספים", "מנהלת כספים", "סמנכ\"ל כספים", "מנהל כספים ראשי"],
    ],
    "payroll": [
        ["Payroll", "payroll", "חשב שכר", "חשבת שכר", "חשבות שכר", "מנהל שכר", "מנהלת שכר", "רכז שכר",
         "רכזת שכר"],
    ],
    "collections": [
        ["Collections / Billing", "collections", "billing", "גבייה", "גביה", "גובה", "גובה כספים", "נציג גבייה", "נציגת גבייה",
         "פקיד גבייה", "פקידת גבייה", "מנהל גבייה", "מנהלת גבייה", "רכזת גבייה", "רכז גבייה"],
    ],
    "banking": [
        ["Bank Teller / Banker", "bank teller", "teller", "banker", "טלר", "טלרית", "בנקאי", "בנקאית",
         "בנקאי משכנתאות", "בנקאית משכנתאות", "יועץ משכנתאות", "יועצת משכנתאות", "פקיד בנק", "פקידת בנק",
         "בנקאי לקוחות", "בנקאית לקוחות"],
    ],
    "insurance": [
        ["Insurance (underwriting / claims)", "underwriter", "claims", "חתם", "חתמת", "מיישב תביעות",
         "מיישבת תביעות", "תביעות ביטוח", "מסלק תביעות", "מסלקת תביעות", "מנהל תיקי לקוחות",
         "מנהלת תיקי לקוחות", "נציג ביטוח", "נציגת ביטוח", "פקיד ביטוח", "פקידת ביטוח", "חוקר תביעות", "חוקרת תביעות"],
    ],
    "legal_office": [
        ["Legal Secretary / Paralegal", "legal secretary", "paralegal", "legal assistant", "מזכירה משפטית",
         "מזכיר משפטי", "עוזר משפטי", "עוזרת משפטית", "פרליגל"],
    ],
    "hr": [
        ["HR / Recruitment", "human resources", "hr manager", "hrbp", "recruiter", "talent acquisition",
         "משאבי אנוש", "מנהל משאבי אנוש", "מנהלת משאבי אנוש", "גיוס", "רכזת גיוס", "רכז גיוס",
         "מגייס", "מגייסת", "שותף עסקי משאבי אנוש", "רכזת משאבי אנוש", "רכז משאבי אנוש", "רכזת רווחה",
         "רכזת פרט", "רכז פרט"],
    ],
    "office": [
        ["Office / Administration", "office manager", "administrative assistant", "secretary", "back office",
         "backoffice", "מזכירה", "מזכיר", "מזכירה רפואית", "מזכירת", "אדמיניסטרציה",
         "אדמיניסטרטיבי", "אדמיניסטרטיבית", "מנהלת משרד", "מנהל משרד", "ניהול משרד", "רכזת", "רכז",
         "בק אופיס", "בק-אופיס", "פקיד", "פקידה", "פקידת", "עובד משרד", "עובדת משרד", "רפרנט", "רפרנטית",
         "תפעול", "עוזרת אישית", "עוזר אישי", "personal assistant"],
        ["Receptionist", "receptionist", "front desk", "פקיד קבלה", "פקידת קבלה", "מזכירת קבלה",
         "מזכיר קבלה", "דיילת קבלה", "קונסיירז'"],
        ["Data Entry", "data entry", "typist", "קלדנית", "קלדן", "הקלדה", "הקלדת נתונים", "קליטת נתונים"],
    ],
    # ------------------------------------------------------------------ sales, service, marketing
    "sales": [
        ["Sales", "sales representative", "sales rep", "salesperson", "account manager", "account executive",
         "business development", "bdr", "sdr", "מכירות", "איש מכירות", "אשת מכירות", "אנשי מכירות",
         "נציג מכירות", "נציגת מכירות", "סוכן מכירות", "סוכנת מכירות", "סוכן שטח", "סוכנת שטח",
         "מנהל מכירות", "מנהלת מכירות", "מנהל לקוחות", "מנהלת לקוחות", "מנהל תיק לקוח", "פיתוח עסקי",
         "מנהל פיתוח עסקי", "מנהלת פיתוח עסקי", "מפתח עסקים", "מפתחת עסקים", "business developer", "טלמרקטינג", "טלמרקטר", "טלמרקטרית", "מכירות טלפוניות",
         "נציג טלמרקטינג", "נציגת טלמרקטינג", "שימור לקוחות", "נציג שימור", "נציגת שימור"],
    ],
    "customer_service": [
        ["Customer Service", "customer service", "customer support", "customer success", "call center",
         "support representative", "שירות לקוחות", "נציג שירות", "נציגת שירות", "נציגי שירות", "מוקדן",
         "מוקדנית", "נציג תמיכה", "נציגת תמיכה", "נציג מוקד", "נציגת מוקד", "מפעיל מוקד", "מפעילת מוקד", "מנהל מוקד",
         "מנהלת מוקד", "קשרי לקוחות", "מנהל הצלחת לקוח", "מנהלת הצלחת לקוח"],
    ],
    "marketing": [
        ["Marketing", "marketing manager", "marketing", "digital marketing", "performance marketing",
         "growth", "ppc", "seo", "sem", "social media", "community manager", "brand manager", "שיווק",
         "מנהל שיווק", "מנהלת שיווק", "שיווק דיגיטלי", "מנהל דיגיטל", "מנהלת דיגיטל", "דיגיטל",
         "מנהל קמפיינים", "מנהלת קמפיינים", "מקדם אתרים", "מקדמת אתרים", "קידום אתרים", "מנהל סושיאל",
         "מנהלת סושיאל", "סושיאל", "מנהל מותג", "מנהלת מותג", "מנהל תוכן", "מנהלת תוכן", "יחסי ציבור",
         "דובר", "דוברת", "מנהל קהילה", "מנהלת קהילה", "סטרטג", "סטרטגית"],
    ],
    "real_estate": [
        ["Real Estate", "real estate", "property manager", "נדל\"ן", "נדלן", "יועץ נדל\"ן", "יועצת נדל\"ן",
         "מנהל נכסים", "מנהלת נכסים", "שיווק נדל\"ן", "איש נדל\"ן"],
    ],
    # ------------------------------------------------------------------ retail, food, hospitality
    "retail": [
        ["Retail Sales / Cashier", "cashier", "retail", "store associate", "sales associate", "מוכר", "מוכרת",
         "מוכרים", "קופאי", "קופאית", "קופאים", "סדרן סחורה", "סדרנית סחורה", "סדרן מדפים", "עובד חנות",
         "עובדת חנות", "דייל", "דיילת", "יועץ מכירות", "יועצת מכירות", "עובד סופר", "עובדת סופר"],
        ["Store Manager", "store manager", "branch manager", "מנהל סניף", "מנהלת סניף",
         "מנהל חנות", "מנהלת חנות", "סגן מנהל סניף", "סגנית מנהל סניף", "סגן מנהל חנות",
         "מנהל אזור", "מנהלת אזור", "מנהל מחלקה"],
    ],
    "kitchen": [
        ["Cook / Chef", "cook", "chef", "sous chef", "טבח", "טבחית", "טבחים", "שף", "סו שף", "עוזר טבח",
         "עוזרת טבח", "קונדיטור", "קונדיטורית", "אופה", "עובד מטבח", "עובדת מטבח", "שוטף כלים",
         "שוטפת כלים", "מנהל מטבח", "מנהלת מטבח"],
    ],
    "front_of_house": [
        ["Waiter / Bartender / Barista", "waiter", "waitress", "bartender", "barista", "host", "hostess",
         "מלצר", "מלצרית", "מלצרים", "ברמן", "ברמנית", "בריסטה", "מארח", "מארחת", "מנהל משמרת מסעדה",
         "מנהל מסעדה", "מנהלת מסעדה", "מנהל בית קפה", "עובד דלפק", "עובדת דלפק"],
    ],
    "hotel": [
        ["Hotel Staff", "housekeeping", "room attendant", "hotel", "חדרן", "חדרנית", "משק בית", "עובד מלון",
         "עובדת מלון", "פקיד קבלה במלון", "מנהל משמרת במלון", "בלבוי", "שוער"],
    ],
    "cleaning": [
        ["Cleaner", "cleaner", "cleaning", "janitor", "ניקיון", "עובד ניקיון", "עובדת ניקיון",
         "עובדי ניקיון", "מנקה", "מנקים", "מפקח ניקיון", "מפקחת ניקיון", "אב בית", "אם בית", "עובד תחזוקה"],
    ],
    "security_guard": [
        ["Security Guard", "security guard", "guard", "מאבטח", "מאבטחת", "מאבטחים", "מאבטח חמוש",
         "מאבטחים חמושים", "שומר", "שומרת", "סייר", "סיירת", "קב\"ט", "ממונה ביטחון", "מוקדן ביטחון",
         "מוקדנית ביטחון", "בודק ביטחוני", "בודקת ביטחונית", "שומרים", "קצין ביטחון", "קצינת ביטחון", "קצין בטחון", "מתשאל", "מתשאלת", "מאבטח מוסדות"],
    ],
    "beauty": [
        ["Hairdresser / Beautician", "hairdresser", "beautician", "barber", "makeup artist", "ספרית",
         "מעצב שיער", "מעצבת שיער", "קוסמטיקאי", "קוסמטיקאית", "מאפרת", "מאפר", "מניקוריסטית",
         "בונה ציפורניים", "בונת ציפורניים", "מעסה", "מטפל ספא", "מטפלת ספא"],
    ],
    # ------------------------------------------------------------------ health
    "nursing": [
        ["Nurse", "nurse", "registered nurse", "אח", "אחות", "אחיות", "אח מוסמך", "אחות מוסמכת", "אח מעשי",
         "אחות מעשית", "אחראית משמרת סיעוד", "סטודנט לסיעוד", "סטודנטית לסיעוד"],
    ],
    "care": [
        ["Caregiver", "caregiver", "nursing aide", "care worker", "מטפל", "מטפלת", "מטפלת סיעודית",
         "מטפל סיעודי", "כוח עזר", "כח עזר", "סניטר", "סניטרית", "מלווה", "עובד סוציאלי ביתי",
         "מטפלת לקשיש", "מטפלת בקשישים", "מטפלת במעון", "מטפלת לתינוקות", "מטפלת בגן", "בייביסיטר"],
    ],
    "medical": [
        ["Medical Doctor", "doctor", "physician", "רופא", "רופאה", "רופאים", "רופא משפחה", "רופאת משפחה",
         "רופא ילדים", "מתמחה ברפואה"],
        ["Pharmacist", "pharmacist", "רוקח", "רוקחת", "עוזר רוקח", "עוזרת רוקח"],
        ["Paramedic / Medic", "paramedic", "medic", "emt", "פרמדיק", "פרמדיקית", "חובש", "חובשת"],
        ["Dental", "dental assistant", "dental hygienist", "dentist", "סייעת שיניים", "סייע שיניים", "שיננית",
         "רופא שיניים", "רופאת שיניים", "טכנאי שיניים", "טכנאית שיניים"],
        ["Medical Technician", "radiographer", "x-ray technician", "טכנאי רנטגן", "טכנאית רנטגן",
         "טכנאי רפואי", "טכנאית רפואית", "אופטומטריסט", "אופטומטריסטית", "אופטיקאי", "אופטיקאית"],
    ],
    "therapy": [
        ["Therapist (paramedical)", "physiotherapist", "occupational therapist", "speech therapist",
         "dietitian", "פיזיותרפיסט", "פיזיותרפיסטית", "מרפא בעיסוק", "מרפאה בעיסוק", "קלינאי תקשורת",
         "קלינאית תקשורת", "דיאטן", "דיאטנית", "תזונאי", "תזונאית"],
        ["Psychologist / Social Worker", "psychologist", "social worker", "therapist", "פסיכולוג",
         "פסיכולוגית", "עובד סוציאלי", "עובדת סוציאלית", "עו\"ס", "מטפל רגשי", "מטפלת רגשית", "פסיכותרפיסט",
         "מטפל באומנות", "מטפלת באומנות"],
    ],
    "vet": [
        ["Veterinary", "veterinarian", "vet", "וטרינר", "וטרינרית", "עוזר וטרינר", "עוזרת וטרינר",
         "טכנאי וטרינרי", "מאלף כלבים"],
    ],
    # ------------------------------------------------------------------ education & social
    "teaching": [
        ["Teacher", "teacher", "tutor", "lecturer", "מורה", "מורים", "מורות", "מורה לאנגלית", "מורה למתמטיקה",
         "מורה מקצועית", "מרצה", "מרצים", "מורה פרטי", "מורה פרטית", "מורה מחליף", "מורה מחליפה",
         "מורה לחינוך מיוחד"],
        ["Kindergarten Teacher / Assistant", "kindergarten teacher", "preschool", "גננת", "גננות",
         "סייעת", "סייע", "סייעות", "סייעת גן", "סייעת לגן", "סייעת לגני ילדים", "סייעת בגן", "סייעת חינוך מיוחד",
         "סייעת כיתה", "סייע כיתה"],
        ["Instructor / Counselor", "instructor", "counselor", "coach", "trainer", "מדריך", "מדריכה", "מדריכים",
         "מדריכות", "מדריך כושר", "מדריכת כושר", "מאמן", "מאמנת", "יועץ חינוכי", "יועצת חינוכית", "יועץ תלמידים", "יועצת תלמידים", "מנהל בית ספר", "מנהלת בית ספר",
         "מדריך נוער", "מדריכת נוער", "רכז חינוך", "רכזת חינוך", "מנחה", "מנחה קבוצות"],
    ],
    # ------------------------------------------------------------------ law & licensed finance
    "law": [
        ["Lawyer", "lawyer", "attorney", "legal counsel", "general counsel", "עורך דין", "עורכת דין", "עו\"ד",
         "יועץ משפטי", "יועצת משפטית", "משפטן", "משפטנית", "מתמחה במשפטים"],
    ],
    "cpa": [
        ["CPA", "cpa", "certified public accountant", "רואה חשבון", "רואת חשבון", "רו\"ח", "מבקר פנים",
         "מבקרת פנים", "מבקר חשבונות", "auditor", "internal auditor", "יועץ מס", "יועצת מס", "tax advisor"],
    ],
    "investment": [
        ["Investment Advisor / Portfolio Manager", "investment advisor", "portfolio manager", "יועץ השקעות",
         "יועצת השקעות", "מנהל תיקים", "מנהלת תיקים", "מנהל תיקי השקעות", "יועץ פנסיוני", "יועצת פנסיונית",
         "מתכנן פיננסי", "מתכננת פיננסית", "סוכן ביטוח", "סוכנת ביטוח"],
    ],
    # ------------------------------------------------------------------ agriculture
    "agriculture": [
        ["Agriculture / Gardening", "farm worker", "gardener", "agronomist", "עובד חקלאות", "עובדת חקלאות",
         "חקלאות", "רפתן", "רפתנית", "לולן", "גנן", "גננית", "גינון", "אגרונום", "אגרונומית"],
    ],
    # ------------------------------------------------------------------ positions, not professions
    None: [
        ["Team Lead", "team lead", "team leader", "tech lead", "ראש צוות", "ראשת צוות", "מנהל צוות",
         "מנהלת צוות", "אחראי משמרת", "אחראית משמרת", "מנהל משמרת", "מנהלת משמרת", "סגן מנהל", "סגנית מנהל",
         "supervisor", "shift manager", "group manager", "vp", "סמנכ\"ל", "מנכ\"ל", "ceo", "cto", "director",
         "head of", "מנהל מחלקת", "מנהלת מחלקת", "מנהל תחום", "מנהלת תחום", "ראש תחום", "ראש מחלקה",
         "ראשת מחלקה", "מנהל אגף", "ראש אגף"],
    ],
}

# Licensed / protected titles: the CV must have the title itself, related knowledge isn't enough
# ("ידע במשפטים" is not "עורך דין"). [display name, aliases...]
CREDENTIALS: list[list[str]] = [
    ["עורך דין", "עורך דין", "עורכת דין", "עו\"ד", "עוה\"ד", "עריכת דין", "יועץ משפטי", "יועצת משפטית", "lawyer",
     "attorney", "advocate", "legal counsel"],
    ["רואה חשבון", "רואה חשבון", "רואת חשבון", "רו\"ח", "cpa", "certified public accountant"],
    ["רופא", "רופא", "רופאה", "רופא משפחה", "רופאת משפחה", "physician", "medical doctor"],
    ["רופא שיניים", "רופא שיניים", "רופאת שיניים", "dentist"],
    ["אחות מוסמכת", "אח מוסמך", "אחות מוסמכת", "registered nurse"],
    ["פסיכולוג", "פסיכולוג", "פסיכולוגית", "psychologist"],
    ["רוקח", "רוקח", "רוקחת", "pharmacist"],
    ["עובד סוציאלי", "עובד סוציאלי", "עובדת סוציאלית", "עו\"ס", "social worker"],
    ["פיזיותרפיסט", "פיזיותרפיסט", "פיזיותרפיסטית", "physiotherapist"],
    ["קלינאי תקשורת", "קלינאי תקשורת", "קלינאית תקשורת", "speech therapist"],
    ["מרפא בעיסוק", "מרפא בעיסוק", "מרפאה בעיסוק", "occupational therapist"],
    ["דיאטן", "דיאטן", "דיאטנית", "dietitian"],
    ["אופטומטריסט", "אופטומטריסט", "אופטומטריסטית", "optometrist"],
    ["וטרינר", "וטרינר", "וטרינרית", "veterinarian"],
    ["שמאי", "שמאי", "שמאית", "שמאי מקרקעין", "appraiser"],
    ["יועץ מס", "יועץ מס", "יועצת מס", "tax advisor"],
    ["יועץ השקעות", "יועץ השקעות", "יועצת השקעות", "מנהל תיקים", "מנהלת תיקים", "investment advisor",
     "portfolio manager"],
    ["סוכן ביטוח", "סוכן ביטוח", "סוכנת ביטוח", "רישיון סוכן ביטוח", "insurance agent"],
    ["מתווך נדל\"ן", "מתווך", "מתווכת", "מתווך נדל\"ן", "מתווכת נדל\"ן", "רישיון תיווך", "real estate broker"],
    ["עמיל מכס", "עמיל מכס", "עמילת מכס", "customs broker"],
    ["חשמלאי מוסמך", "חשמלאי מוסמך", "חשמלאי ראשי", "חשמלאי בכיר", "רישיון חשמלאי"],
    ["אדריכל", "אדריכל", "אדריכלית"],
    ["מהנדס בניין", "מהנדס בניין", "מהנדסת בניין", "מהנדס אזרחי", "מהנדסת אזרחית", "civil engineer"],
    ["מודד מוסמך", "מודד מוסמך", "מודדת מוסמכת"],
    ["נהג רכב כבד", "נהג משאית", "נהגת משאית", "נהג רכב כבד", "נהגת רכב כבד", "רישיון c", "רישיון ג",
     "רשיון c", "truck driver"],
    ["נהג אוטובוס", "נהג אוטובוס", "נהגת אוטובוס", "רישיון d", "רישיון ד", "רשיון d", "bus driver"],
    ["מלגזן", "מלגזן", "מלגזנית", "נהג מלגזה", "רישיון מלגזה", "רשיון מלגזה", "forklift"],
    ["מפעיל עגורן", "עגורנאי", "מפעיל עגורן", "מפעיל מנוף", "מנופאי"],
]

ROLES: list[list[str]] = [role for roles in FAMILIES.values() for role in roles]
ROLE_FAMILY: dict[str, str | None] = {role[0]: fam for fam, roles in FAMILIES.items() for role in roles}
