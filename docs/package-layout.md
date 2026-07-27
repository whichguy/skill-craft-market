# Package layout — skill-craft-market

## Principle

**skill-craft-market never vendors skill prompt bodies.**  
It only pins or documents how hosts obtain packages from **skill-craft**.

```text
skill-craft/                         # SoT
  skills/skill-interop/              # agentskills body (all hosts skill-dir)
    SKILL.md
    prompts/ scripts/ references/
  plugins/skill-interop/             # Claude distribution view only
    .claude-plugin/plugin.json
    skills/skill-interop → ../../skills/skill-interop
    agents/… (optional)

skill-craft-market/                  # catalog / adapters
  .claude-plugin/marketplace.json    # published Claude catalog
  faces/
    claude/.claude-plugin/marketplace.json   # same pins (keep in sync)
    grok/README.md
    codex/README.md
    hermes/README.md
  docs/package-layout.md
```

## Claude pin shape

Claude must pin the **plugin view**, not the bare skill leaf:

```json
{
  "name": "skill-interop",
  "source": {
    "source": "git-subdir",
    "url": "https://github.com/whichguy/skill-craft.git",
    "path": "plugins/skill-interop",
    "ref": "main"
  }
}
```

Until skill-craft publishes a release tag, `ref` stays `main`. Prefer tags (and optional
`sha`) for production pins after the first release.

**Do not** set `"path": "skills/skill-interop"` — Claude plugin validate requires
`.claude-plugin/plugin.json` in the package root.

## Skill-dir paths (Grok / Codex / Hermes)

Skill-dir installs target the agentskills body:

```text
skill-craft/skills/<leaf>/  →  ~/.grok/skills/<leaf>
                            →  ~/.codex/skills/<leaf>
                            →  ~/.hermes/skills/software-development/<leaf>
                            →  ~/.claude/skills/<leaf>   (side-load, not plugin)
```

Use skill-craft `./install.sh --skill <leaf>`.

## Adding a skill pin

1. Land the skill under `skill-craft/skills/<leaf>/`.
2. Add Claude view `skill-craft/plugins/<leaf>/` (`plugin.json` + skill symlink).
3. Add a pin entry to **both** root and `faces/claude` marketplace.json (`path: plugins/<leaf>`).
4. Update Grok/Codex/Hermes face READMEs if install notes differ.
5. Do **not** copy `SKILL.md` or prompts into this repo.

## Skill unit (agentskills.io)

A skill is a directory with `SKILL.md` (+ optional tree). Hosts consume it via skill-dir
symlinks (`install.sh`) or Claude marketplace adapters that reference the skill-craft
**plugin** path.
