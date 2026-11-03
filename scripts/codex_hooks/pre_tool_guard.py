"""Best-effort Codex PreToolUse guard. Not an authorization mechanism."""

import json
import re
import sys
from typing import Any

BLOCKED = (
    re.compile(r"\b(?:curl|http|wget)\b[^\n]*(?:api\.linkedin\.com/rest/posts)", re.I),
    re.compile(r"LINKEDIN_LIVE_PUBLISH_ENABLED\s*=\s*(?:true|1)", re.I),
    re.compile(r"\b(?:rm|del|erase)\b[^\n]*(?:\.env|linkedin_drafts\.db)", re.I),
)


def evaluate(payload: dict[str, Any]) -> str | None:
    """Return a reason for obvious dangerous shell calls, otherwise None.

    Hook inspection is inherently incomplete and must not replace runtime policy.
    """
    name = str(payload.get("tool_name", ""))
    args = payload.get("tool_input", payload.get("tool_args", {}))
    command = args.get("command", "") if isinstance(args, dict) else ""
    if name not in ("Bash", "exec_command") or not isinstance(command, str):
        return None
    for pattern in BLOCKED:
        if pattern.search(command):
            return "High-risk command requires out-of-band human review; use approved service workflow."
    return None


def main() -> int:
    """Consume one JSON hook request and produce documented hook response."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeError):
        print(json.dumps({"systemMessage": "Unparseable tool hook input; review manually."}))
        return 0
    reason = evaluate(payload if isinstance(payload, dict) else {})
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}))
    else:
        print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
