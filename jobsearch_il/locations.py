"""Israeli cities and regions with Hebrew, English and Arabic aliases."""

from __future__ import annotations

import re
from functools import lru_cache

# canonical Hebrew city name -> aliases (English + common spellings)
CITIES: dict[str, list[str]] = {
    "תל אביב": ["tel aviv", "tel-aviv", "tel aviv-yafo", "tel aviv yafo", "תל אביב יפו", "תל-אביב", "ת\"א", "תא", "יפו", "jaffa", "tlv"],
    "ירושלים": ["jerusalem", "י-ם", "ים"],
    "חיפה": ["haifa"],
    "באר שבע": ["beer sheva", "be'er sheva", "beersheba", "beer-sheva", "ב\"ש"],
    "רמת גן": ["ramat gan", "ramat-gan", "ר\"ג", "בורסה"],
    "גבעתיים": ["givatayim", "givataim"],
    "בני ברק": ["bnei brak", "bne brak"],
    "פתח תקווה": ["petah tikva", "petach tikva", "petah tiqva", "פתח תקוה", "פ\"ת"],
    "הרצליה": ["herzliya", "herzlia", "הרצליה פיתוח"],
    "רעננה": ["raanana", "ra'anana"],
    "כפר סבא": ["kfar saba", "kfar sava"],
    "הוד השרון": ["hod hasharon", "hod ha-sharon"],
    "נתניה": ["netanya", "natanya"],
    "ראשון לציון": ["rishon lezion", "rishon le zion", "rishon letsiyon", "ראשל\"צ", "ראשון"],
    "חולון": ["holon"],
    "בת ים": ["bat yam"],
    "רחובות": ["rehovot"],
    "נס ציונה": ["ness ziona", "nes ziona"],
    "לוד": ["lod"],
    "רמלה": ["ramla"],
    "מודיעין": ["modiin", "modi'in", "מודיעין מכבים רעות"],
    "ראש העין": ["rosh haayin", "rosh ha'ayin"],
    "אור יהודה": ["or yehuda"],
    "יהוד": ["yehud", "יהוד מונוסון"],
    "airport city": ["איירפורט סיטי", "קריית שדה התעופה"],
    "כפר קאסם": ["kafr qasim", "kfar kasem"],
    "שוהם": ["shoham"],
    "אשדוד": ["ashdod"],
    "אשקלון": ["ashkelon"],
    "קריית גת": ["kiryat gat", "קרית גת"],
    "אילת": ["eilat"],
    "דימונה": ["dimona"],
    "ירוחם": ["yeruham"],
    "שדרות": ["sderot"],
    "נתיבות": ["netivot"],
    "אופקים": ["ofakim"],
    "יקנעם": ["yokneam", "yoqneam", "יקנעם עילית"],
    "נצרת": ["nazareth", "נוף הגליל", "nof hagalil"],
    "עכו": ["acre", "akko"],
    "נהריה": ["nahariya"],
    "כרמיאל": ["karmiel", "carmiel"],
    "טבריה": ["tiberias"],
    "עפולה": ["afula"],
    "קריות": ["krayot", "קריית ביאליק", "קריית מוצקין", "קריית אתא", "קריית ים"],
    "קיסריה": ["caesarea"],
    "חדרה": ["hadera"],
    "זכרון יעקב": ["zichron yaakov", "zikhron ya'akov"],
    "מגדל העמק": ["migdal haemek", "migdal ha'emek"],
    "תפן": ["tefen"],
    "בית שמש": ["beit shemesh", "bet shemesh"],
    "מבשרת ציון": ["mevaseret zion"],
    "מעלה אדומים": ["maale adumim", "ma'ale adumim"],
    "אריאל": ["ariel"],
}

# Arabic names of the cities above, and Arab towns (canonical Hebrew spelling as job sites write it)
ARABIC_CITY_ALIASES: dict[str, list[str]] = {
    "תל אביב": ["تل أبيب", "تل أبيب يافا", "يافا"], "ירושלים": ["القدس", "أورشليم"], "חיפה": ["حيفا"],
    "באר שבע": ["بئر السبع", "بير السبع"], "רמת גן": ["رمات غان"], "גבעתיים": ["جفعتايم"], "בני ברק": ["بني براك"],
    "פתח תקווה": ["بيتح تكفا", "بتاح تكفا"], "הרצליה": ["هرتسليا"], "רעננה": ["رعنانا"], "כפר סבא": ["كفار سابا"],
    "הוד השרון": ["هود هشارون"], "נתניה": ["نتانيا"], "ראשון לציון": ["ريشون لتسيون"], "חולון": ["حولون"],
    "בת ים": ["بات يام"], "רחובות": ["رحوفوت"], "נס ציונה": ["نيس تسيونا"], "לוד": ["اللد", "لد"],
    "רמלה": ["الرملة", "رملة"], "מודיעין": ["موديعين"], "ראש העין": ["روش هعاين"], "אור יהודה": ["أور يهودا"],
    "יהוד": ["يهود"], "כפר קאסם": ["كفر قاسم"], "שוהם": ["شوهام"], "אשדוד": ["أسدود"], "אשקלון": ["عسقلان"],
    "קריית גת": ["كريات غات"], "אילת": ["إيلات"], "דימונה": ["ديمونا"], "שדרות": ["سديروت"], "נתיבות": ["نتيفوت"],
    "אופקים": ["أوفاكيم"], "יקנעם": ["يوكنعام"], "נצרת": ["الناصرة", "نوف هجليل"], "עכו": ["عكا"],
    "נהריה": ["نهاريا"], "כרמיאל": ["كرمئيل"], "טבריה": ["طبريا"], "עפולה": ["العفولة"], "קריות": ["الكريوت"],
    "קיסריה": ["قيسارية"], "חדרה": ["الخضيرة"], "זכרון יעקב": ["زخرون يعكوف"], "מגדל העמק": ["مجدال هعيمق"],
    "בית שמש": ["بيت شيمش"], "מעלה אדומים": ["معاليه أدوميم"], "אריאל": ["أريئيل"],
}
ARAB_TOWNS: dict[str, tuple[str, list[str]]] = {  # town -> (region, aliases)
    "אום אל-פחם": ("צפון", ["אום אל פחם", "umm al-fahm", "umm al fahm", "أم الفحم"]),
    "ערערה": ("צפון", ["ar'ara", "arara", "عرعرة"]),
    "כפר קרע": ("צפון", ["kafr qara", "kfar kara", "كفر قرع"]),
    "סח'נין": ("צפון", ["סכנין", "sakhnin", "سخنين"]),
    "שפרעם": ("צפון", ["shefa-'amr", "shefa amr", "shfaram", "شفاعمرو", "شفا عمرو"]),
    "טמרה": ("צפון", ["tamra", "طمرة"]),
    "עראבה": ("צפון", ["arraba", "عرابة"]),
    "מגאר": ("צפון", ["maghar", "المغار"]),
    "כפר כנא": ("צפון", ["kafr kanna", "كفر كنا"]),
    "יפיע": ("צפון", ["yafa an-naseriyye", "يافة الناصرة"]),
    "ריינה": ("צפון", ["reineh", "الرينة"]),
    "דלית אל-כרמל": ("צפון", ["דלית אל כרמל", "daliyat al-karmel", "دالية الكرمل"]),
    "עספיא": ("צפון", ["isfiya", "عسفيا"]),
    "ירכא": ("צפון", ["yarka", "يركا"]),
    "מעלות תרשיחא": ("צפון", ["מעלות", "ma'alot", "معلوت ترشيحا", "ترشيحا"]),
    "טייבה": ("שרון", ["taibe", "tayibe", "الطيبة"]),
    "טירה": ("שרון", ["tira", "الطيرة"]),
    "קלנסווה": ("שרון", ["qalansawe", "قلنسوة"]),
    "באקה אל-גרבייה": ("שרון", ["באקה אל גרבייה", "baqa al-gharbiyye", "باقة الغربية"]),
    "ג'סר א-זרקא": ("שרון", ["ג'סר א זרקא", "jisr az-zarqa", "جسر الزرقاء"]),
    "ג'לג'וליה": ("מרכז", ["jaljulia", "جلجولية"]),
    "אבו גוש": ("ירושלים והסביבה", ["abu ghosh", "أبو غوش"]),
    "רהט": ("דרום", ["rahat", "رهط"]),
    "חורה": ("דרום", ["hura", "حورة"]),
    "לקיה": ("דרום", ["lakiya", "اللقية"]),
    "תל שבע": ("דרום", ["tel sheva", "تل السبع"]),
}
for _city, _ar in ARABIC_CITY_ALIASES.items():
    CITIES[_city].extend(_ar)
for _town, (_region, _aliases) in ARAB_TOWNS.items():
    CITIES[_town] = list(_aliases)

REGIONS: dict[str, list[str]] = {
    "מרכז": ["תל אביב", "רמת גן", "גבעתיים", "בני ברק", "פתח תקווה", "ראשון לציון", "חולון", "בת ים",
             "רחובות", "נס ציונה", "לוד", "רמלה", "מודיעין", "ראש העין", "אור יהודה", "יהוד", "airport city",
             "שוהם", "כפר קאסם", "הרצליה", "רעננה", "כפר סבא", "הוד השרון"],
    "שרון": ["הרצליה", "רעננה", "כפר סבא", "הוד השרון", "נתניה", "חדרה", "קיסריה"],
    "גוש דן": ["תל אביב", "רמת גן", "גבעתיים", "בני ברק", "חולון", "בת ים", "פתח תקווה", "אור יהודה"],
    "צפון": ["חיפה", "יקנעם", "נצרת", "עכו", "נהריה", "כרמיאל", "טבריה", "עפולה", "קריות", "מגדל העמק",
             "תפן", "זכרון יעקב"],
    "חיפה והקריות": ["חיפה", "קריות", "יקנעם"],
    "דרום": ["באר שבע", "אשדוד", "אשקלון", "קריית גת", "אילת", "דימונה", "ירוחם", "שדרות", "נתיבות", "אופקים"],
    "ירושלים והסביבה": ["ירושלים", "בית שמש", "מבשרת ציון", "מעלה אדומים"],
    "שפלה": ["רחובות", "נס ציונה", "ראשון לציון", "מודיעין", "לוד", "רמלה"],
    "יהודה ושומרון": ["אריאל", "מעלה אדומים"],
}

for _town, (_region, _aliases) in ARAB_TOWNS.items():
    REGIONS[_region].append(_town)

REGION_ALIASES: dict[str, list[str]] = {
    "מרכז": ["center", "central", "אזור המרכז", "المركز", "الوسط", "منطقة المركز"],
    "שרון": ["sharon", "השרון", "אזור השרון", "الشارون", "منطقة الشارون"],
    "גוש דן": ["gush dan", "غوش دان"],
    "צפון": ["north", "אזור הצפון", "הצפון", "الشمال", "منطقة الشمال"],
    "חיפה והקריות": ["haifa area", "haifa and krayot", "حيفا والكريوت", "منطقة حيفا"],
    "דרום": ["south", "אזור הדרום", "הדרום", "נגב", "negev", "الجنوب", "النقب", "منطقة الجنوب"],
    "ירושלים והסביבה": ["jerusalem area", "אזור ירושלים", "القدس ومحيطها", "منطقة القدس"],
    "שפלה": ["shfela", "shephelah", "השפלה", "الشفيلا"],
    "יהודה ושומרון": ["judea and samaria", "שומרון", "يهودا والسامرة"],
}

REMOTE_TERMS = ["من البيت", "عن بعد", "remote", "work from home", "wfh", "מהבית", "עבודה מהבית", "מרחוק", "עבודה מרחוק", "היברידי",
                "hybrid", "home office"]

ISRAEL_TERMS = ["israel", "ישראל", "il"]


_AR_NORM = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ـ": None})
_AR_MARKS = re.compile(r"[\u064B-\u0652]")  # Arabic short-vowel marks


@lru_cache(maxsize=8192)
def _norm(s: str) -> str:
    s = s.lower().replace("־", " ").replace("-", " ").replace("״", '"').replace("׳", "'")
    s = _AR_MARKS.sub("", s.translate(_AR_NORM))  # "تل أبيب" == "تل ابيب"
    return re.sub(r"\s+", " ", s).strip()


@lru_cache(maxsize=1024)
def city_terms(city: str) -> list[str]:
    for canon, aliases in CITIES.items():
        if _norm(city) == _norm(canon) or _norm(city) in (_norm(a) for a in aliases):
            return [canon, *aliases]
    return [city]


@lru_cache(maxsize=1024)
def expand_location(term: str) -> list[str]:
    """Expand a user location (city or region, any language) into all matching terms."""
    t = _norm(term)
    for region, cities in REGIONS.items():
        if t == _norm(region) or t in (_norm(a) for a in REGION_ALIASES.get(region, [])):
            out = [region, *REGION_ALIASES.get(region, [])]
            for c in cities:
                out.extend(city_terms(c))
            return out
    return city_terms(term)


@lru_cache(maxsize=8192)
def _short_pattern(n: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w]){re.escape(n)}(?![\w])")


def _contains(haystack: str, needle: str) -> bool:
    n = _norm(needle)
    if len(n) <= 3:  # short aliases (ים, תא, il) need whole-word matches
        return _short_pattern(n).search(haystack) is not None
    return n in haystack


def location_matches(job_location: str, wanted: list[str]) -> bool:
    if not wanted:
        return True
    hay = _norm(job_location or "")
    if not hay:
        return False
    return any(_contains(hay, term) for w in wanted for term in expand_location(w))


def is_israel_location(location: str) -> bool:
    hay = _norm(location or "")
    if any(_contains(hay, t) for t in ISRAEL_TERMS):
        return True
    return any(_contains(hay, t) for c in CITIES for t in city_terms(c))


def looks_remote(text: str) -> bool:
    hay = _norm(text or "")
    return any(_norm(t) in hay for t in REMOTE_TERMS)
