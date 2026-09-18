# Pin policy (market-side)

**Normative checklist** (who tags and when):  
https://github.com/whichguy/skill-craft/blob/main/docs/skill-release-checklist.md

## Market rules

1. Every entry requires a full 40-character `source.sha`. Catalog `version` must equal `plugin.json` `version` **at that pinned SHA**; `ref` is an optional release or branch label.
2. `source.path` for skill-craft pins is `plugins/<leaf>` (not bare `skills/`).
3. Advance a pin only when that leaf’s content (or package version) changes at a released tag or verified published commit — **not** because an umbrella tag number moved.
4. **No bulk retarget** of content-identical pins (advisory only).
5. External pins (e.g. lennox-s40) use their own repo URL/tag scheme; monorepo must not also ship the same leaf name.
6. Catalog entries must never include a `hooks` key.

## CI

`pin-freshness.yml` runs the offline catalog and ownership checks, hermetic tests,
and `scripts/check-pins.py`. The remote verifier checks ref reachability when
present, and reads the manifest and advertised skill body at the immutable SHA.
Package name/version mismatches and hooks fail validation; description drift is
advisory. Run the script locally with `GH_TOKEN` in the environment when private
source access is needed.

On every pull request and push, CI also runs
`python3 scripts/check-release-payload.py --base <base-sha>` against the
merge-base catalog. It applies the complete-payload check only to new or changed
entries from the explicit release-payload allowlist: `whichguy/skill-craft`,
`whichguy/workflow-engine`, and `whichguy/backchain`. Unchanged legacy entries are not silently upgraded
to that stronger contract. Removals are reported without payload verification.
A same-name change from the native Skill Craft source to an external source
fails: it requires separately qualified migration review and cannot use a
catalog edit to evade the native release gate. Missing base commits or malformed
base/current catalogs fail visibly.

Backchain 0.3.5 is explicitly qualified as a two-skill root package containing
Backchain and Plan Dispatcher. Its secondary card and bundled dispatcher helper
are required; this exception does not permit extra cards in other packages.

For a new marketplace-readiness release candidate, additionally run
`python3 scripts/check-pins.py --full-payload` (or select **full_payload** in the
manual pin-freshness workflow). This opt-in migration gate verifies the complete
pinned Git tree, packaged LICENSE/README, advertised skill and script payload,
and the required Codex adapter's identity/layout for repositories in that
allowlist. Truncated trees, symlinks and submodules fail rather than pretending
their targets are bundled. Legacy pins may fail this stronger gate until
republished; the default check explicitly reports `payload=not-checked` and
does not imply payload readiness. This gate still does not execute a skill or
prove host/model behavior.

The verifier covers the catalog's current default skill layout:
`<package root>/skills/<manifest name>/SKILL.md`. Explicit manifest `skills`
declarations require extending the verifier with a tested path contract first;
an unsupported declaration fails visibly instead of guessing its location.

## Immutable commit pins

Every entry records its commit SHA, including tagged releases. A package already
shipped on the source repository's `main` branch may use
`ref: "main"` plus a full 40-character `sha` when no release tag contains the
current package. The SHA fixes the package bytes; moving `main` does not advance
that pin. Validate the manifest and version at the SHA and prove the commit is
reachable from the declared ref. Prefer a release tag when one exists. Advance
only changed leaves. This avoids creating a new source release during a catalog
repair and does not claim that untagged changes are a tagged release.

Root-repository sources use `source: "url"` and omit `path`. `git-subdir` is for
non-root paths such as `plugins/shiploop`; Codex silently omits `path: "."`.
The single Claude-compatible catalog includes Codex's `interface.displayName`
and explicit per-entry policy/category; Claude ignores Codex-specific fields.

The current remote verifier supports GitHub HTTPS repository URLs; the local
validator rejects other providers until their verification path is implemented.

## Private source access

`whichguy/backchain` is private. Installing that entry requires GitHub access to
that repository. This catalog does not grant access or change visibility. Public
users can install the other entries only if they can read their source repositories.
The remote CI check uses the optional `MARKETPLACE_READ_TOKEN` Actions secret,
falling back to the workflow token. For a private cross-repository source, configure
a token with read access to that source; the default workflow token cannot grant
that access. No credential is stored in this repository. A 404 from the contents
API can indicate missing access as well as a missing file, and validation fails
rather than silently skipping that entry.
