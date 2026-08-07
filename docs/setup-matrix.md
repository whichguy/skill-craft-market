# Setup matrix — skills, plugins, policy

## Portable skills (L-Skill)

| Want | Claude | Grok | Codex | Hermes |
|------|--------|------|-------|--------|
| **install skill** (default portable) | `cd skill-craft && ./install.sh --skill <leaf> --claude-only` | `… --grok-only` | `… --codex-only` | `… --hermes-only` |
| All hosts skill-dir | `./install.sh --skill <leaf>` (no host flag = all four) | same | same | same |
| **install plugin** (pinned catalog) | `claude plugin install <leaf>@skill-craft-market` | `grok plugin …` if source registered — **lifecycle pilot**; prefer skill-dir until proven | `codex plugin …` if catalog added — **lifecycle pilot**; prefer skill-dir until proven | N/A — skill-dir only |
| Health | `./install.sh --status --skill <leaf>` (**skill-dir only**) | same | same | same |

**Rule:** one track per leaf on a machine. Do not run plugin + skill-dir for the same name without debugging.

## Suites (L-Suite)

| Want | Claude | Others |
|------|--------|--------|
| review-suite, planning-suite, wiki-suite, … | **claude-craft** marketplace | N/A (or skill-craft port if a portable leaf exists, e.g. c-plan) |

## Policy hooks (L-Policy)

| Want | Claude | Grok | Codex | Hermes |
|------|--------|------|-------|--------|
| ExitPlanMode soft_exit / residual skill fire | plan-oversight → settings.json | import via `[compat.claude] hooks=true` | `hooks.json` Stop → codex_stop only | N/A |
| Install hooks via skill-craft-market? | **Never** | **Never** | **Never** | — |
| Install hooks via install.sh? | **Never** | **Never** | **Never** | — |

## Companions (L-Companion)

| Host | Market |
|------|--------|
| Grok↔Claude bridge | grok-plugin-claude-code / xAI official |
| Codex companion | openai-codex plugin market |
