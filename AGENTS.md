# AGENTS.md — LinkedIn Personal MCP

You work in an existing Python 3.12 + uv repository. Preserve working OAuth, MCP 2.3.0, draft SQLite storage, approvals, and profile tools. Never replace the project with a generated skeleton.

## Nonnegotiable release gates

Never create or claim to create a live LinkedIn post unless the actual authorized Person URN is verified, the account identity matches, LinkedIn capability checks pass, independently authenticated human approval is bound to exact bytes/revision/target/visibility, and a durable one-time claim succeeds. No guessed `urn:li:person:{oidc_sub}`. `/v2/me` currently returns 403. Do not attempt scraping, Selenium/Playwright publishing, internal APIs, or permission bypasses. `LINKEDIN_LIVE_PUBLISH_ENABLED=false` by default.

## Required workflows

For any new feature or refactor first follow `$linkedin-architecture` and produce a small acceptance plan. For any authorization, token, approval or publishing code use `$linkedin-publishing-safety`. Before reporting completion follow `$linkedin-test-gate`; do not say tests passed without their output. At each finished gate update `docs/STATUS.md` and `docs/DECISIONS.md` and stop for review; no automatic multi-phase coding.

## Engineering standards

Use `uv run pytest -v`, `uv run ruff check .`, `uv run mypy src` when configured. Write typed Python, docstrings, structured errors, deterministic unit tests, no hardcoded secrets and no real API writes in tests. Keep dependency injection boundaries around LinkedIn HTTP. Distinguish offline simulation from external integration tests. Log operation IDs, never credentials or OAuth codes. Never overwrite `.env`, the DB, or current source to install this kit.

## Responsibility boundaries

Codex may edit source and test code; neither model nor hooks may approve external writes. Only a separately authenticated human actor may approve. Hook scripts are defense in depth; true enforcement belongs in the MCP service and DB transaction.

## Current state

See `docs/STATUS.md`, `BUILD_WITH_CODEX.md` and `plans/EXECUTION_PLAN.md`. Confirm repo content before relying on an earlier design artifact.
