"""Normalization helpers shared by the validation rules and (later) the cleaning step.

Keeping them in one module guarantees that what validation *counts* as fixable is
exactly what cleaning *fixes*.
"""

from __future__ import annotations

import re

import pandas as pd

from .config import SOURCES

# Known spelling variants seen in exports, mapped to the canonical source name.
SOURCE_VARIANTS: dict[str, str] = {
    "linkedin": "LinkedIn",
    "linked in": "LinkedIn",
    "occ": "OCC",
    "occ mundial": "OCC",
    "indeed": "Indeed",
    "referral": "Referral",
    "referido": "Referral",
    "computrabajo": "Computrabajo",
    "career site": "Career site",
    "careers page": "Career site",
}

_APP_REF = re.compile(r"^APP-?(\d{5})$")


def normalize_source(value: object) -> str | None:
    """Map a raw source label to its canonical name; None if it cannot be mapped."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if stripped in SOURCES:
        return stripped
    return SOURCE_VARIANTS.get(" ".join(stripped.lower().split()))


def normalize_application_ref(value: object) -> str | None:
    """Normalize a CRM application reference to the canonical 'APP-00000' format.

    Handles case, surrounding whitespace and a missing hyphen. Returns None when the
    value cannot be interpreted as an application id at all.
    """
    if not isinstance(value, str):
        return None
    match = _APP_REF.match(value.strip().upper())
    return f"APP-{match.group(1)}" if match else None


def normalize_sources(series: pd.Series) -> pd.Series:
    return series.map(normalize_source)


def normalize_application_refs(series: pd.Series) -> pd.Series:
    return series.map(normalize_application_ref)
