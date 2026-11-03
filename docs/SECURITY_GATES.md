# Enforced service-side security gates

## Identity and authorization

A valid stored OAuth token is not proof of post-author identity or permission for every endpoint. `GET /v2/me` yields HTTP 403 for this application. Until a documented authorized Person-URN resolution is proven, keep live publishing disabled. Request only approved scopes; no scraping, automated browser actions, credential extraction or guessed identifiers.

## Approval design

Approval request includes `account_id`, `oauth_subject`, `verified_author_urn`, `draft_id`, `revision`, `sha256(canonical_payload)`, `target`, `visibility`, `requested_at`, `expires_at`, `approver_id`, `state`. Canonical serialization must be stable; check all fields after approval. Human approval must be a distinct authenticated trust boundary, not an LLM-exposed tool. Local CLI is temporary for single user only.

## Execution

Use an append-only audit and durable transaction to claim an approved action before one and only one HTTP write. State transitions REQUESTED -> APPROVED -> CLAIMED -> SENT -> PUBLISHED, or REJECTED/EXPIRED/FAILED_BEFORE_SEND/UNKNOWN_OUTCOME. On uncertain send never auto-retry. Save operation ID, response status, LinkedIn post URN when available and correlation ID. Handle cancellation and double-click race tests.

## Secrets

Never log bearer tokens, client secrets, auth codes, email or raw callback query strings. Use OS keyring locally and KMS/Key Vault envelope encryption for deployed multiuser tokens. Separate inbound ChatGPT-MCP authentication from outbound LinkedIn OAuth. Least privilege; HTTPS; strict CSRF state, callback routing and rate limits.

## Testing

All unit/integration tests use fake HTTP transport. Live operations require separate explicit operator approval and are NOT part of Codex automation. Hook guards do not replace service authorization.
