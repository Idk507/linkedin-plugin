---
name: linkedin-publishing-safety
description: Mandatory for any LinkedIn OAuth, identity resolution, approvals, remote write, posting, scheduling, deletion or credential-handling implementation.
---
# Publish safety gate

Before any code change, read `docs/SECURITY_GATES.md` and current credential/approval/author modules. Treat an OIDC subject as not equivalent to a LinkedIn Person URN until proven by an authorized documented mechanism. Never use browser automation to bypass API restrictions. Require exact-payload approval bound to user, account, draft revision, digest, target, visibility, expiry and one-time execution claim. Commit claim durably before network writes; never automatically retry an ambiguous timeout. Return UNKNOWN_OUTCOME and require reconciliation. All tests must use fake transports unless a human explicitly enables an isolated integration run. Preserve `LINKEDIN_LIVE_PUBLISH_ENABLED=false`.
