"""Read-only local workspace prerequisite checker for Codex handoff."""

from pathlib import Path
import sys


def main() -> int:
    """Identify required working-repo files without modifying them."""
    root = Path.cwd()
    required = ["pyproject.toml", "src/linkedin_mcp/server.py", "src/linkedin_mcp/capabilities.py", "tests"]
    for item in required:
        exists = (root / item).exists()
        print(f"{'PASS' if exists else 'MISSING'} {item}")
    return 0 if all((root / item).exists() for item in required) else 1


if __name__ == "__main__":
    raise SystemExit(main())
