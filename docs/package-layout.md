# Package layout — skill-craft-market

## Principle

**skill-craft-market never vendors skill prompt bodies.**  
It only pins or documents how hosts obtain packages from **skill-craft**.

```text
skill-craft/                         # SoT
  .grok-plugin/marketplace.json      # generated local-source index
  .cursor-plugin/marketplace.json    # generated local-source index
  skills/skill-interop/              # agentskills body (all hosts skill-dir)
    SKILL.md
    prompts/ scripts/ references/
  plugins/skill-interop/             # shared distribution view
    .claude-plugin/plugin.json
    .cursor-plugin/plugin.json
    skills/skill-interop/  # materialized copy (not escaping symlink)
    agents/… (optional)

skill-craft-market/                  # catalog / adapters
  .claude-plugin/marketplace.json    # ONLY committed catalog
  faces/
    claude/README.md                 # pointer to root catalog
    grok/README.md
    codex/README.md
    cursor/README.md
    hermes/README.md
  docs/package-layout.md
  docs/setup-matrix.md
  docs/pin-policy.md
```

## Marketplace pin shape

Claude and Codex pin the **plugin view**, not the bare skill leaf. This historical
example illustrates the shape; current versions, release tags, and immutable
SHAs are recorded in [the catalog](../.claude-plugin/marketplace.json):

```json
{
  "name": "skill-interop",
  "source": {
    "source": "git-subdir",
    "url": "https://github.com/whichguy/skill-craft.git",
    "path": "plugins/skill-interop",
    "ref": "main",
    "sha": "1d46133c3ac7232b00690d9d8ecdfcd932c6592b"
  }
}
```

Production pins require **full verified commit SHAs**. An optional `ref` records a release tag or branch for reachability checks. Advance a pin when that leaf’s content or package version changes at a released tag or a verified published commit (see docs/pin-policy.md).

**Do not** set `"path": "skills/skill-interop"` — Claude plugin validate requires
`.claude-plugin/plugin.json` in the package root.

## Skill-dir paths (all hosts)

Skill-dir installs target the agentskills body:

```text
skill-craft/skills/<leaf>/  →  ~/.grok/skills/<leaf>
                            →  ~/.codex/skills/<leaf>
                            →  ~/.cursor/skills/<leaf>
                            →  ${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills/<leaf>
                            →  ~/.hermes/skills/software-development/<leaf>
                            →  ~/.claude/skills/<leaf>   (side-load, not plugin)
```

Use skill-craft `./install.sh --skill <leaf>`.

## Adding a skill pin

1. Land the skill under `skill-craft/skills/<leaf>/`.
2. Add Claude view `skill-craft/plugins/<leaf>/` (`plugin.json` + materialized skill tree).
3. Add a pin entry to root `.claude-plugin/marketplace.json` only (`path: plugins/<leaf>`).
4. Update faces READMEs only if host install notes differ.
5. Do **not** copy `SKILL.md` or prompts into this repo.

## Skill unit (agentskills.io)

A skill is a directory with `SKILL.md` (+ optional tree). Hosts consume it via skill-dir
symlinks (`install.sh`) or Claude-compatible marketplace adapters that reference the skill-craft
**plugin** path.


## External leaves

Some catalog entries (e.g. **lennox-s40**) pin a **standalone** repo. skill-craft must **not** also ship `skills/<same-name>/`. Install skill-dir from the standalone clone’s `install.sh`.

**until-loop** is a separate external package from `whichguy/until-loop`.
**improve** remains canonical in `skill-craft/skills/improve`, pinned through
`plugins/improve` at the immutable release recorded in the catalog. Its bundled runtime does not create
another standalone Until Loop skill leaf or change ownership of Improve.

**workflow** is the marketplace identity for the standalone
`whichguy/workflow-engine` package. Its user-facing Codex display name is
**Weave**, while the canonical skill remains `skills/workflow/SKILL.md` and the
generated distribution remains `plugins/workflow/`. Keep those files in the
standalone repository; this catalog records only its immutable pin. Backchain,
Until Loop, and ask-agent remain separately selected prerequisites when a run
needs them and are never copied into the Workflow package.
For a skill-directory install, reuse
`skill-craft/install.sh --from /path/to/workflow-engine/skills/workflow`;
Workflow does not duplicate that multi-host installer.

**ask-agent** remains canonical in `skill-craft/skills/ask-agent` and is
distributed through `skill-craft/plugins/ask-agent` independently of Workflow.
A Workflow agent packet names it as a host-selected delegation route; it does
not make that package an unconditional install-time dependency of authored or
command-only workflows.
