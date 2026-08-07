# Claude face — skill-craft-market

The **only** committed plugin catalog is the repo root:

`.claude-plugin/marketplace.json`

Do not re-add a second marketplace.json under `faces/claude/`.

```sh
claude plugin marketplace add whichguy/skill-craft-market
claude plugin install <leaf>@skill-craft-market
```

Or skill-dir: skill-craft `./install.sh --skill <leaf> --claude-only`.

**No hooks** from this catalog. Full matrix: [docs/setup-matrix.md](../../docs/setup-matrix.md).
