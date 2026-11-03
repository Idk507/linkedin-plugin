# Optional installable Codex desktop plugin

This plugin contains only the onboarding skill and a passive session hook. The repository-native `.agents/skills` and `.codex/` files are the primary development integration. This plugin does NOT configure a LinkedIn MCP server endpoint because the existing server is a local Windows `stdio` service with machine-specific paths and private credentials; discover/configure it on the machine explicitly. No `mcp.json` is supplied to avoid pretending it is portable.

The `plugin.json` manifest follows the portable Agent Plugins structure, with a Codex compatibility manifest under `.codex-plugin/`. Hooks are for manually installed Codex desktop use and require user review/trust. Do not submit hook-bearing packages to the public plugin directory. Before installing verify the Codex plugin workflow on your installed version.
