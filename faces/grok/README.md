# Grok face — skill-craft-market

**No second marketplace.json here.** For native Grok plugins, use the generated
`.grok-plugin/marketplace.json` in the **skill-craft source repository**. It points
to the 18 existing `plugins/<leaf>` packages using same-repository local sources.
This sibling repo retains the Claude/Codex release pins.

## install skill (recommended)

```sh
git clone https://github.com/whichguy/skill-craft.git
cd skill-craft
./install.sh --skill review-coverage --grok-only   # or omit --skill for all
./install.sh --status --skill review-coverage
```

Destination: `~/.grok/skills/<leaf>` → skill-craft `skills/<leaf>`.

## install plugin

For local development:

```sh
grok plugin marketplace add /absolute/path/to/skill-craft
grok plugin list --available --json
# Review the selected package; use plugin mode only if it is not in skill-dir:
grok plugin install shiploop --trust
```

After publishing the source adapter, consumers can register `whichguy/skill-craft`.
Full matrix: [docs/setup-matrix.md](../../docs/setup-matrix.md).

## register policy

ExitPlanMode / residual hooks: **plan-oversight** `register-hooks` — never this catalog, never skill-craft `install.sh`.

## Standalone: lennox-s40

Thermostat body: [whichguy/lennox-s40](https://github.com/whichguy/lennox-s40).

```sh
cd ~/src/lennox-s40 && ./install.sh
```
