---
name: linkedin-test-gate
description: Use when reviewing or completing any LinkedIn MCP code change, API adapter, approval workflow, migration or release gate.
---
# Verification workflow

Run existing tests first, then changed tests. For authorized modifications, run `uv run pytest -v`, `uv run ruff check .` and `uv run mypy src` only if declared/configured; report unavailable commands separately. Include mocked LinkedIn errors 401/403/429/5xx, timeout after send, malformed response, approval expiry, changed draft, wrong account, concurrent claim, duplicate execution and crash-after-claim. Never call the real LinkedIn Posts endpoint as a test. Report exact output and update `docs/STATUS.md` when a gate is proven.
