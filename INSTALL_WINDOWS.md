# Windows installation — safe overlay for existing source

The kit is NOT a new implementation of your LinkedIn MCP. It contains Codex policy files, skills, scripts and a separate optional plugin. Do not unzip directly on top of existing source without reviewing filename collisions.

From `C:\Users\dhanu\Downloads\linkedin_mcp`, first run `git status` and `uv run pytest -v`; commit/backup your working code and database **without uploading secrets**. Extract the ZIP into a separate directory. Copy the top-level `AGENTS.md`, `.codex/`, `.agents/`, `docs/`, `plans/` and `scripts/` directories into the repository, but review conflicts before overwriting. Keep current `src/`, `tests/`, `.env` and `pyproject.toml` unchanged. If existing `AGENTS.md` or `docs/` exist, merge carefully rather than replace. `BUILD_WITH_CODEX.md` is a specification only.

Run `uv run python scripts/check_workspace.py` from the source repository. To run hook checks, execute `uv run pytest -v tests/test_codex_hook_policy.py` **only after manually copying this test file into your existing tests directory**; it is optional. Restart Codex, mark the project trusted if prompted, and begin with Gate A prompt from `docs/CODEX_TASKS.md`.

**Codex config and hooks:** Project-scoped `.codex/config.toml` and `.codex/hooks.json` are loaded only under supported trusted-project configurations. Hooks may need explicit enablement/trust and are never substitutes for backend policy. Verify your installed Codex version supports each setting. `sandbox_mode=workspace-write` is a safer proposed value; if Codex app settings override it, keep the stricter effective policy.

**Optional standalone plugin:** `plugin/` is distributable separately as a manual Codex desktop plugin. It does not automatically wire the current local server into ChatGPT or share host credentials. For development, prefer repository-local skills and existing MCP Inspector. Review plugin hook commands before trusting them.
