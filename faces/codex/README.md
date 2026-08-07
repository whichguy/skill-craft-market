# Codex face — skill-craft-market

**No second marketplace.json here.** Root catalog is Claude-format only; Codex consumes skills via **skill-dir**.

## install skill (recommended)

```sh
git clone https://github.com/whichguy/skill-craft.git
cd skill-craft
./install.sh --skill review-coverage --codex-only
./install.sh --status --skill review-coverage
```

Destination: `~/.codex/skills/<leaf>` → skill-craft `skills/<leaf>`.

## install plugin

Lifecycle pilot only. Prefer skill-dir until proven. Full matrix: [docs/setup-matrix.md](../../docs/setup-matrix.md).

## register policy

Codex Stop contract: **plan-oversight** `register-hooks` → `~/.codex/hooks.json` — never this catalog.

## Standalone: lennox-s40

Thermostat body: [whichguy/lennox-s40](https://github.com/whichguy/lennox-s40).

```sh
cd ~/src/lennox-s40 && ./install.sh
```
