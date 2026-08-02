# Grok face — skill-craft-market

Grok does not use Claude-style `name@marketplace` plugin ids for skill packages.

## Recommended: skill-dir install from skill-craft

```sh
git clone https://github.com/whichguy/skill-craft.git
cd skill-craft
./install.sh --skill skill-interop --grok-only
# optional thin agent card:
./install.sh --skill skill-interop --grok-only --agents
```

Destination: `~/.grok/skills/skill-interop` → skill-craft `skills/skill-interop`.

## Plugin marketplace

If installing a **plugin** (not a skill package) via Grok’s plugin CLI, use git URL /
`user/repo` forms — not `name@marketplace`. Skill SoT remains
[whichguy/skill-craft](https://github.com/whichguy/skill-craft).

This face holds **docs only** (no skill prompt bodies).

## Multi-skill monorepo

skill-craft now ships multiple portable skills (skill-interop, c-plan, prompt-*,
architect, plan-test, compare-prompts, lennox-s40, …). Skill-dir install:

```sh
cd skill-craft && ./install.sh          # all skills
cd skill-craft && ./install.sh --skill architect
```

Claude plugin catalog: sibling marketplace pins under `plugins/<leaf>` @ release tags.

## Standalone: lennox-s40

Thermostat skill: [whichguy/lennox-s40](https://github.com/whichguy/lennox-s40). `cd ~/src/lennox-s40 && ./install.sh`.

## devloop-run

Setup/probe multi-host; full engine loops still default to Hermes transport.

```sh
cd skill-craft && ./install.sh --skill devloop-run --grok-only   # or --codex-only
bash ~/.grok/skills/devloop-run/scripts/devloop-run --setup
```
