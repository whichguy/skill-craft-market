# skill-craft-market

**Claude-format plugin catalog** that pins packages from
[skill-craft](https://github.com/whichguy/skill-craft) (and allowed external repos).
**Catalog only** — does not vendor skill prompt bodies.

**No hooks.** This marketplace never installs plan-oversight, ExitPlanMode soft_exit,
or residual skill-fire. Those are **L-Policy** → [plan-oversight](https://github.com/whichguy/plan-oversight).

## Three verbs (memorize)

| Verb | Meaning | Tool |
|------|---------|------|
| **install skill** | skill-dir body on a host | skill-craft `./install.sh` |
| **install plugin** | Claude/Codex/Grok plugin cache from this catalog | host `plugin install …@skill-craft-market` (when supported) |
| **register policy** | ExitPlanMode / Stop hooks | plan-oversight `register-hooks` (not this repo) |

Pick **one track per leaf** on a machine: plugin **or** skill-dir, not both (dev on `main` → skill-dir; consumers wanting pins → plugin).

## Setup matrix

See **[docs/setup-matrix.md](docs/setup-matrix.md)** for Claude / Grok / Codex / Hermes.

### Quick answers

| Want | Do |
|------|-----|
| Skills on Grok/Codex/Hermes | `git clone skill-craft && ./install.sh --skill <leaf>` |
| Skills on Claude (dev) | same skill-dir **or** plugin — not both |
| Skills on Claude (pinned release) | `claude plugin marketplace add whichguy/skill-craft-market` then `claude plugin install <leaf>@skill-craft-market` |
| Suites (review-plan, wiki, …) | **claude-craft** marketplace — not this catalog |
| ExitPlanMode residual fire | **plan-oversight** register — never this catalog, never `install.sh` |

## Claude catalog

```sh
claude plugin marketplace add whichguy/skill-craft-market
claude plugin marketplace update skill-craft-market
claude plugin install review-coverage@skill-craft-market
```

Pin path is always skill-craft **`plugins/<leaf>`** (or external repo root for specials like lennox-s40), at a **git tag**.

Canonical file: **`.claude-plugin/marketplace.json`** (only committed catalog).

## Skill-dir (all hosts)

```sh
git clone https://github.com/whichguy/skill-craft.git
cd skill-craft
./install.sh --skill review-coverage   # all four hosts by default
./install.sh --status --skill review-coverage
```

## External release packages: Until Loop and Improve

[`until-loop`](https://github.com/whichguy/until-loop) and `improve` are two
standalone packages from the external Until Loop repository, each pinned to
`v0.3.0-rc.3`. Improve bundles its compatible Until Loop runtime, so it does
not require a separate Until Loop installation.

```sh
# Codex: add the marketplace once, then choose a package.
codex plugin marketplace add whichguy/skill-craft-market
codex plugin marketplace upgrade skill-craft-market
codex plugin add until-loop@skill-craft-market
# Or:
codex plugin add improve@skill-craft-market

# Claude Code: add the marketplace once, then choose a package.
claude plugin marketplace add whichguy/skill-craft-market
claude plugin marketplace update skill-craft-market
claude plugin install until-loop@skill-craft-market
# Or:
claude plugin install improve@skill-craft-market
```

## External pin: lennox-s40

Thermostat skill body lives in **[whichguy/lennox-s40](https://github.com/whichguy/lennox-s40)** (not skill-craft monorepo).

```sh
cd ~/src/lennox-s40 && ./install.sh    # skill-dir
# Claude plugin still via this catalog (ref v0.2.1, path ".")
```

## Pin policy

Normative release steps: skill-craft [`docs/skill-release-checklist.md`](https://github.com/whichguy/skill-craft/blob/main/docs/skill-release-checklist.md).  
Market-side notes: [docs/pin-policy.md](docs/pin-policy.md).

**Do not bulk-retarget** umbrella tags when leaf content is unchanged vs tip.

## Faces

Host notes under `faces/{grok,codex,hermes}/` point at the setup matrix. No second marketplace.json under faces.

## Layout

See [docs/package-layout.md](docs/package-layout.md).

## Improve release candidate

`improve@skill-craft-market` now resolves to `whichguy/until-loop`, pinned to
`v0.3.0-rc.3`. This supersedes the initial skill-craft catalog pin
`improve-v0.1.0-rc.1` without changing the installable plugin name. The previous
release remains available in Git history. Improve includes its compatible Until
Loop runtime; catalog discovery and isolated runtime tests do not establish full
execution on every host.

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

Start with `Dry-run $improve on these changes without writing files.` See the
[Improve guide](https://github.com/whichguy/until-loop/blob/v0.3.0-rc.3/examples/improve/README.md)
for scope, commit overrides, completion conditions and runtime boundaries.
The ClaudeCraft skill with the same name is a separate implementation.
