#!/usr/bin/env python3
"""Hermetic regression tests for scripts/check-pins.py."""

from __future__ import annotations

import base64
import copy
import importlib.util
import io
import json
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
MCP_REPO = "whichguy/mcp-gas-deploy"
MCP_PATH = "marketplace/mcp-gas-deploy"
MCP_ADAPTER_PIN = "fedcba9876543210fedcba9876543210fedcba98"
MCP_RUNTIME_PIN = "eaab4388b3ca60c05b2179e08727d9164aa3473d"
MCP_REF = "main"


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


def mcp_entry(*, version: str = "0.5.0") -> dict[str, Any]:
    return {
        "name": "mcp-gas-deploy",
        "description": "MCP fixture",
        "version": version,
        "source": {
            "source": "git-subdir",
            "url": f"https://github.com/{MCP_REPO}.git",
            "path": MCP_PATH,
            "sha": MCP_ADAPTER_PIN,
            "ref": MCP_REF,
        },
    }


def mcp_manifest(
    *, version: str = "0.5.0", capabilities: list[str] | None = None
) -> dict[str, Any]:
    return {
        "name": "mcp-gas-deploy",
        "version": version,
        "description": "MCP fixture",
        "license": "Apache-2.0",
        "mcpServers": "./.mcp.json",
        "interface": {"capabilities": capabilities if capabilities is not None else ["Read", "Write"]},
    }


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


def mcp_responses(
    plugin: dict[str, Any],
    *,
    claude: dict[str, Any] | None = None,
    codex: dict[str, Any] | None = None,
    launcher: dict[str, Any] | None = None,
    runtime_sha: str = MCP_RUNTIME_PIN,
    source_package: dict[str, Any] | None = None,
    runtime_package: dict[str, Any] | None = None,
    full_payload: bool = False,
) -> dict[str, Any]:
    source = plugin["source"]
    adapter_sha = source["sha"]
    prefix = f"{source['path']}/"
    version = str(plugin["version"])
    launcher = launcher or {
        "mcpServers": {
            "mcp-gas-deploy": {
                "command": "npx",
                "args": ["-y", f"github:{MCP_REPO}#{runtime_sha}"],
            }
        }
    }
    package = {"name": "mcp-gas-deploy", "version": version}
    responses: dict[str, Any] = {
        check_pins.commit_url(MCP_REPO, source["ref"]): {"sha": adapter_sha},
        check_pins.compare_url(MCP_REPO, adapter_sha, source["ref"]): {"status": "identical"},
        check_pins.content_url(MCP_REPO, prefix + ".claude-plugin/plugin.json", adapter_sha): encoded(
            json.dumps(claude or mcp_manifest(version=version))
        ),
        check_pins.content_url(MCP_REPO, prefix + ".codex-plugin/plugin.json", adapter_sha): encoded(
            json.dumps(codex or mcp_manifest(version=version))
        ),
        check_pins.content_url(MCP_REPO, prefix + ".mcp.json", adapter_sha): encoded(json.dumps(launcher)),
        check_pins.content_url(MCP_REPO, "package.json", adapter_sha): encoded(
            json.dumps(source_package or package)
        ),
        check_pins.commit_url(MCP_REPO, runtime_sha): {"sha": runtime_sha},
        check_pins.compare_url(MCP_REPO, runtime_sha, adapter_sha): {"status": "ahead"},
        check_pins.content_url(MCP_REPO, "package.json", runtime_sha): encoded(
            json.dumps(runtime_package or package)
        ),
    }
    if full_payload:
        paths = [
            "LICENSE",
            "README.md",
            ".claude-plugin/plugin.json",
            ".codex-plugin/plugin.json",
            ".mcp.json",
        ]
        responses[check_pins.tree_url(MCP_REPO, adapter_sha)] = {
            "truncated": False,
            "tree": [
                {"path": prefix + path, "type": "blob", "mode": "100644"}
                for path in paths
            ],
        }
        for path in ("LICENSE", "README.md"):
            responses[check_pins.content_url(MCP_REPO, prefix + path, adapter_sha)] = encoded(
                "fixture content\n"
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
        name: str = "plan-dispatcher", metadata_version: str = "0.1.0"
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

    def test_mcp_default_check_accepts_exact_no_skill_package_and_dynamic_version(self):
        plugin = mcp_entry(version="9.8.7")
        transport = FakeTransport(mcp_responses(plugin))

        failures, advisories, stdout, stderr = self.run_check(catalog(plugin), transport)

        self.assertEqual((failures, advisories), (0, 0), stderr)
        self.assertIn("OK   mcp-gas-deploy version=9.8.7", stdout)
        self.assertFalse(any("SKILL.md" in call for call in transport.calls))

    def test_mcp_accepts_any_lowercase_immutable_runtime_sha(self):
        runtime_sha = "abcdef01abcdef01abcdef01abcdef01abcdef01"
        plugin = mcp_entry()
        transport = FakeTransport(mcp_responses(plugin, runtime_sha=runtime_sha))

        failures, advisories, _, stderr = self.run_check(catalog(plugin), transport)

        self.assertEqual((failures, advisories), (0, 0), stderr)
        self.assertIn(
            check_pins.compare_url(MCP_REPO, runtime_sha, MCP_ADAPTER_PIN), transport.calls
        )

    def test_mcp_rejects_floating_or_malformed_launcher(self):
        cases = (
            (
                "floating runtime ref",
                {
                    "mcpServers": {
                        "mcp-gas-deploy": {
                            "command": "npx",
                            "args": ["-y", f"github:{MCP_REPO}#main"],
                        }
                    }
                },
                "runtime SHA",
            ),
            (
                "wrong command",
                {
                    "mcpServers": {
                        "mcp-gas-deploy": {
                            "command": "node",
                            "args": ["-y", f"github:{MCP_REPO}#{MCP_RUNTIME_PIN}"],
                        }
                    }
                },
                "command",
            ),
            (
                "uppercase runtime SHA",
                {
                    "mcpServers": {
                        "mcp-gas-deploy": {
                            "command": "npx",
                            "args": ["-y", f"github:{MCP_REPO}#{MCP_RUNTIME_PIN.upper()}"],
                        }
                    }
                },
                "runtime SHA",
            ),
            (
                "wrong launcher repository",
                {
                    "mcpServers": {
                        "mcp-gas-deploy": {
                            "command": "npx",
                            "args": [
                                "-y",
                                f"github:example/mcp-gas-deploy#{MCP_RUNTIME_PIN}",
                            ],
                        }
                    }
                },
                "runtime SHA",
            ),
            (
                "extra server",
                {
                    "mcpServers": {
                        "mcp-gas-deploy": {
                            "command": "npx",
                            "args": ["-y", f"github:{MCP_REPO}#{MCP_RUNTIME_PIN}"],
                        },
                        "other": {"command": "npx", "args": ["-y", "other"]},
                    }
                },
                "exactly one",
            ),
        )
        for label, launcher, expected in cases:
            with self.subTest(label):
                plugin = mcp_entry()
                failures, _, _, stderr = self.run_check(
                    catalog(plugin), FakeTransport(mcp_responses(plugin, launcher=launcher))
                )
                self.assertEqual(failures, 1)
                self.assertIn(expected, stderr)

    def test_mcp_rejects_adapter_mismatch_and_forbidden_capabilities(self):
        cases = (
            (
                "Codex adapter server reference",
                mcp_manifest(),
                dict(mcp_manifest(), mcpServers="./other.json"),
                "Codex plugin.json mcpServers",
            ),
            (
                "host manifest mismatch",
                mcp_manifest(),
                dict(mcp_manifest(), description="different host metadata"),
                "Claude and Codex plugin.json must be identical",
            ),
            (
                "Claude skills",
                dict(mcp_manifest(), skills="./skills/"),
                mcp_manifest(),
                "Claude plugin.json must not define skills",
            ),
            (
                "Codex dependencies",
                mcp_manifest(),
                dict(mcp_manifest(), dependencies={"other": "1.0.0"}),
                "Codex plugin.json must not define dependencies",
            ),
            (
                "Codex hooks",
                mcp_manifest(),
                dict(mcp_manifest(), hooks={}),
                "Codex plugin.json must not define hooks",
            ),
        )
        for label, claude, codex, expected in cases:
            with self.subTest(label):
                plugin = mcp_entry()
                failures, _, _, stderr = self.run_check(
                    catalog(plugin), FakeTransport(mcp_responses(plugin, claude=claude, codex=codex))
                )
                self.assertEqual(failures, 1)
                self.assertIn(expected, stderr)

    def test_mcp_rejects_unexpected_capabilities_from_both_adapters(self):
        cases = (
            ("Claude", mcp_manifest(capabilities=["Read"]), mcp_manifest()),
            ("Codex", mcp_manifest(), mcp_manifest(capabilities=["Read"])),
        )
        for adapter, claude, codex in cases:
            with self.subTest(adapter=adapter):
                plugin = mcp_entry()
                failures, _, _, stderr = self.run_check(
                    catalog(plugin), FakeTransport(mcp_responses(plugin, claude=claude, codex=codex))
                )
                self.assertEqual(failures, 1)
                self.assertIn(f"{adapter} plugin.json interface.capabilities", stderr)

    def test_mcp_near_matches_do_not_bypass_skill_validation(self):
        cases = ("repository", "name", "path")
        for mismatch in cases:
            with self.subTest(mismatch=mismatch):
                plugin = mcp_entry()
                responses = mcp_responses(plugin)
                if mismatch == "repository":
                    plugin["source"]["url"] = "https://github.com/example/mcp-gas-deploy.git"
                    responses = {
                        url.replace(MCP_REPO, "example/mcp-gas-deploy"): value
                        for url, value in responses.items()
                    }
                elif mismatch == "name":
                    plugin["name"] = "mcp-gas-deploy-other"
                    responses = mcp_responses(
                        plugin,
                        claude=dict(mcp_manifest(), name="mcp-gas-deploy-other"),
                    )
                else:
                    plugin["source"]["path"] = "marketplace/other"
                    responses = {
                        url.replace(MCP_PATH, "marketplace/other"): value
                        for url, value in responses.items()
                    }

                failures, _, _, stderr = self.run_check(catalog(plugin), FakeTransport(responses))

                self.assertEqual(failures, 1)
                self.assertIn("cannot fetch advertised skill body", stderr)

    def test_mcp_rejects_unreachable_runtime_or_runtime_version_mismatch(self):
        cases = (
            ("unreachable", {"status": "behind"}, None, None, "runtime SHA is not reachable"),
            (
                "wrong source version",
                None,
                {"name": "mcp-gas-deploy", "version": "9.9.9"},
                None,
                "source package.json version",
            ),
            (
                "wrong runtime version",
                None,
                None,
                {"name": "mcp-gas-deploy", "version": "9.9.9"},
                "runtime package.json version",
            ),
        )
        for label, comparison, source_package, runtime_package, expected in cases:
            with self.subTest(label):
                plugin = mcp_entry()
                responses = mcp_responses(
                    plugin,
                    source_package=source_package,
                    runtime_package=runtime_package,
                )
                if comparison is not None:
                    responses[check_pins.compare_url(MCP_REPO, MCP_RUNTIME_PIN, MCP_ADAPTER_PIN)] = comparison
                failures, _, _, stderr = self.run_check(catalog(plugin), FakeTransport(responses))
                self.assertEqual(failures, 1)
                self.assertIn(expected, stderr)

    def test_mcp_rejects_self_referential_adapter_and_runtime_sha(self):
        plugin = mcp_entry()
        plugin["source"]["sha"] = MCP_RUNTIME_PIN

        failures, _, _, stderr = self.run_check(
            catalog(plugin), FakeTransport(mcp_responses(plugin))
        )

        self.assertEqual(failures, 1)
        self.assertIn("runtime SHA must precede the adapter source.sha", stderr)

    def test_mcp_full_payload_requires_the_exact_five_files(self):
        plugin = mcp_entry()
        responses = mcp_responses(plugin, full_payload=True)
        tree = responses[check_pins.tree_url(MCP_REPO, MCP_ADAPTER_PIN)]["tree"]
        tree[:] = [item for item in tree if not item["path"].endswith("/.mcp.json")]

        failures, _, _, stderr = self.run_check(
            catalog(plugin), FakeTransport(responses), full_payload=True
        )

        self.assertEqual(failures, 1)
        self.assertIn("missing packaged .mcp.json", stderr)

    def test_mcp_full_payload_rejects_truncated_tree_and_symlink(self):
        cases = ("truncated", "symlink")
        for label in cases:
            with self.subTest(label):
                plugin = mcp_entry()
                responses = mcp_responses(plugin, full_payload=True)
                tree_response = responses[check_pins.tree_url(MCP_REPO, MCP_ADAPTER_PIN)]
                if label == "truncated":
                    tree_response["truncated"] = True
                    expected = "truncated=false"
                else:
                    tree_response["tree"].append(
                        {
                            "path": f"{MCP_PATH}/skills/mcp-gas-deploy",
                            "type": "blob",
                            "mode": "120000",
                        }
                    )
                    expected = "materialize symlink"
                failures, _, _, stderr = self.run_check(
                    catalog(plugin), FakeTransport(responses), full_payload=True
                )
                self.assertEqual(failures, 1)
                self.assertIn(expected, stderr)

    def test_mcp_full_payload_rejects_hooks_dependencies_and_skills(self):
        cases = ("hooks/hook.json", "dependencies/package.json", "skills/mcp-gas-deploy/SKILL.md")
        for extra in cases:
            with self.subTest(extra=extra):
                plugin = mcp_entry()
                responses = mcp_responses(plugin, full_payload=True)
                responses[check_pins.tree_url(MCP_REPO, MCP_ADAPTER_PIN)]["tree"].append(
                    {
                        "path": f"{MCP_PATH}/{extra}",
                        "type": "blob",
                        "mode": "100644",
                    }
                )
                failures, _, _, stderr = self.run_check(
                    catalog(plugin), FakeTransport(responses), full_payload=True
                )
                self.assertEqual(failures, 1)
                self.assertIn("MCP-only payload must not include", stderr)

    def test_full_payload_accepts_qualified_backchain_multi_skill_package(self):
        check_pins.verify_payload(
            FakeTransport(self.backchain_payload_responses()),
            "whichguy/backchain",
            PIN,
            "",
            self.backchain_manifest(),
            skill_body("backchain", "0.3.5"),
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
                "metadata.version '9.9.9' != expected '0.1.0'",
            ),
            (
                "nested version",
                self.backchain_payload_responses(
                    secondary_body=(
                        "---\nname: plan-dispatcher\nmetadata:\n  nested:\n"
                        "    version: 0.1.0\n---\n\n# Plan dispatcher\n"
                    )
                ),
                "metadata.version None != expected '0.1.0'",
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
