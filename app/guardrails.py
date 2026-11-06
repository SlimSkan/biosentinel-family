"""Safety checks applied to every AI-written explanation before a user sees it.

If any check fails, the app throws the AI text away and shows a pre-written,
reviewed template instead. The AI can make the text friendlier; it can never
make it less safe.

Checks
  1. numbers   - every percentage or "1 in N" must come from the risk engine
  2. directive - no telling people what to do about marriage or pregnancy
  3. diagnosis - a carrier result must never be described as having the disease
  4. length    - explanations stay short enough to read on a phone
  5. coverage  - every key fact and number of the reviewed text is still there
  6. gender    - Arabic: no addressing the reader as a woman unless the reviewed text does
                 (checks 1-4 catch what the AI ADDS; check 5 catches what it DROPS)
"""
import re

# Phrases that push a decision. Kept deliberately broad: a false alarm only
# means the user sees the template, which is always safe.
DIRECTIVE = [
    r"\bshould(n't| not)? (marry|get married|have (children|kids)|cancel|reconsider)",
    r"\b(do not|don't|must not|never) (marry|get married|have (children|kids))",
    r"\byou (must|have to|need to) (marry|cancel|terminate|end)",
    r"\b(terminate|abort|abortion)\b",
    r"\bcall off\b",
    r"\bnot (be )?compatible\b",
    r"يجب (عليكم|عليكما|عليك) (عدم|أن لا|ألا)",
    r"لا (تتزوج|تتزوجا|تتزوجوا|تنجبا|تنجبوا)",
    r"(إجهاض|إنهاء الحمل|إلغاء الزواج)",
    r"غير متوافق",
]

DIAGNOSIS = [
    r"\byou (have|suffer from|are (ill|sick) with)\b",
    r"\byou are (affected|diseased)\b",
    r"(أنت|أنتِ) مصاب",
    r"(أنتما|أنتم) مصاب",
]

MAX_WORDS = 220


def _num(x: float) -> float | int:
    """12.5 stays 12.5; 25.0 becomes 25 (so messages read naturally)."""
    x = round(x, 1)
    return int(x) if x == int(x) else x


def _percentages(text: str) -> set[float]:
    nums = set()
    # "25%", "12.5 %", "25 percent", Arabic "25٪", Arabic-Indic digits ٢٥ and decimal comma ١٢٫٥
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789."))
    for m in re.finditer(r"(\d{1,3}(?:[.,]\d+)?)\s*(%|٪|percent|per cent|بالمائة|في المائة)", text, re.I):
        nums.add(_num(float(m.group(1).replace(",", "."))))
    # "1 in 4", "one in eight" style -> convert to a percentage
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "eight": 8, "واحد": 1}
    for m in re.finditer(r"\b(\d+|one|two|three)\s+(in|out of)\s+(\d+|two|four|eight)\b", text, re.I):
        a = int(m.group(1)) if m.group(1).isdigit() else words[m.group(1).lower()]
        b = int(m.group(3)) if m.group(3).isdigit() else words[m.group(3).lower()]
        if b:
            nums.add(_num(100 * a / b))
    for m in re.finditer(r"(\d+)\s+من\s+(كل\s+)?(\d+)", text):
        if int(m.group(3)):
            nums.add(_num(100 * int(m.group(1)) / int(m.group(3))))
    return nums


_ARABIC_MARKS = re.compile(r"[ً-ْـ]")  # vowel marks (tashkeel) and tatweel
_ALEF = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي"})


def normalise(text: str) -> str:
    """Lower-case, and make Arabic spelling variants match: الأدوية == الادوية."""
    return _ARABIC_MARKS.sub("", text).translate(_ALEF).lower()


def missing_facts(text: str, facts: list[dict], lang: str) -> list[str]:
    """Ids of facts whose keywords are all absent from the text.

    Each fact is {"id", "say", "en": [keywords], "ar": [keywords]}; one keyword is
    enough. This is a coarse check: it proves a topic is mentioned, not that the
    sentence around it is right. Checks 1-3 and human review cover the rest.
    """
    norm = normalise(text)
    return [f["id"] for f in facts
            if not any(normalise(k) in norm for k in f[lang])]


def missing_numbers(text: str, reviewed: str) -> set[float]:
    """Numbers stated in the reviewed text that the rewrite left out."""
    return _percentages(reviewed) - _percentages(text)


# Arabic second-person feminine forms ("you" said to a woman). Checked on the raw
# text, because the kasra mark (ِ) that makes كِ feminine is removed by normalise().
FEMININE_AR = re.compile(r"أنتِ|كِ|تحملين|تعرفين|تحتاجين|ترغبين|تستطيعين|يمكنكِ")


def changes_gender(text: str, reviewed: str) -> bool:
    """True if the rewrite addresses a woman while the reviewed text did not.

    Arabic marks gender in "you". The reader's sex is unknown on most screens
    (a relative, a partner), so the reviewed texts use the general form. The
    woman-only X-linked text uses feminine forms, so it is the reference that decides.
    """
    return bool(FEMININE_AR.search(text)) and not FEMININE_AR.search(reviewed)


def check(text: str, allowed: set[float], facts: list[dict] | None = None,
          lang: str = "en", reviewed: str | None = None) -> list[str]:
    """Return a list of problems. An empty list means the text is safe to show.

    facts/reviewed are optional so that the reviewed templates themselves can be
    checked with the same function.
    """
    problems = []
    if facts:
        gone = missing_facts(text, facts, lang)
        if gone:
            problems.append(f"missing facts: {gone}")
    if reviewed:
        gone_nums = missing_numbers(text, reviewed)
        if gone_nums:
            problems.append(f"missing numbers: {sorted(gone_nums)}")
        if lang == "ar" and changes_gender(text, reviewed):
            problems.append("assumed the reader is a woman")
    bad = _percentages(text) - allowed
    if bad:
        problems.append(f"numbers not from risk engine: {sorted(bad)}")
    low = text.lower()
    for pat in DIRECTIVE:
        if re.search(pat, low):
            problems.append(f"directive language: /{pat}/")
            break
    for pat in DIAGNOSIS:
        if re.search(pat, low):
            problems.append(f"diagnosis language: /{pat}/")
            break
    if len(text.split()) > MAX_WORDS:
        problems.append("too long")
    if not text.strip():
        problems.append("empty")
    return problems
