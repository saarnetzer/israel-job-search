"""Israeli cities and regions with Hebrew/English aliases."""

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

REGION_ALIASES: dict[str, list[str]] = {
    "מרכז": ["center", "central", "אזור המרכז"],
    "שרון": ["sharon", "השרון", "אזור השרון"],
    "גוש דן": ["gush dan"],
    "צפון": ["north", "אזור הצפון", "הצפון"],
    "חיפה והקריות": ["haifa area", "haifa and krayot"],
    "דרום": ["south", "אזור הדרום", "הדרום", "נגב", "negev"],
    "ירושלים והסביבה": ["jerusalem area", "אזור ירושלים"],
    "שפלה": ["shfela", "shephelah", "השפלה"],
    "יהודה ושומרון": ["judea and samaria", "שומרון"],
}

REMOTE_TERMS = ["remote", "work from home", "wfh", "מהבית", "עבודה מהבית", "מרחוק", "עבודה מרחוק", "היברידי",
                "hybrid", "home office"]

ISRAEL_TERMS = ["israel", "ישראל", "il"]


@lru_cache(maxsize=8192)
def _norm(s: str) -> str:
    s = s.lower().replace("־", " ").replace("-", " ").replace("״", '"').replace("׳", "'")
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
