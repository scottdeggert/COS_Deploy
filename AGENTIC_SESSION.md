# COS_Deploy Refactor — Agentic Session Master Prompt
# Paste this into Claude Code to run Phases 1-3 autonomously.
# Human takes over at Phase 4 (droplet deployment).

---

You are an autonomous coding agent executing a structured architectural
refactor of the COS_Deploy repository. This is a multi-phase task.
You will execute each phase completely, verify it, fix any errors,
and proceed to the next phase without waiting for input.

BEFORE ANYTHING ELSE:
1. Read CLAUDE.md in the repo root. That file governs all guardrails.
2. Read REFACTOR_HANDBOOK.md. That file contains the full implementation spec.
3. Confirm you have read both by stating the three most important rules
   from CLAUDE.md before writing any code.

YOUR WORKING ENVIRONMENT:
- Repo root: /Users/scotteggert/Development/Cursor/COS_Deploy
- Python: 3.11.x (verify with python3 --version before starting)
- Branch: you will create refactor/layered-architecture

SUCCESS CRITERIA:
You are done with your part of the session when ALL of the following are true:
- [ ] git tag pre-refactor-june28 exists
- [ ] Branch refactor/layered-architecture exists and is checked out
- [ ] Phase 1 verification: all three import checks print OK
- [ ] Phase 2 verification: all seven import checks print OK, live FUB read returns data
- [ ] Phase 3A verification: router imports, all handlers import, brief handler test passes
- [ ] Phase 3B verification: scheduler/transport/main import, end-to-end classify test passes
- [ ] All new files exist in the correct directories per CLAUDE.md target structure
- [ ] No em dashes exist in any file you created (run the em dash check below)
- [ ] git status shows a clean committed state on the branch
- [ ] A file called PHASE_COMPLETE.md exists in repo root with your session summary

You do NOT deploy to the droplet. You do NOT touch supervisord.
You do NOT merge to main. Stop when the above checklist is complete.

---

## EXECUTION PLAN

Execute these phases in strict order.
After each phase, run ALL verification commands before proceeding.
If a verification fails, fix the error and re-run before moving on.
Do not skip verifications. Do not proceed on a failing test.

---

### PRE-SPRINT SETUP

```bash
cd /Users/scotteggert/Development/Cursor/COS_Deploy

# Confirm environment
python3 --version
git status
git log --oneline -3

# Tag current state as rollback point
git tag pre-refactor-june28 2>/dev/null || echo "tag already exists"

# Create feature branch
git checkout -b refactor/layered-architecture 2>/dev/null || git checkout refactor/layered-architecture

# Confirm branch
git branch --show-current
```

---

### PHASE 1 — Configuration and Identity Layer

Follow REFACTOR_HANDBOOK.md Phase 1 exactly.

Files to create:
- app/__init__.py (empty)
- app/config.py (centralized env loader)
- app/schemas.py (Pydantic contracts)
- clients/ben-olsen/scheduler_config.json (scheduler runtimes)

After creating all four files, run Phase 1 verification:

```bash
cd /Users/scotteggert/Development/Cursor/COS_Deploy
python3 -c "from app.config import FUB_API_KEY, TELEGRAM_CHAT_ID; print('P1 config OK')"
python3 -c "from app.schemas import InboundMessage, RoutedIntent, HandlerResult, InboundCallback; print('P1 schemas OK')"
python3 -c "import json; c=json.load(open('clients/ben-olsen/scheduler_config.json')); print('P1 scheduler config OK:', c['morning_digest']['hour'])"
```

All three must print OK. If any fail, fix and re-run before Phase 2.

Commit Phase 1:
```bash
git add app/ clients/ben-olsen/scheduler_config.json
git commit -m "refactor(phase1): centralized config, schemas, scheduler config"
```

---

### PHASE 2 — Services Layer

Follow REFACTOR_HANDBOOK.md Phase 2 exactly.

Files to create:
- services/__init__.py (empty)
- services/fub_client.py (retry client)

Files to modify (imports only — no logic changes):
- tools/fub.py
- tools/fub_write.py
- tools/fub_activity.py
- tools/hot_leads.py
- tools/appointments.py

CRITICAL: Do not modify tools/voice.py, tools/logger.py, tools/health.py,
tools/telegram.py, or tools/calendar_stub.py.

After all changes, run Phase 2 verification:

```bash
cd /Users/scotteggert/Development/Cursor/COS_Deploy
python3 -c "from services.fub_client import fub_get, fub_post, fub_put; print('P2 fub_client OK')"
python3 -c "from tools.fub import search_contacts, get_contact_by_id; print('P2 fub.py OK')"
python3 -c "from tools.fub_write import add_note_to_contact; print('P2 fub_write.py OK')"
python3 -c "from tools.fub_activity import get_contact_context; print('P2 fub_activity.py OK')"
python3 -c "from tools.hot_leads import get_hot_leads_going_cold; print('P2 hot_leads.py OK')"
python3 -c "from tools.appointments import get_upcoming_appointments; print('P2 appointments.py OK')"
python3 -c "
from services.fub_client import fub_get
data = fub_get('/people/31735')
print('P2 Live FUB OK:', data.get('firstName'), data.get('lastName'))
"
```

All seven must pass. The live FUB test must return a name.

Commit Phase 2:
```bash
git add services/ tools/fub.py tools/fub_write.py tools/fub_activity.py tools/hot_leads.py tools/appointments.py
git commit -m "refactor(phase2): fub_client with retry, refactor tool imports"
```

---

### PHASE 3A — Core Router and Handlers

Follow REFACTOR_HANDBOOK.md Phase 3, Steps 3.1 and 3.2.

Files to create:
- core/__init__.py (empty)
- core/router.py (Haiku classifier + ConversationBuffer)
- handlers/__init__.py (empty)
- handlers/status.py
- handlers/brief.py
- handlers/generative.py
- handlers/hot_leads.py
- handlers/lead_alert.py

Source material: extract from agents/crewai/bot.py as directed in handbook.
Do NOT delete bot.py yet. It stays until Phase 5.

HAIKU QUIRKS — these workarounds must be in core/router.py:
1. Strip markdown fences: raw.strip("` \n").removeprefix("json").strip()
2. Use json.loads(resp.text.strip()) not resp.json()
3. Load dotenv not needed — app.config handles it

HANDLER PATTERN — every handler must:
1. Define FALLBACK_MESSAGE at module level
2. Accept RoutedIntent (or InboundCallback for lead_alert)
3. Return HandlerResult
4. Log start + success/failure
5. Send operator alert on failure
6. Never put technical error in telegram_output

After creating all files, run Phase 3A verification:

```bash
cd /Users/scotteggert/Development/Cursor/COS_Deploy
python3 -c "from core.router import ConversationBuffer, classify_intent; print('P3A router OK')"
python3 -c "from handlers.status import handle_status; print('P3A status OK')"
python3 -c "from handlers.brief import handle; print('P3A brief OK')"
python3 -c "from handlers.generative import handle; print('P3A generative OK')"
python3 -c "from handlers.hot_leads import handle; print('P3A hot_leads OK')"
python3 -c "from handlers.lead_alert import handle_callback; print('P3A lead_alert OK')"

python3 -c "
from app.schemas import InboundMessage, RoutedIntent
from handlers.brief import handle
import time
msg = InboundMessage(chat_id='test', raw_text='brief 31735', timestamp=int(time.time()), client_id='ben-olsen')
intent = RoutedIntent(original_message=msg, intent_type='brief_request', entity='31735', confidence=0.95)
result = handle(intent)
print('P3A brief handler test OK, success:', result.success, 'output_length:', len(result.telegram_output))
assert result.success, 'Brief handler returned failure'
assert len(result.telegram_output) > 100, 'Brief output suspiciously short'
print('P3A assertions passed')
"

python3 -c "
from app.schemas import InboundMessage, RoutedIntent
from handlers.generative import handle
import time
msg = InboundMessage(chat_id='test', raw_text='Draft an email to Ann De Villiers about open house Sunday', timestamp=int(time.time()), client_id='ben-olsen')
intent = RoutedIntent(original_message=msg, intent_type='draft_communication', entity='Ann De Villiers', comm_type='email', confidence=0.9)
result = handle(intent)
print('P3A generative test OK, success:', result.success, 'output_length:', len(result.telegram_output))
assert result.success, 'Generative handler returned failure'
assert 'Ann' in result.telegram_output or len(result.telegram_output) > 100, 'Draft output suspiciously short'
# Check for em dashes
assert '\u2014' not in result.telegram_output, 'EM DASH FOUND IN OUTPUT'
assert '\u2013' not in result.telegram_output, 'EN DASH FOUND IN OUTPUT'
print('P3A no em/en dashes confirmed')
"
```

All must pass before Phase 3B.

Commit Phase 3A:
```bash
git add core/ handlers/
git commit -m "refactor(phase3a): core router, all handlers"
```

---

### PHASE 3B — Transport, Scheduler, and Entry Point

Follow REFACTOR_HANDBOOK.md Phase 3, Steps 3.3-3.5.

Files to create:
- core/scheduler.py (SimpleScheduler with JSON state persistence)
- core/transport.py (Telegram polling — no business logic)
- core/main.py (entry point, wires everything)

SCHEDULER REQUIREMENTS:
- Reads runtimes from clients/ben-olsen/scheduler_config.json
- Persists state to logs/scheduler_state.json
- pre_appointment_check receives AND mutates the state dict
- Morning digest dedup key: last_morning_digest_hour
- Pre-appointment dedup key: briefed_appointment_ids list in state

TRANSPORT REQUIREMENTS:
- poll(on_message, on_callback) only — no routing logic inside
- Normalizes to InboundMessage and InboundCallback
- Mirrors inbound to monitor channel
- Mirrors outbound to monitor channel (first 500 chars)

MAIN REQUIREMENTS:
- _route_message dispatches on RoutedIntent.intent_type
- Status regex bypasses classifier
- _build_scheduled_jobs defines morning_digest and pre_appointment_check
  as closures that read config from scheduler_config.json
- No hardcoded hour=8 or minute=30 — read from config
- Runnable as: python -m core.main

After creating all files, run Phase 3B verification:

```bash
cd /Users/scotteggert/Development/Cursor/COS_Deploy
python3 -c "from core.scheduler import SimpleScheduler; print('P3B scheduler OK')"
python3 -c "from core.transport import poll; print('P3B transport OK')"
python3 -c "from core.main import main, _route_message; print('P3B main OK')"

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
print('P3B classify OK:', result.intent_type, '| entity:', result.entity)
assert result.intent_type == 'draft_communication', f'Expected draft_communication, got {result.intent_type}'
assert result.entity is not None, 'Entity should not be None for named contact'
print('P3B classify assertions passed')
"

python3 -c "
from app.schemas import InboundMessage
from core.main import _route_message
import time

# Test status bypass
msg = InboundMessage(chat_id='test', raw_text='/status', timestamp=int(time.time()), client_id='ben-olsen')
reply = _route_message(msg)
assert reply is not None, 'Status command returned None'
assert len(reply) > 10, 'Status reply suspiciously short'
print('P3B status bypass OK')

# Test greeting
msg2 = InboundMessage(chat_id='test', raw_text='hello', timestamp=int(time.time()), client_id='ben-olsen')
reply2 = _route_message(msg2)
assert reply2 is not None, 'Greeting returned None'
print('P3B greeting OK:', reply2[:60])
"
```

All must pass.

Run the em dash check across all new files:
```bash
cd /Users/scotteggert/Development/Cursor/COS_Deploy
python3 -c "
import os
violations = []
check_dirs = ['app', 'core', 'handlers', 'services']
for d in check_dirs:
    for root, dirs, files in os.walk(d):
        for f in files:
            if f.endswith('.py') or f.endswith('.md') or f.endswith('.json'):
                path = os.path.join(root, f)
                with open(path, encoding='utf-8') as fh:
                    content = fh.read()
                    if '\u2014' in content or '\u2013' in content:
                        violations.append(path)
if violations:
    print('EM DASH VIOLATIONS:', violations)
    raise SystemExit('Fix em dashes before committing')
else:
    print('Em dash check passed — no violations')
"
```

Commit Phase 3B:
```bash
git add core/scheduler.py core/transport.py core/main.py
git commit -m "refactor(phase3b): scheduler, transport, main entry point"
```

---

### FINAL CHECKS

```bash
cd /Users/scotteggert/Development/Cursor/COS_Deploy

# Verify directory structure matches CLAUDE.md
echo "=== app/ ===" && ls app/
echo "=== core/ ===" && ls core/
echo "=== handlers/ ===" && ls handlers/
echo "=== services/ ===" && ls services/
echo "=== clients/ben-olsen/ ===" && ls clients/ben-olsen/

# Verify git state
git log --oneline -6
git status  # should be clean

# Verify old files still present (not deleted yet — that's Phase 5)
ls agents/crewai/bot.py && echo "bot.py still present (correct)"
ls tools/intent_router.py && echo "intent_router.py still present (correct)"

# Push branch to GitHub
git push origin refactor/layered-architecture
```

---

### CREATE SESSION SUMMARY

Create PHASE_COMPLETE.md in the repo root:

```markdown
# Refactor Sprint — Phase 1-3 Complete
Date: [today's date]
Branch: refactor/layered-architecture

## What was built

### Phase 1 — Config and Identity
- app/config.py: centralized env var loader
- app/schemas.py: Pydantic contracts (InboundMessage, InboundCallback, RoutedIntent, HandlerResult)
- clients/ben-olsen/scheduler_config.json: scheduler runtimes extracted from bot.py

### Phase 2 — Services Layer
- services/fub_client.py: requests.Session with urllib3 retry (total=3, backoff_factor=2)
- tools/fub.py, fub_write.py, fub_activity.py, hot_leads.py, appointments.py:
  refactored to import from services.fub_client

### Phase 3A — Router and Handlers
- core/router.py: Haiku classifier + ConversationBuffer (extracted from tools/intent_router.py)
- handlers/brief.py: brief_request handler
- handlers/generative.py: draft_communication + draft_outreach handler
- handlers/hot_leads.py: hot_leads handler
- handlers/lead_alert.py: FUB webhook callback handler
- handlers/status.py: /status command handler

### Phase 3B — Transport, Scheduler, Entry Point
- core/scheduler.py: SimpleScheduler with JSON state persistence
- core/transport.py: Telegram long-poll (transport only, no logic)
- core/main.py: entry point, wires all layers

## What was NOT done (human required)
- Phase 4: droplet deployment and supervisord config update
- Phase 5: cleanup (delete bot.py, main.py, intent_router.py) and merge to main

## Verification status
[Claude Code fills in pass/fail for each phase]

## Ready for deployment
Scott: run CURSOR_PROMPTS.md Prompt Block 4 from the droplet to complete deployment.
```

---

## WHAT TO DO IF A PHASE FAILS

If any verification step fails:
1. Read the error carefully.
2. Identify which file caused it.
3. Fix only that file. Do not refactor adjacent files.
4. Re-run the verification for that phase only.
5. Do not proceed until all verifications for that phase pass.

If you encounter an import error you cannot resolve:
- Check that you are not importing from a module that imports from you (circular import)
- Check that app/config.py is imported before tools/ in any entry point
- The most common cause is a tool file that still has its own load_dotenv() call;
  remove it and ensure app.config is imported first in the calling module

If the live FUB test fails:
- Verify source /root/COS_Deploy/.env has been run (or .env is in repo root)
- Check FUB_API_KEY is set: python3 -c "from app.config import FUB_API_KEY; print(len(FUB_API_KEY))"
- The key must be non-empty

Do not move on with a broken phase.