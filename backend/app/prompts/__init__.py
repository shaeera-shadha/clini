"""Versioned prompt files. Bump the version in PROMPT_VERSIONS when a prompt's behaviour changes."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Literal

PromptName = Literal[
    "extract", "verify", "baseline", "compare", "clinical_assess", "insurance_assess"
]

PROMPT_VERSIONS: dict[PromptName, str] = {
    "extract": "v1",
    "verify": "v1",
    "baseline": "v1",
    "compare": "v1",
    "clinical_assess": "v1",
    "insurance_assess": "v1",
}

_DIR = Path(__file__).resolve().parent


@cache
def load_prompt(name: PromptName) -> str:
    return (_DIR / f"{name}.{PROMPT_VERSIONS[name]}.md").read_text(encoding="utf-8").strip()
