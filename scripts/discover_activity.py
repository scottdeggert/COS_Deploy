#!/usr/bin/env python3
"""Read-only FUB activity discovery script.

Fetches raw JSON from activity-related endpoints for selected contacts.
Print only. No writes to FUB.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.fub_client import fub_get

ASSIGNED_TO_NAME = "Ben Olsen"
BEN_USER_ID = 1
SHOWING_HOMES_STAGE = "Showing homes"
APPOINTMENTS_FETCH_LIMIT = 100


def _assigned_to_name(person: dict[str, Any]) -> str | None:
    assigned = person.get("assignedTo")
    if assigned is None:
        return None
    if isinstance(assigned, dict):
        name = assigned.get("name")
        return str(name) if name is not None else None
    if isinstance(assigned, str):
        return assigned
    return None


def _print_header(title: str) -> None:
    line = "=" * 80
    print(line)
    print(title)
    print(line)


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=False, default=str))
    print()


def _appointment_matches_person(appointment: dict[str, Any], person_id: str) -> bool:
    for invitee in appointment.get("invitees", []):
        invitee_person_id = invitee.get("personId")
        if invitee_person_id is not None and str(invitee_person_id) == person_id:
            return True
    if appointment.get("personId") is not None:
        return str(appointment.get("personId")) == person_id
    return False


def discover_person(person_id: int | str, label: str = "") -> None:
    """Fetch and print raw activity JSON for one FUB personId."""
    person_id_str = str(person_id)
    title_suffix = f" ({label})" if label else ""
    _print_header(f"PERSON {person_id_str}{title_suffix}")

    person = fub_get(f"/people/{person_id_str}")
    assigned_to = _assigned_to_name(person)
    if assigned_to != ASSIGNED_TO_NAME:
        print(
            f"Refused: contact {person_id_str} is assigned to "
            f"{assigned_to or 'unknown'}, not {ASSIGNED_TO_NAME}. Skipping."
        )
        print()
        return

    _print_header(f"GET /v1/people/{person_id_str}")
    _print_json(person)

    _print_header(f"GET /v1/events?personId={person_id_str}")
    _print_json(fub_get("/events", params={"personId": person_id_str}))

    _print_header(f"GET /v1/notes?personId={person_id_str}")
    _print_json(fub_get("/notes", params={"personId": person_id_str}))

    _print_header(f"GET /v1/calls?personId={person_id_str}")
    _print_json(fub_get("/calls", params={"personId": person_id_str}))

    _print_header(f"GET /v1/textMessages?personId={person_id_str}")
    _print_json(fub_get("/textMessages", params={"personId": person_id_str}))

    _print_header(
        "GET /v1/appointments "
        f"(recent limit={APPOINTMENTS_FETCH_LIMIT}, filtered to personId={person_id_str})"
    )
    appointments_payload = fub_get(
        "/appointments",
        params={"limit": APPOINTMENTS_FETCH_LIMIT, "sort": "start", "order": "desc"},
    )
    appointments = appointments_payload.get("appointments", [])
    if not isinstance(appointments, list):
        appointments = []
    filtered_appointments = [
        appt for appt in appointments if _appointment_matches_person(appt, person_id_str)
    ]
    _print_json({"appointments": filtered_appointments})


def select_showing_homes_person_id() -> str:
    """Return the most recently active Ben Olsen contact in Showing homes stage."""
    payload = fub_get(
        "/people",
        params={
            "assignedUserId": BEN_USER_ID,
            "stage": SHOWING_HOMES_STAGE,
            "sort": "lastActivity",
            "order": "desc",
            "limit": 25,
        },
    )
    people = payload.get("people", [])
    if not isinstance(people, list):
        people = []

    for person in people:
        if _assigned_to_name(person) != ASSIGNED_TO_NAME:
            continue
        person_id = person.get("id")
        if person_id is not None:
            return str(person_id)

    raise RuntimeError(
        f"No contact found for assignedUserId={BEN_USER_ID} "
        f"and stage={SHOWING_HOMES_STAGE!r}"
    )


def main() -> None:
    if len(sys.argv) > 1:
        discover_person(sys.argv[1])
        return

    discover_person(32194, "Nicole Bellamy")
    discover_person(32195, "Henrik Thorenfeldt")

    dynamic_person_id = select_showing_homes_person_id()
    _print_header(f"DYNAMIC SELECTION: personId={dynamic_person_id} (Showing homes)")
    print()
    discover_person(dynamic_person_id, "Showing homes (dynamic)")


if __name__ == "__main__":
    main()
