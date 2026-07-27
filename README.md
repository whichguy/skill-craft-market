# skill-craft-market

**Multi-host marketplace adapters** that pin skills from
[skill-craft](https://github.com/whichguy/skill-craft).

This repo is a **catalog only**. It does **not** contain skill prompt bodies
(`SKILL.md` SoT lives in skill-craft). Claude pins use the skill-craft
**plugin view** (`plugins/<name>/`). Other hosts use skill-dir notes that
point at `skills/<name>/`.

## skill-craft vs skill-craft-market vs claude-craft

| Repo | Contains | Role |
|------|----------|------|
| **skill-craft** | `skills/<leaf>/…` + `plugins/<leaf>/` Claude view | Host-neutral skill source of truth |
| **skill-craft-market** (this repo) | Host faces / pins / docs | Marketplace adapters only |
| **claude-craft** | Claude Code plugins | Separate product marketplace |

## Faces

```text
faces/
  claude/     Claude Code marketplace.json (git-subdir pins → skill-craft plugins/)
  grok/       Grok install notes (skill-dir → skills/)
  codex/      Codex install notes (skill-dir → skills/)
  hermes/     Hermes skillhub notes (skill-dir → skills/)
```

Root `.claude-plugin/marketplace.json` is the published Claude catalog (kept in
sync with `faces/claude/`).

### Claude

```sh
# Git marketplace (preferred after publish)
claude plugin marketplace add whichguy/skill-craft-market
claude plugin marketplace update skill-craft-market
claude plugin install skill-interop@skill-craft-market
# also: prompt-audit prompt-align prompt-migrate prompt-refine c-plan
claude plugin list --json

# Local clone of this repo (root has .claude-plugin/marketplace.json)
claude plugin marketplace add /path/to/skill-craft-market
```

**Pin path must be the Claude plugin view**, not the bare skill leaf:

```text
source: {
  source: git-subdir,
  url: https://github.com/whichguy/skill-craft.git,
  path: plugins/skill-interop,   # NOT skills/skill-interop
  ref: main                      # prefer a release tag after first cut
}
```

Bare `skills/<name>` fails Claude plugin validate (missing `plugin.json`).

If `CLAUDE_CONFIG_DIR` is set (e.g. c-thru), installs go to that config tree —
use `env -u CLAUDE_CONFIG_DIR` for the persistent `~/.claude` smoke path.

### Grok / Codex / Hermes

See `faces/<host>/README.md`. Skill-dir side-load remains:

```sh
# From a skill-craft clone
./install.sh --skill skill-interop
```

## Package layout

See [docs/package-layout.md](docs/package-layout.md).

## Install lifecycle (operator)

| Mode | Action |
|------|--------|
| **Dev skill-dir** | Clone skill-craft → `./install.sh --skill <name> [--agents] [--relink]` |
| **Claude plugin** | `claude plugin install <name>@skill-craft-market` |
| **Upgrade skill-dir** | `git pull` in skill-craft + `./install.sh … --relink` if links wrong |
| **Upgrade plugin** | `claude plugin update <name>` / marketplace update |
| **Uninstall skill-dir** | Remove host symlink under `~/.{claude,grok,codex}/skills/<name>` |
| **Uninstall plugin** | `claude plugin uninstall <name>@skill-craft-market` |

## License

Catalog metadata is dual-licensed with skill-craft intent (MIT-friendly). Skill
packages themselves are licensed in skill-craft.
