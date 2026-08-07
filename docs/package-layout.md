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
    skills/skill-interop/  # materialized copy (not escaping symlink)
    agents/… (optional)

skill-craft-market/                  # catalog / adapters
  .claude-plugin/marketplace.json    # ONLY committed catalog
  faces/
    claude/README.md                 # pointer to root catalog
    grok/README.md
    codex/README.md
    hermes/README.md
  docs/package-layout.md
  docs/setup-matrix.md
  docs/pin-policy.md
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

Production pins use **git tags**. Advance a pin when that leaf’s content or package version changes at a released tag (see docs/pin-policy.md).

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
3. Add a pin entry to root `.claude-plugin/marketplace.json` only (`path: plugins/<leaf>`).
4. Update faces READMEs only if host install notes differ.
5. Do **not** copy `SKILL.md` or prompts into this repo.

## Skill unit (agentskills.io)

A skill is a directory with `SKILL.md` (+ optional tree). Hosts consume it via skill-dir
symlinks (`install.sh`) or Claude marketplace adapters that reference the skill-craft
**plugin** path.


## External leaves

Some catalog entries (e.g. **lennox-s40**) pin a **standalone** repo. skill-craft must **not** also ship `skills/<same-name>/`. Install skill-dir from the standalone clone’s `install.sh`.
