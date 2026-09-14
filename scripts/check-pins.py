#!/usr/bin/env python3
"""Verify immutable catalog pins and their conventional advertised skill bodies.

Current packages omit an explicit ``skills`` manifest field and place the body
at ``<package root>/skills/<plugin name>/SKILL.md``. An explicit future layout
fails with evidence instead of being guessed from the catalog entry.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import quote, urlparse


SHA = re.compile(r"^[0-9a-fA-F]{40}$")
FRONTMATTER_FIELD = re.compile(r"^([A-Za-z0-9_-]+):(?:[ \t]*(.*))?$")
GITHUB_API = "https://api.github.com"


def is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_subdir(value: Any) -> bool:
    if not is_text(value) or "\\" in value or value.startswith("/"):
        return False
    return all(part not in ("", ".", "..") for part in value.split("/"))


def github_repo(url: Any) -> str | None:
    if not is_text(url):
        return None
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or len(parts) != 2
        or parsed.query
        or parsed.fragment
    ):
        return None
    owner, repository = parts
    repository = repository.removesuffix(".git")
    if not owner or not repository:
        return None
    return f"{owner}/{repository}"


def content_url(repo: str, path: str, sha: str) -> str:
    return (
        f"{GITHUB_API}/repos/{repo}/contents/{quote(path, safe='/')}"
        f"?ref={quote(sha, safe='')}"
    )


def commit_url(repo: str, ref: str) -> str:
    return f"{GITHUB_API}/repos/{repo}/commits/{quote(ref, safe='')}"


def compare_url(repo: str, sha: str, ref: str) -> str:
    return f"{GITHUB_API}/repos/{repo}/compare/{quote(sha, safe='')}...{quote(ref, safe='')}"


class GitHubTransport:
    def __init__(self, token: str, timeout: int) -> None:
        self.token = token
        self.timeout = timeout

    def get_json(self, url: str) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "skill-craft-market-pin-check",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            url,
            headers=headers,
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.load(response)


def fetch_file(transport: Any, repo: str, path: str, sha: str) -> str:
    payload = transport.get_json(content_url(repo, path, sha))
    if not isinstance(payload, dict) or not isinstance(payload.get("content"), str):
        raise ValueError("GitHub contents response has no base64 content")
    if payload.get("encoding") not in (None, "base64"):
        raise ValueError(f"unsupported GitHub contents encoding {payload.get('encoding')!r}")
    try:
        return base64.b64decode(payload["content"]).decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid base64 UTF-8 content: {exc}") from exc


def parse_frontmatter(text: str) -> dict[str, str] | None:
    lines = text.splitlines()
    if not lines or lines[0].removeprefix("\ufeff").strip() != "---":
        return None
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() in ("---", "..."):
            return fields
        match = FRONTMATTER_FIELD.fullmatch(line)
        if match is None:
            continue
        key, value = match.groups()
        normalized = (value or "").strip()
        if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in ("'", '"'):
            normalized = normalized[1:-1]
        fields[key] = normalized
    return None


def package_paths(plugin: dict[str, Any]) -> tuple[str, dict[str, Any], str, str]:
    name = plugin.get("name")
    if not is_text(name):
        raise ValueError("catalog entry requires a non-empty name")
    source = plugin.get("source")
    if not isinstance(source, dict):
        raise ValueError("catalog entry requires a source object")
    repo = github_repo(source.get("url"))
    if repo is None:
        raise ValueError("source.url must be a GitHub HTTPS repository URL")

    source_type = source.get("source")
    if source_type == "git-subdir":
        package_root = source.get("path")
        if not valid_subdir(package_root):
            raise ValueError("git-subdir source.path must be a confined non-root path")
    elif source_type == "url":
        if "path" in source:
            raise ValueError("root url source must not define source.path")
        package_root = ""
    else:
        raise ValueError(f"unsupported source type {source_type!r}")

    prefix = f"{package_root}/" if package_root else ""
    return name, source, repo, f"{prefix}.claude-plugin/plugin.json"


def advertised_skill_path(package_root: str, manifest: dict[str, Any], name: str) -> str:
    if "skills" in manifest:
        declared = repr(manifest["skills"])
        if len(declared) > 240:
            declared = f"{declared[:237]}..."
        raise ValueError(
            "plugin.json declares an explicit skills layout "
            f"({declared}); this catalog's pinned-package convention is not applicable"
        )
    manifest_name = manifest.get("name")
    if not is_text(manifest_name):
        raise ValueError("plugin.json has no non-empty name for the skill-body path")
    prefix = f"{package_root}/" if package_root else ""
    return f"{prefix}skills/{manifest_name}/SKILL.md"


def verify_catalog(
    data: Any,
    transport: Any,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> tuple[int, int]:
    """Return failure and advisory counts after checking every catalog entry."""
    failures = 0
    advisories = 0

    def fail(message: str) -> None:
        nonlocal failures
        print(f"FAIL {message}", file=stderr)
        failures += 1

    def advise(message: str) -> None:
        nonlocal advisories
        print(f"ADVISORY {message}", file=stdout)
        advisories += 1

    if not isinstance(data, dict):
        fail("catalog must be a JSON object")
        return failures, advisories
    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        fail("catalog plugins must be a non-empty array")
        return failures, advisories

    for index, plugin in enumerate(plugins):
        where = f"plugins[{index}]"
        if not isinstance(plugin, dict):
            fail(f"{where}: entry must be an object")
            continue
        try:
            name, source, repo, manifest_path = package_paths(plugin)
        except ValueError as exc:
            fail(f"{where}: {exc}")
            continue

        sha = source.get("sha")
        if not is_text(sha) or not SHA.fullmatch(sha):
            fail(f"{name}: source.sha must be a full 40-character commit id")
            continue
        ref = source.get("ref")
        if "ref" in source and not is_text(ref):
            fail(f"{name}: source.ref must be a non-empty string when present")
            continue

        if ref:
            try:
                resolved = transport.get_json(commit_url(repo, ref))
                if not isinstance(resolved, dict) or not is_text(resolved.get("sha")):
                    raise ValueError("commit response has no sha")
                comparison = transport.get_json(compare_url(repo, sha, ref))
                if not isinstance(comparison, dict) or comparison.get("status") not in (
                    "ahead",
                    "identical",
                ):
                    raise ValueError(f"sha {sha} is not reachable from ref {ref}")
            except Exception as exc:
                fail(f"{name}: cannot verify sha {sha} against ref {ref}: {exc}")
                continue
        else:
            try:
                transport.get_json(commit_url(repo, sha))
            except Exception as exc:
                fail(f"{name}: sha {sha} not found on {source['url']}: {exc}")
                continue

        package_root = source.get("path", "")
        print(
            f"check {name} path={package_root!r} ref={ref!r} sha={sha!r} "
            f"catalog_version={plugin.get('version')!r}",
            file=stdout,
        )
        try:
            manifest = json.loads(fetch_file(transport, repo, manifest_path, sha))
        except Exception as exc:
            fail(f"{name}: cannot fetch plugin.json at {manifest_path} at sha {sha}: {exc}")
            continue
        if not isinstance(manifest, dict):
            fail(f"{name}: plugin.json at {manifest_path} must be a JSON object")
            continue

        valid_manifest = True
        catalog_version = plugin.get("version")
        manifest_version = manifest.get("version")
        if str(catalog_version) != str(manifest_version):
            fail(
                f"{name}: catalog version {catalog_version} != plugin.json version "
                f"{manifest_version} at sha {sha}"
            )
            valid_manifest = False
        if manifest.get("name") != name:
            fail(f"{name}: target plugin.json name {manifest.get('name')!r} does not match")
            valid_manifest = False
        if "hooks" in manifest:
            fail(f"{name}: target plugin.json must not define hooks")
            valid_manifest = False
        if not valid_manifest:
            continue

        catalog_description = (plugin.get("description") or "").strip()
        manifest_description = (manifest.get("description") or "").strip()
        if catalog_description and manifest_description and catalog_description != manifest_description:
            advise(
                f"{name}: catalog description differs from plugin.json description at sha {sha} "
                "(not a hard fail)"
            )

        try:
            skill_path = advertised_skill_path(package_root, manifest, name)
            skill_body = fetch_file(transport, repo, skill_path, sha)
        except Exception as exc:
            fail(f"{name}: cannot fetch advertised skill body at sha {sha}: {exc}")
            continue
        frontmatter = parse_frontmatter(skill_body)
        if frontmatter is None:
            fail(f"{name}: advertised skill body {skill_path} has no YAML frontmatter")
            continue
        if frontmatter.get("name") != name:
            fail(
                f"{name}: advertised skill body {skill_path} frontmatter name "
                f"{frontmatter.get('name')!r} does not match"
            )
            continue
        skill_version = frontmatter.get("version")
        if skill_version is not None and skill_version != str(manifest_version):
            fail(
                f"{name}: advertised skill body {skill_path} version {skill_version!r} "
                f"!= plugin.json version {manifest_version!r}"
            )
            continue
        print(f"OK   {name} version={manifest_version} body={skill_path}", file=stdout)

    return failures, advisories


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path(".claude-plugin/marketplace.json"),
        help="catalog to check (default: .claude-plugin/marketplace.json)",
    )
    parser.add_argument("--timeout", type=int, default=60, help="GitHub request timeout in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.timeout <= 0:
        print("FAIL timeout must be positive", file=sys.stderr)
        return 1
    catalog = args.catalog.resolve()
    try:
        data = json.loads(catalog.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"FAIL {catalog}: file not found", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"FAIL {catalog}: invalid JSON: {exc}", file=sys.stderr)
        return 1

    failures, advisories = verify_catalog(
        data,
        GitHubTransport(os.environ.get("GH_TOKEN", ""), args.timeout),
    )
    if failures:
        print(f"pin-freshness: {failures} failure(s), {advisories} advisory(ies)", file=sys.stderr)
        return 1
    print(f"pin-freshness: all checks passed ({advisories} advisory(ies))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
