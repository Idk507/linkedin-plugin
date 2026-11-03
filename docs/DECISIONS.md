# Architecture decisions

ADR-001: Preserve existing Python MCP 2.3.0 application. Status: accepted.

ADR-002: SQLite for local drafts/approvals; PostgreSQL with transaction claims for remote multiuser deployment. Status: proposed; inspect schema before migration.

ADR-003: No automated live posts while Person URN unavailable. Status: accepted, blocked by /v2/me HTTP 403.

ADR-004: Repo-native Codex overlay (`.codex/`, `AGENTS.md`, `.agents/skills/`) separate from installable plugin. Status: accepted.

Add decisions with date, evidence, alternatives, and operational consequences. Never invent tests.

2026-11-03 — Gate A evidence record (no new architecture decision): preserve existing runtime and stop after inventory. `docs/REPO_AUDIT.md` records the observed flat module structure, SQLite schema, 14 registered tools, 22 passing offline tests and missing safety guarantees. Workspace/bundle checks passed; live APIs were not exercised. No migration or architecture alternative was selected; no later gate was executed. Reconcile conflicting gate numbering and establish a project Git baseline before implementation. This entry records the completed audit, not sign-off for architecture changes.

2026-11-03 — Gate B implementation record, pending review: user requested building after Gate A. Follow `plans/EXECUTION_PLAN.md` gate numbering. Use an explicit additive, backed-up legacy migration rather than silent account assignment; retain old approval records but require fresh canonical review. Store account ownership as a server-controlled local namespace, explicitly distinct from verified LinkedIn identity. Use immutable revision history/canonical JSON hashes and `BEGIN IMMEDIATE` for local approval transitions; retain offline-only CLI decisions and 14 MCP tools. Evidence: 47 tests passed in 6.37s; real DB copy migration preserved original columns/rows; original DB unchanged. Consequences: legacy DB requires explicit rollout; authenticated human approval, verified OAuth/author binding, one-time claims and live writes remain blocked/later gates. Rationale, alternatives, limitations and rollback are in `docs/GATE_B.md`; no live publication or future-gate sign-off is implied.
