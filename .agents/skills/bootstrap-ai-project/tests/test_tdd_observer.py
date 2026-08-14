#!/usr/bin/env python3
"""Golden, safety, and lifecycle coverage for both passive TDD observers."""

from __future__ import annotations

import glob
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = {
    "python": SKILL / "scripts" / "test_observer.py",
    "node": SKILL / "scripts" / "test_observer.mjs",
}
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tdd-observer" / "outputs"
FAKE_AWS = "AKIA1234567890ABCDEF"
FAKE_GITHUB = "ghp_" + "A" * 36
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.signaturevalue"
FAKE_PASSWORD = "correct-horse-battery-staple"
FAKE_PRIVATE_BODY = "cHJpdmF0ZS1rZXktbXVzdC1ub3QtbGVhaw=="
POLICY_SECRET_RULES = json.loads(
    (SKILL / "policy" / "secret-rules.json").read_text(encoding="UTF-8")
)["rules"]


def canonical(value: Any, root: Path) -> Any:
    if isinstance(value, dict):
        return {key: canonical(item, root) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [canonical(item, root) for item in value]
    if isinstance(value, str):
        for candidate in (str(root.resolve()), str(root), root.resolve().as_posix(), root.as_posix()):
            value = value.replace(candidate, "<ROOT>")
    return value


class ObserverTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "project"
        self.root.mkdir()
        self.config_path = self.root / "observer-config.json"
        self.write_config("pytest", "pytest -q")
        self.session = "observer-test-" + self.id().replace(".", "-")
        for runtime in ("python", "node"):
            self.state_file(runtime).unlink(missing_ok=True)

    def tearDown(self) -> None:
        for runtime in ("python", "node"):
            self.state_file(runtime).unlink(missing_ok=True)
        self.temporary.cleanup()

    def write_config(self, framework: str, base: str) -> None:
        self.config_path.write_text(json.dumps({
            "schema_version": 1,
            "framework": framework,
            "commands": [{"id": "test", "base": base}],
            "report_pattern": "openspec/changes/{change_name}/test-evidence.md",
            "max_failure_summary_chars": 500,
            "secret_rules": POLICY_SECRET_RULES,
            "required_report_marker": "<!-- bootstrap-ai-project:tdd-evidence -->",
            "required_summary_heading": "## TDD 測試摘要",
        }), encoding="UTF-8")

    def event(self, event: str, **values: Any) -> dict[str, Any]:
        return {"hook_event_name": event, "session_id": self.session, **values}

    def invoke(self, runtime: str, event: dict[str, Any], *, parse_only: bool = False) -> tuple[dict[str, Any], str]:
        executable = sys.executable if runtime == "python" else shutil.which("node")
        if not executable:
            self.skipTest("Node.js 不可用")
        command = [str(executable), str(SCRIPTS[runtime]), "--config", str(self.config_path), "--project-root", str(self.root)]
        if parse_only:
            command.append("--parse-only")
        completed = subprocess.run(command, input=json.dumps(event), capture_output=True, text=True,
                                   encoding="UTF-8", errors="replace", timeout=20, check=False)
        self.assertEqual(0, completed.returncode, completed.stderr)
        try:
            output = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise AssertionError(f"{runtime} 並非 JSON-only: {completed.stdout!r}") from error
        self.assertEqual("", completed.stderr, f"{runtime} stderr 不應有 hook 雜訊")
        return output, completed.stdout

    def both(self, event: dict[str, Any], *, parse_only: bool = False) -> dict[str, Any]:
        # Both implementations deliberately use the same OS-temp state-file
        # naming scheme.  Keep their sessions isolated so running parity tests
        # does not make one runtime consume the other's lifecycle transition.
        outputs = []
        for runtime in ("python", "node"):
            isolated = {**event, "session_id": f"{self.session}-{runtime}"}
            outputs.append(self.invoke(runtime, isolated, parse_only=parse_only)[0])
        self.assertEqual(canonical(outputs[0], self.root), canonical(outputs[1], self.root))
        return outputs[0]

    def post(self, command: str, output: str, *, phase: str = "TDD Red: task=add; evidence=red-add", failed: bool = False) -> dict[str, Any]:
        return self.event("PostToolUseFailure" if failed else "PostToolUse", tool_name="Bash",
                          tool_input={"command": command, "description": phase},
                          tool_response={"stdout": output}, duration_ms=17)

    def initialize(self, change: str = "safe-change") -> None:
        self.both(self.event("UserPromptExpansion", command_name="spectra-apply", command_args=[change]))

    def assert_secrets_absent(self, value: Any, stderr: str = "") -> None:
        rendered = json.dumps(value, ensure_ascii=False) + stderr
        for secret in (
            FAKE_AWS,
            FAKE_GITHUB,
            FAKE_JWT,
            FAKE_PASSWORD,
            FAKE_PRIVATE_BODY,
        ):
            self.assertNotIn(secret, rendered)

    def state_file(self, runtime: str) -> Path:
        material = f"{self.session}-{runtime}\0{self.root.resolve()}".encode("UTF-8")
        return Path(tempfile.gettempdir()) / f"bootstrap-ai-project-tdd-observer-{hashlib.sha256(material).hexdigest()}.json"

    def observation_from_envelope(self, envelope: dict[str, Any], event_name: str) -> dict[str, Any]:
        specific = envelope["hookSpecificOutput"]
        self.assertEqual(event_name, specific["hookEventName"])
        return json.loads(specific["additionalContext"].removeprefix("TDD_OBSERVATION "))

    def test_framework_golden_pass_count_and_case_parity(self) -> None:
        cases = [
            ("vitest", "npx vitest run", "vitest-pass.txt", 2, 0, 2),
            ("jest", "npx jest", "jest-pass.txt", 2, 0, 2),
            ("pytest", "pytest -q", "pytest-pass.txt", 2, 0, 2),
            ("xunit", "dotnet test", "dotnet-pass.txt", 2, 0, 2),
            ("go", "go test ./...", "go-pass.txt", None, None, None),
            ("rspec", "bundle exec rspec", "rspec-pass.txt", 2, 0, 2),
            ("cargo", "cargo test", "cargo-pass.txt", 2, 0, 2),
        ]
        for framework, command, filename, passed, failed, total in cases:
            with self.subTest(framework=framework):
                self.write_config(framework, command)
                output = self.both(self.post(command, (FIXTURES / filename).read_text(encoding="UTF-8")), parse_only=True)
                self.assertEqual("passed", output["status"])
                self.assertEqual(passed, output["counts"]["passed"])
                self.assertEqual(failed, output["counts"]["failed"])
                self.assertEqual(total, output["counts"]["total"])
                self.assertFalse(output["raw_output_stored"])
                self.assertIsNone(output["failure_summary"])

    def test_fallback_cwd_uses_canonical_project_root(self) -> None:
        output = self.both(
            self.post("pytest -q", "1 passed"),
            parse_only=True,
        )
        self.assertEqual(str(self.root.resolve()), output["cwd"])

    def test_failure_classification_prioritizes_compile_infrastructure_timeout_and_assertion(self) -> None:
        classifications = [
            ("pytest-assertion-failure.txt", "assertion", "pytest -q"),
            ("vitest-assertion-failure.txt", "assertion", "npx vitest run"),
            ("compile-failure.txt", "compile", "pytest -q"),
            ("missing-dependency.txt", "infrastructure", "pytest -q"),
            ("timeout.txt", "timeout", "pytest -q"),
        ]
        for filename, expected, command in classifications:
            with self.subTest(fixture=filename):
                self.write_config("vitest" if "vitest" in command else "pytest", command)
                output = self.both(self.post(command, (FIXTURES / filename).read_text(encoding="UTF-8"), failed=True), parse_only=True)
                self.assertEqual("failed", output["status"])
                self.assertEqual(expected, output["failure_kind"])

        self.write_config("pytest", "pytest -q")
        priority = self.both(self.post(
            "pytest -q",
            "Compilation failed; Cannot find module 'pytest'; Test timed out; AssertionError",
            failed=True,
        ), parse_only=True)
        self.assertEqual("compile", priority["failure_kind"])

    def test_every_framework_normalizes_assertion_infrastructure_and_timeout(self) -> None:
        frameworks = [
            ("vitest", "npx vitest run"),
            ("jest", "npx jest"),
            ("pytest", "pytest -q"),
            ("xunit", "dotnet test"),
            ("go", "go test ./..."),
            ("rspec", "bundle exec rspec"),
            ("cargo", "cargo test"),
        ]
        failures = [
            ("AssertionError: expected true to be false", "assertion"),
            (
                (FIXTURES / "missing-dependency.txt").read_text(encoding="UTF-8"),
                "infrastructure",
            ),
            ((FIXTURES / "timeout.txt").read_text(encoding="UTF-8"), "timeout"),
        ]
        for framework, command in frameworks:
            self.write_config(framework, command)
            for text, expected in failures:
                with self.subTest(framework=framework, failure=expected):
                    output = self.both(
                        self.post(command, text, failed=True),
                        parse_only=True,
                    )
                    self.assertEqual(expected, output["failure_kind"])
                    self.assertEqual("failed", output["status"])

    def test_parse_only_does_not_create_state_and_never_exposes_secrets(self) -> None:
        before = set(glob.glob(str(Path(tempfile.gettempdir()) / "bootstrap-ai-project-tdd-observer-*.json")))
        text = (
            f"password={FAKE_PASSWORD}\n"
            f"aws={FAKE_AWS}\n"
            f"github={FAKE_GITHUB}\n"
            f"jwt={FAKE_JWT}\n"
            "-----BEGIN PRIVATE KEY-----\n"
            f"{FAKE_PRIVATE_BODY}\n"
            "-----END PRIVATE KEY-----\n"
            + (FIXTURES / "pytest-assertion-failure.txt").read_text(
                encoding="UTF-8"
            )
        )
        for runtime in ("python", "node"):
            output, stdout = self.invoke(runtime, self.post("pytest -q", text, failed=True), parse_only=True)
            self.assert_secrets_absent(output, stdout)
            self.assertTrue(output["redacted"])
        self.assertEqual(before, set(glob.glob(str(Path(tempfile.gettempdir()) / "bootstrap-ai-project-tdd-observer-*.json"))))

    def test_safe_allowlist_and_unsafe_shell_forms_are_ignored(self) -> None:
        allowed = self.both(self.post("pytest -q tests_unit focused_case", "1 passed"), parse_only=True)
        self.assertEqual("pytest -q tests_unit focused_case", allowed["command"])
        spaced = 'pytest -q "tests/程式 測試.py" -k focused_case'
        self.assertEqual(
            spaced,
            self.both(self.post(spaced, "1 passed"), parse_only=True)["command"],
        )
        ignored = [
            "pytest -q && whoami", "pytest -q; whoami",
            "pytest -q > out", "pytest -q $ENV:PATH", "env TOKEN=value pytest -q",
            "bash -c pytest", "unknown-wrapper pytest -q",
            "pytest -q ../sibling", 'pytest -q "C:\\outside\\tests"',
        ]
        for command in ignored:
            with self.subTest(command=command):
                self.assertEqual({}, self.both(self.post(command, "1 passed"), parse_only=True))

    def test_phase_observations_are_report_contract_inputs_not_proof(self) -> None:
        self.initialize()
        green = self.both(self.post("pytest -q", "1 passed", phase="TDD Green: task=add; evidence=green-add"))
        self.assertEqual("green", self.observation_from_envelope(green, "PostToolUse")["phase"])
        invalid_red = self.both(self.post("pytest -q", "1 passed", phase="TDD Red: task=bad path; evidence=bad"))
        self.assertEqual("unclassified", self.observation_from_envelope(invalid_red, "PostToolUse")["phase"])
        invalid_kind = self.both(self.post("pytest -q", "1 passed", phase="TDD Blue: task=add; evidence=blue-add"))
        self.assertEqual("unclassified", self.observation_from_envelope(invalid_kind, "PostToolUse")["phase"])
        # The observer never declares `proven`; it only retains contract-ready observations.
        stop = self.both(self.event("Stop", last_assistant_message=""))
        self.assertIn("TDD evidence is incomplete", stop["hookSpecificOutput"]["additionalContext"])

    def test_codex_prompt_submit_and_nonzero_post_tool_use(self) -> None:
        initialized = self.both(
            self.event("UserPromptSubmit", prompt="$spectra-apply codex-change")
        )
        self.assertIn(
            "initialized", initialized["hookSpecificOutput"]["additionalContext"]
        )
        failed = self.both(
            self.event(
                "PostToolUse",
                tool_name="Bash",
                tool_input={
                    "command": "pytest -q",
                    "description": "TDD Red: task=add; evidence=red-add",
                },
                tool_response={
                    "exit_code": 1,
                    "stdout": "AssertionError: expected 1 but got 2",
                },
            ),
            parse_only=True,
        )
        self.assertEqual("failed", failed["status"])
        self.assertEqual("assertion", failed["failure_kind"])

    def test_lifecycle_prompt_pretool_post_stop_report_and_session_end_cleanup(self) -> None:
        self.assertEqual({}, self.both(self.event("UserPromptExpansion", command_name="other", command_args=[])))
        initialized = self.both(
            self.event(
                "UserPromptExpansion",
                command_name="spectra-apply",
                command_args="",
            )
        )
        self.assertIn(
            "initialized",
            initialized["hookSpecificOutput"]["additionalContext"],
        )
        self.both(self.event("PreToolUse", tool_name="Bash", tool_input={"command": "spectra instructions apply --change safe-change --json"}))
        post = self.both(self.post("pytest -q", "1 passed", phase="TDD Red: task=add; evidence=red-add"))
        self.observation_from_envelope(post, "PostToolUse")
        first_stop = self.both(
            self.event(
                "Stop",
                last_assistant_message="",
                stop_hook_active=True,
            )
        )
        self.assertIn("additionalContext", first_stop["hookSpecificOutput"])
        second_stop = self.both(self.event("Stop", last_assistant_message=""))
        self.assertIn("systemMessage", second_stop)
        # State was cleaned, so a third stop has no state-dependent output.
        self.assertEqual({}, self.both(self.event("Stop", last_assistant_message="")))
        self.initialize("complete-change")
        self.both(self.post("pytest -q", "1 passed", phase="TDD Red: task=add; evidence=red-add"))
        report = self.root / "openspec" / "changes" / "complete-change" / "test-evidence.md"
        report.parent.mkdir(parents=True)
        report.write_text(
            "<!-- bootstrap-ai-project:tdd-evidence -->\n"
            "# TDD Test Evidence\n"
            "Task: add | Status: tested-not-proven\n"
            "Source: hook-observed\n"
            "Command: test / pytest -q\n"
            "<!-- evidence:red-add -->\n"
            "Red | add | test | pytest -q | hook-observed\n",
            encoding="UTF-8",
        )
        self.assertEqual(
            {},
            self.both(
                self.event(
                    "Stop",
                    last_assistant_message=(
                        "## TDD 測試摘要\n"
                        "- Task：add\n"
                        "- 狀態：tested-not-proven\n"
                        "- 完整報告：openspec/changes/complete-change/test-evidence.md"
                    ),
                )
            ),
        )
        self.initialize("session-end")
        self.both(self.event("SessionEnd"))
        self.assertEqual({}, self.both(self.event("Stop", last_assistant_message="")))

    def test_stop_rejects_unrendered_report_template(self) -> None:
        self.initialize("placeholder-change")
        self.both(
            self.post(
                "pytest -q",
                "1 passed",
                phase="TDD Green: task=add; evidence=green-add",
            )
        )
        report = (
            self.root
            / "openspec"
            / "changes"
            / "placeholder-change"
            / "test-evidence.md"
        )
        report.parent.mkdir(parents=True)
        report.write_text(
            (SKILL / "templates" / "test-evidence.md").read_text(
                encoding="UTF-8"
            ),
            encoding="UTF-8",
        )
        output = self.both(
            self.event(
                "Stop",
                last_assistant_message=(
                    "## TDD 測試摘要\n"
                    "- Task：add\n"
                    "- 狀態：tested-not-proven\n"
                    "- 完整報告："
                    "openspec/changes/placeholder-change/test-evidence.md"
                ),
            )
        )
        self.assertIn(
            "unresolved report placeholders",
            output["hookSpecificOutput"]["additionalContext"],
        )

    def test_report_change_slug_rejects_traversal(self) -> None:
        self.both(self.event("UserPromptExpansion", command_name="spectra-apply", command_args=["../escape"]))
        self.both(self.event("PreToolUse", tool_name="Bash", tool_input={"command": "spectra instructions apply --change ../escape --json"}))
        self.both(self.post("pytest -q", "1 passed"))
        output = self.both(self.event("Stop", last_assistant_message=""))
        self.assertIn("a valid Spectra change", output["hookSpecificOutput"]["additionalContext"])
        self.assertFalse((self.root.parent / "escape" / "test-evidence.md").exists())

    def test_hook_envelope_is_json_only_and_context_observation_is_parseable(self) -> None:
        self.initialize()
        event = self.post("pytest -q", f"password={FAKE_PASSWORD}\n1 passed")
        event["session_id"] = f"{self.session}-python"
        output, raw = self.invoke("python", event)
        self.assertEqual(output, json.loads(raw))
        observation = self.observation_from_envelope(output, "PostToolUse")
        self.assertEqual("test-observation", observation["kind"])
        self.assertTrue(observation["observed"])
        self.assert_secrets_absent(output, raw)
        durable = json.loads(
            self.state_file("python").read_text(encoding="UTF-8")
        )
        self.assert_secrets_absent(durable)

    def test_interrupt_boolean_and_duration_are_observed_without_becoming_red(self) -> None:
        event = self.post(
            "pytest -q",
            "1 failed",
            phase="TDD Red: task=add; evidence=red-cancelled",
            failed=True,
        )
        event["is_interrupt"] = True
        event["duration_ms"] = 4187
        output = self.both(event, parse_only=True)
        self.assertEqual("interrupted", output["status"])
        self.assertEqual(4187, output["duration_ms"])
        self.assertNotEqual("assertion", output["failure_kind"])


if __name__ == "__main__":
    unittest.main()
