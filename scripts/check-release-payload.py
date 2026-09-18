#!/usr/bin/env python3
"""Strictly verify changed release payloads from qualified catalog sources."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Sequence, TextIO
from urllib.parse import urlparse


CATALOG_RELATIVE = Path(".claude-plugin/marketplace.json")
NATIVE_REPOSITORY = "whichguy/skill-craft"
WORKFLOW_ENGINE_REPOSITORY = "whichguy/workflow-engine"
# A changed catalog entry from these repositories is a release candidate, so
# CI must inspect its complete immutable payload. Other external entries keep
# their existing verification path until they are explicitly qualified here.
FULL_PAYLOAD_REPOSITORIES = frozenset(
    (NATIVE_REPOSITORY, WORKFLOW_ENGINE_REPOSITORY)
)


class GateError(RuntimeError):
    """A local release-diff precondition was not met."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        required=True,
        help="commit or ref whose merge-base with HEAD supplies the prior catalog",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="GitHub request timeout passed to check-pins.py (default: 60)",
    )
    return parser.parse_args(argv)


def base_argument_starts_with_dash(argv: Sequence[str]) -> bool:
    """Catch a dash-prefixed value before argparse treats it as another option."""
    for index, argument in enumerate(argv):
        if argument.startswith("--base="):
            return argument.removeprefix("--base=").startswith("-")
        if argument == "--base" and index + 1 < len(argv):
            return argv[index + 1].startswith("-")
    return False


def canonical_json(value: Any) -> str:
    """Compare parsed JSON independent of source formatting and key order."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def repository_identity(entry: dict[str, Any]) -> str | None:
    """Return the normalized GitHub repository identity for a catalog entry."""
    source = entry.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("url"), str):
        return None
    parsed = urlparse(source["url"])
    if parsed.scheme.casefold() != "https" or parsed.netloc.casefold() != "github.com":
        return None
    path = parsed.path.strip("/").casefold().removesuffix(".git")
    return path or None


def native_skill_craft_entry(entry: dict[str, Any]) -> bool:
    """Return whether an entry points to the canonical Skill Craft repository."""
    return repository_identity(entry) == NATIVE_REPOSITORY


def full_payload_entry(entry: dict[str, Any]) -> bool:
    """Return whether an entry is covered by the strict release-payload gate."""
    return repository_identity(entry) in FULL_PAYLOAD_REPOSITORIES


def entries_by_name(data: Any, label: str) -> dict[str, dict[str, Any]]:
    """Validate the diff-relevant catalog shape and index entries by name."""
    if not isinstance(data, dict):
        raise GateError(f"{label} catalog must be a JSON object")
    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        raise GateError(f"{label} catalog plugins must be a non-empty array")

    entries: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(plugins):
        if not isinstance(entry, dict):
            raise GateError(f"{label} catalog plugins[{index}] must be an object")
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise GateError(f"{label} catalog plugins[{index}] requires a non-empty name")
        if name in entries:
            raise GateError(f"{label} catalog has duplicate plugin name {name!r}")
        entries[name] = entry
    return entries


def parse_catalog(text: str, label: str) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GateError(f"{label} catalog is malformed JSON: {exc}") from exc
    return entries_by_name(data, label)


def git_output(repo: Path, args: Sequence[str], action: str) -> str:
    git = os.environ.get("GIT", "git")
    try:
        result = subprocess.run(
            [git, "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise GateError(f"cannot {action}: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
        raise GateError(f"cannot {action}: {detail}")
    return result.stdout


def base_catalog(repo: Path, base: str) -> dict[str, dict[str, Any]]:
    base = base.strip()
    if not base:
        raise GateError("--base must name a commit or ref")
    if base.startswith("-"):
        raise GateError("--base must not begin with '-'")
    resolved_base = git_output(
        repo,
        ["rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}"],
        f"resolve merge-base input --base {base!r}",
    ).strip()
    if not resolved_base:
        raise GateError(f"cannot resolve merge-base input --base {base!r}")
    merge_base = git_output(
        repo,
        ["merge-base", resolved_base, "HEAD"],
        f"resolve merge-base for --base {base!r} and HEAD",
    ).strip()
    if not merge_base:
        raise GateError(f"cannot resolve merge-base for --base {base!r} and HEAD")
    text = git_output(
        repo,
        ["show", f"{merge_base}:{CATALOG_RELATIVE.as_posix()}"],
        f"read base catalog at merge-base {merge_base}",
    )
    return parse_catalog(text, "base")


def current_catalog(repo: Path) -> dict[str, dict[str, Any]]:
    path = repo / CATALOG_RELATIVE
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GateError(f"current catalog is missing: {path}") from exc
    except OSError as exc:
        raise GateError(f"cannot read current catalog {path}: {exc}") from exc
    return parse_catalog(text, "current")


def load_check_pins(repo: Path) -> ModuleType:
    """Load the sibling checker without relying on an importable package layout."""
    path = repo / "scripts" / "check-pins.py"
    spec = importlib.util.spec_from_file_location("check_pins", path)
    if spec is None or spec.loader is None:
        raise GateError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_gate(
    *,
    repo: Path,
    base: str,
    timeout: int,
    check_pins_module: ModuleType | Any | None = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Compare catalogs and full-verify changed/new qualified packages."""
    prior = base_catalog(repo, base)
    current = current_catalog(repo)

    migrations = sorted(
        name
        for name, old_entry in prior.items()
        if name in current
        and native_skill_craft_entry(old_entry)
        and not native_skill_craft_entry(current[name])
    )
    if migrations:
        for name in migrations:
            print(
                "FAIL "
                f"{name}: native Skill Craft source migration requires separate qualification; "
                "the release-payload gate will not downgrade it to an external source",
                file=stderr,
            )
        return 1

    for name in sorted(set(prior) - set(current)):
        print(f"REMOVAL {name}: reported only; no payload verification requested", file=stdout)

    selected = [
        current[name]
        for name in sorted(current)
        if full_payload_entry(current[name])
        and (name not in prior or canonical_json(current[name]) != canonical_json(prior[name]))
    ]
    if not selected:
        print("release-payload: no changed or new full-payload-gated entries", file=stdout)
        return 0

    module = check_pins_module or load_check_pins(repo)
    try:
        transport = module.GitHubTransport(os.environ.get("GH_TOKEN", ""), timeout)
        failures, advisories = module.verify_catalog(
            {"plugins": selected},
            transport,
            stdout=stdout,
            stderr=stderr,
            full_payload=True,
        )
    except Exception as exc:
        print(f"FAIL release-payload: strict verification could not run: {exc}", file=stderr)
        return 1
    if failures:
        print(
            f"release-payload: {failures} strict failure(s), {advisories} advisory(ies)",
            file=stderr,
        )
        return 1
    print(
        f"release-payload: strict payload verification passed for {len(selected)} "
        f"changed/new full-payload-gated entr{'y' if len(selected) == 1 else 'ies'} "
        f"({advisories} advisory(ies))",
        file=stdout,
    )
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    repo: Path | None = None,
    check_pins_module: ModuleType | Any | None = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    command = list(sys.argv[1:] if argv is None else argv)
    if base_argument_starts_with_dash(command):
        print("FAIL release-payload: --base must not begin with '-'", file=stderr)
        return 1
    args = parse_args(command)
    if args.timeout <= 0:
        print("FAIL release-payload: timeout must be positive", file=stderr)
        return 1
    root = (repo or Path(__file__).resolve().parents[1]).resolve()
    try:
        return run_gate(
            repo=root,
            base=args.base,
            timeout=args.timeout,
            check_pins_module=check_pins_module,
            stdout=stdout,
            stderr=stderr,
        )
    except GateError as exc:
        print(f"FAIL release-payload: {exc}", file=stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
