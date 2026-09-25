# skill-craft-market (retired)

This repository is retired and archived. The marketplace now lives in
[whichguy/skill-craft](https://github.com/whichguy/skill-craft): its root
catalogs (`.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`,
`.grok-plugin/`, `.cursor-plugin/`) keep the marketplace name
`skill-craft-market`, so plugin IDs such as `shiploop@skill-craft-market` are
unchanged. Plugins published from other repositories are pinned in
`catalog/external-plugins.json` there.

Re-point an existing registration:

- Claude Code: `claude plugin marketplace add whichguy/skill-craft` (run it over
  the existing registration; do not remove the old one first, which uninstalls
  its plugins). If your settings declare the old source under
  `extraKnownMarketplaces`, change it to GitHub `whichguy/skill-craft` first.
- Codex: `codex plugin marketplace remove skill-craft-market`, then
  `codex plugin marketplace add whichguy/skill-craft`.
- Grok and Cursor: register `whichguy/skill-craft`.

See [Install and distribute Skill Craft](https://github.com/whichguy/skill-craft/blob/main/docs/distribution.md).
