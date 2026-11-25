"""Deterministic normalization of numbers, durations, doses, drug names and polarity cues.

Used by the verification checks so that "5 days" matches "five days", "10mg" matches
"10 milligrams" and drug names match case-insensitively.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.lexicon import DRUG_NAMES

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}  # fmt: skip
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}  # fmt: skip
# "once" is left out: "once a day" vs "every morning" is a paraphrase, not a different number.
_MULTIPLES = {"twice": 2, "thrice": 3, "dozen": 12, "hundred": 100}
_VAGUE = {
    "a": 1.0, "an": 1.0, "a couple of": 2.0, "a couple": 2.0, "couple of": 2.0,
    "the next": 1.0, "the last": 1.0, "the past": 1.0,
}  # fmt: skip

_NUMBER_WORD = (
    r"(?:(?:"
    + "|".join(_TENS)
    + r")(?:[\s-](?:"
    + "|".join(k for k in _UNITS if k != "zero")
    + r"))?|"
    + "|".join(sorted(_UNITS, key=len, reverse=True))
    + r")"
)
_DIGITS = r"\d+(?:\.\d+)?"

_DURATION_UNITS = {
    "second": "second", "sec": "second", "minute": "minute", "min": "minute", "hour": "hour",
    "hr": "hour", "day": "day", "night": "night", "week": "week", "wk": "week",
    "fortnight": "fortnight", "month": "month", "year": "year", "yr": "year",
}  # fmt: skip
_DOSE_UNITS = {
    "mg": "mg", "milligram": "mg", "milligramme": "mg", "mcg": "mcg", "microgram": "mcg",
    "µg": "mcg", "ug": "mcg", "g": "g", "gram": "g", "gramme": "g", "ml": "ml",
    "millilitre": "ml", "milliliter": "ml", "l": "l", "litre": "l", "liter": "l", "unit": "unit",
    "iu": "unit", "puff": "puff", "tablet": "tablet", "tab": "tablet", "capsule": "capsule",
    "drop": "drop",
}  # fmt: skip

_QUANTITY_RE = re.compile(
    rf"(?<![\w.])(?P<num>{_DIGITS}|{_NUMBER_WORD}"
    r"|a couple of|a couple|couple of|a few|few|several|the next|the last|the past|an|a)"
    r"[\s-]*(?P<unit>[a-zµ]+)",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(
    rf"(?<![\w.]){_DIGITS}|\b{_NUMBER_WORD}\b|\b(?:twice|thrice)\b", re.IGNORECASE
)

NEGATION_CUES = re.compile(
    r"\b(no|not|never|none|nothing|nobody|without|denies|denied|deny|negative|absent|free of|"
    r"neither|nor)\b|n't\b|\b\w+-free\b",
    re.IGNORECASE,
)
HEDGE_CUES = re.compile(
    r"\b(maybe|might|perhaps|possibly|possible|probably|likely|unsure|not sure|i think|"
    r"i guess|i suppose|could be|may be|may have|sort of|kind of|wonder|seems?|"
    r"don't know|do not know|not certain|uncertain)\b",
    re.IGNORECASE,
)
_DRUG_SUFFIX = re.compile(
    r"\b[a-z]{3,}(?:cillin|mycin|cycline|floxacin|pril|sartan|olol|statin|prazole|azole|dipine|"
    r"tidine|triptan|oxetine|gliptin|gliflozin|semide|thiazide|vir|mab|parin|xaban)\b",
    re.IGNORECASE,
)


def word_to_number(token: str) -> float | None:
    t = token.lower().strip()
    if re.fullmatch(_DIGITS, t):
        return float(t)
    if t in _UNITS:
        return float(_UNITS[t])
    if t in _MULTIPLES:
        return float(_MULTIPLES[t])
    parts = re.split(r"[\s-]+", t)
    if parts[0] in _TENS:
        rest = _UNITS.get(parts[1], -1) if len(parts) == 2 else 0
        return float(_TENS[parts[0]] + rest) if rest >= 0 else None
    return None


# "six out of ten" / "6/10": the denominator is the scale the clinician asked about, not a finding.
_SCALE_DENOMINATOR = re.compile(r"(?:\bout of|/)\s*(?:10|ten)\b", re.IGNORECASE)


def numbers_in(text: str) -> set[float]:
    """Every explicit number (digits or number words) in the text, ignoring scale denominators."""
    found: set[float] = set()
    for match in _NUMBER_RE.finditer(_SCALE_DENOMINATOR.sub(" ", text)):
        value = word_to_number(match.group(0))
        if value is not None:
            found.add(value)
    return found


@dataclass(frozen=True)
class Quantity:
    value: float | None  # None = vague ("a few days")
    unit: str

    def render(self) -> str:
        amount = "a few" if self.value is None else f"{self.value:g}"
        plural = "" if self.value == 1 or self.unit in {"mg", "mcg", "g", "ml", "l"} else "s"
        return f"{amount} {self.unit}{plural}"


def _unit(raw: str, table: dict[str, str]) -> str | None:
    u = raw.lower()
    if u in table:
        return table[u]
    if u.endswith("s") and u[:-1] in table:
        return table[u[:-1]]
    return None


def _quantities(text: str, table: dict[str, str]) -> set[Quantity]:
    found: set[Quantity] = set()
    for match in _QUANTITY_RE.finditer(text):
        unit = _unit(match.group("unit"), table)
        if unit is None:
            continue
        raw = re.sub(r"\s+", " ", match.group("num").lower())
        if raw in {"a few", "few", "several"}:
            value: float | None = None
        elif raw in _VAGUE:
            value = _VAGUE[raw]
        else:
            value = word_to_number(raw)
            if value is None:
                continue
        found.add(Quantity(value, unit))
    return found


def standalone_numbers_in(text: str) -> set[float]:
    """Numbers that are not part of a duration or dose ("one week", "10 mg"): those are
    compared as whole quantities by the duration and dose checks instead."""
    tables = {**_DURATION_UNITS, **_DOSE_UNITS}

    def strip(match: re.Match[str]) -> str:
        return " " if _unit(match.group("unit"), tables) else match.group(0)

    return numbers_in(_QUANTITY_RE.sub(strip, text))


def durations_in(text: str) -> set[Quantity]:
    return _quantities(text, _DURATION_UNITS)


def doses_in(text: str) -> set[Quantity]:
    return _quantities(text, _DOSE_UNITS)


def drugs_in(text: str) -> set[str]:
    words = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z\-]+", text)}
    found = {w for w in words if w in DRUG_NAMES}
    found |= {m.group(0).lower() for m in _DRUG_SUFFIX.finditer(text)}
    return found


_STOPWORDS = frozenset(
    "the a an of and or to in on at for with from by as is are was were be been has have had "
    "his her their my your patient reports reported denies left right both side sides".split()
)


def content_stems(text: str) -> set[str]:
    words = re.findall(r"[a-z]{3,}", text.lower())
    return {w[:5] for w in words if w not in _STOPWORDS}


_CLAUSE_BREAK = re.compile(
    r"[,;:]|\b(?:but|although|though|however|whereas|except)\b", re.IGNORECASE
)


def negated_mentions(sentence: str, stems: set[str], window: int = 5) -> tuple[int, int]:
    """Count (mentions, negated mentions) of the stems. A mention is negated when a negation
    cue appears within `window` words before it in the same clause."""
    mentions = negated = 0
    for clause in _CLAUSE_BREAK.split(sentence.lower()):
        tokens = re.findall(r"[a-z']+", clause)
        for i, token in enumerate(tokens):
            if len(token) >= 3 and token[:5] in stems:
                mentions += 1
                if NEGATION_CUES.search(" ".join(tokens[max(0, i - window) : i])):
                    negated += 1
    return mentions, negated
