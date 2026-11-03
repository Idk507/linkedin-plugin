# LinkedIn MCP — Senior Codex Development Workspace

This is an **overlay**, not a replacement application. Apply it to the EXISTING Windows project `C:\Users\dhanu\Downloads\linkedin_mcp` after creating a backup/git commit. The ZIP also contains a separate optional local plugin under `plugin/`.

## What is actually verified

OAuth token scopes `email,openid,profile,w_member_social`; `GET /v2/userinfo` succeeds for the personal member; the 8 prior unit tests passed; draft creation and human approval plus an offline dry-run were user-verified; `/v2/me` returns `403`. No live LinkedIn post has been created. Do not claim that 19 tests or any further phase ran in the user's repository.

## Canonical implementation locations

`AGENTS.md` is loaded as Codex repository instructions. `.codex/config.toml` is trusted-project configuration. `.codex/agents/*.toml` contains read-only specialists. `.agents/skills/*/SKILL.md` contains opt-in/instructed workflow skills. `.codex/hooks.json` supplies project lifecycle hooks; these are *advisory*, not an authentication boundary. `docs/` and `plans/` are engineering records. `scripts/` are deterministic checks. `plugin/` is an optional manually installable Codex desktop plugin, not a requirement for project Codex automation.

## First run

1. Read `INSTALL_WINDOWS.md`. Do NOT unzip over the existing source blindly.
2. Run `uv run pytest -v` in the existing source repository before modifications.
3. Start Codex from the existing repository and use the first prompt in `docs/CODEX_TASKS.md`. Only execute Gate A (read-only audit).
4. After completing Gate A, validate `scripts/check_workspace.py` and run offline hook tests. Then execute one implementation gate at a time.

## Architecture and delivery

The authoritative complete implementation scope is in `BUILD_WITH_CODEX.md`. It is intentionally detailed and defines signed-off gates, schemas, tests, failure handling, security and release criteria. Project instructions here remain short to save agent context.

## Critical limitation

Do not transform OIDC `sub` into a Person URN without an authorized and verified method; `w_member_social` alone does not prove the `/v2/me` endpoint is authorized. Live publish is disabled until that is resolved, one-time durable approval consumption exists, and controlled acceptance tests pass. Do not bypass LinkedIn API restrictions with a browser bot.

## Reference docs

- https://developers.openai.com/codex/config-reference
- https://developers.openai.com/codex/subagents
- https://developers.openai.com/codex/hooks
- https://developers.openai.com/plugins/build/plugins
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
