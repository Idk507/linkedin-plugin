# Sequential implementation gates — one per Codex turn

## Gate A — Existing-source inventory [COMPLETE]

Read-only inspect `pyproject.toml`, src, tests, database migrations, current hooks, environment configuration (never print values), git status. Run existing tests; document current verified behavior and drift from blueprint. Do not code. Output: `docs/REPO_AUDIT.md`; stop.

## Gate B — Safety and persistence baseline [IMPLEMENTED — REVIEW PENDING]

Create hardened schemas/migrations only after comparing actual SQLite tables; add account binding, approval payload canonicalization, immutable revision digest and transactional status transitions. Test concurrency, rejection, expiry. No LinkedIn network writes. Stop for user review.

Observed 2026-11-03: 47 offline tests pass; see `docs/GATE_B.md`. Original database remains unmigrated. Local ownership namespaces are implemented; verified OAuth identity and authenticated human approval remain separate future requirements. Use this plan's gate numbering where the older blueprint differs.

## Gate C — Official LinkedIn API feasibility

Research official current docs for member author identification and API versions. Document endpoints, scopes and whether accessible; add mock author resolver and fail-closed status. No OIDC sub guessing, no real posts. Stop if blocked.

## Gate D — Posts adapter, offline

Typed payload, `Linkedin-Version` and Rest.li header contract, fake transport, response `x-restli-id`, mapped 400/401/403/429/5xx, timeout-after-send uncertain result. No real network tests. Stop.

## Gate E — Durable one-time publication command

Atomic approval claim before sending; statuses and append-only audit; lease/recovery without duplicate POST; kill-and-restart tests. The first executable path must remain dry_run=true, live_enabled=false. Stop.

## Gate F — Human control plane

CLI authenticated local single-user control and secure UI design for remote. Approve/reject/revoke, exact payload display; no model approval tool. Verify account isolation and CSRF. Stop.

## Gate G — Controlled live acceptance [BLOCKED]

Only when documented authorized Person URN + correct scopes + operator approval + preflight evidence + explicit live toggle. Never perform this in unattended CI/Codex. User chooses when to submit one public test post. Capture real response and reconcile. Stop.

## Gate H — Remote MCP and ChatGPT integration

OAuth and authentication between ChatGPT and MCP; HTTPS Streamable HTTP; multiuser isolation; secrets, IAM, tracing, auto-scaling, worker leases and runbooks. Re-validate current ChatGPT connector capabilities. Stop.

## Gate I — Extended features

Only after scoped endpoint validation: edits, deletes, comments/reactions, analytics from permitted sources, image/video, scheduling. Restricted features remain explicit unsupported. Stop.

For every gate, record: evidence, code changes, tests observed, security impact, rollback, unresolved issues and next action.
