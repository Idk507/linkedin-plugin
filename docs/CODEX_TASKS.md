# Copy-and-run Codex prompts

## Start here — Gate A

> Open AGENTS.md, docs/STATUS.md, plans/EXECUTION_PLAN.md and BUILD_WITH_CODEX.md. Use $linkedin-architecture. Execute **Gate A only**, performing a read-only audit of my CURRENT repository. Preserve all source, tests, `.env` and SQLite files. Run the existing tests, inspect registration of MCP tools and OAuth callbacks, identify exact import and schema differences, and write docs/REPO_AUDIT.md with file-grounded findings. Do not build the publisher or change runtime behavior. End with exact verification results and stop.

## Gate B

> Use $linkedin-architecture and $linkedin-publishing-safety. Read the Gate A audit and implement only Gate B after reconciling real schemas. Add deterministic tests for immutable approval payload, account binding and race-safe status transitions, using a disposable database. Run $linkedin-test-gate and stop with evidence.

## Gate C

> Use $linkedin-publishing-safety. Investigate only the officially documented authorization path for a valid LinkedIn Person URN with this app's actual scopes and `/v2/me` HTTP 403. Build a fail-closed adapter with fake transport and diagnostic status. No live API write or browser automation. Stop and report blockers.

## Gate D

> Implement typed LinkedIn Posts adapter behind an injected HTTP transport with LIVE=false. All tests are mocked, verify headers, JSON schema, errors, and ambiguous timeout behavior. Use $linkedin-test-gate; update STATUS and stop.

## Gate E

> Implement one-time durable claim with append-only audit, crash recovery and UNKNOWN_OUTCOME with no automatic retry after send. Test concurrent claim, duplicate tool call, stale approval, wrong account and kill-after-send. No real network write. Stop after tests.

## Gate F

> Implement and test out-of-band user approval UX with exact target/content/visibility and account. No LLM approval primitive. Demonstrate revocation, expiry, concurrency, CSRF and session boundaries. Stop.

## Gate G

> Perform **read-only** live readiness audit only. Do not publish. List missing permission/identity/reconciliation evidence for explicit independent operator review. Keep LIVE=false.

## Gate H

> Design remote authenticated MCP, validate current ChatGPT connection requirements and add local mock tests, IAM, encrypted token storage, OpenTelemetry and deployment runbook. Do not expose remote endpoint until approved. Stop.
