"""
FUB suppression check for relaunch mail batches.

Matches property owners to Ben-assigned FUB contacts (name + city), then
holds send when the match carries #NeverMail or Do Not Contact.

Fail closed: any FUB API error on an otherwise-sendable row becomes
HELD_SUPPRESSED. Below high-confidence matches are flagged for human
review and are not auto-decided.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools.fub import get_contact_by_id, search_contacts

SUPPRESSION_TAGS = frozenset({"#NeverMail", "Do Not Contact"})


@dataclass(frozen=True)
class SuppressionOutcome:
    """Result of one property-row FUB suppression check."""

    hold: bool
    reason: str
    contact_id: str | None = None
    confidence: str = "none"  # high | low | none | error
    review: bool = False


def _norm(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def _owner_name(row: dict[str, str]) -> tuple[str, str]:
    first = (row.get("public.owner1FirstName") or row.get("owner1FirstName") or "").strip()
    last = (row.get("public.owner1LastName") or row.get("owner1LastName") or "").strip()
    return first, last


def _listing_city(row: dict[str, str]) -> str:
    return (
        row.get("listing.address.city")
        or row.get("public.address.city")
        or ""
    ).strip()


def _listing_street(row: dict[str, str]) -> str:
    return (
        row.get("listing.address.unparsedAddress")
        or row.get("public.address.address")
        or ""
    ).strip()


def _contact_cities(person: dict[str, Any]) -> list[str]:
    cities: list[str] = []
    for addr in person.get("addresses") or []:
        if not isinstance(addr, dict):
            continue
        city = (addr.get("city") or "").strip()
        if city:
            cities.append(city)
    return cities


def _contact_streets(person: dict[str, Any]) -> list[str]:
    streets: list[str] = []
    for addr in person.get("addresses") or []:
        if not isinstance(addr, dict):
            continue
        street = (addr.get("street") or addr.get("address") or "").strip()
        if street:
            streets.append(street)
    return streets


def _name_matches(person: dict[str, Any], first: str, last: str) -> bool:
    p_first = _norm(str(person.get("firstName") or ""))
    p_last = _norm(str(person.get("lastName") or ""))
    return p_first == _norm(first) and p_last == _norm(last)


def _city_matches(person: dict[str, Any], city: str) -> bool:
    if not city:
        return False
    target = _norm(city)
    return any(_norm(c) == target for c in _contact_cities(person))


def _street_matches(person: dict[str, Any], street: str) -> bool:
    if not street:
        return False
    # Compare first token group (house number + street) casefold containment.
    needle = _norm(street.split(",")[0])
    if not needle:
        return False
    for candidate in _contact_streets(person):
        hay = _norm(candidate)
        if needle in hay or hay in needle:
            return True
    return False


def _tags_of(person: dict[str, Any]) -> set[str]:
    raw = person.get("tags") or []
    if not isinstance(raw, list):
        return set()
    return {str(t).strip() for t in raw if str(t).strip()}


def _has_suppression_tag(person: dict[str, Any]) -> list[str]:
    tags = _tags_of(person)
    return sorted(tags & SUPPRESSION_TAGS)


def _candidates_from_search(results: Any, first: str, last: str) -> list[dict[str, Any]]:
    """Normalize search_contacts return into a list of name-matching people."""
    if isinstance(results, dict):
        primary = results.get("primary") or {}
        people = [primary] + [
            {"id": d.get("id"), "firstName": "", "lastName": ""}
            for d in (results.get("duplicates_found") or [])
        ]
        # Reload full records for duplicate summaries (id only).
        full: list[dict[str, Any]] = []
        for person in people:
            cid = str(person.get("id") or "")
            if not cid:
                continue
            full.append(get_contact_by_id(cid))
        if results.get("disambiguation_required"):
            # Ambiguous active duplicates — not high confidence.
            return full
        return [p for p in full if _name_matches(p, first, last)]

    if isinstance(results, list):
        return [p for p in results if _name_matches(p, first, last)]
    return []


def resolve_match(row: dict[str, str]) -> SuppressionOutcome:
    """
    Attempt a high-confidence FUB match for the property owner.

    High confidence requires a single Ben-assigned name match that also
    matches listing city (or street). Anything weaker is review-only.
    """
    first, last = _owner_name(row)
    if not first:
        return SuppressionOutcome(
            hold=False,
            reason="no_owner_first_name",
            confidence="none",
        )

    query = f"{first} {last}".strip()
    city = _listing_city(row)
    street = _listing_street(row)

    try:
        results = search_contacts(query, limit=25)
        if isinstance(results, dict) and results.get("disambiguation_required"):
            primary = results.get("primary") or {}
            cid = str(primary.get("id") or "") or None
            return SuppressionOutcome(
                hold=False,
                reason="fub_match_ambiguous_disambiguation_required",
                contact_id=cid,
                confidence="low",
                review=True,
            )

        name_matches = _candidates_from_search(results, first, last)
        if not name_matches:
            return SuppressionOutcome(
                hold=False,
                reason="fub_no_match",
                confidence="none",
            )

        # Prefer city-confirmed matches; street match also qualifies.
        confirmed: list[dict[str, Any]] = []
        for person in name_matches:
            # search_contacts may return thin list rows — hydrate for addresses/tags.
            full = get_contact_by_id(str(person.get("id")))
            if _city_matches(full, city) or _street_matches(full, street):
                confirmed.append(full)

        if len(confirmed) == 1:
            person = confirmed[0]
            cid = str(person.get("id"))
            suppressed = _has_suppression_tag(person)
            if suppressed:
                return SuppressionOutcome(
                    hold=True,
                    reason=f"suppression_tags={','.join(suppressed)} contact_id={cid}",
                    contact_id=cid,
                    confidence="high",
                )
            return SuppressionOutcome(
                hold=False,
                reason=f"fub_match_clear contact_id={cid}",
                contact_id=cid,
                confidence="high",
            )

        if len(confirmed) > 1:
            ids = ",".join(str(p.get("id")) for p in confirmed)
            return SuppressionOutcome(
                hold=False,
                reason=f"fub_match_ambiguous_multi_city ids={ids}",
                confidence="low",
                review=True,
            )

        # Name match(es) but no city/street confirmation — do not auto-decide.
        ids = ",".join(str(p.get("id")) for p in name_matches)
        return SuppressionOutcome(
            hold=False,
            reason=f"fub_match_low_confidence_no_city ids={ids}",
            contact_id=str(name_matches[0].get("id")) if len(name_matches) == 1 else None,
            confidence="low",
            review=True,
        )
    except Exception as exc:
        return SuppressionOutcome(
            hold=True,
            reason=f"fub_error:{exc}",
            confidence="error",
        )


def check_row_suppression(row: dict[str, str]) -> SuppressionOutcome:
    """Public entry: fail-closed suppression decision for one CSV row."""
    return resolve_match(row)
