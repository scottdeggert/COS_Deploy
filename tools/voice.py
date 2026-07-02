"""Ben Olsen voice context — loaded into every generative request."""

BEN_VOICE_CONTEXT = """You are writing as Ben Olsen, founder of BrightWork Realty Advocates, a seasoned real estate agent in Lamorinda, CA (Lafayette, Orinda, Moraga). Ben has been in the business since 2004. The BrightWork team has operated in Lamorinda since 1977.

Ben's voice: plain-spoken, warm, direct. Uses contractions. Semi-formal but sounds like a real person. Consultative and calm — not salesy. Acknowledges the human side of real estate decisions, moves quickly to practical next steps.

Core style rules:
- NEVER use em dashes (—) or en dashes (–). Rewrite the sentence instead. This is a hard rule with no exceptions.
- No hype words or clichés
- No closing phrase or signature — the email client or FUB appends it
- Sign off as "Ben" not "Ben Olsen"
- Do not mention AI or automation
- Write as if Ben is personally composing this, not a system
- Use specific, concrete language — avoid vague pleasantries
- Contractions are fine and preferred
- Medium-length sentences, occasionally one short punchy line for emphasis

For emails: body only. No subject line unless explicitly requested.
For SMS: under 160 characters, very casual, first name only.
For notes: professional tone, suitable for a FUB contact record."""


def _load_voice_guide() -> str:
    from pathlib import Path

    from tools.logger import log_event

    guide_path = (
        Path(__file__).resolve().parent.parent
        / "clients/ben-olsen/knowledge/voice-guide.md"
    )
    try:
        return guide_path.read_text(encoding="utf-8")
    except OSError:
        log_event(
            "cos_agent",
            "load_voice_guide",
            "fallback",
            detail="voice-guide.md missing or unreadable",
            file=__file__,
            function="_load_voice_guide",
        )
        return BEN_VOICE_CONTEXT


def load_communication_prefs() -> str:
    """Load saved communication preferences and return as a formatted string.
    Returns empty string if no prefs exist yet."""
    import json
    from pathlib import Path

    prefs_path = Path("/root/COS_Deploy/clients/ben-olsen/communication_prefs.json")
    if not prefs_path.exists():
        return ""

    try:
        with prefs_path.open(encoding="utf-8") as f:
            prefs = json.load(f)
        if not prefs:
            return ""
        lines = ["Ben's standing communication preferences:"]
        for context, notes in prefs.items():
            lines.append(f"- {context}: {notes}")
        return "\n".join(lines)
    except Exception:
        return ""


def build_system_prompt(contact_context: dict | None = None) -> str:
    """Assemble the full system prompt: voice + prefs + optional contact context."""
    parts = [_load_voice_guide()]

    prefs = load_communication_prefs()
    if prefs:
        parts.append(prefs)

    if contact_context:
        lines = ["Contact context from CRM:"]
        if contact_context.get("name"):
            lines.append(f"- Name: {contact_context['name']}")
        if contact_context.get("stage"):
            lines.append(f"- Pipeline stage: {contact_context['stage']}")
        if contact_context.get("last_activity"):
            lines.append(f"- Last activity: {contact_context['last_activity']}")
        if contact_context.get("tags"):
            lines.append(f"- Tags: {contact_context['tags']}")
        if contact_context.get("source"):
            lines.append(f"- Lead source: {contact_context['source']}")
        if contact_context.get("notes"):
            lines.append(f"- Recent notes:\n{contact_context['notes']}")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)
