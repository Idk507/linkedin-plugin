"""Plugin session reminder; no secrets or external calls."""

import json


def main() -> int:
    """Write a minimal Codex hook response."""
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "For LinkedIn MCP changes, read AGENTS.md and STATUS; never automate LinkedIn writes or invent Person URNs."}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
