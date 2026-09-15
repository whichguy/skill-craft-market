#!/usr/bin/env python3
"""Hermetic regression tests for scripts/check-pins.py."""

from __future__ import annotations

import base64
import copy
import importlib.util
import io
import unittest
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / "scripts" / "check-pins.py"
SPEC = importlib.util.spec_from_file_location("check_pins", CHECK)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {CHECK}")
check_pins = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_pins)

PIN = "0123456789abcdef0123456789abcdef01234567"
REPO_NAME = "example/alpha"
REF = "v1.2.3"


def encoded(text: str) -> dict[str, str]:
    return {"encoding": "base64", "content": base64.b64encode(text.encode()).decode()}


def skill_body(name: str = "alpha", version: str | None = "1.2.3") -> str:
    version_line = f"version: {version}\n" if version is not None else ""
    return f"---\nname: {name}\n{version_line}---\n\n# {name}\n"


def entry(*, sha: Any = PIN, ref: Any = REF, version: str = "1.2.3") -> dict[str, Any]:
    source: dict[str, Any] = {
        "source": "url",
        "url": f"https://github.com/{REPO_NAME}.git",
        "sha": sha,
    }
    if ref is not None:
        source["ref"] = ref
    return {
        "name": "alpha",
        "description": "alpha description",
        "version": version,
        "source": source,
    }


def catalog(plugin: dict[str, Any]) -> dict[str, Any]:
    return {"plugins": [plugin]}


def manifest(*, name: str = "alpha", version: str = "1.2.3") -> dict[str, Any]:
    return {"name": name, "version": version, "description": "alpha description"}


def codex_manifest(*, name: str = "alpha", version: str = "1.2.3") -> dict[str, Any]:
    return {
        **manifest(name=name, version=version),
        "skills": "./skills/",
        "interface": {
            "displayName": name.title(),
            "shortDescription": "Pinned fixture",
            "longDescription": "A complete pinned fixture for payload validation.",
            "developerName": "Skill Craft",
            "category": "Productivity",
            "capabilities": ["Read"],
            "defaultPrompt": [f"Use ${name} for this task."],
        },
    }


class FakeTransport:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get_json(self, url: str) -> Any:
        self.calls.append(url)
        response = self.responses.get(url)
        if isinstance(response, Exception):
            raise response
        if response is None:
            raise OSError(f"no mocked response for {url}")
        return copy.deepcopy(response)


def valid_responses(
    plugin: dict[str, Any],
    *,
    plugin_manifest: dict[str, Any] | None = None,
    body: str | None = None,
) -> dict[str, Any]:
    source = plugin["source"]
    sha = source["sha"]
    package_root = source.get("path", "")
    prefix = f"{package_root}/" if package_root else ""
    responses = {
        check_pins.commit_url(REPO_NAME, source.get("ref", sha)): {"sha": sha},
        check_pins.content_url(REPO_NAME, f"{prefix}.claude-plugin/plugin.json", sha): encoded(
            __import__("json").dumps(plugin_manifest or manifest())
        ),
        check_pins.content_url(REPO_NAME, f"{prefix}skills/alpha/SKILL.md", sha): encoded(
            body or skill_body()
        ),
    }
    if source.get("ref"):
        responses[check_pins.compare_url(REPO_NAME, sha, source["ref"])] = {"status": "identical"}
    return responses


class PinCheckTest(unittest.TestCase):
    def run_check(self, body: dict[str, Any], transport: FakeTransport, **options) -> tuple[int, int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        failures, advisories = check_pins.verify_catalog(
            body,
            transport,
            stdout=stdout,
            stderr=stderr,
            **options,
        )
        return failures, advisories, stdout.getvalue(), stderr.getvalue()

    def full_responses(self, plugin=None):
        plugin = plugin or entry()
        responses = valid_responses(plugin)
        prefix = plugin["source"].get("path", "")
        prefix = prefix + "/" if prefix else ""
        paths = ["LICENSE", "README.md", ".claude-plugin/plugin.json", "skills/alpha/SKILL.md"]
        responses[check_pins.tree_url(REPO_NAME, PIN)] = {
            "truncated": False,
            "tree": [{"path": prefix + path, "type": "blob", "mode": "100644"} for path in paths],
        }
        for path in ("LICENSE", "README.md"):
            responses[check_pins.content_url(REPO_NAME, prefix + path, PIN)] = encoded("fixture content\n")
        return responses

    def test_full_payload_checks_pinned_subdirectory(self):
        plugin = entry()
        plugin["source"].update(source="git-subdir", path="plugins/alpha")
        failures, _, stdout, stderr = self.run_check(catalog(plugin), FakeTransport(self.full_responses(plugin)), full_payload=True)
        self.assertEqual(failures, 0, stderr)
        self.assertIn("payload=checked", stdout)

    def test_legacy_check_does_not_claim_full_payload(self):
        plugin = entry()
        failures, _, stdout, _ = self.run_check(catalog(plugin), FakeTransport(valid_responses(plugin)))
        self.assertEqual(failures, 0)
        self.assertIn("payload=not-checked", stdout)

    def test_full_payload_rejects_missing_license(self):
        responses = self.full_responses()
        tree = responses[check_pins.tree_url(REPO_NAME, PIN)]["tree"]
        tree[:] = [item for item in tree if item["path"] != "LICENSE"]
        failures, _, _, stderr = self.run_check(catalog(entry()), FakeTransport(responses), full_payload=True)
        self.assertEqual(failures, 1)
        self.assertIn("missing packaged LICENSE", stderr)

    def test_full_payload_rejects_truncated_tree(self):
        responses = self.full_responses()
        responses[check_pins.tree_url(REPO_NAME, PIN)]["truncated"] = True
        failures, _, _, stderr = self.run_check(catalog(entry()), FakeTransport(responses), full_payload=True)
        self.assertEqual(failures, 1)
        self.assertIn("truncated=false", stderr)

    def test_full_payload_rejects_symlink(self):
        responses = self.full_responses()
        responses[check_pins.tree_url(REPO_NAME, PIN)]["tree"].append({"path": "skills/alpha/scripts", "type": "blob", "mode": "120000"})
        failures, _, _, stderr = self.run_check(catalog(entry()), FakeTransport(responses), full_payload=True)
        self.assertEqual(failures, 1)
        self.assertIn("materialize symlink", stderr)

    def test_full_payload_rejects_unbundled_scripts(self):
        responses = self.full_responses()
        body = "---\nname: alpha\nversion: 1.2.3\nmetadata:\n  skill_craft:\n    kind: script-backed\n---\n"
        responses[check_pins.content_url(REPO_NAME, "skills/alpha/SKILL.md", PIN)] = encoded(body)
        failures, _, _, stderr = self.run_check(catalog(entry()), FakeTransport(responses), full_payload=True)
        self.assertEqual(failures, 1)
        self.assertIn("no runnable bundled script", stderr)

    def test_full_payload_rejects_placeholder_script_files(self):
        responses = self.full_responses()
        body = "---\nname: alpha\nversion: 1.2.3\nmetadata:\n  skill_craft:\n    kind: script-backed\n---\n"
        responses[check_pins.content_url(REPO_NAME, "skills/alpha/SKILL.md", PIN)] = encoded(body)
        responses[check_pins.tree_url(REPO_NAME, PIN)]["tree"].append(
            {"path": "skills/alpha/scripts/README.md", "type": "blob", "mode": "100644"}
        )
        responses[check_pins.tree_url(REPO_NAME, PIN)]["tree"].append(
            {"path": "skills/alpha/scripts/.DS_Store", "type": "blob", "mode": "100644"}
        )
        failures, _, _, stderr = self.run_check(catalog(entry()), FakeTransport(responses), full_payload=True)
        self.assertEqual(failures, 1)
        self.assertIn("no runnable bundled script", stderr)

    def test_unknown_extensionless_shebang_requires_executable_mode(self):
        body = "---\nname: alpha\nversion: 1.2.3\nmetadata:\n  skill_craft:\n    kind: script-backed\n---\n"
        path = "skills/alpha/scripts/run"
        files = {path: {"type": "blob", "mode": "100644"}}
        responses = {
            check_pins.content_url(REPO_NAME, path, PIN): encoded(
                "#!/usr/bin/env python3\nprint('fixture')\n"
            ),
        }
        with self.assertRaisesRegex(ValueError, "not executable"):
            check_pins.validate_script_payload(
                FakeTransport(responses), REPO_NAME, PIN, "", "alpha", body, files
            )

    def test_absolute_interpreter_shebangs_are_recognized(self):
        self.assertEqual("python3", check_pins.script_interpreter("run", "#!/usr/bin/python3\n"))
        self.assertEqual("bash", check_pins.script_interpreter("run", "#!/bin/bash\n"))

    def test_native_entrypoint_is_checked_at_its_declared_path(self):
        body = "---\nname: review-coverage\nversion: 1.2.3\nmetadata:\n  skill_craft:\n    kind: script-backed\n---\n"
        files = {
            "skills/review-coverage/scripts/README.md": {"type": "blob", "mode": "100644"},
        }
        with self.assertRaisesRegex(ValueError, "declared entrypoint scripts/review-coverage"):
            check_pins.validate_script_payload(
                FakeTransport({}),
                "whichguy/skill-craft",
                PIN,
                "",
                "review-coverage",
                body,
                files,
            )

    def test_extensionless_python_entrypoint_does_not_need_executable_mode(self):
        body = "---\nname: review-coverage\nversion: 1.2.3\nmetadata:\n  skill_craft:\n    kind: script-backed\n---\n"
        path = "skills/review-coverage/scripts/review-coverage"
        files = {path: {"type": "blob", "mode": "100644"}}
        responses = {
            check_pins.content_url("whichguy/skill-craft", path, PIN): encoded(
                "#!/usr/bin/env python3\nprint('fixture')\n"
            ),
        }
        check_pins.validate_script_payload(
            FakeTransport(responses),
            "whichguy/skill-craft",
            PIN,
            "",
            "review-coverage",
            body,
            files,
        )

    def test_native_full_payload_requires_matching_codex_adapter(self):
        repo = "whichguy/skill-craft"
        responses = {url.replace(REPO_NAME, repo): value for url, value in self.full_responses().items()}
        responses[check_pins.tree_url(repo, PIN)]["tree"].append({"path": ".codex-plugin/plugin.json", "type": "blob", "mode": "100644"})
        responses[check_pins.content_url(repo, ".codex-plugin/plugin.json", PIN)] = encoded(
            __import__("json").dumps(dict(manifest(), skills="./skills/", version="9.9.9")))
        with self.assertRaisesRegex(ValueError, "Codex manifest version"):
            check_pins.verify_payload(FakeTransport(responses), repo, PIN, "", manifest(), skill_body())

    def test_native_full_payload_requires_complete_codex_interface(self):
        repo = "whichguy/skill-craft"
        responses = {url.replace(REPO_NAME, repo): value for url, value in self.full_responses().items()}
        responses[check_pins.tree_url(repo, PIN)]["tree"].append(
            {"path": ".codex-plugin/plugin.json", "type": "blob", "mode": "100644"}
        )
        incomplete = codex_manifest()
        incomplete["interface"].pop("category")
        responses[check_pins.content_url(repo, ".codex-plugin/plugin.json", PIN)] = encoded(
            __import__("json").dumps(incomplete)
        )
        with self.assertRaisesRegex(ValueError, "Codex interface category"):
            check_pins.verify_payload(FakeTransport(responses), repo, PIN, "", manifest(), skill_body())

    def test_rejects_missing_sha_even_when_ref_is_present(self) -> None:
        plugin = entry(sha=None)
        plugin["source"].pop("sha")

        failures, _, _, stderr = self.run_check(catalog(plugin), FakeTransport({}))

        self.assertEqual(failures, 1)
        self.assertIn("source.sha must be a full 40-character commit id", stderr)

    def test_rejects_invalid_present_ref_before_transport(self) -> None:
        plugin = entry(ref=7)

        failures, _, _, stderr = self.run_check(catalog(plugin), FakeTransport({}))

        self.assertEqual(failures, 1)
        self.assertIn("source.ref must be a non-empty string when present", stderr)

    def test_rejects_wrong_manifest_version_and_name(self) -> None:
        plugin = entry()
        responses = valid_responses(plugin, plugin_manifest=manifest(name="wrong", version="9.9.9"))

        failures, _, _, stderr = self.run_check(catalog(plugin), FakeTransport(responses))

        self.assertEqual(failures, 2)
        self.assertIn("catalog version 1.2.3 != plugin.json version 9.9.9", stderr)
        self.assertIn("target plugin.json name 'wrong' does not match", stderr)

    def test_rejects_unreachable_ref(self) -> None:
        plugin = entry()
        responses = valid_responses(plugin)
        responses[check_pins.compare_url(REPO_NAME, PIN, REF)] = {"status": "behind"}

        failures, _, _, stderr = self.run_check(catalog(plugin), FakeTransport(responses))

        self.assertEqual(failures, 1)
        self.assertIn("is not reachable from ref", stderr)

    def test_rejects_missing_advertised_skill_body(self) -> None:
        plugin = entry()
        responses = valid_responses(plugin)
        responses.pop(check_pins.content_url(REPO_NAME, "skills/alpha/SKILL.md", PIN))

        failures, _, _, stderr = self.run_check(catalog(plugin), FakeTransport(responses))

        self.assertEqual(failures, 1)
        self.assertIn("cannot fetch advertised skill body at sha", stderr)

    def test_rejects_mismatched_skill_frontmatter(self) -> None:
        plugin = entry()
        responses = valid_responses(plugin, body=skill_body(name="wrong", version="9.9.9"))

        failures, _, _, stderr = self.run_check(catalog(plugin), FakeTransport(responses))

        self.assertEqual(failures, 1)
        self.assertIn("frontmatter name 'wrong' does not match", stderr)

    def test_rejects_mismatched_skill_frontmatter_version(self) -> None:
        plugin = entry()
        responses = valid_responses(plugin, body=skill_body(version="9.9.9"))

        failures, _, _, stderr = self.run_check(catalog(plugin), FakeTransport(responses))

        self.assertEqual(failures, 1)
        self.assertIn("version '9.9.9' != plugin.json version '1.2.3'", stderr)

    def test_allows_skill_body_without_a_version_field(self) -> None:
        plugin = entry()
        responses = valid_responses(plugin, body=skill_body(version=None))

        failures, advisories, _, stderr = self.run_check(catalog(plugin), FakeTransport(responses))

        self.assertEqual((failures, advisories), (0, 0), stderr)

    def test_accepts_successful_pinned_fetch(self) -> None:
        plugin = entry()
        transport = FakeTransport(valid_responses(plugin))

        failures, advisories, stdout, stderr = self.run_check(catalog(plugin), transport)

        self.assertEqual((failures, advisories), (0, 0), stderr)
        self.assertIn("OK   alpha version=1.2.3 body=skills/alpha/SKILL.md", stdout)
        self.assertIn(
            check_pins.content_url(REPO_NAME, ".claude-plugin/plugin.json", PIN), transport.calls
        )
        self.assertIn(
            check_pins.content_url(REPO_NAME, "skills/alpha/SKILL.md", PIN), transport.calls
        )
        self.assertNotIn("?ref=v1.2.3", "\n".join(transport.calls))

    def test_accepts_git_subdir_package_at_its_prefixed_paths(self) -> None:
        plugin = entry()
        plugin["source"].update({"source": "git-subdir", "path": "plugins/alpha"})
        transport = FakeTransport(valid_responses(plugin))

        failures, advisories, stdout, stderr = self.run_check(catalog(plugin), transport)

        self.assertEqual((failures, advisories), (0, 0), stderr)
        self.assertIn("body=plugins/alpha/skills/alpha/SKILL.md", stdout)
        self.assertIn(
            check_pins.content_url(
                REPO_NAME, "plugins/alpha/.claude-plugin/plugin.json", PIN
            ),
            transport.calls,
        )
        self.assertIn(
            check_pins.content_url(REPO_NAME, "plugins/alpha/skills/alpha/SKILL.md", PIN),
            transport.calls,
        )

    def test_accepts_sha_only_entry_with_direct_sha_lookup(self) -> None:
        plugin = entry(ref=None)
        transport = FakeTransport(valid_responses(plugin))

        failures, advisories, _, stderr = self.run_check(catalog(plugin), transport)

        self.assertEqual((failures, advisories), (0, 0), stderr)
        self.assertIn(check_pins.commit_url(REPO_NAME, PIN), transport.calls)
        self.assertFalse(any("/compare/" in call for call in transport.calls))


if __name__ == "__main__":
    unittest.main()
