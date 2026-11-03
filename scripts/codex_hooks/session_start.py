"""Give the current gate status to the Codex session without secrets."""

import json
from pathlib import Path


def main() -> int:
    """Emit a short context reminder from the repository status file."""
    status = Path("docs/STATUS.md")
    snippet = status.read_text(encoding="utf-8")[:1500] if status.exists() else "No status file found."
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": (
            "Read AGENTS.md; live publishing remains disabled. Current status:\n" + snippet
        )
    }}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
