"""Offline tests for repository Codex hook heuristics."""

import importlib.util
from pathlib import Path


def load_guard():
    """Load the hook module independently of the app installation."""
    p = Path(__file__).resolve().parents[1] / "scripts/codex_hooks/pre_tool_guard.py"
    spec = importlib.util.spec_from_file_location("guard", p)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_blocks_direct_live_posts_call():
    """Deny obvious live endpoint shell invocation."""
    guard = load_guard()
    assert guard.evaluate({"tool_name": "Bash", "tool_input": {"command": "curl -X POST https://api.linkedin.com/rest/posts"}})


def test_blocks_enabling_live_publish():
    """Deny shell changes that explicitly enable live publishing."""
    guard = load_guard()
    assert guard.evaluate({"tool_name": "Bash", "tool_input": {"command": "echo LINKEDIN_LIVE_PUBLISH_ENABLED=true"}})


def test_allows_test_commands():
    """Allow routine offline verification."""
    guard = load_guard()
    assert guard.evaluate({"tool_name": "Bash", "tool_input": {"command": "uv run pytest -v"}}) is None
