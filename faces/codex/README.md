# Codex face — skill-craft-market

## Recommended: skill-dir install from skill-craft

```sh
git clone https://github.com/whichguy/skill-craft.git
cd skill-craft
./install.sh --skill skill-interop --codex-only
```

Destination: `~/.codex/skills/skill-interop` → skill-craft `skills/skill-interop`.

## Plugin marketplace

Codex plugin CLIs (when used) take host-specific marketplace/plugin commands. Skill
packages are not required to be packaged as Codex plugins; skill-dir install is the
portable path.

Skill SoT: [whichguy/skill-craft](https://github.com/whichguy/skill-craft)  
skill-dir path: `skills/skill-interop` (not the Claude pin path `plugins/skill-interop`).

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
