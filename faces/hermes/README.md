# Hermes face — skill-craft-market

Hermes uses skillhub / software-development skill-dir layout (not Claude plugin marketplaces).

## Recommended: skill-dir install from skill-craft

```sh
git clone https://github.com/whichguy/skill-craft.git
cd skill-craft
./install.sh --skill skill-interop --hermes-only
```

Destination (host):

`~/.hermes/skills/software-development/skill-interop`

When `~/.hermes` is bind-mounted into the Hermes container at `/opt/data`, the container path is:

`/opt/data/skills/software-development/skill-interop`

Skill SoT: [whichguy/skill-craft](https://github.com/whichguy/skill-craft)  
skill-dir path: `skills/skill-interop` (not the Claude pin path `plugins/skill-interop`).

This face holds **docs only** (no skill prompt bodies). Hermes is not covered by the
skill-interop marketplace facade CLI (skill-dir only).

## Multi-skill monorepo

skill-craft now ships multiple portable skills (skill-interop, c-plan, prompt-*,
architect, plan-test, compare-prompts, …). Skill-dir install:

```sh
cd skill-craft && ./install.sh          # all skills
cd skill-craft && ./install.sh --skill architect
```

Claude plugin catalog: sibling marketplace pins under `plugins/<leaf>` @ release tags.
