# COS_Deploy Refactor — Cursor Prompt Blocks
# Run these in order. Each block is self-contained.
# Read CLAUDE.md before running any block.
# Verify each phase passes its tests before starting the next.

---

## PROMPT BLOCK 1 — Configuration and Identity Layer

Paste this entire block into Cursor/Claude Code as a single prompt.

---

You are working on the COS_Deploy repository for the BrightWork CoS agent.
Read CLAUDE.md before doing anything else.

Your task for this session is Phase 1 of the architectural refactor:
creating the centralized configuration layer.

RULES:
- Do not modify any existing files in this phase.
- Do not build anything not listed below.
- No em dashes anywhere. Not in comments, not in docstrings.
- Follow the directory structure in CLAUDE.md exactly.

CREATE these files exactly as specified in REFACTOR_HANDBOOK.md Phase 1:

1. Create `app/__init__.py` — empty file.

2. Create `app/config.py` — centralized env var loader.
   - Uses python-dotenv with override=True
   - Loads .env from repo root
   - Exposes all env vars as typed module-level constants
   - _require() raises EnvironmentError if a required var is missing
   - _optional() returns a default if the var is not set
   - Full constant list is in REFACTOR_HANDBOOK.md Step 1.1

3. Create `app/schemas.py` — Pydantic contracts.
   - Four models: InboundMessage, InboundCallback, RoutedIntent, HandlerResult
   - Full model definitions are in REFACTOR_HANDBOOK.md Step 1.2
   - intent_type on RoutedIntent uses Literal with all current intents

4. Create `clients/ben-olsen/scheduler_config.json` — scheduler runtimes.
   - morning_digest: hour 8, minute 30, timezone_offset_hours -7
   - pre_appointment_check: interval_seconds 900, window 90-120 min
   - hot_leads_silence_days: 14
   - Full JSON structure in REFACTOR_HANDBOOK.md Step 1.3

After creating all four files, run these verification commands and show
me the output:

```bash
python3 -c "from app.config import FUB_API_KEY, TELEGRAM_CHAT_ID; print('config OK')"
python3 -c "from app.schemas import InboundMessage, RoutedIntent, HandlerResult; print('schemas OK')"
python3 -c "import json; c=json.load(open('clients/ben-olsen/scheduler_config.json')); print('scheduler config OK:', c['morning_digest'])"
```

All three must print OK before we proceed.

---

## PROMPT BLOCK 2 — Services Layer (FUB Resilience)

Paste this entire block into Cursor/Claude Code as a single prompt.
Phase 1 must be complete and verified before running this.

---

You are working on the COS_Deploy repository for the BrightWork CoS agent.
Read CLAUDE.md before doing anything else.

Your task is Phase 2 of the architectural refactor:
creating the FUB API client with retry logic and refactoring all FUB tools
to use it.

RULES:
- Do not modify tools/voice.py, tools/logger.py, tools/health.py,
  tools/telegram.py, or tools/calendar_stub.py.
- Do not change any function signatures or return types in tools/.
- No em dashes anywhere.
- Import app.config constants, not os.environ directly.

STEP 1: Create `services/__init__.py` — empty file.

STEP 2: Create `services/fub_client.py`.
Full implementation in REFACTOR_HANDBOOK.md Step 2.1.
Key requirements:
- Singleton requests.Session via _get_session()
- Auth from app.config.FUB_API_KEY
- urllib3 Retry: total=3, backoff_factor=2, status_forcelist=[429,500,502,503,504]
- Timeout: 15 seconds on all requests
- Exposes: fub_get(path, params) -> dict, fub_post(path, json) -> dict, fub_put(path, json) -> dict
- Each verb logs failure via tools.logger.log_event on non-2xx

STEP 3: Refactor `tools/fub.py`.
- Remove module-level requests.Session instantiation
- Remove load_dotenv() call and FUB_API_KEY / FUB_BASE constants
- Import fub_get from services.fub_client
- Replace every session.get(...) call with fub_get(path, params=...)
- Do not change any function signatures

STEP 4: Refactor `tools/fub_write.py`.
Same pattern as Step 3.
- Import fub_post, fub_put from services.fub_client
- Replace direct session calls

STEP 5: Refactor `tools/fub_activity.py`.
Same pattern. Replace the private _fub_get() helper.
The get_contact_context() function signature stays unchanged.

STEP 6: Refactor `tools/hot_leads.py`.
Same pattern. Replace the private _fub_get() helper.
get_active_action_plan_ids() and get_hot_leads_going_cold() stay unchanged.

STEP 7: Refactor `tools/appointments.py`.
Same pattern. Client-side date filtering logic is unchanged.
Only the HTTP call mechanism changes.

After all steps, run these verification commands and show me the output:

```bash
python3 -c "from services.fub_client import fub_get, fub_post; print('fub_client OK')"
python3 -c "from tools.fub import search_contacts, get_contact_by_id; print('fub.py OK')"
python3 -c "from tools.fub_write import add_note_to_contact; print('fub_write.py OK')"
python3 -c "from tools.fub_activity import get_contact_context; print('fub_activity.py OK')"
python3 -c "from tools.hot_leads import get_hot_leads_going_cold; print('hot_leads.py OK')"
python3 -c "from tools.appointments import get_upcoming_appointments; print('appointments.py OK')"
python3 -c "
from services.fub_client import fub_get
data = fub_get('/people/31735')
print('Live FUB OK:', data.get('firstName'), data.get('lastName'))
"
```

All seven must pass before Phase 3 begins.

---

## PROMPT BLOCK 3A — Core Router and Handlers

Paste this entire block into Cursor/Claude Code as a single prompt.
Phases 1 and 2 must be complete and verified before running this.

---

You are working on the COS_Deploy repository for the BrightWork CoS agent.
Read CLAUDE.md before doing anything else.

Your task is the first half of Phase 3: creating core/router.py
and all handlers/ files.

RULES:
- Handlers import from tools/ and app/ only. No direct API calls.
- Every handler returns a HandlerResult.
- Every handler defines a FALLBACK_MESSAGE constant.
- Every handler logs start + success/failure via tools.logger.log_event.
- Every handler sends operator alert on failure via tools.telegram.send_operator_alert.
- Ben never sees technical error details.
- No em dashes anywhere.

STEP 1: Create `core/__init__.py` — empty file.

STEP 2: Create `core/router.py`.
Full implementation in REFACTOR_HANDBOOK.md Step 3.1.
Key requirements:
- ConversationBuffer class with MAX_TURNS=10, persists to logs/conversation_buffer.json
- classify_intent(message: InboundMessage, buffer: ConversationBuffer) -> RoutedIntent
- Imports OPENROUTER_API_KEY, OPENROUTER_URL, HAIKU_MODEL from app.config
- Returns RoutedIntent, never a raw dict
- Handles Haiku markdown fence quirk:
  raw.strip("` \n").removeprefix("json").strip()
- Falls back to intent_type="unknown" on any exception
- Uses json.loads(resp.text.strip()) not resp.json()

STEP 3: Create `handlers/__init__.py` — empty file.

STEP 4: Create `handlers/status.py`.
Extract _get_status_log from agents/crewai/bot.py.
Expose: handle_status(lines: int = 50) -> HandlerResult
Log path: logs/cos_agent.log
Truncate at 3800 chars.

STEP 5: Create `handlers/brief.py`.
Extract from agents/crewai/bot.py:
- _run_brief_for_contact -> run_brief_for_contact(client_id, contact_id) -> str
- _handle_disambiguation_result -> (keep same logic)
- _send_contact_disambiguation_prompt -> (keep same logic, use send_inline_message)
- _duplicate_merge_note -> (keep same logic)
Expose: handle(intent: RoutedIntent) -> HandlerResult
Logic: if entity is numeric, ID lookup. If string, name search + disambiguation.

STEP 6: Create `handlers/generative.py`.
Extract _handle_generative_request from agents/crewai/bot.py.
Imports: draft_communication from tools.draft_communication,
         get_contact_context from tools.fub_activity,
         search_contacts, get_contact_by_id from tools.fub
Expose: handle(intent: RoutedIntent) -> HandlerResult
On multiple contact matches: send clarification message to Ben's chat
and draft without context (same behavior as before).

STEP 7: Create `handlers/hot_leads.py`.
Extract _handle_hot_leads_list from agents/crewai/bot.py.
Expose: handle(intent: RoutedIntent) -> HandlerResult
When entity is set (Ben named a lead), call generative.handle(intent)
and return its HandlerResult.

STEP 8: Create `handlers/lead_alert.py`.
Extract _handle_callback from agents/crewai/bot.py.
Also extract _load_lead_alert_state, _save_lead_alert_state,
_get_lead_draft, _get_lead_contact, _mark_lead_responded.
These helper functions stay in this file.
Expose: handle_callback(callback: InboundCallback) -> HandlerResult
State file: logs/lead_alert_state.json (unchanged path).

After all steps, run:

```bash
python3 -c "from core.router import ConversationBuffer, classify_intent; print('router OK')"
python3 -c "from handlers import brief, generative, hot_leads, lead_alert, status; print('all handlers OK')"
python3 -c "
from app.schemas import InboundMessage, RoutedIntent
from handlers import brief
import time
msg = InboundMessage(chat_id='test', raw_text='brief 31735', timestamp=int(time.time()), client_id='ben-olsen')
intent = RoutedIntent(original_message=msg, intent_type='brief_request', entity='31735', confidence=0.95)
result = brief.handle(intent)
print('Brief handler OK, success:', result.success, '| output length:', len(result.telegram_output))
"
```

---

## PROMPT BLOCK 3B — Transport, Scheduler, and Entry Point

Paste this entire block into Cursor/Claude Code as a single prompt.
Prompt Block 3A must be complete and verified before running this.

---

You are working on the COS_Deploy repository for the BrightWork CoS agent.
Read CLAUDE.md before doing anything else.

Your task is the second half of Phase 3: creating core/scheduler.py,
core/transport.py, and core/main.py.

RULES:
- Scheduled jobs call tools/ directly. They do not go through RoutedIntent.
- transport.py contains no business logic. It normalizes Telegram events
  and passes them to callbacks.
- core/main.py orchestrates. It contains no business logic.
- No em dashes anywhere.
- No hardcoded schedule times. Read from clients/ben-olsen/scheduler_config.json.

STEP 1: Create `core/scheduler.py`.
Full implementation in REFACTOR_HANDBOOK.md Step 3.3.
Key requirements:
- Reads runtimes from clients/ben-olsen/scheduler_config.json via _load_config()
- Persists state (briefed_appointment_ids, last_morning_digest_hour) to
  logs/scheduler_state.json via _load_state() / _save_state()
- pre_appointment_check receives the state dict as argument and mutates it
- Morning digest dedup: fires only if last_morning_digest_hour != current hour
- Pre-appointment brief dedup: checks briefed_appointment_ids in state

STEP 2: Create `core/transport.py`.
Full implementation in REFACTOR_HANDBOOK.md Step 3.4.
Key requirements:
- poll(on_message, on_callback) blocks indefinitely
- Normalizes Telegram message events to InboundMessage
- Normalizes Telegram callback events to InboundCallback
- Calls _answer_callback_query() immediately on every callback
- Mirrors all inbound messages to monitor channel via send_monitor_copy
- Mirrors all outbound replies to monitor channel (first 500 chars)
- Contains no routing logic or business logic

STEP 3: Create `core/main.py`.
Full implementation in REFACTOR_HANDBOOK.md Step 3.5.
Key requirements:
- _route_message(message: InboundMessage) -> str | None
  Dispatches to handlers based on RoutedIntent.intent_type
  Status command bypasses classifier (regex match)
- _route_callback(callback: InboundCallback) -> str | None
  Delegates to lead_alert.handle_callback
- _build_scheduled_jobs(scheduler) defines and registers morning_digest
  and pre_appointment_check as closures
- main() runs startup health check, starts scheduler, starts poll loop
- Entry point: if __name__ == "__main__": main()
  Also expose as python -m core.main

After all steps, run:

```bash
python3 -c "from core.scheduler import SimpleScheduler; print('scheduler OK')"
python3 -c "from core.transport import poll; print('transport OK')"
python3 -c "from core.main import main; print('main OK')"

python3 -c "
from app.schemas import InboundMessage
from core.router import ConversationBuffer, classify_intent
import time
msg = InboundMessage(
    chat_id='test',
    raw_text='Draft an email to Ann De Villiers about the open house Sunday 1 to 4',
    timestamp=int(time.time()),
    client_id='ben-olsen'
)
buf = ConversationBuffer()
result = classify_intent(msg, buf)
print('End-to-end classify OK:', result.intent_type, '| entity:', result.entity)
"
```

---

## PROMPT BLOCK 4 — Integration Test and Hot Swap

This block is run ON THE DROPLET, not the Mac Mini.
Push the branch to GitHub first, then SSH into the droplet.

---

You are performing the final deployment phase of the COS_Deploy refactor.
This runs directly on the DigitalOcean Droplet (CoS-BenOlsen, SFO3).

CRITICAL: Ben's live agent will be briefly offline during this swap.
Estimated downtime: under 2 minutes.
Rollback is available: git checkout main + supervisorctl restart cos-agent.

STEP 1: Pull the refactor branch on the droplet.
```bash
cd /root/COS_Deploy
git fetch
git checkout refactor/layered-architecture
pip install -r requirements.txt
source /root/COS_Deploy/.env
```

STEP 2: Run pre-deploy verification.
```bash
python3 -c "from app.config import FUB_API_KEY; print('config OK')"
python3 -c "from core.main import main; print('main import OK')"
python3 -c "
from services.fub_client import fub_get
data = fub_get('/people/31735')
print('FUB live read OK:', data.get('firstName'))
"
```

All three must pass before continuing.

STEP 3: Stop old agent and start new agent manually.
```bash
supervisorctl stop cos-agent
cd /root/COS_Deploy
python3 -m core.main
```

STEP 4: From Ben's Telegram (or the monitor channel), send:
1. "hot leads"
2. "brief 31735"
3. "Draft an email to Ann De Villiers about the open house Sunday 1 to 4"
4. "/status"
5. "Look up Ann De Villiers"

All five must return valid responses before proceeding.
Ctrl+C to stop the manual run after tests pass.

STEP 5: Update supervisord config.
```bash
cat /etc/supervisor/conf.d/cos-agent.conf
```
Change the command line from:
  command=python agents/crewai/bot.py
To:
  command=python -m core.main

Keep directory=/root/COS_Deploy and all environment= lines unchanged.

STEP 6: Reload supervisord and start agent.
```bash
supervisorctl reread
supervisorctl update
supervisorctl restart cos-agent
sleep 5
supervisorctl status cos-agent
tail -20 /root/COS_Deploy/logs/cos_agent.log
```

cos-agent must show RUNNING status.
Log must show startup success entry.
Operator alert "CoS Agent is online." must arrive on Scott's monitor channel.

STEP 7: Repeat the five smoke tests from Step 4 via Telegram.
All five must pass.

If any step fails at any point, run:
```bash
git checkout main
# Edit supervisord conf back to: command=python agents/crewai/bot.py
supervisorctl restart cos-agent
```

---

## PROMPT BLOCK 5 — Cleanup and Merge

Run this after Phase 4 is confirmed working on the droplet.
Run on the Mac Mini, not the droplet.

---

You are performing cleanup after a successful refactor deployment.
Phase 4 is confirmed working. The droplet is running the new architecture.

STEP 1: On the Mac Mini, verify branch is up to date.
```bash
git fetch
git checkout refactor/layered-architecture
git status  # should be clean
```

STEP 2: Delete the replaced files.
```bash
git rm agents/crewai/bot.py
git rm agents/crewai/main.py
git rm tools/intent_router.py
```

STEP 3: Commit and push cleanup.
```bash
git commit -m "cleanup: remove bot.py, main.py, intent_router.py — replaced by core/ and handlers/"
git push origin refactor/layered-architecture
```

STEP 4: Merge to main.
```bash
git checkout main
git merge refactor/layered-architecture --no-ff -m "refactor: layered architecture complete (June 28, 2026)"
git push origin main
```

STEP 5: Tag the new canonical state.
```bash
git tag post-refactor-june28
git push origin post-refactor-june28
```

STEP 6: On the droplet, pull the clean main.
```bash
# SSH into droplet
git checkout main
git pull origin main
supervisorctl status cos-agent  # should still be RUNNING — no restart needed
```

STEP 7: Verify final state.
```bash
ls core/          # main.py, router.py, scheduler.py, transport.py
ls handlers/      # brief.py, generative.py, hot_leads.py, lead_alert.py, status.py
ls services/      # fub_client.py
ls app/           # config.py, schemas.py
# These should NOT exist:
ls agents/crewai/bot.py         # should fail
ls agents/crewai/main.py        # should fail
ls tools/intent_router.py       # should fail
```

The refactor is complete when all verification steps pass and the
definition of done checklist in REFACTOR_HANDBOOK.md Appendix C
is fully checked off.