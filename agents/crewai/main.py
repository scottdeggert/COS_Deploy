"""Entry point for the BrightWork Chief of Staff CrewAI agent."""

import argparse

from dotenv import load_dotenv

from crew import BrightWorkCrew


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the BrightWork CoS agent")
    parser.add_argument(
        "--client",
        default="ben-olsen",
        help="Client ID (maps to clients/{client_id}/)",
    )
    args = parser.parse_args()

    load_dotenv()

    crew = BrightWorkCrew(client_id=args.client)

    inputs = {
        "contact_name": "",
        "contact_id": "",
        "trigger": "",
    }

    crew.kickoff(inputs)


if __name__ == "__main__":
    main()
