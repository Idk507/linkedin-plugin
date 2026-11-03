"""Perform offline checks against Codex engineering kit files."""

import json
import tomllib
from pathlib import Path


def main() -> int:
    """Validate expected manifests and safety instructions."""
    root = Path(__file__).resolve().parents[1]
    for path in [".codex/config.toml", *[str(x.relative_to(root)) for x in (root / '.codex/agents').glob('*.toml')]]:
        with (root / path).open('rb') as stream:
            tomllib.load(stream)
    for path in [".codex/hooks.json", "plugin/plugin.json", "plugin/.codex-plugin/plugin.json", "plugin/hooks/hooks.json"]:
        json.loads((root / path).read_text(encoding='utf-8'))
    skills = list((root/'.agents/skills').glob('*/SKILL.md'))
    assert len(skills) >= 3
    assert all(s.read_text(encoding='utf-8').startswith('---') for s in skills)
    print('PASS: TOML, JSON, skill front matter presence, basic structure')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
