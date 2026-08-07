#!/usr/bin/env bash
# Doc-test: setup-matrix host flags ⊆ skill-craft install.sh --help (when sibling clone present).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
matrix="$root/docs/setup-matrix.md"
fail() { printf 'setup-matrix-flags.test.sh: FAIL %s\n' "$*" >&2; exit 1; }

[[ -f "$matrix" ]] || fail "missing $matrix"
rg -q 'Claude' "$matrix" || fail "matrix missing Claude"
rg -q 'Grok' "$matrix" || fail "matrix missing Grok"
rg -q 'Codex' "$matrix" || fail "matrix missing Codex"
rg -q 'Hermes' "$matrix" || fail "matrix missing Hermes"
rg -q 'install skill' "$matrix" || fail "matrix missing install skill"
rg -q 'install plugin' "$matrix" || fail "matrix missing install plugin"
rg -q 'register policy|plan-oversight' "$matrix" || fail "matrix missing policy"

# Optional sibling skill-craft: assert host flags appear in install.sh --help
skill_craft_candidates=(
  "${SKILL_CRAFT_ROOT:-}"
  "$root/../skill-craft"
  "$HOME/src/skill-craft"
)
install_sh=""
for c in "${skill_craft_candidates[@]}"; do
  [[ -n "$c" && -x "$c/install.sh" ]] || continue
  install_sh="$c/install.sh"
  break
done

if [[ -n "$install_sh" ]]; then
  help_out="$("$install_sh" --help 2>&1 || true)"
  for flag in --claude-only --grok-only --codex-only --hermes-only --status; do
    printf '%s\n' "$help_out" | grep -q -- "$flag" || fail "install.sh --help missing $flag"
  done
  # matrix documents these flag forms
  for flag in --claude-only --grok-only --codex-only --hermes-only; do
    rg -q -- "$flag" "$matrix" || fail "matrix missing $flag"
  done
  printf 'setup-matrix-flags.test.sh: sibling install.sh OK (%s)\n' "$install_sh"
else
  printf 'setup-matrix-flags.test.sh: skip install.sh cross-check (no sibling skill-craft)\n'
fi

# Catalog shape anchors (S2/S3-ish local)
mp="$root/.claude-plugin/marketplace.json"
[[ -f "$mp" ]] || fail "missing marketplace.json"
rg -q 'No hooks' "$mp" || fail "marketplace description must contain No hooks"
[[ ! -e "$root/faces/claude/.claude-plugin/marketplace.json" ]] || fail "dual faces/claude catalog must not exist"

printf 'setup-matrix-flags.test.sh: PASS\n'
