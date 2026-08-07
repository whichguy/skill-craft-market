# Grok face — skill-craft-market

**No second marketplace.json here.** Root catalog is Claude-format only; Grok consumes skills via **skill-dir**.

## install skill (recommended)

```sh
git clone https://github.com/whichguy/skill-craft.git
cd skill-craft
./install.sh --skill review-coverage --grok-only   # or omit --skill for all
./install.sh --status --skill review-coverage
```

Destination: `~/.grok/skills/<leaf>` → skill-craft `skills/<leaf>`.

## install plugin

Lifecycle pilot only. Prefer skill-dir until host plugin install is proven. Full matrix: [docs/setup-matrix.md](../../docs/setup-matrix.md).

## register policy

ExitPlanMode / residual hooks: **plan-oversight** `register-hooks` — never this catalog, never skill-craft `install.sh`.

## Standalone: lennox-s40

Thermostat body: [whichguy/lennox-s40](https://github.com/whichguy/lennox-s40).

```sh
cd ~/src/lennox-s40 && ./install.sh
```
