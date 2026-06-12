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


def run_brief(client_id: str, contact_id: str) -> str:
    """Load config, assemble the crew, and return a pre-appointment brief."""
    client_config = load_client_config(client_id)
    soul_context = build_soul_context(client_config)

    agents_config = load_yaml_config(str(CONFIG_DIR / "agents.yaml"))
    tasks_config = load_yaml_config(str(CONFIG_DIR / "tasks.yaml"))

    llm = LLM(model="anthropic/claude-sonnet-4-5")

    supervisor = _make_agent(agents_config["supervisor"], soul_context, llm)
    brief_generator = _make_agent(
        agents_config["brief_generator"],
        soul_context,
        llm,
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
