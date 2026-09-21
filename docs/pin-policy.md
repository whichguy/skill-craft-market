# Pin policy (market-side)

**Normative checklist** (who tags and when):  
https://github.com/whichguy/skill-craft/blob/main/docs/skill-release-checklist.md

## Market rules

1. Every entry except the coordinated workflow set requires a full 40-character `source.sha`. Catalog `version` must equal `plugin.json` `version` at that pinned SHA; `ref` is an optional release or branch label.
2. `ask-agent`, `shiploop`, `improve`, and `backchain` deliberately use `source.ref: "main"` and omit `source.sha`. Their strict SemVer 2 package versions remain required catalog and source metadata, and give host caches an update/reinstall signal; they do not pin or gate the branch content selected from `main`. Build metadata follows SemVer's rule that numeric identifiers may retain leading zeroes.
3. `source.path` for skill-craft packages is `plugins/<leaf>` (not bare `skills/`). Backchain is a root `source: "url"` package and has no `path`.
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
Run the script locally with `GH_TOKEN` in the environment when private source
access is needed.

On every pull request and push, CI also runs
`python3 scripts/check-release-payload.py --base <base-sha>` against the
merge-base catalog. It applies the complete-payload check to new or changed
entries from the explicit release-payload allowlist: `whichguy/skill-craft`,
`whichguy/workflow-engine`, and `whichguy/backchain`; the four rolling entries
are selected on every invocation because their ref can advance without a catalog
diff. Unchanged legacy entries are not silently upgraded to that stronger
contract. Removals are reported without payload verification.
A same-name change from the native Skill Craft source to an external source
fails: it requires separately qualified migration review and cannot use a
catalog edit to evade the native release gate. Missing base commits or malformed
base/current catalogs fail visibly.

Backchain is explicitly qualified as a two-skill root package containing
Backchain and Plan Dispatcher. Its secondary card must retain the
`plan-dispatcher` identity, a semantic metadata version, script-backed kind, and
bundled dispatcher helper. Static historical pins retain their original paired
version check; the rolling entry validates this semantic contract so future
released versions do not require checker edits merely to advance a number.

For a new marketplace-readiness release candidate, additionally run
`python3 scripts/check-pins.py --full-payload` (or select **full_payload** in the
manual pin-freshness workflow). This opt-in migration gate verifies the complete
resolved Git tree, packaged LICENSE/README, advertised skill and script payload,
and the required Codex adapter's identity/layout for repositories in that
allowlist. The rolling entries always receive this complete-payload validation,
even without the flag. Truncated trees, symlinks and submodules fail rather than
pretending their targets are bundled. Legacy pins may fail the opt-in stronger
gate until republished; a default `payload=not-checked` for those legacy entries
does not imply payload readiness. This gate still does not execute a skill or
prove host/model behavior.

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
