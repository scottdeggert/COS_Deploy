#!/usr/bin/env python3
"""Read-only audit: list Action Plan email steps and flag pre-meeting templates.

Uses services/fub_client.py for all FUB HTTP. Does not modify FUB data.
"""

from __future__ import annotations

import csv
import io
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.fub_client import fub_get

FLAG_TEMPLATE_ID = 165
SEQUENCES_DIR = _REPO_ROOT / "clients" / "ben-olsen" / "sequences"


def _paginate_list(path: str, list_key: str) -> list[dict]:
    """Fetch all pages from a FUB list endpoint."""
    items: list[dict] = []
    offset = 0
    limit = 100
    while True:
        payload = fub_get(path, params={"limit": limit, "offset": offset})
        batch = payload.get(list_key, [])
        items.extend(batch)
        total = payload.get("_metadata", {}).get("total", len(items))
        offset += limit
        if offset >= total or not batch:
            break
    return items


def _load_flag_names_from_sequences() -> set[str]:
    """Scan sequences/ once for pre-meeting or appointment template name hints."""
    flags: set[str] = set()
    if not SEQUENCES_DIR.is_dir():
        return flags

    pre_meeting_re = re.compile(
        r"pre[- ]meeting|appointment[- ]based|appointment template",
        re.IGNORECASE,
    )
    template_path_re = re.compile(
        r"(?:Template:\s*|templates/)([\w./-]+\.(?:html|md))",
        re.IGNORECASE,
    )

    for path in sorted(SEQUENCES_DIR.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not pre_meeting_re.search(text):
            continue
        for match in template_path_re.finditer(text):
            basename = Path(match.group(1)).stem.lower()
            flags.add(basename)
            flags.add(match.group(1).split("/")[-1].lower())

    return flags


def _build_template_name_index(template_names: dict[int, str]) -> dict[str, list[int]]:
    """Map lowercase template basename hints to template IDs."""
    index: dict[str, list[int]] = {}
    for tid, name in template_names.items():
        lower = name.lower()
        index.setdefault(lower, []).append(tid)
        slug = lower.split(" - ")[0].strip()
        index.setdefault(slug, []).append(tid)
    return index


def _is_flagged(
    template_id: int | None,
    template_name: str,
    flag_template_ids: set[int],
    flag_name_hints: set[str],
    name_index: dict[str, list[int]],
) -> bool:
    if template_id is not None and template_id in flag_template_ids:
        return True
    lower_name = template_name.lower()
    if "seller-programs-overview" in lower_name:
        return True
    for hint in flag_name_hints:
        if hint in lower_name:
            return True
        for tid in name_index.get(hint, []):
            if tid == template_id:
                return True
    return False


def main() -> None:
    sequence_hints = _load_flag_names_from_sequences()
    flag_template_ids = {FLAG_TEMPLATE_ID}

    templates = _paginate_list("/templates", "templates")
    template_names: dict[int, str] = {t["id"]: t.get("name", "") for t in templates}
    name_index = _build_template_name_index(template_names)

    plans = _paginate_list("/actionPlans", "actionPlans")

    rows: list[tuple] = []
    for plan in sorted(plans, key=lambda p: p.get("id", 0)):
        plan_id = plan["id"]
        plan_name = plan.get("name", "")
        detail = fub_get(f"/actionPlans/{plan_id}")
        steps = detail.get("steps", [])
        for step in sorted(steps, key=lambda s: s.get("position", 0)):
            template_id = step.get("emailTemplateId")
            if template_id is None:
                continue
            template_name = template_names.get(template_id, "")
            if not template_name:
                try:
                    fetched = fub_get(f"/templates/{template_id}")
                    template_name = fetched.get("name", "")
                    template_names[template_id] = template_name
                except Exception:
                    template_name = "(unknown)"
            flagged = _is_flagged(
                template_id,
                template_name,
                flag_template_ids,
                sequence_hints,
                name_index,
            )
            rows.append(
                (
                    plan_id,
                    plan_name,
                    step.get("position"),
                    template_id,
                    template_name,
                    "yes" if flagged else "no",
                )
            )

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["plan_id", "plan_name", "step_number", "template_id", "template_name", "flagged"]
    )
    writer.writerows(rows)
    print(out.getvalue().rstrip())

    flagged_rows = [r for r in rows if r[5] == "yes"]
    print()
    print(f"Total email steps scanned: {len(rows)}")
    print(f"Flag criteria: template_id={FLAG_TEMPLATE_ID}")
    if sequence_hints:
        print(f"Sequence name hints: {sorted(sequence_hints)}")
    else:
        print("Sequence name hints: none (no pre-meeting/appointment templates named in sequences/)")
    print(f"Flagged steps: {len(flagged_rows)}")
    if flagged_rows:
        flagged_plans = sorted({(r[0], r[1]) for r in flagged_rows})
        print("Plans with flagged steps:")
        for pid, pname in flagged_plans:
            print(f"  - {pid}: {pname}")


if __name__ == "__main__":
    main()
