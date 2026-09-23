# Setup matrix — skills, plugins, policy

## Portable skills

| Host | Install skill from skill-craft | Install plugin | Marketplace repository |
|------|-------------------------------|----------------|------------------------|
| Grok | `./install.sh --grok-only` | `grok plugin install <leaf> --trust` after review/registration | `whichguy/skill-craft` native Grok index |
| Claude Code | `./install.sh --claude-only` | `claude plugin install <leaf>@skill-craft-market` | `whichguy/skill-craft-market` |
| Cursor | `./install.sh --cursor-only` | Native package/local test or marketplace UI; see [Cursor notes](../faces/cursor/README.md) | `whichguy/skill-craft` native Cursor index |
| Codex | `./install.sh --codex-only` | `codex plugin add <leaf>@skill-craft-market` | `whichguy/skill-craft-market` |
| OpenCode | `./install.sh --opencode-only` | N/A — skill-dir | N/A |
| Hermes | `./install.sh --hermes-only` | N/A — managed skill-dir copy | N/A |

Add `--skill <leaf>` to select one skill. No host flag targets all six hosts.
For exactly Grok, Claude, Cursor, Codex, and OpenCode:

```sh
./install.sh --grok-only --claude-only --cursor-only --codex-only --opencode-only
```

Use `--dry-run` to preview or `--status` to inspect skill-dir state. Keep one
installation track per skill per host; confirm cached plugin enablement before
calling it an active duplicate. Cursor also reads Claude/Codex compatibility
skill directories.

OpenCode uses `${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills/<leaf>`.
Keep compatible Claude-directory discovery pointed at the same source; installation
does not change OpenCode providers, permissions, or experimental task settings.

Register Claude/Codex with `plugin marketplace add whichguy/skill-craft-market`.
Grok registers `grok plugin marketplace add whichguy/skill-craft` after the native
adapter has been published, or a local source checkout for development. Cursor
team import/public submission are separate publication steps. Native source
indexes expose the source skills and the vendored Backchain bundle; this catalog
also includes Lennox S40 and standalone Until Loop. Improve remains owned by skill-craft;
the Until Loop entry does not replace its source or marketplace release. See [package layout](package-layout.md).

## Suites

Claude product suites (review-suite, planning-suite, wiki-suite) belong in
**claude-craft**. Portable leaves such as c-plan belong in skill-craft.

## Policy hooks

To **register policy**, use **plan-oversight** and its host-specific setup.
Neither skill-craft-market nor skill-craft's installer installs ExitPlanMode,
Stop, or residual-fire policy hooks. Grok's Claude hook compatibility is a
separate configuration choice.

## Runtime capability

Installation makes skill instructions discoverable. It does not prove engine
execution, install external tools, or provide another project's harness. Check
each skill's runtime requirements; DevLoop execution uses Grok/Hermes bindings.
