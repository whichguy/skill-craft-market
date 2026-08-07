# Hermes face — skill-craft-market

**No second marketplace.json here.** Hermes is skill-dir only (skillhub / software-development layout).

## install skill (only path)

```sh
git clone https://github.com/whichguy/skill-craft.git
cd skill-craft
./install.sh --skill review-coverage --hermes-only
./install.sh --status --skill review-coverage
```

Host path: `~/.hermes/skills/software-development/<leaf>`  
Container (when `~/.hermes` is bind-mounted at `/opt/data`):  
`/opt/data/skills/software-development/<leaf>`

## install plugin

N/A for Hermes.

## register policy

N/A — plan-oversight harness adapters target Claude/Grok/Codex.

## Standalone: lennox-s40

Thermostat body: [whichguy/lennox-s40](https://github.com/whichguy/lennox-s40).

```sh
cd ~/src/lennox-s40 && ./install.sh
```
