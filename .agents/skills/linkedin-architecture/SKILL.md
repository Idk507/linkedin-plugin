---
name: linkedin-architecture
description: Use before modifying LinkedIn MCP architecture, module boundaries, workflows, schemas or API adapters in the existing Python repository.
---
# Architecture workflow

Read `AGENTS.md`, `docs/STATUS.md`, `BUILD_WITH_CODEX.md` and relevant current code. Identify the requested gate; map existing implementation and interfaces before changing anything. Write a minimal decision record to `docs/DECISIONS.md` only after user sign-off for architecture changes. Prefer small functional increments; provide file-by-file tests and a rollback path. Stop after one gate. Never assume legacy sample code is implemented.
