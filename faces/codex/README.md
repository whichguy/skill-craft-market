# Codex face — skill-craft-market

**No second marketplace.json here.** Codex supports the root Claude-compatible catalog. Choose marketplace plugins for released packages or **skill-dir** for development; use one track per leaf.

## install skill (recommended)

```sh
git clone https://github.com/whichguy/skill-craft.git
cd skill-craft
./install.sh --skill review-coverage --codex-only
./install.sh --status --skill review-coverage
```

Destination: `~/.codex/skills/<leaf>` → skill-craft `skills/<leaf>`.

## install plugin

```sh
codex plugin marketplace add whichguy/skill-craft-market
codex plugin list --marketplace skill-craft-market --available --json
codex plugin add shiploop@skill-craft-market
```

For a local checkout, pass its absolute root to `marketplace add` instead.
Open Plugins in the Codex app and select **Skill Craft**. Registration exposes
available packages without installing them. Start a new thread after installation.
Do not install a plugin for a leaf already exposed through skill-dir.

Full matrix: [docs/setup-matrix.md](../../docs/setup-matrix.md).

## register policy

Codex Stop contract: **plan-oversight** `register-hooks` → `~/.codex/hooks.json` — never this catalog.

## Standalone: lennox-s40

Thermostat body: [whichguy/lennox-s40](https://github.com/whichguy/lennox-s40).

```sh
cd ~/src/lennox-s40 && ./install.sh
```
