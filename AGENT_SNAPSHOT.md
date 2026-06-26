# Agent Codebase Snapshot
Generated: June 25, 2026
Purpose: Claude project reference. Paste this file into the 
BrightWork CoS Claude project to give the AI assistant full 
line of sight to the current agent codebase.
Do not commit this file — add AGENT_SNAPSHOT.md to .gitignore.

---
## FILE: clients/ben-olsen/fub-config.yaml
*Last modified: June 25, 2026 15:12 UTC*

# BrightWork / Ben Olsen — FUB Runtime Config
# Populated after Theresa completes Action Plan build in FUB UI

fub_user_id: 1

stages:
  lead: 2
  attempted_contact: 24
  spoke_with_customer: 25
  appointment_set: 26
  met_with_customer: 27
  showing_homes: 28
  listing_agreement: 29
  active_listing: 30
  submitting_offers: 31
  active_client: 12
  under_contract: 32
  nurture: 33
  nurture_6m_plus: 4
  warm_3_6m: 22
  hot_prospect_0_3m: 3
  pending: 7
  past_client: 9
  sphere: 10
  unresponsive: 13
  closed: 8
  non_client: 23
  trash: 11

# Closed People stage ID confirmed. Note: post-close workflow should
# trigger from dealsUpdated webhook (Deals pipeline), not
# peopleStageUpdated. peopleStageUpdated on stage 8 is a secondary
# signal only — Ben does not consistently move contacts here after
# closing a Deal.
closed_stage_ids: [8]

action_plans:
  zillow_seller: null
  zillow_buyer: null
  homelight: 49
  off_market_buyer: 55
  buy_before_you_sell: 56
  mcc_estimator: 50
  expired_packet: 58
  senior_workshop: 57
  quiet_listing: 51
  brightflip: 52
  final_offer: 53
  relaunch: 54
  general_buyer: null
  agent_referral: null
  portal_seller: null
  portal_buyer: null

---

---
## FILE: clients/ben-olsen/soul.yaml
*Last modified: June 21, 2026 03:16 UTC*

---
name: Chief of Staff
archetype: The Penny
proactivity: default
personality_summary: >
  Clever, poised, and equal — a sharp partner, not a subordinate.
  Lead with the decision or action item. Brief and direct by default.
  Flag urgent items clearly at the top. Wit is welcome; filler is not.
  Expand only for appointment prep, compliance flags, or first-time
  contact reviews where missing context would cause a bad decision.
knowledge_base_manifest:
  - knowledge-base/agent-knowledge-index.md
  - knowledge-base/voice-guide.md
  - knowledge-base/brand-context.md
  - knowledge-base/local-market-context.md
  - knowledge-base/fair-housing-language.md
  - knowledge-base/contact-classification-taxonomy.md
  - knowledge-base/source-of-truth-matrix.md
  - knowledge-base/posthog-event-schema.md
  - fub/tag-taxonomy.md
  - utm-catalog.md

---

---
## FILE: agents/crewai/config/agents.yaml
*Last modified: June 21, 2026 03:16 UTC*

supervisor:
  model: openrouter/anthropic/claude-haiku-4-5
  role: "Chief of Staff Supervisor"
  goal: >
    Receive requests from Ben Olsen, determine what information is needed,
    delegate to specialist agents, and return a clear, useful response.
    Never contact clients. Never take action without Ben's approval.
  backstory: >
    You are Ben Olsen's Chief of Staff. You know his business, his voice,
    and his market. You coordinate information gathering and surface what
    Ben needs to do his job well. You delegate to specialist agents and
    synthesize their outputs into something Ben can act on immediately.
    {soul_context}
  verbose: false
  allow_delegation: true
  max_iter: 5

brief_generator:
  model: openrouter/anthropic/claude-sonnet-4-6
  role: "Pre-Appointment Brief Specialist"
  goal: >
    Given a contact ID, pull everything known about that contact from FUB
    and produce a concise pre-appointment brief Ben can read in 90 seconds
    before getting on the phone or walking into a meeting.
  backstory: >
    You are a research specialist who knows Follow Up Boss inside out.
    You retrieve contact records, recent activity, and appointment history,
    then distill them into a structured brief. You write in plain language.
    You surface what matters and leave out what doesn't.
    {soul_context}
  verbose: false
  allow_delegation: false
  max_iter: 3

---

---
## FILE: agents/crewai/config/tasks.yaml
*Last modified: June 21, 2026 03:16 UTC*

# Expand as agent capabilities grow

generate_pre_appointment_brief:
  description: >
    Pull the FUB contact record and recent activity for contact ID
    {contact_id}, then generate a pre-appointment brief for Ben Olsen.

    The brief must include:
    - Contact name, type (Buyer/Seller), and current stage
    - Primary phone and email
    - Tags (summarized, not a raw list dump)
    - Last activity date and what it was
    - Any upcoming appointments
    - A 2-3 sentence "situation summary" in plain English

    Format the brief so Ben can read it in 90 seconds. Use short sections
    with clear labels. No bullet walls. No filler.
  expected_output: |
    A private pre-appointment brief for Ben Olsen. This is internal 
    intelligence only — not a script, not a message to send.

    Format:
    
    CONTACT
    Full name, type, stage, phone, email, company/role if known.
    
    TAGS — WHAT THEY SIGNAL
    Interpret the tags in plain English. What do they tell Ben about 
    this person's situation and intent?
    
    LAST ACTIVITY
    Most recent FUB activity. Frame behavioral data (website visits, 
    estimator runs, form submissions) as context, not surveillance. 
    "Has been actively researching MCC property values" not 
    "ran 7 estimator sessions across 5 addresses."
    
    UPCOMING APPOINTMENTS
    Any scheduled appointments from FUB. If none, say so briefly.
    
    SITUATION
    2-4 sentences synthesizing what Ben needs to know walking in. 
    What is this person trying to solve? What is the likely unlock?
    Keep it direct. No filler.
    
    DO NOT include an opening move, suggested script, or any text 
    intended for the contact. Ben decides how to open the conversation.
  agent: brief_generator
  context: []

---

---
## FILE: tools/fub.py
*Last modified: June 21, 2026 03:16 UTC*

"""
Follow Up Boss API client.

Framework-agnostic integration — no CrewAI or other agent framework imports.
Can be used directly or wrapped by any orchestration layer.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests
from requests.exceptions import HTTPError, RequestException

from tools.logger import log_event

BASE_URL = "https://api.followupboss.com/v1"
ASSIGNED_TO_NAME = "Ben Olsen"
DEFAULT_TIMEOUT = 10

session = requests.Session()

_original_request = session.request


def _request_with_timeout(method: str, url: str, **kwargs: Any) -> requests.Response:
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    return _original_request(method, url, **kwargs)


session.request = _request_with_timeout  # type: ignore[method-assign]


def _ensure_api_key() -> None:
    api_key = os.environ.get("FUB_API_KEY", "")
    if not api_key:
        raise ValueError("FUB_API_KEY environment variable is required")
    session.auth = (api_key, "")


def _assigned_to_name(person: dict) -> str | None:
    assigned = person.get("assignedTo")
    if assigned is None:
        return None
    if isinstance(assigned, dict):
        name = assigned.get("name")
        return str(name) if name is not None else None
    if isinstance(assigned, str):
        return assigned
    return None


def _require_ben_olsen(person: dict) -> None:
    if _assigned_to_name(person) != ASSIGNED_TO_NAME:
        raise PermissionError("Contact not assigned to Ben Olsen")


def _log_http_error(method: str, endpoint: str, response: requests.Response) -> None:
    print(
        f"FUB API error: {method} {endpoint} — HTTP {response.status_code}: {response.text}",
        file=sys.stderr,
    )


def _raise_http_error(method: str, endpoint: str, response: requests.Response) -> None:
    _log_http_error(method, endpoint, response)
    raise HTTPError(
        f"{method} {endpoint} failed with HTTP {response.status_code}",
        response=response,
    )


def _get_json(method: str, endpoint: str, **kwargs: Any) -> dict:
    _ensure_api_key()
    url = f"{BASE_URL}{endpoint}"
    try:
        response = session.request(method, url, **kwargs)
    except RequestException as exc:
        print(f"FUB API error: {method} {endpoint} — {exc}", file=sys.stderr)
        raise

    if not response.ok:
        _raise_http_error(method, endpoint, response)

    try:
        return response.json()
    except json.JSONDecodeError as exc:
        print(
            f"FUB API error: {method} {endpoint} — invalid JSON response: {exc}",
            file=sys.stderr,
        )
        raise ValueError(f"Invalid JSON from FUB API: {endpoint}") from exc


def _extract_list(payload: dict, key: str) -> list[dict]:
    items = payload.get(key, [])
    if not isinstance(items, list):
        raise ValueError(f"Expected list at '{key}' in FUB API response")
    return items


def get_contact_by_id(contact_id: str) -> dict:
    """Fetch a contact by FUB person ID."""
    log_event(
        "fub",
        "get_contact",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="get_contact_by_id",
    )
    endpoint = f"/people/{contact_id}"
    try:
        _ensure_api_key()
        url = f"{BASE_URL}{endpoint}"
        try:
            response = session.get(url)
        except RequestException as exc:
            print(f"FUB API error: GET {endpoint} — {exc}", file=sys.stderr)
            raise

        if response.status_code != 200:
            _log_http_error("GET", endpoint, response)
            raise ValueError(
                f"Failed to fetch contact {contact_id}: HTTP {response.status_code}"
            )

        try:
            result = response.json()
        except json.JSONDecodeError as exc:
            print(
                f"FUB API error: GET {endpoint} — invalid JSON response: {exc}",
                file=sys.stderr,
            )
            raise ValueError(f"Invalid JSON from FUB API: {endpoint}") from exc

        log_event(
            "fub",
            "get_contact",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="get_contact_by_id",
        )
        return result
    except Exception as e:
        log_event(
            "fub",
            "get_contact",
            "failure",
            detail=str(e),
            contact_id=contact_id,
            exc_info=e,
        )
        raise


def get_recent_activity(contact_id: str, limit: int = 10) -> list[dict]:
    """Fetch recent timeline events for a contact, most recent first."""
    log_event(
        "fub",
        "get_recent_activity",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="get_recent_activity",
    )
    try:
        contact = get_contact_by_id(contact_id)
        _require_ben_olsen(contact)

        endpoint = "/events"
        params = {
            "personId": contact_id,
            "limit": limit,
            "sort": "created",
            "direction": "desc",
        }
        payload = _get_json("GET", endpoint, params=params)
        result = _extract_list(payload, "events")
        log_event(
            "fub",
            "get_recent_activity",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="get_recent_activity",
        )
        return result
    except Exception as e:
        log_event(
            "fub",
            "get_recent_activity",
            "failure",
            detail=str(e),
            contact_id=contact_id,
            exc_info=e,
        )
        raise


def search_contacts(query: str, limit: int = 25) -> list[dict]:
    """Search contacts assigned in FUB, filtered to Ben Olsen."""
    endpoint = "/people"
    params = {"q": query, "limit": limit, "assigned": "true"}
    payload = _get_json("GET", endpoint, params=params)
    people = _extract_list(payload, "people")
    return [person for person in people if _assigned_to_name(person) == ASSIGNED_TO_NAME]


def get_contact_by_email(email: str) -> dict | None:
    """Return the first matching person by email, or None if not found or not Ben's."""
    endpoint = "/people"
    params = {"email": email}
    payload = _get_json("GET", endpoint, params=params)
    people = _extract_list(payload, "people")
    if not people:
        return None

    person = people[0]
    if _assigned_to_name(person) != ASSIGNED_TO_NAME:
        return None
    return person


def get_appointments(contact_id: str) -> list[dict]:
    """Fetch appointments for a contact."""
    log_event(
        "fub",
        "get_appointments",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="get_appointments",
    )
    try:
        contact = get_contact_by_id(contact_id)
        _require_ben_olsen(contact)

        endpoint = "/appointments"
        params = {"personId": contact_id}
        payload = _get_json("GET", endpoint, params=params)
        result = _extract_list(payload, "appointments")
        log_event(
            "fub",
            "get_appointments",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="get_appointments",
        )
        return result
    except Exception as e:
        log_event(
            "fub",
            "get_appointments",
            "failure",
            detail=str(e),
            contact_id=contact_id,
            exc_info=e,
        )
        raise


if __name__ == "__main__":
    TEST_CONTACT_ID = os.environ.get("TEST_FUB_CONTACT_ID", "")
    if TEST_CONTACT_ID:
        contact = get_contact_by_id(TEST_CONTACT_ID)
        print(json.dumps(contact, indent=2))
        activity = get_recent_activity(TEST_CONTACT_ID)
        print(f"\nRecent activity ({len(activity)} events):")
        for event in activity:
            print(f"  {event.get('created', '')} — {event.get('type', '')}")
    else:
        print("Set TEST_FUB_CONTACT_ID env var to run smoke test")

---

---
## FILE: tools/telegram.py
*Last modified: June 25, 2026 02:31 UTC*

"""Telegram bot client for send/receive messaging."""

import os
import sys

import requests

from tools.logger import log_event

TELEGRAM_API = "https://api.telegram.org"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
OPERATOR_CHAT_ID = os.environ.get("OPERATOR_TELEGRAM_CHAT_ID", "")

session = requests.Session()
_original_request = session.request


def _request_with_timeout(method: str, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 10)
    return _original_request(method, url, **kwargs)


session.request = _request_with_timeout  # type: ignore[method-assign]


def send_message(text: str, chat_id: str = None, parse_mode: str | None = None) -> bool:
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id or CHAT_ID,
        "text": text,
    }
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode
    try:
        resp = session.post(url, json=payload)
        if resp.ok:
            return True
        print(f"sendMessage failed: {resp.status_code}", file=sys.stderr)
        return False
    except requests.RequestException as exc:
        print(f"sendMessage error: {exc}", file=sys.stderr)
        return False


def send_inline_message(text: str, reply_markup: dict, chat_id: str = None) -> bool:
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id or CHAT_ID,
        "text": text,
        "reply_markup": reply_markup,
    }
    try:
        resp = session.post(url, json=payload)
        if resp.ok:
            return True
        print(f"sendMessage failed: {resp.status_code}", file=sys.stderr)
        return False
    except requests.RequestException as exc:
        print(f"sendMessage error: {exc}", file=sys.stderr)
        return False


def send_operator_alert(message: str) -> None:
    """Send a plain-text alert to the operator channel. Never raises."""
    try:
        if not OPERATOR_CHAT_ID:
            log_event(
                "monitoring",
                "operator_alert",
                "fallback",
                detail="OPERATOR_TELEGRAM_CHAT_ID not set",
                file=__file__,
                function="send_operator_alert",
            )
            return

        url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": OPERATOR_CHAT_ID,
            "text": message,
        }
        resp = session.post(url, json=payload)
        if resp.ok:
            log_event(
                "monitoring",
                "operator_alert",
                "success",
                file=__file__,
                function="send_operator_alert",
            )
        else:
            log_event(
                "monitoring",
                "operator_alert",
                "failure",
                detail=f"HTTP {resp.status_code}",
                file=__file__,
                function="send_operator_alert",
            )
    except Exception as exc:
        log_event(
            "monitoring",
            "operator_alert",
            "failure",
            detail=str(exc),
            exc_info=exc,
        )


def get_updates(offset: int = 0, timeout: int = 10) -> list[dict]:
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": timeout}
    try:
        resp = session.get(url, params=params, timeout=timeout + 5)
        if not resp.ok:
            print(f"getUpdates failed: {resp.status_code}", file=sys.stderr)
            return []
        return resp.json().get("result", [])
    except requests.RequestException as exc:
        print(f"getUpdates error: {exc}", file=sys.stderr)
        return []


def extract_message(update: dict) -> dict | None:
    message = update.get("message")
    if not message:
        return None
    text = message.get("text")
    if not text:
        return None
    chat = message.get("chat", {})
    sender = message.get("from", {})
    return {
        "update_id": update["update_id"],
        "chat_id": str(chat.get("id", "")),
        "text": text,
        "from_name": sender.get("first_name", ""),
    }


if __name__ == "__main__":
    test_msg = "Chief of Staff is online. Pre-appointment brief system ready."
    success = send_message(test_msg)
    if success:
        print("Message sent successfully")
    else:
        print("Failed to send message")

---

---
## FILE: tools/logger.py
*Last modified: June 21, 2026 03:16 UTC*

"""Structured JSON logging for CoS Agent events."""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "cos_agent.log"


def log_event(
    agent: str,
    action: str,
    status: str,
    detail: str = "",
    contact_id: str = "",
    file: str = "",
    function: str = "",
    exc_info: BaseException | None = None,
) -> None:
    """Write one JSON log line. Never raises."""
    try:
        resolved_file = file
        resolved_function = function
        exc_info_line: str | None = None

        if exc_info is not None:
            if exc_info.__traceback__ is not None:
                frames = traceback.extract_tb(exc_info.__traceback__)
                if frames:
                    last_frame = frames[-1]
                    if not resolved_file:
                        resolved_file = last_frame.filename
                    if not resolved_function:
                        resolved_function = last_frame.name

            tb_lines = traceback.format_exception(
                type(exc_info), exc_info, exc_info.__traceback__
            )
            if tb_lines:
                exc_info_line = tb_lines[-1].strip()
            else:
                exc_info_line = str(exc_info)

        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "action": action,
            "status": status,
            "detail": detail,
            "contact_id": contact_id,
            "file": resolved_file,
            "function": resolved_function,
        }
        if exc_info_line is not None:
            entry["exc_info"] = exc_info_line
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

---

---
## FILE: tools/health.py
*Last modified: June 21, 2026 03:16 UTC*

"""Health reporting for CoS Agent jobs. Operator-facing; never raises."""

from __future__ import annotations

from tools.logger import log_event
from tools.telegram import send_operator_alert


def run_health_check(job_name: str, outcome: dict) -> None:
    """Report job outcome. Failures alert the operator; success is log-only."""
    try:
        status = outcome.get("status")
        if status == "failure":
            action = outcome.get("action", "")
            detail = outcome.get("detail", "")
            message = f"[{job_name}] failed — {action}"
            if detail:
                message += f" — {detail}"
            send_operator_alert(message)
            log_event(
                "health",
                job_name,
                "failure",
                detail=outcome.get("detail", ""),
                contact_id=outcome.get("contact_id", ""),
                file=__file__,
                function="run_health_check",
            )
        elif status == "success":
            log_event(
                "health",
                job_name,
                "success",
                contact_id=outcome.get("contact_id", ""),
                file=__file__,
                function="run_health_check",
            )
    except Exception:
        pass

---

---
## FILE: agents/crewai/crew.py
*Last modified: June 21, 2026 03:16 UTC*

"""
CrewAI orchestration layer for the BrightWork Chief of Staff agent.

Loads client config at runtime, wires tools to agents, injects soul_context,
and runs the generate_pre_appointment_brief task.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml
from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import tool

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.fub import get_appointments, get_contact_by_id, get_recent_activity
from tools.logger import log_event


@tool("Get FUB Contact by ID")
def fub_get_contact(contact_id: str) -> str:
    """Fetch a contact record from Follow Up Boss by contact ID.
    Returns the full contact record as a JSON string."""
    import json
    return json.dumps(get_contact_by_id(contact_id))


@tool("Get FUB Recent Activity")
def fub_get_activity(contact_id: str) -> str:
    """Fetch recent activity events for a contact from Follow Up Boss.
    Returns a list of activity events as a JSON string."""
    import json
    return json.dumps(get_recent_activity(contact_id))


@tool("Get FUB Appointments")
def fub_get_appointments(contact_id: str) -> str:
    """Fetch upcoming appointments for a contact from Follow Up Boss.
    Returns a list of appointment records as a JSON string."""
    import json
    return json.dumps(get_appointments(contact_id))


CONFIG_DIR = ROOT / "agents" / "crewai" / "config"
CLIENTS_DIR = ROOT / "clients"


def load_yaml_config(path: str) -> dict:
    """Read a YAML file and return the parsed dict."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def load_client_config(client_id: str) -> dict:
    """Load and merge soul.yaml and fub-config.yaml for a client."""
    client_dir = ROOT / "clients" / client_id
    soul_path = client_dir / "soul.yaml"
    fub_path = client_dir / "fub-config.yaml"

    if not soul_path.is_file():
        raise FileNotFoundError(f"Missing client config file: {soul_path}")
    if not fub_path.is_file():
        raise FileNotFoundError(f"Missing client config file: {fub_path}")

    soul = load_yaml_config(str(soul_path))
    fub = load_yaml_config(str(fub_path))
    return {**soul, **fub}


def build_soul_context(soul: dict) -> str:
    """Build a short soul_context string for agent backstory injection."""
    if not isinstance(soul, dict):
        return ""
    name = soul.get("name")
    personality = soul.get("personality_summary")
    if not name or not personality:
        return ""
    return f"Your name is {name}. {personality}"


def load_knowledge_context(client_id: str) -> str:
    """Load brief-relevant knowledge files and return as a combined string."""
    knowledge_dir = CLIENTS_DIR / client_id / "knowledge"

    # Files to load for appointment briefs, per agent-knowledge-index.md
    brief_files = [
        "contact-classification-taxonomy.md",
        "local-market-context.md",
        "fair-housing-language.md",
        "voice-guide.md",
    ]

    sections = []
    for filename in brief_files:
        filepath = knowledge_dir / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            sections.append(f"## {filename}\n\n{content}")
        else:
            log_event(
                "crew",
                "knowledge_load",
                "warning",
                detail=f"{filename} not found",
                contact_id="",
                file=__file__,
                function="load_knowledge_context",
            )

    return "\n\n---\n\n".join(sections)


def _make_agent(
    spec: dict, soul_context: str, llm: LLM, tools: list | None = None
) -> Agent:
    backstory = spec["backstory"].replace("{soul_context}", soul_context)
    kwargs: dict = {
        "role": spec["role"],
        "goal": spec["goal"],
        "backstory": backstory,
        "llm": llm,
        "verbose": spec.get("verbose", False),
        "allow_delegation": spec.get("allow_delegation", False),
        "max_iter": spec.get("max_iter", 3),
    }
    if tools is not None:
        kwargs["tools"] = tools
    return Agent(**kwargs)


def make_llm(role: str, agents_config: dict) -> LLM:
    model = agents_config.get(role, {}).get("model", "openrouter/anthropic/claude-haiku-4-5")
    return LLM(
        model=model,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )


def run_brief(client_id: str, contact_id: str) -> str:
    """Load config, assemble the crew, and return a pre-appointment brief."""
    client_config = load_client_config(client_id)
    soul_context = build_soul_context(client_config)
    knowledge_context = load_knowledge_context(client_id)

    agents_config = load_yaml_config(str(CONFIG_DIR / "agents.yaml"))
    tasks_config = load_yaml_config(str(CONFIG_DIR / "tasks.yaml"))

    supervisor = _make_agent(
        agents_config["supervisor"],
        soul_context,
        make_llm("supervisor", agents_config),
    )
    brief_spec = dict(agents_config["brief_generator"])
    brief_spec["backstory"] = (
        brief_spec["backstory"].replace("{soul_context}", soul_context)
        + "\n\n## KNOWLEDGE BASE\n\n"
        + knowledge_context
    )
    brief_generator = Agent(
        role=brief_spec["role"],
        goal=brief_spec["goal"],
        backstory=brief_spec["backstory"],
        llm=make_llm("brief_generator", agents_config),
        verbose=brief_spec.get("verbose", False),
        allow_delegation=brief_spec.get("allow_delegation", False),
        max_iter=brief_spec.get("max_iter", 3),
        tools=[fub_get_contact, fub_get_activity, fub_get_appointments],
    )

    task_spec = tasks_config["generate_pre_appointment_brief"]
    description = task_spec["description"].replace("{contact_id}", contact_id)
    brief_task = Task(
        description=description,
        expected_output=task_spec["expected_output"],
        agent=brief_generator,
    )

    crew = Crew(
        agents=[supervisor, brief_generator],
        tasks=[brief_task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff()
    return result.raw if hasattr(result, "raw") else str(result)


if __name__ == "__main__":
    client_id = os.environ.get("CLIENT_ID", "ben-olsen")
    contact_id = os.environ.get("TEST_FUB_CONTACT_ID", "")
    if not contact_id:
        print("Set TEST_FUB_CONTACT_ID to run")
    else:
        print(run_brief(client_id, contact_id))


class BrightWorkCrew:
    """Wrapper around run_brief() for kickoff-style invocation."""

    def __init__(self, client_id: str) -> None:
        self.client_id = client_id

    def kickoff(self, inputs: dict) -> str:
        try:
            contact_id = (inputs or {}).get("contact_id", "")
            if not contact_id or not str(contact_id).strip():
                return (
                    "No contact ID provided. Provide a FUB contact ID to generate a brief."
                )
            return run_brief(self.client_id, str(contact_id).strip())
        except Exception:
            return (
                "Unable to generate brief. Check FUB directly: "
                "https://app.followupboss.com"
            )

---

---
## FILE: agents/crewai/bot.py
*Last modified: June 25, 2026 02:31 UTC*

"""Telegram polling loop connecting inbound messages to CoS Agent brief generation."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crew import run_brief
from tools.fub import get_contact_by_id, search_contacts
from tools.fub_write import add_note_to_contact, enroll_in_action_plan
from tools.health import run_health_check
from tools.logger import log_event
from tools.telegram import (
    BOT_TOKEN,
    CHAT_ID,
    TELEGRAM_API,
    extract_message,
    get_updates,
    send_message,
    send_operator_alert,
    session as telegram_session,
)

LEAD_ALERT_STATE_PATH = ROOT / "logs" / "lead_alert_state.json"

BRIEF_ID_PATTERN = re.compile(r"^(?:/)?brief\s+(\d+)$", re.IGNORECASE)
BRIEF_NAME_PATTERN = re.compile(
    r"^(?:/)?brief\s+([A-Za-z][A-Za-z\s\-'\.]{1,50})$", re.IGNORECASE
)
GREETING_PATTERN = re.compile(r"^(?:hello|hi)$", re.IGNORECASE)
IDENTITY_PATTERN = re.compile(
    r"^(who are you|what are you|what do you do|what can you do|do you do anything else).*$",
    re.IGNORECASE,
)
HELP_PATTERN = re.compile(r"^(help|commands|options|\?)$", re.IGNORECASE)
POLL_TIMEOUT = 30
BRIEF_ERROR_MSG = (
    "I ran into a problem pulling that brief. Check FUB directly: "
    "https://app.followupboss.com"
)
UNKNOWN_MSG = "I didn't get that. Try: brief 31735 or brief Scott Eggert"
GREETING_REPLY = "Chief of Staff here. Send me a contact ID or name and I'll pull a brief."
IDENTITY_REPLY = "I'm Ben's Chief of Staff. Right now I pull pre-appointment briefs on contacts. Send me a name or contact ID and I'll get you what I know."
HELP_REPLY = "Here's what I can do:\n• brief [name] — pull a contact brief by name\n• brief [ID] — pull a contact brief by FUB ID\n• hello — check that I'm online"

REQUIRED_ENV_VARS = (
    "FUB_API_KEY",
    "ANTHROPIC_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


def startup_check() -> None:
    """Verify required env vars and optional FUB connectivity before polling."""
    for key in REQUIRED_ENV_VARS:
        value = os.environ.get(key, "")
        if not value:
            log_event(
                "health",
                "startup",
                "failure",
                detail=f"missing {key}",
                file=__file__,
                function="startup_check",
            )
            send_operator_alert(f"CoS Agent failed to start — missing env var: {key}")
            raise SystemExit(f"CoS Agent failed to start — missing env var: {key}")
        log_event(
            "health",
            "startup",
            "success",
            detail=f"{key} set",
            file=__file__,
            function="startup_check",
        )

    health_contact_id = os.environ.get("HEALTH_CHECK_CONTACT_ID", "").strip()
    if health_contact_id:
        log_event(
            "health",
            "startup",
            "start",
            detail="fub connectivity check",
            contact_id=health_contact_id,
            file=__file__,
            function="startup_check",
        )
        try:
            get_contact_by_id(health_contact_id)
            log_event(
                "health",
                "startup",
                "success",
                detail="fub connectivity check",
                contact_id=health_contact_id,
                file=__file__,
                function="startup_check",
            )
        except Exception as exc:
            log_event(
                "health",
                "startup",
                "failure",
                detail=f"fub connectivity check: {exc}",
                contact_id=health_contact_id,
                exc_info=exc,
            )
            send_operator_alert(
                f"CoS Agent failed to start — FUB connectivity check failed: {exc}"
            )
            raise SystemExit(
                f"CoS Agent failed to start — FUB connectivity check failed: {exc}"
            )
    else:
        log_event(
            "health",
            "startup",
            "success",
            detail="fub check skipped",
            file=__file__,
            function="startup_check",
        )

    log_event(
        "health",
        "startup",
        "success",
        file=__file__,
        function="startup_check",
    )


def _load_lead_alert_state() -> dict[str, Any]:
    if not LEAD_ALERT_STATE_PATH.exists():
        return {"drafts": {}, "contacts": {}, "responded": []}
    try:
        with LEAD_ALERT_STATE_PATH.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"drafts": {}, "contacts": {}, "responded": []}


def _save_lead_alert_state(state: dict[str, Any]) -> None:
    LEAD_ALERT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEAD_ALERT_STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(state, handle)


def _get_lead_draft(contact_id: str) -> tuple[str, str]:
    state = _load_lead_alert_state()
    draft = state.get("drafts", {}).get(contact_id, {})
    if isinstance(draft, dict):
        return draft.get("draft_email", ""), draft.get("draft_subject", "")
    return str(draft), ""


def _get_lead_contact(contact_id: str) -> dict[str, str]:
    state = _load_lead_alert_state()
    contact = state.get("contacts", {}).get(contact_id, {})
    if contact:
        return contact
    person = get_contact_by_id(contact_id)
    phones = person.get("phones") or []
    phone = ""
    if isinstance(phones, list) and phones:
        value = phones[0].get("value") if isinstance(phones[0], dict) else phones[0]
        phone = str(value or "")
    return {
        "first_name": str(person.get("firstName", "")),
        "last_name": str(person.get("lastName", "")),
        "phone": phone,
        "source": str(person.get("source", "")),
    }


def _mark_lead_responded(contact_id: str) -> None:
    state = _load_lead_alert_state()
    responded = state.setdefault("responded", [])
    if contact_id not in responded:
        responded.append(contact_id)
    _save_lead_alert_state(state)


def _answer_callback_query(callback_query_id: str) -> None:
    if not callback_query_id:
        return
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    try:
        telegram_session.post(url, json=payload, timeout=10)
    except Exception:
        pass


def _drain_stale_updates() -> int:
    """Acknowledge queued updates on startup without executing callbacks or sends."""
    offset = 0
    while True:
        updates = get_updates(offset=offset, timeout=0)
        if not updates:
            break
        for update in updates:
            offset = update.get("update_id", 0) + 1
            callback_query = update.get("callback_query")
            if callback_query:
                _answer_callback_query(callback_query.get("id", ""))
    return offset


def _handle_callback(client_id: str, callback_query: dict) -> None:
    """Route inline keyboard actions for lead alert cards."""
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat = message.get("chat", {})
    chat_id = str(chat.get("id", ""))

    if not data or ":" not in data:
        return

    action, contact_id = data.split(":", 1)
    contact_info = _get_lead_contact(contact_id)
    first_name = contact_info.get("first_name", "")
    action_plan_id = contact_info.get("action_plan_id")

    if action == "approve":
        if action_plan_id:
            try:
                enroll_in_action_plan(contact_id, int(action_plan_id))
            except Exception as exc:
                log_event(
                    "lead_alert",
                    "approve",
                    "failure",
                    detail=str(exc),
                    contact_id=contact_id,
                    exc_info=exc,
                    file=__file__,
                    function="_handle_callback",
                )
                send_message(
                    "Action plan enrollment failed. Check FUB manually.",
                    chat_id=chat_id,
                )
                return
            send_message(
                f"Sequence started for {first_name}. FUB will send Day 1 email.",
                chat_id=chat_id,
            )
            add_note_to_contact(
                contact_id,
                "Lead Alert: Ben approved. Action plan enrolled by CoS agent.",
            )
            _mark_lead_responded(contact_id)
        else:
            send_message(
                "No sequence mapped for this lead source. Check FUB manually.",
                chat_id=chat_id,
            )
            add_note_to_contact(
                contact_id,
                "Lead Alert: Ben approved but no action plan mapped for source.",
            )
        log_event(
            "lead_alert",
            "approve",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="_handle_callback",
        )
        return

    if action == "call":
        phone = contact_info.get("phone", "")
        phone_digits = re.sub(r"\D", "", phone)
        send_message(
            f"Call {first_name} — tap to dial:\n+1{phone_digits}",
            chat_id=chat_id,
        )
        add_note_to_contact(contact_id, "Lead Alert: Ben tapped CALL.")
        _mark_lead_responded(contact_id)
        log_event(
            "lead_alert",
            "call",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="_handle_callback",
        )
        return


def _handle_message(client_id: str, text: str) -> str:
    if GREETING_PATTERN.match(text.strip()):
        return GREETING_REPLY

    if IDENTITY_PATTERN.match(text.strip()):
        return IDENTITY_REPLY
    if HELP_PATTERN.match(text.strip()):
        return HELP_REPLY

    brief_match = BRIEF_ID_PATTERN.match(text.strip())
    if brief_match:
        contact_id = brief_match.group(1)
        log_event(
            "bot",
            "brief_requested",
            "start",
            contact_id=contact_id,
            file=__file__,
            function="_handle_message",
        )
        log_event(
            "cos_agent",
            "run_brief",
            "start",
            contact_id=contact_id,
            file=__file__,
            function="_handle_message",
        )
        try:
            result = run_brief(client_id, contact_id)
            log_event(
                "cos_agent",
                "run_brief",
                "success",
                contact_id=contact_id,
                file=__file__,
                function="_handle_message",
            )
            run_health_check(
                "brief",
                {
                    "status": "success",
                    "agent": "brief_generator",
                    "action": "generate_brief",
                    "contact_id": contact_id,
                },
            )
            return result
        except Exception as exc:
            run_health_check(
                "brief",
                {
                    "status": "failure",
                    "agent": "brief_generator",
                    "action": "generate_brief",
                    "detail": str(exc),
                    "contact_id": contact_id,
                },
            )
            log_event(
                "cos_agent",
                "run_brief",
                "failure",
                detail=str(exc),
                contact_id=contact_id,
                exc_info=exc,
            )
            return BRIEF_ERROR_MSG

    name_match = BRIEF_NAME_PATTERN.match(text.strip())
    if name_match:
        query = name_match.group(1).strip()
        log_event(
            "bot",
            "name_lookup",
            "start",
            detail=query,
            file=__file__,
            function="_handle_message",
        )
        results = search_contacts(query, limit=5)
        if not results:
            return f"No contact found for '{query}'. Check the name or use a contact ID."
        if len(results) > 1:
            lines = [f"Found {len(results)} matches. Which one?"]
            for p in results:
                name = f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()
                cid = str(p.get("id", ""))
                lines.append(f"  brief {cid} — {name}")
            return "\n".join(lines)
        contact = results[0]
        contact_id = str(contact.get("id", ""))
        name = f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
        log_event(
            "bot",
            "name_lookup",
            "success",
            detail=f"{name} → {contact_id}",
            file=__file__,
            function="_handle_message",
        )
        log_event(
            "bot",
            "brief_requested",
            "start",
            contact_id=contact_id,
            file=__file__,
            function="_handle_message",
        )
        log_event(
            "cos_agent",
            "run_brief",
            "start",
            contact_id=contact_id,
            file=__file__,
            function="_handle_message",
        )
        try:
            result = run_brief(client_id, contact_id)
            log_event(
                "cos_agent",
                "run_brief",
                "success",
                contact_id=contact_id,
                file=__file__,
                function="_handle_message",
            )
            return result
        except Exception as exc:
            log_event(
                "cos_agent",
                "run_brief",
                "failure",
                detail=str(exc),
                contact_id=contact_id,
                exc_info=exc,
            )
            return BRIEF_ERROR_MSG

    return UNKNOWN_MSG


def _watchdog_supervisor() -> None:
    """Keep tools/watchdog.py running; restart automatically on crash."""
    while True:
        log_event(
            "monitoring",
            "watchdog",
            "start",
            file=__file__,
            function="_watchdog_supervisor",
        )
        proc = subprocess.Popen(
            [sys.executable, "-m", "tools.watchdog"],
            cwd=str(ROOT),
        )
        proc.wait()
        log_event(
            "monitoring",
            "watchdog",
            "failure",
            detail=f"exit code {proc.returncode}",
            file=__file__,
            function="_watchdog_supervisor",
        )
        time.sleep(2)


def _start_watchdog() -> threading.Thread:
    thread = threading.Thread(target=_watchdog_supervisor, daemon=True)
    thread.start()
    return thread


def run_bot(client_id: str) -> None:
    """Poll Telegram indefinitely and route messages to CoS Agent."""
    startup_check()
    _start_watchdog()
    log_event(
        "cos_agent",
        "bot_start",
        "start",
        file=__file__,
        function="run_bot",
    )
    send_message("Chief of Staff is online.")
    log_event(
        "cos_agent",
        "bot_start",
        "success",
        detail="CoS Agent is online.",
        file=__file__,
        function="run_bot",
    )

    offset = _drain_stale_updates()
    configured_chat_id = str(CHAT_ID)

    try:
        while True:
            updates = get_updates(offset=offset, timeout=POLL_TIMEOUT)
            for update in updates:
                update_id = update.get("update_id", 0)
                offset = update_id + 1

                message = extract_message(update)
                if message:
                    chat_id = message["chat_id"]
                    if chat_id == configured_chat_id:
                        text = message["text"]
                        log_event(
                            "telegram",
                            "inbound",
                            "success",
                            detail=text,
                            contact_id="",
                            file=__file__,
                            function="run_bot",
                        )

                        reply = _handle_message(client_id, text)
                        send_message(reply, chat_id=chat_id)
                        log_event(
                            "telegram",
                            "outbound",
                            "success",
                            detail=reply[:200],
                            contact_id="",
                            file=__file__,
                            function="run_bot",
                        )

                callback_query = update.get("callback_query")
                if callback_query:
                    callback_query_id = callback_query.get("id", "")
                    _answer_callback_query(callback_query_id)
                    callback_chat_id = str(
                        callback_query.get("message", {})
                        .get("chat", {})
                        .get("id", "")
                    )
                    if callback_chat_id == configured_chat_id:
                        _handle_callback(client_id, callback_query)
    except KeyboardInterrupt:
        log_event(
            "cos_agent",
            "bot_stop",
            "start",
            detail="keyboard interrupt",
            file=__file__,
            function="run_bot",
        )
        send_message("Chief of Staff going offline.")
        log_event(
            "cos_agent",
            "bot_stop",
            "success",
            detail="CoS Agent going offline.",
            file=__file__,
            function="run_bot",
        )

if __name__ == "__main__":
    run_bot("ben-olsen")

---

---
## FILE: agents/crewai/main.py
*Last modified: June 21, 2026 03:16 UTC*

"""Entry point for the BrightWork Chief of Staff CrewAI agent."""

from dotenv import load_dotenv

load_dotenv()

import argparse

from crew import run_brief


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the BrightWork CoS agent")
    parser.add_argument(
        "--client",
        default="ben-olsen",
        help="Client ID (maps to clients/{client_id}/)",
    )
    parser.add_argument(
        "--mode",
        choices=["brief", "bot"],
        default="bot",
        help="Run mode: brief (one-shot) or bot (Telegram polling loop)",
    )
    parser.add_argument(
        "--contact",
        help="FUB contact ID (required when --mode brief)",
    )
    args = parser.parse_args()

    if args.mode == "bot":
        from bot import run_bot

        run_bot(args.client)
    else:
        if not args.contact:
            parser.error("--contact is required when --mode is brief")
        print(run_brief(args.client, args.contact))


if __name__ == "__main__":
    main()

---

---
## FILE: clients/ben-olsen/knowledge/fub-field-dictionary.md
*Last modified: June 25, 2026 15:02 UTC*

# fub-field-dictionary.md
Purpose: Complete reference for FUB structured fields, pipeline stages,
and lead sources as they exist in Ben Olsen's account. Pulled live from
the FUB API June 2026.
Agent Use: Brief Generator and Lead Router reference this before reading
or writing any contact record. Stage IDs and source strings here are the
canonical values — never infer or guess them.
Maintained by: MKTNG.co
Last updated: June 2026

---

## PRIMARY CONTACT FIELDS

These are structured fields on every FUB contact record. The agent
reads these first, before tags.

| Field | Type | Agent Use | Notes |
|---|---|---|---|
| `id` | integer | Primary key | Never modify |
| `firstName` / `lastName` | string | Display, personalization | |
| `stage` | string | Pipeline position | See stage list below |
| `type` | string | Buyer / Seller / Buyer & Seller / Renter / Other | Primary classification signal |
| `source` | string | Lead origin | See source list below |
| `assignedTo` | string | Owner filter | Must be "Ben Olsen" for all agent ops |
| `assignedUserId` | integer | Owner filter (numeric) | Ben's user ID: 1 |
| `contacted` | boolean | Has Ben made contact | 0 = no, 1 = yes |
| `tags` | array | Supplementary signals | Read after structured fields |
| `customZipCodeOrigin` | string | Geographic market signal | Maps to local-market-context.md |
| `price` | integer | Target price point | Buyer budget or seller expectation |
| `lastActivity` | datetime | Recency | Key signal for nurture vs. active |
| `emails` | array | Email addresses | Check `status` field — use Valid only |
| `phones` | array | Phone numbers | Check `isLandline` — prefer mobile |

---

## PIPELINE STAGES

Verified live from Ben Olsen's FUB account, June 25, 2026.
Use exact string values when reading or writing the `stage` field.

### API-Confirmed Stage IDs

| ID | Stage Name | People Count | Agent Behavior |
|---|---|---|---|
| 2 | Lead | 19,452 | New arrival. Confirm assignedTo before any action. High volume — filter by lastActivity before surfacing. |
| 24 | Attempted contact | 126 | Outreach sent, no response. Monitor for re-engagement. |
| 25 | Spoke with customer | 427 | Two-way contact established. Brief mode eligible. |
| 26 | Appointment set | 151 | Appointment exists. Flag for pre-appointment brief. |
| 27 | Met with customer | 101 | Consultation completed. Monitor next step. |
| 28 | Showing homes | 99 | Active buyer. Do not interrupt with nurture sequences. |
| 29 | Listing agreement | 0 | Listing signed. Transaction mode. |
| 30 | Active listing | 0 | Home on market. Do not sequence. |
| 31 | Submitting offers | 3 | Offer in progress. Transaction mode. |
| 12 | Active Client | 12 | Actively working relationship. |

### Stage IDs Pending (stages exist in account, IDs not yet pulled)

Run `GET /v1/stages?limit=50` to resolve these before building write logic.

| Stage Name | People Count | Agent Behavior |
|---|---|---|
| Nurture | 153 | Active nurture. Sequence appropriate. |
| Nurture 6m+ | 12 | Long-horizon. Low-frequency contact. |
| Warm 3-6m | 11 | Active nurture. Sequence appropriate. |
| Hot Prospect 0-3m | 6 | High priority. Surface in morning digest. |
| Pending | 2 | Transaction pending. Do not sequence. |
| Past Client | 6 | No outreach. Monitor for referral signals. Re-engage via sphere track. |
| Sphere | 5,656 | Largest meaningful segment. Referral sources, past clients, neighbors. No auto-sequence without Ben approval. |
| Unresponsive | 3 | Suppress outreach. Flag for Ben review. |
| Closed | 71 | No outreach. Closed transactions. Monitor for anniversary and referral triggers. |
| Non Client | 47 | No outreach without Ben instruction. |
| Trash | 3,083 | Suppress all operations. |

### Important Notes

- "Lead" (19,452) contains the Chime import dump. Do not treat as
  uniformly hot. Filter by lastActivity and source before surfacing.
- "Sphere" (5,656) is the largest active segment and the primary
  re-engagement opportunity. No sequence enrollment without explicit
  Ben approval.
- "Past Client" (6) is severely underpopulated relative to closed
  Deals count (85+ transactions). Past clients are likely sitting in
  Sphere or at their last active stage. This is a data hygiene gap.
- Closed transaction trigger must use Deals pipeline stage changes
  (dealsUpdated webhook), NOT peopleStageUpdated. Ben does not
  consistently move contacts to the "Closed" People stage.

---

## LEAD SOURCES

These are the actual source strings appearing in Ben's contact
records. The agent maps these to sequences and trust levels.

### Active / High-Volume Sources

| Source String | Description | Sequence | Trust Level |
|---|---|---|---|
| `Zillow` | Zillow Premier Agent portal | zillow-seller or zillow-buyer by type | Low-moderate |
| `Ben-Olsen-ZillowPremier` | Legacy Zillow Premier label | Treat same as Zillow | Low-moderate |
| `Zillow Rentals` | Zillow rental inquiries | No active sequence — flag for Ben | Low |
| `HomeLight` | HomeLight referral platform | homelight | Medium-high |
| `Referral` | Agent or personal referral | agent-referral | High |
| `CSV Import` | Batch import | No auto-sequence. Ben approval required. | Unscored |
| `<unspecified>` | Source not captured | No auto-sequence. Flag for classification. | Unknown |

### Legacy / Low-Volume Sources

| Source String | Description | Agent Behavior |
|---|---|---|
| `Homesnap` | Defunct portal (merged into Realtor.com) | No active sequence. Treat as portal-buyer/seller by type if re-engaged. |
| `AgentMachine` | Legacy lead service | No active sequence. Flag for Ben. |
| `iHomeFinder` | Legacy IDX portal | No active sequence. |
| `FastExpert` | Agent matching platform | No active sequence. Flag for Ben. |
| `FB_Lafayette` / `FB_Moraga` | Facebook ad campaigns by city | No active sequence. Flag for Ben. |
| `Google` / `googsell` | Google ad campaigns | No active sequence. Flag for Ben. |
| `TP Websites` | Third-party website lead | No active sequence. Flag for Ben. |

### Sources Not Yet Appearing (Expected from New Programs)

| Source String | Expected From | Sequence |
|---|---|---|
| `BrightWork Website` | Landing page forms | Varies by tag |
| `Final Offer` | finaloffer.brightworkrealty.com | final-offer |
| `Open House` | ShowingTime / manual | No sequence — direct Ben action |

---

## CUSTOM FIELDS

| Field Name | API Key | Type | Notes |
|---|---|---|---|
| Zip Code Origin | `customZipCodeOrigin` | string | Migrated from zip code tags June 2026. Maps to local-market-context.md. Agent reads this for geographic routing. |

Note: Additional custom fields likely exist in the account but were
not exposed in the current API pull. This section should be updated
after a full custom fields endpoint query.

---

## AGENT WRITE RULES (SUMMARY)

Permitted writes to FUB contact records:
- Add tags with `mergeTags: true` — never replace tag arrays
- Update `stage` — always log previous stage in activity note
- Log activity notes
- Update `customZipCodeOrigin` if null
- Enroll in sequence after Ben Telegram approval on first touch

Prohibited writes:
- Delete contacts
- Remove tags without explicit Ben instruction
- Write to contacts where `assignedTo` is not "Ben Olsen"
- Overwrite `stage` without logging previous value

See source-of-truth-matrix.md for full write permission rules.

---

---
## FILE: clients/ben-olsen/knowledge/contact-classification-taxonomy.md
*Last modified: June 25, 2026 15:02 UTC*

# contact-classification-taxonomy.md
Purpose: Defines contact types, lead sources, funnel stages, and how the agent interprets FUB data to classify any given contact
Agent Use: Lead Router reads this to determine sequence eligibility and next-best action. Brief Generator reads this to frame who a contact is before an appointment. All FUB operations must be consistent with classifications defined here.
Maintained by: MKTNG.co
Last updated: June 2026

---

## Classification Hierarchy

The agent reads FUB structured fields first, tags second. This is a hard rule.

**Primary fields (in order of priority):**

1. `type` — Buyer, Seller, Buyer & Seller, Renter, Other
2. `stage` — the pipeline stage (see stage definitions below)
3. `source` — where the lead originated
4. `assignedTo` — must be Ben Olsen for any agent operation
5. `lastActivity` — recency signal
6. `customZipCodeOrigin` — maps contact to a market area (see `local-market-context.md`)

Tags are supplementary signals. If a tag contradicts a structured field, the structured field wins. Flag the conflict for Ben.

---

## FUB Stage Definitions

FUB may also use intent-specific entry stages (`New Buyer Lead`, `New Seller Lead`). Treat these as subtypes of **Lead** for routing purposes.

Use exact stage string values as they appear in Ben's FUB account (verified June 25, 2026).

| Stage | Meaning | Agent behavior |
|---|---|---|
| **Lead** | Just arrived, no contact yet | Confirm assignedTo before any action. High volume — filter by lastActivity before surfacing. Priority: trigger or confirm Day 0 sequence enrollment |
| **Attempted contact** | Outreach sent, no response | Monitor for re-engagement signals; do not duplicate Day 0 |
| **Spoke with customer** | Two-way communication established | Brief mode eligible; pause or exit active sequences per exit conditions |
| **Appointment set** | Appointment scheduled | Flag for pre-appointment brief |
| **Met with customer** | Consultation completed | Monitor next step |
| **Showing homes** | Active buyer | Do not interrupt with nurture sequences |
| **Listing agreement** | Listing signed | Transaction mode; no sequence contact |
| **Active listing** | Home on market | Do not sequence |
| **Submitting offers** | Offer in progress | Transaction mode; no sequence contact |
| **Active Client** | Actively working relationship | Brief mode; confirm whether an active sequence should continue or exit |
| **Nurture** | Active nurture contact | Sequence enrollment appropriate when source/tags warrant |
| **Nurture 6m+** | Long-horizon contact | Low-frequency contact |
| **Warm 3-6m** | Active nurture segment | Sequence appropriate |
| **Hot Prospect 0-3m** | High priority prospect | Surface in morning digest |
| **Pending** | Transaction pending | Defer to SkySlope/Dotloop; no sequence contact |
| **Past Client** | Prior closed transaction with Ben | No outreach; monitor for referral signals. Re-engage via sphere track |
| **Sphere** | Referral sources, past clients, neighbors | No auto-sequence without Ben approval |
| **Unresponsive** | No response over extended period | Suppress outreach; flag for Ben review |
| **Closed** | Closed transactions | No outreach; monitor for anniversary and referral triggers |
| **Non Client** | Not a client contact | No outreach without Ben instruction |
| **Trash** | Disqualified / junk | Suppress all operations |

**Engagement milestones** (used as sequence exit conditions, not primary pipeline stages): Engaged, Listing Appointment, Active Seller, Showing, Active Buyer. When a contact reaches any of these, active pursuit sequences should pause or hand off to nurture per sequence rules.

**FUB Deals module:** Transaction management, not pipeline. Do not confuse Deal stage with Contact stage.

---

## Lead Source Mapping

For each source: what it means, which sequence it maps to, and trust/intent level.

| Source | Meaning | Sequence | Trust / intent |
|---|---|---|---|
| **Zillow** | Portal lead, unverified intent | `zillow-buyer` if `type` = Buyer; `zillow-seller` if `type` = Seller and seller intent signal present (valuation inquiry, "thinking of selling") | Low–moderate. Portal behavior, not pre-qualified |
| **Realtor.com / Homes.com** | Portal lead, same logic as Zillow | `portal-buyer` or `portal-seller` (apply Zillow Buyer/Seller sequence logic until dedicated portal sequences exist) | Low–moderate |
| **HomeLight** | Referred lead, pre-screened by HomeLight | `homelight` | High. Warm transfer, seller-focused |
| **Final Offer landing page** | Seller lead from finaloffer.brightworkrealty.com | `final-offer` (trigger tag: `final-offer-inquiry`) | Moderate–high. Program-specific intent |
| **Off-Market landing page** | Buyer lead from offmarket.brightworkrealty.com | `off-market-buyer` (trigger tag: `off-market-lead`) | Moderate–high. Opted into private inventory access |
| **Buy Before You Sell landing page** | Buyer/seller hybrid from buybefore.brightworkrealty.com | `buy-before-you-sell` (trigger tag: `buy-before-you-sell-lead`) | Moderate–high. Dual-transaction intent |
| **Quiet Listing landing page** | Seller lead, privacy-first, from quiet.brightworkrealty.com | `quiet-listing` (trigger tag: `quiet-listing-inquiry`) | Moderate–high. Discretion-driven seller |
| **Relaunch landing page** | Expired listing owner, skeptical, from relaunch.brightworkrealty.com | `relaunch` (trigger tag: `relaunch-inquiry`) | Moderate. Frustrated prior listing experience |
| **BrightFlip landing page** | Seller with deferred maintenance, from brightflip.brightworkrealty.com | `brightflip` (trigger tag: `presale-improvement-inquiry`) | Moderate–high. Renovation-capital intent |
| **MCC Estimator** | Moraga Country Club seller via moragacountryclubrealestate.com | `mcc-estimator` (trigger tag: `MCC Estimator`) | Moderate–high. Community-specific, floor-plan driven |
| **Senior Workshop** | Event registration via seniors.brightworkrealty.com | `senior-workshop` (trigger tags: `workshop-registration`, `workshop-interest-list`) | Moderate. Long-horizon transition planning |
| **Agent Referral** | Referred by another agent | Agent Referral sequence (fallback: `general-buyer` or seller equivalent based on `type`) | High. Warm intro, professional referral |
| **Past Client** | Prior closed transaction with Ben/BrightWork | Nurture flow or direct Ben outreach — no automated sequence without Ben instruction | Highest. Existing relationship |
| **Open House** | In-person contact from open house sign-in | `general-buyer` if Buyer; seller outreach based on `type` and conversation notes | Moderate. In-person but intent varies |
| **Manual / Ben** | Ben entered directly in FUB | No sequence without Ben instruction | N/A — Ben-controlled |
| **Expired Packet Recipient** | Received mailed expired listing packet | `expired-packet` (trigger tag: `expired-listing`) | Moderate. Direct mail response, skeptical seller profile |
| **Website / General inquiry** | Contact form or inquiry not covered by a program landing page | `general-buyer` if Buyer; route seller by closest program tag or Ben review | Low–moderate |

---

## Tag Interpretation Rules

Full tag definitions live in `fub/tag-taxonomy.md`. Behavioral rules the agent must apply:

### Program and enrollment tags

Program tags are enrollment triggers for the matching sequence. Before enrolling, verify the corresponding sequence is not already active and the contact is not suppressed.

| Tag | Sequence | Notes |
|---|---|---|
| `off-market-lead` | Off-Market Buyer VIP | Canonical off-market landing page tag |
| `quiet-listing-inquiry` | Quiet Listing | Privacy-first seller |
| `presale-improvement-inquiry` | BrightFlip | Also appears as `Pre-Sale Reno` on MCC form |
| `final-offer-inquiry` | Final Offer | |
| `relaunch-inquiry` | Relaunch | |
| `buy-before-you-sell-lead` | Buy Before You Sell | Also `Buy Before Sell` on MCC form |
| `MCC Estimator` | MCC Value Estimator | Primary MCC trigger |
| `homelight-lead` | HomeLight | |
| `zillow-lead` | Zillow Buyer or Zillow Seller | Requires buyer/seller intent signal |
| `expired-listing` | Expired Packet | Direct mail response |

Do not re-enroll a contact who already carries an active `Program:` sequence tag unless Ben instructs.

### VIP and relationship tags

| Tag | Rule |
|---|---|
| `#HitList` | Ben's VIP relationship list. These contacts do **not** receive automated sequences. Flag for direct Ben action only. |
| `#AlwaysMail` | Direct mail override — include in mail campaigns unless `#NeverMail` or `Unsubscribed` blocks email |
| `#NeverMail` | Hard suppression for direct mail |

### Intent and priority tags

| Tag | Rule |
|---|---|
| `mcc-report-request` | Higher-intent signal than `MCC Estimator` alone. Brief Generator must note in appointment prep. |
| `Call Requested` | Highest-intent MCC signal. Trigger immediate follow-up alert to Ben. |
| `Hot 90 Days` | Active buy/sell within 90 days. Priority for direct outreach. |
| `Warm 6-12 Months` | Mid-priority nurture. |
| `Future seller` | Long-horizon seller intent. Nurture candidate, not active listing. |

### MCC Estimator — Interpretation Rule

MCC Estimator runs are awareness-stage behavior. A contact running valuations on one or more MCC properties is exploring options, not declaring intent to sell. Treat estimator activity as private context for Ben only — it tells him the contact is engaged and thinking, not that they are ready to transact.

In briefs: surface estimator activity as background signal ("has been exploring MCC values") not as a primary intent indicator. Never frame it as evidence of a selling decision. The opening move should invite the contact to share their thinking, not reference the valuations directly. Ben should let the contact lead with their own situation.

Exception: if the contact also submitted a call request on a specific property, that submission is an explicit intent signal and can be referenced. The call request is the signal. The valuation runs are the context.

### Pre-Appointment Brief vs. Lead Alert — Do Not Confuse These

Pre-appointment briefs are private intelligence for Ben. They summarize 
what Ben needs to know before a conversation. They never include a 
suggested opening line, drafted message, or anything framed as 
something Ben should say. End the brief at Situation.

Lead alerts are a separate feature triggered by new inbound contacts. 
They include drafted first-touch messages and approval buttons. 
Do not apply lead alert patterns to pre-appointment briefs.

### Import and data quality tags

| Tag | Rule |
|---|---|
| `chimeimport` | Historical Chime CRM import with low data quality. Do not initiate outreach without Ben verification. |
| `Import` | Batch-imported contact. No behavioral signal — do not auto-enroll. |
| `Corliss Neighbors` | Neighborhood canvass import (June 2026). No email sequences without explicit Ben approval. |

### Workshop tags

| Tag | Rule |
|---|---|
| `workshop-registration` | Confirmed event registration. Enroll in Senior Workshop sequence. |
| `workshop-interest-list` | Expressed interest only — not confirmed registration. Flag for Ben review before sequence enrollment. |
| `SeniorWorkshop` | Applied by event registration flow. Treat as workshop segment tag. |

### Suppression tags (hard stops)

| Tag | Rule |
|---|---|
| `Unsubscribed` | Hard email suppression. Never enroll in any email sequence. |
| `Bounced` | Do not send email. Flag for data cleanup. |

### Tags to ignore

- **Zillow-injected tags** (`Zillow Connected`, `Zillow High Intent Buyer`, etc.): Read `source` field instead.
- **City/location tags** (`ORINDA`, `MORAGA`, `WALNUT CREEK`, etc.): Zillow search-area noise. Read `customZipCodeOrigin` for geography.
- **Redundant type tags** (`Buyer`, `Seller`): Read structured `type` field instead.

---

## Contact Type Decision Tree

Plain-English logic the agent follows for every contact:

1. **Read `assignedTo`.** If not Ben Olsen, stop. No agent operations on this contact.

2. **Check suppression.** If `Unsubscribed`, `Bounced`, or `#NeverMail` applies to the planned channel, stop that channel. Email suppression is a hard block.

3. **Read `type`.** Is this a Buyer, Seller, Buyer & Seller, Renter, or Other? Buyer & Seller contacts route to the sequence matching their highest-intent signal (program tag or source).

4. **Read `source`.** Which sequence does this map to per the Lead Source Mapping table?

5. **Check active tags.** Do any program tags override source-based routing? Program tags take precedence over generic source when both are present and aligned with `type`.

6. **Check `stage`.** Is this contact in a state where sequence enrollment is appropriate?
   - Enroll: Lead, Attempted contact (if sequence not yet started), Nurture, Warm 3-6m, Nurture 6m+
   - Do not enroll: Pending, Listing agreement, Active listing, Submitting offers, Closed, Unresponsive, Trash, Non Client
   - Sphere: no auto-sequence without Ben approval
   - Brief mode: Spoke with customer, Appointment set, Met with customer, Showing homes, Active Client, Hot Prospect 0-3m

7. **Check `#HitList`.** If present, stop. Flag for direct Ben action only. No automated sequences.

8. **Check import flags.** If `chimeimport`, `Import`, or `Corliss Neighbors` is present without a fresh inbound signal, stop and flag for Ben verification.

9. **Verify sequence not already active.** Check for existing `Program:` tags or active action plan before enrolling.

10. **Map geography.** Read `customZipCodeOrigin` and cross-reference `local-market-context.md` for market framing in briefs.

11. **Route or flag.**
    - All checks pass → enroll in appropriate sequence or generate brief
    - Any conflict between tags and structured fields → structured field wins, flag conflict for Ben
    - Uncertainty → flag for Ben review rather than auto-enroll

---

---
## FILE: clients/ben-olsen/knowledge/agent-knowledge-index.md
*Last modified: June 21, 2026 03:16 UTC*

# agent-knowledge-index.md

Purpose: Master index of all knowledge-base files for the BrightWork CoS agent. Describes each file's contents and the agent use case that triggers loading it.

Agent Use: Loaded at initialization. Agent consults this index to determine which files are relevant for a given task before loading full file contents.

Maintained by: MKTNG.co

Last updated: June 2026

---

## How to Use This Index

1. Identify the task type (copy generation, contact routing, appointment prep, data write, etc.).
2. Load only the files whose trigger tasks match the current operation.
3. For client-facing copy, always load `voice-guide.md`, `brand-context.md`, and `fair-housing-language.md` together.
4. For any FUB read or write, load `source-of-truth-matrix.md` before acting.
5. Sequence content lives in `realtors/ben-olsen/sequences/` — load the specific sequence file when drafting or reviewing sequence emails, not at initialization.

---

## Knowledge-Base Files

### agent-knowledge-index.md

**Path:** `realtors/ben-olsen/knowledge-base/agent-knowledge-index.md`

**Description:** This file — the master routing table that maps agent tasks to the knowledge files that contain the rules and context for those tasks.

**Load when:** Agent initialization; any time the agent needs to determine which other files to load for an unfamiliar task.

---

### voice-guide.md

**Path:** `realtors/ben-olsen/knowledge-base/voice-guide.md`

**Description:** Ben Olsen's personal voice, tone, reasoning patterns, hard copy rules, and program framing constraints for all client-facing communications.

**Load when:** Drafting or reviewing emails, SMS, letters, blog posts, sequence copy, social posts, or any outbound message written in Ben's voice; checking formatting rules (no em dashes, no signature blocks, REALTOR not Broker, etc.).

---

### brand-context.md

**Path:** `realtors/ben-olsen/knowledge-base/brand-context.md`

**Description:** BrightWork Realty Advocates brand positioning, promise, audience personas, program inventory, landing page references, and messaging pillars.

**Load when:** Writing marketing copy, program introductions, listing narratives, or outreach that references BrightWork services; selecting the right message angle for a contact persona; explaining what BrightWork offers vs. a generic agent.

---

### local-market-context.md

**Path:** `realtors/ben-olsen/knowledge-base/local-market-context.md`

**Description:** Geographic and market context for Ben's service territory — Lamorinda cities, Moraga Country Club, Walnut Creek, Pleasant Hill, Rossmoor, price bands, school districts, and seasonal dynamics.

**Load when:** Generating appointment briefs; framing a contact by geography; writing copy with local market references; flagging Rossmoor cooperative workflow or MCC floor-plan context; verifying school district boundaries by address.

---

### fair-housing-language.md

**Path:** `realtors/ben-olsen/knowledge-base/fair-housing-language.md`

**Description:** Fair Housing Act and California FEHA compliance rules — protected classes, prohibited language patterns, school district copy rules, and Rossmoor/MCC/senior content constraints.

**Load when:** Any client-facing copy touches a neighborhood, community, property, or contact; compliance review before delivering drafts; uncertain whether phrasing could imply steering, demographic preference, or age-targeted suitability.

---

### contact-classification-taxonomy.md

**Path:** `realtors/ben-olsen/knowledge-base/contact-classification-taxonomy.md`

**Description:** FUB contact classification hierarchy, pipeline stage definitions, lead source-to-sequence mapping, tag interpretation rules, and contact handling decision logic.

**Load when:** Routing a new or existing contact to a sequence; determining enrollment eligibility; interpreting FUB stage, type, or source fields; deciding whether to initiate outreach, pause a sequence, or flag for Ben review.

---

### source-of-truth-matrix.md

**Path:** `realtors/ben-olsen/knowledge-base/source-of-truth-matrix.md`

**Description:** Authoritative data source for every data type the agent reads or writes, conflict resolution rules, and per-system write permissions.

**Load when:** Any read or write to FUB, PostHog, Google Calendar, BatchData, CloudCMA, or SkySlope/Dotloop; resolving conflicting data between systems; before updating contact fields, stages, or tags; before enrolling a contact in a sequence.

---

### posthog-event-schema.md

**Path:** `realtors/ben-olsen/knowledge-base/posthog-event-schema.md`

**Description:** PostHog event definitions, property schemas, and identity linkage conventions for Ben's landing pages and the MCC site.

**Load when:** Enriching contact briefs with web behavioral context; interpreting form submission or page-view events; matching PostHog `distinct_id` to FUB contacts; building or validating UTM-attributed activity timelines.

---

### tag-taxonomy.md

**Path:** `realtors/ben-olsen/fub/tag-taxonomy.md`

**Description:** Complete FUB tag dictionary with source, meaning, and agent interpretation rules — program enrollment tags, MCC tags, suppression flags, VIP markers, and import flags.

**Load when:** Interpreting tags on a FUB contact record; verifying enrollment trigger tags before sequence assignment; checking suppression or VIP flags (`#HitList`, `Unsubscribed`, `chimeimport`, etc.); resolving tag-vs-field conflicts after reading structured fields.

---

### utm-catalog.md

**Path:** `realtors/ben-olsen/utm-catalog.md`

**Description:** Landing page URL registry and UTM parameter conventions (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content`) for all BrightWork campaigns and channels.

**Load when:** Building tracked links in sequence emails, social posts, or SMS; matching a contact's inbound campaign to a landing page; appending UTM parameters to Calendly or program URLs in any outbound copy.

---

---
## FILE: clients/ben-olsen/knowledge/source-of-truth-matrix.md
*Last modified: June 21, 2026 03:16 UTC*

# source-of-truth-matrix.md
Purpose: Defines the authoritative data source for every data type the agent touches, conflict resolution rules, and write permissions per system
Agent Use: Consulted before any read or write operation. If two systems have conflicting data, this file determines which one the agent trusts. Write permissions here are hard limits — the agent does not write to a system unless explicitly permitted.
Maintained by: MKTNG.co
Last updated: June 2026

---

## The Rule

One system owns each data type. When systems conflict, the owner wins. The agent does not reconcile conflicts silently — it flags them for Ben.

---

## System Inventory

### Follow Up Boss (FUB)

CRM. Primary source of truth for all contact data, pipeline stage, sequence state, and activity history. All agent contact operations scope to contacts assigned to Ben Olsen unless explicitly instructed otherwise.

### PostHog

Behavioral analytics. Source of truth for web activity, form submission events, and cross-session identity signals from Ben's landing pages and the MCC site. Enrichment only — never overrides CRM state.

### Google Calendar

Appointment truth. Source of truth for Ben's scheduled appointments, times, and attendees. Calendar Monitor and Brief Generator read from here.

### Calendly

Scheduling layer. Feeds appointments into Google Calendar via integration. Calendly is the intake mechanism; Google Calendar is authoritative for what is actually on Ben's schedule.

### BatchData

Property data. Source of truth for ownership records, equity estimates, and property characteristics used in seller lead enrichment and prospecting sweeps.

### CloudCMA

Comparative market analysis. Draft-only outputs. Never authoritative. Always requires Ben approval before use or client delivery.

### SkySlope / Dotloop

Transaction management. Source of truth for contract state, contingency dates, and closing timelines on active transactions. Agent reads for context; does not modify.

### Cloudflare Workers

Form submission routing layer. Not a data store. Events pass through to FUB and PostHog. Agent does not read from or write to Workers directly.

---

## Data Type Ownership Matrix

| Data Type | Authoritative System | Secondary Reference | Agent Write Permission | Conflict Rule |
|---|---|---|---|---|
| Contact name, email, phone | FUB | Calendly booking form, PostHog identify events | FUB: update only when correcting blank or verified data; log change in activity note | FUB wins. Flag if Calendly or PostHog show different contact details. |
| Contact pipeline stage | FUB | — | FUB: permitted with previous state logged in activity note | FUB wins. Never infer stage from PostHog or Calendar. |
| Contact type (buyer/seller) | FUB (`type` field) | Tags (`Buyer`, `Seller`), form submission context | FUB: read preferred; update only with Ben instruction | Structured `type` field wins over tags. Flag tag conflicts. |
| Contact lead source | FUB (`source` field) | PostHog UTM parameters, landing page events | FUB: read only unless blank and high-confidence source from intake event | FUB `source` wins. Use PostHog UTMs to enrich briefs, not to overwrite source. |
| Active sequence enrollment | FUB (action plans, `Program:` tags) | — | FUB: enroll with Ben approval on first contact | FUB wins. Do not infer enrollment from tags alone — verify action plan state. |
| Last activity date | FUB (`lastActivity`) | PostHog last seen, Google Calendar last appointment | FUB: read only | FUB wins for CRM recency. PostHog supplements behavioral context only. |
| Appointment datetime and attendees | Google Calendar | Calendly booking record, FUB activity log | Read only (both systems) | Google Calendar wins. Flag if FUB has no matching activity log. |
| Property address associated with a contact | FUB (contact record, notes) | BatchData ownership lookup, Calendly form fields | FUB: update only when blank and verified from appointment or intake | FUB wins for contact association. BatchData wins for ownership verification at address level. |
| Property equity estimate | BatchData | FUB notes, CloudCMA draft | Read only (BatchData) | BatchData wins for automated estimates. Ben's manual notes win over BatchData when Ben explicitly stated a figure. Flag the conflict. |
| Property ownership record | BatchData | FUB contact record | Read only (BatchData) | BatchData wins. Flag if FUB contact name does not match BatchData owner of record. |
| Web behavioral events (page views, form submits) | PostHog | Cloudflare Workers event payload (transient) | Read only (PostHog) | PostHog wins. Workers events are not retained — do not treat Workers as reference. |
| PostHog identity (`distinct_id`) | PostHog | FUB email address (identity link assumption) | Read only (PostHog) | PostHog wins for behavioral identity. Match to FUB contact by email; flag if no match. |
| CMA draft | CloudCMA (draft output) | — | Initiate draft generation only; mark all outputs DRAFT | CloudCMA draft is never authoritative. Ben approval required before any client delivery. |
| Transaction contingency dates | SkySlope / Dotloop | FUB notes, Google Calendar | Read only (SkySlope / Dotloop) | SkySlope / Dotloop wins. FUB stage may lag — defer to transaction system for active deals. |
| Closing date | SkySlope / Dotloop | FUB notes, Google Calendar | Read only (SkySlope / Dotloop) | SkySlope / Dotloop wins. Flag if FUB stage does not reflect Under Contract or Closed. |

---

## Write Permission Rules

### FUB — permitted agent writes

- Add or update tags (additive only with `mergeTags: true` — never destructive)
- Update contact stage (log previous stage in activity note before overwriting)
- Log activity notes
- Enroll in sequence (with Ben approval on first contact)
- Update `customZipCodeOrigin` field if blank

### FUB — prohibited agent writes

- Delete contacts
- Remove tags without explicit Ben instruction
- Modify another agent's contacts (Kyle Lerch, Erin Kelly, Claudia Lee are off-limits)
- Change sequence content
- Overwrite existing stage without logging the previous state
- Create contacts without intake workflow authorization
- Send email or SMS directly from FUB without Ben approval

### PostHog — agent reads only. No writes.

### Google Calendar — agent reads only. No writes.

### Calendly — agent reads only. No writes.

### BatchData — agent reads only. No writes.

### CloudCMA — agent initiates draft generation only. All outputs marked DRAFT. Ben approves before any client delivery.

### SkySlope / Dotloop — agent reads only. No writes.

### Cloudflare Workers — not a data store. No reads or writes by the agent.

---

## Conflict Scenarios

### 1. FUB stage says Active, but PostHog shows no web activity in 90 days

**Resolution:** Trust FUB stage as pipeline truth. PostHog absence is not a stage conflict — it means the contact has not visited Ben's web properties recently. Note the behavioral gap in briefs (`DATA_GAP: no recent web activity`). Do not downgrade stage. Flag for Ben only if the contact is in an active sequence that depends on web re-engagement.

### 2. Google Calendar shows an appointment, but FUB has no matching activity log

**Resolution:** Trust Google Calendar for appointment datetime and attendees. Log a FUB activity note documenting the calendar event and the missing CRM record. Attempt to match the calendar attendee to an existing FUB contact by email. If no match, flag for Ben to confirm or create the contact. Do not suppress brief generation if the contact resolves — generate brief with a `DATA_GAP: FUB activity log missing for this appointment` marker.

### 3. BatchData equity estimate conflicts with a figure Ben mentioned in a note

**Resolution:** Ben's manually stated figure takes precedence for client-facing context and brief framing. BatchData figure remains the reference for automated enrichment fields. Flag the conflict to Ben with both values. Do not silently replace either figure. Do not include conflicting numbers in outbound copy without Ben resolution.

### 4. Two FUB tags suggest different sequence enrollment (e.g., `quiet-listing-inquiry` and `zillow-lead`)

**Resolution:** Structured fields win over tags per `contact-classification-taxonomy.md`. Check active action plan state in FUB — the enrolled sequence is authoritative. Do not enroll a second sequence. Flag the conflicting tags for Ben to clean up. If no action plan is active, route by structured `source` and `type`, then by most recent program tag timestamp.

### 5. A contact appears in both Ben's pipeline and another agent's contacts

**Resolution:** Stop all agent operations immediately. Do not read, write, tag, enroll, or draft copy for the contact. Flag for Ben with both agent assignments visible. Kyle Lerch, Erin Kelly, and Claudia Lee contacts are permanently off-limits unless Ben explicitly reassigns the contact.

---

## The Non-Negotiable

No autonomous client contact. All outbound communications — email, SMS, calls initiated by the agent — require Ben to review and approve before sending. This applies regardless of which system the contact data came from.

---

---
## FILE: CLAUDE.md
*Last modified: June 21, 2026 03:16 UTC*

# CLAUDE.md
# Context file for AI-assisted development in COS_Deploy.
# Read this entire file before touching anything.

## What this repo is

COS_Deploy is the runtime deployment for the BrightWork Chief of Staff 
AI agent, built by MKTNG.co (Scott Eggert) for real estate professionals.
It runs on top of Follow Up Boss CRM and delivers an AI operations layer 
via Telegram. First deployment: Ben Olsen, BrightWork Realty Advocates, 
Moraga CA.

This is the repo that ships. It is NOT the content authoring repo.
Content (sequences, knowledge base, platform specs) is authored in the 
sibling repo COS_Project_Build and synced here manually when finalized.

Do not author or edit sequence copy, HTML templates, or platform 
architecture docs in this repo. Make those changes in COS_Project_Build.

---

## Repo structure
COS_Deploy/
├── agents/crewai/          ← CrewAI orchestration (crew.py, bot.py, main.py, config/)
├── tools/                  ← Framework-agnostic API clients (fub.py, telegram.py, logger.py)
├── scripts/                ← One-off utility scripts (push_fub_templates.py)
├── clients/ben-olsen/      ← Tenant config and content for Ben Olsen
│   ├── soul.yaml           ← Agent identity and personality
│   ├── fub-config.yaml     ← FUB stage IDs and action plan IDs (all null currently)
│   ├── knowledge/          ← Domain knowledge markdown files (not yet loaded at runtime)
│   └── sequences/          ← Drip sequence copy and HTML templates
├── platform/               ← Shared specs and architecture docs (human reference only)
├── logs/                   ← Runtime log output (gitignored)
├── .env                    ← Live secrets (gitignored, never commit)
└── .env.example            ← Key names only, no values

---

## Current runtime state (as of June 2026)

What works:
- FUB read operations: get_contact_by_id, get_recent_activity, get_appointments
- Telegram send/receive: bot.py polls for messages, routes to run_brief()
- Pre-appointment brief generation: crew.py run_brief() via CrewAI
- Structured logging: tools/logger.py writes JSON to logs/cos_agent.log
- FUB template push: scripts/push_fub_templates.py (manual, one-way)

What is NOT built yet:
- FastAPI webhook gateway (no /telegram/webhook, /fub/webhook, /health routes)
- FUB write operations (no sequence enrollment, no note writes, no tag writes)
- Knowledge base loader (9 markdown files exist but are not injected into agents)
- Cron scheduler (no APScheduler, no jobs config)
- Morning digest
- Lead alert Telegram card (APPROVE/EDIT/CALL)
- Google Calendar integration (NotImplementedError stub)
- PostHog integration (keys empty, no client code)
- Calendly, Bluedot, CloudCMA, RealEstateAPI, BatchData, Lob.com
- Docker and VPS deployment
- Monitoring health reporter
- Engineer agent for self-repair

What is broken or incomplete:
- FUB action_plans in fub-config.yaml are all null (awaiting Theresa)
- posthog-event-schema.md is empty (0 bytes)
- knowledge/ files not loaded at runtime despite being listed in soul.yaml manifest
- Six platform/playbook files are empty placeholders
- Log file references a placeholder agent name that needs to be replaced

---

## How to run locally

```bash
# Start the Telegram polling loop
python agents/crewai/main.py --mode bot

# Generate a brief directly (no Telegram)
python agents/crewai/main.py --mode brief --contact 12345

# Push FUB email templates (dry run)
python scripts/push_fub_templates.py --dry-run

# Push FUB email templates (live)
python scripts/push_fub_templates.py --live
```

All commands require a populated .env file. Copy .env.example and fill values.

---

## Agent identity

The agent has no confirmed product name yet. Do not introduce or 
proliferate any name. In code, use neutral identifiers: "cos_agent", 
"chief_of_staff", or "agent". In soul.yaml, the name field is a 
placeholder pending Ben Olsen's input. In Telegram messages to Ben, 
the agent refers to itself as "Chief of Staff" until a name is chosen.

If you encounter the name "Scout" anywhere in this codebase, that is 
a stale placeholder. Replace it with "Chief of Staff" in user-facing 
strings and "cos_agent" in code identifiers.

---

## Tenant structure

clients/ben-olsen/ is the only active tenant. When onboarding a new 
realtor, copy this directory, rename it to clients/{realtor-name}/, 
and replace all content. Do not modify platform/ or agents/ to 
accommodate a single tenant.

---

## Zero-hardcoding policy

No API keys, user IDs, stage IDs, sequence IDs, phone numbers, or 
schedule values in source code. They belong in:
- .env for secrets and credentials
- clients/{name}/fub-config.yaml for FUB topology
- clients/{name}/soul.yaml for agent identity
- scheduler-config.json (not yet created) for cron timing

---

## FUB write rules

The agent is currently READ ONLY. No FUB writes are implemented.

When writes are added:
- Always filter to assignedTo: Ben Olsen (user ID 1)
- mergeTags: true for additive tag operations
- mergeTags: false for tag replacement (pass full corrected array)
- Never write to a contact without resolving identity first
- All client-facing sends require explicit realtor approval. No autonomous outbound.

---

## Logging

Every agent action must be logged via tools/logger.py log_event().
Fields: timestamp, agent, action, status, detail, contact_id.
Status values: start, success, failure, fallback.
Log file: logs/cos_agent.log

Do not log to stdout in production code. Use logger.py.
Never include PII (contact email, phone, full name) in log detail fields.
Contact ID only.

---

## LLM

All LLM calls route through OpenRouter, not Anthropic direct.
Base URL: https://openrouter.ai/api/v1
Auth: OPENROUTER_API_KEY in .env

Model assignment by task complexity:
- Brief generation, voice drafts, anything Ben reads: 
    anthropic/claude-sonnet-4-6
- Routing, classification, intent parsing, health summaries: 
    anthropic/claude-haiku-4-5
- Default fallback if unspecified: anthropic/claude-haiku-4-5

Model strings live in agents/crewai/config/agents.yaml per agent role.
Never hardcode a model string in crew.py or bot.py.
Add OPENROUTER_API_KEY to .env and .env.example.
Do not use ANTHROPIC_API_KEY for inference. Keep it only if 
CrewAI requires a fallback — check requirements first.

---

## Monitoring (not yet built, building next)

Target architecture:
- Health reporter runs after every scheduled job and agent action
- Failures route to a separate operator Telegram channel (not Ben's bot)
- Ben's bot has one graceful degradation message per failure type
- Structured log is the source of truth for the Engineer agent (future)

Do not build monitoring into Ben's Telegram interface. 
Errors go to the operator channel, not to the realtor.

---

## Key files

| Need | Read |
|---|---|
| Agent orchestration | agents/crewai/crew.py |
| Telegram bot loop | agents/crewai/bot.py |
| FUB API client | tools/fub.py |
| Logging | tools/logger.py |
| Agent personas | agents/crewai/config/agents.yaml |
| Task definitions | agents/crewai/config/tasks.yaml |
| Ben's identity config | clients/ben-olsen/soul.yaml |
| FUB topology | clients/ben-olsen/fub-config.yaml |
| Full target architecture | platform/architecture/cos-handbook.md |
| Lead alert spec | platform/architecture/lead-alert-pattern.md |

---
