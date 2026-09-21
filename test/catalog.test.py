#!/usr/bin/env python3
"""Hermetic regression tests for scripts/check-catalog.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / "scripts" / "check-catalog.py"
TEST_SHA = "0123456789abcdef0123456789abcdef01234567"
SKILL_CRAFT_URL = "https://github.com/whichguy/skill-craft.git"
BACKCHAIN_URL = "https://github.com/whichguy/backchain.git"

ROLLING_SOURCES: dict[str, tuple[str, str, str | None]] = {
    "ask-agent": ("git-subdir", SKILL_CRAFT_URL, "plugins/ask-agent"),
    "shiploop": ("git-subdir", SKILL_CRAFT_URL, "plugins/shiploop"),
    "improve": ("git-subdir", SKILL_CRAFT_URL, "plugins/improve"),
    "backchain": ("url", BACKCHAIN_URL, None),
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


def plugin(
    name: str, source: dict[str, object], *, version: str = "1.0.0"
) -> dict[str, object]:
    source = {"sha": TEST_SHA, **source}
    return {
        "name": name,
        "description": f"{name} description",
        "version": version,
        "source": source,
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }


def rolling_plugin(name: str, *, version: str = "1.0.0") -> dict[str, object]:
    source_type, url, path = ROLLING_SOURCES[name]
    source: dict[str, object] = {"source": source_type, "url": url, "ref": "main"}
    if path is not None:
        source["path"] = path
    return {
        "name": name,
        "description": f"{name} description",
        "version": version,
        "source": source,
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }


def catalog(plugins: list[dict[str, object]]) -> dict[str, object]:
    return {
        "name": "fixture-market",
        "description": "Fixture catalog. No hooks.",
        "interface": {"displayName": "Fixture Market"},
        "plugins": plugins,
    }


class CatalogCheckTest(unittest.TestCase):
    def init_git(self, root: Path) -> None:
        root.mkdir(parents=True)
        subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True, text=True)

    def write_catalog(self, root: Path, body: dict[str, object]) -> Path:
        path = root / ".claude-plugin" / "marketplace.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(body), encoding="utf-8")
        return path

    def run_check(self, catalog_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECK), "--catalog", str(catalog_path), *extra],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_rejects_git_subdir_root_dot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            path = self.write_catalog(
                root,
                catalog(
                    [
                        plugin(
                            "alpha",
                            {
                                "source": "git-subdir",
                                "url": "https://github.com/whichguy/skill-craft.git",
                                "path": ".",
                                "ref": "v1.0.0",
                            },
                        )
                    ]
                ),
            )
            result = self.run_check(path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("confined non-root path", result.stderr)

    def test_rejects_duplicate_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            root_url = {
                "source": "url",
                "url": "https://github.com/example/alpha.git",
                "ref": "v1.0.0",
            }
            path = self.write_catalog(root, catalog([plugin("alpha", root_url), plugin("alpha", root_url)]))
            result = self.run_check(path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate plugin name", result.stderr)

    def test_accepts_root_url_source_without_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            path = self.write_catalog(
                root,
                catalog(
                    [
                        plugin(
                            "external",
                            {
                                "source": "url",
                                "url": "https://github.com/example/external.git",
                            },
                        )
                    ]
                ),
            )
            result = self.run_check(path)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_accepts_external_generated_subdirectory_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            path = self.write_catalog(
                root,
                catalog(
                    [
                        plugin(
                            "workflow",
                            {
                                "source": "git-subdir",
                                "url": "https://github.com/whichguy/workflow-engine.git",
                                "path": "plugins/workflow",
                                "ref": "workflow-v0.2.0",
                            },
                        )
                    ]
                ),
            )

            result = self.run_check(path)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_source_without_supported_remote_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_catalog(Path(tmp) / "market", catalog([
                plugin("external", {"source": "url", "url": "https://example.test/external.git", "ref": "v1"})
            ]))
            result = self.run_check(path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("GitHub HTTPS repository URL", result.stderr)

    def test_rejects_skill_craft_root_url_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            path = self.write_catalog(
                root,
                catalog(
                    [
                        plugin(
                            "alpha",
                            {
                                "source": "url",
                                "url": "https://github.com/whichguy/skill-craft.git",
                                "ref": "v1.0.0",
                            },
                        )
                    ]
                ),
            )
            result = self.run_check(path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("skill-craft entries must use git-subdir", result.stderr)

    def test_rejects_missing_sha_even_with_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            entry = plugin(
                "external",
                {
                    "source": "url",
                    "url": "https://github.com/example/external.git",
                    "ref": "v1.0.0",
                },
            )
            entry["source"].pop("sha")
            path = self.write_catalog(root, catalog([entry]))

            result = self.run_check(path)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source.sha must be a full 40-character commit id", result.stderr)

    def test_accepts_only_the_bounded_rolling_latest_entries_without_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            path = self.write_catalog(
                root,
                catalog([rolling_plugin(name) for name in sorted(ROLLING_SOURCES)]),
            )

            result = self.run_check(path)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_enforces_strict_semver_for_all_rolling_latest_entries(self) -> None:
        for version, valid in STRICT_SEMVER_CASES:
            for name in sorted(ROLLING_SOURCES):
                with self.subTest(name=name, version=version):
                    with tempfile.TemporaryDirectory() as tmp:
                        path = self.write_catalog(
                            Path(tmp) / "market",
                            catalog([rolling_plugin(name, version=version)]),
                        )

                        result = self.run_check(path)

                    if valid:
                        self.assertEqual(result.returncode, 0, result.stderr)
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn(
                            "rolling-latest version must be a semantic version",
                            result.stderr,
                        )

    def test_allows_nonsemantic_version_for_immutable_external_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_catalog(
                Path(tmp) / "market",
                catalog(
                    [
                        plugin(
                            "external",
                            {
                                "source": "url",
                                "url": "https://github.com/example/external.git",
                            },
                            version="legacy-release-name",
                        )
                    ]
                ),
            )

            result = self.run_check(path)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_a_rolling_latest_entry_that_keeps_a_sha_or_moves_off_main(self) -> None:
        for label, mutate, expected in (
            (
                "sha",
                lambda item: item["source"].update(sha=TEST_SHA),
                "must omit source.sha",
            ),
            (
                "ref",
                lambda item: item["source"].update(ref="v1.0.0"),
                "must use source.ref 'main'",
            ),
            (
                "path",
                lambda item: item["source"].update(path="plugins/shiploop"),
                "must use source.path 'plugins/ask-agent'",
            ),
        ):
            with self.subTest(label):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / "market"
                    item = rolling_plugin("ask-agent")
                    mutate(item)
                    path = self.write_catalog(root, catalog([item]))

                    result = self.run_check(path)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)

    def test_rejects_nontext_ref_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_catalog(
                Path(tmp) / "market",
                catalog(
                    [
                        plugin(
                            "external",
                            {
                                "source": "url",
                                "url": "https://github.com/example/external.git",
                                "ref": 7,
                            },
                        )
                    ]
                ),
            )

            result = self.run_check(path)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source.ref must be a non-empty string when present", result.stderr)

    def test_coverage_reports_missing_skill_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            skill_craft = Path(tmp) / "skill-craft"
            for leaf in ("alpha", "beta"):
                path = skill_craft / "skills" / leaf / "SKILL.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("---\nname: fixture\n---\n", encoding="utf-8")
            catalog_path = self.write_catalog(
                root,
                catalog(
                    [
                        plugin(
                            "alpha",
                            {
                                "source": "git-subdir",
                                "url": "https://github.com/whichguy/skill-craft.git",
                                "path": "plugins/alpha",
                                "ref": "v1.0.0",
                            },
                        )
                    ]
                ),
            )
            result = self.run_check(catalog_path, "--skill-craft-root", str(skill_craft))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing catalog entry for skill-craft skills/beta/SKILL.md", result.stderr)

    def test_coverage_rejects_external_source_for_canonical_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            skill_craft = Path(tmp) / "skill-craft"
            skill = skill_craft / "skills" / "alpha" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: alpha\n---\n", encoding="utf-8")
            external_url = "https://github.com/whichguy/until-loop.git"
            catalog_path = self.write_catalog(
                root,
                catalog(
                    [
                        plugin(
                            "alpha",
                            {
                                "source": "git-subdir",
                                "url": external_url,
                                "path": "plugins/alpha",
                                "ref": "v1.0.0",
                            },
                        )
                    ]
                ),
            )

            result = self.run_check(catalog_path, "--skill-craft-root", str(skill_craft))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("canonical ownership collision", result.stderr)
            self.assertIn("skills/alpha/SKILL.md", result.stderr)
            self.assertIn(external_url, result.stderr)
            self.assertIn("https://github.com/whichguy/skill-craft.git", result.stderr)
            self.assertNotIn("missing catalog entry for skill-craft skills/alpha", result.stderr)

    def test_coverage_allows_external_leaf_without_canonical_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            skill_craft = Path(tmp) / "skill-craft"
            skill = skill_craft / "skills" / "alpha" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: alpha\n---\n", encoding="utf-8")
            catalog_path = self.write_catalog(
                root,
                catalog(
                    [
                        plugin(
                            "alpha",
                            {
                                "source": "git-subdir",
                                "url": "https://github.com/whichguy/skill-craft.git",
                                "path": "plugins/alpha",
                                "ref": "v1.0.0",
                            },
                        ),
                        plugin(
                            "until-loop",
                            {
                                "source": "git-subdir",
                                "url": "https://github.com/whichguy/until-loop.git",
                                "path": "plugins/until-loop",
                                "ref": "v1.0.0",
                            },
                        ),
                    ]
                ),
            )

            result = self.run_check(catalog_path, "--skill-craft-root", str(skill_craft))

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_coverage_treats_suffix_lookalike_host_as_external(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            skill_craft = Path(tmp) / "skill-craft"
            skill = skill_craft / "skills" / "alpha" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: alpha\n---\n", encoding="utf-8")
            lookalike_url = "https://notgithub.com/whichguy/skill-craft.git"
            catalog_path = self.write_catalog(
                root,
                catalog(
                    [
                        plugin(
                            "alpha",
                            {
                                "source": "git-subdir",
                                "url": lookalike_url,
                                "path": "plugins/alpha",
                                "ref": "v1.0.0",
                            },
                        )
                    ]
                ),
            )

            result = self.run_check(catalog_path, "--skill-craft-root", str(skill_craft))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("canonical ownership collision", result.stderr)
            self.assertIn(lookalike_url, result.stderr)
            self.assertNotIn("missing catalog entry for skill-craft skills/alpha", result.stderr)

    def test_coverage_rejects_missing_skills_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            skill_craft = Path(tmp) / "skill-craft"
            catalog_path = self.write_catalog(
                root,
                catalog(
                    [
                        plugin(
                            "external",
                            {
                                "source": "url",
                                "url": "https://github.com/example/external.git",
                                "ref": "v1.0.0",
                            },
                        )
                    ]
                ),
            )

            result = self.run_check(catalog_path, "--skill-craft-root", str(skill_craft))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing skills directory", result.stderr)

    def test_coverage_rejects_empty_skill_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            skill_craft = Path(tmp) / "skill-craft"
            (skill_craft / "skills" / "alpha").mkdir(parents=True)
            catalog_path = self.write_catalog(
                root,
                catalog(
                    [
                        plugin(
                            "external",
                            {
                                "source": "url",
                                "url": "https://github.com/example/external.git",
                                "ref": "v1.0.0",
                            },
                        )
                    ]
                ),
            )

            result = self.run_check(catalog_path, "--skill-craft-root", str(skill_craft))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("has no skills/*/SKILL.md leaves", result.stderr)

    def test_repository_ignores_untracked_ignored_worktree_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            self.init_git(root)
            (root / ".gitignore").write_text(".claude/worktrees/\n", encoding="utf-8")
            body = catalog([
                plugin("external", {
                    "source": "url",
                    "url": "https://github.com/example/external.git",
                    "ref": "v1.0.0",
                })
            ])
            body["description"] = "Fixture catalog only. No hooks."
            path = self.write_catalog(root, body)
            ignored = root / ".claude" / "worktrees" / "improve-marketplace-20260914"
            duplicate_catalog = ignored / ".claude-plugin" / "marketplace.json"
            duplicate_catalog.parent.mkdir(parents=True)
            duplicate_catalog.write_text(json.dumps(body), encoding="utf-8")
            ignored_body = ignored / "skills" / "alpha" / "SKILL.md"
            ignored_body.parent.mkdir(parents=True)
            ignored_body.write_text("---\nname: alpha\n---\n", encoding="utf-8")

            result = self.run_check(path)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_repository_detects_nonignored_duplicate_catalog_and_prompt_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            self.init_git(root)
            body = catalog([
                plugin("external", {
                    "source": "url",
                    "url": "https://github.com/example/external.git",
                    "ref": "v1.0.0",
                })
            ])
            body["description"] = "Fixture catalog only. No hooks."
            path = self.write_catalog(root, body)
            duplicate_catalog = root / "copies" / ".claude-plugin" / "marketplace.json"
            duplicate_catalog.parent.mkdir(parents=True)
            duplicate_catalog.write_text(json.dumps(body), encoding="utf-8")
            prompt_body = root / "copies" / "skills" / "alpha" / "SKILL.md"
            prompt_body.parent.mkdir(parents=True)
            prompt_body.write_text("---\nname: alpha\n---\n", encoding="utf-8")

            result = self.run_check(path)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate catalog", result.stderr)
            self.assertIn("catalog-only repository must not vendor skill prompt bodies", result.stderr)

    def test_repository_detects_tracked_ignored_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            self.init_git(root)
            (root / ".gitignore").write_text(".claude/worktrees/\n", encoding="utf-8")
            body = catalog([
                plugin("external", {
                    "source": "url",
                    "url": "https://github.com/example/external.git",
                    "ref": "v1.0.0",
                })
            ])
            body["description"] = "Fixture catalog only. No hooks."
            path = self.write_catalog(root, body)
            tracked = root / ".claude" / "worktrees" / "tracked-copy"
            duplicate_catalog = tracked / ".claude-plugin" / "marketplace.json"
            duplicate_catalog.parent.mkdir(parents=True)
            duplicate_catalog.write_text(json.dumps(body), encoding="utf-8")
            prompt_body = tracked / "skills" / "alpha" / "SKILL.md"
            prompt_body.parent.mkdir(parents=True)
            prompt_body.write_text("---\nname: alpha\n---\n", encoding="utf-8")
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "add",
                    "--force",
                    ".claude/worktrees/tracked-copy/.claude-plugin/marketplace.json",
                    ".claude/worktrees/tracked-copy/skills/alpha/SKILL.md",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            result = self.run_check(path)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate catalog", result.stderr)
            self.assertIn("catalog-only repository must not vendor skill prompt bodies", result.stderr)

    def test_repository_git_errors_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "market"
            root.mkdir()
            (root / ".git").write_text("gitdir: missing\n", encoding="utf-8")
            path = self.write_catalog(
                root,
                catalog([
                    plugin("external", {
                        "source": "url",
                        "url": "https://github.com/example/external.git",
                        "ref": "v1.0.0",
                    })
                ]),
            )

            result = self.run_check(path)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unable to enumerate repository content with git ls-files", result.stderr)


if __name__ == "__main__":
    unittest.main()
