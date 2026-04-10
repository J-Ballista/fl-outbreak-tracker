"""
NLP signal extractor
====================
Extracts disease names, Florida county names, and case counts from free text
(news article titles + bodies).

Uses spaCy en_core_web_sm for:
  - GPE (geo-political entity) recognition → county / city resolution
  - PhraseMatcher for disease keyword matching (more robust than naive substring)

Regex is kept for case count extraction (spaCy doesn't model numeric patterns
like "17 cases" reliably).

Return value of extract_signals():
    List of dicts, may be empty if nothing relevant found.
    Each dict has:
        county_fips   : str | None
        disease_id    : int | None   (resolved against DISEASE_ID_MAP)
        case_count    : int | None
        confidence    : float        (0.0–1.0)
        notes         : str | None
"""

from __future__ import annotations

import re
from functools import lru_cache

import spacy
from spacy.matcher import PhraseMatcher

# ---------------------------------------------------------------------------
# Static reference tables
# (kept here so the classifier is self-contained; keep in sync with DB seed)
# ---------------------------------------------------------------------------

# county name (lowercase) → FIPS code
COUNTY_FIPS_MAP: dict[str, str] = {
    "alachua": "12001", "baker": "12003", "bay": "12005", "bradford": "12007",
    "brevard": "12009", "broward": "12011", "calhoun": "12013", "charlotte": "12015",
    "citrus": "12017", "clay": "12019", "collier": "12021", "columbia": "12023",
    "desoto": "12027", "dixie": "12029", "duval": "12031", "escambia": "12033",
    "flagler": "12035", "franklin": "12037", "gadsden": "12039", "gilchrist": "12041",
    "glades": "12043", "gulf": "12045", "hamilton": "12047", "hardee": "12049",
    "hendry": "12051", "hernando": "12053", "highlands": "12055",
    "hillsborough": "12057", "holmes": "12059", "indian river": "12061",
    "jackson": "12063", "jefferson": "12065", "lafayette": "12067", "lake": "12069",
    "lee": "12071", "leon": "12073", "levy": "12075", "liberty": "12077",
    "madison": "12079", "manatee": "12081", "marion": "12083", "martin": "12085",
    "miami-dade": "12086", "miami dade": "12086", "monroe": "12087",
    "nassau": "12089", "okaloosa": "12091", "okeechobee": "12093",
    "orange": "12095", "osceola": "12097", "palm beach": "12099",
    "pasco": "12101", "pinellas": "12103", "polk": "12105", "putnam": "12107",
    "st. johns": "12109", "saint johns": "12109", "st johns": "12109",
    "st. lucie": "12111", "saint lucie": "12111", "st lucie": "12111",
    "santa rosa": "12113", "sarasota": "12115", "seminole": "12117",
    "sumter": "12119", "suwannee": "12121", "taylor": "12123", "union": "12125",
    "volusia": "12127", "wakulla": "12129", "walton": "12131",
    "washington": "12133",
}

# Common city → county FIPS (for when county isn't named directly)
CITY_TO_FIPS: dict[str, str] = {
    "miami": "12086", "fort lauderdale": "12011", "boca raton": "12099",
    "west palm beach": "12099", "orlando": "12095", "tampa": "12057",
    "st. petersburg": "12103", "saint petersburg": "12103",
    "jacksonville": "12031", "tallahassee": "12073", "gainesville": "12001",
    "pensacola": "12033", "sarasota": "12115", "fort myers": "12071",
    "naples": "12021", "daytona beach": "12127", "clearwater": "12103",
    "cape coral": "12071", "coral springs": "12011", "pompano beach": "12011",
    "hollywood": "12011", "miramar": "12011", "hialeah": "12086",
    "kissimmee": "12097", "ocala": "12083", "deltona": "12127",
    "melbourne": "12009", "palm bay": "12009", "lakeland": "12105",
}

# disease keyword (lowercase) → disease name (matches diseases.name in DB)
DISEASE_KEYWORD_MAP: dict[str, str] = {
    "measles": "Measles",
    "mumps": "Mumps",
    "rubella": "Rubella", "german measles": "Rubella",
    "pertussis": "Pertussis", "whooping cough": "Pertussis",
    "varicella": "Varicella", "chickenpox": "Varicella", "chicken pox": "Varicella",
    "hepatitis a": "Hepatitis A",
    "hepatitis b": "Hepatitis B",
    "meningococcal": "Meningococcal Disease", "meningitis": "Meningococcal Disease",
    "haemophilus influenzae": "Haemophilus Influenzae", "hib": "Haemophilus Influenzae",
    "tetanus": "Tetanus", "lockjaw": "Tetanus",
    "diphtheria": "Diphtheria",
    "polio": "Poliomyelitis", "poliomyelitis": "Poliomyelitis",
}

# disease name → DB id (populated at first call from DB; kept as module-level
# cache so repeated calls don't re-query). Falls back to None if not cached yet.
_disease_name_to_id: dict[str, int] = {}


def set_disease_id_cache(mapping: dict[str, int]) -> None:
    """
    Pre-populate the disease name → id cache.
    Call this at app startup after loading diseases from the DB:

        from backend.nlp.classifier import set_disease_id_cache
        set_disease_id_cache({d.name: d.id for d in all_diseases})
    """
    _disease_name_to_id.update(mapping)


# ---------------------------------------------------------------------------
# spaCy model + PhraseMatcher (lazy-loaded once per process)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_nlp():
    """Load spaCy model and build PhraseMatcher. Cached after first call."""
    nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])

    # Re-enable only the NER component for GPE detection
    nlp.enable_pipe("ner")

    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    patterns = [nlp.make_doc(kw) for kw in DISEASE_KEYWORD_MAP]
    matcher.add("DISEASE", patterns)

    return nlp, matcher


# ---------------------------------------------------------------------------
# Regex patterns (case count extraction)
# ---------------------------------------------------------------------------

_COUNT_PATTERNS: list[re.Pattern] = [
    re.compile(r"(\d[\d,]*).{0,30}?\bcases?\b", re.I),
    re.compile(r"(\d[\d,]*)\s+(?:people|patients|residents|individuals).{0,20}?(?:infected|diagnosed|affected)", re.I),
    re.compile(r"(?:infected|diagnosed|sickened)\s+(\d[\d,]*)", re.I),
]

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "dozen": 12, "twenty": 20, "hundred": 100,
}


def _find_case_count(text: str) -> int | None:
    for pattern in _COUNT_PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except ValueError:
                pass
    m = re.search(
        r"\b(" + "|".join(_WORD_NUMBERS) + r")\b.{0,30}?\bcases?\b", text, re.I
    )
    if m:
        return _WORD_NUMBERS.get(m.group(1).lower())
    return None


# ---------------------------------------------------------------------------
# spaCy-based extraction helpers
# ---------------------------------------------------------------------------

def _find_disease_spacy(doc, matcher) -> tuple[str | None, int | None]:
    """
    Use PhraseMatcher to find the first disease keyword in the document.
    Returns (disease_name, disease_id_or_None).

    Multi-word phrases (e.g. "whooping cough", "hepatitis a") are matched
    correctly because PhraseMatcher respects token boundaries and the LOWER
    attribute normalises case.
    """
    matches = matcher(doc)
    if not matches:
        return None, None

    # Sort by span start; prefer longer matches if overlapping
    matches.sort(key=lambda m: (m[1], -(m[2] - m[1])))
    for _, start, end in matches:
        keyword = doc[start:end].text.lower()
        disease_name = DISEASE_KEYWORD_MAP.get(keyword)
        if disease_name:
            return disease_name, _disease_name_to_id.get(disease_name)

    return None, None


def _find_county_fips_spacy(doc) -> str | None:
    """
    Use spaCy NER GPE entities to extract location names, then resolve to
    a Florida county FIPS code.

    Falls back to the substring approach for multi-word county names that
    spaCy might tokenise differently (e.g. "Miami-Dade", "Palm Beach").
    """
    # Build a combined lower-cased text for the substring fallback
    lower_text = doc.text.lower()

    # 1. Try NER GPE entities first (most reliable for city names)
    for ent in doc.ents:
        if ent.label_ == "GPE":
            candidate = ent.text.lower().strip()
            if candidate in COUNTY_FIPS_MAP:
                return COUNTY_FIPS_MAP[candidate]
            if candidate in CITY_TO_FIPS:
                return CITY_TO_FIPS[candidate]

    # 2. Substring fallback: try multi-word county names (longest first)
    for name in sorted(COUNTY_FIPS_MAP, key=len, reverse=True):
        if name in lower_text:
            return COUNTY_FIPS_MAP[name]

    # 3. Substring fallback: city names
    for city in sorted(CITY_TO_FIPS, key=len, reverse=True):
        if city in lower_text:
            return CITY_TO_FIPS[city]

    return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def extract_signals(text: str) -> list[dict]:
    """
    Extract disease/county/case-count signals from free text.

    Returns a list of signal dicts (may be empty if nothing relevant found).
    Each dict has:
        county_fips   : str | None
        disease_id    : int | None
        case_count    : int | None
        confidence    : float
        notes         : str | None
    """
    if not text or not text.strip():
        return []

    nlp, matcher = _get_nlp()

    # Truncate to 50k chars to keep spaCy fast on large bodies
    doc = nlp(text[:50_000])

    disease_name, disease_id = _find_disease_spacy(doc, matcher)
    if disease_name is None:
        return []

    county_fips = _find_county_fips_spacy(doc)
    case_count = _find_case_count(text)

    # Confidence heuristic: reward each field found
    confidence = 0.4  # base: disease was found
    if county_fips:
        confidence += 0.3
    if case_count is not None:
        confidence += 0.2
    confidence = min(confidence, 0.95)

    notes_parts = [f"disease={disease_name!r}"]
    if county_fips:
        notes_parts.append(f"county_fips={county_fips!r}")
    if case_count is not None:
        notes_parts.append(f"case_count={case_count}")

    return [
        {
            "county_fips": county_fips,
            "disease_id": disease_id,
            "case_count": case_count,
            "confidence": round(confidence, 2),
            "notes": ", ".join(notes_parts),
        }
    ]
