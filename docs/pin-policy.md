# Pin policy (market-side)

**Normative checklist** (who tags and when):  
https://github.com/whichguy/skill-craft/blob/main/docs/skill-release-checklist.md

## Market rules

1. Every entry except the coordinated workflow set requires a full 40-character `source.sha`. Catalog `version` must equal `plugin.json` `version` at that pinned SHA; `ref` is an optional release or branch label.
2. `ask-agent`, `shiploop`, `improve`, and `backchain` deliberately use `source.ref: "main"` and omit `source.sha`. Their strict SemVer 2 package versions remain required catalog and source metadata, and give host caches an update/reinstall signal; they do not pin or gate the branch content selected from `main`. Build metadata follows SemVer's rule that numeric identifiers may retain leading zeroes.
3. `source.path` for skill-craft packages is `plugins/<leaf>` (not bare `skills/`), including the vendored Backchain bundle at `plugins/backchain`.
4. The rolling set is closed by the local validator. A catalog edit cannot make another package floating, pin a member of the set, redirect it, or move it off `main`.
5. Immutable entries advance only when that leaf’s content (or package version) changes at a released tag or verified published commit — not because an umbrella tag number moved. **No bulk retarget** of content-identical pins (advisory only).
6. External pins (e.g. lennox-s40) use their own repo URL/tag scheme; monorepo must not also ship the same leaf name.
7. Catalog entries must never include a `hooks` key.

## CI

`pin-freshness.yml` runs the offline catalog and ownership checks, hermetic tests,
and `scripts/check-pins.py`. Immutable entries retain ref-reachability and
immutable-byte validation. For each rolling `(repository, main)` pair, the remote
verifier resolves `main` once, records the exact returned SHA, and fetches the
manifest, card, helper payload, and complete tree only at that SHA. A ref move
during validation therefore cannot mix bytes from two revisions. Package
name/version mismatches and hooks fail validation; description drift is advisory.

There is one validation tier. Every run of `scripts/check-pins.py` applies the
complete-payload check to every rolling entry and to every immutable entry from
`FULL_PAYLOAD_REPOSITORIES` (`whichguy/skill-craft` and
`whichguy/workflow-engine`, defined once in `check-pins.py`): the complete
resolved Git tree, packaged LICENSE/README, the advertised skill and its
declared script entrypoints, and the required Codex adapter's identity/layout.
Truncated trees, symlinks and submodules fail rather than pretending their
targets are bundled. External pins from other repositories (lennox-s40,
until-loop) report `payload=not-checked`; they keep ref, manifest and skill-body
validation. The payload check does not execute a skill or prove host/model
behavior.

No entry requires private access. `GH_TOKEN` is optional: set it only to avoid
GitHub's anonymous API limit (60 requests per hour), which a full local
`check-pins.py` run can exceed.

On every pull request and push, CI also runs
`python3 scripts/check-release-payload.py --base <base-sha>` against the
merge-base catalog. It selects new or changed entries from
`FULL_PAYLOAD_REPOSITORIES` (the same constant `check-pins.py` uses) and runs
the same verifier on them; the four rolling entries are selected on every
invocation because their ref can advance without a catalog diff. Removals are
reported without payload verification.
A same-name change from the native Skill Craft source to an external source
fails: it requires separately qualified migration review and cannot use a
catalog edit to evade the native release gate. Missing base commits or malformed
base/current catalogs fail visibly.

Backchain is explicitly qualified as a two-skill package, and only at
`whichguy/skill-craft` `plugins/backchain` (skill-craft's vendored bundle). Its
secondary card must retain the `plan-dispatcher` identity, a semantic metadata
version, script-backed kind, and bundled dispatcher helper. This semantic
contract means released versions do not require checker edits merely to advance
a number. The former private root location is no longer qualified.

The verifier covers the catalog's current default skill layout:
`<package root>/skills/<manifest name>/SKILL.md`. Explicit manifest `skills`
declarations require extending the verifier with a tested path contract first;
an unsupported declaration fails visibly instead of guessing its location.

## Immutable commit pins

All entries outside the coordinated workflow set record an immutable commit SHA,
including tagged releases. A package already shipped on the source repository's
`main` branch may use `ref: "main"` plus a full 40-character `sha` when no
release tag contains the current package. The SHA fixes the package bytes;
moving `main` does not advance that pin. Validate the manifest and version at
the SHA and prove the commit is reachable from the declared ref. Prefer a
release tag when one exists. This does not claim that untagged changes are a
tagged release.

## Rolling workflow releases

The coordinated workflow set follows each source repository's published `main`
branch. Its semantic package version is a compatibility and host-cache update
signal, not a SHA pin or branch-content gate: `main` can advance between version
bumps under this latest policy. Claude and Codex may cache installed plugins, so
a released version bump gives consumers a distinct marketplace refresh and
update/reinstall signal. Validation output records `source=floating`, `ref=main`,
and the resolved SHA for the exact bytes it inspected.

Root-repository sources use `source: "url"` and omit `path`. `git-subdir` is for
non-root paths such as `plugins/shiploop`; Codex silently omits `path: "."`.
The single Claude-compatible catalog includes Codex's `interface.displayName`
and explicit per-entry policy/category; Claude ignores Codex-specific fields.

The current remote verifier supports GitHub HTTPS repository URLs; the local
validator rejects other providers until their verification path is implemented.

## Source access

Every catalog source is public; install and CI need no credentials. Backchain's
development repository stays private, but this catalog selects its public,
provenance-verified copy in skill-craft (`plugins/backchain`). The remote CI
check still accepts the optional `MARKETPLACE_READ_TOKEN` Actions secret and
otherwise uses the workflow token. No credential is stored in this repository.
A 404 from the contents API fails validation rather than silently skipping an
entry.
