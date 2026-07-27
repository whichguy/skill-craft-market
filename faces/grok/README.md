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
