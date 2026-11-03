# Gate A — verified repository audit

Date: 2026-11-03. Scope: existing-source inventory and baseline verification only.

## Acceptance plan and result

Inspect instructions, source, tests, configuration, installed SDK, hooks and existing SQLite schema; run the existing offline suite; document actual boundaries and implementation gaps; change documentation only and stop. These acceptance steps are complete. No later gate is authorized by this audit.

## Evidence and limits

- Read `AGENTS.md`, `docs/STATUS.md`, `plans/EXECUTION_PLAN.md`, `BUILD_WITH_CODEX.md`, architecture and test-gate skills, all current application modules and all five test files.
- `uv run pytest -v`: exit 0, **22 passed in 2.55s**, Python 3.12.12, pytest 9.2.0. Counts: approvals 5, capabilities 5, hook policy 3, drafts 6, LinkedIn client 3. No failed or skipped tests.
- An import/introspection script run through `uv run python` successfully imported `linkedin_mcp.server.mcp`, printed `MCPServer`, and awaited `mcp.list_tools()`: 14 registered tools. This verifies in-process registration, not an MCP Inspector/client handshake.
- Installed versions: MCP 2.3.0, httpx 0.28.1, pydantic 2.14.1, FastAPI 0.162.0, uvicorn 0.54.0. Inspected installed `mcp/server/mcpserver/server.py`; the application uses the installed `MCPServer`, not an assumed replacement API.
- `uv run python scripts/check_workspace.py`: exit 0, four prerequisite paths PASS.
- `uv run python scripts/validate_bundle.py`: exit 0, `PASS: TOML, JSON, skill front matter presence, basic structure`. This is syntax/structure validation, not proof of hook activation or plugin installation.
- Ruff and mypy are neither declared nor configured in `pyproject.toml`; their checks were not run. No coverage measurement was performed.
- Tests mock profile HTTP and credentials and use temporary SQLite databases. They exercise offline behavior, not external integration. No LinkedIn endpoint, OAuth callback or credential-store read/write was invoked by the audit. Environment values and database row contents were not printed.
- Prior successful OAuth/profile calls, human CLI approval, Inspector connection and `/v2/me` HTTP 403 remain user-reported historical evidence; they were not repeated here. No live publication is verified.

## Real structure and interfaces

All application modules are directly under `src/linkedin_mcp/`; `__init__.py` is empty.

| Module | Existing responsibility and boundary |
| --- | --- |
| `server.py` | MCP tool wrappers; local stdio entry point; imports service functions directly; standard logging. |
| `auth_web.py` | Separate FastAPI `/connect` and `/auth/linkedin/callback`; single in-memory OAuth state, 600-second lifetime, invalidation before token exchange; synchronous httpx token exchange. Loads dotenv on import. |
| `credential_store.py` | One fixed keyring service/account; token JSON storage, expiry calculation and 60-second expiry margin; deletion helper. Actual OS backend was not exercised. |
| `linkedin_client.py` | Synchronous `GET /v2/userinfo`, controlled API errors, normalized profile; returned `id` is OIDC `sub`, not a verified Person URN. |
| `capabilities.py` | Scope parsing and manifest; post publishing and restricted history disabled. |
| `author_identity.py` | Read-only `/v2/me` diagnostic; uses returned Profile API `id` for a Person URN, never OIDC `sub`; no durable identity evidence/account binding. Not invoked. |
| `drafts.py` | SQLite connection, schema bootstrap, validated content, CRUD and optimistic revision update. |
| `approvals.py` | Snapshot/hash/revision approvals, 15-minute expiry, local decision function, offline preview; no network operation. |
| `approval_cli.py` | Displays snapshot/revision/hash/expiry, requires exact `APPROVE`, calls local decision function. No independent actor authentication. |

Registered tools (observed): `health_check`, `get_account_capabilities`, `get_linkedin_connection_status`, `get_my_profile`, `verify_linkedin_connection`, `create_linkedin_draft`, `get_linkedin_draft`, `list_linkedin_drafts`, `update_linkedin_draft`, `delete_linkedin_draft`, `request_publish_approval`, `get_publish_approval_status`, `preview_approved_publish`, `check_linkedin_author_identity`. Neither approval decision nor executable publishing is registered.

Other locations: `tests/` has the five suites listed above; `scripts/` has workspace/bundle checks and advisory Codex hooks; `.codex/` contains project preferences, hook declarations and specialist configurations; `.agents/skills/` contains workflow skills. `plugin/` is separate optional plugin packaging with a session reminder. `Architecture/`, `architecture.md`, `BUILD_WITH_CODEX.md` and `plans/` are design/instruction artifacts, not implementation evidence.

## Persistence and environment inspection

The existing default `data/linkedin_drafts.db` was opened via SQLite URI `mode=ro`. Only schema and journal mode were queried; no application bootstrap or data mutation was invoked. WAL mode was observed; WAL/SHM files exist. Source connection setup uses WAL and a 10-second busy timeout.

- `drafts`: `id` primary key; `content`, `status` (default `draft`), `revision` (default 1), `created_at`, `updated_at`. Index: `idx_drafts_updated` on descending update time.
- `publish_approvals`: `id` primary key; `draft_id`, `draft_revision`, `content_snapshot`, `content_hash`, `status`, `created_at`, `expires_at`, nullable `decided_at`, `consumed_at`. Status CHECK permits PENDING, APPROVED, REJECTED, EXPIRED, CONSUMED.
- No account IDs, approval actor, author/visibility/distribution binding, foreign-key relationship, publication ledger or audit table is present. No versioned migration framework exists; initialization is `CREATE TABLE IF NOT EXISTS`.

`.env` exists. Key names only were inventoried: client ID/secret, redirect URI, scopes, API version and live-publish toggle. Values were not disclosed or changed. `.env.example` contains client ID/secret, redirect URI and API version keys, but omits scopes, database path and live toggle. Runtime source does not read `LINKEDIN_LIVE_PUBLISH_ENABLED`; live writes are absent rather than protected by an implemented publishing toggle. The audit did not enable publishing or evaluate private configuration values as proof of readiness.

`pyproject.toml` permits Python >=3.11 and MCP >=2,<3, although the observed environment is Python 3.12.12/MCP 2.3.0. `uv.lock` exists. Pytest is the only declared development extra. `.gitignore` excludes environment secrets, virtualenv, caches and local databases/data.

## Implementation gaps and design drift

1. **Live release remains blocked.** No Posts adapter, supported API-version validation, durable verified-author record, publication command, one-time claim, operation ledger, recovery workflow or independently authenticated approval actor exists. No live write path was found. Preserve that boundary.
2. **Approval binding is incomplete for future publication.** Hash covers UTF-8 content only; approval binds draft/revision but no account/action/author/visibility/distribution/actor. PUBLIC/MAIN_FEED is hardcoded only in the preview. CONSUMED is allowed in schema but unused. Repeated previews deliberately do not consume approvals.
3. **Concurrency is not proven.** Decision SELECTs precede a conditional UPDATE, without `BEGIN IMMEDIATE`; affected-row count is not checked. Python's connection context does not itself begin a transaction for these SELECTs. Snapshot creation and preview validation span separate connections. Sequential duplicate-decision and stale-revision tests do not establish concurrent approval/claim safety.
4. **Expiry persistence differs from effective status.** `get_approval` computes EXPIRED without persisting it. `decide_approval` updates EXPIRED then raises inside the connection context; rollback undoes that update. Effective expiry checks still reject use. This is source-derived, not covered by current tests.
5. **Capability drift.** `draft_local` reports unavailable/“not implemented” despite implemented and tested CRUD. Profile capability uses scope presence rather than endpoint validation. The richer blueprint capability fields are absent; publishing correctly stays unavailable.
6. **Single-user trust boundary.** Fixed keyring identity, unscoped draft/approval IDs and unauthenticated local CLI do not provide multiuser isolation or separately authenticated human decisions. No remote MCP authentication/control plane is implemented.
7. **HTTP/error/observability gaps.** HTTP clients are constructed inside functions and mocked through patching, rather than injected transports. Structured error codes, operation IDs, append-only audit and telemetry modules are absent. Exception logging needs later credential-redaction review; no runtime logging changes were made.
8. **Missing test evidence.** No current tests for OAuth state/callback or credential storage, author diagnostic, MCP contracts, CLI actor control, expiry, wrong account, parallel decisions/claims, crash/restart, duplicate execution, malformed profile responses, 403/429/5xx or timeout-after-send. Existing HTTP error coverage is 401 only. No global network-denial fixture is present.
9. **Hooks are advisory.** Guard inspects `command`, while the available execution tool uses `cmd`; matcher omits `exec_command`, and edits/mutations are not inspected by `evaluate`. Malformed JSON returns a reminder and success. Existing tests cover only three heuristic examples. This is no backend authorization boundary; activation was not verified.
10. **Version-control baseline needs attention.** `git rev-parse --show-toplevel` reports `C:/Users/dhanu/Downloads`, and scoped `git status --short -- .` reports `?? ./`. This project is untracked within a parent repository, so a project-specific tracked diff/rollback baseline is unavailable. Unrelated parent changes were left untouched. No branch or database backup was needed for this documentation-only audit; establish a safe source baseline and database backup before future runtime/schema edits.
11. **Gate numbering conflicts.** `plans/EXECUTION_PLAN.md` separates B (persistence) and C (API feasibility), whereas the blueprint combines them and numbers later gates differently. This audit follows the user's Gate A scope; reconcile numbering before implementation. README/status historical eight-test claims are superseded by this observed 22-test baseline, not by new integration evidence.

## Change scope, rollback and next action

Changes: this audit plus required Gate A status/decision record updates only. No source, tests, dependencies, hook configuration, environment or database records were edited. Test runs created normal temporary/cache artifacts; SQLite read-only inspection may use WAL shared-memory bookkeeping. No new architecture choice or migration was approved.

Rollback: remove this audit and revert the Gate A documentation entries if needed; no runtime/database rollback is required. Stop here for user review. Any Gate B implementation requires a separate instruction, a minimal acceptance plan, actual-schema migration comparison, and publishing-safety workflow where applicable. Do not proceed to live publication.
