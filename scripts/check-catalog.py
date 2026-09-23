#!/usr/bin/env python3
"""Validate the catalog's local marketplace contract without network access."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SHA = re.compile(r"^[0-9a-fA-F]{40}$")
# Strict SemVer 2.0.0: numeric prerelease identifiers cannot lead with zero;
# build-metadata identifiers may.
SEMVER = re.compile(
    r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-(?:(?:0|[1-9][0-9]*)|(?:[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))"
    r"(?:\.(?:(?:0|[1-9][0-9]*)|(?:[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
SKILL_CRAFT_URL = "https://github.com/whichguy/skill-craft.git"

# These four packages are released as one coordinated workflow surface. They
# deliberately follow skill-craft's published main branch rather than retaining
# an immutable catalog SHA. Backchain is skill-craft's vendored plugin bundle
# (bundles/backchain -> plugins/backchain); its development repository stays
# private. Keep this allowlist small: every other catalog entry remains an
# immutable pin.
ROLLING_LATEST_SOURCES: dict[str, tuple[str, str, str | None]] = {
    "ask-agent": ("git-subdir", SKILL_CRAFT_URL, "plugins/ask-agent"),
    "shiploop": ("git-subdir", SKILL_CRAFT_URL, "plugins/shiploop"),
    "improve": ("git-subdir", SKILL_CRAFT_URL, "plugins/improve"),
    "backchain": ("git-subdir", SKILL_CRAFT_URL, "plugins/backchain"),
}


def is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_skill_craft_url(value: Any) -> bool:
    """Return whether value identifies the canonical skill-craft repository.

    Catalog URLs are constrained to GitHub HTTPS URLs, so compare the parsed
    repository identity instead of accepting a suffix that an unrelated host
    could share.
    """
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.query
        or parsed.fragment
    ):
        return False
    normalized_path = parsed.path.strip("/").removesuffix(".git").casefold()
    return normalized_path == "whichguy/skill-craft"


def valid_subdir(value: Any) -> bool:
    if not is_text(value) or "\\" in value or value.startswith("/"):
        return False
    return all(part not in ("", ".", "..") for part in value.split("/"))


def rolling_latest_errors(name: Any, source: dict[str, Any]) -> list[str]:
    """Return policy errors for one explicitly allowed rolling-latest entry."""
    if not isinstance(name, str):
        return []
    expected = ROLLING_LATEST_SOURCES.get(name)
    if expected is None:
        return []
    source_type, url, path = expected
    errors: list[str] = []
    if source.get("source") != source_type:
        errors.append(f"rolling-latest {name} must use source.source {source_type!r}")
    if source.get("url") != url:
        errors.append(f"rolling-latest {name} must use source.url {url!r}")
    if path is None:
        if "path" in source:
            errors.append(f"rolling-latest {name} must not define source.path")
    elif source.get("path") != path:
        errors.append(f"rolling-latest {name} must use source.path {path!r}")
    if source.get("ref") != "main":
        errors.append(f"rolling-latest {name} must use source.ref 'main'")
    if "sha" in source:
        errors.append(f"rolling-latest {name} must omit source.sha")
    return errors


def catalog_root(catalog: Path) -> Path | None:
    if catalog.name == "marketplace.json" and catalog.parent.name == ".claude-plugin":
        return catalog.parent.parent
    return None


def content_candidates(root: Path) -> tuple[list[Path], list[str]]:
    """Return repository content while respecting its ignore rules when available."""
    if (root / ".git").exists():
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "ls-files",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                    "-z",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            return [], [f"{root}: unable to enumerate repository content with git ls-files: {exc}"]
        if result.returncode != 0:
            detail = result.stderr.strip() or f"exit status {result.returncode}"
            return [], [f"{root}: unable to enumerate repository content with git ls-files: {detail}"]

        candidates: list[Path] = []
        seen: set[str] = set()
        for value in result.stdout.split("\0"):
            if not value or value in seen:
                continue
            seen.add(value)
            relative = Path(value)
            if relative.is_absolute() or ".." in relative.parts:
                return [], [f"{root}: git ls-files returned an unsafe path {value!r}"]
            candidate = root / relative
            if candidate.is_file():
                candidates.append(candidate)
        return candidates, []

    return [
        candidate
        for candidate in root.rglob("*")
        if candidate.is_file() and ".git" not in candidate.relative_to(root).parts
    ], []


def validate_catalog(data: Any, catalog: Path) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    entries: list[dict[str, Any]] = []
    if not isinstance(data, dict):
        return [f"{catalog}: catalog must be a JSON object"], entries

    if not is_text(data.get("name")):
        errors.append(f"{catalog}: missing catalog name")
    if not is_text(data.get("description")):
        errors.append(f"{catalog}: missing catalog description")
    interface = data.get("interface")
    if not isinstance(interface, dict) or not is_text(interface.get("displayName")):
        errors.append(f"{catalog}: interface.displayName is required")
    if "hooks" in data:
        errors.append(f"{catalog}: catalog must not define hooks")

    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        errors.append(f"{catalog}: plugins must be a non-empty array")
        plugins = []

    seen: dict[str, int] = {}
    for index, plugin in enumerate(plugins):
        where = f"{catalog}: plugins[{index}]"
        if not isinstance(plugin, dict):
            errors.append(f"{where}: entry must be an object")
            continue
        entries.append(plugin)
        name = plugin.get("name")
        if not is_text(name) or not NAME.fullmatch(name):
            errors.append(f"{where}: name must be a lowercase hyphenated identifier")
        else:
            key = name.casefold()
            if key in seen:
                errors.append(f"{where}: duplicate plugin name {name!r} (also plugins[{seen[key]}])")
            else:
                seen[key] = index
        if not is_text(plugin.get("description")):
            errors.append(f"{where}: missing description")
        if not is_text(plugin.get("version")):
            errors.append(f"{where}: missing version")
        if "hooks" in plugin:
            errors.append(f"{where}: plugin entry must not define hooks")

        policy = plugin.get("policy")
        if not isinstance(policy, dict):
            errors.append(f"{where}: missing policy")
        else:
            if policy.get("installation") != "AVAILABLE":
                errors.append(f"{where}: policy.installation must be AVAILABLE")
            if policy.get("authentication") != "ON_INSTALL":
                errors.append(f"{where}: policy.authentication must be ON_INSTALL")
        if not is_text(plugin.get("category")):
            errors.append(f"{where}: missing category")

        source = plugin.get("source")
        if not isinstance(source, dict):
            errors.append(f"{where}: missing source object")
            continue
        source_type = source.get("source")
        if source_type not in ("git-subdir", "url"):
            errors.append(f"{where}: source.source must be git-subdir or url")
        if not is_text(source.get("url")):
            errors.append(f"{where}: source.url is required")
        else:
            parsed = urlparse(source["url"])
            if parsed.scheme != "https" or parsed.netloc != "github.com" or len(parsed.path.strip("/").split("/")) != 2 or parsed.query or parsed.fragment:
                errors.append(f"{where}: source.url must be a GitHub HTTPS repository URL")
        rolling_latest = isinstance(name, str) and name in ROLLING_LATEST_SOURCES
        version = plugin.get("version")
        if rolling_latest and (
            not is_text(version) or not SEMVER.fullmatch(version)
        ):
            errors.append(f"{where}: rolling-latest version must be a semantic version")
        rolling_errors = rolling_latest_errors(name, source)
        errors.extend(f"{where}: {error}" for error in rolling_errors)
        if not rolling_latest:
            sha = source.get("sha")
            if not is_text(sha) or not SHA.fullmatch(sha):
                errors.append(f"{where}: source.sha must be a full 40-character commit id")
        ref = source.get("ref")
        if "ref" in source and not is_text(ref):
            errors.append(f"{where}: source.ref must be a non-empty string when present")

        path = source.get("path")
        if source_type == "git-subdir":
            if not valid_subdir(path):
                errors.append(
                    f"{where}: git-subdir source.path must be a confined non-root path"
                )
            elif is_skill_craft_url(source.get("url")) and is_text(name):
                expected = f"plugins/{name}"
                if path != expected:
                    errors.append(
                        f"{where}: skill-craft source.path must be {expected!r}, got {path!r}"
                    )
        elif source_type == "url":
            if "path" in source:
                errors.append(f"{where}: root url source must not define source.path")
            if is_skill_craft_url(source.get("url")):
                errors.append(
                    f"{where}: skill-craft entries must use git-subdir plugins/{name}"
                )

    root = catalog_root(catalog)
    if root is None:
        errors.append(f"{catalog}: catalog must be root .claude-plugin/marketplace.json")
    else:
        candidates, candidate_errors = content_candidates(root)
        errors.extend(candidate_errors)
        if not candidate_errors:
            for candidate in candidates:
                if candidate.name == "marketplace.json" and candidate.resolve() != catalog.resolve():
                    errors.append(f"{candidate}: duplicate catalog; root catalog is the only allowed catalog")
            if "catalog only" in str(data.get("description", "")).casefold():
                for candidate in candidates:
                    if candidate.name == "SKILL.md":
                        errors.append(
                            f"{candidate}: catalog-only repository must not vendor skill prompt bodies"
                        )
    return errors, entries


def validate_coverage(entries: list[dict[str, Any]], skill_craft_root: Path) -> list[str]:
    errors: list[str] = []
    skills = skill_craft_root / "skills"
    if not skills.is_dir():
        return [f"coverage: skill-craft source is missing skills directory {skills}"]
    leaf_names = {path.parent.name for path in skills.glob("*/SKILL.md") if path.is_file()}
    if not leaf_names:
        return [f"coverage: skill-craft source has no skills/*/SKILL.md leaves at {skills}"]
    # Plugin bundles (bundles/<plugin>/bundle.json) publish plugins/<plugin>
    # like a leaf; install.sh never installs them, but the catalog must.
    bundle_names = {
        path.parent.name
        for path in (skill_craft_root / "bundles").glob("*/bundle.json")
        if path.is_file()
    }
    publishable = leaf_names | bundle_names

    catalog_names: set[str] = set()
    ownership_collisions: set[str] = set()
    for entry in entries:
        name = entry.get("name")
        source = entry.get("source")
        if not is_text(name) or not isinstance(source, dict):
            continue
        source_url = source.get("url")
        if is_skill_craft_url(source_url):
            catalog_names.add(name)
        elif name in publishable and is_text(source_url):
            ownership_collisions.add(name)
            owned = f"skills/{name}/SKILL.md" if name in leaf_names else f"bundles/{name}/bundle.json"
            errors.append(
                "coverage: canonical ownership collision for "
                f"skill-craft source {owned}: catalog source.url "
                f"{source_url!r}; expected {SKILL_CRAFT_URL!r}"
            )

    for leaf in sorted(leaf_names - catalog_names - ownership_collisions):
        errors.append(f"coverage: missing catalog entry for skill-craft skills/{leaf}/SKILL.md")
    for bundle in sorted(bundle_names - catalog_names - ownership_collisions):
        errors.append(f"coverage: missing catalog entry for skill-craft bundles/{bundle}/bundle.json")
    for name in sorted(catalog_names - publishable):
        errors.append(
            f"coverage: stale skill-craft catalog entry {name!r}; "
            f"no matching skills/{name}/SKILL.md or bundles/{name}/bundle.json"
        )
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path(".claude-plugin/marketplace.json"),
        help="catalog to validate (default: .claude-plugin/marketplace.json)",
    )
    parser.add_argument(
        "--skill-craft-root",
        type=Path,
        help="compare current skills/*/SKILL.md leaves against skill-craft catalog entries",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog = args.catalog.resolve()
    try:
        data = json.loads(catalog.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"FAIL {catalog}: file not found", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"FAIL {catalog}: invalid JSON: {exc}", file=sys.stderr)
        return 1

    errors, entries = validate_catalog(data, catalog)
    if args.skill_craft_root is not None:
        errors.extend(validate_coverage(entries, args.skill_craft_root.resolve()))
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        return 1
    print(f"catalog check: PASS ({catalog})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
