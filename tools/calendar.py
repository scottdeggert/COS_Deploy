"""
Google Calendar client for appointment awareness.

Framework-agnostic integration — no CrewAI or other agent framework imports.
Can be used directly or wrapped by any orchestration layer.
"""

import os


class CalendarClient:
    """Client for reading upcoming calendar appointments."""

    def __init__(self, credentials_path: str | None = None):
        self.credentials_path = credentials_path or os.environ.get(
            "GOOGLE_CALENDAR_CREDENTIALS_PATH", ""
        )

    def get_upcoming_appointments(self, days_ahead: int = 3) -> list[dict]:
        """Return appointments scheduled within the next N days."""
        raise NotImplementedError
