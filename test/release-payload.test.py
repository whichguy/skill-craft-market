#!/usr/bin/env python3
"""Hermetic release-diff tests for scripts/check-release-payload.py."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / "scripts" / "check-release-payload.py"
SPEC = importlib.util.spec_from_file_location("check_release_payload", CHECK)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {CHECK}")
check_release_payload = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_release_payload)

PIN = "0123456789abcdef0123456789abcdef01234567"
NATIVE_URL = "https://github.com/whichguy/skill-craft.git"
EXTERNAL_URL = "https://github.com/example/legacy.git"
WORKFLOW_ENGINE_URL = "https://github.com/whichguy/workflow-engine.git"


def available_git() -> str | None:
    candidates = [os.environ.get("GIT"), shutil.which("git")]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            result = subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            continue
        if result.returncode == 0:
            return candidate
    return None


def plugin(
    name: str,
    *,
    native: bool,
    workflow_engine: bool = False,
    version: str = "1.0.0",
) -> dict[str, object]:
    source: dict[str, object] = {
        "source": "git-subdir" if native or workflow_engine else "url",
        "url": (
            NATIVE_URL
            if native
            else WORKFLOW_ENGINE_URL if workflow_engine else EXTERNAL_URL
        ),
        "sha": PIN,
        "ref": "v1.0.0",
    }
    if native or workflow_engine:
        source["path"] = f"plugins/{name}"
    return {
        "name": name,
        "description": f"{name} description",
        "version": version,
        "source": source,
    }


def catalog(plugins: list[dict[str, object]]) -> dict[str, object]:
    return {
        "name": "fixture-market",
        "description": "fixture",
        "plugins": plugins,
    }


class FakePins:
    class GitHubTransport:
        def __init__(self, token: str, timeout: int) -> None:
            self.token = token
            self.timeout = timeout

    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, object], object, bool]] = []

    def verify_catalog(
        self,
        data: dict[str, object],
        transport: object,
        *,
        full_payload: bool,
        **_: object,
    ) -> tuple[int, int]:
        self.calls.append((data, transport, full_payload))
        return 0, 0


@unittest.skipUnless(available_git(), "a working git executable is required")
class ReleasePayloadTest(unittest.TestCase):
    git = available_git()

    def git_run(self, root: Path, *args: str) -> str:
        result = subprocess.run(
            [self.git, "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def write_catalog(self, root: Path, body: dict[str, object]) -> None:
        path = root / ".claude-plugin" / "marketplace.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, sort_keys=True), encoding="utf-8")

    def make_repo(
        self,
        root: Path,
        base_catalog: dict[str, object],
        current_catalog: dict[str, object] | None = None,
    ) -> tuple[Path, str]:
        repo = root / "market"
        repo.mkdir()
        self.git_run(repo, "init", "--quiet")
        self.git_run(repo, "config", "user.email", "tests@example.invalid")
        self.git_run(repo, "config", "user.name", "Release Payload Tests")
        self.write_catalog(repo, base_catalog)
        self.git_run(repo, "add", ".claude-plugin/marketplace.json")
        self.git_run(repo, "commit", "--quiet", "-m", "base catalog")
        base = self.git_run(repo, "rev-parse", "HEAD").strip()
        if current_catalog is not None:
            self.write_catalog(repo, current_catalog)
            self.git_run(repo, "add", ".claude-plugin/marketplace.json")
            self.git_run(repo, "commit", "--quiet", "-m", "catalog update")
        return repo, base

    def run_gate(
        self,
        repo: Path,
        base: str,
        fake: FakePins | None = None,
    ) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.dict(os.environ, {"GIT": str(self.git)}, clear=False):
            result = check_release_payload.main(
                ["--base", base],
                repo=repo,
                check_pins_module=fake,
                stdout=stdout,
                stderr=stderr,
            )
        return result, stdout.getvalue(), stderr.getvalue()

    def test_changed_and_new_qualified_entries_get_one_strict_payload_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = catalog([plugin("alpha", native=True), plugin("legacy", native=False)])
            current = catalog(
                [
                    plugin("alpha", native=True, version="2.0.0"),
                    plugin("beta", native=True),
                    plugin("legacy", native=False),
                ]
            )
            repo, base_ref = self.make_repo(Path(tmp), base, current)
            fake = FakePins()

            result, stdout, stderr = self.run_gate(repo, base_ref, fake)

        self.assertEqual(result, 0, stderr)
        self.assertEqual(len(fake.calls), 1)
        selected, transport, full_payload = fake.calls[0]
        self.assertEqual(
            [entry["name"] for entry in selected["plugins"]],
            ["alpha", "beta"],
        )
        self.assertTrue(full_payload)
        self.assertEqual(transport.timeout, 60)
        self.assertIn(
            "strict payload verification passed for 2 changed/new full-payload-gated entries",
            stdout,
        )

    def test_new_workflow_engine_entry_gets_strict_payload_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = catalog([plugin("legacy", native=False)])
            current = catalog(
                [
                    plugin("legacy", native=False),
                    plugin("workflow", native=False, workflow_engine=True),
                ]
            )
            repo, base_ref = self.make_repo(Path(tmp), base, current)
            fake = FakePins()

            result, stdout, stderr = self.run_gate(repo, base_ref, fake)

        self.assertEqual(result, 0, stderr)
        self.assertEqual(len(fake.calls), 1)
        selected, _, full_payload = fake.calls[0]
        self.assertEqual([entry["name"] for entry in selected["plugins"]], ["workflow"])
        self.assertTrue(full_payload)
        self.assertIn(
            "strict payload verification passed for 1 changed/new full-payload-gated entry",
            stdout,
        )

    def test_unchanged_legacy_and_removal_do_not_trigger_strict_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = catalog([plugin("legacy", native=False), plugin("retired", native=True)])
            current = catalog([plugin("legacy", native=False)])
            repo, base_ref = self.make_repo(Path(tmp), base, current)
            fake = FakePins()

            result, stdout, stderr = self.run_gate(repo, base_ref, fake)

        self.assertEqual(result, 0, stderr)
        self.assertEqual(fake.calls, [])
        self.assertIn("REMOVAL retired: reported only", stdout)
        self.assertIn("no changed or new full-payload-gated entries", stdout)

    def test_native_to_external_migration_fails_without_running_checker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = catalog([plugin("alpha", native=True)])
            current = catalog([plugin("alpha", native=False)])
            repo, base_ref = self.make_repo(Path(tmp), base, current)
            fake = FakePins()

            result, _, stderr = self.run_gate(repo, base_ref, fake)

        self.assertEqual(result, 1)
        self.assertEqual(fake.calls, [])
        self.assertIn("native Skill Craft source migration requires separate qualification", stderr)

    def test_missing_base_fails_before_payload_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            body = catalog([plugin("alpha", native=True)])
            repo, _ = self.make_repo(Path(tmp), body)
            fake = FakePins()

            result, _, stderr = self.run_gate(repo, "does-not-exist", fake)

        self.assertEqual(result, 1)
        self.assertEqual(fake.calls, [])
        self.assertIn("cannot resolve merge-base", stderr)

    def test_base_starting_with_dash_fails_before_payload_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            body = catalog([plugin("alpha", native=True)])
            repo, _ = self.make_repo(Path(tmp), body)
            fake = FakePins()

            result, _, stderr = self.run_gate(repo, "-unsafe", fake)

        self.assertEqual(result, 1)
        self.assertEqual(fake.calls, [])
        self.assertIn("--base must not begin with '-'", stderr)

    def test_base_option_is_required(self) -> None:
        with patch.object(sys, "stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                check_release_payload.main([])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
