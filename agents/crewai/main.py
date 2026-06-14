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
