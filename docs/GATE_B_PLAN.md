# Gate B acceptance plan

2026-11-03. The user's instruction to start building authorizes the next gate only. Use gate names in `plans/EXECUTION_PLAN.md`: B is storage/approval safety; C is official API feasibility. No HTTP publishing adapter or human control plane in this gate.

1. Preserve the 22-test baseline, OAuth/profile modules and 14 MCP tool names. Create a source rollback archive because the project is untracked under its parent Git repository.
2. Add versioned storage initialization and explicit legacy migration with an exclusive backup destination. Preserve drafts and approval records; put legacy rows in a deliberate local account namespace. Require fresh review for approvals that lack the new canonical binding. Do not migrate the user's DB during development.
3. Scope repository operations to server-configured `LINKEDIN_LOCAL_ACCOUNT_ID` (default `local-single-user`); never accept an account argument from MCP tools. This is local ownership partitioning, not authenticated LinkedIn identity. OAuth binding and authenticated operator identity remain blockers for later gates.
4. Bind immutable approvals to canonical UTF-8 bytes containing namespace, action, target, revision, content digest, visibility/distribution and expiry. Author remains explicitly unverified/null. Retain immutable revision snapshots. Serialize decisions and validation with SQLite transactions; persist expiry before returning an error.
5. Add offline tests for migration/backup/preservation, isolation, tampering, stale/deleted drafts, expiry, rejection, concurrent decisions and edits, and tool registration. Test with real temporary SQLite connections; make no network writes.

Rollback: restore edited source from ignored `data/backups/gate-b-source-baseline.zip`. No production DB change is planned. An operator migration requires stopping the service and retains a SQLite backup; restore that backup with the service stopped if reverting the schema/code together. Stop for review after observed test results and STATUS/DECISIONS updates.
