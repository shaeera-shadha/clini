"""Small fixed vocabularies used by deterministic checks and the not-mentioned checklist."""

from __future__ import annotations

import re

# Generic and common brand drug names likely in primary-care consultations (lowercase).
DRUG_NAMES: frozenset[str] = frozenset(
    [
        "paracetamol",
        "acetaminophen",
        "ibuprofen",
        "naproxen",
        "aspirin",
        "diclofenac",
        "codeine",
        "tramadol",
        "morphine",
        "amoxicillin",
        "augmentin",
        "co-amoxiclav",
        "azithromycin",
        "clarithromycin",
        "doxycycline",
        "cefalexin",
        "ciprofloxacin",
        "metronidazole",
        "nitrofurantoin",
        "trimethoprim",
        "penicillin",
        "flucloxacillin",
        "cetirizine",
        "loratadine",
        "fexofenadine",
        "chlorphenamine",
        "salbutamol",
        "albuterol",
        "ventolin",
        "beclometasone",
        "budesonide",
        "fluticasone",
        "montelukast",
        "prednisolone",
        "prednisone",
        "hydrocortisone",
        "metformin",
        "gliclazide",
        "sitagliptin",
        "empagliflozin",
        "dapagliflozin",
        "insulin",
        "glargine",
        "lisinopril",
        "ramipril",
        "enalapril",
        "amlodipine",
        "losartan",
        "candesartan",
        "bisoprolol",
        "atenolol",
        "propranolol",
        "atorvastatin",
        "simvastatin",
        "rosuvastatin",
        "clopidogrel",
        "warfarin",
        "apixaban",
        "rivaroxaban",
        "furosemide",
        "bendroflumethiazide",
        "indapamide",
        "spironolactone",
        "digoxin",
        "nitroglycerin",
        "gtn",
        "omeprazole",
        "lansoprazole",
        "pantoprazole",
        "esomeprazole",
        "ranitidine",
        "famotidine",
        "gaviscon",
        "antacid",
        "buscopan",
        "hyoscine",
        "mebeverine",
        "loperamide",
        "lactulose",
        "senna",
        "ondansetron",
        "metoclopramide",
        "sertraline",
        "citalopram",
        "fluoxetine",
        "amitriptyline",
        "gabapentin",
        "pregabalin",
        "sumatriptan",
        "levothyroxine",
        "thyroxine",
        "emollient",
        "clotrimazole",
        "terbinafine",
        "miconazole",
        "aciclovir",
        "permethrin",
        "betamethasone",
        "mometasone",
        "ketoconazole",
        "isotretinoin",
    ]
)

RELATIVES = re.compile(
    r"\b(mother|mum|mom|father|dad|sister|brother|sibling|parent|parents|grandmother|"
    r"grandfather|grandparent|aunt|uncle|cousin|son|daughter|family)\b",
    re.IGNORECASE,
)
ALLERGY = re.compile(r"\ballerg", re.IGNORECASE)
MEDICATION = re.compile(
    r"\b(medication|medicine|tablet|tablets|capsule|inhaler|cream|ointment|drops|injection|"
    r"prescribed|prescription|dose|mg|mcg|ml|units?|taking|takes|took|pills?)\b",
    re.IGNORECASE,
)
SOCIAL = re.compile(
    r"\b(smok\w*|cigarette\w*|tobacco|vap\w*|alcohol|drink\w*|units of alcohol|recreational|"
    r"occupation|works? as|exercise)\b",
    re.IGNORECASE,
)
ONSET = re.compile(
    r"\b(since|ago|for the (?:last|past)|over the (?:last|past)|started|began|came up|"
    r"yesterday|this morning|last night)\b",
    re.IGNORECASE,
)
SEVERITY = re.compile(
    r"\b(mild|mildly|moderate|severe|severely|slight|slightly|a little|a bit|very|worst|"
    r"out of (?:10|ten)|on a scale|severity)\b|\d+\s*/\s*10\b",
    re.IGNORECASE,
)
VITALS = re.compile(
    r"(\btemperature\b|\bblood pressure\b|\bbp\b|\bpulse\b|\bheart rate\b|\boxygen\b|"
    r"\bsaturation\b|\bspo2\b|\brespiratory rate\b|\bweight\b|\bbmi\b|mmhg|\bbpm\b|°)",
    re.IGNORECASE,
)


def mentions_drug(text: str) -> bool:
    words = re.findall(r"[a-z][a-z\-]+", text.lower())
    return any(w in DRUG_NAMES for w in words)
