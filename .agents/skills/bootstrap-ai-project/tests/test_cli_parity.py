#!/usr/bin/env python3
"""Golden and safety tests for both bundled runtimes."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SKILL = Path(__file__).resolve().parents[1]
PYTHON_CLI = SKILL / "scripts" / "bootstrap.py"
NODE_CLI = SKILL / "scripts" / "bootstrap.mjs"
VALIDATOR = SKILL / "scripts" / "validate_skill.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
FAKE_AWS_KEY = "AKIA1234567890ABCDEF"
ENV_VALUE = "this-value-must-never-appear-in-output"


def canonical(value: Any, target: Path | None = None) -> Any:
    if isinstance(value, dict):
        return {key: canonical(value[key], target) for key in sorted(value)}
    if isinstance(value, list):
        return [canonical(item, target) for item in value]
    if isinstance(value, str) and target is not None:
        variants = {
            str(target),
            str(target.resolve()),
            target.as_posix(),
            target.resolve().as_posix(),
        }
        for variant in sorted(variants, key=len, reverse=True):
            value = value.replace(variant, "<TARGET>")
    return value


def run_cli(
    runtime: str,
    command: str,
    request: dict[str, Any],
    *,
    confirm: str | None = None,
) -> tuple[int, dict[str, Any], str]:
    script = PYTHON_CLI if runtime == "python" else NODE_CLI
    executable = sys.executable if runtime == "python" else shutil.which("node")
    if not executable:
        raise unittest.SkipTest("Node.js 不可用")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", encoding="UTF-8", delete=False
    ) as request_file:
        json.dump(request, request_file, ensure_ascii=False)
        request_path = Path(request_file.name)
    try:
        argv = [str(executable), str(script), command, "--request", str(request_path)]
        if confirm is not None:
            argv.extend(["--confirm", confirm])
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="UTF-8",
            timeout=20,
            check=False,
        )
        try:
            output = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise AssertionError(
                f"{runtime} {command} 未輸出合法 JSON：{completed.stdout!r}"
            ) from error
        return completed.returncode, output, completed.stderr
    finally:
        request_path.unlink(missing_ok=True)


class CliParityTests(unittest.TestCase):
    maxDiff = None

    def make_target(self, fixture: str = "discover-node") -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        target = Path(temporary.name) / "target"
        shutil.copytree(FIXTURES / fixture, target)
        return temporary, target

    def assert_no_secret(self, output: dict[str, Any], stderr: str, secret: str) -> None:
        rendered = json.dumps(output, ensure_ascii=False)
        self.assertNotIn(secret, rendered)
        self.assertNotIn(secret, stderr)

    def test_skill_frontmatter_and_references(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(VALIDATOR), str(SKILL)],
            capture_output=True,
            text=True,
            encoding="UTF-8",
            timeout=20,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertEqual("ok", json.loads(completed.stdout)["status"])

    def test_tdd_contract_templates_are_complete_and_observer_is_passive(self) -> None:
        rule = (SKILL / "templates" / "rules" / "testing.md").read_text(
            encoding="UTF-8"
        )
        report = (SKILL / "templates" / "test-evidence.md").read_text(
            encoding="UTF-8"
        )
        for required in (
            "task + scenario/example + test case",
            "tested-not-proven",
            "編譯錯誤",
            "## TDD 測試摘要",
            "spectra task done",
            "未觀測",
        ):
            self.assertIn(required, rule)
        for required in (
            "<!-- bootstrap-ai-project:tdd-evidence -->",
            "## Spec Mapping",
            "## Red / Green / Refactor Evidence",
            "Working directory",
            "Duration",
            "## Changed Tests",
            "## Regression",
            "## Gaps / Follow-up",
        ):
            self.assertIn(required, report)
        python_observer = (SKILL / "scripts" / "test_observer.py").read_text(
            encoding="UTF-8"
        )
        node_observer = (SKILL / "scripts" / "test_observer.mjs").read_text(
            encoding="UTF-8"
        )
        self.assertNotIn("import subprocess", python_observer)
        self.assertNotIn("child_process", node_observer)

    def test_discover_parity_and_env_key_only(self) -> None:
        left_temp, left = self.make_target()
        right_temp, right = self.make_target()
        try:
            (left / ".git").mkdir()
            (right / ".git").mkdir()
            left_code, left_output, left_stderr = run_cli(
                "python", "discover", {"target": str(left)}
            )
            right_code, right_output, right_stderr = run_cli(
                "node", "discover", {"target": str(right)}
            )
            self.assertEqual(0, left_code, left_stderr)
            self.assertEqual(0, right_code, right_stderr)
            self.assertEqual(
                canonical(left_output, left),
                canonical(right_output, right),
            )
            for output, stderr in (
                (left_output, left_stderr),
                (right_output, right_stderr),
            ):
                self.assert_no_secret(output, stderr, ENV_VALUE)
                rendered = json.dumps(output, ensure_ascii=False)
                self.assertIn("PUBLIC_API_URL", rendered)
                self.assertIn("EXAMPLE_PASSWORD", rendered)
                self.assertEqual(
                    {
                        "requested": False,
                        "effective": False,
                        "observer_runtime": "unavailable",
                        "report_pattern": None,
                    },
                    output["derived"]["tdd_observability"],
                )
        finally:
            left_temp.cleanup()
            right_temp.cleanup()

    def test_scan_parity_and_does_not_read_real_env(self) -> None:
        temporary, target = self.make_target()
        try:
            (target / ".env").write_text(
                f"REAL_SECRET={FAKE_AWS_KEY}\n", encoding="UTF-8"
            )
            safe_request = {"target": str(target), "text": "public documentation"}
            results = [
                run_cli(runtime, "scan", safe_request)
                for runtime in ("python", "node")
            ]
            self.assertEqual([0, 0], [item[0] for item in results])
            self.assertEqual(
                canonical(results[0][1], target),
                canonical(results[1][1], target),
            )
            explicit_env = [
                run_cli(
                    runtime,
                    "scan",
                    {"target": str(target), "files": [".env"]},
                )
                for runtime in ("python", "node")
            ]
            self.assertEqual([0, 0], [item[0] for item in explicit_env])
            self.assertEqual(
                canonical(explicit_env[0][1], target),
                canonical(explicit_env[1][1], target),
            )

            blocked_request = {
                "target": str(target),
                "texts": [{"path": "generated.md", "content": FAKE_AWS_KEY}],
            }
            blocked = [
                run_cli(runtime, "scan", blocked_request)
                for runtime in ("python", "node")
            ]
            self.assertEqual([2, 2], [item[0] for item in blocked])
            self.assertEqual(
                canonical(blocked[0][1], target),
                canonical(blocked[1][1], target),
            )
            for _, output, stderr in blocked:
                self.assert_no_secret(output, stderr, FAKE_AWS_KEY)
        finally:
            temporary.cleanup()

    def operation_request(self, target: Path) -> dict[str, Any]:
        (target / ".claude").mkdir(exist_ok=True)
        (target / ".claude" / "settings.json").write_text(
            json.dumps({"env": {"LANG": "keep-existing"}}, ensure_ascii=False),
            encoding="UTF-8",
        )
        return {
            "target": str(target),
            "operations": [
                {
                    "id": "docs",
                    "type": "write",
                    "path": "docs/README.md",
                    "content": "# 文件\n",
                },
                {
                    "id": "ignore",
                    "type": "managed_gitignore",
                    "strategy": "ignore",
                },
                {
                    "id": "settings",
                    "type": "merge_json",
                    "path": ".claude/settings.json",
                    "patch": {
                        "env": {"LANG": "must-not-overwrite", "PYTHONUTF8": "1"},
                        "hooks": {
                            "Stop": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "pwsh",
                                            "args": [
                                                "-NoProfile",
                                                "-File",
                                                "${CLAUDE_PROJECT_DIR}/.claude/hooks/stop.ps1",
                                            ],
                                        }
                                    ]
                                }
                            ]
                        },
                    },
                },
                {
                    "id": "stop-hook",
                    "type": "write",
                    "path": ".claude/hooks/stop.ps1",
                    "content": (
                        "\ufeff[Console]::InputEncoding = "
                        "[System.Text.UTF8Encoding]::new($false)\n"
                        "[Console]::OutputEncoding = "
                        "[System.Text.UTF8Encoding]::new($false)\n"
                        "exit 0\n"
                    ),
                },
            ],
        }

    def test_plan_apply_verify_parity(self) -> None:
        targets: list[tuple[tempfile.TemporaryDirectory[str], Path, str]] = []
        try:
            for runtime in ("python", "node"):
                temporary, target = self.make_target()
                request = self.operation_request(target)
                code, planned, stderr = run_cli(runtime, "plan", request)
                self.assertEqual(0, code, stderr)
                targets.append((temporary, target, planned["plan_sha256"]))

            plans = [
                canonical(
                    run_cli(runtime, "plan", self.operation_request(target))[1],
                    target,
                )
                for runtime, (_, target, _) in zip(
                    ("python", "node"), targets, strict=True
                )
            ]
            for output in plans:
                output["plan_sha256"] = "<TARGET-BOUND-PLAN>"
            self.assertEqual(plans[0], plans[1])

            apply_outputs = []
            verify_outputs = []
            for runtime, (_, target, plan_hash) in zip(
                ("python", "node"), targets, strict=True
            ):
                request = self.operation_request(target)
                code, output, stderr = run_cli(
                    runtime, "apply", request, confirm=plan_hash
                )
                self.assertEqual(0, code, stderr)
                normalized_apply = canonical(output, target)
                normalized_apply["plan_sha256"] = "<TARGET-BOUND-PLAN>"
                apply_outputs.append(normalized_apply)
                settings = json.loads(
                    (target / ".claude" / "settings.json").read_text(encoding="UTF-8")
                )
                self.assertEqual("keep-existing", settings["env"]["LANG"])
                self.assertEqual("1", settings["env"]["PYTHONUTF8"])
                code, output, stderr = run_cli(runtime, "verify", request)
                self.assertEqual(0, code, stderr)
                verify_outputs.append(canonical(output, target))
            self.assertEqual(apply_outputs[0], apply_outputs[1])
            self.assertEqual(verify_outputs[0], verify_outputs[1])
        finally:
            for temporary, _, _ in targets:
                temporary.cleanup()

    def test_tdd_observability_components_plan_apply_and_verify(self) -> None:
        secret_rules = json.loads(
            (SKILL / "policy" / "secret-rules.json").read_text(encoding="UTF-8")
        )["rules"]
        observer = (SKILL / "scripts" / "test_observer.py").read_text(
            encoding="UTF-8"
        )
        testing_rule = (SKILL / "templates" / "rules" / "testing.md").read_text(
            encoding="UTF-8"
        )

        def request(target: Path, *, weaken_secrets: bool = False) -> dict[str, Any]:
            config = {
                "schema_version": 1,
                "framework": "pytest",
                "commands": [{"id": "regression", "base": "python -m pytest"}],
                "report_pattern": "openspec/changes/{change_name}/test-evidence.md",
                "max_failure_summary_chars": 500,
                "secret_rules": [] if weaken_secrets else secret_rules,
                "required_report_marker": "<!-- bootstrap-ai-project:tdd-evidence -->",
                "required_summary_heading": "## TDD 測試摘要",
            }
            handler = {
                "type": "command",
                "command": "python",
                "args": [
                    "${CLAUDE_PROJECT_DIR}/.ai/bootstrap-ai-project/hooks/test-observer.py",
                    "--config",
                    "${CLAUDE_PROJECT_DIR}/.ai/bootstrap-ai-project/tdd-observer.json",
                    "--project-root",
                    "${CLAUDE_PROJECT_DIR}",
                ],
            }
            hooks = {
                "UserPromptExpansion": [
                    {"matcher": "spectra-apply", "hooks": [handler]}
                ],
                "PreToolUse": [{"matcher": "Bash", "hooks": [handler]}],
                "PostToolUse": [{"matcher": "Bash", "hooks": [handler]}],
                "PostToolUseFailure": [{"matcher": "Bash", "hooks": [handler]}],
                "Stop": [{"hooks": [handler]}],
                "SessionEnd": [{"hooks": [handler]}],
            }
            return {
                "target": str(target),
                "operations": [
                    {
                        "id": "testing-rule",
                        "type": "write",
                        "path": ".claude/rules/testing.md",
                        "content": testing_rule,
                    },
                    {
                        "id": "observer",
                        "type": "write",
                        "path": ".ai/bootstrap-ai-project/hooks/test-observer.py",
                        "content": observer,
                    },
                    {
                        "id": "observer-config",
                        "type": "write",
                        "path": ".ai/bootstrap-ai-project/tdd-observer.json",
                        "content": json.dumps(
                            config, ensure_ascii=False, indent=2
                        )
                        + "\n",
                    },
                    {
                        "id": "observer-hooks",
                        "type": "merge_json",
                        "path": ".claude/settings.json",
                        "patch": {"hooks": hooks},
                    },
                ],
            }

        for runtime in ("python", "node"):
            with self.subTest(runtime=runtime):
                temporary, target = self.make_target()
                try:
                    code, planned, stderr = run_cli(
                        runtime, "plan", request(target)
                    )
                    self.assertEqual(0, code, stderr)
                    code, _, stderr = run_cli(
                        runtime,
                        "apply",
                        request(target),
                        confirm=planned["plan_sha256"],
                    )
                    self.assertEqual(0, code, stderr)
                    code, verified, stderr = run_cli(
                        runtime, "verify", request(target)
                    )
                    self.assertEqual(0, code, stderr)
                    self.assertTrue(verified["ok"])
                    self.assertTrue(
                        all(
                            result["status"] == "success"
                            for result in verified["results"]
                        )
                    )
                    settings = json.loads(
                        (target / ".claude" / "settings.json").read_text(
                            encoding="UTF-8"
                        )
                    )
                    self.assertNotIn("matcher", settings["hooks"]["Stop"][0])
                    self.assertEqual(
                        "spectra-apply",
                        settings["hooks"]["UserPromptExpansion"][0]["matcher"],
                    )
                finally:
                    temporary.cleanup()

        temporary, target = self.make_target()
        try:
            self.assertEqual(
                [3, 3],
                [
                    run_cli(
                        runtime,
                        "plan",
                        request(target, weaken_secrets=True),
                    )[0]
                    for runtime in ("python", "node")
                ],
            )
        finally:
            temporary.cleanup()

    def test_broken_marker_and_plan_drift_fail_closed(self) -> None:
        for runtime in ("python", "node"):
            temporary, target = self.make_target("gitignore-broken")
            try:
                request = {
                    "target": str(target),
                    "operations": [
                        {
                            "id": "ignore",
                            "type": "managed_gitignore",
                            "strategy": "ignore",
                        }
                    ],
                }
                code, output, stderr = run_cli(runtime, "plan", request)
                self.assertEqual(4, code, output)
                self.assert_no_secret(output, stderr, FAKE_AWS_KEY)
            finally:
                temporary.cleanup()

            temporary, target = self.make_target()
            try:
                request = {
                    "target": str(target),
                    "operations": [
                        {
                            "id": "docs",
                            "type": "write",
                            "path": "docs/README.md",
                            "content": "# 文件\n",
                        }
                    ],
                }
                code, planned, _ = run_cli(runtime, "plan", request)
                self.assertEqual(0, code)
                (target / "docs").mkdir()
                (target / "docs" / "README.md").write_text(
                    "external change\n", encoding="UTF-8"
                )
                code, _, _ = run_cli(
                    runtime, "apply", request, confirm=planned["plan_sha256"]
                )
                self.assertEqual(4, code)
                self.assertEqual(
                    "external change\n",
                    (target / "docs" / "README.md").read_text(encoding="UTF-8"),
                )
            finally:
                temporary.cleanup()

    def test_source_manifest_records_exclusions_without_values(self) -> None:
        left_temp, left = self.make_target()
        right_temp, right = self.make_target()
        try:
            for target in (left, right):
                (target / ".env").write_text(
                    f"REAL_SECRET={FAKE_AWS_KEY}\n", encoding="UTF-8"
                )
                (target / ".env.staging.local").write_text(
                    f"OTHER_SECRET={FAKE_AWS_KEY}\n", encoding="UTF-8"
                )
                (target / "id_rsa").write_text(
                    "private fixture value\n", encoding="UTF-8"
                )
                dependency = target / "node_modules"
                dependency.mkdir()
                (dependency / "ignored.js").write_text(
                    "ignored\n", encoding="UTF-8"
                )
                (target / "oversized.txt").write_bytes(b"x" * 1_048_577)
                (target / "image.png").write_bytes(b"\x89PNG\r\n")
            outputs = [
                run_cli(runtime, "discover", {"target": str(target)})
                for runtime, target in (("python", left), ("node", right))
            ]
            self.assertEqual([0, 0], [item[0] for item in outputs])
            self.assertEqual(
                canonical(outputs[0][1], left),
                canonical(outputs[1][1], right),
            )
            manifest = {
                item["path"]: item
                for item in outputs[0][1]["discovery"]["source_manifest"]
            }
            self.assertEqual("secret-file", manifest[".env"]["reason"])
            self.assertEqual(
                "secret-file", manifest[".env.staging.local"]["reason"]
            )
            self.assertEqual("secret-file", manifest["id_rsa"]["reason"])
            self.assertEqual(
                "excluded-directory", manifest["node_modules"]["reason"]
            )
            self.assertEqual("too-large", manifest["oversized.txt"]["reason"])
            self.assertEqual(
                "binary-or-generated", manifest["image.png"]["reason"]
            )
            for _, output, stderr in outputs:
                self.assert_no_secret(output, stderr, FAKE_AWS_KEY)
                self.assertNotIn("private fixture value", json.dumps(output))
        finally:
            left_temp.cleanup()
            right_temp.cleanup()

    def test_spectra_state_parity(self) -> None:
        for value, expected in (
            ("false", "disabled"),
            ("true", "enabled"),
            ("maybe", "invalid"),
        ):
            left_temp, left = self.make_target()
            right_temp, right = self.make_target()
            try:
                for target in (left, right):
                    (target / ".spectra.yaml").write_text(
                        f"tdd: {value}\n", encoding="UTF-8"
                    )
                outputs = [
                    run_cli(runtime, "discover", {"target": str(target)})
                    for runtime, target in (("python", left), ("node", right))
                ]
                self.assertEqual([0, 0], [item[0] for item in outputs])
                self.assertEqual(
                    canonical(outputs[0][1], left),
                    canonical(outputs[1][1], right),
                )
                self.assertEqual(
                    expected,
                    outputs[0][1]["discovery"]["spectra"]["tdd_status"],
                )
            finally:
                left_temp.cleanup()
                right_temp.cleanup()

    def test_monorepo_target_is_scoped(self) -> None:
        temporaries: list[tempfile.TemporaryDirectory[str]] = []
        outputs = []
        try:
            for runtime in ("python", "node"):
                temporary = tempfile.TemporaryDirectory()
                temporaries.append(temporary)
                root = Path(temporary.name)
                (root / ".git").mkdir()
                selected = root / "packages" / "selected"
                sibling = root / "packages" / "sibling"
                selected.mkdir(parents=True)
                sibling.mkdir(parents=True)
                (selected / "package.json").write_text(
                    '{"name":"selected"}\n', encoding="UTF-8"
                )
                (sibling / "package.json").write_text(
                    '{"name":"sibling"}\n', encoding="UTF-8"
                )
                (sibling / "sibling.test.js").write_text(
                    "throw new Error('outside target');\n", encoding="UTF-8"
                )
                outputs.append(
                    (selected, run_cli(runtime, "discover", {"target": str(selected)}))
                )
            self.assertEqual([0, 0], [item[1][0] for item in outputs])
            normalized = [
                canonical(output[1][1], output[0]) for output in outputs
            ]
            for output in normalized:
                output["target"]["repo_root"] = "<REPO>"
            self.assertEqual(normalized[0], normalized[1])
            discovery = outputs[0][1][1]
            self.assertEqual("monorepo-target", discovery["target"]["kind"])
            self.assertEqual(
                "unavailable",
                discovery["discovery"]["test_profiles"][0]["source"],
            )
            self.assertEqual(
                "unavailable",
                discovery["derived"]["test_profile"]["source"],
            )
            self.assertNotIn("sibling", json.dumps(discovery))
        finally:
            for temporary in temporaries:
                temporary.cleanup()

    def test_codex_hooks_use_native_command_strings_and_shared_runtime(self) -> None:
        hooks = {
            "description": "Codex shared runtime test",
            "hooks": {
                "Stop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": (
                                    "python .ai/bootstrap-ai-project/"
                                    "hooks/claim-guard.py"
                                ),
                            }
                        ]
                    }
                ]
            },
        }
        for runtime in ("python", "node"):
            with self.subTest(runtime=runtime):
                temporary, target = self.make_target()
                try:
                    request = {
                        "target": str(target),
                        "operations": [
                            {
                                "id": "shared-runtime",
                                "type": "write",
                                "path": (
                                    ".ai/bootstrap-ai-project/"
                                    "hooks/claim-guard.py"
                                ),
                                "content": "#!/usr/bin/env python3\nprint('ok')\n",
                            },
                            {
                                "id": "codex-hooks",
                                "type": "write",
                                "path": ".codex/hooks.json",
                                "content": json.dumps(
                                    hooks, ensure_ascii=False, indent=2
                                )
                                + "\n",
                            },
                        ],
                    }
                    code, planned, stderr = run_cli(runtime, "plan", request)
                    self.assertEqual(0, code, stderr)
                    code, applied, stderr = run_cli(
                        runtime,
                        "apply",
                        request,
                        confirm=planned["plan_sha256"],
                    )
                    self.assertEqual(0, code, stderr)
                    self.assertTrue(applied["ok"])
                    code, verified, stderr = run_cli(runtime, "verify", request)
                    self.assertEqual(0, code, stderr)
                    self.assertTrue(verified["ok"])

                    invalid_args = json.loads(json.dumps(hooks))
                    invalid_args["hooks"]["Stop"][0]["hooks"][0]["args"] = []
                    missing_script = json.loads(json.dumps(hooks))
                    missing_script["hooks"]["Stop"][0]["hooks"][0][
                        "command"
                    ] = "python .ai/bootstrap-ai-project/hooks/missing.py"
                    invalid_event = json.loads(json.dumps(hooks))
                    invalid_event["hooks"]["PostToolUseFailure"] = (
                        invalid_event["hooks"].pop("Stop")
                    )
                    for invalid in (invalid_args, missing_script, invalid_event):
                        code, _, _ = run_cli(
                            runtime,
                            "plan",
                            {
                                "target": str(target),
                                "operations": [
                                    {
                                        "id": "invalid-codex-hooks",
                                        "type": "write",
                                        "path": ".codex/hooks.json",
                                        "content": json.dumps(invalid) + "\n",
                                    }
                                ],
                            },
                        )
                        self.assertEqual(3, code)
                finally:
                    temporary.cleanup()

    def test_invalid_hooks_and_json_fail_closed(self) -> None:
        temporary, target = self.make_target()
        try:
            invalid_requests = [
                {
                    "target": str(target),
                    "operations": [
                        {
                            "id": "matcher",
                            "type": "merge_json",
                            "path": ".claude/settings.json",
                            "patch": {
                                "hooks": {
                                    "Stop": [
                                        {
                                            "matcher": "always",
                                            "hooks": [
                                                {
                                                    "type": "command",
                                                    "command": "pwsh",
                                                    "args": [],
                                                }
                                            ],
                                        }
                                    ]
                                }
                            },
                        }
                    ],
                },
                {
                    "target": str(target),
                    "operations": [
                        {
                            "id": "args",
                            "type": "merge_json",
                            "path": ".claude/settings.json",
                            "patch": {
                                "hooks": {
                                    "Stop": [
                                        {
                                            "hooks": [
                                                {
                                                    "type": "command",
                                                    "command": "pwsh",
                                                }
                                            ]
                                        }
                                    ]
                                }
                            },
                        }
                    ],
                },
                {
                    "target": str(target),
                    "operations": [
                        {
                            "id": "missing-script",
                            "type": "merge_json",
                            "path": ".claude/settings.json",
                            "patch": {
                                "hooks": {
                                    "Stop": [
                                        {
                                            "hooks": [
                                                {
                                                    "type": "command",
                                                    "command": "pwsh",
                                                    "args": [
                                                        "-File",
                                                        "${CLAUDE_PROJECT_DIR}/.claude/hooks/missing.ps1",
                                                    ],
                                                }
                                            ]
                                        }
                                    ]
                                }
                            },
                        }
                    ],
                },
            ]
            for request in invalid_requests:
                codes = [
                    run_cli(runtime, "plan", request)[0]
                    for runtime in ("python", "node")
                ]
                self.assertEqual([3, 3], codes)

            settings = target / ".claude" / "settings.json"
            settings.parent.mkdir()
            settings.write_text("{invalid", encoding="UTF-8")
            request = {
                "target": str(target),
                "operations": [
                    {
                        "id": "invalid-json",
                        "type": "merge_json",
                        "path": ".claude/settings.json",
                        "patch": {"env": {"LANG": "C"}},
                    }
                ],
            }
            self.assertEqual(
                [3, 3],
                [
                    run_cli(runtime, "plan", request)[0]
                    for runtime in ("python", "node")
                ],
            )
        finally:
            temporary.cleanup()

    def test_gitignore_behavior_with_git(self) -> None:
        git = shutil.which("git")
        if not git:
            self.skipTest("Git 不可用")
        for runtime in ("python", "node"):
            temporary, target = self.make_target()
            try:
                xdg_config = Path(temporary.name) / "xdg-config"
                xdg_config.mkdir()
                git_env = {
                    **os.environ,
                    "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "XDG_CONFIG_HOME": str(xdg_config),
                }
                subprocess.run(
                    [git, "init", "-q", str(target)],
                    check=True,
                    capture_output=True,
                    timeout=20,
                    env=git_env,
                )
                request = {
                    "target": str(target),
                    "operations": [
                        {
                            "id": "ignore",
                            "type": "managed_gitignore",
                            "strategy": "ignore",
                        }
                    ],
                }
                code, planned, _ = run_cli(runtime, "plan", request)
                self.assertEqual(0, code)
                code, _, _ = run_cli(
                    runtime,
                    "apply",
                    request,
                    confirm=planned["plan_sha256"],
                )
                self.assertEqual(0, code)
                sample = target / ".claude" / "sample.json"
                sample.parent.mkdir()
                sample.write_text("{}\n", encoding="UTF-8")
                ignored = subprocess.run(
                    [git, "-C", str(target), "check-ignore", "-q", "--", ".claude/sample.json"],
                    check=False,
                    timeout=20,
                    env=git_env,
                )
                self.assertEqual(0, ignored.returncode)
                track_request = {
                    "target": str(target),
                    "operations": [
                        {
                            "id": "track",
                            "type": "managed_gitignore",
                            "strategy": "track",
                        }
                    ],
                }
                code, planned, _ = run_cli(runtime, "plan", track_request)
                self.assertEqual(0, code)
                code, _, _ = run_cli(
                    runtime,
                    "apply",
                    track_request,
                    confirm=planned["plan_sha256"],
                )
                self.assertEqual(0, code)
                tracked = subprocess.run(
                    [git, "-C", str(target), "check-ignore", "-q", "--", ".claude/sample.json"],
                    check=False,
                    timeout=20,
                    env=git_env,
                )
                self.assertEqual(1, tracked.returncode)
            finally:
                temporary.cleanup()

    def test_old_entry_and_copilot_template_are_absent(self) -> None:
        self.assertFalse((SKILL.parent / ("init-" + "project-docs")).exists())
        self.assertFalse((SKILL / "templates" / "copilot-instructions.md").exists())
        body = (SKILL / "SKILL.md").read_text(encoding="UTF-8")
        self.assertIn("只撰寫文件（預設）", body)
        spectra = (SKILL / "references" / "apply-spectra.md").read_text(
            encoding="UTF-8"
        )
        self.assertIn(".spectra.yaml", spectra)
        self.assertIn("openspec/config.yaml", spectra)
        self.assertIn("/spectra-apply", spectra)

    def test_apply_requires_confirmation_and_symlink_is_rejected(self) -> None:
        temporary, target = self.make_target()
        try:
            request = {
                "target": str(target),
                "operations": [
                    {
                        "id": "docs",
                        "type": "write",
                        "path": "docs/README.md",
                        "content": "# 文件\n",
                    }
                ],
            }
            for runtime in ("python", "node"):
                code, output, _ = run_cli(runtime, "apply", request)
                self.assertEqual(64, code)
                self.assertEqual(64, output["error"]["code"])

            outside = Path(temporary.name) / "outside"
            outside.mkdir()
            link = target / "linked"
            try:
                os.symlink(outside, link, target_is_directory=True)
            except (OSError, NotImplementedError):
                return
            link_request = {
                "target": str(target),
                "operations": [
                    {
                        "id": "escape",
                        "type": "write",
                        "path": "linked/file.md",
                        "content": "blocked\n",
                    }
                ],
            }
            for runtime in ("python", "node"):
                code, _, _ = run_cli(runtime, "plan", link_request)
                self.assertEqual(4, code)
            self.assertFalse((outside / "file.md").exists())
        finally:
            temporary.cleanup()

    def test_plan_confirmation_is_target_bound(self) -> None:
        left_temp, left = self.make_target()
        right_temp, right = self.make_target()
        try:
            left_request = {
                "target": str(left),
                "operations": [
                    {
                        "id": "docs",
                        "type": "write",
                        "path": "docs/README.md",
                        "content": "# 文件\n",
                    }
                ],
            }
            right_request = {**left_request, "target": str(right)}
            for runtime in ("python", "node"):
                code, planned, _ = run_cli(runtime, "plan", left_request)
                self.assertEqual(0, code)
                code, _, _ = run_cli(
                    runtime,
                    "apply",
                    right_request,
                    confirm=planned["plan_sha256"],
                )
                self.assertEqual(4, code)
                self.assertFalse((right / "docs" / "README.md").exists())
        finally:
            left_temp.cleanup()
            right_temp.cleanup()

    def test_exception_type_and_overlapping_paths_fail_closed(self) -> None:
        temporary, target = self.make_target()
        try:
            invalid_exception = {
                "target": str(target),
                "secret_exceptions": "generic-secret-assignment",
                "operations": [
                    {
                        "id": "docs",
                        "type": "write",
                        "path": "docs/README.md",
                        "content": "password=fixture-password-value\n",
                    }
                ],
            }
            null_exception = {
                **invalid_exception,
                "secret_exceptions": None,
            }
            overlap = {
                "target": str(target),
                "operations": [
                    {
                        "id": "child",
                        "type": "write",
                        "path": "created/a.txt",
                        "content": "a\n",
                    },
                    {
                        "id": "parent",
                        "type": "write",
                        "path": "created",
                        "content": "b\n",
                    },
                ],
            }
            for runtime in ("python", "node"):
                code, _, _ = run_cli(runtime, "plan", invalid_exception)
                self.assertEqual(3, code)
                code, _, _ = run_cli(runtime, "plan", null_exception)
                self.assertEqual(3, code)
                code, _, _ = run_cli(runtime, "plan", overlap)
                self.assertEqual(4, code)
            self.assertFalse((target / "created").exists())
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
