"""Guards for the role dictionary (jobsearch_il/roles_data.py)."""

import collections

from jobsearch_il.cv import GENERIC_ROLE_WORDS, _title_roles
from jobsearch_il.roles_data import CREDENTIALS, FAMILIES, ROLES


def test_every_alias_belongs_to_one_role():
    counts = collections.Counter(a.lower() for r in ROLES for a in r[1:])
    assert [a for a, n in counts.items() if n > 1] == []


def test_roles_are_well_formed():
    names = [r[0] for r in ROLES]
    assert len(names) == len(set(names))
    for r in ROLES + CREDENTIALS:
        assert len(r) >= 2, r[0]
        for a in r[1:]:
            assert a == a.strip() and len(a) >= 2, (r[0], a)
            assert a.lower() == a or not a.isascii(), (r[0], a)  # English aliases are lower case


def test_generic_words_dont_hide_jobs_alone():
    # a title that is only a generic word must not count as a profession
    for w in ("מנהל", "עובד", "משרה", "manager", "specialist"):
        assert w not in {a for r in ROLES for a in r[1:]}, w
        assert _title_roles(w) == {}, w


def test_real_titles_are_recognized():
    cases = {
        "חשב/ת שכר לחברה מובילה": "payroll",           # longer match beats "חשב"
        "מורה לבית ספר יסודי": "teaching",              # "ספר" is not a barber here
        "פקיד/ת בק אופיס למחלקת שיווק": "office",       # department isn't the role
        "עורכ.ת דין במחלקה המשפטית": "law",             # gender mark with a dot + final letter
        "מאבטחים חמושים למוסדות": "security_guard",
        "טבח/ית למסעדה בתל אביב": "kitchen",
        "מכונאי/ת רכב כבד": "maintenance",
        "Senior Backend Engineer": "dev",
        "מנהל/ת עבודה מוסמך/ת": "construction_eng",
        "קלינאי/ת תקשורת לגני ילדים": "therapy",
    }
    for title, fam in cases.items():
        assert fam in _title_roles(title), (title, _title_roles(title))
    assert _title_roles("ראש צוות") == {}  # a position, not a profession
    assert None not in FAMILIES or all(r[0] for r in FAMILIES[None])
    assert "סוג" in GENERIC_ROLE_WORDS
