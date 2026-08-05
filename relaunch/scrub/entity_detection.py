"""Institutional entity detection for relaunch scrub and salutation logic."""

from __future__ import annotations

import re
from typing import Any

# Terms that must never appear in INSTITUTIONAL_KEYWORDS (trust-owned individuals
# are in-scope for this campaign; trust language alone is not entity evidence).
PROTECTED_OWNERSHIP_TERMS: tuple[str, ...] = (
    "trust",
    "living trust",
    "family trust",
    "revocable",
    "tr",
)

INSTITUTIONAL_KEYWORDS: tuple[str, ...] = (
    "llc",
    "inc",
    "corp",
    "corporation",
    "lp",
    "holdings",
    "district",
    "sanitary",
    "authority",
    "association",
    "hoa",
    "municipal",
    "redevelopment",
    "city of",
    "county of",
    "bank",
    "credit union",
    "foundation",
    "diocese",
    "church",
)

_OWNER_FIELDS_NO_FIRST_NAME = (
    "public.owner1LastName",
    "public.companyName",
    "public.owner2LastName",
    "public.owner2Company",
)


def _assert_keywords_safe() -> None:
    for keyword in INSTITUTIONAL_KEYWORDS:
        keyword_lower = keyword.lower()
        for protected in PROTECTED_OWNERSHIP_TERMS:
            if protected == "tr":
                if keyword_lower == "tr":
                    raise RuntimeError(
                        "INSTITUTIONAL_KEYWORDS must not contain protected ownership "
                        f"term {protected!r}; found in keyword {keyword!r}"
                    )
                continue
            if protected in keyword_lower:
                raise RuntimeError(
                    "INSTITUTIONAL_KEYWORDS must not contain protected ownership "
                    f"term {protected!r}; found in keyword {keyword!r}"
                )


_assert_keywords_safe()


def _field_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _contains_institutional_keyword(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    for keyword in INSTITUTIONAL_KEYWORDS:
        if " " in keyword:
            if keyword in lowered:
                return True
        elif re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return True
    return False


def is_true_entity(row: dict[str, Any]) -> bool | None:
    """
    Classify whether a REAPI row represents institutional ownership.

    Returns:
        False  — individual first name present on owner1 or owner2 (not an entity)
        True   — no individual first name and institutional keyword match
        None   — no individual first name and no keyword match (ambiguous)
    """
    owner1_first = _field_text(row, "public.owner1FirstName")
    owner2_first = _field_text(row, "public.owner2FirstName")

    if owner1_first or owner2_first:
        return False

    for key in _OWNER_FIELDS_NO_FIRST_NAME:
        if _contains_institutional_keyword(_field_text(row, key)):
            return True

    return None
