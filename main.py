"""Main CLI entry point for Plumtree Agents."""

import sys


USAGE = """\
Plumtree Agents
===============

Usage:
  plumtree research [--now]     Run the weekly research brief agent
                                --now  Run immediately instead of waiting for Friday

  plumtree proposal             Start an interactive proposal/SOW session

  plumtree --help               Show this help message

Environment:
  Copy .env.example to .env and fill in your credentials.
  See README.md for full setup instructions.
"""


def main():
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(USAGE)
        sys.exit(0)

    command = args[0]

    if command == "research":
        from agents.research.agent import main as research_main
        # Pass remaining args through
        sys.argv = ["plumtree-research"] + args[1:]
        research_main()

    elif command == "proposal":
        from agents.proposal_sow.agent import main as proposal_main
        sys.argv = ["plumtree-proposal"] + args[1:]
        proposal_main()

    else:
        print(f"Unknown command: {command}")
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
