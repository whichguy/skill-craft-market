# skill-craft-market

Multi-host **marketplace adapters** for [skill-craft](https://github.com/whichguy/skill-craft).

- **skill-craft** = skill bodies (SoT)
- **skill-craft-market** = catalogs / attach docs only

No single marketplace format is shared by Claude/Grok/Codex/Hermes. Shared unit is agentskills packages.

## Claude

```bash
claude plugin marketplace add whichguy/skill-craft-market
claude plugin install skill-interop@skill-craft-market
```

Root `.claude-plugin/marketplace.json` lists pins into `whichguy/skill-craft`.

## Grok / Codex / Hermes

See `faces/*/README.md`. Prefer skill-dir install from skill-craft for Grok/Codex; Hermes via HSM snapshots.

## License

MIT
