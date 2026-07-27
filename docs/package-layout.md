# Package layout — skill-craft-market

## Principle

**skill-craft-market never vendors skill prompt bodies.**  
It only pins or documents how hosts obtain packages from **skill-craft**.

```text
skill-craft/                    # SoT
  skills/skill-interop/
    SKILL.md
    prompts/ scripts/ references/

skill-craft-market/             # catalog / adapters
  faces/
    claude/.claude-plugin/marketplace.json   # git-subdir pins
    grok/README.md
    codex/README.md
    hermes/README.md
  docs/package-layout.md
```

## Claude pin shape

```json
{
  "name": "skill-interop",
  "source": {
    "source": "git-subdir",
    "url": "https://github.com/whichguy/skill-craft.git",
    "path": "skills/skill-interop",
    "ref": "main"
  }
}
```

Until skill-craft publishes a release tag, `ref` stays `main`. Prefer tags (and optional
`sha`) for production pins after the first release.

## Adding a skill pin

1. Land the skill under `skill-craft/skills/<leaf>/`.
2. Add a pin entry to `faces/claude/.claude-plugin/marketplace.json` (git-subdir).
3. Update Grok/Codex/Hermes face READMEs if install notes differ.
4. Do **not** copy `SKILL.md` or prompts into this repo.

## Skill unit (agentskills.io)

A skill is a directory with `SKILL.md` (+ optional tree). Hosts consume it via skill-dir
symlinks (`install.sh`) or host marketplace adapters that reference the skill-craft path.
