# skill-craft-market

**Claude-compatible plugin catalog for Claude Code and Codex** that pins packages from
[skill-craft](https://github.com/whichguy/skill-craft) (and allowed external repos).
**Catalog only** — does not vendor skill prompt bodies.

**No hooks.** This marketplace never installs plan-oversight, ExitPlanMode soft_exit,
or residual skill-fire. Those are **L-Policy** → [plan-oversight](https://github.com/whichguy/plan-oversight).

## Three verbs (memorize)

| Verb | Meaning | Tool |
|------|---------|------|
| **install skill** | skill-dir body on a host | skill-craft `./install.sh` |
| **install plugin** | Host plugin cache from its supported catalog | Claude `plugin install`, Codex `plugin add`; Grok/Cursor use source-repo adapters |
| **register policy** | ExitPlanMode / Stop hooks | plan-oversight `register-hooks` (not this repo) |

Pick **one track per leaf** on a machine: plugin **or** skill-dir, not both (dev on `main` → skill-dir; consumers wanting pins → plugin).

## Setup matrix

See **[docs/setup-matrix.md](docs/setup-matrix.md)** for Grok / Claude / Cursor / Codex / OpenCode / Hermes.
The source repo's [distribution guide](https://github.com/whichguy/skill-craft/blob/main/docs/distribution.md)
describes both personal installs and marketplace publication.

### Quick answers

| Want | Do |
|------|-----|
| Skills on Grok/Claude/Cursor/Codex/OpenCode (development) | In a skill-craft clone: `./install.sh --grok-only --claude-only --cursor-only --codex-only --opencode-only` |
| Skills on Claude (dev) | same skill-dir **or** plugin — not both |
| Skills on Claude (pinned release) | `claude plugin marketplace add whichguy/skill-craft-market` then `claude plugin install <leaf>@skill-craft-market` |
| Native Grok/Cursor marketplace | Source repo `whichguy/skill-craft`, using its generated native indexes; see host notes |
| Suites (review-plan, wiki, …) | **claude-craft** marketplace — not this catalog |
| ExitPlanMode residual fire | **plan-oversight** register — never this catalog, never `install.sh` |

## Codex marketplace

```sh
codex plugin marketplace add whichguy/skill-craft-market
codex plugin list --marketplace skill-craft-market --available --json
# Install only leaves that are not already installed through skill-dir:
codex plugin add shiploop@skill-craft-market
```

For a local checkout, register its root instead:

```sh
codex plugin marketplace add /absolute/path/to/skill-craft-market
```

In the Codex app, open Plugins and select **Skill Craft** as the marketplace.
Start a new thread after installing a plugin to load its skills. Marketplace
registration makes packages discoverable; it does not install every package.
Use `codex plugin marketplace upgrade skill-craft-market` to refresh a Git
marketplace. A local marketplace reads the checkout. Existing skill-dir
installations remain independent; do not install a duplicate plugin for a leaf.

Installation IDs and invocation names differ: install
`shiploop@skill-craft-market`, then invoke `$shiploop:shiploop` in Codex or
`/shiploop:shiploop` in Claude. The plugin name supplies the namespace; the
marketplace name selects the catalog. Bare `$shiploop` can select a separate
skill-directory installation.

The same `.claude-plugin/marketplace.json` is supported by Codex; no second
catalog is needed. Root-repository plugins use `source: "url"`; subdirectory
plugins use `source: "git-subdir"` with a non-root path. Codex omits root-dot
`git-subdir` entries. Codex presentation and policy fields are ignored by Claude.
See [official marketplace documentation](https://developers.openai.com/plugins/build/plugins#marketplace-metadata).

## Claude catalog

```sh
claude plugin marketplace add whichguy/skill-craft-market
claude plugin marketplace update skill-craft-market
claude plugin install review-coverage@skill-craft-market
```

Pin path is always skill-craft **`plugins/<leaf>`** (or external repo root for specials like lennox-s40), at a **full verified commit SHA**, optionally labeled with a release tag or branch.

Canonical file: **`.claude-plugin/marketplace.json`** (only committed catalog).

## Skill-dir (all hosts)

```sh
git clone https://github.com/whichguy/skill-craft.git
cd skill-craft
./install.sh --skill review-coverage   # all six hosts by default, including OpenCode and Hermes
./install.sh --status --skill review-coverage
```

## External release package: Until Loop

[`until-loop`](https://github.com/whichguy/until-loop) is a standalone package
from its dedicated repository, pinned to the immutable commit recorded in
[the catalog](.claude-plugin/marketplace.json). Improve remains a
canonical skill-craft package with its own bundled Until Loop runtime and
independent release pin; see its release section below.

```sh
# Codex: add the marketplace once, then install Until Loop.
codex plugin marketplace add whichguy/skill-craft-market
codex plugin marketplace upgrade skill-craft-market
codex plugin add until-loop@skill-craft-market

# Claude Code: add the marketplace once, then install Until Loop.
claude plugin marketplace add whichguy/skill-craft-market
claude plugin marketplace update skill-craft-market
claude plugin install until-loop@skill-craft-market
```

## Google Apps Script MCP server

`mcp-gas-deploy@skill-craft-market` provides 16 Google Apps Script tools,
including local validation, project discovery, deployment, built-in guides,
and remote sandboxes for Git worktrees. The standalone adapter comes from
[mcp-gas-deploy](https://github.com/whichguy/mcp-gas-deploy/tree/main/marketplace/mcp-gas-deploy).
It includes no planning dependency or lifecycle hooks.

The source repository is private. Installation and the first server launch
require existing GitHub read access and working Git credentials; catalog
discovery does not grant repository access.

```sh
# After registering this marketplace:
codex plugin marketplace upgrade skill-craft-market
codex plugin add mcp-gas-deploy@skill-craft-market

claude plugin marketplace update skill-craft-market
claude plugin install mcp-gas-deploy@skill-craft-market
```

Requires Node.js 22.13 or later and npm. The first MCP start downloads and builds
the server with `npx`; Google authentication is a separate tool operation.
Git-based starts can take more than a minute. The adapter gives Codex a 180-second
startup budget. For Claude Code, launch with `MCP_TIMEOUT=180000 claude` to allow
the same startup time; this is separate from individual tool execution timeouts.
The catalog pins the adapter to a commit, and its launcher pins the server to
a verified commit as well. Updating the catalog does not silently advance that
runtime pin. These pins identify source revisions; npm dependencies still resolve
under the source package's version constraints. Installation alone does not verify Google account access or deploy
an application. Enable one GAS server integration per host to avoid duplicate
servers from `gas-suite`, the original GAS marketplace, or a manual MCP setup.

## Private source: backchain

The Backchain 0.3.5 plugin contains the planning skill and Plan Dispatcher.
In Codex, select `$backchain:backchain` or `$backchain:plan-dispatcher`;
in Claude, use `/backchain:backchain` or `/backchain:plan-dispatcher`.

Backchain is a private repository. Its marketplace entry requires existing GitHub
read access; listing the entry does not grant access. CI access requirements are
documented in [pin policy](docs/pin-policy.md#private-source-access).

## External pin: lennox-s40

Thermostat skill body lives in **[whichguy/lennox-s40](https://github.com/whichguy/lennox-s40)** (not skill-craft monorepo).

```sh
cd ~/src/lennox-s40 && ./install.sh    # skill-dir
# Claude/Codex plugin via this catalog (immutable main SHA, standalone repository URL)
```

## Pin policy

Standalone **Until Loop** is also available as `until-loop@skill-craft-market`
from [whichguy/until-loop](https://github.com/whichguy/until-loop), using the
immutable catalog pin. **Improve** retains its canonical skill-craft source and its own
release pin; installing Until Loop does not replace Improve.

Normative release steps: skill-craft [`docs/skill-release-checklist.md`](https://github.com/whichguy/skill-craft/blob/main/docs/skill-release-checklist.md).  
Market-side notes: [docs/pin-policy.md](docs/pin-policy.md).

**Do not bulk-retarget** umbrella tags when leaf content is unchanged vs tip.

## Faces

Host notes under `faces/{claude,grok,cursor,codex,hermes}/` point at the setup matrix.
No second marketplace.json under faces. Grok/Cursor indexes live in the source
repo and reference its existing packages; this repo retains only release pins.

## Layout

See [docs/package-layout.md](docs/package-layout.md).

## Improve release candidate

`improve@skill-craft-market` publishes the standalone Improve workflow from
`skill-craft/plugins/improve`, at the version and immutable SHA recorded in
[the catalog](.claude-plugin/marketplace.json). It includes the
compatible Until Loop runtime, so installing this plugin does not require a
separate Until Loop checkout. The package remains a release candidate; catalog
discovery and isolated runtime tests do not establish full execution on every
host.

```sh
codex plugin marketplace upgrade skill-craft-market
codex plugin add improve@skill-craft-market
# Claude Code:
claude plugin marketplace update skill-craft-market
claude plugin install improve@skill-craft-market
```

Choose one installation track. If Improve is already exposed through a local
skill-directory pilot, keep that pilot or deliberately switch to this pinned
plugin; do not install a duplicate merely to update the catalog. These commands
are for hosts where the marketplace is already registered.

Start with `Dry-run $improve:improve on these changes without writing files.` See the
[Improve guide](https://github.com/whichguy/skill-craft/blob/b6486f7a09eeafd5bd1e8478e4d4211a4ed3747a/skills/improve/README.md)
for scope, commit overrides, completion conditions and runtime boundaries.
The ClaudeCraft skill with the same name is a separate implementation.
