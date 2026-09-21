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
ROLLING_SOURCES: dict[str, tuple[str, str, str | None]] = {
    "ask-agent": ("git-subdir", "whichguy/skill-craft", "plugins/ask-agent"),
    "shiploop": ("git-subdir", "whichguy/skill-craft", "plugins/shiploop"),
    "improve": ("git-subdir", "whichguy/skill-craft", "plugins/improve"),
    "backchain": ("url", "whichguy/backchain", None),
}
STRICT_SEMVER_CASES = (
    ("0.0.0", True),
    ("1.2.3-rc.5", True),
    ("1.2.3+001.02", True),
    ("01.2.3", False),
    ("1.02.3", False),
    ("1.2.03", False),
    ("1.2.3-01", False),
    ("1.2.3-alpha..1", False),
)


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


def rolling_entry(name: str, version: str) -> dict[str, Any]:
    source_type, repo, path = ROLLING_SOURCES[name]
    source: dict[str, Any] = {
        "source": source_type,
        "url": f"https://github.com/{repo}.git",
        "ref": "main",
    }
    if path is not None:
        source["path"] = path
    return {
        "name": name,
        "description": f"{name} description",
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


def rolling_responses(plugin: dict[str, Any], sha: str = PIN) -> dict[str, Any]:
    """Build a complete native package response for a rolling-ref fixture."""
    name = plugin["name"]
    version = plugin["version"]
    _, repo, package_root = ROLLING_SOURCES[name]
    prefix = f"{package_root}/" if package_root else ""
    manifest_body = {
        "name": name,
        "version": version,
        "description": plugin["description"],
    }
    if name == "backchain":
        secondary_body = (
            "---\nname: plan-dispatcher\nmetadata:\n  version: 0.1.2\n"
            "  skill_craft:\n    kind: script-backed\n---\n\n# Plan dispatcher\n"
        )
        paths = [
            "LICENSE",
            "README.md",
            ".claude-plugin/plugin.json",
            "skills/backchain/SKILL.md",
            "skills/plan-dispatcher/SKILL.md",
            "skills/plan-dispatcher/scripts/dispatch.js",
        ]
        return {
            check_pins.commit_url(repo, "main"): {"sha": sha},
            check_pins.content_url(repo, ".claude-plugin/plugin.json", sha): encoded(
                __import__("json").dumps(manifest_body)
            ),
            check_pins.content_url(repo, "skills/backchain/SKILL.md", sha): encoded(
                skill_body("backchain", version)
            ),
            check_pins.tree_url(repo, sha): {
                "truncated": False,
                "tree": [
                    {"path": path, "type": "blob", "mode": "100644"}
                    for path in paths
                ],
            },
            check_pins.content_url(repo, "LICENSE", sha): encoded("fixture license\n"),
            check_pins.content_url(repo, "README.md", sha): encoded("fixture readme\n"),
            check_pins.content_url(repo, "skills/plan-dispatcher/SKILL.md", sha): encoded(
                secondary_body
            ),
            check_pins.content_url(
                repo, "skills/plan-dispatcher/scripts/dispatch.js", sha
            ): encoded("#!/usr/bin/env node\nconsole.log('fixture');\n"),
        }

    codex_body = {
        **manifest_body,
        "skills": "./skills/",
        "interface": {
            "displayName": name.title(),
            "shortDescription": "Rolling fixture",
            "longDescription": "A complete rolling fixture for payload validation.",
            "developerName": "Skill Craft",
            "category": "Productivity",
            "capabilities": ["Read"],
            "defaultPrompt": [f"Use ${name} for this task."],
        },
    }
    script_paths = {
        "ask-agent": ("scripts/ask_agent_workspace.py",),
        "shiploop": ("scripts/shiploop",),
        "improve": (check_pins.IMPROVE_EPHEMERAL_RUNTIME,),
    }[name]
    skill_kind = "mixed" if name == "ask-agent" else "script-backed"
    body = (
        f"---\nname: {name}\nversion: {version}\nmetadata:\n"
        f"  skill_craft:\n    kind: {skill_kind}\n---\n"
    )
    if name == "improve":
        body += f'RUNTIME_SCRIPT="$SKILL_ROOT/{check_pins.IMPROVE_EPHEMERAL_RUNTIME}"\n'
    paths = [
        "LICENSE",
        "README.md",
        ".claude-plugin/plugin.json",
        ".codex-plugin/plugin.json",
        f"skills/{name}/SKILL.md",
        *(f"skills/{name}/{path}" for path in script_paths),
    ]
    responses: dict[str, Any] = {
        check_pins.commit_url(repo, "main"): {"sha": sha},
        check_pins.content_url(repo, prefix + ".claude-plugin/plugin.json", sha): encoded(
            __import__("json").dumps(manifest_body)
        ),
        check_pins.content_url(repo, prefix + f"skills/{name}/SKILL.md", sha): encoded(body),
        check_pins.tree_url(repo, sha): {
            "truncated": False,
            "tree": [
                {"path": prefix + path, "type": "blob", "mode": "100644"}
                for path in paths
            ],
        },
        check_pins.content_url(repo, prefix + "LICENSE", sha): encoded("fixture license\n"),
        check_pins.content_url(repo, prefix + "README.md", sha): encoded("fixture readme\n"),
        check_pins.content_url(repo, prefix + ".codex-plugin/plugin.json", sha): encoded(
            __import__("json").dumps(codex_body)
        ),
    }
    for path in script_paths:
        responses[check_pins.content_url(repo, prefix + f"skills/{name}/{path}", sha)] = encoded(
            "#!/usr/bin/env python3\nprint('fixture')\n"
        )
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

    def backchain_payload_responses(
        self,
        *,
        repo: str = "whichguy/backchain",
        package_root: str = "",
        secondary_body: str | None = None,
        include_secondary: bool = True,
        include_dispatch: bool = True,
        extra_skill: str | None = None,
    ) -> dict[str, Any]:
        paths = [
            "LICENSE",
            "README.md",
            ".claude-plugin/plugin.json",
            "skills/backchain/SKILL.md",
        ]
        if include_secondary:
            paths.append("skills/plan-dispatcher/SKILL.md")
        if include_dispatch:
            paths.append("skills/plan-dispatcher/scripts/dispatch.js")
        if extra_skill:
            paths.append(f"skills/{extra_skill}/SKILL.md")
        prefix = f"{package_root}/" if package_root else ""
        responses: dict[str, Any] = {
            check_pins.tree_url(repo, PIN): {
                "truncated": False,
                "tree": [
                    {"path": prefix + path, "type": "blob", "mode": "100644"}
                    for path in paths
                ],
            }
        }
        for path in ("LICENSE", "README.md"):
            responses[check_pins.content_url(repo, prefix + path, PIN)] = encoded("fixture content\n")
        if include_secondary:
            responses[check_pins.content_url(repo, prefix + "skills/plan-dispatcher/SKILL.md", PIN)] = encoded(
                secondary_body or self.plan_dispatcher_body()
            )
        if include_dispatch:
            responses[check_pins.content_url(repo, prefix + "skills/plan-dispatcher/scripts/dispatch.js", PIN)] = encoded(
                "#!/usr/bin/env node\nconsole.log('fixture');\n"
            )
        return responses

    @staticmethod
    def backchain_manifest(version: str = "0.3.5") -> dict[str, Any]:
        return {"name": "backchain", "version": version, "description": "Backchain fixture"}

    @staticmethod
    def plan_dispatcher_body(
        name: str = "plan-dispatcher", metadata_version: str = "0.1.1"
    ) -> str:
        return (
            f"---\nname: {name}\nmetadata:\n  version: {metadata_version}\n"
            "  skill_craft:\n    kind: script-backed\n---\n\n# Plan dispatcher\n"
        )

    def test_full_payload_checks_pinned_subdirectory(self):
        plugin = entry()
        plugin["source"].update(source="git-subdir", path="plugins/alpha")
        failures, _, stdout, stderr = self.run_check(catalog(plugin), FakeTransport(self.full_responses(plugin)), full_payload=True)
        self.assertEqual(failures, 0, stderr)
        self.assertIn("payload=checked", stdout)

    def test_full_payload_accepts_qualified_backchain_multi_skill_package(self):
        check_pins.verify_payload(
            FakeTransport(self.backchain_payload_responses()),
            "whichguy/backchain",
            PIN,
            "",
            self.backchain_manifest(),
            skill_body("backchain", "0.3.5"),
        )

    def test_full_payload_accepts_rolling_backchain_dispatcher_by_semantic_contract(self):
        check_pins.verify_payload(
            FakeTransport(
                self.backchain_payload_responses(
                    secondary_body=self.plan_dispatcher_body(metadata_version="0.1.2")
                )
            ),
            "whichguy/backchain",
            PIN,
            "",
            self.backchain_manifest("0.3.6"),
            skill_body("backchain", "0.3.6"),
            rolling_backchain=True,
        )

    def test_full_payload_rejects_rolling_backchain_dispatcher_without_semantic_script_contract(self):
        invalid = self.plan_dispatcher_body(metadata_version="not-a-version")
        with self.assertRaisesRegex(ValueError, "is not a semantic version"):
            check_pins.verify_payload(
                FakeTransport(self.backchain_payload_responses(secondary_body=invalid)),
                "whichguy/backchain",
                PIN,
                "",
                self.backchain_manifest("0.3.6"),
                skill_body("backchain", "0.3.6"),
                rolling_backchain=True,
            )

        wrong_kind = self.plan_dispatcher_body(metadata_version="0.1.2").replace(
            "kind: script-backed", "kind: mixed"
        )
        with self.assertRaisesRegex(ValueError, "metadata.skill_craft.kind"):
            check_pins.verify_payload(
                FakeTransport(self.backchain_payload_responses(secondary_body=wrong_kind)),
                "whichguy/backchain",
                PIN,
                "",
                self.backchain_manifest("0.3.6"),
                skill_body("backchain", "0.3.6"),
                rolling_backchain=True,
            )

    def test_full_payload_rejects_missing_or_mismatched_backchain_secondary_card(self):
        cases = (
            ("missing", self.backchain_payload_responses(include_secondary=False), "missing packaged skills/plan-dispatcher/SKILL.md"),
            (
                "wrong name",
                self.backchain_payload_responses(secondary_body=self.plan_dispatcher_body("wrong")),
                "frontmatter name 'wrong' does not match",
            ),
            (
                "wrong version",
                self.backchain_payload_responses(secondary_body=self.plan_dispatcher_body(metadata_version="9.9.9")),
                "metadata.version '9.9.9' != expected '0.1.1'",
            ),
            (
                "nested version",
                self.backchain_payload_responses(
                    secondary_body=(
                        "---\nname: plan-dispatcher\nmetadata:\n  nested:\n"
                        "    version: 0.1.1\n---\n\n# Plan dispatcher\n"
                    )
                ),
                "metadata.version None != expected '0.1.1'",
            ),
        )
        for label, responses, expected in cases:
            with self.subTest(label):
                with self.assertRaisesRegex(ValueError, expected):
                    check_pins.verify_payload(
                        FakeTransport(responses),
                        "whichguy/backchain",
                        PIN,
                        "",
                        self.backchain_manifest(),
                        skill_body("backchain", "0.3.5"),
                    )

    def test_full_payload_rejects_unqualified_backchain_secondary_card(self):
        cases = (
            (
                "historical version",
                "whichguy/backchain",
                self.backchain_manifest("0.3.4"),
                skill_body("backchain", "0.3.4"),
            ),
            (
                "repository spoof",
                "example/backchain",
                self.backchain_manifest(),
                skill_body("backchain", "0.3.5"),
            ),
        )
        for label, repo, package_manifest, body in cases:
            with self.subTest(label):
                with self.assertRaisesRegex(ValueError, "unexpected additional advertised skill"):
                    check_pins.verify_payload(
                        FakeTransport(self.backchain_payload_responses(repo=repo)),
                        repo,
                        PIN,
                        "",
                        package_manifest,
                        body,
                    )

    def test_full_payload_rejects_backchain_secondary_card_outside_canonical_root(self):
        package_root = "plugins/backchain"
        with self.assertRaisesRegex(ValueError, "unexpected additional advertised skill"):
            check_pins.verify_payload(
                FakeTransport(self.backchain_payload_responses(package_root=package_root)),
                "whichguy/backchain",
                PIN,
                package_root,
                self.backchain_manifest(),
                skill_body("backchain", "0.3.5"),
            )

    def test_full_payload_rejects_third_card_for_qualified_backchain_package(self):
        with self.assertRaisesRegex(ValueError, "unexpected additional advertised skill"):
            check_pins.verify_payload(
                FakeTransport(self.backchain_payload_responses(extra_skill="rogue")),
                "whichguy/backchain",
                PIN,
                "",
                self.backchain_manifest(),
                skill_body("backchain", "0.3.5"),
            )

    def test_full_payload_requires_backchain_secondary_dispatch_entrypoint(self):
        with self.assertRaisesRegex(ValueError, "dispatch.js is missing or not a regular file"):
            check_pins.verify_payload(
                FakeTransport(self.backchain_payload_responses(include_dispatch=False)),
                "whichguy/backchain",
                PIN,
                "",
                self.backchain_manifest(),
                skill_body("backchain", "0.3.5"),
            )

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

    def test_ask_agent_requires_workspace_helper_even_with_another_python_script(self):
        body = (
            "---\nname: ask-agent\nversion: 0.6.0\nmetadata:\n"
            "  skill_craft:\n    kind: mixed\n---\n"
        )
        path = "skills/ask-agent/scripts/unrelated.py"
        files = {path: {"type": "blob", "mode": "100644"}}
        transport = FakeTransport({
            check_pins.content_url("whichguy/skill-craft", path, PIN): encoded(
                "#!/usr/bin/env python3\nprint('fixture')\n"
            ),
        })
        with self.assertRaisesRegex(ValueError, "declared entrypoint scripts/ask_agent_workspace.py"):
            check_pins.validate_script_payload(
                transport, "whichguy/skill-craft", PIN, "", "ask-agent", body, files
            )

    def test_shiploop_e2e_audit_requires_all_declared_entrypoints(self):
        body = (
            "---\nname: shiploop-e2e-audit\nversion: 0.2.0\nmetadata:\n"
            "  skill_craft:\n    kind: script-backed\n---\n"
        )
        present = (
            "scripts/resolve_harness.py",
            "harness/run.py",
        )
        files = {
            f"skills/shiploop-e2e-audit/{relative}": {"type": "blob", "mode": "100644"}
            for relative in present
        }
        transport = FakeTransport({
            check_pins.content_url("whichguy/skill-craft", f"skills/shiploop-e2e-audit/{relative}", PIN): encoded(
                "#!/usr/bin/env python3\nprint('fixture')\n"
            )
            for relative in present
        })

        with self.assertRaisesRegex(ValueError, "harness/check_suite.py is missing or not a regular file"):
            check_pins.validate_script_payload(
                transport,
                "whichguy/skill-craft",
                PIN,
                "",
                "shiploop-e2e-audit",
                body,
                files,
            )

    def test_improve_ephemeral_card_requires_its_declared_runtime_only(self):
        body = (
            "---\nname: improve\nversion: 0.2.0-rc.1\nmetadata:\n"
            "  skill_craft:\n    kind: script-backed\n---\n\n"
            'RUNTIME_SCRIPT="$SKILL_ROOT/runtime/until-loop/scripts/until_loop_ephemeral.py"\n'
        )
        path = "skills/improve/runtime/until-loop/scripts/until_loop_ephemeral.py"
        files = {path: {"type": "blob", "mode": "100644"}}
        transport = FakeTransport({
            check_pins.content_url("whichguy/skill-craft", path, PIN): encoded(
                "#!/usr/bin/env python3\nprint('fixture')\n"
            ),
        })

        check_pins.validate_script_payload(
            transport, "whichguy/skill-craft", PIN, "", "improve", body, files
        )

        calls = "\n".join(transport.calls)
        self.assertIn(path, calls)
        self.assertNotIn("runtime/until-loop/scripts/until-loop", calls)
        self.assertNotIn("scripts/capture_evidence.py", calls)

    def test_improve_ephemeral_card_rejects_missing_declared_runtime(self):
        body = (
            "---\nname: improve\nversion: 0.2.0-rc.1\nmetadata:\n"
            "  skill_craft:\n    kind: script-backed\n---\n\n"
            'RUNTIME_SCRIPT="$SKILL_ROOT/runtime/until-loop/scripts/until_loop_ephemeral.py"\n'
        )

        with self.assertRaisesRegex(ValueError, "until_loop_ephemeral.py"):
            check_pins.validate_script_payload(
                FakeTransport({}), "whichguy/skill-craft", PIN, "", "improve", body, {}
            )

    def test_legacy_improve_card_keeps_durable_entrypoints(self):
        body = "---\nname: improve\nversion: 0.1.0-rc.2\nmetadata:\n  skill_craft:\n    kind: script-backed\n---\n"
        files = {
            "skills/improve/runtime/until-loop/scripts/until-loop": {"type": "blob", "mode": "100755"},
        }
        transport = FakeTransport({
            check_pins.content_url(
                "whichguy/skill-craft",
                "skills/improve/runtime/until-loop/scripts/until-loop",
                PIN,
            ): encoded("#!/usr/bin/env python3\nprint('fixture')\n"),
        })

        with self.assertRaisesRegex(ValueError, "scripts/capture_evidence.py"):
            check_pins.validate_script_payload(
                transport, "whichguy/skill-craft", PIN, "", "improve", body, files
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

    def test_workflow_engine_full_payload_requires_codex_adapter(self):
        repo = "whichguy/workflow-engine"
        responses = {url.replace(REPO_NAME, repo): value for url, value in self.full_responses().items()}

        with self.assertRaisesRegex(ValueError, "missing packaged .codex-plugin/plugin.json"):
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

    def test_rolling_latest_resolves_all_sources_once_and_checks_bound_payloads(self) -> None:
        plugins = [
            rolling_entry("ask-agent", "0.7.1"),
            rolling_entry("shiploop", "0.18.19"),
            rolling_entry("improve", "0.2.0-rc.5"),
            rolling_entry("backchain", "0.3.6"),
        ]
        responses: dict[str, Any] = {}
        for plugin in plugins:
            package_responses = rolling_responses(plugin)
            _, repo, _ = ROLLING_SOURCES[plugin["name"]]
            tree = check_pins.tree_url(repo, PIN)
            if tree in responses:
                responses[tree]["tree"].extend(package_responses.pop(tree)["tree"])
            responses.update(package_responses)
        transport = FakeTransport(responses)

        failures, advisories, stdout, stderr = self.run_check(
            {"plugins": plugins}, transport
        )

        self.assertEqual((failures, advisories), (0, 0), stderr)
        resolution_calls = [call for call in transport.calls if "/commits/" in call]
        self.assertCountEqual(
            resolution_calls,
            [
                check_pins.commit_url("whichguy/skill-craft", "main"),
                check_pins.commit_url("whichguy/backchain", "main"),
            ],
        )
        expected_payload_calls = {
            url for url in responses if "/contents/" in url or "/git/trees/" in url
        }
        self.assertTrue(expected_payload_calls.issubset(transport.calls))
        payload_calls = [
            call for call in transport.calls if "/contents/" in call or "/git/trees/" in call
        ]
        self.assertTrue(
            all(
                f"?ref={PIN}" in call or f"/git/trees/{PIN}" in call
                for call in payload_calls
            )
        )
        self.assertIn("source=floating ref='main' resolved_sha='" + PIN + "'", stdout)
        self.assertIn("source=floating ref=main resolved_sha=" + PIN + " payload=checked", stdout)
        self.assertNotIn("?ref=main", "\n".join(transport.calls))

    def test_rolling_latest_validates_matching_catalog_and_manifest_strict_semver(self) -> None:
        for version, valid in STRICT_SEMVER_CASES:
            with self.subTest(version=version):
                plugin = rolling_entry("ask-agent", version)

                failures, _, _, stderr = self.run_check(
                    catalog(plugin), FakeTransport(rolling_responses(plugin))
                )

                if valid:
                    self.assertEqual(failures, 0, stderr)
                else:
                    self.assertEqual(failures, 2)
                    self.assertIn(
                        f"catalog version {version!r} must be a semantic version",
                        stderr,
                    )
                    self.assertIn(
                        f"plugin.json version {version!r} must be a semantic version",
                        stderr,
                    )

    def test_immutable_external_entry_allows_nonsemantic_matching_version(self) -> None:
        plugin = entry(version="legacy-release-name")
        responses = valid_responses(
            plugin,
            plugin_manifest=manifest(version="legacy-release-name"),
            body=skill_body(version="legacy-release-name"),
        )

        failures, advisories, _, stderr = self.run_check(catalog(plugin), FakeTransport(responses))

        self.assertEqual((failures, advisories), (0, 0), stderr)

    def test_rolling_latest_rejects_a_sha_or_non_main_ref_before_transport(self) -> None:
        cases = (
            ("sha", lambda item: item["source"].update(sha=PIN), "must omit source.sha"),
            ("ref", lambda item: item["source"].update(ref="v0.7.1"), "must be 'main'"),
        )
        for label, mutate, expected in cases:
            with self.subTest(label):
                plugin = rolling_entry("ask-agent", "0.7.1")
                mutate(plugin)

                failures, _, _, stderr = self.run_check({"plugins": [plugin]}, FakeTransport({}))

                self.assertEqual(failures, 1)
                self.assertIn(expected, stderr)

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
