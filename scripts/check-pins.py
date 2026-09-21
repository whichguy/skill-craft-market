#!/usr/bin/env python3
"""Verify catalog sources and their conventional advertised skill bodies.

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
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z][0-9A-Za-z.-]*)?(?:\+[0-9A-Za-z][0-9A-Za-z.-]*)?$")
FRONTMATTER_FIELD = re.compile(r"^([A-Za-z0-9_-]+):(?:[ \t]*(.*))?$")
GITHUB_API = "https://api.github.com"
SCRIPT_SUFFIX_INTERPRETERS = {
    ".py": "python3",
    ".sh": "bash",
    ".js": "node",
    ".cjs": "node",
    ".mjs": "node",
}
CODEX_INTERFACE_TEXT_FIELDS = (
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
)
CODEX_ADAPTER_REPOSITORIES = frozenset(
    ("whichguy/skill-craft", "whichguy/workflow-engine")
)

# These coordinated workflow packages deliberately track their source main
# branch. The catalog validator restricts this no-SHA form to the same set;
# repeat it here because this file is also a standalone verifier.
ROLLING_LATEST_SOURCES: dict[str, tuple[str, str, str | None]] = {
    "ask-agent": ("git-subdir", "whichguy/skill-craft", "plugins/ask-agent"),
    "shiploop": ("git-subdir", "whichguy/skill-craft", "plugins/shiploop"),
    "improve": ("git-subdir", "whichguy/skill-craft", "plugins/improve"),
    "backchain": ("url", "whichguy/backchain", None),
}

# Immutable native package entrypoints for this marketplace family. This map
# is intentionally local to the pin verifier: validating a historical SHA must
# never depend on whatever happens to be in a current source checkout. Update
# it only with an intentional native package contract/catalog transition.
NATIVE_SCRIPT_ENTRYPOINTS: dict[str, dict[str, str]] = {
    "ask-agent": {"scripts/ask_agent_workspace.py": "python3"},
    "devloop": {"scripts/devloop-run": "bash"},
    "evidence-gates": {"scripts/evidence-gates": "python3"},
    "improve": {
        "runtime/until-loop/scripts/until-loop": "python3",
        "scripts/capture_evidence.py": "python3",
    },
    "review-coverage": {"scripts/review-coverage": "python3"},
    "shiploop": {"scripts/shiploop": "python3"},
    "shiploop-e2e-audit": {
        "scripts/resolve_harness.py": "python3",
        "harness/run.py": "python3",
        "harness/check_suite.py": "python3",
    },
    "skill-interop": {
        "scripts/marketplace-run.sh": "bash",
        "scripts/scaffold-skill.sh": "bash",
    },
}
BACKCHAIN_MULTI_SKILL_REPOSITORY = "whichguy/backchain"
# This is the historical immutable package exception. A floating Backchain
# release validates the secondary card's semantic metadata and helper rather
# than baking each future paired version into this verifier.
BACKCHAIN_MULTI_SKILL_PRIMARY = ("backchain", "0.3.5")
BACKCHAIN_MULTI_SKILL_SECONDARY = ("plan-dispatcher", "0.1.1")
BACKCHAIN_MULTI_SKILL_ENTRYPOINTS = {"scripts/dispatch.js": "node"}
IMPROVE_EPHEMERAL_RUNTIME = "runtime/until-loop/scripts/until_loop_ephemeral.py"
_IMPROVE_EPHEMERAL_RUNTIME_DECLARATION = re.compile(
    r'^RUNTIME_SCRIPT="\$SKILL_ROOT/' + re.escape(IMPROVE_EPHEMERAL_RUNTIME) + r'"$',
    re.MULTILINE,
)


def is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def rolling_latest_error(name: str, source: dict[str, Any], repo: str) -> str | None:
    """Validate the bounded no-SHA source form used by coordinated packages."""
    expected = ROLLING_LATEST_SOURCES.get(name)
    if expected is None:
        return None
    source_type, expected_repo, expected_path = expected
    if source.get("source") != source_type:
        return f"rolling-latest source.source must be {source_type!r}"
    if repo.casefold() != expected_repo:
        return f"rolling-latest source.url must identify {expected_repo!r}"
    if expected_path is None:
        if "path" in source:
            return "rolling-latest root source must not define source.path"
    elif source.get("path") != expected_path:
        return f"rolling-latest source.path must be {expected_path!r}"
    if source.get("ref") != "main":
        return "rolling-latest source.ref must be 'main'"
    if "sha" in source:
        return "rolling-latest source must omit source.sha"
    return None


def resolve_rolling_ref(
    transport: Any,
    repo: str,
    ref: str,
    cache: dict[tuple[str, str], str],
) -> str:
    """Resolve one mutable ref once, then bind every later fetch to that SHA."""
    key = (repo.casefold(), ref)
    if key in cache:
        return cache[key]
    resolved = transport.get_json(commit_url(repo, ref))
    sha = resolved.get("sha") if isinstance(resolved, dict) else None
    if not is_text(sha) or not SHA.fullmatch(sha):
        raise ValueError("commit response has no full 40-character sha")
    cache[key] = sha
    return sha


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


def tree_url(repo: str, sha: str) -> str:
    return f"{GITHUB_API}/repos/{repo}/git/trees/{quote(sha, safe='')}?recursive=1"


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


def script_interpreter(path: str, source: str) -> str | None:
    """Infer a supported interpreter from a conventional suffix or shebang."""
    suffix = Path(path).suffix
    if suffix in SCRIPT_SUFFIX_INTERPRETERS:
        return SCRIPT_SUFFIX_INTERPRETERS[suffix]
    first_line = source.splitlines()[0] if source else ""
    if not first_line.startswith("#!"):
        return None
    command = first_line[2:].strip().split()
    if not command:
        return None
    interpreter = Path(command[0]).name
    if interpreter == "env":
        command = command[1:]
        if command[:1] == ["-S"]:
            command = command[1:]
        if not command:
            return None
        interpreter = Path(command[0]).name
    if re.fullmatch(r"python(?:3(?:\.\d+)?)?", interpreter):
        return "python3"
    if interpreter in ("bash", "sh"):
        return "bash"
    if interpreter == "node":
        return "node"
    return None


def remote_script_problem(
    transport: Any,
    repo: str,
    sha: str,
    prefix: str,
    files: dict[str, dict[str, Any]],
    relative: str,
    expected: str | None,
) -> str | None:
    item = files.get(relative)
    if not isinstance(item, dict) or item.get("type") != "blob" or item.get("mode") not in ("100644", "100755"):
        return "is missing or not a regular file"
    try:
        source = fetch_file(transport, repo, prefix + relative, sha)
    except Exception as exc:
        return f"is unreadable: {exc}"
    actual = script_interpreter(relative, source)
    if actual is None:
        return "is not a recognized script (expected a supported extension or shebang)"
    if expected is not None and actual != expected:
        return f"expected {expected}, found {actual}"
    # A declared native entrypoint is invoked through its mapped interpreter,
    # so it need not be executable. The fallback accepts an extensionless
    # shebang only as a direct command and therefore requires mode 100755.
    if expected is None and not Path(relative).suffix and item["mode"] != "100755":
        return "is an extensionless shebang command but is not executable"
    return None


def native_script_entrypoints(name: str, skill_body: str) -> dict[str, str] | None:
    """Return immutable native helpers, following Improve's pinned card contract.

    Improve 0.1.x declares the durable v2 CLI and evidence collector. Its newer
    card declares the ephemeral callback runtime instead. Read that declaration
    from the pinned body so historical releases retain their original contract.
    """
    declared = NATIVE_SCRIPT_ENTRYPOINTS.get(name)
    if name == "improve" and _IMPROVE_EPHEMERAL_RUNTIME_DECLARATION.search(skill_body):
        return {IMPROVE_EPHEMERAL_RUNTIME: "python3"}
    return declared


def permits_backchain_secondary_skill(
    repo: str,
    package_root: str,
    manifest: dict[str, Any],
    *,
    rolling_backchain: bool = False,
) -> bool:
    """Allow the qualified dispatcher card for a static or rolling Backchain package."""
    is_backchain_root = (
        repo == BACKCHAIN_MULTI_SKILL_REPOSITORY
        and package_root == ""
        and manifest.get("name") == BACKCHAIN_MULTI_SKILL_PRIMARY[0]
    )
    return is_backchain_root and (
        rolling_backchain
        or (manifest.get("name"), manifest.get("version")) == BACKCHAIN_MULTI_SKILL_PRIMARY
    )


def backchain_secondary_metadata_version(skill_body: str) -> str | None:
    """Read only the qualified dispatcher's metadata.version field."""
    in_metadata = False
    for line in skill_body.splitlines()[1:]:
        if line.strip() in ("---", "..."):
            break
        if line == "metadata:":
            in_metadata = True
            continue
        if in_metadata and line and not line[0].isspace():
            break
        if in_metadata:
            match = re.fullmatch(r" {2}version:(?:[ \t]*(.*))?", line)
            if match is not None:
                value = (match.group(1) or "").strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                    value = value[1:-1]
                return value
    return None


def backchain_secondary_kind(skill_body: str) -> str | None:
    """Read the dispatcher's metadata.skill_craft.kind without a YAML dependency."""
    in_metadata = False
    in_skill_craft = False
    for line in skill_body.splitlines()[1:]:
        if line.strip() in ("---", "..."):
            break
        if line == "metadata:":
            in_metadata = True
            continue
        if in_metadata and line and not line[0].isspace():
            break
        if in_metadata and line == "  skill_craft:":
            in_skill_craft = True
            continue
        if in_skill_craft:
            if line and not line.startswith("    "):
                break
            match = re.fullmatch(r" {4}kind:(?:[ \t]*(.*))?", line)
            if match is not None:
                return (match.group(1) or "").strip().strip("'\"")
    return None


def validate_backchain_secondary_skill(
    transport: Any,
    repo: str,
    sha: str,
    prefix: str,
    files: dict[str, dict[str, Any]],
    *,
    expected_version: str | None,
) -> None:
    """Validate Backchain's paired Plan Dispatcher card and bundled helper."""
    secondary_name, _ = BACKCHAIN_MULTI_SKILL_SECONDARY
    secondary_path = f"skills/{secondary_name}/SKILL.md"
    try:
        secondary_body = fetch_file(transport, repo, prefix + secondary_path, sha)
    except Exception as exc:
        raise ValueError(f"cannot fetch qualified secondary skill {secondary_path}: {exc}") from exc
    frontmatter = parse_frontmatter(secondary_body)
    if frontmatter is None:
        raise ValueError(f"qualified secondary skill {secondary_path} has no YAML frontmatter")
    if frontmatter.get("name") != secondary_name:
        raise ValueError(
            f"qualified secondary skill {secondary_path} frontmatter name "
            f"{frontmatter.get('name')!r} does not match"
        )
    metadata_version = backchain_secondary_metadata_version(secondary_body)
    if expected_version is not None and metadata_version != expected_version:
        raise ValueError(
            f"qualified secondary skill {secondary_path} metadata.version "
            f"{metadata_version!r} != expected {expected_version!r}"
        )
    if not is_text(metadata_version) or not SEMVER.fullmatch(metadata_version):
        raise ValueError(
            f"qualified secondary skill {secondary_path} metadata.version "
            f"{metadata_version!r} is not a semantic version"
        )
    if backchain_secondary_kind(secondary_body) != "script-backed":
        raise ValueError(
            f"qualified secondary skill {secondary_path} metadata.skill_craft.kind "
            "must be 'script-backed'"
        )
    for relative, expected in BACKCHAIN_MULTI_SKILL_ENTRYPOINTS.items():
        problem = remote_script_problem(
            transport,
            repo,
            sha,
            prefix,
            files,
            f"skills/{secondary_name}/{relative}",
            expected,
        )
        if problem:
            raise ValueError(
                f"qualified secondary skill {secondary_name} declared entrypoint "
                f"{relative} {problem}"
            )


def validate_script_payload(
    transport: Any,
    repo: str,
    sha: str,
    prefix: str,
    name: str,
    skill_body: str,
    files: dict[str, dict[str, Any]],
) -> None:
    """Require actual invokable bundled helpers for a script-backed skill."""
    kind = re.search(
        r"^\s+kind:\s*(script-backed|mixed)\s*$",
        skill_body.split("\n---\n", 1)[0],
        re.M,
    )
    if kind is None:
        return
    declared = native_script_entrypoints(name, skill_body) if repo.casefold() == "whichguy/skill-craft" else None
    if declared is not None:
        for relative, expected in declared.items():
            problem = remote_script_problem(
                transport, repo, sha, prefix, files, f"skills/{name}/{relative}", expected
            )
            if problem:
                raise ValueError(f"{kind[1]} declared entrypoint {relative} {problem}")
        return

    scripts_prefix = f"skills/{name}/scripts/"
    candidates = sorted(path for path in files if path.startswith(scripts_prefix))
    for relative in candidates:
        problem = remote_script_problem(transport, repo, sha, prefix, files, relative, None)
        if problem is None:
            return
        if problem.endswith("but is not executable"):
            raise ValueError(f"{kind[1]} script candidate {relative} {problem}")
    raise ValueError(f"{kind[1]} package has no runnable bundled script entrypoint")


def validate_codex_interface(codex: dict[str, Any]) -> None:
    interface = codex.get("interface")
    if not isinstance(interface, dict):
        raise ValueError("Codex interface must be an object")
    for field in CODEX_INTERFACE_TEXT_FIELDS:
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Codex interface {field} must be a non-empty string")
    capabilities = interface.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities or not all(
        isinstance(value, str) and value.strip() for value in capabilities
    ):
        raise ValueError("Codex interface capabilities must be a non-empty string array")
    prompts = interface.get("defaultPrompt")
    if not isinstance(prompts, list) or not prompts or len(prompts) > 3 or not all(
        isinstance(value, str) and value.strip() and len(value) <= 128 for value in prompts
    ):
        raise ValueError("Codex interface defaultPrompt must contain one to three short strings")


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


def verify_payload(
    transport: Any,
    repo: str,
    sha: str,
    package_root: str,
    manifest: dict[str, Any],
    skill_body: str,
    *,
    rolling_backchain: bool = False,
) -> None:
    """Release-only gate for a complete resolved tree; never executes its code.

    This remains opt-in for old immutable pins while they are being migrated.
    Rolling sources call it unconditionally after binding their ref to one SHA.
    """
    payload = transport.get_json(tree_url(repo, sha))
    if not isinstance(payload, dict) or payload.get("truncated") is not False:
        raise ValueError("GitHub tree must be complete (truncated=false)")
    tree = payload.get("tree")
    if not isinstance(tree, list):
        raise ValueError("GitHub tree response has no tree array")
    prefix = f"{package_root}/" if package_root else ""
    files = {}
    for item in tree:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("malformed GitHub tree entry")
        path = item["path"]
        if not path.startswith(prefix):
            continue
        relative = path[len(prefix):]
        if not valid_subdir(relative):
            raise ValueError(f"unsafe payload path {relative!r}")
        if item.get("mode") in ("120000", "160000"):
            raise ValueError(f"payload must materialize symlink/submodule: {relative}")
        if item.get("type") == "blob":
            files[relative] = item
    name = manifest["name"]
    permits_secondary_skill = permits_backchain_secondary_skill(
        repo,
        package_root,
        manifest,
        rolling_backchain=rolling_backchain,
    )
    required = ["LICENSE", "README.md", ".claude-plugin/plugin.json", f"skills/{name}/SKILL.md"]
    if permits_secondary_skill:
        secondary_name, _ = BACKCHAIN_MULTI_SKILL_SECONDARY
        required.append(f"skills/{secondary_name}/SKILL.md")
    requires_codex_adapter = repo.casefold() in CODEX_ADAPTER_REPOSITORIES
    if requires_codex_adapter:
        required.append(".codex-plugin/plugin.json")
    for path in required:
        if path not in files:
            raise ValueError(f"missing packaged {path}")
    for path in ("LICENSE", "README.md"):
        if not fetch_file(transport, repo, prefix + path, sha).strip():
            raise ValueError(f"empty packaged {path}")
    allowed_skill_cards = {f"skills/{name}/SKILL.md"}
    if permits_secondary_skill:
        secondary_name, _ = BACKCHAIN_MULTI_SKILL_SECONDARY
        allowed_skill_cards.add(f"skills/{secondary_name}/SKILL.md")
    for path in files:
        if path.endswith("/SKILL.md") and path not in allowed_skill_cards:
            raise ValueError(f"unexpected additional advertised skill: {path}")
    validate_script_payload(transport, repo, sha, prefix, name, skill_body, files)
    if permits_secondary_skill:
        expected_secondary_version = (
            None if rolling_backchain else BACKCHAIN_MULTI_SKILL_SECONDARY[1]
        )
        validate_backchain_secondary_skill(
            transport,
            repo,
            sha,
            prefix,
            files,
            expected_version=expected_secondary_version,
        )
    if requires_codex_adapter:
        codex = json.loads(fetch_file(transport, repo, prefix + ".codex-plugin/plugin.json", sha))
        if not isinstance(codex, dict):
            raise ValueError("Codex manifest must be an object")
        for field in ("name", "version", "description", "license"):
            if codex.get(field) != manifest.get(field):
                raise ValueError(f"Codex manifest {field} differs from pinned Claude manifest")
        if codex.get("skills") != "./skills/":
            raise ValueError("Codex manifest must expose ./skills/")
        validate_codex_interface(codex)


def verify_catalog(
    data: Any,
    transport: Any,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    full_payload: bool = False,
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

    resolved_rolling_refs: dict[tuple[str, str], str] = {}
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

        ref = source.get("ref")
        floating = name in ROLLING_LATEST_SOURCES
        if floating:
            error = rolling_latest_error(name, source, repo)
            if error is not None:
                fail(f"{name}: {error}")
                continue
            try:
                sha = resolve_rolling_ref(transport, repo, "main", resolved_rolling_refs)
            except Exception as exc:
                fail(f"{name}: cannot resolve floating ref 'main': {exc}")
                continue
        else:
            sha = source.get("sha")
            if not is_text(sha) or not SHA.fullmatch(sha):
                fail(f"{name}: source.sha must be a full 40-character commit id")
                continue
            if "ref" in source and not is_text(ref):
                fail(f"{name}: source.ref must be a non-empty string when present")
                continue

        if not floating and ref:
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
        elif not floating:
            try:
                transport.get_json(commit_url(repo, sha))
            except Exception as exc:
                fail(f"{name}: sha {sha} not found on {source['url']}: {exc}")
                continue

        package_root = source.get("path", "")
        resolution_label = f"resolved SHA {sha}" if floating else f"sha {sha}"
        if floating:
            print(
                f"check {name} path={package_root!r} source=floating ref='main' "
                f"resolved_sha={sha!r} catalog_version={plugin.get('version')!r}",
                file=stdout,
            )
        else:
            print(
                f"check {name} path={package_root!r} ref={ref!r} sha={sha!r} "
                f"catalog_version={plugin.get('version')!r}",
                file=stdout,
            )
        try:
            manifest = json.loads(fetch_file(transport, repo, manifest_path, sha))
        except Exception as exc:
            fail(f"{name}: cannot fetch plugin.json at {manifest_path} at {resolution_label}: {exc}")
            continue
        if not isinstance(manifest, dict):
            fail(f"{name}: plugin.json at {manifest_path} must be a JSON object")
            continue

        valid_manifest = True
        catalog_version = plugin.get("version")
        manifest_version = manifest.get("version")
        if floating and (
            not is_text(catalog_version) or not SEMVER.fullmatch(catalog_version)
        ):
            fail(
                f"{name}: catalog version {catalog_version!r} must be a semantic version "
                f"at {resolution_label}"
            )
            valid_manifest = False
        if floating and (
            not is_text(manifest_version) or not SEMVER.fullmatch(manifest_version)
        ):
            fail(
                f"{name}: plugin.json version {manifest_version!r} must be a semantic version "
                f"at {resolution_label}"
            )
            valid_manifest = False
        if str(catalog_version) != str(manifest_version):
            fail(
                f"{name}: catalog version {catalog_version} != plugin.json version "
                f"{manifest_version} at {resolution_label}"
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
                f"{name}: catalog description differs from plugin.json description at {resolution_label} "
                "(not a hard fail)"
            )

        try:
            skill_path = advertised_skill_path(package_root, manifest, name)
            skill_body = fetch_file(transport, repo, skill_path, sha)
        except Exception as exc:
            fail(f"{name}: cannot fetch advertised skill body at {resolution_label}: {exc}")
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
        payload_checked = full_payload or floating
        if payload_checked:
            try:
                verify_payload(
                    transport,
                    repo,
                    sha,
                    package_root,
                    manifest,
                    skill_body,
                    rolling_backchain=floating,
                )
            except Exception as exc:
                fail(f"{name}: complete payload at {resolution_label}: {exc}")
                continue
        if floating:
            print(
                f"OK   {name} version={manifest_version} body={skill_path} "
                f"source=floating ref=main resolved_sha={sha} payload=checked",
                file=stdout,
            )
        else:
            print(f"OK   {name} version={manifest_version} body={skill_path}"
                  f" payload={'checked' if payload_checked else 'not-checked'}", file=stdout)

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
    parser.add_argument("--full-payload", action="store_true",
                        help="release gate: also verify license, README, complete tree and required Codex adapter at each resolved SHA")
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
        full_payload=args.full_payload,
    )
    if failures:
        print(f"pin-freshness: {failures} failure(s), {advisories} advisory(ies)", file=sys.stderr)
        return 1
    print(f"pin-freshness: all checks passed ({advisories} advisory(ies))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
