# Gate B — local persistence and approval safety

Implemented 2026-11-03; stopped for review. Gate names follow `plans/EXECUTION_PLAN.md`. Acceptance plan: `docs/GATE_B_PLAN.md`.

## Behavior and boundaries

- `storage.py` owns schema version 1, connection setup, safe workflow errors and explicit additive legacy migration. The migration reserves a new backup filename, uses SQLite backup (including committed WAL contents), then performs DDL/data changes in one `BEGIN IMMEDIATE` transaction. Unknown columns/tables and existing backup paths are rejected. Service must be stopped during migration.
- Draft CRUD filters by the server process's `LINKEDIN_LOCAL_ACCOUNT_ID`, default `local-single-user`. No MCP tool accepts an account argument. Each revision appends immutable content and SHA-256 history in the same transaction as the edit. Existing whitespace trimming and revision-conflict behavior remain.
- Approvals retain existing public fields and add local account, canonical JSON and payload SHA-256. Canonical UTF-8 JSON binds approval ID, account, action, LOCAL_OFFLINE target, unverified/null author, draft/revision, content bytes/digest, PUBLIC visibility, MAIN_FEED distribution, request time and expiry. No normalization changes exact stored content bytes.
- SQLite triggers protect revision history, approval snapshot fields, draft ownership and permitted approval status transitions. Conditional decision updates check affected rows. Request creation, decision and preview validation use one write transaction each; expiry is persisted before returning an expiry error.
- Existing local CLI displays the full canonical tuple and digest before confirmation. It remains a temporary offline review mechanism, not independent actor authentication. Approval decision is not an MCP tool. Repeated previews never consume approval and always report `ready_for_live_publish=false`.
- Local tool errors retain existing success/error fields and add stable workflow codes. All 14 tool names and argument contracts remain. OAuth, credential storage, profile HTTP, author diagnostics and capability source files were verified byte-identical to the pre-build archive. No dependencies changed.

Local namespaces are ownership partitions, not verified OAuth-account or Person-URN binding. Switching LinkedIn credentials does not establish or update these namespaces automatically. Do not use this boundary as remote/multiuser authentication. Verified LinkedIn author identity, authenticated human approval, durable execution claims and publication recovery remain future gates. No live publishing path or runtime live-toggle implementation was added. Existing stale capability reporting remains documented in the Gate A audit.

## Existing database rollout

**The user's current database was not migrated.** The new storage code returns `MIGRATION_REQUIRED` for the legacy database until the explicit migration runs. This prevents silently assigning old data to an account. OAuth/profile code remains available. Tests use fresh temporary databases or copies.

Before rollout, stop all MCP/approval processes, select the intended local namespace and ensure the same process environment is used by server and CLI. `LINKEDIN_LOCAL_ACCOUNT_ID` is a process environment variable; server startup does not automatically load new settings from `.env`. Choose the database path deliberately if `LINKEDIN_DRAFT_DB` is configured.

For the audited default DB and default local namespace, the explicit command is:

```powershell
uv run python -m linkedin_mcp.storage --database data/linkedin_drafts.db --backup data/backups/pre-gate-b.db --legacy-account-id local-single-user
```

This command has **not** been executed on the original DB. It refuses an existing backup destination. Schema drift also stops migration. The migration preserves existing IDs, content, revisions, timestamps and decision history. Only the currently available draft revision can be backfilled; older revisions cannot be reconstructed. Legacy approvals remain readable as history, but their canonical binding is null and preview/decision validation requires a new approval request and fresh review. They are never silently promoted.

## Verification observed

Baseline before source edits: `uv run pytest -v` — **22 passed in 1.83s**, exit 0.

Initial regression run reproduced cross-account access, missing canonical binding, nonpersistent expiry and two concurrent decision successes. An initial MCP-contract test also had an incorrect SDK field assumption; it was corrected to the installed SDK's `input_schema`.

Final `uv run pytest -v` output:

```text
collected 47 items
============================= 47 passed in 6.37s ==============================
```

Exit 0; no skips or failures. This includes the original 22 tests, 7 migration tests and 18 storage/approval tests. New coverage includes backup preservation/non-overwrite, unknown schema refusal, migration failure rollback, idempotent initialization, wrong-account CRUD/approval access, immutable revisions, payload tampering, expiry at the exact boundary, rejection, changed/deleted drafts, independent-connection concurrent decisions/edits, repeatable offline preview, full CLI display, stable MCP errors and registration boundaries.

The test suite now denies external socket connections; numeric loopback connections are allowed for Windows asyncio internals. An initial overly strict guard blocked that internal connection; the final guard and full suite pass. Tests make no real LinkedIn requests. No claims are made about HTTP 403/429/5xx, malformed remote responses, timeout-after-send, crash-after-claim or duplicate network execution: the future publisher/claim modules do not exist yet.

An additional offline verification copied the actual current DB through a read-only connection, migrated only the temporary copy, compared all original columns/rows, and ran SQLite integrity checking. It passed; the original schema and rows were also compared unchanged. No row values or secrets were printed. The successful verification copy was removed.

`scripts/check_workspace.py` and `scripts/validate_bundle.py` both returned PASS/exit 0. Ruff/mypy remain undeclared/unconfigured and were not run. No test coverage percentage was measured. This is local/offline verification, not OAuth, Inspector or external integration acceptance.

## Review, security impact and rollback

Self-review checked account-filtered SQL, immutable tuple verification, transaction boundaries, connection closure, safe migration failure and unchanged network boundaries. This closes the reproduced local decision race and expiry rollback bug; it does not establish a live release gate.

Work branch: `codex/gate-b-safety-baseline` in the existing parent Git repository. The project remains untracked there; no source commit, remote push or merge was made. Pre-edit source/docs/tests/dependency baseline is archived at ignored `data/backups/gate-b-source-baseline.zip` without `.env` or credentials. Restore the four changed existing source files from that archive and remove the new storage module to roll back runtime code before any database migration. If migrating later, stop the service and restore source and the matching SQLite backup together; never overwrite a running database or retain mismatched WAL files.

An earlier verification script completed its assertions but failed temporary-directory cleanup due to an open SQLite connection. Connections were closed explicitly in the successful rerun. Automatic approval review then rejected the requested removal of the earlier directory as blocked by policy; `C:\Users\dhanu\AppData\Local\Temp\linkedin-gate-b-1li5mc35` remains and contains local verification copies. No deletion workaround was attempted.

Next action: review Gate B and its explicit database rollout. Gate C may research the official authorized author-identity options only after a separate instruction. No later gate started.
