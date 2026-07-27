# skill-craft-market

**Multi-host marketplace adapters** that pin skills from
[skill-craft](https://github.com/whichguy/skill-craft).

This repo is a **catalog only**. It does **not** contain skill prompt bodies
(`SKILL.md` SoT lives in skill-craft). Each host face points at a skill-craft
path (e.g. `skills/skill-interop`) via git-subdir or host-specific install notes.

## skill-craft vs skill-craft-market vs claude-craft

| Repo | Contains | Role |
|------|----------|------|
| **skill-craft** | `skills/<leaf>/…` | Host-neutral skill source of truth |
| **skill-craft-market** (this repo) | Host faces / pins / docs | Marketplace adapters only |
| **claude-craft** | Claude Code plugins | Separate product marketplace |

## Faces

```text
faces/
  claude/     Claude Code marketplace.json (git-subdir pins → skill-craft)
  grok/       Grok install notes
  codex/      Codex install notes
  hermes/     Hermes skillhub notes
```

### Claude

```sh
# Add this marketplace face (path to faces/claude)
claude plugin marketplace add /path/to/skill-craft-market/faces/claude
# or, after publish, a git source that resolves marketplace.json under faces/claude

claude plugin install skill-interop@skill-craft-market
```

Pin shape: `source: { source: git-subdir, url: whichguy/skill-craft, path: skills/skill-interop, ref: main }`
(until the first release tag).

### Grok / Codex / Hermes

See `faces/<host>/README.md`. Skill-dir side-load remains:

```sh
# From a skill-craft clone
./install.sh --skill skill-interop
```

## Package layout

See [docs/package-layout.md](docs/package-layout.md).

## License

Catalog metadata is dual-licensed with skill-craft intent (MIT-friendly). Skill
packages themselves are licensed in skill-craft.
