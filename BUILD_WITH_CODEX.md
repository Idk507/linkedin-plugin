# LinkedIn Personal MCP — Codex Engineering Blueprint

**Edition:** 2026-11-03 | **Target:** Windows, Python 3.12, uv, MCP SDK 2.3.0, SQLite (local), PostgreSQL (production)

## 0. Mission and existing verified state

Build a personal-account LinkedIn MCP service, using the official LinkedIn API, with independently enforced human approval for every external write. The existing source project is `C:\Users\dhanu\Downloads\linkedin_mcp`. **Extend it; do not replace it.** User-confirmed results: LinkedIn OAuth with `email,openid,profile,w_member_social`; authenticated `GET /v2/userinfo`; `8/8` tests passed at the prior checkpoint; draft `aceb765d-724f-465e-9951-01c40d60306e` at revision 1; human approval successfully recorded and dry-run preview validated. A diagnostic call to `/v2/me` produced HTTP 403. Do not claim that a live post was published. Tests for later draft/approval phases have not been proven by the user in the current conversation.

**Non-negotiable blocker:** Do not use the OpenID Connect `sub` as `urn:li:person:{sub}` without authoritative documentation or an authorized independent validation that this mapping is supported for the active application. Current `/v2/me` access is denied. Do not scrape LinkedIn, automate the website, reverse engineer internal endpoints, request unapproved scopes or fabricate author URNs. A working and approved alternative may need LinkedIn developer support. Keep live posting disabled until that gate is met.

## 1. User-facing product scope and exclusions

The assistant must support personal account connection/status, permitted profile reads, local draft create/read/list/update/delete, approval request/status, safe offline previews, scheduled workflows and remote ChatGPT access once authenticated. Support public posts, reactions, comments, media, analytics and post mutation only to the extent that **the actual application scopes and official endpoints permit**. Restricted functions (direct messages, connection invitations, broad searches, profile edits, arbitrary post history) must return explicit `NOT_AUTHORIZED` or `NOT_SUPPORTED` responses rather than fake execution. Keep local draft deletion distinct from deleting a published post.

Use a capability matrix with fields: `feature`, `implemented`, `scope_granted`, `identity_verified`, `endpoint_validated`, `human_approval_required`, `currently_available`, `reason`. In no circumstance infer API authorization solely from `w_member_social` for a read endpoint. The capability tool must report both granted scope and operational readiness.

## 2. Architecture

```
ChatGPT/Codex MCP client
         | stdio for local tests / HTTPS Streamable HTTP for remote
         v
MCP tools (strict, typed, no raw token access)
         |
Identity and policy gate ---> account binding + scope/endpoint matrix
         |
Draft + publication workflow ---> transactional approval ledger ---> one-time claim
         |                                              |
         +-> SQLite local / PostgreSQL deployed          +-> local HITL CLI / user-authenticated UI
         |
Author resolver [BLOCKED pending authorized resolution]
         |
LinkedIn official Posts adapter [LIVE=false] -> safe failure reconciliation
         |
Structured audit + OpenTelemetry + operational metrics
```

Separate the LinkedIn OAuth authorization boundary from ChatGPT-to-MCP authorization. The remotely deployed MCP **must** enforce per-user authentication and bind every tool invocation to the server-side owner's account, rather than trusting account IDs supplied by the model. OAuth tokens are stored in the Windows credential manager in the existing local prototype; production uses encrypted, per-user token records with KMS/Key Vault and rotation. Never expose tokens in tool output, logs, database exports or exception bodies. The `stdio` transport should remain local-only.

## 3. Repository changes (do not clobber existing files)

```
src/linkedin_mcp/
    auth_web.py, credential_store.py, linkedin_client.py, capabilities.py, server.py
    drafts.py, approvals.py, approval_cli.py, author_identity.py
    publishing/
        __init__.py
        schemas.py              # typed request/response + state enums
        author_resolver.py      # explicit unverifiable identity state
        linkedin_posts.py      # HTTP adapter, versioned headers, strict payload validation
        ledger.py              # transactional claim / outbox / attempt journaling
        service.py             # approval -> claim -> network -> reconciliation
        recovery.py            # UNKNOWN_OUTCOME operator reconciliation
    security/
        policy.py, principal.py, audit.py
    storage/
        migrations.py, repositories.py
    observability/
        logging.py, metrics.py
    remote/
        app.py, auth.py        # only after local service safety is proven
scripts/
    preflight.py, operator_publish.py, reconcile_attempt.py, migrate.py
tests/
    test_author_resolution.py, test_publish_payload.py,
    test_publish_policy.py, test_publish_ledger.py,
    test_publish_recovery.py, test_mcp_tool_contracts.py,
    test_hook_policy.py
```

Preserve current public tool names and backward compatibility unless tests and a migration are provided. Use `uv`, Python 3.12, `mcp==2.3.0` or the confirmed installed version; don't silently switch API classes. Verify `MCPServer` imports and tool registration in the installed SDK source before adding code. Prefer `httpx`, `pydantic`, `sqlite3`, `pytest`, `respx` (if installed), `ruff`, and `mypy`. Do not add Docker, Redis, LangGraph or paid API dependencies without demonstrable need.

## 4. Data model and persistence invariants

`drafts`: id, account_id (single-user migration with deliberate legacy mapping), content, revision, status, updated_at, created_at. `approval_requests`: id, draft_id, account_id, snapshot_text, snapshot_sha256, revision, action='PUBLISH', visibility, distribution, resolved_author_urn, approved_by, expires_at, decided_at, status. `publish_operations`: id, approval_id UNIQUE, account_id, lifecycle (`CLAIMED`, `REQUEST_SENT`, `PUBLISHED`, `FAILED_BEFORE_SEND`, `UNKNOWN_OUTCOME`, `RECONCILED`), request_sha256, remote_post_urn, attempt_no, response_code, last_error_class, timestamps. `audit_events`: append-only event_id, subject, action, target, decision, timestamp, correlation_id, sanitized details.

Every mutation uses explicit transactions, parameterized SQL, optimistic revision checks, and a UNIQUE constraint on `approval_id`. Atomic claim must be committed **before** external network submission. Store an attempt intent durably before sending. Never automatically retry `POST /rest/posts` after a timeout or uncertain response. Terminal `PUBLISHED` cannot revert to `CLAIMED`. A claim on an already-used approval returns its recorded result or an explicit in-progress/unknown status, never another POST. Approval expiry must be checked transactionally at claim time. Any change in content, author, visibility, target account, or distribution invalidates existing approval.

SQLite is appropriate for the existing single-user Windows prototype; use `BEGIN IMMEDIATE`, WAL, busy timeout and migration backups. For production horizontal scale, use PostgreSQL transactions, row locks and a serialized publication queue. Enforce row-level account scope in repositories, not merely tool wrappers.

## 5. Author identity gate (P0 blocker)

Current evidence: `GET /v2/me` returned HTTP 403 with existing scopes; OIDC `sub` is available but **not established as the Person URN ID**. First inspect current official LinkedIn documentation and granted products. Implement `AuthorResolver` with `UNVERIFIED`, `VERIFIED`, `UNAVAILABLE`, and `EXPIRED` states. A verified author requires a documented supported API response or an explicitly authorized verification procedure; record source, timestamp, member account binding and evidence. Never derive the author from public profile URL, email, vanity name, OIDC sub by assumption, scraping or operator's unauthenticated input. If no compliant route exists, keep `LIVE=false` and report the blocker. Do not demand unsupported `r_liteprofile` or `r_basicprofile` if not granted by LinkedIn.

Codex must independently review the official docs and provide a short, cited architecture decision record (`docs/ADR_AUTHOR_ID.md`). Do not infer access from old posts API examples. A `403` is an explicit authorization result, not an instruction to bypass it.

## 6. LinkedIn publishing API adapter

Use `POST https://api.linkedin.com/rest/posts`, exact currently supported `Linkedin-Version: YYYYMM` verified against the current documentation (never pin an obsolete default), `X-Restli-Protocol-Version: 2.0.0`, and bearer token retrieved only inside the adapter. A plain-text post payload is structured as:

```json
{
  "author": "urn:li:person:VERIFIED_ID_ONLY",
  "commentary": "Exact approved snapshot",
  "visibility": "PUBLIC",
  "distribution": {
    "feedDistribution": "MAIN_FEED",
    "targetEntities": [],
    "thirdPartyDistributionChannels": []
  },
  "lifecycleState": "PUBLISHED",
  "isReshareDisabledByAuthor": false
}
```

Treat this as a schema template that must be checked against the supported live API version before use. Validate successful status and `x-restli-id` if returned. Parse all errors conservatively: 401 expired/invalid credentials; 403 missing product/scope; 429 rate-limit; 5xx transient; network timeout after request sent => `UNKNOWN_OUTCOME`, no replay. Never log Authorization headers, token exchange data, full post content or personal emails. Implement a mockable HTTP transport and contract tests; no real network requests in ordinary test runs.

## 7. HITL authorization contract

Workflow: `DRAFT -> APPROVAL_REQUESTED -> APPROVED -> CLAIMED -> REQUEST_SENT -> PUBLISHED` or `REJECTED/EXPIRED/FAILED_BEFORE_SEND/UNKNOWN_OUTCOME`. The model may request an approval and inspect status but must not be able to approve its own publishing request. The approval CLI or authenticated operator UI is independent. Approval is for the full immutable tuple `(account_id, action, draft_id, draft_revision, snapshot_sha256, author_urn, visibility, distribution, expiry)`. Bind approval to a human identity. Validate strict expiry, nonce uniqueness and one-time consumption. A refusal or changed draft must result in zero LinkedIn calls.

In the local POC, `approval_cli.py` must display exact content and require a typed confirmation. For any final live publish, require a second explicit terminal confirmation with exact target account/visibility. Never provide an unguarded `publish_post(content)` MCP tool. Even if Codex hooks are disabled or fail open, the backend publishing service must enforce approval and authorization.

## 8. Capability and tool contracts

Read-only: `health_check`, `get_linkedin_connection_status`, `get_my_profile`, `get_account_capabilities`, `check_linkedin_author_identity`, `get_linkedin_draft`, `list_linkedin_drafts`, `get_publish_approval_status`, `get_publish_operation_status`.

Local mutations: `create_linkedin_draft`, `update_linkedin_draft` (expected revision required), `delete_linkedin_draft`, `request_publish_approval`.

Publishing: expose `preview_approved_publish` (no network). `execute_approved_publish` must **not be registered to the MCP server in local phase**; it remains an operator CLI command. Only consider exposing an authenticated tool later if the backend approval gate and client controls are independently validated and enabled. `get_account_capabilities` must report `post_publish.available=false` while author ID or live gate is absent, regardless of scope grants.

Use typed errors with codes: `NOT_AUTHENTICATED`, `MISSING_SCOPE`, `AUTHOR_UNVERIFIED`, `APPROVAL_REQUIRED`, `APPROVAL_EXPIRED`, `DRAFT_REVISION_CONFLICT`, `ALREADY_CLAIMED`, `UNKNOWN_OUTCOME`, `RATE_LIMITED`, `UPSTREAM_FORBIDDEN`, `UNSUPPORTED_FEATURE`. Do not leak raw exception bodies to MCP clients.

## 9. Phased build instructions for Codex

### Gate A — Repository audit / no modifications

Inspect current tree, `pyproject.toml`, SDK version, `.env.example`, existing tests and DB structure. Run `uv run pytest -v`, `uv run python -c "from linkedin_mcp.server import mcp; print(type(mcp).__name__)"` and inspect registered tools. Record baseline in `docs/BASELINE.md`; report exact passed/failed counts. Never print `.env`, secrets or token values. Before changes, make a Git branch and backup local SQLite if applicable. Stop if source diverges from this proposal; propose migration first.

**Acceptance:** documented existing state, green baseline or specific failures, non-destructive plan.

### Gate B — Security + author-ID feasibility (no live writes)

Research official scopes/profile identification, current API version and Posts API requirements. Implement `AuthorResolver` fail closed with tests. Write `docs/ADR_AUTHOR_ID.md`, `docs/API_CAPABILITIES.md`, `docs/THREAT_MODEL.md`. Operator-only test diagnostic; do not call arbitrary LinkedIn endpoints beyond authorized read checks.

**Acceptance:** unverified identities rejected by publisher, explicit reason visible; no web automation.

### Gate C — Typed mock publisher

Implement Pydantic request validation, stable payload digest, mock HTTP transport and normalized API responses. HTTP transport must be injectable. Test missing token, unsupported version, 201 with ID, 400/401/403/429, 5xx, and timeout. No outbound network in tests.

**Acceptance:** ≥90% coverage on new publishing/identity modules; sensitive-data logging audit.

### Gate D — Durable one-time publish ledger

Implement SQLite migrations with unique approval claim, intent-before-send, deterministic status machine, expiry/nonce checks and crash recovery. Build concurrent tests using separate SQLite connections/threads. Simulate crash after CLAIMED, after REQUEST_SENT and after 201 before receipt persistence; `UNKNOWN_OUTCOME` must not cause automatic retry.

**Acceptance:** two concurrent invocations result in ≤1 HTTP POST; expired/mutated/rejected approval => 0; repeated attempt => 0 additional POSTs.

### Gate E — Operator-controlled live publication (feature flag OFF)

Implement `scripts/operator_publish.py` with dry-run default; it must refuse unless `LINKEDIN_LIVE_PUBLISH_ENABLED=true`, authorized Person URN verified and bound to account, human approval current, API version supported, and explicit terminal confirmation performed. Place send attempt behind ledger. Use mock transport for acceptance. Never enable real networking during automated tests.

**Acceptance:** offline end-to-end receipts show no network by default; actual remote write stays disabled until human deliberately enables and validates it.

### Gate F — Live publishing release gate

Only after official author identity issue is resolved and operator authorizes the action, perform one small test publication to personal account. Record the exact approved content and target identity, response status, returned post URN, timestamp and audit evidence. On uncertainty, halt and reconcile manually; no blind retry. Never do this autonomously on the basis of this build specification.

**Acceptance:** a visible post exists on correct personal profile, independently confirmed; or clearly documented BLOCKED state if author resolution unavailable.

### Gate G — Remote MCP and ChatGPT integration

Only after B–E are validated, create authenticated HTTPS Streamable HTTP MCP service, OAuth authorization for the MCP client, user/account binding, secret store, origin checks, rate limits, load management, observability and deployment configuration. Confirm actual ChatGPT plan/workspace support before promising custom write tools. Test tenant isolation and permission revocation. Keep local stdio server usable.

**Acceptance:** remote unauthorized request rejected, cross-account requests rejected, independent HITL required for writes, no secret exposure, traced requests and rollback plan.

### Gate H — Expanded compliant social workflows

Implement media, comments, reactions, editing/deletion, analytics, scheduling only with separately verified scopes/endpoints. For denied permissions, provide manual-assist workflows (draft and copy) rather than browser automation. Test each capability independently and add per-operation HITL.

**Acceptance:** capability manifest grounded in tested endpoints; no unsupported LinkedIn action represented as complete.

## 10. Comprehensive testing matrix

Unit: schema validation, content/revision hashing, author resolver, policy, expiry, allowed transitions, error normalization. Integration: real SQLite migrations with independent connections, token store mocked, mocked HTTP transport, process restart and reconciliation, account ownership. E2E: inspector tool discovery, OAuth read-only profile, local draft CRUD, CLI human review, approved dry-run. Security: prompt injection cannot approve; forged account IDs rejected; replayed/expired approvals rejected; stdout/stderr sanitized; lack of hooks does not bypass gate; egress network forbidden in default tests. Reliability: two processes competing for approval; token expiry between approval and send; request sent but no response; 201 response but persistence failure; API version sunset; rate limit; invalid member URN; revoked token; DB busy; disk full. Observe p50/p95 latency, error classes, queue depth, approval rejection rates, unknown outcomes, trace IDs, safe account identifiers. No uncontrolled real LinkedIn traffic in CI.

## 11. Security and deployment principles

`LINKEDIN_LIVE_PUBLISH_ENABLED=false` is the default. Do not use client-supplied author/account IDs as trusted. Treat all LinkedIn content as untrusted and prevent prompt injection in returned content. HTTPS + OAuth for remote MCP, short-lived bound sessions, KMS encryption, least privilege, explicit deletion consent, audit retention policy, backup/restore. For scale, separate stateless API from durable worker and PostgreSQL. Avoid automatic retry of non-idempotent posting. Set alerts on `UNKNOWN_OUTCOME` and multiple claim attempts. Configure structured JSON logs with request ID and redacted secrets.

## 12. Codex operating discipline (low token use)

Use the shipped `AGENTS.md`, phase prompts (`docs/CODEX_PHASE_PROMPTS.md`), and skills. At every phase: inspect only relevant files, write concise ADR before large changes, patch the smallest units, run narrow tests then full suite, update `docs/PROGRESS.md` and `docs/NEXT_SESSION.md` after each accepted phase. Never implement every phase in a single model call. Report actual terminal results, changed paths, limitations, next phase, and decisions needed. Do not claim tests ran unless run in the actual project. Use hooks as defense in depth only, not security enforcement.

## 13. Final acceptance checklist

The project is complete only after confirmed authorized identity, actual HITL with non-model approval, transactional one-time posting, checked API version, verified personal-profile post, secure and observable remote endpoint, independent integration/security tests, documented recovery and rollback, and a clear supported/unsupported capability matrix. **Until the identity gate is passed, completion means a secure offline publishing pipeline, not a functional live LinkedIn publisher.**

## References (verify recency during implementation)

- Plugin packaging: https://developers.openai.com/plugins/build/plugins
- Codex hooks: https://learn.chatgpt.com/docs/hooks
- LinkedIn developer documentation: https://learn.microsoft.com/en-us/linkedin/
- LinkedIn Posts API: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
- LinkedIn OAuth: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
