# Pin policy (market-side)

**Normative checklist** (who tags and when):  
https://github.com/whichguy/skill-craft/blob/main/docs/skill-release-checklist.md

## Market rules

1. Catalog `version` must equal `plugin.json` `version` **at the pinned ref**.
2. `source.path` for skill-craft pins is `plugins/<leaf>` (not bare `skills/`).
3. Advance a pin only when that leaf’s content (or package version) changes at a released tag — **not** because an umbrella tag number moved.
4. **No bulk retarget** of content-identical pins (advisory only).
5. External pins (e.g. lennox-s40) use their own repo URL/tag scheme; monorepo must not also ship the same leaf name.
6. Catalog entries must never include a `hooks` key.

## CI

`pin-freshness.yml`: ref resolves + plugin.json at path + version equality (+ optional content-drift advisory).
