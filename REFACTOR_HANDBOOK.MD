# COS_Deploy Refactor Handbook
# BrightWork CoS / MKTNG.co
# Sprint: June 28, 2026
# Author: Scott Eggert + Claude (Sonnet 4.6)

---

## PURPOSE

This handbook is the complete execution plan for the June 28 architectural
refactor of COS_Deploy. It is written to be run by Claude Code or Cursor
with zero prior context. Every step is self-contained. Every file path is
absolute from the repo root. Every decision is documented here so there is
no improvising.

Read CLAUDE.md first. That file governs all guardrails.
This file governs execution sequence and implementation detail.

Do not run phases out of order. Do not skip steps.
Ben's live deployment must survive this refactor.

---

## PRE-SPRINT CHECKLIST

Run these before writing a single line of code.

```bash
# 1. Verify you are on the Mac Mini, not the droplet
hostname

# 2. Confirm the repo is clean and synced with main
cd /path/to/COS_Deploy
git status
git pull origin main

# 3. Tag the current state — this is your rollback point
git tag pre-refactor-june28
git push origin pre-refactor-june28

# 4. Create the feature branch
git checkout -b refactor/layered-architecture

# 5. Verify Python version
python3 --version  # Must be 3.11.x

# 6. Confirm the agent is running on the droplet (do not touch it yet)
ssh root@droplet-ip "supervisorctl status"
```

---

## PHASE 1 — Configuration and Identity Layer

**Goal:** Eliminate per-module dotenv() calls and hardcoded schedule times.
Single source of truth for env vars, FUB topology, and scheduler config.

**Risk to live system:** Zero — these are additive changes only.
No existing files are deleted or modified in Phase 1.

**Time estimate:** 45-60 minutes

---

### Step 1.1 — Create app/config.py

Create the file `app/__init__.py` (empty) and `app/config.py`.

`app/config.py` must:
- Load .env once using python-dotenv with override=True
- Expose every required env var as a typed module-level constant
- Raise a clear error at import time if a required var is missing
- Never be imported circularly (no imports from tools/ or agents/)

```python
# app/config.py
"""Centralized configuration loader.

This is the single place where environment variables are read.
All other modules import from here instead of calling os.environ directly
or loading dotenv themselves.

Import order matters: this module must be imported before any tools/
or agents/ modules in the entry point.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from repo root regardless of working directory
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH, override=True)


def _require(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Check your .env file at {_ENV_PATH}"
        )
    return value


def _optional(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# LLM Inference
OPENROUTER_API_KEY: str = _require("OPENROUTER_API_KEY")
OPENROUTER_URL: str = "https://openrouter.ai/api/v1/chat/completions"
SONNET_MODEL: str = "anthropic/claude-sonnet-4-6"
HAIKU_MODEL: str = "anthropic/claude-haiku-4-5"

# Follow Up Boss
FUB_API_KEY: str = _require("FUB_API_KEY")
FUB_BASE_URL: str = "https://api.followupboss.com/v1"

# Telegram
TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID: str = _require("TELEGRAM_CHAT_ID")
TELEGRAM_MONITOR_CHAT_ID: str = _require("TELEGRAM_MONITOR_CHAT_ID")
OPERATOR_TELEGRAM_CHAT_ID: str = _require("OPERATOR_TELEGRAM_CHAT_ID")

# Tenant
CLIENT_ID: str = _optional("CLIENT_ID", "ben-olsen")
HEALTH_CHECK_CONTACT_ID: str = _optional("HEALTH_CHECK_CONTACT_ID")

# Paths
REPO_ROOT: Path = Path(__file__).resolve().parent.parent
CLIENTS_DIR: Path = REPO_ROOT / "clients"
LOGS_DIR: Path = REPO_ROOT / "logs"
```

**Verification:**
```python
# Run this to confirm it works before moving on
python3 -c "from app.config import FUB_API_KEY, TELEGRAM_CHAT_ID; print('Config OK')"
```

---

### Step 1.2 — Create app/schemas.py

Create `app/schemas.py` with the four Pydantic contracts.

```python
# app/schemas.py
"""Internal data contracts between layers.

These models are the only way the transport, router, and handler
layers communicate. Do not pass raw strings or dicts between layers.

Adding a new intent type: add it to the Literal in RoutedIntent.intent_type.
Adding a new callback action: add it to InboundCallback.data format docs.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class InboundMessage(BaseModel):
    """Raw inbound Telegram message, normalized from the polling loop."""
    chat_id: str
    raw_text: str
    timestamp: int
    client_id: str  # tenant identifier, e.g. "ben-olsen"


class InboundCallback(BaseModel):
    """Inline keyboard button press from a Telegram message."""
    chat_id: str
    callback_query_id: str
    data: str           # format: "action:contact_id", e.g. "approve:31735"
    message_id: int     # ID of the original message with the keyboard
    client_id: str


class RoutedIntent(BaseModel):
    """Result of Haiku intent classification. Passed to handlers."""
    original_message: InboundMessage
    intent_type: Literal[
        "brief_request",
        "draft_communication",
        "draft_outreach",
        "hot_leads",
        "hot_leads_list",
        "status_check",
        "greeting",
        "identity_query",
        "help_request",
        "unknown",
    ]
    entity: Optional[str] = None        # contact name or ID extracted by Haiku
    comm_type: Optional[str] = None     # email | sms | note (generative intents)
    confidence: float = 0.0


class HandlerResult(BaseModel):
    """Standard return from every handler. Transport layer reads this."""
    success: bool
    telegram_output: str            # what Ben receives — always set
    operator_note: Optional[str] = None   # sent to monitor if set
    fub_writes: int = 0             # count of FUB mutations performed
    error_details: Optional[str] = None   # logged, never shown to Ben
```

---

### Step 1.3 — Create clients/ben-olsen/scheduler_config.json

Extract hardcoded schedule values from bot.py into this file.

```json
{
  "morning_digest": {
    "hour": 8,
    "minute": 30,
    "timezone_offset_hours": -7,
    "note": "Pacific time. UTC-7 (PDT). Change to -8 in November when PST begins."
  },
  "pre_appointment_check": {
    "interval_seconds": 900,
    "window_start_minutes": 90,
    "window_end_minutes": 120
  },
  "hot_leads_silence_days": 14
}
```

---

### Step 1.4 — Phase 1 verification

```bash
# All of these must succeed before Phase 2 begins
python3 -c "from app.config import FUB_API_KEY; print('config OK')"
python3 -c "from app.schemas import InboundMessage, RoutedIntent, HandlerResult; print('schemas OK')"
python3 -c "import json; c=json.load(open('clients/ben-olsen/scheduler_config.json')); print('scheduler config OK:', c['morning_digest'])"
```

---

## PHASE 2 — Services Layer (FUB Resilience)

**Goal:** All FUB API calls go through one client with retry logic.
Eliminates silent failures on transient FUB errors.

**Risk to live system:** Low. We are building the new client and refactoring
tool imports. The live droplet still runs old bot.py and is untouched.

**Time estimate:** 60-90 minutes

---

### Step 2.1 — Create services/__init__.py and services/fub_client.py

```python
# services/fub_client.py
"""Centralized FUB API client with retry and rate-limit handling.

All tools that make FUB API calls must import from this module.
Do not use requests.Session directly in tools/.

FUB rate limits: sliding 10-second window, ~180-200 global requests,
20 for events, 10 for notes. The retry adapter handles 429s automatically.

Usage:
    from services.fub_client import fub_get, fub_post, fub_put

    data = fub_get("/people/31735")
    result = fub_post("/notes", json={"body": "...", "personId": 31735})
"""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import FUB_API_KEY, FUB_BASE_URL
from tools.logger import log_event

_SESSION: requests.Session | None = None


def _get_session() -> requests.Session:
    """Return the singleton FUB session, creating it if needed."""
    global _SESSION
    if _SESSION is not None:
        return _SESSION

    session = requests.Session()
    session.auth = (FUB_API_KEY, "")

    retry_strategy = Retry(
        total=3,
        backoff_factor=2,           # waits: 2s, 4s, 8s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "PATCH"],
        raise_on_status=False,      # we handle status ourselves
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    _SESSION = session
    return _SESSION


def fub_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET from the FUB API. Returns parsed JSON dict.

    Raises requests.HTTPError on non-2xx after retries exhausted.
    """
    session = _get_session()
    url = f"{FUB_BASE_URL}{path}"
    resp = session.get(url, params=params or {}, timeout=15)

    if not resp.ok:
        log_event(
            "fub_client", "get", "failure",
            detail=f"HTTP {resp.status_code} — {path}",
            file=__file__, function="fub_get",
        )
        resp.raise_for_status()

    return resp.json()


def fub_post(path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
    """POST to the FUB API. Returns parsed JSON dict.

    Raises requests.HTTPError on non-2xx after retries exhausted.
    """
    session = _get_session()
    url = f"{FUB_BASE_URL}{path}"
    resp = session.post(url, json=json or {}, timeout=15)

    if not resp.ok:
        log_event(
            "fub_client", "post", "failure",
            detail=f"HTTP {resp.status_code} — {path}",
            file=__file__, function="fub_post",
        )
        resp.raise_for_status()

    return resp.json()


def fub_put(path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
    """PUT to the FUB API. Returns parsed JSON dict.

    Raises requests.HTTPError on non-2xx after retries exhausted.
    """
    session = _get_session()
    url = f"{FUB_BASE_URL}{path}"
    resp = session.put(url, json=json or {}, timeout=15)

    if not resp.ok:
        log_event(
            "fub_client", "put", "failure",
            detail=f"HTTP {resp.status_code} — {path}",
            file=__file__, function="fub_put",
        )
        resp.raise_for_status()

    return resp.json()
```

---

### Step 2.2 — Refactor tools/fub.py to use fub_client

Open `tools/fub.py`. Make the following changes:

1. Remove the module-level `requests.Session()` instantiation and auth setup.
2. Remove any `load_dotenv()` call and `FUB_API_KEY` / `FUB_BASE` constants.
3. Import `fub_get` from `services.fub_client`.
4. Replace every `session.get(f"{FUB_BASE}{path}", auth=(FUB_API_KEY, ""), ...)` 
   call with `fub_get(path, params=...)`.
5. Leave all business logic (search, disambiguation, contact summary) unchanged.
6. Add `from app.config import CLIENT_ID` if any config values are needed.

Do not change any function signatures or return types.

---

### Step 2.3 — Refactor tools/fub_write.py to use fub_client

Same pattern as 2.2:

1. Remove session setup, dotenv, and auth constants.
2. Import `fub_post`, `fub_put` from `services.fub_client`.
3. Replace direct session calls.
4. Function signatures unchanged.

---

### Step 2.4 — Refactor tools/fub_activity.py to use fub_client

Same pattern. This file is newer (June 26) and already has a clean
structure. Just replace the `_fub_get()` private helper with imports
from `services.fub_client`.

---

### Step 2.5 — Refactor tools/hot_leads.py to use fub_client

Same pattern. Replace the private `_fub_get()` helper. The
`get_active_action_plan_ids()` and `get_hot_leads_going_cold()` functions
stay unchanged.

---

### Step 2.6 — Refactor tools/appointments.py to use fub_client

Same pattern. The client-side date filtering logic stays exactly as-is.
Only the HTTP call mechanism changes.

---

### Step 2.7 — Phase 2 verification

```bash
# Unit test the FUB client directly
python3 -c "
from services.fub_client import fub_get
data = fub_get('/people/31735')
print('FUB client OK — name:', data.get('firstName'))
"

# Verify refactored tools still import cleanly
python3 -c "from tools.fub import search_contacts, get_contact_by_id; print('fub.py OK')"
python3 -c "from tools.fub_write import add_note_to_contact; print('fub_write.py OK')"
python3 -c "from tools.fub_activity import get_contact_context; print('fub_activity.py OK')"
python3 -c "from tools.hot_leads import get_hot_leads_going_cold; print('hot_leads.py OK')"
python3 -c "from tools.appointments import get_upcoming_appointments; print('appointments.py OK')"

# Live FUB read test through refactored stack
python3 -c "
from tools.fub import get_contact_by_id
contact = get_contact_by_id('31735')
print('Live FUB read OK:', contact.get('firstName'), contact.get('lastName'))
"
```

All five imports must succeed and the live FUB read must return data before
Phase 3 begins.

---

## PHASE 3 — Decompose bot.py into Layered Architecture

**Goal:** Split bot.py into transport, router, and handlers.
This is the most complex phase. Execute methodically.

**Risk to live system:** Zero until deployment. The droplet still runs
old bot.py. We are building in parallel.

**Time estimate:** 2-3 hours

**Order within this phase matters:**
3.1 core/router.py first (Haiku classifier)
3.2 handlers/ second (business logic)
3.3 core/scheduler.py third (scheduled jobs)
3.4 core/transport.py fourth (polling loop)
3.5 core/main.py last (entry point, wires everything)

---

### Step 3.1 — Create core/__init__.py and core/router.py

Extract the Haiku intent classifier and ConversationBuffer from
`tools/intent_router.py` into `core/router.py`.

`core/router.py` must:
- Maintain the `ConversationBuffer` class (identical logic, new location)
- Expose `classify_intent(message: InboundMessage, buffer: ConversationBuffer) -> RoutedIntent`
- Import model constants from `app.config`
- Return a `RoutedIntent` (not a raw dict)
- Handle the Haiku markdown fence stripping bug
- Handle the leading whitespace bug in OpenRouter responses

```python
# core/router.py
"""Haiku-powered intent classifier.

Receives an InboundMessage, sends it to Haiku with recent conversation
context, and returns a RoutedIntent that the transport layer passes
to the appropriate handler.

Known Haiku quirks (do not remove these workarounds):
- Haiku wraps JSON in markdown fences despite prompt instructions.
  Strip with: raw.strip('` \\n').removeprefix('json').strip()
- OpenRouter responses have leading whitespace before JSON.
  Always use json.loads(resp.text.strip()) not resp.json().
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from app.config import OPENROUTER_API_KEY, OPENROUTER_URL, HAIKU_MODEL
from app.schemas import InboundMessage, RoutedIntent
from tools.logger import log_event

_INTENTS = """
brief_request - user wants a contact brief, profile, or lookup by name or ID; includes "look up", "find", "what's X's address"
hot_leads - user asks about cooling hot leads in general
hot_leads_list - user wants to see the cooling hot leads list; says "hot leads", "show me the list", or "yes" after being prompted
draft_outreach - user wants outreach drafted for one or all cold hot leads; entity is the contact name or "all"
draft_communication - user wants to draft an email, text, or note to someone; entity is the full contact name if provided; type is email/sms/note
status_check - user wants recent log output
greeting - hello, hi, checking in
identity_query - asking what the agent is or does
help_request - asking for commands or help
unknown - anything else
"""

_SYSTEM_PROMPT = f"""You are an intent classifier for a real estate agent's AI Chief of Staff.
Classify the user's message into exactly one intent from this list:
{_INTENTS}

Extract any entity (contact name, contact ID, or "all") if present.
For draft_communication: extract the full contact name as entity and the type (email/sms/note, default email).
For brief_request: treat "look up", "find", "what's X's address", and similar lookup phrases as brief_request.
For draft_outreach: extract the contact name as entity, or "all" if the user says "all", "everyone", "draft all".

Respond ONLY with valid JSON in this exact format:
{{"intent": "intent_name", "entity": "extracted entity or null", "type": "email or sms or note or null", "confidence": 0.0}}

No other text. No markdown. Just the JSON object."""


class ConversationBuffer:
    """Rolling window of recent exchanges, persisted to disk.

    Survives agent restarts so Ben can resume threads.
    """

    MAX_TURNS: int = 10
    PERSIST_PATH: Path = Path("/root/COS_Deploy/logs/conversation_buffer.json")

    def __init__(self) -> None:
        self._turns: list[dict[str, str]] = []
        self._load()

    def _load(self) -> None:
        try:
            if self.PERSIST_PATH.exists():
                with self.PERSIST_PATH.open(encoding="utf-8") as f:
                    self._turns = json.load(f)
        except Exception:
            self._turns = []

    def _save(self) -> None:
        try:
            self.PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            with self.PERSIST_PATH.open("w", encoding="utf-8") as f:
                json.dump(self._turns[-self.MAX_TURNS:], f)
        except Exception:
            pass

    def add(self, role: str, content: str) -> None:
        self._turns.append({
            "role": role,
            "content": content,
            "ts": datetime.now(tz=timezone.utc).isoformat(),
        })
        if len(self._turns) > self.MAX_TURNS:
            self._turns = self._turns[-self.MAX_TURNS:]
        self._save()

    def recent(self, n: int = 3) -> list[dict[str, str]]:
        return self._turns[-n:]

    def last_agent_message(self) -> str | None:
        for turn in reversed(self._turns):
            if turn.get("role") == "assistant":
                return turn.get("content")
        return None


def classify_intent(message: InboundMessage, buffer: ConversationBuffer) -> RoutedIntent:
    """Classify inbound message intent via Haiku.

    Returns a RoutedIntent. Never raises — falls back to intent_type='unknown'
    on any failure.
    """
    recent = buffer.recent(3)
    context_lines = []
    for turn in recent:
        role = "Ben" if turn["role"] == "user" else "Agent"
        context_lines.append(f"{role}: {turn['content'][:200]}")
    context = "\n".join(context_lines)

    user_prompt = (
        f"Recent conversation:\n{context}\n\nNew message: {message.raw_text}"
        if context
        else f"Message: {message.raw_text}"
    )

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": HAIKU_MODEL,
                "max_tokens": 100,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = json.loads(resp.text.strip())
        raw_content = data["choices"][0]["message"]["content"].strip()
        raw_content = raw_content.strip("` \n").removeprefix("json").strip()
        parsed = json.loads(raw_content)

        intent_type = parsed.get("intent", "unknown")
        log_event(
            "router", "classify", "success",
            detail=f"{message.raw_text[:50]} -> {intent_type}",
            file=__file__, function="classify_intent",
        )
        return RoutedIntent(
            original_message=message,
            intent_type=intent_type,
            entity=parsed.get("entity"),
            comm_type=parsed.get("type"),
            confidence=float(parsed.get("confidence", 0.0)),
        )
    except Exception as exc:
        log_event(
            "router", "classify", "failure",
            detail=str(exc), exc_info=exc,
            file=__file__, function="classify_intent",
        )
        return RoutedIntent(
            original_message=message,
            intent_type="unknown",
            entity=None,
            comm_type=None,
            confidence=0.0,
        )
```

---

### Step 3.2 — Create handlers/

Create `handlers/__init__.py` (empty) and the five handler files.

Each handler follows this exact pattern:

```python
# handlers/[name].py
"""[Handler description]"""

from __future__ import annotations

from app.schemas import HandlerResult, RoutedIntent
from tools.logger import log_event
from tools.telegram import send_operator_alert

FALLBACK_MESSAGE = "I ran into a problem with that. Check FUB directly: https://app.followupboss.com"

def handle(intent: RoutedIntent) -> HandlerResult:
    log_event("[handler]", "[action]", "start", ...)
    try:
        # ... business logic using tools/ only ...
        return HandlerResult(success=True, telegram_output="...")
    except Exception as exc:
        log_event("[handler]", "[action]", "failure", detail=str(exc), exc_info=exc, ...)
        send_operator_alert(f"[handler] failed: {exc}")
        return HandlerResult(
            success=False,
            telegram_output=FALLBACK_MESSAGE,
            error_details=str(exc),
        )
```

**handlers/brief.py:**
Extract `_run_brief_for_contact`, `_handle_disambiguation_result`,
`_send_contact_disambiguation_prompt`, `_duplicate_merge_note` from bot.py.
These functions are already well-isolated. Move them with minimal changes.
The handler's `handle(intent: RoutedIntent) -> HandlerResult` function routes
to these based on whether entity is numeric (ID lookup) or string (name lookup).

**handlers/generative.py:**
Extract `_handle_generative_request` from bot.py.
Imports `draft_communication` from `tools.draft_communication`.
Imports `get_contact_context` from `tools.fub_activity`.
Imports `search_contacts`, `get_contact_by_id` from `tools.fub`.

**handlers/hot_leads.py:**
Extract `_handle_hot_leads_list` from bot.py.
The draft-for-one-lead flow routes to `handlers/generative.py` — call
`generative.handle(intent)` when entity is set.

**handlers/lead_alert.py:**
Extract `_handle_callback` from bot.py.
This handler accepts an `InboundCallback` not a `RoutedIntent`.
Define a separate `handle_callback(callback: InboundCallback) -> HandlerResult`.
Imports: `enroll_in_action_plan`, `add_note_to_contact` from `tools.fub_write`.
State file: still reads/writes `logs/lead_alert_state.json` (unchanged).

**handlers/status.py:**
Extract `_get_status_log` from bot.py.
Single function, minimal logic.

---

### Step 3.3 — Create core/scheduler.py

Extract scheduled job logic from bot.py. The scheduler must:
- Read runtimes from `clients/ben-olsen/scheduler_config.json`
- Persist `last_run` timestamps to `logs/scheduler_state.json`
- Not fire a job if `last_run` was within the same hour (morning digest)
- Survive restarts (pre-appointment brief dedup moves to the state file)

```python
# core/scheduler.py
"""SimpleScheduler with JSON-backed last_run persistence.

Reads job configuration from clients/{client_id}/scheduler_config.json.
Persists last_run timestamps to logs/scheduler_state.json so jobs
do not re-fire after a process restart within the same window.

Scheduled jobs call tools/ directly. They do not go through RoutedIntent.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from app.config import CLIENT_ID, CLIENTS_DIR, LOGS_DIR
from tools.logger import log_event

_STATE_PATH = LOGS_DIR / "scheduler_state.json"
_CONFIG_PATH = CLIENTS_DIR / CLIENT_ID / "scheduler_config.json"


def _load_config() -> dict:
    with _CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _load_state() -> dict:
    if not _STATE_PATH.exists():
        return {"briefed_appointment_ids": [], "last_morning_digest_hour": -1}
    try:
        with _STATE_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"briefed_appointment_ids": [], "last_morning_digest_hour": -1}


def _save_state(state: dict) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f)


class SimpleScheduler:
    """Daemon thread scheduler. Reads config from tenant directory."""

    def __init__(self) -> None:
        self._daily_jobs: list[dict] = []
        self._interval_jobs: list[dict] = []
        self._thread: threading.Thread | None = None

    def add_daily(self, *, hour: int, minute: int, job: Callable, name: str) -> None:
        self._daily_jobs.append({
            "hour": hour, "minute": minute, "job": job, "name": name
        })

    def add_interval(self, *, seconds: int, job: Callable, name: str) -> None:
        self._interval_jobs.append({
            "seconds": seconds, "job": job, "name": name,
            "next_run": time.monotonic() + seconds,
        })

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while True:
            try:
                self._tick()
            except Exception as exc:
                log_event(
                    "scheduler", "tick", "failure",
                    detail=str(exc), exc_info=exc,
                    file=__file__, function="_loop",
                )
            time.sleep(60)

    def _tick(self) -> None:
        config = _load_config()
        offset = config["morning_digest"]["timezone_offset_hours"]
        now_local = datetime.now(tz=timezone.utc) + timedelta(hours=offset)
        state = _load_state()

        for job_def in self._daily_jobs:
            if (
                now_local.hour == job_def["hour"]
                and now_local.minute < job_def["minute"] + 5
                and state.get("last_morning_digest_hour") != now_local.hour
            ):
                log_event(
                    "scheduler", job_def["name"], "start",
                    file=__file__, function="_tick",
                )
                try:
                    job_def["job"]()
                    state["last_morning_digest_hour"] = now_local.hour
                    _save_state(state)
                    log_event(
                        "scheduler", job_def["name"], "success",
                        file=__file__, function="_tick",
                    )
                except Exception as exc:
                    log_event(
                        "scheduler", job_def["name"], "failure",
                        detail=str(exc), exc_info=exc,
                        file=__file__, function="_tick",
                    )

        for job_def in self._interval_jobs:
            if time.monotonic() >= job_def["next_run"]:
                log_event(
                    "scheduler", job_def["name"], "start",
                    file=__file__, function="_tick",
                )
                try:
                    job_def["job"](state)
                    _save_state(state)
                    log_event(
                        "scheduler", job_def["name"], "success",
                        file=__file__, function="_tick",
                    )
                except Exception as exc:
                    log_event(
                        "scheduler", job_def["name"], "failure",
                        detail=str(exc), exc_info=exc,
                        file=__file__, function="_tick",
                    )
                finally:
                    job_def["next_run"] = time.monotonic() + job_def["seconds"]
```

---

### Step 3.4 — Create core/transport.py

The transport layer does exactly one thing: poll Telegram, normalize
events into `InboundMessage` or `InboundCallback`, and pass them to
a routing function. It contains no business logic.

```python
# core/transport.py
"""Telegram long-poll transport layer.

This module is responsible for receiving messages from Telegram and
passing them to the router. It contains no business logic.

If Telegram polling behavior ever changes (e.g., migrating to webhooks),
only this file changes. The router and handlers are unaffected.
"""

from __future__ import annotations

import time
from typing import Callable

from app.config import CLIENT_ID, TELEGRAM_CHAT_ID, TELEGRAM_MONITOR_CHAT_ID
from app.schemas import InboundCallback, InboundMessage
from tools.logger import log_event
from tools.telegram import (
    BOT_TOKEN,
    TELEGRAM_API,
    extract_message,
    get_updates,
    send_monitor_copy,
    session as telegram_session,
)

POLL_TIMEOUT = 30


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
    """Acknowledge queued updates on startup without executing them."""
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


def poll(
    on_message: Callable[[InboundMessage], str | None],
    on_callback: Callable[[InboundCallback], str | None],
) -> None:
    """Start the polling loop. Blocks indefinitely.

    on_message: called with each InboundMessage; return value sent to Ben.
    on_callback: called with each InboundCallback; return value sent to Ben.
    """
    configured_chat_id = str(TELEGRAM_CHAT_ID)
    monitor_chat_id = str(TELEGRAM_MONITOR_CHAT_ID)
    offset = _drain_stale_updates()

    from tools.telegram import send_long_message

    while True:
        updates = get_updates(offset=offset, timeout=POLL_TIMEOUT)
        for update in updates:
            update_id = update.get("update_id", 0)
            offset = update_id + 1

            message = extract_message(update)
            if message:
                chat_id = message["chat_id"]
                if chat_id in (configured_chat_id, monitor_chat_id):
                    text = message["text"]
                    ts = int(time.time())

                    log_event(
                        "transport", "inbound", "success",
                        detail=text, file=__file__, function="poll",
                    )
                    send_monitor_copy(f"[BEN -> CoS] {text}")

                    inbound = InboundMessage(
                        chat_id=chat_id,
                        raw_text=text,
                        timestamp=ts,
                        client_id=CLIENT_ID,
                    )
                    reply = on_message(inbound)
                    if reply is not None:
                        send_long_message(reply, chat_id=chat_id)
                        send_monitor_copy(f"[BEN] {text}\n[CoS] {reply[:500]}")
                        log_event(
                            "transport", "outbound", "success",
                            detail=reply[:200], file=__file__, function="poll",
                        )

            callback_query = update.get("callback_query")
            if callback_query:
                callback_id = callback_query.get("id", "")
                _answer_callback_query(callback_id)
                cb_chat_id = str(
                    callback_query.get("message", {}).get("chat", {}).get("id", "")
                )
                if cb_chat_id == configured_chat_id:
                    inbound_cb = InboundCallback(
                        chat_id=cb_chat_id,
                        callback_query_id=callback_id,
                        data=callback_query.get("data", ""),
                        message_id=callback_query.get("message", {}).get("message_id", 0),
                        client_id=CLIENT_ID,
                    )
                    reply = on_callback(inbound_cb)
                    if reply is not None:
                        send_long_message(reply, chat_id=cb_chat_id)
```

---

### Step 3.5 — Create core/main.py

The entry point wires everything together. This replaces
`agents/crewai/main.py` and `agents/crewai/bot.py`.

```python
# core/main.py
"""CoS Agent entry point.

Wires transport, router, handlers, and scheduler together.
This file orchestrates; it contains no business logic.

Usage:
    python -m core.main
"""

from __future__ import annotations

import re

from app.config import CLIENT_ID
from app.schemas import InboundCallback, InboundMessage, RoutedIntent
from core.router import ConversationBuffer, classify_intent
from core.scheduler import SimpleScheduler
from core.transport import poll
from handlers import brief, generative, hot_leads, lead_alert, status
from tools.health import run_health_check
from tools.logger import log_event
from tools.telegram import send_long_message, send_operator_alert

STATUS_PATTERN = re.compile(r"^(?:/)?status(?:\s+(\d+))?$", re.IGNORECASE)

GREETING_REPLY = "Chief of Staff here. Send me a contact ID or name and I'll pull a brief."
IDENTITY_REPLY = (
    "I'm Ben's Chief of Staff. I pull pre-appointment briefs, draft emails in your voice, "
    "and monitor your pipeline. Send me a name or contact ID to get started."
)
HELP_REPLY = (
    "Here's what I can do:\n"
    "* brief [name] or [ID] -- pull a contact brief\n"
    "* draft an email to [name] about [topic]\n"
    "* hot leads -- see your warm pipeline going cold\n"
    "* status -- check recent agent log"
)
UNKNOWN_REPLY = (
    "I didn't catch that. Try asking me to draft an email, "
    "pull up a contact, or check your hot leads."
)

_buffer = ConversationBuffer()


def _route_message(message: InboundMessage) -> str | None:
    """Classify intent and dispatch to handler. Return reply string or None."""

    # Status command bypasses classifier
    status_match = STATUS_PATTERN.match(message.raw_text.strip())
    if status_match:
        lines = int(status_match.group(1) or 50)
        result = status.handle_status(lines)
        return result.telegram_output

    # Classify via Haiku
    intent = classify_intent(message, _buffer)

    if intent.intent_type == "greeting":
        return GREETING_REPLY

    if intent.intent_type == "identity_query":
        return IDENTITY_REPLY

    if intent.intent_type == "help_request":
        return HELP_REPLY

    if intent.intent_type == "brief_request":
        result = brief.handle(intent)
        return result.telegram_output

    if intent.intent_type in ("hot_leads", "hot_leads_list"):
        result = hot_leads.handle(intent)
        return result.telegram_output

    if intent.intent_type in ("draft_outreach", "draft_communication"):
        result = generative.handle(intent)
        return result.telegram_output

    if intent.intent_type == "status_check":
        result = status.handle_status(50)
        return result.telegram_output

    return UNKNOWN_REPLY


def _route_callback(callback: InboundCallback) -> str | None:
    """Route inline keyboard button presses to lead_alert handler."""
    result = lead_alert.handle_callback(callback)
    return result.telegram_output if result.telegram_output else None


def _build_scheduled_jobs(scheduler: SimpleScheduler) -> None:
    """Register all scheduled jobs. Job functions call tools/ directly."""
    from tools.appointments import format_appointment_summary, get_contact_id_from_appointment, get_upcoming_appointments
    from tools.hot_leads import get_hot_leads_going_cold
    import random
    from datetime import timedelta, timezone, datetime

    def morning_digest() -> None:
        from app.config import TELEGRAM_CHAT_ID
        from tools.telegram import send_long_message

        now_pacific = datetime.now(tz=timezone.utc) + timedelta(hours=-7)
        day_name = now_pacific.strftime("%A")
        greetings = [
            "Good morning, Ben.",
            "Morning, Ben. Here's your day.",
            "Buenos dias, Ben.",
            f"Happy {day_name}, Ben.",
            "Good morning, Ben. Another day in Lamorinda.",
        ]
        lines = [random.choice(greetings), ""]

        appointments = get_upcoming_appointments(hours_ahead=18)
        if appointments:
            lines.append("Today's appointments:")
            for appt in appointments:
                summary = format_appointment_summary(appt)
                contact_id = get_contact_id_from_appointment(appt)
                if contact_id:
                    summary += f"\n  Send: brief {contact_id} for a full brief"
                lines.append(f"* {summary}")
        else:
            lines.append("No appointments in FUB today.")

        lines.append("")

        cold = get_hot_leads_going_cold(days_silent=14)
        if cold:
            lines.append(
                f"One thing worth knowing: you have {len(cold)} lead"
                f"{'s' if len(cold) != 1 else ''} tagged Hot 90 Days with no "
                f"activity in the last 14 days. They're warm and going cold. "
                f"Reply \"hot leads\" to see the list."
            )
        else:
            lines.append("Your Hot 90 Days leads are all active. Nothing going cold.")

        send_long_message("\n".join(lines), chat_id=str(TELEGRAM_CHAT_ID))

    def pre_appointment_check(state: dict) -> None:
        from app.config import TELEGRAM_CHAT_ID
        from tools.telegram import send_long_message, send_message
        from datetime import datetime, timezone
        from agents.crewai.crew import run_brief as _run_brief

        appointments = get_upcoming_appointments(hours_ahead=2)
        now = datetime.now(tz=timezone.utc)
        briefed_ids: list = state.setdefault("briefed_appointment_ids", [])

        for appt in appointments:
            start_str = appt.get("start", "")
            try:
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            except ValueError:
                continue

            minutes_until = (start - now).total_seconds() / 60
            if minutes_until > 120 or minutes_until < 90:
                continue

            appt_id = appt.get("id")
            if appt_id in briefed_ids:
                continue
            briefed_ids.append(appt_id)

            contact_id = get_contact_id_from_appointment(appt)
            if not contact_id:
                title = appt.get("title", "your next appointment")
                send_message(
                    f"Heads up -- {title} starts in about 2 hours. "
                    "No contact linked in FUB so I can't pull a brief automatically. "
                    "Send me a name or ID if you want one.",
                    chat_id=str(TELEGRAM_CHAT_ID),
                )
                continue

            try:
                brief_text = _run_brief(CLIENT_ID, contact_id)
                title = appt.get("title", "upcoming appointment")
                send_long_message(
                    f"2-hour brief for {title}:\n\n{brief_text}",
                    chat_id=str(TELEGRAM_CHAT_ID),
                )
            except Exception as exc:
                log_event(
                    "scheduler", "pre_appointment_brief", "failure",
                    detail=str(exc), contact_id=contact_id, exc_info=exc,
                    file=__file__, function="pre_appointment_check",
                )
                send_operator_alert(f"Pre-appointment brief failed for contact {contact_id}: {exc}")

    scheduler.add_daily(hour=8, minute=30, job=morning_digest, name="morning_digest")
    scheduler.add_interval(seconds=900, job=pre_appointment_check, name="pre_appointment_check")


def main() -> None:
    """Start the CoS agent."""
    from tools.health import run_health_check
    from tools.fub import get_contact_by_id
    from app.config import HEALTH_CHECK_CONTACT_ID
    import os

    log_event("cos_agent", "startup", "start", file=__file__, function="main")

    # Startup health check
    if HEALTH_CHECK_CONTACT_ID:
        try:
            get_contact_by_id(HEALTH_CHECK_CONTACT_ID)
            log_event("cos_agent", "startup", "success",
                      detail="FUB connectivity confirmed", file=__file__, function="main")
        except Exception as exc:
            send_operator_alert(f"CoS Agent startup failed -- FUB check: {exc}")
            raise SystemExit(f"FUB connectivity check failed: {exc}")

    send_operator_alert("CoS Agent is online.")
    log_event("cos_agent", "startup", "success", file=__file__, function="main")

    # Start scheduler
    scheduler = SimpleScheduler()
    _build_scheduled_jobs(scheduler)
    scheduler.start()

    # Start buffer (already initialized at module level)
    log_event("cos_agent", "buffer", "start",
              detail="ConversationBuffer loaded", file=__file__, function="main")

    # Start polling loop (blocks)
    try:
        poll(on_message=_route_message, on_callback=_route_callback)
    except KeyboardInterrupt:
        send_operator_alert("CoS Agent going offline.")
        log_event("cos_agent", "shutdown", "success", file=__file__, function="main")


if __name__ == "__main__":
    main()
```

---

### Step 3.6 — Phase 3 verification

```bash
# Verify all new modules import cleanly
python3 -c "from app.schemas import InboundMessage, RoutedIntent, HandlerResult; print('schemas OK')"
python3 -c "from core.router import ConversationBuffer, classify_intent; print('router OK')"
python3 -c "from core.scheduler import SimpleScheduler; print('scheduler OK')"
python3 -c "from core.transport import poll; print('transport OK')"
python3 -c "from handlers import brief, generative, hot_leads, lead_alert, status; print('handlers OK')"
python3 -c "from core.main import main; print('main OK')"

# Simulate intent classification end-to-end
python3 -c "
from app.schemas import InboundMessage
from core.router import ConversationBuffer, classify_intent
import time

msg = InboundMessage(
    chat_id='test', raw_text='Draft an email to Ann De Villiers about Sunday open house',
    timestamp=int(time.time()), client_id='ben-olsen'
)
buf = ConversationBuffer()
result = classify_intent(msg, buf)
print('Intent:', result.intent_type, '| Entity:', result.entity, '| Type:', result.comm_type)
"

# Simulate brief handler
python3 -c "
from app.schemas import InboundMessage, RoutedIntent
from handlers import brief
import time

msg = InboundMessage(chat_id='test', raw_text='brief 31735', timestamp=int(time.time()), client_id='ben-olsen')
intent = RoutedIntent(original_message=msg, intent_type='brief_request', entity='31735', confidence=0.95)
result = brief.handle(intent)
print('Brief handler result — success:', result.success)
print('Output preview:', result.telegram_output[:200])
"
```

---

## PHASE 4 — Integration Test and Hot Swap

**Goal:** Verify the refactored system works end-to-end against Ben's live
FUB account, then swap supervisord to run the new entry point.

**Risk to live system:** Medium during the swap window. Mitigated by having
the git tag rollback ready and the swap taking under 60 seconds.

**Time estimate:** 30-45 minutes

---

### Step 4.1 — Read-only integration test

Start the new agent locally against the live Droplet... no wait.
Run this ON THE DROPLET after pushing the branch. Do not run two
agent instances simultaneously. Stop the old agent first.

```bash
# On the droplet:
git fetch
git checkout refactor/layered-architecture
pip install -r requirements.txt

# Stop old agent (Ben's Telegram goes dark for < 2 min)
supervisorctl stop cos-agent

# Start new agent manually to watch output
cd /root/COS_Deploy
python3 -m core.main
```

Send these test messages from Ben's Telegram (or the monitor channel):
1. "hot leads" -- verify list comes back
2. "brief 31735" -- verify brief generates
3. "Draft an email to Ann De Villiers about the open house Sunday 1-4"
   -- verify draft returns in Ben's voice, no em dashes
4. "/status" -- verify log tail
5. "Look up Ann De Villiers" -- verify brief routes correctly

If all five pass, proceed. If any fail, Ctrl+C and diagnose before deploying.

---

### Step 4.2 — Update supervisord config

```bash
# Current conf points to agents/crewai/bot.py
# Update to point to core/main.py

cat /etc/supervisor/conf.d/cos-agent.conf
```

Edit the `command` line:
```
# OLD
command=python agents/crewai/bot.py

# NEW
command=python -m core.main
```

The `directory` line stays as `/root/COS_Deploy`.
The `environment` line stays unchanged.

---

### Step 4.3 — Deploy

```bash
# Push branch to GitHub
git add -A  # verify git status first
git commit -m "refactor: layered architecture - phase 1-4 complete"
git push origin refactor/layered-architecture

# On droplet: restart via supervisord
supervisorctl reread
supervisorctl update
supervisorctl restart cos-agent
sleep 3
supervisorctl status cos-agent

# Tail the log
tail -f /root/COS_Deploy/logs/cos_agent.log
```

---

### Step 4.4 — Post-deploy smoke test

```bash
# From the monitor channel, verify:
# 1. Startup alert arrives: "CoS Agent is online."
# 2. Send "hot leads" from Ben's Telegram
# 3. Send "Draft an email to Ann De Villiers about Sunday open house"
# 4. Wait — next morning digest will confirm scheduler works
```

---

### Step 4.5 — Rollback procedure (if needed)

```bash
# On droplet:
git checkout main

# Edit supervisord conf back to agents/crewai/bot.py
# Then:
supervisorctl restart cos-agent
```

This gets Ben back on the working system in under 2 minutes.

---

## PHASE 5 — Cleanup (Post-Deploy)

Only after Phase 4 passes.

```bash
# Delete the files that have been replaced
git rm agents/crewai/bot.py
git rm agents/crewai/main.py
git rm tools/intent_router.py  # absorbed into core/router.py

# Commit the cleanup
git commit -m "cleanup: remove bot.py, main.py, intent_router.py after successful refactor"

# Merge to main
git checkout main
git merge refactor/layered-architecture
git push origin main

# Tag the new canonical state
git tag post-refactor-june28
git push origin post-refactor-june28
```

---

## APPENDIX A — Files Modified Per Phase

| Phase | New Files | Modified Files | Deleted Files |
|---|---|---|---|
| 1 | app/config.py, app/schemas.py, clients/ben-olsen/scheduler_config.json | none | none |
| 2 | services/__init__.py, services/fub_client.py | tools/fub.py, tools/fub_write.py, tools/fub_activity.py, tools/hot_leads.py, tools/appointments.py | none |
| 3 | core/__init__.py, core/main.py, core/router.py, core/scheduler.py, core/transport.py, handlers/__init__.py, handlers/brief.py, handlers/generative.py, handlers/hot_leads.py, handlers/lead_alert.py, handlers/status.py | none | none |
| 4 | none | /etc/supervisor/conf.d/cos-agent.conf | none |
| 5 | none | none | agents/crewai/bot.py, agents/crewai/main.py, tools/intent_router.py |

---

## APPENDIX B — What Stays Completely Unchanged

These files must not be touched at any point during the sprint:

- tools/voice.py
- tools/logger.py
- tools/health.py
- tools/telegram.py
- tools/calendar_stub.py
- agents/crewai/crew.py
- agents/crewai/config/agents.yaml
- agents/crewai/config/tasks.yaml
- clients/ben-olsen/soul.yaml
- clients/ben-olsen/fub-config.yaml
- clients/ben-olsen/knowledge/
- clients/ben-olsen/communication_prefs.json
- .env
- .gitignore
- requirements.txt (unless a new import requires it)

---

## APPENDIX C — Definition of Done

The sprint is complete when:

- [ ] All Phase 1-5 verification steps pass
- [ ] cos-agent is RUNNING via supervisord on the droplet
- [ ] Startup alert received on Scott's monitor channel
- [ ] "hot leads" returns the list from Ben's Telegram
- [ ] "draft an email to [name] about [topic]" returns a draft in Ben's voice
- [ ] "brief [name]" returns a full contact brief
- [ ] "/status" returns log tail
- [ ] Morning digest fires at 8:30am the following morning
- [ ] No em dashes in any output
- [ ] git log shows clean commit history on main
- [ ] post-refactor-june28 tag exists on main
- [ ] Old bot.py, main.py, intent_router.py are deleted